"""discobsb: a 6-minute F minor disco house engine.  Hot-swapped on every save.

F aeolian, 118 BPM, 176 bars (about six minutes).  This file holds the form, the energy curve and the
section cadences; parts are added goal by goal.
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


# --- Bass: Authentic Bernard Edwards (Chic) Style Disco-Funk Hook ---
# Rooted in staccato rests, disco octave pops, chromatic leading tones, and pentatonic/Dorian movement.
F1, F2, E1, EB1 = notes.F1, notes.F2, notes.E1, notes.EB1
AB1, BB1, C2, EB2 = notes.AB1, notes.BB1, notes.C2, notes.EB2
GHOST = 38

def riff_bar (hits):
	"""One bar of (16th step, pitch, velocity, duration) hits as a Motif."""
	return subsequence.Motif.steps(
		[h[0] for h in hits], [h[1] for h in hits], velocities=[h[2] for h in hits], durations=[h[3] for h in hits], length=4.0,
	)

# Bar 1 (Call): Strong downbeat root, crisp octave pop, and minor pentatonic climb
BASS_CALL_1 = riff_bar([
	(0, F1, 114, 0.20),   # Beat 1: Heavy low root anchor
	(2, F2, 106, 0.15),   # Beat 1-and: Staccato octave pop
	(3, F1, GHOST, 0.10), # Ghost note push
	(4, F1, 98, 0.18),    # Beat 2
	(6, EB1, 102, 0.18),  # Beat 2-and: Offbeat flat-7th anticipation
	(8, F1, 108, 0.20),   # Beat 3
	(10, AB1, 104, 0.18), # Beat 3-and: Minor 3rd
	(12, BB1, 100, 0.20), # Beat 4: 4th degree
	(14, C2, 106, 0.18),  # Beat 4-and: 5th degree
])

# Bar 2 (Answer): Space on Beat 1, Tumbao octave push on 2-and, chromatic leading tone E1
BASS_ANSWER = riff_bar([
	(0, F1, GHOST, 0.10), # Beat 1: Rest/space for Chic start-stop feel
	(2, AB1, 106, 0.18),  # Beat 1-and: Offbeat entry
	(4, BB1, 98, 0.18),   # Beat 2
	(6, F2, 112, 0.15),   # Beat 2-and: Tumbao octave lift
	(8, F1, 104, 0.20),   # Beat 3
	(10, EB1, 98, 0.18),  # Beat 3-and: Flat-7th
	(11, E1, 92, 0.15),   # Beat 3-a: Chromatic E natural leading tone
	(12, F1, 110, 0.25),  # Beat 4: Resolution to root
	(15, F1, GHOST, 0.10),# Beat 4-a: Ghost tail
])

# Bar 3 (Call Variation): Upper register octave flourish
BASS_CALL_2 = riff_bar([
	(0, F1, 114, 0.20),   # Beat 1
	(2, F2, 108, 0.15),   # Beat 1-and: Octave pop
	(4, C2, 98, 0.18),    # Beat 2
	(6, EB2, 106, 0.18),  # Beat 2-and: High Eb2
	(8, F2, 110, 0.20),   # Beat 3: High F2 octave
	(10, C2, 100, 0.18),  # Beat 3-and
	(12, BB1, 102, 0.18), # Beat 4
	(14, AB1, 96, 0.18),  # Beat 4-and
])

# Bar 4 (Turnaround Fill): Classic Chic descending walkdown
BASS_TURNAROUND = riff_bar([
	(0, F2, 116, 0.20),   # Beat 1: High F2 stab
	(2, EB2, 106, 0.18),  # Beat 1-and
	(4, C2, 102, 0.18),   # Beat 2
	(6, BB1, 104, 0.18),  # Beat 2-and
	(8, AB1, 108, 0.20),  # Beat 3
	(10, EB1, 98, 0.15),  # Beat 3-and: Low Eb1
	(11, E1, 102, 0.15),  # Beat 3-a: Chromatic E1 leading tone
	(12, F1, 118, 0.35),  # Beat 4: Strong root home
	(15, F1, GHOST, 0.10),# Pickup ghost note into next cycle
])

# Complete 4-Bar Bernard Edwards / Chic Disco Bass Hook
BASS_HOOK = BASS_CALL_1.then(BASS_ANSWER).then(BASS_CALL_2).then(BASS_TURNAROUND)

# Intro and outro: root-octave pulse. Builds: 16th-note pedal on the low root.
BASS_PULSE = subsequence.Motif.steps([0, 8], [F1, F2], velocities=[100, 92], durations=0.2, length=4.0)
BASS_PEDAL = subsequence.Motif.euclidean(16, 16, F1, length=4.0, durations=0.15)


def section_state (p):

	"""(name, bar in section, bars in section) or ("", 0, 0) outside the form."""

	return (p.section.name, p.section.bar, p.section.bars) if p.section else ("", 0, 0)


# --- Parts ---

@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def drums (p):

	name, bar, bars = section_state(p)
	e = p.energy

	is_break = name in ("strings_break", "mini_break")
	is_drop = name in ("drop", "drop_2")

	if not is_break:
		# The first kick of every fourth bar gets a +6 accent.
		accent = 6 if bar % 4 == 0 else 0
		low, high = 100 + int(22 * e), 112 + int(15 * e)
		p.hit_steps("kick_1", [0], velocity=(min(low + accent, 126), min(high + accent, 127)), duration=0.2)
		p.hit_steps("kick_1", [4, 8, 12], velocity=(min(low, 126), min(high, 127)), duration=0.2)

	# Intro brings the open hat in at bar 9; the outro takes the clap, then the open hat, away in turn.
	has_clap = name in ("groove", "groove_2", "drop", "drop_2") or (name == "outro" and bar < 8)
	has_open_hat = name in ("groove", "groove_2", "build", "build_2") or is_drop 		or (name == "intro" and bar >= 8) or (name == "outro" and bar < 16)

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
def bass (p):

	name, bar, bars = section_state(p)

	# Silent for the strings break, the first half of the intro, the end of the outro and past the form.
	if not name or name == "strings_break" or (name == "intro" and bar < 8) or (name == "outro" and bar >= 16):
		return

	if name in ("build", "build_2"):
		# The pedal rises across the build.
		p.phrase(BASS_PEDAL, root=F1, velocity=(60 + int(50 * bar / bars), 80 + int(40 * bar / bars)), fit=0.0)
	elif name == "intro" or (name == "outro" and bar >= 8):
		p.phrase(BASS_PULSE, root=F1, fit=0.0)
	else:
		# fit=0 keeps the riff as written: the chords are chosen around it, so it must not snap to them.
		# root=F1 anchors the generated fill bar, whose degrees resolve against it.
		p.phrase(BASS_HOOK, root=F1, fit=0.0, align="section")

		if name == "drop_2":
			p.transpose(12)

	p.swing(56)


composition.data["form_bars"] = FORM.bars

# Only (re)bind the form when it changed, so a hot reload doesn't restart the song.
if composition.data.get("form") != FORM:
	composition.form(FORM)
	composition.data["form"] = FORM
