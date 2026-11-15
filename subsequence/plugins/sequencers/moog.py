"""The Moog 960 Sequential Controller and the Moog 962 Sequential Switch, as sequencer models.

Each is written as a musician writes their own model: a function called once a step
with ``s``, its controls its annotated parameters.  Where the hardware leaves a
behaviour open, the docstring says which way the model goes.
"""

import math
import typing

# The engine under the name a musician's own model file gives the package, so a
# packaged model reads as theirs does.  The dotted name cannot be reached while the
# package's __init__ is importing this module; the "as" form can.
import subsequence.plugins.sequencers.engine as sequencers


Range = typing.Literal["x1", "x2", "x4"]
StageSwitch = typing.Literal["normal", "skip", "stop"]

KnobLane = sequencers.Lane[sequencers.Knob]
StageLane = sequencers.Lane[StageSwitch]
Steps = typing.Annotated[int, sequencers.Span(1, 16), sequencers.Unit("steps"), sequencers.Step(1)]

# A lane's range switch, x1, x2 and x4 (2, 4 and 8 volts on the 960): how much of the
# sequencer's 0 to 1 a knob turned fully up reaches.
RANGE = {"x1": 0.25, "x2": 0.5, "x4": 1.0}


@sequencers.model(
	stages = 8,
	inputs = {
		"shift": sequencers.TRIGGER,
		"on": sequencers.TRIGGER,
		"off": sequencers.TRIGGER,
		"timing": sequencers.CV,
		**sequencers.stage_jacks(8, sequencers.TRIGGER),
	},
	outputs = {
		"lane_a": sequencers.CV,
		"lane_b": sequencers.CV,
		"lane_c": sequencers.CV,
		**sequencers.stage_jacks(8, sequencers.GATE),
	},
	normals = [("lane_c", "timing", "timing")],
	patch = [("clock.out", "@.shift"), ("clock.out", "midi.trigger"), ("@.lane_a", "midi.pitch")],
	label = "Moog 960 Sequential Controller",
)
def moog_960 (
	s: sequencers.StepContext,
	lane_a: KnobLane = 0.0,
	lane_b: KnobLane = 0.0,
	lane_c: KnobLane = 0.0,
	range_a: Range = "x4",
	range_b: Range = "x4",
	range_c: Range = "x4",
	mode: StageLane = "normal",
	stage_9: typing.Literal["skip", "stop"] = "skip",
	timing: bool = False,
	longest: Steps = 8,
) -> None:

	"""Eight stages by three lanes, A, B and C (the 960's rows of knobs), a skip or stop on each stage, stage jacks in and out, and lane C as timing.

	A shift moves to the next stage not set to skip; a stop stage sounds and holds until a
	trigger into a stage's input moves it on.  Stage 9 on skip loops; on stop it ends the pass,
	the lanes go to zero, and shifts are ignored until a stage is set.  A trigger into a stage's
	input jumps there at once, and into a stage set to skip lands on the first that is not (as the
	Q960, a modern recreation, documents it; the original lights several).  Two jumps
	in one step take the higher stage.  With ``timing`` on, lane C sets how many clock steps each
	stage lasts, at most ``longest``, each step up the lane halving it, as each volt does on the
	960's oscillator.
	"""

	def next_playable (start: int) -> typing.Optional[int]:
		for n in range(start, 9):
			if mode[n - 1] != "skip":
				return n
		return None

	if s.received("off"):
		s.memory["running"] = False
	if s.received("on"):
		s.memory["running"] = True

	arrived = False
	jumps = [n for n in range(1, 9) if s.received(f"stage{n}")]

	if jumps:
		target = jumps[-1]
		if mode[target - 1] == "skip":
			target = next_playable(1) or 1
		s.stage, arrived = target, True
		s.memory["running"] = True

	elif s.received("shift") and s.memory.get("running", True):

		if 1 <= s.stage <= 8 and mode[s.stage - 1] == "stop":
			pass
		elif s.memory.get("left", 0) > 0:
			s.memory["left"] -= 1
		else:
			found = next_playable(s.stage + 1) if s.stage < 9 else None
			if found is None and stage_9 == "stop" and s.stage > 0:
				s.stage = 9
				s.memory["running"] = False
			elif found is None:
				found = next_playable(1)
			if found is not None:
				s.stage, arrived = found, True

	sounding = 1 <= s.stage <= 8

	for lane, values, scale in (("lane_a", lane_a, range_a), ("lane_b", lane_b, range_b), ("lane_c", lane_c, range_c)):
		s.send(lane, values[s.stage - 1] * RANGE[scale] if sounding else 0.0)

	for n in range(1, 9):
		s.send(f"stage{n}", s.stage == n)

	if arrived:
		s.memory["left"] = 0
		if s.patched("timing"):
			cv = min(1.0, max(0.0, s.read("timing")))
			s.memory["left"] = int(math.floor(longest ** (1.0 - cv) + 0.5)) - 1


@sequencers.model(
	stages = 3,
	inputs = {
		"shift": sequencers.TRIGGER,
		"in1": sequencers.CV,
		"in2": sequencers.CV,
		"in3": sequencers.CV,
		**sequencers.stage_jacks(3, sequencers.TRIGGER),
	},
	outputs = {
		"out": sequencers.CV,
		**sequencers.stage_jacks(3, sequencers.GATE),
	},
	patch = [("clock.out", "@.shift"), ("clock.out", "midi.trigger"), ("@.out", "midi.pitch")],
	label = "Moog 962 Sequential Switch",
)
def moog_962 (s: sequencers.StepContext) -> None:

	"""Three inputs to one output in turn: 1 and 2, or 1, 2 and 3 once something is patched into input 3.

	A trigger into a stage's input jumps there at once; two in one step take the higher.
	"""

	positions = 3 if s.patched("in3") else 2
	jumps = [n for n in range(1, 4) if s.received(f"stage{n}")]

	if jumps:
		s.stage = min(jumps[-1], positions)
	elif s.received("shift"):
		s.stage = s.stage % positions + 1

	s.send("out", s.read(f"in{s.stage}") if s.stage else 0.0)

	for n in range(1, 4):
		s.send(f"stage{n}", s.stage == n)


sequencers.register(moog_960, moog_962)
