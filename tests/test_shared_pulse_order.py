"""Events that share a moment go out as note-offs, then channel messages, then note-ons (#2791)."""

import heapq
import pathlib
import typing

import mido

import subsequence
import subsequence.pattern
import subsequence.sequencer


def _render (composition: subsequence.Composition, bars: int, tmp_path: pathlib.Path) -> typing.List[typing.Tuple[int, mido.Message]]:

	"""Render and return the file's (tick, message) timeline, meta messages left out."""

	path = str(tmp_path / "order.mid")
	composition.render(bars=bars, filename=path)

	now = 0
	timeline = []

	for message in mido.MidiFile(path).tracks[0]:
		now += message.time
		if not message.is_meta:
			timeline.append((now, message))

	return timeline


def _at (timeline: typing.List[typing.Tuple[int, mido.Message]], tick: int) -> typing.List[str]:

	"""What the file says at *tick*, in order, as short labels."""

	labels = []

	for when, message in timeline:
		if when != tick:
			continue
		if message.type in ("note_on", "note_off"):
			labels.append(f"{message.type} {message.note}")
		elif message.type == "control_change":
			labels.append(f"cc {message.control}")
		elif message.type == "program_change":
			labels.append(f"program {message.program}")
		elif message.type == "pitchwheel":
			labels.append("bend 0" if message.pitch == 0 else "bend")
		else:
			labels.append(message.type)

	assert labels, f"nothing at tick {tick}"

	return labels


def test_a_program_change_on_a_note_s_beat_reaches_the_synth_before_the_note (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Bank select, then the program, then the note, whatever order the pattern called them in."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	@composition.pattern(channel=1, beats=4)
	def bass (p: typing.Any) -> None:
		p.note(28, beat=0, duration=1)
		p.program_change(38, bank_msb=1, bank_lsb=2)

	assert _at(_render(composition, 1, tmp_path), 0) == ["cc 0", "cc 32", "program 38", "note_on 28"]


def test_a_slide_target_starts_after_its_bend_is_reset (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""At the target's onset the sliding note is released, the bend lands and resets, and only then does the target sound."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	@composition.pattern(channel=2, beats=4)
	def acid (p: typing.Any) -> None:
		p.sequence(steps=[0, 4, 8, 12], pitches=[40, 42, 40, 43], durations=1)
		p.slide(notes=[1], time=0.5, bend_range=12)

	assert _at(_render(composition, 1, tmp_path), 480) == ["note_off 40", "bend", "bend 0", "note_on 42"]


def test_a_pitch_released_on_the_beat_another_part_starts_it_does_not_cut_the_new_note (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Two parts on one channel: the release pushed after the new note-on still goes out before it."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	@composition.pattern(channel=1, beats=4)
	def later (p: typing.Any) -> None:
		p.note(60, beat=1, duration=1)

	@composition.pattern(channel=1, beats=4)
	def earlier (p: typing.Any) -> None:
		p.note(60, beat=0, duration=1)

	assert _at(_render(composition, 1, tmp_path), 480) == ["note_off 60", "note_on 60"]


def test_a_zero_length_note_is_released_a_pulse_after_it_starts (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Note-offs lead their moment, so a note-off due at its own note-on's pulse would hang the note."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	@composition.pattern(channel=1, beats=4)
	def blip (p: typing.Any) -> None:
		p._pattern.add_note(position=0, pitch=60, velocity=100, duration=0)

	timeline = _render(composition, 1, tmp_path)

	assert _at(timeline, 0) == ["note_on 60"]
	assert _at(timeline, 20) == ["note_off 60"]


def test_the_rank_follows_the_message_whenever_it_is_read () -> None:

	"""A note-on at velocity 0 is a note-off, and an event changed after it was built sorts by what it is when pushed."""

	sequencer = subsequence.sequencer.Sequencer.__new__(subsequence.sequencer.Sequencer)
	sequencer.event_queue = []
	sequencer._event_counter = iter(range(100))

	muted = subsequence.sequencer.MidiEvent(pulse=0, message_type="note_on", channel=0, note=60, velocity=0)
	sounding = subsequence.sequencer.MidiEvent(pulse=0, message_type="note_on", channel=0, note=62, velocity=90)
	cc = subsequence.sequencer.MidiEvent(pulse=0, message_type="control_change", channel=0, control=7, value=100)
	changed = subsequence.sequencer.MidiEvent(pulse=0, message_type="note_on", channel=0, note=64, velocity=90)
	changed.velocity = 0

	for event in (sounding, cc, changed, muted):
		sequencer._push_event(event)

	order = []

	while sequencer.event_queue:
		event = heapq.heappop(sequencer.event_queue)
		order.append((event.message_type, event.note, event.velocity))

	assert order == [("note_on", 64, 0), ("note_on", 60, 0), ("control_change", 0, 0), ("note_on", 62, 90)]
