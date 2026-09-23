"""Interactive REPL client for live coding a running Subsequence composition.

Usage::

    python -m subsequence.live_client
    python -m subsequence.live_client --port 5555

The client connects to a live server started by ``composition.live()`` and
provides an interactive Python prompt. Multi-line blocks are supported - type
a block header, or a decorator, and the client waits for the rest; a blank line
sends it.

Press Ctrl+C to cancel the current input. Press Ctrl+D to quit.

Press Ctrl+C while waiting for an answer to stop the code the composition is
running - a runaway loop, a long sleep - and the music carries on, as Python's
own REPL would stop it.  Press it again to stop waiting.
"""

import argparse
import codeop
import socket
import sys
import typing


SENTINEL = b"\x04"

# What asks the server to stop the code it is running: ETX, the byte Ctrl+C types.
INTERRUPT = b"\x03"


class LiveClient:

	"""TCP client that sends code to a running Subsequence live server."""

	def __init__ (self) -> None:

		"""Initialise with no connection."""

		self._sock: typing.Optional[socket.socket] = None

		# What has arrived but not been answered yet.  Kept here rather than in
		# a read, so a Ctrl+C in the middle of one loses nothing.
		self._buffer = b""

	def connect (self, host: str = "127.0.0.1", port: int = 5555) -> None:

		"""Connect to the live server."""

		self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._sock.connect((host, port))

	def send (self, code: str) -> str:

		"""Send code to the server and return the response."""

		if self._sock is None:
			raise ConnectionError("Not connected")

		self._sock.sendall(code.encode("utf-8") + SENTINEL)

		return self.answer()

	def answer (self) -> str:

		"""Wait for the server's next answer, and return it."""

		if self._sock is None:
			raise ConnectionError("Not connected")

		while SENTINEL not in self._buffer:

			chunk = self._sock.recv(4096)

			if not chunk:
				raise ConnectionError("Server closed connection")

			self._buffer += chunk

		message, _, self._buffer = self._buffer.partition(SENTINEL)

		return message.decode("utf-8")

	def interrupt (self) -> None:

		"""Ask the server to stop the code it is running for this client (#3371).

		Its answer to that code then comes back as usual, reading
		``KeyboardInterrupt``.  With nothing running, the server ignores it.
		"""

		if self._sock is None:
			raise ConnectionError("Not connected")

		self._sock.sendall(INTERRUPT)

	def close (self) -> None:

		"""Close the connection."""

		if self._sock is not None:
			self._sock.close()
			self._sock = None


def _is_incomplete (code: str) -> bool:

	"""Return True if the code looks like an incomplete multi-line block."""

	stripped = code.rstrip()

	if not stripped:
		return False

	# Ask Python, which is the only thing that knows.  Counting brackets and
	# looking for a trailing colon reads a block header, but it calls a lone
	# decorator finished — so `@composition.pattern(channel=1, beats=4)` went
	# off to the server by itself, came back a SyntaxError, and the `def` after
	# it arrived undecorated.  A decorated function, which is what live() is
	# for, could not be sent at all (#2999).
	try:
		return codeop.compile_command(code, "<live>", "exec") is None
	except (SyntaxError, OverflowError, ValueError):
		# Broken beyond repair: send it, and let the server say what is wrong.
		# Holding the performer at a "..." prompt they cannot escape is worse.
		return False


def main () -> None:

	"""Run the interactive REPL loop."""

	parser = argparse.ArgumentParser(description="Subsequence live coding client")
	parser.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
	parser.add_argument("--port", type=int, default=5555, help="Server port (default: 5555)")
	args = parser.parse_args()

	client = LiveClient()

	try:
		client.connect(args.host, args.port)
	except ConnectionRefusedError:
		print(f"Could not connect to {args.host}:{args.port}")
		print("Is the composition running with composition.live() enabled?")
		sys.exit(1)

	print(f"Connected to Subsequence on {args.host}:{args.port}")

	# Fetch and display status header.  A failure here is cosmetic (the REPL
	# still works), but say so instead of hiding it.
	try:
		info_response = client.send("composition.live_info()")
		print(info_response)
	except Exception as e:
		print(f"(could not fetch the status header: {e})")

	print()

	try:

		while True:

			try:
				line = input(">>> ")
			except KeyboardInterrupt:
				print()
				continue

			lines = [line]

			# Accumulate multi-line blocks.  Once a block has started, only a
			# BLANK line ends it (standard REPL behaviour) — terminating when
			# the joined code merely "looked complete" cut every block off
			# after its first body line.
			in_block = _is_incomplete(line)

			while in_block or _is_incomplete("\n".join(lines)):
				try:
					continuation = input("... ")
				except KeyboardInterrupt:
					print()
					lines = []
					break

				if in_block and continuation.strip() == "":
					break

				lines.append(continuation)

			if not lines:
				continue

			code = "\n".join(lines).strip()

			if not code:
				continue

			try:

				try:
					response = client.send(code)

				except KeyboardInterrupt:

					# Stop what the composition is running for us; the music carries on.
					client.interrupt()
					print("\nInterrupting - press Ctrl+C again to stop waiting.")

					try:
						response = client.answer()
					except KeyboardInterrupt:
						print("\nStopped waiting.  The composition is still playing.")
						break

				print(response)

			except ConnectionError:
				print("Connection lost.")
				break

	except EOFError:
		print()

	finally:
		client.close()


if __name__ == "__main__":
	main()
