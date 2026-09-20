import typing

import mido
import pytest


class FakeMidiOut:

	"""Minimal MIDI output stub for tests."""

	def send (self, message: mido.Message) -> None:

		"""Ignore outgoing MIDI messages."""

		return None


	def close (self) -> None:

		"""No-op close for the fake device."""

		return None


	def panic (self) -> None:

		"""No-op panic for the fake device."""

		return None


	def reset (self) -> None:

		"""No-op reset for the fake device."""

		return None


class SpyMidiOut(FakeMidiOut):

	"""FakeMidiOut that records every sent message for test assertions."""

	def __init__ (self) -> None:

		self.sent: typing.List[mido.Message] = []


	def send (self, message: mido.Message) -> None:

		self.sent.append(message)


class FakeMidiIn:

	"""Minimal MIDI input stub for tests."""

	def __init__ (self, callback: typing.Optional[typing.Callable] = None) -> None:

		"""Store the callback for injecting test messages."""

		self.callback = callback

	def close (self) -> None:

		"""No-op close for the fake device."""

		return None

	def inject (self, message: mido.Message) -> None:

		"""Simulate receiving a MIDI message by calling the stored callback."""

		if self.callback is not None:
			self.callback(message)


def _fake_get_output_names () -> list[str]:

	"""Return a fixed list of MIDI output names for tests."""

	return ["Dummy MIDI"]


def _fake_open_output (name: str) -> FakeMidiOut:

	"""Return a fake MIDI output regardless of the name."""

	return FakeMidiOut()


# Module-level reference so tests can access the most recently created FakeMidiIn.
_current_fake_input: typing.Optional[FakeMidiIn] = None


def _fake_get_input_names () -> list[str]:

	"""Return a fixed list of MIDI input names for tests."""

	return ["Dummy MIDI"]


def _fake_open_input (name: str, callback: typing.Optional[typing.Callable] = None) -> FakeMidiIn:

	"""Return a fake MIDI input regardless of the name."""

	global _current_fake_input
	fake = FakeMidiIn(callback=callback)
	_current_fake_input = fake
	return fake


@pytest.fixture(autouse = True)
def fake_midi_backend (monkeypatch: pytest.MonkeyPatch) -> None:

	"""Give EVERY test the fake MIDI backend, whether it asks for one or not.

	This is autouse deliberately.  The rig plays out of this working tree, so a
	test that reaches a real port sends notes into the synths in the room —
	and the fixture used to be opt-in, which made isolation a property of what
	the tests currently happen to do rather than of the suite.  One test
	written without it was all it took, and nothing said so until something
	made a noise.

	It runs before any non-autouse fixture at the same scope, so
	:func:`patch_midi_multi` still layers its own named ports on top.
	"""

	monkeypatch.setattr(mido, "get_output_names", _fake_get_output_names)
	monkeypatch.setattr(mido, "open_output", _fake_open_output)
	monkeypatch.setattr(mido, "get_input_names", _fake_get_input_names)
	monkeypatch.setattr(mido, "open_input", _fake_open_input)


@pytest.fixture
def patch_midi (fake_midi_backend: None) -> None:

	"""Kept for the hundreds of tests that name it, and for what naming it says.

	The backend is faked for every test now, so this asks for nothing extra —
	but a test that names it is saying "I touch MIDI", which is worth reading
	in a signature.
	"""

	return None


# ---------------------------------------------------------------------------
# Multi-device helpers
# ---------------------------------------------------------------------------

class NamedSpyMidiOut(SpyMidiOut):

	"""SpyMidiOut with a human-readable name for multi-device tests."""

	def __init__ (self, name: str = "unnamed") -> None:
		super().__init__()
		self.name = name


def _make_multi_output_patcher (device_names: typing.List[str]) -> typing.Callable:

	"""Return an open_output stub that creates a NamedSpyMidiOut per device name."""

	ports: typing.Dict[str, NamedSpyMidiOut] = {n: NamedSpyMidiOut(n) for n in device_names}

	def _open (name: str) -> NamedSpyMidiOut:
		if name not in ports:
			ports[name] = NamedSpyMidiOut(name)
		return ports[name]

	_open._ports = ports  # type: ignore[attr-defined]
	return _open


@pytest.fixture
def patch_midi_multi (monkeypatch: pytest.MonkeyPatch) -> typing.Dict[str, NamedSpyMidiOut]:

	"""Patch mido for multi-device tests.

	Returns a dict mapping device names to their NamedSpyMidiOut instances.
	Registers three outputs: 'Primary MIDI', 'Secondary MIDI', and 'Third MIDI'.
	"""

	device_names = ["Primary MIDI", "Secondary MIDI", "Third MIDI"]

	opener = _make_multi_output_patcher(device_names)

	monkeypatch.setattr(mido, "get_output_names", lambda: device_names)
	monkeypatch.setattr(mido, "open_output", opener)
	monkeypatch.setattr(mido, "get_input_names", lambda: ["Input A", "Input B"])
	monkeypatch.setattr(mido, "open_input", _fake_open_input)

	return opener._ports  # type: ignore[attr-defined]
