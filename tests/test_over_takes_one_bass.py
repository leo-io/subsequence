"""over() takes one bass, and refuses anything else rather than printing it into the chords' names (#3017).

A list - a plausible guess at one bass per chord - was accepted in silence: every chord printed it
(``C/['G', None, None, 'E']``) and none of them sounded a bass.  ``True``, being an int, became a
C#, and ``7.0`` printed as ``C/7.0``.  The per-chord form is ``only=``.
"""

import typing

import pytest

import subsequence


def _pop () -> subsequence.progressions.Progression:

	return subsequence.progression(["C", "F", "G", "Am"])


@pytest.mark.parametrize("bass", [["G", None, None, "E"], True, 7.0], ids=["a list", "True", "a float"])
def test_a_bass_that_is_not_a_bass_is_refused (bass: typing.Any) -> None:

	with pytest.raises(TypeError, match=r"only=\[slot\]"):
		_pop().over(bass)


def test_one_bass_per_chord_is_written_with_only () -> None:

	"""What the list was reaching for.  A guard: this passed before #3017 as well."""

	value = _pop().over("G", only=[1]).over("E", only=[4])

	assert [span.bass for span in value.spans] == [7, None, None, 4]


def test_a_pitch_class_a_note_name_and_the_tonic_still_work () -> None:

	"""A guard: the three forms over() documents.  This passed before #3017 as well."""

	assert _pop().over(7).spans[0].bass == 7
	assert _pop().over("G").spans[0].bass == 7
	assert _pop().over("tonic").spans[0].bass == "tonic"


def test_none_takes_the_bass_away () -> None:

	"""A guard: documented now, and it always did.  This passed before #3017 as well."""

	value = _pop().over("G").over(None, only=[2])

	assert [span.bass for span in value.spans] == [7, None, 7, 7]
