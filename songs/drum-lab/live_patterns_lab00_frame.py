"""Lab 00, the frame: a fixed house kit that makes the cell and the phrase audible.  Hot-swapped on every save.

What to listen for:
- Cell (2 bars): bar 1 is the call, the full kit.  Bar 2 answers it with its own steps plus mutes and
  solos: a voice can drop out, or play alone, for any stretch of the bar.
- Phrase (4 bars): bars 1-3 run the cell.  Bar 4 is a response bar that gets a drum fill: the kit cuts
  at fill_from and the fill chosen in bar4 takes over up to the next downbeat.
- Feel: the whole kit, fills included, rides the Todd Terry groove from the engine at one strength
  (FRAME["groove"]).  The groove drags only odd 16ths, so it is heard on the hats on 7 and 15 and on
  odd-step fill hits; even steps stay put.

The frame itself (mutes, solos, fills, groove) lives in frame.py and is shared by every lab.

Experiments:
1. Step bar4 through "tom_run", "snare_roll", "kick_roll", "clap_stab", "dead_stop", "open_hat" and
   "none", one save per phrase.
2. Set fill_from to 8: the kit cuts on beat 3 and the fill lands after a two-beat hole.
3. Put "kick" in fill_keep: the four-on-the-floor drives through the fill instead of stopping.
4. response_solo = ("kick", 8, 16): the second half of the answer is the kick alone.
5. response_mute = {"hats": (0, 16), "clap": (0, 8)}: an answer with no hats and half the claps.
6. Add 3 and 11 to CALL["hats"], or 11 to RESPONSE["kick"], to hear the swing on more of the kit.
"""

import importlib

import subsequence.constants.instruments.gm_drums as gm_drums

import frame

importlib.reload(frame)


DRUMS_CHANNEL = 10

# ---- KNOBS -------------------------------------------------------------------------------------------------

# Steps per voice, 0-15 on a 16th grid
CALL = {
	"kick": [0, 4, 8, 12],
	"clap": [4, 12],
	"hats": [2, 6, 10, 14],
}
RESPONSE = {
	"kick": [8, 12, 14],
	"clap": [4, 12],
	"hats": [2, 6, 7, 10, 14, 15],
}

FRAME = dict(
	call_mute = {},
	call_solo = None,
	response_mute = {"hats": (8, 16)},
	response_solo = None,
	bar4 = "tom_run",       # "tom_run" | "snare_roll" | "kick_roll" | "clap_stab" | "dead_stop" | "open_hat" | "none"
	fill_from = 12,         # the kit cuts here on bar 4: 12 = beat 4, 8 = beat 3
	fill_keep = [],         # voices that play through the fill, e.g. ["kick"]
	groove = 1.0,           # whole kit: 0.0 straight … 1.0 full Todd Terry swing
)

# ------------------------------------------------------------------------------------------------------------

PITCH = {"kick": "kick_1", "clap": "hand_clap", "hats": "hi_hat_closed"}
VELOCITY = {"kick": 120, "clap": 112, "hats": (75, 100)}


def place (p, voice: str) -> None:

	steps = (CALL if p.bar_cycle(2).first else RESPONSE)[voice]
	p.hit_steps(PITCH[voice], steps, velocity=VELOCITY[voice])
	frame.finish(p, voice, FRAME)


@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def kick (p):
	place(p, "kick")


@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def clap (p):
	place(p, "clap")


@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def hats (p):
	place(p, "hats")


@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def fill (p):
	frame.fill(p, FRAME)
