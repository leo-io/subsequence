"""Perlin noise is actually noise, and actually spans 0 to 1 (#3011).

The gradient hash was `(a*pos + b*seed + 12345) & 0x7FFFFFFF` with every
multiplier congruent to 1 mod 4, so the bottom bits of the result were the
bottom bits of the input.  `perlin_2d` picks its gradient with `h & 3`, so the
whole field was decided by `seed % 4`: four fields in total, and the same noise
back again every four seeds.  `perlin_1d` came out an alternation rather than a
wander.  And a continuous gradient meant neither reached its documented ends —
the real spans were [0.23, 0.82] and [0.22, 0.77] — so `examples/emergence.py`'s
lightning, at `chaos_spark > 0.92`, never once fired.

Decision 6 of #2991: fix it in place, with a real integer hash and a true 0–1.
"""

import statistics
import typing

import pytest

import subsequence.sequence_utils


def _autocorrelation (values: typing.Sequence[float], lag: int) -> float:

	"""How much each sample tells you about the one *lag* later."""

	mean = statistics.fmean(values)
	centred = [value - mean for value in values]
	spread = sum(c * c for c in centred)

	if spread == 0.0:
		return 0.0

	return sum(centred[i] * centred[i + lag] for i in range(len(centred) - lag)) / spread


def _field (seed: int, samples: int = 32) -> typing.Tuple[float, ...]:

	"""A signature of the 2-D field a seed produces."""

	return tuple(
		round(subsequence.sequence_utils.perlin_2d(i * 0.37, i * 0.21, seed = seed), 9)
		for i in range(samples)
	)


# ---------------------------------------------------------------------------
# A seed is a seed
# ---------------------------------------------------------------------------

def test_every_seed_gives_its_own_field () -> None:

	"""There were four fields in total, one per `seed % 4`."""

	fields = {_field(seed) for seed in range(64)}

	assert len(fields) == 64, f"64 seeds produced {len(fields)} distinct fields"


def test_the_seed_does_not_repeat_itself () -> None:

	"""`perlin_2d` came back to the same field every four seeds."""

	first = _field(0)

	for seed in range(1, 65):
		assert _field(seed) != first, f"seed {seed} is seed 0 again"


def test_two_seeds_a_stone_apart_are_not_the_same_walk () -> None:

	"""Seeds 63 apart used to be near-identical in 1-D."""

	base = [subsequence.sequence_utils.perlin_1d(i * 0.08, seed = 0) for i in range(200)]

	closest = min(
		(
			sum(
				abs(base[i] - subsequence.sequence_utils.perlin_1d(i * 0.08, seed = other))
				for i in range(200)
			),
			other,
		)
		for other in range(1, 128)
	)

	assert closest[0] > 5.0, f"seed {closest[1]} differs from seed 0 by only {closest[0]:.4f} over 200 samples"


@pytest.mark.parametrize("slot", [0, 1, 2])
def test_one_flipped_input_bit_moves_half_the_output_bits (slot: int) -> None:

	"""Avalanche, the property the old hash had none of — at EVERY bit position.

	`(a*pos + b*seed + 12345)` with multipliers congruent to 1 mod 4 left the
	bottom two bits of the output equal to the bottom two of the input, which
	is the whole of `perlin_2d`'s gradient choice.

	The high bits are where this is easiest to get wrong and hardest to see: a
	multiply carries bits upward only, so a mixer without the finalising
	xor-shifts moves ONE output bit for a flip of input bit 31, and a test that
	looks at the low sixteen never notices.
	"""

	for bit in range(32):

		moved = []

		for n in range(200):
			arguments = [7, 13, n]
			before = subsequence.sequence_utils._noise_hash(*arguments)
			arguments[slot] ^= 1 << bit
			moved.append(bin(before ^ subsequence.sequence_utils._noise_hash(*arguments)).count("1"))

		average = statistics.fmean(moved)

		assert 12 < average < 20, \
			f"flipping bit {bit} of argument {slot} moves {average:.1f} of 32 output bits"


def test_the_bottom_bits_are_not_the_bottom_bits_of_the_seed () -> None:

	"""`perlin_2d` reads `h & 3`, so these three bits ARE the field it draws."""

	for mask, name in ((3, "two"), (7, "three")):
		counts = [0] * (mask + 1)

		for seed in range(4000):
			counts[subsequence.sequence_utils._noise_hash(1, 2, seed) & mask] += 1

		expected = 4000 / (mask + 1)

		assert all(abs(count - expected) < expected * 0.15 for count in counts), \
			f"the bottom {name} bits fall {counts} over 4000 seeds"


def test_the_bottom_bits_do_not_track_the_seeds_own_bottom_bits () -> None:

	"""Evenly spread is not enough — the old hash was even AND a copy of the input.

	`h & 3` was `seed & 3`, so it hit each value a quarter of the time and still
	gave four fields.  What matters is that knowing the seed's low bits tells
	you nothing about the hash's.
	"""

	joint = [[0] * 8 for _ in range(8)]

	for seed in range(8000):
		joint[seed & 7][subsequence.sequence_utils._noise_hash(1, 2, seed) & 7] += 1

	busiest = max(max(row) for row in joint)

	assert busiest < 250, \
		f"one low-bit pairing came up {busiest} times in 8000, where independence gives about 125"


# ---------------------------------------------------------------------------
# It reaches the ends it promises
# ---------------------------------------------------------------------------

def test_one_dimensional_noise_covers_nought_to_one () -> None:

	"""The documented range was a promise the code never kept: [0.22, 0.77]."""

	values = [
		subsequence.sequence_utils.perlin_1d(i * 0.017, seed = seed)
		for seed in range(30) for i in range(1500)
	]

	assert min(values) < 0.01, f"the floor was {min(values):.4f}"
	assert max(values) > 0.99, f"the ceiling was {max(values):.4f}"


def test_two_dimensional_noise_covers_nought_to_one () -> None:

	"""Its extremes live at cell centres, where all four corners slope away."""

	values = [
		subsequence.sequence_utils.perlin_2d(i + 0.5, j + 0.5, seed = seed)
		for seed in range(20) for i in range(20) for j in range(20)
	]

	assert min(values) < 0.01, f"the floor was {min(values):.4f}"
	assert max(values) > 0.99, f"the ceiling was {max(values):.4f}"


def test_nothing_escapes_the_range () -> None:

	"""A real 0–1 means both ends, and nothing outside them."""

	for seed in range(20):
		for i in range(300):
			one = subsequence.sequence_utils.perlin_1d(i * 0.031, seed = seed)
			two = subsequence.sequence_utils.perlin_2d(i * 0.031, i * 0.017, seed = seed)

			assert 0.0 <= one <= 1.0
			assert 0.0 <= two <= 1.0


def test_a_sequence_mapped_to_velocities_reaches_both_ends () -> None:

	"""`50 + round(v * 25)` came out 51–64 where the example promised 50–75."""

	velocities = [
		50 + round(value * 25)
		for seed in range(40)
		for value in subsequence.sequence_utils.perlin_1d_sequence(0.0, 0.08, 800, seed = seed)
	]

	assert min(velocities) == 50, f"the quietest was {min(velocities)}"
	assert max(velocities) == 75, f"the loudest was {max(velocities)}"


# ---------------------------------------------------------------------------
# It wanders rather than oscillating
# ---------------------------------------------------------------------------

def test_a_walk_does_not_simply_alternate () -> None:

	"""At half-integer steps the lag-2 autocorrelation was −0.945 — a sine, not noise."""

	walk = [subsequence.sequence_utils.perlin_1d(i * 0.5, seed = 42) for i in range(4000)]

	assert abs(_autocorrelation(walk, 2)) < 0.75, \
		f"lag-2 autocorrelation is {_autocorrelation(walk, 2):+.3f}"


@pytest.mark.parametrize("seed", [11, 3, 77])
def test_cell_centres_show_independent_gradients (seed: int) -> None:

	"""The signature of gradients drawn independently, which is the thing at issue.

	A cell centre is a quarter of (this gradient minus the next), so neighbouring
	centres share one gradient with opposite signs and MUST correlate at −0.5 —
	that number is Perlin working, not Perlin broken.  What independence shows up
	as is everything past lag 1 being nothing: two centres a cell apart share no
	gradient at all.  The old hash gave −0.945 at lag 2, where zero belongs.
	"""

	walk = [subsequence.sequence_utils.perlin_1d(i + 0.5, seed = seed) for i in range(6000)]

	assert -0.62 < _autocorrelation(walk, 1) < -0.38, \
		f"lag-1 is {_autocorrelation(walk, 1):+.3f}, where sharing one gradient implies −0.5"

	for lag in (2, 3, 4):
		assert abs(_autocorrelation(walk, lag)) < 0.1, \
			f"lag-{lag} is {_autocorrelation(walk, lag):+.3f}, but those cells share no gradient"


def test_the_values_cluster_in_the_middle () -> None:

	"""Two gradients would pile 8% of the values into the top tenth; the docstrings
	promise a threshold means something, and a flat or bimodal field breaks that."""

	values = [
		subsequence.sequence_utils.perlin_1d(i * 0.013, seed = seed)
		for seed in range(30) for i in range(1500)
	]

	total = len(values)
	middle = sum(1 for v in values if 0.35 <= v <= 0.65) / total
	top = sum(1 for v in values if v > 0.92) / total

	assert middle > 0.4, f"only {middle:.1%} of values are near the middle"
	assert 0.001 < top < 0.03, f"{top:.2%} of values are above 0.92 — a threshold there means nothing"


# ---------------------------------------------------------------------------
# The shape it always had
# ---------------------------------------------------------------------------

def test_it_is_still_smooth () -> None:

	"""However random the lattice, the walk between points must not jump."""

	for seed in (0, 5, 99):
		walk = [subsequence.sequence_utils.perlin_1d(i * 0.01, seed = seed) for i in range(2000)]
		biggest = max(abs(b - a) for a, b in zip(walk, walk[1:]))

		assert biggest < 0.05, f"seed {seed} jumps by {biggest:.4f} in one hundredth of a cell"


def test_it_is_still_the_same_answer_for_the_same_question () -> None:

	"""Noise a piece can be seeded against has to be a pure function."""

	for seed in (0, 7, 1234):
		assert subsequence.sequence_utils.perlin_1d(3.25, seed = seed) == subsequence.sequence_utils.perlin_1d(3.25, seed = seed)
		assert subsequence.sequence_utils.perlin_2d(3.25, 1.5, seed = seed) == subsequence.sequence_utils.perlin_2d(3.25, 1.5, seed = seed)


def test_a_sequence_is_the_same_as_calling_one_at_a_time () -> None:

	"""`perlin_1d_sequence` documents itself as exactly that."""

	one_at_a_time = [subsequence.sequence_utils.perlin_1d(0.3 + i * 0.07, seed = 5) for i in range(40)]

	assert subsequence.sequence_utils.perlin_1d_sequence(0.3, 0.07, 40, seed = 5) == one_at_a_time


def test_a_negative_position_is_noise_too () -> None:

	"""`math.floor` handles it; the hash has to as well, and a mask on a negative
	number is where an integer hash most easily goes wrong."""

	left = [subsequence.sequence_utils.perlin_1d(-i * 0.08, seed = 3) for i in range(1, 600)]

	assert all(0.0 <= v <= 1.0 for v in left)
	assert len({round(v, 6) for v in left}) > 400, "the left half of the field repeats itself"


# ---------------------------------------------------------------------------
# What the example asks for
# ---------------------------------------------------------------------------

def test_the_emergence_example_lightning_can_strike () -> None:

	"""`chaos_spark > 0.92` fired exactly zero times in the whole field."""

	cycles = 20000
	sparks = [subsequence.sequence_utils.perlin_1d(cycle * 0.13, seed = 6) for cycle in range(cycles)]

	struck = sum(1 for spark in sparks if spark > 0.92)

	assert struck > 0, "the lightning still never strikes"
	assert struck / cycles < 0.03, \
		f"lightning on {struck / cycles:.2%} of cycles is not the rare burst it is documented as"


def test_the_emergence_example_swarm_snare_can_fire () -> None:

	"""`chaos_spark > 0.78`, also dead, and also further gated by the bar."""

	cycles = 20000
	sparks = [subsequence.sequence_utils.perlin_1d(cycle * 0.13, seed = 6) for cycle in range(cycles)]

	fired = sum(1 for spark in sparks if spark > 0.78)

	assert fired > 0
	assert 0.005 < fired / cycles < 0.20, f"{fired / cycles:.2%} of cycles"
