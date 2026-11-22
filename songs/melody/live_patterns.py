"""Melody: an F minor call and response over a four-on-the-floor kick.  Hot-swapped on every save.

Piano calls on even bars and guitar answers on odd bars; the synth lead calls on bars 1 and 3 of each
four while the strings swell in the gaps; the bass reads the drums' syncopation and answers it.
Tempo, key and the live harmony engine live in ``live_init.py``.
"""

import subsequence
import subsequence.constants
import subsequence.constants.instruments.gm_drums as gm_drums
import subsequence.constants.midi_notes as notes
import subsequence.sequence_utils as sequence_utils


# --- MIDI Channel Mapping (matches mel.als) ---
BASS_CHANNEL = 2
STRINGS_CHANNEL = 3
SYNTH_CHANNEL = 4
PIANO_CHANNEL = 5
GUITAR_CHANNEL = 6
DRUMS_CHANNEL = 10

PULSES_PER_STEP = subsequence.constants.MIDI_QUARTER_NOTE // 4

S = subsequence.Section


# --- Form & Structure ---
FORM = subsequence.Form([
	S("intro", bars=4, energy=0.3),  # piano call introduced, soft strings cushion
	S("build", bars=4, energy=0.6),  # guitar response enters, synth call builds tension
	S("main", bars=4, energy=1.0),   # peak call-and-response dialogue and climax
	S("outro", bars=4, energy=0.4),  # gentle resolving conversation
])

composition.data["form_bars"] = FORM.bars  # read by live_init.py to size the render

# Re-binding the form restarts it, so only rebind when the form itself changed.
if composition.data.get("applied_form") != FORM:
	composition.form(FORM, loop=True)
	composition.data["applied_form"] = FORM


# --- Harmonic Architecture (F Aeolian / Chase Nashville Numbers) ---
# intro: 6m -> 4 -> 3(7) -> 6m (authentic close on tonic Fm)
INTRO_CHORDS = subsequence.progression(["i", "VI", "V7", "i"], beats=4)

# build: 6m -> 2m -> 4 -> 3(7) (circular harmonic gravity ending on half-cadence open question)
BUILD_CHORDS = subsequence.progression(["i", "iv", "VI", "V7"], beats=4)

# main: 6m -> 4 -> 2m -> 3(7) (driving momentum ending on open dominant for continuous drive)
MAIN_CHORDS = subsequence.progression(["i", "VI", "iv", "V7"], beats=4)

# outro: 4 -> 2m -> 3(7) -> 6m (authentic cadence resolving definitively home to Fm)
OUTRO_CHORDS = subsequence.progression(["VI", "iv", "V7", "i"], beats=4)

SECTION_CHORDS = {
	"intro": INTRO_CHORDS,
	"build": BUILD_CHORDS,
	"main": MAIN_CHORDS,
	"outro": OUTRO_CHORDS,
}

for section_name, section_progression in SECTION_CHORDS.items():
	composition.section_chords(section_name, section_progression)

# Drop the drums for the bar before the main section (transition is idempotent)
composition.transition(before="main", mute=["drums"], beats=4)

# Shared call/response state; setdefault so a live-reload save doesn't reset it mid-performance.
composition.data.setdefault("piano_call_active", False)
composition.data.setdefault("synth_call_active", False)
composition.data.setdefault("drum_syncopation", 0.0)


# --- Melodic Motifs & Material ---
# Piano Call: scale degrees 1 3 5 4 . 3 2 1 (F Ab C Bb . Ab G F).
# An internal question (beats 0-2) and answer (beats 2.5-4) in a 4-beat motif.
PIANO_CALL = subsequence.Motif.degrees(
	[1, 3, 5, 4, None, 3, 2, 1],
	beats=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
	durations=0.45,
	length=4.0,
)

# Synth Lead: VM phrases of 6 notes with appoggiatura on beat 2.0 and climax at 66-75%.
# Build: bar 0 establishes the rising shape; bar 2 leaps to F5 (climax at 67%) and steps down (100% recovery).
BUILD_LEAD_0 = subsequence.Motif.degrees([1, 2, 3, 4, 3, 1], beats=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0], durations=0.45, length=4.0)
BUILD_LEAD_2 = subsequence.Motif.degrees([3, 4, 5, 8, 7, 6], beats=[0.5, 1.0, 1.5, 2.75, 3.25, 3.75], durations=0.45, length=4.0)

# Main: bar 0 drives with high energy; bar 2 achieves the song's global peak Ab5 at 67% with step recovery.
MAIN_LEAD_0 = subsequence.Motif.degrees([3, 4, 5, 6, 5, 3], beats=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0], durations=0.45, length=4.0)
MAIN_LEAD_2 = subsequence.Motif.degrees([5, 6, 8, 10, 9, 8], beats=[0.5, 1.0, 1.5, 2.75, 3.25, 3.75], durations=0.45, length=4.0)


# --- Helpers ---
def section_state (p):

	"""(name, bar in section, bars in section) or ("", 0, 0) outside the form."""

	return (p.section.name, p.section.bar, p.section.bars) if p.section else ("", 0, 0)


# --- Parts ---

@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def drums (p):

	name, bar, bars = section_state(p)

	p.hit_steps("kick_1", [0, 4, 8, 12], velocity=100, duration=0.2)
	p.hit_steps("snare_1", [4, 12], velocity=96, duration=0.2)
	p.hit_steps("hi_hat_closed", range(0, 16, 2), velocity=75)

	if p.energy >= 0.6:
		p.ghost_fill("snare_1", density=0.4, velocity=(25, 45), bias="before")

	# Measure syncopation so the bass can decide whether to lock down or move.
	steps = [note.position // PULSES_PER_STEP for note in p.placed()]
	p.data["drum_syncopation"] = sequence_utils.syncopation(steps, p.grid)

	if p.section and p.section.last_bar:
		p.sequence(
			steps=[12, 13, 14, 15],
			pitches=["high_tom", "high_mid_tom", "low_tom", "low_floor_tom"],
			velocities=[90, 95, 100, 110],
		)


@composition.pattern(channel=PIANO_CHANNEL, beats=4, min_energy=0.3)
def piano (p, chord):

	# The call on even bars; quiet strummed chords while the guitar answers on odd bars.
	if p.bar % 2 == 0:
		p.motif(PIANO_CALL, root=notes.F4, velocity=(85, 100))
		p.data["piano_call_active"] = True
	else:
		p.strum(chord, root=notes.F3, count=2, spacing=0.5, velocity=(55, 75), detached=0.2)
		p.data["piano_call_active"] = False


@composition.pattern(channel=GUITAR_CHANNEL, beats=4, min_energy=0.4)
def guitar (p, chord):

	# Answers on odd bars while piano plays quiet chords; silent on even bars during piano call.
	if not p.data.get("piano_call_active", False):
		p.broken_chord(chord, root=notes.F3, order=[0, 2, 1, 3], spacing=0.25, velocity=(75, 95))


@composition.pattern(channel=SYNTH_CHANNEL, beats=4, min_energy=0.6)
def synth_lead (p, chord):

	name, bar, bars = section_state(p)

	# Calls on bars 0 and 2 of each 4-bar section; rests on bars 1 and 3 so strings can answer.
	if bar % 4 == 0:
		motif = BUILD_LEAD_0 if name == "build" else MAIN_LEAD_0
		p.motif(motif, root=notes.F4, velocity=(85, 100))
		p.data["synth_call_active"] = True
	elif bar % 4 == 2:
		motif = BUILD_LEAD_2 if name == "build" else MAIN_LEAD_2
		p.motif(motif, root=notes.F4, velocity=(95, 110))
		p.data["synth_call_active"] = True
	else:
		p.data["synth_call_active"] = False


@composition.pattern(channel=STRINGS_CHANNEL, beats=4, voice_leading=True)
def strings (p, chord):

	# A low cushion under the synth's call, a higher swell as the answer when it pauses.
	if p.data.get("synth_call_active", False):
		p.chord(chord, root=notes.F3, sustain=True, velocity=60)
	else:
		vel = 60 if p.energy < 0.5 else 85
		p.chord(chord, root=notes.F4, sustain=True, velocity=vel)


@composition.pattern(channel=BASS_CHANNEL, beats=4, min_energy=0.4)
def bass (p, chord):

	# Busy drums (>0.58 syncopation) or peak energy get a grounded bass; straight drums get a moving one.
	if p.data.get("drum_syncopation", 0.0) > 0.58 or p.energy >= 0.8:
		p.arpeggio(chord, root=notes.F1, count=2, spacing=0.5, velocity=95)
	else:
		p.arpeggio(chord, root=notes.F1, count=4, spacing=0.25, velocity=85)
