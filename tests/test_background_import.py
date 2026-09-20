"""Importing subsequence must not stop a backgrounded job (#3033).

`subsequence/keystroke.py` probes for hotkey support at import time, and every
`import subsequence` imports it.  That probe used to *write* the terminal's
settings (`termios.tcsetattr`).  A process in a background process group that
writes its terminal's settings is sent SIGTTOU by the kernel, whose default
action is to **stop** it — so

    python render_album.py &

stopped at the import and did nothing, silently, until somebody foregrounded
it.  Measured: `import subsequence` stopped with SIGTTOU while `import os`
exited 0.

Reading the settings is harmless and proves everything the probe needs, so the
probe reads and does not write.
"""

import os
import pathlib
import pty
import select
import signal
import subprocess
import sys
import typing

import pytest

import subsequence


REPO_ROOT = str(pathlib.Path(subsequence.__file__).resolve().parent.parent)


def _run_in_background_process_group (
	code: str,
	timeout: float = 30.0,
) -> typing.Tuple[str, int]:

	"""Run *code* in a background process group of a fresh controlling terminal.

	Returns ``("stopped", signum)``, ``("exited", status)`` or
	``("signalled", signum)``.

	The terminal is built here rather than borrowed from the test runner, so
	this neither depends on nor disturbs however pytest was invoked.
	"""

	read_fd, write_fd = os.pipe()
	master, slave = pty.openpty()
	slave_name = os.ttyname(slave)

	middle = os.fork()

	if middle == 0:							# pragma: no cover - child process
		try:
			os.close(master)
			os.close(read_fd)
			os.setsid()

			# A session with no controlling terminal acquires one by opening it.
			tty_fd = os.open(slave_name, os.O_RDWR)

			child = os.fork()

			if child == 0:
				os.setpgid(0, 0)			# a background group: not the foreground one
				os.dup2(tty_fd, 0)
				os.dup2(tty_fd, 1)
				os.dup2(tty_fd, 2)

				env = dict(os.environ)
				env["PYTHONPATH"] = REPO_ROOT
				env["PYTHONDONTWRITEBYTECODE"] = "1"

				os.execve(sys.executable, [sys.executable, "-c", code], env)
				os._exit(127)

			_, status = os.waitpid(child, os.WUNTRACED)

			if os.WIFSTOPPED(status):
				os.kill(child, signal.SIGKILL)
				os.waitpid(child, 0)
				answer = f"stopped {os.WSTOPSIG(status)}"
			elif os.WIFSIGNALED(status):
				answer = f"signalled {os.WTERMSIG(status)}"
			else:
				answer = f"exited {os.WEXITSTATUS(status)}"

			os.write(write_fd, answer.encode())
		finally:
			os._exit(0)

	os.close(write_fd)
	os.close(slave)

	ready, _, _ = select.select([read_fd], [], [], timeout)

	if not ready:
		os.kill(middle, signal.SIGKILL)
		os.waitpid(middle, 0)
		os.close(read_fd)
		os.close(master)
		pytest.fail(f"the child never finished within {timeout}s")

	answer = os.read(read_fd, 64).decode()

	os.close(read_fd)
	os.close(master)
	os.waitpid(middle, 0)

	kind, _, number = answer.partition(" ")

	return kind, int(number or 0)


pytestmark = [
	pytest.mark.skipif(
		not hasattr(os, "fork") or not hasattr(signal, "SIGTTOU"),
		reason = "needs POSIX process groups and job control",
	),
	# The grandchild calls execve immediately, which is the one fork pattern
	# that is safe in a threaded parent — and a background process group of a
	# terminal it owns cannot be built any other way.
	pytest.mark.filterwarnings("ignore:This process .* is multi-threaded:DeprecationWarning"),
]


def test_a_backgrounded_import_is_not_stopped () -> None:

	"""The finding itself: `python render_album.py &` must get as far as its own code."""

	kind, number = _run_in_background_process_group("import subsequence")

	if kind == "stopped":
		pytest.fail(
			f"importing subsequence in a background job was stopped by "
			f"{signal.Signals(number).name} — it would never run"
		)

	assert (kind, number) == ("exited", 0)


def test_importing_the_keystroke_module_alone_is_not_stopped () -> None:

	"""Narrows it to the module that holds the probe, so a fix elsewhere cannot fake this."""

	kind, number = _run_in_background_process_group("import subsequence.keystroke")

	assert kind == "exited", f"import subsequence.keystroke was {kind} {number}"
	assert number == 0


def test_the_harness_itself_lets_an_innocent_import_through () -> None:

	"""A control.  Without it, a harness that stops everything proves nothing.

	This is not hypothetical: the first version of this check appended the
	`import subsequence` assertion to the control as well, so the control
	"stopped" too and the two cases were indistinguishable.
	"""

	assert _run_in_background_process_group("import os") == ("exited", 0)


def test_the_harness_can_still_see_a_stop () -> None:

	"""And the other half of the control: a real terminal write must still stop.

	If this ever passes, the harness has stopped measuring what it claims to —
	the process group is no longer in the background, or there is no terminal.
	"""

	kind, number = _run_in_background_process_group(
		"import sys, termios; "
		"fd = sys.stdin.fileno(); "
		"termios.tcsetattr(fd, termios.TCSADRAIN, termios.tcgetattr(fd))"
	)

	assert (kind, number) == ("stopped", int(signal.SIGTTOU)), \
		"a background tcsetattr no longer stops — this harness proves nothing"


def test_a_terminal_that_termios_cannot_read_is_not_claimed_as_supported (
	monkeypatch: pytest.MonkeyPatch,
) -> None:

	"""The read is not only a leftover of the write: it is the check itself.

	`sys.stdin.isatty()` says a terminal is there; `tcgetattr` says it can
	actually be interrogated.  Without this, removing the read broke nothing
	at all and the line would have been dead weight.
	"""

	import termios

	import subsequence.keystroke

	class LooksLikeATerminal:
		def isatty (self) -> bool:
			return True
		def fileno (self) -> int:
			return 0

	def unreadable (fd: int) -> typing.Any:
		raise OSError("this terminal cannot be interrogated")

	monkeypatch.setattr(sys, "stdin", LooksLikeATerminal())
	monkeypatch.setattr(termios, "tcgetattr", unreadable)

	supported, reason = subsequence.keystroke._detect_hotkey_support()

	assert supported is False, "a terminal termios cannot read was claimed to support hotkeys"

	# Naming the termios failure is what makes this test non-vacuous: if the
	# isatty() patch had not taken, the reason would be the pipe one instead
	# and this would pass without the read having been reached at all.
	assert "cannot be interrogated" in str(reason), reason


def test_hotkey_support_is_still_detected () -> None:

	"""Reading instead of writing must not cost the capability check its answer."""

	# No TTY on stdin: unsupported, with a reason that says so.
	piped = subprocess.run(
		[
			sys.executable, "-c",
			"import subsequence.keystroke as k; print(k.HOTKEYS_SUPPORTED, k.HOTKEYS_UNAVAILABLE_REASON)",
		],
		stdin = subprocess.DEVNULL,
		capture_output = True,
		text = True,
		env = {**os.environ, "PYTHONPATH": REPO_ROOT, "PYTHONDONTWRITEBYTECODE": "1"},
		timeout = 60,
	)

	assert piped.returncode == 0, piped.stderr
	assert piped.stdout.startswith("False"), piped.stdout
	assert "TTY" in piped.stdout

	# A real TTY: supported.
	master, slave = pty.openpty()

	try:
		on_a_tty = subprocess.run(
			[sys.executable, "-c", "import subsequence.keystroke as k; print(k.HOTKEYS_SUPPORTED)"],
			stdin = slave,
			capture_output = True,
			text = True,
			env = {**os.environ, "PYTHONPATH": REPO_ROOT, "PYTHONDONTWRITEBYTECODE": "1"},
			timeout = 60,
		)
	finally:
		os.close(master)
		os.close(slave)

	assert on_a_tty.returncode == 0, on_a_tty.stderr
	assert on_a_tty.stdout.strip() == "True", on_a_tty.stdout
