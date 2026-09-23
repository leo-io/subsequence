"""TCP eval server for live coding a running composition.

Start the server by calling ``composition.live()`` before ``composition.play()``.
The server listens on a TCP port (default 5555) and accepts Python code from any
source - the bundled REPL client, an editor plugin, or a raw socket connection.

Protocol
────────
Messages are delimited by ``\\x04`` (ASCII EOT). The server reads until it
receives this sentinel, evaluates the code, and sends the result (or error
traceback) followed by ``\\x04``.  Messages may be sent back to back without
waiting for each answer, and each is answered in turn; an empty message is
answered ``OK``.

Each message is a declaration pass in its own right, run on the loop that owns
the composition: whatever it declares afresh is brought in at the next whole
multiple of its own length, whatever it re-declares is swapped in place, and
what it leaves behind is remembered under ``REPL_SOURCE`` so a watched file's
save never tears the performer's own work down.

Security note: the server binds to ``localhost`` only and is opt-in via
``composition.live()``. It executes arbitrary Python in the composition's
process - this is intentional for live coding. Any process on the same
machine that can connect to the port has full code execution in this
process, so do not enable live mode on shared or multi-user hosts, and
never expose the port to a network.
"""

import asyncio
import logging
import traceback
import types
import typing

if typing.TYPE_CHECKING:
	from subsequence.composition import Composition


logger = logging.getLogger(__name__)

SENTINEL = b"\x04"

# The longest message the server will wait for, sentinel included.  asyncio's
# default is 64 KiB, which a pasted composition file can pass; past this a
# connection is closed rather than buffered without end.
MESSAGE_LIMIT = 16 * 1024 * 1024

# What the REPL declares is filed under this name, so a watched file's save
# removes only what that file stopped declaring and never the performer's
# typing (#2999).
REPL_SOURCE = "<repl>"


class LiveServer:

	"""Async TCP server that evaluates Python code inside a running composition."""

	def __init__ (self, composition: "Composition", port: int = 5555) -> None:

		"""Store a reference to the composition and the port to listen on."""

		self._composition = composition
		self._port = port
		self._server: typing.Optional[asyncio.AbstractServer] = None
		self._namespace: typing.Dict[str, typing.Any] = {}
		self._clients: typing.Set[asyncio.StreamWriter] = set()

	async def start (self) -> None:

		"""Start listening for connections on localhost."""

		self._namespace = self._composition._build_live_namespace()

		self._server = await asyncio.start_server(
			self._handle_connection,
			host = "127.0.0.1",
			port = self._port,
			limit = MESSAGE_LIMIT
		)

		logger.info(f"Live server listening on 127.0.0.1:{self._port}")

	async def stop (self) -> None:

		"""Close the server, and every client still connected, then wait for it to shut down.

		From Python 3.12.1 ``wait_closed()`` waits for every open connection, and
		a REPL left connected in another terminal never closes by itself: Ctrl+C
		silenced the music and ``play()`` then waited for that client to quit
		(#3365).  ``Server.close_clients()`` would do this from Python 3.13; the
		server keeps its own list so it works on every version this supports.
		"""

		if self._server is not None:
			self._server.close()

			for writer in list(self._clients):
				writer.close()

			await self._server.wait_closed()
			self._server = None
			logger.info("Live server stopped")

	async def _handle_connection (self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:

		"""Handle a single client connection with an eval/exec loop."""

		peer = writer.get_extra_info("peername")
		logger.info(f"Live client connected: {peer}")
		self._clients.add(writer)

		try:

			# A client that connected just as stop() began is not in the list it
			# closed, so it leaves here instead of waiting to be read from.
			while self._server is not None and self._server.is_serving():

				code = await self._read_message(reader)

				if code is None:
					break

				response = await self._submit(code) if code else "OK"
				writer.write(response.encode() + SENTINEL)
				await writer.drain()

		except ConnectionResetError:
			logger.info(f"Live client disconnected (reset): {peer}")

		except Exception as exc:
			logger.warning(f"Live connection error: {exc}")

		finally:
			self._clients.discard(writer)
			writer.close()
			try:
				await writer.wait_closed()
			except Exception:
				pass
			logger.info(f"Live client disconnected: {peer}")

	async def _read_message (self, reader: asyncio.StreamReader) -> typing.Optional[str]:

		"""Read one message, up to its sentinel, or None once the client has gone.

		Whatever follows the sentinel stays in the reader for the next call, so
		messages sent back to back, or one split across two sends, each arrive
		whole.  This used to read in chunks and keep only what came before the
		first sentinel in each, so a second message in the same read was lost and
		its client waited forever, and an empty message read as the client
		leaving (#3364).  Bytes after the last sentinel when the client closes are
		a message it never finished, and are dropped.
		"""

		try:
			raw = await reader.readuntil(SENTINEL)
		except (asyncio.IncompleteReadError, ConnectionResetError):
			return None

		return raw[:-len(SENTINEL)].decode("utf-8", errors = "replace").strip()

	async def _submit (self, code: str) -> str:

		"""Play one typed submission into the composition, and start what it added.

		A line typed at the REPL is a declaration in its own right, and is
		treated as one - the same pass a file save gets.  What it declares
		afresh comes in at the next whole multiple of its own length, so a
		new part lands on a bar line rather than wherever the typing fell
		(:meth:`Composition._next_start_pulse`), and re-declaring a part that
		is already playing swaps its body in place instead of standing a
		second copy beside it.

		Until #2999 a submission was run on a worker thread and then left
		alone: a new ``@composition.pattern`` was acknowledged with ``OK``
		and never heard, and a re-declared ``layer()`` came back as a second
		layer with a ``#2`` on its name.  Running it here, on the loop that
		owns the pattern registry and the scheduler's queue, is what lets the
		declaration be acted on - at the cost of holding the clock for as
		long as the submission runs, which is the same bargain a watched file
		save already makes.

		What the REPL declares is remembered under its own name, so a later
		file save tears down its own deletions and leaves the performer's
		typing alone.
		"""

		composition = self._composition

		# Each submission is a fresh declaration pass, exactly as a save is.
		# Names left over from startup are what turned a re-declared layer
		# into a second one, because the name it would have reused was still
		# taken.
		composition._declared_names = set()

		response, declared = self._evaluate(code)

		if not declared:
			return response

		# Bring anything newly declared into rotation.  A part that was
		# already playing hot-swapped inside the exec and is not here.
		await composition._activate_new_pending_patterns()

		composition._source_declared[REPL_SOURCE] = (
			composition._source_declared.get(REPL_SOURCE, set()) | composition._declared_names
		)

		return response

	def _evaluate (self, code: str) -> typing.Tuple[str, bool]:

		"""Validate, then eval/exec the code string.

		Returns the text to send back, and whether the code ran to completion -
		a submission that raised has declared nothing worth scheduling, and its
		half-built patterns must not be started.
		"""

		# Validate syntax before executing - never run invalid code.
		try:
			statement = compile(code, "<live>", "exec")
		except SyntaxError:
			return traceback.format_exc(), False

		# An expression answers with its value, and anything else runs as a
		# statement.  Which one it is gets settled here, before anything runs,
		# so the code runs exactly once.  This used to try eval() and fall back
		# to exec() on any SyntaxError, so an expression that raised one while
		# RUNNING - compile() or eval() on bad text - was run a second time as a
		# statement, side effects and all (#3366).
		try:
			expression: typing.Optional[types.CodeType] = compile(code, "<live>", "eval")
		except SyntaxError:
			expression = None

		try:

			if expression is not None:
				result = eval(expression, self._namespace)
				return (repr(result) if result is not None else "OK"), True

			exec(statement, self._namespace)
			return "OK", True

		except SystemExit:
			return "SystemExit is not allowed in live mode.", False
		except Exception:
			return traceback.format_exc(), False
