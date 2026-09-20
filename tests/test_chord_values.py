"""A chord's intervals belong to the chord, and an inversion stays playable (#3042).

Two ways a chord handed back something that was not a chord.

`Chord.intervals()` returned `CHORD_INTERVALS[quality]` — the library's own
list object. Anything a caller did to it happened to every chord of that
quality for the life of the process: appending a ninth to one C major gave
every major chord a ninth, including ones built afterwards, which in a live
session means until the rig restarts. Nothing raised.

`invert_chord` raised the moved note by exactly one octave, which is right for
a chord narrower than an octave and wrong for anything wider. A ninth spans 14
semitones, so `[0, 4, 7, 11, 14]` inverted came back `[4, 7, 11, 14, 12]` —
the moved note below the ninth it was meant to clear — and `[0, 4, 7, 12]`
came back `[4, 7, 12, 12]`, the same pitch twice, where one note_off ends
both.
"""

import typing

import pytest

import subsequence
import subsequence.chords
import subsequence.voicings


# ---------------------------------------------------------------------------
# The list belongs to the chord
# ---------------------------------------------------------------------------

def test_a_chord_does_not_hand_out_the_librarys_own_list () -> None:

	"""The identity check, which is what the bug actually was."""

	chord = subsequence.chords.Chord("C", "major")

	assert chord.intervals() is not subsequence.chords.CHORD_INTERVALS["major"]


def test_changing_one_chords_intervals_leaves_every_other_chord_alone () -> None:

	"""The consequence a musician would meet: every major chord grew a ninth."""

	mine = subsequence.chords.Chord("C", "major").intervals()

	mine.append(14)

	assert subsequence.chords.Chord("G", "major").intervals() == [0, 4, 7]
	assert subsequence.chords.Chord("F", "major").intervals() == [0, 4, 7]
	assert subsequence.chords.CHORD_INTERVALS["major"] == [0, 4, 7]


def test_two_calls_on_the_same_chord_are_independent () -> None:

	"""A fresh list each time, not one cached copy handed out twice."""

	chord = subsequence.chords.Chord("C", "major")

	first = chord.intervals()
	second = chord.intervals()

	assert first == second
	assert first is not second


def test_an_unknown_quality_still_refuses () -> None:

	"""The control: copying must not turn a bad quality into an empty chord."""

	with pytest.raises(ValueError, match = "quality"):
		subsequence.chords.Chord("C", "not_a_quality").intervals()


# ---------------------------------------------------------------------------
# An inversion is still a chord
# ---------------------------------------------------------------------------

WIDE_CHORDS = [
	[0, 4, 7, 11, 14],			# major ninth
	[0, 4, 7, 12],				# a triad with its octave doubled
	[0, 3, 7, 10, 14, 17],		# minor eleventh
	[0, 4, 7, 10, 14, 21],		# thirteenth
]


@pytest.mark.parametrize("intervals", WIDE_CHORDS)
@pytest.mark.parametrize("inversion", [1, 2, 3])
def test_an_inversion_is_sorted (intervals: typing.List[int], inversion: int) -> None:

	"""An inversion moves the bottom note to the TOP, so the result stays in order."""

	voiced = subsequence.voicings.invert_chord(list(intervals), inversion)

	assert voiced == sorted(voiced), f"invert_chord({intervals}, {inversion}) -> {voiced}"


@pytest.mark.parametrize("intervals", WIDE_CHORDS)
@pytest.mark.parametrize("inversion", [1, 2, 3])
def test_an_inversion_sounds_every_note_once (intervals: typing.List[int], inversion: int) -> None:

	"""A doubled pitch on one channel is one note_off away from a hanging note."""

	voiced = subsequence.voicings.invert_chord(list(intervals), inversion)

	assert len(voiced) == len(set(voiced)), f"invert_chord({intervals}, {inversion}) -> {voiced}"


@pytest.mark.parametrize("intervals", WIDE_CHORDS)
@pytest.mark.parametrize("inversion", [1, 2, 3])
def test_an_inversion_keeps_the_chord_it_was (intervals: typing.List[int], inversion: int) -> None:

	"""Same pitch classes, same count — only the voicing moved."""

	voiced = subsequence.voicings.invert_chord(list(intervals), inversion)

	assert len(voiced) == len(intervals)
	assert sorted(p % 12 for p in voiced) == sorted(p % 12 for p in intervals)


def test_the_documented_triad_examples_are_unchanged () -> None:

	"""The control. Lifting further must not move a chord that never needed it."""

	assert subsequence.voicings.invert_chord([0, 4, 7], 0) == [0, 4, 7]
	assert subsequence.voicings.invert_chord([0, 4, 7], 1) == [4, 7, 12]
	assert subsequence.voicings.invert_chord([0, 4, 7], 2) == [7, 12, 16]


def test_a_moved_note_clears_the_chord_rather_than_rising_forever () -> None:

	"""It lifts by octaves until it is on top, and then stops.

	Without this, "sorted and unique" would also be satisfied by lifting
	everything into the ceiling, which would be a different bug.
	"""

	voiced = subsequence.voicings.invert_chord([0, 4, 7, 11, 14], 1)

	assert voiced == [4, 7, 11, 14, 24]


def test_an_empty_chord_and_a_whole_turn_still_behave () -> None:

	"""Edges the rewrite must not have dropped."""

	assert subsequence.voicings.invert_chord([], 1) == []
	assert subsequence.voicings.invert_chord([0, 4, 7], 3) == [0, 4, 7]
