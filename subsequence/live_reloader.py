"""Watch a Python file and re-exec it on save into a live composition.

Provides ``LiveReloader``, the engine behind ``Composition.watch(path)``.
Together they enable file-based live coding: edit a Python file in your
normal editor, save, and the running composition picks up the changes
without stopping the clock.

How it works
────────────

``Composition.watch(path)`` constructs a ``LiveReloader`` and calls
``start()``.

``start()`` performs an initial synchronous load: it reads, compiles and
execs the file itself, into a namespace that has ``composition`` and
``subsequence`` in scope - not through ``Composition.load_patterns()``,
which waits on the event loop and would deadlock if ``watch()`` were called
from it.  This is the first chance for ``@composition.pattern`` decorators
in the file to register with the composition.  If the initial load fails
(``SyntaxError``, missing file), the exception propagates - the user should
know immediately if their entry point is broken.

A daemon thread is then spawned that looks at the file's modification time
and size every ``poll_interval`` seconds.  A change is applied only once
the file has held still for a whole poll, so a save caught half-written is
never taken for the new version (#3375).  The thread then schedules
``_reload_async()`` onto the composition's event loop via
``asyncio.run_coroutine_threadsafe()``, so mutation happens on the event
loop thread (where the rest of the sequencer lives).

``_reload_async()`` reads + compiles the file content, then delegates to
``Composition._apply_source_async()`` for exec, pattern activation, and
diff-and-unregister against the running set.  Errors from any phase are
logged but do not abort the watcher.

Existing patterns hot-swap in place via the decorator path: when the
same function name is re-decorated while ``_is_live=True``,
``Composition._redeclare`` replaces the running pattern's
``_builder_fn`` and applies each decorator argument that differs from
its last declaration, all heard from the next rebuild.  The cycle
counter, stream, mutes and tweaks carry on.  A changed device is the
exception, applied when the composition restarts, because opening a
port while the clock runs would be heard.

Error handling
──────────────

``SyntaxError`` during a reload - log a warning and skip the reload
entirely.  Previous state is preserved.  The user fixes the file and
saves again, and that save is picked up as any other.

Runtime error during ``exec()`` (e.g. ``NameError``, ``ImportError``) -
treated the same way: log a warning and skip the rest of the reload.
``Composition._apply_source_async`` re-raises exec failures specifically
so this catch can suppress the diff-and-unregister phase, which would
otherwise tear down patterns the broken file failed to reach.  Note
that decorators that already side-effect'd before the error fired
cannot be rolled back - those builders will run their new bodies on
the next reschedule.

File missing or unreadable - wait, and try again at the next poll: a read
that fails forgets what was applied, so the watcher looks again rather than
waiting for the next save.  Editor "atomic save" (write-temp-then-rename)
is handled by catching ``OSError`` around the stat and the read.  A file
that changes while it is being read is left for the watcher to settle on
again, rather than applied half-read.

Module-level state in the watched file
──────────────────────────────────────

Each reload uses a fresh namespace dict holding only ``composition`` and
``subsequence``.  Module-level objects in the watched file (e.g.
``state = MelodicState(...)``) are recreated on every reload, and names
defined in the wrapper script (the file that calls ``composition.watch()``)
are not visible.  Long-lived state belongs on ``composition.data``: create
it once in the wrapper, before ``watch()``, and read it back from
``composition.data`` in the live file.

Security note
─────────────

This module calls ``exec()`` on arbitrary Python by design.  Treat the watched
file like any other source file in your project; never point it at
untrusted content.
"""

import asyncio
import logging
import os
import pathlib
import threading
import traceback
import typing

import subsequence.live_server


if typing.TYPE_CHECKING:
	import subsequence.composition


logger = logging.getLogger(__name__)


class LiveReloader:

	"""Watch a Python file and re-exec it on save into a live composition.

	Constructed by ``Composition.watch(path)``; users do not instantiate
	this class directly.  Owns a daemon thread that polls the file's
	modification time and a reference back to the composition for
	scheduling reloads onto its event loop.
	"""

	def __init__ (
		self,
		composition: "subsequence.composition.Composition",
		path: typing.Union[str, pathlib.Path],
		poll_interval: float = 0.25,
		skip_initial_exec: bool = False,
	) -> None:

		"""Initialise the reloader in a stopped state.

		Parameters:
			composition: The live ``Composition`` instance to reload into.
			path: Path to the Python file to watch.
			poll_interval: Seconds between looks at the file.  A save is
				applied once it has held still for one of them, so it is
				heard up to two polls after it lands.  Default 0.25 s.
			skip_initial_exec: When ``True``, ``start()`` skips the
				compile + exec phase of the initial load and only records
				what the file is now.  Set by ``Composition.watch()`` when it
				detects a self-watch (the file calling ``watch()`` is the
				file being watched), since the outer Python script execution
				will already run the patterns at the module level - a second
				exec via ``_load_initial`` would double-register every one.
		"""

		self._composition = composition
		self._path: pathlib.Path = pathlib.Path(path)
		self._poll_interval = poll_interval
		self._skip_initial_exec = skip_initial_exec

		# The file's (mtime, size) when it was last applied, and a change seen
		# at the previous poll that has not held still long enough to apply
		# yet.  A save caught half-written used to be applied at first sight,
		# restarting every part it had not reached (#3375).
		self._applied: typing.Optional[typing.Tuple[int, int]] = None
		self._settling: typing.Optional[typing.Tuple[int, int]] = None

		# Daemon thread state — created on start().
		self._thread: typing.Optional[threading.Thread] = None
		self._stop_event = threading.Event()

	def start (self) -> None:

		"""Perform the initial synchronous load, then spawn the watcher thread.

		Raises :exc:`SyntaxError` or :exc:`FileNotFoundError` if the file
		cannot be loaded - better to fail loudly here than to leave the
		user wondering why no patterns are running.

		Safe to call once.  A second call while the watcher is already
		running is a no-op.
		"""

		if self._thread is not None and self._thread.is_alive():
			logger.debug(f"LiveReloader.start() no-op: already watching {self._path}")
			return

		# Initial load — synchronous, on the calling thread.  Raises on failure.
		self._load_initial()

		self._stop_event.clear()
		self._thread = threading.Thread(
			target = self._watch_loop,
			name = f"subsequence-live-reloader-{self._path.name}",
			daemon = True,
		)
		self._thread.start()
		logger.info(f"LiveReloader watching {self._path} (poll {self._poll_interval}s)")

	def stop (self) -> None:

		"""Signal the watcher thread to exit; safe to call multiple times.

		Joins the thread with a short timeout so shutdown is bounded.
		"""

		self._stop_event.set()

		if self._thread is not None and self._thread.is_alive():
			self._thread.join(timeout = self._poll_interval * 2 + 0.5)

		self._thread = None

	def claim_what_the_script_declared (self) -> None:

		"""For a file that watches itself, record what the script's own run declared as this file's (#3376).

		Python's run of the script is what declares its parts, so ``start()``
		skipped the exec that would have recorded them, and the first save had
		nothing to diff against: a part it deleted played on.  ``play()`` calls
		this as it starts, before anything typed can run.  In the single-file
		layout the whole script is the file, so every name declared by then is
		the file's own - less any another source already owns, such as a
		``load_patterns()`` label.
		"""

		if not self._skip_initial_exec:
			return

		key = str(self._path)
		declared = self._composition._source_declared

		if key in declared:
			return

		owned: typing.Set[str] = set().union(*declared.values())
		declared[key] = set(self._composition._declared_names) - owned

	# ── Internals ──────────────────────────────────────────────────────────

	def _load_initial (self) -> None:

		"""Synchronous first load; raises on failure.

		Reads, compiles and execs the file on the calling thread.  Doesn't
		go through ``Composition.load_patterns()`` because that method
		schedules onto the event loop when one is running and waits via
		``future.result()`` - which would deadlock if ``watch()`` happens
		to be called from inside the event loop (e.g. in tests).  The
		``_load_initial`` contract is pre-play setup, so direct exec is
		correct here: decorators populate ``_pending_patterns`` and the
		composition's ``play()`` graduates them.

		When ``self._skip_initial_exec`` is ``True`` (single-file self-watch),
		the compile+exec step is skipped - the outer Python script will run
		the decorators itself.  We still record the file's (mtime, size) so
		the watcher loop doesn't immediately re-trigger on the first poll.
		"""

		if not self._skip_initial_exec:

			content = self._path.read_text(encoding = "utf-8")
			compiled = compile(content, str(self._path), "exec")

			namespace = self._composition._build_live_namespace(source_label = str(self._path))

			# Mirror _apply_source_async's bookkeeping so the FIRST save can
			# already diff against what this file declares now — recording
			# only this file's names, not the wrapper script's.
			self._composition._declared_names = set()
			before = self._composition._pending_snapshot()

			try:
				exec(compiled, namespace)
			except BaseException:
				# The error still reaches the caller; the parts the file reached
				# before it do not wait for play() to start them (#3377).
				self._composition._roll_back_pending(before)
				raise

			self._composition._source_declared[str(self._path)] = set(self._composition._declared_names)

		self._applied = self._signature()

	def _signature (self) -> typing.Optional[typing.Tuple[int, int]]:

		"""The file's modification time and size, which change whenever a save does, or None if it cannot be seen."""

		try:
			stat = os.stat(self._path)
		except OSError:
			return None

		return (stat.st_mtime_ns, stat.st_size)

	def _due (self) -> typing.Optional[typing.Tuple[int, int]]:

		"""One poll: the file's (mtime, size) if a change has now held still for a whole poll, else None.

		A save is seen as it is written - truncated, then filled - so a change
		is applied only once a second poll finds it just as the first did.  Any
		difference at all counts as a change, older included: a
		timestamp-preserving replacement (``mv backup.py watched.py``) can
		legitimately go back in time.
		"""

		seen = self._signature()

		# Missing or unreadable, as in an editor's rename: wait it out.
		if seen is None:
			return None

		if seen == self._applied:
			self._settling = None
			return None

		# New, or still moving: give it one more poll.
		if seen != self._settling:
			self._settling = seen
			return None

		return seen

	def _poll (self) -> None:

		"""One look at the file: once a change has held still for a whole poll, schedule its reload.

		The reload is handed the (mtime, size) the watcher settled on, so it can
		tell whether the file moved again while it was being read.
		"""

		due = self._due()

		if due is None:
			return

		loop = self._composition._sequencer._event_loop

		if loop is None:
			# Event loop isn't running yet (watch() called before play(), or
			# play() not called).  Nothing is applied, so the next poll finds the
			# same settled change and tries again.
			logger.debug("LiveReloader: no event loop yet, deferring reload")
			return

		self._applied = due
		self._settling = None
		asyncio.run_coroutine_threadsafe(self._reload_async(due), loop = loop)

	def _watch_loop (self) -> None:

		"""Polling loop running in the daemon thread: :meth:`_poll` every ``poll_interval`` seconds."""

		while not self._stop_event.is_set():

			self._poll()

			# Use the stop event's wait() so shutdown is instantaneous instead
			# of having to wait out the full poll interval.
			self._stop_event.wait(self._poll_interval)

	async def _reload_async (self, expected: typing.Optional[typing.Tuple[int, int]] = None) -> None:

		"""Read, compile, apply - runs on the event loop thread.

		Delegates the exec + activate + diff-and-unregister phases to
		``Composition._apply_source_async``.  We do the compile step here
		(rather than via ``Composition.load_patterns``) so SyntaxError can
		be reported with a watcher-specific log message, and so the apply
		coroutine runs directly on the loop without re-scheduling through
		``run_coroutine_threadsafe``.

		Errors are logged but do not abort the watcher.

		``expected`` is the file's (mtime, size) the watcher settled on.  If
		the file no longer matches it once read, it changed during the read:
		what was read is dropped, and the watcher settles on it again.
		"""

		try:
			content = self._path.read_text(encoding = "utf-8")
		except OSError as exc:
			logger.warning(f"LiveReloader: could not read {self._path}: {exc}")
			# Forget what was applied, so the next poll tries again (#3375).
			self._applied = None
			return

		if expected is not None and self._signature() != expected:
			logger.debug(f"LiveReloader: {self._path} changed while it was read; waiting for it to settle")
			self._applied = None
			return

		# Syntax check — bail early without touching state.
		try:
			compiled = compile(content, str(self._path), "exec")
		except SyntaxError:
			logger.warning(f"LiveReloader: SyntaxError in {self._path}, skipping reload:\n{traceback.format_exc()}")
			return

		namespace = self._composition._build_live_namespace(source_label = str(self._path))

		try:
			await self._composition._apply_source_async(compiled, namespace, source_key = str(self._path))
		except subsequence.live_server.Interrupted:
			# Ctrl+C or SIGTERM stopped a save that held the loop; the signal has
			# gone on to end the performance, which is not this save's failure.
			logger.warning(f"LiveReloader: {self._path} was stopped while it ran, and the performance is stopping")
			return
		except Exception:
			# Apply re-raises on exec failure; suppress here so the watcher
			# keeps running.  The diff-and-unregister phase inside
			# _apply_source_async is skipped automatically when exec raises,
			# so previous state is preserved.
			logger.warning(f"LiveReloader: error executing {self._path}, skipping reload:\n{traceback.format_exc()}")
			return
