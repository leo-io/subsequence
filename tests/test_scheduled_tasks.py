import asyncio
import logging
import pathlib
import threading
import time
import typing

import mido
import pytest

import subsequence
import subsequence.composition
import subsequence.sequencer


def test_sequencer_data_store_exists (patch_midi: None) -> None:

	"""Sequencer should have an empty data dict on creation."""

	seq = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", initial_bpm=120)

	assert isinstance(seq.data, dict)
	assert len(seq.data) == 0


@pytest.mark.asyncio
async def test_safe_callback_catches_exceptions (caplog: pytest.LogCaptureFixture) -> None:

	"""A failing safe callback should log a warning naming the task instead of raising."""

	def bad_fn () -> None:
		raise RuntimeError("boom")

	wrapped = subsequence.composition._make_safe_callback(bad_fn)

	# wrapper is sync, fires a background task.
	with caplog.at_level(logging.WARNING, logger="subsequence.composition"):
		wrapped(0)

		# Poll until the background task has run and logged (executor thread + event loop).
		for _ in range(200):
			if any("Scheduled task 'bad_fn' failed: boom" in r.message for r in caplog.records):
				break

			await asyncio.sleep(0.01)

	warnings = [r for r in caplog.records if r.levelno == logging.WARNING]

	assert any("Scheduled task 'bad_fn' failed: boom" in r.message for r in warnings)


@pytest.mark.asyncio
async def test_safe_callback_runs_sync_in_executor () -> None:

	"""Sync functions wrapped by _make_safe_callback should run in a thread pool."""

	thread_names: typing.List[str] = []

	def sync_fn () -> None:
		thread_names.append(threading.current_thread().name)

	wrapped = subsequence.composition._make_safe_callback(sync_fn)
	wrapped(0)

	# Yield control so the executor thread completes.
	await asyncio.sleep(0.05)

	assert len(thread_names) == 1
	# The main asyncio thread is typically "MainThread"; executor threads are not.
	assert thread_names[0] != "MainThread"


@pytest.mark.asyncio
async def test_safe_callback_runs_async_directly () -> None:

	"""Async functions wrapped by _make_safe_callback should run on the event loop."""

	thread_names: typing.List[str] = []

	async def async_fn () -> None:
		thread_names.append(threading.current_thread().name)

	wrapped = subsequence.composition._make_safe_callback(async_fn)
	wrapped(0)

	# Yield control so the background task runs.
	await asyncio.sleep(0)

	assert len(thread_names) == 1
	assert thread_names[0] == "MainThread"


@pytest.mark.asyncio
async def test_safe_callback_does_not_block () -> None:

	"""The wrapper should return immediately without blocking the caller."""

	completed = []

	def slow_fn () -> None:
		import time
		time.sleep(0.1)
		completed.append(True)

	wrapped = subsequence.composition._make_safe_callback(slow_fn)

	# Call and immediately check - should not have run yet.
	wrapped(0)
	assert len(completed) == 0

	# Now wait for it to finish in the background.
	await asyncio.sleep(0.2)
	assert len(completed) == 1


@pytest.mark.asyncio
async def test_schedule_task_registers_callback (patch_midi: None) -> None:

	"""schedule_task should register a callback on the sequencer."""

	seq = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", initial_bpm=120)

	def my_task () -> None:
		pass

	await subsequence.composition.schedule_task(sequencer=seq, fn=my_task, cycle_beats=8)

	assert len(seq.callback_queue) == 1


@pytest.mark.asyncio
async def test_schedule_task_defer_skips_pulse_zero (patch_midi: None) -> None:

	"""schedule_task(defer=True) should set start_pulse to one full cycle."""

	seq = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", initial_bpm=120)

	def my_task () -> None:
		pass

	await subsequence.composition.schedule_task(sequencer=seq, fn=my_task, cycle_beats=8, defer=True)

	assert len(seq.callback_queue) == 1

	# With defer, start_pulse = 8 beats * 24 ppq = 192.
	# Backshift subtracts lookahead: next_fire = 192 - (1 * 24) = 168.
	_, _, scheduled = seq.callback_queue[0]
	lookahead_pulses = int(1 * seq.pulses_per_beat)
	expected_fire = int(8 * seq.pulses_per_beat) - lookahead_pulses

	assert scheduled.next_fire_pulse == expected_fire


@pytest.mark.asyncio
async def test_schedule_task_no_defer_fires_at_zero (patch_midi: None) -> None:

	"""schedule_task without defer should backshift to fire at pulse 0."""

	seq = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", initial_bpm=120)

	def my_task () -> None:
		pass

	await subsequence.composition.schedule_task(sequencer=seq, fn=my_task, cycle_beats=8)

	_, _, scheduled = seq.callback_queue[0]

	# Without defer, backshift puts the first fire at pulse 0 (or close to it).
	# The next_fire_pulse should be less than one full cycle.
	one_cycle = int(8 * seq.pulses_per_beat)

	assert scheduled.next_fire_pulse < one_cycle


def test_initial_runs_before_first_pattern_build (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""End-to-end: schedule(wait_for_initial=True) completes before the first pattern build, so the data it writes is visible to patterns from bar 1."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=960)
	first_build_saw_sentinel: typing.List[bool] = []

	def populate () -> None:
		composition.data["sentinel"] = "ready"

	composition.schedule(populate, cycle_beats=4, wait_for_initial=True)

	@composition.pattern(channel=1, beats=4)
	def p (p: typing.Any) -> None:
		if not first_build_saw_sentinel:
			first_build_saw_sentinel.append(composition.data.get("sentinel") == "ready")

	composition.render(bars=1, filename=str(tmp_path / "initial.mid"))

	assert first_build_saw_sentinel, "the pattern never built"
	assert first_build_saw_sentinel[0] is True


def test_initial_runs_async_fn_before_patterns (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""wait_for_initial=True blocks on an ASYNC function through the real _run() path.

	The coroutine branch of _run()'s wait-for-initial block: the async
	populate must complete before the first pattern build reads the data.
	"""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=960)
	first_build_saw_sentinel: typing.List[bool] = []

	async def populate () -> None:
		composition.data["sentinel"] = "ready"

	composition.schedule(populate, cycle_beats=4, wait_for_initial=True)

	@composition.pattern(channel=1, beats=4)
	def p (p: typing.Any) -> None:
		if not first_build_saw_sentinel:
			first_build_saw_sentinel.append(composition.data.get("sentinel") == "ready")

	composition.render(bars=1, filename=str(tmp_path / "initial_async.mid"))

	assert first_build_saw_sentinel, "the pattern never built"
	assert first_build_saw_sentinel[0] is True


def test_initial_failure_does_not_raise (
	tmp_path: pathlib.Path,
	patch_midi: None,
	caplog: pytest.LogCaptureFixture,
) -> None:

	"""A failing wait_for_initial function must not crash play — _run() logs a warning.

	Exercises the real try/except in _run()'s wait-for-initial block: the
	run completes (the pattern still builds) and the failure is warned with
	the function's name.
	"""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=960)
	built: typing.List[bool] = []

	def bad_fn () -> None:
		raise RuntimeError("network error")

	composition.schedule(bad_fn, cycle_beats=4, wait_for_initial=True)

	@composition.pattern(channel=1, beats=4)
	def p (p: typing.Any) -> None:
		built.append(True)

	with caplog.at_level(logging.WARNING, logger="subsequence.composition"):
		composition.render(bars=1, filename=str(tmp_path / "initial_fail.mid"))

	assert built, "the failing initial fn must not stop patterns from building"
	assert any(
		"bad_fn" in record.getMessage() and "failed" in record.getMessage()
		for record in caplog.records
	)


# ---------------------------------------------------------------------------
# A render waits for what it schedules (#2793)
# ---------------------------------------------------------------------------

def _fed_render (tmp_path: pathlib.Path, run: int, feed_kind: str) -> typing.List[int]:

	"""Render twelve bars where a scheduled function sets each bar's pitch; return the pitches played."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=1)
	composition.data["step"] = 0

	if feed_kind == "plain":
		def feed (p: subsequence.composition.ScheduleContext) -> None:
			time.sleep(0.001)		# a reading that takes a moment, as a real one does
			composition.data["step"] = p.cycle
	else:
		async def feed (p: subsequence.composition.ScheduleContext) -> None:	# type: ignore[misc]
			composition.data["step"] = p.cycle

	composition.schedule(feed, cycle_beats=4, wait_for_initial=True)

	@composition.pattern(channel=1, beats=4)
	def lead (p: typing.Any) -> None:
		p.note(60 + composition.data["step"], beat=0, duration=1)

	path = str(tmp_path / f"fed-{feed_kind}-{run}.mid")
	composition.render(bars=12, filename=path)

	return [message.note for message in mido.MidiFile(path).tracks[0] if message.type == "note_on" and message.velocity > 0]


@pytest.mark.parametrize("feed_kind", ["plain", "async"])
def test_a_render_fed_by_a_scheduled_function_is_the_same_every_run (patch_midi: None, tmp_path: pathlib.Path, feed_kind: str) -> None:

	"""Each bar hears the reading taken for it, on every run, whether the function is plain or async."""

	expected = [60 + bar for bar in range(12)]

	for run in range(4):
		assert _fed_render(tmp_path, run, feed_kind) == expected


@pytest.mark.asyncio
async def test_the_wrapper_hands_its_run_to_the_clock_only_when_asked () -> None:

	"""With wait() True the call runs when awaited and not before; with it False the call is spawned."""

	calls: typing.List[str] = []
	waiting = [True]

	def fn () -> None:
		calls.append("ran")

	wrapped = subsequence.composition._make_safe_callback(fn, wait=lambda: waiting[0])

	handed = wrapped(0)
	assert handed is not None and calls == []

	await handed
	assert calls == ["ran"]

	waiting[0] = False
	assert wrapped(0) is None

	for _ in range(200):
		if len(calls) == 2:
			break
		await asyncio.sleep(0.01)

	assert calls == ["ran", "ran"]


@pytest.mark.asyncio
async def test_schedule_task_waits_in_a_render_and_spawns_live (patch_midi: None) -> None:

	"""The direct-API schedule_task reads the sequencer's render mode at each call."""

	seq = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", initial_bpm=120)
	calls: typing.List[int] = []

	def my_task () -> None:
		calls.append(1)

	await subsequence.composition.schedule_task(sequencer=seq, fn=my_task, cycle_beats=8)
	callback = seq.callback_queue[0][2].callback

	seq.render_mode = True
	handed = callback(0)
	assert handed is not None
	await handed
	assert calls == [1]

	seq.render_mode = False
	assert callback(0) is None
