"""What a queued cc_forward carries to the synth (#3068, M9 of the 2026-09-19 review).

`cc_forward` has two modes. **Instant** hands the mido message straight to the
port and was always right. **Queued** puts it through the event heap, so every
message is turned into a `MidiEvent` by `from_mido` and back by `to_mido` — and
neither handled three of the types `_forward_identity` names as forwardable.

Measured on `798bbe6`, round-tripping each type:

    sent: program 42 / aftertouch 77 / polytouch 64:88 / CC 7 = 99

    program_change  -> program=0
    aftertouch      -> DROPPED (to_mido returned None)
    polytouch       -> DROPPED (to_mido returned None)
    control_change  -> control=7 value=99

**The program change lost its number** because `from_mido`'s fallback read
`getattr(msg, 'value', 0)` where mido carries `.program` — so forwarding a
patch change from a controller silently selected **patch 0** on the synth.

**Aftertouch and polytouch vanished** because `to_mido` had no branch for
them, and `None` is how OSC is filtered out on the way to a port.
"""

import typing

import mido
import pytest

import subsequence
import subsequence.sequencer


# Every channel-voice message a forward can carry, with the attribute that
# holds its payload.  `_forward_identity` names the first four as controls
# whose later value replaces an earlier one, which is what says the forwarding
# path means to carry them.
ROUND_TRIP = [
	mido.Message("program_change", channel = 3, program = 42),
	mido.Message("aftertouch", channel = 4, value = 77),
	mido.Message("polytouch", channel = 5, note = 64, value = 88),
	mido.Message("control_change", channel = 6, control = 7, value = 99),
	mido.Message("pitchwheel", channel = 7, pitch = -2000),
	mido.Message("note_on", channel = 8, note = 60, velocity = 100),
	mido.Message("note_off", channel = 8, note = 60, velocity = 0),
]


@pytest.mark.parametrize("message", ROUND_TRIP, ids = lambda m: m.type)
def test_a_forwarded_message_reaches_the_synth_unchanged (message: mido.Message) -> None:

	"""Through the event queue and back out, byte for byte.

	Comparing whole messages rather than named fields is deliberate: the bug
	was a field nobody thought to check, so a test naming the fields it knows
	about would have missed it in exactly the same way.
	"""

	event = subsequence.sequencer.MidiEvent.from_mido(0, message, device = 0)
	returned = event.to_mido()

	assert returned is not None, (
		f"a {message.type} was dropped on the way to the port — to_mido returned None, "
		f"which is how OSC is filtered, so nothing said a word"
	)

	assert returned.bytes() == message.bytes(), (
		f"a {message.type} changed on the way through: sent {message}, got {returned}"
	)


def test_a_forwarded_program_change_keeps_its_patch_number () -> None:

	"""The audible one, named on its own: patch 42 must not arrive as patch 0."""

	sent = mido.Message("program_change", channel = 0, program = 42)
	returned = subsequence.sequencer.MidiEvent.from_mido(0, sent, device = 0).to_mido()

	assert returned is not None
	assert returned.program == 42, (
		f"forwarding patch {sent.program} selected patch {returned.program} on the synth"
	)


def test_pressure_survives_the_queue (patch_midi_multi: typing.Dict[str, typing.Any]) -> None:

	"""End to end: the drain puts a forwarded aftertouch on the actual port.

	The round-trip tests above read the conversion; this one drives the path
	the messages really take, so a break anywhere between the forward buffer
	and the port is caught too.
	"""

	sequencer = subsequence.sequencer.Sequencer(
		output_device_name = "Primary MIDI", initial_bpm = 120,
	)
	sequencer._init_midi_output()

	spy = patch_midi_multi["Primary MIDI"]
	before = len(spy.sent)

	for message in (
		mido.Message("aftertouch", channel = 0, value = 77),
		mido.Message("polytouch", channel = 0, note = 64, value = 88),
		mido.Message("program_change", channel = 0, program = 42),
	):
		sequencer._send_midi(subsequence.sequencer.MidiEvent.from_mido(0, message, device = 0))

	arrived = spy.sent[before:]

	assert [m.type for m in arrived] == ["aftertouch", "polytouch", "program_change"], (
		f"not everything reached the port: {[m.type for m in arrived]}"
	)

	assert arrived[0].value == 77
	assert (arrived[1].note, arrived[1].value) == (64, 88)
	assert arrived[2].program == 42


def test_osc_is_the_only_thing_that_converts_to_nothing () -> None:

	"""`to_mido() is None` must mean OSC and nothing else.

	That is the invariant the silent drop broke: `_send_midi` reads `None` as
	"an internal type, skip it", so any message type that falls past every
	branch disappears wearing OSC's clothes.
	"""

	osc = subsequence.sequencer.MidiEvent(
		pulse = 0, message_type = "osc", channel = 0, data = ("/x", (1,)),
	)

	assert osc.to_mido() is None

	for message in ROUND_TRIP:
		event = subsequence.sequencer.MidiEvent.from_mido(0, message, device = 0)
		assert event.to_mido() is not None, f"{message.type} converts to nothing, like OSC does"


def test_a_message_that_cannot_be_sent_says_so (
	patch_midi_multi: typing.Dict[str, typing.Any],
	caplog: pytest.LogCaptureFixture,
) -> None:

	"""A drop is logged, so the next one of these is not found months later."""

	sequencer = subsequence.sequencer.Sequencer(
		output_device_name = "Primary MIDI", initial_bpm = 120,
	)
	sequencer._init_midi_output()

	unsendable = subsequence.sequencer.MidiEvent(
		pulse = 0, message_type = "songpos", channel = 0,
	)

	with caplog.at_level("WARNING"):
		sequencer._send_midi(unsendable)

	assert "songpos" in caplog.text, (
		f"a message nothing can put on the wire was dropped in silence: {caplog.text!r}"
	)
