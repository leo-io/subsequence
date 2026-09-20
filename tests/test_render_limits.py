"""A render's limits are checked where they are written (#3037).

Two things, both from M21 of the 2026-09-19 review.

**A bar count of zero or less meant "no limit".**  `render()` stores
`bars if bars is not None else 0`, and the engine reads `0` as its own "no bar
limit" sentinel — so `render(bars=0, max_minutes=None)` ran for ever, filling
memory with recorded events while it did.  Measured: `bars=0` and `bars=-4`
were both still running when killed at 12 s, where `bars=2` returned in 0.00 s.

**A render could not run off the main thread.**  Only `NotImplementedError`
was caught around `loop.add_signal_handler` (for Windows).  Off the main thread
the failure is a `RuntimeError` — "set_wakeup_fd only works in main thread of
the main interpreter" — so a batch script rendering several pieces on worker
threads failed on every one of them.  Ctrl+C is a convenience; the render is
the point.
"""

import pathlib
import threading
import typing

import pytest

import subsequence


def _piece (bpm: int = 480) -> subsequence.Composition:

	composition = subsequence.Composition(bpm = bpm)

	@composition.pattern(channel = 1, beats = 4)
	def drums (p: typing.Any) -> None:
		p.note(beat = 0, pitch = 36, velocity = 100)

	return composition


def _render_expecting_a_refusal (
	composition: subsequence.Composition,
	**kwargs: typing.Any,
) -> BaseException:

	"""Call `render()` on a worker thread and insist it comes back.

	The limit being tested is the one that stops an endless render, so a
	regression here does not fail — it runs for ever.  Called directly, these
	tests would hang the suite instead of reporting, and a hang in CI is read
	as an infrastructure problem rather than a bug.  The deadline turns that
	into a sentence somebody can act on.
	"""

	outcome: typing.List[typing.Any] = []

	def go () -> None:
		try:
			composition.render(**kwargs)
			outcome.append(None)
		except BaseException as e:				# noqa: BLE001 - reporting it is the point
			outcome.append(e)

	worker = threading.Thread(target = go, daemon = True)
	worker.start()
	worker.join(timeout = 20.0)

	if worker.is_alive():
		pytest.fail(
			f"render({kwargs}) neither returned nor refused within 20s — "
			f"it is rendering with no limit at all"
		)

	raised = outcome[0]

	assert raised is not None, f"render({kwargs}) returned instead of refusing"

	return typing.cast(BaseException, raised)


# ---------------------------------------------------------------------------
# A bar count is a number of bars
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bars", [0, -1, -4])
def test_a_bar_count_of_zero_or_less_is_refused (
	bars: int,
	tmp_path: pathlib.Path,
	patch_midi: None,
) -> None:

	"""It used to mean "for ever", which is the one thing nobody asks for by writing 0."""

	refusal = _render_expecting_a_refusal(
		_piece(),
		bars = bars,
		max_minutes = None,
		filename = str(tmp_path / "out.mid"),
	)

	assert isinstance(refusal, ValueError), repr(refusal)
	assert str(bars) in str(refusal), str(refusal)


def test_the_refusal_points_at_the_way_to_ask_for_no_bar_limit (
	tmp_path: pathlib.Path,
	patch_midi: None,
) -> None:

	"""Somebody writing bars=0 wants something; say what it is called."""

	refusal = _render_expecting_a_refusal(
		_piece(),
		bars = 0,
		max_minutes = None,
		filename = str(tmp_path / "out.mid"),
	)

	assert "max_minutes" in str(refusal), str(refusal)


@pytest.mark.parametrize("bars", [1.5, "4", True])
def test_a_bar_count_that_is_not_a_whole_number_is_refused (
	bars: typing.Any,
	tmp_path: pathlib.Path,
	patch_midi: None,
) -> None:

	"""Bars are counted, so a float, a string or a bool is a mistake, not a rounding."""

	composition = _piece()

	with pytest.raises(ValueError):
		composition.render(bars = bars, max_minutes = None, filename = str(tmp_path / "out.mid"))


@pytest.mark.parametrize("max_minutes", [0, -1.0])
def test_a_time_cap_of_zero_or_less_is_refused (
	max_minutes: float,
	tmp_path: pathlib.Path,
	patch_midi: None,
) -> None:

	"""`max_minutes=0` silently rendered nothing at all; say so instead."""

	composition = _piece()

	with pytest.raises(ValueError) as refusal:
		composition.render(bars = None, max_minutes = max_minutes, filename = str(tmp_path / "out.mid"))

	assert "max_minutes" in str(refusal.value)


def test_an_ordinary_bar_count_still_renders (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""The control.  A guard that refuses everything would pass every test above."""

	filename = str(tmp_path / "out.mid")

	_piece().render(bars = 2, max_minutes = None, filename = filename)

	assert pathlib.Path(filename).exists()
	assert pathlib.Path(filename).stat().st_size > 0


def test_a_time_cap_alone_still_renders (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""The other control: no bars at all is still a legitimate way to ask."""

	filename = str(tmp_path / "out.mid")

	_piece().render(bars = None, max_minutes = 0.01, filename = filename)

	assert pathlib.Path(filename).exists()


# ---------------------------------------------------------------------------
# Off the main thread
# ---------------------------------------------------------------------------

def test_a_render_runs_on_a_worker_thread (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""A batch script that renders several pieces at once used to fail on all of them."""

	filename = str(tmp_path / "out.mid")
	composition = _piece()
	outcome: typing.List[typing.Any] = []

	def render_it () -> None:
		try:
			composition.render(bars = 2, filename = filename)
			outcome.append("rendered")
		except BaseException as e:				# noqa: BLE001 - the point is what it was
			outcome.append(e)

	worker = threading.Thread(target = render_it)
	worker.start()
	worker.join(timeout = 60.0)

	assert not worker.is_alive(), "the render never finished on the worker thread"
	assert outcome, "the probe observed nothing at all"
	assert outcome == ["rendered"], f"the render failed off the main thread: {outcome[0]!r}"
	assert pathlib.Path(filename).exists()


def test_a_render_on_the_main_thread_still_installs_its_handler (
	tmp_path: pathlib.Path,
	patch_midi: None,
) -> None:

	"""Catching the failure must not become "never try": Ctrl+C still stops a piece.

	The signal handler is installed on the running loop, so the honest check is
	that the loop was asked — not that a handler object exists afterwards, since
	the loop is closed by the time the render returns.
	"""

	import asyncio

	asked: typing.List[int] = []
	original = asyncio.unix_events._UnixSelectorEventLoop.add_signal_handler	# type: ignore[attr-defined]

	def recording (self: typing.Any, sig: int, callback: typing.Any, *args: typing.Any) -> None:
		asked.append(sig)
		return original(self, sig, callback, *args)

	asyncio.unix_events._UnixSelectorEventLoop.add_signal_handler = recording	# type: ignore[attr-defined,method-assign]

	try:
		_piece().render(bars = 2, filename = str(tmp_path / "out.mid"))
	finally:
		asyncio.unix_events._UnixSelectorEventLoop.add_signal_handler = original	# type: ignore[attr-defined,method-assign]

	import signal as signal_module

	assert int(signal_module.SIGINT) in asked, \
		"the render no longer asks for a Ctrl+C handler at all"
