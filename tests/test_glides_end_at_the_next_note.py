"""portamento() and slide() glide before the next note's onset even when their note rings on past it (#3478).

Each glide sat in the tail of the first note's whole duration and its reset at the next note's
onset, so a first note that rang on past the next one glided after the reset - bending the next
note, since one channel has one pitch wheel.  Note 60 ringing to pulse 48 over a note 62 from
pulse 24 glided at pulses 40-48.  The glide is now fitted to the first note's time before the
next onset, arriving at the next note's pitch as that note starts, as ``bend()`` was in #3477.

#2957's verification, and #3477, measured this with 60 then 64 - a pair these glides skip for
being wider than the bend range - and so reported that they laid nothing.
"""

import typing

import subsequence.pattern
import subsequence.pattern_builder


def _glided (build: typing.Callable[[subsequence.pattern_builder.PatternBuilder], typing.Any]) -> typing.List[typing.Tuple[int, int]]:

	"""Pitch-wheel events as (pulse, value), in the order they were laid."""

	pattern = subsequence.pattern.Pattern(channel=0, length=4)
	builder = subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=0, default_grid=16)
	build(builder)
	builder._finish_build()

	return [(event.pulse, event.value) for event in pattern.cc_events if event.message_type == "pitchwheel"]


def _overlapping (p: subsequence.pattern_builder.PatternBuilder) -> None:

	p.note(60, beat=0, velocity=90, duration=2)		# rings to pulse 48
	p.note(62, beat=1, velocity=90, duration=1)		# starts at pulse 24


def test_portamento_glides_before_the_next_note_starts () -> None:

	bends = _glided(lambda p: (_overlapping(p), p.portamento(wrap=False)))

	assert bends
	assert max(pulse for pulse, _ in bends) == 24
	assert [value for pulse, value in bends if pulse == 24] == [8191, 0]


def test_slide_without_extend_glides_before_the_next_note_starts () -> None:

	bends = _glided(lambda p: (_overlapping(p), p.slide(notes=[1], extend=False, wrap=False)))

	assert bends
	assert max(pulse for pulse, _ in bends) == 24
	assert [value for pulse, value in bends if pulse == 24] == [8191, 0]


def test_the_glide_takes_its_share_of_the_time_before_the_next_note () -> None:

	"""time=0.5 glides across the second half of the 24 pulses before the next note, not the second half of all 48."""

	bends = _glided(lambda p: (_overlapping(p), p.portamento(time=0.5, wrap=False)))
	rising = [pulse for pulse, value in bends if value != 0]

	assert rising
	assert (min(rising), max(rising)) == (13, 24)


def test_a_last_note_ringing_into_the_next_cycle_glides_before_it () -> None:

	"""The wrapped glide from the last note arrives at the next cycle's first note, pulse 96."""

	def build (p: subsequence.pattern_builder.PatternBuilder) -> None:
		p.note(60, beat=0, velocity=90, duration=1)
		p.note(62, beat=3, velocity=90, duration=2)		# rings to pulse 120, past 96
		p.portamento()

	bends = _glided(build)

	assert max(pulse for pulse, _ in bends) == 96


def test_slide_with_extend_is_unchanged () -> None:

	"""A guard: extend= already stretches the first note to meet its target.  This passed before #3478 as well."""

	bends = _glided(lambda p: (_overlapping(p), p.slide(notes=[1], wrap=False)))

	assert max(pulse for pulse, _ in bends) == 24


def test_notes_that_do_not_overlap_glide_as_before () -> None:

	"""A guard: a first note that ends at the next onset glides in its own tail.  This passed before #3478 as well."""

	def build (p: subsequence.pattern_builder.PatternBuilder) -> None:
		p.note(60, beat=0, velocity=90, duration=1)
		p.note(62, beat=1, velocity=90, duration=1)
		p.portamento(wrap=False)

	bends = _glided(build)

	assert [pulse for pulse, value in bends if value != 0] == [21, 22, 23, 24]
