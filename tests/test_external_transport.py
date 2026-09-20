"""Following a master's transport under ``clock_follow`` (#3053, decision 14 of #2991).

*"Follow as a slave. Stop pauses: it holds position and releases notes. Continue
resumes. Start restarts from bar 0: it flushes, releases and rebuilds every part
from cycle 0. The session ends only with Ctrl+C or ``stop()``."*

Three things were wrong, all measured on `8977ef5`:

**Stop ended the session.** ``running = False``, the loop task completed, and a
Continue after it did nothing — 48 pulses stayed 48.

**Start released nothing.** A note still sounding when a Start arrived was left
on; it came off 193 pulses (8.04 beats) later, which was its own written
duration. The Start had no effect on it at all.

**Start did not restart.** ``pulse_count`` went to 0 but the queues kept the old
numbering, so with a 4-bar pattern playing a note on each of its 16 beats,
stopped six beats in, the first thing heard after the Start was **pitch 66** —
beat 6, exactly where the transport had been interrupted — 6.04 beats later. A
Start was heard as a silence as long as the piece had already played, followed
by the middle of the phrase.

``tests/test_midi_input.py`` covers the pulse arithmetic; this file covers what
a listener hears.
"""

import asyncio
import time
import typing

import mido
import pytest

import subsequence
import subsequence.pattern
import subsequence.sequencer


PPQN = 24


def _follower () -> subsequence.sequencer.Sequencer:

	"""A follower on patch_midi_multi's recording ports.

	The default fake output discards what it is sent, and every question here
	is about what a listener hears — so these use the named spies.
	"""

	return subsequence.sequencer.Sequencer(
		output_device_name = "Primary MIDI",
		initial_bpm = 120,
		input_device_name = "Input A",
		clock_follow = True,
	)


async def _drain (sequencer: subsequence.sequencer.Sequencer) -> None:

	"""Let the clock loop consume everything injected into its input queue."""

	for _ in range(5000):
		if sequencer._midi_input_queue.empty():
			break
		await asyncio.sleep(0)
	else:
		raise AssertionError("the clock loop never drained its input queue")

	for _ in range(200):
		await asyncio.sleep(0)


async def _send (sequencer: subsequence.sequencer.Sequencer, kind: str) -> None:

	sequencer._midi_input_queue.put_nowait((0, mido.Message(kind), time.perf_counter()))
	await _drain(sequencer)


async def _tick (sequencer: subsequence.sequencer.Sequencer, count: int) -> None:

	for _ in range(count):
		sequencer._midi_input_queue.put_nowait((0, mido.Message("clock"), time.perf_counter()))

	await _drain(sequencer)


def _sixteen_beat_scale () -> subsequence.pattern.Pattern:

	"""Four bars, one note per beat, each beat a different pitch.

	The pitch is what makes the restart legible: pitch 60 is beat 0, so a
	listener can tell "restarted from the top" from "resumed mid-phrase"
	without counting pulses.
	"""

	pattern = subsequence.pattern.Pattern(channel = 0, length = 16.0, device = 0)

	for beat in range(16):
		pattern.add_note(position = beat * PPQN, pitch = 60 + beat, velocity = 100, duration = 6)

	return pattern


def _note_ons (spy: typing.Any, since: int = 0) -> typing.List[mido.Message]:

	return [
		message for message in spy.sent[since:]
		if message.type == "note_on" and message.velocity > 0
	]


def _note_offs (spy: typing.Any, since: int = 0) -> typing.List[mido.Message]:

	return [
		message for message in spy.sent[since:]
		if message.type == "note_off" or (message.type == "note_on" and message.velocity == 0)
	]


# ---------------------------------------------------------------------------
# Stop holds the position
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_stop_releases_what_is_sounding (patch_midi_multi: typing.Dict[str, typing.Any]) -> None:

	"""A held note comes off when the master stops, rather than ringing on."""

	sequencer = _follower()
	await sequencer.start()

	try:
		await _send(sequencer, "start")

		pattern = subsequence.pattern.Pattern(channel = 0, length = 16.0, device = 0)
		pattern.add_note(position = 0, pitch = 60, velocity = 100, duration = 8 * PPQN)
		await sequencer.schedule_pattern_repeating(pattern, 0)

		await _tick(sequencer, 2 * PPQN)

		assert sequencer.active_notes, "nothing was sounding, so the release below proves nothing"

		await _send(sequencer, "stop")

		assert not sequencer.active_notes, "a note was left ringing across the stop"

	finally:
		await sequencer.stop()


@pytest.mark.asyncio
async def test_a_continue_carries_on_from_where_the_stop_left_off (patch_midi_multi: typing.Dict[str, typing.Any]) -> None:

	"""The piece resumes mid-phrase, which is the whole difference from Start."""

	sequencer = _follower()
	await sequencer.start()

	try:
		await _send(sequencer, "start")
		await sequencer.schedule_pattern_repeating(_sixteen_beat_scale(), 0)

		await _tick(sequencer, 6 * PPQN)

		spy = patch_midi_multi["Primary MIDI"]
		heard_before = [message.note for message in _note_ons(spy)]

		assert heard_before == [60, 61, 62, 63, 64, 65], f"the pattern did not play as written: {heard_before}"

		await _send(sequencer, "stop")

		mark = len(spy.sent)

		await _send(sequencer, "continue")
		await _tick(sequencer, 2 * PPQN)

		heard_after = [message.note for message in _note_ons(spy, mark)]

		assert heard_after == [66, 67], f"a continue did not resume the phrase: {heard_after}"
		assert sequencer.pulse_count == 8 * PPQN

	finally:
		await sequencer.stop()


@pytest.mark.asyncio
async def test_the_session_survives_a_stop (patch_midi_multi: typing.Dict[str, typing.Any]) -> None:

	"""Only Ctrl+C or stop() ends a session — never the master's Stop button."""

	sequencer = _follower()
	await sequencer.start()

	try:
		await _send(sequencer, "start")
		await _tick(sequencer, PPQN)

		await _send(sequencer, "stop")

		assert sequencer.running is True
		assert sequencer.task is not None and not sequencer.task.done()

		# And it is still following: a later Start is still heard.
		await _send(sequencer, "start")
		await _tick(sequencer, PPQN)

		assert sequencer.pulse_count == PPQN, "the loop stopped listening after the stop"

	finally:
		await sequencer.stop()


@pytest.mark.asyncio
async def test_a_user_cannot_resume_a_transport_that_is_not_theirs (patch_midi_multi: typing.Dict[str, typing.Any]) -> None:

	"""resume() refuses under clock_follow, exactly as pause() does.

	Without the refusal ``resume()`` cleared the paused flag while the transport
	stayed held, so ``paused`` reported False with nothing advancing.
	"""

	sequencer = _follower()
	await sequencer.start()

	try:
		await _send(sequencer, "start")
		await _tick(sequencer, PPQN)
		await _send(sequencer, "stop")

		assert sequencer.paused is True

		sequencer.resume()

		assert sequencer.paused is True, "resume() released a transport belonging to the master"

		await _tick(sequencer, PPQN)

		assert sequencer.pulse_count == PPQN, "resume() restarted a clock it does not own"

	finally:
		await sequencer.stop()


# ---------------------------------------------------------------------------
# Start goes back to the top
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_start_is_heard_from_the_top_of_the_phrase (patch_midi_multi: typing.Dict[str, typing.Any]) -> None:

	"""The finding: a Start six beats in was heard as pitch 66, 6.04 beats later.

	Pitch is the whole point. A Start must sound beat 0 of the pattern —
	pitch 60 — on the next tick, not the note the transport was interrupted on.
	"""

	sequencer = _follower()
	await sequencer.start()

	try:
		await _send(sequencer, "start")
		await sequencer.schedule_pattern_repeating(_sixteen_beat_scale(), 0)

		await _tick(sequencer, 6 * PPQN)

		spy = patch_midi_multi["Primary MIDI"]

		assert _note_ons(spy), "the pattern never played, so the restart below proves nothing"

		mark = len(spy.sent)

		await _send(sequencer, "start")
		await _tick(sequencer, 2 * PPQN)

		heard = [message.note for message in _note_ons(spy, mark)]

		assert heard, "a restarted piece stayed silent for two beats"
		assert heard[0] == 60, f"a start resumed mid-phrase on pitch {heard[0]} instead of the top"
		assert heard == [60, 61], f"the restarted phrase did not carry on from its top: {heard}"

	finally:
		await sequencer.stop()


@pytest.mark.asyncio
async def test_a_start_releases_what_is_sounding (patch_midi_multi: typing.Dict[str, typing.Any]) -> None:

	"""The held note was left on; it came off 8.04 beats later, when it always would."""

	sequencer = _follower()
	await sequencer.start()

	try:
		await _send(sequencer, "start")

		pattern = subsequence.pattern.Pattern(channel = 0, length = 16.0, device = 0)
		pattern.add_note(position = 0, pitch = 60, velocity = 100, duration = 8 * PPQN)
		await sequencer.schedule_pattern_repeating(pattern, 0)

		await _tick(sequencer, 2 * PPQN)

		assert sequencer.active_notes, "nothing was sounding, so the release below proves nothing"

		spy = patch_midi_multi["Primary MIDI"]
		mark = len(spy.sent)

		await _send(sequencer, "start")

		assert _note_offs(spy, mark), "a start left the sounding note on"
		assert not sequencer.active_notes

	finally:
		await sequencer.stop()


@pytest.mark.asyncio
async def test_a_start_drops_the_events_the_old_position_had_queued (patch_midi_multi: typing.Dict[str, typing.Any]) -> None:

	"""20 events stayed queued at pulses 144-366 while the clock restarted at 0.

	That is the mechanism behind the silence: the piece had to tick all the way
	back up to 144 before anything it had queued came due.
	"""

	sequencer = _follower()
	await sequencer.start()

	try:
		await _send(sequencer, "start")
		await sequencer.schedule_pattern_repeating(_sixteen_beat_scale(), 0)

		await _tick(sequencer, 6 * PPQN)

		before = sorted(event.pulse for event in sequencer.event_queue)

		assert before, "nothing was queued, so the flush below proves nothing"
		assert min(before) >= 6 * PPQN, f"the queue held nothing ahead of the clock: {before[:4]}"

		spy = patch_midi_multi["Primary MIDI"]
		mark = len(spy.sent)

		await _send(sequencer, "start")

		after = sorted(event.pulse for event in sequencer.event_queue)

		assert after, "the restart queued nothing at all — the piece would be silent"
		assert min(after) == 0, f"cycle 0 was not laid down: the earliest queued pulse is {min(after)}"

		# Exactly one cycle: sixteen notes, each with its note_off.  A pulse
		# range will not do — the old position's events land between 144 and
		# 366, which is inside the fresh cycle's own 0 to 366, so "nothing
		# queued past the end" is true whether they were dropped or not.
		assert len(after) == 32, (
			f"the queue holds {len(after)} events where one cycle is 32 — "
			f"the old position's events are still in it"
		)

		# And the audible consequence, which is what a listener would notice:
		# left unflushed, the old position's copy of each note sounds again
		# beside the restarted one.
		await _tick(sequencer, 8 * PPQN)

		heard = [message.note for message in _note_ons(spy, mark)]

		assert heard == [60, 61, 62, 63, 64, 65, 66, 67], (
			f"the restarted cycle did not play cleanly through: {heard}"
		)

	finally:
		await sequencer.stop()


@pytest.mark.asyncio
async def test_a_start_re_anchors_the_reschedule_heap (patch_midi_multi: typing.Dict[str, typing.Any]) -> None:

	"""The pattern's next rebuild is counted from cycle 0, not from where it was."""

	sequencer = _follower()
	await sequencer.start()

	try:
		await _send(sequencer, "start")
		pattern = _sixteen_beat_scale()
		await sequencer.schedule_pattern_repeating(pattern, 0)

		await _tick(sequencer, 20 * PPQN)		# past the first rebuild

		anchored = [entry[2].cycle_start_pulse for entry in sequencer.reschedule_queue]

		assert anchored and anchored[0] > 0, f"the pattern never rebuilt, so re-anchoring is vacuous: {anchored}"

		await _send(sequencer, "start")

		cycles = [entry[2].cycle_start_pulse for entry in sequencer.reschedule_queue]
		due = [entry[0] for entry in sequencer.reschedule_queue]

		assert cycles == [0], f"the pattern is still anchored on its old cycle: {cycles}"
		assert due == [16 * PPQN - PPQN], f"the next rebuild is not one lookahead before cycle 1: {due}"
		assert pattern._cycle_start_pulse == 0

	finally:
		await sequencer.stop()


@pytest.mark.asyncio
async def test_a_start_puts_a_repeating_callback_back_where_it_began (patch_midi_multi: typing.Dict[str, typing.Any]) -> None:

	"""A clock scheduled one interval in must not fire at the restart.

	The harmonic clock is scheduled that way on purpose — ``HarmonicState``
	already holds the tonic, so firing at pulse 0 would advance the harmony a
	step the piece never asked for. A callback scheduled at 0 does fire there.
	Nothing but ``initial_start_pulse`` tells the two apart.
	"""

	sequencer = _follower()
	await sequencer.start()

	try:
		await _send(sequencer, "start")

		fired_at_zero: typing.List[int] = []
		fired_skipping: typing.List[int] = []

		await sequencer.schedule_callback_repeating(
			lambda pulse: fired_at_zero.append(pulse), interval_beats = 4, start_pulse = 0,
		)
		await sequencer.schedule_callback_repeating(
			lambda pulse: fired_skipping.append(pulse), interval_beats = 4, start_pulse = 4 * PPQN,
		)

		await _tick(sequencer, 8 * PPQN)

		assert fired_at_zero, "the callback scheduled at 0 never fired, so the restart proves nothing"

		at_zero_before = len(fired_at_zero)
		skipping_before = len(fired_skipping)

		await _send(sequencer, "start")
		await _tick(sequencer, 1)

		assert len(fired_at_zero) == at_zero_before + 1, (
			"the callback scheduled at pulse 0 did not fire at the restart"
		)
		assert len(fired_skipping) == skipping_before, (
			"a callback scheduled one interval in fired at the restart — the harmonic "
			"clock would advance a step the piece never asked for"
		)

	finally:
		await sequencer.stop()


@pytest.mark.asyncio
async def test_stopping_does_not_wait_for_the_cable (patch_midi_multi: typing.Dict[str, typing.Any]) -> None:

	"""Ctrl+C on a clock-following piece quits now, not in two seconds.

	The external loop parks on its input queue for up to two seconds at a time.
	That used to be invisible because a master's Stop ended the loop; a Stop
	holds the position now, so ``stop()`` is the way out and it has to wake the
	loop rather than wait for a timeout that exists only to notice a silent
	cable.
	"""

	sequencer = _follower()
	await sequencer.start()

	await _send(sequencer, "start")
	await _tick(sequencer, PPQN)

	assert sequencer.pulse_count == PPQN, "the clock never ran, so the shutdown below proves nothing"

	began = time.perf_counter()
	await sequencer.stop()
	took = time.perf_counter() - began

	assert took < 0.5, f"stopping a clock-following session took {took:.2f}s waiting on the cable"


@pytest.mark.asyncio
async def test_the_clock_loop_ends_without_an_exception (patch_midi_multi: typing.Dict[str, typing.Any]) -> None:

	"""Shutting down must not leave the loop dying on its way out.

	``stop()`` logs and swallows an exception from the loop task, so that a
	crashed loop cannot abort the cleanup that a dying session needs most —
	which also means **a loop that dies on shutdown looks exactly like one
	that ended cleanly**, from the outside and from the suite.

	It cost nothing to catch here once. The wake-up message ``stop()`` pushes
	has to be the same shape as one the input callback pushes, and when the
	callback started stamping an arrival time (#3066) the wake-up did not —
	so every shutdown raised ``ValueError: not enough values to unpack`` into
	that swallow, while the timing test above went on passing.
	"""

	sequencer = _follower()
	await sequencer.start()

	await _send(sequencer, "start")
	await _tick(sequencer, PPQN)

	assert sequencer.pulse_count == PPQN, "the clock never ran, so the shutdown below proves nothing"

	task = sequencer.task
	await sequencer.stop()

	assert task is not None and task.done()
	assert not task.cancelled(), "the loop was cancelled rather than ending on its own"
	assert task.exception() is None, f"the clock loop died on shutdown: {task.exception()!r}"
