"""A note keeps the step it was placed on, however far feel moves it (#3447).

``swing()``, ``groove()`` and ``randomize()`` move notes off their grid lines.
The verbs that read the grid - ``scale_velocities()``, ``thin()`` and
``ratchet(steps=)`` - classified a note where it plays: a sixteenth swung half a
step late counted as the next step, and one pulled a pulse early as the step
before.  Each note now records how far the feel moved it (``Note.nudge``), and
those verbs read the step it was placed on.

Every note here has pitch 60 plus the step it was placed on, so that step can
be read back whatever the feel and the transforms did to its position.
"""

import typing

import pytest

import subsequence.groove
import subsequence.pattern
import subsequence.pattern_builder

KICKS = [0, 4, 8, 12]
KEEP_THE_BEATS = [0.0 if step % 4 == 0 else 1.0 for step in range(16)]	# thin() drop priorities: every note off the beat goes
DROP_THE_BEATS = [1.0 if step % 4 == 0 else 0.0 for step in range(16)]	# thin() drop priorities: every note on the beat goes


def _sixteenths (steps: typing.Iterable[int] = range(16)) -> typing.Tuple[subsequence.pattern.Pattern, subsequence.pattern_builder.PatternBuilder]:

	"""One bar of sixteenths, each pitched 60 plus the step it is placed on."""

	pattern = subsequence.pattern.Pattern(channel=0, length=4)
	builder = subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=0, default_grid=16)

	for step in steps:
		builder.note(60 + step, beat=step * 0.25, velocity=100, duration=0.25)

	return pattern, builder


def _placed_steps (pattern: subsequence.pattern.Pattern, keep: typing.Callable[[subsequence.pattern.Note], bool] = lambda note: True) -> typing.List[int]:

	"""The steps the pattern's notes were placed on, read from their pitch, one entry per note."""

	return sorted(note.pitch - 60 for step in pattern.steps.values() for note in step.notes if keep(note))


def _silenced (pattern: subsequence.pattern.Pattern) -> typing.List[int]:

	"""The steps whose notes a duck map took to velocity 0."""

	return _placed_steps(pattern, keep = lambda note: note.velocity == 0)


def _plays_at (pattern: subsequence.pattern.Pattern, placed_step: int) -> int:

	"""Where the note placed on *placed_step* plays now."""

	return next(pulse for pulse, step in pattern.steps.items() for note in step.notes if note.pitch - 60 == placed_step)


@pytest.mark.parametrize("percent", [71, 75, 88, 99])
def test_a_duck_map_after_swing_silences_the_notes_on_its_steps (percent: int) -> None:

	"""Swung half a step or more, an offbeat sixteenth still takes its own step's factor.

	From 71% the offbeats move 3 pulses or more of a 6-pulse step, and
	``scale_velocities()`` rounded each to the step after it: a duck on the
	kick steps silenced steps 3, 7, 11 and 15 as well as 0, 4, 8 and 12.
	"""

	pattern, builder = _sixteenths()
	builder.swing(percent)

	assert _plays_at(pattern, 1) - 6 >= 3		# the offbeats really are half a step late

	builder.scale_velocities(builder.duck_map(KICKS))

	assert _silenced(pattern) == KICKS


def test_thin_after_an_early_groove_keeps_the_notes_placed_on_the_beat () -> None:

	"""A beat pulled a pulse early is still a beat to ``thin()``.

	``thin()`` floored each note's pulse into a step, so a beat one pulse early
	counted as the sixteenth before it, the first thing a thinning drops.  With
	the strength strategy at full amount, beats 2 to 4 went every time.
	"""

	pattern, builder = _sixteenths()
	builder.groove(subsequence.groove.Groove(offsets=[-1 / 24], grid=0.25))

	assert _plays_at(pattern, 4) == 23		# beat 2 plays a pulse early

	builder.thin(strategy=KEEP_THE_BEATS, amount=1.0)

	assert _placed_steps(pattern) == KICKS


def test_thin_after_randomize_keeps_the_notes_placed_on_the_beat () -> None:

	"""Timing jitter moves notes both ways, and each still counts as its own step.

	This seed pulls beats 2 and 4 two pulses early, which ``thin()`` counted
	as offbeats, and pulls steps 1, 9 and 13 back into the beat before them,
	which it counted as beats.
	"""

	pattern, builder = _sixteenths()
	builder.randomize(timing=0.1, seed=4)

	assert _plays_at(pattern, 4) < 24 and _plays_at(pattern, 12) < 72
	assert _plays_at(pattern, 9) < 54

	builder.thin(strategy=KEEP_THE_BEATS, amount=1.0)

	assert _placed_steps(pattern) == KICKS


def test_ratchet_steps_after_an_early_groove_rolls_the_notes_placed_on_those_steps () -> None:

	"""``ratchet(steps=[4, 8, 12])`` rolls beats 2 to 4 when a groove pulls them early.

	It shared ``thin()``'s floor, so it rolled steps 5, 9 and 13 instead.
	"""

	pattern, builder = _sixteenths()
	builder.groove(subsequence.groove.Groove(offsets=[-1 / 24], grid=0.25))
	builder.ratchet(2, steps=[4, 8, 12])

	placed = _placed_steps(pattern)

	assert [step for step in range(16) if placed.count(step) == 2] == [4, 8, 12]


def test_a_ratchets_sub_hits_count_as_the_step_their_note_was_placed_on () -> None:

	"""A roll on a swung note belongs to that note's step, all of it.

	Swung 75%, the offbeat on step 3 plays at pulse 21 and its second sub-hit
	at 24, on beat 2's line.  Read where it plays, that sub-hit was a beat,
	and a thinning of the beats took it out of the roll.
	"""

	pattern, builder = _sixteenths()
	builder.swing(75)
	builder.ratchet(2)

	assert 24 in {pulse for pulse, step in pattern.steps.items() for note in step.notes if note.pitch == 63}

	builder.thin(strategy=DROP_THE_BEATS, amount=1.0)

	assert _placed_steps(pattern) == sorted(2 * [step for step in range(16) if step not in KICKS])


def test_rotate_carries_each_note_with_the_step_it_was_placed_on () -> None:

	"""Rotated two steps, the swung notes duck by their new steps and nothing else.

	The notes now on the kick steps are those placed on steps 14, 2, 6 and 10.
	Read where they play, the swung notes placed on steps 1, 5, 9 and 13
	rounded up onto the kick steps as well.
	"""

	pattern, builder = _sixteenths()
	builder.swing(75)
	builder.rotate(2)
	builder.scale_velocities(builder.duck_map(KICKS))

	assert _silenced(pattern) == [2, 6, 10, 14]


def test_reverse_carries_each_note_with_the_step_it_was_placed_on () -> None:

	"""Reversed, a swung note plays early of its mirrored step and still ducks by it.

	The note placed on step s is mirrored to step 16 - s, so the kick steps
	still duck the notes placed on 0, 4, 8 and 12.  Read where they play, the
	swung notes placed on steps 3, 7, 11 and 15 ducked too.
	"""

	pattern, builder = _sixteenths()
	builder.swing(75)
	builder.reverse()
	builder.scale_velocities(builder.duck_map(KICKS))

	assert _silenced(pattern) == KICKS


def test_reverse_keeps_a_late_downbeat_on_the_downbeat () -> None:

	"""The mirrored downbeat is the downbeat, even when a late feel plays it before the bar line.

	Every note three pulses late, then reversed: the note placed on step 0
	plays at pulse 93, the end of the bar, and belongs to step 0.
	"""

	pattern, builder = _sixteenths()
	builder.groove(subsequence.groove.Groove(offsets=[3 / 24], grid=0.25))
	builder.reverse()

	assert _plays_at(pattern, 0) == 93

	builder.thin(strategy=DROP_THE_BEATS, amount=1.0)

	assert _placed_steps(pattern) == [step for step in range(16) if step not in KICKS]


def test_stretch_carries_each_note_with_the_step_it_was_placed_on () -> None:

	"""Stretched to twice the length, notes pulled early still count as the steps they were placed on.

	Eighths pulled two pulses early land on 20, 44 and 68 at double length:
	four pulses early of beats 2 to 4, which ``thin()`` counted as offbeats.
	"""

	pattern, builder = _sixteenths(steps=[0, 2, 4, 6])
	builder.groove(subsequence.groove.Groove(offsets=[-2 / 24], grid=0.25))
	builder.stretch(2.0)

	assert [_plays_at(pattern, step) for step in (2, 4, 6)] == [20, 44, 68]

	builder.thin(strategy=KEEP_THE_BEATS, amount=1.0)

	assert _placed_steps(pattern) == [0, 2, 4, 6]
