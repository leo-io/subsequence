"""Lab 01, euclidean: every voice is p.euclidean(pulses) turned by p.rotate(steps).  Hot-swapped on every save.

What to listen for:
- p.euclidean spreads N hits as evenly as the 16 steps allow, always starting on step 0; p.rotate turns
  that ring so the same rhythm starts somewhere else.  4 pulses is four-on-the-floor, 3 is the tresillo
  (0, 5, 10), 5 is a broken kick (0, 3, 6, 9, 12), 7 is a busy, lopsided 16th figure.
- Cell: the call is house (kick 4, clap 2 turned to the backbeat, hats 4 turned to the off-beats); the
  response answers with odd pulse counts, so the same kit suddenly leans and breaks.
- Rotation moves hits between even and odd 16ths, and the Terry groove drags only the odd ones: the
  same rhythm turned by one step swings, turned by two it sits straight.
- The rim can run on a 12-step grid (PERC_GRID = 12): its pulses then fall on triplet 16ths, a
  polyrhythm against the 16th kit.

Mutes, solos, the bar-4 fill and the groove come from the shared frame (frame.py), as in lab 00.

Experiments:
1. RESPONSE kick pulses 5 -> 3 -> 7: broken, tresillo, then a kick roll that fights the clap.
2. RESPONSE hats rotate 1 -> 0 -> 2 -> 3: hear the swing come and go as hits move between odd and even.
3. PERC_GRID = 12 with rim pulses 5: triplets against the 16ths; then 7 for a denser cross-rhythm.
4. Give CALL and RESPONSE the same pulses: the cell flattens into a 1-bar loop.
5. HAT_PROBABILITY = 0.7: the euclidean hats start to breathe, a different set of hits each bar.
6. frame: response_solo = ("rim", 0, 8): the answer opens on the rim's polyrhythm alone.
"""

import importlib

import subsequence.constants.instruments.gm_drums as gm_drums

import frame

importlib.reload(frame)


DRUMS_CHANNEL = 10

# ---- KNOBS -------------------------------------------------------------------------------------------------

# (pulses, rotate) per voice; rotate is in the voice's own grid steps, positive = later
CALL = {
	"kick": (4, 0),
	"clap": (2, 4),
	"hats": (4, 2),
	"rim":  (3, 2),
}
RESPONSE = {
	"kick": (5, 0),
	"clap": (2, 4),
	"hats": (7, 1),
	"rim":  (5, 2),
}

PERC_GRID = 16              # rim grid: 16 = 16ths with the kit, 12 = triplet 16ths against it
HAT_PROBABILITY = 1.0       # chance each euclidean hat plays

FRAME = dict(
	call_mute = {},
	call_solo = None,
	response_mute = {},
	response_solo = None,
	bar4 = "tom_run",       # "tom_run" | "snare_roll" | "kick_roll" | "clap_stab" | "dead_stop" | "open_hat" | "none"
	fill_from = 12,         # the kit cuts here on bar 4: 12 = beat 4, 8 = beat 3
	fill_keep = [],         # voices that play through the fill, e.g. ["kick"]
	groove = 1.0,           # whole kit: 0.0 straight … 1.0 full Todd Terry swing
)

# ------------------------------------------------------------------------------------------------------------

PITCH = {"kick": "kick_1", "clap": "hand_clap", "hats": "hi_hat_closed", "rim": "side_stick"}
VELOCITY = {"kick": 120, "clap": 112, "hats": (70, 100), "rim": (80, 105)}


def place (p, voice: str, probability: float = 1.0) -> None:

	pulses, rotate = (CALL if p.bar_cycle(2).first else RESPONSE)[voice]
	p.euclidean(PITCH[voice], pulses, velocity=VELOCITY[voice], probability=probability)
	p.rotate(rotate)
	frame.finish(p, voice, FRAME)


@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def kick (p):
	place(p, "kick")


@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def clap (p):
	place(p, "clap")


@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def hats (p):
	place(p, "hats", probability=HAT_PROBABILITY)


# Step mode: PERC_GRID steps that together last one bar
@composition.pattern(channel=DRUMS_CHANNEL, steps=PERC_GRID, step_duration=4 / PERC_GRID, drum_note_map=gm_drums.GM_DRUM_MAP)
def rim (p):
	place(p, "rim")


@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def fill (p):
	frame.fill(p, FRAME)
