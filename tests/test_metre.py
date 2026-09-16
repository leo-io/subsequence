"""A time signature's unit sets the bar, the counter counts it, and accents follow its groups (#2738)."""

import ast
import logging
import pathlib
import random
import sys
import types
import typing
import unittest.mock

import pytest

import subsequence
import subsequence.conductor
import subsequence.metre
import subsequence.pattern
import subsequence.pattern_builder
import subsequence.sequence_utils
import subsequence.sequencer


PACKAGE = pathlib.Path(subsequence.__file__).resolve().parent


def _builder (time_signature: typing.Tuple[int, int], length: float, grid: int, **arguments: typing.Any) -> subsequence.pattern_builder.PatternBuilder:

	"""A builder over a *length*-beat pattern of *grid* steps, in *time_signature*."""

	pattern = subsequence.pattern.Pattern(channel=0, length=length)

	return subsequence.pattern_builder.PatternBuilder(pattern, cycle=0, default_grid=grid, time_signature=time_signature, **arguments)


# --- the definition ------------------------------------------------------------------

@pytest.mark.parametrize("time_signature, bar_beats", [
	((4, 4), 4.0), ((3, 4), 3.0), ((6, 8), 3.0), ((7, 8), 3.5), ((12, 8), 6.0),
	((2, 2), 4.0), ((3, 2), 6.0), ((5, 16), 1.25), ((1, 1), 4.0), ((9, 32), 1.125),
])
def test_a_bar_is_beats_times_four_over_the_unit_wherever_it_is_read (patch_midi: None, time_signature: typing.Tuple[int, int], bar_beats: float) -> None:

	"""The composition, its sequencer and a builder all publish the same bar."""

	composition = subsequence.Composition(output_device="Dummy MIDI", time_signature=time_signature)
	builder = _builder(time_signature, length=4, grid=16)

	assert subsequence.metre.bar_beats(time_signature) == bar_beats
	assert (composition.bar_beats, composition.sequencer.bar_beats, builder.bar_beats) == (bar_beats, bar_beats, bar_beats)


@pytest.mark.parametrize("unit", subsequence.metre.UNITS)
@pytest.mark.parametrize("beats", range(1, 33))
def test_every_allowed_metre_has_a_bar_and_a_unit_of_whole_pulses (beats: int, unit: int) -> None:

	"""So nothing that counts bars or units in pulses ever rounds."""

	assert subsequence.metre.pulses_per_bar((beats, unit)) * unit == beats * 96
	assert subsequence.metre.pulses_per_unit((beats, unit)) * unit == 96


@pytest.mark.parametrize("time_signature", [
	pytest.param((4, 3), id="a unit of three"),
	pytest.param((4, 0), id="a unit of zero"),
	pytest.param((4, 64), id="a unit finer than a thirty-second"),
	pytest.param((0, 4), id="no beats"),
	pytest.param((-3, 4), id="negative beats"),
	pytest.param((4.0, 4), id="a float beat count"),
	pytest.param((4, 4.0), id="a float unit"),
	pytest.param((True, 4), id="a bool"),
	pytest.param((4,), id="one number"),
	pytest.param((4, 4, 4), id="three numbers"),
	pytest.param("4/4", id="a string"),
	pytest.param(4, id="a bare number"),
])
def test_a_metre_the_bar_cannot_be_built_from_is_refused_at_construction (patch_midi: None, time_signature: typing.Any) -> None:

	"""Loudly, and before playback, by the composition, the sequencer and a builder alike."""

	with pytest.raises(ValueError, match="time signature"):
		subsequence.Composition(output_device="Dummy MIDI", time_signature=time_signature)

	with pytest.raises(ValueError, match="time signature"):
		subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", time_signature=time_signature)

	with pytest.raises(ValueError, match="time signature"):
		_builder(time_signature, length=4, grid=16)


def test_a_list_is_taken_as_the_tuple_it_spells () -> None:

	"""A time signature read from JSON arrives as a list, and is kept as a tuple."""

	assert subsequence.metre.check([6, 8]) == (6, 8)


# --- nothing reads the tuple by index but the definition ------------------------------

def _indexed_reads (source: str) -> typing.List[int]:

	"""The line of every ``time_signature[...]`` in *source*, however the name is reached."""

	lines = []

	for node in ast.walk(ast.parse(source)):

		if not isinstance(node, ast.Subscript):
			continue

		value = node.value
		name = value.attr if isinstance(value, ast.Attribute) else value.id if isinstance(value, ast.Name) else None

		if name == "time_signature":
			lines.append(node.lineno)

	return sorted(lines)


def test_the_guard_finds_an_indexed_read_however_it_is_spelled () -> None:

	"""Attribute, bare name, chained and sliced, so the next test's silence means something."""

	source = "a = self.time_signature[0]\nb = time_signature[1]\nc = comp.sequencer.time_signature[0] * 24\nd = x.time_signature[:1]\ne = time_signature\n"

	assert _indexed_reads(source) == [1, 2, 3, 4]


def test_nothing_outside_the_definition_reads_a_time_signature_by_index () -> None:

	"""A bar is ``bar_beats``, a count of units is unpacked by name, and only metre.py does the sum."""

	files = sorted(path for path in PACKAGE.rglob("*.py") if path.name != "metre.py")
	offenders = [f"{path.relative_to(PACKAGE)}:{line}" for path in files for line in _indexed_reads(path.read_text())]

	assert len(files) > 40
	assert offenders == []


# --- the bar -------------------------------------------------------------------------

def _render_notes (composition: subsequence.Composition, bars: int, tmp_path: pathlib.Path) -> typing.List[int]:

	"""Render and return the pulse of every note_on sent, in order."""

	onsets: typing.List[int] = []
	original = subsequence.sequencer.Sequencer._dispatch_with_compensation

	def _record (self: subsequence.sequencer.Sequencer, event: subsequence.sequencer.MidiEvent) -> None:
		if event.message_type == 'note_on':
			onsets.append(event.pulse)
		original(self, event)

	with unittest.mock.patch.object(subsequence.sequencer.Sequencer, "_dispatch_with_compensation", _record):
		composition.render(bars=bars, filename=str(tmp_path / "metre.mid"))

	return onsets


def test_a_bar_of_seven_eighths_is_eighty_four_pulses_for_lengths_bars_and_the_form (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""bars=1 is 3.5 beats, p.bar counts a bar every 84 pulses, and a render of three bars stops after three."""

	composition = subsequence.Composition(output_device="Dummy MIDI", time_signature=(7, 8))
	seen: typing.List[typing.Tuple[int, int, float, int]] = []

	@composition.pattern(channel=1, bars=1)
	def downbeats (p: typing.Any) -> None:
		seen.append((p.cycle, p.bar, p._pattern.length, p.grid))
		p.note(60, beat=0)

	onsets = _render_notes(composition, 3, tmp_path)

	assert onsets == [0, 84, 168]
	assert seen[:3] == [(0, 0, 3.5, 14), (1, 1, 3.5, 14), (2, 2, 3.5, 14)]


def test_a_bpm_ramp_of_two_bars_lasts_two_bars_of_the_metre (patch_midi: None) -> None:

	"""Two bars of 7/8 is 168 pulses, not 336."""

	sequencer = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", initial_bpm=120, time_signature=(7, 8))
	sequencer.set_target_bpm(140, bars=2)

	assert sequencer._bpm_transition is not None
	assert sequencer._bpm_transition.total_pulses == 168


def test_a_signal_is_read_where_the_bar_starts (patch_midi: None) -> None:

	"""Bar 2 of 6/8 starts at beat 6.0, so a ramp over twelve beats reads halfway."""

	conductor = subsequence.conductor.Conductor()
	conductor.line("rise", start_val=0.0, end_val=1.0, duration_beats=12)
	builder = _builder((6, 8), length=3, grid=12, conductor=conductor, bar=2)

	assert builder.signal("rise") == pytest.approx(0.5)


def test_a_phrase_aligned_to_the_section_starts_where_the_section_s_bar_does () -> None:

	"""The second bar of a 6/8 section is three beats in, so it places what offset=3 places from the start."""

	phrase = subsequence.Phrase([subsequence.Motif.degrees([1, 2, 3, 4]), subsequence.Motif.degrees([5, 6, 7, 8])])

	class SecondBar:
		name = "verse"
		bar = 1

	def placed (**arguments: typing.Any) -> typing.List[typing.Tuple[int, int]]:
		builder = _builder((6, 8), length=3, grid=12, key="A", scale="minor", rng=random.Random(1), **{k: v for k, v in arguments.items() if k == "section"})
		builder.phrase(phrase, root=60, **{k: v for k, v in arguments.items() if k != "section"})
		return [(pulse, note.pitch) for pulse in sorted(builder._pattern.steps) for note in builder._pattern.steps[pulse].notes]

	aligned = placed(section=SecondBar(), align="section")

	assert aligned
	assert aligned == placed(offset=3.0)
	assert aligned != placed(offset=6.0)

def test_a_transition_mute_defaults_to_one_bar_of_the_metre (patch_midi: None) -> None:

	"""In 6/8 the default mute window is three beats."""

	composition = subsequence.Composition(output_device="Dummy MIDI", time_signature=(6, 8))
	composition.transition(before="chorus", mute=["hats"])

	assert composition._transitions[0].beats == 3.0


def test_a_bar_shorter_than_a_beat_plays_once_its_patterns_fit_it (patch_midi: None, tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture) -> None:

	"""3/16 with harmony: a note and a chord every 18 pulses, and no warning about a lookahead no pattern set."""

	composition = subsequence.Composition(output_device="Dummy MIDI", key="C", seed=7, time_signature=(3, 16))
	composition.harmony(style="functional_major")

	@composition.pattern(channel=1, bars=1, reschedule_lookahead=0.25)
	def downbeats (p: typing.Any) -> None:
		p.note(60, beat=0)

	with caplog.at_level(logging.WARNING):
		onsets = _render_notes(composition, 4, tmp_path)

	assert onsets == [0, 18, 36, 54]
	assert [(start, end) for start, end, _ in composition._harmony_horizon._spans][:4] == [(0.0, 0.75), (0.75, 1.5), (1.5, 2.25), (2.25, 3.0)]
	assert [record.getMessage() for record in caplog.records if "reschedule_lookahead" in record.getMessage()] == []


def test_harmony_alone_in_a_short_bar_warns_of_no_pattern (patch_midi: None, tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture) -> None:

	"""With no patterns there is no pattern lookahead to warn about, whatever the bar."""

	composition = subsequence.Composition(output_device="Dummy MIDI", key="C", seed=7, time_signature=(1, 8))
	composition.harmony(style="functional_major")

	with caplog.at_level(logging.WARNING):
		composition.render(bars=2, filename=str(tmp_path / "harmony.mid"))

	assert composition._harmony_horizon._spans, "the clock laid down no chords, so the render never reached the check"
	assert [record.getMessage() for record in caplog.records if "reschedule_lookahead" in record.getMessage()] == []

def test_a_pattern_whose_lookahead_outlasts_a_short_bar_is_told_what_to_set (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""A one-bar pattern of 3/16 keeps the default one-beat lookahead, and the refusal names the number that fits."""

	composition = subsequence.Composition(output_device="Dummy MIDI", time_signature=(3, 16))

	@composition.pattern(channel=1, bars=1)
	def downbeats (p: typing.Any) -> None:
		p.note(60, beat=0)

	with pytest.raises(ValueError, match=r"set reschedule_lookahead= to 0\.75 or less"):
		_render_notes(composition, 1, tmp_path)

# --- the counter ---------------------------------------------------------------------

@pytest.mark.parametrize("time_signature, per_bar", [
	pytest.param((4, 4), [0, 1, 2, 3], id="4/4"),
	pytest.param((3, 4), [0, 1, 2], id="3/4"),
	pytest.param((6, 8), [0, 1, 2, 3, 4, 5], id="6/8"),
	pytest.param((7, 8), [0, 1, 2, 3, 4, 5, 6], id="7/8"),
	pytest.param((2, 2), [0, 1], id="2/2"),
])
def test_the_beat_counter_counts_the_written_unit (patch_midi: None, tmp_path: pathlib.Path, time_signature: typing.Tuple[int, int], per_bar: typing.List[int]) -> None:

	"""Two bars of 6/8 count 1–6 twice, which is what Live and Logic show; 4/4 and 3/4 are unchanged."""

	composition = subsequence.Composition(output_device="Dummy MIDI", time_signature=time_signature)
	beats: typing.List[int] = []
	bars: typing.List[int] = []
	composition.on_event("beat", beats.append)
	composition.on_event("bar", bars.append)

	@composition.pattern(channel=1, bars=1)
	def downbeats (p: typing.Any) -> None:
		p.note(60, beat=0)

	_render_notes(composition, 2, tmp_path)

	assert bars == [0, 1]
	assert beats == per_bar * 2


# --- the accents ---------------------------------------------------------------------

def _before_2738 (time_signature: typing.Tuple[int, int], grid: int) -> typing.List[float]:

	"""build_metric_weights as it was, where only the beat count shaped the table."""

	beats = time_signature[0]
	weights = []

	for i in range(grid):
		numerator = i * beats
		if i == 0:
			weights.append(1.0)
		elif beats % 2 == 0 and 2 * i == grid:
			weights.append(0.75)
		elif numerator % grid == 0:
			weights.append(0.5)
		elif (2 * numerator) % grid == 0:
			weights.append(0.25)
		else:
			weights.append(0.125)

	return weights


@pytest.mark.parametrize("beats", range(1, 17))
def test_every_quarter_note_metre_keeps_the_accents_it_had (beats: int) -> None:

	"""No piece in /4 hears a single accent move, at any grid."""

	for grid in range(1, 97):
		assert subsequence.sequence_utils.build_metric_weights((beats, 4), grid) == _before_2738((beats, 4), grid), grid


@pytest.mark.parametrize("time_signature, grid, weights", [
	pytest.param((6, 8), 6, [1.0, 0.25, 0.25, 0.75, 0.25, 0.25], id="6/8 in eighths: 3+3"),
	pytest.param((6, 8), 12, [1.0, 0.125, 0.25, 0.125, 0.25, 0.125, 0.75, 0.125, 0.25, 0.125, 0.25, 0.125], id="6/8 in sixteenths"),
	pytest.param((9, 8), 9, [1.0, 0.25, 0.25, 0.5, 0.25, 0.25, 0.5, 0.25, 0.25], id="9/8: 3+3+3"),
	pytest.param((12, 8), 12, [1.0, 0.25, 0.25, 0.5, 0.25, 0.25, 0.75, 0.25, 0.25, 0.5, 0.25, 0.25], id="12/8: half-bar group 0.75"),
	pytest.param((5, 8), 5, [1.0, 0.25, 0.5, 0.25, 0.25], id="5/8: 2+3"),
	pytest.param((7, 8), 7, [1.0, 0.25, 0.5, 0.25, 0.5, 0.25, 0.25], id="7/8: 2+2+3"),
	pytest.param((11, 8), 11, [1.0, 0.25, 0.5, 0.25, 0.5, 0.25, 0.5, 0.25, 0.5, 0.25, 0.25], id="11/8: 2+2+2+2+3"),
	pytest.param((3, 8), 3, [1.0, 0.5, 0.5], id="3/8 is simple: each unit a beat"),
	pytest.param((2, 2), 8, [1.0, 0.125, 0.25, 0.125, 0.75, 0.125, 0.25, 0.125], id="2/2 accents its halves"),
])
def test_other_units_accent_the_metre_s_own_pulses (time_signature: typing.Tuple[int, int], grid: int, weights: typing.List[float]) -> None:

	"""Compound metres group in threes, irregular ones in twos with a three at the end."""

	assert subsequence.sequence_utils.build_metric_weights(time_signature, grid) == weights


def test_a_custom_weight_list_still_overrides_the_metre () -> None:

	"""7/8 felt as 3+2+2 is a list, not a guess: syncopation reads it, not the default."""

	three_two_two = [1.0, 0.25, 0.25, 0.5, 0.25, 0.5, 0.25]

	assert subsequence.sequence_utils.syncopation([3], 7, time_signature=(7, 8), weights=three_two_two) == 0.5
	assert subsequence.sequence_utils.syncopation([3], 7, time_signature=(7, 8)) == 0.75


# --- chords, Link --------------------------------------------------------------------

@pytest.mark.parametrize("time_signature, cycle_beats, span", [
	pytest.param((3, 4), None, 3.0, id="3/4 changes every bar"),
	pytest.param((6, 8), None, 3.0, id="6/8 changes every three quarter notes"),
	pytest.param((4, 4), None, 4.0, id="4/4 unchanged"),
	pytest.param((3, 4), 6, 6.0, id="an explicit cycle wins"),
])
def test_chords_change_once_a_bar_by_default (patch_midi: None, tmp_path: pathlib.Path, time_signature: typing.Tuple[int, int], cycle_beats: typing.Optional[int], span: float) -> None:

	"""Every chord the clock laid down starts on its cycle and lasts it."""

	composition = subsequence.Composition(output_device="Dummy MIDI", key="C", seed=7, time_signature=time_signature)
	composition.harmony(style="functional_major", cycle_beats=cycle_beats)

	@composition.pattern(channel=1, bars=1)
	def downbeats (p: typing.Any) -> None:
		p.note(60, beat=0)

	_render_notes(composition, 8, tmp_path)
	spans = composition._harmony_horizon._spans

	assert len(spans) >= 4
	assert all(start % span == 0 and end - start == span for start, end, _ in spans), spans


def test_freeze_captures_a_chord_a_bar_by_default (patch_midi: None) -> None:

	"""In 3/4, two frozen chords are two spans of three beats."""

	composition = subsequence.Composition(output_device="Dummy MIDI", key="C", seed=7, time_signature=(3, 4))
	composition.harmony(style="functional_major")

	assert [span.beats for span in composition.freeze(bars=2).spans] == [3.0, 3.0]


@pytest.mark.parametrize("time_signature, quantum, expected", [
	pytest.param((7, 8), None, 3.5, id="7/8 aligns on its bar"),
	pytest.param((4, 4), None, 4.0, id="4/4 unchanged"),
	pytest.param((7, 8), 4, 4.0, id="an explicit quantum wins"),
])
def test_link_aligns_peers_on_the_bar_by_default (patch_midi: None, time_signature: typing.Tuple[int, int], quantum: typing.Optional[float], expected: float) -> None:

	"""The Link quantum is the bar unless one is given."""

	composition = subsequence.Composition(output_device="Dummy MIDI", time_signature=time_signature)

	with unittest.mock.patch.dict(sys.modules, {"aalink": types.ModuleType("aalink")}):
		composition.link() if quantum is None else composition.link(quantum=quantum)

	assert composition._link_quantum == expected


# --- steps per beat ------------------------------------------------------------------

def test_a_ghost_curve_finds_the_beat_in_a_bar_of_three () -> None:

	"""A 12-step bar of 3/4 has four steps a beat, so the & is steps 2, 6 and 10 — not 1, 4, 7 and 10."""

	offbeat = subsequence.pattern_builder.PatternBuilder.build_ghost_bias(12, "offbeat", beats=3)

	assert [step for step, weight in enumerate(offbeat) if weight == 1.0] == [2, 6, 10]
	assert [step for step, weight in enumerate(offbeat) if weight == 0.05] == [0, 4, 8]


def test_thinning_by_strength_drops_the_weakest_steps_of_a_bar_of_three (patch_midi: None) -> None:

	"""Every e and a (the odd steps) goes at full amount; the grid // 4 reading dropped steps 2, 5, 8 and 11 instead."""

	builder = _builder((3, 4), length=3, grid=12, rng=random.Random(3))
	builder.hit_steps(60, list(range(12)))
	builder.thin(strategy="strength", amount=1.0)

	kept = sorted(pulse // 6 for pulse in builder._pattern.steps)

	assert kept, "thinning at full amount kept nothing, so this cannot tell the readings apart"
	assert all(step % 2 == 0 for step in kept), kept

