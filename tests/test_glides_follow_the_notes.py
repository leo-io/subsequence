"""Glides and tunings are laid against the notes where they finally sit, whatever moved them and in whatever order (#2792)."""

import logging
import pathlib
import typing

import mido
import pytest

import subsequence
import subsequence.pattern
import subsequence.pattern_builder
import subsequence.tuning

# Sixteen sixteenths of an acid line; steps 3, 7, 11 and 15 are the slide
# targets, each the second sixteenth of its beat, so swing moves every one.
STEPS = list(range(16))
PITCHES = [36, 43, 48, 51] * 4
TARGETS = [3, 7, 11, 15]


def _render (composition: subsequence.Composition, tmp_path: pathlib.Path, name: str) -> typing.List[typing.Tuple[int, str]]:

	"""Render one bar and return the file's (tick, label) timeline, meta messages left out."""

	path = str(tmp_path / f"{name}.mid")
	composition.render(bars=1, filename=path)

	now = 0
	timeline = []

	for message in mido.MidiFile(path).tracks[0]:
		now += message.time
		if message.type in ("note_on", "note_off"):
			timeline.append((now, f"{message.type} {message.note}"))
		elif message.type == "pitchwheel":
			timeline.append((now, "bend 0" if message.pitch == 0 else "bend"))

	assert timeline, "the render placed nothing"

	return timeline


def _at (timeline: typing.List[typing.Tuple[int, str]], tick: int) -> typing.List[str]:

	"""What the file says at *tick*, in order."""

	return [label for when, label in timeline if when == tick]


def _acid (build: typing.Callable[[typing.Any], None], tmp_path: pathlib.Path, name: str) -> typing.List[typing.Tuple[int, str]]:

	"""Render the acid line with *build* doing the rest of the pattern's work."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	@composition.pattern(channel=2, beats=4)
	def acid (p: typing.Any) -> None:
		p.sequence(steps=STEPS, pitches=PITCHES, durations=0.2)
		build(p)

	return _render(composition, tmp_path, name)


@pytest.mark.parametrize("percent, late", [(57, 1), (67, 2), (75, 3)])
def test_a_slide_lands_on_its_swung_target_whichever_is_called_first (patch_midi: None, tmp_path: pathlib.Path, percent: int, late: int) -> None:

	"""Slide then swing, or swing then slide by step: the same glide, ending as the swung target sounds."""

	def slide_then_swing (p: typing.Any) -> None:
		p.slide(steps=TARGETS, time=0.5, bend_range=12)
		p.swing(percent)

	def swing_then_slide (p: typing.Any) -> None:
		p.swing(percent)
		p.slide(steps=TARGETS, time=0.5, bend_range=12)

	first = _acid(slide_then_swing, tmp_path, "slide_then_swing")
	second = _acid(swing_then_slide, tmp_path, "swing_then_slide")

	assert first == second

	for target in TARGETS:
		straight = target * 120
		swung = straight + late * 20
		assert _at(first, swung) == ["note_off 48", "bend", "bend 0", "note_on 51"], target
		assert "bend 0" not in _at(first, straight) and not any(label.startswith("note_on") for label in _at(first, straight)), target


def test_portamento_glides_into_each_swung_note_whichever_is_called_first (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Each glide's reset lands with the note it leads into, where the swing put it."""

	def glide_then_swing (p: typing.Any) -> None:
		p.portamento(time=0.5, bend_range=12)
		p.swing(57)

	def swing_then_glide (p: typing.Any) -> None:
		p.swing(57)
		p.portamento(time=0.5, bend_range=12)

	first = _acid(glide_then_swing, tmp_path, "glide_then_swing")
	second = _acid(swing_then_glide, tmp_path, "swing_then_glide")

	assert first == second

	# Steps 1 and 3 are swung a pulse late, to ticks 140 and 380: each glide
	# resets as its note sounds, and nothing happens where it used to be.
	assert _at(first, 140) == ["bend 0", "note_on 43"]
	assert _at(first, 380) == ["bend 0", "note_on 51"]
	assert _at(first, 120) == [] and _at(first, 360) == []


def test_a_tuning_bends_each_note_where_the_groove_moved_it (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Tuned then swung: each swung note's tuning bend arrives with it, not a pulse ahead while the last note still sounds."""

	def tune_then_swing (p: typing.Any) -> None:
		p.apply_tuning(subsequence.tuning.Tuning.equal(19), bend_range=2.0, reference_note=48)
		p.swing(57)

	timeline = _acid(tune_then_swing, tmp_path, "tune_then_swing")

	at_swung = _at(timeline, 140)

	assert len(at_swung) >= 2 and at_swung[-1].startswith("note_on") and at_swung[-2].startswith("bend"), at_swung
	assert _at(timeline, 120) == []


def test_a_tuned_slide_is_the_same_whichever_is_called_first (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""The tuning shifts the slide's bends into the tuned pitch space in either order."""

	nineteen = subsequence.tuning.Tuning.equal(19)

	def tune_then_slide (p: typing.Any) -> None:
		p.apply_tuning(nineteen, bend_range=12, reference_note=48)
		p.slide(notes=TARGETS, time=0.5, bend_range=12)

	def slide_then_tune (p: typing.Any) -> None:
		p.slide(notes=TARGETS, time=0.5, bend_range=12)
		p.apply_tuning(nineteen, bend_range=12, reference_note=48)

	tuned = _acid(tune_then_slide, tmp_path, "tune_then_slide")

	assert tuned == _acid(slide_then_tune, tmp_path, "slide_then_tune")

	# The slide's reset into note 3 (tick 360) is retuned to that note's
	# offset, so the target sounds in tune rather than at plain 12-TET.
	assert "bend 0" not in _at(tuned, 360) and _at(tuned, 360)[-1].startswith("note_on"), _at(tuned, 360)


def test_a_glide_s_bad_arguments_are_refused_at_the_call () -> None:

	"""A glide is laid when the build finishes, but a mistake in how it was asked for is still refused where it was written."""

	builder = subsequence.pattern_builder.PatternBuilder(pattern=subsequence.pattern.Pattern(channel=0, length=4), cycle=0)

	with pytest.raises(ValueError):
		builder.slide(notes=[1], shape="wobble")

	with pytest.raises(ValueError, match="resolution must be at least 1 pulse"):
		builder.portamento(resolution=0)

	assert builder._pending_glides == []


def test_a_slide_by_step_says_once_when_no_note_falls_on_any_of_its_steps (caplog: pytest.LogCaptureFixture) -> None:

	"""Steps 1 and 5 of a part that plays on 0, 4, 8 and 12: nothing slides, and it is said."""

	builder = subsequence.pattern_builder.PatternBuilder(pattern=subsequence.pattern.Pattern(channel=0, length=4), cycle=0, default_grid=16)
	builder.sequence(steps=[0, 4, 8, 12], pitches=[40, 42, 40, 43])

	with caplog.at_level(logging.WARNING, logger="subsequence.pattern_midi"):
		builder.slide(steps=[1, 5])
		builder._finish_build()

	assert [e for e in builder._pattern.cc_events if e.message_type == "pitchwheel"] == []
	assert "slides into steps [1, 5], but no note falls on any of them, so it did not slide" in caplog.text


def test_a_triggered_one_shot_slides_too (patch_midi: None, monkeypatch: pytest.MonkeyPatch) -> None:

	"""trigger() finishes its build as a pattern's rebuild does, so a one-shot's slide is laid."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)
	scheduled: typing.List[subsequence.pattern.Pattern] = []

	monkeypatch.setattr(composition, "_schedule_one_shot", lambda pattern, start_pulse: scheduled.append(pattern))

	def riff (p: typing.Any) -> None:
		p.sequence(steps=[0, 4, 8, 12], pitches=[40, 42, 40, 43])
		p.slide(notes=[1])

	composition.trigger(riff, channel=2, beats=4)

	(pattern,) = scheduled

	bends = [e.pulse for e in pattern.cc_events if e.message_type == "pitchwheel"]

	assert bends and max(bends) == 24, bends
