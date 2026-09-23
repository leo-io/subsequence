"""A glide under a tuning arrives where its target sounds (#3476).

portamento() and slide() lay their bends in 12-TET semitones toward the target, and the tuning
pass only shifted each bend by the offset of the note sounding under it.  Under 19-TET a glide
from 60 to 62 climbed toward 8191 - 200 cents, the 12-TET distance - and the target then sounded
at 61 bent +1078, 126.3 cents: an overshoot of 74 cents, and a snap.  Each glide's bends are now
tagged with the notes it joins, and the tuning re-aims them at the tuned distance, keeping each
bend's share of the way.
"""

import typing

import subsequence.pattern
import subsequence.pattern_builder
import subsequence.tuning

NINETEEN = subsequence.tuning.Tuning.equal(19)


def _glide (first: int, second: int, verb: str = "portamento", tuning: typing.Optional[subsequence.tuning.Tuning] = NINETEEN) -> typing.List[typing.Tuple[int, int, int]]:

	"""The bends of a two-note glide from *first* to *second*, as (pulse, value, priority) in laid order."""

	pattern = subsequence.pattern.Pattern(channel=0, length=4)
	p = subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=0, default_grid=16)
	p.note(first, beat=0, velocity=90, duration=1)
	p.note(second, beat=1, velocity=90, duration=1)

	if verb == "portamento":
		p.portamento(wrap=False)
	else:
		p.slide(notes=[1], wrap=False)

	if tuning is not None:
		p.apply_tuning(tuning)

	p._finish_build()

	return [(event.pulse, event.value, event.priority) for event in pattern.cc_events if event.message_type == "pitchwheel"]


def _semitones (value: int) -> float:

	return value / 8192.0 * 2.0


def test_a_glide_arrives_where_its_target_sounds () -> None:

	"""The glide ends 126.3 cents above 60, where 61 bent +1078 sounds - it climbed to 200.

	Within one step of the pitch wheel, 1/4096 of a semitone: each of the two bends is rounded.
	"""

	bends = _glide(60, 62)
	glide_end = [value for pulse, value, priority in bends if pulse == 24 and priority == 0][0]
	target = [value for pulse, value, priority in bends if pulse == 24 and priority == -1][0]

	assert target == 1078
	assert abs((60 + _semitones(glide_end)) - (61 + _semitones(target))) <= 1.0001 / 4096


def test_a_glide_never_passes_its_target () -> None:

	"""No overshoot on the way: every bend of the ramp stays at or below the target's tuned pitch."""

	bends = _glide(60, 62)

	assert max(value for pulse, value, priority in bends if pulse < 24) < 5173


def test_after_the_glide_the_target_sounds_in_tune () -> None:

	"""The last bend at the target's onset is its own tuning, 1078 - the reset follows the glide's end.

	A guard for that order: the reset came last before #3476 as well.
	"""

	bends = _glide(60, 62)

	assert [value for pulse, value, priority in bends if pulse == 24 and priority == 0][-1] == 1078


def test_a_falling_glide_starts_where_its_first_note_sounds () -> None:

	"""62 sounds as 61 +1078; a glide down to 60 starts at 1078 and ends a whole semitone below 61."""

	bends = _glide(62, 60)
	ramp = [value for pulse, value, priority in bends if 20 <= pulse <= 24 and priority == 0]

	assert ramp[0] == 1078
	assert ramp[-2] == -4096		# the glide's end, before the reset to 60's own tuning, 0


def test_a_slide_is_re_aimed_as_a_portamento_is () -> None:

	"""slide() tags its bends too: it arrives at 5173, as the portamento does, where it climbed to 8191."""

	slide = _glide(60, 62, verb="slide")

	assert [value for pulse, value, priority in slide if pulse == 24 and priority == 0][0] == 5173
	assert slide == _glide(60, 62)


def test_twelve_tone_equal_temperament_glides_as_before () -> None:

	"""A guard: under 12-TET the tuned distance is the laid one.  This passed before #3476 as well."""

	assert [(pulse, value) for pulse, value, _ in _glide(60, 62, tuning=subsequence.tuning.Tuning.equal(12)) if value] == \
		[(pulse, value) for pulse, value, _ in _glide(60, 62, tuning=None) if value]


def test_a_bend_is_still_shifted_by_the_note_it_bends () -> None:

	"""A guard: bend() has no target, so it keeps the additive shift.  This passed before #3476 as well."""

	pattern = subsequence.pattern.Pattern(channel=0, length=4)
	p = subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=0, default_grid=16)
	p.note(62, beat=0, velocity=90, duration=1)
	p.bend(0, amount=0.25)
	p.apply_tuning(NINETEEN)
	p._finish_build()

	halfway = [event.value for event in pattern.cc_events if event.message_type == "pitchwheel" and event.pulse == 12]

	assert halfway == [1024 + 1078]
