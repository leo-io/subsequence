"""New Hope: a 6-minute F minor house engine.  Hot-swapped on every save.

F aeolian, 118 BPM, 176 bars (about six minutes).  Hard constraints are the ones the song needs to be itself:
the four-bar loop that opens on i and ends on a dominant, each section's close (``section_cadence``), the
hook as a period (antecedent hangs on 2 or 5, consequent lands on 1), the flat-six sigh on the melody's
downbeats and the four-on-the-floor pulse.  Everything else is drawn per seed: chords between the anchors
(the live harmony engine walks the aeolian graph), the hook's pitches, the melody's four ideas, the bass
syncopation, and the percussion accents.
"""

import random

import subsequence
import subsequence.constants.instruments.gm_drums as gm_drums
import subsequence.constants.midi_notes as notes


DRUMS_CHANNEL = 10
BASS_CHANNEL = 2
PAD_CHANNEL = 3
MELODY_CHANNEL = 4
HOOK_CHANNEL = 5

BASS_ROOT = notes.F2
PAD_ROOT = notes.F3
HOOK_ROOT = notes.F4
MELODY_ROOT = notes.F5

S = subsequence.Section


# Form structure
FORM = subsequence.Form([
	S("intro", 16), S("groove", 32), S("breakdown", 16), S("build", 8), S("drop", 32),
	S("breakdown", 16), S("build", 8), S("drop", 32), S("outro", 16),
])

composition.energy({
	"intro": (0.2, 0.45), "groove": (0.55, 0.7), "breakdown": (0.35, 0.25), "build": (0.5, 1.0),
	"drop": 0.95, "outro": (0.5, 0.05),
})


# --- Harmony & Structure Integrity ---

# Reset pinned chords and transitions so hot-reloading doesn't accumulate stale state
composition._pinned_chords.clear()
composition._transitions.clear()

# What each section hangs on at its last bar.
CLOSES = {"intro": "open", "groove": "open", "breakdown": "open", "build": "open", "drop": "soft", "outro": "strong"}

for section_name, close in CLOSES.items():
	composition.section_cadence(section_name, close)

# Four-bar loop anchor: bar 1 of each 4-bar loop opens on the tonic (1).
# We omit pinning bar 4 to let the live harmony engine walk naturally to section cadences.
bar = 1
for section in FORM.sections:
	for loop in range(section.bars // 4):
		composition.pin_chord(bar, 1)
		bar += 4


# --- Melodic material: generated, then grown. ---

SIGHS = [(6, 5), (6, 5), (4, 3), (2, 1)]  # flat-six sighing onto the fifth is the favourite


def idea (rhythm_rng, contour, pins=None, end_on=None, pulses=(5, 7)):

	"""A two-bar figure (7 beats of notes, a beat of breath) with a seeded euclidean rhythm."""

	rhythm = subsequence.Motif.euclidean(rhythm_rng.randint(*pulses), 14, 0, length=7.0)

	return subsequence.Motif.generate(
		rhythm=rhythm, length=8, contour=contour, pins=pins, end_on=end_on,
		max_pitches=5, nir_strength=1.0, seed=rhythm_rng.randrange(1 << 30),
	)


def make_hook (variant):

	"""Two bars asking (ends on 2 or 5), two bars answering (the same material, ends on 1)."""

	rng = random.Random(f"{composition.seed_for('hook')}/{variant}")
	antecedent = idea(rng, "arch", pins={1: 5}, end_on=rng.choice([2, 5]))

	if variant:
		antecedent = antecedent.vary(1 + variant, seed=rng.randrange(1 << 30), keep_contour=True)

	consequent = antecedent.vary(1, seed=rng.randrange(1 << 30), keep_contour=True).answer(to=1)

	return antecedent.then(consequent)


HOOKS = [make_hook(v) for v in range(3)]


def make_line (tag, contour):

	"""An 8-bar line: a drawn idea that opens with a sigh, grown a-b-a-c."""

	rng = random.Random(f"{composition.seed_for('melody')}/{tag}")
	first, second = rng.choice(SIGHS)
	melody = idea(rng, contour, pins={1: first, 2: second}, pulses=(4, 6))

	return subsequence.Phrase.develop(melody, bars=8, plan=["a", "b", "a", "c"], seed=rng.randrange(1 << 30))


LINES = {
	"drop": [make_line("drop-a", "arch"), make_line("drop-b", "arch")],
	"build": [make_line("build", "ascending")],
	"breakdown": [make_line("breakdown", "valley")],
	"outro": [make_line("outro", "descending")],
}


def section_state (p):

	"""(name, bar in section, bars in section) or ("", 0, 0) outside the form."""

	return (p.section.name, p.section.bar, p.section.bars) if p.section else ("", 0, 0)


# --- Parts ---

@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def drums (p):

	name, bar, bars = section_state(p)
	e = p.energy

	if name != "breakdown" or bar >= bars - 4:
		p.hit_steps("kick_1", [0, 4, 8, 12], velocity=(100, 108), duration=0.2)

	if name in ("groove", "build", "drop", "outro") and not (name == "groove" and bar < 8):
		p.hit_steps("hand_clap", [4, 12], velocity=(86, 98))

	if name != "breakdown":
		p.hit_steps("hi_hat_open", [2, 6, 10, 14], velocity=(60 + int(20 * e), 78 + int(20 * e)), duration=0.3)
		# Pattern RNG stream automatically handles deterministic generation and respects lock/reroll
		p.ghost_fill("hi_hat_closed", density=0.15 + 0.5 * e, velocity=(28, 52), bias="sixteenths")
		p.bresenham_poly({"shaker": 0.6, "tambourine": 0.25}, velocity=(30, 48), probability=0.3 + 0.4 * e)

	p.swing(54)
	p.every(8, lambda q: q.ratchet(2, pitch="hi_hat_closed", probability=0.4))


# Snare roll into every drop.
composition.transition(
	before="drop",
	fill=subsequence.Motif.hits("snare_1", [0, 1, 2, 2.5, 3, 3.25, 3.5, 3.75], length=4, velocities=(60, 110)),
	channel=DRUMS_CHANNEL, drum_note_map=gm_drums.GM_DRUM_MAP,
)


@composition.pattern(channel=BASS_CHANNEL, beats=4)
def bass (p, chord):

	name, bar, bars = section_state(p)
	e = p.energy
	root = chord.root_note(BASS_ROOT)

	if name == "breakdown" or (name == "intro" and bar < 8):
		p.note(root, beat=0, velocity=(50, 62), duration=p.bar_beats - 0.1)
		return

	# Off-beat octave bounce under the kick; the sixteenth between is added more often as energy rises.
	for step in (2, 6, 10, 14):
		p.note(root + (12 if step in (6, 14) else 0), beat=step / 4, velocity=(78 + int(20 * e), 92 + int(20 * e)), duration=0.4)

	for step in (3, 7, 11, 13, 15):
		if p.rng.random() < 0.08 + 0.3 * e:
			p.note(root, beat=step / 4, velocity=(60, 72), duration=0.2)

	# Chromatic approach into the next root using chord.next
	next_chord = chord.next
	target = next_chord.root_note(BASS_ROOT) if next_chord else None

	if target is not None and target != root and p.rng.random() < 0.35 + 0.4 * e:
		step = p.rng.choice([-1, 1])
		p.note(target + step, beat=3.75, velocity=(70, 84), duration=0.2)


@composition.pattern(channel=PAD_CHANNEL, beats=4, voice_leading=True)
def pad (p, chord):

	name, bar, bars = section_state(p)
	level = 36 + int(36 * p.energy)

	# Common tones are kept and voices move by step: voice_leading picks the inversion.
	p.chord(chord, root=PAD_ROOT, count=4, velocity=(level - 5, level + 5), duration=p.bar_beats)
	p.transpose(0, within=(notes.F3, notes.G5))

	if name == "build":
		p.cc_ramp(74, int(30 + 90 * bar / bars), int(30 + 90 * (bar + 1) / bars), beat_start=0, beat_end=p.bar_beats)


@composition.pattern(channel=HOOK_CHANNEL, bars=4)
def hook (p):

	name, bar, bars = section_state(p)

	if name == "drop" or (name == "groove" and bar >= 16) or (name == "outro" and bar < 8):
		# Cycle 0 of a section states the hook plainly; later passes are drawn from the bank.
		m = HOOKS[0] if bar == 0 else p.rng.choice(HOOKS)
		p.phrase(m, root=HOOK_ROOT, velocity=(70 + int(25 * p.energy), 84 + int(25 * p.energy)), align="section")
	elif name == "build":
		# Only the answering half, riding the rising energy.
		p.phrase(HOOKS[0].slice(8, 16), root=HOOK_ROOT, velocity=(70, 100), align="section")
		p.dropout(probability=0.4 * (1 - p.energy))


@composition.pattern(channel=MELODY_CHANNEL, bars=8)
def melody (p):

	name, bar, bars = section_state(p)

	if name not in LINES or (name == "outro" and bar >= 8):
		return

	bank = LINES[name]
	line = p.rng.choice(bank)
	level = (58, 72) if name in ("breakdown", "outro") else (80, 100)

	# fit=0 keeps the flat-six on the downbeat unsnapped: it is the appoggiatura, and it resolves by step.
	p.phrase(line, root=MELODY_ROOT, velocity=level, fit=0.0, align="section")
	p.dropout(probability=0.3 * (1 - p.energy))


composition.data["form_bars"] = FORM.bars

# Re-binding the form restarts it, so a save only rebinds when the form itself changed.
if composition.data.get("form") != FORM:
	composition.form(FORM)
	composition.data["form"] = FORM
