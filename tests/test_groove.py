import os
import pathlib
import re
import struct
import typing

import mido
import pytest

import subsequence
import subsequence.groove
import subsequence.pattern
import subsequence.pattern_builder


def _make_steps (*pulses: int, velocity: int = 100) -> dict:

	"""
	Build a steps dict with one note per pulse position.
	"""

	steps = {}
	for p in pulses:
		steps[p] = subsequence.pattern.Step(notes=[
			subsequence.pattern.Note(pitch=60, velocity=velocity, duration=6, channel=0)
		])
	return steps


# ── Groove.swing() factory ───────────────────────────────────────────

def test_swing_50_percent_is_straight () -> None:

	"""50% swing produces zero offsets (straight time)."""

	g = subsequence.groove.Groove.swing(percent=50.0)
	assert g.offsets == [0.0, 0.0]
	assert g.grid == 0.25


def test_swing_57_percent () -> None:

	"""57% swing produces the expected offset for 16th notes."""

	g = subsequence.groove.Groove.swing(percent=57.0)
	assert g.offsets[0] == 0.0
	assert abs(g.offsets[1] - 0.035) < 1e-9


def test_swing_67_percent_triplet () -> None:

	"""67% gives approximate triplet swing."""

	g = subsequence.groove.Groove.swing(percent=67.0)
	assert g.offsets[0] == 0.0
	# 67% of 0.5 = 0.335, offset = 0.335 - 0.25 = 0.085
	assert abs(g.offsets[1] - 0.085) < 1e-9


def test_swing_eighth_note_grid () -> None:

	"""Swing can be applied to 8th note grid."""

	g = subsequence.groove.Groove.swing(percent=57.0, grid=0.5)
	assert g.grid == 0.5
	# pair_duration = 1.0, offset = (0.57 - 0.5) * 1.0 = 0.07
	assert abs(g.offsets[1] - 0.07) < 1e-9


def test_swing_invalid_percent () -> None:

	"""Percent outside 50-99 range raises ValueError."""

	with pytest.raises(ValueError):
		subsequence.groove.Groove.swing(percent=40.0)

	with pytest.raises(ValueError):
		subsequence.groove.Groove.swing(percent=100.0)


# ── apply_groove() ───────────────────────────────────────────────────

def test_apply_groove_shifts_offbeat_16ths () -> None:

	"""Off-beat 16th notes are shifted by the groove offset."""

	# 16th notes at pulses 0, 6, 12, 18 (one beat of 16ths at 24 PPQN)
	steps = _make_steps(0, 6, 12, 18)
	g = subsequence.groove.Groove.swing(percent=57.0)

	result = subsequence.groove.apply_groove(steps, g, pulses_per_quarter=24)

	# On-beat 16ths (pulse 0, 12) should stay put
	assert 0 in result
	assert 12 in result

	# Off-beat 16ths: ideal=6, offset=0.035*24=0.84 → round(6+0.84)=7
	assert 7 in result
	# ideal=18, offset=0.035*24=0.84 → round(18+0.84)=19
	assert 19 in result


def test_apply_groove_straight_no_change () -> None:

	"""50% swing (straight) produces no timing changes."""

	steps = _make_steps(0, 6, 12, 18)
	g = subsequence.groove.Groove.swing(percent=50.0)

	result = subsequence.groove.apply_groove(steps, g, pulses_per_quarter=24)

	assert set(result.keys()) == {0, 6, 12, 18}


def test_apply_groove_empty_pattern () -> None:

	"""Empty pattern returns empty result."""

	g = subsequence.groove.Groove.swing(percent=57.0)
	result = subsequence.groove.apply_groove({}, g, pulses_per_quarter=24)
	assert result == {}


def test_apply_groove_notes_between_grid_untouched () -> None:

	"""Notes not close to a grid position are left alone."""

	# Place a note at pulse 3 — midway between grid positions 0 and 6
	steps = _make_steps(3)
	g = subsequence.groove.Groove(offsets=[0.0, 0.1], grid=0.25)

	result = subsequence.groove.apply_groove(steps, g, pulses_per_quarter=24)

	# Pulse 3 is exactly half a grid cell from each neighbor — should be untouched
	assert 3 in result


def test_apply_groove_velocity_scaling () -> None:

	"""Velocity scaling adjusts note velocities per grid slot."""

	steps = _make_steps(0, 6)
	g = subsequence.groove.Groove(
		offsets=[0.0, 0.0],
		grid=0.25,
		velocities=[1.0, 0.5]
	)

	result = subsequence.groove.apply_groove(steps, g, pulses_per_quarter=24)

	# Slot 0: velocity unchanged (100 * 1.0 = 100)
	assert result[0].notes[0].velocity == 100
	# Slot 1: velocity halved (100 * 0.5 = 50)
	assert result[6].notes[0].velocity == 50


def test_apply_groove_velocity_clamp () -> None:

	"""Velocity is clamped to 1-127."""

	steps = _make_steps(0, velocity=120)
	g = subsequence.groove.Groove(
		offsets=[0.0],
		grid=0.25,
		velocities=[2.0]  # would produce 240
	)

	result = subsequence.groove.apply_groove(steps, g, pulses_per_quarter=24)
	assert result[0].notes[0].velocity == 127


def test_apply_groove_cyclic_repetition () -> None:

	"""Short offset list repeats cyclically across more grid positions."""

	# 2-slot pattern applied to 4 beats of 16th notes (16 positions)
	pulses = [i * 6 for i in range(16)]  # 0, 6, 12, 18, 24, ...
	steps = _make_steps(*pulses)
	g = subsequence.groove.Groove(offsets=[0.0, 0.035], grid=0.25)

	result = subsequence.groove.apply_groove(steps, g, pulses_per_quarter=24)

	# Every even slot (0, 2, 4, ...) stays; every odd slot shifts
	for i in range(0, 16, 2):
		assert i * 6 in result, f"Even slot {i} at pulse {i * 6} should be unchanged"


def test_apply_groove_no_negative_pulses () -> None:

	"""Notes at pulse 0 with a negative offset are clamped to 0."""

	steps = _make_steps(0)
	g = subsequence.groove.Groove(offsets=[-0.1], grid=0.25)

	result = subsequence.groove.apply_groove(steps, g, pulses_per_quarter=24)
	assert 0 in result


def test_apply_groove_preserves_note_data () -> None:

	"""Notes keep their pitch, duration, and channel through the transform."""

	steps = {6: subsequence.pattern.Step(notes=[
		subsequence.pattern.Note(pitch=48, velocity=90, duration=12, channel=5)
	])}
	g = subsequence.groove.Groove.swing(percent=57.0)

	result = subsequence.groove.apply_groove(steps, g, pulses_per_quarter=24)

	# Find the moved note (should be at pulse 7)
	assert 7 in result
	note = result[7].notes[0]
	assert note.pitch == 48
	assert note.duration == 12
	assert note.channel == 5


# ── Groove.from_agr() ───────────────────────────────────────────────

def test_from_agr_parses_swing_16ths_57 () -> None:

	"""The sample .agr file produces the expected groove.

	The asset is tracked at examples/assets/ — a missing file is a real
	failure, so there is deliberately no existence guard here.
	"""

	agr_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples", "assets", "Swing 16ths 57.agr")

	g = subsequence.groove.Groove.from_agr(agr_path)

	# 16 notes in 4 beats → 16th note grid
	assert abs(g.grid - 0.25) < 1e-9

	# 16 offsets
	assert len(g.offsets) == 16

	# Even slots should be ~0, odd slots should be ~0.035
	for i in range(0, 16, 2):
		assert abs(g.offsets[i]) < 0.001, f"Even slot {i} offset should be ~0"
	for i in range(1, 16, 2):
		assert abs(g.offsets[i] - 0.035) < 0.001, f"Odd slot {i} offset should be ~0.035"

	# All velocities are 127 → no velocity variation → None
	assert g.velocities is None


def test_from_agr_matches_swing_factory () -> None:

	"""The .agr import and Groove.swing(57) produce equivalent offsets."""

	agr_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples", "assets", "Swing 16ths 57.agr")

	agr_groove = subsequence.groove.Groove.from_agr(agr_path)
	factory_groove = subsequence.groove.Groove.swing(percent=57.0)

	# The factory produces a 2-slot repeating pattern
	# The .agr produces a 16-slot pattern that repeats the same 2-slot pattern
	for i in range(16):
		slot = i % len(factory_groove.offsets)
		assert abs(agr_groove.offsets[i] - factory_groove.offsets[slot]) < 0.001


def _swing_clip (tmp_path: pathlib.Path, percent: int, grid: float) -> str:

	"""The tracked Ableton asset with its notes moved to a given swing, times stored as Ableton stores them (float32)."""

	template = pathlib.Path(os.path.dirname(os.path.dirname(__file__)), "examples", "assets", "Swing 16ths 57.agr").read_text()
	count = int(round(4 / grid))
	late = (percent / 100 - 0.5) * 2 * grid
	times = [struct.unpack("f", struct.pack("f", index * grid + (late if index % 2 else 0.0)))[0] for index in range(count)]
	events = "".join(
		f'<MidiNoteEvent Time="{time!r}" Duration="0.0625" Velocity="127" VelocityDeviation="0" OffVelocity="64" Probability="1" IsEnabled="true" NoteId="{index + 1}" />'
		for index, time in enumerate(times)
	)
	body = re.sub(r"(<Notes>\s*)(?:<MidiNoteEvent[^>]*/>\s*)+", lambda match: match.group(1) + events, template, count=1)
	assert body.count("<MidiNoteEvent") == count, "the template's notes were not replaced"

	path = tmp_path / f"swing_{percent}_{grid:g}.agr"
	path.write_text(body)

	return str(path)


@pytest.mark.parametrize("grid", [0.25, 0.5], ids=["sixteenths", "eighths"])
def test_from_agr_imports_every_swing_amount (tmp_path: pathlib.Path, grid: float) -> None:

	"""Swing of 75% or more would not import: each late note was bound to the NEXT grid line (#3404).

	Every amount from straight to 99% must import - with the grid inferred and passed in - as
	exactly the swing Groove.swing() makes.  It worked before July, and 75% is inside the range
	the docstring calls useful.
	"""

	wrong = []

	for percent in range(50, 100):

		clip = _swing_clip(tmp_path, percent, grid)
		expected = subsequence.groove.Groove.swing(percent=percent, grid=grid).offsets

		for given in (None, grid):

			try:
				offsets = subsequence.groove.Groove.from_agr(clip, grid=given).offsets
			except ValueError as error:
				wrong.append((percent, given, str(error)[-60:]))
				continue

			if any(abs(offsets[index] - expected[index % 2]) > 1e-4 for index in range(len(offsets))):
				wrong.append((percent, given, [round(offset, 4) for offset in offsets[:2]]))

	assert wrong == []


def _write_agr (path: str, timing_amount: float = 100.0, velocity_amount: float = 100.0, note_times_and_velocities = None) -> None:

	"""Write a minimal synthetic .agr file for testing."""

	if note_times_and_velocities is None:
		note_times_and_velocities = [
			(0.0, 127), (0.285, 127), (0.5, 127), (0.785, 127),
		]

	notes_xml = "\n\t\t\t\t\t\t\t\t\t".join(
		f'<MidiNoteEvent Time="{t}" Duration="0.0625" Velocity="{v}" '
		f'VelocityDeviation="0" OffVelocity="64" Probability="1" '
		f'IsEnabled="true" NoteId="{i+1}" />'
		for i, (t, v) in enumerate(note_times_and_velocities)
	)

	content = (
		"<?xml version='1.0' encoding='UTF-8'?>\n"
		"<Ableton MajorVersion=\"5\">\n"
		"\t<Groove>\n"
		"\t\t<Clip><Value><MidiClip Id=\"0\" Time=\"0\">\n"
		"\t\t\t<CurrentStart Value=\"0\" />\n"
		f"\t\t\t<CurrentEnd Value=\"{len(note_times_and_velocities) * 0.25}\" />\n"
		"\t\t\t<Notes><KeyTracks><KeyTrack Id=\"0\"><Notes>\n"
		f"\t\t\t\t\t\t\t\t\t{notes_xml}\n"
		"\t\t\t</Notes></KeyTrack></KeyTracks></Notes>\n"
		"</MidiClip></Value></Clip>\n"
		f"\t\t<TimingAmount Value=\"{timing_amount}\" />\n"
		f"\t\t<VelocityAmount Value=\"{velocity_amount}\" />\n"
		"\t</Groove>\n"
		"</Ableton>\n"
	)
	with open(path, "w") as f:
		f.write(content)


def test_from_agr_timing_amount_scales_offsets () -> None:

	"""TimingAmount=50 halves all timing offsets relative to TimingAmount=100."""

	import tempfile

	with tempfile.NamedTemporaryFile(suffix=".agr", delete=False, mode="w") as f:
		tmp_path = f.name

	try:
		_write_agr(tmp_path, timing_amount=100.0)
		g_full = subsequence.groove.Groove.from_agr(tmp_path)

		_write_agr(tmp_path, timing_amount=50.0)
		g_half = subsequence.groove.Groove.from_agr(tmp_path)

		for i in range(len(g_full.offsets)):
			assert abs(g_half.offsets[i] - g_full.offsets[i] * 0.5) < 1e-9, \
				f"Slot {i}: expected half offset, got {g_half.offsets[i]} vs full {g_full.offsets[i]}"
	finally:
		os.unlink(tmp_path)


def test_from_agr_velocity_amount_zero_gives_no_velocity () -> None:

	"""VelocityAmount=0 collapses all velocity deviation to None (no variation)."""

	import tempfile

	notes = [(0.0, 127), (0.25, 80), (0.5, 127), (0.75, 80)]

	with tempfile.NamedTemporaryFile(suffix=".agr", delete=False, mode="w") as f:
		tmp_path = f.name

	try:
		_write_agr(tmp_path, velocity_amount=0.0, note_times_and_velocities=notes)
		g = subsequence.groove.Groove.from_agr(tmp_path)

		# velocity_amount=0 → all scales collapse to 1.0 → stored as None
		assert g.velocities is None
	finally:
		os.unlink(tmp_path)


def test_from_agr_velocity_amount_50_blends () -> None:

	"""VelocityAmount=50 produces velocity scales halfway between 1.0 and the raw scale."""

	import tempfile

	# max=127, other=63 → raw_scale ≈ 0.496
	notes = [(0.0, 127), (0.25, 63)]

	with tempfile.NamedTemporaryFile(suffix=".agr", delete=False, mode="w") as f:
		tmp_path = f.name

	try:
		_write_agr(tmp_path, velocity_amount=100.0, note_times_and_velocities=notes)
		g_full = subsequence.groove.Groove.from_agr(tmp_path)

		_write_agr(tmp_path, velocity_amount=50.0, note_times_and_velocities=notes)
		g_half = subsequence.groove.Groove.from_agr(tmp_path)

		assert g_full.velocities is not None
		assert g_half.velocities is not None

		for i in range(len(g_full.velocities)):
			expected = 1.0 + (g_full.velocities[i] - 1.0) * 0.5
			assert abs(g_half.velocities[i] - expected) < 1e-9, \
				f"Slot {i}: expected {expected}, got {g_half.velocities[i]}"
	finally:
		os.unlink(tmp_path)


def test_from_agr_out_of_order_events_keep_velocity_pairing () -> None:

	"""MidiNoteEvent elements listed out of time order still pair each note time with ITS OWN velocity."""

	import tempfile

	# Deliberately out of time order, each time with a distinct velocity.
	notes = [(0.5, 80), (0.0, 127), (0.785, 90), (0.285, 110)]

	with tempfile.NamedTemporaryFile(suffix=".agr", delete=False, mode="w") as f:
		tmp_path = f.name

	try:
		_write_agr(tmp_path, note_times_and_velocities=notes)
		g = subsequence.groove.Groove.from_agr(tmp_path)

		# Offsets follow time-sorted order: 0.0, 0.285, 0.5, 0.785 on a 0.25 grid.
		expected_offsets = [0.0, 0.035, 0.0, 0.035]
		for i in range(4):
			assert abs(g.offsets[i] - expected_offsets[i]) < 1e-9, \
				f"Slot {i}: expected offset {expected_offsets[i]}, got {g.offsets[i]}"

		# Velocities must travel with their times: 127, 110, 80, 90 (each / max 127).
		assert g.velocities is not None
		expected_velocities = [127 / 127, 110 / 127, 80 / 127, 90 / 127]
		for i in range(4):
			assert abs(g.velocities[i] - expected_velocities[i]) < 1e-9, \
				f"Slot {i}: expected velocity scale {expected_velocities[i]}, got {g.velocities[i]}"
	finally:
		os.unlink(tmp_path)


# ── Validation ───────────────────────────────────────────────────────


def test_groove_empty_offsets_raises () -> None:

	"""Empty offsets list raises ValueError."""

	with pytest.raises(ValueError):
		subsequence.groove.Groove(offsets=[])


def test_groove_zero_grid_raises () -> None:

	"""Zero grid raises ValueError."""

	with pytest.raises(ValueError):
		subsequence.groove.Groove(offsets=[0.0], grid=0.0)


def test_groove_empty_velocities_raises () -> None:

	"""Empty velocities list raises ValueError (use None instead)."""

	with pytest.raises(ValueError):
		subsequence.groove.Groove(offsets=[0.0], velocities=[])


# ── strength parameter ────────────────────────────────────────────────

def test_apply_groove_strength_zero_no_change () -> None:

	"""strength=0.0 leaves timing and velocity completely unchanged."""

	steps = _make_steps(0, 6, 12, 18)
	g = subsequence.groove.Groove.swing(percent=57.0)

	result = subsequence.groove.apply_groove(steps, g, pulses_per_quarter=24, strength=0.0)

	# All original positions preserved
	assert set(result.keys()) == {0, 6, 12, 18}


def test_apply_groove_strength_zero_leaves_off_grid_note_untouched () -> None:

	"""strength=0.0 leaves a note that sits off the groove grid (pulse 1) exactly where it is."""

	steps = _make_steps(1)  # pulse 1 — just off the 16th-note grid
	g = subsequence.groove.Groove(offsets=[0.05] * 16, grid=0.25)

	result = subsequence.groove.apply_groove(steps, g, pulses_per_quarter=24, strength=0.0)

	assert set(result.keys()) == {1}
	assert result[1].notes[0].velocity == 100


def test_apply_groove_strength_half_timing () -> None:

	"""strength=0.5 produces half the timing offset of strength=1.0."""

	steps = _make_steps(6)  # off-beat 16th
	g = subsequence.groove.Groove.swing(percent=57.0)

	result_full = subsequence.groove.apply_groove(steps, g, pulses_per_quarter=24, strength=1.0)
	result_half = subsequence.groove.apply_groove(steps, g, pulses_per_quarter=24, strength=0.5)

	# Full: pulse 6 moves to 7 (offset ≈ +0.84 pulses → rounds to 1)
	# Half: pulse 6 moves by half that offset → offset ≈ +0.42 → rounds to 0 → stays at 6
	# The key thing is that half is closer to 6 than full
	full_pulse = list(result_full.keys())[0]
	half_pulse = list(result_half.keys())[0]

	# Half-strength offset is less than or equal to full-strength offset
	assert abs(half_pulse - 6) <= abs(full_pulse - 6)


def test_apply_groove_strength_velocity_blend () -> None:

	"""strength blends velocity deviation: 0.0 = no change, 1.0 = full scale."""

	steps = _make_steps(0, velocity=100)
	g = subsequence.groove.Groove(
		offsets=[0.0],
		grid=0.25,
		velocities=[0.5],  # full strength would halve velocity to 50
	)

	result_full = subsequence.groove.apply_groove(steps, g, pulses_per_quarter=24, strength=1.0)
	result_half = subsequence.groove.apply_groove(steps, g, pulses_per_quarter=24, strength=0.5)
	result_zero = subsequence.groove.apply_groove(steps, g, pulses_per_quarter=24, strength=0.0)

	vel_full = result_full[0].notes[0].velocity  # 100 * 0.5 = 50
	vel_half = result_half[0].notes[0].velocity  # 100 * 0.75 = 75  (blended halfway)
	vel_zero = result_zero[0].notes[0].velocity  # 100 (unchanged)

	assert vel_full == 50
	assert vel_half == 75
	assert vel_zero == 100


def test_apply_groove_strength_out_of_range_raises () -> None:

	"""strength outside 0.0-1.0 raises ValueError."""

	g = subsequence.groove.Groove.swing(percent=57.0)

	with pytest.raises(ValueError):
		subsequence.groove.apply_groove({}, g, strength=-0.1)

	with pytest.raises(ValueError):
		subsequence.groove.apply_groove({}, g, strength=1.1)


# ── Swing moves in whole pulses, and the docs say which percentages share one (#2787) ──

def _percent_groups (grid: float) -> typing.List[str]:

	"""Whole percentages from 50 to 79 grouped by the pulse the swung note lands on, as "first–last"."""

	landed: typing.Dict[int, typing.List[int]] = {}
	offbeat = int(grid * 24)

	for percent in range(50, 80):
		step = subsequence.pattern.Step()
		step.notes.append(subsequence.pattern.Note(pitch=42, velocity=80, duration=1, channel=9))
		moved = subsequence.groove.apply_groove({offbeat: step}, subsequence.groove.Groove.swing(percent, grid))
		(pulse,) = moved.keys()
		landed.setdefault(pulse, []).append(percent)

	return [f"{group[0]}–{group[-1]}" for _, group in sorted(landed.items())]


def test_swing_lands_in_whole_pulse_steps_as_its_docs_list_them () -> None:

	"""If the steps ever change, the docstring's ranges are wrong, and this names them."""

	doc = " ".join(subsequence.pattern_builder.PatternBuilder.swing.__doc__.split())
	sixteenths = _percent_groups(0.25)
	eighths = _percent_groups(0.5)

	assert sixteenths == ["50–54", "55–62", "63–70", "71–79"]
	assert eighths[:6] == ["50–52", "53–56", "57–60", "61–64", "65–68", "69–72"]

	for described in sixteenths + eighths[1:6]:
		assert described in doc, described


# ── A groove is counted on the song's timeline, so parts of any length swing together (#2788) ──

def _swung_note_at (local_pulse: int, origin_pulse: int, percent: float = 57.0) -> int:

	"""Where one note sitting at *local_pulse* lands when its cycle starts at *origin_pulse*."""

	step = subsequence.pattern.Step()
	step.notes.append(subsequence.pattern.Note(pitch=42, velocity=80, duration=1, channel=9))
	moved = subsequence.groove.apply_groove(
		{local_pulse: step}, subsequence.groove.Groove.swing(percent), origin_pulse=origin_pulse
	)
	(pulse,) = moved.keys()

	return pulse


def _note_on_pulses (composition: subsequence.Composition, bars: int, tmp_path: pathlib.Path) -> typing.List[float]:

	"""Render and return every note-on's position in pulses (20 ticks each, at 480 PPQN)."""

	path = str(tmp_path / "groove.mid")
	composition.render(bars=bars, filename=path)

	now = 0
	pulses = []

	for message in mido.MidiFile(path).tracks[0]:
		now += message.time
		if message.type == "note_on" and message.velocity > 0:
			pulses.append(now / 20)

	assert pulses, "the render placed no notes"

	return pulses


def test_a_note_swings_by_where_its_cycle_starts_in_the_piece () -> None:

	"""The same note in the same place in its pattern: straight from a downbeat, delayed from a second sixteenth."""

	assert _swung_note_at(0, origin_pulse=0) == 0
	assert _swung_note_at(0, origin_pulse=6) == 1
	assert _swung_note_at(0, origin_pulse=12) == 0
	assert _swung_note_at(0, origin_pulse=18) == 1


def test_a_groove_counts_from_the_song_by_default_so_old_calls_are_unchanged () -> None:

	"""apply_groove() without an origin is exactly what it always was: the pattern starts the count."""

	assert _swung_note_at(6, origin_pulse=0) == 7
	assert _swung_note_at(0, origin_pulse=0) == 0


def test_a_pattern_that_is_not_a_whole_number_of_groove_cycles_swings_with_the_bar (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Three sixteenths long: its hits that fall on a second sixteenth are delayed like every other part's (#2788)."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	@composition.pattern(channel=10, beats=0.75, reschedule_lookahead=0.75)
	def hats (p: typing.Any) -> None:
		p.note(42, beat=0, duration=0.25)
		p.swing(57)

	assert _note_on_pulses(composition, 3, tmp_path)[:8] == [0, 19, 36, 55, 72, 91, 108, 127]


def test_a_whole_bar_pattern_swings_exactly_as_it_did_before (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Sixteen hats a bar over two bars: every off-step still one pulse late, and bar 2 repeats bar 1."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	@composition.pattern(channel=10, beats=4)
	def hats (p: typing.Any) -> None:
		for step in range(16):
			p.note(42, beat=step * 0.25, duration=0.25)
		p.swing(57)

	expected = [bar * 96 + pair * 12 + offset for bar in (0, 1) for pair in range(8) for offset in (0, 7)]

	assert _note_on_pulses(composition, 2, tmp_path) == expected


def test_a_triggered_part_swings_by_where_it_lands_in_the_piece (patch_midi: None, monkeypatch: pytest.MonkeyPatch) -> None:

	"""A swung one-shot landing on a second sixteenth is delayed like every other part; landing on a downbeat, it is not."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)
	scheduled: typing.List[typing.Tuple[int, typing.List[int]]] = []

	monkeypatch.setattr(composition, "_schedule_one_shot", lambda pattern, start_pulse: scheduled.append((start_pulse, sorted(pattern.steps))))

	def hit (p: typing.Any) -> None:
		p.note(42, beat=0, duration=0.1)
		p.swing(57)

	for now in (1, 7):
		composition._sequencer.pulse_count = now
		composition.trigger(hit, channel=10, quantize=0.25)

	assert scheduled == [(6, [1]), (12, [0])]
