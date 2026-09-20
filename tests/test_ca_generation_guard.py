"""A negative CA generation must not reach the shared cache (#3050).

`generate_cellular_automaton_1d` memoises `(generation, state)` per
`(steps, rule, seed)` in a **module-level** dict. A negative generation stored
the INITIAL state under a negative number; the next call with `generation=0`
then found `-3 <= 0`, accepted the cached entry, and ran `range(-3, 0)` —
three evolution steps — returning them as "generation 0".

Measured in one process, identical arguments both times:

    generation=0 on a clean process : [0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0]
    generation=-3                   : [0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0]
    generation=0 again              : [0,0,0,0,0,1,1,0,1,1,1,1,0,0,0,0]

The cache is process-global, so it reached *other patterns* sharing a rule and
seed; and it depended on the order calls happened to be made in, so it showed
up in some sessions and not others. `p.cycle` is never negative, but
`generation=p.cycle - 4` is the obvious way to write a lagged layer.

The 2D generator has the same cache shape and had the same bug.
"""

import typing

import pytest

import subsequence.sequence_utils


# ---------------------------------------------------------------------------
# It is refused
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("generation", [-1, -3, -100])
def test_a_negative_generation_is_refused (generation: int) -> None:

	"""Where it is written, naming the value — as MIDI numbers are (#3004)."""

	with pytest.raises(ValueError) as refusal:
		subsequence.sequence_utils.generate_cellular_automaton_1d(16, rule = 30, generation = generation)

	assert str(generation) in str(refusal.value), str(refusal.value)


@pytest.mark.parametrize("generation", [-1, -5])
def test_the_two_dimensional_generator_refuses_it_too (generation: int) -> None:

	"""Same cache shape, same bug, same guard."""

	with pytest.raises(ValueError):
		subsequence.sequence_utils.generate_cellular_automaton_2d(4, 8, generation = generation)


def test_the_refusal_says_what_generation_zero_means () -> None:

	"""Somebody writing p.cycle - 4 wants a lag; tell them where the floor is."""

	with pytest.raises(ValueError) as refusal:
		subsequence.sequence_utils.generate_cellular_automaton_1d(16, generation = -2)

	assert "0" in str(refusal.value)
	assert "cycle" in str(refusal.value).lower()


# ---------------------------------------------------------------------------
# The cache survives it
# ---------------------------------------------------------------------------

def test_generation_zero_still_means_generation_zero_afterwards () -> None:

	"""The consequence: one bad call changed what a later, innocent call returned."""

	rule, seed = 30, 1

	before = subsequence.sequence_utils.generate_cellular_automaton_1d(16, rule = rule, generation = 0, seed = seed)

	with pytest.raises(ValueError):
		subsequence.sequence_utils.generate_cellular_automaton_1d(16, rule = rule, generation = -3, seed = seed)

	after = subsequence.sequence_utils.generate_cellular_automaton_1d(16, rule = rule, generation = 0, seed = seed)

	assert before == after, f"the cache was poisoned: {before} became {after}"


def test_generation_zero_is_the_initial_state () -> None:

	"""Named directly, so a regression is recognisable rather than merely unequal.

	Seed 1 is documented as a single centre cell.
	"""

	state = subsequence.sequence_utils.generate_cellular_automaton_1d(16, rule = 30, generation = 0, seed = 1)

	assert sum(state) == 1, state
	assert state[8] == 1, state


def test_another_pattern_sharing_the_rule_is_unaffected () -> None:

	"""The cache is process-global, which is why this was worse than one bad call."""

	rule, seed = 90, 3

	one = subsequence.sequence_utils.generate_cellular_automaton_1d(16, rule = rule, generation = 4, seed = seed)

	with pytest.raises(ValueError):
		subsequence.sequence_utils.generate_cellular_automaton_1d(16, rule = rule, generation = -2, seed = seed)

	two = subsequence.sequence_utils.generate_cellular_automaton_1d(16, rule = rule, generation = 4, seed = seed)

	assert one == two


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("generation", [0, 1, 5, 40])
def test_an_ordinary_generation_still_evolves (generation: int) -> None:

	"""A guard that refused everything would pass every test above."""

	state = subsequence.sequence_utils.generate_cellular_automaton_1d(16, rule = 30, generation = generation, seed = 1)

	assert len(state) == 16
	assert all(cell in (0, 1) for cell in state)


def test_the_cache_still_makes_a_long_walk_agree_with_a_short_one () -> None:

	"""The cache exists for a reason; the guard must not have disabled it.

	Walking generations one at a time, as `p.cycle` does, must land on the
	same state as asking for the last one outright.
	"""

	rule, seed = 30, 7

	for generation in range(12):
		walked = subsequence.sequence_utils.generate_cellular_automaton_1d(16, rule = rule, generation = generation, seed = seed)

	subsequence.sequence_utils._ca_1d_cache.clear()

	direct = subsequence.sequence_utils.generate_cellular_automaton_1d(16, rule = rule, generation = 11, seed = seed)

	assert walked == direct


def test_a_degenerate_size_is_still_a_no_op () -> None:

	"""steps<=0 returns [] and must keep doing so — the guard sits after it."""

	assert subsequence.sequence_utils.generate_cellular_automaton_1d(0, generation = 3) == []
