"""The sequencers plugin (#5201): models patched with cables and played inside a pattern.

Every scenario is rendered through a Composition and read back from the MIDI file, as a
musician would hear it.  The first half carries the sketch's measurements (#5190) into
the package; the second pins what the package adds: a sequencer committed only by a
build that succeeds, a random stream per module, the per-cycle ``playing`` report, the
build hook, notes inside a step, and gate notes placed whole.
"""

import json
import logging
import math
import pathlib
import typing

import mido
import pytest

import subsequence
import subsequence.constants.durations as dur
import subsequence.pattern
import subsequence.pattern_builder
import subsequence.plugins.sequencers as sequencers
import subsequence.plugins.sequencers.engine


LANE_A = [s / 60 for s in (0, 3, 7, 10, 12, 15, 19, 22)]
PITCH = [36 + s for s in (0, 3, 7, 10, 12, 15, 19, 22)]
UP = 12 / 60

Played = typing.List[typing.Tuple[float, int, int, float]]
Declare = typing.Callable[[subsequence.Composition], None]


class _Warnings (logging.Handler):

	"""Every warning or error the package logs while it is attached."""

	def __init__ (self) -> None:
		super().__init__(logging.WARNING)
		self.messages: typing.List[str] = []

	def emit (self, record: logging.LogRecord) -> None:
		if record.name.startswith("subsequence"):
			self.messages.append(record.getMessage())


def _read (path: pathlib.Path) -> typing.Tuple[typing.Dict[int, Played], typing.List[typing.Tuple[float, int, int]]]:

	"""Each channel's notes as (beat, pitch, velocity, length), and every controller as (beat, control, value)."""

	midi = mido.MidiFile(str(path))
	open_notes: typing.Dict[typing.Tuple[int, int], typing.Tuple[int, int]] = {}
	found: typing.Dict[int, Played] = {}
	ccs: typing.List[typing.Tuple[float, int, int]] = []

	for track in midi.tracks:
		tick = 0
		for message in track:
			tick += message.time
			if message.type == "control_change":
				ccs.append((round(tick / midi.ticks_per_beat, 4), message.control, message.value))
			if message.type == "note_on" and message.velocity > 0:
				open_notes[(message.channel, message.note)] = (tick, message.velocity)
			elif message.type in ("note_off", "note_on") and (message.channel, message.note) in open_notes:
				start, velocity = open_notes.pop((message.channel, message.note))
				found.setdefault(message.channel + 1, []).append(
					(round(start / midi.ticks_per_beat, 4), message.note, velocity, round((tick - start) / midi.ticks_per_beat, 3))
				)

	return {channel: sorted(events) for channel, events in found.items()}, ccs


def _render (declare: Declare, tmp_path: pathlib.Path, bars: int = 2, warnings: int = 0, seed: typing.Optional[int] = 1) -> Played:

	"""Render *bars* of what *declare* declares and return channel 1's notes, failing on any warning not expected."""

	return _render_with_ccs(declare, tmp_path, bars, warnings, seed)[0]


def _render_with_ccs (declare: Declare, tmp_path: pathlib.Path, bars: int = 2, warnings: int = 0, seed: typing.Optional[int] = 1) -> typing.Tuple[Played, typing.List[typing.Tuple[float, int, int]]]:

	"""As ``_render``, with channel 1's controllers too."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=seed)
	declare(composition)
	caught = _Warnings()
	logging.getLogger("subsequence").addHandler(caught)
	path = tmp_path / "sequencers.mid"

	try:
		composition.render(bars=bars, filename=str(path))
	finally:
		logging.getLogger("subsequence").removeHandler(caught)

	assert len(caught.messages) == warnings, caught.messages
	found, ccs = _read(path)

	return found.get(1, []), ccs


def _lead (body: typing.Callable[[sequencers.Sequencer, typing.Any], None], steps: int = 16, after: typing.Optional[typing.Callable[[typing.Any], None]] = None) -> Declare:

	"""An ordinary pattern called lead whose body declares a sequencer and plays it."""

	def declare (composition: subsequence.Composition) -> None:

		@composition.pattern(channel=1, steps=steps, step_duration=dur.SIXTEENTH)
		def lead (p: typing.Any) -> None:
			seq = sequencers.sequencer(p)
			body(seq, p)
			seq.play()
			if after is not None:
				after(p)

	return declare


def _plain (seq: sequencers.Sequencer, p: typing.Any) -> None:

	seq.add(sequencers.moog_960, "960", lane_a=LANE_A)
	seq.default_patch("960")


def _pitches (played: Played) -> typing.List[int]:

	return [n for _, n, _, _ in played]


def _bars (played: Played, bars: int) -> typing.List[typing.List[typing.Tuple[float, int, int]]]:

	"""Per bar, the sorted (beat in the bar, pitch, velocity) played."""

	return [sorted((round(b - bar * 4, 4), n, v) for b, n, v, _ in played if bar * 4 <= b < (bar + 1) * 4) for bar in range(bars)]


def _pitches_by_bar (played: Played, bars: int) -> typing.List[typing.List[int]]:

	return [[n for _, n, _ in bar] for bar in _bars(played, bars)]


# What the sketch measured, in the package ------------------------------------------------------------------------

def _five (seq: sequencers.Sequencer, p: typing.Any) -> None:

	"""Stage 6 into stage 1: a five-stage loop."""

	_plain(seq, p)
	seq.patch("960.stage6", "960.stage1")


def test_a_960_loops_five_stages_unbroken_through_four_bars (tmp_path: pathlib.Path) -> None:

	played = _render(_lead(_five), tmp_path, bars=4)

	assert [b for b, *_ in played] == [i * 0.25 for i in range(64)]
	assert _pitches(played) == [PITCH[i % 5] for i in range(64)]


def test_one_beat_cycles_play_the_same_loop (tmp_path: pathlib.Path) -> None:

	"""The stage carries from cycle to cycle, so the loop is free of the pattern's length."""

	assert _render(_lead(_five, steps=4), tmp_path, bars=4) == _render(_lead(_five), tmp_path, bars=4)


def test_the_decorator_form_plays_what_the_pattern_form_plays (tmp_path: pathlib.Path) -> None:

	def decorated (composition: subsequence.Composition) -> None:

		@sequencers.pattern(composition, channel=1, steps=16, step_duration=dur.SIXTEENTH)
		def lead (seq: sequencers.Sequencer) -> None:
			_five(seq, seq.p)

	assert _render(decorated, tmp_path, bars=4) == _render(_lead(_five), tmp_path, bars=4)


def test_the_timing_switch_makes_each_stage_last_its_own_steps (tmp_path: pathlib.Path) -> None:

	lane_c = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

	def timed (seq: sequencers.Sequencer, p: typing.Any) -> None:
		seq.add(sequencers.moog_960, "960", lane_a=LANE_A, lane_c=lane_c, timing=True)
		seq.patch("clock.out", "960.shift")
		seq.patch("960.lane_a", "midi.pitch")
		for n in range(1, 9):
			seq.patch(f"960.stage{n}", "midi.trigger")

	played = _render(_lead(timed), tmp_path, bars=4)
	lengths = [int(math.floor(8 ** (1 - cv) + 0.5)) for cv in lane_c]
	onsets: typing.List[float] = []
	beat, k = 0.0, 0

	while beat < 16:
		onsets.append(beat)
		beat += lengths[k % 8] * 0.25
		k += 1

	assert len(set(lengths)) > 3
	assert [b for b, *_ in played] == onsets


def _tie (seq: sequencers.Sequencer, p: typing.Any) -> None:

	"""Stages 4 and 5 into the MIDI out's gate."""

	seq.add(sequencers.moog_960, "960", lane_a=LANE_A)
	seq.patch("clock.out", "960.shift")
	seq.patch("960.lane_a", "midi.pitch")
	seq.patch("960.stage4", "midi.gate")
	seq.patch("960.stage5", "midi.gate")


def test_two_gated_stages_play_legato_across_a_cycle_end (tmp_path: pathlib.Path) -> None:

	"""In one-beat cycles stage 4 is the last step of one cycle and stage 5 the first of the next: the second note starts a pulse before the first ends."""

	played = _render(_lead(_tie, steps=4), tmp_path, bars=2)

	assert [(b, n, d) for b, n, _, d in played[:2]] == [(0.75, PITCH[3], 0.292), (1.0, PITCH[4], 0.25)]


def test_two_gated_stages_of_one_pitch_tie_into_one_note (tmp_path: pathlib.Path) -> None:

	def same_pitch (seq: sequencers.Sequencer, p: typing.Any) -> None:
		_tie(seq, p)
		seq.add(sequencers.moog_960, "960", lane_a=LANE_A[:4] + [LANE_A[3]] + LANE_A[5:])

	played = _render(_lead(same_pitch, steps=4), tmp_path, bars=2)

	assert [(b, n, d) for b, n, _, d in played[:2]] == [(0.75, PITCH[3], 0.5), (2.75, PITCH[3], 0.5)]


def test_a_960_s_three_lanes_through_a_962_make_twenty_four_steps (tmp_path: pathlib.Path) -> None:

	def twenty_four (seq: sequencers.Sequencer, p: typing.Any) -> None:
		seq.add(sequencers.moog_960, "960", lane_a=LANE_A, lane_b=[v + 12 / 60 for v in LANE_A], lane_c=[v + 24 / 60 for v in LANE_A])
		seq.add(sequencers.moog_962, "962")
		seq.patch("clock.out", "960.shift")
		seq.patch("clock.out", "midi.trigger")
		seq.patch("960.stage1", "962.shift")
		for n, lane in enumerate(("lane_a", "lane_b", "lane_c"), start=1):
			seq.patch(f"960.{lane}", f"962.in{n}")
		seq.patch("962.out", "midi.pitch")

	played = _render(_lead(twenty_four), tmp_path, bars=4)

	assert _pitches(played[:48]) == (PITCH + [x + 12 for x in PITCH] + [x + 24 for x in PITCH]) * 2


def test_a_lane_plays_as_a_controller_and_a_swing_acts_after_the_sequencer (tmp_path: pathlib.Path) -> None:

	def filter_lane (seq: sequencers.Sequencer, p: typing.Any) -> None:
		seq.add(sequencers.moog_960, "960", lane_a=LANE_A, lane_b=[i / 7 for i in range(8)])
		seq.add(sequencers.midi_out, "midi", cc_number=19)
		seq.default_patch("960")
		seq.patch("960.lane_b", "midi.cc")
		seq.after(lambda: seq.p.swing(60))

	played, ccs = _render_with_ccs(_lead(filter_lane), tmp_path, bars=1)

	assert [v for _, c, v in ccs if c == 19][:8] == [round(i / 7 * 127) for i in range(8)]
	assert played[1][0] > 0.25 and played[2][0] == 0.5


def test_a_surface_s_document_lays_over_the_code_and_hands_back_when_cleared (tmp_path: pathlib.Path) -> None:

	def overridden (composition: subsequence.Composition) -> None:

		@composition.pattern(channel=1, steps=16, step_duration=dur.SIXTEENTH)
		def lead (p: typing.Any) -> None:
			seq = sequencers.sequencer(p)
			_plain(seq, p)
			seq.play()

		@composition.pattern(channel=3, steps=16, step_duration=dur.SIXTEENTH)
		def surface (p: typing.Any) -> None:
			p.hit_steps(72, [0])
			if p.cycle == 1:
				composition.tweak("lead", sequencer={"modules": {"960": {"settings": {"lane_a": [v + UP for v in LANE_A], "mode": ["normal"] * 4 + ["skip"] * 4}}}})
			if p.cycle == 3:
				composition.clear_tweak("lead", "sequencer")

	played = _render(overridden, tmp_path, bars=6)
	by_bar = [{n for b, n, _, _ in played if bar * 4 <= b < bar * 4 + 4} for bar in range(6)]

	assert by_bar[0] == by_bar[1] == set(PITCH)
	assert by_bar[2] == by_bar[3] == {x + 12 for x in PITCH[:4]}
	assert by_bar[4] == by_bar[5] == set(PITCH)


SLIDERS = [i / 24 for i in range(16)]


def _arp (settings: typing.Dict[str, typing.Any], pitch_from: str = "1601.quantised_a", transpose: bool = False, trigger_from: str = "clock.out") -> Declare:

	def body (seq: sequencers.Sequencer, p: typing.Any) -> None:
		seq.add(sequencers.arp_1601, "1601", slider=SLIDERS, **settings)
		if transpose:
			seq.add(sequencers.knob, "transpose", value=12 / 60)
			seq.patch("transpose.out", "1601.cv_in")
		seq.patch("clock.out", "1601.step")
		seq.patch(trigger_from, "midi.trigger")
		seq.patch(pitch_from, "midi.pitch")

	return _lead(body)


RESET_BUS = ["1"] * 8 + ["3"] + ["1"] * 7


def test_the_1601_s_bus_3_resets_or_skips (tmp_path: pathlib.Path) -> None:

	assert _pitches(_render(_arp({"bus": RESET_BUS, "bus_3": "reset"}), tmp_path)[:16]) == [36 + i for i in range(8)] * 2
	assert _pitches(_render(_arp({"bus": RESET_BUS, "bus_3": "skip"}), tmp_path)[:15]) == [36 + i for i in range(16) if i != 8]


def test_the_1601_s_cv_input_transposes_after_its_quantiser (tmp_path: pathlib.Path) -> None:

	assert _pitches(_render(_arp({}, transpose=True), tmp_path)[:16]) == [48 + i for i in range(16)]


def test_the_1601_split_8_2_sends_steps_9_to_16_to_b (tmp_path: pathlib.Path) -> None:

	assert _pitches(_render(_arp({"split": "8/2"}, pitch_from="1601.quantised_b"), tmp_path)[:16]) == [44 + i for i in range(8)] * 2


def test_the_1601_s_clocked_gate_1_sounds_bus_1_only (tmp_path: pathlib.Path) -> None:

	assert _pitches(_render(_arp({"bus": ["1", "2"] * 8}, trigger_from="1601.clocked_bus1"), tmp_path)[:8]) == [36 + i for i in range(0, 16, 2)]


@sequencers.model(stages=8, inputs={"clock": sequencers.TRIGGER, "reset": sequencers.TRIGGER}, outputs={"pitch": sequencers.CV, **sequencers.stage_jacks(8, sequencers.GATE)})
def pendulum (
	s: sequencers.StepContext,
	pitch: sequencers.Lane[sequencers.Knob] = 0.0,
	stay: typing.Annotated[float, sequencers.Span(0.0, 1.0)] = 0.0,
) -> None:

	"""Eight stages, there and back, with a chance of staying on a stage for another step."""

	if s.received("reset") or s.stage == 0:
		s.stage, s.memory["direction"] = 1, 1
	elif s.received("clock") and s.rng.random() >= stay:
		if not 1 <= s.stage + s.memory["direction"] <= 8:
			s.memory["direction"] *= -1
		s.stage += s.memory["direction"]

	s.send("pitch", pitch[s.stage - 1])

	for n in range(1, 9):
		s.send(f"stage{n}", s.stage == n)


def _swinging (seq: sequencers.Sequencer, p: typing.Any, stay: float = 0.0) -> None:

	seq.add(pendulum, "pendulum", pitch=LANE_A, stay=stay)
	seq.patch("clock.out", "pendulum.clock")
	seq.patch("clock.out", "midi.trigger")
	seq.patch("pendulum.pitch", "midi.pitch")


def test_a_model_written_from_scratch_plays (tmp_path: pathlib.Path) -> None:

	played = _render(_lead(_swinging), tmp_path, bars=2)
	order = [1, 2, 3, 4, 5, 6, 7, 8, 7, 6, 5, 4, 3, 2, 1, 2]

	assert _pitches(played[:16]) == [PITCH[i - 1] for i in order]
	assert [c["name"] for c in pendulum.describe()["controls"]] == ["pitch", "stay"]


# What a surface sets: one entry per control, per stage and per cable, under the last change winning.

def _with_surface (
	code: typing.Callable[[sequencers.Sequencer, typing.Any], None],
	surface: typing.Callable[[subsequence.Composition, int, typing.Dict[typing.Any, typing.Any]], None],
) -> typing.Tuple[Declare, typing.Dict[typing.Any, typing.Any]]:

	"""A lead pattern whose body is code(seq, p), and a surface pattern reading its state and acting at each cycle."""

	seen: typing.Dict[typing.Any, typing.Any] = {}

	def declare (composition: subsequence.Composition) -> None:

		@composition.pattern(channel=1, steps=16, step_duration=dur.SIXTEENTH)
		def lead (p: typing.Any) -> None:
			seq = sequencers.sequencer(p)
			code(seq, p)
			seq.play()

		@composition.pattern(channel=3, steps=16, step_duration=dur.SIXTEENTH)
		def surface_pattern (p: typing.Any) -> None:
			p.hit_steps(72, [0])
			if p.cycle == 0:
				return          # a pattern joins the running set after its first build, as tweak() also finds
			seen[p.cycle] = json.loads(json.dumps(sequencers.state(composition, "lead")))
			seen.setdefault("tweaks", {})[p.cycle] = composition.get_tweaks("lead").get("sequencer")
			surface(composition, p.cycle, seen)

	return declare, seen


def _code_a (seq: sequencers.Sequencer, p: typing.Any) -> None:

	"""The code changes stage 5 from the fourth cycle."""

	lane = list(LANE_A)

	if p.cycle >= 3:
		lane[4] = LANE_A[4] + 5 / 60

	seq.add(sequencers.moog_960, "960", lane_a=lane)
	seq.default_patch("960")


GLASS = [PITCH[0], PITCH[1], PITCH[2] + 12, PITCH[3], PITCH[4] + 12, PITCH[5], PITCH[6], PITCH[7]] * 2
CODE_WON = [PITCH[0], PITCH[1], PITCH[2] + 12, PITCH[3], PITCH[4] + 5, PITCH[5], PITCH[6], PITCH[7]] * 2
THIRD_UP = [PITCH[0], PITCH[1], PITCH[2] + 12] + PITCH[3:]


def test_each_stage_is_its_own_control_and_the_code_takes_back_only_what_it_changed (tmp_path: pathlib.Path) -> None:

	def surface (composition: subsequence.Composition, cycle: int, seen: typing.Dict[typing.Any, typing.Any]) -> None:
		if cycle == 1:
			composition.tweak("lead", sequencer={"modules": {"960": {"settings": {"lane_a": {"2": LANE_A[2] + UP, "4": LANE_A[4] + UP}}}}})

	declare, seen = _with_surface(_code_a, surface)
	by_bar = _pitches_by_bar(_render(declare, tmp_path, bars=6), 6)

	assert by_bar[0] == by_bar[1] == PITCH * 2
	assert by_bar[2] == GLASS
	assert by_bar[3] == by_bar[4] == by_bar[5] == CODE_WON
	assert seen[3]["held"] == {"modules": {"960": {"settings": {"lane_a": {"2": LANE_A[2] + UP}}}}}
	assert seen[3]["taken_back"][0]["entries"] == {"modules": {"960": {"settings": {"lane_a": {"4": True}}}}}
	assert seen["tweaks"][3] == dict(seen[3]["held"], revision=seen[3]["revision"])
	assert seen[2]["revision"] > seen[1]["revision"] and seen[3]["revision"] > seen[2]["revision"]
	assert seen[3]["revision"] == seen[4]["revision"] == seen[5]["revision"]


def test_a_cable_pulled_out_on_the_surface_comes_back_when_the_code_changes_it (tmp_path: pathlib.Path) -> None:

	def code (seq: sequencers.Sequencer, p: typing.Any) -> None:
		seq.add(sequencers.moog_960, "960", lane_a=LANE_A, lane_b=1.0, lane_c=0.2)
		seq.default_patch("960")
		seq.patch("960.lane_b", "midi.velocity", 1.0 if p.cycle < 3 else 0.5)

	def surface (composition: subsequence.Composition, cycle: int, seen: typing.Dict[typing.Any, typing.Any]) -> None:
		if cycle == 1:
			composition.tweak("lead", sequencer={"patch": [["960.lane_b", "midi.velocity", 0], ["960.lane_c", "midi.velocity", 1.0]]})

	declare, seen = _with_surface(code, surface)
	velocities = [sorted({v for _, _, v in bar}) for bar in _bars(_render(declare, tmp_path, bars=6), 6)]

	assert velocities == [[127], [127], [26], [89], [89], [89]]
	assert seen[3]["held"] == {"patch": [["960.lane_c", "midi.velocity", 1.0]]}
	assert seen[3]["taken_back"][0]["entries"] == {"patch": [["960.lane_b", "midi.velocity", True]]}


def test_a_stale_resend_cannot_undo_a_take_back_and_a_fresh_one_counts (tmp_path: pathlib.Path) -> None:

	def surface (composition: subsequence.Composition, cycle: int, seen: typing.Dict[typing.Any, typing.Any]) -> None:
		if cycle == 1:
			composition.tweak("lead", sequencer={"revision": seen[1]["revision"], "modules": {"960": {"settings": {"lane_a": {"2": LANE_A[2] + UP, "4": LANE_A[4] + UP}}}}})
		if cycle == 3:
			stale = seen[3]["taken_back"][0]["revision"] - 1
			composition.tweak("lead", sequencer={"revision": stale, "modules": {"960": {"settings": {"lane_a": {"0": LANE_A[0] + UP, "2": LANE_A[2] + UP, "4": LANE_A[4] + UP}}}}})
		if cycle == 4:
			composition.tweak("lead", sequencer={"revision": seen[4]["revision"], "modules": {"960": {"settings": {"lane_a": {"0": LANE_A[0] + UP, "2": LANE_A[2] + UP, "4": LANE_A[4] + UP}}}}})

	declare, seen = _with_surface(_code_a, surface)
	by_bar = _pitches_by_bar(_render(declare, tmp_path, bars=6), 6)

	assert by_bar[2] == GLASS and by_bar[3] == CODE_WON
	assert by_bar[4] == [PITCH[0] + 12] + CODE_WON[1:8] + [PITCH[0] + 12] + CODE_WON[9:]
	assert by_bar[5] == [PITCH[0] + 12] + GLASS[1:8] + [PITCH[0] + 12] + GLASS[9:]


def test_the_same_tweak_typed_again_in_the_repl_counts_again (tmp_path: pathlib.Path) -> None:

	def surface (composition: subsequence.Composition, cycle: int, seen: typing.Dict[typing.Any, typing.Any]) -> None:
		if cycle in (1, 4):
			composition.tweak("lead", sequencer={"modules": {"960": {"settings": {"lane_a": {"2": LANE_A[2] + UP, "4": LANE_A[4] + UP}}}}})

	declare, seen = _with_surface(_code_a, surface)
	by_bar = _pitches_by_bar(_render(declare, tmp_path, bars=6), 6)

	assert by_bar[2] == GLASS and by_bar[3] == by_bar[4] == CODE_WON and by_bar[5] == GLASS


def test_a_module_removed_on_the_surface_stays_off_until_the_code_changes_it (tmp_path: pathlib.Path) -> None:

	def code (seq: sequencers.Sequencer, p: typing.Any) -> None:
		_plain(seq, p)
		seq.add(sequencers.knob, "transpose", value=7 / 60 if p.cycle < 3 else 12 / 60)
		seq.patch("transpose.out", "midi.pitch")

	def surface (composition: subsequence.Composition, cycle: int, seen: typing.Dict[typing.Any, typing.Any]) -> None:
		if cycle == 1:
			composition.tweak("lead", sequencer={"removed": ["transpose"]})

	declare, seen = _with_surface(code, surface)
	by_bar = _pitches_by_bar(_render(declare, tmp_path, bars=6), 6)

	assert by_bar[:2] == [[n + 7 for n in PITCH * 2]] * 2
	assert by_bar[2] == PITCH * 2
	assert by_bar[3:] == [[n + 12 for n in PITCH * 2]] * 3
	assert "transpose" not in seen[2]["played"]["modules"] and "transpose" in seen[3]["played"]["modules"]


def test_a_module_and_a_cable_added_on_the_surface_play (tmp_path: pathlib.Path) -> None:

	def surface (composition: subsequence.Composition, cycle: int, seen: typing.Dict[typing.Any, typing.Any]) -> None:
		if cycle == 1:
			composition.tweak("lead", sequencer={"modules": {"lift": {"model": "knob", "settings": {"value": UP}}}, "patch": [["lift.out", "midi.pitch", 1.0]]})

	declare, seen = _with_surface(_plain, surface)
	by_bar = _pitches_by_bar(_render(declare, tmp_path, bars=4), 4)

	assert by_bar[2] == by_bar[3] == [n + 12 for n in PITCH * 2]
	assert seen[3]["played"]["modules"]["lift"]["model"] == "knob"


def test_an_entry_naming_a_jack_that_is_not_there_is_left_out_with_one_warning (tmp_path: pathlib.Path) -> None:

	def surface (composition: subsequence.Composition, cycle: int, seen: typing.Dict[typing.Any, typing.Any]) -> None:
		if cycle == 1:
			composition.tweak("lead", sequencer={"patch": [["960.lane_z", "midi.pitch", 1.0]], "modules": {"960": {"settings": {"lane_a": {"2": LANE_A[2] + UP}}}}})

	declare, seen = _with_surface(_plain, surface)
	by_bar = _pitches_by_bar(_render(declare, tmp_path, bars=4, warnings=1), 4)

	assert by_bar[2] == by_bar[3] == THIRD_UP * 2
	assert "patch" not in seen["tweaks"][2]
	assert "lane_z" in seen[2]["refused"][0]["reason"]


def _bias_model (outputs: typing.Dict[str, str]) -> sequencers.Model:

	@sequencers.model(outputs=outputs, label="bias")
	def bias (s: sequencers.StepContext, value: sequencers.Knob = 0.0) -> None:
		"""A voltage on each of its outputs."""
		for jack in outputs:
			s.send(jack, value)

	return bias


BIAS_TWO, BIAS_ONE = _bias_model({"out": sequencers.CV, "alt": sequencers.CV}), _bias_model({"out": sequencers.CV})


def test_a_save_that_removes_a_surface_cable_s_output_refuses_that_cable_and_plays_on (tmp_path: pathlib.Path) -> None:

	def code (seq: sequencers.Sequencer, p: typing.Any) -> None:
		_plain(seq, p)
		seq.add(BIAS_TWO if p.cycle < 3 else BIAS_ONE, "b", value=UP)

	def surface (composition: subsequence.Composition, cycle: int, seen: typing.Dict[typing.Any, typing.Any]) -> None:
		if cycle == 1:
			composition.tweak("lead", sequencer={"revision": seen[1]["revision"], "patch": [["b.alt", "midi.pitch", 1.0]], "modules": {"960": {"settings": {"lane_a": {"2": LANE_A[2] + UP}}}}})

	declare, seen = _with_surface(code, surface)
	by_bar = _pitches_by_bar(_render(declare, tmp_path, bars=6, warnings=1), 6)
	refused = seen[3]["refused"]

	assert by_bar[2] == [n + 12 for n in THIRD_UP * 2] and by_bar[3:] == [THIRD_UP * 2] * 3
	assert len(refused) == 1 and refused[0]["entries"] == {"patch": [["b.alt", "midi.pitch", True]]}
	assert "alt" in refused[0]["reason"] and refused[0]["revision"] == seen[3]["revision"]
	assert seen[3]["held"] == {"modules": {"960": {"settings": {"lane_a": {"2": LANE_A[2] + UP}}}}}
	assert "lane_a" in str(seen["tweaks"][3]) and "b.alt" not in str(seen["tweaks"][3])


def test_a_value_no_control_can_take_is_refused_with_its_reason (tmp_path: pathlib.Path) -> None:

	def surface (composition: subsequence.Composition, cycle: int, seen: typing.Dict[typing.Any, typing.Any]) -> None:
		if cycle == 1:
			composition.tweak("lead", sequencer={"modules": {"960": {"settings": {"mode": {"3": "sideways"}, "lane_a": {"2": LANE_A[2] + UP}}}}})

	declare, seen = _with_surface(_plain, surface)
	by_bar = _pitches_by_bar(_render(declare, tmp_path, bars=4, warnings=1), 4)

	assert by_bar[2] == by_bar[3] == THIRD_UP * 2
	assert seen[2]["refused"][0]["entries"] == {"modules": {"960": {"settings": {"mode": {"3": True}}}}}
	assert "sideways" in seen[2]["refused"][0]["reason"]


@pytest.mark.parametrize("document", [
	"lane_a up",
	{"modules": ["960"]},
	{"modules": {"960": "loud"}},
	{"modules": {"lift": {"model": ["knob"]}}},
	{"patch": "960.lane_a to midi.pitch"},
	{"patch": [["960.lane_a", "midi.pitch"]]},
	{"patch": [[["960.lane_a"], "midi.pitch", 1.0]]},
	{"removed": "960"},
	{"removed": [["960"]]},
	{"revision": "seven", "modules": {"960": {"settings": {"lane_a": []}}}},
	{"modules": {"960": {"settings": {"longest": True}}}},
])
def test_a_document_of_the_wrong_shape_is_refused_and_the_part_plays_on (document: typing.Any, tmp_path: pathlib.Path) -> None:

	"""Each of these raised inside the build before, which silences a part every cycle."""

	def surface (composition: subsequence.Composition, cycle: int, seen: typing.Dict[typing.Any, typing.Any]) -> None:
		if cycle == 1:
			composition.tweak("lead", sequencer=document)

	declare, seen = _with_surface(_plain, surface)
	by_bar = _pitches_by_bar(_render(declare, tmp_path, bars=4, warnings=1), 4)

	assert by_bar == [PITCH * 2] * 4
	assert seen[2]["refused"] and seen[2]["refused"][0]["reason"]
	assert seen["tweaks"][2] is None


GATES = [0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 0.6, 0.0]


def _cv_trigger (amount: float) -> Declare:

	def body (seq: sequencers.Sequencer, p: typing.Any) -> None:
		seq.add(sequencers.moog_960, "960", lane_a=LANE_A, lane_b=GATES)
		seq.patch("clock.out", "960.shift")
		seq.patch("960.lane_a", "midi.pitch")
		seq.patch("960.lane_b", "midi.trigger", amount)

	return _lead(body)


def test_a_voltage_into_a_trigger_fires_as_it_rises_past_one_half (tmp_path: pathlib.Path) -> None:

	"""Stages 2, 4 and 7 fire (5 does not rise); at an amount of 0.4 none do, and at 0.5 stage 7's 0.6 reads 0.3."""

	fired = [(b, n) for b, n, _, _ in _render(_cv_trigger(1.0), tmp_path, bars=1)]

	assert fired == [(0.25, PITCH[1]), (0.75, PITCH[3]), (1.5, PITCH[6]), (2.25, PITCH[1]), (2.75, PITCH[3]), (3.5, PITCH[6])]
	assert _render(_cv_trigger(0.4), tmp_path, bars=1) == []
	assert [(b, n) for b, n, _, _ in _render(_cv_trigger(0.5), tmp_path, bars=1)] == [(0.25, PITCH[1]), (0.75, PITCH[3]), (2.25, PITCH[1]), (2.75, PITCH[3])]


def test_state_is_plain_data_whose_revision_moves_only_when_something_does (tmp_path: pathlib.Path) -> None:

	declare, seen = _with_surface(_plain, lambda composition, cycle, seen: None)
	_render(declare, tmp_path, bars=4)

	assert [seen[c]["revision"] for c in range(1, 4)] == [1, 1, 1]
	assert seen[1]["held"] == {} and seen[1]["taken_back"] == [] and seen[1]["refused"] == []
	assert set(seen[1]["models"]) == {"clock", "midi_out", "moog_960"}
	assert seen[1]["cables"] == sequencers.CABLES


def test_the_revision_moves_when_a_saved_model_describes_itself_differently (tmp_path: pathlib.Path) -> None:

	relabelled = sequencers.model(
		stages=8, inputs=sequencers.moog_960.inputs, outputs=sequencers.moog_960.outputs,
		normals=sequencers.moog_960.normals, patch=sequencers.moog_960.patch, label="960, saved",
	)(sequencers.moog_960.fn)

	def saved (seq: sequencers.Sequencer, p: typing.Any) -> None:
		seq.add(sequencers.moog_960 if p.cycle < 2 else relabelled, "960", lane_a=LANE_A)
		seq.default_patch("960")

	declare, seen = _with_surface(saved, lambda composition, cycle, seen: None)
	played = _render(declare, tmp_path, bars=4)

	assert [seen[c]["revision"] for c in range(1, 4)] == [1, 2, 2]
	assert seen[2]["models"]["moog_960"]["label"] == "960, saved"
	assert _pitches_by_bar(played, 4) == [PITCH * 2] * 4


def test_a_lane_is_a_kind_of_its_own_and_the_midi_out_is_labelled_for_what_it_carries () -> None:

	described = sequencers.moog_960.describe()
	lane_a, mode = (next(c for c in described["controls"] if c["name"] == n) for n in ("lane_a", "mode"))

	assert lane_a == {"name": "lane_a", "label": "lane a", "kind": "lane", "count": 8, "of": {"kind": "number", "min": 0.0, "max": 1.0}, "required": False, "default": [0.0] * 8}
	assert mode["kind"] == "lane" and mode["of"]["kind"] == "choice" and mode["default"] == ["normal"] * 8
	assert [o["value"] for o in mode["of"]["options"]] == ["normal", "skip", "stop"]
	assert sequencers.midi_out.describe()["label"] == "notes"
	assert all(json.loads(json.dumps(entry)) == entry for entry in sequencers.models())


def test_a_live_save_keeps_every_module_where_it_was (tmp_path: pathlib.Path) -> None:

	"""A save re-declares the pattern; the 960 carries on from the stage it was on, and the save's new lane plays from the next cycle."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=1)
	composition._is_live = True

	def lead (p: typing.Any) -> None:
		seq = sequencers.sequencer(p)
		_five(seq, p)
		seq.play()

	def saved (p: typing.Any) -> None:
		seq = sequencers.sequencer(p)
		seq.add(sequencers.moog_960, "960", lane_a=[v + UP for v in LANE_A])
		seq.default_patch("960")
		seq.patch("960.stage6", "960.stage1")
		seq.play()

	saved.__name__ = "lead"

	def save (p: typing.Any) -> None:
		if p.cycle == 1:
			composition.pattern(channel=1, steps=4, step_duration=dur.SIXTEENTH)(saved)

	composition.pattern(channel=1, steps=4, step_duration=dur.SIXTEENTH)(lead)
	composition.schedule(save, cycle_beats=4)
	path = tmp_path / "saved.mid"
	composition.render(bars=3, filename=str(path))
	played = _read(path)[0][1]

	# Every step on the stage the unbroken loop would have it on, and the saved lane from the bar after the save.
	assert [round(b * 4) for b, *_ in played] == list(range(48))
	assert all(n in (PITCH[round(b * 4) % 5], PITCH[round(b * 4) % 5] + 12) for b, n, _, _ in played)
	assert all(n == PITCH[round(b * 4) % 5] for b, n, _, _ in played if b < 3)
	assert all(n == PITCH[round(b * 4) % 5] + 12 for b, n, _, _ in played if b >= 8)


# What the package adds --------------------------------------------------------------------------------------------

def test_a_build_that_raises_leaves_the_sequencer_where_the_last_good_one_did (tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture) -> None:

	"""One-beat cycles of a five-stage loop; the second cycle raises after playing, so it is silent and the third plays what the second would have."""

	def after (p: typing.Any) -> None:
		if p.cycle == 1:
			raise RuntimeError("a mistake after the sequencer played")

	with caplog.at_level(logging.ERROR):
		played = _render(_lead(_five, steps=4, after=after), tmp_path, bars=1, warnings=1)

	beats = [b for b, *_ in played]
	assert beats == [0.0, 0.25, 0.5, 0.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75]
	assert _pitches(played) == [PITCH[i % 5] for i in range(12)]


@sequencers.model(inputs={"clock": sequencers.TRIGGER}, outputs={"pitch": sequencers.CV})
def counter (s: sequencers.StepContext) -> None:

	"""Counts its clocks in its memory, and wanders from the count at random."""

	if s.received("clock"):
		s.memory["count"] = s.memory.get("count", 0) + 1

	s.send("pitch", (s.memory.get("count", 0) % 12 + s.rng.randrange(12)) / sequencers.SEMITONES)


def test_a_build_that_raises_leaves_each_module_s_memory_and_stream_as_they_were (tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture) -> None:

	"""After a failed cycle the next plays exactly what the failed one would have: nothing it counted or drew is kept."""

	def body (seq: sequencers.Sequencer, p: typing.Any) -> None:
		seq.add(counter, "counter")
		seq.patch("clock.out", "counter.clock")
		seq.patch("clock.out", "midi.trigger")
		seq.patch("counter.pitch", "midi.pitch")

	def after (p: typing.Any) -> None:
		if p.cycle == 1:
			raise RuntimeError("a mistake after the sequencer played")

	clean = _pitches(_render(_lead(body, steps=4), tmp_path, bars=1))

	with caplog.at_level(logging.ERROR):
		failed = _render(_lead(body, steps=4, after=after), tmp_path, bars=1, warnings=1)

	assert len(set(clean)) > 6
	assert [b for b, *_ in failed][4] == 2.0
	assert _pitches(failed) == clean[:12]


def _random_lead (names: typing.Sequence[str], stay: float = 0.5) -> Declare:

	"""One pendulum per name, each lingering at random; only the first is heard."""

	def body (seq: sequencers.Sequencer, p: typing.Any) -> None:
		for name in names:
			seq.add(pendulum, name, pitch=LANE_A, stay=stay)
			seq.patch("clock.out", f"{name}.clock")
		seq.patch("clock.out", "midi.trigger")
		seq.patch(f"{names[0]}.pitch", "midi.pitch")

	return _lead(body)


def test_each_module_draws_from_a_stream_of_its_own (tmp_path: pathlib.Path) -> None:

	"""Seeded, so a render repeats; another random module beside it changes nothing it plays; renamed, it draws afresh."""

	alone = _pitches(_render(_random_lead(["a"]), tmp_path, bars=4))

	assert len(set(alone)) > 4 and len(alone) == 64
	assert _pitches(_render(_random_lead(["a"]), tmp_path, bars=4)) == alone
	assert _pitches(_render(_random_lead(["a", "b"]), tmp_path, bars=4)) == alone
	assert _pitches(_render(_random_lead(["renamed"]), tmp_path, bars=4)) != alone
	assert _pitches(_render(_random_lead(["a"]), tmp_path, bars=4, seed=2)) != alone


def test_an_unseeded_composition_s_modules_still_draw (tmp_path: pathlib.Path) -> None:

	assert len(set(_pitches(_render(_random_lead(["a"]), tmp_path, bars=4, seed=None)))) > 2


def test_a_reroll_deals_a_module_a_new_stream (tmp_path: pathlib.Path) -> None:

	def rerolled (composition: subsequence.Composition) -> None:

		def roll (p: typing.Any) -> None:
			if p.cycle == 1:
				composition.reroll("lead")

		_random_lead(["a"])(composition)
		composition.schedule(roll, cycle_beats=8)

	alone = _pitches(_render(_random_lead(["a"]), tmp_path, bars=6))
	moved = _pitches(_render(rerolled, tmp_path, bars=6))

	assert moved[:32] == alone[:32]
	assert moved[48:] != alone[48:]


def _record (composition: subsequence.Composition) -> typing.List[typing.Tuple[str, typing.Dict[str, typing.Any], typing.Any]]:

	"""Every report the build hook hands over.

	A render of N bars of a one-bar pattern builds N + 1 cycles: the last is built a beat
	before the end, as every cycle is built a beat before it plays.
	"""

	reports: typing.List[typing.Tuple[str, typing.Dict[str, typing.Any], typing.Any]] = []
	sequencers.on_build(composition, lambda name, state, playing: reports.append((name, state, playing)))

	return reports


def test_playing_says_which_stage_each_module_was_on_at_each_step (tmp_path: pathlib.Path) -> None:

	"""From 0, None before the first stage, and the cycle's start beat counted from the composition's start."""

	def body (seq: sequencers.Sequencer, p: typing.Any) -> None:
		seq.add(sequencers.moog_960, "960", lane_a=LANE_A, mode=["normal"] * 6 + ["skip", "normal"])
		seq.add(sequencers.clock, "slow", every=2, offset=1)
		seq.patch("slow.out", "960.shift")
		seq.patch("clock.out", "midi.trigger")
		seq.patch("960.lane_a", "midi.pitch")

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=1)
	_lead(body, steps=8)(composition)
	reports = _record(composition)
	composition.render(bars=2, filename=str(tmp_path / "playing.mid"))
	starts = [playing["cycle"]["start_beat"] for _, _, playing in reports]
	positions = [playing["modules"]["960"]["positions"]["stage"] for _, _, playing in reports]

	assert starts[:4] == [0.0, 2.0, 4.0, 6.0]
	assert reports[0][2]["cycle"] == {"start_beat": 0.0, "steps": 8, "step_beats": 0.25}
	assert positions[0] == [None, 0, 0, 1, 1, 2, 2, 3]
	assert positions[1] == [3, 4, 4, 5, 5, 7, 7, 0]
	assert set(reports[0][2]["modules"]) == {"960"}


def test_playing_is_kept_out_of_the_revision (tmp_path: pathlib.Path) -> None:

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=1)
	_lead(_plain, steps=4)(composition)
	reports = _record(composition)
	composition.render(bars=2, filename=str(tmp_path / "revision.mid"))

	assert len({json.dumps(playing["modules"]) for _, _, playing in reports}) > 1
	assert {state["revision"] for _, state, _ in reports} == {1}


def test_the_build_hook_reports_from_the_first_cycle_in_both_forms (tmp_path: pathlib.Path) -> None:

	"""Named by p.name (#5202), so the first build reports before the pattern has joined running_patterns."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=1)
	_lead(_plain)(composition)

	@sequencers.pattern(composition, channel=2, steps=16, step_duration=dur.SIXTEENTH)
	def bass (seq: sequencers.Sequencer) -> None:
		_plain(seq, seq.p)

	reports = _record(composition)
	composition.render(bars=3, filename=str(tmp_path / "hook.mid"))
	names = [name for name, _, _ in reports]

	assert names[:2] == ["lead", "bass"] and names.count("lead") == names.count("bass") >= 3
	assert reports[0][2]["cycle"]["start_beat"] == 0.0 and reports[0][1]["revision"] == 1
	assert [state for name, state, _ in reports if name == "lead"][-1] == sequencers.state(composition, "lead")


def test_the_build_hook_hands_over_copies_nothing_changes (tmp_path: pathlib.Path) -> None:

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=1)
	_lead(_plain)(composition)
	firsts: typing.List[typing.Any] = []

	def spoil (name: str, state: typing.Dict[str, typing.Any], playing: typing.Any) -> None:
		firsts.append(json.dumps([state, playing], sort_keys=True))
		state["models"]["moog_960"]["controls"].clear()
		state["cables"]["kinds"].clear()
		playing["modules"]["960"]["positions"]["stage"].clear()

	sequencers.on_build(composition, spoil)
	reports = _record(composition)
	composition.render(bars=2, filename=str(tmp_path / "copies.mid"))

	assert len(reports) == 3 and len(firsts) == 3
	assert reports[1][1]["models"]["moog_960"]["controls"] and reports[1][1]["cables"]["kinds"] == [sequencers.TRIGGER, sequencers.GATE, sequencers.CV]
	assert len(reports[1][2]["modules"]["960"]["positions"]["stage"]) == 16
	assert sequencers.CABLES["kinds"] == [sequencers.TRIGGER, sequencers.GATE, sequencers.CV]


def test_a_failed_build_reports_nothing (tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture) -> None:

	def after (p: typing.Any) -> None:
		if p.cycle == 1:
			raise RuntimeError("a mistake after the sequencer played")

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=1)
	_lead(_plain, after=after)(composition)
	reports = _record(composition)

	with caplog.at_level(logging.ERROR):
		composition.render(bars=3, filename=str(tmp_path / "failed.mid"))

	assert [playing["cycle"]["start_beat"] for _, _, playing in reports] == [0.0, 8.0, 12.0]


def test_a_listener_that_raises_does_not_stop_the_music_and_is_logged_once (tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture) -> None:

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=1)
	_lead(_plain)(composition)

	def broken (name: str, state: typing.Any, playing: typing.Any) -> None:
		raise ValueError("the adapter is broken")

	sequencers.on_build(composition, broken)
	reports = _record(composition)
	path = tmp_path / "broken.mid"

	with caplog.at_level(logging.ERROR):
		composition.render(bars=3, filename=str(path))

	logged = [r for r in caplog.records if "build listener" in r.getMessage()]
	assert len(logged) == 1
	assert len(reports) == 4
	assert _pitches_by_bar(_read(path)[0][1], 3) == [PITCH * 2] * 3


def test_a_listener_hears_only_its_own_composition (tmp_path: pathlib.Path) -> None:

	first = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=1)
	second = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=1)
	_lead(_plain)(first)
	_lead(_plain)(second)
	heard = _record(second)
	first.render(bars=2, filename=str(tmp_path / "first.mid"))

	assert heard == []

	second.render(bars=2, filename=str(tmp_path / "second.mid"))

	assert len(heard) == 3


def test_on_build_takes_only_a_function () -> None:

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=1)

	with pytest.raises(TypeError, match="takes a function"):
		sequencers.on_build(composition, "print")  # type: ignore[arg-type]


@sequencers.model(inputs={"clock": sequencers.TRIGGER})
def ratchet (s: sequencers.StepContext, hits: typing.Annotated[int, sequencers.Span(1, 4)] = 3, pitch: sequencers.Note = 60) -> None:

	"""Several notes in each step it is clocked, evenly inside the step."""

	if s.received("clock"):
		for k in range(hits):
			s.note(pitch, 100, s.step_beats / (2 * hits), at=k * s.step_beats / hits)


def test_a_model_places_notes_inside_its_step (tmp_path: pathlib.Path) -> None:

	def body (seq: sequencers.Sequencer, p: typing.Any) -> None:
		seq.add(ratchet, "ratchet", hits=3)
		seq.add(sequencers.clock, "quarters", every=4)
		seq.patch("quarters.out", "ratchet.clock")

	played = _render(_lead(body), tmp_path, bars=1)

	assert [round(b * 24) for b, *_ in played] == [0, 2, 4, 24, 26, 28, 48, 50, 52, 72, 74, 76]
	assert {d for *_, d in played} == {0.042}


@sequencers.model(inputs={"clock": sequencers.TRIGGER})
def offbeat (s: sequencers.StepContext, at: float = 0.0) -> None:

	"""A note on, a controller and a note off, each half a step after the clock."""

	if s.received("clock"):
		s.note_on(64, 90, at=at)
		s.cc(74, 100, at=at)
	elif s.step % 4 == 2:
		s.note_off(64, at=at)


def test_a_note_on_a_note_off_and_a_controller_take_an_offset_inside_the_step (tmp_path: pathlib.Path) -> None:

	def body (seq: sequencers.Sequencer, p: typing.Any) -> None:
		seq.add(offbeat, "offbeat", at=0.125)
		seq.add(sequencers.clock, "quarters", every=4)
		seq.patch("quarters.out", "offbeat.clock")

	played, ccs = _render_with_ccs(_lead(body), tmp_path, bars=1)

	assert [(b, n, d) for b, n, _, d in played] == [(0.125, 64, 0.5), (1.125, 64, 0.5), (2.125, 64, 0.5), (3.125, 64, 0.5)]
	assert [(b, c, v) for b, c, v in ccs] == [(0.125, 74, 100), (1.125, 74, 100), (2.125, 74, 100), (3.125, 74, 100)]


@pytest.mark.parametrize("at", [-0.01, 0.25, 0.3])
def test_an_offset_outside_the_step_is_refused (at: float, tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture) -> None:

	def body (seq: sequencers.Sequencer, p: typing.Any) -> None:
		seq.add(offbeat, "offbeat", at=at)
		seq.add(sequencers.clock, "quarters", every=4)
		seq.patch("quarters.out", "offbeat.clock")

	with caplog.at_level(logging.ERROR):
		played = _render(_lead(body), tmp_path, bars=1, warnings=2)

	assert played == []
	assert any("how far into this step" in str(r.exc_info[1]) for r in caplog.records if r.exc_info)


def test_a_gate_note_inside_a_cycle_is_placed_whole_and_one_across_its_end_is_not () -> None:

	"""Placed with p.note(), so the verbs that act on notes act on it; one still sounding at the cycle's end starts with p.note_on()."""

	pattern = subsequence.pattern.Pattern(channel=0, length=1.0)
	placed: typing.List[typing.Tuple[int, typing.List[typing.Tuple[int, int]], int]] = []

	for cycle in range(2):
		p = subsequence.pattern_builder.PatternBuilder(pattern, cycle=cycle, default_grid=4)
		seq = sequencers.sequencer(p)
		_tie(seq, p)
		seq.patch("960.stage2", "midi.gate")
		seq.play()
		pattern._finish_builds()
		placed.append((cycle, [(pulse, note.duration) for pulse, step in sorted(pattern.steps.items()) for note in step.notes], len(pattern.raw_note_events)))
		pattern.steps.clear()
		pattern.raw_note_events.clear()

	assert placed[0] == (0, [(6, 6)], 1)
	assert placed[1] == (1, [(0, 6)], 1)


def test_a_document_applied_in_code_lays_its_entries_and_warns_of_the_rest (tmp_path: pathlib.Path) -> None:

	def body (seq: sequencers.Sequencer, p: typing.Any) -> None:
		seq.apply({"modules": {"960": {"model": "moog_960", "settings": {"lane_a": LANE_A}}}, "patch": [["clock.out", "960.shift", 1], ["clock.out", "midi.trigger", 1], ["960.lane_a", "midi.pitch", 1], ["960.nowhere", "midi.pitch", 1]]})

	assert _pitches(_render(_lead(body), tmp_path, bars=1, warnings=2)) == PITCH * 2


def test_state_names_a_pattern_with_no_sequencer (tmp_path: pathlib.Path) -> None:

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=1)
	composition.pattern(channel=1, beats=4)(lambda p: p.note(60, beat=0))
	composition.render(bars=1, filename=str(tmp_path / "none.mid"))

	with pytest.raises(ValueError, match="not a running pattern with a sequencer"):
		sequencers.state(composition, "<lambda>")

	with pytest.raises(ValueError, match="not a running pattern with a sequencer"):
		sequencers.playing(composition, "lead")


def test_a_sequencer_plays_once_a_cycle () -> None:

	p = subsequence.pattern_builder.PatternBuilder(subsequence.pattern.Pattern(channel=0, length=1.0), cycle=0, default_grid=4)
	seq = sequencers.sequencer(p)
	seq.play()

	assert sequencers.sequencer(p) is seq

	with pytest.raises(RuntimeError, match="once a cycle"):
		seq.play()


@pytest.mark.parametrize("name", ["", "9.60", 960])
def test_a_module_s_name_is_a_word_with_no_dot (name: typing.Any) -> None:

	p = subsequence.pattern_builder.PatternBuilder(subsequence.pattern.Pattern(channel=0, length=1.0), cycle=0, default_grid=4)

	with pytest.raises(ValueError, match="no dot"):
		sequencers.sequencer(p).add(sequencers.knob, name)


def test_a_model_s_controls_need_defaults_and_its_jacks_a_kind () -> None:

	def no_default (s: sequencers.StepContext, value: sequencers.Knob) -> None:
		pass

	def a_wire (s: sequencers.StepContext) -> None:
		pass

	with pytest.raises(TypeError, match="needs a default"):
		sequencers.model()(no_default)

	with pytest.raises(ValueError, match="a trigger, a gate or a cv"):
		sequencers.model(inputs={"in": "wire"})(a_wire)


def test_a_cable_to_a_module_not_declared_this_cycle_is_refused_in_code () -> None:

	p = subsequence.pattern_builder.PatternBuilder(subsequence.pattern.Pattern(channel=0, length=1.0), cycle=0, default_grid=4)

	with pytest.raises(ValueError, match="add it first"):
		sequencers.sequencer(p).patch("960.lane_a", "midi.pitch")


def test_the_engine_keeps_its_sequencer_where_it_says () -> None:

	"""Under MEMORY in p.memory, and only once the build has finished."""

	pattern = subsequence.pattern.Pattern(channel=0, length=1.0)
	p = subsequence.pattern_builder.PatternBuilder(pattern, cycle=0, default_grid=4)
	seq = sequencers.sequencer(p)
	seq.play()

	assert subsequence.plugins.sequencers.engine.MEMORY not in pattern.memory

	pattern._finish_builds()

	assert pattern.memory[subsequence.plugins.sequencers.engine.MEMORY] is seq
