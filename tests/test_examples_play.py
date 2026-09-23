"""Every example runs the way a musician runs it, and plays (#3041).

Nothing ran ``examples/``, so an example could go on advertising an API that had moved: the Direct
Pattern API was broken for two days while ``demo_advanced.py`` showed it off (#2959), and
``frozen.py`` passed ``harmony()`` the retired ``gravity=`` for three days, until this test.

Each runs as ``__main__``, as ``python examples/<name>.py`` runs it, with the one call that never
returns replaced: ``play()`` renders four bars, and the Direct Pattern API's ``run_until_stopped()``
runs its sequencer in render mode.  A pattern that raises is logged rather than raised, and iss.py
keeps going when a fetch fails, so any warning fails an example too, logged or raised - every
example runs clean today, and a warning is how the next rename will show.  Nothing reaches a device (the fake backend, and a render opens
nothing), the network (a socket refuses to connect; ``iss.py`` gets a stand-in for ``requests``) or
a Link session (``link()`` is replaced, and recorded).
"""

import logging
import pathlib
import socket
import sys
import types
import typing
import warnings

import mido
import pytest

import subsequence
import subsequence.composition


EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / "examples"

BARS = 4

# Loaded by another example, which needs to be running for it to mean anything.
_LOADED_BY = {"live_patterns.py": "live_init.py"}


def _names () -> typing.List[str]:

	names = sorted(path.name for path in EXAMPLES.glob("*.py") if path.name not in _LOADED_BY)

	assert len(names) >= 12, f"only {len(names)} examples found"

	return names


class _Telemetry:

	"""What api.wheretheiss.at answers, fixed: iss.py's stand-in for a fetch."""

	def json (self) -> typing.Dict[str, typing.Any]:

		return {
			"latitude": 30.0, "longitude": -60.0, "altitude": 420.0, "velocity": 27600.0,
			"visibility": "daylight", "footprint": 4500.0, "solar_lat": 10.0, "solar_lon": 45.0,
			"daynum": 2461000.5,
		}


def _play (name: str, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> typing.Dict[str, typing.Any]:

	"""Run one example as __main__; what it played, and what it asked for on the way."""

	played: typing.Dict[str, typing.Any] = {"files": [], "linked": 0}

	def refuse (*args: typing.Any, **kwargs: typing.Any) -> None:
		raise OSError("the examples' smoke test does not reach the network")

	def render_instead_of_playing (self: subsequence.Composition) -> None:
		filename = str(tmp_path / f"{name}.mid")
		self.render(bars=BARS, filename=filename)
		played["files"].append(filename)

	running = subsequence.composition.run_until_stopped

	async def render_instead_of_running (sequencer: typing.Any) -> None:

		# A Composition's render comes through here too, already rendering.
		if sequencer.render_mode:
			await running(sequencer)
			return

		filename = str(tmp_path / f"{name}.mid")
		sequencer.recording = True
		sequencer.record_filename = filename
		sequencer.render_mode = True
		sequencer.render_bars = BARS
		await sequencer.start()
		await sequencer.task
		await sequencer.stop()
		played["files"].append(filename)

	def link_nowhere (self: subsequence.Composition, *args: typing.Any, **kwargs: typing.Any) -> None:
		played["linked"] += 1

	requests = types.ModuleType("requests")
	requests.get = lambda url, **kwargs: _Telemetry()		# type: ignore[attr-defined]

	monkeypatch.setattr(socket.socket, "connect", refuse)
	monkeypatch.setattr(socket, "create_connection", refuse)
	monkeypatch.setattr(subsequence.Composition, "play", render_instead_of_playing)
	monkeypatch.setattr(subsequence.composition, "run_until_stopped", render_instead_of_running)
	monkeypatch.setattr(subsequence.Composition, "link", link_nowhere)
	monkeypatch.setitem(sys.modules, "requests", requests)
	monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: None)

	path = EXAMPLES / name
	namespace: typing.Dict[str, typing.Any] = {"__name__": "__main__", "__file__": str(path)}
	exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)		# noqa: S102

	played["notes"] = [
		message.note
		for filename in played["files"]
		for track in mido.MidiFile(filename).tracks
		for message in track
		if message.type == "note_on" and message.velocity > 0
	]

	return played


@pytest.mark.parametrize("name", _names())
def test_an_example_plays (name: str, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:

	with caplog.at_level(logging.WARNING), warnings.catch_warnings(record=True) as raised:
		warnings.simplefilter("always")
		played = _play(name, tmp_path, monkeypatch)

	logged = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]

	assert len(played["files"]) == 1, "the example never reached play() - did its __main__ block run?"
	assert played["notes"], "it played nothing"
	assert logged == []
	assert [str(warning.message) for warning in raised] == []


def test_the_example_that_links_asks_to_and_joins_nothing (tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:

	"""link_sync.py calls link() once, and the replacement took it: no session was joined.

	If it stopped calling link(), the replacement would be hiding nothing, and should go.
	"""

	assert _play("link_sync.py", tmp_path, monkeypatch)["linked"] == 1


def test_the_live_file_is_played_through_the_example_that_loads_it (tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:

	"""live_patterns.py is not run alone: live_init.py loads it, and its patterns are what live_init.py plays."""

	assert "live_patterns.py" in (EXAMPLES / "live_init.py").read_text(encoding="utf-8")

	played = _play("live_init.py", tmp_path, monkeypatch)

	assert played["notes"]
