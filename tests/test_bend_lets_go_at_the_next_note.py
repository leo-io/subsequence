"""bend() lets go at the next note's onset even when its note rings on past it (#3477).

The ramp was measured against the bent note's whole duration and the reset laid at the next
note's onset, so a note that rang on past the next one kept bending after the reset - and one
channel has one pitch wheel, so the next note was bent too.  The ramp is now fitted to the
note's time before the next onset, still reaching its full amount.
"""

import typing

import subsequence.pattern
import subsequence.pattern_builder


def _builder () -> typing.Tuple[subsequence.pattern.Pattern, subsequence.pattern_builder.PatternBuilder]:

	pattern = subsequence.pattern.Pattern(channel=0, length=4)

	return pattern, subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=0, default_grid=16)


def _bends (pattern: subsequence.pattern.Pattern) -> typing.List[typing.Tuple[int, int]]:

	"""Pitch-wheel events as (pulse, value), in the order they were laid."""

	return [(event.pulse, event.value) for event in pattern.cc_events if event.message_type == "pitchwheel"]


def test_nothing_bends_after_the_next_notes_onset () -> None:

	"""Note 0 rings to pulse 48 and note 1 starts at 24: the bend ran on to 48, bending note 1."""

	pattern, p = _builder()
	p.note(60, beat=0, velocity=90, duration=2)
	p.note(64, beat=1, velocity=90, duration=1)
	p.bend(0, amount=0.5)
	p._finish_build()

	bends = _bends(pattern)

	assert bends
	assert max(pulse for pulse, _ in bends) == 24


def test_the_ramp_still_reaches_its_full_amount () -> None:

	"""Fitted rather than cut short: 4096 at the next onset, and the reset after it."""

	pattern, p = _builder()
	p.note(60, beat=0, velocity=90, duration=2)
	p.note(64, beat=1, velocity=90, duration=1)
	p.bend(0, amount=0.5)
	p._finish_build()

	at_the_onset = [value for pulse, value in _bends(pattern) if pulse == 24]

	assert at_the_onset == [4096, 0]


def test_start_and_end_count_the_notes_time_before_the_next () -> None:

	"""start=0.5 begins halfway to the next note, at pulse 12, where it began halfway through the whole note, at 24."""

	pattern, p = _builder()
	p.note(60, beat=0, velocity=90, duration=2)
	p.note(64, beat=1, velocity=90, duration=1)
	p.bend(0, amount=0.5, start=0.5)
	p._finish_build()

	ramp = [pulse for pulse, value in _bends(pattern) if value != 0]

	assert ramp
	assert (min(ramp), max(ramp)) == (13, 24)


def test_the_last_note_lets_go_before_the_next_cycle_begins () -> None:

	"""The last note rings past the bar line into the next cycle's first note, at pulse 96: its bend now ends there."""

	pattern, p = _builder()
	p.note(60, beat=0, velocity=90, duration=1)
	p.note(64, beat=3, velocity=90, duration=2)
	p.bend(-1, amount=0.5)
	p._finish_build()

	bends = _bends(pattern)

	assert max(pulse for pulse, _ in bends) == 96
	assert [value for pulse, value in bends if pulse == 96] == [4096, 0]


def test_a_note_that_ends_before_the_next_bends_as_before () -> None:

	"""A guard: a note that lets go before the next one is measured against itself.  This passed before #3477 as well."""

	pattern, p = _builder()
	p.note(60, beat=0, velocity=90, duration=0.5)
	p.note(64, beat=1, velocity=90, duration=1)
	p.bend(0, amount=0.5)
	p._finish_build()

	ramp = [pulse for pulse, value in _bends(pattern) if value != 0]

	assert max(ramp) == 12
