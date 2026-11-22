
import subsequence.constants.instruments.gm_drums as gm_drums
from subsequence.motifs import Motif
from subsequence.sequence_utils import weighted_choice


DRUMS_CHANNEL = 10

groove = subsequence.Groove.from_agr(r"C:\Users\user\Documents\Ableton\User Library\Grooves\toody terry.agr", grid=0.25)

sn = "snare_1"
cp = "hand_clap"
kc = "kick_1"
hc = "hi_hat_closed"
ho = "hi_hat_open"
rs = "side_stick"
cy = "ride_bell"
cr = "crash_1"

# One bar of the main beat, kept as separate voices so a fill or effect can solo one.
KICK = Motif.hits(kc, [0, 1, 2, 3], length=4)                              # quarter notes
HATS = Motif.hits(hc, [s / 4 for s in range(16)], length=4, durations=0.25)  # sixteenth notes
SNARE = Motif.hits(sn, [1, 3], length=4)                                   # snare on beats 2 and 4 (backbeat)

# What the closed hat does in each bar, with weights - drawn fresh per bar.
HAT_FEELS = [
	(HATS, 5),                                               # sixteenths
	(Motif.hits(hc, [s / 2 for s in range(8)], length=4), 2),  # eighths
	(Motif.hits(hc, [0.5, 1.5, 2.5, 3.5], length=4), 2),     # offbeats only
	(Motif.empty(), 2),                                      # no hat
]

# Bar (1-based) -> how long its fill may be, in beats, with weights.
FILLS = {
	4: [(1, 2), (2, 1)],
	8: [(2, 2), (1, 1), (4, 1)],
}

# Which kind of fill to play, with weights - drawn fresh every cycle.
FILL_KINDS = [
	("stutter", 0),        # repetition: a slice of the beat looped
	("call_response", 3),  # snare figure answered by the same rhythm on clap, rim or open hat
	("gate", 1),           # beat + snare 16ths chopped by random gating
	("mute", 10),           # abrupt silence
	("solo", 0),           # one voice of the beat alone
	("ghost", 9),          # kick + ghost snares + accent pickup
	("roll", 3),           # snare 8ths ratcheted into a crescendo roll
]

# Bars without a fill sometimes get an effect over part of the bar.
EFFECT_CHANCE = 0.1                          # chance per bar
EFFECT_LENGTHS = [(1, 3), (2, 2)]            # beats, with weights; starts on a random beat
EFFECTS = [
	("stutter", 6),        # repeat: a slice of the bar looped
	("gate", 7),           # chop: the bar gated by random dropout
	("solo", 2),           # one voice alone
	("mute", 1),           # abrupt silence
]


def fill_motif (p, kind, start, n, voices):

	"""An n-beat fill or effect starting at `start`, grooved in place, as a Motif (None = silence).

	`voices` is the bar's own [kick, snare, hat] so the fill works on what that bar plays.
	"""

	if kind == "mute":
		return None

	s = p.scratch(f"fill_{start}")
	r = s.rng
	bar = voices[0].stack(voices[1]).stack(voices[2])
	off = start % 4
	under = bar.slice(off, off + n)                                        # the beat this fill replaces

	if kind == "stutter":
		cell = r.choice([c for c in (0.25, 0.5, 1) if c <= n])
		at = r.randrange(4)                                                # cell starts on a beat, so it carries the kick
		s.motif(Motif.join([bar.slice(at, at + cell)] * int(n / cell)), beat=start)

	elif kind == "call_response":
		half = n / 2
		steps = int(half * 4)
		call = Motif.euclidean(pulses=r.randint(max(1, steps // 2), steps), steps=steps, pitch=sn, length=half)
		response = call.reverse() if r.random() < 0.5 else call
		s.motif(call.then(response.pitched(r.choice([cp, rs, ho]))), beat=start)

	elif kind == "gate":
		s.motif(under.stack(Motif.hits(sn, [i / 4 for i in range(n * 4)], length=n, velocities=80)), beat=start)
		s.dropout(r.uniform(0.25, 0.5))

	elif kind == "solo":
		s.motif(r.choice(voices).slice(off, off + n), beat=start)

	elif kind == "ghost":
		s.motif(voices[0].slice(off, off + n).stack(Motif.hits(sn, [n - 0.25], length=n, velocities=115)), beat=start)
		s.ghost_fill(sn, density=0.6, velocity=(25, 55), bias="sixteenths")

	elif kind == "roll":
		hits = n * 2
		s.motif(Motif.hits(sn, [i / 2 for i in range(hits)], length=n, durations=0.5, velocities=s.build_velocity_ramp(50, 120, "ease_in", grid=hits)), beat=start)

	s.groove(groove, strength=1.0)

	if kind == "roll":
		s.ratchet(r.choice([2, 3, 4]), pitch=sn)                          # after the groove, so each roll moves with its note

	return s.capture(start, n)


@composition.pattern(channel=DRUMS_CHANNEL, beats=32, drum_note_map=gm_drums.GM_DRUM_MAP)
def drums (p):

	plan = []

	for bar in range(1, 9):
		voices = [KICK, SNARE, weighted_choice(HAT_FEELS, p.rng)]
		beat = voices[0].stack(voices[1]).stack(voices[2])
		bar_start = (bar - 1) * 4

		if bar in FILLS:                                                   # fill at the end of the bar
			kind, n = weighted_choice(FILL_KINDS, p.rng), weighted_choice(FILLS[bar], p.rng)
			off = 4 - n
		elif p.rng.random() < EFFECT_CHANCE:                               # effect somewhere in the bar
			kind, n = weighted_choice(EFFECTS, p.rng), weighted_choice(EFFECT_LENGTHS, p.rng)
			off = p.rng.randrange(4 - n + 1)
		else:
			kind, n, off = None, 0, 4

		if off > 0:
			p.motif(beat.slice(0, off), beat=bar_start)
		if off + n < 4:
			p.motif(beat.slice(off + n, 4), beat=bar_start + off + n)
		if kind:
			plan.append((kind, bar_start + off, n, voices))

	p.hit(cr, [0])                    # crash on the first beat of every 32
	p.groove(groove, strength=1.0)

	for kind, start, n, voices in plan:
		fill = fill_motif(p, kind, start, n, voices)
		if fill is not None:
			p.motif(fill, beat=start)
