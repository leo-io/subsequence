"""The fit dial travels with each note (#3458, Simon's call on #3423).

A generated motif carried one fit for the whole motif, and every operation that built
a new motif decided afresh what to do with it: ``reroll()`` and ``Phrase.rotate()``
dropped it, ``&`` kept only the left operand's, and ``then()`` lent it to the other
motif's notes.  So a written line changed sound depending on what it was joined to,
``a & b`` placed differently from ``b & a``, and a phrase's written bar sounded one
way under a four-beat pattern and another under an eight-beat one.

Now ``generate()`` gives each note it makes a fit of 0.7, a written note has none,
and the fit goes wherever its note goes.  Everything here is in A minor over Am,
where degree 2 (B, 59) is off the chord, so a snap shows.
"""

import random
import typing
import warnings

import pytest

import subsequence
import subsequence.chords
import subsequence.constants
import subsequence.pattern
import subsequence.pattern_builder
from subsequence.motifs import Degree
from subsequence.motifs import Motif as M
from subsequence.motifs import MotifEvent
from subsequence.motifs import Phrase as P

A_MINOR = subsequence.chords.parse_chord("Am")
WRITTEN = M.degrees([2, 2, 2, 2], beats=[0, 1, 2, 3], length=4, durations=0.5)
GENERATED = M.generate(rhythm=[0, 1, 2, 3], length=4, seed=5)
SNAPPING = M.generate(rhythm=[0, 1, 2, 3], length=4, seed=1)		# a line its own fit moves: 59 to 60, 62 to 64


class _AmEverywhere:

	"""A harmony view with Am sounding under every beat."""

	def chord_at (self, beat: float) -> typing.Any:
		return A_MINOR

	def next_chord_at (self, beat: float) -> typing.Any:
		return None


def _builder (length: float = 4.0, cycle: int = 0) -> subsequence.pattern_builder.PatternBuilder:

	pattern = subsequence.pattern.Pattern(channel=0, length=length)

	return subsequence.pattern_builder.PatternBuilder(
		pattern=pattern, cycle=cycle, key="A", scale="minor", rng=random.Random(1), harmony=_AmEverywhere(),
	)


def _placed (p: subsequence.pattern_builder.PatternBuilder) -> typing.List[typing.Tuple[float, int]]:

	return [
		(pulse / subsequence.constants.MIDI_QUARTER_NOTE, note.pitch)
		for pulse in sorted(p._pattern.steps) for note in p._pattern.steps[pulse].notes
	]


def _place (m: M, length: float = 4.0, **kwargs: typing.Any) -> typing.List[typing.Tuple[float, int]]:

	p = _builder(length)
	p.motif(m, root=60, **kwargs)

	return _placed(p)


def test_a_written_line_plays_as_written_on_its_own () -> None:

	"""The premise: alone, the written B's stay B's and the generated line snaps as it always did."""

	assert _place(WRITTEN) == [(0.0, 59), (1.0, 59), (2.0, 59), (3.0, 59)]
	assert _place(GENERATED) == [(0.0, 69), (1.0, 71), (2.0, 72), (3.0, 76)]


def test_a_generated_line_snaps_by_its_own_fit_wherever_it_is () -> None:

	"""Alone, beside a written line or after one, a generated line plays against the chord as it always did.

	Stacked under a written line it used to lose its fit, and after one it
	lent the fit to the written notes, whose snaps then drew from the same
	random stream and moved its own.
	"""

	alone = _place(SNAPPING)

	assert alone == [(0.0, 60), (1.0, 72), (2.0, 71), (3.0, 64)]
	assert [pitch for _, pitch in _place(SNAPPING, fit=0.0)] == [59, 72, 71, 62]
	assert sorted(_place(WRITTEN & SNAPPING)) == sorted(_place(WRITTEN) + alone)
	assert _place(WRITTEN.then(SNAPPING), length=8)[4:] == [(beat + 4, pitch) for beat, pitch in alone]


def test_stacking_is_order_independent () -> None:

	"""``written & generated`` and ``generated & written`` are the same motif, and sound the same.

	Stacking kept only the left operand's fit: the same eight notes placed with
	five off the chord one way round and two the other.
	"""

	assert (WRITTEN & GENERATED) == (GENERATED & WRITTEN)
	assert _place(WRITTEN & GENERATED) == _place(GENERATED & WRITTEN)
	assert all((float(beat), 59) in _place(GENERATED & WRITTEN) for beat in range(4))		# every written B stays a B


def test_a_written_line_joined_to_a_generated_one_still_plays_as_written () -> None:

	"""``then()`` lent the generated fit to the written notes, which snapped to [60, 59, 59, 60]."""

	written_first = _place(WRITTEN.then(GENERATED), length=8)
	written_last = _place(GENERATED.then(WRITTEN), length=8)

	assert written_first[:4] == [(0.0, 59), (1.0, 59), (2.0, 59), (3.0, 59)]
	assert written_last[4:] == [(4.0, 59), (5.0, 59), (6.0, 59), (7.0, 59)]


def test_a_phrase_sounds_the_same_at_any_pattern_length () -> None:

	"""The written bar of written-then-generated sounds the same under a four-beat pattern and an eight-beat one."""

	phrase = P([WRITTEN, GENERATED])

	four = _builder(length=4.0, cycle=0)
	four.phrase(phrase, root=60)

	eight = _builder(length=8.0, cycle=0)
	eight.phrase(phrase, root=60)

	assert _placed(four) == _placed(eight)[:4] == [(0.0, 59), (1.0, 59), (2.0, 59), (3.0, 59)]


def test_rerolling_one_bar_leaves_the_others_sounding_as_they_did () -> None:

	"""reroll() dropped every segment's fit, so the bars it did not touch sounded different - 47 of 60 seeds."""

	for seed in range(20):
		with warnings.catch_warnings():
			warnings.simplefilter("ignore")
			source = M.generate(rhythm=[0, 1, 2, 3], length=4, seed=seed)
			phrase = P.develop(source, bars=2, plan=["a", "b"], seed=3)
			rerolled = phrase.reroll(bar=2, seed=4)

		before = _builder(length=4.0, cycle=0)
		before.phrase(phrase, root=60)

		after = _builder(length=4.0, cycle=0)
		after.phrase(rerolled, root=60)

		assert _placed(before) == _placed(after), f"seed {seed}"


def test_rotating_a_phrase_keeps_its_fit () -> None:

	"""Phrase.rotate() rebuilt its segments without a fit; Motif.rotate() kept it."""

	with warnings.catch_warnings():
		warnings.simplefilter("ignore")
		phrase = P.develop(GENERATED, bars=2, plan=["a", "b"], seed=3)

	rotated = phrase.rotate(1)

	assert [segment.fit for segment in rotated.segments] == [0.7, 0.7]
	assert all(event.fit == 0.7 for segment in rotated.segments for event in segment.events if event.pitch is not None)


def test_a_motif_reads_back_the_fit_its_notes_share () -> None:

	"""0.7 for a generated motif, None for a written one, and None for a mix of the two, whichever way round."""

	assert GENERATED.fit == 0.7
	assert WRITTEN.fit is None
	assert (WRITTEN & GENERATED).fit is None
	assert (GENERATED & WRITTEN).fit is None
	assert M.join([GENERATED, GENERATED]).fit == 0.7


def test_the_fit_control_still_sets_every_note () -> None:

	"""``p.motif(fit=)`` is unchanged: 0 plays everything as written, 1 snaps every strong beat, written notes included.

	This passed before #3458 as well; it pins that the published control did not move.
	"""

	both = WRITTEN & GENERATED

	assert _place(both, fit=0.0) == _place_with_no_harmony(both)
	assert all(pitch % 12 in {9, 0, 4} for _, pitch in _place(both, fit=1.0))


def test_a_rhythm_repitched_by_hand_is_written () -> None:

	"""A generated line's rhythm, given a pitch by hand, plays that pitch: the fit does not leak through.

	This passed before #3458 as well.
	"""

	skeleton = GENERATED.rhythm()

	assert all(event.fit is None for event in skeleton.events)		# no notes, so no fits

	# Through the skeleton, and straight from the generated line: pitched()
	# writes its pitch on every note, so none of them keeps a fit.
	for repitched in (skeleton.pitched(Degree(2)), SNAPPING.pitched(Degree(2))):
		assert repitched.fit is None
		assert [pitch for _, pitch in _place(repitched)] == [59, 59, 59, 59]


def test_a_fit_is_a_chance () -> None:

	"""A note's fit is a probability, so anything outside 0 to 1 is refused where it is written."""

	with pytest.raises(ValueError, match="fit"):
		MotifEvent(beat=0.0, pitch=60, fit=1.5)


def _place_with_no_harmony (m: M) -> typing.List[typing.Tuple[float, int]]:

	"""Where a motif's notes land with no chord under them, so nothing can snap."""

	pattern = subsequence.pattern.Pattern(channel=0, length=4.0)
	p = subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=0, key="A", scale="minor", rng=random.Random(1))
	p.motif(m, root=60)

	return _placed(p)
