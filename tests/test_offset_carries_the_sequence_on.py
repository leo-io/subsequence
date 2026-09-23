"""thue_morse and lsystem take offset=, so a part can walk on along its sequence (#3470, Simon's call on #3423).

Both played the same bar every cycle: thue_morse always took the sequence's
first values, and lsystem re-expanded its string and placed it from the first
symbol.  Over 32 bars each gave one distinct bar.  Now ``offset=`` starts
further in, and 0 keeps today's sound.  For thue_morse it indexes the infinite
sequence.  For lsystem the expanded string is a loop and offset says where on
it the bar starts, which gives ``spacing=None`` - where the whole string already
fills the bar - a meaning: the bar holds all of it, turned.
"""

import typing

import subsequence
import subsequence.pattern
import subsequence.pattern_builder
import subsequence.sequence_utils

import pytest

FIBONACCI = {"A": "AB", "B": "A"}

Bar = typing.Tuple[typing.Tuple[int, int], ...]


def _bar (build: typing.Callable[[subsequence.pattern_builder.PatternBuilder], typing.Any], cycle: int = 0, grid: int = 16) -> Bar:

	"""What one bar plays: (pulse, pitch) for every note, in order."""

	pattern = subsequence.pattern.Pattern(channel=9, length=grid / 4)
	build(subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=cycle, default_grid=grid))

	return tuple(sorted((position, note.pitch) for position, step in pattern.steps.items() for note in step.notes))


def _thue_morse_value (index: int) -> int:

	return bin(index).count("1") % 2


# --- thue_morse ---


def test_the_kernel_starts_offset_values_in () -> None:

	"""Against the sequence's own definition, and the values the kernel's docstring gives - never the kernel itself."""

	for offset in (1, 5, 16, 100):
		assert subsequence.sequence_utils.thue_morse(16, offset=offset) == [_thue_morse_value(index) for index in range(offset, offset + 16)]

	assert subsequence.sequence_utils.thue_morse(16, offset=16) == [1, 0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0, 0, 1]


def test_the_kernel_refuses_a_negative_offset () -> None:

	with pytest.raises(ValueError, match="offset"):
		subsequence.sequence_utils.thue_morse(16, offset=-1)


def _mirror (bar: Bar) -> Bar:

	"""Single-pitch mode's mirror: hits where the rests were, on a 16-step bar of sixteenths."""

	hits = {position for position, _ in bar}

	return tuple((position, 36) for position in range(0, 96, 6) if position not in hits)


def test_carried_on_a_bar_at_a_time_the_bars_fall_in_thue_morse_order () -> None:

	"""On 16 steps each bar is the first or its mirror, the choice itself following the sequence."""

	first = _bar(lambda p: p.thue_morse(36))

	for cycle in range(16):
		played = _bar(lambda p: p.thue_morse(36, offset=p.cycle * p.grid), cycle=cycle)
		assert played == (_mirror(first) if _thue_morse_value(cycle) else first), cycle


def test_the_mirror_swaps_the_two_pitches () -> None:

	"""In two-pitch mode the second bar carried on is the first with kick and snare swapped."""

	first = _bar(lambda p: p.thue_morse(36, pitch_b=38, offset=p.cycle * p.grid), cycle=0)
	second = _bar(lambda p: p.thue_morse(36, pitch_b=38, offset=p.cycle * p.grid), cycle=1)

	assert second == tuple((position, 38 if pitch == 36 else 36) for position, pitch in first)


@pytest.mark.parametrize(("grid", "bars"), [(8, 2), (12, 6), (16, 2), (24, 6), (32, 2)])
def test_how_many_bars_carrying_on_gives (grid: int, bars: int) -> None:

	"""The docstring's figures: two on 8, 16 or 32 steps, six on 12 or 24, over 64 bars."""

	assert len({_bar(lambda p: p.thue_morse(36, offset=p.cycle * p.grid), cycle=cycle, grid=grid) for cycle in range(64)}) == bars


def test_sliding_a_step_a_bar_gives_46_bars_in_64 () -> None:

	assert len({_bar(lambda p: p.thue_morse(36, offset=p.cycle), cycle=cycle) for cycle in range(64)}) == 46


def test_thue_morse_without_offset_plays_the_same_bar () -> None:

	"""A guard, not a fix: the default keeps today's sound.  This passed before #3470 as well."""

	assert len({_bar(lambda p: p.thue_morse(36), cycle=cycle) for cycle in range(8)}) == 1


def test_a_negative_offset_starts_at_the_beginning () -> None:

	"""Clamped to the published floor, as every declared bound is - never an index before the start."""

	assert _bar(lambda p: p.thue_morse(36, offset=-5)) == _bar(lambda p: p.thue_morse(36))


# --- lsystem ---


def _string (generations: int) -> str:

	return subsequence.sequence_utils.lsystem_expand("A", FIBONACCI, generations)


def _as_written (string: str, spacing: typing.Optional[float] = None) -> Bar:

	"""The bar a string plays when placed as it stands: an axiom with no rules, never rewritten."""

	return _bar(lambda p: p.lsystem(pitch_map={"A": 36}, axiom=string, rules={}, generations=0, spacing=spacing, velocity=80))


def _fibonacci (generations: int, offset: int, spacing: typing.Optional[float] = None, cycle: int = 0) -> Bar:

	return _bar(lambda p: p.lsystem(pitch_map={"A": 36}, axiom="A", rules=FIBONACCI, generations=generations, spacing=spacing, velocity=80, offset=offset), cycle=cycle)


def test_offset_turns_the_whole_string_within_the_bar () -> None:

	"""With spacing=None every symbol still plays; the bar starts ``offset`` symbols in."""

	string = _string(6)

	for offset in (1, 5, 20):
		assert _fibonacci(6, offset) == _as_written(string[offset:] + string[:offset]), offset


def test_offset_walks_on_through_the_string_at_a_fixed_spacing () -> None:

	"""Sixteen quarter-beat symbols to the bar: ``offset=16 * c`` plays symbols 16c to 16c + 15."""

	string = _string(8)

	for cycle in range(3):
		assert _fibonacci(8, 16 * cycle, spacing=0.25) == _as_written(string[16 * cycle:16 * cycle + 16], spacing=0.25), cycle


def test_the_walk_wraps_round_to_the_start () -> None:

	"""The 55-symbol word: 48 in, the bar runs off the end and on from its start."""

	string = _string(8)

	assert _fibonacci(8, 48, spacing=0.25) == _as_written(string[48:] + string[:9], spacing=0.25)
	assert _fibonacci(8, 55 + 3, spacing=0.25) == _fibonacci(8, 3, spacing=0.25)


def test_turning_the_six_generation_word_gives_21_bars () -> None:

	"""The docstring's figure: ``offset=p.cycle`` comes round again after 21 bars."""

	bars = [_fibonacci(6, cycle, cycle=cycle) for cycle in range(64)]

	assert len(set(bars)) == 21
	assert bars[21] == bars[0]


def test_lsystem_without_offset_plays_the_same_bar () -> None:

	"""A guard, not a fix: the default keeps today's sound.  This passed before #3470 as well."""

	bars = {_bar(lambda p: p.lsystem(pitch_map={"A": 36}, axiom="A", rules=FIBONACCI, generations=6, velocity=80), cycle=cycle) for cycle in range(8)}

	assert len(bars) == 1


def test_a_negative_lsystem_offset_starts_at_the_beginning () -> None:

	"""lsystem is bounded now, so its floor holds: a loop would otherwise turn backwards."""

	assert _fibonacci(6, -5) == _fibonacci(6, 0)


# --- the catalogue ---


@pytest.mark.parametrize("verb", ["thue_morse", "lsystem"])
def test_offset_is_published_as_a_whole_number_from_zero (verb: str) -> None:

	"""A new key on both entries: a count of steps or symbols, with a floor and no ceiling."""

	parameters = {entry["name"]: entry for entry in subsequence.describe_generator(verb)["parameters"]}
	offset = parameters.get("offset", {})

	assert {key: offset.get(key) for key in ("kind", "min", "max", "step", "default", "required")} == {
		"kind": "number", "min": 0, "max": None, "step": 1, "default": 0, "required": False,
	}
