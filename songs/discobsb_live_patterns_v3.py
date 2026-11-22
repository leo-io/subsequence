"""discobsb: a 6-minute F minor disco house engine (v3 - Generative Subsequence Hooks).
Hot-swapped on every save using Subsequence's algorithmic composition engine.
"""

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

# --- Generative Bassline Engine (Powered by Subsequence) ---
# Notes anchor reference
F1, F2 = notes.F1, notes.F2

# 1. BASS_CALL: Generative Ascending Minor Pentatonic Motif with Octave Pinning
# Uses Subsequence's Motif.generate with contour, pins, and custom velocity/duration envelopes
BASS_CALL = subsequence.Motif.generate(
	rhythm=[0.0, 0.5, 0.75, 1.0, 1.75, 2.0, 2.5, 2.75, 3.0, 3.75], # 16th syncopated grid
	length=4.0,
	scale="minor_pentatonic",
	contour="ascending",
	pins={
		0: subsequence.Degree(1),            # Pin Beat 1: Heavy low root anchor
		1: subsequence.Degree(1, octave=1), # Pin Beat 1-and: Staccato octave pop
		8: subsequence.Degree(1),            # Pin Beat 4: Low root home
	},
	max_pitches=6,
	velocities=[116, 108, 38, 98, 105, 96, 108, 92, 102, 95],
	durations=[0.20, 0.15, 0.10, 0.20, 0.18, 0.20, 0.18, 0.15, 0.20, 0.15],
	seed=12,
)

# 2. BASS_ANSWER: Generative Tumbao Arch Motif with Off-Beat Octave Lift
# Leaves beat 1 open via ghost-pin, arches through Dorian color notes, and resolves to tonic
BASS_ANSWER = subsequence.Motif.generate(
	rhythm=[0.0, 0.5, 0.75, 1.0, 1.75, 2.0, 2.5, 2.75, 3.0, 3.75],
	length=4.0,
	scale="dorian",
	contour="arch",
	pins={
		0: subsequence.Degree(1),            # Low velocity ghost note (percussive space)
		1: subsequence.Degree(3),            # Offbeat minor 3rd lift
		4: subsequence.Degree(1, octave=1), # Tumbao octave push on beat 2-and
		7: subsequence.Degree(7, octave=-1),# Leading tone approach note on beat 3-a
	},
	end_on=1,
	max_pitches=5,
	velocities=[38, 110, 94, 100, 112, 102, 96, 92, 114, 98],
	durations=[0.10, 0.18, 0.15, 0.20, 0.15, 0.20, 0.18, 0.15, 0.22, 0.15],
	seed=42,
)

# 3. BASS_FILL: Generative Descending Walkdown Turnaround
# Algorithmic descending pentatonic cascade from upper octave down to the low root anchor
BASS_FILL = subsequence.Motif.generate(
	rhythm=[0.0, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 2.75, 3.0, 3.75],
	length=4.0,
	scale="aeolian",
	contour="descending",
	pins={
		0: subsequence.Degree(1, octave=1),  # Start high on octave F2
	},
	end_on=1,                              # Resolve home to root F1
	max_pitches=6,
	velocities=[118, 106, 98, 104, 110, 115, 96, 100, 116, 88],
	durations=[0.22, 0.18, 0.15, 0.20, 0.20, 0.25, 0.15, 0.15, 0.35, 0.15],
	seed=7,
)

# 4. Generative Rhythmic Pulses (Euclidean Engine)
BASS_PULSE = subsequence.Motif.euclidean(2, 16, F1, length=4.0, durations=0.2)
BASS_PEDAL = subsequence.Motif.euclidean(16, 16, F1, length=4.0, durations=0.15)

# 4-Bar Call & Response Hook Assembly
BASS_HOOK = BASS_CALL.then(BASS_ANSWER).then(BASS_CALL).then(BASS_FILL)

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

	# Silent for the strings break, the first half of the intro, the end of the outro and past the form.
	if not name or name == "strings_break" or (name == "intro" and bar < 8) or (name == "outro" and bar >= 16):
		return

	if name in ("build", "build_2"):
		p.phrase(BASS_PEDAL, root=F1, velocity=(60 + int(50 * bar / bars), 80 + int(40 * bar / bars)), fit=0.0)
	elif name == "intro" or (name == "outro" and bar >= 8):
		p.phrase(BASS_PULSE, root=F1, fit=0.0)
	else:
		# fit=0 keeps the generative riff rooted at F1
		p.phrase(BASS_HOOK, root=F1, fit=0.0, align="section")
		if name == "drop_2":
			p.transpose(12)

	p.swing(56)
