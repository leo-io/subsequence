"""Pulse-based MIDI timing constants.

The sequencer uses **24 pulses per quarter note** (PPQN = 24) as its internal time base.
These constants represent the number of pulses for each standard note duration.

These are used internally by the sequencer engine. Pattern builders work in beats
(see ``subsequence.constants.durations`` for beat-based constants).
"""

# MIDI Standards - number of pulses in each

MIDI_THIRTYSECOND_NOTE = 3
MIDI_SIXTEENTH_NOTE = 6
MIDI_EIGHTH_NOTE = 12
MIDI_QUARTER_NOTE = 24
MIDI_HALF_NOTE = 48
MIDI_WHOLE_NOTE = 96


# Far larger than float noise on any realistic pulse count, far smaller than any
# fraction of a pulse a grid can mean.
_WHOLE_PULSE_TOLERANCE = 1e-6


def beats_to_pulses (beats: float, pulses_per_beat: int = MIDI_QUARTER_NOTE) -> int:

	"""Convert a time in beats to whole pulses, as ``int()`` would — without its float error.

	A third of a beat is not exact in binary floating point, so seven of them
	come to ``55.99999999999999`` pulses and ``int()`` floors that a whole pulse
	early.  A value within a millionth of a pulse of a whole number is taken as
	that number; any other fraction truncates toward zero exactly as ``int()``
	does, so a grid that really falls between pulses (sixteen steps over three
	beats, 4.5 pulses a step) keeps the positions it has always had.

	Every conversion from beats to pulses goes through here —
	``tests/test_pulse_rounding.py`` fails on a bare ``int()`` of one.
	"""

	pulses = beats * pulses_per_beat
	nearest = round(pulses)

	if abs(pulses - nearest) < _WHOLE_PULSE_TOLERANCE:
		return int(nearest)

	return int(pulses)
