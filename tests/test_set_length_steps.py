"""``set_length(steps=…)``: a pattern shortened while it plays keeps the size of its steps (#2546)."""

import inspect
import pathlib
import typing

import pytest

import subsequence
import subsequence.constants.durations as dur
import subsequence.constants.pulses
import subsequence.pattern
import subsequence.pattern_builder
import subsequence.sequencer


def _bar_builder (repeating: bool = False, lookahead: float = 1) -> typing.Tuple[subsequence.pattern.Pattern, subsequence.pattern_builder.PatternBuilder]:

	"""A sixteen-step, four-beat pattern and a builder over it."""

	pattern = subsequence.pattern.Pattern(channel=0, length=4, reschedule_lookahead=lookahead)

	return pattern, subsequence.pattern_builder.PatternBuilder(pattern, cycle=0, default_grid=16, repeating=repeating)


def _render_onsets (composition: subsequence.Composition, bars: int, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> typing.List[int]:

	"""Render *bars* bars and return the pulse of every note_on sent, in order."""

	onsets: typing.List[int] = []
	original = subsequence.sequencer.Sequencer._dispatch_with_compensation

	def _record (self: subsequence.sequencer.Sequencer, event: subsequence.sequencer.MidiEvent) -> None:
		if event.message_type == 'note_on':
			onsets.append(event.pulse)
		original(self, event)

	monkeypatch.setattr(subsequence.sequencer.Sequencer, "_dispatch_with_compensation", _record)
	composition.render(bars=bars, filename=str(tmp_path / "render.mid"))

	return onsets


def test_a_step_count_keeps_each_step_its_size_and_moves_the_grid () -> None:

	"""Twelve steps of a sixteen-step bar are twelve sixteenths, and what counts steps counts twelve."""

	pattern, builder = _bar_builder()

	builder.set_length(steps=12)
	builder.euclidean(36, pulses=3)

	assert pattern.length == 3.0
	assert builder.grid == 12
	assert sorted(pattern.steps) == [0, 24, 48]


def test_a_length_in_beats_still_keeps_the_grid () -> None:

	"""The beats form keeps its meaning: same steps, squeezed to the new length."""

	pattern, builder = _bar_builder()

	builder.set_length(3)

	assert pattern.length == 3
	assert builder.grid == 16


def test_a_step_count_after_a_length_in_beats_counts_the_declared_step () -> None:

	"""A squeeze does not change what a step is: steps=12 after set_length(3) is still three beats."""

	pattern, builder = _bar_builder()

	builder.set_length(3)
	builder.set_length(steps=12)

	assert pattern.length == 3.0
	assert builder.grid == 12


@pytest.mark.parametrize("call", [
	pytest.param({"length": 3, "steps": 12}, id="both"),
	pytest.param({}, id="neither"),
	pytest.param({"steps": 0}, id="zero steps"),
	pytest.param({"steps": -4}, id="negative steps"),
	pytest.param({"steps": 2.5}, id="fractional steps"),
	pytest.param({"steps": True}, id="a bool"),
	pytest.param({"length": 0}, id="zero beats"),
	pytest.param({"length": 0.01}, id="under a pulse"),
])
def test_set_length_refuses_what_it_cannot_honour_and_changes_nothing (call: typing.Dict[str, typing.Any]) -> None:

	"""Each refusal is a ValueError that leaves the length and the grid as they were."""

	pattern, builder = _bar_builder()

	with pytest.raises(ValueError):
		builder.set_length(**call)

	assert pattern.length == 4
	assert builder.grid == 16


def test_a_repeating_pattern_is_refused_a_length_its_lookahead_would_run_past () -> None:

	"""Three sixteenths is under a one-beat lookahead; four is exactly it and allowed."""

	pattern, builder = _bar_builder(repeating=True, lookahead=1)

	with pytest.raises(ValueError, match="reschedule_lookahead"):
		builder.set_length(steps=3)

	with pytest.raises(ValueError, match="reschedule_lookahead"):
		builder.set_length(0.5)

	assert pattern.length == 4
	assert builder.grid == 16

	builder.set_length(steps=4)

	assert pattern.length == 1.0


def test_a_one_shot_may_be_shorter_than_a_lookahead_it_never_uses () -> None:

	"""trigger() and fills build with repeating=False, so a short one-shot is not refused."""

	pattern, builder = _bar_builder(repeating=False, lookahead=1)

	builder.set_length(0.5)

	assert pattern.length == 0.5


def test_steps_is_a_keyword_named_steps () -> None:

	"""Superconductor detects the step form by this parameter, so its name and kind are a contract."""

	parameter = inspect.signature(subsequence.pattern_builder.PatternBuilder.set_length).parameters["steps"]

	assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
	assert parameter.default is None


def test_a_lookahead_equal_to_a_triplet_length_is_scheduled_not_refused () -> None:

	"""Five triplet eighths, with a lookahead of 5/3, compare equal in pulses though not in floats."""

	sequencer = subsequence.sequencer.Sequencer.__new__(subsequence.sequencer.Sequencer)
	sequencer.pulses_per_beat = 24

	assert 5 * dur.TRIPLET_EIGHTH < 5 / 3
	assert sequencer._get_schedule_timing(5 * dur.TRIPLET_EIGHTH, 5 / 3) == (40, 40)


def test_a_step_count_carries_into_later_cycles (patch_midi: None, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:

	"""Set once on the first cycle, the twelve steps hold: every later build sees grid 12 and three beats."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)
	seen: typing.List[typing.Tuple[int, int, float]] = []

	@composition.pattern(channel=1, beats=4)
	def hats (p: typing.Any) -> None:
		seen.append((p.cycle, p.grid, p._pattern.length))
		if p.cycle == 0:
			p.set_length(steps=12)
		p.hit_steps(42, [0])

	onsets = _render_onsets(composition, 4, tmp_path, monkeypatch)

	assert len(seen) >= 4
	assert seen[0] == (0, 16, 4)
	assert all(grid == 12 and length == 3.0 for _, grid, length in seen[1:]), seen
	assert onsets[:5] == [0, 72, 144, 216, 288]


def test_a_step_count_counts_the_declared_step_across_cycles (patch_midi: None, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:

	"""A squeeze on one cycle does not redefine the step for a later steps= call."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)
	lengths: typing.List[float] = []

	@composition.pattern(channel=1, beats=4)
	def squeezed (p: typing.Any) -> None:
		if p.cycle == 0:
			p.set_length(3)
		elif p.cycle == 1:
			p.set_length(steps=12)
		lengths.append(p._pattern.length)
		p.hit_steps(42, [0])

	_render_onsets(composition, 3, tmp_path, monkeypatch)

	assert lengths[:2] == [3, 3.0]


def test_a_step_mode_pattern_counts_in_its_own_step (patch_midi: None, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:

	"""Declared as six eighths, four steps is two beats — and seven triplet eighths is 56 whole pulses."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	@composition.pattern(channel=1, steps=6, step_duration=dur.EIGHTH, reschedule_lookahead=0.5)
	def eighths (p: typing.Any) -> None:
		p.set_length(steps=4)
		p.hit_steps(60, [0])

	@composition.pattern(channel=2, steps=8, step_duration=dur.TRIPLET_EIGHTH, reschedule_lookahead=dur.TRIPLET_EIGHTH)
	def triplets (p: typing.Any) -> None:
		p.set_length(steps=7)
		p.hit_steps(62, [0])

	onsets = _render_onsets(composition, 4, tmp_path, monkeypatch)
	eighths_pattern = composition._running_patterns["eighths"]
	triplets_pattern = composition._running_patterns["triplets"]

	assert (subsequence.constants.pulses.beats_to_pulses(eighths_pattern.length), eighths_pattern._default_grid) == (48, 4)
	assert (subsequence.constants.pulses.beats_to_pulses(triplets_pattern.length), triplets_pattern._default_grid) == (56, 7)
	assert set(onsets) >= {0, 48, 96, 144} | {56, 112, 168, 224}


def test_a_refused_length_costs_one_cycle_not_the_pattern (patch_midi: None, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:

	"""A build that asks for too short a length is silent once, then the pattern plays on at its old length.

	Before the refusal the length was stored, every later rebuild failed, and
	the pattern stayed silent until something set a longer one.
	"""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	@composition.pattern(channel=1, beats=4, reschedule_lookahead=1)
	def once_too_short (p: typing.Any) -> None:
		p.hit_steps(36, [0])
		if p.cycle == 1:
			p.set_length(steps=2)

	onsets = _render_onsets(composition, 4, tmp_path, monkeypatch)

	assert onsets == [0, 192, 288]
