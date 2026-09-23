"""How the live server reads what a client sends, on a real socket.

The bundled REPL sends one message and waits for its answer, but the module invites editor
plugins and raw sockets, which send messages back to back and split them wherever a write
happens to end.  Each message has to arrive whole and be answered in turn (#3364), and has
to run exactly once (#3366).
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


@contextlib.asynccontextmanager
async def _connected (composition: subsequence.Composition) -> typing.AsyncIterator[typing.Tuple[asyncio.StreamReader, asyncio.StreamWriter]]:

	"""A live server on a free port on 127.0.0.1, and one client connected to it."""

	server = subsequence.live_server.LiveServer(composition, port=0)
	await server.start()
	assert server._server is not None
	port = server._server.sockets[0].getsockname()[1]
	reader, writer = await asyncio.open_connection("127.0.0.1", port)

	try:
		yield reader, writer
	finally:
		writer.close()
		with contextlib.suppress(Exception):
			await writer.wait_closed()
		await server.stop()


async def _sent (writer: asyncio.StreamWriter, data: bytes) -> bool:

	"""Write to the server, and whether it was still taking what was written: False if it hung up mid-send."""

	try:
		writer.write(data)
		await writer.drain()
	except (ConnectionResetError, BrokenPipeError):
		return False

	return True


async def _answers (reader: asyncio.StreamReader, count: int) -> typing.List[str]:

	"""Up to `count` answers, with TIMEOUT or CLOSED in place of the first one that never came."""

	found: typing.List[str] = []

	for _ in range(count):

		try:
			raw = await asyncio.wait_for(reader.readuntil(SENTINEL), timeout=2.0)
		except asyncio.TimeoutError:
			found.append("TIMEOUT")
			break
		except (asyncio.IncompleteReadError, ConnectionResetError):
			found.append("CLOSED")
			break

		found.append(raw[:-len(SENTINEL)].decode())

	return found


@pytest.mark.asyncio
async def test_messages_sent_back_to_back_are_each_answered (composition: subsequence.Composition) -> None:

	"""Two messages in one write: the second used to be thrown away, and its client waited forever."""

	async with _connected(composition) as (reader, writer):

		writer.write(b"1 + 1" + SENTINEL + b"2 + 2" + SENTINEL)
		await writer.drain()

		assert await _answers(reader, 2) == ["2", "4"]


@pytest.mark.asyncio
async def test_a_message_split_across_two_writes_arrives_whole (composition: subsequence.Composition) -> None:

	"""The start of a message that shared a read with the sentinel before it used to be dropped: `20 + 2` ran as `2`."""

	async with _connected(composition) as (reader, writer):

		writer.write(b"10 + 1" + SENTINEL + b"20")
		await writer.drain()
		await asyncio.sleep(0.05)
		writer.write(b" + 2" + SENTINEL)
		await writer.drain()

		assert await _answers(reader, 2) == ["11", "22"]


@pytest.mark.asyncio
async def test_an_empty_message_is_answered_and_the_client_stays_connected (composition: subsequence.Composition) -> None:

	"""An empty message used to read as the client leaving, and closed the connection."""

	async with _connected(composition) as (reader, writer):

		writer.write(SENTINEL)
		await writer.drain()

		assert await _answers(reader, 1) == ["OK"]

		writer.write(b"3 + 3" + SENTINEL)
		await writer.drain()

		assert await _answers(reader, 1) == ["6"]


@pytest.mark.asyncio
async def test_a_message_past_asyncios_default_limit_still_arrives (composition: subsequence.Composition) -> None:

	"""A pasted file can pass the 64 KiB a stream buffers by default, so the server raises its limit."""

	async with _connected(composition) as (reader, writer):

		assert await _sent(writer, b"len('" + b"a" * 200_000 + b"')" + SENTINEL)
		assert await _answers(reader, 1) == ["200000"]


@pytest.mark.asyncio
async def test_an_expression_that_raises_syntax_error_as_it_runs_runs_once (composition: subsequence.Composition) -> None:

	"""A SyntaxError raised by running code used to read as "not an expression", and send it round again as a statement."""

	async with _connected(composition) as (reader, writer):

		writer.write(b"hits = []" + SENTINEL)
		writer.write(b"hits.append(1) or compile('1 +', 'typed', 'eval')" + SENTINEL)
		writer.write(b"len(hits)" + SENTINEL)
		await writer.drain()

		made, raised, counted = await _answers(reader, 3)

		assert made == "OK"
		assert raised.strip().splitlines()[-1].startswith("SyntaxError")
		assert counted == "1"
