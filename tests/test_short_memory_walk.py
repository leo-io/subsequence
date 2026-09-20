"""A seeded walk is not one of two melodies (#3047).

`self_avoiding_walk` avoided every value it had ever visited, which on a
one-dimensional range leaves nothing to choose: after the first step one
neighbour is always visited, so every step after it is forced until the walk
traps itself and bounces back. Measured over 500 seeds it produced exactly
**two** distinct melodies for any given range and length — the only randomness
in the whole function was the direction of the first step.

Decision 19 of #2991: a short-memory walk. Steps of ±1, occasionally ±2,
refusing only what was heard in the last few notes — about half the range.

**Seeded pieces using it sound different.**
"""

import collections
import random
import typing

import pytest

import subsequence
import subsequence.sequence_utils


# ---------------------------------------------------------------------------
# #3047 — the walk has somewhere to go
# ---------------------------------------------------------------------------

def _walks (n: int, low: int, high: int, seeds: int = 500) -> typing.Set[typing.Tuple[int, ...]]:

	return {
		tuple(subsequence.sequence_utils.self_avoiding_walk(n, low, high, random.Random(seed)))
		for seed in range(seeds)
	}


@pytest.mark.parametrize(("low", "high", "n"), [(60, 72, 16), (40, 64, 16), (60, 67, 12)])
def test_the_seed_actually_changes_the_melody (low: int, high: int, n: int) -> None:

	"""Two distinct melodies across 500 seeds was the finding, and no test saw it.

	The review noted the self-avoiding-walk tests never compared seeds. This
	is that test.
	"""

	distinct = len(_walks(n, low, high))

	assert distinct > 50, f"only {distinct} distinct melodies across 500 seeds for {low}-{high}"


def test_a_value_does_not_come_straight_back () -> None:

	"""What the short memory is for: no repetition near at hand."""

	for seed in range(50):
		walk = subsequence.sequence_utils.self_avoiding_walk(16, 60, 72, random.Random(seed))

		for i, value in enumerate(walk):
			for j in range(i + 1, min(i + 3, len(walk))):
				assert walk[j] != value, f"{value} returned after {j - i} notes: {walk}"


@pytest.mark.parametrize("seed", range(10))
def test_every_step_is_a_step_or_a_small_leap (seed: int) -> None:

	"""±1 mostly, ±2 occasionally — never a jump, never standing still."""

	walk = subsequence.sequence_utils.self_avoiding_walk(24, 60, 72, random.Random(seed))

	for a, b in zip(walk, walk[1:]):
		assert abs(b - a) in (1, 2), f"{a} -> {b}"


def test_steps_outnumber_leaps () -> None:

	"""'Occasionally ±2' is a claim about proportion, so measure the proportion.

	Weighted 8:1 rather than 4:1, because the choice is made among what is
	REACHABLE and the note just left is usually the ±1 that is excluded — at
	4:1 that delivered 37% leaps, which is not occasional.
	"""

	sizes: collections.Counter = collections.Counter()

	for seed in range(200):
		walk = subsequence.sequence_utils.self_avoiding_walk(16, 60, 72, random.Random(seed))
		sizes.update(abs(b - a) for a, b in zip(walk, walk[1:]))

	leaps = sizes[2] / (sizes[1] + sizes[2])

	assert 0.05 < leaps < 0.40, f"leaps were {leaps:.0%} of steps"


@pytest.mark.parametrize(("low", "high"), [(60, 60), (60, 61), (60, 62)])
def test_a_range_with_no_room_still_behaves (low: int, high: int) -> None:

	"""A range of one, two or three values has little freedom; it must not raise."""

	walk = subsequence.sequence_utils.self_avoiding_walk(12, low, high, random.Random(1))

	assert len(walk) == 12
	assert all(low <= value <= high for value in walk)

	# Standing still also satisfies "right length, in range", and standing
	# still is the one thing a walk must not do where it has anywhere to go.
	# "More than one distinct value" is not enough either: a walk that takes
	# one step and then stalls satisfies that too. It must move EVERY step.
	if high > low:
		stalls = [i for i, (a, b) in enumerate(zip(walk, walk[1:])) if a == b]

		assert not stalls, f"the walk stopped moving at step(s) {stalls}: {walk}"


def test_the_walk_is_still_deterministic_for_one_seed () -> None:

	"""The control: more variety across seeds, none within one."""

	first = subsequence.sequence_utils.self_avoiding_walk(16, 60, 72, random.Random(99))
	again = subsequence.sequence_utils.self_avoiding_walk(16, 60, 72, random.Random(99))

	assert first == again


def test_the_walk_still_honours_its_range_and_length () -> None:

	"""The other controls, which the old version also passed."""

	walk = subsequence.sequence_utils.self_avoiding_walk(32, 48, 55, random.Random(5))

	assert len(walk) == 32
	assert all(48 <= value <= 55 for value in walk)
	assert subsequence.sequence_utils.self_avoiding_walk(0, 0, 7, random.Random(1)) == []
