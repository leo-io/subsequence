"""One broken section listener must not stop the music (#3034).

Sections are announced with `EventEmitter.emit_sync`, on the clock.  It used to
do neither of the things `emit_async` does:

- an `async def` listener raised `ValueError: Async callback encountered in
  emit_sync` at the **opening** section, so the piece failed before a note
  played — and nothing in `on_section`'s docstring said it had to be sync;
- a listener that raised took every listener after it down with it, and the
  exception skipped that bar's transition hook.  Measured: of three listeners
  the middle one raising, only `['first']` ran, where `emit_async` on the same
  three ran `['first', 'third']`.

An async callback is now refused where it is **written**, not at the first
section change, and a raising one is logged and stepped over.
"""

import asyncio
import pathlib
import typing
import unittest.mock

import pytest

import subsequence
import subsequence.event_emitter


# ---------------------------------------------------------------------------
# An async listener is refused at registration
# ---------------------------------------------------------------------------

def test_an_async_section_listener_is_refused_when_it_is_registered (patch_midi: None) -> None:

	"""At registration, where the author is — not at the first boundary, mid-performance."""

	composition = subsequence.Composition(bpm = 480)

	async def announce (info: typing.Any) -> None:
		pass

	with pytest.raises(ValueError) as refusal:
		composition.on_section(announce)

	assert "announce" in str(refusal.value), str(refusal.value)
	assert "async" in str(refusal.value)


def test_the_refusal_says_what_to_do_instead (patch_midi: None) -> None:

	"""A refusal a musician cannot act on is only half a fix."""

	composition = subsequence.Composition(bpm = 480)

	async def announce (info: typing.Any) -> None:
		pass

	with pytest.raises(ValueError) as refusal:
		composition.on_section(announce)

	assert "create_task" in str(refusal.value), str(refusal.value)


def test_the_same_refusal_comes_through_on_event (patch_midi: None) -> None:

	"""`on_section` is not the only door to the same event."""

	composition = subsequence.Composition(bpm = 480)

	async def announce (info: typing.Any) -> None:
		pass

	with pytest.raises(ValueError, match = "async"):
		composition.on_event("section", announce)


def test_an_async_listener_for_an_async_event_is_still_welcome (patch_midi: None) -> None:

	"""Only the events delivered from the clock are restricted."""

	composition = subsequence.Composition(bpm = 480)

	async def every_bar (bar: int) -> None:
		pass

	composition.on_event("bar", every_bar)		# must not raise

	assert "bar" not in subsequence.event_emitter.EventEmitter.SYNCHRONOUS_EVENTS
	assert "section" in subsequence.event_emitter.EventEmitter.SYNCHRONOUS_EVENTS


# ---------------------------------------------------------------------------
# A raising listener is stepped over
# ---------------------------------------------------------------------------

def test_a_raising_listener_does_not_silence_the_ones_after_it () -> None:

	"""The heart of it: `['first', 'third']`, where it used to be `['first']`."""

	emitter = subsequence.event_emitter.EventEmitter()
	ran = []

	emitter.on("section", lambda info: ran.append("first"))

	def broken (info: typing.Any) -> None:
		raise RuntimeError("this listener is broken")

	emitter.on("section", broken)
	emitter.on("section", lambda info: ran.append("third"))

	emitter.emit_sync("section", None)

	assert ran == ["first", "third"]


def test_a_raising_listener_is_logged_rather_than_swallowed () -> None:

	"""Continuing quietly would make "why did nothing happen?" unanswerable."""

	emitter = subsequence.event_emitter.EventEmitter()

	def broken (info: typing.Any) -> None:
		raise RuntimeError("this listener is broken")

	emitter.on("section", broken)

	with unittest.mock.patch.object(subsequence.event_emitter.logger, "exception") as logged:
		emitter.emit_sync("section", None)

	assert logged.called, "a listener failed and nothing was said about it"


def test_emit_sync_and_emit_async_treat_a_broken_listener_the_same () -> None:

	"""The two halves of one promise; they disagreed, and that was the bug."""

	def build () -> typing.Tuple[subsequence.event_emitter.EventEmitter, typing.List[str]]:
		emitter = subsequence.event_emitter.EventEmitter()
		ran: typing.List[str] = []

		emitter.on("x", lambda: ran.append("first"))

		def broken () -> None:
			raise RuntimeError("broken")

		emitter.on("x", broken)
		emitter.on("x", lambda: ran.append("third"))

		return emitter, ran

	sync_emitter, ran_sync = build()
	sync_emitter.emit_sync("x")

	async_emitter, ran_async = build()
	asyncio.run(async_emitter.emit_async("x"))

	assert ran_sync == ran_async == ["first", "third"]


def test_an_async_callable_object_is_stepped_over_rather_than_raising () -> None:

	"""`iscoroutinefunction` misses an async `__call__`, so registration cannot catch it."""

	class Announcer:
		async def __call__ (self, info: typing.Any) -> None:
			pass

	emitter = subsequence.event_emitter.EventEmitter()
	ran = []

	emitter.on("section", Announcer())
	emitter.on("section", lambda info: ran.append("after"))

	with unittest.mock.patch.object(subsequence.event_emitter.logger, "error") as logged:
		emitter.emit_sync("section", None)

	assert ran == ["after"], "an un-awaitable listener stopped the ones after it"
	assert logged.called, "it did not run and nothing was said about it"


# ---------------------------------------------------------------------------
# The musician-visible consequence
# ---------------------------------------------------------------------------

def test_a_piece_still_plays_through_a_broken_section_listener (
	tmp_path: pathlib.Path,
	patch_midi: None,
) -> None:

	"""What the finding is actually about: the music does not stop."""

	filename = str(tmp_path / "out.mid")
	composition = subsequence.Composition(bpm = 480)
	composition.form([("verse", 1), ("chorus", 1)])

	seen = []

	def broken (info: typing.Any) -> None:
		raise RuntimeError("this listener is broken")

	composition.on_section(broken)
	composition.on_section(lambda info: seen.append(info))

	@composition.pattern(channel = 1, beats = 4)
	def drums (p: typing.Any) -> None:
		p.note(beat = 0, pitch = 36, velocity = 100)

	composition.render(bars = 4, filename = filename)

	assert pathlib.Path(filename).exists()
	assert seen, "the listener after the broken one never saw a section"
