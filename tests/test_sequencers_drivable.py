"""Every packaged sequencer model, driven from its JSON description alone, plays and warns of nothing (#5201).

A control surface builds a model's controls from its description and nothing else, as it
does a generator's (``test_catalogue_drivable.py`` is the catalogue's guard).  So each
model goes on a sequencer from a document built only from the descriptions, through JSON:

- at its defaults, with the cables it usually opens with, where it must play;
- with each control at each edge it declares: a number at its bounds, a pitch at 0 and
  127, every option of a choice, both positions of a switch, and a lane set whole to
  each edge of what one stage takes;
- with every single cable from any output on the sequencer to any input.

None may raise or log a warning.  A model added to the package is driven here the day it
is registered, with nothing to list.
"""

import json
import logging
import pathlib
import typing

import mido
import pytest

import subsequence
import subsequence.constants.durations as dur
import subsequence.plugins.sequencers as sequencers


DESCRIBED = {entry["name"]: entry for entry in json.loads(json.dumps(sequencers.models()))}

# Every sequencer has these two already; each other model is driven beside them.
PARTS = ("clock", "midi_out")


class _Warnings (logging.Handler):

	"""Every warning or error the package logs while it is attached."""

	def __init__ (self) -> None:
		super().__init__(logging.WARNING)
		self.messages: typing.List[str] = []

	def emit (self, record: logging.LogRecord) -> None:
		if record.name.startswith("subsequence"):
			self.messages.append(record.getMessage())


def _document (model: typing.Dict[str, typing.Any], setting: typing.Optional[typing.Tuple[str, str, typing.Any]] = None, cable: typing.Optional[typing.Tuple[str, str]] = None) -> typing.Dict[str, typing.Any]:

	"""The model as module ``m`` beside the sequencer's own clock and MIDI out, every control at its default, with its usual cables."""

	parts = {"m": model, "clock": DESCRIBED["clock"], "midi": DESCRIBED["midi_out"]}
	modules = {}

	for name, described in parts.items():
		settings = {c["name"]: c["default"] for c in described["controls"]}
		if setting is not None and setting[0] == name:
			settings[setting[1]] = setting[2]
		modules[name] = {"model": described["name"], "settings": settings}

	patch = [[s.replace("@", "m"), d.replace("@", "m"), 1.0] for s, d in model["default_patch"]]

	if cable is not None:
		patch.append([cable[0], cable[1], 1.0])

	return {"modules": modules, "patch": patch}


def _play (document: typing.Dict[str, typing.Any], tmp_path: pathlib.Path) -> typing.Tuple[typing.List[typing.Tuple[int, int, int]], typing.List[str]]:

	"""Two bars of a pattern whose sequencer is the document and nothing else: what it played, and what it logged."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=1)

	@composition.pattern(channel=1, steps=16, step_duration=dur.SIXTEENTH)
	def driven (p: typing.Any) -> None:
		seq = sequencers.sequencer(p)
		seq.apply(json.loads(json.dumps(document)))
		seq.play()

	caught = _Warnings()
	logging.getLogger("subsequence").addHandler(caught)
	path = tmp_path / "driven.mid"

	try:
		composition.render(bars=2, filename=str(path))
	finally:
		logging.getLogger("subsequence").removeHandler(caught)

	tick, played = 0, []

	for message in mido.MidiFile(str(path)).tracks[0]:
		tick += message.time
		if message.type == "note_on" and message.velocity > 0:
			played.append((tick, message.note, message.velocity))

	return played, caught.messages


def _edges (control: typing.Dict[str, typing.Any]) -> typing.List[typing.Any]:

	"""Each edge a control declares; a lane's are its element's, set on every stage."""

	element = control["of"] if control["kind"] == "lane" else control
	kind = element["kind"]

	if kind == "number":
		values: typing.List[typing.Any] = [element["min"], element["max"]]
	elif kind == "pitch":
		values = [0, 127]
	elif kind == "choice":
		values = [o["value"] for o in element["options"]]
	elif kind == "switch":
		values = [True, False]
	else:
		raise AssertionError(f"{control['name']}: a {kind} control has no edges this guard knows how to drive")

	return [[v] * control["count"] for v in values] if control["kind"] == "lane" else values


DRIVEN = [name for name in DESCRIBED if name not in PARTS]


def test_every_packaged_model_is_driven () -> None:

	"""A floor, so the sweep cannot quietly shrink: the 960, 962 and 1601, and the knob."""

	assert {"moog_960", "moog_962", "arp_1601", "knob"} <= set(DRIVEN)


@pytest.mark.parametrize("name", DRIVEN)
def test_a_model_plays_from_its_description_alone_at_every_edge_and_on_every_cable (name: str, tmp_path: pathlib.Path) -> None:

	model = DESCRIBED[name]
	base, logged = _play(_document(model), tmp_path)

	assert logged == []
	assert base or not model["default_patch"], f"{name} played nothing from its defaults and its usual cables"

	failures: typing.List[str] = []
	edges = changed_edges = 0

	for part, described in (("m", model), ("clock", DESCRIBED["clock"]), ("midi", DESCRIBED["midi_out"])):
		for control in described["controls"]:
			if control["kind"] == "lane":
				assert control["count"] == described["stages"] and len(control["default"]) == control["count"], control
			for value in _edges(control):
				played, logged = _play(_document(model, setting=(part, control["name"], value)), tmp_path)
				edges += 1
				changed_edges += played != base
				if logged:
					failures.append(f"{part}.{control['name']} = {value!r}: {logged}")

	jacks = {"m": model, "clock": DESCRIBED["clock"], "midi": DESCRIBED["midi_out"]}
	outputs = [f"{n}.{j['name']}" for n, d in jacks.items() for j in d["outputs"]]
	inputs = [f"{n}.{j['name']}" for n, d in jacks.items() for j in d["inputs"]]
	cables = changed_cables = 0

	for source in outputs:
		for destination in inputs:
			played, logged = _play(_document(model, cable=(source, destination)), tmp_path)
			cables += 1
			changed_cables += played != base
			if logged:
				failures.append(f"{source} -> {destination}: {logged}")

	assert failures == []
	# The sweep reached something: some edges and some cables change what plays.  A
	# model with no usual cables (the knob) is silent at every setting.
	assert edges and (changed_edges or not model["default_patch"]), f"{name}: {edges} edges, none changed what played"
	assert cables and changed_cables, f"{name}: {cables} cables, none changed what played"
