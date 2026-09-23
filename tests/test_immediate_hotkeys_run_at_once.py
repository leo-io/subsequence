"""A quantize=0 hotkey runs when its key arrives, not at the next bar line (#3480).

hotkey() documents quantize=0 as "execute immediately", but only the bar event took keys, so an
immediate hotkey behaved as quantize=1: pressed on beat 2 of a bar at 120 BPM, its action ran
1.52 s later, on the bar line.  The listener now wakes the composition as keys arrive, and the
composition takes them on the clock's loop at once.  The bar event still takes any the wake-up
missed, and it is still where a quantised action waits for its bar.

The first two tests play a real piece at 30 BPM, a bar every 8 seconds, with stdin a
pseudo-terminal, and type the key once bar 0's own bar event has passed.
"""

import asyncio
import os
import sys
import termios
import threading
import time
import types
import typing
import unittest.mock

import pytest

import subsequence
import subsequence.composition
import subsequence.keystroke


async def _until (condition: typing.Callable[[], bool], within: float = 5.0) -> bool:

	"""Wait on the loop until *condition* holds or *within* seconds pass; say which."""

	deadline = time.monotonic() + within

	while not condition():
		if time.monotonic() >= deadline:
			return False
		await asyncio.sleep(0.005)

	return True


async def _press_a_key_in_bar_0 (monkeypatch: pytest.MonkeyPatch) -> typing.Tuple[int, typing.List[typing.Tuple[int, threading.Thread]]]:

	"""Play at 30 BPM, type an immediate hotkey early in bar 0, and return the pulse it was typed at and what its action saw."""

	master, slave = os.openpty()
	stdin = open(slave, "r", encoding="utf-8", closefd=False)

	monkeypatch.setattr(subsequence.keystroke, "HOTKEYS_SUPPORTED", True)
	monkeypatch.setattr(sys, "stdin", stdin)

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=30)
	composition.hotkeys()

	ran: typing.List[typing.Tuple[int, threading.Thread]] = []
	composition.hotkey("a", lambda: ran.append((composition._sequencer.pulse_count, threading.current_thread())))

	@composition.pattern(channel=1, beats=4)
	def keep_time (p: typing.Any) -> None:
		p.note(60, beat=0, velocity=1, duration=0.1)

	def ready () -> bool:
		listener = composition._keystroke_listener
		cbreak = not termios.tcgetattr(slave)[3] & termios.ICANON
		return composition._sequencer.pulse_count >= 3 and listener is not None and listener.active and cbreak

	playing = asyncio.create_task(composition._run())

	try:
		assert await _until(ready), "the piece never got past bar 0's own bar event with the listener in cbreak mode"
		pressed = composition._sequencer.pulse_count
		os.write(master, b"a")
		await _until(lambda: bool(ran), within=1.0)
	finally:
		await composition._sequencer.stop()
		await asyncio.wait_for(playing, timeout=5)
		stdin.close()
		os.close(slave)
		os.close(master)

	return pressed, ran


@pytest.mark.asyncio
async def test_an_immediate_hotkey_runs_when_its_key_arrives (monkeypatch: pytest.MonkeyPatch) -> None:

	"""Typed at pulse 3 or so, it runs within a second, where it waited for pulse 96 - eight seconds."""

	pressed, ran = await _press_a_key_in_bar_0(monkeypatch)

	assert ran, "the action had not run a second after its key was typed"
	assert pressed <= ran[0][0] < pressed + 12


@pytest.mark.asyncio
async def test_an_immediate_hotkey_runs_on_the_clocks_loop (monkeypatch: pytest.MonkeyPatch) -> None:

	"""The action runs on the loop's thread, where every mutation method is safe, never on the listener's."""

	_, ran = await _press_a_key_in_bar_0(monkeypatch)

	assert ran, "the action had not run a second after its key was typed"
	assert ran[0][1] is threading.current_thread()


def test_the_listener_announces_keys_once_they_are_queued (monkeypatch: pytest.MonkeyPatch) -> None:

	"""Each announcement finds its keys already waiting in drain()."""

	master, slave = os.openpty()
	stdin = open(slave, "r", encoding="utf-8", closefd=False)

	monkeypatch.setattr(subsequence.keystroke, "HOTKEYS_SUPPORTED", True)
	monkeypatch.setattr(sys, "stdin", stdin)

	seen: typing.List[typing.List[str]] = []
	listener = subsequence.keystroke.KeystrokeListener(on_key=lambda: seen.append(listener.drain()))

	try:
		listener.start()
		deadline = time.monotonic() + 2.0

		while termios.tcgetattr(slave)[3] & termios.ICANON:
			assert time.monotonic() < deadline, "the listener never put the terminal into cbreak mode"
			time.sleep(0.001)

		os.write(master, b"ab")
		deadline = time.monotonic() + 1.0

		while sum(len(keys) for keys in seen) < 2 and time.monotonic() < deadline:
			time.sleep(0.005)
	finally:
		listener.stop()
		stdin.close()
		os.close(slave)
		os.close(master)

	assert seen and all(seen), f"an announcement came before its keys were queued: {seen!r}"
	assert [key for keys in seen for key in keys] == ["a", "b"]


class TestTakingKeys:

	"""The loop's side, with the listener and the sequencer stood in for."""

	def setup_method (self) -> None:

		self.comp = subsequence.composition.Composition.__new__(subsequence.composition.Composition)
		self.comp._hotkeys_enabled = True
		self.comp._hotkey_bindings = {}
		self.comp._pending_hotkey_actions = []
		self.comp._form_state = None
		self.comp._sequencer = types.SimpleNamespace(running=True, _event_loop=None)

		self.listener = unittest.mock.MagicMock()
		self.listener.drain.return_value = []
		self.comp._keystroke_listener = self.listener

		self.called: typing.List[str] = []

	def _bind (self, key: str, quantize: int = 0) -> None:

		self.comp._hotkey_bindings[key] = subsequence.composition.HotkeyBinding(
			key=key, action=lambda: self.called.append(key), quantize=quantize, label=key
		)

	def test_a_quantised_hotkey_taken_as_it_arrives_still_waits_for_its_bar (self) -> None:

		"""quantize=4, typed in bar 1: taken at once, run on bar 4 and not before."""

		self._bind("q", quantize=4)
		self.listener.drain.return_value = ["q"]

		self.comp._take_typed_hotkeys()
		self.listener.drain.return_value = []

		assert self.called == []
		assert len(self.comp._pending_hotkey_actions) == 1

		self.comp._process_hotkeys(bar=3)
		assert self.called == []

		self.comp._process_hotkeys(bar=4)
		assert self.called == ["q"]

	def test_a_key_that_arrives_as_the_piece_stops_runs_nothing (self) -> None:

		"""With the sequencer stopped, an announced key's action does not run."""

		self._bind("a")
		self.listener.drain.return_value = ["a"]
		self.comp._sequencer.running = False

		self.comp._take_typed_hotkeys()

		assert self.called == []

	def test_a_key_typed_after_the_loop_has_closed_is_dropped_quietly (self) -> None:

		"""The piece is over: nothing is handed over, and nothing is raised on the listener's thread."""

		loop = asyncio.new_event_loop()
		loop.close()
		self.comp._sequencer._event_loop = loop

		self.comp._keys_arrived()

	def test_a_key_typed_before_the_clock_has_a_loop_is_taken_on_the_first_bar (self) -> None:

		"""Nowhere to hand it over yet, so it waits in the listener for bar 0.

		A guard: keys were only ever taken on the bar before #3480.
		"""

		self._bind("a")
		self.listener.drain.return_value = ["a"]

		self.comp._keys_arrived()
		assert self.called == []
		assert self.listener.drain.call_count == 0

		self.comp._process_hotkeys(bar=0)
		assert self.called == ["a"]
