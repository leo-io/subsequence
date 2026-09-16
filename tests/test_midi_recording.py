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
	assert seq.recorded_events[-1] == (48.0, msg)


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
	_, msg = seq.recorded_events[0]
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
	_, msg = seq.recorded_events[0]
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
	seq.recorded_events.append((0.0, mido.Message('note_on', channel=0, note=60, velocity=100)))
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


def test_a_metre_is_written_over_four_because_a_beat_is_a_quarter_note (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""Only the beat count sets a bar here, so a declared (7, 8) plays and is written as 7/4 (#2736).

	Writing 7/8 would put a DAW's bar lines every three and a half quarter
	notes, against notes laid out seven quarter notes to the bar.
	"""

	timeline = _render(tmp_path, 2, bpm=120, time_signature=(7, 8))
	onsets = [tick for tick, message in timeline if message.type == "note_on" and message.velocity > 0]

	assert _opening(timeline) == [("time_signature", (7, 4)), ("set_tempo", 120.0)]
	assert onsets == [0, 7 * 480]
