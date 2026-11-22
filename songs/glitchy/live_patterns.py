import subsequence
import subsequence.constants.durations as dur
import subsequence.constants.instruments.gm_drums as gm_drums
from subsequence.sequence_utils import choke, perlin_1d, sequence_to_indices


# ── Grid ─────────────────────────────────────────────────────────────────────
# Normal 4/4 time: 16 steps of a 16th note = 4 beats = 1 bar.
STEPS = 16
STEP = dur.SIXTEENTH

# Bar cycles for phrase turnarounds and fills.
PHRASE = 4
DOUBLE_PHRASE = 8


# ── Kit ──────────────────────────────────────────────────────────────────────
DRUMS_CHANNEL = 10
DRUM_KIT = dict(channel=DRUMS_CHANNEL, steps=STEPS, step_duration=STEP, drum_note_map=gm_drums.GM_DRUM_MAP)

KICK = "kick_1"
SNARE = "snare_1"
CLAP = "hand_clap"
RIM = "side_stick"
HAT_CLOSED = "hi_hat_closed"
HAT_OPEN = "hi_hat_open"
SHAKER = "shaker"
CRASH = "crash_1"

GLITCH_PERC = [RIM, CLAP, SHAKER, "high_woodblock", "low_woodblock"]

# Step allocations computed once at module level so voices interlock.
KICK_STEPS = [0, 3, 10]
KICK_TURN_STEP = [6]
SNARE_STEPS = [4, 12]
OPEN_HAT_STEPS = [2, 10]
CLOSED_HAT_STEPS = sequence_to_indices(choke([1] * STEPS, steps=OPEN_HAT_STEPS))
CLAP_STEPS = [1, 6, 11]
EVEN_STEPS = list(range(0, STEPS, 2))

# Drop strategies and ghost-bias curves computed once at module level.
ANCHOR_STEPS = KICK_STEPS + KICK_TURN_STEP + SNARE_STEPS + OPEN_HAT_STEPS
ANCHOR_DROP = choke([0.0] * STEPS, steps=ANCHOR_STEPS, floor=1.0)
RIM_DROP = choke(ANCHOR_DROP, steps=CLAP_STEPS, floor=1.0)
KICK_GHOST_BIAS = choke(subsequence.PatternBuilder.build_ghost_bias(STEPS, "sixteenths"), steps=ANCHOR_STEPS)
SNARE_GHOST_BIAS = choke(subsequence.PatternBuilder.build_ghost_bias(STEPS, "before"), steps=ANCHOR_STEPS)


# ── Feel ─────────────────────────────────────────────────────────────────────
GLITCH_SWING = subsequence.Groove.swing(percent=58, grid=STEP)


# ── Patterns ─────────────────────────────────────────────────────────────────
# Groove parts are muted by transition() on the section's last bar; the fill
# pattern takes over there.

@composition.pattern(**DRUM_KIT)
def kick (p):
	p.hit_steps(KICK, KICK_STEPS, velocity=(95, 110), duration=STEP)
	if p.bar_cycle(2).last:
		p.hit_steps(KICK, KICK_TURN_STEP, velocity=85, duration=STEP)

	if p.bar_cycle(PHRASE).last:
		p.ghost_fill(KICK, density=0.2, velocity=(35, 55), bias=KICK_GHOST_BIAS)

	p.groove(GLITCH_SWING)

	if p.bar_cycle(DOUBLE_PHRASE).last:
		p.ratchet(
			subdivisions=2,
			pitch=KICK,
			steps=[6, 10],
			probability=0.35,
			velocity_start=0.55,
			velocity_end=1.0,
			shape="ease_in",
			gate=0.4,
		)


@composition.pattern(**DRUM_KIT)
def snare (p):
	p.hit_steps(SNARE, SNARE_STEPS, velocity=(90, 105), duration=STEP)
	p.ghost_fill(SNARE, density=0.15, velocity=(28, 45), bias=SNARE_GHOST_BIAS)

	if p.bar_cycle(PHRASE).last:
		p.thin(SNARE, strategy="e_and_a", amount=0.35)

	p.groove(GLITCH_SWING)

	p.ratchet(
		subdivisions=3,
		pitch=SNARE,
		steps=[12],
		probability=0.2 + 0.2 * p.energy,
		velocity_start=1.0,
		velocity_end=0.3,
		shape="ease_out",
		gate=0.35,
	)


@composition.pattern(**DRUM_KIT)
def hi_hat (p):
	p.hit_steps(HAT_CLOSED, CLOSED_HAT_STEPS, velocity=(55, 80), duration=STEP)
	p.hit_steps(HAT_OPEN, OPEN_HAT_STEPS, velocity=(70, 85), duration=STEP)

	sparseness = perlin_1d(p.cycle * 0.13, seed=11)
	p.thin(HAT_CLOSED, strategy="strength", amount=0.35 + sparseness * 0.50)
	p.groove(GLITCH_SWING)

	p.ratchet(
		subdivisions=2,
		pitch=HAT_CLOSED,
		steps=EVEN_STEPS,
		probability=0.08 + 0.08 * p.energy,
		velocity_start=0.45,
		velocity_end=1.0,
		shape="ease_in",
		gate=0.35,
	)


@composition.pattern(**DRUM_KIT, min_energy=0.6)
def micro_perc (p):
	p.euclidean(CLAP, pulses=3, velocity=(50, 70), probability=0.45)
	p.rotate(1)
	p.cellular_1d(RIM, rule=110, velocity=(45, 75), probability=0.35)
	p.thin(RIM, strategy=RIM_DROP, amount=1.0)

	if p.bar_cycle(DOUBLE_PHRASE).last:
		p.reverse()

	p.thin(strategy=ANCHOR_DROP, amount=1.0)
	p.groove(GLITCH_SWING)


@composition.pattern(**DRUM_KIT)
def crash (p):
	if p.bar_cycle(DOUBLE_PHRASE).first:
		p.hit_steps(CRASH, [0], velocity=105)


@composition.pattern(**DRUM_KIT)
def fill (p):
	if p.section and p.section.ending:
		voices = p.rng.sample(GLITCH_PERC, 3)
		p.bresenham_poly(
			{voices[0]: 0.40, voices[1]: 0.30, voices[2]: 0.20},
			velocity=(55, 95),
			duration=STEP,
			probability=0.85,
		)
		p.groove(GLITCH_SWING)
		p.ratchet(
			subdivisions=2,
			steps=EVEN_STEPS[4:],
			probability=0.35,
			velocity_start=0.45,
			velocity_end=1.0,
			shape="ease_in",
			gate=0.35,
		)

