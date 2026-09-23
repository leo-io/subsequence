"""Motif.generate() spells its degrees against its own scale (#3460, Simon's calls on #3423).

Its degrees were always spelled against the nearer of major and minor, so a line
placed in a composition using its own scale played wrong notes: three in four of a
minor pentatonic line, a tenth of a mixolydian one.  A named scale is now the scale
its degrees count in, so the line is exact there, and under any other scale it maps
degree for degree, like a typed motif.  An interval list stays a mask over major or
minor, as it was, unless it is exactly a built-in scale.

"Exact" is measured against the walk itself: the same walk over the same pitches
given as an explicit MIDI pool returns the notes it chose, and the degrees placed
in the scale must land on exactly those.
"""

import random
import typing

import pytest

import subsequence
import subsequence.intervals
import subsequence.pattern
import subsequence.pattern_builder
from subsequence.motifs import Degree
from subsequence.motifs import Motif as M

RHYTHM = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5]
MODES = [
	"ionian", "minor", "dorian", "phrygian", "lydian", "mixolydian", "locrian", "harmonic_minor",
	"melodic_minor", "major_pentatonic", "minor_pentatonic", "hirajoshi", "in_sen", "iwato", "yo", "egyptian",
]


def _placed_in (m: M, scale: str) -> typing.List[int]:

	"""The MIDI notes a motif places in C in *scale*, with no chord to snap to."""

	pattern = subsequence.pattern.Pattern(channel=0, length=m.length)
	builder = subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=0, key="C", scale=scale, rng=random.Random(1))
	builder.motif(m, root=60)

	return [note.pitch for pulse in sorted(pattern.steps) for note in pattern.steps[pulse].notes]


def _walked (intervals: typing.Sequence[int], seed: int) -> typing.List[int]:

	"""The notes the walk chooses over these intervals, read straight off an explicit MIDI pool."""

	pool = [60 + octave * 12 + interval for octave in (0, 1) for interval in intervals if octave * 12 + interval <= 19]

	return [event.pitch for event in M.generate(rhythm=RHYTHM, scale=pool, seed=seed).events]


@pytest.mark.parametrize("mode", MODES)
def test_a_line_is_exact_in_a_composition_using_its_scale (mode: str) -> None:

	"""Every built-in scale: the degrees, placed in that scale, are the notes the walk chose.

	Spelled against major or minor, only the major, minor, dorian and lydian
	lines came out exact; the rest played from 10% to 77% wrong notes.
	"""

	intervals = subsequence.intervals.scale_pitch_classes(0, mode)

	for seed in range(20):
		line = M.generate(rhythm=RHYTHM, scale=mode, seed=seed)

		assert _placed_in(line, mode) == _walked(intervals, seed), f"{mode}, seed {seed}"


def test_an_interval_list_is_still_a_mask () -> None:

	"""``[0, 4, 7]`` in a C major piece plays C, E and G, exactly the notes the walk chose (Simon's call).

	This passed before #3460 as well: an interval list keeps its spelling
	against the nearer of major and minor.
	"""

	for seed in range(20):
		line = M.generate(rhythm=RHYTHM, scale=[0, 4, 7], seed=seed)

		assert _placed_in(line, "ionian") == _walked([0, 4, 7], seed)


def test_a_registered_scale_does_not_turn_a_mask_into_a_scale () -> None:

	"""A custom scale registered as [0, 4, 7] leaves the list [0, 4, 7] a mask: registrations are process-wide."""

	subsequence.register_scale("test_triad_mask_3460", [0, 4, 7])

	for seed in range(20):
		line = M.generate(rhythm=RHYTHM, scale=[0, 4, 7], seed=seed)

		assert _placed_in(line, "ionian") == _walked([0, 4, 7], seed)


def test_a_list_that_is_a_built_in_scale_is_spelled_as_that_scale () -> None:

	"""``[0, 3, 5, 7, 10]`` walks and spells exactly as ``"minor_pentatonic"`` does."""

	for seed in range(20):
		assert M.generate(rhythm=RHYTHM, scale=[0, 3, 5, 7, 10], seed=seed) == M.generate(rhythm=RHYTHM, scale="minor_pentatonic", seed=seed)


def test_an_open_cadence_closes_on_the_fifth_whichever_step_holds_it () -> None:

	"""The open half cadence closes on the fifth: step 4 of a pentatonic scale, step 5 of a seven-note one.

	Degree 5 of a minor pentatonic scale is its flat seventh, where a
	literal reading of the cadence's degree would have closed.
	"""

	for seed in range(20):
		pentatonic = M.generate(rhythm=RHYTHM, scale="minor_pentatonic", cadence="open", seed=seed)
		major = M.generate(rhythm=RHYTHM, scale="ionian", cadence="open", seed=seed)

		assert pentatonic.events[-1].pitch.step == 4
		assert _placed_in(pentatonic, "minor_pentatonic")[-1] % 12 == 7
		assert major.events[-1].pitch == Degree(5)
