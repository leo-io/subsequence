"""Roman numerals read the textbook way in minor, and an extended numeral gets its key's seventh (#3026).

Decision 8 of #2991: in natural minor the case of a numeral on the sixth or seventh degree decides
raised or natural - ``vii°`` is G#dim and ``vi`` F#m in A minor, ``VI`` and ``VII`` stay F and G - so
``pop_axis`` in A minor plays A E F#m D, where it played A E Fm D, from neither key.

Decision 9: a numeral that is its key's own extends diatonically, as a degree does - ``V+7`` is G7,
``ii+7`` Dm7 and ``vii°+7`` Bm7b5 in C major, where every roman took its concrete colour and ``V``
became Gmaj7.  An altered numeral keeps its colour.  In natural minor, at Simon's call on #2991,
every numeral on a degree of the key is its own, so ``i iv V i`` extends to Am7 Dm7 E7 Am7, and a
secondary dominant is read in the key it points to: ``V/V+7`` is D7 in C.
"""

import typing

import subsequence.progressions

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _tones (elements: typing.Any, key: str, scale: str, *extensions: typing.Any, borrow: typing.Optional[int] = None) -> typing.List[str]:

	"""Each chord's notes, root first, spelled with sharps: ``["A C E", "E G# B"]``."""

	progression = subsequence.progressions.progression(elements)

	if borrow is not None:
		progression = progression.borrow(borrow)

	if extensions:
		progression = progression.extend(*extensions)

	return [
		" ".join(NAMES[(span.chord.root_pc + interval) % 12] for interval in span.decorated_intervals())
		for span in progression.resolve(key, scale).spans
	]


# --- decision 8: the sixth and seventh in minor ---


def test_pop_axis_in_a_minor_plays_the_textbook_chords () -> None:

	"""The decision's own example: A E F#m D."""

	assert _tones("pop_axis", "A", "minor") == ["A C# E", "E G# B", "F# A C#", "D F# A"]


def test_a_minor_or_diminished_sixth_or_seventh_is_raised_in_minor () -> None:

	assert _tones(["vi", "vii°", "vii", "viiø7"], "A", "minor") == ["F# A C#", "G# B D", "G# B D#", "G# B D F#"]


def test_a_major_sixth_or_seventh_stays_natural_in_minor () -> None:

	"""A guard for the other half of decision 8: ``VI`` and ``VII`` were F and G already.  This passed before #3026 as well."""

	assert _tones(["VI", "VII", "VI+"], "A", "minor") == ["F A C", "G B D", "F A C#"]


def test_the_rule_reads_the_scale_not_its_name () -> None:

	"""``aeolian`` is natural minor too - #3008's lesson, where a name comparison made it borrow from itself."""

	assert _tones(["vi", "vii°"], "A", "aeolian") == _tones(["vi", "vii°"], "A", "minor") == ["F# A C#", "G# B D"]


def test_another_mode_reads_its_own_degrees () -> None:

	"""A guard: only natural minor has a variable sixth and seventh, so dorian keeps its own.  This passed before #3026 as well."""

	assert _tones(["vi", "vii°"], "A", "dorian") == ["F# A C#", "G A# C#"]


def test_a_degree_still_reads_the_scale () -> None:

	"""A guard: a bare degree names no case, so 6 and 7 in A minor are F and G.  This passed before #3026 as well."""

	assert _tones([6, 7], "A", "minor") == ["F A C", "G B D"]


def test_a_borrowed_numeral_takes_the_mode_it_borrows_from () -> None:

	"""A guard: borrowed ``vi`` in C is the parallel minor's A-flat, not a raised sixth of it.  This passed before #3026 as well."""

	assert _tones(["vi"], "C", "ionian", borrow = 1) == ["G# C D#"]


# --- decision 9: which seventh an extended numeral gets ---


def test_a_numeral_that_is_its_keys_own_takes_the_diatonic_seventh () -> None:

	"""V+7 is G7, ii+7 Dm7 and vii°+7 Bm7b5: V was Gmaj7, and vii° a fully diminished seventh."""

	assert _tones(["I", "ii", "iii", "IV", "V", "vi", "vii°"], "C", "ionian", 7) == [
		"C E G B", "D F A C", "E G B D", "F A C E", "G B D F", "A C E G", "B D F A",
	]


def test_a_numeral_and_its_degree_extend_alike () -> None:

	assert _tones("pop_axis", "C", "ionian", 7) == _tones([1, 5, 6, 4], "C", "ionian", 7)


def test_an_altered_numeral_keeps_its_own_colour () -> None:

	"""A guard: ``II`` and ``bVII`` are not C major's, so they keep a major seventh.  This passed before #3026 as well."""

	assert _tones(["II", "bVII"], "C", "ionian", 7) == ["D F# A C#", "A# D F A"]


def test_a_secondary_dominant_takes_the_seventh_of_the_key_it_points_to () -> None:

	"""V/V is V of G major, so its seventh is G major's: D7, where it was Dmaj7."""

	assert _tones(["V/V"], "C", "ionian", 7) == ["D F# A C"]


def test_in_minor_every_numeral_on_the_key_takes_its_seventh () -> None:

	"""Simon's call: V and IV take the key's seventh, as a textbook has it."""

	assert _tones(["i", "iv", "V", "i"], "A", "minor", 7) == ["A C E G", "D F A C", "E G# B D", "A C E G"]
	assert _tones(["IV", "vi", "vii°", "VII", "II"], "A", "minor", 7) == [
		"D F# A C", "F# A C# E", "G# B D F", "G B D F", "B D# F# A",
	]


def test_the_ninth_comes_from_the_key_as_well () -> None:

	"""V+9 in A minor is the textbook minor ninth: E G# B D F."""

	assert _tones(["V"], "A", "minor", 9) == ["E G# B D F"]


def test_a_numeral_that_names_its_seventh_keeps_it () -> None:

	"""Vmaj7 extended to a ninth stays a major seventh: the key's seventh would sit beside the one it asked for.

	Decision 9 is about the seventh an extension gives, so a numeral that names its own keeps
	today's colour for the whole extension.  In major the key's own triads have no seventh, so
	only minor, where every numeral on the key is its own, can tell: there Vmaj7 would gain D
	beside its D#.  A guard in the sense that it passed before #3026 as well.
	"""

	assert _tones(["Vmaj7"], "C", "ionian", 9) == ["G B D F# A"]
	assert _tones(["V7"], "C", "ionian", 9) == ["G B D F A"]
	assert _tones(["Vmaj7"], "A", "minor", 9) == ["E G# B D# F#"]
	assert _tones(["V7"], "A", "minor", 9) == ["E G# B D F#"]


def test_a_numeral_is_judged_by_its_chord_not_its_spelling () -> None:

	"""``bVII`` in A minor is the key's own G, so G7; in C it is B-flat, altered, and keeps its colour.

	The same holds for the scale-proof spelling ``Progression.generate`` writes, where every
	chord is spelled from the major scale.
	"""

	assert _tones(["bVII"], "A", "minor", 7) == ["G B D F"]
	assert _tones(["bVII"], "C", "ionian", 7) == ["A# D F A"]

	generated = subsequence.progressions.ChordSpan(
		chord = subsequence.progressions.RomanChord(degree = 7, accidental = -1, quality = "major", major_relative = True),
		beats = 4.0,
		extensions = (7,),
	).resolve(9, "minor")

	assert [NAMES[(generated.chord.root_pc + interval) % 12] for interval in generated.decorated_intervals()] == ["G", "B", "D", "F"]


def test_a_borrowed_seventh_takes_the_parallel_minors_seventh () -> None:

	"""Borrowed 7 in C is the parallel minor's B-flat, and its seventh is C minor's A-flat: B-flat 7.

	A guard for the borrowed half of the key: this passed before #3026 as well, because the old
	name comparison happened to hold for ``ionian``.
	"""

	assert _tones([7], "C", "ionian", 7, borrow = 1) == ["A# D F G#"]


def test_a_borrowed_degree_extends_in_the_mode_it_borrows_from () -> None:

	"""Borrowed 3 in A minor is C#m from A major, so its seventh is B - under every minor name.

	The extension read the mode by comparing names, so ``aeolian`` and ``dorian`` stacked A minor's
	thirds on a chord borrowed from A major and gave C#m with a major seventh.
	"""

	for scale in ("minor", "aeolian", "dorian"):
		assert _tones([3], "A", scale, 7, borrow = 1) == ["C# E G# B"], scale
