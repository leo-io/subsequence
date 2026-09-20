"""A service that fails to start must not strand the others (#3035).

`Composition._run` started the display, live server, OSC server, keystroke
listener and web UI *before* the `try`/`finally` that tears them down.  So any
one of them failing skipped the whole teardown — including the keystroke
listener's restore of the terminal.

The usual trigger was the web UI's port already being in use, and `web_ui()`
took no port arguments at all, so the musician could not move it out of the
way.  Measured on a real pty with the port occupied:

    before: {'ECHO': True,  'ICANON': True}
    after : {'ECHO': False, 'ICANON': False}

— a shell that no longer echoes what you type, recoverable only by typing a
blind `stty sane`.

The services now start inside the `try`, `web_ui()` takes `http_port` and
`ws_port`, and the listener also restores the terminal from `atexit` for the
exits that never reach a teardown at all.
"""

import atexit
import os
import pathlib
import pty
import select
import signal
import socket
import sys
import termios
import typing
import unittest.mock

import pytest

import subsequence
import subsequence.keystroke
import subsequence.web_ui


REPO_ROOT = str(pathlib.Path(subsequence.__file__).resolve().parent.parent)


def _piece () -> subsequence.Composition:

	composition = subsequence.Composition(bpm = 480)

	@composition.pattern(channel = 1, beats = 4)
	def drums (p: typing.Any) -> None:
		p.note(beat = 0, pitch = 36, velocity = 100)

	return composition


def _free_port () -> int:

	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
		probe.bind(("127.0.0.1", 0))
		return int(probe.getsockname()[1])


# ---------------------------------------------------------------------------
# The teardown runs
# ---------------------------------------------------------------------------

def test_a_service_that_fails_to_start_still_stops_the_keystroke_listener (
	monkeypatch: pytest.MonkeyPatch,
	patch_midi: None,
) -> None:

	"""The listener starts before the web UI, and is what holds the terminal."""

	composition = _piece()
	composition.hotkeys()
	composition.web_ui()

	stopped: typing.List[str] = []

	monkeypatch.setattr(
		subsequence.keystroke.KeystrokeListener, "stop",
		lambda self: stopped.append("keystroke"),
	)

	def will_not_start (self: typing.Any) -> None:
		raise OSError(98, "Address already in use")

	monkeypatch.setattr(subsequence.web_ui.WebUI, "start", will_not_start)

	with pytest.raises(OSError):
		composition.play()

	assert stopped == ["keystroke"], \
		"the web UI failed to start and the terminal was left to the listener's daemon thread"


def test_a_service_that_fails_to_start_still_stops_the_display (
	monkeypatch: pytest.MonkeyPatch,
	patch_midi: None,
) -> None:

	"""The display swaps the log handlers, and used to leave them swapped."""

	composition = _piece()
	composition.display()
	composition.web_ui()

	stopped: typing.List[str] = []

	monkeypatch.setattr(
		subsequence.display.Display, "stop",
		lambda self: stopped.append("display"),
	)

	def will_not_start (self: typing.Any) -> None:
		raise OSError(98, "Address already in use")

	monkeypatch.setattr(subsequence.web_ui.WebUI, "start", will_not_start)

	with pytest.raises(OSError):
		composition.play()

	assert stopped == ["display"]


def test_an_ordinary_run_still_tears_everything_down (
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
	patch_midi: None,
) -> None:

	"""The control: moving the starts inside the try must not skip them on success."""

	composition = _piece()
	composition.hotkeys()

	started: typing.List[str] = []
	stopped: typing.List[str] = []

	monkeypatch.setattr(
		subsequence.keystroke.KeystrokeListener, "start",
		lambda self: started.append("keystroke"),
	)
	monkeypatch.setattr(
		subsequence.keystroke.KeystrokeListener, "stop",
		lambda self: stopped.append("keystroke"),
	)

	composition.render(bars = 2, filename = str(tmp_path / "out.mid"))

	# A render starts no listener at all — that is the render contract (#2995).
	assert started == []
	assert stopped == []


# ---------------------------------------------------------------------------
# The port is the musician's to move
# ---------------------------------------------------------------------------

def test_web_ui_ports_reach_the_server (patch_midi: None) -> None:

	"""`web_ui()` took hosts but no ports, so a taken 8080 could not be moved."""

	composition = _piece()
	composition.web_ui(http_port = 8090, ws_port = 8775)

	seen: typing.Dict[str, typing.Any] = {}

	original = subsequence.web_ui.WebUI.__init__

	def recording (self: typing.Any, composition: typing.Any, **kwargs: typing.Any) -> None:
		seen.update(kwargs)
		original(self, composition, **kwargs)

	def will_not_start (self: typing.Any) -> None:
		raise OSError(98, "Address already in use")

	with unittest.mock.patch.object(subsequence.web_ui.WebUI, "__init__", recording), \
	     unittest.mock.patch.object(subsequence.web_ui.WebUI, "start", will_not_start):

		with pytest.raises(OSError):
			composition.play()

	assert seen.get("http_port") == 8090, seen
	assert seen.get("ws_port") == 8775, seen


def test_the_web_ui_ports_still_default_to_the_documented_pair (patch_midi: None) -> None:

	"""Adding the parameters must not move anybody's dashboard."""

	composition = _piece()
	composition.web_ui()

	assert composition._web_ui_http_port == 8080
	assert composition._web_ui_ws_port == 8765


# ---------------------------------------------------------------------------
# The terminal itself
# ---------------------------------------------------------------------------

def test_the_listener_registers_an_atexit_restore (monkeypatch: pytest.MonkeyPatch) -> None:

	"""For the exits that never reach any teardown, a daemon thread included.

	The runner usually has no TTY on stdin, so hotkey support is patched on and
	the reader thread stubbed out — otherwise this would skip, and a skipped
	test pins nothing.
	"""

	monkeypatch.setattr(subsequence.keystroke, "HOTKEYS_SUPPORTED", True)

	class NotReallyAThread:
		def __init__ (self, **kwargs: typing.Any) -> None:
			pass
		def start (self) -> None:
			pass
		def is_alive (self) -> bool:
			return False

	monkeypatch.setattr(subsequence.keystroke.threading, "Thread", NotReallyAThread)

	registered: typing.List[typing.Any] = []
	unregistered: typing.List[typing.Any] = []

	monkeypatch.setattr(subsequence.keystroke.atexit, "register", lambda fn: registered.append(fn))
	monkeypatch.setattr(subsequence.keystroke.atexit, "unregister", lambda fn: unregistered.append(fn))

	listener = subsequence.keystroke.KeystrokeListener()
	listener.start()

	assert listener._restore_terminal in registered, \
		"nothing puts the terminal back if stop() is never reached"

	listener.stop()

	assert listener._restore_terminal in unregistered, \
		"a stopped listener still holds an exit hook for a terminal it no longer owns"


def test_restoring_a_terminal_that_was_never_taken_touches_nothing (
	monkeypatch: pytest.MonkeyPatch,
) -> None:

	"""stop() and atexit both call it, on listeners that never ran.

	Asserting only that it does not raise proves nothing — the restore
	swallows exceptions by design, so it would pass with the guard removed and
	`tcsetattr(fd, TCSADRAIN, None)` failing quietly underneath.  What says the
	guard is there is that nothing was written at all.
	"""

	import termios

	written: typing.List[typing.Any] = []

	class LooksLikeATerminal:
		def fileno (self) -> int:
			return 0

	# Without a working fileno(), the restore fails on `sys.stdin.fileno()`
	# before it reaches tcsetattr — under pytest stdin raises there — and this
	# test passes with the guard removed, having proved nothing.
	monkeypatch.setattr(sys, "stdin", LooksLikeATerminal())
	monkeypatch.setattr(termios, "tcsetattr", lambda *args: written.append(args))

	listener = subsequence.keystroke.KeystrokeListener()

	listener._restore_terminal()				# never started: nothing to put back
	listener._restore_terminal()

	assert written == [], "it tried to write terminal settings it never saved"


@pytest.mark.skipif(
	not hasattr(os, "fork") or not hasattr(termios, "ECHO"),
	reason = "needs POSIX job control and termios",
)
# The child calls execve immediately, which is the one fork pattern that is
# safe in a threaded parent — but only a new session gives the composition a
# controlling terminal of its own to leave broken, and that needs the fork.
@pytest.mark.filterwarnings("ignore:This process .* is multi-threaded:DeprecationWarning")
def test_a_failed_startup_leaves_the_terminal_usable () -> None:

	"""The finding as the musician meets it: echo and line editing survive.

	Runs a composition on a real pty with the dashboard's port already taken,
	and reads the terminal flags afterwards.

	Two independent mechanisms hold this up — the teardown in `_run`'s
	`finally`, and the listener's `atexit` restore — so breaking either one
	alone leaves this passing, and it is the tests above that pin them
	individually.  That is the point of having two; this one says the musician
	gets a usable terminal back, however that is achieved.
	"""

	port = _free_port()

	blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	blocker.bind(("127.0.0.1", port))
	blocker.listen(1)

	child_code = (
		"import subsequence\n"
		"c = subsequence.Composition(bpm=480, output_device='Dummy MIDI')\n"
		"@c.pattern(channel=1, beats=4)\n"
		"def d(p): p.note(beat=0, pitch=36, velocity=100)\n"
		"c.hotkeys()\n"
		f"c.web_ui(http_port={port})\n"
		"try:\n"
		"    c.play()\n"
		"except BaseException as e:\n"
		"    import sys; sys.stderr.write('FAILED %s\\n' % type(e).__name__)\n"
	)

	master, slave = pty.openpty()
	slave_name = os.ttyname(slave)

	def flags (fd: int) -> typing.Dict[str, bool]:
		lflag = termios.tcgetattr(fd)[3]
		return {"ECHO": bool(lflag & termios.ECHO), "ICANON": bool(lflag & termios.ICANON)}

	before = flags(slave)

	child = os.fork()

	if child == 0:								# pragma: no cover - child process
		try:
			os.close(master)
			os.setsid()
			tty_fd = os.open(slave_name, os.O_RDWR)
			os.dup2(tty_fd, 0)
			os.dup2(tty_fd, 1)
			os.dup2(tty_fd, 2)

			env = dict(os.environ)
			env["PYTHONPATH"] = REPO_ROOT
			env["PYTHONDONTWRITEBYTECODE"] = "1"

			os.execve(sys.executable, [sys.executable, "-c", child_code], env)
		finally:
			os._exit(127)

	os.close(slave)

	try:
		import time

		deadline = time.monotonic() + 60.0
		os.set_blocking(master, False)
		seen = b""
		finished = False

		while time.monotonic() < deadline:
			done, _ = os.waitpid(child, os.WNOHANG)

			try:
				chunk = os.read(master, 4096)
				if chunk:
					seen += chunk
			except (BlockingIOError, OSError):
				pass

			if done:
				finished = True
				break

			time.sleep(0.02)

		if not finished:
			os.kill(child, signal.SIGKILL)
			os.waitpid(child, 0)
			pytest.fail("the composition neither started nor failed within 60s")

		after = flags(master)

		assert b"FAILED" in seen, \
			f"the port was taken but the composition did not fail: {seen[-500:]!r}"

		changed = [name for name in before if before[name] != after[name]]

		assert changed == [], \
			f"a failed startup left the terminal with {changed} changed — no echo, no line editing"

	finally:
		os.close(master)
		blocker.close()
