"""Motif.generate(state=) walks in the state's key, and 0 to 12 in scale= are intervals (#3456).

With a state, the walk kept the state's key for its closure rule - the tonic is
a stable landing point - but built and spelled its candidates from C at 60.  So
an A state's closure aimed at A, degree 6 of that pool, and its lines closed on
degree 6 more and on the tonic less than a C state's.  The pool, the pins and
the spelling now count from the state's tonic, so a state in any key walks as
a state in C does, a key apart.

And a scale list was read as MIDI notes unless it began on 0 and stopped below
12, so [0, 7, 12] and [2, 4, 7, 9] placed MIDI notes 0 to 12, far below hearing.
"""

import random
import typing

import pytest

import subsequence
import subsequence.pattern
import subsequence.pattern_builder
from subsequence.motifs import Degree
from subsequence.motifs import Motif as M

RHYTHM = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5]


def _state (key: str, mode: str = "ionian", history: typing.Sequence[int] = ()) -> subsequence.MelodicState:

	"""A state that leans hard on its closure rule, so its key shows in the line."""

	state = subsequence.MelodicState(key=key, mode=mode, nir_strength=1.0)
	state.history = list(history)

	return state


def _pitch_classes (m: M) -> typing.Set[int]:

	"""The pitch classes a degree motif sounds in C major."""

	pattern = subsequence.pattern.Pattern(channel=0, length=m.length)
	builder = subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=0, key="C", scale="ionian", rng=random.Random(1))
	builder.motif(m, root=60)

	return {note.pitch % 12 for step in pattern.steps.values() for note in step.notes}


@pytest.mark.parametrize(("key", "mode", "scale"), [("A", "aeolian", "minor"), ("G", "ionian", None), ("F#", "ionian", None)])
def test_a_state_in_any_key_walks_as_a_state_in_c_does (key: str, mode: str, scale: typing.Optional[str]) -> None:

	"""Same seed, same dials, a different key: the same line of degrees.

	Before, 17 of these 50 A-minor lines differed from the C-minor ones (22
	in G, 11 in F sharp), because each state's closure rule pulled towards
	its own tonic inside a pool spelled from C.
	"""

	for seed in range(50):
		there = M.generate(rhythm=RHYTHM, scale=scale, state=_state(key, mode), seed=seed)
		home = M.generate(rhythm=RHYTHM, scale=scale, state=_state("C", mode), seed=seed)

		assert there == home, f"seed {seed}: {there.describe()} against {home.describe()}"

		# A pinned close lands on the state's own tonic too.
		closed = M.generate(rhythm=RHYTHM, scale=scale, state=_state(key, mode), end_on=1, seed=seed)

		assert closed == M.generate(rhythm=RHYTHM, scale=scale, state=_state("C", mode), end_on=1, seed=seed)
		assert closed.events[-1].pitch == Degree(1)


def test_a_history_played_in_another_register_walks_as_it_would_beside_the_pool () -> None:

	"""C2 D2 E2 continues as C4 D4 E4 would: the gesture carries over, not its register.

	Before, 35 of these 50 lines differed: the walk read a two-octave leap
	from the history to the pool that nobody played.
	"""

	for seed in range(50):
		low = M.generate(rhythm=RHYTHM, state=_state("C", history=[36, 38, 40]), seed=seed)
		beside = M.generate(rhythm=RHYTHM, state=_state("C", history=[60, 62, 64]), seed=seed)

		assert low == beside, f"seed {seed}"


def test_a_history_already_beside_the_pool_stays_where_it_is () -> None:

	"""A line that last played E5, inside the pool's span, is not moved to E4.

	This passed before #3456 as well: it pins that only a history outside the
	pool moves, so a C state played in its usual register walks as it did.
	"""

	high = [M.generate(rhythm=RHYTHM, state=_state("C", history=[72, 74, 76]), seed=seed) for seed in range(20)]
	low = [M.generate(rhythm=RHYTHM, state=_state("C", history=[60, 62, 64]), seed=seed) for seed in range(20)]

	assert high != low


def test_without_a_state_the_walk_is_unchanged () -> None:

	"""With no state the tonic is C at 60, as it always was: this line predates #3456 exactly."""

	line = M.generate(rhythm=[0, 1, 1.5, 1.75, 2.5], contour="arch", end_on=1, seed=7)

	assert [event.pitch for event in line.events] == GOLDEN_NO_STATE


@pytest.mark.parametrize(("scale", "classes"), [
	([0, 7, 12], {0, 7}),
	([2, 4, 7, 9], {2, 4, 7, 9}),
	([0, 4, 7, 12], {0, 4, 7}),
])
def test_a_list_from_0_to_12_is_intervals (scale: typing.List[int], classes: typing.Set[int]) -> None:

	"""Values from 0 to 12 are intervals above the tonic, 12 the octave; they come back as degrees.

	[0, 7, 12] and [2, 4, 7, 9] were taken for MIDI notes, and placed as such.
	"""

	for seed in range(10):
		line = M.generate(rhythm=RHYTHM, scale=scale, seed=seed)

		assert all(isinstance(event.pitch, Degree) for event in line.events)
		assert _pitch_classes(line) <= classes


def test_a_major_scale_with_its_octave_is_the_major_scale () -> None:

	"""[0, 2, 4, 5, 7, 9, 11, 12] walks exactly as scale="ionian" does."""

	for seed in range(10):
		assert M.generate(rhythm=RHYTHM, scale=[0, 2, 4, 5, 7, 9, 11, 12], seed=seed) == M.generate(rhythm=RHYTHM, scale="ionian", seed=seed)


def test_a_list_mixing_intervals_and_midi_notes_is_refused () -> None:

	"""[0, 7, 14] is neither: 14 is past the octave, and 0 and 7 are far below any real note."""

	with pytest.raises(ValueError, match="mixes intervals"):
		M.generate(rhythm=RHYTHM, scale=[0, 7, 14], seed=1)


# Measured on main at b6bbd05, before #3456: ^3 ^6 ^4+ ^5 ^1.
GOLDEN_NO_STATE: typing.List[Degree] = [Degree(3), Degree(6), Degree(4, octave=1), Degree(5), Degree(1)]
