"""The Lorenz generator runs where it is published to run (M17 of the 2026-09-19 review).

Plain Euler ran the classic system off to infinity from a step of about 0.025, and a rebuild
then raised, silencing the part - with dt published as a control with no bounds.  And the
trajectory's highest point, which min-max normalisation always puts at exactly 1.0, wrapped round
to the lowest pitch.
"""

import logging
import math
import typing

import pytest

import subsequence
import subsequence.pattern
import subsequence.pattern_builder
import subsequence.sequence_utils


POOL = [60, 62, 64, 65, 67, 69, 71, 72]


def _built (**kwargs: typing.Any) -> typing.List[int]:

	"""A four-beat bar of Lorenz sixteenths over POOL, as the pitches it plays, in order."""

	pattern = subsequence.pattern.Pattern(channel=0, length=4.0)
	builder = subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=0)
	builder.lorenz(POOL, **kwargs)
	builder._finish_build()

	return [note.pitch for pulse in sorted(pattern.steps) for note in pattern.steps[pulse].notes]


def test_a_long_dt_no_longer_runs_off_to_infinity () -> None:

	"""At dt 0.03 plain Euler reached NaN within 200 points; every point is finite, and in range."""

	points = subsequence.sequence_utils.lorenz_attractor(200, dt=0.03)

	assert len(points) == 200
	assert all(math.isfinite(value) and 0.0 <= value <= 1.0 for point in points for value in point)


def test_a_bar_with_a_long_dt_plays_across_its_pool () -> None:

	"""At dt 0.1 the bar built, but the runaway trajectory played one pitch over and over."""

	pitches = _built(dt=0.1)

	assert len(pitches) == 16
	assert len(set(pitches)) >= 4


def test_up_to_one_step_the_trajectory_is_exactly_what_it_was () -> None:

	"""Sub-stepping splits only a dt longer than 0.01, so the default sound of every piece stands."""

	x, y, z, sigma, rho, beta, dt = 0.1, 0.0, 0.0, 10.0, 28.0, 8.0 / 3.0, 0.01
	raw = []

	for _ in range(16):
		x, y, z = x + sigma * (y - x) * dt, y + (x * (rho - z) - y) * dt, z + (x * y - beta * z) * dt
		raw.append(x)

	lo, hi = min(raw), max(raw)
	expected = [(value - lo) / (hi - lo) for value in raw]

	assert [point[0] for point in subsequence.sequence_utils.lorenz_attractor(16)] == pytest.approx(expected, abs=1e-12)


def test_the_trajectory_s_highest_point_plays_the_highest_pitch () -> None:

	"""x reaches exactly 1.0 once a phrase, and a modulo sent it round to the lowest pitch."""

	points = subsequence.sequence_utils.lorenz_attractor(16)
	top = max(range(16), key=lambda index: points[index][0])
	assert points[top][0] == 1.0

	assert _built()[top] == POOL[-1]


def test_dt_is_held_to_its_span (caplog: pytest.LogCaptureFixture) -> None:

	"""A control surface can send any dt the catalogue publishes, so it publishes a span and holds to it."""

	with caplog.at_level(logging.WARNING):
		pitches = _built(dt=5.0)

	assert len(pitches) == 16
	assert "dt" in caplog.text

	entry = next(entry for entry in subsequence.generators() if entry["name"] == "lorenz")
	dt = next(parameter for parameter in entry["parameters"] if parameter["name"] == "dt")

	assert (dt["min"], dt["max"]) == (0.001, 0.5)
