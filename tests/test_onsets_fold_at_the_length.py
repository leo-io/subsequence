"""A note that rotate() or quantize() moves onto a motif's length plays on beat 0 (#3455).

The length is the next cycle's downbeat.  An onset there was placed on the pulse
after the last one, so it sounded beside the next cycle's own first note - two
downbeat hits every bar after the first, and a stray one after the end - and a
phrase, which keeps only the onsets inside each segment, dropped it.

Rotating by a third of a beat's multiples reaches the length through float
rounding (``x % L`` is exactly ``L`` for a tiny negative ``x``); snapping to a grid
reaches it by rounding up.
"""

import random
import typing

import subsequence
import subsequence.pattern
import subsequence.pattern_builder
from subsequence.motifs import Motif as M
from subsequence.motifs import Phrase as P


def _pulses (m: M) -> typing.List[int]:

	"""The pulses a motif's notes are placed on, in a pattern of its own length."""

	pattern = subsequence.pattern.Pattern(channel=9, length=m.length)
	builder = subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=0, drum_note_map={"kick": 36}, rng=random.Random(1))
	builder.motif(m)

	return sorted(pulse for pulse, step in pattern.steps.items() for _ in step.notes)


def test_a_hit_quantized_onto_the_length_plays_on_the_downbeat () -> None:

	"""3.8 snapped to half beats is 4.0, the end of a four-beat motif; it plays at 0."""

	snapped = M.hits("kick", beats=[1, 2, 3.8], length=4).quantize(0.5)

	assert [event.beat for event in snapped.events] == [0.0, 1.0, 2.0]
	assert _pulses(snapped) == [0, 24, 48]


def test_a_note_rotated_onto_the_length_plays_on_the_downbeat () -> None:

	"""Five in twelve, rotated back five twelfths of the bar, puts its last hit exactly on 4.0."""

	rotated = M.euclidean(5, 12, "kick").rotate(-5 * 4 / 12)

	assert all(0 <= event.beat < 4 for event in rotated.events)
	assert _pulses(rotated) == [0, 16, 40, 56, 72]


def test_a_note_rotated_a_rounding_error_short_of_the_length_plays_on_the_downbeat () -> None:

	"""Six in seven, rotated on two sevenths, puts a hit at 3.9999999999999996 - pulse 96 all the same.

	So the fold reads the pulse an onset places on: a test for exactly 4.0
	would let this one through to the next downbeat.
	"""

	rotated = M.euclidean(6, 7, "kick").rotate(2 * 4 / 7)
	pulses = _pulses(rotated)

	assert len(pulses) == 6
	assert pulses[0] == 0 and pulses[-1] < 96


def test_a_phrase_keeps_a_note_rotated_onto_its_length () -> None:

	"""The phrase kept only onsets inside each segment, so that note was lost: 10 became 9."""

	phrase = P([M.euclidean(5, 12, "kick"), M.euclidean(5, 12, "kick")])
	rotated = phrase.rotate(-5 * 4 / 12)

	assert sum(len(segment.events) for segment in rotated.segments) == 10
	assert _pulses(rotated.flatten()) == [0, 16, 40, 56, 72, 96, 112, 136, 152, 168]


def test_nothing_short_of_the_length_moves () -> None:

	"""An onset a hundredth of a beat before the end stays there; only the length itself folds.

	This passed before the fix as well.  It pins that the fold reads the pulse
	an onset places on, not a loose tolerance.
	"""

	late = M.hits("kick", beats=[0, 3.99], length=4)

	assert [event.beat for event in late.rotate(0).events] == [0.0, 3.99]
	assert _pulses(late.rotate(0)) == [0, 95]

	nearly = M.hits("kick", beats=[0, 3.7], length=4)

	assert [event.beat for event in nearly.quantize(0.25).events] == [0.0, 3.75]
