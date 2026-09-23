"""A drone follows the pattern's tuning, as the notes beside it do (#3475).

A drone is a raw ``note_on`` in ``pattern.raw_note_events``, and the tuning pass walked only
``pattern.steps``: under 19-TET a note 62 became 61 bent +1078 (degree 2, 126.3 cents) while a
drone 62 stayed a 12-TET D.  Now a drone's ``note_on`` takes the nearest note and a bend at its
onset, and a ``note_off`` the same nearest note, so ``drone_off()`` releases the note the drone
sounds - in whichever cycle it comes.
"""

import typing

import subsequence.pattern
import subsequence.pattern_builder
import subsequence.tuning

NINETEEN = subsequence.tuning.Tuning.equal(19)


def _built (build: typing.Callable[[subsequence.pattern_builder.PatternBuilder], typing.Any], cycle: int = 0) -> subsequence.pattern.Pattern:

	pattern = subsequence.pattern.Pattern(channel=3, length=4)
	builder = subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=cycle, default_grid=16)
	build(builder)
	builder.apply_tuning(NINETEEN)
	builder._finish_build()

	return pattern


def _drone_bends (pattern: subsequence.pattern.Pattern, pulse: int) -> typing.List[typing.Tuple[int, typing.Optional[int], int]]:

	"""Pitch-wheel events at *pulse*, as (value, channel, priority)."""

	return [(event.value, event.channel, event.priority) for event in pattern.cc_events if event.message_type == "pitchwheel" and event.pulse == pulse]


def test_a_drone_takes_the_tuned_pitch () -> None:

	"""Drone 62 plays 61 bent +1078, as note 62 does: 19-TET's degree 2."""

	pattern = _built(lambda p: p.drone(62, beat=2))

	assert [(event.message_type, event.pitch) for event in pattern.raw_note_events] == [("note_on", 61)]
	assert _drone_bends(pattern, 48) == [(1078, 3, -1)]


def test_a_drone_and_a_note_on_one_pitch_sound_alike () -> None:

	pattern = _built(lambda p: (p.note(62, beat=0, velocity=90, duration=1), p.drone(62, beat=2)))

	note = next(note for step in pattern.steps.values() for note in step.notes)

	assert note.pitch == pattern.raw_note_events[0].pitch == 61
	assert _drone_bends(pattern, 0)[0][0] == _drone_bends(pattern, 48)[0][0] == 1078


def test_drone_off_releases_the_note_the_drone_sounds () -> None:

	"""In a later cycle, drone_off(62) sends a note_off for 61, the note that is sounding, where it sent 62."""

	started = _built(lambda p: p.drone(62), cycle=0)
	ended = _built(lambda p: p.drone_off(62), cycle=1)

	assert [(event.message_type, event.pitch) for event in started.raw_note_events + ended.raw_note_events] == [("note_on", 61), ("note_off", 61)]
	assert _drone_bends(ended, 0) == []


def test_a_part_that_is_only_a_drone_is_tuned () -> None:

	"""The tuning pass returned at once when a pattern had no step notes, drone or no drone."""

	pattern = _built(lambda p: p.drone(64))

	nearest, bend = NINETEEN.pitch_bend_for_note(64)

	assert pattern.raw_note_events[0].pitch == nearest
	assert _drone_bends(pattern, 0) == [(subsequence.tuning._norm_to_raw(bend), 3, -1)]


def test_step_notes_are_tuned_as_before () -> None:

	"""A guard: the notes' own tuning is unchanged.  This passed before #3475 as well."""

	pattern = _built(lambda p: p.note(62, beat=0, velocity=90, duration=1))

	assert [note.pitch for step in pattern.steps.values() for note in step.notes] == [61]
	assert _drone_bends(pattern, 0) == [(1078, 3, -1)]
