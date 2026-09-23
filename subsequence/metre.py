"""What a time signature means: how long its bar lasts, what its counter counts, and where it accents.

A time signature is ``(beats, unit)`` as written, so ``(6, 8)`` is six eighth
notes to the bar.  Everywhere else in Subsequence a beat is a quarter note, so a
bar lasts ``beats × 4 / unit`` of them: ``(4, 4)`` is 4.0, ``(6, 8)`` is 3.0 and
``(7, 8)`` is 3.5.

This module is the one place that sum is done.  ``tests/test_metre.py`` fails on
code anywhere else in the package that reads a time signature by index.
"""

import itertools
import typing

import subsequence.constants.pulses


# A thirty-second note is three pulses at 24 PPQN, so every one of these units,
# and every bar made of them, is a whole number of pulses.
UNITS: typing.Tuple[int, ...] = (1, 2, 4, 8, 16, 32)


def check (time_signature: typing.Any) -> typing.Tuple[int, int]:

	"""Return *time_signature* as a ``(beats, unit)`` tuple, or raise ValueError saying what is wrong with it."""

	try:
		beats, unit = time_signature
	except (TypeError, ValueError):
		raise ValueError(f"A time signature is (beats, unit), such as (4, 4) or (6, 8) - got {time_signature!r}") from None

	if isinstance(beats, bool) or not isinstance(beats, int) or beats < 1:
		raise ValueError(f"A time signature's beat count must be a whole number, at least 1 - got {beats!r}")

	if isinstance(unit, bool) or not isinstance(unit, int) or unit not in UNITS:
		raise ValueError(f"A time signature's unit must be 1, 2, 4, 8, 16 or 32 - got {unit!r}")

	return beats, unit


def bar_beats (time_signature: typing.Any) -> float:

	"""How many beats (quarter notes) one bar of *time_signature* lasts: 3.0 for ``(6, 8)``."""

	beats, unit = check(time_signature)

	return beats * 4 / unit


def pulses_per_bar (time_signature: typing.Any, pulses_per_beat: int = subsequence.constants.pulses.MIDI_QUARTER_NOTE) -> int:

	"""How many pulses one bar of *time_signature* lasts: 84 for ``(7, 8)``."""

	return subsequence.constants.pulses.beats_to_pulses(bar_beats(time_signature), pulses_per_beat)


def pulses_per_unit (time_signature: typing.Any, pulses_per_beat: int = subsequence.constants.pulses.MIDI_QUARTER_NOTE) -> int:

	"""How many pulses one written unit lasts, which is what the beat counter counts: 12 for any ``/8``."""

	_, unit = check(time_signature)

	return subsequence.constants.pulses.beats_to_pulses(4 / unit, pulses_per_beat)


def accent_groups (time_signature: typing.Any) -> typing.Optional[typing.List[int]]:

	"""How a bar's written units group into felt beats, or None where each unit is a beat of its own.

	Only a unit of an eighth or finer groups:

	- **Compound** (a multiple of three, six or more): threes, so ``(6, 8)`` is
	  3+3 and ``(12, 8)`` is 3+3+3+3.
	- **Irregular** (not a multiple of three): twos, with a three at the end when
	  the count is odd, so ``(5, 8)`` is 2+3 and ``(7, 8)`` is 2+2+3.

	Everything else is simple, and returns None: every ``/1``, ``/2`` and ``/4``
	metre, and ``(3, 8)``.
	"""

	beats, unit = check(time_signature)

	if unit < 8:
		return None

	if beats % 3 == 0:
		return [3] * (beats // 3) if beats >= 6 else None

	if beats == 1:
		return [1]

	if beats % 2 == 0:
		return [2] * (beats // 2)

	return [2] * ((beats - 3) // 2) + [3]


def group_starts (time_signature: typing.Any) -> typing.Set[int]:

	"""The written units that begin a felt beat, counted from 0: ``{0, 2, 4}`` for ``(7, 8)``."""

	groups = accent_groups(time_signature)

	if groups is None:
		beats, _ = check(time_signature)
		return set(range(beats))

	return set(itertools.accumulate([0] + groups[:-1]))
