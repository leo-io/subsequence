"""invert() keeps its first note where it is, and a line can go below the tonic (#3453).

``Motif.invert()`` pivoted on the first note's scale step alone, so a first note
with an octave or an accidental moved: ``[^3+, ^5, ^1]`` dropped its first note two
octaves.  And a ``Degree`` could not sit below the tonic, so ``transpose(steps=-1)``
raised on a melody as plain as 1 2 3, and ``invert()`` refused every line that
starts on the tonic and rises.  Placement always resolved a step of 0 or below:
the step under the tonic, an octave down.

What a flattened first note does was Simon's call: it stays, and the mirror keeps
to the key (E♭ G C becomes E♭ C G).

All of these are in C major at root 60 unless they say otherwise.
"""

import random
import typing

import pytest

import subsequence
import subsequence.pattern
import subsequence.pattern_builder
from subsequence.motifs import Degree
from subsequence.motifs import Motif as M
from subsequence.motifs import Phrase as P


def _midi (m: M, key: str = "C", scale: str = "ionian") -> typing.List[int]:

	"""The MIDI notes a motif places, in order."""

	pattern = subsequence.pattern.Pattern(channel=0, length=m.length)
	builder = subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=0, key=key, scale=scale, rng=random.Random(1))
	builder.motif(m, root=60)

	return [note.pitch for pulse in sorted(pattern.steps) for note in pattern.steps[pulse].notes]


def test_invert_keeps_a_first_note_an_octave_up_where_it_is () -> None:

	"""The first note is the pivot, its octave included.

	Pivoting on its step alone put E5 at E3: [76, 67, 60] became [52, 60, 67].
	"""

	line = subsequence.motif([Degree(3, octave=1), 5, 1])

	assert _midi(line) == [76, 67, 60]
	assert _midi(line.invert()) == [76, 84, 91]


def test_invert_keeps_a_first_note_an_octave_down_where_it_is () -> None:

	"""A first note below the home octave stays below it; it used to rise 24 semitones."""

	line = subsequence.motif([Degree(5, octave=-1), 1, 3])

	assert _midi(line.invert())[0] == 55


def test_invert_keeps_a_flattened_first_note_and_the_key () -> None:

	"""E♭ G C becomes E♭ C G: the first note stays, and the mirrored notes are the key's own.

	Its flat used to flip to a sharp, so the line began on F (65).
	"""

	line = subsequence.motif([Degree(3, chroma=-1), 5, 1])

	assert _midi(line) == [63, 67, 60]
	assert _midi(line.invert()) == [63, 60, 67]


def test_invert_flips_the_other_accidentals () -> None:

	"""Off the pivot's step, a sharp mirrors to a flat, as it always has: F sharp around E is D flat."""

	line = subsequence.motif([3, Degree(4, chroma=1)])

	assert _midi(line.invert()) == [64, 61]


def test_a_line_that_starts_on_the_tonic_and_rises_can_be_inverted () -> None:

	"""1 2 3 mirrors to 1 0 -1, C B A: it used to raise "below the tonic"."""

	assert _midi(subsequence.motif([1, 2, 3]).invert()) == [60, 59, 57]
	assert _midi(subsequence.motif([1, 3, 5]).invert()) == [60, 57, 53]


@pytest.mark.parametrize(("degrees", "steps", "expected"), [
	([1, 2, 3], -1, [59, 60, 62]),
	([3, 2, 1], -2, [60, 59, 57]),
	([5, 6, 5, 3], -3, [62, 64, 62, 59]),
	([1, 2, 3], -7, [48, 50, 52]),
])
def test_transpose_down_goes_below_the_tonic (degrees: typing.List[int], steps: int, expected: typing.List[int]) -> None:

	"""A line transposed down past the tonic keeps going; each of these raised."""

	assert _midi(subsequence.motif(degrees).transpose(steps=steps)) == expected


@pytest.mark.parametrize(("key", "scale", "expected"), [("C", "ionian", 59), ("C", "minor_pentatonic", 58), ("A", "aeolian", 55)])
def test_the_step_below_the_tonic_is_the_top_of_the_scale_an_octave_down (key: str, scale: str, expected: int) -> None:

	"""Degree(0) is the scale's last step under the tonic, in any scale."""

	assert _midi(M.degrees([Degree(0)]), key=key, scale=scale) == [expected]


def test_phrase_invert_keeps_its_first_note_where_it_is () -> None:

	"""A phrase inverts every segment around its first note, octave included."""

	phrase = P([subsequence.motif([Degree(3, octave=1), 5]), subsequence.motif([1])])

	assert _midi(phrase.invert().flatten()) == [76, 84, 91]


def test_a_degree_pivot_can_be_given () -> None:

	"""``invert(pivot=Degree(5))`` mirrors around G; an int pivot still means a scale step."""

	line = subsequence.motif([1, 3, 5])

	assert _midi(line.invert(pivot=Degree(5))) == [74, 71, 67]
	assert line.invert(pivot=5) == line.invert(pivot=Degree(5))


def test_inverting_twice_gives_back_the_motif () -> None:

	"""The mirror is its own inverse, octaves and accidentals included."""

	line = M.degrees([Degree(3, chroma=-1), Degree(4, chroma=1), Degree(6, octave=-1), 3, Degree(1, octave=1)])

	assert line.invert().invert() == line


def test_a_motif_of_midi_notes_and_degrees_refuses_to_invert () -> None:

	"""One pivot cannot mirror both, so it says so instead of making notes nothing can place.

	Around MIDI 60, degrees 5 and 3 became steps 115 and 117.
	"""

	with pytest.raises(TypeError, match="both"):
		(M.degrees([5, 3]) & M.notes([60])).invert()


def test_midi_notes_refuse_a_degree_pivot () -> None:

	"""A scale degree has no MIDI number until a key resolves it."""

	with pytest.raises(TypeError, match="scale degree"):
		M.notes([60, 64]).invert(pivot=Degree(1))
