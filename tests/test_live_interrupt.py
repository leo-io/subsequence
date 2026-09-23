"""Ctrl+C in the live REPL stops only the code it is waiting on, and the music carries on (#3371).

Typed code runs on the event loop, so while it runs the loop cannot hear anything - including
a request to stop it.  The client sends ETX, the byte Ctrl+C types, and a thread watching the
connection sends SIGUSR1 to the main thread, which breaks into the code even mid-`sleep`.
Nothing the performance stops on is involved, so it carries on.
"""

import asyncio
import os
import signal
import socket
import sys
import threading
import time
import typing

import pytest

import subsequence
import subsequence.live_client
import subsequence.live_server


pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="interrupting typed code needs SIGUSR1, which is Unix only")

SENTINEL = subsequence.live_server.SENTINEL
ETX = b"\x03"

# Code that holds the loop for six seconds, in the two ways that happen.  Bounded, so a tree
# without the feature answers late instead of hanging.
_HOLDERS = {
	"busy": "import time\nuntil = time.monotonic() + 6\nwhile time.monotonic() < until: pass",
	"sleep": "import time\ntime.sleep(6)",
}


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


def _client_answer (client: subsequence.live_client.LiveClient) -> str:

	"""The client's next answer, or TIMEOUT if it never comes, so that fails as an assertion."""

	assert client._sock is not None
	client._sock.settimeout(3.0)

	try:
		return client.answer()
	except socket.timeout:
		return "TIMEOUT"


async def _answer (reader: asyncio.StreamReader) -> str:

	"""The next answer, or TIMEOUT or CLOSED if it never comes, so that fails as an assertion."""

	try:
		raw = await asyncio.wait_for(reader.readuntil(SENTINEL), timeout=10.0)
	except asyncio.TimeoutError:
		return "TIMEOUT"
	except (asyncio.IncompleteReadError, ConnectionResetError):
		return "CLOSED"

	return raw[:-len(SENTINEL)].decode()


@pytest.mark.asyncio
@pytest.mark.parametrize("holder", sorted(_HOLDERS))
async def test_an_interrupt_stops_typed_code_and_the_performance_carries_on (composition: subsequence.Composition, holder: str) -> None:

	"""The code stops within moments, the connection carries on, and nothing that ends a performance fires.

	The performance's own handlers are installed as `run_until_stopped` installs them, so a
	stop request would be heard.
	"""

	loop = asyncio.get_running_loop()
	stopped: typing.List[int] = []

	for number in (signal.SIGINT, signal.SIGTERM):
		loop.add_signal_handler(number, stopped.append, number)

	server, port = await _started(composition)
	reader, writer = await asyncio.open_connection("127.0.0.1", port)

	try:
		writer.write(_HOLDERS[holder].encode() + SENTINEL)
		await writer.drain()

		# The loop is about to be held, so the interrupt has to come from elsewhere,
		# as it does from the REPL: another thread writes it down the same connection.
		sock = writer.get_extra_info("socket")
		timer = threading.Timer(0.3, lambda: os.write(sock.fileno(), ETX))
		sent = time.monotonic()
		timer.start()

		answered = await _answer(reader)
		took = time.monotonic() - sent

		writer.write(b"1 + 1" + SENTINEL)
		await writer.drain()

		assert answered == "KeyboardInterrupt"
		assert took < 3.0
		assert await _answer(reader) == "2"

		await asyncio.sleep(0.1)
		assert stopped == []

	finally:
		for number in (signal.SIGINT, signal.SIGTERM):
			loop.remove_signal_handler(number)
		writer.close()
		await server.stop()


@pytest.mark.asyncio
async def test_an_interrupt_with_nothing_running_is_not_read_as_code (composition: subsequence.Composition) -> None:

	"""A Ctrl+C that lands after its code finished must not turn the next message into a SyntaxError."""

	server, port = await _started(composition)
	reader, writer = await asyncio.open_connection("127.0.0.1", port)

	try:
		writer.write(ETX)
		writer.write(b"2 + 2" + SENTINEL)
		writer.write(b"3 " + ETX + b"+ 3" + SENTINEL)
		await writer.drain()

		assert [await _answer(reader), await _answer(reader)] == ["4", "6"]

	finally:
		writer.close()
		await server.stop()


@pytest.mark.asyncio
async def test_the_server_holds_the_interrupt_signal_so_a_late_one_does_nothing (composition: subsequence.Composition) -> None:

	"""SIGUSR1's default action ends the process, and a request can land just after its code finished.

	The hold is checked before the signal is sent, so a server that does not hold it fails here
	rather than taking the test run down with it.
	"""

	# A handler of the test's own, so what stop() must put back is known whatever ran before.
	original = signal.getsignal(signal.SIGUSR1)
	ours = lambda number, frame: None
	signal.signal(signal.SIGUSR1, ours)

	try:
		server, port = await _started(composition)

		try:
			held = signal.getsignal(signal.SIGUSR1)
			assert callable(held) and held not in (signal.SIG_DFL, signal.SIG_IGN, ours)

			os.kill(os.getpid(), signal.SIGUSR1)
			await asyncio.sleep(0.1)

			reader, writer = await asyncio.open_connection("127.0.0.1", port)
			writer.write(b"1 + 1" + SENTINEL)
			await writer.drain()
			assert await _answer(reader) == "2"
			writer.close()

		finally:
			await server.stop()

		assert signal.getsignal(signal.SIGUSR1) is ours

	finally:
		signal.signal(signal.SIGUSR1, original)


@pytest.mark.asyncio
async def test_the_bundled_client_interrupts_and_hears_the_answer (composition: subsequence.Composition) -> None:

	"""`LiveClient.interrupt()` from another thread, while `send()` waits: what Ctrl+C in the REPL does."""

	server, port = await _started(composition)
	client = subsequence.live_client.LiveClient()
	client.connect("127.0.0.1", port)
	answers: typing.List[str] = []

	try:
		waiting = threading.Thread(target=lambda: answers.append(client.send(_HOLDERS["busy"])))
		waiting.start()
		timer = threading.Timer(0.3, client.interrupt)
		timer.start()

		finished = await asyncio.to_thread(waiting.join, 10.0)
		assert finished is None and not waiting.is_alive()
		assert answers == ["KeyboardInterrupt"]

		assert await asyncio.to_thread(client.send, "1 + 1") == "2"

	finally:
		client.close()
		await server.stop()


@pytest.mark.asyncio
async def test_the_client_keeps_an_answer_that_arrives_with_another (composition: subsequence.Composition) -> None:

	"""Two answers in one read: the second used to be thrown away, so the next wait never ended."""

	server, port = await _started(composition)
	client = subsequence.live_client.LiveClient()
	client.connect("127.0.0.1", port)

	try:
		assert client._sock is not None
		client._sock.sendall(b"1 + 1" + SENTINEL + b"2 + 2" + SENTINEL)
		await asyncio.sleep(0.2)

		assert await asyncio.to_thread(_client_answer, client) == "2"
		assert await asyncio.to_thread(_client_answer, client) == "4"

	finally:
		client.close()
		await server.stop()


class _FakeClient:

	"""Stands in for LiveClient in the REPL loop, raising Ctrl+C where told to."""

	def __init__ (self, second_ctrl_c: bool) -> None:

		"""Say whether a second Ctrl+C lands while it waits."""

		self.second_ctrl_c = second_ctrl_c
		self.interrupted = 0
		self.closed = False

	def connect (self, host: str, port: int) -> None:

		"""Pretend to connect."""

	def send (self, code: str) -> str:

		"""Answer the status header, and meet anything else with Ctrl+C."""

		if code == "composition.live_info()":
			return "status"
		raise KeyboardInterrupt

	def interrupt (self) -> None:

		"""Count the requests to stop the code."""

		self.interrupted += 1

	def answer (self) -> str:

		"""The interrupted code's answer, or a second Ctrl+C."""

		if self.second_ctrl_c:
			raise KeyboardInterrupt
		return "KeyboardInterrupt"

	def close (self) -> None:

		"""Remember being closed."""

		self.closed = True


@pytest.mark.parametrize("second_ctrl_c", [False, True], ids=["once", "twice"])
def test_the_repl_stops_the_code_on_ctrl_c_and_stops_waiting_on_a_second (monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], second_ctrl_c: bool) -> None:

	"""Ctrl+C while waiting interrupts the code and prints its answer; a second one leaves the REPL."""

	fake = _FakeClient(second_ctrl_c)
	typed = iter(["while True: pass"])

	def _input (prompt: str) -> str:
		try:
			return next(typed)
		except StopIteration:
			raise EOFError

	monkeypatch.setattr(subsequence.live_client, "LiveClient", lambda: fake)
	monkeypatch.setattr("builtins.input", _input)
	monkeypatch.setattr(sys, "argv", ["live_client"])

	# Before, the Ctrl+C escaped the REPL altogether; catch it here so that fails as an
	# assertion rather than stopping the test run as a KeyboardInterrupt would.
	try:
		subsequence.live_client.main()
		escaped = False
	except KeyboardInterrupt:
		escaped = True

	printed = capsys.readouterr().out

	assert not escaped, "Ctrl+C while waiting ended the REPL"
	assert fake.interrupted == 1
	assert fake.closed

	if second_ctrl_c:
		assert "Stopped waiting" in printed
	else:
		assert printed.rstrip().endswith("KeyboardInterrupt")


@pytest.mark.asyncio
async def test_an_ordinary_line_is_answered_without_waiting_on_the_watcher (composition: subsequence.Composition) -> None:

	"""Watching for Ctrl+C must cost a typed line nothing: its answer, and the clock, wait on the watcher.

	The first watcher polled, and stopping it waited out the poll on the loop, so every line held
	the clock up to 50 ms longer.  Twenty lines normally take a few milliseconds all told; the
	limit is generous, and still well under the one second a 50 ms poll would add.
	"""

	server, port = await _started(composition)
	reader, writer = await asyncio.open_connection("127.0.0.1", port)

	try:
		started = time.monotonic()

		for _ in range(20):
			writer.write(b"1 + 1" + SENTINEL)
			await writer.drain()
			assert await _answer(reader) == "2"

		assert time.monotonic() - started < 0.5

	finally:
		writer.close()
		await server.stop()


@pytest.mark.asyncio
async def test_no_watcher_listens_once_the_signal_has_been_taken_back (composition: subsequence.Composition) -> None:

	"""Code outside a submission can set SIGUSR1 back to its default, and then a watcher's request would end the process.

	(A submission's own change is undone as it finishes, along with the other handlers it was
	lent.)  So a watcher runs only while the server's handler is really in place.  Asked from
	inside a submission, which is when a watcher would be running, the list of threads says
	whether one is - no signal is sent, so a server that gets this wrong fails here instead of dying.
	"""

	server, port = await _started(composition)
	reader, writer = await asyncio.open_connection("127.0.0.1", port)
	watching = b"'live-interrupt-watcher' in [thread.name for thread in threading.enumerate()]"

	try:
		writer.write(b"import threading" + SENTINEL)
		writer.write(watching + SENTINEL)
		await writer.drain()
		assert [await _answer(reader), await _answer(reader)] == ["OK", "True"]

		signal.signal(signal.SIGUSR1, signal.SIG_DFL)

		writer.write(watching + SENTINEL)
		await writer.drain()
		assert await _answer(reader) == "False"

	finally:
		writer.close()
		await server.stop()
