"""A recording keeps which synth played what (#3067, M9 of the 2026-09-19 review).

`_record_event` stored `(pulse, message)` and `save_recording` built exactly one
track, so a session driving several synths saved as if it were one. Measured on
`798bbe6` with two parts on **channel 0 of different devices**, playing
overlapping note 60s:

    tracks in the file:     1
    channels in the file:   [0]
    note messages in order: ['note_on[60]', 'note_on[60]', 'note_off[60]', 'note_off[60]']

Two note-ons then two note-offs for the same pitch on the same channel. No
importer can pair those up — a DAW matches the first off to the first on, so
both notes get the wrong length and the two parts are indistinguishable.

The device travels with each recorded event now, and each gets its own track.
**The first device shares track 0 with the tempo and metre** rather than there
being a conductor track of its own, so a single-device recording — nearly all
of them — is exactly the one-track file it has always been.
"""

import pathlib
import typing

import mido
import pytest

import subsequence
import subsequence.pattern
import subsequence.sequencer


PPQN = 24


def _recorder (
	filename: pathlib.Path,
	device_names: typing.Sequence[str],
	ports: typing.Dict[str, typing.Any],
) -> subsequence.sequencer.Sequencer:

	"""A render-mode sequencer recording to *filename* across *device_names*."""

	sequencer = subsequence.sequencer.Sequencer(
		output_device_name = device_names[0],
		initial_bpm = 600,
		record_filename = str(filename),
	)
	sequencer.render_mode = True
	sequencer.render_bars = 2
	sequencer.recording = True

	sequencer._init_midi_output()

	for name in device_names[1:]:
		sequencer.add_output_device(name, ports[name])

	return sequencer


async def _play_one_note_per_device (
	sequencer: subsequence.sequencer.Sequencer,
	count: int,
) -> None:

	"""One part per device, all on channel 0, all playing an overlapping note 60.

	Same channel and same pitch on purpose: that is the case a single track
	cannot represent, because the note-offs cannot be matched to the right
	note-ons.
	"""

	for device in range(count):
		pattern = subsequence.pattern.Pattern(channel = 0, length = 4.0, device = device)
		pattern.add_note(position = device * 6, pitch = 60, velocity = 100, duration = 2 * PPQN)
		await sequencer.schedule_pattern(pattern, 0)

	await sequencer.start()
	await sequencer.task
	await sequencer.stop()


def _notes_on (track: mido.MidiTrack) -> typing.List[str]:

	return [
		f"{message.type}[{message.note}]" for message in track
		if message.type in ("note_on", "note_off")
	]


# ---------------------------------------------------------------------------
# More than one synth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_two_synths_save_as_two_tracks (
	tmp_path: pathlib.Path,
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""The finding: both parts used to land on one track, unpairable."""

	filename = tmp_path / "two.mid"
	sequencer = _recorder(filename, ["Primary MIDI", "Secondary MIDI"], patch_midi_multi)

	await _play_one_note_per_device(sequencer, 2)

	written = mido.MidiFile(str(filename))

	assert len(written.tracks) == 2, (
		f"two synths played and the file has {len(written.tracks)} track(s) — their parts "
		f"are merged and cannot be told apart"
	)

	for index, track in enumerate(written.tracks):
		assert _notes_on(track) == ["note_on[60]", "note_off[60]"], (
			f"track {index} holds {_notes_on(track)}, not one note with its own release"
		)


@pytest.mark.asyncio
async def test_each_track_is_named_after_its_synth (
	tmp_path: pathlib.Path,
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""So an import reads "Secondary MIDI" rather than "Track 2"."""

	filename = tmp_path / "named.mid"
	sequencer = _recorder(filename, ["Primary MIDI", "Secondary MIDI"], patch_midi_multi)

	await _play_one_note_per_device(sequencer, 2)

	written = mido.MidiFile(str(filename))

	names = [
		next(
			(message.name for message in track if message.type == "track_name"),
			None,
		)
		for track in written.tracks
	]

	assert names == ["Primary MIDI", "Secondary MIDI"], f"the tracks are named {names}"


@pytest.mark.asyncio
async def test_the_tempo_and_metre_are_written_once_on_the_first_track (
	tmp_path: pathlib.Path,
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""They describe the file, so they belong to it and not to a synth.

	Copying them onto every track is the obvious wrong answer, and a DAW reads
	the duplicates as a tempo map fighting itself.
	"""

	filename = tmp_path / "metre.mid"
	sequencer = _recorder(filename, ["Primary MIDI", "Secondary MIDI"], patch_midi_multi)

	await _play_one_note_per_device(sequencer, 2)

	written = mido.MidiFile(str(filename))

	per_track = [
		[message.type for message in track if message.type in ("set_tempo", "time_signature")]
		for track in written.tracks
	]

	assert per_track[0] == ["time_signature", "set_tempo"], (
		f"track 0 does not open with the metre and tempo: {per_track[0]}"
	)
	assert per_track[1] == [], f"the markings were copied onto track 1 as well: {per_track[1]}"


@pytest.mark.asyncio
async def test_every_track_ends_where_playback_stopped (
	tmp_path: pathlib.Path,
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""A short track reads as the piece ending early on that synth.

	Each track carries its own delta times, so each needs its own end — the
	device that stops playing first would otherwise close its track there.
	"""

	filename = tmp_path / "ends.mid"
	sequencer = _recorder(filename, ["Primary MIDI", "Secondary MIDI"], patch_midi_multi)

	await _play_one_note_per_device(sequencer, 2)

	written = mido.MidiFile(str(filename))

	lengths = [sum(message.time for message in track) for track in written.tracks]

	assert lengths[0] == lengths[1], (
		f"the tracks end at different points: {lengths} ticks — a DAW would read the "
		f"shorter one as that synth stopping early"
	)
	assert lengths[0] > 0, "the file has no length at all"


@pytest.mark.asyncio
async def test_a_third_synth_gets_a_third_track (
	tmp_path: pathlib.Path,
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""The control on the arithmetic: it is per device, not a hardcoded two."""

	filename = tmp_path / "three.mid"
	sequencer = _recorder(
		filename, ["Primary MIDI", "Secondary MIDI", "Third MIDI"], patch_midi_multi,
	)

	await _play_one_note_per_device(sequencer, 3)

	written = mido.MidiFile(str(filename))

	assert len(written.tracks) == 3, f"three synths played and the file has {len(written.tracks)} track(s)"

	# Counting tracks is not enough: routing every device back onto track 0
	# leaves the other two present and EMPTY, which a count cannot see.
	for index, track in enumerate(written.tracks):
		assert _notes_on(track) == ["note_on[60]", "note_off[60]"], (
			f"track {index} holds {_notes_on(track)}, not the one note its synth played"
		)


# ---------------------------------------------------------------------------
# One synth, which is nearly every recording
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_one_synth_still_saves_as_one_track (
	tmp_path: pathlib.Path,
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""Nothing changes for a piece driving a single synth.

	That is why the first device shares track 0 with the conductor's markings
	instead of there being a track of its own: a conductor track would turn
	every existing one-track recording into a two-track file.
	"""

	filename = tmp_path / "one.mid"
	sequencer = _recorder(filename, ["Primary MIDI"], patch_midi_multi)

	await _play_one_note_per_device(sequencer, 1)

	written = mido.MidiFile(str(filename))

	assert len(written.tracks) == 1, (
		f"a single-synth recording became a {len(written.tracks)}-track file"
	)

	assert _notes_on(written.tracks[0]) == ["note_on[60]", "note_off[60]"]

	assert not [message for message in written.tracks[0] if message.type == "track_name"], (
		"a single-track file gained a track name it never had"
	)


# ---------------------------------------------------------------------------
# The device travels with the event
# ---------------------------------------------------------------------------

def test_a_tempo_marking_belongs_to_the_file_not_a_synth (patch_midi: None) -> None:

	"""CONDUCTOR, so it is never sorted onto a synth's track."""

	sequencer = subsequence.sequencer.Sequencer(record = True, initial_bpm = 120)
	sequencer.recorded_events.clear()

	sequencer.set_bpm(140)

	assert sequencer.recorded_events, "nothing was recorded, so this proves nothing"

	_, message, device = sequencer.recorded_events[-1]

	assert message.type == "set_tempo"
	assert device == subsequence.sequencer.CONDUCTOR, (
		f"a tempo marking was recorded against device {device}"
	)


def test_a_release_is_recorded_against_the_synth_it_was_sounding_on (
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""A note-off sent outside the queue must land on its note-on's track.

	``stop()``, ``pause()`` and ``unregister()`` release notes directly, and
	those releases are recorded by ``_record_release``. Sent to the wrong
	track, a note hangs in the file on one synth while an orphan release sits
	on another.
	"""

	sequencer = subsequence.sequencer.Sequencer(
		output_device_name = "Primary MIDI", initial_bpm = 120, record = True,
	)
	sequencer._init_midi_output()
	sequencer.add_output_device("Secondary MIDI", patch_midi_multi["Secondary MIDI"])
	sequencer.recorded_events.clear()

	sequencer._record_release(channel = 0, note = 64, device = 1)

	assert sequencer.recorded_events, "the release was not recorded at all"

	_, message, device = sequencer.recorded_events[-1]

	assert message.type == "note_off" and message.note == 64
	assert device == 1, f"a release from device 1 was recorded against device {device}"


def test_a_device_name_is_captured_before_the_ports_close (
	patch_midi_multi: typing.Dict[str, typing.Any],
) -> None:

	"""``stop()`` closes and clears the registry before it saves.

	So a name read at save time is always None, and every track would be
	unnamed. The name is taken when a device first records something instead.
	"""

	sequencer = subsequence.sequencer.Sequencer(
		output_device_name = "Primary MIDI", initial_bpm = 120, record = True,
	)
	sequencer._init_midi_output()
	sequencer.add_output_device("Secondary MIDI", patch_midi_multi["Secondary MIDI"])

	sequencer._record_event(0, mido.Message("note_on", channel = 0, note = 60, velocity = 100), 1)

	assert sequencer._recorded_device_names.get(1) == "Secondary MIDI"

	sequencer._output_devices.close_all()

	assert sequencer._output_devices.name_of(1) is None, (
		"the registry still knows the name after close_all, so this test proves nothing"
	)
	assert sequencer._recorded_device_names.get(1) == "Secondary MIDI", (
		"the captured name was lost when the ports closed"
	)
