"""A borrowed degree comes from the parallel mode, and says so when it cannot (#3008).

`borrow()` only flipped a flag; resolution then re-rooted against a "parallel"
scale chosen by comparing the scale's NAME with "minor", and kept the roman's
own case for the quality.  So in C:

- romans `I IV vi vii°` borrowing slots 2-4 gave `C F G#m A#dim` — `G#m`
  belongs to neither key, since the parallel minor's sixth is `G#` major;
- `pop_axis.borrow(...)` gave `C G G#m F`;
- `scale="aeolian"`, a literal alias of minor, borrowed *from* minor and
  changed nothing at all, as did phrygian;
- accidental and secondary numerals were silently ignored.

The fix picks the parallel mode by the scale's third, and a borrowed degree
takes the borrowed mode's diatonic quality.
"""

import logging
import typing

import pytest

import subsequence
import subsequence.chords
import subsequence.progressions


def _spell (
	progression: subsequence.progressions.Progression,
	key: str = "C",
	scale: str = "ionian",
) -> typing.List[str]:

	"""What this progression actually plays, in *key* and *scale*."""

	key_pc = subsequence.chords.key_name_to_pc(key)
	spelled = []

	for span in progression.spans:
		chord = span.chord
		if hasattr(chord, "resolve"):
			chord = chord.resolve(key_pc, scale)
		spelled.append(chord.name())

	return spelled


def _all_slots (progression: subsequence.progressions.Progression) -> typing.List[int]:

	"""Every 1-based slot."""

	return list(range(1, len(progression.spans) + 1))


# ---------------------------------------------------------------------------
# The chord that belonged to neither key
# ---------------------------------------------------------------------------

def test_a_borrowed_sixth_is_the_parallel_minors_flat_six () -> None:

	"""`vi` borrowed gave `G#m`: a minor chord on a root only the minor key has."""

	progression = subsequence.progressions.progression(["I", "IV", "vi", "vii°"], beats = 4.0)

	assert _spell(progression) == ["C", "F", "Am", "Bdim"]
	assert _spell(progression.borrow(_all_slots(progression))) == ["Cm", "Fm", "G#", "A#"]


def test_a_borrowed_roman_matches_the_same_degree_written_as_an_int () -> None:

	"""They are the same chord written two ways; they were not the same chord."""

	romans = subsequence.progressions.progression(["I", "IV", "vi", "vii°"], beats = 4.0)
	integers = subsequence.progressions.progression([1, 4, 6, 7], beats = 4.0)

	assert _spell(romans.borrow(_all_slots(romans))) == _spell(integers.borrow(_all_slots(integers)))


def test_the_pop_axis_example () -> None:

	"""The ticket's own case: `C G G#m F`."""

	axis = subsequence.progressions.progression("pop_axis", beats = 4.0)

	assert _spell(axis) == ["C", "G", "Am", "F"]
	assert _spell(axis.borrow(_all_slots(axis))) == ["Cm", "Gm", "G#", "Fm"]


def test_every_borrowed_chord_is_diatonic_to_the_parallel_mode () -> None:

	"""The general form of it: nothing borrowed may be foreign to what it borrowed from."""

	progression = subsequence.progressions.progression([1, 2, 3, 4, 5, 6, 7], beats = 4.0)
	borrowed = subsequence.progressions.progression(["I", "ii", "iii", "IV", "V", "vi", "vii°"], beats = 4.0)

	parallel = _spell(
		subsequence.progressions.progression([1, 2, 3, 4, 5, 6, 7], beats = 4.0),
		scale = "aeolian",
	)

	assert _spell(borrowed.borrow(_all_slots(borrowed))) == parallel
	assert _spell(progression.borrow(_all_slots(progression))) == parallel


# ---------------------------------------------------------------------------
# Which mode is the parallel one
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scale, expected", [
	("ionian", "aeolian"),
	("major", "aeolian"),
	("lydian", "aeolian"),
	("mixolydian", "aeolian"),
	("minor", "ionian"),
	("aeolian", "ionian"),
	("dorian", "ionian"),
	("phrygian", "ionian"),
	("locrian", "ionian"),
	("harmonic_minor", "ionian"),
	("melodic_minor", "ionian"),
])
def test_the_parallel_mode_is_chosen_by_the_third (scale: str, expected: str) -> None:

	"""Not by whether the scale is called "minor" — `aeolian` is minor and was not."""

	assert subsequence.progressions._parallel_mode(scale) == expected


@pytest.mark.parametrize("scale", ["aeolian", "phrygian", "dorian", "locrian", "minor"])
def test_a_minor_third_scale_borrows_something_different (scale: str) -> None:

	"""Under aeolian and phrygian, borrow() used to be a no-op."""

	progression = subsequence.progressions.progression(["i", "iv", "VI", "VII"], beats = 4.0)

	plain = _spell(progression, scale = scale)
	borrowed = _spell(progression.borrow(_all_slots(progression)), scale = scale)

	assert plain != borrowed, f"borrow() changed nothing under {scale}: {plain}"


@pytest.mark.parametrize("scale", ["dorian", "phrygian", "aeolian", "locrian", "minor"])
def test_a_minor_third_scale_borrows_from_ionian (scale: str) -> None:

	"""Dorian and phrygian borrowed from natural minor, which they nearly are."""

	progression = subsequence.progressions.progression([1, 2, 3, 4, 5, 6, 7], beats = 4.0)
	plain_ionian = _spell(progression, scale = "ionian")

	assert _spell(progression.borrow(_all_slots(progression)), scale = scale) == plain_ionian


def test_a_scale_too_short_to_have_a_third_still_borrows () -> None:

	"""No built-in scale is this short, but `register_scale` lets anyone make one."""

	subsequence.register_scale("borrowtest_twonote", [0, 7], qualities = ["major", "major"])

	progression = subsequence.progressions.progression([1, 2], beats = 4.0)

	assert _spell(progression.borrow([1, 2]), scale = "borrowtest_twonote") == ["Cm", "Ddim"]


@pytest.mark.parametrize("borrowed", [False, True])
def test_an_unknown_scale_names_itself_in_the_error (borrowed: bool) -> None:

	"""The message used to name the parallel it had computed, not what was asked for —
	which is only visible when borrowing, because that is when the two differ."""

	progression = subsequence.progressions.progression([1], beats = 4.0)

	if borrowed:
		progression = progression.borrow([1])

	with pytest.raises(ValueError, match = "wurlitzian"):
		_spell(progression, scale = "wurlitzian")


# ---------------------------------------------------------------------------
# What cannot be borrowed says so
# ---------------------------------------------------------------------------

def test_an_accidental_degree_is_left_alone_with_a_warning (caplog: pytest.LogCaptureFixture) -> None:

	"""`bVII` is the whole step below the tonic in either mode — there is no parallel."""

	progression = subsequence.progressions.progression(["I", "bVII"], beats = 4.0)

	with caplog.at_level(logging.WARNING):
		borrowed = progression.borrow([2])

	assert _spell(borrowed) == _spell(progression), "a chromatic degree was moved"
	assert "bVII" in caplog.text
	assert "chromatic" in caplog.text


def test_a_secondary_numeral_is_left_alone_with_a_warning (caplog: pytest.LogCaptureFixture) -> None:

	"""`V/V` resolves against its own target's key; borrowing has no meaning for it."""

	progression = subsequence.progressions.progression(["I", "V/V"], beats = 4.0)

	with caplog.at_level(logging.WARNING):
		borrowed = progression.borrow([2])

	assert _spell(borrowed) == _spell(progression)
	assert "V/V" in caplog.text
	assert "secondary" in caplog.text


def test_the_slots_that_can_be_borrowed_still_are (caplog: pytest.LogCaptureFixture) -> None:

	"""One numeral refusing must not stop the rest."""

	progression = subsequence.progressions.progression(["I", "bVII", "V/V", "IV"], beats = 4.0)

	with caplog.at_level(logging.WARNING):
		borrowed = progression.borrow([1, 2, 3, 4])

	assert _spell(borrowed) == ["Cm", "A#", "D", "Fm"]


def test_a_concrete_chord_still_raises () -> None:

	"""There is nothing relative to borrow, and that is an error rather than a warning."""

	progression = subsequence.progressions.progression(["Am", "F"], beats = 4.0)

	with pytest.raises(ValueError, match = "concrete chord"):
		progression.borrow([1])


# ---------------------------------------------------------------------------
# Generated progressions
# ---------------------------------------------------------------------------

def test_a_generated_progression_borrows () -> None:

	"""Its spans are major-relative, and used to read the major scale whatever was asked."""

	generated = subsequence.progressions.Progression.generate("functional_major", bars = 4, seed = 3)

	plain = _spell(generated)
	borrowed = _spell(generated.borrow(_all_slots(generated)))

	assert plain != borrowed, f"borrow() changed nothing: {plain}"


def test_a_generated_progression_borrows_into_the_parallel_mode () -> None:

	"""Every borrowed chord has to be one the parallel mode owns."""

	generated = subsequence.progressions.Progression.generate("functional_major", bars = 6, seed = 11)
	borrowed = generated.borrow(_all_slots(generated))

	aeolian = set(_spell(
		subsequence.progressions.progression([1, 2, 3, 4, 5, 6, 7], beats = 4.0),
		scale = "aeolian",
	))

	for chord in _spell(borrowed):
		assert chord in aeolian, f"{chord} is in neither the key nor its parallel"


def test_a_generated_progression_bound_to_a_key_is_concrete_and_says_so () -> None:

	"""With `key=` it produces real chords, and there is nothing relative left to borrow."""

	generated = subsequence.progressions.Progression.generate("functional_major", bars = 4, key = "C", seed = 3)

	with pytest.raises(ValueError, match = "concrete chord"):
		generated.borrow([1])


# ---------------------------------------------------------------------------
# What borrowing must not disturb
# ---------------------------------------------------------------------------

def test_borrowing_twice_puts_it_back () -> None:

	"""The flag toggles, and toggling twice is the identity."""

	progression = subsequence.progressions.progression(["I", "IV", "vi"], beats = 4.0)
	slots = _all_slots(progression)

	assert _spell(progression.borrow(slots).borrow(slots)) == _spell(progression)


def test_an_unborrowed_slot_is_untouched () -> None:

	"""Borrowing one chord must not re-spell its neighbours."""

	progression = subsequence.progressions.progression(["I", "IV", "vi", "V"], beats = 4.0)
	borrowed = _spell(progression.borrow([3]))

	assert borrowed == ["C", "F", "G#", "G"]


def test_the_spans_keep_their_beats () -> None:

	"""borrow() decorates the chord, never the timing."""

	progression = subsequence.progressions.progression([("I", 3.0), ("vi", 1.0)])
	borrowed = progression.borrow([1, 2])

	assert [span.beats for span in borrowed.spans] == [3.0, 1.0]


def test_an_int_degree_borrows_as_it_always_did () -> None:

	"""The two tests this had were both on ints, and they must still mean the same."""

	progression = subsequence.progressions.progression([1, 4, 5], beats = 4.0)

	assert _spell(progression.borrow([1, 2, 3])) == ["Cm", "Fm", "Gm"]
