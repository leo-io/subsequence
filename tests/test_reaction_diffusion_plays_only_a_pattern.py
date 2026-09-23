"""reaction_diffusion plays a pattern or nothing, never a dead field stretched into hits (#3464).

The kernel normalised whatever the simulation left, and caught an empty field
only when every cell was exactly equal.  So a field that had died out - the
docstring's own example left 1.7e-40 of the chemical - or evened out to a
ripple of 1e-15 was stretched into a bar of hits, the same hits whatever the
rates.  Across the documented range that was 95% of the settings.

Now a field whose peak is under a millionth has died out, and one that varies
by less than a hundredth of its own peak has evened out; either holds no
pattern, and the call plays nothing and says why, once per setting.  At
Simon's call on #3423 the default rates moved to feed 0.08 and kill 0.061, which
form a pattern on every grid of 8 steps or more; the old ones died out on 12
steps or fewer.
"""

import inspect
import logging
import typing

import pytest

import subsequence
import subsequence.pattern
import subsequence.pattern_algorithmic
import subsequence.pattern_builder
import subsequence.sequence_utils


def _builder (grid: int = 16) -> typing.Tuple[subsequence.pattern.Pattern, subsequence.pattern_builder.PatternBuilder]:

	pattern = subsequence.pattern.Pattern(channel=9, length=grid / 4)

	return pattern, subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=0, default_grid=grid)


def _steps (pattern: subsequence.pattern.Pattern) -> typing.List[int]:

	"""The grid steps that hold a note, on a sixteenth grid."""

	return sorted(position // 6 for position in pattern.steps)


def _warnings (caplog: pytest.LogCaptureFixture) -> typing.List[str]:

	return [record.getMessage() for record in caplog.records if record.getMessage().startswith("reaction_diffusion(")]


def test_a_field_that_dies_out_holds_no_pattern () -> None:

	"""The old docstring example: 1.7e-40 of the chemical left, which played ten hits."""

	profile = subsequence.sequence_utils.reaction_diffusion_1d(16, steps=1000, feed_rate=0.037, kill_rate=0.060)

	assert profile == [0.0] * 16


def test_a_field_that_evens_out_holds_no_pattern () -> None:

	"""A field at about 0.25 everywhere, varying by rounding noise, played eight hits."""

	profile = subsequence.sequence_utils.reaction_diffusion_1d(16, steps=1000, feed_rate=0.030, kill_rate=0.049)

	assert profile == [0.0] * 16


def test_a_field_that_dies_away_in_shape_holds_no_pattern () -> None:

	"""A little too much kill: the run fades keeping its shape, so only its size says it has died.

	After 200 steps this field peaks at 6.5e-8 and still varies by 0.59 of that,
	which no measure of evenness would call flat.
	"""

	profile = subsequence.sequence_utils.reaction_diffusion_1d(16, steps=200, feed_rate=0.08, kill_rate=0.064)

	assert profile == [0.0] * 16


def test_a_faint_field_with_a_shape_is_still_a_pattern () -> None:

	"""The two lines sit where they do on purpose: a field above a millionth that varies by a tenth plays.

	At 2000 steps on 32 cells this one peaks at 9.3e-5 and varies by 0.11 of
	that, on its way to dying out by 5000.  Until then the simulation still has
	this shape, and normalising it gives the shape back rather than inventing one.
	"""

	profile = subsequence.sequence_utils.reaction_diffusion_1d(32, steps=2000, feed_rate=0.028, kill_rate=0.052)

	assert [step for step, value in enumerate(profile) if value > 0.5] == [0, 1, 2, 3, 4, 5, 6, 7, 24, 25, 26, 27, 28, 29, 30, 31]


def test_a_fading_ripple_is_not_a_pattern () -> None:

	"""Evenness is measured against the field's own peak, not as an absolute spread.

	At 1000 steps this field peaks at 0.22 and varies by 2.4e-5 - a ripple on its
	way to flat, gone by 2000 steps.  A spread of a millionth would have let it
	through as a two-run pattern, as it would ten others at 16 cells.
	"""

	profile = subsequence.sequence_utils.reaction_diffusion_1d(16, steps=1000, feed_rate=0.034, kill_rate=0.056)

	assert profile == [0.0] * 16


def test_the_reason_is_what_happened_to_the_field () -> None:

	reporting = subsequence.sequence_utils._reaction_diffusion_reporting

	assert reporting(16, 1000, 0.037, 0.060)[1] == "died out"
	assert reporting(16, 1000, 0.030, 0.049)[1] == "evened out"
	assert reporting(16, 1000, 0.08, 0.061)[1] is None


def test_a_pattern_is_still_normalised () -> None:

	"""A guard, not a fix: a field with a pattern comes back exactly as before.

	This passed before #3464 as well.
	"""

	profile = subsequence.sequence_utils.reaction_diffusion_1d(16, steps=1000, feed_rate=0.08, kill_rate=0.061)

	assert (min(profile), max(profile)) == (0.0, 1.0)
	assert [step for step, value in enumerate(profile) if value > 0.5] == [5, 6, 7, 8, 9, 10]


def test_a_blown_up_simulation_raises () -> None:

	"""Rates far outside the band overflow to infinity; that is an error, as lorenz's is (#3408), not silence."""

	with pytest.raises(ValueError, match="blew up"):
		subsequence.sequence_utils.reaction_diffusion_1d(16, steps=1000, feed_rate=2.0, kill_rate=2.0)


def test_a_setting_with_no_pattern_places_nothing () -> None:

	pattern, p = _builder()
	p.reaction_diffusion(42, feed_rate=0.037, kill_rate=0.060)

	assert pattern.steps == {}


def test_a_setting_with_no_pattern_says_why_once (caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:

	"""A rebuild runs every bar: the first warning is the useful one, and a new setting earns its own.

	A setting is the rates, the grid and the steps together.
	"""

	monkeypatch.setattr(subsequence.pattern_algorithmic, "_warned_no_pattern", set())

	with caplog.at_level(logging.WARNING, logger="subsequence.pattern_algorithmic"):
		for grid, kill_rate, steps in ((16, 0.060, 1000), (16, 0.060, 1000), (16, 0.065, 1000), (12, 0.065, 1000), (12, 0.065, 2000)):
			_, p = _builder(grid)
			p.reaction_diffusion(42, feed_rate=0.037, kill_rate=kill_rate, steps=steps)

	said = " with too much kill for the feed, so there is no pattern to play. The default rates form one on any grid of 8 steps or more."

	assert _warnings(caplog) == [
		"reaction_diffusion(feed_rate=0.037, kill_rate=0.06) on 16 steps: the chemical died out," + said,
		"reaction_diffusion(feed_rate=0.037, kill_rate=0.065) on 16 steps: the chemical died out," + said,
		"reaction_diffusion(feed_rate=0.037, kill_rate=0.065) on 12 steps: the chemical died out," + said,
		"reaction_diffusion(feed_rate=0.037, kill_rate=0.065) on 12 steps: the chemical died out," + said,
	]


def test_a_field_that_evened_out_says_there_was_too_little_kill (caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:

	monkeypatch.setattr(subsequence.pattern_algorithmic, "_warned_no_pattern", set())

	with caplog.at_level(logging.WARNING, logger="subsequence.pattern_algorithmic"):
		pattern, p = _builder()
		p.reaction_diffusion(42, feed_rate=0.030, kill_rate=0.049)

	assert pattern.steps == {}
	assert [message.split(": ", 1)[1].split(",")[0] for message in _warnings(caplog)] == ["the chemical evened out"]
	assert "too little kill for the feed" in _warnings(caplog)[0]


def test_a_pattern_is_not_warned_about (caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:

	monkeypatch.setattr(subsequence.pattern_algorithmic, "_warned_no_pattern", set())

	with caplog.at_level(logging.WARNING, logger="subsequence.pattern_algorithmic"):
		pattern, p = _builder()
		p.reaction_diffusion(42)

	assert _steps(pattern) == [5, 6, 7, 8, 9, 10]
	assert _warnings(caplog) == []


@pytest.mark.parametrize(("grid", "steps"), [
	(8, [2, 3, 4, 5]),
	(12, [3, 4, 5, 6, 7, 8]),
	(16, [5, 6, 7, 8, 9, 10]),
	(24, [4, 5, 6, 7, 8, 15, 16, 17, 18, 19]),
	(32, [7, 8, 9, 10, 11, 20, 21, 22, 23, 24]),
])
def test_the_default_rates_play_what_the_docstring_says (grid: int, steps: typing.List[int]) -> None:

	"""A run of 4 on 8 steps, 6 on 12 or 16, and two runs of 5 on 24 or 32 (Simon's call on #3423).

	The old defaults died out on 12 steps or fewer, and played a run of 8 on 16.
	"""

	pattern, p = _builder(grid)
	p.reaction_diffusion(42)

	assert _steps(pattern) == steps


@pytest.mark.parametrize("grid", [8, 9, 10, 11, 13, 15, 20, 28, 40, 48, 64])
def test_the_default_rates_form_a_pattern_on_any_grid_from_8_steps (grid: int) -> None:

	"""The warning's promise: measured on every grid from 8 to 128 steps, and 100 to 5000 steps."""

	pattern, p = _builder(grid)
	p.reaction_diffusion(42)

	assert pattern.steps


def test_the_kernel_shares_the_builders_default_rates () -> None:

	"""A bare ``reaction_diffusion_1d`` call on 12 cells would otherwise still die out."""

	def rates (function: typing.Callable[..., typing.Any]) -> typing.Tuple[typing.Any, typing.Any]:
		parameters = inspect.signature(function).parameters
		return parameters["feed_rate"].default, parameters["kill_rate"].default

	assert rates(subsequence.sequence_utils.reaction_diffusion_1d) == rates(subsequence.pattern_builder.PatternBuilder.reaction_diffusion) == (0.08, 0.061)


@pytest.mark.parametrize(("feed_rate", "run"), [(0.058, 12), (0.066, 10), (0.072, 8), (0.08, 6), (0.088, 4), (0.046, 0), (0.096, 0)])
def test_feed_rate_sets_the_runs_length_as_documented (feed_rate: float, run: int) -> None:

	"""On 16 steps at the default kill: 12, 10, 8, 6 and 4, and nothing below about 0.048 or above about 0.094."""

	pattern, p = _builder()
	p.reaction_diffusion(42, feed_rate=feed_rate)

	assert len(_steps(pattern)) == run


def test_the_rates_are_published_with_the_range_that_can_form_a_pattern () -> None:

	"""Unbounded, a surface drew each as a stepper that could be pushed anywhere.

	No setting outside these formed a pattern, on any grid from 8 to 64 steps.
	No step is published: these are rates in an equation, with no musical
	increment.
	"""

	parameters = {entry["name"]: entry for entry in subsequence.describe_generator("reaction_diffusion")["parameters"]}

	assert {name: (parameters[name].get("min"), parameters[name].get("max"), parameters[name]["default"]) for name in ("feed_rate", "kill_rate")} == {
		"feed_rate": (0.0, 0.2, 0.08),
		"kill_rate": (0.0, 0.07, 0.061),
	}
	assert "step" not in parameters["feed_rate"] and "step" not in parameters["kill_rate"]


def test_every_setting_in_the_published_range_builds () -> None:

	"""A guard for #3431, which drives only required parameters: every corner of both ranges, and between.

	This passed before #3464 as well - nothing in the range blows up.  The corners
	also run at the most steps allowed.
	"""

	rates = [(feed_rate, kill_rate) for feed_rate in (0.0, 0.05, 0.1, 0.15, 0.2) for kill_rate in (0.0, 0.02, 0.04, 0.06, 0.07)]

	for feed_rate, kill_rate in rates:
		profile = subsequence.sequence_utils.reaction_diffusion_1d(16, 1000, feed_rate, kill_rate)
		assert all(0.0 <= value <= 1.0 for value in profile), (feed_rate, kill_rate)

	for feed_rate in (0.0, 0.2):
		for kill_rate in (0.0, 0.07):
			_, p = _builder(8)
			p.reaction_diffusion(42, feed_rate=feed_rate, kill_rate=kill_rate, steps=20000)
