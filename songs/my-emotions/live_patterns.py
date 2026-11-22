"""My Emotions: a 6-minute F minor deep house track.  Hot-swapped on every save.

F aeolian, 118 BPM, 176 bars (about 5:58).  Tonal strategy C: one warm, static four-chord loop
(Fm9, Dbmaj9, Abmaj9, Eb7) carries the whole piece, and contrast comes from register, density, the
breakdown's subdominant turn and the lone dominant that hangs each build.  The rhythm section is a soft
four-on-the-floor with a rolling off-beat sub bass, deep 7th-chord stabs and a slow, sighing top line.
"""

import random

import subsequence
import subsequence.constants.instruments.gm_drums as gm_drums
import subsequence.constants.midi_notes as notes


DRUMS_CHANNEL = 10
BASS_CHANNEL = 2
PAD_CHANNEL = 3
STAB_CHANNEL = 4
MELODY_CHANNEL = 5

BASS_ROOT = notes.F1 + 12
PAD_ROOT = notes.F3
STAB_ROOT = notes.F4
MELODY_ROOT = notes.F5

S = subsequence.Section


# --- Form ---

FORM = subsequence.Form([
	S("intro", 16), S("groove", 32), S("breakdown", 16), S("build", 8), S("main", 32),
	S("breakdown", 16), S("build", 8), S("main", 32), S("outro", 16),
])

composition.energy({
	"intro": (0.15, 0.4), "groove": (0.5, 0.65), "breakdown": (0.3, 0.2), "build": (0.45, 0.85),
	"main": 0.8, "outro": (0.5, 0.05),
})


# --- Harmony: the loop, its breakdown turn and the hanging build ---

LOOP = ["Fm9", "Dbmaj9", "Abmaj9", "Eb7"]
TURN = ["Fm9", "Bbm9", "Dbmaj9", "C7"]
HANG = ["Bbm9", "Dbmaj9", "Bbm9", "C7"]
HOME = ["Fm9", "Dbmaj9", "Bbm9", "Fm9"]

# The bound progression covers only its own bars, so each loop is repeated to the section's length.
for section in FORM.sections:
	loop = {"intro": LOOP, "groove": LOOP, "breakdown": TURN, "build": HANG, "main": LOOP, "outro": HOME}[section.name]
	composition.section_chords(section.name, subsequence.progression(loop * (section.bars // 4)))


# --- Melodic material: slow, conjunct, generated then grown ---

SIGHS = [(6, 5), (6, 5), (4, 3), (2, 1)]


def idea (rng, contour, pins=None, end_on=None):

	"""A two-bar figure (7 beats of notes, a beat of breath) with a sparse seeded euclidean rhythm."""

	rhythm = subsequence.Motif.euclidean(rng.randint(3, 5), 14, 0, length=7.0)

	return subsequence.Motif.generate(
		rhythm=rhythm, length=8, contour=contour, pins=pins, end_on=end_on,
		max_pitches=4, nir_strength=1.0, seed=rng.randrange(1 << 30),
	)


def make_line (tag, contour):

	"""An 8-bar line that opens with a sigh, grown a-b-a-c."""

	rng = random.Random(f"{composition.seed_for('melody')}/{tag}")
	first, second = rng.choice(SIGHS)
	melody = idea(rng, contour, pins={1: first, 2: second})

	return subsequence.Phrase.develop(melody, bars=8, plan=["a", "b", "a", "c"], seed=rng.randrange(1 << 30))


LINES = {
	"groove": [make_line("groove", "arch")],
	"main": [make_line("main-a", "arch"), make_line("main-b", "arch")],
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
		p.hit_steps("kick_1", [0, 4, 8, 12], velocity=(92, 100), duration=0.2)

	if name in ("groove", "build", "main", "outro") and not (name == "groove" and bar < 8):
		p.hit_steps("side_stick", [4, 12], velocity=(70, 84))

	if name != "breakdown":
		p.hit_steps("hi_hat_open", [2, 6, 10, 14], velocity=(52 + int(18 * e), 68 + int(18 * e)), duration=0.3)
		p.ghost_fill("hi_hat_closed", density=0.1 + 0.4 * e, velocity=(24, 46), bias="sixteenths")
		p.bresenham_poly({"shaker": 0.6}, velocity=(26, 42), probability=0.3 + 0.4 * e)

	p.swing(56)


composition.transition(
	before="main",
	fill=subsequence.Motif.hits("snare_1", [0, 1, 2, 2.5, 3, 3.5, 3.75], length=4, velocities=(50, 96)),
	channel=DRUMS_CHANNEL, drum_note_map=gm_drums.GM_DRUM_MAP,
)


@composition.pattern(channel=BASS_CHANNEL, beats=4)
def bass (p, chord):

	name, bar, bars = section_state(p)
	e = p.energy
	root = chord.root_note(BASS_ROOT)

	if name == "breakdown" or (name == "intro" and bar < 8):
		p.note(root, beat=0, velocity=(48, 60), duration=p.bar_beats - 0.1)
		return

	# Rolling off-beat sub under the kick, a ghost sixteenth now and then.
	for step in (2, 6, 10, 14):
		p.note(root + (12 if step in (6, 14) else 0), beat=step / 4, velocity=(72 + int(18 * e), 88 + int(18 * e)), duration=0.4)

	for step in (3, 11, 15):
		if p.rng.random() < 0.05 + 0.25 * e:
			p.note(root, beat=step / 4, velocity=(56, 68), duration=0.2)


@composition.pattern(channel=PAD_CHANNEL, beats=4, voice_leading=True)
def pad (p, chord):

	name, bar, bars = section_state(p)
	level = 34 + int(34 * p.energy)

	p.chord(chord, root=PAD_ROOT, count=4, velocity=(level - 5, level + 5), duration=p.bar_beats)
	p.transpose(0, within=(notes.F3, notes.G5))

	if name == "build":
		p.cc_ramp(74, int(30 + 90 * bar / bars), int(30 + 90 * (bar + 1) / bars), beat_start=0, beat_end=p.bar_beats)


@composition.pattern(channel=STAB_CHANNEL, beats=4, voice_leading=True, min_energy=0.45)
def stabs (p, chord):

	name, bar, bars = section_state(p)

	if name in ("breakdown", "outro") and bar >= bars - 4 and name == "outro":
		return

	# The classic deep-house offbeat stab, syncopated on the "and" of 2 and 4.
	level = 56 + int(24 * p.energy)

	for beat in (1.5, 3.5):
		p.chord(chord, root=STAB_ROOT, count=4, beat=beat, velocity=(level - 6, level + 6), duration=0.35)

	p.transpose(0, within=(notes.F3, notes.C6))


@composition.pattern(channel=MELODY_CHANNEL, bars=8)
def melody (p):

	name, bar, bars = section_state(p)

	if name not in LINES or (name == "groove" and bar < 16) or (name == "outro" and bar >= 8):
		return

	line = p.rng.choice(LINES[name])
	level = (54, 70) if name in ("breakdown", "outro") else (72, 92)

	# fit=0 keeps the flat-six on the downbeat unsnapped: it is the sigh, and it resolves by step.
	p.phrase(line, root=MELODY_ROOT, velocity=level, fit=0.0, align="section")
	p.dropout(probability=0.25 * (1 - p.energy))


composition.data["form_bars"] = FORM.bars

# Re-binding the form restarts it, so a save only rebinds when the form itself changed.
if composition.data.get("form") != FORM:
	composition.form(FORM)
	composition.data["form"] = FORM
