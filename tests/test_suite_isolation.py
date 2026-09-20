"""No test reaches a real MIDI port, whether it remembers to ask or not (#3039).

The rig plays out of this working tree, so a test that opens a real port sends
notes into the synths in the room. The fake backend used to be an opt-in
fixture, which made that safety a property of what the tests currently happen
to do rather than of the suite: one test written without `patch_midi` was all
it took, and nothing said so until something made a noise.

Measured before changing it, with a session-wide recorder in front of the real
mido: **zero** of the 4151 tests reached it — #2995 (a port opens at `play()`,
not at construction) and #2997 (a device that fails to open keeps a
placeholder) had already removed the exposure the review found. That is the
reason to make the guard structural rather than to leave it: the suite was
safe by coincidence.

None of the tests in this file name `patch_midi`. That is the point.
"""

import typing

import mido
import pytest

import subsequence
import conftest


def test_a_test_that_asks_for_nothing_still_gets_the_fake_backend () -> None:

	"""The guard itself. No fixture is named here on purpose."""

	assert mido.get_output_names() == ["Dummy MIDI"], \
		f"a test naming no fixture saw {mido.get_output_names()} — the real backend"

	port = mido.open_output("anything at all")

	assert isinstance(port, conftest.FakeMidiOut), \
		f"opening a port gave {type(port).__name__}, not a fake"

	port.close()


def test_the_input_side_is_faked_too () -> None:

	"""A clock_follow input is a real device on this machine as well."""

	assert mido.get_input_names() == ["Dummy MIDI"]

	port = mido.open_input("anything at all")

	assert isinstance(port, conftest.FakeMidiIn)

	port.close()


def test_a_composition_that_plays_reaches_no_real_port () -> None:

	"""End to end, with nothing asked for: the ports a piece opens are fakes."""

	composition = subsequence.Composition(bpm = 480, output_device = "Dummy MIDI")

	@composition.pattern(channel = 1, beats = 4)
	def drums (p: typing.Any) -> None:
		p.note(beat = 0, pitch = 36, velocity = 100)

	composition._open_output_devices()

	opened = list(composition._sequencer._output_devices)

	assert opened, "the probe opened nothing, so it proves nothing"

	for device in opened:
		assert isinstance(device, conftest.FakeMidiOut), \
			f"a device came back as {type(device).__name__}"


def test_the_multi_device_fixture_still_wins (
	patch_midi_multi: typing.Dict[str, conftest.NamedSpyMidiOut],
) -> None:

	"""The autouse guard runs first, so a fixture that wants its own ports gets them.

	If the ordering ever inverted, every multi-device test would quietly see
	one port called "Dummy MIDI" and assert things about the wrong rig.
	"""

	assert mido.get_output_names() == ["Primary MIDI", "Secondary MIDI", "Third MIDI"]

	port = mido.open_output("Primary MIDI")

	assert isinstance(port, conftest.NamedSpyMidiOut)
	assert port.name == "Primary MIDI"


def test_patch_midi_still_works_for_the_tests_that_name_it (patch_midi: None) -> None:

	"""Hundreds of signatures name it; it must keep meaning what it meant."""

	assert mido.get_output_names() == ["Dummy MIDI"]
	assert isinstance(mido.open_output("x"), conftest.FakeMidiOut)


def test_the_fake_backend_fixture_is_autouse () -> None:

	"""Said directly, so removing `autouse=True` fails here and not only by luck.

	The behavioural tests above would keep passing on any run where every test
	in the session happened to name patch_midi, which is how this was missed
	before.
	"""

	fixture = conftest.fake_midi_backend

	# pytest 8 wraps a fixture in a FixtureFunctionDefinition carrying
	# `_fixture_function_marker`; older versions hang `_pytestfixturefunction`
	# on the function itself. Read whichever is there, and fail if neither is,
	# rather than silently finding no marker and concluding nothing.
	marker = getattr(fixture, "_fixture_function_marker", None) \
		or getattr(fixture, "_pytestfixturefunction", None)

	assert marker is not None, \
		f"fake_midi_backend carries no fixture marker pytest recognises: {type(fixture)}"
	assert marker.autouse is True, "the fake MIDI backend is opt-in again"
