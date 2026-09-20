"""Interactive REPL client for live coding a running Subsequence composition.

Usage::

    python -m subsequence.live_client
    python -m subsequence.live_client --port 5555

The client connects to a live server started by ``composition.live()`` and
provides an interactive Python prompt. Multi-line blocks are supported - type
a block header, or a decorator, and the client waits for the rest; a blank line
sends it.

Press Ctrl+C to cancel the current input. Press Ctrl+D to quit.
"""

import argparse
import codeop
import socket
import sys
import typing


SENTINEL = b"\x04"


class LiveClient:

	"""TCP client that sends code to a running Subsequence live server."""

	def __init__ (self) -> None:

		"""Initialize with no connection."""

		self._sock: typing.Optional[socket.socket] = None

	def connect (self, host: str = "127.0.0.1", port: int = 5555) -> None:

		"""Connect to the live server."""

		self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._sock.connect((host, port))

	def send (self, code: str) -> str:

		"""Send code to the server and return the response."""

		if self._sock is None:
			raise ConnectionError("Not connected")

		self._sock.sendall(code.encode("utf-8") + SENTINEL)

		chunks: typing.List[bytes] = []

		while True:
			chunk = self._sock.recv(4096)

			if not chunk:
				raise ConnectionError("Server closed connection")

			if SENTINEL in chunk:
				before, _, _ = chunk.partition(SENTINEL)
				chunks.append(before)
				break

			chunks.append(chunk)

		return b"".join(chunks).decode("utf-8")

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
				response = client.send(code)
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
