"""Analogue step sequencers in a pattern: a Moog 960 through a Moog 962, and an ARP 1601.

The sequencers plugin gives a pattern a small modular system: models of the hardware,
patched together with cables, clocked by the pattern's own steps and played on its MIDI
channel.  Their stages carry on from cycle to cycle, so a line of twelve or twenty-four
steps runs on across a sixteen-step bar instead of starting again with it.

- **Bass:** one Moog 960's three lanes through a Moog 962.  The 962 moves on each time
  the 960 comes back to stage 1, so lanes A, B and C play in turn: a 24-step line from
  one eight-stage sequencer, the way a 960 and a 962 were patched.
- **Lead:** an ARP 1601.  Steps on gate bus 1 sound and steps on bus 2 rest.  Step 13
  is on bus 3 with bus 3 set to reset, so the line is twelve steps long and drifts
  across the bar.  Its quantiser rounds each slider to a semitone, and a knob into its
  CV input moves the whole line every two bars, as a keyboard into a 1601 would.

The bass is written with ``@sequencers.pattern``, which makes the sequencer and plays it
for you; the lead with an ordinary ``@composition.pattern`` and ``sequencers.sequencer(p)``,
which mixes a sequencer with anything else a pattern does.  A voltage of 0 to 1 at a MIDI
out's pitch spans five octaves above its lowest note, so a lane value of ``7 / 60`` is a
fifth.
"""

import logging

import subsequence
import subsequence.constants.durations as dur
import subsequence.constants.midi_notes as midi_notes
import subsequence.plugins.sequencers as sequencers

logging.basicConfig(level=logging.INFO)

BASS_CHANNEL = 6
LEAD_CHANNEL = 4

composition = subsequence.Composition(
	bpm=124,
	key="A"
)

# Semitones above A1 for each of the 960's eight stages: lane A a phrase, lane B its
# answer, lane C its turn.
LANES = {
	"lane_a": [0, 0, 12, 0, 7, 0, 10, 12],
	"lane_b": [3, 3, 15, 3, 10, 3, 12, 15],
	"lane_c": [5, 5, 17, 5, 12, 7, 14, 19],
}

# The 1601's sixteen sliders, in semitones above A2 (its quantiser reaches two octaves),
# and the gate bus each step is on.
STEPS = [0, 12, 3, 0, 7, 0, 10, 12, 0, 15, 7, 5, 0, 0, 0, 0]
BUSES = ["1", "1", "2", "1", "1", "2", "1", "1", "1", "1", "2", "1", "3", "1", "1", "1"]

# Where the keyboard into the 1601's CV input sits, one value per two bars, in semitones.
TRANSPOSE = [0, 0, 5, 7]


@sequencers.pattern(composition, channel=BASS_CHANNEL, steps=16, step_duration=dur.SIXTEENTH)
def bass (seq):

	seq.add(sequencers.moog_960, "960", **{lane: [s / sequencers.SEMITONES for s in semitones] for lane, semitones in LANES.items()})
	seq.add(sequencers.moog_962, "962")
	seq.add(sequencers.midi_out, "midi", lowest=midi_notes.A1)

	seq.patch("clock.out", "960.shift")        # every step moves the 960 on
	seq.patch("960.stage1", "962.shift")       # each time round, the next lane
	seq.patch("960.lane_a", "962.in1")
	seq.patch("960.lane_b", "962.in2")
	seq.patch("960.lane_c", "962.in3")         # with input 3 patched, the 962 counts to three
	seq.patch("962.out", "midi.pitch")
	seq.patch("clock.out", "midi.trigger")


@composition.pattern(channel=LEAD_CHANNEL, steps=16, step_duration=dur.SIXTEENTH)
def lead (p):

	seq = sequencers.sequencer(p)

	seq.add(sequencers.arp_1601, "1601", slider=[s / 24 for s in STEPS], bus=BUSES, bus_3="reset")
	seq.add(sequencers.knob, "keyboard", value=TRANSPOSE[(p.cycle // 2) % len(TRANSPOSE)] / sequencers.SEMITONES)
	seq.add(sequencers.midi_out, "midi", lowest=midi_notes.A2)

	seq.patch("clock.out", "1601.step")
	seq.patch("keyboard.out", "1601.cv_in")
	seq.patch("1601.quantised_a", "midi.pitch")
	seq.patch("1601.clocked_bus1", "midi.trigger")    # bus 1 and the clock together: bus 2 rests

	seq.play()


if __name__ == "__main__":

	composition.play()
