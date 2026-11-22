

import random

import subsequence.constants.durations as dur
import subsequence.constants.instruments.gm_drums as gm_drums


# ── Grid ─────────────────────────────────────────────────────────────────────
# Method A - double tempo (see live_init.py).  An engine 8th is a real 16th,
# so each pattern is 16 steps of an engine 8th: one real bar on a real-16th
# grid.  Step mode sets that grid for every call - hit_steps, ghost_fill and
# the cellular fills alike - where grid= would only reach hit_steps.
STEPS = 16
STEP = dur.EIGHTH

# Bar cycles for fills and accents, counted from each section's first bar
# (section_cycle below), so they stay on the phrase whatever the section
# lengths and however often the file is saved.
PHRASE = 4
DOUBLE_PHRASE = 8

# Named ghost curves are read against the pattern's length, which is 8 engine
# beats here, so "offbeat" would mean real 16th e/a.  Build them over the 4 real
# beats instead (real_bias below).
REAL_BEATS = 4


# ── Kit ──────────────────────────────────────────────────────────────────────
DRUMS_CHANNEL = 10
DRUM_KIT = dict(channel=DRUMS_CHANNEL, steps=STEPS, step_duration=STEP, drum_note_map=gm_drums.GM_DRUM_MAP)

KICK = "kick_1"
SNARE = "snare_1"
CLAP = "hand_clap"
SIDE_STICK = "side_stick"
HAT = "hi_hat_closed"
CRASH = "crash_1"

FILL_PITCHES = [CLAP, SNARE, SIDE_STICK]

# Pattern names (the functions below), not drum names.  live_init.py mutes the
# same list in the bar before each section change - keep the two in step.
GROOVE_PARTS = ["kick", "snare", "hi_hat_closed"]


# ── Feel ─────────────────────────────────────────────────────────────────────
# SP-1200 swing: 63% on engine 8ths = real 16ths.
SP1200_SWING = subsequence.Groove.swing(percent=63, grid=STEP)


# ── Form ─────────────────────────────────────────────────────────────────────
# The form and the section-change mute are declared once, in live_init.py: a
# form() re-run on every save restarts the form, and transition() rules stack.


# ── Helpers ──────────────────────────────────────────────────────────────────
def pick_pitches (p, pool):
	"""Return a random number of distinct pitches from pool, drawn from the pattern's RNG."""
	return p.rng.sample(pool, p.rng.randint(1, len(pool)))


def section_cycle (p, length):
	"""bar_cycle(), counted from the section's first bar instead of from play."""
	return subsequence.pattern_builder.BarCycle(bar=p.section.bar % length, length=length)


def real_bias (p, name):
	"""A named ghost_fill() bias curve laid over the real bar's 4 beats."""
	return p.build_ghost_bias(STEPS, name, beats=REAL_BEATS)


def mute_gap (p, start, steps, pitch=None, amount=1.0):
	"""Crop notes on steps start..start+steps-1 - one instrument, or all with pitch=None.

	amount=1.0 empties the gap; lower leaves a ragged, dropout-like gap.
	"""
	gap = [1.0 if start <= s < start + steps else 0.0 for s in range(p.grid)]
	p.thin(pitch, gap, amount=amount)


# ── Dropout ──────────────────────────────────────────────────────────────────
# Hip-hop dropout: on some bars a few instruments cut out abruptly mid-bar and
# stay out until the barline.  The plan is drawn from the bar number, so every
# pattern building that bar agrees on who drops and where.
DROP_CHANCE = 0.1
DROPPABLE = GROOVE_PARTS
DROP_STARTS = [4, 8, 10, 12, 14]	# real beat 2, beat 3, "and" of 3, beat 4, "and" of 4


def drop_plan (p):
	"""This bar's dropout - (pattern names that cut, start step) - or None."""
	rng = random.Random(f"{composition.seed_for('dropout')}:{p.bar}")
	if rng.random() >= DROP_CHANCE:
		return None
	return rng.sample(DROPPABLE, rng.randint(1, len(DROPPABLE))), rng.choice(DROP_STARTS)


def dropout_cut (p, name):
	"""Cut this pattern from the drop point to the barline if this bar's plan includes it."""
	plan = drop_plan(p)
	if plan and name in plan[0]:
		mute_gap(p, plan[1], p.grid - plan[1])


# ── Patterns ─────────────────────────────────────────────────────────────────
# Fills skip the section's last bar: the transition mutes the groove parts there.

@composition.pattern(**DRUM_KIT)
def kick (p):
	p.hit_steps(KICK, [0, 4, 8, 12], velocity=100)

	if not p.section.ending:
		if section_cycle(p, PHRASE).last:
			p.ghost_fill(KICK, density=0.4, velocity=(30, 45), bias=real_bias(p, "offbeat"))
		if section_cycle(p, DOUBLE_PHRASE).last:
			p.cellular_1d(KICK, rule=30, velocity=40, no_overlap=True)

	# dropout_cut(p, "kick")
	p.groove(SP1200_SWING)


@composition.pattern(**DRUM_KIT)
def snare (p):
	p.hit_steps(SNARE, [4, 12], velocity=90)

	if not p.section.ending and section_cycle(p, PHRASE).last:
		p.ghost_fill(SNARE, density=0.4, velocity=(30, 45), bias=real_bias(p, "offbeat"))

	# dropout_cut(p, "snare")
	p.groove(SP1200_SWING)


@composition.pattern(**DRUM_KIT, min_energy=0.6)
def hi_hat_closed (p):
	p.hit_steps(HAT, range(p.grid), velocity=70)
	# dropout_cut(p, "hi_hat_closed")
	p.groove(SP1200_SWING)


@composition.pattern(**DRUM_KIT)
def crash (p):
	if section_cycle(p, DOUBLE_PHRASE).first:
		p.hit_steps(CRASH, [0], velocity=110)


# The fill gap is GAP_STEPS long and always fits inside the bar.
GAP_STEPS = 5


@composition.pattern(**DRUM_KIT)
def fill (p):
	if p.section.ending:
		p.cellular_2d(pick_pitches(p, FILL_PITCHES), rule="B3/S23", initial_state="random", density=0.8)
		mute_gap(p, p.rng.randrange(p.grid - GAP_STEPS + 1), GAP_STEPS)
		p.groove(SP1200_SWING)
