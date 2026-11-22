"""Entry point for the drum lab: plays one or more study labs and hot-reloads them, or renders them to MIDI.

    python live_init.py                   # play lab 00 live (needs a MIDI port)
    python live_init.py --lab 05          # play one lab
    python live_init.py --lab 02,05       # layer two labs
    python live_init.py --list            # list the labs on disk
    python live_init.py --render --lab 05 # render only: drum-lab_lab05.mid, two four-bar phrases

While it plays, edit the KNOBS in a lab file and save: its patterns hot-swap on
the next bar without stopping the clock.  Settings that can't change
mid-performance (tempo, metre, the groove template) live here, and the groove
is shared with every lab through ``composition.data["groove"]``.
"""

import argparse
import logging
import pathlib
import sys

import subsequence


HERE = pathlib.Path(__file__).resolve().parent
SONG = HERE.name

# The labs import the shared frame (frame.py) from this folder
if str(HERE) not in sys.path:
	sys.path.insert(0, str(HERE))

log = logging.getLogger(f"{SONG}.init")

BPM = 118
TIME_SIGNATURE = (4, 4)
SEED = 1
OUTPUT_DEVICE = None  # None = default port; otherwise a wildcard name pattern

# Two four-bar phrases: enough to hear the cell, the phrase and the bar-4 variation twice.
RENDER_BARS = 8

# Todd Terry's swing: about 0.05 beat late on every off-16th.  Labs apply it with
# p.groove(composition.data["groove"], strength=...).
GROOVE_FILE = pathlib.Path(r"C:\Users\user\Documents\Ableton\User Library\Grooves\toody terry.agr")
GROOVE_GRID = 0.25


def lab_files (labs: list[str]) -> list[pathlib.Path]:

	"""Find the live file for each lab number, e.g. "05" -> live_patterns_lab05_ghost_fill.py."""

	files = []

	for lab in labs:
		matches = sorted(HERE.glob(f"live_patterns_lab{int(lab):02d}_*.py"))
		if not matches:
			raise SystemExit(f"no lab {lab} in {HERE} (try --list)")
		files.extend(matches)

	return files


def build (files: list[pathlib.Path], seed: int = SEED) -> subsequence.Composition:

	"""Create the composition, load the groove and the chosen labs (does not play)."""

	composition = subsequence.Composition(
		bpm = BPM,
		time_signature = TIME_SIGNATURE,
		seed = seed,
		output_device = OUTPUT_DEVICE,
	)

	# Loaded once here, so a save in a lab file never reads the .agr again.
	composition.data["groove"] = subsequence.Groove.from_agr(str(GROOVE_FILE), grid=GROOVE_GRID)

	for live_file in files:
		composition.watch(live_file)

	return composition


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description=f"Play or render the {SONG} study labs.")
	parser.add_argument("--lab", default="00", help="lab number(s), comma separated, e.g. 05 or 02,05")
	parser.add_argument("--list", action="store_true", help="list the labs on disk and exit")
	parser.add_argument("--render", action="store_true", help="render to MIDI and exit, without playing")
	parser.add_argument("--bars", type=int, default=RENDER_BARS)
	parser.add_argument("--seed", type=int, default=SEED)
	args = parser.parse_args()

	logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s", datefmt="%H:%M:%S")

	if args.list:
		for path in sorted(HERE.glob("live_patterns_lab*.py")):
			print(path.stem.removeprefix("live_patterns_"))
		raise SystemExit

	labs = [lab.strip() for lab in args.lab.split(",")]
	files = lab_files(labs)
	out = HERE / f"{SONG}_lab{'-'.join(f'{int(lab):02d}' for lab in labs)}.mid"

	# The render runs on its own composition, so the live one starts fresh.
	preview = build(files, args.seed)
	preview.render(bars=args.bars, filename=str(out))
	log.info("rendered %d bars (seed %d) to %s", args.bars, args.seed, out)

	if not args.render:
		composition = build(files, args.seed)
		composition.display(grid=True)
		composition.play()
