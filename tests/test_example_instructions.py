"""An example played the way its own instructions say still makes music (#3483).

examples/subharmonicon.py's PHYSICAL CONTROLLER MAPPING block says to map a fader to
VELOCITY_SWELL with cc_map() and comment out the LFO.  The voices read the swell with
p.signal(), a conductor signal, while cc_map() writes p.data, so following the instructions
sent every note at velocity 0: none of the 87 notes in eight bars could be heard.  The voices
now read the swell through a helper that takes the controller's value once it has arrived.

These follow the instructions by editing the example's text, so an edit that moves the lines
the instructions name fails here instead of leaving the test behind.
"""

import logging
import pathlib
import typing

import mido
import pytest


EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "examples" / "subharmonicon.py"

LFO = 'composition.conductor.lfo("VELOCITY_SWELL", shape="sine", cycle_beats=16,\n\tmin_val=55, max_val=105)'

CONTROLLER = [
	'# composition.midi_input("My Controller")',
	'# composition.cc_map(7, "VELOCITY_SWELL", min_val=55, max_val=105)',
]


def _as_shipped () -> str:

	return EXAMPLE.read_text(encoding="utf-8")


def _with_the_controller () -> str:

	"""The example with its controller instructions followed: the fader in, the LFO out."""

	source = _as_shipped()

	assert source.count(LFO) == 1, "the LFO line the instructions name has moved"
	source = source.replace(LFO, "# " + LFO.replace("\n", "\n# "))

	for line in CONTROLLER:
		assert source.count(line) == 1, f"a line the instructions name has moved: {line}"
		source = source.replace(line, line[2:])

	return source


def _velocities (source: str, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, data: typing.Optional[typing.Dict[str, float]] = None) -> typing.List[int]:

	"""Every note-on velocity in eight rendered bars of *source*."""

	# The example configures logging for a musician's terminal; the suite has its own.
	# The controller the instructions name is not plugged in here, which a render
	# does not need (#3485).
	monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: None)

	namespace: typing.Dict[str, typing.Any] = {"__name__": "example", "__file__": str(EXAMPLE)}
	exec(compile(source, str(EXAMPLE), "exec"), namespace)
	composition = namespace["composition"]

	if data is not None:
		composition.data.update(data)

	filename = tmp_path / "subharmonicon.mid"
	composition.render(bars=8, filename=str(filename))

	velocities = [message.velocity for track in mido.MidiFile(str(filename)).tracks for message in track if message.type == "note_on"]
	assert velocities, "the render held no notes at all"

	return velocities


def test_following_the_controller_instructions_leaves_every_note_audible (tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:

	"""Before the fader first moves, the swell sits at 80, where every note was sent at 0."""

	assert set(_velocities(_with_the_controller(), tmp_path, monkeypatch)) == {80}


def test_the_fader_sets_the_swell_once_it_has_moved (tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:

	"""What cc_map() wrote into composition.data is what the voices play."""

	velocities = _velocities(_with_the_controller(), tmp_path, monkeypatch, data={"VELOCITY_SWELL": 100.4})

	assert set(velocities) == {100}


def test_as_shipped_the_lfo_still_swells (tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:

	"""A guard: with no controller the LFO plays the swell, 55 to 105.  This passed before #3483 as well."""

	assert set(_velocities(_as_shipped(), tmp_path, monkeypatch)) == {55, 80, 105}
