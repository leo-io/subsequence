"""Stopping a performance that has a live server, on a real socket.

A REPL is usually left connected in a terminal of its own for the whole set, so stopping
must not wait for it.  From Python 3.12.1 the server's `wait_closed()` waits for every open
connection, and nothing closed them: Ctrl+C silenced the music and `play()` then waited for
the performer to quit the REPL (#3365).
"""

import asyncio
import contextlib
import typing

import pytest

import subsequence
import subsequence.live_server


SENTINEL = subsequence.live_server.SENTINEL


@pytest.fixture
def composition (patch_midi: None) -> subsequence.Composition:

	"""A composition for the server to evaluate against."""

	return subsequence.Composition(output_device="Dummy MIDI", bpm=120, key="C")


async def _started (composition: subsequence.Composition) -> typing.Tuple[subsequence.live_server.LiveServer, int]:

	"""A live server on a free port on 127.0.0.1, and that port."""

	server = subsequence.live_server.LiveServer(composition, port=0)
	await server.start()
	assert server._server is not None

	return server, server._server.sockets[0].getsockname()[1]


async def _finishes (awaitable: typing.Awaitable[typing.Any], seconds: float = 2.0) -> bool:

	"""Whether something finishes in time: a hang has to fail as an assertion, not as a timeout error."""

	try:
		await asyncio.wait_for(awaitable, timeout=seconds)
	except asyncio.TimeoutError:
		return False

	return True


async def _closed_by_the_server (reader: asyncio.StreamReader) -> bool:

	"""Whether the server has hung up on this client: its next read is the end of the stream."""

	try:
		return await asyncio.wait_for(reader.read(), timeout=2.0) == b""
	except asyncio.TimeoutError:
		return False


async def _release (server: subsequence.live_server.LiveServer, writers: typing.List[asyncio.StreamWriter]) -> None:

	"""Close whatever a failing test left open, so it cannot hold the next one."""

	for writer in writers:
		writer.close()

	if server._server is not None:
		with contextlib.suppress(Exception):
			await asyncio.wait_for(server.stop(), timeout=2.0)


@pytest.mark.asyncio
async def test_stopping_closes_every_client_still_connected (composition: subsequence.Composition) -> None:

	"""One client has typed something and one never has, the usual REPL; stopping closes both at once."""

	server, port = await _started(composition)
	talker_reader, talker = await asyncio.open_connection("127.0.0.1", port)
	silent_reader, silent = await asyncio.open_connection("127.0.0.1", port)

	try:
		talker.write(b"1 + 1" + SENTINEL)
		await talker.drain()
		assert await asyncio.wait_for(talker_reader.readuntil(SENTINEL), timeout=2.0) == b"2" + SENTINEL

		# Let the silent client's handler start and settle into waiting for a
		# message, which is where a REPL left open sits.
		await asyncio.sleep(0.1)

		assert await _finishes(server.stop()), "stop() was still waiting for a connected client"
		assert await _closed_by_the_server(talker_reader)
		assert await _closed_by_the_server(silent_reader)

	finally:
		await _release(server, [talker, silent])


@pytest.mark.asyncio
async def test_a_client_that_connects_as_the_server_stops_is_closed_too (composition: subsequence.Composition) -> None:

	"""A connection accepted in the same moment as stop() is handled after it began, and must leave rather than wait to be read.

	Its handler starts after stop() has closed every client it knew of, so nothing else would
	close it, and from Python 3.12.1 stop() would then wait on it forever.  The test holds the
	handler back until stop() is under way, which is the order a Ctrl+C at the moment a REPL
	connects produces.
	"""

	server = subsequence.live_server.LiveServer(composition, port=0)
	handle = server._handle_connection
	stopping = asyncio.Event()

	async def _held (reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
		await stopping.wait()
		await handle(reader, writer)

	server._handle_connection = _held  # type: ignore[method-assign]
	await server.start()
	assert server._server is not None
	port = server._server.sockets[0].getsockname()[1]
	reader, writer = await asyncio.open_connection("127.0.0.1", port)

	try:
		stop = asyncio.ensure_future(server.stop())
		await asyncio.sleep(0.05)
		assert not stop.done(), "stop() finished before the held connection was released, so this tests nothing"
		stopping.set()

		assert await _finishes(stop), "stop() was still waiting for a client that connected as it began"
		assert await _closed_by_the_server(reader)

	finally:
		stopping.set()
		await _release(server, [writer])
