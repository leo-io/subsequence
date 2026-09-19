"""A figure stepped at a spacing binary cannot hold exactly places each onset once and never one on its end (#2960)."""

import fractions
import math
import pathlib
import typing

import mido
import pytest

import subsequence
import subsequence.pattern
import subsequence.pattern_builder

# Spacings as exact fractions: a third, a sixth, a seventh, a tenth, a fifth,
# two thirds, a twelfth, and the plain sixteenth and eighth for contrast.
SPACINGS = [(1, 3), (1, 6), (1, 7), (1, 10), (1, 5), (2, 3), (1, 12), (1, 4), (1, 2)]
LENGTHS = [1, 2, 3, 4, 6, 8]


def _expected (length: float, spacing: typing.Tuple[int, int]) -> int:

	"""How many onsets fall before *length* beats at *spacing*, counted exactly."""

	return math.ceil(fractions.Fraction(length) / fractions.Fraction(*spacing))


def _builder (length: float) -> typing.Tuple[subsequence.pattern.Pattern, subsequence.pattern_builder.PatternBuilder]:

	pattern = subsequence.pattern.Pattern(channel=0, length=length)

	return pattern, subsequence.pattern_builder.PatternBuilder(pattern, cycle=0)


def _pulses (pattern: subsequence.pattern.Pattern) -> typing.List[int]:

	"""Every placed note's pulse, one entry per note."""

	return sorted(pulse for pulse, step in pattern.steps.items() for _ in step.notes)


@pytest.mark.parametrize("length", LENGTHS)
@pytest.mark.parametrize("spacing", SPACINGS, ids=lambda s: f"{s[0]}/{s[1]}")
@pytest.mark.parametrize("verb", ["repeat", "arpeggio", "add_arpeggio_beats"])
def test_every_onset_falls_once_and_before_the_end (verb: str, spacing: typing.Tuple[int, int], length: int) -> None:

	"""The count is exact, and no note sits on (or past) the pattern's last pulse."""

	pattern, p = _builder(length)
	step = spacing[0] / spacing[1]

	if verb == "repeat":
		p.repeat(42, spacing=step)
	elif verb == "arpeggio":
		p.arpeggio([60, 64, 67], spacing=step)
	else:
		pattern.add_arpeggio_beats([60, 64, 67], spacing_beats=step)

	pulses = _pulses(pattern)

	assert len(pulses) == _expected(length, spacing)
	assert pulses[-1] < length * 24


def test_a_positioned_triplet_arpeggio_stays_in_its_chord_s_window () -> None:

	"""Two chords a half-bar each: the first chord's triplets end before the second chord's first note."""

	pattern, p = _builder(4)
	p.arpeggio([60, 64, 67], spacing=1 / 3, beat=0, span=2)
	p.arpeggio([62, 65, 69], spacing=1 / 3, beat=2, span=2)

	at_the_change = sorted(note.pitch for note in pattern.steps[48].notes)

	assert at_the_change == [62]
	assert len(_pulses(pattern)) == 12


def test_a_two_bar_triplet_hat_line_does_not_double_the_downbeat (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Rendered over three cycles, every bar line carries exactly one hat."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	@composition.pattern(channel=10, bars=2)
	def hats (p: typing.Any) -> None:
		p.repeat(42, spacing=1 / 3, duration=0.1)

	path = str(tmp_path / "hats.mid")
	composition.render(bars=6, filename=path)

	now = 0
	onsets = []

	for message in mido.MidiFile(path).tracks[0]:
		now += message.time
		if message.type == "note_on" and message.velocity > 0:
			onsets.append(now)

	assert len(onsets) == 72
	assert len(set(onsets)) == 72


def test_an_onset_float_noise_puts_a_hair_before_the_end_is_not_placed_on_it () -> None:

	"""49 × (1/49) is 0.9999999999999999 in binary: that onset would round onto the next cycle's first pulse, so it is not placed."""

	assert 49 * (1 / 49) < 1

	pattern = subsequence.pattern.Pattern(channel=0, length=1)
	pattern.add_arpeggio_beats([60], spacing_beats=1 / 49)
	pulses = _pulses(pattern)

	assert len(pulses) == 49
	assert pulses[-1] < 24
