"""tuning()'s just-intonation example keeps ordinary notes on their names (#3474).

A tuning maps consecutive MIDI notes onto its degrees, so the old headline example - a
seven-degree table - made every MIDI note a scale degree: 62 played 64 and 64 played 67, and
ordinary music was scrambled.  The headline is now a twelve-degree just table, and the
seven-degree one is shown as what it is.  These tests read the examples out of the docstring
itself, so the one a reader copies is the one checked.
"""

import ast
import re
import typing

import subsequence
import subsequence.tuning


def _example_ratios (comment: str) -> typing.List[float]:

	"""The ``ratios=[...]`` of the tuning() example under the comment that starts *comment*."""

	doc = subsequence.Composition.tuning.__doc__ or ""
	match = re.search(re.escape(comment) + r"[^\n]*\n\s*comp\.tuning\(ratios=(\[[^\]]*\])\)", doc)

	assert match is not None, f"no tuning() example under {comment!r}"

	return [float(eval(compile(ast.Expression(element), "<ratio>", "eval"))) for element in ast.parse(match.group(1), mode="eval").body.elts]	# noqa: S307


def _plays (ratios: typing.List[float], midi: int) -> typing.Tuple[int, float]:

	"""The nearest MIDI note a tuned note sounds at, and its offset in cents."""

	nearest, bend = subsequence.tuning.Tuning.from_ratios(ratios).pitch_bend_for_note(midi)

	return nearest, bend * 200.0


def test_the_headline_just_example_keeps_every_note_on_its_name () -> None:

	ratios = _example_ratios("# Just intonation in C")

	for midi in range(60, 73):
		nearest, cents = _plays(ratios, midi)
		assert nearest == midi and abs(cents) < 20, (midi, nearest, round(cents, 1))


def test_the_docstring_says_how_far_e_and_g_move () -> None:

	"""E 14 cents flat and G 2 cents sharp, as the docstring says."""

	ratios = _example_ratios("# Just intonation in C")

	assert round(_plays(ratios, 64)[1]) == -14
	assert round(_plays(ratios, 67)[1]) == 2


def test_a_seven_degree_table_steps_consecutive_notes_through_the_scale () -> None:

	"""60, 61 and 62 play C, D and E - the degrees, as the docstring says."""

	ratios = _example_ratios("# A seven-degree just scale")

	assert [_plays(ratios, midi)[0] for midi in (60, 61, 62)] == [60, 62, 64]
