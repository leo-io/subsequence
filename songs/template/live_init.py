"""Live-coding entry point — runs once and watches the live pattern files.

TEMPLATE: copy this folder to ``songs/<name>/``, fill in ``song.md``, then ask
for the song to be generated.  The ``<<GENERATE …>>`` blocks below are
rewritten from ``song.md``; everything else is shared plumbing.

Workflow: run ``python songs/<name>/live_init.py``, then open
``live_patterns.py`` (or any other ``.py`` file beside this one) in your
editor and edit + save — patterns hot-swap on the next bar without
stopping the clock.

Anything that should run once at startup (MIDI device selection, tempo,
long-lived state) lives here.  Anything you want to iterate on at runtime
(form, section chords, ``@composition.pattern`` definitions) lives in the
live files, which see only ``composition`` and ``subsequence``.  State that
must survive a save goes on ``composition.data``.
"""

import logging
import pathlib

import subsequence


HERE = pathlib.Path(__file__).resolve().parent
SONG = HERE.name  # the folder name names the song, its log and its render

log = logging.getLogger(f"{SONG}.init")

# Every other .py file in this directory is an updatable live file.
LIVE_FILES = sorted(p for p in HERE.glob("*.py") if p.resolve() != pathlib.Path(__file__).resolve())

RENDER_FILE = HERE / f"{SONG}.mid"
LOG_FILE = HERE / f"{SONG}.log"

# <<GENERATE song settings: from song.md "BPM", "Time signature", "Home key / mode", "Output">>
BPM = 120
TIME_SIGNATURE = (4, 4)
KEY = "C"
SCALE = "ionian"
OUTPUT_DEVICE = None  # None = default port; otherwise a wildcard name pattern
# <</GENERATE>>


def build () -> subsequence.Composition:

	"""Create the composition and start watching the live files (does not play)."""

	composition = subsequence.Composition(
		bpm = BPM,
		time_signature = TIME_SIGNATURE,
		key = KEY,
		scale = SCALE,
		output_device = OUTPUT_DEVICE,
	)
	log.info("composition ready: bpm=%s key=%s scale=%s", BPM, KEY, SCALE)

	# <<GENERATE one-time setup: long-lived state, conductor signals, hotkeys, CC maps>>
	# <</GENERATE>>

	for live_file in LIVE_FILES:
		composition.watch(live_file)
		log.info("watching %s", live_file.name)

	return composition


if __name__ == "__main__":
	logging.basicConfig(
		level = logging.INFO,
		format = "%(asctime)s %(name)s: %(message)s",
		datefmt = "%H:%M:%S",
		handlers = [logging.StreamHandler(), logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")],
	)
	log.info("logging to %s", LOG_FILE)

	# Render a preview first, on its own composition, so the live one starts fresh.
	preview = build()
	form_bars = preview.data["form_bars"]
	log.info("rendering %d bars (one full pass of the form) to %s", form_bars, RENDER_FILE.name)
	preview.render(bars=form_bars, filename=str(RENDER_FILE))
	log.info("render saved: %s", RENDER_FILE)

	composition = build()
	composition.display(grid=True)
	composition.play()
