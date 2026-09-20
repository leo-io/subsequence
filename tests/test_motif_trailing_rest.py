"""A rest holds its slot, so a figure that ends in silence keeps its length (#3009).

``None`` is documented as a rest whose beat slot still advances, and the Motif
class docstring says a trailing rest is meaningful — but the default length was
computed from the sounding events alone, so ``motif([1, 3, 5, None])`` was three
beats and looped a bar's idea against the bar for ever.

The second half here is the refusal that goes with it: an explicit ``length=``
that leaves an event past the end says so, rather than quietly dropping it.
"""

import random
import typing

import pytest

import subsequence
import subsequence.motifs
import subsequence.pattern
import subsequence.pattern_builder


M = subsequence.Motif


def _builder (cycle: int = 0, length: float = 4.0) -> subsequence.pattern_builder.PatternBuilder:

	"""A standalone builder over a fresh pattern."""

	pattern = subsequence.pattern.Pattern(channel = 0, length = length)

	return subsequence.pattern_builder.PatternBuilder(
		pattern = pattern,
		cycle = cycle,
		key = "A",
		scale = "minor",
		rng = random.Random(1),
	)


def _placed (builder: subsequence.pattern_builder.PatternBuilder) -> typing.List[typing.Tuple[float, int]]:

	"""(beat, pitch) of every note on the builder's pattern, in time order."""

	ppq = subsequence.constants.MIDI_QUARTER_NOTE

	return sorted(
		(pulse / ppq, note.pitch)
		for pulse, step in builder._pattern.steps.items()
		for note in step.notes
	)


# ---------------------------------------------------------------------------
# The length a constructor computes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("build, expected", [
	(lambda: subsequence.motif([1, 3, 5, None]), 4.0),
	(lambda: subsequence.motif([1, None, None, None]), 4.0),
	(lambda: M.notes([60, None, None]), 3.0),
	(lambda: M.degrees([1, None, None, None]), 4.0),
	(lambda: M.notes([60, 62, None, None], beats = [0.0, 1.0, 2.0, 3.0]), 4.0),
])
def test_a_trailing_rest_keeps_its_slot_in_the_length (build: typing.Callable[[], subsequence.Motif], expected: float) -> None:

	"""The slot a rest occupies counts, exactly as a sounding note's would."""

	assert build().length == expected


def test_a_rest_in_the_middle_was_never_the_problem () -> None:

	"""Only a trailing rest was lost — one between two notes was always counted."""

	assert subsequence.motif([1, None, 5, 6]).length == 4.0


def test_a_figure_of_nothing_but_rests_still_has_its_length () -> None:

	"""Four silent slots are four beats of silence, not an empty motif."""

	silence = M.notes([None, None, None, None])

	assert silence.events == ()
	assert silence.length == 4.0


# ---------------------------------------------------------------------------
# What that length then governs
# ---------------------------------------------------------------------------

def test_a_repeated_figure_keeps_the_rest_each_time_round () -> None:

	"""Two bars of a one-bar figure are two bars, by * and by then()."""

	figure = subsequence.motif([1, 3, 5, None])

	assert (figure * 2).length == 8.0
	assert figure.then(figure).length == 8.0


def test_a_figure_ending_in_silence_builds_a_sentence () -> None:

	"""sentence() refused it outright: 'the motif is 3 beats but each unit spans 4'."""

	phrase = subsequence.sentence(subsequence.motif([1, 3, 5, None]), bars = 4, seed = 1)

	assert phrase.length == 16.0


def test_p_phrase_loops_a_figure_ending_in_silence_on_the_bar () -> None:

	"""A bar-long figure starts every bar, instead of walking a beat earlier each cycle."""

	value = subsequence.Phrase([subsequence.motif([1, 3, 5, None])])

	first = _builder(cycle = 0)
	first.phrase(value, root = 60)

	second = _builder(cycle = 1)
	second.phrase(value, root = 60)

	assert _placed(first) == _placed(second)
	assert [beat for beat, _ in _placed(first)] == [0.0, 1.0, 2.0]


# ---------------------------------------------------------------------------
# An explicit length that does not hold the figure
# ---------------------------------------------------------------------------

def test_a_length_that_leaves_an_event_past_the_end_is_refused () -> None:

	"""Four notes in a one-beat motif: three of them never sound, and now it says so."""

	with pytest.raises(ValueError, match = r"length is 1.0 beats.*beat 3.0"):
		M.notes([60, 62, 64, 65], length = 1.0)


def test_a_note_may_still_ring_past_the_end () -> None:

	"""A note tied over the barline is ordinary music, not a mistake."""

	tied = M.from_events([subsequence.MotifEvent(beat = 3.5, pitch = 60, duration = 1.0)], length = 4.0)

	assert tied.length == 4.0


def test_an_event_on_the_end_is_the_boundary_not_past_it () -> None:

	"""A discrete control write at the end of its motif is how a gesture closes."""

	gesture = M.cc(74, [64], beats = [2.0])

	assert gesture.length == 2.0
