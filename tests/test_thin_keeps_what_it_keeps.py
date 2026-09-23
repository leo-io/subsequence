"""thin() keeps the positions its strategy says it keeps (#3462, Simon's call on #3423).

It borrowed ghost_fill's weights, whose floor of 0.05 on the beat and 0.3 on the &
suit placing a ghost note, and dropped each note with probability priority x amount.
So its own docstring example lost an anchor kick in 9.3% of bars at amount 0.5 and
19.2% at 1.0, and "sixteenths" dropped 24% of the & notes it says it keeps.  Now a
position a strategy keeps is never touched, and one it removes goes with
probability ``amount``.
"""

import random
import typing

import pytest

import subsequence.pattern
import subsequence.pattern_builder

KICK = 36
BEATS = {0, 4, 8, 12}
ANDS = {2, 6, 10, 14}
BEFORE = {3, 7, 11, 15}
AFTER = {1, 5, 9, 13}
EVERY_STEP = set(range(16))


def _builder (seed: int) -> subsequence.pattern_builder.PatternBuilder:

	pattern = subsequence.pattern.Pattern(channel=9, length=4)

	return subsequence.pattern_builder.PatternBuilder(
		pattern=pattern, cycle=0, default_grid=16, drum_note_map={"kick_1": KICK}, rng=random.Random(seed),
	)


def _steps (p: subsequence.pattern_builder.PatternBuilder) -> typing.Set[int]:

	"""The sixteenth steps that still hold a note."""

	return {pulse // 6 for pulse, step in p._pattern.steps.items() if step.notes}


@pytest.mark.parametrize("amount", [0.5, 0.8, 1.0])
def test_the_docstring_example_never_drops_an_anchor_or_an_and (amount: float) -> None:

	"""Anchors on the beats and ghosts on the & survive thin("sixteenths"), at any amount."""

	for seed in range(300):
		p = _builder(seed)
		p.hit_steps("kick_1", [0, 4, 8, 12], velocity=100)
		p.ghost_fill("kick_1", density=0.3, velocity=(25, 40), bias="sixteenths")
		kept_before = _steps(p) & (BEATS | ANDS)

		p.thin("kick_1", "sixteenths", amount=amount)

		assert _steps(p) & (BEATS | ANDS) == kept_before, f"seed {seed}"
		assert BEATS <= _steps(p)


@pytest.mark.parametrize(("strategy", "survivors"), [
	("sixteenths", BEATS | ANDS),
	("e_and_a", BEATS),
	("upbeat", EVERY_STEP - ANDS),
	("downbeat", EVERY_STEP - BEATS),
	("before", EVERY_STEP - BEFORE),
	("after", EVERY_STEP - AFTER),
	("uniform", set()),
])
def test_each_strategy_removes_exactly_what_it_names (strategy: str, survivors: typing.Set[int]) -> None:

	"""At full amount, a note on every step: what the strategy keeps, and nothing else, survives, every time."""

	for seed in range(50):
		p = _builder(seed)
		p.hit_steps("kick_1", range(16), velocity=100)
		p.thin("kick_1", strategy, amount=1.0)

		assert _steps(p) == survivors, f"{strategy}, seed {seed}"


def test_offbeat_removes_the_and_and_thins_the_sixteenths_lightly () -> None:

	"""The & goes, the beats stay, and about three in ten of the e and a go too."""

	removed = 0

	for seed in range(500):
		p = _builder(seed)
		p.hit_steps("kick_1", range(16), velocity=100)
		p.thin("kick_1", "offbeat", amount=1.0)

		assert BEATS <= _steps(p) and not _steps(p) & ANDS, f"seed {seed}"
		removed += len((BEFORE | AFTER) - _steps(p))

	assert 0.25 < removed / (500 * 8) < 0.35


def test_strength_still_thins_weakest_first () -> None:

	"""The graded strategy is unchanged: at full amount a beat still goes one time in twenty.

	This passed before #3462 as well.
	"""

	lost = {"beats": 0, "ands": 0, "sixteenths": 0}

	for seed in range(1000):
		p = _builder(seed)
		p.hit_steps("kick_1", range(16), velocity=100)
		p.thin("kick_1", "strength", amount=1.0)
		lost["beats"] += len(BEATS - _steps(p))
		lost["ands"] += len(ANDS - _steps(p))
		lost["sixteenths"] += len((BEFORE | AFTER) - _steps(p))

	assert 0.03 < lost["beats"] / 4000 < 0.07
	assert 0.55 < lost["ands"] / 4000 < 0.65
	assert lost["sixteenths"] == 8000
