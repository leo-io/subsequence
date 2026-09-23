"""Stopping a performance that has a live server, on a real socket.

A REPL is usually left connected in a terminal of its own for the whole set, so stopping
must not wait for it.  From Python 3.12.1 the server's `wait_closed()` waits for every open
connection, and nothing closed them: Ctrl+C silenced the music and `play()` then waited for
the performer to quit the REPL (#3365).

And typed code runs on the event loop, where the performance hears Ctrl+C and SIGTERM, so
code that never returned left the process deaf to both (#3367).
"""

import asyncio
import contextlib
import os
import signal
import sys
import threading
import time
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

		# Before 3.12.1 wait_closed() does not wait for connections, so stop()
		# is already done and only the client's closing below is left to
		# check - which the handler's is_serving() check still decides (#3451).
		if sys.version_info >= (3, 12, 1):
			assert not stop.done(), "stop() finished before the held connection was released, so this tests nothing"

		stopping.set()

		assert await _finishes(stop), "stop() was still waiting for a client that connected as it began"
		assert await _closed_by_the_server(reader)

	finally:
		stopping.set()
		await _release(server, [writer])


# Code that holds the loop for six seconds, in the two ways that happen: a busy loop, and a call
# that blocks.  Bounded, so a tree without the fix fails with an answer instead of hanging.
_HOLDERS = {
	"busy": b"import time\nuntil = time.monotonic() + 6\nwhile time.monotonic() < until: pass",
	"sleep": b"import time\ntime.sleep(6)",
}


@pytest.mark.skipif(sys.platform == "win32", reason="sends a signal to its own process")
@pytest.mark.asyncio
@pytest.mark.parametrize("holder", sorted(_HOLDERS))
@pytest.mark.parametrize("number", [signal.SIGINT, signal.SIGTERM], ids=["SIGINT", "SIGTERM"])
async def test_a_stopping_signal_stops_typed_code_that_holds_the_loop (composition: subsequence.Composition, number: signal.Signals, holder: str) -> None:

	"""The signal stops the code, and then still reaches the performance's own handler, once.

	The handler is installed with `loop.add_signal_handler`, as `run_until_stopped` does, so its
	callback runs on the loop the code was holding.  Before, the code ran its full six seconds
	and the signal waited for it.
	"""

	loop = asyncio.get_running_loop()
	heard: typing.List[float] = []
	loop.add_signal_handler(number, lambda: heard.append(time.monotonic()))
	server, port = await _started(composition)
	reader, writer = await asyncio.open_connection("127.0.0.1", port)
	timer = threading.Timer(0.3, os.kill, (os.getpid(), number))

	try:
		writer.write(_HOLDERS[holder] + SENTINEL)
		await writer.drain()
		sent = time.monotonic()
		timer.start()

		answer = await asyncio.wait_for(reader.readuntil(SENTINEL), timeout=10.0)
		took = time.monotonic() - sent

		# The signal's own wake-up is handled on the loop's next turn.
		await asyncio.sleep(0.1)

		assert answer == f"Interrupted by {number.name}.".encode() + SENTINEL
		assert took < 3.0
		assert len(heard) == 1

	finally:
		timer.cancel()
		loop.remove_signal_handler(number)
		await _release(server, [writer])


def test_the_handlers_are_put_back_once_the_code_has_run (composition: subsequence.Composition) -> None:

	"""A handler left swapped would raise into whatever Python ran next, long after the submission."""

	server = subsequence.live_server.LiveServer(composition, port=0)
	before = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}

	assert server._evaluate("1 + 1") == ("2", True)
	assert server._evaluate("raise ValueError('x')")[1] is False

	assert {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)} == before


def test_code_run_off_the_main_thread_is_left_alone (composition: subsequence.Composition) -> None:

	"""Only the main thread may set a signal handler, and only it is ever sent one, so elsewhere nothing changes."""

	server = subsequence.live_server.LiveServer(composition, port=0)
	answers: typing.List[typing.Any] = []

	def _run () -> None:
		try:
			answers.append(server._evaluate("1 + 1"))
		except BaseException as error:
			answers.append(error)

	worker = threading.Thread(target=_run)
	worker.start()
	worker.join(timeout=5.0)

	assert answers == [("2", True)]


def _interrupted_on_the_main_thread (composition: subsequence.Composition, handler: typing.Any) -> typing.Tuple[typing.Any, float]:

	"""Run held-up code with `handler` on SIGINT, send SIGINT 0.3 s in, and say what `_evaluate` did and how long it took."""

	server = subsequence.live_server.LiveServer(composition, port=0)
	previous = signal.signal(signal.SIGINT, handler)
	timer = threading.Timer(0.3, os.kill, (os.getpid(), signal.SIGINT))
	started = time.monotonic()

	try:
		timer.start()

		try:
			outcome: typing.Any = server._evaluate(_HOLDERS["busy"].decode())
		except KeyboardInterrupt:
			outcome = "KeyboardInterrupt"

		return outcome, time.monotonic() - started

	finally:
		timer.cancel()
		signal.signal(signal.SIGINT, previous)


@pytest.mark.skipif(sys.platform == "win32", reason="sends a signal to its own process")
def test_a_plain_handler_hears_the_signal_that_stopped_the_code_once (composition: subsequence.Composition) -> None:

	"""Where a performance could not use the loop's handlers, it hears Ctrl+C through a plain one, as on Windows."""

	heard: typing.List[int] = []
	outcome, took = _interrupted_on_the_main_thread(composition, lambda number, frame: heard.append(number))

	assert outcome == ("Interrupted by SIGINT.", False)
	assert took < 3.0
	assert heard == [signal.SIGINT]


@pytest.mark.skipif(sys.platform == "win32", reason="sends a signal to its own process")
def test_with_python_s_own_handler_ctrl_c_still_raises_once_the_code_has_stopped (composition: subsequence.Composition) -> None:

	"""With nothing else installed, Ctrl+C is a KeyboardInterrupt, and it still arrives, just after the code stops."""

	outcome, took = _interrupted_on_the_main_thread(composition, signal.default_int_handler)

	assert outcome == "KeyboardInterrupt"
	assert took < 3.0
