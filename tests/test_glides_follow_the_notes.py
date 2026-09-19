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


# ---------------------------------------------------------------------------
# The Direct Pattern API (#2959)
# ---------------------------------------------------------------------------

class _HandBuilt (subsequence.pattern.Pattern):

	"""A pattern built the way examples/demo_advanced.py builds one: a PatternBuilder of its own, rebuilt each cycle."""

	def __init__ (self, build: typing.Callable[[subsequence.pattern_builder.PatternBuilder], None]) -> None:

		super().__init__(channel=0, length=4)
		self._build_with = build
		self.on_reschedule()

	def on_reschedule (self) -> None:

		self.steps = {}
		self.cc_events = []
		p = subsequence.pattern_builder.PatternBuilder(self, cycle=0)
		p.note(60, beat=0, duration=1)
		p.note(62, beat=1, duration=1)
		self._build_with(p)


async def _queued_bends (pattern: subsequence.pattern.Pattern, start_pulse: int = 0) -> typing.List[typing.Tuple[int, int]]:

	"""Schedule *pattern* on a bare sequencer and return the (pulse, value) of every pitch bend it queued."""

	seq = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", initial_bpm=120)
	await seq.schedule_pattern(pattern, start_pulse)

	notes = [event for event in seq.event_queue if event.message_type == "note_on"]
	assert len(notes) == 2, "the pattern's notes were not scheduled"

	return sorted((event.pulse, event.value) for event in seq.event_queue if event.message_type == "pitchwheel")


@pytest.mark.asyncio
async def test_a_hand_built_pattern_glides (patch_midi: None) -> None:

	"""portamento() on a builder made by hand is laid when the pattern is scheduled: it rises through the last half beat of 60 into 62."""

	bends = await _queued_bends(_HandBuilt(lambda p: p.portamento(time=0.5, wrap=False)))
	rise = [value for pulse, value in bends if 12 <= pulse < 24]

	assert rise, "no glide was laid"
	assert rise == sorted(rise) and rise[-1] > 7500


@pytest.mark.asyncio
async def test_a_hand_built_pattern_is_tuned (patch_midi: None) -> None:

	"""apply_tuning() on a builder made by hand bends each tuned note as the pattern is scheduled."""

	bends = await _queued_bends(_HandBuilt(lambda p: p.apply_tuning(subsequence.tuning.Tuning.equal(19))))

	assert (24, 1078) in bends


@pytest.mark.asyncio
async def test_a_hand_built_pattern_glides_again_each_cycle (patch_midi: None) -> None:

	"""The next cycle's builder is finished when that cycle is scheduled, as the first one was."""

	pattern = _HandBuilt(lambda p: p.portamento(time=0.5, wrap=False))
	await _queued_bends(pattern)
	pattern.on_reschedule()

	bends = await _queued_bends(pattern, start_pulse=96)
	rise = [value for pulse, value in bends if 108 <= pulse < 120]

	assert rise and rise == sorted(rise) and rise[-1] > 7500
	assert all(pulse >= 96 for pulse, _ in bends)


def test_the_engine_leaves_nothing_for_the_sequencer_to_finish (patch_midi: None) -> None:

	"""A decorated pattern's build is finished by the engine, so its pattern holds no unfinished build."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	@composition.pattern(channel=1, beats=4)
	def lead (p: typing.Any) -> None:
		p.note(60, beat=0, duration=1)
		p.note(62, beat=1, duration=1)
		p.portamento(time=0.5)

	pattern = composition._build_pattern_from_pending(composition._pending_patterns[0])

	assert any(event.message_type == "pitchwheel" for event in pattern.cc_events), "the engine laid no glide"
	assert pattern._unfinished_builds == []


def test_a_failed_build_leaves_nothing_to_lay (patch_midi: None) -> None:

	"""A builder that raises after asking for a glide is emptied, deferred work included, so the sequencer lays nothing against it."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	@composition.pattern(channel=1, beats=4)
	def lead (p: typing.Any) -> None:
		p.note(60, beat=0, duration=1)
		p.portamento(time=0.5)
		raise RuntimeError("a typo in the builder")

	pattern = composition._build_pattern_from_pending(composition._pending_patterns[0])

	assert pattern.steps == {} and pattern.cc_events == []
	assert pattern._unfinished_builds == []
