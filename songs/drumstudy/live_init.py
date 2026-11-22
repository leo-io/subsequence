"""Live-coding entry point - runs once and watches the live pattern file.

Workflow: run ``python songs/drumstudy/live_init.py``, then open
``songs/drumstudy/live_patterns.py`` in your editor and edit + save - patterns
hot-swap on the next bar without stopping the clock.

The split is intentional: anything that should run once at startup
(MIDI device selection, harmony engine, form definition, tempo) lives
in this wrapper file.  Anything you want to iterate on at runtime
(``@composition.pattern`` definitions) lives in ``live_patterns.py``.

Things worth knowing
────────────────────

Module-level state in the live file (e.g. a ``MelodicState``) is
recreated on every reload, and the live file cannot see names defined
here.  For long-lived state, create it in this file before the
``watch()`` call, put it on ``composition.data``, and read it back from
``composition.data`` in the live file.

A save replaces each pattern's body, and any decorator argument you
changed (``channel``, ``beats``, ``min_energy`` and the rest), heard from
its next cycle.  Only a changed ``device`` waits until you restart.

Syntax errors are caught before exec and skipped - your previous
patterns keep running until you fix and save again.  Runtime errors
during reload are also caught and skip the rest of the reload, so a
half-broken save won't tear down working patterns.

Patterns deleted from the live file are automatically unregistered on
the next save: sounding notes are stopped (including drones, and notes
on every mirror destination) and the pattern is dropped from rotation.
"""

import pathlib

import subsequence


LIVE_FILE = pathlib.Path(__file__).parent / "live_patterns.py"


# Method A - double tempo.  The engine runs at 2 x REAL_BPM so an SP-1200 swing on
# engine 8ths lands on real 16ths, timed inside the engine.  One engine beat
# is a real 8th note, so an 8/4 bar is one real 4/4 bar: Form lengths,
# bar_cycle() and the display still count real bars.
#
# Costs: every part is written in doubled time (beats, durations, cycle_beats);
# MIDI clock and Link run at 2 x REAL_BPM, so this cannot sync to a REAL_BPM
# session; a recorded .mid is doubled - halve it in Live (":2") after import.
REAL_BPM = 120

# seed= makes every random choice repeatable, and lets reroll()/lock() reach them.
composition = subsequence.Composition(bpm=REAL_BPM * 2, time_signature=(8, 4), key="E", seed=1)

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
GROOVE_PARTS = ["kick", "snare", "hi_hat_closed"]
composition.transition(before="*", mute=GROOVE_PARTS)

# Watch the live file - changes are picked up on save.
composition.watch(LIVE_FILE)


if __name__ == "__main__":
	composition.display(grid=True, nesting={"cell": 2, "phrase": 4, "double phrase": 8, "block": 16})
	composition.play()
