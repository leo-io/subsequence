"""minimalme: a 16-bar (64-beat) elaborated minimal techno loop.  Hot-swapped on every save.

G# aeolian, 124 BPM.  Four four-bar cells (A, A', B, A'') turn over on bar 16.
Parts are added goal by goal; see brief.md.
"""

import subsequence


S = subsequence.Section

# One section, one seamless loop.
FORM = subsequence.Form([S("loop", 16)])

composition.form(FORM, loop=True)  # a seamless loop: bar 17 is bar 1 again
composition.data["form_bars"] = 16

import subsequence.constants.instruments.gm_drums as gm_drums
import subsequence.constants.midi_notes as notes
import subsequence.sequence_utils as su


DRUMS_CHANNEL = 10
BASS_CHANNEL = 2

BASS_ROOT = notes.GS1

# One groove for every part, so the bass and riff added later swing with the drums.
FEEL = subsequence.Groove.swing(56)

# Four four-bar cells: A (core), A' (density), B (mutated), A'' (drop-out, bar 4 is the gap).
CELL_NAMES = ["A", "A'", "B", "A''"]


def euclid_steps (pulses, rotation=0):

	"""Step indices of a euclidean rhythm on a 16-step bar, rotated by *rotation* steps."""

	onsets = [i for i, on in enumerate(su.generate_euclidean_sequence(16, pulses)) if on]
	return sorted(su.rotate(onsets, rotation, 16))


def cell_state (p):

	"""(cell name, bar within the cell 0-3) from the bar in the 16-bar loop."""

	bar = p.section.bar if p.section else 0
	return CELL_NAMES[(bar // 4) % 4], bar % 4


# Closed hat / perc euclid pulses and rotations per cell.
HAT = {"A": (7, 0), "A'": (9, 0), "B": (5, 2), "A''": (7, 0)}
PERC = {"A": (3, 0), "A'": (5, 0), "B": (3, 5), "A''": (3, 0)}


@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def drums (p):

	cell, bar = cell_state(p)
	gap = cell == "A''" and bar == 3  # the one bar that drops out

	# Kick: four on the floor; the gap leaves only the last quarter.
	# The first kick of each cell is the accent that marks the cell turn (no ramp).
	accent = bar == 0
	kick_steps = [12] if gap else [0, 4, 8, 12]
	p.sequence(steps=kick_steps, pitches="kick_1", velocities=[112 if (accent and s == 0) else 100 for s in kick_steps], durations=0.2)

	# Rim: step 12 in the core, adds step 7 in A', moves to 4 + 12 in B, alone on the gap bar.
	rim = {"A": [12], "A'": [7, 12], "B": [4, 12], "A''": [12]}[cell]
	p.hit_steps("side_stick", rim, velocity=(70, 90))

	if not gap:
		# Off-beat open hat; B drops the last one.
		# Open hat pulse: strong on 2 and 10, soft on 6 and 14.
		open_steps = [2, 6, 10] if cell == "B" else [2, 6, 10, 14]
		p.sequence(steps=open_steps, pitches="hi_hat_open", velocities=[78 if s in (2, 10) else 60 for s in open_steps], durations=0.3)
		pulses, rotation = HAT[cell]
		p.hit_steps("hi_hat_closed", euclid_steps(pulses, rotation), velocity=(40, 62), duration=0.1)
		if cell == "A" and bar == 3:
			# seam 1: hat stutter, a run of 16ths on the last beat, each doubled
			p.hit_steps("hi_hat_closed", [s for s in (12, 13, 14, 15) if s not in euclid_steps(pulses, rotation)], velocity=(40, 62), duration=0.1)
			p.ratchet(2, pitch="hi_hat_closed", steps=[12, 13, 14, 15])
		if cell == "A'":
			p.ghost_fill("hi_hat_closed", density=0.2, velocity=(28, 44), bias="sixteenths")

	# Perc: euclidean tom/conga; the gap bar keeps one pickup hit on step 15.
	if gap:
		p.hit_steps("low_conga", [15], velocity=(60, 75))
	else:
		pulses, rotation = PERC[cell]
		p.hit_steps("low_conga", euclid_steps(pulses, rotation), velocity=(50, 80))
		if cell == "B" and bar == 3:
			# seam 3: stack extra perc on the last beat, on steps the euclid doesn't already hit
			stack = [s for s in (13, 14, 15) if s not in euclid_steps(pulses, rotation)]
			p.hit_steps("low_conga", stack, velocity=(70, 90))

	p.groove(FEEL)


# --- Bass hook: a rolling off-kick figure, three pitches, varied once per loop. ---

BASS_STEPS = [2, 3, 6, 10, 11, 14]  # none on the kick (0 4 8 12)

BASS_RIFF = subsequence.Motif.generate(
	rhythm = [s * 0.25 for s in BASS_STEPS], length = 4.0, scale = "aeolian",
	contour = "valley", pins = {1: 1}, max_pitches = 3, durations = 0.2,
	seed = composition.seed_for("bass"),
)

BASS_RIFF_B = BASS_RIFF.vary(3, seed = composition.seed_for("bass-b"), keep_contour = True)


@composition.pattern(channel=BASS_CHANNEL, beats=4)
def bass (p):

	cell, bar = cell_state(p)

	if cell == "A''" and bar == 3:
		return  # the gap bar

	# Seam 2: the bass cuts out for the last beat of bar 8 (the kick carries on).
	span = 3.0 if (cell == "A'" and bar == 3) else None
	p.motif(BASS_RIFF_B if cell == "B" else BASS_RIFF, span=span, root=BASS_ROOT, velocity=(85, 105))
	p.groove(FEEL)


# --- Riff: onset steps per cell, all on the dead spots (no kick, no bass). ---

RIFF_STEPS = {"A": [7, 9, 13], "A'": [1, 7, 9, 13], "B": [5, 9, 13, 15], "A''": [7, 9, 13]}

MELODY_CHANNEL = 4
RIFF_ROOT = notes.GS3

# Core figure 5 -> b3 -> 1 on the last three notes of every cell; a free pool pitch leads in where there is a fourth note.
CORE = {1: 5, 2: 3, 3: 1}


def make_riff (cell):

	steps = RIFF_STEPS[cell]
	lead = len(steps) - 3
	pins = {lead + k: degree for k, degree in CORE.items()}

	return subsequence.Motif.generate(
		rhythm = [s * 0.25 for s in steps], length = 4.0, scale = "aeolian",
		contour = "descending", pins = pins, max_pitches = 3, durations = 0.3,
		seed = composition.seed_for(f"riff-{cell}"),
	)


RIFFS = {cell: make_riff(cell) for cell in CELL_NAMES}

# Each 4-bar cell: three restatements, then a re-pitched answer bar.  The four cells join into one 16-bar line.
CELL_PHRASES = {
	cell: subsequence.Phrase.develop(RIFFS[cell], bars=4, plan=["a", "a", "a", "b"], seed=composition.seed_for(f"phrase-{cell}"))
	for cell in CELL_NAMES
}

RIFF_LINE = subsequence.Motif.join([CELL_PHRASES[cell].flatten() for cell in CELL_NAMES])


@composition.pattern(channel=MELODY_CHANNEL, beats=4)
def riff (p):

	cell, bar = cell_state(p)

	if cell == "A''" and bar == 3:
		return  # the gap bar

	p.phrase(RIFF_LINE, root=RIFF_ROOT, velocity=(75, 95), align="section")
	p.groove(FEEL)


# --- Pad: a quiet held chord, voice-led, between the bass and the riff. ---

PAD_CHANNEL = 3
PAD_ROOT = notes.C3


@composition.pattern(channel=PAD_CHANNEL, beats=4, voice_leading=True)
def pad (p, chord):

	cell, bar = cell_state(p)

	if cell == "A''" and bar == 3:
		return  # the gap bar: the pad cuts out with everything else

	# Common tones are kept and voices move by step: voice_leading picks the inversion.
	p.chord(chord, root=PAD_ROOT, count=4, velocity=(45, 60), duration=3.9)
