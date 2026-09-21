"""A harmony() arriving mid-playback starts where the music is (#3083).

M3 of the 2026-09-19 review: "First harmony() mid-playback.  The walker is
anchored at beat 0, so it replays every past boundary at one chord per pulse,
and a bound progression enters partway through its loop.  Binding
[Am, F, C, G, Em] during bar 2 makes bar 3 play C."

The clock walked its first boundary at beat 0 unconditionally and was then
scheduled from a pulse computed from beat 0 — both in the past when the clock
started mid-playback.  Measured before the fix, exactly as the review said:
binding during bar 2 made bar 3 play **C**, the progression's third chord.
With a live style instead, the engine committed **5 chords across 4 pulses**
at the instant of the call, replaying the four boundaries the music had
already gone by.

It starts at the next BAR LINE now.  Chord changes are bar-aligned everywhere
else in the engine, and a chord appearing mid-bar under a pattern that has
already rendered that bar would clash with it.
"""

import pathlib
import typing

import pytest

import subsequence
import subsequence.harmonic_state


CHORDS = ["Am", "F", "C", "G", "Em"]


def _chord_per_bar (
	comp: "subsequence.Composition",
	bars: int,
	tmp_path: pathlib.Path,
) -> typing.List[typing.Tuple[int, typing.Optional[str]]]:

	"""Render; report (bar, chord) as each bar's pattern cycle was built."""

	seen: typing.List[typing.Tuple[int, typing.Optional[str]]] = []

	@comp.pattern(channel = 1, bars = 1)
	def melody (p: typing.Any) -> None:
		chord = None if p.harmony is None or p.harmony.chord is None else p.harmony.chord.name()
		seen.append((p.bar, chord))
		p.note(pitch = 60, beat = 0, velocity = 100, duration = 1)

	comp.render(bars = bars, filename = str(tmp_path / "h.mid"))

	return seen


def test_a_progression_bound_mid_playback_enters_at_its_first_chord (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""The review's own case: bar 3 played C, the third chord, not Am."""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 11)
	bound_at: typing.Dict[str, int] = {}

	def watch () -> None:
		beat = comp._sequencer.pulse_count / comp._sequencer.pulses_per_beat
		bar = int(beat // comp.bar_beats) + 1

		if bar == 2 and not bound_at:
			comp.harmony(progression = subsequence.progression(CHORDS))
			bound_at["bar"] = bar

	comp.schedule(watch, cycle_beats = int(comp.bar_beats))

	seen = _chord_per_bar(comp, 8, tmp_path)

	assert bound_at, "the progression was never bound — the test proves nothing"

	# p.bar is 0-based; the bind happened during 1-based bar 2.
	after = [(bar, chord) for bar, chord in seen if chord is not None]

	assert after, f"nothing sounded after the bind: {seen}"

	first_bar, first_chord = after[0]

	assert first_chord == CHORDS[0], (
		f"the progression entered on {first_chord}, its chord number "
		f"{CHORDS.index(first_chord) + 1 if first_chord in CHORDS else '?'}, "
		f"instead of {CHORDS[0]}.  The whole reading was {seen}"
	)


def test_the_bound_progression_then_walks_in_order (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""Entering at the top is not enough — it must go on in order from there.

	Anchoring correctly and then walking from the wrong offset would satisfy
	a test that only looked at the first chord.
	"""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 11)
	bound_at: typing.Dict[str, int] = {}

	def watch () -> None:
		beat = comp._sequencer.pulse_count / comp._sequencer.pulses_per_beat
		bar = int(beat // comp.bar_beats) + 1

		if bar == 2 and not bound_at:
			comp.harmony(progression = subsequence.progression(CHORDS))
			bound_at["bar"] = bar

	comp.schedule(watch, cycle_beats = int(comp.bar_beats))

	seen = _chord_per_bar(comp, 9, tmp_path)
	sounded = [chord for _bar, chord in seen if chord is not None]

	assert len(sounded) >= 5, f"too little played to check the walk: {seen}"

	expected = [CHORDS[i % len(CHORDS)] for i in range(len(sounded))]

	assert sounded == expected, (
		f"the progression did not walk in order from its top: {sounded} "
		f"against {expected}"
	)


def test_a_live_engine_arriving_mid_playback_does_not_replay_the_past (
	patch_midi: None, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:

	"""One chord per boundary, not one per pulse.

	`hs.history` is capped at 4 (harmonic_state.py), so its LENGTH is a
	saturated proxy and cannot size a replay — it reported "2 replayed" where
	counting the engine's actual commits showed 4.  Count the commits.
	"""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 11)

	commits: typing.List[float] = []
	real_commit = subsequence.harmonic_state.HarmonicState.commit_chord

	def recording (self: typing.Any, chord: typing.Any, *a: typing.Any, **k: typing.Any) -> typing.Any:
		commits.append(comp._sequencer.pulse_count / comp._sequencer.pulses_per_beat)
		return real_commit(self, chord, *a, **k)

	monkeypatch.setattr(subsequence.harmonic_state.HarmonicState, "commit_chord", recording)

	started: typing.Dict[str, float] = {}

	def watch () -> None:
		beat = comp._sequencer.pulse_count / comp._sequencer.pulses_per_beat
		bar = int(beat // comp.bar_beats) + 1

		if bar == 5 and not started:
			comp.harmony(style = "functional_major")
			started["beat"] = beat

	comp.schedule(watch, cycle_beats = int(comp.bar_beats))

	_chord_per_bar(comp, 8, tmp_path)

	assert started, "harmony() was never called — the test proves nothing"
	assert commits, "the engine never committed a chord — the test proves nothing"

	call_beat = started["beat"]
	bar_beats = float(comp.bar_beats)

	# Everything committed inside the bar the call landed in.  One is right —
	# the clock walks its first boundary synchronously.  Five is the fault.
	burst = [beat for beat in commits if call_beat <= beat < call_beat + bar_beats]

	assert len(burst) <= 1, (
		f"{len(burst)} chords were committed inside one bar "
		f"({burst}) — the walker replayed boundaries the music had passed"
	)


def test_a_harmony_at_play_time_still_starts_at_beat_zero (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""The guard: the ordinary path must be untouched.

	_run() registers the clock before playback, where the playhead is 0, so
	the start beat computes to 0 and nothing changes.
	"""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 11)
	comp.harmony(progression = subsequence.progression(CHORDS))

	seen = _chord_per_bar(comp, 5, tmp_path)

	sounded = [chord for _bar, chord in seen]

	assert sounded[:5] == CHORDS, (
		f"a harmony configured before play() did not start at its first chord "
		f"on bar 1: {sounded}"
	)


def test_a_mid_playback_harmony_waits_for_the_bar_line (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""A chord must not appear mid-bar, under a pattern that already rendered it."""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 11)
	bound_at: typing.Dict[str, float] = {}

	def watch () -> None:
		# Fire on the half-bar, so a clock that started "now" would put a
		# chord boundary in the middle of a bar.
		beat = comp._sequencer.pulse_count / comp._sequencer.pulses_per_beat

		if 5.0 <= beat < 7.0 and not bound_at:
			comp.harmony(progression = subsequence.progression(CHORDS))
			bound_at["beat"] = beat

	comp.schedule(watch, cycle_beats = 1)

	comp.render(bars = 6, filename = str(tmp_path / "h.mid"))

	assert bound_at, "the progression was never bound — the test proves nothing"

	boundaries = [start for start, _end, _chord in comp._harmony_horizon._spans]

	assert boundaries, "no spans were committed"

	off_grid = [start for start in boundaries if abs(start % comp.bar_beats) > 1e-6]

	assert not off_grid, (
		f"chord boundaries landed off the bar grid at {off_grid} "
		f"(bound at beat {bound_at['beat']})"
	)


def test_the_walker_is_not_scheduled_into_the_past (
	patch_midi: None
) -> None:
	"""The first scheduled pulse must be ahead of the playhead, not behind it.

	Walking the first boundary at the right beat already stops the *burst*:
	next_change is correct, so a callback firing from a past pulse finds no
	boundary due and commits nothing.  What a past start pulse still costs is
	one wasted fire per boundary the music has already gone by — a hundred
	bars in, a hundred of them, on the event loop between pulses.  That is a
	real cost rather than a rarer fault, so it is fixed and pinned here.
	"""

	import unittest.mock

	import subsequence.composition

	captured: typing.Dict[str, typing.Any] = {}

	mock_seq = unittest.mock.MagicMock()
	mock_seq.pulses_per_beat = 24

	async def capture (callback: typing.Any, start_pulse: int = 0, reschedule_lookahead: float = 1) -> None:
		captured["start_pulse"] = start_pulse

	mock_seq.schedule_callback_sequence = capture

	horizon = subsequence.composition._HarmonyHorizon()

	import asyncio

	# The music is 20 beats in (bar 6 of 4/4) when the harmony arrives.
	playhead_beat = 20.0

	asyncio.run(subsequence.composition.schedule_harmonic_clock(
		sequencer = mock_seq,
		horizon = horizon,
		bar_beats = 4.0,
		cycle_beats = 4.0,
		get_harmonic_state = lambda: None,
		get_bound_progression = lambda: subsequence.progression(CHORDS),
		start_beat = playhead_beat,
	))

	assert "start_pulse" in captured, "the clock never scheduled itself"

	scheduled_beat = captured["start_pulse"] / 24

	assert scheduled_beat > playhead_beat, (
		f"the walker was scheduled at beat {scheduled_beat}, behind the "
		f"playhead at {playhead_beat} — it will fire once for every boundary "
		f"the music has already passed"
	)
