"""Live-coding entry point - runs once and watches the live pattern file.

Workflow: run ``python songs/glitchy/live_init.py``, then open
``songs/glitchy/live_patterns.py`` in your editor and edit + save - patterns
hot-swap on the next bar without stopping the clock.

The split is intentional: anything that should run once at startup
(MIDI device selection, harmony engine, form definition, tempo) lives
in this wrapper file.  Anything you want to iterate on at runtime
(``@composition.pattern`` definitions) lives in ``live_patterns.py``.
"""

import pathlib

import subsequence


LIVE_FILE = pathlib.Path(__file__).parent / "live_patterns.py"

BPM = 128

# seed= makes every random choice repeatable, and lets reroll()/lock() reach them.
composition = subsequence.Composition(bpm=BPM, time_signature=(4, 4), key="E", seed=7)

# Form and transitions live here, not in the live file: a form() call re-run
# on every save restarts the form at its first bar, and transition() rules
# are only ever added, so an edited rule would stack on the old one.
composition.form(subsequence.Form([
	subsequence.Section("groovea", 16, energy=0.5),
	subsequence.Section("grooveb", 16, energy=1.0),
]), loop=True)

# The bar before every section change belongs to the fill alone: the groove
# parts are muted for that bar and unmuted on the next section's first bar.
# These are pattern names from live_patterns.py - keep them in step.
GROOVE_PARTS = ["kick", "snare", "hi_hat", "micro_perc"]
composition.transition(before="*", mute=GROOVE_PARTS)

# Watch the live file - changes are picked up on save.
composition.watch(LIVE_FILE)


if __name__ == "__main__":
	composition.display(grid=True, nesting={"cell": 2, "phrase": 4, "double phrase": 8, "block": 16})
	composition.play()
