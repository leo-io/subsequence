"""The event loop the clock runs on, and the runner that builds it (#2533).

CPython's epoll selector rounds a timeout up to whole milliseconds twice, so a
sleep that rounds to 13 or 18 ms oversleeps by a further millisecond — more than
the clock's 1 ms spin margin absorbs.  These tests pin the choice of loop and the
runner's ``asyncio.run`` behaviour, not wall-clock timing, which a CI runner
cannot measure to a millisecond.
"""

import asyncio
import pathlib
import selectors
import sys
import types
import typing

import pytest

import subsequence
import subsequence.sequencer


EPOLL_DEFAULT = getattr(selectors, "EpollSelector", None) is not None and selectors.DefaultSelector is getattr(selectors, "EpollSelector", None)


def _selector_of (loop: asyncio.AbstractEventLoop) -> typing.Any:

	"""The selector a selector-based loop waits in."""

	return getattr(loop, "_selector")


@pytest.mark.skipif(not EPOLL_DEFAULT, reason="only where the default selector is epoll")
def test_where_epoll_is_the_default_the_clock_loop_waits_in_select () -> None:

	"""The loop the clock runs on must not wait in epoll, whose timeout rounding oversleeps."""

	loop = subsequence.sequencer.new_event_loop()

	try:
		assert isinstance(_selector_of(loop), selectors.SelectSelector)
	finally:
		loop.close()


def test_where_epoll_is_not_the_default_the_platform_loop_is_kept (monkeypatch: pytest.MonkeyPatch) -> None:

	"""Only epoll is replaced: another platform's default selector is left alone."""

	monkeypatch.setattr(selectors, "DefaultSelector", selectors.PollSelector)

	loop = subsequence.sequencer.new_event_loop()

	try:
		assert isinstance(_selector_of(loop), selectors.PollSelector)
	finally:
		loop.close()


@pytest.mark.skipif(not EPOLL_DEFAULT, reason="only where the default selector is epoll")
@pytest.mark.parametrize("entry", ["play", "render"])
def test_a_composition_starts_on_the_clock_loop (patch_midi: None, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, entry: str) -> None:

	"""``play()`` and ``render()`` both run the composition on the loop that keeps the clock on time."""

	seen: typing.List[typing.Any] = []

	async def _capture_loop (self: subsequence.Composition) -> None:
		seen.append(_selector_of(asyncio.get_running_loop()))

	monkeypatch.setattr(subsequence.Composition, "_run", _capture_loop)

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	if entry == "play":
		composition.play()
	else:
		composition.render(bars=1, filename=str(tmp_path / "unused.mid"))

	assert len(seen) == 1
	assert isinstance(seen[0], selectors.SelectSelector)


RUNNER_PATHS = ["asyncio.Runner", "python 3.10 steps"]


@pytest.fixture(params=RUNNER_PATHS)
def runner_path (request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:

	"""Run each runner test down both branches, where the interpreter has both."""

	if request.param == "asyncio.Runner" and sys.version_info < (3, 11):
		pytest.skip("asyncio.Runner needs Python 3.11")

	if request.param == "python 3.10 steps":
		monkeypatch.setattr(subsequence.sequencer, "sys", types.SimpleNamespace(version_info=(3, 10, 0)))

	return typing.cast(str, request.param)


def test_run_returns_what_its_coroutine_returns (runner_path: str) -> None:

	"""``run`` hands back the coroutine's result, as ``asyncio.run`` does."""

	async def _answer () -> int:
		await asyncio.sleep(0)
		return 42

	assert subsequence.sequencer.run(_answer()) == 42


def test_run_raises_what_its_coroutine_raises (runner_path: str) -> None:

	"""An exception inside the coroutine reaches the caller unchanged."""

	async def _fail () -> None:
		raise LookupError("from inside the loop")

	with pytest.raises(LookupError, match="from inside the loop"):
		subsequence.sequencer.run(_fail())


def test_run_cancels_what_is_left_and_closes_its_loop (runner_path: str) -> None:

	"""A task still running when the coroutine returns is cancelled, and the loop is closed after."""

	state: typing.Dict[str, typing.Any] = {}

	async def _leave_a_task_behind () -> None:

		async def _forever () -> None:
			try:
				await asyncio.sleep(3600)
			except asyncio.CancelledError:
				state["cancelled"] = True
				raise

		state["task"] = asyncio.get_running_loop().create_task(_forever())
		state["loop"] = asyncio.get_running_loop()
		await asyncio.sleep(0)

	subsequence.sequencer.run(_leave_a_task_behind())

	assert state.get("cancelled") is True
	assert state["task"].cancelled()
	assert state["loop"].is_closed()
