"""discobsb: a 6-minute F minor disco house engine.  Hot-swapped on every save."""

import subsequence
import subsequence.constants.instruments.gm_drums as gm_drums
import subsequence.constants.midi_notes as notes

DRUMS_CHANNEL = 10
BASS_CHANNEL = 2

S = subsequence.Section

# Form structure
FORM = subsequence.Form([
	S("intro", 16), S("groove", 16), S("strings_break", 16), S("build", 8), S("drop", 32),
	S("groove_2", 16), S("mini_break", 8), S("build_2", 8), S("drop_2", 32), S("outro", 24),
])

composition.energy({
	"intro": (0.25, 0.5), "groove": (0.6, 0.7), "strings_break": (0.35, 0.3), "build": (0.55, 1.0),
	"drop": 0.9, "groove_2": (0.65, 0.6), "mini_break": 0.3, "build_2": (0.6, 1.0),
	"drop_2": 1.0, "outro": (0.55, 0.05),
})

# What each section hangs on at its last bar.
CLOSES = {
	"intro": "open", "groove": "open", "strings_break": "open", "build": "open", "drop": "soft",
	"groove_2": "open", "mini_break": "open", "build_2": "open", "drop_2": "soft", "outro": "strong",
}

for section_name, close in CLOSES.items():
	composition.section_cadence(section_name, close)

# --- Bass: Chic-style Disco & Afro-Cuban Tumbao Hybrid Hook ---
# Notes in F minor / Dorian pentatonic
F1, F2, E1, EB1 = notes.F1, notes.F2, notes.E1, notes.EB1
AB1, BB1, C2, EB2 = notes.AB1, notes.BB1, notes.C2, notes.EB2
GHOST = 38

def riff_bar(hits):
	"""One bar of (16th step, pitch, velocity, duration) hits as a Motif."""
	return subsequence.Motif.steps(
		[h[0] for h in hits],
		[h[1] for h in hits],
		velocities=[h[2] for h in hits],
		durations=[h[3] for h in hits],
		length=4.0,
	)

# 1. BASS_CALL: Crisp Disco Octave pop on beat 1 with a syncopated Minor Pentatonic climb
# Uses percussive 16th ghost notes and staccato pops (duration 0.15 - 0.20) for maximum pocket.
BASS_CALL = riff_bar([
	(0, F1, 116, 0.20),   # Beat 1: Heavy Low Root
	(2, F2, 108, 0.15),   # Beat 1-and: Staccato Octave Pop
	(3, F1, GHOST, 0.10), # Ghost note push
	(4, F1, 98, 0.20),    # Beat 2
	(6, AB1, 105, 0.18),  # Beat 2-and (Tumbao syncopation accent)
	(8, BB1, 96, 0.20),   # Beat 3
	(10, C2, 108, 0.18),  # Beat 3-and: Accent Fifth
	(11, EB2, 92, 0.15),  # Beat 3-e: Offbeat Seventh
	(12, F1, 102, 0.20),  # Beat 4: Low Root
	(14, EB1, 95, 0.15),  # Beat 4-and: Anticipation note
	(15, E1, 90, 0.12),   # Chromatic leading tone into bar 2
])

# 2. BASS_ANSWER: Afro-Cuban Tumbao Lift & Leading Tone Resolution
# Leaves beat 1 open (start-stop space), lifting on beat 2-and & 4-and with a tight E1->F1 resolution.
BASS_ANSWER = riff_bar([
	(0, F1, GHOST, 0.10), # Start-stop rest / ghost on beat 1
	(2, AB1, 110, 0.18),  # Beat 1-and offbeat entrance
	(3, BB1, 94, 0.15),   # Ghost/passing note
	(4, C2, 100, 0.20),   # Beat 2
	(6, F2, 112, 0.15),   # Beat 2-and: Tumbao octave push
	(8, F1, 102, 0.20),   # Beat 3
	(10, EB1, 96, 0.18),  # Beat 3-and
	(11, E1, 92, 0.15),   # Beat 3-a: Chromatic E natural leading tone
	(12, F1, 114, 0.22),  # Beat 4: Anchor Root
	(14, F1, GHOST, 0.10),# Ghost tail
	(15, F1, 98, 0.15),   # Push into next bar
])

# 3. BASS_FILL: Iconic Chic/Bernard Edwards Pentatonic Walkdown Turnaround
# High-energy descending octave/pentatonic figure (F2 -> EB2 -> C2 -> BB1 -> AB1 -> F1)
BASS_FILL = riff_bar([
	(0, F2, 118, 0.22),   # Beat 1: High Octave Staccato Stab
	(2, EB2, 106, 0.18),  # Beat 1-and
	(3, C2, 98, 0.15),    # Beat 1-a
	(4, BB1, 104, 0.20),  # Beat 2
	(6, AB1, 110, 0.20),  # Beat 2-and: Syncopated Minor Third
	(8, F1, 115, 0.25),   # Beat 3: Low Root Drop
	(10, EB1, 96, 0.15),  # Beat 3-and
	(11, E1, 100, 0.15),  # Chromatic Step E1
	(12, F1, 116, 0.35),  # Beat 4: Strong Root Home
	(15, EB1, 88, 0.15),  # Turnaround pickup
])

# Four-bar call-and-response hook structure: Call -> Answer -> Call -> Fill
BASS_HOOK = BASS_CALL.then(BASS_ANSWER).then(BASS_CALL).then(BASS_FILL)

# Intro and outro: root-octave pulse. Builds: 16th-note pedal on low root.
BASS_PULSE = subsequence.Motif.steps([0, 8], [F1, F2], velocities=[100, 92], durations=0.2, length=4.0)
BASS_PEDAL = subsequence.Motif.euclidean(16, 16, F1, length=4.0, durations=0.15)

def section_state(p):
	return (p.section.name, p.section.bar, p.section.bars) if p.section else ("", 0, 0)

@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def drums(p):
	name, bar, bars = section_state(p)
	e = p.energy
	is_break = name in ("strings_break", "mini_break")
	is_drop = name in ("drop", "drop_2")

	if not is_break:
		accent = 6 if bar % 4 == 0 else 0
		low, high = 100 + int(22 * e), 112 + int(15 * e)
		p.hit_steps("kick_1", [0], velocity=(min(low + accent, 126), min(high + accent, 127)), duration=0.2)
		p.hit_steps("kick_1", [4, 8, 12], velocity=(min(low, 126), min(high, 127)), duration=0.2)

	has_clap = name in ("groove", "groove_2", "drop", "drop_2") or (name == "outro" and bar < 8)
	has_open_hat = name in ("groove", "groove_2", "build", "build_2") or is_drop or (name == "intro" and bar >= 8) or (name == "outro" and bar < 16)

	if has_clap:
		p.hit_steps("hand_clap", [4, 12], velocity=(84 + int(16 * e), 98 + int(14 * e)))
	if has_open_hat:
		p.hit_steps("hi_hat_open", [2, 6, 10, 14], velocity=(64 + int(20 * e), 80 + int(20 * e)), duration=0.3)

	p.ghost_fill("hi_hat_closed", density=0.15 + 0.5 * e, velocity=(24 + int(14 * e), 44 + int(18 * e)), bias="sixteenths")

	if is_break or is_drop:
		p.ghost_fill("shaker", density=0.5 + 0.4 * e, velocity=(26 + int(14 * e), 46 + int(14 * e)), bias="sixteenths")
	if is_drop:
		p.hit_steps("tambourine", [4, 12], velocity=(60, 76))
		if bar == 0:
			p.hit_steps("crash_1", [0], velocity=(100, 110), duration=1.0)

	p.swing(56)

@composition.pattern(channel=BASS_CHANNEL, bars=4)
def bass(p):
	name, bar, bars = section_state(p)

	# Silent for strings break, first half of intro, end of outro
	if not name or name == "strings_break" or (name == "intro" and bar < 8) or (name == "outro" and bar >= 16):
		return

	if name in ("build", "build_2"):
		p.phrase(BASS_PEDAL, root=F1, velocity=(60 + int(50 * bar / bars), 80 + int(40 * bar / bars)), fit=0.0)
	elif name == "intro" or (name == "outro" and bar >= 8):
		p.phrase(BASS_PULSE, root=F1, fit=0.0)
	else:
		# fit=0 keeps the riff as written; root=F1 anchors the generated fill bar.
		p.phrase(BASS_HOOK, root=F1, fit=0.0, align="section")
		if name == "drop_2":
			p.transpose(12)

	p.swing(56)
