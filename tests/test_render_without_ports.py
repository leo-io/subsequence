"""A render writes its file with no MIDI port at all, and a Composition runs once (#2994).

``stop()`` returned early whenever the sequencer was not running *and* no
output port was registered — which is the ordinary end of a render on a CI
runner, in a container, under cron or over SSH. The recording was never saved,
the stop event never fired, inputs stayed open and Link was never left, and
``render()`` returned as if all was well.

The second half is decision 5 of #2991: a Composition is a take. The first run
closes its ports and empties its pending patterns, so a second one used to do
nothing at all — and with the stop guard fixed it would have written the first
take's notes again, since ``recorded_events`` is never cleared.
"""

import pathlib
import typing

import mido
import pytest

import subsequence
import subsequence.sequencer


@pytest.fixture
def no_midi_ports (monkeypatch: pytest.MonkeyPatch) -> None:

	"""A machine with no MIDI at all — a CI runner, a container, a cron job."""

	def _refuse (*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
		raise OSError("no MIDI ports here")

	monkeypatch.setattr(mido, "get_output_names", lambda: [])
	monkeypatch.setattr(mido, "get_input_names", lambda: [])
	monkeypatch.setattr(mido, "open_output", _refuse)
	monkeypatch.setattr(mido, "open_input", _refuse)


def _piece () -> subsequence.Composition:

	"""A one-part composition that plays a note every bar."""

	composition = subsequence.Composition(bpm = 960)

	@composition.pattern(channel = 1, beats = 4)
	def part (p) -> None:
		p.note(60, beat = 0, duration = 1)

	return composition


def _note_ons (filename: str) -> typing.List[int]:

	"""Every note_on pitch in a written file."""

	return [
		message.note
		for track in mido.MidiFile(filename).tracks
		for message in track
		if not isinstance(message, mido.MetaMessage) and message.type == "note_on" and message.velocity > 0
	]


# ---------------------------------------------------------------------------
# A render with no port
# ---------------------------------------------------------------------------

def test_a_render_with_no_midi_output_still_writes_its_file (tmp_path: pathlib.Path, no_midi_ports: None) -> None:

	"""The CI case: no ports exist, and the file is the whole point of rendering."""

	filename = str(tmp_path / "headless.mid")

	_piece().render(bars = 2, filename = filename)

	assert pathlib.Path(filename).exists()
	assert _note_ons(filename) == [60, 60]


def test_the_stop_event_fires_with_no_port_open (tmp_path: pathlib.Path, no_midi_ports: None) -> None:

	"""Everything hanging off `stop` — saving, closing, leaving Link — is skipped with it."""

	stopped: typing.List[str] = []

	composition = _piece()
	composition._sequencer.events.on("stop", lambda *args: stopped.append("stop"))
	composition.render(bars = 1, filename = str(tmp_path / "event.mid"))

	assert stopped == ["stop"]


@pytest.mark.asyncio
async def test_stop_is_idempotent (patch_midi: None) -> None:

	"""It is the flag that makes it safe to call twice, not the empty registry."""

	sequencer = subsequence.sequencer.Sequencer(output_device_name = "Dummy MIDI", initial_bpm = 120)

	await sequencer.stop()
	await sequencer.stop()

	assert sequencer._stopped is True


@pytest.mark.asyncio
async def test_starting_again_arms_the_stop (patch_midi: None) -> None:

	"""A sequencer started after a stop must be stoppable again."""

	sequencer = subsequence.sequencer.Sequencer(output_device_name = "Dummy MIDI", initial_bpm = 120)

	await sequencer.stop()
	assert sequencer._stopped is True

	await sequencer.start()
	assert sequencer._stopped is False

	stopped: typing.List[str] = []
	sequencer.events.on("stop", lambda *args: stopped.append("stop"))

	await sequencer.stop()

	assert stopped == ["stop"]


# ---------------------------------------------------------------------------
# One take per Composition
# ---------------------------------------------------------------------------

def test_a_second_render_says_a_composition_runs_once (tmp_path: pathlib.Path, no_midi_ports: None) -> None:

	"""It used to write nothing and return as if it had."""

	composition = _piece()
	composition.render(bars = 1, filename = str(tmp_path / "first.mid"))

	with pytest.raises(RuntimeError, match = "runs once"):
		composition.render(bars = 1, filename = str(tmp_path / "second.mid"))

	assert not (tmp_path / "second.mid").exists()


def test_a_second_play_says_the_same (tmp_path: pathlib.Path, no_midi_ports: None) -> None:

	"""play() and render() share the one entry point, so they share the rule."""

	composition = _piece()
	composition.render(bars = 1, filename = str(tmp_path / "first.mid"))

	with pytest.raises(RuntimeError, match = "runs once"):
		composition.play()


def test_a_fresh_composition_per_take_still_works (tmp_path: pathlib.Path, no_midi_ports: None) -> None:

	"""The documented way round it: build one per take."""

	for take in (1, 2):
		filename = str(tmp_path / f"take_{take}.mid")
		_piece().render(bars = 1, filename = filename)

		assert pathlib.Path(filename).exists(), f"take {take} wrote no file"
		assert _note_ons(filename) == [60]
