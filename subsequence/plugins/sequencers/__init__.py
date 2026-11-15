"""Hardware step sequencers, and your own, played inside an ordinary pattern.

A sequencer here is a small modular system: models such as the Moog 960 and the ARP
1601, patched together with cables, clocked by the pattern's own steps, and playing
notes on the pattern's own MIDI channel.  Its stages and memories carry on from one
cycle to the next, so an eight-stage loop runs across a sixteen-step bar, and a part
can be edited and saved while it plays without starting again::

	import subsequence
	import subsequence.constants.durations as dur
	import subsequence.plugins.sequencers as sequencers

	composition = subsequence.Composition(bpm=118, key="E")

	@composition.pattern(channel=6, steps=16, step_duration=dur.SIXTEENTH)
	def lead (p):
		seq = sequencers.sequencer(p)          # a clock and a MIDI out come with it
		seq.add(sequencers.moog_960, "960", lane_a=[0.0, 0.2, 0.1, 0.05, 0.0, 0.17, 0.25, 0.08])
		seq.add(sequencers.midi_out, "midi", lowest=28)
		seq.patch("clock.out", "960.shift")         # every step moves the 960 on
		seq.patch("clock.out", "midi.trigger")      # and plays a note
		seq.patch("960.lane_a", "midi.pitch")
		seq.play()

Or let ``@sequencers.pattern(composition, ...)`` make the sequencer and play it, over
``def lead (seq)``.

**The parts.**

- **Models**: ``moog_960`` (eight stages by three lanes, skip and stop, stage jacks,
  lane C as timing), ``moog_962`` (three inputs in turn) and ``arp_1601`` (sixteen
  sliders on three gate buses, quantisers, 16/1 or 8/2, sequential or random), and
  every sequencer's own ``clock`` (the pattern's steps, divided), ``knob`` (a value
  from the code) and ``midi_out`` (notes; "notes" on a control surface).
- **Modules**: ``seq.add(model, name, **controls)`` puts a model on the sequencer
  under a name; ``clock`` and ``midi`` are already there.  A module's jacks are
  named ``"name.jack"``, such as ``"960.lane_a"``.
- **Cables**: ``seq.patch(source, destination, amount)``.  Any output may feed any
  input, as on a modular: a trigger, a gate or a voltage (``CABLES`` says what each
  reads as at each other).  A voltage of 0 to 1 into the MIDI out's pitch spans
  ``SEMITONES`` (60) above its lowest note, so a lane value of ``7 / 60`` is a fifth.
  An amount scales a cable, and a negative one inverts it.

**Writing your own model** is writing a function, as a pattern is.  It is called once
on every step with ``s`` (the step, as ``p`` is the cycle), and its controls are its
own annotated parameters, declared the way the generators declare theirs, each with a
default::

	@sequencers.model(stages=8, inputs={"clock": sequencers.TRIGGER}, outputs={"pitch": sequencers.CV, "gate": sequencers.GATE})
	def pendulum (s, pitch: sequencers.Lane[sequencers.Knob] = 0.0, gate: sequencers.Lane[bool] = True):
		if s.stage == 0:
			s.stage, s.memory["direction"] = 1, 1
		elif s.received("clock"):
			if not 1 <= s.stage + s.memory["direction"] <= 8:
				s.memory["direction"] *= -1
			s.stage += s.memory["direction"]
		s.send("pitch", pitch[s.stage - 1])
		s.send("gate", gate[s.stage - 1])

``s`` reads inputs (``received()``, ``read()``, ``high()``, ``patched()``), sets outputs
(``send()``, ``fire()``), keeps ``s.stage`` and ``s.memory`` from step to step and cycle
to cycle, and draws from ``s.rng``, a random stream of the module's own.  It may also
place notes itself, on its step or inside it, with
``s.note(pitch, velocity, duration, at=)``, ``s.note_on()``, ``s.note_off()`` and
``s.cc()``, where ``at`` is how many beats into the step, less than ``s.step_beats``.
Modules are still called once a step, and cables carry values only at steps.

**How a cycle runs.**  The modules, settings and cables are declared afresh every
cycle, so a save changes them from the next one, while the stages, memories and
random streams carry on, and only from a build that succeeded: one that raises leaves
the sequencer where the last good one left it.  Within a step, modules run in the
order their cables flow, a trigger arrives at once along any cable, and a module with
no outputs plays last.

**From a control surface, or the REPL.**  The tweak ``sequencer`` holds only what was
set, one entry per control, per stage of a lane (``{"lane_a": {"2": 0.4}}``, the third
stage) and per cable, and is laid over what the code declared::

	composition.tweak("lead", sequencer={"modules": {"960": {"settings": {"lane_a": {"2": 0.4}}}}})

The last change wins, per control: when the code changes a control, a stage or a
cable, the sequencer takes that entry back and writes what is still held back into
the tweak.  An entry the sequencer cannot take is refused with its reason, and the
part plays on.  To read it all:

- ``sequencers.state(composition, "lead")``: as it last played, what is held, what
  the code took back, what was refused and why, the models on it, and a ``revision``
  that moves whenever any of it does;
- ``sequencers.playing(composition, "lead")``: which stage each module was on at
  each step of the last cycle, and the cycle's start beat;
- ``sequencers.on_build(composition, callback)``: both, handed over after every build.

**Limits.**  A pattern plays on one MIDI channel, so a sequencer driving two
instruments is declared in two patterns; the copies stay in step, because they are
the same machine on the same clock.  Renaming a module starts it afresh.
"""

# Each submodule by its own name: a package cannot reach itself by its dotted
# name while this file runs, and the "as" form can.
import subsequence.plugins.sequencers.arp as arp
import subsequence.plugins.sequencers.engine as engine
import subsequence.plugins.sequencers.moog as moog


TRIGGER = engine.TRIGGER
GATE = engine.GATE
CV = engine.CV
CABLES = engine.CABLES
SEMITONES = engine.SEMITONES
TWEAK = engine.TWEAK

Span = engine.Span
Unit = engine.Unit
Step = engine.Step
Knob = engine.Knob
Note = engine.Note
Lane = engine.Lane
stage_jacks = engine.stage_jacks

Model = engine.Model
Module = engine.Module
StepContext = engine.StepContext
Sequencer = engine.Sequencer
model = engine.model
sequencer = engine.sequencer
pattern = engine.pattern
register = engine.register
models = engine.models
state = engine.state
playing = engine.playing
on_build = engine.on_build

clock = engine.clock
knob = engine.knob
midi_out = engine.midi_out
moog_960 = moog.moog_960
moog_962 = moog.moog_962
arp_1601 = arp.arp_1601

__all__ = [
	"CABLES",
	"CV",
	"GATE",
	"Knob",
	"Lane",
	"Model",
	"Module",
	"Note",
	"SEMITONES",
	"Sequencer",
	"Span",
	"Step",
	"StepContext",
	"TRIGGER",
	"TWEAK",
	"Unit",
	"arp_1601",
	"clock",
	"knob",
	"midi_out",
	"model",
	"models",
	"moog_960",
	"moog_962",
	"on_build",
	"pattern",
	"playing",
	"register",
	"sequencer",
	"stage_jacks",
	"state",
]
