"""Beats become whole pulses without float noise pushing a note a pulse early (#2549).

A third of a beat is not exact in binary floating point, so seven of them come
to ``55.99999999999999`` pulses, and ``int()`` floored that to 55: the eighth of
twelve hi-hats in a bar sounded a pulse (about 21 ms at 120 BPM) early, and a
seven-step triplet pattern's cycle ran a pulse short.  Sixteenths are exact and
were never affected.
"""

import ast
import fractions
import pathlib
import typing

import pytest

import subsequence
import subsequence.constants.durations as dur
import subsequence.constants.pulses
import subsequence.pattern
import subsequence.pattern_builder
import subsequence.sequencer


PACKAGE = pathlib.Path(subsequence.__file__).parent

# Step lengths whose size in pulses is whole, as the constants spell them.
WHOLE_PULSE_STEPS = [
	("thirty-second", dur.THIRTYSECOND, fractions.Fraction(1, 8)),
	("sixteenth", dur.SIXTEENTH, fractions.Fraction(1, 4)),
	("dotted sixteenth", dur.DOTTED_SIXTEENTH, fractions.Fraction(3, 8)),
	("triplet eighth", dur.TRIPLET_EIGHTH, fractions.Fraction(1, 3)),
	("triplet sixteenth", dur.TRIPLET_EIGHTH / 2, fractions.Fraction(1, 6)),
	("triplet thirty-second", dur.TRIPLET_EIGHTH / 4, fractions.Fraction(1, 12)),
	("eighth", dur.EIGHTH, fractions.Fraction(1, 2)),
	("triplet quarter", dur.TRIPLET_QUARTER, fractions.Fraction(2, 3)),
	("quarter", dur.QUARTER, fractions.Fraction(1, 1)),
]


def _builder (length: float, grid: int) -> typing.Tuple[subsequence.pattern.Pattern, subsequence.pattern_builder.PatternBuilder]:

	"""A bare pattern of *length* beats and a builder over it with *grid* steps."""

	pattern = subsequence.pattern.Pattern(channel=0, length=length)

	return pattern, subsequence.pattern_builder.PatternBuilder(pattern, cycle=0, default_grid=grid)


def test_float_noise_lands_on_the_whole_pulse_and_a_real_fraction_still_truncates () -> None:

	"""Only a value a hair from a whole pulse moves; anything else keeps ``int()``'s answer."""

	to_pulses = subsequence.constants.pulses.beats_to_pulses

	assert to_pulses(7 * dur.TRIPLET_EIGHTH) == 56
	assert to_pulses(5 * (2.0 / 6)) == 40
	assert to_pulses(2.25) == 54
	assert to_pulses(4.5 / 24) == 4
	assert to_pulses(13.5 / 24) == 13
	assert to_pulses(0.99 / 24) == 0
	assert to_pulses(-7 * dur.TRIPLET_EIGHTH) == -56
	assert to_pulses(-4.5 / 24) == -4
	assert to_pulses(1.0, pulses_per_beat=96) == 96


@pytest.mark.parametrize("name,step_beats,exact", WHOLE_PULSE_STEPS, ids=[row[0] for row in WHOLE_PULSE_STEPS])
def test_every_step_of_a_step_mode_pattern_lands_on_its_own_pulse (name: str, step_beats: float, exact: fractions.Fraction) -> None:

	"""``steps=n, step_duration=d`` places step i at exactly i × d, for every n up to 32."""

	step_pulses = int(exact * 24)
	wrong: typing.List[typing.Tuple[int, int, int]] = []

	for steps in range(1, 33):

		pattern, builder = _builder(steps * step_beats, steps)
		builder.hit_steps(60, list(range(steps)))

		positions = sorted(pattern.steps)
		assert len(positions) == steps, (steps, positions)

		wrong.extend((steps, i, pulse) for i, pulse in enumerate(positions) if pulse != i * step_pulses)

	assert not wrong, f"(steps, step, pulse) off their pulse: {wrong[:6]}"


@pytest.mark.parametrize("grid", [3, 6, 12, 24, 48])
def test_a_triplet_grid_in_a_bar_puts_every_step_on_its_pulse (grid: int) -> None:

	"""Twelve hats across a 4/4 bar are all on the beat grid, the eighth included."""

	pattern, builder = _builder(4.0, 16)
	builder.hit_steps(42, list(range(grid)), grid=grid)

	assert sorted(pattern.steps) == [i * (96 // grid) for i in range(grid)]


def test_a_grid_that_really_falls_between_pulses_keeps_its_positions () -> None:

	"""Sixteen steps over three beats is 4.5 pulses a step: those still truncate as before."""

	pattern, builder = _builder(3.0, 16)
	builder.hit_steps(60, list(range(16)))

	assert sorted(pattern.steps) == [int(i * 4.5) for i in range(16)]


def test_events_placed_at_a_computed_triplet_beat_land_on_its_pulse () -> None:

	"""CC, program change and OSC take the same conversion as notes."""

	pattern, builder = _builder(4.0, 12)
	beat = 7 * dur.TRIPLET_EIGHTH

	builder.cc(1, 64, beat=beat)
	builder.program_change(5, beat=beat)
	builder.osc("/cue", 1, beat=beat)
	builder.note(60, beat=beat)

	assert [event.pulse for event in pattern.cc_events] == [56, 56]
	assert [event.pulse for event in pattern.osc_events] == [56]
	assert sorted(pattern.steps) == [56]


@pytest.mark.parametrize("name,step_beats,exact", WHOLE_PULSE_STEPS, ids=[row[0] for row in WHOLE_PULSE_STEPS])
def test_a_step_mode_cycle_is_exactly_its_steps_long (name: str, step_beats: float, exact: fractions.Fraction) -> None:

	"""The sequencer schedules ``steps × step_duration`` as that many whole pulses, for every n up to 32."""

	sequencer = subsequence.sequencer.Sequencer.__new__(subsequence.sequencer.Sequencer)
	sequencer.pulses_per_beat = 24

	wrong = []

	for steps in range(1, 33):
		length_pulses, _ = sequencer._get_schedule_timing(steps * step_beats, 0)
		if length_pulses != steps * int(exact * 24):
			wrong.append((steps, length_pulses))

	assert not wrong, f"(steps, cycle pulses) not whole steps long: {wrong[:6]}"


def test_a_seven_step_triplet_pattern_stays_on_its_cycle (patch_midi: None, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:

	"""Played through a composition, each cycle starts 56 pulses after the last — no drift."""

	onsets: typing.List[int] = []
	original = subsequence.sequencer.Sequencer._dispatch_with_compensation

	def _record (self: subsequence.sequencer.Sequencer, event: subsequence.sequencer.MidiEvent) -> None:
		if event.message_type == 'note_on':
			onsets.append(event.pulse)
		original(self, event)

	monkeypatch.setattr(subsequence.sequencer.Sequencer, "_dispatch_with_compensation", _record)

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	@composition.pattern(channel=1, steps=7, step_duration=dur.TRIPLET_EIGHTH, reschedule_lookahead=0.25)
	def seven (p: typing.Any) -> None:
		p.hit_steps(60, [0])

	composition.render(bars=4, filename=str(tmp_path / "seven.mid"))

	assert len(onsets) >= 6, onsets
	assert onsets == [cycle * 56 for cycle in range(len(onsets))]


def _name_of (node: ast.AST) -> typing.Optional[str]:

	"""The name a node spells: an attribute, a variable, or a string key such as ``state["pulses_per_beat"]``."""

	if isinstance(node, ast.Constant) and isinstance(node.value, str):
		return node.value

	if isinstance(node, ast.Attribute):
		return node.attr

	return getattr(node, "id", None)


def _truncating_pulse_conversions (source: str) -> typing.List[int]:

	"""Line numbers where ``int()`` is applied straight to a product with the pulse rate."""

	lines = []

	for node in ast.walk(ast.parse(source)):

		if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "int" and len(node.args) == 1):
			continue

		argument = node.args[0]

		if not isinstance(argument, ast.BinOp):
			continue

		names = {_name_of(child) for child in ast.walk(argument)}

		if names & {"MIDI_QUARTER_NOTE", "pulses_per_beat", "pulses_per_quarter", "ppq"}:
			lines.append(node.lineno)

	return lines


def test_no_module_converts_beats_to_pulses_with_a_bare_int () -> None:

	"""Every conversion goes through ``beats_to_pulses``, so a new one cannot bring the flooring back."""

	offenders = {
		str(path.relative_to(PACKAGE)): lines
		for path in sorted(PACKAGE.rglob("*.py"))
		if (lines := _truncating_pulse_conversions(path.read_text()))
	}

	assert not offenders, f"use subsequence.constants.pulses.beats_to_pulses: {offenders}"


def test_the_bare_int_guard_recognises_what_it_forbids () -> None:

	"""The guard would catch each spelling the package used, and passes the helper."""

	assert _truncating_pulse_conversions("x = int(beat * subsequence.constants.MIDI_QUARTER_NOTE)") == [1]
	assert _truncating_pulse_conversions("x = int(length_beats * self.pulses_per_beat)") == [1]
	assert _truncating_pulse_conversions("x = int(float(result) * self.pulses_per_beat)") == [1]
	assert _truncating_pulse_conversions("lo, hi = int(beat * ppq), int((beat + span) * ppq)") == [1, 1]
	assert _truncating_pulse_conversions('x = int(pattern.length * state["pulses_per_beat"])') == [1]
	assert _truncating_pulse_conversions("x = beats_to_pulses(beat)") == []
	assert _truncating_pulse_conversions("x = int(round(beat * pulses_per_beat))") == []
