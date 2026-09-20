import os
import pathlib
import typing

import mido
import pytest

import subsequence
import subsequence.sequencer


# ---------------------------------------------------------------------------
# _record_event
# ---------------------------------------------------------------------------

def test_record_event_appends_message (patch_midi: None) -> None:

	"""_record_event stores (pulse, message) when recording is enabled."""

	seq = subsequence.sequencer.Sequencer(record=True)
	initial_count = len(seq.recorded_events)
	msg = mido.Message('note_on', channel=0, note=60, velocity=100)
	seq._record_event(48, msg)

	assert len(seq.recorded_events) == initial_count + 1
	assert seq.recorded_events[-1] == (48.0, msg, subsequence.sequencer.CONDUCTOR)


def test_record_event_skipped_when_not_recording (patch_midi: None) -> None:

	"""_record_event does nothing when recording is disabled."""

	seq = subsequence.sequencer.Sequencer(record=False)
	msg = mido.Message('note_on', channel=0, note=60, velocity=100)
	seq._record_event(48, msg)

	assert len(seq.recorded_events) == 0


# ---------------------------------------------------------------------------
# set_bpm tempo recording
# ---------------------------------------------------------------------------

def test_set_bpm_records_tempo_event (patch_midi: None) -> None:

	"""set_bpm appends a set_tempo MetaMessage when recording."""

	seq = subsequence.sequencer.Sequencer(record=True)
	seq.recorded_events.clear()  # discard the initial set_bpm event from __init__

	seq.set_bpm(140)

	assert len(seq.recorded_events) == 1
	_, msg, _ = seq.recorded_events[0]
	assert isinstance(msg, mido.MetaMessage)
	assert msg.type == 'set_tempo'
	assert msg.tempo == mido.bpm2tempo(140)


def test_set_bpm_does_not_record_when_not_recording (patch_midi: None) -> None:

	"""set_bpm does not append anything when recording is disabled."""

	seq = subsequence.sequencer.Sequencer(record=False)
	seq.set_bpm(140)

	assert len(seq.recorded_events) == 0


def test_initial_bpm_is_recorded_on_construction (patch_midi: None) -> None:

	"""The initial BPM is stored as the first recorded event."""

	seq = subsequence.sequencer.Sequencer(record=True, initial_bpm=110)

	assert len(seq.recorded_events) >= 1
	_, msg, _ = seq.recorded_events[0]
	assert isinstance(msg, mido.MetaMessage)
	assert msg.type == 'set_tempo'
	assert msg.tempo == mido.bpm2tempo(110)


# ---------------------------------------------------------------------------
# save_recording
# ---------------------------------------------------------------------------

def test_save_recording_creates_valid_midi_file (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""save_recording writes a Type 1 MIDI file with the recorded events."""

	filename = str(tmp_path / "test.mid")
	seq = subsequence.sequencer.Sequencer(record=True, record_filename=filename)

	# Add a note_on and note_off on top of the initial tempo event
	seq._record_event(0,  mido.Message('note_on',  channel=1, note=64, velocity=90))
	seq._record_event(96, mido.Message('note_off', channel=1, note=64, velocity=0))
	seq.save_recording()

	assert os.path.exists(filename)

	mid = mido.MidiFile(filename)
	assert mid.type == 1
	assert mid.ticks_per_beat == 480

	note_events   = [m for m in mid.tracks[0] if not isinstance(m, mido.MetaMessage)]
	tempo_events  = [m for m in mid.tracks[0] if isinstance(m, mido.MetaMessage) and m.type == 'set_tempo']

	assert len(note_events)  == 2  # note_on + note_off
	assert len(tempo_events) == 1  # initial set_bpm


def test_save_recording_delta_ticks_are_correct (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""Events at known pulses produce the expected delta tick values (1 pulse = 20 ticks)."""

	filename = str(tmp_path / "ticks.mid")
	seq = subsequence.sequencer.Sequencer(record=True, record_filename=filename)
	seq.recorded_events.clear()  # start from blank

	# Pulse 0 and pulse 24 (= one beat at 24 PPQN = 480 ticks at 20× scale)
	seq._record_event(0,  mido.Message('note_on',  channel=0, note=60, velocity=100))
	seq._record_event(24, mido.Message('note_off', channel=0, note=60, velocity=0))
	seq.save_recording()

	mid = mido.MidiFile(filename)
	events = list(mid.tracks[0])

	assert events[0].time == 0     # first event: delta 0
	assert events[1].time == 480   # 24 pulses × 20 = 480 ticks


def test_save_recording_skips_when_no_events (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""save_recording does nothing when recorded_events is empty."""

	filename = str(tmp_path / "empty.mid")
	seq = subsequence.sequencer.Sequencer(record=True, record_filename=filename)
	seq.recorded_events.clear()
	seq.save_recording()

	assert not os.path.exists(filename)


def test_save_recording_skips_when_not_recording (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""save_recording does nothing when self.recording is False, even with events present."""

	filename = str(tmp_path / "disabled.mid")
	seq = subsequence.sequencer.Sequencer(record=False, record_filename=filename)

	# Bypass the _record_event guard to inject a synthetic event
	seq.recorded_events.append((0.0, mido.Message('note_on', channel=0, note=60, velocity=100), 0))
	seq.save_recording()

	assert not os.path.exists(filename)


def test_save_recording_generates_timestamp_filename (tmp_path: pathlib.Path, patch_midi: None, monkeypatch: pytest.MonkeyPatch) -> None:

	"""save_recording uses a timestamped filename when record_filename is not set."""

	monkeypatch.chdir(tmp_path)  # write into tmp_path so the file is cleaned up
	seq = subsequence.sequencer.Sequencer(record=True)  # no record_filename
	seq.save_recording()

	mid_files = list(tmp_path.glob("session_*.mid"))
	assert len(mid_files) == 1


# ---------------------------------------------------------------------------
# Composition integration
# ---------------------------------------------------------------------------

def test_composition_record_passed_to_sequencer (patch_midi: None) -> None:

	"""Composition(record=True, record_filename=...) passes both params to Sequencer."""

	composition = subsequence.Composition(record=True, record_filename="session.mid")
	assert composition._sequencer.recording is True
	assert composition._sequencer.record_filename == "session.mid"


def test_composition_record_defaults_to_off (patch_midi: None) -> None:

	"""Composition() with no record arg creates a non-recording sequencer."""

	composition = subsequence.Composition()
	assert composition._sequencer.recording is False


# ---------------------------------------------------------------------------
# The opening a DAW reads: metre and tempo at tick 0 (#2719)
# ---------------------------------------------------------------------------

def _timeline (path: str) -> typing.List[typing.Tuple[int, mido.Message]]:

	"""Every message in a saved file's track with its absolute tick."""

	now = 0
	timeline = []

	for message in mido.MidiFile(path).tracks[0]:
		now += message.time
		timeline.append((now, message))

	return timeline


def _render (tmp_path: pathlib.Path, bars: int, **composition_arguments: typing.Any) -> typing.List[typing.Tuple[int, mido.Message]]:

	"""Render a one-note-a-bar composition and return its file's timeline."""

	composition = subsequence.Composition(output_device="Dummy MIDI", **composition_arguments)

	@composition.pattern(channel=1, bars=1)
	def downbeats (p: typing.Any) -> None:
		p.note(60, beat=0)

	path = str(tmp_path / "opening.mid")
	composition.render(bars=bars, filename=path)

	return _timeline(path)


def _opening (timeline: typing.List[typing.Tuple[int, mido.Message]]) -> typing.List[typing.Tuple[str, typing.Any]]:

	"""The meta messages at tick 0, in file order, as (type, what it says)."""

	said = []

	for tick, message in timeline:

		if tick != 0 or not message.is_meta:
			continue

		if message.type == "time_signature":
			said.append(("time_signature", (message.numerator, message.denominator)))
		elif message.type == "set_tempo":
			said.append(("set_tempo", round(mido.tempo2bpm(message.tempo), 6)))

	return said


def test_a_render_opens_with_its_metre_and_tempo (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""A DAW importing the file meets 3/4 at 96 bpm before the first note, and the notes do not move."""

	timeline = _render(tmp_path, 2, bpm=96, time_signature=(3, 4))
	onsets = [tick for tick, message in timeline if message.type == "note_on" and message.velocity > 0]
	first_note_index = next(i for i, (_, message) in enumerate(timeline) if message.type == "note_on")
	opening_indices = [i for i, (tick, message) in enumerate(timeline) if tick == 0 and message.is_meta]

	assert _opening(timeline) == [("time_signature", (3, 4)), ("set_tempo", 96.0)]
	assert opening_indices and max(opening_indices) < first_note_index
	assert onsets == [0, 1440]


def test_record_true_opens_with_one_tempo_not_two (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""With recording on from construction, the constructor's tempo and the opening's are not both written."""

	timeline = _render(tmp_path, 1, bpm=96, time_signature=(5, 4), record=True)

	assert _opening(timeline) == [("time_signature", (5, 4)), ("set_tempo", 96.0)]


def test_the_opening_states_the_tempo_playback_starts_at (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""A tempo set after construction and before playback is the one the file opens with, once."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=96, record=True)

	@composition.pattern(channel=1, bars=1)
	def downbeats (p: typing.Any) -> None:
		p.note(60, beat=0)

	composition.set_bpm(120)
	path = str(tmp_path / "retempo.mid")
	composition.render(bars=1, filename=path)

	assert _opening(_timeline(path)) == [("time_signature", (4, 4)), ("set_tempo", 120.0)]


def test_a_tempo_change_during_the_render_is_written_where_it_happens (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""The opening does not swallow later changes: a set_bpm on the second cycle lands after tick 0."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=96)

	@composition.pattern(channel=1, bars=1)
	def speeds_up (p: typing.Any) -> None:
		p.note(60, beat=0)
		if p.cycle == 1:
			composition.set_bpm(120)

	path = str(tmp_path / "change.mid")
	composition.render(bars=3, filename=path)
	timeline = _timeline(path)
	later = [(tick, round(mido.tempo2bpm(message.tempo), 6)) for tick, message in timeline if message.type == "set_tempo" and tick > 0]

	assert _opening(timeline) == [("time_signature", (4, 4)), ("set_tempo", 96.0)]
	assert [bpm for _, bpm in later] == [120.0]


@pytest.mark.parametrize("time_signature, bar_ticks", [
	pytest.param((7, 8), 1680, id="7/8"),
	pytest.param((6, 8), 1440, id="6/8"),
	pytest.param((2, 2), 1920, id="2/2"),
])
def test_a_metre_is_written_as_declared_with_bar_lines_where_the_notes_are (tmp_path: pathlib.Path, patch_midi: None, time_signature: typing.Tuple[int, int], bar_ticks: int) -> None:

	"""A declared (7, 8) is written 7/8 and its bars are seven eighth notes, so a DAW's bar lines land on the downbeats (#2738).

	Until the unit set the bar, a (7, 8) played bars of seven quarter notes and
	was written 7/4 to match (#2719).
	"""

	timeline = _render(tmp_path, 2, bpm=120, time_signature=time_signature)
	onsets = [tick for tick, message in timeline if message.type == "note_on" and message.velocity > 0]

	assert _opening(timeline) == [("time_signature", time_signature), ("set_tempo", 120.0)]
	assert onsets == [0, bar_ticks]


# ---------------------------------------------------------------------------
# The end of a recording (#2790)
# ---------------------------------------------------------------------------

def _file (tmp_path: pathlib.Path, bars: int, build: typing.Callable[[typing.Any], None]) -> typing.Tuple[typing.List[typing.Tuple[int, mido.Message]], int]:

	"""Render a one-bar pattern built by *build* for *bars* bars; return the timeline and the file's length in ticks."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	@composition.pattern(channel=1, beats=4)
	def part (p: typing.Any) -> None:
		build(p)

	path = str(tmp_path / "ending.mid")
	composition.render(bars=bars, filename=path)
	timeline = _timeline(path)

	return timeline, timeline[-1][0]


def _sounding_at_the_end (timeline: typing.List[typing.Tuple[int, mido.Message]]) -> typing.List[int]:

	"""Notes started and never released, in pitch order."""

	sounding: typing.Dict[int, int] = {}

	for _, message in timeline:
		if message.type == "note_on" and message.velocity > 0:
			sounding[message.note] = sounding.get(message.note, 0) + 1
		elif message.type == "note_off" or (message.type == "note_on" and message.velocity == 0):
			sounding[message.note] = sounding.get(message.note, 0) - 1

	return sorted(note for note, count in sounding.items() if count > 0)


def test_a_chord_held_to_the_end_of_a_render_is_released_on_its_last_tick (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""Every bar's chord ends on the next bar line, the last one included, and each note is released once."""

	timeline, length = _file(tmp_path, 2, lambda p: [p.note(pitch, beat=0, duration=4) for pitch in (60, 64, 67)])
	releases = [(tick, message.note) for tick, message in timeline if message.type == "note_off"]

	assert _sounding_at_the_end(timeline) == []
	assert sorted(releases) == [(1920, 60), (1920, 64), (1920, 67), (3840, 60), (3840, 64), (3840, 67)]
	assert length == 3840


def test_a_note_running_past_the_end_of_a_render_is_released_where_the_render_ends (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""Six beats in a one-bar render: cut at the bar line, as a DAW's bounce would."""

	timeline, length = _file(tmp_path, 1, lambda p: p.note(60, beat=0, duration=6))

	assert [(tick, message.type) for tick, message in timeline if getattr(message, "note", None) == 60] == [(0, "note_on"), (1920, "note_off")]
	assert length == 1920


def test_a_render_lasts_its_bars_when_its_last_bar_ends_in_silence (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""A beat-long note in each of two bars: the file is still two bars long, not seven beats."""

	timeline, length = _file(tmp_path, 2, lambda p: p.note(60, beat=2, duration=1))

	assert _sounding_at_the_end(timeline) == []
	assert length == 3840


@pytest.mark.asyncio
async def test_a_release_sent_outside_the_queue_reaches_the_recording (patch_midi: None) -> None:

	"""stop(), pause() and unregister() release notes straight to the port; each release is recorded at the pulse it happened on."""

	seq = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", record=True)
	seq.recorded_events.clear()

	class Drone:
		device = 0
		channel = 2
		mirrors: typing.List[typing.Any] = []

	seq.active_notes = {(0, 2, 36), (0, 5, 72)}
	seq.pulse_count = 48
	await seq._stop_pattern_notes(Drone())

	seq.pulse_count = 96
	await seq._stop_all_active_notes(compensated=True)

	recorded = [(pulse, message.type, message.channel, message.note) for pulse, message, _ in seq.recorded_events]

	assert recorded == [(48.0, "note_off", 2, 36), (96.0, "note_off", 5, 72)]
	assert seq.active_notes == set()


@pytest.mark.asyncio
async def test_a_release_is_not_recorded_when_nothing_is_recording (patch_midi: None) -> None:

	"""Live playback without record=True keeps no events, released notes included."""

	seq = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI")
	seq.active_notes = {(0, 2, 36)}
	seq.pulse_count = 48

	await seq._stop_all_active_notes(compensated=True)

	assert seq.recorded_events == []
	assert seq.active_notes == set()


# ---------------------------------------------------------------------------
# A note no MIDI message can carry (#2958)
# ---------------------------------------------------------------------------

async def _sounded_at_pulse_zero (seq: subsequence.sequencer.Sequencer, notes: typing.List[typing.Tuple[int, int]]) -> None:

	"""Dispatch a note-on for each (note, channel) at pulse 0, as a pattern's first step would."""

	for note, channel in notes:
		seq._push_event(subsequence.sequencer.MidiEvent(pulse=0, message_type="note_on", channel=channel, note=note, velocity=100))

	await seq._process_pulse(0)


@pytest.mark.asyncio
@pytest.mark.parametrize("compensated", [False, True])
async def test_a_note_no_message_can_carry_does_not_stop_the_others_being_released (patch_midi: None, compensated: bool) -> None:

	"""Note 140 fails to send and never sounds; stop() and pause() still release the valid note beside it, and record that release."""

	seq = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", record=True)
	seq.recorded_events.clear()

	await _sounded_at_pulse_zero(seq, [(140, 0), (64, 0)])
	assert seq.active_notes == {(0, 0, 64)}

	seq.pulse_count = 96
	await seq._stop_all_active_notes(compensated=compensated)

	recorded = [(pulse, message.type, message.note) for pulse, message, _ in seq.recorded_events if message.type in ("note_on", "note_off")]

	assert recorded == [(0.0, "note_on", 64), (96.0, "note_off", 64)]
	assert seq.active_notes == set()


@pytest.mark.asyncio
async def test_unregistering_a_part_with_a_note_no_message_can_carry_releases_its_valid_notes (patch_midi: None) -> None:

	"""The unregister pass skips the note that never sounded and releases the one that did."""

	seq = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", record=True)
	seq.recorded_events.clear()

	class Part:
		device = 0
		channel = 2
		mirrors: typing.List[typing.Any] = []

	await _sounded_at_pulse_zero(seq, [(200, 2), (36, 2)])
	seq.pulse_count = 48
	await seq._stop_pattern_notes(Part())

	released = [(pulse, message.note) for pulse, message, _ in seq.recorded_events if message.type == "note_off"]

	assert released == [(48.0, 36)]
	assert seq.active_notes == set()


def _hold_a_note_past_the_ceiling (p: typing.Any, pitches: typing.Sequence[int]) -> None:

	"""Put notes MIDI cannot carry straight onto the pattern, below every check.

	`chord("C", root=110, count=8)` used to produce 132 and 136 and this is
	what it produced them for.  It folds them into range now, and a builder
	verb refuses one written by hand (#3004) — so the only way to set up what
	#2958 guards against is to place the Note itself.
	"""

	step = p._pattern.steps.setdefault(0, subsequence.pattern.Step())

	for pitch in pitches:
		step.notes.append(subsequence.pattern.Note(
			pitch = pitch, velocity = 100, duration = 8 * 24, channel = p._pattern.channel,
		))


def test_a_render_holding_a_chord_voiced_past_127_still_writes_its_file (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""A note past 127 held to the end of the render costs neither the file nor the valid notes' releases."""

	def build (p: typing.Any) -> None:
		p.chord("C", root=110, count=6, duration=8)
		_hold_a_note_past_the_ceiling(p, (132, 136))

	timeline, length = _file(tmp_path, 1, build)
	sounded = sorted(message.note for _, message in timeline if message.type == "note_on" and message.velocity > 0)

	assert sounded == [108, 112, 115, 120, 124, 127]
	assert _sounding_at_the_end(timeline) == []
	assert length == 1920


def test_recording_a_release_no_message_can_carry_is_logged_not_raised (patch_midi: None, caplog: pytest.LogCaptureFixture) -> None:

	"""The release pass must finish whatever it meets: a note number out of range is logged and skipped."""

	seq = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", record=True)
	seq.recorded_events.clear()
	seq.pulse_count = 24

	failure: typing.Optional[BaseException] = None

	try:
		seq._record_release(0, 140)
		seq._record_release(0, 64)
	except Exception as caught:
		failure = caught

	assert failure is None
	assert [(pulse, message.note) for pulse, message, _ in seq.recorded_events] == [(24.0, 64)]
	assert "Could not record the release of note 140" in caplog.text


@pytest.mark.parametrize(("channel", "note", "velocity", "sounds"), [
	pytest.param(0, 60, 100, True, id="ordinary"),
	pytest.param(15, 127, 127, True, id="every-maximum"),
	pytest.param(16, 60, 100, False, id="channel-17"),
	pytest.param(0, 128, 100, False, id="note-128"),
	pytest.param(0, 60, 128, False, id="velocity-128"),
	pytest.param(-1, 60, 100, False, id="channel-below-0"),
	pytest.param(0.5, 60, 100, False, id="fractional-channel"),
	pytest.param(0, 60.0, 100, False, id="float-note"),
	pytest.param(True, 60, 100, False, id="bool-channel"),
])
def test_only_a_note_on_midi_can_carry_counts_as_sounding (channel: typing.Any, note: typing.Any, velocity: typing.Any, sounds: bool) -> None:

	"""A channel from 0 to 15 and a note and velocity from 0 to 127, each a whole number; anything else would fail to send."""

	assert subsequence.sequencer._can_sound(channel, note, velocity) is sounds
