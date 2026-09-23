"""Single-keystroke input listener for live compositions.

Provides a background thread that reads individual keystrokes from stdin
without requiring the user to press Enter.  Designed to work alongside
:class:`subsequence.display.Display` without conflicts - the display writes
to **stderr** while this module reads from **stdin**.

**Platform support:** Linux and macOS.  Requires :mod:`tty` and :mod:`termios`,
which are only available on POSIX systems.  On unsupported platforms (e.g.
Windows, or environments where stdin is not a real TTY), the listener starts
in a degraded mode and logs a warning instead of raising an exception.

Check :data:`HOTKEYS_SUPPORTED` at import time to know whether the current
platform can support hotkeys.

This module is used internally by :class:`subsequence.composition.Composition`
when hotkeys are enabled via ``composition.hotkeys()``.  You do not need to
import it directly.
"""

import atexit
import logging
import queue
import select
import sys
import threading
import typing


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform capability detection
# ---------------------------------------------------------------------------

#: ``True`` when the current platform supports single-keystroke input.
#:
#: Requires :mod:`tty` and :mod:`termios` (POSIX-only) and a real TTY on
#: stdin.  Check this before enabling hotkeys if you need to branch on
#: platform support:
#:
#: .. code-block:: python
#:
#:     from subsequence.keystroke import HOTKEYS_SUPPORTED
#:     if HOTKEYS_SUPPORTED:
#:         composition.hotkeys()
HOTKEYS_SUPPORTED: bool = False

#: Short human-readable explanation of why hotkeys are not supported, or
#: ``None`` when :data:`HOTKEYS_SUPPORTED` is ``True``.
HOTKEYS_UNAVAILABLE_REASON: typing.Optional[str] = None


def _detect_hotkey_support () -> typing.Tuple[bool, typing.Optional[str]]:

	"""Decide whether this process can read single keystrokes, and say why not.

	Reads the terminal's settings; it must never **write** them.  A process in
	a background process group that writes its terminal's settings is sent
	SIGTTOU, whose default action is to stop it - and this runs on every
	``import subsequence``, so an import-time ``tcsetattr`` here stopped
	``python render_album.py &`` dead at the import, before the script ran a
	line of its own (#3033).

	Returns ``(supported, reason_if_not)``.
	"""

	try:
		import termios					# noqa: PLC0415
		import tty						# noqa: PLC0415,F401

		if not sys.stdin.isatty():
			raise OSError("stdin is not a TTY (running in a pipe or non-interactive context)")

		# Reading the settings proves the terminal can actually be
		# interrogated, which isatty() alone does not.
		termios.tcgetattr(sys.stdin.fileno())

	except ImportError:
		return False, (
			"The 'tty' and 'termios' modules are not available on this platform. "
			"Hotkeys require a POSIX operating system (Linux or macOS)."
		)
	except OSError as e:
		return False, (
			f"Hotkeys require an interactive terminal (TTY) on stdin. "
			f"Reason: {e}"
		)
	except Exception as e:
		return False, f"Hotkeys unavailable: {e}"

	return True, None


HOTKEYS_SUPPORTED, HOTKEYS_UNAVAILABLE_REASON = _detect_hotkey_support()


# ---------------------------------------------------------------------------
# Listener class
# ---------------------------------------------------------------------------

class KeystrokeListener:

	"""Background daemon thread that reads single keystrokes from stdin.

	Puts stdin into *cbreak* mode so each keypress is delivered immediately,
	without waiting for Enter.  Keystrokes are placed in a thread-safe queue
	and retrieved by the caller via :meth:`drain`.

	Terminal settings are always restored on shutdown, even if an exception
	occurs, so a crashed listener will not leave the terminal in a broken state.

	If the current platform does not support hotkeys (:data:`HOTKEYS_SUPPORTED`
	is ``False``), :meth:`start` logs a warning and returns immediately without
	starting the thread.  All other methods remain safe no-ops.

	Example::

		listener = KeystrokeListener()
		listener.start()

		# ...later, from the event loop...
		for key in listener.drain():
		    handle(key)

		listener.stop()
	"""

	def __init__ (self) -> None:

		"""Initialise the listener in a stopped state."""

		self._queue: queue.Queue[str] = queue.Queue()
		self._thread: typing.Optional[threading.Thread] = None
		self._running: bool = False
		self._old_settings: typing.Optional[typing.List[typing.Any]] = None

		#: ``True`` after a successful :meth:`start` on a supported platform.
		self.active: bool = False

	def start (self) -> None:

		"""Start the background keystroke listener thread.

		Puts stdin into cbreak mode and begins reading.  Call :meth:`stop`
		to restore normal terminal behaviour.  Safe to call more than once -
		a second call while already running is a no-op.

		If :data:`HOTKEYS_SUPPORTED` is ``False``, logs a warning and returns
		without starting the thread.  :attr:`active` will remain ``False``.
		"""

		if self._running:
			return

		# A previous listener may still be inside its ~0.1 s poll: wait for it,
		# or it would see the new _running=True, never exit, and the new thread
		# would snapshot CBREAK mode as the "original" terminal settings.
		if self._thread is not None and self._thread.is_alive():
			self._thread.join(timeout=0.5)

		if not HOTKEYS_SUPPORTED:
			logger.warning(
				f"Hotkeys are not available on this system and will be disabled. "
				f"{HOTKEYS_UNAVAILABLE_REASON}"
			)
			return

		self._running = True
		self.active = True
		self._thread = threading.Thread(
			target = self._listen,
			name   = "subsequence-keystroke-listener",
			daemon = True,   # Dies automatically when the main thread exits.
		)
		self._thread.start()

		# Last resort.  stop() is the ordinary route back to a usable
		# terminal, but it is reached only if the composition gets as far as
		# its teardown — and a musician left without echo cannot even read
		# what they type to fix it.  This costs nothing and runs whatever
		# happened.
		atexit.register(self._restore_terminal)

	def stop (self) -> None:

		"""Signal the listener to stop and restore the terminal.

		Waits briefly for the background thread (it polls every ~0.1 s), then
		restores the terminal settings directly if the thread has not done so -
		a daemon thread killed at interpreter exit never runs its ``finally``
		block, which used to leave the shell in cbreak mode (no echo) on most
		clean exits.  Safe to call on an unsupported platform - it is a no-op.
		"""

		self._running = False
		self.active = False

		if self._thread is not None and self._thread.is_alive():
			self._thread.join(timeout=0.5)

		# Belt and braces: if the thread is somehow still alive (blocked
		# read), restore the terminal from here - tcsetattr is idempotent.
		self._restore_terminal()

		atexit.unregister(self._restore_terminal)


	def _restore_terminal (self) -> None:

		"""Put the terminal back the way it was found.  Idempotent.

		Called by :meth:`stop`, and registered with ``atexit`` by
		:meth:`start` for the exits that never reach a teardown at all.
		"""

		settings = self._old_settings

		if settings is None:
			return

		try:
			import termios  # noqa: PLC0415
			termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, settings)
		except Exception:
			# At interpreter exit there may be no stdin left to restore.  A
			# failure here must never become the last thing a musician sees.
			logger.debug("Could not restore the terminal settings", exc_info = True)

	def drain (self) -> typing.List[str]:

		"""Return all keystrokes that have arrived since the last drain.

		Non-blocking.  Returns an empty list if nothing has been pressed, or
		if the listener is not active.  Safe to call at any time.

		Returns:
		    A list of single-character strings, one per keypress, in order.
		"""

		keys: typing.List[str] = []

		while True:
			try:
				keys.append(self._queue.get_nowait())
			except queue.Empty:
				break

		return keys

	def _listen (self) -> None:

		"""Internal thread target.  Runs until ``_running`` is set False.

		Uses :func:`select.select` with a short timeout so the thread can
		notice the ``_running = False`` signal without blocking indefinitely.
		Terminal settings are restored in the ``finally`` block so they are
		always cleaned up, even if an exception occurs.
		"""

		# These imports are guaranteed safe here — _listen is only called
		# when HOTKEYS_SUPPORTED is True, which already confirmed they exist.
		import termios  # noqa: PLC0415
		import tty      # noqa: PLC0415

		fd = sys.stdin.fileno()
		old_settings = termios.tcgetattr(fd)

		# Shared with stop() so it can restore the terminal if this thread is
		# killed before the finally block runs (daemon threads at exit).
		self._old_settings = old_settings

		try:
			# cbreak: one character at a time, no Enter required.
			# Differs from raw in that Ctrl+C / Ctrl+Z still work normally.
			tty.setcbreak(fd)

			while self._running:
				# Poll with a short timeout so we can check _running regularly.
				ready, _, _ = select.select([sys.stdin], [], [], 0.1)
				if ready:
					char = sys.stdin.read(1)
					if char:
						self._queue.put(char)

		except Exception:
			# A broken listener must not crash the composition — but dying
			# silently left "why did my hotkeys stop working?" unanswerable
			# (the finally below marks the listener inactive).
			logger.warning("Keystroke listener stopped after an unexpected error — hotkeys are now inactive", exc_info=True)

		finally:
			# Always restore terminal, even after exceptions.
			termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
			self.active = False
