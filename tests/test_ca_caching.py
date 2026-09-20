"""The cellular-automaton caches are bounded, and cover an explicit grid (#3071, M19).

Both generators memoise their evolution per configuration and advance it
incrementally, because the common idiom drives `generation` from `p.cycle` —
one per bar — and without a cache every bar replays every prior generation.

Two things fell outside it. **An explicit starting grid was never cached**, for
want of a hashable key. And **the caches never evicted**, so a piece whose key
varied per bar grew them for as long as the process ran.

Measured on `41af9a4`, one rebuild per bar through a 400-bar set on an 8×32
grid:

    one int seed, cached                  0.10 ms at bar 400      39 ms total
    an explicit grid, never cached       37.59 ms at bar 400    7641 ms total

Nearly 400× a bar, and 7.6 seconds of event-loop time across the set — between
pulses, where a pulse at 120 BPM is 20.8 ms. After 1,200 bars with a fresh seed
each, the caches held 1,200 and 1,601 entries.

The remaining cost here is a *correctness* question, not a caching one: an
unseeded `initial_state="random"` draws a new seed every bar, so each bar is a
fresh evolution from generation 0 and there is nothing to reuse. That is #3072.
"""

import contextlib
import typing

import pytest

import subsequence
import subsequence.sequence_utils


def _2d (generation: int, seed: typing.Any, rows: int = 4, cols: int = 16) -> typing.List[typing.List[int]]:

	return subsequence.sequence_utils.generate_cellular_automaton_2d(
		rows = rows, cols = cols, generation = generation, rule = "B3/S23",
		seed = seed, density = 0.4,
	)


@contextlib.contextmanager
def _counting_steps () -> typing.Iterator[typing.Callable[[], int]]:

	"""Count evolution steps rather than timing them.

	A stopwatch here would be flaky on a loaded machine, and the step count is
	the thing that actually grew: a rebuild replaying from generation 0 does
	one step per generation, every bar.
	"""

	steps = 0
	real_step = subsequence.sequence_utils._ca_2d_step

	def counting (*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
		nonlocal steps
		steps += 1
		return real_step(*args, **kwargs)

	subsequence.sequence_utils._ca_2d_step = counting		# type: ignore[assignment]

	try:
		yield lambda: steps
	finally:
		subsequence.sequence_utils._ca_2d_step = real_step	# type: ignore[assignment]


def _1d (generation: int, seed: int, steps: int = 16) -> typing.List[int]:

	return subsequence.sequence_utils.generate_cellular_automaton_1d(
		steps = steps, generation = generation, rule = 30, seed = seed,
	)


@pytest.fixture (autouse = True)
def _empty_caches () -> typing.Iterator[None]:

	"""Each test starts from empty, since the caches are module-level."""

	subsequence.sequence_utils._ca_1d_cache.clear()
	subsequence.sequence_utils._ca_2d_cache.clear()

	yield

	subsequence.sequence_utils._ca_1d_cache.clear()
	subsequence.sequence_utils._ca_2d_cache.clear()


# ---------------------------------------------------------------------------
# An explicit starting grid is cached like any other
# ---------------------------------------------------------------------------

def test_an_explicit_starting_grid_is_cached () -> None:

	"""Asking twice for the same generation must do the work once.

	This asserted only that a cache ENTRY appeared, which a break that stopped
	the cache being *read* passed happily: the entry was still written, just
	never used. Doing no work the second time is the behaviour.
	"""

	grid = [[(r + c) % 2 for c in range(16)] for r in range(4)]

	with _counting_steps() as count:
		_2d(10, grid)
		first = count()

		_2d(10, grid)
		repeat = count() - first

	assert first == 10, f"the first call took {first} evolution steps, not 10"
	assert repeat == 0, (
		f"asking for the same generation again took {repeat} steps — an explicit "
		f"starting grid is not being read back from the cache"
	)


def test_a_caller_may_mutate_the_grid_it_is_handed () -> None:

	"""What comes back is the caller's own, not a window into the cache.

	`cellular_2d` hands the grid to pattern code, which is free to do what it
	likes with it. The guarantee lives in the cache *write*, which stores a
	copy — there used to be a second copy on the read as well, guarding
	nothing, and a break removing it failed no test until this one.
	"""

	grid = [[0 for _ in range(16)] for _ in range(4)]
	for col in (6, 7, 8):
		grid[1][col] = 1

	first = _2d(3, grid)
	expected = [row[:] for row in first]

	assert any(any(row) for row in first), "the pattern died out, so mutating it proves nothing"

	for row in first:
		for index in range(len(row)):
			row[index] = 1

	again = _2d(3, grid)

	assert again == expected, (
		f"a caller mutating the grid it was given corrupted the cache: {again}"
	)


def test_a_cached_explicit_grid_advances_instead_of_replaying () -> None:

	"""Generation 11 must cost one step from the cached 10, not eleven from scratch.

	Counted rather than timed: a stopwatch here would be a flaky test on a
	loaded machine, and the number of evolution steps is the thing that
	actually grew.
	"""

	grid = [[(r + c) % 2 for c in range(16)] for r in range(4)]

	with _counting_steps() as count:
		_2d(10, grid)
		after_first = count()

		_2d(11, grid)
		advancing = count() - after_first

	assert after_first == 10, f"the first call took {after_first} steps, not 10"
	assert advancing == 1, (
		f"advancing one generation took {advancing} steps — it is replaying from "
		f"the start rather than continuing from the cache"
	)


def test_a_cached_explicit_grid_still_gives_the_right_answer () -> None:

	"""Caching must not change a note. The control on every speed claim here."""

	grid = [[(r + c) % 2 for c in range(16)] for r in range(4)]

	walked = [_2d(generation, grid) for generation in range(6)]

	subsequence.sequence_utils._ca_2d_cache.clear()

	fresh = [_2d(generation, grid) for generation in range(6)]

	assert walked == fresh, "the cached walk and a cold one disagree"


def test_two_different_grids_do_not_share_an_entry () -> None:

	"""The key is the grid's contents, so a different grid is a different evolution.

	A blinker and a block, both of which B3/S23 keeps alive indefinitely. My
	first attempt used all-ones and a stripe pattern, and both die out to an
	empty grid within one generation — so they genuinely agreed and the test
	failed on its own premise rather than on the code.
	"""

	blinker = [[0 for _ in range(16)] for _ in range(4)]
	for col in (6, 7, 8):
		blinker[1][col] = 1

	block = [[0 for _ in range(16)] for _ in range(4)]
	for row, col in ((1, 3), (1, 4), (2, 3), (2, 4)):
		block[row][col] = 1

	from_blinker = _2d(3, blinker)
	from_block = _2d(3, block)

	assert any(any(row) for row in from_blinker), "the blinker died, so this compares two empty grids"
	assert any(any(row) for row in from_block), "the block died, so this compares two empty grids"

	assert from_blinker != from_block, (
		"two different starting grids produced the same generation 3 — they are "
		"sharing a cache entry"
	)

	assert len(subsequence.sequence_utils._ca_2d_cache) == 2


def test_a_grid_that_differs_in_one_cell_is_a_different_evolution () -> None:

	"""A content key has to be the whole content."""

	first = [[0 for _ in range(16)] for _ in range(4)]
	second = [row[:] for row in first]
	second[2][7] = 1

	_2d(1, first)
	_2d(1, second)

	assert len(subsequence.sequence_utils._ca_2d_cache) == 2, (
		"two grids differing in one cell collapsed to one cache entry"
	)


# ---------------------------------------------------------------------------
# The caches are bounded
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dimension", ["1d", "2d"])
def test_the_cache_does_not_grow_past_its_limit (dimension: str) -> None:

	"""A fresh key per bar used to add an entry per bar, for ever."""

	limit = subsequence.sequence_utils._CA_CACHE_ENTRIES

	for bar in range(limit * 4):
		if dimension == "1d":
			_1d(1, seed = 1_000 + bar)
		else:
			_2d(1, seed = 1_000 + bar)

	cache = (
		subsequence.sequence_utils._ca_1d_cache if dimension == "1d"
		else subsequence.sequence_utils._ca_2d_cache
	)

	assert len(cache) > 0, "nothing was cached, so the bound below proves nothing"
	assert len(cache) <= limit, (
		f"the {dimension} cache holds {len(cache)} entries after {limit * 4} distinct "
		f"configurations, with a limit of {limit}"
	)


def test_the_configuration_a_piece_keeps_using_survives_eviction () -> None:

	"""Least-recently-used, not least-recently-added.

	A piece with one steady CA beside something churning through seeds must
	not have its own entry thrown away — that would be the worst of both, a
	bounded cache that never hits.
	"""

	limit = subsequence.sequence_utils._CA_CACHE_ENTRIES

	steady = 7777

	for bar in range(limit * 3):
		_2d(bar + 1, seed = steady)			# the piece's own CA, every bar
		_2d(1, seed = 90_000 + bar)			# something taking a new seed each bar

	cached = subsequence.sequence_utils._ca_2d_cache.get((4, 16, "B3/S23", steady, 0.4))

	assert cached is not None, "the steadily-used configuration was evicted"
	assert cached[0] == limit * 3, f"it was kept but not advanced: generation {cached[0]}"


def test_a_read_counts_as_use () -> None:

	"""Reading an entry must move it to the newest end, or an LRU is a FIFO."""

	limit = subsequence.sequence_utils._CA_CACHE_ENTRIES
	cache = subsequence.sequence_utils._ca_2d_cache

	for index in range(limit):
		cache.put(("key", index), (0, [[0]]))

	# Touch the oldest, then push one more in.
	assert cache.get(("key", 0)) is not None

	cache.put(("key", limit), (0, [[0]]))

	assert cache.get(("key", 0)) is not None, "the entry just read was evicted anyway"
	assert cache.get(("key", 1)) is None, "the wrong entry was evicted"


# ---------------------------------------------------------------------------
# Nothing about the caching changes what is generated
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("generation", [0, 1, 5, 20])
def test_an_int_seeded_walk_is_unchanged (generation: int) -> None:

	"""The control: the cached path was already right and must stay right."""

	cold = _2d(generation, seed = 4242)

	subsequence.sequence_utils._ca_2d_cache.clear()

	warm_up = [_2d(step, seed = 4242) for step in range(generation + 1)]

	assert warm_up[-1] == cold, (
		"walking generation by generation disagrees with jumping straight there"
	)
