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


def _render_three_devices (tmp_path: pathlib.Path, ports: typing.Dict[str, conftest.NamedSpyMidiOut]) -> subsequence.Composition:

	"""One part per device — by number for the first two, by alias for the third."""

	composition = subsequence.Composition(output_device = "Synth A", bpm = 960)
	composition.midi_output("Synth B", name = "middle")
	composition.midi_output("Synth C", name = "last")

	@composition.pattern(channel = 1, beats = 4, device = 0)
	def on_primary (p) -> None:
		p.note(48, beat = 0, duration = 1)

	@composition.pattern(channel = 2, beats = 4, device = 1)
	def on_middle (p) -> None:
		p.note(60, beat = 0, duration = 1)

	@composition.pattern(channel = 3, beats = 4, device = 2)
	def on_last (p) -> None:
		p.note(72, beat = 0, duration = 1)

	@composition.pattern(channel = 4, beats = 4, device = "middle")
	def by_alias (p) -> None:
		p.note(84, beat = 0, duration = 1)

	composition.render(bars = 1, filename = str(tmp_path / "devices.mid"))

	return composition


def _notes (port: conftest.NamedSpyMidiOut) -> typing.List[int]:

	"""The note numbers a spy port was sent."""

	return sorted({message.note for message in port.sent if message.type == "note_on" and message.velocity > 0})


# ---------------------------------------------------------------------------
# Through a render, with the middle device unplugged
# ---------------------------------------------------------------------------

def test_a_device_that_does_not_open_keeps_its_number (tmp_path: pathlib.Path, patch_midi_with_a_dead_port: typing.Any) -> None:

	"""Synth C is still device 2, so the part written for it arrives there."""

	ports = patch_midi_with_a_dead_port("Synth B")
	composition = _render_three_devices(tmp_path, ports)

	assert composition._output_device_names["Synth C"] == 2
	assert composition._output_device_names["last"] == 2
	assert _notes(ports["Synth C"]) == [72]


def test_a_part_on_a_missing_device_is_silent_rather_than_moved (tmp_path: pathlib.Path, patch_midi_with_a_dead_port: typing.Any) -> None:

	"""Its note used to land on whichever device inherited the number."""

	ports = patch_midi_with_a_dead_port("Synth B")
	_render_three_devices(tmp_path, ports)

	assert 60 not in _notes(ports["Synth A"])
	assert 60 not in _notes(ports["Synth C"])


def test_the_alias_of_a_missing_device_resolves_to_the_placeholder (tmp_path: pathlib.Path, patch_midi_with_a_dead_port: typing.Any) -> None:

	"""'middle' means the device that did not open — not device 0."""

	ports = patch_midi_with_a_dead_port("Synth B")
	composition = _render_three_devices(tmp_path, ports)

	# The audible symptom first: unmapped, the alias fell back to device 0 and
	# the part played out of the primary synth.
	assert 84 not in _notes(ports["Synth A"])
	assert 84 not in _notes(ports["Synth C"])
	assert composition._output_device_names["middle"] == 1


def test_a_missing_primary_keeps_device_zero (tmp_path: pathlib.Path, patch_midi_with_a_dead_port: typing.Any) -> None:

	"""Everything used to shuffle up onto index 0: the lead out of the drum machine."""

	ports = patch_midi_with_a_dead_port("Synth A")
	composition = _render_three_devices(tmp_path, ports)

	assert composition._output_device_names["Synth B"] == 1
	assert composition._output_device_names["Synth C"] == 2
	assert _notes(ports["Synth B"]) == [60, 84]		# device 1 and its alias
	assert _notes(ports["Synth C"]) == [72]
	assert 48 not in _notes(ports["Synth B"])		# the primary's part is silent


def test_the_missing_device_is_named_in_the_log (tmp_path: pathlib.Path, patch_midi_with_a_dead_port: typing.Any, caplog: pytest.LogCaptureFixture) -> None:

	"""One line, naming the device and the number it keeps."""

	ports = patch_midi_with_a_dead_port("Synth B")

	with caplog.at_level("WARNING"):
		_render_three_devices(tmp_path, ports)

	warnings = [record.getMessage() for record in caplog.records if "Synth B" in record.getMessage()]

	assert any("keeps device 1" in message for message in warnings), warnings


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
