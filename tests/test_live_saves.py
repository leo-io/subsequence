"""What a save to a watched file does to a playing composition.

Driven through `_reload_async` directly, as `tests/test_live_reloader.py` does, so each save
lands exactly when the test says.
"""

import asyncio
import os
import pathlib
import signal
import sys
import threading
import time
import typing

import pytest

import subsequence


def _part (name: str) -> str:

	"""One part, as a watched file declares it."""

	return f"@composition.pattern(channel=1, beats=4)\ndef {name} (p):\n\tpass\n\n"


async def _watching (tmp_path: pathlib.Path, source: str) -> typing.Tuple[subsequence.Composition, pathlib.Path]:

	"""A composition watching a file that holds `source`, its parts already playing."""

	live_file = tmp_path / "parts.py"
	live_file.write_text(source)

	composition = subsequence.Composition(bpm=120, output_device="Dummy MIDI")
	composition._sequencer._event_loop = asyncio.get_running_loop()
	composition.watch(live_file)

	# What _run() does with the parts the first load declared.
	await composition._activate_new_pending_patterns()

	# From here on a save lands only when the test says: the polling thread would
	# otherwise notice each rewrite too, and apply it a second time.
	assert composition._live_reloader is not None
	composition._live_reloader.stop()

	return composition, live_file


@pytest.mark.skipif(sys.platform == "win32", reason="sends a signal to its own process")
@pytest.mark.asyncio
@pytest.mark.parametrize("number", [signal.SIGINT, signal.SIGTERM], ids=["SIGINT", "SIGTERM"])
async def test_a_stopping_signal_stops_a_save_that_holds_the_loop (patch_midi: None, tmp_path: pathlib.Path, number: signal.Signals) -> None:

	"""A save whose top level never finished held the music, and the signal waited for it (#3378).

	The performance's handler is installed as `run_until_stopped` installs it, so its callback
	runs on the loop the save was holding: it must still hear the signal, once, after the save
	has been stopped.
	"""

	loop = asyncio.get_running_loop()
	heard: typing.List[float] = []
	loop.add_signal_handler(number, lambda: heard.append(time.monotonic()))
	composition, live_file = await _watching(tmp_path, _part("drums"))
	timer = threading.Timer(0.3, os.kill, (os.getpid(), number))

	try:
		# Bounded, so a tree without the guard finishes late instead of hanging.
		live_file.write_text(_part("drums") + "import time\nuntil = time.monotonic() + 6\nwhile time.monotonic() < until: pass\n")

		started = time.monotonic()
		timer.start()

		try:
			await composition._live_reloader._reload_async()
			escaped: typing.Optional[BaseException] = None
		except BaseException as error:
			escaped = error

		took = time.monotonic() - started
		await asyncio.sleep(0.1)

		# A stopped save is the performance ending, not the file's error, and
		# must not escape the watcher's coroutine.
		assert escaped is None
		assert took < 3.0
		assert len(heard) == 1

	finally:
		timer.cancel()
		loop.remove_signal_handler(number)
		composition._live_reloader.stop()
