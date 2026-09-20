"""Where a followed tempo is measured from (#3066, M9 of the 2026-09-19 review).

`_run_loop_external_clock` took `time.perf_counter()` **when it dequeued** a
clock tick, not when the tick came off the cable. Every delay in between — a
pattern rebuild, a busy callback, an ordinary scheduling hiccup — was therefore
read as a change of tempo. And `_estimate_bpm` writes a `set_tempo` meta event
into the recording whenever its rounded estimate moves, so those went into the
file: a steady 120 BPM master with one 60 ms stall wrote **eight** tempo events
where it should write one, reaching down to 104 BPM.

The arrival time is stamped in `_on_midi_input` now, on the port's own callback
thread, and travels on the queue beside the message.

**A silence is not a slow tempo.** The averaging window is a beat wide, so a
master that stops and starts again left a window straddling the gap. Measured
with a two-second silence, a steady 120 BPM master read **23 BPM for 23 ticks**;
a longer one reaches 0, which the review saw. A gap now starts the window again.
"""

import asyncio
import time
import typing

import mido
import pytest

import subsequence
import subsequence.sequencer


PPQN = 24
TICK = 60.0 / 120 / PPQN		# one tick of a steady 120 BPM master


def _follower (initial_bpm: float = 60) -> subsequence.sequencer.Sequencer:

	"""A follower whose constructor tempo is deliberately WRONG.

	60 where the ticks say 120, so a correct reading can only have come from
	the ticks — a sequencer that ignored them entirely would read 60 and pass
	a test that merely checked the tempo was sensible.
	"""

	return subsequence.sequencer.Sequencer(
		output_device_name = "Dummy MIDI",
		initial_bpm = initial_bpm,
		input_device_name = "Dummy MIDI",
		clock_follow = True,
	)


async def _drain (sequencer: subsequence.sequencer.Sequencer) -> None:

	for _ in range(5000):
		if sequencer._midi_input_queue.empty():
			break
		await asyncio.sleep(0)
	else:
		raise AssertionError("the clock loop never drained its input queue")

	for _ in range(200):
		await asyncio.sleep(0)


def _tempo_events (sequencer: subsequence.sequencer.Sequencer) -> typing.List[int]:

	return [
		round(mido.tempo2bpm(message.tempo))
		for _, message in sequencer.recorded_events
		if message.is_meta and message.type == "set_tempo"
	]


@pytest.mark.asyncio
async def test_the_tempo_is_what_the_cable_sent_however_slowly_it_was_read (
	patch_midi: None,
) -> None:

	"""Ticks stamped a steady 120 BPM apart read 120, whatever the loop was doing.

	This is the whole of the bug in one measurement. Every tick is queued up
	front with a synthetic, perfectly even arrival time, and the loop then
	drains all 96 of them as fast as it can — about 20 ms of wall clock for
	four beats that took two seconds to arrive. Read from the dequeue clock
	that is a tempo of roughly 12,000 BPM; read from the arrival stamps it is
	120.
	"""

	sequencer = _follower()
	sequencer.recording = True

	await sequencer.start()

	origin = time.perf_counter()

	sequencer._midi_input_queue.put_nowait((0, mido.Message("start"), origin))

	for index in range(96):
		sequencer._midi_input_queue.put_nowait(
			(0, mido.Message("clock"), origin + index * TICK)
		)

	await _drain(sequencer)

	assert sequencer.pulse_count >= 90, (
		f"only {sequencer.pulse_count} pulses advanced — the loop did not read the "
		f"ticks, so the tempo below means nothing"
	)

	assert sequencer.current_bpm == 120, (
		f"a steady 120 BPM master read as {sequencer.current_bpm} BPM, so the tempo "
		f"is being taken from when the loop got round to the tick"
	)

	await sequencer.stop()


@pytest.mark.asyncio
async def test_a_steady_master_writes_one_tempo_into_the_recording (patch_midi: None) -> None:

	"""The consequence a musician meets: the .mid's tempo map.

	Eight tempo events from a steady master is a file that wanders when a DAW
	plays it back.
	"""

	sequencer = _follower()
	sequencer.recording = True

	await sequencer.start()

	origin = time.perf_counter()

	sequencer._midi_input_queue.put_nowait((0, mido.Message("start"), origin))

	for index in range(96):
		sequencer._midi_input_queue.put_nowait(
			(0, mido.Message("clock"), origin + index * TICK)
		)

	await _drain(sequencer)

	written = _tempo_events(sequencer)

	assert written, "nothing was recorded at all, so this proves nothing"

	# The opening tempo is the constructor's 60; the one change is to 120.
	assert written == [60, 120], (
		f"a steady 120 BPM master wrote {written} into the recording"
	)


@pytest.mark.asyncio
async def test_a_real_tempo_change_is_still_followed (patch_midi: None) -> None:

	"""The control. Stamping arrival must not stop it hearing a genuine change."""

	sequencer = _follower()
	sequencer.recording = True

	await sequencer.start()

	origin = time.perf_counter()
	sequencer._midi_input_queue.put_nowait((0, mido.Message("start"), origin))

	when = origin

	for _ in range(96):							# four beats at 120
		sequencer._midi_input_queue.put_nowait((0, mido.Message("clock"), when))
		when += TICK

	await _drain(sequencer)

	assert sequencer.current_bpm == 120

	for _ in range(96):							# then four at 90
		sequencer._midi_input_queue.put_nowait((0, mido.Message("clock"), when))
		when += 60.0 / 90 / PPQN

	await _drain(sequencer)

	assert sequencer.current_bpm == 90, (
		f"the master slowed to 90 and the follower reads {sequencer.current_bpm}"
	)

	assert 120 in _tempo_events(sequencer) and 90 in _tempo_events(sequencer), (
		f"the recording missed a real tempo change: {_tempo_events(sequencer)}"
	)

	await sequencer.stop()


# ---------------------------------------------------------------------------
# A silence is not a slow tempo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_gap_in_the_clock_does_not_drag_the_tempo_down (patch_midi: None) -> None:

	"""A master that stops for two seconds and starts again is still at 120.

	Measured before the fix: 23 BPM, held for 23 ticks while the averaging
	window still straddled the silence.
	"""

	sequencer = _follower()

	await sequencer.start()

	origin = time.perf_counter()
	sequencer._midi_input_queue.put_nowait((0, mido.Message("start"), origin))

	when = origin

	for _ in range(48):
		sequencer._midi_input_queue.put_nowait((0, mido.Message("clock"), when))
		when += TICK

	await _drain(sequencer)

	assert sequencer.current_bpm == 120, "the tempo was not established before the gap"

	when += 2.0			# the master stops sending

	readings = []

	for _ in range(30):
		sequencer._midi_input_queue.put_nowait((0, mido.Message("clock"), when))
		when += TICK
		await _drain(sequencer)
		readings.append(sequencer.current_bpm)

	assert all(value == 120 for value in readings), (
		f"the silence was averaged into the tempo: {readings}"
	)

	await sequencer.stop()


@pytest.mark.asyncio
async def test_a_long_silence_never_reads_as_no_tempo_at_all (patch_midi: None) -> None:

	"""A two-minute silence is where the old arithmetic reached zero exactly.

	The review reported "current_bpm reads 0 for 23 ticks". Working out when:
	the window averages over 23 intervals, so a mean above 5 s — which is what
	rounds 60 / (interval x 24) down to zero — needs a total span above 115
	seconds. A two-second gap reads 23 BPM, not 0; two minutes reads 0. Both
	are wrong in the same way, and the gap reset is what fixes both.
	"""

	sequencer = _follower()

	await sequencer.start()

	origin = time.perf_counter()
	sequencer._midi_input_queue.put_nowait((0, mido.Message("start"), origin))

	when = origin

	for _ in range(48):
		sequencer._midi_input_queue.put_nowait((0, mido.Message("clock"), when))
		when += TICK

	await _drain(sequencer)

	when += 120.0		# the master is left stopped for two minutes

	for _ in range(30):
		sequencer._midi_input_queue.put_nowait((0, mido.Message("clock"), when))
		when += TICK
		await _drain(sequencer)

		assert sequencer.current_bpm > 0, (
			f"the tempo read zero after a long silence — a display showing 0 BPM "
			f"beside a piece that is plainly playing"
		)
		assert sequencer.current_bpm == 120, (
			f"a two-minute silence dragged the tempo to {sequencer.current_bpm}"
		)

	assert sequencer.current_bpm == 120, (
		f"after a long silence the master is still at 120, read as {sequencer.current_bpm}"
	)

	await sequencer.stop()


def test_a_gap_resets_the_window_rather_than_averaging_it (patch_midi: None) -> None:

	"""The mechanism, driven directly: the window starts again at a gap."""

	sequencer = _follower()

	base = 1000.0

	for index in range(48):
		sequencer._estimate_bpm(base + index * TICK)

	assert sequencer.current_bpm == 120
	assert len(sequencer._clock_tick_times) > 1

	sequencer._estimate_bpm(base + 48 * TICK + 5.0)

	assert sequencer._clock_tick_times == [base + 48 * TICK + 5.0], (
		f"the window kept ticks from before the gap: {len(sequencer._clock_tick_times)} of them"
	)
	assert sequencer.current_bpm == 120, "the tempo moved on a gap rather than holding"


def test_the_arrival_time_is_stamped_where_it_is_true (patch_midi: None) -> None:

	"""`_on_midi_input` puts the arrival on the queue, on the callback thread.

	Everything above drives the queue directly, because a mido callback needs a
	real port — so without this nothing covers the half of the fix that decides
	*what* the loop is handed. A break that stamped a constant there failed no
	test at all until this was written.
	"""

	sequencer = _follower()
	sequencer._midi_input_queue = asyncio.Queue()
	sequencer._input_loop = _ImmediateLoop()

	before = time.perf_counter()
	sequencer._on_midi_input(mido.Message("clock"), 0)
	after = time.perf_counter()

	assert not sequencer._midi_input_queue.empty(), "the tick never reached the queue"

	device, message, arrived_at = sequencer._midi_input_queue.get_nowait()

	assert device == 0
	assert message.type == "clock"
	assert before <= arrived_at <= after, (
		f"the arrival stamp {arrived_at} is not the moment the message came in "
		f"({before} to {after}) — a constant or a later clock would pass a test "
		f"that only checked the field was there"
	)


class _ImmediateLoop:

	"""Stands in for the event loop so the callback's queue push happens now.

	`_on_midi_input` runs on mido's thread and hands the push to the loop with
	`call_soon_threadsafe`; there is no loop running in a synchronous test, and
	what is under test is the argument it passes, not the hand-off.
	"""

	def call_soon_threadsafe (self, callback: typing.Callable, *args: typing.Any) -> None:
		callback(*args)
