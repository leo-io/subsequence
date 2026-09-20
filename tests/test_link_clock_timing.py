"""Ableton Link plays at the session's tempo, starting on the bar (#2993).

`aalink.Link.sync(n)` resumes at the next **multiple** of *n* — aalink's own
documentation gives `sync(2)` at beat 11.5 resuming at 12 — and the loop passed
it an absolute beat, `beat_origin + pulse / 24`.  So every pulse waited for a
multiple of itself: pulse 0 waited for two bars, and every pulse after it landed
on a lattice twice as coarse as intended.

Measured against a stand-in with aalink's semantics: the old loop started at
beat 8.0 where the bar line was 4.0, and 47 pulses spanned 3.9167 beats where
1.9583 was due — a tempo ratio of exactly **0.500**, while the display went on
showing the right BPM.

**Ableton Link is never enabled by these tests.**  They drive a stand-in whose
`sync()` has aalink's next-multiple semantics; no session is joined and nothing
touches the network.
"""

import asyncio
import math
import typing
import unittest.mock

import pytest

import subsequence
import subsequence.sequencer


PPQ = 24


class FakeLinkSession:

	"""A Link session with aalink's own timing semantics and no network.

	`sync(period)` resumes at the next multiple of *period* strictly after the
	current beat, and returns the beat it resumed at.
	"""

	def __init__ (self, tempo: float = 120.0, quantum: float = 4.0, start: float = 0.0) -> None:
		self.tempo = tempo
		self.quantum = quantum
		self.num_peers = 0
		self.beat = start
		self.asked_for: typing.List[float] = []

	def _next_multiple (self, period: float) -> float:
		# The epsilon matters: floor(4.0416666 / 0.0416666) is 96, not 97, so
		# without it the session never advances and every assertion over it
		# passes for nothing.
		return (math.floor(self.beat / period + 1e-9) + 1) * period

	async def wait_for_bar (self) -> float:
		self.beat = self._next_multiple(self.quantum)
		return self.beat

	async def sync (self, period: float) -> float:
		self.asked_for.append(period)
		self.beat = self._next_multiple(period)
		return self.beat

	def stall (self, beats: float) -> None:
		"""Pretend the loop was away for *beats* of session time."""
		self.beat += beats


async def _play (
	session: FakeLinkSession,
	pulses: int,
	on_pulse: typing.Optional[typing.Callable[[int], None]] = None,
) -> typing.List[float]:

	"""Run the Link loop for *pulses* pulses; report the session beat at each."""

	sequencer = subsequence.sequencer.Sequencer(output_device_name = "Dummy MIDI", initial_bpm = 120)
	sequencer._event_loop = asyncio.get_running_loop()
	sequencer.running = True

	# Without something sounding, the loop's exhaustion check stops it at once.
	sequencer.active_notes.add((0, 0, 60))

	heard: typing.List[float] = []

	async def counted () -> None:
		heard.append(session.beat)
		sequencer.pulse_count += 1

		if on_pulse is not None:
			on_pulse(len(heard))

		if len(heard) >= pulses:
			sequencer.running = False

	sequencer._advance_pulse = counted		# type: ignore[method-assign]

	await sequencer._run_loop_link_clock(session, pulses_per_bar = 96)

	return heard


# ---------------------------------------------------------------------------
# The stand-in itself
# ---------------------------------------------------------------------------

def test_the_stand_in_actually_advances () -> None:

	"""A fake that stands still makes every test over it vacuously true.

	This is not hypothetical: the first version of it lost to floating point
	and returned the same beat for ever, and the tempo measured 47x.
	"""

	session = FakeLinkSession(start = 4.0)

	beats = [asyncio.run(session.sync(1 / PPQ)) for _ in range(4)]

	assert beats == pytest.approx([4 + n / PPQ for n in range(1, 5)])


def test_the_stand_in_resumes_at_a_multiple_not_a_position () -> None:

	"""aalink's documented behaviour, which is the whole of this ticket."""

	session = FakeLinkSession(start = 11.5)

	assert asyncio.run(session.sync(2.0)) == 12.0


# ---------------------------------------------------------------------------
# Tempo and phase
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_piece_plays_at_the_sessions_tempo (patch_midi: None) -> None:

	"""47 pulses spanned 3.9167 beats where 1.9583 was due — exactly half speed."""

	session = FakeLinkSession()
	heard = await _play(session, 48)

	spanned = heard[-1] - heard[0]

	assert spanned == pytest.approx((len(heard) - 1) / PPQ), \
		f"{len(heard) - 1} pulses spanned {spanned:.4f} beats"


@pytest.mark.asyncio
async def test_the_first_pulse_lands_on_the_bar_line (patch_midi: None) -> None:

	"""It waited for `2 × quantum` — a whole bar late — because of the same mistake."""

	session = FakeLinkSession(quantum = 4.0)
	heard = await _play(session, 4)

	assert heard[0] == 4.0, f"the piece started at beat {heard[0]}, not the bar line"


@pytest.mark.asyncio
async def test_every_pulse_is_one_pulse_after_the_last (patch_midi: None) -> None:

	"""The lattice the loop actually walks."""

	session = FakeLinkSession()
	heard = await _play(session, 30)

	gaps = [b - a for a, b in zip(heard, heard[1:])]

	assert gaps == pytest.approx([1 / PPQ] * len(gaps))


@pytest.mark.asyncio
async def test_the_loop_asks_for_a_period_never_a_position (patch_midi: None) -> None:

	"""A position grows without bound; a period is always the same small number."""

	session = FakeLinkSession()
	await _play(session, 20)

	assert session.asked_for, "the loop never synced at all"
	assert all(period == pytest.approx(1 / PPQ) for period in session.asked_for), \
		f"the loop asked for {sorted(set(session.asked_for))[:4]}"


@pytest.mark.asyncio
@pytest.mark.parametrize("quantum", [1.0, 2.0, 4.0, 3.0])
async def test_the_start_is_a_bar_line_whatever_the_quantum (patch_midi: None, quantum: float) -> None:

	"""`wait_for_bar` is `sync(quantum)`, so this follows from the session, not arithmetic."""

	session = FakeLinkSession(quantum = quantum)
	heard = await _play(session, 3)

	assert heard[0] == pytest.approx(quantum)


# ---------------------------------------------------------------------------
# Falling behind
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_short_stall_is_caught_up_pulse_by_pulse (patch_midi: None) -> None:

	"""As the internal clock's inner loop does: play what was missed, in order.

	Counting pulses alone proves nothing — the loop plays 30 of them whether it
	catches up or simply runs six pulses late for ever.  What says it caught up
	is that those six cost no waiting: six fewer syncs than pulses.
	"""

	session = FakeLinkSession()

	def stall_once (count: int) -> None:
		if count == 5:
			session.stall(6 / PPQ)		# six pulses of session time

	heard = await _play(session, 30, on_pulse = stall_once)

	assert len(heard) == 30, "pulses were dropped rather than caught up"
	assert len(session.asked_for) == 24, \
		f"30 pulses with six caught up should cost 24 waits, not {len(session.asked_for)}"

	# Six of the thirty were played without waiting, which is what catching up
	# IS — so thirty pulses fall on twenty-four distinct session beats.
	assert len({round(beat, 9) for beat in heard}) == 24


@pytest.mark.asyncio
async def test_a_long_stall_moves_to_the_sessions_position (patch_midi: None) -> None:

	"""Playing off a large backlog is a burst of noise and then a piece running slow."""

	session = FakeLinkSession()

	def stall_once (count: int) -> None:
		if count == 3:
			session.stall(4.0)		# four beats: 96 pulses, far past the limit

	with unittest.mock.patch.object(subsequence.sequencer.logger, "warning") as warned:
		heard = await _play(session, 12, on_pulse = stall_once)

	said = [str(call) for call in warned.call_args_list if "behind" in str(call)]

	assert said, f"nothing was said about falling behind: {warned.call_args_list}"
	assert "96" in said[0], said[0]
	assert len(heard) == 12


@pytest.mark.asyncio
async def test_a_long_stall_leaves_the_pulse_count_where_the_session_is (patch_midi: None) -> None:

	"""Resyncing means the counter moves too, or the bars drift for the rest of the piece."""

	session = FakeLinkSession()
	sequencer = subsequence.sequencer.Sequencer(output_device_name = "Dummy MIDI", initial_bpm = 120)
	sequencer._event_loop = asyncio.get_running_loop()
	sequencer.running = True
	sequencer.active_notes.add((0, 0, 60))

	played = []

	async def counted () -> None:
		played.append(sequencer.pulse_count)
		sequencer.pulse_count += 1

		if len(played) == 3:
			session.stall(4.0)

		if len(played) >= 6:
			sequencer.running = False

	sequencer._advance_pulse = counted		# type: ignore[method-assign]

	await sequencer._run_loop_link_clock(session, pulses_per_bar = 96)

	# Three ordinary pulses, then a jump of about a beat's worth of pulses.
	assert played[:3] == [0, 1, 2]
	assert played[3] > 90, f"the counter stayed at {played[3]} while the session moved four beats"


@pytest.mark.asyncio
async def test_no_stall_means_no_catch_up (patch_midi: None) -> None:

	"""The ordinary case must not be reported as falling behind."""

	session = FakeLinkSession()

	with unittest.mock.patch.object(subsequence.sequencer.logger, "warning") as warned:
		heard = await _play(session, 40)

	assert [call for call in warned.call_args_list if "behind" in str(call)] == []
	assert len(heard) == 40

	# One wait per pulse.  Fewer would mean the loop believed it was behind and
	# played pulses it had not waited for.
	assert len(session.asked_for) == 40, \
		f"40 pulses cost {len(session.asked_for)} waits — the loop caught up over nothing"


# ---------------------------------------------------------------------------
# What the adapter asks aalink for
# ---------------------------------------------------------------------------

def test_wait_for_bar_asks_the_session_for_a_bar () -> None:

	"""It computed the boundary itself, which raised on aalink 0.2.3 at zero or below
	and hung with the GIL held on 0.2.2 and earlier."""

	import subsequence.link_clock

	asked: typing.List[float] = []

	class Link:
		quantum = 4.0
		beat = -2.5

		async def sync (self, period: float) -> float:
			asked.append(period)
			return 0.0

	clock = subsequence.link_clock.LinkClock.__new__(subsequence.link_clock.LinkClock)
	clock._link = Link()		# type: ignore[attr-defined]

	assert asyncio.run(clock.wait_for_bar()) == 0.0
	assert asked == [4.0], "wait_for_bar computed a boundary instead of asking for one"


def test_the_aalink_floor_is_at_least_two () -> None:

	"""`sync()` returning 0.0 safely for a zero boundary is a 0.2 behaviour."""

	import pathlib
	import re

	pyproject = (pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
	pinned = re.search(r'"aalink>=([0-9.]+)"', pyproject)

	assert pinned is not None, "aalink is no longer pinned in pyproject.toml"

	major, minor = (int(part) for part in pinned.group(1).split(".")[:2])

	assert (major, minor) >= (0, 2), f"the floor is aalink {pinned.group(1)}"
