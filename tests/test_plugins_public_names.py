"""A plugin reaches the core only through public names (#5192, #5201).

Two halves, because each misses what the other sees:

- **In the source**: every private name a plugin reads (``x._name``, or
  ``getattr(x, "_name")``) must be one a plugin defines itself.  This catches a
  reach into a core module, such as ``subsequence.catalogue._describe_parameter``,
  which never touches an object at run time.
- **At run time**: while every part of the sequencers plugin runs, a read of a
  private attribute of the builder, a pattern or the composition from a plugin's own
  code fails.  This catches a name a plugin happens to define as well, and a name
  built at run time.
"""

import ast
import json
import pathlib
import sys
import typing

import pytest

import subsequence
import subsequence.composition
import subsequence.constants.durations as dur
import subsequence.pattern
import subsequence.pattern_builder
import subsequence.plugins.sequencers as sequencers


PLUGINS = pathlib.Path(subsequence.__file__).resolve().parent / "plugins"
SOURCES = sorted(PLUGINS.rglob("*.py"))
ACCESSORS = ("getattr", "setattr", "hasattr", "delattr")


def _private (name: str) -> bool:

	return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def _defined (trees: typing.Iterable[ast.AST]) -> typing.Set[str]:

	"""Every private name the plugins define: functions, classes, and names and attributes they assign."""

	names: typing.Set[str] = set()

	for tree in trees:
		for node in ast.walk(tree):
			if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
				names.add(node.name)
			elif isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Store):
				names.add(node.id if isinstance(node, ast.Name) else node.attr)

	return {name for name in names if _private(name)}


def _reached (tree: ast.AST) -> typing.List[typing.Tuple[int, str]]:

	"""Every private name *tree* reads from something: an attribute, or a string given to getattr() and its kin."""

	found: typing.List[typing.Tuple[int, str]] = []

	for node in ast.walk(tree):
		if isinstance(node, ast.Attribute) and _private(node.attr):
			found.append((node.lineno, node.attr))
		elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ACCESSORS and len(node.args) > 1:
			name = node.args[1]
			if not (isinstance(name, ast.Constant) and isinstance(name.value, str)):
				found.append((node.lineno, f"<a name built at run time, given to {node.func.id}()>"))
			elif _private(name.value):
				found.append((node.lineno, name.value))
		elif isinstance(node, (ast.Import, ast.ImportFrom)):
			module = node.module if isinstance(node, ast.ImportFrom) else None
			for alias in node.names:
				dotted = f"{module}.{alias.name}" if module else alias.name
				if any(_private(part) for part in dotted.split(".")):
					found.append((node.lineno, dotted))

	return found


def test_the_plugins_are_found () -> None:

	"""A floor, so the sweep cannot quietly read nothing."""

	assert {path.name for path in SOURCES} >= {"__init__.py", "engine.py", "moog.py", "arp.py"}


def test_a_plugin_reads_no_private_name_it_does_not_define () -> None:

	trees = {path: ast.parse(path.read_text()) for path in SOURCES}
	own = _defined(trees.values())
	reached = [
		f"{path.relative_to(PLUGINS.parent)}:{line} {name}"
		for path, tree in trees.items()
		for line, name in _reached(tree)
		if name not in own
	]

	assert own, "the plugins define no private names at all - has the reading changed?"
	assert reached == []


def test_the_core_never_names_a_plugin () -> None:

	"""The other half of the rule: nothing outside subsequence/plugins imports one or names it."""

	core = [path for path in sorted(PLUGINS.parent.rglob("*.py")) if PLUGINS not in path.parents]
	naming = [f"{path.relative_to(PLUGINS.parent)}" for path in core if "subsequence.plugins" in path.read_text()]

	assert len(core) > 50
	assert naming == []


def test_the_source_check_sees_a_reach_into_the_core () -> None:

	"""The check above, on code that does each thing it forbids."""

	tree = ast.parse(
		"import subsequence.catalogue\n"
		"subsequence.catalogue._describe_parameter\n"
		"p._pattern.length\n"
		"getattr(p, '_tweaks')\n"
		"getattr(p, name)\n"
		"from subsequence import _private_module\n"
		"self._own = 1\n"
		"self._own\n"
	)
	own = _defined([tree])

	assert own == {"_own"}
	assert sorted(name for _, name in _reached(tree) if name not in own) == sorted([
		"_describe_parameter", "_pattern", "_tweaks", "<a name built at run time, given to getattr()>", "subsequence._private_module",
	])


def _exercise (tmp_path: pathlib.Path) -> None:

	"""Every part of the plugin a musician or a surface reaches: both forms, every model, a surface's settings, the reads and the build hook."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=1)

	@composition.pattern(channel=1, steps=16, step_duration=dur.SIXTEENTH)
	def lead (p: typing.Any) -> None:
		seq = sequencers.sequencer(p)
		seq.add(sequencers.moog_960, "960", lane_a=[0.1, 0.2], mode=["normal", "skip"], timing=True)
		seq.add(sequencers.moog_962, "962")
		seq.add(sequencers.knob, "lift", value=0.2)
		seq.add(sequencers.midi_out, "midi", lowest=40)
		seq.patch("clock.out", "960.shift")
		seq.patch("960.stage1", "962.shift")
		seq.patch("960.lane_a", "962.in1")
		seq.patch("lift.out", "962.in2")
		seq.patch("962.out", "midi.pitch")
		seq.patch("960.stage2", "midi.gate")
		seq.patch("960.lane_b", "midi.cc")
		seq.inject("960.stage3")
		seq.after(lambda: seq.p.swing(55))
		seq.play()

	@sequencers.pattern(composition, channel=2, steps=4, step_duration=dur.SIXTEENTH)
	def arp (seq: sequencers.Sequencer) -> None:
		seq.add(sequencers.arp_1601, "1601", slider=[i / 24 for i in range(16)], order="random", split="8/2")
		seq.default_patch("1601")
		seq.apply({"modules": {"extra": {"model": "knob"}}, "patch": [["extra.out", "1601.cv_in", 1]]})

	@composition.pattern(channel=3, beats=4)
	def surface (p: typing.Any) -> None:
		p.hit_steps(72, [0])
		if p.cycle == 1:
			composition.tweak("lead", sequencer={"revision": 1, "modules": {"960": {"settings": {"lane_a": {"1": 0.5}}}, "add": {"model": "knob"}}, "patch": [["add.out", "midi.velocity", 1]], "removed": ["lift"]})
		if p.cycle == 2:
			composition.tweak("lead", sequencer={"modules": {"960": {"settings": {"mode": {"0": "sideways"}}}}})

	heard: typing.List[str] = []
	sequencers.on_build(composition, lambda name, state, playing: heard.append(json.dumps([name, state, playing])))
	composition.render(bars=4, filename=str(tmp_path / "exercise.mid"))
	json.dumps([sequencers.state(composition, "lead"), sequencers.playing(composition, "arp"), sequencers.models()])

	assert len(heard) >= 8


def test_a_plugin_reads_no_private_attribute_of_the_core_while_it_plays (tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:

	reads: typing.Dict[str, int] = {"public": 0}
	private: typing.List[str] = []

	def spy_on (cls: type) -> None:

		original = cls.__getattribute__

		def spy (self: typing.Any, name: str) -> typing.Any:
			caller = sys._getframe(1).f_code.co_filename
			if caller.startswith(str(PLUGINS)):
				if _private(name):
					private.append(f"{cls.__name__}.{name} from {pathlib.Path(caller).name}:{sys._getframe(1).f_lineno}")
				else:
					reads["public"] += 1
			return original(self, name)

		monkeypatch.setattr(cls, "__getattribute__", spy)

	for cls in (subsequence.pattern_builder.PatternBuilder, subsequence.pattern.Pattern, subsequence.composition.Composition):
		spy_on(cls)

	_exercise(tmp_path)

	# The spy saw the plugin at work, so an empty list below means something.
	assert reads["public"] > 100
	assert private == []
