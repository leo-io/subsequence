"""Entry point for one song: renders it to MIDI, or plays it and hot-reloads the live files.

    python live_init.py                  # render a preview, then play live (needs a MIDI port)
    python live_init.py --render         # render only: <song>.mid, one full pass of the form
    python live_init.py --render --seed 7

While it plays, edit and save ``live_patterns.py``: patterns hot-swap on the
next bar without stopping the clock.  Tempo, metre and key live here.  There
is no live harmony engine: the harmony is one fixed B major triad, and the
bass moves beneath it.
"""

import argparse
import logging
import pathlib

import subsequence


HERE = pathlib.Path(__file__).resolve().parent
SONG = HERE.name

log = logging.getLogger(f"{SONG}.init")

LIVE_FILES = sorted(p for p in HERE.glob("live_patterns*.py"))

RENDER_FILE = HERE / f"{SONG}.mid"

BPM = 115
TIME_SIGNATURE = (4, 4)
KEY = "G#"
SCALE = "aeolian"
SEED = 1
OUTPUT_DEVICE = None  # None = default port; otherwise a wildcard name pattern


def build (seed: int = SEED) -> subsequence.Composition:

	"""Create the composition and load the live files (does not play)."""

	composition = subsequence.Composition(
		bpm = BPM,
		time_signature = TIME_SIGNATURE,
		key = KEY,
		scale = SCALE,
		seed = seed,
		output_device = OUTPUT_DEVICE,
	)

	for live_file in LIVE_FILES:
		composition.watch(live_file)

	return composition


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description=f"Render or play {SONG}.")
	parser.add_argument("--render", action="store_true", help="render to MIDI and exit, without playing")
	parser.add_argument("--seed", type=int, default=SEED)
	parser.add_argument("--out", type=pathlib.Path, default=RENDER_FILE)
	args = parser.parse_args()

	logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s", datefmt="%H:%M:%S")

	# The render runs on its own composition, so the live one starts fresh.
	preview = build(args.seed)
	form_bars = preview.data["form_bars"]
	preview.render(bars=form_bars, filename=str(args.out))
	log.info("rendered %d bars (seed %d) to %s", form_bars, args.seed, args.out)

	if not args.render:
		composition = build(args.seed)
		composition.display(grid=True)
		composition.play()
