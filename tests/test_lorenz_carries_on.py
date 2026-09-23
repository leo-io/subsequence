"""lorenz carries one trajectory on from bar to bar, measured against the range it covers (#3472, Simon's calls on #3423).

Each bar used to integrate from (x0, y0, z0) and stretch its own sixteen points to fill the pool.
From near the origin a bar-long stretch is x0 times a fixed curve, and the stretching divided x0
back out, so the documented ``x0=p.cycle * 0.001`` played one bar in 199 of 200 cycles.  Now bar c
plays points 16c to 16c + 15 of one trajectory, cached so each bar carries on from the last, and
every axis is scaled against the range the trajectory covers over its first sixty time units.  The
default dt moved from 0.01, where the continued line was nearly a drone, to 0.1.
"""

import collections
import inspect
import math
import statistics
import types
import typing

import pytest

import subsequence
import subsequence.pattern
import subsequence.pattern_builder
import subsequence.sequence_utils

POOL = [60, 62, 64, 65, 67, 69, 71, 72]


def _bar (cycle: int, **kwargs: typing.Any) -> typing.List[int]:

	"""A four-beat bar of Lorenz sixteenths over POOL at this cycle, as the pitches it plays."""

	pattern = subsequence.pattern.Pattern(channel=0, length=4.0)
	builder = subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=cycle)
	builder.lorenz(POOL, **kwargs)

	return [note.pitch for pulse in sorted(pattern.steps) for note in pattern.steps[pulse].notes]


def _steps (bar: typing.List[int]) -> typing.List[int]:

	return [POOL.index(pitch) for pitch in bar]


def test_a_bar_carries_on_from_the_last () -> None:

	"""Bar c is points 16c to 16c + 15 of one trajectory, scaled the same way as every other bar."""

	whole = subsequence.sequence_utils.lorenz_attractor(64)

	for cycle in range(4):
		assert subsequence.sequence_utils.lorenz_attractor(16, start=16 * cycle) == whole[16 * cycle:16 * cycle + 16], cycle
		assert _bar(cycle) == [POOL[min(int(x * 8), 7)] for x, _, _ in whole[16 * cycle:16 * cycle + 16]], cycle


def test_the_line_keeps_moving () -> None:

	"""Over 200 bars at the defaults, 182 are different; every bar was the same one."""

	assert len({tuple(_bar(cycle)) for cycle in range(200)}) == 182


def test_a_quiet_stretch_stays_quiet () -> None:

	"""Circling one wing, a bar holds a pitch or two - stretched to fill itself, every bar swept the pool."""

	spans = [max(_steps(bar)) - min(_steps(bar)) for bar in (_bar(cycle) for cycle in range(200))]

	assert spans.count(0) == 13
	assert statistics.median(spans) == 5


def test_the_default_dt_moves_like_a_line () -> None:

	"""Simon's call on #3423: at 0.1 about half the notes repeat and most of the rest step to a neighbour.

	Counted over 200 bars, 3000 moves from one note to the next.  At 0.01, continued, 2842 of them
	repeated the note before - nearly a drone.
	"""

	moves = collections.Counter(abs(b - a) for bar in (_steps(_bar(cycle)) for cycle in range(200)) for a, b in zip(bar, bar[1:]))

	assert sorted(moves.items()) == [(0, 1565), (1, 1204), (2, 197), (3, 34)]


def test_the_kernel_shares_the_builders_default_dt () -> None:

	def dt (function: typing.Callable[..., typing.Any]) -> typing.Any:
		return inspect.signature(function).parameters["dt"].default

	assert dt(subsequence.sequence_utils.lorenz_attractor) == dt(subsequence.pattern_builder.PatternBuilder.lorenz) == 0.1


def test_a_different_start_is_a_different_line () -> None:

	"""Replaces a test that only asked whether the floats differed, which they do by 2e-5 while the phrases agree.

	A millionth apart, the two lines part company by the second bar, and over 200 bars 187 differ;
	the rest meet by chance, both circling the same wing on the same pitch.
	"""

	one = [_bar(cycle) for cycle in range(200)]
	other = [_bar(cycle, x0=0.100001) for cycle in range(200)]

	assert one[0] == other[0]
	assert one[1] != other[1]
	assert sum(a != b for a, b in zip(one, other)) == 187


@pytest.mark.parametrize(("rho", "bars"), [(10.0, 5), (15.0, 28)])
def test_a_calm_rho_comes_to_rest_on_one_pitch (rho: float, bars: int) -> None:

	"""The docstring's figure: at about 15 or below the line comes to rest within 30 bars.

	Stretched to fill each bar, the dying spiral swept the whole pool for ever.
	"""

	played = [_bar(cycle, rho=rho) for cycle in range(bars + 8)]

	assert all(bar == [played[-1][0]] * 16 for bar in played[bars:])
	assert played[bars - 1] != played[bars]


def test_an_earlier_bar_is_played_again_exactly (monkeypatch: pytest.MonkeyPatch) -> None:

	"""A guard for the cache: going back integrates from the start again, so a bar never depends on what was played before it.

	From a cache of its own: one left by an earlier test could hand back anything, and a bar
	compared with another from the same state proves nothing.
	"""

	monkeypatch.setattr(subsequence.sequence_utils, "_lorenz_cache", subsequence.sequence_utils._EvolutionCache())

	fresh = _bar(10)

	_bar(50)

	assert len(fresh) == 16
	assert _bar(10) == fresh


def test_each_bar_integrates_only_its_own_points (monkeypatch: pytest.MonkeyPatch) -> None:

	"""Counted, not timed: carrying on from the cache, bar 101 integrates 16 points, not 1632.

	Every point is checked for running off with three ``math.isfinite`` calls, so the calls count
	the work.  This passed before #3472 as well, when every bar integrated its own sixteen points
	from the start; it is here for the cache, without which bar 101 would integrate all 1632.
	"""

	_bar(100)

	calls = 0

	def counted (value: float) -> bool:
		nonlocal calls
		calls += 1
		return bool(math_isfinite(value))

	math_isfinite = subsequence.sequence_utils.math.isfinite
	counting = types.SimpleNamespace(**{name: getattr(subsequence.sequence_utils.math, name) for name in dir(subsequence.sequence_utils.math) if not name.startswith("__")})
	counting.isfinite = counted
	monkeypatch.setattr(subsequence.sequence_utils, "math", counting)

	_bar(101)

	assert calls == 3 * 16


def test_a_trajectory_at_the_origin_plays_the_middle () -> None:

	"""A guard: started exactly at the origin the system never moves, and every axis sits in the middle."""

	assert subsequence.sequence_utils.lorenz_attractor(4, x0=0.0, y0=0.0, z0=0.0) == [(0.5, 0.5, 0.5)] * 4


def test_a_system_that_runs_off_says_so_before_the_first_bar () -> None:

	"""The range is measured first, over sixty time units, so a runaway fails at once rather than bars later.

	At sigma 100 and beta 201 the first bar is finite, and the system runs off 19 time units in,
	a dozen bars into the line.
	"""

	first_bar = subsequence.sequence_utils._lorenz_states(16, 0, 0.1, 100.0, 28.0, 201.0, 0.1, 0.0, 0.0)

	assert all(math.isfinite(value) for state in first_bar for value in state)

	with pytest.raises(ValueError, match="ran off to infinity"):
		subsequence.sequence_utils.lorenz_attractor(16, sigma=100.0, beta=201.0)


def test_the_kernel_refuses_a_negative_start () -> None:

	with pytest.raises(ValueError, match="start"):
		subsequence.sequence_utils.lorenz_attractor(16, start=-1)


def test_a_point_beyond_the_measured_range_is_clamped () -> None:

	"""Sixty time units do not reach every corner of the attractor: 280 units in, y dips below the range.

	That point plays the bottom of the range rather than below it, and all 3000 points stay in
	[0, 1].  Measured, the dips are all on the low side: the first loop out of the origin
	overshoots every later one.
	"""

	_, (lo_y, _), _ = subsequence.sequence_utils._lorenz_range(0.1, 10.0, 28.0, 8.0 / 3.0, 0.1, 0.0, 0.0)
	_, raw_y, _ = subsequence.sequence_utils._lorenz_states(1, 2796, 0.1, 10.0, 28.0, 8.0 / 3.0, 0.1, 0.0, 0.0)[0]

	assert raw_y < lo_y
	assert subsequence.sequence_utils.lorenz_attractor(1, start=2796)[0][1] == 0.0
	assert all(0.0 <= value <= 1.0 for point in subsequence.sequence_utils.lorenz_attractor(3000) for value in point)
