"""A render writes a file and touches nothing else (#2995).

The Sequencer opened the output port in its constructor, so by the time
``render()`` said it was a render the rig was already connected — and every
event went straight out: a four-bar render of two parts put 860 messages
through two ports in a fraction of a second, program changes and clock ticks
among them, while the piece those synths were actually playing carried on.
A render configured with ``clock_follow`` waited for ticks that never came and
never returned at all.

So: a render opens no port, sends nothing, starts no server, and runs its own
simulated clock whatever the piece asked for. What it does do is register every
device as a placeholder, so routing is exactly what a performance would give.
"""

import asyncio
import pathlib
import typing

import mido
import pytest

import subsequence
import subsequence.composition
import subsequence.pattern
import subsequence.sequencer


@pytest.fixture
def watched_ports (monkeypatch: pytest.MonkeyPatch) -> typing.Dict[str, typing.Any]:

	"""Two rig-like outputs, recording every port opened and everything sent."""

	opened: typing.Dict[str, typing.Any] = {}

	class Port:

		def __init__ (self, name: str) -> None:
			self.name = name
			self.sent: typing.List[typing.Any] = []

		def send (self, message: typing.Any) -> None:
			self.sent.append(message)

		def close (self) -> None:
			pass

		def panic (self) -> None:
			pass

		def reset (self) -> None:
			pass

	def _open (name: str, *args: typing.Any, **kwargs: typing.Any) -> Port:
		opened.setdefault(name, Port(name))
		return opened[name]

	monkeypatch.setattr(mido, "get_output_names", lambda: ["Rig Synth", "Rig Drums"])
	monkeypatch.setattr(mido, "get_input_names", lambda: ["Rig Clock"])
	monkeypatch.setattr(mido, "open_output", _open)
	monkeypatch.setattr(mido, "open_input", lambda *a, **k: _open("Rig Clock"))

	return opened


def _piece (**options: typing.Any) -> subsequence.Composition:

	"""A two-device piece, with the rig's clock output on."""

	composition = subsequence.Composition(output_device = "Rig Synth", bpm = 960)
	composition.midi_output("Rig Drums", name = "drums")
	composition.clock_output()

	if options.get("follow"):
		composition.midi_input("Rig Clock", clock_follow = True)

	if options.get("link"):
		# link() itself requires the optional aalink package, which a test
		# machine need not have; _link_quantum is the state it sets and the
		# state the render path reads.
		composition._link_quantum = 4.0

	if options.get("servers"):
		composition.osc(receive_port = 9999, send_port = 9998)
		composition.live(port = 5999)

	@composition.pattern(channel = 1, beats = 4)
	def lead (p) -> None:
		p.note(60, beat = 0, duration = 1)
		p.program_change(5, beat = 2)

	@composition.pattern(channel = 10, beats = 4, device = "drums")
	def drums (p) -> None:
		p.note(36, beat = 0, duration = 1)

	return composition


def _pitches (filename: str) -> typing.List[int]:

	"""Every note_on pitch in the rendered file."""

	return sorted(
		message.note
		for track in mido.MidiFile(filename).tracks
		for message in track
		if not isinstance(message, mido.MetaMessage) and message.type == "note_on" and message.velocity > 0
	)


# ---------------------------------------------------------------------------
# What a render does not touch
# ---------------------------------------------------------------------------

def test_a_render_opens_no_port (tmp_path: pathlib.Path, watched_ports: typing.Dict[str, typing.Any]) -> None:

	"""Not one — the rig is usually playing something else."""

	_piece().render(bars = 4, filename = str(tmp_path / "quiet.mid"))

	assert watched_ports == {}


def test_a_render_sends_nothing_to_a_device (tmp_path: pathlib.Path, watched_ports: typing.Dict[str, typing.Any]) -> None:

	"""Even if a port were open, nothing is dispatched to it."""

	_piece().render(bars = 4, filename = str(tmp_path / "quiet.mid"))

	assert [message for port in watched_ports.values() for message in port.sent] == []


def test_a_render_starts_no_osc_or_live_server (tmp_path: pathlib.Path, watched_ports: typing.Dict[str, typing.Any], monkeypatch: pytest.MonkeyPatch) -> None:

	"""A render ends; a socket left listening invites control of nothing."""

	started: typing.List[str] = []

	composition = _piece(servers = True)

	async def _osc_start (*args: typing.Any, **kwargs: typing.Any) -> None:
		started.append("osc")

	async def _live_start (*args: typing.Any, **kwargs: typing.Any) -> None:
		started.append("live")

	monkeypatch.setattr(composition._osc_server, "start", _osc_start)
	monkeypatch.setattr(composition._live_server, "start", _live_start)

	composition.render(bars = 2, filename = str(tmp_path / "quiet.mid"))

	assert started == []
	assert composition._sequencer.osc_server is None		# nor is it wired to the clock


def test_a_render_joins_no_link_session (tmp_path: pathlib.Path, watched_ports: typing.Dict[str, typing.Any]) -> None:

	"""link() puts the piece in the room's tempo, which a file does not want."""

	composition = _piece(link = True)
	composition.render(bars = 2, filename = str(tmp_path / "quiet.mid"))

	assert composition._sequencer._link_clock is None


# ---------------------------------------------------------------------------
# What a render still does
# ---------------------------------------------------------------------------

def test_a_render_writes_every_part_on_every_device (tmp_path: pathlib.Path, watched_ports: typing.Dict[str, typing.Any]) -> None:

	"""Routing still resolves — the placeholders are what keep it honest."""

	filename = str(tmp_path / "both.mid")
	composition = _piece()
	composition.render(bars = 1, filename = filename)

	assert composition._output_device_names["drums"] == 1
	assert _pitches(filename) == [36, 60]


@pytest.mark.asyncio
async def test_a_render_under_clock_follow_completes (tmp_path: pathlib.Path, watched_ports: typing.Dict[str, typing.Any]) -> None:

	"""It waited for external ticks that never arrive, and never returned.

	Driven through _run with a timeout rather than render(), so a regression
	fails the suite instead of hanging it.
	"""

	composition = _piece(follow = True)
	composition._sequencer.recording = True
	composition._sequencer.record_filename = str(tmp_path / "followed.mid")
	composition._sequencer.render_mode = True
	composition._sequencer.render_bars = 2
	composition._sequencer.render_max_seconds = None

	await asyncio.wait_for(composition._run(), timeout = 10)

	assert pathlib.Path(str(tmp_path / "followed.mid")).exists()


@pytest.mark.asyncio
async def test_a_sequencer_in_render_mode_does_not_wait_for_an_external_clock (patch_midi: None) -> None:

	"""The guard in the clock loop itself, which the Composition path never reaches.

	Composition.render() turns clock_follow off before the loop starts, so
	only a Sequencer driven directly — the Direct Pattern API — arrives here
	still following. It must render rather than wait for ticks.
	"""

	sequencer = subsequence.sequencer.Sequencer(
		output_device_name = "Dummy MIDI",
		input_device_name = "Dummy MIDI",		# clock_follow needs an input to follow
		initial_bpm = 960,
		clock_follow = True,
	)
	sequencer.render_mode = True
	sequencer.render_bars = 1

	pattern = subsequence.pattern.Pattern(channel = 0, length = 4, device = 0)
	pattern.add_note(position = 0, pitch = 60, velocity = 100, duration = 12)
	await sequencer.schedule_pattern(pattern, start_pulse = 0)

	await sequencer.start()

	assert sequencer.task is not None
	await asyncio.wait_for(sequencer.task, timeout = 10)
	await sequencer.stop()

	assert sequencer.pulse_count >= 96		# it ran its bar on its own clock


def test_a_render_says_it_ignored_the_clock_it_was_given (tmp_path: pathlib.Path, watched_ports: typing.Dict[str, typing.Any], caplog: pytest.LogCaptureFixture) -> None:

	"""Once, because it changes what the file is."""

	with caplog.at_level("INFO"):
		_piece(follow = True, link = True).render(bars = 1, filename = str(tmp_path / "quiet.mid"))

	said = [record.getMessage() for record in caplog.records if "internal clock" in record.getMessage()]

	assert len(said) == 1
	assert "clock_follow" in said[0] and "link()" in said[0]


# ---------------------------------------------------------------------------
# Inputs (#3485)
# ---------------------------------------------------------------------------

def _controlled_piece (*inputs: str) -> subsequence.Composition:

	"""A piece written for controllers: a fader mapped with cc_map() sets its velocity."""

	composition = subsequence.Composition(output_device = "Dummy MIDI", bpm = 960)

	for index, device in enumerate(inputs):
		composition.midi_input(device, name = None if index == 0 else f"input_{index}")

	composition.cc_map(7, "swell", min_val = 55, max_val = 105)

	@composition.pattern(channel = 1, beats = 4)
	def lead (p) -> None:
		p.note(60, beat = 0, velocity = round(p.data.get("swell", 80)), duration = 1)

	return composition


def _velocities (filename: pathlib.Path) -> typing.List[int]:

	"""Every sounding note_on velocity in the rendered file."""

	return [
		message.velocity
		for track in mido.MidiFile(str(filename)).tracks
		for message in track
		if message.type == "note_on" and message.velocity > 0
	]


def test_a_render_opens_no_input (tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:

	"""Neither the primary input nor another: a control arriving mid-render would change the file."""

	opened: typing.List[str] = []

	class Port:

		def close (self) -> None:
			pass

	def open_input (name: typing.Optional[str] = None, *args: typing.Any, **kwargs: typing.Any) -> Port:
		opened.append(str(name))
		return Port()

	monkeypatch.setattr(mido, "get_input_names", lambda: ["Rig Keys", "Rig Pads"])
	monkeypatch.setattr(mido, "open_input", open_input)

	filename = tmp_path / "controlled.mid"
	_controlled_piece("Rig Keys", "Rig Pads").render(bars = 1, filename = str(filename))

	assert _velocities(filename) == [80]
	assert opened == []


def test_a_piece_whose_controller_is_not_plugged_in_still_renders (tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:

	"""It refused, naming the missing device.  It renders as though no control had moved."""

	monkeypatch.setattr(mido, "get_input_names", lambda: [])

	filename = tmp_path / "unplugged.mid"
	_controlled_piece("My Controller").render(bars = 1, filename = str(filename))

	assert _velocities(filename) == [80]


def test_a_piece_whose_second_controller_is_not_plugged_in_still_renders (tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:

	"""An additional input is looked up by its own path, which refused the same way."""

	monkeypatch.setattr(mido, "get_input_names", lambda: ["Rig Keys"])

	filename = tmp_path / "half_plugged.mid"
	_controlled_piece("Rig Keys", "My Pads").render(bars = 1, filename = str(filename))

	assert _velocities(filename) == [80]
