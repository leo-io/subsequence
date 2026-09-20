"""A future-dated OSC bundle waits its turn without stopping the music (#3001).

python-osc honours a bundle's timetag by calling `time.sleep()` inside
`datagram_received` — on the event loop, which is the loop the MIDI clock runs
on.  A bundle half a second ahead stopped the piece for half a second and then
burst the missed notes out together; one an hour ahead stopped it for an hour,
Ctrl+C included.  It happened whatever the address, handled or not, because
`handlers_for_address` returns a generator and a generator is always truthy.

Measured on the unchanged tree with a 2 ms tick: 113 ticks in 250 ms normally,
2 with a +0.5 s bundle in flight, worst gap 500.2 ms.
"""

import asyncio
import socket
import time
import typing

import pytest
import pythonosc.osc_bundle_builder
import pythonosc.osc_message_builder

import subsequence
import subsequence.osc


def _bundle (address: str, value: typing.Any, seconds_ahead: float) -> bytes:

	"""One OSC message in a bundle timed *seconds_ahead* from now."""

	timestamp = (
		pythonosc.osc_bundle_builder.IMMEDIATELY
		if seconds_ahead == 0
		else time.time() + seconds_ahead
	)

	builder = pythonosc.osc_bundle_builder.OscBundleBuilder(timestamp)

	message = pythonosc.osc_message_builder.OscMessageBuilder(address = address)
	message.add_arg(value)
	builder.add_content(message.build())

	return builder.build().dgram


async def _listening (
	composition: subsequence.Composition,
) -> typing.Tuple[subsequence.osc.OscServer, int]:

	"""Start the composition's OSC server on a free port and report it."""

	composition.osc(receive_port = 0, send_port = 0)

	server = composition._osc_server
	assert server is not None

	await server.start()

	port = server._transport.get_extra_info("socket").getsockname()[1]

	return server, port


def _send (port: int, datagram: bytes) -> None:

	"""Put one packet on the wire, on the loopback only."""

	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

	try:
		sock.sendto(datagram, ("127.0.0.1", port))
	finally:
		sock.close()


async def _tick (count: int = 100) -> float:

	"""Run a 2 ms tick, like the sequencer's, *count* times, and report how long it took.

	A COUNT, not a deadline.  A deadline measures nothing here: the loop is
	blocked right through it, so the run ends with no tick recorded after the
	block and a gap nothing ever looked at.  Both stall tests passed against
	the unblocked tree that way.  Ticking a fixed number of times means the
	block has to be paid for in wall-clock time, which is the thing at issue.
	"""

	started = time.perf_counter()

	for _ in range(count):
		await asyncio.sleep(0.002)

	return time.perf_counter() - started


@pytest.fixture
def composition (patch_midi: None) -> subsequence.Composition:

	"""A composition to hang an OSC server off."""

	return subsequence.Composition(output_device = "Dummy MIDI", bpm = 120, key = "C")


# ---------------------------------------------------------------------------
# The clock keeps running
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_future_bundle_does_not_stall_the_loop (composition: subsequence.Composition) -> None:

	"""This is the whole finding: half a second of silence, then a burst."""

	server, port = await _listening(composition)

	try:
		ticking = asyncio.create_task(_tick(100))
		await asyncio.sleep(0.02)

		_send(port, _bundle("/bpm", 130, 0.5))

		elapsed = await ticking

		assert elapsed < 0.45, \
			f"100 ticks of 2 ms took {elapsed * 1000:.0f} ms — the loop was held"

	finally:
		await server.stop()


@pytest.mark.asyncio
async def test_an_unhandled_address_does_not_stall_the_loop_either (composition: subsequence.Composition) -> None:

	"""`if not handlers: continue` never fired — a generator is always truthy."""

	server, port = await _listening(composition)

	try:
		ticking = asyncio.create_task(_tick(100))
		await asyncio.sleep(0.02)

		_send(port, _bundle("/nothing/is/mapped/here", 1, 0.5))

		elapsed = await ticking

		assert elapsed < 0.45, \
			f"100 ticks took {elapsed * 1000:.0f} ms on an address nothing handles"

	finally:
		await server.stop()


@pytest.mark.asyncio
async def test_a_bundle_an_hour_ahead_does_not_stop_the_piece (composition: subsequence.Composition) -> None:

	"""The unbounded case: the clock froze for the whole hour, Ctrl+C included."""

	server, port = await _listening(composition)

	try:
		ticking = asyncio.create_task(_tick(60))
		await asyncio.sleep(0.02)

		_send(port, _bundle("/bpm", 140, 3600.0))

		elapsed = await asyncio.wait_for(ticking, timeout = 10.0)

		assert elapsed < 0.4, f"60 ticks took {elapsed * 1000:.0f} ms"

	finally:
		await server.stop()


# ---------------------------------------------------------------------------
# The message still lands when it said it would
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_an_immediate_bundle_is_acted_on_at_once (composition: subsequence.Composition) -> None:

	"""Not stalling must not become not listening."""

	server, port = await _listening(composition)

	try:
		_send(port, _bundle("/bpm", 133, 0))
		await asyncio.sleep(0.1)

		assert composition.bpm == 133

	finally:
		await server.stop()


@pytest.mark.asyncio
async def test_a_future_bundle_is_acted_on_at_its_time (composition: subsequence.Composition) -> None:

	"""The timetag is honoured, which is why it cannot simply be ignored."""

	server, port = await _listening(composition)

	try:
		before = composition.bpm

		_send(port, _bundle("/bpm", 137, 0.25))

		await asyncio.sleep(0.1)
		assert composition.bpm == before, "it was acted on early"

		await asyncio.sleep(0.35)
		assert composition.bpm == 137, "its time came and nothing happened"

	finally:
		await server.stop()


@pytest.mark.asyncio
async def test_messages_in_one_bundle_keep_their_order (composition: subsequence.Composition) -> None:

	"""Two timetags, two arrivals, in the order the timetags say."""

	server, port = await _listening(composition)
	seen: typing.List[str] = []

	composition.osc_map("/mark/*", lambda address, *args: seen.append(address))

	try:
		_send(port, _bundle("/mark/late", 1, 0.25))
		_send(port, _bundle("/mark/early", 1, 0.08))
		_send(port, _bundle("/mark/now", 1, 0))

		await asyncio.sleep(0.5)

		assert seen == ["/mark/now", "/mark/early", "/mark/late"], seen

	finally:
		await server.stop()


@pytest.mark.asyncio
async def test_a_timetag_past_the_horizon_is_played_now (composition: subsequence.Composition) -> None:

	"""A surface that appears dead for an hour is worse than one that acts early."""

	server, port = await _listening(composition)

	try:
		_send(port, _bundle("/bpm", 141, 3600.0))
		await asyncio.sleep(0.15)

		assert composition.bpm == 141, "an hour-ahead message was simply swallowed"

	finally:
		await server.stop()


@pytest.mark.asyncio
async def test_a_timetag_inside_the_horizon_still_waits (composition: subsequence.Composition) -> None:

	"""The cap must not turn every timetag into 'now'."""

	server, port = await _listening(composition)

	try:
		before = composition.bpm

		_send(port, _bundle("/bpm", 143, subsequence.osc.MAX_TIMETAG_AHEAD_SECONDS - 5.0))
		await asyncio.sleep(0.15)

		assert composition.bpm == before, "a message inside the horizon was played at once"

	finally:
		await server.stop()


@pytest.mark.asyncio
async def test_the_horizon_is_said_once_not_per_message (composition: subsequence.Composition) -> None:

	"""A surface with a skewed clock would otherwise fill the log."""

	server, port = await _listening(composition)

	try:
		import unittest.mock

		with unittest.mock.patch.object(subsequence.osc.logger, "warning") as warned:
			for _ in range(5):
				_send(port, _bundle("/bpm", 120, 3600.0))
			await asyncio.sleep(0.2)

		horizon = [call for call in warned.call_args_list if "ahead" in str(call)]

		assert len(horizon) == 1, f"said {len(horizon)} times"

	finally:
		await server.stop()


# ---------------------------------------------------------------------------
# Stopping means stopping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stopping_drops_what_was_still_waiting (composition: subsequence.Composition) -> None:

	"""A stopped composition must not be played into half a second later."""

	server, port = await _listening(composition)

	before = composition.bpm

	_send(port, _bundle("/bpm", 151, 0.3))
	await asyncio.sleep(0.05)

	await server.stop()
	await asyncio.sleep(0.4)

	assert composition.bpm == before, \
		"a message fired into a composition whose OSC server had stopped"


@pytest.mark.asyncio
async def test_a_handler_that_raises_does_not_take_the_server_down (composition: subsequence.Composition) -> None:

	"""It is on the loop now, so an escaping exception would reach the clock."""

	server, port = await _listening(composition)

	def explode (address: str, *args: typing.Any) -> None:
		raise RuntimeError("no")

	composition.osc_map("/boom", explode)

	try:
		_send(port, _bundle("/boom", 1, 0))
		await asyncio.sleep(0.1)

		_send(port, _bundle("/bpm", 147, 0))
		await asyncio.sleep(0.1)

		assert composition.bpm == 147, "the server stopped listening after a bad handler"

	finally:
		await server.stop()


@pytest.mark.asyncio
async def test_one_bad_handler_does_not_silence_the_others (composition: subsequence.Composition) -> None:

	"""Two things can be mapped to one address, and the second is not the first's to lose.

	Letting the exception escape ends the loop over the address's handlers, so
	everything registered after the one that failed simply stops happening —
	silently, because asyncio logs the traceback and carries on.
	"""

	server, port = await _listening(composition)
	reached: typing.List[str] = []

	def explode (address: str, *args: typing.Any) -> None:
		raise RuntimeError("no")

	def survive (address: str, *args: typing.Any) -> None:
		reached.append(address)

	composition.osc_map("/both", explode)
	composition.osc_map("/both", survive)

	try:
		_send(port, _bundle("/both", 1, 0))
		await asyncio.sleep(0.1)

		assert reached == ["/both"], "the handler after the failing one never ran"

	finally:
		await server.stop()


@pytest.mark.asyncio
async def test_a_malformed_packet_is_ignored (composition: subsequence.Composition) -> None:

	"""Anything can arrive on a UDP port, and none of it should show up as a crash.

	An unguarded parse raises out of `datagram_received`; asyncio catches that
	and the server survives, so the only way to tell is that the loop's
	exception handler was called at all.
	"""

	server, port = await _listening(composition)
	crashes: typing.List[typing.Any] = []

	loop = asyncio.get_running_loop()
	previous = loop.get_exception_handler()
	loop.set_exception_handler(lambda _loop, context: crashes.append(context))

	try:
		_send(port, b"this is not OSC at all")
		_send(port, b"\x00\x01\x02")
		await asyncio.sleep(0.1)

		assert crashes == [], f"a malformed packet was reported as a crash: {crashes}"

		_send(port, _bundle("/bpm", 149, 0))
		await asyncio.sleep(0.1)

		assert composition.bpm == 149

	finally:
		loop.set_exception_handler(previous)
		await server.stop()
