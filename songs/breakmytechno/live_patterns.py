"""Break My Techno: a 256-bar Detroit minimal techno reading of "Break My Soul".  Hot-swapped on every save.

G# minor, 115 BPM, 256 bars (about 8:54) in 16-bar blocks.  One B major triad stab sits on top almost the
whole way; the mood changes only through the bass beneath it:

    1-16     edge in   drums only (kick, hat, rim clave): the DJ mix-in
    17-128   cook      stab + bass creeping G# <-> A, no clap or snare, filtered and dry; a pad voice slides
                       D# -> D -> C# -> C (the most dissonant note: a semitone over B, a tritone over F#) and freezes
    129-144  rise      kick out, bass jumps D# then A, filters open
    145-192  shine     the frozen C resolves up to C#; bass E, F#, B, G# (a bright major-9th loop); kick, clap,
                       open hats, strings and the vocal hook all arrive on the downbeat of bar 145
    193-240  tense     back to the G#/A pedal, ghost echoes of the shine stab, filters closing
    241-256  edge out  kick, hat and rim clave: the DJ mix-out
"""

import subsequence
import subsequence.constants.instruments.gm_drums as gm_drums
import subsequence.constants.midi_notes as notes
import subsequence.sequence_utils as su


DRUMS_CHANNEL = 10
BASS_CHANNEL = 2
STAB_CHANNEL = 3
PAD_CHANNEL = 4
STRINGS_CHANNEL = 5
VOCAL_CHANNEL = 6

CUTOFF = 74
REVERB = 91

S = subsequence.Section


# --- Form: sixteen-bar blocks. ---

FORM = subsequence.Form([
	S("edge_in", 16), S("cook1", 48), S("cook2", 64), S("rise", 16), S("shine", 48), S("tense", 48), S("edge_out", 16),
])

composition.energy({
	"edge_in": 0.3, "cook1": (0.35, 0.5), "cook2": (0.5, 0.65), "rise": (0.6, 0.95),
	"shine": 0.95, "tense": (0.55, 0.35), "edge_out": 0.3,
})

# Section start (0-based global bar), so the pad can walk an absolute timeline.
START = {}
_bar = 0
for _section in FORM.sections:
	START[_section.name] = _bar
	_bar += _section.bars


# --- Material. ---

B_TRIAD = [notes.B3, notes.DS4, notes.FS4]            # the stab that stays on top
ADD9 = [notes.B3, notes.DS4, notes.FS4, notes.CS5]    # the shine stab: the same triad with the 9th on top

# Stab rhythms are euclidean skeletons: sparse for the cook, denser for the shine.
COOK_STAB = su.rotate(su.sequence_to_indices(su.generate_euclidean_sequence(16, 3)), 3, 16)
SHINE_STAB = su.rotate(su.sequence_to_indices(su.generate_euclidean_sequence(16, 5)), 2, 16)

# Bass hook: one off-beat rhythm, pitches walked in a two-note pool (G# and A, a semitone apart).
BASS_RHYTHM = [0.5, 1.5, 2.25, 2.75, 3.5]
BASS_G = subsequence.Motif.generate(rhythm=BASS_RHYTHM, length=4, scale=[0, 1], pins={1: 1}, max_pitches=2, seed=3, durations=0.25)
BASS_A = subsequence.Motif.generate(rhythm=BASS_RHYTHM, length=4, scale=[0, 1], pins={1: subsequence.Degree(2, chroma=-1)}, max_pitches=2, seed=3, durations=0.25)

# Rise: the same rhythm struck on a single note, D# then A.
BASS_RISE = {"ds": BASS_G.rhythm().pitched(notes.DS2), "a": BASS_G.rhythm().pitched(notes.A1)}

# Shine: the major-9th loop under the B triad, one root per bar: E, F#, B, G#.
SHINE_ROOTS = [notes.E2, notes.FS2, notes.B1, notes.GS1]
SHINE_BASS = [subsequence.Motif.notes([r, r + 12, r + 12, r, r + 12], beats=BASS_RHYTHM, length=4, durations=0.25) for r in SHINE_ROOTS]

# Vocal hook: a two-bar question and answer in the G# minor pentatonic (G#, B, C#, D#, F#: the triad plus its 9th).
HOOK_RHYTHM = [0.5, 1.0, 2.0, 3.5, 4.0, 5.5, 6.0, 7.0]
_question = subsequence.Motif.generate(rhythm=HOOK_RHYTHM, length=8, scale=[0, 3, 5, 7, 10], contour="arch", max_pitches=4, seed=11, durations=0.4)
VOCAL_HOOK = _question.then(_question.vary(2, seed=5, keep_contour=True).answer(to=1))

CLAVE = subsequence.Motif.preset("son_clave_3_2", pitch="claves", length=4, velocities=(70, 84))


# --- Helpers (glue only). ---

def section_state (p):

	"""(name, bar in section, bars in section) or ("", 0, 0) outside the form."""

	return (p.section.name, p.section.bar, p.section.bars) if p.section else ("", 0, 0)


# (start, end) of the filter cutoff CC per section; the cook is filtered, the rise opens it, the tense part closes it.
CUTOFFS = {
	"edge_in": (127, 127), "cook1": (36, 56), "cook2": (56, 72), "rise": (72, 127),
	"shine": (118, 127), "tense": (100, 18), "edge_out": (18, 18),
}


def filter_sweep (p):

	"""Ride the cutoff across this bar of the section; the reverb stays dry except in the shine."""

	name, bar, bars = section_state(p)

	if not bars:
		return

	low, high = CUTOFFS.get(name, (127, 127))
	p.cc_ramp(CUTOFF, int(low + (high - low) * bar / bars), int(low + (high - low) * (bar + 1) / bars), beat_start=0, beat_end=p.bar_beats)
	p.cc(REVERB, 36 if name == "shine" else 0, beat=0)


# --- Parts ---

@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def drums (p):

	name, bar, bars = section_state(p)
	e = p.energy
	edge = name in ("edge_in", "edge_out")

	# The kick is out for the whole rise and nowhere else.
	if name != "rise":
		p.hit_steps("kick_1", [0, 4, 8, 12], velocity=(100, 108), duration=0.2)

	if name == "rise":
		# Hats stutter harder as the block runs; the last bar is cut dead after two beats.
		last = bar == bars - 1
		p.hit_steps("hi_hat_closed", list(range(8 if last else 16)), velocity=(40, 64), duration=0.1)
		if bar >= bars - 4:
			p.ratchet(2, pitch="hi_hat_closed", probability=0.6)
	else:
		p.hit_steps("hi_hat_closed", [2, 6, 10, 14], velocity=(58, 72), duration=0.1)
		p.ghost_fill("hi_hat_closed", density=0.1 + 0.2 * e, velocity=(24, 40), bias="sixteenths")

	if edge:
		p.motif(CLAVE)

	# Clap, open hats: only in the shine, where they arrive with everything else.
	if name == "shine":
		p.hit_steps("hand_clap", [4, 12], velocity=(92, 102))
		p.hit_steps("hi_hat_open", [2, 6, 10, 14], velocity=(66, 80), duration=0.3)

	p.swing(52)


@composition.pattern(channel=BASS_CHANNEL, beats=4)
def bass (p):

	name, bar, bars = section_state(p)

	if name in ("edge_in", "edge_out"):
		return

	filter_sweep(p)

	if name in ("cook1", "cook2", "tense"):
		# The pedal creeps: the A bars crowd in at the end of each four-bar loop (more of them in the second cook).
		a_bars = {"cook1": (3,), "cook2": (2, 3), "tense": (1, 2, 3)}[name]
		p.motif(BASS_A if bar % 4 in a_bars else BASS_G, root=notes.GS1, velocity=(92, 104))

	elif name == "rise":
		# D# then A, a bar each; the last four bars swap every other bar-half by halving the unit.
		if bar < bars - 4:
			p.motif(BASS_RISE["ds"] if bar % 2 == 0 else BASS_RISE["a"], velocity=(92, 106))
		else:
			p.motif(BASS_RISE["ds"].slice(0, 2), velocity=(98, 108))
			p.motif(BASS_RISE["a"].slice(2, 4), beat=2, velocity=(98, 108))

	elif name == "shine":
		p.motif(SHINE_BASS[bar % 4], velocity=(94, 108))


@composition.pattern(channel=STAB_CHANNEL, beats=4)
def stab (p):

	name, bar, bars = section_state(p)

	if name in ("edge_in", "edge_out"):
		return

	filter_sweep(p)

	if name in ("cook1", "cook2", "tense"):
		for step in COOK_STAB:
			p.chord(B_TRIAD, beat=step / 4, duration=0.2, velocity=(78, 90))

	if name == "rise":
		for step in COOK_STAB:
			p.chord(B_TRIAD, beat=step / 4, duration=0.2, velocity=(80, 96))

	if name == "shine":
		for step in SHINE_STAB:
			p.chord(ADD9, beat=step / 4, duration=0.2, velocity=(90, 104))

	if name == "tense":
		# Ghost echoes of the shine stab, a dotted eighth behind each hit.
		for step in SHINE_STAB:
			p.chord(ADD9, beat=(step + 3) / 4 % p.bar_beats, duration=0.15, velocity=(18, 34))


# The pad voice: held a bar at a time.  It enters on D#, slides down to C, freezes, resolves up to C# in the shine,
# and falls back to C for the tense part.
def pad_pitch (name, bar):

	"""The pad's single pitch for this bar, or None when it is silent."""

	if name not in START:
		return None

	g = START[name] + bar   # 0-based global bar

	if name == "cook1":
		return notes.DS5 if g >= 48 else None
	if name == "cook2":
		for until, pitch in ((72, notes.DS5), (80, notes.D5), (88, notes.CS5)):
			if g < until:
				return pitch
		return notes.C5
	if name == "rise":
		return notes.C5
	if name == "shine":
		return notes.CS5
	if name == "tense":
		return notes.C5
	return None


@composition.pattern(channel=PAD_CHANNEL, beats=4)
def pad (p):

	name, bar, bars = section_state(p)
	pitch = pad_pitch(name, bar)

	if pitch is None:
		return

	filter_sweep(p)
	p.note(pitch, beat=0, velocity=(62, 72), duration=p.bar_beats)


@composition.pattern(channel=STRINGS_CHANNEL, bars=4)
def strings (p):

	name, bar, bars = section_state(p)

	if name != "shine":
		return

	# Sustained B major with the 9th on top; the bass loop moves under it.
	p.chord([notes.B4, notes.DS5, notes.FS5, notes.CS6], beat=0, duration=16.0, velocity=(64, 76))


@composition.pattern(channel=VOCAL_CHANNEL, bars=4)
def vocal (p):

	name, bar, bars = section_state(p)

	if name != "shine":
		return

	p.phrase(VOCAL_HOOK, root=notes.GS4, velocity=(84, 98), align="section")


composition.data["form_bars"] = FORM.bars

# Re-binding the form restarts it, so a save only rebinds when the form itself changed.
if composition.data.get("form") != FORM:
	composition.form(FORM)
	composition.data["form"] = FORM
