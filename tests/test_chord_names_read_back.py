"""Every chord label the library prints reads back as the same chord (#3014).

``ChordSpan.label()`` writes decorated names - a quality tail after the number (``C7sus4``,
``Cm9b5``, ``C+maj7``), named extensions on the end (``Cadd9``, ``Cm6``), a bass after a slash
(``C/E``) - and ``progression([...])`` refused all of them: of 2475 labels over every built-in
quality, extension and bass, 126 read back.  A progression shown on a display, logged, or sent to a
control surface could not be pasted back in.

Measuring the round trip also found labels the printer got wrong, which now read back as the chords
they are: a major-seventh sus4 printed as ``C7sus4``, a 6th was taken for a diminished seventh
(``C76`` for Cmaj7 with a 6th), and a 7 glued onto a name ending in one read as another number.

``C+7`` is still refused, and ``C+9`` keeps its reading: what an augmented chord's number means is
the ``C+9`` question on #3012, not settled here.
"""

import itertools
import typing

import pytest

import subsequence
import subsequence.chords
import subsequence.progressions


# The built-in qualities, named here: other tests register their own into the shared table.
_QUALITIES = (
	"major", "minor", "diminished", "augmented", "dominant_7th", "major_7th",
	"minor_7th", "half_diminished_7th", "diminished_7th", "sus2", "sus4",
)


def _read (name: str) -> subsequence.progressions.ChordSpan:

	return subsequence.progressions.parse_element(name, beats = 4)


def _span (quality: str, extensions: typing.Tuple[typing.Any, ...] = (), bass: typing.Optional[int] = None, root: int = 0) -> subsequence.progressions.ChordSpan:

	chord = subsequence.chords.Chord(root_pc = root, quality = quality)

	return subsequence.progressions.ChordSpan(chord = chord, beats = 4, extensions = extensions, bass = bass)


def _sound (span: subsequence.progressions.ChordSpan) -> typing.Tuple[typing.Any, ...]:

	"""What a span plays: its notes above the root, the root, and the bass."""

	return (span.decorated_intervals(), span.chord.root_pc, span.bass)


def test_every_label_over_every_quality_extension_and_bass_reads_back () -> None:

	"""The whole domain the printer covers, on three roots: the same notes, root and bass, and the same label.

	The one family left out is the augmented chord with a number and a sus,
	which prints ``C+7sus4`` and waits on the C+9 question.  It is refused,
	never read as another chord, and the test says so if that changes.
	"""

	misread: typing.List[str] = []
	refused: typing.Set[str] = set()
	read = 0

	for root, quality, number, name, bass in itertools.product(
		(0, 6, 10),
		_QUALITIES,
		(None, 7, 9, 11, 13),
		(None, "add9", "6", "sus2", "sus4"),
		(None, 4, 2),
	):

		span = _span(quality, tuple(e for e in (number, name) if e is not None), bass, root)
		label = span.label()

		try:
			back = _read(label)
		except ValueError:
			refused.add(label)
			continue

		read += 1

		if _sound(back) != _sound(span):
			misread.append(f"{label}: {_sound(span)} read as {_sound(back)}")
		elif back.label() != label:
			misread.append(f"{label}: prints back as {back.label()!r}")

	assert misread == []
	assert read == 2457
	assert len(refused) == 18
	assert all("+7sus" in label for label in refused), sorted(refused)


@pytest.mark.parametrize("name, intervals", [
	("C7sus4", [0, 5, 7, 10]),
	("C9sus4", [0, 5, 7, 10, 14]),
	("Cm9b5", [0, 3, 6, 10, 14]),
	("C+maj7", [0, 4, 8, 11]),
	("CmMaj7", [0, 3, 7, 11]),
	("CmMaj9", [0, 3, 7, 11, 14]),
	("Cadd9", [0, 4, 7, 14]),
	("Cm6", [0, 3, 7, 9]),
	("C6add9", [0, 4, 7, 9, 14]),
	("Cmaj7sus4", [0, 5, 7, 11]),
	("Cmaj9sus2", [0, 2, 7, 11, 14]),
	("Cdim9sus2", [0, 2, 6, 9, 14]),
])
def test_a_chart_symbol_reads_as_the_chord_it_names (name: str, intervals: typing.List[int]) -> None:

	assert _read(name).decorated_intervals() == intervals


def test_a_slash_chord_puts_its_bass_under_the_chord () -> None:

	"""C/E is C major over an E, and Am7/G an A minor seventh over a G."""

	c_over_e = _read("C/E")
	a_over_g = _read("Am7/G")

	assert (c_over_e.chord.quality, c_over_e.bass) == ("major", 4)
	assert (a_over_g.chord.root_pc, a_over_g.chord.quality, a_over_g.bass) == (9, "minor_7th", 7)
	assert min(c_over_e.tones(60)) % 12 == 4


def test_a_slash_with_no_note_after_it_says_what_it_needs () -> None:

	with pytest.raises(ValueError, match = "after the slash comes a note"):
		_read("C/H")


def test_a_bare_chord_refuses_a_slash_and_says_where_one_is_read () -> None:

	"""parse_chord() makes a Chord, which has no bass: it points at the progression that does."""

	with pytest.raises(ValueError, match = r"progression\(\['C/E'\]\) reads it"):
		subsequence.chords.parse_chord("C/E")


@pytest.mark.parametrize("quality, extensions, was, now", [
	("major_7th", (7, "sus4"), "C7sus4", "Cmaj7sus4"),
	("major", (7, "6"), "C76", "Cmaj76"),
	("diminished", (7, "sus2"), "Cdim7sus2", "Cm7b5sus2"),
	("diminished_7th", (7, "sus2"), "Cdim77sus2", "Cdim7sus2"),
	("half_diminished_7th", (7, "sus4"), "Cm7b57sus4", "Cm7b5sus4"),
])
def test_the_printer_names_the_chord_it_has (quality: str, extensions: typing.Tuple[typing.Any, ...], was: str, now: str) -> None:

	"""Five labels that named a different chord, or could not be read at all."""

	assert _span(quality, extensions).label() == now


def test_an_augmented_chord_with_a_seven_is_still_not_read () -> None:

	"""A guard for the C+9 question on #3012: C+7 is refused, as it was before #3014."""

	with pytest.raises(ValueError):
		_read("C+7")


def test_an_augmented_ninth_keeps_its_reading () -> None:

	"""A guard for the same question: C+9 reads as it always has, with a major seventh."""

	assert _read("C+9").decorated_intervals() == [0, 4, 8, 11, 14]
