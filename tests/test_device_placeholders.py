"""A device that does not open keeps its number, and stays silent (#2997).

Only the ports that opened used to be registered, numbered by position, so one
unplugged synth moved every later device down by one: a part written for device
2 arrived at device 1's instrument, the last index resolved to nothing and its
part was dropped without a word, and the missing device's own alias resolved to
device 0 — the lead playing out of the drum machine.
"""

import pathlib
import typing

import mido
import pytest

import subsequence
import subsequence.composition
import subsequence.midi_utils
import subsequence.sequencer
import conftest


DEVICES = ["Synth A", "Synth B", "Synth C"]


@pytest.fixture
def patch_midi_with_a_dead_port (monkeypatch: pytest.MonkeyPatch) -> typing.Callable[[str], typing.Dict[str, conftest.NamedSpyMidiOut]]:

	"""Patch mido with three outputs, one of which refuses to open."""

	def install (dead: str) -> typing.Dict[str, conftest.NamedSpyMidiOut]:

		ports: typing.Dict[str, conftest.NamedSpyMidiOut] = {}

		def _open (name: str) -> conftest.NamedSpyMidiOut:
			if name == dead:
				raise OSError(f"{name}: unplugged")
			ports.setdefault(name, conftest.NamedSpyMidiOut(name))
			return ports[name]

		monkeypatch.setattr(mido, "get_output_names", lambda: list(DEVICES))
		monkeypatch.setattr(mido, "open_output", _open)
		monkeypatch.setattr(mido, "get_input_names", lambda: [])

		return ports

	return install


def _three_devices (ports: typing.Dict[str, conftest.NamedSpyMidiOut]) -> subsequence.Composition:

	"""A composition with three declared outputs, whose ports are then opened.

	It opens them through the very method a performance uses. A *render* is no
	longer the way to test this: since #2995 a render opens no port at all and
	stands every device in with a placeholder, so nothing would try to open the
	dead one.
	"""

	composition = subsequence.Composition(output_device = "Synth A", bpm = 960)
	composition.midi_output("Synth B", name = "middle")
	composition.midi_output("Synth C", name = "last")

	composition._open_output_devices()

	return composition


def _port_of (composition: subsequence.Composition, device: typing.Union[int, str]) -> typing.Any:

	"""The port a device name or number resolves to — None for a placeholder."""

	return composition._sequencer._output_devices.get(device)


# ---------------------------------------------------------------------------
# With the middle device unplugged
# ---------------------------------------------------------------------------

def test_a_device_that_does_not_open_keeps_its_number (tmp_path: pathlib.Path, patch_midi_with_a_dead_port: typing.Any) -> None:

	"""Synth C is still device 2, so a part written for it reaches its port."""

	ports = patch_midi_with_a_dead_port("Synth B")
	composition = _three_devices(ports)

	assert composition._output_device_names["Synth C"] == 2
	assert composition._output_device_names["last"] == 2
	assert _port_of(composition, 2) is ports["Synth C"]


def test_a_part_on_a_missing_device_is_silent_rather_than_moved (tmp_path: pathlib.Path, patch_midi_with_a_dead_port: typing.Any) -> None:

	"""Device 1 is the device that did not open — not whoever inherited the number."""

	ports = patch_midi_with_a_dead_port("Synth B")
	composition = _three_devices(ports)

	assert composition._output_device_names["Synth B"] == 1
	assert _port_of(composition, 1) is None
	assert _port_of(composition, 0) is ports["Synth A"]


def test_the_alias_of_a_missing_device_resolves_to_the_placeholder (tmp_path: pathlib.Path, patch_midi_with_a_dead_port: typing.Any) -> None:

	"""'middle' means the device that did not open — it used to mean device 0."""

	ports = patch_midi_with_a_dead_port("Synth B")
	composition = _three_devices(ports)

	assert composition._output_device_names["middle"] == 1
	assert _port_of(composition, "middle") is None


def test_a_missing_primary_keeps_device_zero (tmp_path: pathlib.Path, patch_midi_with_a_dead_port: typing.Any) -> None:

	"""Everything used to shuffle up onto index 0: the lead out of the drum machine."""

	ports = patch_midi_with_a_dead_port("Synth A")
	composition = _three_devices(ports)

	assert _port_of(composition, 0) is None
	assert composition._output_device_names["Synth B"] == 1
	assert composition._output_device_names["Synth C"] == 2
	assert _port_of(composition, 1) is ports["Synth B"]
	assert _port_of(composition, 2) is ports["Synth C"]


def test_the_missing_device_is_named_in_the_log (tmp_path: pathlib.Path, patch_midi_with_a_dead_port: typing.Any, caplog: pytest.LogCaptureFixture) -> None:

	"""One line, naming the device and the number it keeps."""

	ports = patch_midi_with_a_dead_port("Synth B")

	with caplog.at_level("WARNING"):
		_three_devices(ports)

	warnings = [record.getMessage() for record in caplog.records if "Synth B" in record.getMessage()]

	assert any("keeps device 1" in message for message in warnings), warnings


def test_a_render_stands_every_device_in_and_opens_none (tmp_path: pathlib.Path, patch_midi_with_a_dead_port: typing.Any) -> None:

	"""A render resolves every name to a placeholder, so routing is unchanged (#2995)."""

	ports = patch_midi_with_a_dead_port("Synth B")

	composition = subsequence.Composition(output_device = "Synth A", bpm = 960)
	composition.midi_output("Synth B", name = "middle")
	composition.midi_output("Synth C", name = "last")
	composition._sequencer.render_mode = True

	composition._open_output_devices()

	assert composition._output_device_names["Synth A"] == 0
	assert composition._output_device_names["middle"] == 1
	assert composition._output_device_names["last"] == 2
	assert [_port_of(composition, index) for index in (0, 1, 2)] == [None, None, None]
	assert ports == {}		# not one port was opened


# ---------------------------------------------------------------------------
# The registry itself
# ---------------------------------------------------------------------------

def test_a_placeholder_takes_an_index_and_answers_to_its_name () -> None:

	"""The index and the name survive; only the port is missing."""

	registry = subsequence.midi_utils.MidiDeviceRegistry()
	registry.add("open", conftest.NamedSpyMidiOut("open"))
	placeholder = registry.add("dead", None)
	after = registry.add("later", conftest.NamedSpyMidiOut("later"))

	assert (placeholder, after) == (1, 2)
	assert registry.index_of("dead") == 1
	assert registry.get("dead") is None
	assert registry.get(2) is not None


def test_iterating_the_registry_skips_a_placeholder () -> None:

	"""Panic and the MIDI clock walk the registry, and neither may call None.send()."""

	registry = subsequence.midi_utils.MidiDeviceRegistry()
	registry.add("dead", None)
	registry.add("open", conftest.NamedSpyMidiOut("open"))

	ports = list(registry)

	assert len(ports) == 1
	assert ports[0].name == "open"
	assert len(registry) == 2		# it still counts as a device


def test_closing_the_registry_skips_a_placeholder (caplog: pytest.LogCaptureFixture) -> None:

	"""Shutdown passes it by quietly — not with a logged failure to close nothing."""

	registry = subsequence.midi_utils.MidiDeviceRegistry()
	registry.add("dead", None)
	registry.add("open", conftest.NamedSpyMidiOut("open"))

	with caplog.at_level("ERROR"):
		registry.close_all()

	assert len(registry) == 0
	assert not [record for record in caplog.records if "dead" in record.getMessage()]
