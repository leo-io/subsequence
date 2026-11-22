"""The drum lab's shared frame: the cell, the phrase, mutes, solos, bar-4 fills and the global groove.

A lab places each voice's hits with whatever generator it studies, then calls ``finish()``, which takes
out the steps the frame silences this bar and applies the Todd Terry groove.  A lab's ``fill`` pattern
calls ``fill()``.  The knobs live in each lab as one ``FRAME`` dict:

    FRAME = dict(
        call_mute = {},                     # {voice: (from_step, to_step)}, 16th steps, end exclusive
        call_solo = None,                   # (voice, from_step, to_step): every other voice is cut there
        response_mute = {"hats": (8, 16)},
        response_solo = None,
        bar4 = "tom_run",                   # a key of FILLS, or "none"
        fill_from = 12,                     # the kit cuts here on bar 4: 12 = beat 4, 8 = beat 3
        fill_keep = [],                     # voices that play through the fill
        groove = 1.0,                       # whole kit: 0.0 straight … 1.0 full Todd Terry swing
    )

Cell = 2 bars, ``p.bar_cycle(2)``: bar 1 calls, bar 2 responds.  Phrase = 4 bars, ``p.bar_cycle(4)``: bar 4
is a response bar that ends in a fill.  Labs reload this module on every save, so edits here hot-swap too.
"""

GRID = 16

# Each fill: (steps, pitches, velocities), one entry per hit, played with p.sequence()
FILLS = {
	"tom_run":    ([12, 13, 14, 15], ["high_tom", "high_tom", "low_mid_tom", "low_floor_tom"], [100, 110, 118, 127]),
	"snare_roll": ([12, 13, 14, 15], "snare_1", [90, 105, 118, 127]),
	"kick_roll":  ([12, 13, 14, 15], "kick_1", [110, 100, 115, 127]),
	"clap_stab":  ([12, 14, 15], "hand_clap", [127, 105, 127]),
	"dead_stop":  ([], "kick_1", 0),
	"open_hat":   ([14], "hi_hat_open", [110]),
}


def fill_bar (p, frame: dict) -> bool:

	"""True on bar 4 of the phrase when a fill is chosen."""

	return p.bar_cycle(4).last and frame["bar4"] != "none"


def cut_steps (voice: str, call: bool, fill_bar: bool, frame: dict) -> set[int]:

	"""The 16th steps a voice is silenced on this bar: its mute, another voice's solo, the fill's cut."""

	mutes = frame["call_mute"] if call else frame["response_mute"]
	solo = frame["call_solo"] if call else frame["response_solo"]
	cut: set[int] = set()

	if voice in mutes:
		cut.update(range(*mutes[voice]))

	if solo and solo[0] != voice:
		cut.update(range(solo[1], solo[2]))

	if fill_bar and voice not in frame["fill_keep"]:
		cut.update(range(frame["fill_from"], GRID))

	return cut


def finish (p, voice: str, frame: dict) -> None:

	"""Silence what the frame cuts this bar, then put the whole voice on the groove."""

	cut = cut_steps(voice, p.bar_cycle(2).first, fill_bar(p, frame), frame)

	# A per-step drop list at amount 1.0 removes exactly the cut steps, whatever placed them
	if cut:
		p.thin(strategy=[1.0 if s in cut else 0.0 for s in range(GRID)], amount=1.0, grid=GRID)

	p.groove(p.data["groove"], strength=frame["groove"])


def fill (p, frame: dict) -> None:

	"""Play bar 4's fill, on the groove like the rest of the kit."""

	if not (fill_bar(p, frame) and frame["bar4"] in FILLS):
		return

	steps, pitches, velocities = FILLS[frame["bar4"]]
	p.sequence(steps=steps, pitches=pitches, velocities=velocities)
	p.groove(p.data["groove"], strength=frame["groove"])
