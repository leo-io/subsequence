"""Latency compensation covers the transport, and never reorders (#3069, M9).

Two faults, both about `_send_offset_seconds` being consulted in the wrong
place or at the wrong moment.

**The transport bypassed compensation.** `_send_clock_message` wrote straight
to every port while the notes for the same device went through
`_dispatch_with_compensation`, so compensation pulled the transport and the
music *apart* instead of together. Measured with device 0 at 0 ms and device 1
at 20 ms, which gives device 0 a 20 ms offset: a Start reached the faster synth
in **0.01 ms** where its notes wait 20 ms, so a slaved drum machine ran a whole
offset ahead of the part it was locking to.

**A mid-play latency change stranded a note.** The offset is read at dispatch,
and `set_device_latency` is a live control, so a note_on deferred by 50 ms could
have its note_off dispatched under an offset of 0 and sent first. Measured:
the synth received `['note_off', 'note_on']`, and `active_notes` had already
forgotten the note — so neither the release sweep nor `stop()` would catch it.

The fix is a per-device floor: nothing is sent before the moment the last send
for that device is due. That covers the whole class, not just note pairs.
"""

import asyncio
import typing

import mido
import pytest

import subsequence
import subsequence.sequencer


def _two_devices (
	ports: typing.Dict[str, typing.Any],
	second_latency_ms: float,
) -> subsequence.sequencer.Sequencer:

	"""Device 0 with no latency, device 1 with *second_latency_ms*.

	That makes device 0 the FASTER one, so compensation holds it back by the
	difference to let the slower one catch up — which is what gives device 0 a
	non-zero send offset to observe.
	"""

	sequencer = subsequence.sequencer.Sequencer(
		output_device_name = "Primary MIDI",
		initial_bpm = 600,
		clock_output = True,
	)

	sequencer._init_midi_output()
	sequencer.add_output_device("Secondary MIDI", ports["Secondary MIDI"], latency_ms = second_latency_ms)
	sequencer.set_device_latency(0, 0.0)

	return sequencer


def _note (message_type: str, note: int, device: int, pulse: int = 0) -> subsequence.sequencer.MidiEvent:

	return subsequence.sequencer.MidiEvent(
		pulse = pulse,
		message_type = message_type,
		channel = 0,
		note = note,
		velocity = 100 if message_type == "note_on" else 0,
		device = device,
	)


# ---------------------------------------------------------------------------
# The transport waits with the music
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_transport_message_waits_for_its_device_like_a_note (
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""A Start used to reach the faster synth in 0.01 ms where its notes wait 20 ms."""

	sequencer = _two_devices(patch_midi_multi, second_latency_ms = 20.0)
	sequencer._event_loop = asyncio.get_running_loop()

	fast = patch_midi_multi["Primary MIDI"]

	assert sequencer._send_offset_seconds(0) > 0, (
		"device 0 has no compensation offset, so there is nothing for this to observe"
	)

	before = len(fast.sent)

	sequencer._send_clock_message("start")

	assert not fast.sent[before:], (
		f"the start reached the faster synth at once, ahead of its own notes: "
		f"{[m.type for m in fast.sent[before:]]}"
	)

	await asyncio.sleep(0.05)

	assert [m.type for m in fast.sent[before:]] == ["start"], (
		f"the start never arrived: {[m.type for m in fast.sent[before:]]}"
	)

	await sequencer.stop()


@pytest.mark.asyncio
async def test_the_slowest_device_still_gets_the_transport_at_once (
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""The control: compensation delays the fast, it does not delay everything.

	Device 1 is the slowest, so its offset is zero and nothing should be held
	back for it. Without this, "it waited" would pass with every send deferred.
	"""

	sequencer = _two_devices(patch_midi_multi, second_latency_ms = 20.0)
	sequencer._event_loop = asyncio.get_running_loop()

	slow = patch_midi_multi["Secondary MIDI"]

	assert sequencer._send_offset_seconds(1) == 0.0

	before = len(slow.sent)

	sequencer._send_clock_message("start")

	assert [m.type for m in slow.sent[before:]] == ["start"], (
		"the slowest device was made to wait, which delays the whole rig"
	)

	await sequencer.stop()


@pytest.mark.asyncio
async def test_the_stop_at_shutdown_is_sent_at_once (
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""It must not be deferred: the ports close immediately afterwards.

	A deferred Stop would fire on a closed port, and a Stop that never arrives
	leaves a slaved device running after the piece has ended. Early by one
	offset at the very end costs nothing by comparison.
	"""

	sequencer = _two_devices(patch_midi_multi, second_latency_ms = 20.0)
	sequencer._event_loop = asyncio.get_running_loop()

	fast = patch_midi_multi["Primary MIDI"]
	before = len(fast.sent)

	await sequencer.stop()

	assert "stop" in [m.type for m in fast.sent[before:]], (
		f"the faster synth never got a Stop: {[m.type for m in fast.sent[before:]]}"
	)


# ---------------------------------------------------------------------------
# Nothing overtakes what is already waiting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_latency_change_cannot_strand_a_sounding_note (
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""The finding: the synth received ['note_off', 'note_on'] and the note hung."""

	sequencer = _two_devices(patch_midi_multi, second_latency_ms = 50.0)
	sequencer._event_loop = asyncio.get_running_loop()

	fast = patch_midi_multi["Primary MIDI"]
	before = len(fast.sent)

	assert sequencer._send_offset_seconds(0) == pytest.approx(0.05), (
		"device 0 is not being held back, so the race below cannot happen at all"
	)

	sequencer._dispatch_with_compensation(_note("note_on", 60, device = 0))

	# The performer drops the other device's latency, which makes device 0 the
	# slowest and takes its own offset to zero.
	sequencer.set_device_latency(1, 0.0)

	assert sequencer._send_offset_seconds(0) == 0.0, "the offset did not change, so nothing is under test"

	sequencer._dispatch_with_compensation(_note("note_off", 60, device = 0, pulse = 12))

	await asyncio.sleep(0.12)

	order = [m.type for m in fast.sent[before:]]

	assert order == ["note_on", "note_off"], (
		f"the synth received {order} — a note_off ahead of its own note_on leaves "
		f"the note ringing for good"
	)

	await sequencer.stop()


@pytest.mark.asyncio
async def test_a_burst_keeps_its_order_across_a_latency_change (
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""An NRPN burst is CC 99, 98, 6, 38 and means nothing in another order.

	The per-device offset is what keeps a burst in order normally — the
	docstring on `_send_offset_seconds` says so. A latency change mid-burst
	broke exactly that, which is why the fix is a floor rather than a rule
	about note pairs.
	"""

	sequencer = _two_devices(patch_midi_multi, second_latency_ms = 80.0)
	sequencer._event_loop = asyncio.get_running_loop()

	fast = patch_midi_multi["Primary MIDI"]
	before = len(fast.sent)

	for index, control in enumerate((99, 98, 6, 38)):
		sequencer._dispatch_with_compensation(subsequence.sequencer.MidiEvent(
			pulse = 0, message_type = "control_change", channel = 0,
			control = control, value = index, device = 0,
		))
		# The knob moves under the burst.
		sequencer.set_device_latency(1, 80.0 - index * 20.0)

	await asyncio.sleep(0.2)

	sent = [m.control for m in fast.sent[before:] if m.type == "control_change"]

	assert sent == [99, 98, 6, 38], f"the burst arrived as {sent}"

	await sequencer.stop()


@pytest.mark.asyncio
async def test_compensation_still_lets_an_uncontended_send_go_straight_out (
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""The control on the floor: it must not defer what has nothing to wait for.

	With no latency configured anywhere — which is most rigs — every offset is
	zero and nothing should be scheduled at all.
	"""

	sequencer = _two_devices(patch_midi_multi, second_latency_ms = 0.0)
	sequencer._event_loop = asyncio.get_running_loop()

	fast = patch_midi_multi["Primary MIDI"]
	before = len(fast.sent)

	sequencer._dispatch_with_compensation(_note("note_on", 60, device = 0))

	assert [m.type for m in fast.sent[before:]] == ["note_on"], (
		"a send with no offset was deferred anyway"
	)
	assert not sequencer._pending_sends, "a timer was scheduled where none was needed"

	await sequencer.stop()


@pytest.mark.asyncio
async def test_a_deferred_send_lands_when_it_was_scheduled_to (
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""The floor holds the order without pushing sends noticeably late.

	The nudge past the floor is a microsecond, so four clamped messages arrive
	within the offset they were compensated by rather than measurably after it.
	"""

	sequencer = _two_devices(patch_midi_multi, second_latency_ms = 30.0)
	sequencer._event_loop = asyncio.get_running_loop()

	fast = patch_midi_multi["Primary MIDI"]
	before = len(fast.sent)

	loop = asyncio.get_running_loop()
	began = loop.time()

	for index in range(4):
		sequencer._dispatch_with_compensation(_note("note_on", 60 + index, device = 0))

	# Poll rather than sleeping a fixed span and timing that, which measures
	# the sleep.
	for _ in range(400):
		if len([m for m in fast.sent[before:] if m.type == "note_on"]) == 4:
			break
		await asyncio.sleep(0.001)

	took = loop.time() - began
	arrived = [m.note for m in fast.sent[before:] if m.type == "note_on"]

	assert arrived == [60, 61, 62, 63], f"the notes arrived as {arrived}"

	# The offset is 30 ms; four microsecond nudges are invisible against it.
	assert took < 0.045, (
		f"four sends compensated by 30 ms took {took * 1000:.1f} ms — the ordering "
		f"nudge is delaying them instead of merely ordering them"
	)

	await sequencer.stop()


@pytest.mark.asyncio
async def test_the_recorded_floor_is_when_the_send_will_actually_happen (
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""The floor must equal the scheduled time exactly, not approximately.

	This is why the deferral uses ``call_at`` with an absolute time rather than
	``call_later`` with a delay: ``call_later`` reads the clock again itself, so
	the send lands a few hundred nanoseconds past the floor recorded for it.
	The next message is then held to a floor that has already passed, and
	whether it still arrives second depends on which of the two clock reads was
	slower. It is a race, and it lost — the measured order was
	``['note_off', 'note_on']`` with the floor in place but scheduled by delay.

	The microsecond nudge hides this most of the time, which is exactly why it
	is worth asserting rather than trusting: the drift only has to exceed a
	microsecond once, under load, to strand a note.
	"""

	sequencer = _two_devices(patch_midi_multi, second_latency_ms = 50.0)
	sequencer._event_loop = asyncio.get_running_loop()

	sequencer._dispatch_with_compensation(_note("note_on", 60, device = 0))

	assert len(sequencer._pending_sends) == 1, "nothing was deferred, so there is no floor to check"

	handle = next(iter(sequencer._pending_sends))

	assert sequencer._send_floor[0] == handle.when(), (
		f"the floor says {sequencer._send_floor[0]!r} and the send is scheduled for "
		f"{handle.when()!r} — a difference of {(handle.when() - sequencer._send_floor[0]) * 1e9:.0f} ns, "
		f"so anything clamped behind it is racing that gap"
	)

	await sequencer.stop()
