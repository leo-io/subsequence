"""Cb, Fb, E# and B# are read wherever a note name is, and offered nowhere (#3488).

Each is a real spelling - Cb major has seven flats, E# is the third of C# major, B# the leading
note in C# minor - and each was refused: as a chord's root, a key, and a slash bass.  They stay out
of ``NOTE_NAME_TO_PC``, which the catalogue publishes as a control surface's list of roots: each is
a second name for a note the list already offers.
"""

import pytest

import subsequence
import subsequence.catalogue
import subsequence.chords
import subsequence.progressions


@pytest.mark.parametrize("name, root_pc, quality", [
	("Cb", 11, "major"),
	("Fbm", 4, "minor"),
	("E#7", 5, "dominant_7th"),
	("B#dim", 0, "diminished"),
	("Cbmaj7", 11, "major_7th"),
])
def test_a_chord_on_a_spelling_that_falls_on_a_natural_is_read (name: str, root_pc: int, quality: str) -> None:

	assert subsequence.chords.parse_chord(name) == subsequence.chords.Chord(root_pc=root_pc, quality=quality)


@pytest.mark.parametrize("name, pc", [("Cb", 11), ("Fb", 4), ("E#", 5), ("B#", 0)])
def test_a_key_is_read_in_the_same_spellings (name: str, pc: int) -> None:

	assert subsequence.chords.key_name_to_pc(name) == pc


def test_a_slash_bass_is_read_in_them_too () -> None:

	"""Ab over its third, written Cb as a chart writes it."""

	assert subsequence.progressions.parse_element("Ab/Cb", beats=4).bass == 11


def test_a_composition_takes_one_as_its_key () -> None:

	composition = subsequence.Composition(output_device="Dummy MIDI", key="Cb")
	composition.harmony(style="functional_major", cycle_beats=4)

	assert composition._harmonic_state is not None
	assert composition._harmonic_state.key_root_pc == 11


def test_the_published_roots_do_not_offer_them () -> None:

	"""A guard: the catalogue's list of roots is the seventeen it always was.  This held before #3488 as well."""

	chord_forms = [parameter["chord"] for parameter in subsequence.catalogue.describe_generator("chord")["parameters"] if "chord" in parameter]
	offered = [entry["value"] for entry in chord_forms[0]["roots"]]

	assert len(offered) == 17
	assert not {"Cb", "Fb", "E#", "B#"} & set(offered)
