"""A silenced part lets its drone go, and a teardown spares the neighbours (#2996).

Three faults, one area.

`mute()`, the energy gate and a transition mute all stop a part's builder, and
the builder is what would have turned its drone off — so a drone struck at beat
0 and muted at cycle 2 was released only when the render ended, at beat 48.

A drone queued inside the reschedule lookahead played *after* `unregister()`'s
release pass, and nothing ever released it.

And `_stop_pattern_notes` released every sounding note on the pattern's
`(device, channel)`, its own or not: a pad's four-beat note was cut 0.08 of a
beat in when an arp on the same channel was unregistered.

Decision 3 of #2991: release at the start of the first silent cycle, and
unmuting does not strike it again.
"""

import asyncio
import typing

import pytest

import conftest

import subsequence
import subsequence.pattern
import subsequence.sequencer


PPQ = 24


def _sequencer () -> subsequence.sequencer.Sequencer:

	"""A sequencer with a spy on device 0."""

	sequencer = subsequence.sequencer.Sequencer(output_device_name = "Dummy MIDI", initial_bpm = 120)
	sequencer.midi_out = conftest.SpyMidiOut()

	return sequencer


class _Part (subsequence.pattern.Pattern):

	"""A pattern that can be told it has been silenced."""

	def __init__ (self, **kwargs: typing.Any) -> None:
		self.is_silenced = False
		super().__init__(**kwargs)


async def _hold_a_drone (
	sequencer: subsequence.sequencer.Sequencer,
	pattern: typing.Any,
	note: int = 40,
) -> None:

	"""Put *pattern* in the state of holding a drone, as a struck drone leaves it."""

	async with sequencer.queue_lock:
		sequencer._held_drones.setdefault(pattern, set()).add((pattern.device, pattern.channel, note))

	sequencer.active_notes.add((pattern.device, pattern.channel, note))
	sequencer._note_owner[(pattern.device, pattern.channel, note)] = pattern


def _note_offs (sequencer: subsequence.sequencer.Sequencer) -> typing.List[typing.Any]:

	"""Every note_off the queue holds."""

	return [event for event in sequencer.event_queue if event.message_type == "note_off"]


# ---------------------------------------------------------------------------
# A silenced part releases its drone
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_muted_part_releases_its_drone (patch_midi: None) -> None:

	"""It rang until the performance stopped, because the builder never ran again."""

	sequencer = _sequencer()
	pattern = _Part(channel = 0, length = 4, device = 0)

	await _hold_a_drone(sequencer, pattern)

	pattern.is_silenced = True
	await sequencer.schedule_pattern(pattern, start_pulse = 4 * PPQ)

	assert sequencer._held_drones.get(pattern) == set(), "the drone is still held"

	released = _note_offs(sequencer)

	assert len(released) == 1
	assert released[0].note == 40
	assert released[0].pulse == 4 * PPQ, "released somewhere other than the start of the silent cycle"


@pytest.mark.asyncio
async def test_a_part_still_playing_keeps_its_drone (patch_midi: None) -> None:

	"""A drone is meant to last across cycles — releasing it every bar is not the fix."""

	sequencer = _sequencer()
	pattern = _Part(channel = 0, length = 4, device = 0)

	await _hold_a_drone(sequencer, pattern)

	pattern.is_silenced = False
	await sequencer.schedule_pattern(pattern, start_pulse = 4 * PPQ)

	assert sequencer._held_drones.get(pattern) == {(0, 0, 40)}, "a sounding part lost its drone"
	assert _note_offs(sequencer) == []


@pytest.mark.asyncio
async def test_a_silenced_part_releases_on_every_destination (patch_midi: None) -> None:

	"""A mirrored drone rings on the mirror too."""

	sequencer = _sequencer()
	sequencer._output_devices.add("Secondary", conftest.SpyMidiOut())

	pattern = _Part(channel = 2, length = 4, device = 0, mirrors = [(1, 7)])

	async with sequencer.queue_lock:
		sequencer._held_drones.setdefault(pattern, set()).update({(0, 2, 40), (1, 7, 40)})

	pattern.is_silenced = True
	await sequencer.schedule_pattern(pattern, start_pulse = 4 * PPQ)

	released = {(event.device, event.channel, event.note) for event in _note_offs(sequencer)}

	assert released == {(0, 2, 40), (1, 7, 40)}, released


@pytest.mark.asyncio
async def test_unmuting_does_not_strike_the_drone_again (patch_midi: None) -> None:

	"""Decision 3: the builder decides what sounds, so it places a new one or does not."""

	sequencer = _sequencer()
	pattern = _Part(channel = 0, length = 4, device = 0)

	await _hold_a_drone(sequencer, pattern)

	pattern.is_silenced = True
	await sequencer.schedule_pattern(pattern, start_pulse = 4 * PPQ)

	pattern.is_silenced = False
	sequencer.event_queue.clear()
	await sequencer.schedule_pattern(pattern, start_pulse = 8 * PPQ)

	struck = [event for event in sequencer.event_queue if event.message_type == "note_on"]

	assert struck == [], "unmuting brought the drone back by itself"
	assert sequencer._held_drones.get(pattern) == set()


@pytest.mark.parametrize("muted, gated, expected", [
	(True, False, True),		# a performer mute
	(False, True, True),		# the energy gate closing
	(True, True, True),			# both
	(False, False, False),		# playing
])
def test_the_three_ways_of_being_silenced_all_count (
	patch_midi: None, muted: bool, gated: bool, expected: bool,
) -> None:

	"""A transition mute sets `_muted` too, so these two flags are the whole set."""

	composition = subsequence.Composition(bpm = 120, output_device = "Dummy MIDI")

	@composition.pattern(channel = 1, beats = 4)
	def part (p: typing.Any) -> None:
		p.note(60, beat = 0.0)

	pattern = composition._build_pattern_from_pending(composition._pending_patterns[-1], start_pulse = 0)

	pattern._muted = muted
	pattern._energy_gated = gated

	assert pattern.is_silenced is expected


# ---------------------------------------------------------------------------
# unregister() spares the neighbours
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unregister_leaves_another_patterns_note_sounding (patch_midi: None) -> None:

	"""The pad's four-beat note was cut 0.08 of a beat in when the arp went."""

	sequencer = _sequencer()

	arp = subsequence.pattern.Pattern(channel = 3, length = 1, device = 0)
	pad = subsequence.pattern.Pattern(channel = 3, length = 4, device = 0)

	for pattern, note in ((arp, 60), (pad, 67)):
		sequencer.active_notes.add((0, 3, note))
		sequencer._note_owner[(0, 3, note)] = pattern

	await sequencer._stop_pattern_notes(arp)

	assert (0, 3, 67) in sequencer.active_notes, "the pad's note was cut with the arp's"
	assert (0, 3, 60) not in sequencer.active_notes, "the arp's own note kept ringing"

	sent = [message for message in sequencer.midi_out.sent if message.type == "note_off"]

	assert [message.note for message in sent] == [60]


@pytest.mark.asyncio
async def test_two_parts_on_one_channel_end_to_end (patch_midi: None) -> None:

	"""The ticket's own case, with nothing set by hand.

	Both notes are placed by `schedule_pattern`, dispatched by `_advance_pulse`
	and only then is one part torn down — so this catches a break anywhere along
	the chain, where a test that writes the owner map itself catches only the
	last link.
	"""

	sequencer = _sequencer()

	arp = subsequence.pattern.Pattern(channel = 3, length = 4, device = 0)
	pad = subsequence.pattern.Pattern(channel = 3, length = 4, device = 0)

	arp.add_note_beats(0.0, 60, 100, 0.25)
	pad.add_note_beats(0.0, 67, 80, 4.0)

	await sequencer.schedule_pattern(arp, start_pulse = 0)
	await sequencer.schedule_pattern(pad, start_pulse = 0)

	await sequencer._advance_pulse()

	assert {(0, 3, 60), (0, 3, 67)} <= sequencer.active_notes, \
		f"both notes should be sounding: {sorted(sequencer.active_notes)}"

	await sequencer._stop_pattern_notes(arp)

	assert (0, 3, 67) in sequencer.active_notes, "the pad's four-beat note was cut with the arp's"
	assert (0, 3, 60) not in sequencer.active_notes, "the arp's own note kept ringing"


@pytest.mark.asyncio
async def test_unregister_still_releases_a_note_nobody_owns (patch_midi: None) -> None:

	"""A one-shot's note has no builder coming back for it — this is its last chance."""

	sequencer = _sequencer()
	pattern = subsequence.pattern.Pattern(channel = 3, length = 4, device = 0)

	sequencer.active_notes.add((0, 3, 55))		# no owner recorded

	await sequencer._stop_pattern_notes(pattern)

	assert (0, 3, 55) not in sequencer.active_notes, "an unowned note was left to ring for ever"


@pytest.mark.asyncio
async def test_unregister_drops_its_own_queued_note_ons (patch_midi: None) -> None:

	"""A drone struck inside the lookahead played after the release pass."""

	sequencer = _sequencer()
	pattern = subsequence.pattern.Pattern(channel = 5, length = 4, device = 0)

	sequencer._push_event(subsequence.sequencer.MidiEvent(
		pulse = 10 * PPQ, message_type = "note_on", channel = 5, note = 48, velocity = 90, device = 0,
	), owner = pattern)

	await sequencer._stop_pattern_notes(pattern)

	assert [event for event in sequencer.event_queue if event.message_type == "note_on"] == [], \
		"a note-on it had queued survived the teardown"


@pytest.mark.asyncio
async def test_unregister_leaves_another_patterns_queued_notes_alone (patch_midi: None) -> None:

	"""Dropping pending note-ons must not empty the queue for everyone."""

	sequencer = _sequencer()

	going = subsequence.pattern.Pattern(channel = 5, length = 4, device = 0)
	staying = subsequence.pattern.Pattern(channel = 5, length = 4, device = 0)

	for pattern, note in ((going, 48), (staying, 55)):
		sequencer._push_event(subsequence.sequencer.MidiEvent(
			pulse = 10 * PPQ, message_type = "note_on", channel = 5, note = note, velocity = 90, device = 0,
		), owner = pattern)

	await sequencer._stop_pattern_notes(going)

	left = [event.note for event in sequencer.event_queue if event.message_type == "note_on"]

	assert left == [55], left


@pytest.mark.asyncio
async def test_unregister_leaves_queued_note_offs_alone (patch_midi: None) -> None:

	"""Dropping a note-off would strand the note it was going to end."""

	sequencer = _sequencer()
	pattern = subsequence.pattern.Pattern(channel = 5, length = 4, device = 0)

	sequencer._push_event(subsequence.sequencer.MidiEvent(
		pulse = 10 * PPQ, message_type = "note_off", channel = 5, note = 48, velocity = 0, device = 0,
	), owner = pattern)

	await sequencer._stop_pattern_notes(pattern)

	assert len(_note_offs(sequencer)) == 1, "a queued release was thrown away"


# ---------------------------------------------------------------------------
# What the sequencer records about a note
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_dispatched_note_records_who_struck_it (patch_midi: None) -> None:

	"""The whole mechanism rests on this being kept up to date."""

	sequencer = _sequencer()
	pattern = subsequence.pattern.Pattern(channel = 1, length = 4, device = 0)

	sequencer._push_event(subsequence.sequencer.MidiEvent(
		pulse = 0, message_type = "note_on", channel = 1, note = 64, velocity = 100, device = 0,
	), owner = pattern)

	await sequencer._advance_pulse()

	assert sequencer._note_owner.get((0, 1, 64)) is pattern


@pytest.mark.asyncio
async def test_a_released_note_is_forgotten (patch_midi: None) -> None:

	"""Otherwise the map grows for the length of the performance."""

	sequencer = _sequencer()
	pattern = subsequence.pattern.Pattern(channel = 1, length = 4, device = 0)

	sequencer._push_event(subsequence.sequencer.MidiEvent(
		pulse = 0, message_type = "note_on", channel = 1, note = 64, velocity = 100, device = 0,
	), owner = pattern)
	sequencer._push_event(subsequence.sequencer.MidiEvent(
		pulse = 1, message_type = "note_off", channel = 1, note = 64, velocity = 0, device = 0,
	), owner = pattern)

	await sequencer._advance_pulse()
	await sequencer._advance_pulse()

	assert (0, 1, 64) not in sequencer._note_owner


@pytest.mark.asyncio
async def test_a_pattern_is_not_kept_alive_by_a_note_it_left_ringing (patch_midi: None) -> None:

	"""The map is weak on purpose: a hung note must not pin its pattern in memory."""

	import gc
	import weakref

	sequencer = _sequencer()
	pattern = subsequence.pattern.Pattern(channel = 1, length = 4, device = 0)
	watch = weakref.ref(pattern)

	sequencer._push_event(subsequence.sequencer.MidiEvent(
		pulse = 0, message_type = "note_on", channel = 1, note = 64, velocity = 100, device = 0,
	), owner = pattern)

	await sequencer._advance_pulse()
	sequencer.event_queue.clear()

	del pattern
	gc.collect()

	assert watch() is None, "a ringing note kept its pattern alive"
