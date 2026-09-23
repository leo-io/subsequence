"""Keys typed together reach the hotkeys together, and a closed terminal ends the listener (#3479).

The listener waited on select() for the terminal, then read one character through sys.stdin,
whose text wrapper took every byte the kernel held and kept the rest where select() could not
see them.  Two keys typed together delivered the first; the second waited for a third key - 40
of 40 trials on a real pseudo-terminal.  It reads the descriptor itself now.

These run the listener on a real pseudo-terminal.  tty.setcbreak() flushes whatever is waiting
when the listener starts (TCSAFLUSH), so every key here is typed after the listener has cleared
ICANON: a key typed before that is discarded, which is how the first probe for this lost both.
"""

import array
import fcntl
import os
import sys
import termios
import threading
import time
import typing

import pytest

import subsequence.keystroke


class _Terminal:

	"""Both ends of a pseudo-terminal whose slave side is stdin."""

	def __init__ (self) -> None:

		self.master, self.slave = os.openpty()
		self.stdin = open(self.slave, "r", encoding="utf-8", closefd=False)
		self.hung_up = False

	def type (self, data: bytes) -> None:

		"""Keys, as a keyboard would send them."""

		os.write(self.master, data)

	def hang_up (self) -> None:

		"""Close the terminal's far end, as closing its window does."""

		os.close(self.master)
		self.hung_up = True

	def wait_until_read (self) -> None:

		"""Wait until the listener has taken everything the kernel held.

		The kernel moves what the master is sent across to the slave a moment
		later, so an empty count straight after typing can mean "not there
		yet" rather than "read".  That let two bytes typed apart arrive in one
		read here, and a break that decoded each read on its own passed.
		"""

		time.sleep(0.1)

		waiting = array.array("i", [1])
		deadline = time.monotonic() + 1.0

		while True:
			fcntl.ioctl(self.slave, termios.FIONREAD, waiting)
			if waiting[0] == 0:
				return
			assert time.monotonic() < deadline, "the listener never read what was typed"
			time.sleep(0.001)

	def close (self) -> None:

		self.stdin.close()
		os.close(self.slave)

		if not self.hung_up:
			os.close(self.master)


@pytest.fixture
def terminal (monkeypatch: pytest.MonkeyPatch) -> typing.Iterator[_Terminal]:

	"""A pseudo-terminal on stdin, with hotkeys supported."""

	pty = _Terminal()

	monkeypatch.setattr(subsequence.keystroke, "HOTKEYS_SUPPORTED", True)
	monkeypatch.setattr(sys, "stdin", pty.stdin)

	yield pty

	pty.close()


def _listening () -> subsequence.keystroke.KeystrokeListener:

	"""A started listener, once it has put the terminal into cbreak mode."""

	listener = subsequence.keystroke.KeystrokeListener()
	listener.start()
	assert listener.active

	deadline = time.monotonic() + 2.0

	while termios.tcgetattr(sys.stdin.fileno())[3] & termios.ICANON:
		assert time.monotonic() < deadline, "the listener never put the terminal into cbreak mode"
		time.sleep(0.001)

	return listener


def _collect (listener: subsequence.keystroke.KeystrokeListener, count: int, within: float = 1.0) -> typing.List[str]:

	"""Keys from the listener, until *count* have arrived or *within* seconds have passed."""

	keys: typing.List[str] = []
	deadline = time.monotonic() + within

	while len(keys) < count and time.monotonic() < deadline:
		keys.extend(listener.drain())
		time.sleep(0.005)

	return keys


def test_two_keys_typed_together_both_arrive (terminal: _Terminal) -> None:

	"""'ab' in one write: both keys arrive, without a third key to push the second out."""

	listener = _listening()

	try:
		terminal.type(b"ab")
		keys = _collect(listener, 2)
	finally:
		listener.stop()

	assert keys == ["a", "b"]


def test_a_character_split_across_two_reads_arrives_whole (terminal: _Terminal) -> None:

	"""The two bytes of an é, read one at a time, make one key.

	A guard for the descriptor read: sys.stdin decoded this before #3479 as well.
	"""

	encoded = "é".encode("utf-8")
	listener = _listening()

	try:
		terminal.type(encoded[:1])
		terminal.wait_until_read()
		terminal.type(encoded[1:])
		keys = _collect(listener, 1)
		time.sleep(0.05)
		keys.extend(listener.drain())
	finally:
		listener.stop()

	assert keys == ["é"]


def test_the_listener_ends_when_its_terminal_closes (terminal: _Terminal) -> None:

	"""With the terminal gone the listener stops by itself.  It spun a core until stop()."""

	listener = _listening()
	assert listener._thread is not None

	try:
		terminal.hang_up()
		listener._thread.join(timeout=1.0)

		assert not listener._thread.is_alive()
		assert listener.active is False
	finally:
		listener.stop()


def test_a_terminal_that_has_gone_is_not_restored_as_an_error (terminal: _Terminal, monkeypatch: pytest.MonkeyPatch) -> None:

	"""The listener cannot put a closed terminal back, and says nothing about it.

	The failure used to escape its thread as a traceback.
	"""

	escaped: typing.List[typing.Optional[BaseException]] = []
	monkeypatch.setattr(threading, "excepthook", lambda args: escaped.append(args.exc_value))

	listener = _listening()
	assert listener._thread is not None

	terminal.hang_up()
	listener._thread.join(timeout=1.0)
	listener.stop()

	assert not listener._thread.is_alive()
	assert escaped == []
