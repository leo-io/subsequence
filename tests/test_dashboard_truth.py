"""What the dashboard and the status line say, and what they can install on (#3051).

Three things from M22 of the 2026-09-19 review.

**The websockets floor.** `web_ui.py` is imported on every `import
subsequence`, and it uses `websockets.asyncio.server` and top-level
`websockets.broadcast`. Measured by installing each version: 12.0 has no
`websockets.asyncio` at all, and on 13.x `websockets.broadcast` is still the
**legacy** one, which cannot broadcast to the `ServerConnection` objects the
new server yields. 14.0 is the first that works.

**The dashboard's chord.** It read `harmonic_state.current_chord`, which flips
`lookahead` beats early and is absent entirely under a bound progression.
Sampled every beat of an 8-bar render: 8 of 32 beats disagreed with
`current_chord()` under a graph style, and **32 of 32** under a bound
progression, where the dashboard showed no chord at all while the terminal
showed C, Am, F, G.

**The status line.** Nothing limited it to the terminal's width. A piece with
a key, a form, a chord and three conductor signals gave **132 characters in an
80-column terminal** — and the redraw assumes one line, so every refresh left
a stale copy and the display walked down the screen.
"""

import pathlib
import re
import shutil
import typing

import pytest

import subsequence
import subsequence.display
import subsequence.web_ui


REPO_ROOT = pathlib.Path(subsequence.__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# The floor it can actually install on
# ---------------------------------------------------------------------------

def test_the_websockets_floor_admits_only_versions_that_work () -> None:

	"""12.x cannot import web_ui; 13.x broadcasts through the legacy function."""

	pyproject = (REPO_ROOT / "pyproject.toml").read_text()
	pinned = re.search(r'"websockets>=([0-9.]+)"', pyproject)

	assert pinned is not None, "websockets is no longer pinned in pyproject.toml"

	major = int(pinned.group(1).split(".")[0])

	assert major >= 14, (
		f"the floor is websockets {pinned.group(1)}: 12 has no websockets.asyncio, "
		f"and 13 still has the legacy websockets.broadcast"
	)


def test_the_installed_websockets_has_what_the_dashboard_uses () -> None:

	"""The floor is a claim about an API; check the API rather than the number.

	`websockets.broadcast` has to BE the asyncio one — on 13.x it exists and
	is the legacy function, which is the whole reason the floor is 14.
	"""

	import websockets
	import websockets.asyncio.server

	assert hasattr(websockets.asyncio.server, "serve")
	assert hasattr(websockets.asyncio.server, "ServerConnection")

	assert getattr(websockets.broadcast, "__module__", "") == "websockets.asyncio.server", \
		f"websockets.broadcast comes from {websockets.broadcast.__module__}"


# ---------------------------------------------------------------------------
# The chord it shows
# ---------------------------------------------------------------------------

def _piece (bound: bool) -> subsequence.Composition:

	composition = subsequence.Composition(bpm = 480, key = "C", scale = "major", seed = 5)

	if bound:
		composition.harmony(progression = subsequence.progression([1, 6, 4, 5]), cycle_beats = 4)
	else:
		composition.harmony(style = "pop_major", cycle_beats = 4)

	@composition.pattern(channel = 1, beats = 4)
	def pad (p: typing.Any) -> None:
		p.note(beat = 0, pitch = 60, velocity = 90)

	return composition


@pytest.mark.parametrize("bound", [False, True])
def test_the_dashboard_shows_the_chord_that_is_sounding (
	bound: bool,
	tmp_path: pathlib.Path,
	patch_midi: None,
) -> None:

	"""Sampled every beat of a render, the dashboard must agree with the terminal."""

	composition = _piece(bound)
	web = subsequence.web_ui.WebUI(composition)

	disagreements: typing.List[typing.Tuple[typing.Any, typing.Any]] = []
	sampled = []

	def look (beat: int) -> None:
		shown = web._get_state(composition).get("chord")
		sounding = composition.current_chord()
		expected = sounding.name() if sounding is not None else None

		sampled.append(shown)

		if shown != expected:
			disagreements.append((shown, expected))

	composition.on_event("beat", look)
	composition.render(bars = 8, filename = str(tmp_path / "out.mid"))

	assert sampled, "the probe sampled nothing at all"
	assert any(value is not None for value in sampled), \
		"the dashboard never showed a chord — this would pass with harmony switched off"
	assert not disagreements, f"{len(disagreements)} of {len(sampled)} beats disagreed: {disagreements[:4]}"


def test_a_piece_with_no_harmony_still_reports_no_chord (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""The control: "always agrees" must not be achieved by always saying None."""

	composition = subsequence.Composition(bpm = 480, seed = 5)

	@composition.pattern(channel = 1, beats = 4)
	def pad (p: typing.Any) -> None:
		p.note(beat = 0, pitch = 60, velocity = 90)

	web = subsequence.web_ui.WebUI(composition)

	assert web._get_state(composition).get("chord") is None


# ---------------------------------------------------------------------------
# The width it fits in
# ---------------------------------------------------------------------------

def _status_line (
	monkeypatch: pytest.MonkeyPatch,
	columns: int,
	section_name: str = "intro",
	signals: int = 3,
) -> str:

	monkeypatch.setattr(
		shutil, "get_terminal_size",
		lambda fallback = (80, 24): shutil.os.terminal_size((columns, 24)),
	)

	composition = subsequence.Composition(bpm = 128, key = "Bb", scale = "mixolydian", seed = 5)
	composition.harmony(style = "pop_major", cycle_beats = 4)
	composition.form([(section_name, 4), ("verse", 8)])

	@composition.pattern(channel = 1, beats = 4)
	def pad (p: typing.Any) -> None:
		p.note(beat = 0, pitch = 60, velocity = 90)

	for name in ("brightness", "density", "energy")[:signals]:
		composition.conductor.lfo(name, cycle_beats = 16)

	composition._open_output_devices()
	composition.display()

	display = composition._display
	assert display is not None

	return display._format_status()


@pytest.mark.parametrize("columns", [40, 60, 80, 100, 200])
def test_the_status_line_fits_the_terminal (
	columns: int,
	monkeypatch: pytest.MonkeyPatch,
	patch_midi: None,
) -> None:

	"""The finding: 132 characters in 80 columns, wrapping on every redraw."""

	line = _status_line(monkeypatch, columns)

	assert len(line) <= columns, f"{len(line)} characters in {columns} columns: {line!r}"


def test_a_narrow_terminal_keeps_the_tempo_and_the_bar (
	monkeypatch: pytest.MonkeyPatch,
	patch_midi: None,
) -> None:

	"""Fitting is easy if you return nothing; it has to keep what matters."""

	line = _status_line(monkeypatch, 40)

	assert "BPM" in line, line
	assert line.strip(), "the status line came back empty"


@pytest.mark.parametrize("columns", [1, 4, 8])
def test_a_terminal_narrower_than_one_part_still_says_something (
	columns: int,
	monkeypatch: pytest.MonkeyPatch,
	patch_midi: None,
) -> None:

	"""The last part is never dropped, however narrow it gets.

	Dropping while anything is left empties the line entirely at a width
	below the first part — and an empty status line reads as a crashed
	display rather than a narrow one.
	"""

	line = _status_line(monkeypatch, columns)

	assert line, f"a {columns}-column terminal produced nothing at all"
	assert len(line) <= columns


def test_a_signal_is_dropped_before_the_chord_is_cut (
	monkeypatch: pytest.MonkeyPatch,
	patch_midi: None,
) -> None:

	"""Whole parts go from the right, so a narrow line loses a signal, not half a chord.

	Truncating the joined string instead cut "Chord: A#" in half while keeping
	three signals that had pushed it off the end.
	"""

	line = _status_line(monkeypatch, 80)

	assert "Chord:" in line, f"the chord was dropped before the signals: {line!r}"
	assert line.count(": 0.") < 3, f"all three signals survived an 80-column line: {line!r}"

	# And no truncation mark: whole parts were available to drop, so cutting
	# the text was never necessary. Without this the test passes when the
	# joined string is simply sliced — the chord survives at character 51 and
	# only one signal is left visible, which satisfies both lines above.
	assert "…" not in line, f"the line was cut mid-part instead of dropping one: {line!r}"


def test_a_wide_terminal_keeps_everything (
	monkeypatch: pytest.MonkeyPatch,
	patch_midi: None,
) -> None:

	"""The control. Nothing is dropped when there is room for it."""

	line = _status_line(monkeypatch, 200)

	assert "BPM" in line
	assert "Chord:" in line
	assert line.count(": 0.") == 3, f"a 200-column line lost a signal: {line!r}"
	assert "…" not in line


def test_nothing_is_cut_when_it_already_fits (
	monkeypatch: pytest.MonkeyPatch,
	patch_midi: None,
) -> None:

	"""The documented example is 54 characters and must come through whole."""

	line = _status_line(monkeypatch, 120, signals = 0)

	assert "…" not in line, line
	assert "Chord:" in line
