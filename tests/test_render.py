"""Tests for composition.render() — limits, safety cap, and validation."""

import pathlib
import typing
import unittest.mock

import mido
import pytest

import subsequence
import subsequence.sequencer


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------

def test_render_raises_when_both_limits_are_none (patch_midi: None) -> None:

	"""render(bars=None, max_minutes=None) must raise ValueError immediately."""

	composition = subsequence.Composition(bpm=120)

	@composition.pattern(channel=1, beats=4)
	def p (p) -> None:
		pass

	with pytest.raises(ValueError, match="at least one limit"):
		composition.render(bars=None, max_minutes=None)


def test_render_accepts_bars_only (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""render(bars=N, max_minutes=None) completes without error and stops at bar N."""

	filename = str(tmp_path / "out.mid")
	composition = subsequence.Composition(bpm=480)

	@composition.pattern(channel=1, beats=4)
	def p (p) -> None:
		pass

	# Should complete without raising — output file may be empty (no recorded notes
	# with patch_midi) but no exception means the bar limit worked correctly.
	composition.render(bars=4, max_minutes=None, filename=filename)
	assert composition._sequencer.current_bar >= 4


def test_render_accepts_max_minutes_only (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""render(bars=None, max_minutes=M) completes without error and stops at the time cap."""

	filename = str(tmp_path / "out.mid")
	composition = subsequence.Composition(bpm=120)

	@composition.pattern(channel=1, beats=4)
	def p (p) -> None:
		pass

	# A tiny cap (0.001 min = 0.06 s of MIDI) stops quickly without error.
	composition.render(bars=None, max_minutes=0.001, filename=filename)
	# The render stopped, so elapsed time should be very small
	assert composition._sequencer._render_elapsed_seconds <= 0.1


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------

def _limits_render_would_set (
	composition: subsequence.Composition,
	tmp_path: pathlib.Path,
	**kwargs: typing.Any,
) -> typing.Tuple[typing.Optional[float], int]:

	"""What render() hands the sequencer, without running the render.

	Both of these tests used to `mock.patch("asyncio.run")` and then call
	render() for real.  render() does not call asyncio.run — sequencer.run
	uses asyncio.Runner — so the mock was inert, each test ran a full
	sixty-minute simulated render (0.87 s and 0.85 s of a 15 s suite), and
	each wrote a `dummy.mid` into the WORKING DIRECTORY.  That file is
	gitignored, which is why it went unnoticed; it is also a plain truncating
	write into the current directory, which is the hazard that wedged the
	share on 2026-09-19 (#2438).

	Stopping the run at the point the limits are set measures the thing these
	tests are named for, and touches no disk at all.
	"""

	stopped_here: typing.List[typing.Tuple[typing.Optional[float], int]] = []

	def capture (main: typing.Any) -> None:
		stopped_here.append(
			(composition._sequencer.render_max_seconds, composition._sequencer.render_bars)
		)
		main.close()

	with unittest.mock.patch.object(subsequence.sequencer, "run", capture):
		composition.render(filename=str(tmp_path / "unwritten.mid"), **kwargs)

	assert stopped_here, "render() no longer goes through sequencer.run — this test is measuring nothing"

	return stopped_here[0]


def test_render_default_max_minutes_is_60 (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""The sequencer receives render_max_seconds = 3600 when max_minutes is unset."""

	composition = subsequence.Composition(bpm=120)

	@composition.pattern(channel=1, beats=4)
	def p (p) -> None:
		pass

	max_seconds, _ = _limits_render_would_set(composition, tmp_path)

	assert max_seconds == pytest.approx(3600.0)


def test_render_default_bars_is_none (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""render() with no arguments sets render_bars = 0 (unlimited) on the sequencer."""

	composition = subsequence.Composition(bpm=120)

	@composition.pattern(channel=1, beats=4)
	def p (p) -> None:
		pass

	_, bars = _limits_render_would_set(composition, tmp_path)

	assert bars == 0


def test_a_render_writes_nothing_outside_the_file_it_was_given (
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
	patch_midi: None,
) -> None:

	"""No stray file in the working directory, whatever the working directory is.

	The two tests above wrote `dummy.mid` into wherever pytest was started —
	the repo root in practice, and the share if anybody ran the suite there.
	"""

	monkeypatch.chdir(tmp_path)

	workspace = tmp_path / "cwd"
	workspace.mkdir()
	monkeypatch.chdir(workspace)

	composition = subsequence.Composition(bpm=480)

	@composition.pattern(channel=1, beats=4)
	def p (p) -> None:
		p.note(beat=0, pitch=36, velocity=100)

	target = tmp_path / "wanted.mid"
	composition.render(bars=2, filename=str(target))

	assert target.exists()
	assert list(workspace.iterdir()) == [], \
		f"a render left files behind: {[f.name for f in workspace.iterdir()]}"


# ---------------------------------------------------------------------------
# Recorded output
# ---------------------------------------------------------------------------

def test_render_writes_pattern_notes (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""A note placed by a pattern ends up in the rendered MIDI file as a note_on."""

	filename = str(tmp_path / "notes.mid")
	composition = subsequence.Composition(bpm=480)

	@composition.pattern(channel=1, beats=4)
	def p (p) -> None:
		p.note(60, beat=0)

	composition.render(bars=1, filename=filename)

	mid = mido.MidiFile(filename)
	note_ons = [
		msg for track in mid.tracks for msg in track
		if not isinstance(msg, mido.MetaMessage) and msg.type == "note_on" and msg.velocity > 0
	]

	assert any(msg.note == 60 for msg in note_ons)


def test_render_does_not_leak_the_next_bar_downbeat (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""render(bars=N) stops exactly at the limit — bar N's downbeat is not rendered.

	Regression: the bar limit tripped inside _check_bar_change but the loop still
	dispatched that pulse, so the first beat of the next (unrendered) bar leaked
	into the file.
	"""

	filename = str(tmp_path / "limit.mid")
	composition = subsequence.Composition(bpm=480)

	@composition.pattern(channel=1, beats=4)
	def p (p) -> None:
		p.note(60, beat=0)			# a note on every bar's downbeat

	composition.render(bars=2, filename=filename)

	mid = mido.MidiFile(filename)
	note_ons = [
		msg for track in mid.tracks for msg in track
		if not isinstance(msg, mido.MetaMessage) and msg.type == "note_on" and msg.velocity > 0
	]

	assert len(note_ons) == 2		# bars 0 and 1 only — no third note at bar 2's downbeat


# ---------------------------------------------------------------------------
# Time cap stops render
# ---------------------------------------------------------------------------

def test_render_stops_at_time_cap (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""A very small max_minutes cap stops the render before reaching many bars."""

	filename = str(tmp_path / "short.mid")
	# At 120 BPM, 1 bar = 2 seconds. A 0.01-minute (0.6 s) cap should stop
	# the render well before bar 100.
	composition = subsequence.Composition(bpm=120)

	@composition.pattern(channel=1, beats=4)
	def p (p) -> None:
		pass

	composition.render(bars=100, max_minutes=0.01, filename=filename)

	# The sequencer should have stopped early (elapsed < 100 bars).
	assert composition._sequencer.current_bar < 100
