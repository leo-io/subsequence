"""The sequencers' engine: models, modules, cables, the step walk, what a control surface sets, and what it reads.

``subsequence.plugins.sequencers`` gives a musician everything here, so read that
module's docstring first.  This one says how the engine keeps its promises.

- **Where a sequencer lives.**  A pattern's sequencer is kept in ``p.memory`` under
  ``MEMORY``, as it stood after the pattern's last build that succeeded.  Each build
  plays a copy, and the copy takes its place in ``p.after_build()``.  So a build that
  raises leaves every stage, memory and random stream where the last good one left
  them, and a reader on another thread only ever sees a sequencer no build is changing.
- **How a step runs.**  Every module is called once a step, in the order its cables
  flow, so a module reads what the modules feeding it sent this step.  A trigger
  arrives at once, along any cable, and the module it reaches is called again; an
  output fires at most once a step, which is what makes a step end.  A cable that
  closes a loop of voltages reads its source as it was at the end of the step
  before, as a software modular's cable delay does.  A module with no outputs plays:
  it is called once, last, with everything that arrived at it in the step.
- **What a surface sets** arrives as the tweak ``sequencer``, holding only what the
  surface set, one entry per control, per stage of a lane and per cable.  The last
  change wins, per control: when the code changes an entry, the sequencer takes it
  back from the surface and writes what the surface still holds back into the tweak.
  Every entry is checked every cycle, and one the sequencer cannot take is refused
  with its reason, so neither a document nor a save can silence the part.
- **What it reports.**  ``state()`` is the sequencer as it last played and what the
  surface holds, with a ``revision`` that moves when any of it does.  ``playing()``
  is where each module was on each step of the last cycle, sent every cycle and kept
  out of the revision.  ``on_build()`` hands both to a listener after each build.
"""

import copy
import dataclasses
import inspect
import logging
import numbers
import random
import threading
import typing
import weakref
import zlib

import subsequence.catalogue
import subsequence.composition
import subsequence.constants
import subsequence.declarations
import subsequence.pattern_builder


TRIGGER = "trigger"
GATE = "gate"
CV = "cv"

Span = subsequence.declarations.Span
Unit = subsequence.declarations.Unit
Step = subsequence.declarations.Step

Knob = typing.Annotated[float, subsequence.declarations.Span(0.0, 1.0)]
Note = typing.Annotated[int, subsequence.declarations.PitchParameter()]

# The sequencer's pitch convention: a voltage of 1.0 is this many semitones above a
# MIDI out's lowest note, so a quantiser inside a model and the MIDI out it feeds
# agree on what a semitone is, and voltages summed into a pitch transpose exactly.
SEMITONES = 60

# The name a control surface's settings travel under, as a tweak on the pattern.
TWEAK = "sequencer"

# Where a pattern keeps its sequencer, in p.memory.
MEMORY = "subsequence.plugins.sequencers"

logger = logging.getLogger(__name__)

# Which jack may feed which, for a surface that decides before a cable goes in.  Any
# output may feed any input, as on a modular; this says what each kind of output
# reads as at each kind of input.  Notes are not a jack: a model with no outputs
# plays, and its notes go to the instrument its pattern plays.
CABLES: typing.Dict[str, typing.Any] = {
	"rule": "any output may feed any input",
	"kinds": [TRIGGER, GATE, CV],
	"reads": {
		TRIGGER: {TRIGGER: "fires it", GATE: "high for the step it fires", CV: "the cable's amount for the step it fires"},
		GATE: {TRIGGER: "fires it as the gate rises", GATE: "high while the gate is", CV: "the cable's amount while the gate is high"},
		CV: {TRIGGER: "fires it as the voltage rises past one half", GATE: "high at one half and above", CV: "its value times the cable's amount"},
	},
	"notes": "a model with no outputs plays, into the instrument its pattern plays",
}


class _LaneMark:

	"""Marks an annotation as a lane: one value per stage."""


_LANE = _LaneMark()

_T = typing.TypeVar("_T")

if typing.TYPE_CHECKING:

	# A type checker sees a lane as a list of its values, or anything, so a
	# default of one value for every stage (``= 0.0``) checks, and so does
	# reading a stage of it.  At run time it is the class below.
	Lane = typing.Union[typing.List[_T], typing.Any]

else:

	class Lane:

		"""``Lane[X]``: one X per stage, a lane of knobs, switches or choices.

		Its default may be one value for every stage (``= 0.0``) or a value per stage.
		A shorter list starts again from its beginning.
		"""

		def __class_getitem__ (cls, item: typing.Any) -> typing.Any:

			"""The annotation a lane of *item* stands for: a list of them, marked as a lane."""

			return typing.Annotated[typing.List[item], _LANE]


def stage_jacks (count: int, kind: str, prefix: str = "stage") -> typing.Dict[str, str]:

	"""``stage1`` to ``stageN``, all of one kind: a model's jacks along its stages."""

	return {f"{prefix}{n}": kind for n in range(1, count + 1)}


@dataclasses.dataclass
class _Control:

	"""One control of a model, as described, and what each of its values is held to."""

	name: str
	described: typing.Dict[str, typing.Any]
	lane: bool
	integer: bool
	# What one value is held to: the control itself, or for a lane its "of".
	element: typing.Dict[str, typing.Any]


class Model:

	"""A sequencer model: its function, its jacks, and its controls, read from the function's signature."""

	def __init__ (
		self,
		fn: typing.Callable[..., None],
		stages: int,
		inputs: typing.Dict[str, str],
		outputs: typing.Dict[str, str],
		normals: typing.Sequence[typing.Tuple[str, str, typing.Optional[str]]],
		patch: typing.Sequence[typing.Tuple[str, str]],
		label: typing.Optional[str],
	) -> None:

		"""Read the model's controls from *fn*'s annotated parameters, and check its normals name its own jacks."""

		self.fn = fn
		self.name: str = fn.__name__
		self.label = label or fn.__name__.replace("_", " ")
		self.summary = (inspect.getdoc(fn) or "").split("\n\n")[0].replace("\n", " ")
		self.stages = stages
		self.inputs = dict(inputs)
		self.outputs = dict(outputs)
		self.normals = list(normals)
		self.patch = list(patch)
		self.controls: typing.Dict[str, _Control] = {}
		self._described: typing.Optional[typing.Dict[str, typing.Any]] = None

		for kind in list(self.inputs.values()) + list(self.outputs.values()):
			if kind not in (TRIGGER, GATE, CV):
				raise ValueError(f"{self.name}: a jack is a trigger, a gate or a cv, not {kind!r}")

		hints = typing.get_type_hints(fn, include_extras=True)

		for name, parameter in list(inspect.signature(fn).parameters.items())[1:]:

			if parameter.default is inspect.Parameter.empty:
				raise TypeError(f"{self.name}: the control {name!r} needs a default, so the model plays as soon as it is added")

			annotation = hints.get(name)
			lane = _LANE in getattr(annotation, "__metadata__", ())

			if lane:
				element = typing.get_args(typing.get_args(annotation)[0])[0]
				default = parameter.default[0] if isinstance(parameter.default, (list, tuple)) else parameter.default
				described = subsequence.catalogue.describe_parameter(name, parameter.replace(default=default), element)
				base = element
			else:
				described = subsequence.catalogue.describe_parameter(name, parameter, annotation)
				base = annotation

			if described is None:
				raise TypeError(f"{self.name}: the control {name!r} has an annotation no control can draw")

			while typing.get_origin(base) is typing.Annotated:
				base = typing.get_args(base)[0]

			if lane:
				# A lane is a kind of its own, because a kind settles the shape of a
				# value: "count" values, each one what "of" describes.
				of = {k: v for k, v in described.items() if k not in ("name", "label", "required", "default")}
				described = {"name": described["name"], "label": described["label"], "kind": "lane", "count": stages, "of": of, "required": False, "default": self._lane_of(parameter.default)}
				self.controls[name] = _Control(name, described, True, base is int, of)
			else:
				self.controls[name] = _Control(name, described, False, base is int, described)

		for source, destination, when in self.normals:
			if source not in self.outputs or destination not in self.inputs:
				raise ValueError(f"{self.name}: the normal {source} -> {destination} names a jack the model does not have")
			if when is not None and when not in self.controls:
				raise ValueError(f"{self.name}: the normal {source} -> {destination} follows a switch the model does not have, {when!r}")

	def _lane_of (self, value: typing.Any) -> typing.List[typing.Any]:

		"""*value* as one value per stage: a single value on every stage, and a short list started again."""

		values = list(value) if isinstance(value, (list, tuple)) else [value]

		if not values:
			raise ValueError(f"{self.label}: a lane needs at least one value")

		return [values[i % len(values)] for i in range(self.stages)]

	def hold (self, name: str, value: typing.Any) -> typing.Any:

		"""A control's value held to what it declares: a number clamped, a choice checked, a short lane started again."""

		control = self.controls.get(name)

		if control is None:
			raise ValueError(f"{self.label} has no control called {name!r} - it has {list(self.controls)}")

		if control.lane:
			return [self._hold_one(control, v) for v in self._lane_of(value)]

		return self._hold_one(control, value)

	def _hold_one (self, control: _Control, value: typing.Any) -> typing.Any:

		"""One value held to what *control* (or one stage of it) declares."""

		described = control.element
		kind = described["kind"]

		if kind == "choice":
			options = [o["value"] for o in described["options"]]
			if value not in options:
				raise ValueError(f"{control.name} takes one of {options}, not {value!r}")
			return value

		if kind == "switch":
			return bool(value)

		if isinstance(value, bool) or not isinstance(value, numbers.Real):
			raise ValueError(f"{control.name} takes a number, not {value!r}")

		value = float(value)

		if "min" in described:
			value = max(described["min"], value)

		if "max" in described:
			value = min(described["max"], value)

		if kind == "pitch":
			value = min(127.0, max(0.0, value))

		return int(round(value)) if control.integer or kind == "pitch" else value

	def describe (self) -> typing.Dict[str, typing.Any]:

		"""Everything a surface needs to draw this model and offer its cables, as plain data, a fresh copy."""

		return copy.deepcopy(self._description())

	def _description (self) -> typing.Dict[str, typing.Any]:

		"""The description itself, made once: a model does not change after it is made, and a sequencer compares it every cycle."""

		if self._described is None:
			self._described = {
				"name": self.name,
				"label": self.label,
				"summary": self.summary,
				"stages": self.stages,
				"plays": not self.outputs,
				"controls": [copy.deepcopy(c.described) for c in self.controls.values()],
				"inputs": [{"name": n, "kind": k} for n, k in self.inputs.items()],
				"outputs": [{"name": n, "kind": k} for n, k in self.outputs.items()],
				"normals": [dict({"from": s, "to": d}, **({"when": w} if w else {})) for s, d, w in self.normals],
				"default_patch": [list(edge) for edge in self.patch],
			}

		return self._described


def model (
	stages: int = 0,
	inputs: typing.Optional[typing.Dict[str, str]] = None,
	outputs: typing.Optional[typing.Dict[str, str]] = None,
	normals: typing.Sequence[typing.Tuple[str, str, typing.Optional[str]]] = (),
	patch: typing.Sequence[typing.Tuple[str, str]] = (),
	label: typing.Optional[str] = None,
) -> typing.Callable[[typing.Callable[..., None]], Model]:

	"""Make a function into a sequencer model.

	The function is called once a step with ``s``, the step, as a pattern is called
	once a cycle with ``p``.  Its other parameters are its controls, annotated as a
	generator's are, and each needs a default.

	Parameters:
		stages: How many stages its lanes have (0 for a model with no lanes).
		inputs: Its input jacks, ``{name: kind}``, the kinds being ``TRIGGER``,
			``GATE`` and ``CV``.
		outputs: Its output jacks.  A model with none plays notes, and is called last.
		normals: ``(output, input, switch)``: one of its outputs connected to one of
			its own inputs until a cable goes in, and only while the named switch is
			on (``None`` for always).
		patch: The cables it usually opens with, where ``@`` is the module's name
			and ``clock`` and ``midi`` are the sequencer's own.
		label: Its name on a control surface.

	Example::

		import subsequence.plugins.sequencers as sequencers

		@sequencers.model(stages=4, inputs={"clock": sequencers.TRIGGER}, outputs={"pitch": sequencers.CV})
		def four (s, pitch: sequencers.Lane[sequencers.Knob] = 0.0):
			if s.received("clock"):
				s.stage = s.stage % 4 + 1
			s.send("pitch", pitch[s.stage - 1] if s.stage else 0.0)
	"""

	def wrap (fn: typing.Callable[..., None]) -> Model:

		"""The model *fn* describes."""

		return Model(fn, stages, inputs or {}, outputs or {}, normals, patch, label)

	return wrap


class Module:

	"""One model on one sequencer: its settings for this cycle, and its playing state, which carries on."""

	def __init__ (self, model_: Model, name: str) -> None:

		"""A module of *model_* called *name*, at its defaults, before its first stage."""

		self.model = model_
		self.name = name
		self.settings: typing.Dict[str, typing.Any] = {}
		self.stage = 0
		self.memory: typing.Dict[str, typing.Any] = {}
		self.values: typing.Dict[str, typing.Any] = {}
		self.rng = random.Random()
		self._dealt = False
		self._dealt_from: typing.Optional[int] = None
		self.reset()

	def reset (self) -> None:

		"""Every control back to the model's default."""

		self.settings = {n: copy.copy(c.described["default"]) for n, c in self.model.controls.items()}

	def set (self, **controls: typing.Any) -> "Module":

		"""Set controls by name, each held to what it declares."""

		for name, value in controls.items():
			self.settings[name] = self.model.hold(name, value)

		return self

	def _deal (self, stream_seed: typing.Optional[int]) -> None:

		"""Give this module its own random stream, from the pattern's seed and its own name, unless it already has it."""

		if self._dealt and stream_seed == self._dealt_from:
			return

		self.rng = random.Random(None if stream_seed is None else zlib.crc32(f"{stream_seed}:{self.name}".encode()))
		self._dealt, self._dealt_from = True, stream_seed

	def _carried (self) -> "Module":

		"""A copy for the next build to play, sharing nothing it could change."""

		# Not through __init__, whose defaults the module's first declaration in the
		# next build sets again anyway.
		other = Module.__new__(Module)
		other.model, other.name = self.model, self.name
		other.settings = dict(self.settings)
		other.stage = self.stage
		other.memory = copy.deepcopy(self.memory)
		other.values = dict(self.values)
		other.rng = random.Random()
		other.rng.setstate(self.rng.getstate())
		other._dealt, other._dealt_from = self._dealt, self._dealt_from

		return other


class StepContext:

	"""``s``: what a model sees on one step, and what it can do.  The step's ``p``, for a sequencer."""

	def __init__ (self, sequencer_: "Sequencer", module: Module, arrived: typing.Set[str], beat: float) -> None:

		"""The step at *beat* in the cycle, as *module* on *sequencer_* sees it."""

		self._sequencer = sequencer_
		self._module = module
		self._arrived = arrived
		self._beat = beat

	@property
	def stage (self) -> int:

		"""The current stage, from 1; 0 before the first."""

		return self._module.stage

	@stage.setter
	def stage (self, value: int) -> None:

		self._module.stage = int(value)

	@property
	def stages (self) -> int:

		"""How many stages the model has."""

		return self._module.model.stages

	@property
	def memory (self) -> typing.Dict[str, typing.Any]:

		"""Anything else the module needs to remember from step to step, and from cycle to cycle."""

		return self._module.memory

	@property
	def step (self) -> int:

		"""Steps played since this pattern began, across every cycle."""

		return self._sequencer.step

	@property
	def step_beats (self) -> float:

		"""How many beats this step lasts, the pattern's own step."""

		return self._sequencer._step_beats

	@property
	def rng (self) -> random.Random:

		"""This module's own random stream.

		It comes from the composition's seed, the pattern's name and the module's name,
		and carries on from cycle to cycle, so adding another module does not change
		what this one draws.  Renaming the module starts it afresh.
		"""

		return self._module.rng

	def received (self, jack: str) -> bool:

		"""Whether a trigger arrived at this input since this module was last called."""

		self._sequencer._jack(self._module, jack, inputs=True)

		return jack in self._arrived

	def patched (self, jack: str) -> bool:

		"""Whether anything is connected to this input, a cable or a normal."""

		self._sequencer._jack(self._module, jack, inputs=True)

		return self._sequencer.connected(f"{self._module.name}.{jack}")

	def read (self, jack: str) -> float:

		"""The sum of everything connected to this input: a voltage its value, a gate 1 while high, a trigger 1 on its step."""

		self._sequencer._jack(self._module, jack, inputs=True)

		return self._sequencer.read(f"{self._module.name}.{jack}")

	def high (self, jack: str) -> bool:

		"""Whether this input is high: a gate is, a trigger on its step, a voltage at one half and above."""

		return self.read(jack) >= 0.5

	def send (self, jack: str, value: typing.Union[float, bool]) -> None:

		"""Set an output.  It holds until sent again; a gate rising fires whatever its cables reach."""

		self._sequencer._send(self._module, jack, value)

	def fire (self, jack: str) -> None:

		"""Fire a trigger output, once a step at most."""

		self._sequencer._fire(self._module, jack)

	def note (self, pitch: int, velocity: int, duration: float, at: float = 0.0) -> None:

		"""Place a note on this step, or *at* beats into it, in the pattern playing the sequencer."""

		self._sequencer.p.note(int(pitch), beat=self._at(at), velocity=int(velocity), duration=duration)

	def note_on (self, pitch: int, velocity: int, at: float = 0.0) -> None:

		"""Start a note on this step, or *at* beats into it.  It sounds until a ``note_off()`` ends it."""

		self._sequencer._note_on(int(pitch), self._at(at), int(velocity))

	def note_off (self, pitch: int, at: float = 0.0) -> None:

		"""End a note on this step, or *at* beats into it."""

		self._sequencer._note_off(int(pitch), self._at(at))

	def cc (self, control: int, value: int, at: float = 0.0) -> None:

		"""Send a controller on this step, or *at* beats into it."""

		self._sequencer.p.cc(int(control), int(value), beat=self._at(at))

	def _at (self, at: float) -> float:

		"""The beat in the cycle *at* beats into this step, which has to be inside the step."""

		if not 0.0 <= at < self.step_beats:
			raise ValueError(f"at= is how far into this step, from 0 up to its length of {self.step_beats} beats, not {at!r}")

		return self._beat + at


# The sequencer's own parts --------------------------------------------------------------------------------------

@model(outputs={"out": TRIGGER}, label="clock")
def clock (
	s: StepContext,
	every: typing.Annotated[int, Span(1, 16), Unit("steps"), Step(1)] = 1,
	offset: typing.Annotated[int, Span(0, 15), Unit("steps"), Step(1)] = 0,
) -> None:

	"""The pattern's own steps as a clock: the composition's clock, divided."""

	if (s.step - offset) % every == 0:
		s.fire("out")


@model(outputs={"out": CV}, label="knob")
def knob (s: StepContext, value: Knob = 0.0) -> None:

	"""A knob, 0 to 1.  Set it from anything a pattern can read, such as a value cc_map() keeps in composition.data."""

	s.send("out", value)


# Its label is the word a surface shows, which names what it carries rather than the
# transport (#2108: "the sockets are not called MIDI"); in code it is midi_out.
@model(inputs={"trigger": TRIGGER, "gate": GATE, "pitch": CV, "velocity": CV, "duration": CV, "cc": CV}, label="notes")
def midi_out (
	s: StepContext,
	lowest: Note = 36,
	shortest: typing.Annotated[float, Span(0.0625, 1.0), Unit("beats"), Step(0.0625)] = 0.0625,
	longest: typing.Annotated[float, Span(0.25, 8.0), Unit("beats"), Step(0.25)] = 2.0,
	cc_number: typing.Annotated[int, Span(0, 127), Step(1)] = 74,
) -> None:

	"""Turns triggers or a gate, and voltages for pitch, velocity and duration, into notes on this pattern's MIDI channel.

	Pitch is ``lowest`` plus 60 semitones across 0 to 1.  With a gate patched, a note starts as the
	gate rises and ends as it falls, so neighbouring stages tie.  A pitch that changes while the
	gate is held plays legato, as a voltage under a held gate does: the new note starts and the old
	one ends a pulse later, which a mono synth hears as legato or glide.  A voltage into ``cc`` is
	sent as controller ``cc_number`` whenever it changes.
	"""

	def level (jack: str, otherwise: float) -> float:
		return min(1.0, max(0.0, s.read(jack))) if s.patched(jack) else otherwise

	pitch = min(127, lowest + round(level("pitch", 0.0) * SEMITONES))
	velocity = 1 + round(level("velocity", 0.8) * 126)

	if s.patched("cc"):
		value = round(level("cc", 0.0) * 127)
		if s.memory.get("cc") != (cc_number, value):
			s.cc(cc_number, value)
			s.memory["cc"] = (cc_number, value)

	if s.patched("gate"):
		high = s.high("gate")
		held = s.memory.get("held")
		if held is not None and not high:
			s.note_off(held)
			s.memory["held"] = None
		elif held is not None and pitch != held:
			s.note_on(pitch, velocity)
			s.note_off(held, at=1 / subsequence.constants.MIDI_QUARTER_NOTE)
			s.memory["held"] = pitch
		elif high and held is None:
			s.note_on(pitch, velocity)
			s.memory["held"] = pitch
		return

	if s.received("trigger"):
		span = max(shortest, longest)
		s.note(pitch, velocity, shortest * (span / shortest) ** level("duration", 0.3))


# The sequencer --------------------------------------------------------------------------------------------------

class Sequencer:

	"""One pattern's modules and cables.  It comes with ``clock`` (the pattern's steps) and ``midi`` (its notes)."""

	def __init__ (self) -> None:

		"""An empty sequencer, before its first cycle."""

		self.modules: typing.Dict[str, Module] = {}
		self.cables: typing.Dict[typing.Tuple[str, str], float] = {}
		self.step = 0
		self.loops_read_late = 0

		# What a surface set, and what it still holds once the code has taken
		# entries back (an entry is a key such as ("set", "960", "lane_a", 2)).
		self.revision = 0
		self.taken_back: typing.List[typing.Dict[str, typing.Any]] = []
		self.refused: typing.List[typing.Dict[str, typing.Any]] = []
		self._held: typing.Dict[typing.Tuple[typing.Any, ...], typing.Any] = {}
		self._taken_at: typing.Dict[typing.Tuple[typing.Any, ...], int] = {}
		self._seen: typing.Any = None
		self._code: typing.Optional[typing.Dict[typing.Tuple[typing.Any, ...], typing.Any]] = None
		self._played: typing.Dict[str, typing.Any] = {}
		self._described: typing.Dict[str, typing.Any] = {}
		self._playing: typing.Optional[typing.Dict[str, typing.Any]] = None
		self._previous: typing.Dict[str, typing.Any] = {}

		# This build's: the builder (held weakly, so a sequencer kept in a weak
		# table never keeps its build alive), what the code declared, and the walk.
		self._builder: typing.Optional[weakref.ReferenceType[subsequence.pattern_builder.PatternBuilder]] = None
		self._has_played = False
		self._declared: typing.Set[str] = set()
		self._injected: typing.List[str] = []
		self._after: typing.List[typing.Callable[[], typing.Any]] = []
		self._edges: typing.Dict[typing.Tuple[str, str], float] = {}
		# This cycle's cables by their ends, so a step never walks them all.
		self._into: typing.Dict[str, typing.List[typing.Tuple[str, float]]] = {}
		self._from: typing.Dict[str, typing.List[typing.Tuple[str, float]]] = {}
		self._order: typing.Dict[str, int] = {}
		self._step_beats = 0.25
		self._fired: typing.Set[str] = set()
		self._crossed: typing.Set[str] = set()
		self._arrivals: typing.Dict[str, typing.Set[str]] = {}
		self._all_arrivals: typing.Dict[str, typing.Set[str]] = {}
		self._wanted: typing.Set[str] = set()
		# Notes started and not yet ended this cycle, by pitch: (beat, velocity).
		self._sounding: typing.Dict[int, typing.Tuple[float, int]] = {}
		self._positions: typing.Dict[str, typing.List[typing.Optional[int]]] = {}

	@property
	def p (self) -> subsequence.pattern_builder.PatternBuilder:

		"""The pattern's ``p`` for this build: its own verbs, for anything the sequencer does not place."""

		builder = self._builder() if self._builder is not None else None

		if builder is None:
			raise RuntimeError("this sequencer's build is over: reach the pattern through p, inside the pattern")

		return builder

	def add (self, model_: Model, name: str, **controls: typing.Any) -> Module:

		"""This sequencer's module of a model: made the first time, the same one after.

		Its first declaration in a cycle starts from the model's defaults, then takes the
		controls given here; its stage, memory and random stream carry on.  A model is
		matched by its name, so a live save that runs the file again keeps a model
		written in it where it was.  A module that is renamed starts afresh.
		"""

		if not isinstance(name, str) or not name or "." in name:
			raise ValueError(f"a module's name is a word with no dot in it, such as '960', not {name!r}")

		module = self.modules.get(name)

		if module is None or module.model.name != model_.name:
			module = Module(model_, name)
			self.modules[name] = module
		else:
			module.model = model_
			if name not in self._declared:
				module.reset()

		module._deal(self.p.stream_seed)
		self._declared.add(name)

		return module.set(**controls)

	def default_patch (self, name: str) -> None:

		"""The cables a module's model usually opens with."""

		for source, destination in self.modules[name].model.patch:
			self.patch(source.replace("@", name), destination.replace("@", name))

	def patch (self, source: str, destination: str, amount: typing.Union[bool, float] = True) -> None:

		"""A cable from an output to an input.  An amount scales it, as an attenuator would; a negative one inverts."""

		self._jack_of(source, inputs=False)
		self._jack_of(destination, inputs=True)

		if amount is False or amount == 0:
			self.cables.pop((source, destination), None)
		else:
			self.cables[(source, destination)] = float(amount)

	def inject (self, path: str) -> None:

		"""A trigger into an input from the code, such as ``"960.stage1"``: it arrives on this cycle's first step."""

		self._jack_of(path, inputs=True)
		self._injected.append(path)

	def after (self, action: typing.Callable[[], typing.Any]) -> None:

		"""Something to do once this cycle's notes are placed, such as ``lambda: seq.p.swing(57)``."""

		self._after.append(action)

	def document (self) -> typing.Dict[str, typing.Any]:

		"""The whole sequencer as plain data: every module's settings and every cable."""

		# A setting is a value or a lane of values, so a list copied is a copy.
		return {
			"modules": {n: {"model": m.model.name, "settings": {k: list(v) if isinstance(v, list) else v for k, v in m.settings.items()}} for n, m in self.modules.items()},
			"patch": [[s, d, a] for (s, d), a in self.cables.items()],
		}

	def apply (self, document: typing.Optional[typing.Dict[str, typing.Any]], models: typing.Optional[typing.Dict[str, Model]] = None) -> None:

		"""Lay a sequencer document over what the code declared, entry by entry.

		A module it names with a model and the code did not declare is added; a setting
		replaces the code's (a lane's stages one at a time, keyed by index); a cable is
		added or re-attenuated, and an amount of 0 pulls it out; a module in ``removed``
		is taken off the sequencer with its cables.  Anything it cannot take is left out,
		with one warning.
		"""

		if not document:
			return

		entries, malformed = self._entries(document, models)
		why = self._refusals(entries, models)
		reasons = [reason for _, reason in malformed] + list(why.values())

		if reasons:
			logger.warning("A sequencer document named what this sequencer cannot take, left out: %s", "; ".join(reasons))

		self._lay({k: v for k, v in entries.items() if k not in why}, models)

	def state (self) -> typing.Dict[str, typing.Any]:

		"""What a surface reads, as a fresh copy: the sequencer as it last played, what the surface still holds, what the code took back, what was refused and why, and the models on it.

		``revision`` moves whenever any of them does, so one number says whether to look again.
		"""

		return copy.deepcopy({
			"revision": self.revision,
			"played": self._played,
			"held": self._document_of(self._held),
			"taken_back": self.taken_back,
			"refused": self.refused,
			"models": self._described,
			"cables": CABLES,
		})

	def playing (self) -> typing.Optional[typing.Dict[str, typing.Any]]:

		"""Where each module was on each step of the last cycle, as a fresh copy; None before the first.

		``cycle`` says where the cycle starts, in beats from the composition's start, and
		how many steps it has of what length.  ``modules`` gives each module with stages a
		``positions`` entry per cursor (``stage`` for now): one stage index per step,
		from 0 as a lane's stages are, and None where it was on no stage.
		"""

		return copy.deepcopy(self._playing)

	def edges (self) -> typing.Dict[typing.Tuple[str, str], float]:

		"""What is connected now: every cable, and each normal whose input has no cable and whose switch is on."""

		cabled = {d for _, d in self.cables}
		live: typing.Dict[typing.Tuple[str, str], float] = {}

		for name, module in self.modules.items():
			for source, destination, when in module.model.normals:
				edge = (f"{name}.{source}", f"{name}.{destination}")
				if edge[1] not in cabled and (when is None or module.settings.get(when)):
					live[edge] = 1.0

		live.update(self.cables)

		return live

	def connected (self, destination: str) -> bool:

		"""Whether anything this cycle reaches *destination*, an input such as ``"midi.pitch"``."""

		return destination in self._into

	def read (self, destination: str) -> float:

		"""The sum of everything reaching *destination* on this step."""

		total = 0.0

		for source, amount in self._into.get(destination, ()):
			name, jack = source.split(".", 1)
			if self.modules[name].model.outputs[jack] == TRIGGER:
				total += amount if source in self._fired else 0.0
				continue
			if self._late(name, destination.split(".", 1)[0]):
				self.loops_read_late += 1
				value = self._previous.get(source, 0.0)
			else:
				value = self.modules[name].values.get(jack, 0.0)
			total += amount * float(value)

		return total

	def play (self) -> None:

		"""Lay over what a surface has set, then walk this cycle's steps and place what the sequencer plays."""

		if self._has_played:
			raise RuntimeError("a sequencer plays once a cycle: call play() once in the pattern")

		self._has_played = True
		p = self.p
		moved = self._overlay(p)

		for name in [n for n in self.modules if n not in self._declared]:
			del self.modules[name]

		self.cables = {(s, d): a for (s, d), a in self.cables.items() if s.split(".", 1)[0] in self.modules and d.split(".", 1)[0] in self.modules}

		played = self.document()
		described = {m.model.name: m.model._description() for m in self.modules.values()}

		if moved or played != self._played or described != self._described:
			self.revision += 1
			self._played, self._described = played, described

		self._edges = self.edges()
		self._into, self._from = {}, {}

		for (source, destination), amount in self._edges.items():
			self._into.setdefault(destination, []).append((source, amount))
			self._from.setdefault(source, []).append((destination, amount))

		players = {n for n, m in self.modules.items() if not m.model.outputs}
		self._order = self._flow_order(players)
		self._step_beats = p.step_beats
		self._sounding = {}
		self._positions = {n: [] for n, m in self.modules.items() if m.model.stages > 0}

		for k in range(p.grid):
			self._step(k * self._step_beats, players)
			self.step += 1

		# A note still sounding at the cycle's end is started here and ended by a
		# later cycle; every other note was placed whole.
		for pitch, (beat, velocity) in self._sounding.items():
			p.note_on(pitch, beat=beat, velocity=velocity)

		self._sounding = {}
		self._playing = {
			"cycle": {"start_beat": p.start_beat, "steps": p.grid, "step_beats": self._step_beats},
			"modules": {n: {"positions": {"stage": positions}} for n, positions in self._positions.items()},
		}

		for action in self._after:
			action()

		memory, pattern_name, data = p.memory, p.name, p.data

		def commit () -> None:
			self._builder = None
			memory[MEMORY] = self
			_report(data, pattern_name, self)

		p.after_build(commit)

	def _carried (self) -> "Sequencer":

		"""A copy for the next build to play: everything that carries from cycle to cycle, and nothing of this build's."""

		other = Sequencer()
		other.modules = {n: m._carried() for n, m in self.modules.items()}
		other.step = self.step
		other.loops_read_late = self.loops_read_late
		other.revision = self.revision
		other.taken_back = list(self.taken_back)
		other.refused = list(self.refused)
		other._held = dict(self._held)
		other._taken_at = dict(self._taken_at)
		other._seen = copy.deepcopy(self._seen)
		# Replaced whole each cycle and never changed in place, so shared.
		other._code = self._code
		other._played = self._played
		other._described = self._described
		other._playing = self._playing
		other._previous = dict(self._previous)

		return other

	def _known (self, models: typing.Optional[typing.Dict[str, Model]] = None) -> typing.Dict[str, Model]:

		"""Every model this sequencer can name: those registered, those given, and those on it."""

		known = dict(MODELS)
		known.update(models or {})
		known.update({m.model.name: m.model for m in self.modules.values()})

		return known

	def _entries (
		self,
		document: typing.Any,
		models: typing.Optional[typing.Dict[str, Model]] = None,
	) -> typing.Tuple[typing.Dict[typing.Tuple[typing.Any, ...], typing.Any], typing.List[typing.Tuple[typing.Any, str]]]:

		"""A document as entries, one per control, stage, cable or removal, read for shape alone, and what could not be read.

		Whether each entry fits the sequencer is asked separately, every cycle
		(``_refusals``), because a save can take away what an entry names after the
		entry arrived.
		"""

		known = self._known(models)
		entries: typing.Dict[typing.Tuple[typing.Any, ...], typing.Any] = {}
		malformed: typing.List[typing.Tuple[typing.Any, str]] = []

		if not isinstance(document, dict):
			return entries, [(document, f"a sequencer document is a dict, not {document!r}")]

		modules = document.get("modules", {})

		if not isinstance(modules, dict):
			malformed.append(({"modules": modules}, f"modules is a dict of modules by name, not {modules!r}"))
			modules = {}

		for name, module in modules.items():

			if not isinstance(module, dict) or not isinstance(module.get("settings", {}), dict):
				malformed.append(({"modules": {name: module}}, f"{name}: a module is a dict with a model and settings, not {module!r}"))
				continue

			if name in self._declared:
				model_: typing.Optional[Model] = self.modules[name].model
			else:
				named = module.get("model")
				model_ = known.get(named) if isinstance(named, str) else None
				entries[("module", name)] = named

			for control, value in module.get("settings", {}).items():
				held = model_.controls.get(control) if model_ is not None else None
				if held is not None and held.lane and isinstance(value, dict):
					for index, v in value.items():
						entries[("set", name, control, int(index) if str(index).isdigit() else index)] = v
				elif held is not None and held.lane and model_ is not None:
					try:
						lane = model_._lane_of(value)
					except ValueError as error:
						malformed.append(({"modules": {name: {"settings": {control: value}}}}, f"{name}.{control}: {error}"))
						continue
					for index, v in enumerate(lane):
						entries[("set", name, control, index)] = v
				else:
					entries[("set", name, control)] = value

		patch = document.get("patch", [])

		if not isinstance(patch, list):
			malformed.append(({"patch": patch}, f"patch is a list of cables, not {patch!r}"))
			patch = []

		for cable in patch:
			if not isinstance(cable, (list, tuple)) or len(cable) != 3 or not isinstance(cable[0], str) or not isinstance(cable[1], str):
				malformed.append(({"patch": [cable]}, f"a cable is [from, to, amount], not {cable!r}"))
				continue
			entries[("cable", cable[0], cable[1])] = cable[2]

		removed = document.get("removed", [])

		if not isinstance(removed, list):
			malformed.append(({"removed": removed}, f"removed is a list of module names, not {removed!r}"))
			removed = []

		for name in removed:
			if not isinstance(name, str):
				malformed.append(({"removed": [name]}, f"a removed module is named by a word, not {name!r}"))
				continue
			entries[("removed", name)] = True

		return entries, malformed

	def _refusals (self, entries: typing.Dict[typing.Tuple[typing.Any, ...], typing.Any], models: typing.Optional[typing.Dict[str, Model]] = None) -> typing.Dict[typing.Tuple[typing.Any, ...], str]:

		"""Why each entry cannot be laid on the sequencer as it stands this cycle; an entry left out is fine."""

		known = self._known(models)
		on_sequencer = {n: self.modules[n].model for n in self._declared}
		why: typing.Dict[typing.Tuple[typing.Any, ...], str] = {}

		for key, value in entries.items():
			if key[0] == "module":
				if isinstance(value, str) and value in known:
					on_sequencer[key[1]] = known[value]
				elif not isinstance(key[1], str) or not key[1] or "." in key[1]:
					why[key] = f"a module's name is a word with no dot in it, not {key[1]!r}"
				else:
					why[key] = f"there is no model called {value!r} to add as {key[1]!r}"

		def jack (path: typing.Any, inputs: bool) -> typing.Optional[str]:
			name, _, jack_ = str(path).partition(".")
			if name not in on_sequencer:
				return f"there is nothing called {name!r} on this sequencer"
			jacks = on_sequencer[name].inputs if inputs else on_sequencer[name].outputs
			if jack_ not in jacks:
				return f"{name} ({on_sequencer[name].label}) has no {'input' if inputs else 'output'} called {jack_!r}"
			return None

		for key, value in entries.items():
			if key[0] == "set":
				model_ = on_sequencer.get(key[1])
				control = model_.controls.get(key[2]) if model_ is not None else None
				if model_ is None:
					why[key] = f"there is nothing called {key[1]!r} on this sequencer"
				elif control is None:
					why[key] = f"{key[1]} ({model_.label}) has no control called {key[2]!r}"
				elif control.lane != (len(key) == 4):
					why[key] = f"{key[1]}.{key[2]} is {'a lane' if control.lane else 'not a lane'} now"
				elif control.lane and not (isinstance(key[3], int) and 0 <= key[3] < model_.stages):
					why[key] = f"{key[1]} ({model_.label}) has no stage index {key[3]!r}: it has {model_.stages} stages, from 0"
				else:
					try:
						model_._hold_one(control, value)
					except (TypeError, ValueError) as error:
						why[key] = f"{key[1]}.{key[2]}: {error}"
			elif key[0] == "cable":
				problem = jack(key[1], inputs=False) or jack(key[2], inputs=True)
				if problem is None and (isinstance(value, bool) or not isinstance(value, numbers.Real)):
					problem = f"a cable's amount is a number, not {value!r}"
				if problem is not None:
					why[key] = problem

		return why

	@staticmethod
	def _document_of (entries: typing.Dict[typing.Tuple[typing.Any, ...], typing.Any]) -> typing.Dict[str, typing.Any]:

		"""Entries as a document again: the shape a surface sends."""

		modules: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
		document: typing.Dict[str, typing.Any] = {}

		for key, value in entries.items():
			if key[0] == "module":
				modules.setdefault(key[1], {})["model"] = value
			elif key[0] == "set":
				settings = modules.setdefault(key[1], {}).setdefault("settings", {})
				if len(key) == 4:
					settings.setdefault(key[2], {})[str(key[3])] = value
				else:
					settings[key[2]] = value
			elif key[0] == "cable":
				document.setdefault("patch", []).append([key[1], key[2], value])
			else:
				document.setdefault("removed", []).append(key[1])

		if modules:
			document["modules"] = modules

		return document

	def _lay (self, entries: typing.Dict[typing.Tuple[typing.Any, ...], typing.Any], models: typing.Optional[typing.Dict[str, Model]] = None) -> None:

		"""Lay entries already checked onto the sequencer: modules first, then settings and cables, then removals."""

		known = self._known(models)

		for key, value in entries.items():
			if key[0] == "module" and key[1] not in self._declared:
				self.add(known[value], key[1])

		for key, value in entries.items():
			if key[0] == "set" and key[1] in self.modules:
				module = self.modules[key[1]]
				if len(key) == 4:
					lane = list(module.settings[key[2]])
					lane[key[3]] = module.model._hold_one(module.model.controls[key[2]], value)
					module.settings[key[2]] = lane
				else:
					module.set(**{key[2]: value})
			elif key[0] == "cable":
				self.patch(key[1], key[2], float(value))

		removed = {key[1] for key in entries if key[0] == "removed"}

		for name in removed:
			self.modules.pop(name, None)
			self._declared.discard(name)

		self.cables = {(s, d): a for (s, d), a in self.cables.items() if s.split(".", 1)[0] not in removed and d.split(".", 1)[0] not in removed}

	def _declaration (self) -> typing.Dict[typing.Tuple[typing.Any, ...], typing.Any]:

		"""What the code declared this cycle, as entries: every module, control, stage and cable."""

		entries: typing.Dict[typing.Tuple[typing.Any, ...], typing.Any] = {}

		for name in self._declared:
			module = self.modules[name]
			entries[("module", name)] = module.model.name
			for control, value in module.settings.items():
				if module.model.controls[control].lane:
					for index, v in enumerate(value):
						entries[("set", name, control, index)] = v
				else:
					entries[("set", name, control)] = value

		for (source, destination), amount in self.cables.items():
			entries[("cable", source, destination)] = amount

		return entries

	def _overlay (self, p: subsequence.pattern_builder.PatternBuilder) -> bool:

		"""Lay what the surface holds over the code, after taking back whatever the code changed.  True when what it holds moved.

		The last change wins, per control: an entry the code changed since the cycle
		before goes back to the code.  What the surface still holds is written back into
		the tweak when this build succeeds, so reading the tweak tells the truth.  A
		document carrying the ``revision`` it was made from keeps an entry out that was
		taken back after it, so a surface that has not yet read the take-back cannot
		undo it by sending what it held before.  An entry the sequencer cannot take is
		refused, with its reason, and the part plays on.
		"""

		code = self._declaration()
		changed = set() if self._code is None else {k for k in code.keys() | self._code.keys() if code.get(k) != self._code.get(k)}
		self._code = code

		incoming = p.param(TWEAK)
		moved = False
		malformed: typing.List[typing.Tuple[typing.Any, str]] = []

		if incoming != self._seen:
			entries, malformed = self._entries(incoming if incoming is not None else {})
			based_on = incoming.get("revision") if isinstance(incoming, dict) else None
			if isinstance(based_on, int) and not isinstance(based_on, bool):
				entries = {k: v for k, v in entries.items() if self._taken_at.get(k, -1) <= based_on}
			moved = entries != self._held
			self._held = entries

		touched = {k[1] for k in changed}
		taken = {k for k in self._held if k in changed or (k[0] in ("removed", "module") and k[1] in touched)}

		if taken:
			for k in taken:
				del self._held[k]
			self.taken_back = ([{"revision": self.revision + 1, "entries": self._document_of({k: True for k in taken})}] + self.taken_back)[:32]
			for k in taken:
				self._taken_at[k] = self.revision + 1
			moved = True

		# Checked every cycle, not only when a document arrives: a save can take away
		# the jack, control, stage or option an entry names after it arrived.
		why = self._refusals(self._held)
		refusals = [(piece, reason) for piece, reason in malformed] + [(self._document_of({k: True}), why[k]) for k in why]

		if refusals:
			for k in why:
				del self._held[k]
			self.refused = ([{"revision": self.revision + 1, "entries": piece, "reason": reason} for piece, reason in refusals] + self.refused)[:32]
			logger.warning("The surface's settings named what this sequencer cannot take, left out: %s", "; ".join(reason for _, reason in refusals))
			moved = True

		held = dict(self._document_of(self._held), revision=self.revision + (1 if moved else 0)) if self._held else None

		if held != incoming:
			if held is None:
				p.clear_tweak(TWEAK)
			else:
				p.tweak(**{TWEAK: held})

		self._seen = copy.deepcopy(held)
		self._lay(self._held)

		return moved

	def _jack_of (self, path: str, inputs: bool) -> str:

		"""The kind of the jack *path* names, such as ``"960.lane_a"``, or a ValueError saying why there is none."""

		name, _, jack = str(path).partition(".")
		module = self.modules.get(name)

		if module is None or name not in self._declared:
			raise ValueError(f"there is nothing called {name!r} on this sequencer - add it first")

		return self._jack(module, jack, inputs)

	def _jack (self, module: Module, jack: str, inputs: bool) -> str:

		"""The kind of *module*'s jack, or a ValueError naming the jacks it has."""

		jacks = module.model.inputs if inputs else module.model.outputs

		if jack not in jacks:
			raise ValueError(f"{module.name} ({module.model.label}) has no {'input' if inputs else 'output'} called {jack!r} - it has {list(jacks)}")

		return jacks[jack]

	def _late (self, source: str, reader: str) -> bool:

		"""A cable read against the order cables flow in closes a loop, and reads the step before.

		A module reading its own output (a normal, such as the 960's lane C into its
		timing) sees what it has sent.
		"""

		return source != reader and self._order[source] >= self._order[reader]

	def _send (self, module: Module, jack: str, value: typing.Union[float, bool]) -> None:

		"""Set *module*'s output, waking whatever it feeds later in the flow, and firing what a rising gate or voltage reaches."""

		kind = self._jack(module, jack, inputs=False)
		before = module.values.get(jack)
		module.values[jack] = value

		if before == value:
			return

		path = f"{module.name}.{jack}"
		cables = self._from.get(path, ())

		for destination, _ in cables:
			reader = destination.split(".", 1)[0]
			if self._order[module.name] < self._order[reader]:
				self._wanted.add(reader)

		if kind == GATE and value and not before:
			self._fire(module, jack, check=False)
		elif kind == CV and path not in self._crossed:
			# A voltage into a trigger input fires it as it rises past one half,
			# along each cable at that cable's amount, once a step at most.
			for destination, amount in cables:
				if amount * float(before or 0.0) < 0.5 <= amount * float(value):
					self._crossed.add(path)
					self._arrive(destination)

	def _fire (self, module: Module, jack: str, check: bool = True) -> None:

		"""Fire *module*'s output once this step, along every cable from it with a positive amount."""

		if check:
			self._jack(module, jack, inputs=False)

		path = f"{module.name}.{jack}"

		if path in self._fired:
			return

		self._fired.add(path)

		for destination, amount in self._from.get(path, ()):
			if amount > 0:
				self._arrive(destination)

	def _arrive (self, destination: str) -> None:

		"""A trigger reaching an input: only a trigger input takes one."""

		name, input_jack = destination.split(".", 1)

		if self.modules[name].model.inputs[input_jack] == TRIGGER:
			self._arrivals.setdefault(name, set()).add(input_jack)
			self._all_arrivals.setdefault(name, set()).add(input_jack)
			self._wanted.add(name)

	def _note_on (self, pitch: int, beat: float, velocity: int) -> None:

		"""Start a note, kept until it ends so a note that ends this cycle is placed whole."""

		self._end(pitch, beat)
		self._sounding[pitch] = (beat, velocity)

	def _note_off (self, pitch: int, beat: float) -> None:

		"""End a note: placed whole if it started this cycle, or ended here if it started in an earlier one."""

		if pitch in self._sounding:
			self._end(pitch, beat)
		else:
			self.p.note_off(pitch, beat=beat)

	def _end (self, pitch: int, beat: float) -> None:

		"""Place the note sounding at *pitch* this cycle as a whole note ending at *beat*.  One that lasted no time is dropped."""

		started = self._sounding.pop(pitch, None)

		if started is not None and beat > started[0]:
			self.p.note(pitch, beat=started[0], velocity=started[1], duration=beat - started[0])

	def _flow_order (self, players: typing.Set[str]) -> typing.Dict[str, int]:

		"""The order cables flow in: a module after the modules feeding it, a loop broken where it was declared."""

		names = [n for n in self.modules if n not in players]
		feeds: typing.Dict[str, typing.Set[str]] = {n: set() for n in names}

		for source, destination in self._edges:
			a, b = source.split(".", 1)[0], destination.split(".", 1)[0]
			if a != b and a in feeds and b in feeds:
				feeds[b].add(a)

		order: typing.List[str] = []
		remaining = list(names)

		while remaining:
			ready = [n for n in remaining if feeds[n] <= set(order)]
			chosen = ready[0] if ready else remaining[0]
			order.append(chosen)
			remaining.remove(chosen)

		ranks = {n: i for i, n in enumerate(order)}
		ranks.update({n: len(order) + i for i, n in enumerate(sorted(players))})

		return ranks

	def _step (self, beat: float, players: typing.Set[str]) -> None:

		"""Walk one step: every module once in flow order, again for each trigger that reaches it, then the players."""

		self._fired = set()
		self._crossed = set()
		self._arrivals = {}
		self._all_arrivals = {}
		self._wanted = {n for n in self.modules if n not in players}

		for path in self._injected:
			name, jack = path.split(".", 1)
			self._arrivals.setdefault(name, set()).add(jack)
			self._all_arrivals.setdefault(name, set()).add(jack)

		self._injected.clear()
		calls = 0

		while self._wanted:
			name = min(self._wanted, key=lambda n: self._order[n])
			self._wanted.discard(name)
			if name in players:
				continue
			module = self.modules[name]
			arrived = self._arrivals.pop(name, set())
			module.model.fn(StepContext(self, module, arrived, beat), **module.settings)
			calls += 1
			if calls > 64 * max(1, len(self.modules)):
				raise RuntimeError("the sequencer did not settle within a step")

		for name in sorted(players, key=lambda n: self._order[n]):
			module = self.modules[name]
			module.model.fn(StepContext(self, module, self._all_arrivals.get(name, set()), beat), **module.settings)

		for name, positions in self._positions.items():
			module = self.modules[name]
			positions.append(module.stage - 1 if 1 <= module.stage <= module.model.stages else None)

		self._previous = {f"{n}.{j}": v for n, m in self.modules.items() for j, v in m.values.items()}


# This build's sequencer for each builder, so a pattern that asks twice in one build
# gets the same one.  Weak, and the sequencer holds its builder weakly, so a build that
# raises leaves nothing behind once its builder goes.
_building: "weakref.WeakKeyDictionary[subsequence.pattern_builder.PatternBuilder, Sequencer]" = weakref.WeakKeyDictionary()
_building_lock = threading.Lock()


def sequencer (p: subsequence.pattern_builder.PatternBuilder) -> Sequencer:

	"""This pattern's sequencer, carrying on from its last cycle, with its ``clock`` and ``midi`` already declared.

	Declare its modules and cables, then call ``play()``.  The modules, settings and
	cables are declared afresh every cycle; the stages, memories and random streams
	carry on, and only once the build has succeeded.

	Example::

		import subsequence.constants.durations as dur
		import subsequence.plugins.sequencers as sequencers

		@composition.pattern(channel=6, steps=16, step_duration=dur.SIXTEENTH)
		def lead (p):
			seq = sequencers.sequencer(p)
			seq.add(sequencers.moog_960, "960", lane_a=[0.0, 0.2, 0.1, 0.25])
			seq.patch("clock.out", "960.shift")
			seq.patch("clock.out", "midi.trigger")
			seq.patch("960.lane_a", "midi.pitch")
			seq.play()
	"""

	with _building_lock:
		held = _building.get(p)

	if held is not None:
		return held

	committed = p.memory.get(MEMORY)
	held = committed._carried() if isinstance(committed, Sequencer) else Sequencer()
	held._builder = weakref.ref(p)

	with _building_lock:
		_building[p] = held

	held.add(clock, "clock")
	held.add(midi_out, "midi")

	return held


def pattern (composition: subsequence.composition.Composition, **pattern_options: typing.Any) -> typing.Callable[[typing.Callable[[Sequencer], None]], typing.Callable[..., None]]:

	"""A pattern that is a sequencer: ``def lead (seq)`` declares modules and cables, and is played for you.

	Takes everything ``@composition.pattern`` takes.  The pattern's own verbs are on
	``seq.p``; one meant for what the sequencer plays, such as a swing, goes in
	``seq.after(...)`` so it acts once the notes are placed.

	Example::

		import subsequence.constants.durations as dur
		import subsequence.plugins.sequencers as sequencers

		@sequencers.pattern(composition, channel=6, steps=16, step_duration=dur.SIXTEENTH)
		def lead (seq):
			seq.add(sequencers.moog_960, "960", lane_a=[0.0, 0.2, 0.1, 0.25])
			seq.default_patch("960")
	"""

	def wrap (fn: typing.Callable[[Sequencer], None]) -> typing.Callable[..., None]:

		"""The pattern that builds *fn*'s sequencer and plays it."""

		def build (p: subsequence.pattern_builder.PatternBuilder) -> None:
			held = sequencer(p)
			fn(held)
			held.play()

		build.__name__ = fn.__name__
		build.__qualname__ = fn.__qualname__
		build.__doc__ = fn.__doc__
		decorated: typing.Callable[..., None] = composition.pattern(**pattern_options)(build)

		return decorated

	return wrap


MODELS: typing.Dict[str, Model] = {m.name: m for m in (clock, knob, midi_out)}


def register (*models_: Model) -> None:

	"""Make models known by name, so a sequencer document, and a surface, can add one."""

	for m in models_:
		if not isinstance(m, Model):
			raise TypeError(f"register() takes models made with @sequencers.model, not {m!r}")
		MODELS[m.name] = m


def models () -> typing.List[typing.Dict[str, typing.Any]]:

	"""Every known model's description, as plain data."""

	return [m.describe() for m in MODELS.values()]


def _sequencer_of (composition: subsequence.composition.Composition, pattern_name: str) -> Sequencer:

	"""The sequencer a running pattern last built, or a ValueError."""

	running = composition.running_patterns.get(pattern_name)
	held = running.memory.get(MEMORY) if running is not None else None

	if not isinstance(held, Sequencer):
		raise ValueError(f"{pattern_name!r} is not a running pattern with a sequencer")

	return held


def state (composition: subsequence.composition.Composition, pattern_name: str) -> typing.Dict[str, typing.Any]:

	"""What a surface reads of one pattern's sequencer, as it stood after its last build.

	As it last played, what the surface still holds, what the code took back, what was
	refused and why, the models on it and the cable rule.  The revision moves when the
	sequencer plays differently, when what the surface holds changes (the surface's
	own change, or the code taking an entry back), or when a model on it changes its
	description, as a model written in a watched file can on a save.  A surface
	compares one number after a build.  It is a fresh copy, safe to read from any
	thread.
	"""

	return _sequencer_of(composition, pattern_name).state()


def playing (composition: subsequence.composition.Composition, pattern_name: str) -> typing.Optional[typing.Dict[str, typing.Any]]:

	"""Where each module of one pattern's sequencer was on each step of its last cycle.

	A report rather than state: it changes every cycle, so it is kept out of the
	revision.  The cycle's ``start_beat`` counts from the composition's start, and a
	cycle is built ahead of when it plays (a beat ahead by default), so a surface
	keeps the last cycle's positions until the beat reaches the new one.
	"""

	return _sequencer_of(composition, pattern_name).playing()


@dataclasses.dataclass
class _Listener:

	"""A function told of every build, and whether it has failed before (it is logged once)."""

	callback: typing.Callable[[str, typing.Dict[str, typing.Any], typing.Optional[typing.Dict[str, typing.Any]]], typing.Any]
	failed: bool = False


_listeners: "weakref.WeakKeyDictionary[subsequence.composition.Composition, typing.List[_Listener]]" = weakref.WeakKeyDictionary()
_listeners_lock = threading.Lock()


def on_build (
	composition: subsequence.composition.Composition,
	callback: typing.Callable[[str, typing.Dict[str, typing.Any], typing.Optional[typing.Dict[str, typing.Any]]], typing.Any],
) -> None:

	"""Call *callback* after every successful build of a sequencer in *composition*.

	It is called as ``callback(pattern_name, state, playing)``, with ``state()`` and
	``playing()`` as fresh copies nothing changes afterwards, from the first cycle on.
	A build that raises calls nothing.  It runs on the clock's own loop, inside the
	build, so it should only hand the two on (to a queue, or to another loop) and
	return.  If it raises, the music carries on, and the first failure is logged.

	Example::

		import subsequence.plugins.sequencers as sequencers

		def show (pattern_name, state, playing):
			print(pattern_name, state["revision"], playing["modules"])

		sequencers.on_build(composition, show)
	"""

	if not callable(callback):
		raise TypeError(f"on_build() takes a function, not {callback!r}")

	with _listeners_lock:
		_listeners.setdefault(composition, []).append(_Listener(callback))


def _report (data: typing.Dict[str, typing.Any], pattern_name: typing.Optional[str], held: Sequencer) -> None:

	"""Tell the listeners of the composition whose ``data`` this build shares that its sequencer has built."""

	if pattern_name is None:
		return

	with _listeners_lock:
		found = [list(listeners) for composition, listeners in _listeners.items() if composition.data is data]

	for listeners in found:
		for listener in listeners:
			try:
				listener.callback(pattern_name, held.state(), held.playing())
			except Exception:
				if not listener.failed:
					listener.failed = True
					logger.exception("A sequencer's build listener raised; the music carries on, and later failures of it are not logged")
