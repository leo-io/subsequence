"""What a plugin needs from the core, made public as tools a musician can use too (#5200).

The sequencers plugin reaches the core only through public names (#5192).  Each test here
pins one of them: ``p.step_beats``, ``p.start_beat``, ``p.memory``, ``p.tweak()`` and
``p.clear_tweak()``, ``p.after_build()``, ``p.stream_seed`` and
``subsequence.catalogue.describe_parameter()``; and ``composition.tweak()`` handing its change
to the clock, so a tweak never lands partway through a build.
"""

import inspect
import logging
import pathlib
import typing

import mido
import pytest

import subsequence
import subsequence.catalogue
import subsequence.constants.durations as dur
import subsequence.pattern
import subsequence.pattern_builder


def _render (composition: subsequence.Composition, tmp_path: pathlib.Path, bars: int = 4) -> typing.List[typing.Tuple[int, int]]:

	"""Render *bars* and return each note-on as (tick, note)."""

	path = str(tmp_path / "hooks.mid")
	composition.render(bars=bars, filename=path)

	now = 0
	onsets = []

	for message in mido.MidiFile(path).tracks[0]:
		now += message.time
		if message.type == "note_on" and message.velocity > 0:
			onsets.append((now, message.note))

	return onsets


def _composition (seed: typing.Optional[int] = 1) -> subsequence.Composition:

	return subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=seed)


# p.step_beats

def test_a_step_lasts_the_pattern_s_length_over_its_steps (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Sixteen steps of a 4/4 bar are a quarter beat each, and set_length() stretching them over three beats makes them 0.1875."""

	seen: typing.Dict[str, typing.List[float]] = {"sixteenths": [], "eighths": [], "stretched": []}
	composition = _composition()

	def sixteenths (p: typing.Any) -> None:
		seen["sixteenths"].append(p.step_beats)

	def eighths (p: typing.Any) -> None:
		seen["eighths"].append(p.step_beats)

	def stretched (p: typing.Any) -> None:
		p.set_length(3)
		seen["stretched"].append(p.step_beats)

	composition.pattern(channel=1, steps=16, step_duration=dur.SIXTEENTH)(sixteenths)
	composition.pattern(channel=2, steps=8, step_duration=dur.EIGHTH)(eighths)
	composition.pattern(channel=3, steps=16, step_duration=dur.SIXTEENTH)(stretched)
	_render(composition, tmp_path, bars=1)

	assert seen["sixteenths"] and set(seen["sixteenths"]) == {0.25}
	assert seen["eighths"] and set(seen["eighths"]) == {0.5}
	assert seen["stretched"] and set(seen["stretched"]) == {3 / 16}


# p.start_beat

def test_each_cycle_says_the_beat_of_the_piece_it_starts_on (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""A one-bar part starts its cycles on beats 0, 4, 8 and 12; a two-bar part on 0 and 8."""

	starts: typing.Dict[str, typing.List[float]] = {"bar": [], "two_bars": []}
	composition = _composition()

	def bar (p: typing.Any) -> None:
		starts["bar"].append(p.start_beat)

	def two_bars (p: typing.Any) -> None:
		starts["two_bars"].append(p.start_beat)

	composition.pattern(channel=1, beats=4)(bar)
	composition.pattern(channel=2, beats=8)(two_bars)
	_render(composition, tmp_path, bars=4)

	assert starts["bar"][:4] == [0.0, 4.0, 8.0, 12.0]
	assert starts["two_bars"][:2] == [0.0, 8.0]


# p.memory

def test_a_pattern_s_memory_carries_from_cycle_to_cycle (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""The count a cycle leaves is there in the next one, and each pattern keeps its own."""

	counts: typing.Dict[str, typing.List[int]] = {"lead": [], "bass": []}
	composition = _composition()

	def lead (p: typing.Any) -> None:
		p.memory["plays"] = p.memory.get("plays", 0) + 1
		counts["lead"].append(p.memory["plays"])

	def bass (p: typing.Any) -> None:
		p.memory["plays"] = p.memory.get("plays", 0) + 10
		counts["bass"].append(p.memory["plays"])

	composition.pattern(channel=1, beats=4)(lead)
	composition.pattern(channel=2, beats=4)(bass)
	_render(composition, tmp_path, bars=4)

	assert counts["lead"][:4] == [1, 2, 3, 4]
	assert counts["bass"][:4] == [10, 20, 30, 40]
	assert composition.running_patterns["lead"].memory["plays"] == counts["lead"][-1]


def test_a_live_save_keeps_a_pattern_s_memory (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""A save between bars 0 and 1 swaps the function and keeps the memory, so the count goes on rather than starting again."""

	counts: typing.List[typing.Tuple[str, int]] = []
	composition = _composition()
	composition._is_live = True

	def version (label: str) -> typing.Callable[[typing.Any], None]:

		def part (p: typing.Any) -> None:
			p.memory["plays"] = p.memory.get("plays", 0) + 1
			counts.append((label, p.memory["plays"]))

		return part

	composition.pattern(channel=1, beats=4)(version("first"))

	def save (p: typing.Any) -> None:
		if p.cycle == 1:
			composition.pattern(channel=1, beats=4)(version("saved"))

	composition.schedule(save, cycle_beats=4)
	_render(composition, tmp_path, bars=4)

	assert counts[:4] == [("first", 1), ("saved", 2), ("saved", 3), ("saved", 4)]


# p.tweak() and p.clear_tweak()

def test_a_pattern_s_own_tweak_lands_from_its_next_cycle (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Starting with no tweaks at all: each cycle reads one more than the last, and within a cycle the old value holds after tweak()."""

	seen: typing.List[typing.Tuple[int, int]] = []
	composition = _composition()

	def counter (p: typing.Any) -> None:
		n = p.param("n", 0)
		p.tweak(n=n + 1)
		seen.append((n, p.param("n", 0)))

	composition.pattern(channel=1, beats=4)(counter)
	_render(composition, tmp_path, bars=4)

	assert seen[:4] == [(0, 0), (1, 1), (2, 2), (3, 3)]
	assert composition.get_tweaks("counter")["n"] == len(seen)


def test_a_build_that_raises_keeps_none_of_its_tweaks (patch_midi: None, tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture) -> None:

	"""Cycle 0 tweaks and then raises: cycle 1 still reads the default."""

	seen: typing.List[typing.Any] = []
	composition = _composition()

	def faulty (p: typing.Any) -> None:
		seen.append(p.param("x", "default"))
		if p.cycle == 0:
			p.tweak(x="from the failed build")
			raise RuntimeError("this build fails")

	composition.pattern(channel=1, beats=4)(faulty)

	with caplog.at_level(logging.ERROR, logger="subsequence"):
		_render(composition, tmp_path, bars=2)

	assert seen[:2] == ["default", "default"]
	assert any("this build fails" in str(record.exc_info[1]) for record in caplog.records if record.exc_info)


def test_clear_tweak_removes_one_or_all_from_the_next_cycle (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Set two, clear one, then clear the rest: each lands a cycle after it was asked for."""

	seen: typing.List[typing.Dict[str, typing.Any]] = []
	composition = _composition()

	def part (p: typing.Any) -> None:
		seen.append({"a": p.param("a"), "b": p.param("b")})
		if p.cycle == 0:
			p.tweak(a=1, b=2)
		elif p.cycle == 1:
			p.clear_tweak("a")
		elif p.cycle == 2:
			p.clear_tweak()

	composition.pattern(channel=1, beats=4)(part)
	_render(composition, tmp_path, bars=4)

	assert seen[:4] == [{"a": None, "b": None}, {"a": 1, "b": 2}, {"a": None, "b": 2}, {"a": None, "b": None}]


# p.after_build()

def test_after_build_runs_once_a_cycle_in_order_after_the_build (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Two functions run in the order given, after the builder function has returned, once per cycle."""

	order: typing.List[str] = []
	composition = _composition()

	def part (p: typing.Any) -> None:
		p.after_build(lambda: order.append("first"))
		p.after_build(lambda: order.append("second"))
		p.note(60, beat=0, duration=1)
		order.append("built")

	composition.pattern(channel=1, beats=4)(part)
	onsets = _render(composition, tmp_path, bars=3)

	assert order[:9] == ["built", "first", "second"] * 3
	assert [note for _, note in onsets] == [60, 60, 60]


def test_after_build_does_not_run_when_the_build_raises (patch_midi: None, tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture) -> None:

	"""A build that raises keeps nothing: its after_build() never runs and its cycle is silent."""

	ran: typing.List[int] = []
	composition = _composition()

	def part (p: typing.Any) -> None:
		cycle = p.cycle
		p.after_build(lambda: ran.append(cycle))
		p.note(60, beat=0, duration=1)
		if cycle == 1:
			raise RuntimeError("cycle 1 fails")

	composition.pattern(channel=1, beats=4)(part)

	with caplog.at_level(logging.ERROR, logger="subsequence"):
		onsets = _render(composition, tmp_path, bars=3)

	assert ran[:2] == [0, 2]
	assert [tick for tick, _ in onsets] == [0, 3840]


def test_an_after_build_that_raises_fails_its_build (patch_midi: None, tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture) -> None:

	"""As if the pattern itself had raised: that cycle is silent, and the others play."""

	composition = _composition()

	def keep (cycle: int) -> None:
		if cycle == 1:
			raise RuntimeError("the keeping failed")

	def part (p: typing.Any) -> None:
		cycle = p.cycle
		p.note(60, beat=0, duration=1)
		p.after_build(lambda: keep(cycle))

	composition.pattern(channel=1, beats=4)(part)

	with caplog.at_level(logging.ERROR, logger="subsequence"):
		onsets = _render(composition, tmp_path, bars=3)

	assert [tick for tick, _ in onsets] == [0, 3840]
	assert any("the keeping failed" in str(record.exc_info[1]) for record in caplog.records if record.exc_info)


def test_after_build_takes_only_a_function (patch_midi: None) -> None:

	pattern = subsequence.pattern.Pattern(channel=0, length=4)
	builder = subsequence.pattern_builder.PatternBuilder(pattern, cycle=0)

	with pytest.raises(TypeError, match="takes a function"):
		builder.after_build(42)  # type: ignore[arg-type]


def test_a_hand_made_builder_s_after_build_runs_when_its_pattern_is_finished (patch_midi: None) -> None:

	"""The Direct Pattern API: a builder made by hand is finished when the sequencer schedules its pattern (#2959), and its after_build() runs then, once."""

	pattern = subsequence.pattern.Pattern(channel=0, length=4)
	builder = subsequence.pattern_builder.PatternBuilder(pattern, cycle=0)
	ran: typing.List[str] = []

	builder.after_build(lambda: ran.append("ran"))
	assert ran == []

	pattern._finish_builds()
	pattern._finish_builds()

	assert ran == ["ran"]


# p.stream_seed

def test_a_pattern_s_stream_seed_is_steady_its_own_and_none_unseeded (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""The same on every cycle, different between patterns, the composition's own derivation, and None with no seed."""

	seeds: typing.Dict[str, typing.List[typing.Optional[int]]] = {"lead": [], "bass": []}
	composition = _composition(seed=7)

	def lead (p: typing.Any) -> None:
		seeds["lead"].append(p.stream_seed)

	def bass (p: typing.Any) -> None:
		seeds["bass"].append(p.stream_seed)

	composition.pattern(channel=1, beats=4)(lead)
	composition.pattern(channel=2, beats=4)(bass)
	_render(composition, tmp_path, bars=3)

	assert len(seeds["lead"]) >= 3 and len(set(seeds["lead"])) == 1
	assert seeds["lead"][0] is not None and seeds["lead"][0] != seeds["bass"][0]
	assert seeds["lead"][0] == composition._stream_seed("lead")

	unseeded: typing.List[typing.Optional[int]] = []
	plain = _composition(seed=None)
	plain.pattern(channel=1, beats=4)(lambda p: unseeded.append(p.stream_seed))
	_render(plain, tmp_path, bars=1)

	assert unseeded and set(unseeded) == {None}


# subsequence.catalogue.describe_parameter()

def test_describe_parameter_describes_a_control_as_the_catalogue_does () -> None:

	"""The public describer gives exactly the entry the catalogue publishes for a generator's parameter."""

	method = subsequence.pattern_builder.PatternBuilder.euclidean
	signature = inspect.signature(method)
	hints = typing.get_type_hints(method, include_extras=True)
	published = next(entry for entry in subsequence.describe_generator("euclidean")["parameters"] if entry["name"] == "pulses")

	assert subsequence.catalogue.describe_parameter("pulses", signature.parameters["pulses"], hints["pulses"], signature.parameters) == published


# composition.tweak() on the clock

def test_composition_tweak_and_clear_tweak_hand_their_change_to_the_clock (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Nothing changes until the clock makes the change, so a tweak from another thread cannot land partway through a build."""

	composition = _composition()
	composition.pattern(channel=1, beats=4)(lambda p: None)
	_render(composition, tmp_path, bars=1)

	handed: typing.List[typing.Tuple[typing.Callable[..., typing.Any], typing.Tuple[typing.Any, ...]]] = []
	composition._sequencer._on_the_clock = lambda change, *args: handed.append((change, args))  # type: ignore[method-assign]
	name = next(iter(composition.running_patterns))

	composition.tweak(name, density=0.5)
	assert composition.get_tweaks(name) == {}
	assert len(handed) == 1

	change, args = handed.pop()
	change(*args)
	assert composition.get_tweaks(name) == {"density": 0.5}

	composition.clear_tweak(name, "density")
	assert composition.get_tweaks(name) == {"density": 0.5}

	change, args = handed.pop()
	change(*args)
	assert composition.get_tweaks(name) == {}


def test_after_build_sees_the_notes_where_they_finally_sit (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""A legato chord is sized once the build is done (#3463): the body reads its placeholder length, after_build() the final one."""

	lengths: typing.Dict[str, typing.List[int]] = {"body": [], "after": []}
	composition = _composition()

	def chord_length (p: typing.Any) -> int:
		return next(note.duration for note in p.placed() if note.pitch == 60)

	def part (p: typing.Any) -> None:
		p.chord([60, 64, 67], beat=0, legato=0.75)
		p.note(72, beat=2, duration=1)
		lengths["body"].append(chord_length(p))
		p.after_build(lambda: lengths["after"].append(chord_length(p)))

	composition.pattern(channel=1, beats=4)(part)
	_render(composition, tmp_path, bars=1)

	assert lengths["after"] and set(lengths["after"]) == {36}
	assert lengths["body"] and set(lengths["body"]) != {36}


def test_a_build_finished_twice_runs_its_after_build_once (patch_midi: None) -> None:

	"""Finishing forgets what it ran, as it forgets the glides it laid."""

	pattern = subsequence.pattern.Pattern(channel=0, length=4)
	builder = subsequence.pattern_builder.PatternBuilder(pattern, cycle=0)
	ran: typing.List[str] = []

	builder.after_build(lambda: ran.append("ran"))
	builder._finish_build()
	builder._finish_build()

	assert ran == ["ran"]
