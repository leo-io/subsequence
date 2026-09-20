"""A section with no chords holds the last one; the clock does not give up (#2998).

With `section_chords()` on some sections and no `harmony()`, `advance()` returned
None at the first section it had no source for.  The sequencer drops a callback
sequence that returns None, so the harmonic clock was gone for the rest of the
performance — `verse:C verse:F bridge:F bridge:F verse:F verse:F…`, with every
later verse losing its chords, and the log blaming "live graph mode".
`_harmonic_clock_started` stayed True, so a `harmony()` arriving later could not
start a replacement.

Decision 2 of #2991: hold the last chord, keep the window, and say at startup
which sections have none of their own.
"""

import asyncio
import logging
import typing
import unittest.mock

import pytest

import subsequence
import subsequence.chords
import subsequence.composition
import subsequence.progressions


Section = typing.Tuple[str, int, int, typing.Optional["subsequence.progressions.Progression"]]


async def _clock (
	sections: typing.Sequence[Section],
	playhead: typing.Dict[str, int],
	**kwargs: typing.Any,
) -> typing.Tuple[typing.Optional[typing.Callable[[int], typing.Optional[float]]], "subsequence.composition._HarmonyHorizon"]:

	"""The real clock over a form the caller steps through bar by bar."""

	captured: typing.Dict[str, typing.Any] = {}

	mock_seq = unittest.mock.MagicMock()
	mock_seq.pulses_per_beat = 24

	async def capture (callback: typing.Callable, start_pulse: int = 0, reschedule_lookahead: float = 1) -> None:
		captured["callback"] = callback

	mock_seq.schedule_callback_sequence = capture

	horizon = subsequence.composition._HarmonyHorizon()

	kwargs.setdefault("get_harmonic_state", lambda: None)

	await subsequence.composition.schedule_harmonic_clock(
		sequencer = mock_seq,
		horizon = horizon,
		bar_beats = 4.0,
		cycle_beats = 4,
		get_section_progression = lambda: sections[min(playhead["bar"], len(sections) - 1)],
		**kwargs,
	)

	return captured.get("callback"), horizon


def _verse_bridge_verse () -> typing.List[Section]:

	"""Two bars of a verse with chords, two of a bridge without, then the verse again."""

	verse = subsequence.progressions.progression(["C", "F"], beats = 4.0)

	return [("verse", 0, 2, verse)] * 2 + [("bridge", 1, 2, None)] * 2 + [("verse", 2, 2, verse)] * 2


async def _walk_bars (bars: int, sections: typing.Sequence[Section], **kwargs: typing.Any) -> typing.List[str]:

	"""Play *bars* bars of the form and report the chord heard in each."""

	playhead = {"bar": 0}
	callback, horizon = await _clock(sections, playhead, **kwargs)

	assert callback is not None, "the clock never registered at all"

	heard = [horizon.chord_at(0.0).name()]

	for bar in range(1, bars):
		playhead["bar"] = bar

		assert callback(bar * 4 * 24) is not None, f"the clock gave up at bar {bar + 1}"

		heard.append(horizon.chord_at(bar * 4.0).name())

	return heard


# ---------------------------------------------------------------------------
# The verse/bridge form
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_bridge_holds_and_the_verse_gets_its_chords_back (patch_midi: None) -> None:

	"""The reported sound was `C F F F F F`; it should be `C F F F C F`."""

	heard = await _walk_bars(6, _verse_bridge_verse())

	assert heard == ["C", "F", "F", "F", "C", "F"], heard


@pytest.mark.asyncio
async def test_an_unbound_section_holds_rather_than_falling_silent (patch_midi: None) -> None:

	"""Each held bar is *realised*, not projected.

	`span_at` falls back to the section's own future projection past the last
	realised span, so a bar can look covered while the clock that should have
	committed it is dead — which is exactly how `bridge:F bridge:F` read as
	working.  The window is kept only if the span is really there.
	"""

	playhead = {"bar": 0}
	callback, horizon = await _clock(_verse_bridge_verse(), playhead)

	for bar in range(1, 4):
		playhead["bar"] = bar
		callback(bar * 4 * 24)

	realised = [(start, end) for start, end, _ in horizon._spans]

	for beat in (8.0, 12.0):
		assert any(start - 1e-9 <= beat < end - 1e-9 for start, end in realised), \
			f"beat {beat} was never committed, only projected: {realised}"


@pytest.mark.asyncio
async def test_the_clock_keeps_going_for_a_long_unbound_stretch (patch_midi: None) -> None:

	"""One held bar was never the problem — the clock being dropped was."""

	verse = subsequence.progressions.progression(["C", "F"], beats = 4.0)
	sections: typing.List[Section] = [("verse", 0, 2, verse)] * 2 + [("solo", 1, 16, None)] * 16

	heard = await _walk_bars(18, sections)

	assert heard[2:] == ["F"] * 16, heard


@pytest.mark.asyncio
async def test_the_hold_is_said_once_not_every_bar (patch_midi: None) -> None:

	"""A line a bar for a sixteen-bar solo is noise."""

	verse = subsequence.progressions.progression(["C", "F"], beats = 4.0)
	sections: typing.List[Section] = [("verse", 0, 2, verse)] * 2 + [("solo", 1, 8, None)] * 8

	with unittest.mock.patch.object(subsequence.composition.logger, "info") as logged:
		await _walk_bars(10, sections)

	held = [call for call in logged.call_args_list if "holding" in str(call).lower()]

	assert len(held) == 1, f"said {len(held)} times"


@pytest.mark.asyncio
async def test_a_form_with_no_chords_at_all_still_stops (patch_midi: None) -> None:

	"""Nothing has ever sounded, so there is no chord to hold and no clock to keep."""

	sections: typing.List[Section] = [("intro", 0, 4, None)] * 4

	playhead = {"bar": 0}
	callback, horizon = await _clock(sections, playhead)

	assert callback is None, "a clock with nothing to play registered anyway"


# ---------------------------------------------------------------------------
# A later harmony()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_clock_that_stops_frees_its_slot (patch_midi: None) -> None:

	"""The flag stayed True after the sequence was dropped, so nothing could replace it."""

	stopped: typing.List[bool] = []

	sections: typing.List[Section] = [("intro", 0, 4, None)] * 4

	await _clock(sections, {"bar": 0}, on_stop = lambda: stopped.append(True))

	assert stopped == [True]


@pytest.mark.asyncio
async def test_a_composition_whose_clock_stopped_can_start_another (patch_midi: None) -> None:

	"""`harmony()` arriving mid-piece found `_harmonic_clock_started` still True."""

	composition = subsequence.Composition(bpm = 120, key = "C", output_device = "Dummy MIDI")

	composition._harmonic_clock_started = True
	composition._harmonic_clock_stopped()

	assert composition._harmonic_clock_started is False


@pytest.mark.asyncio
async def test_the_engine_is_used_as_soon_as_it_arrives (patch_midi: None) -> None:

	"""A held section starts walking the moment a live engine exists."""

	verse = subsequence.progressions.progression(["C", "F"], beats = 4.0)
	sections: typing.List[Section] = [("verse", 0, 2, verse)] * 2 + [("solo", 1, 6, None)] * 6

	engine: typing.List[typing.Optional[subsequence.harmonic_state.HarmonicState]] = [None]

	playhead = {"bar": 0}
	callback, horizon = await _clock(sections, playhead, get_harmonic_state = lambda: engine[0])

	for bar in (1, 2, 3):
		playhead["bar"] = bar

		assert callback(bar * 4 * 24) is not None, \
			f"the clock gave up at bar {bar + 1}, before the engine could arrive"

	held = horizon.chord_at(12.0).name()

	arrived = subsequence.harmonic_state.HarmonicState(key_name = "C", graph_style = "functional_major")
	arrived.rng.seed(1)
	arrived.current_chord = subsequence.chords.parse_chord(held)
	engine[0] = arrived

	walked = []

	for bar in (4, 5, 6, 7):
		playhead["bar"] = bar
		assert callback(bar * 4 * 24) is not None
		walked.append(horizon.chord_at(bar * 4.0).name())

	assert len(set(walked)) > 1, f"the clock kept holding after an engine arrived: {walked}"


# ---------------------------------------------------------------------------
# Saying so at startup
# ---------------------------------------------------------------------------

def _with_form (sections: typing.Sequence[typing.Tuple[str, int]], bound: typing.Sequence[str]) -> subsequence.Composition:

	"""A composition with a form, some sections given chords and no harmony()."""

	composition = subsequence.Composition(bpm = 120, key = "C", output_device = "Dummy MIDI")
	composition.form(list(sections), loop = True)

	for name in bound:
		composition.section_chords(name, ["C", "F"])

	return composition


def test_the_sections_with_no_chords_are_named (patch_midi: None, caplog: pytest.LogCaptureFixture) -> None:

	"""Holding is a reasonable sound and almost never the intended one."""

	composition = _with_form([("verse", 2), ("bridge", 2), ("outro", 2)], ["verse"])

	with caplog.at_level(logging.WARNING):
		composition._warn_about_sections_with_no_chords()

	assert "bridge" in caplog.text
	assert "outro" in caplog.text
	assert "verse" not in caplog.text


def test_nothing_is_said_when_every_section_has_chords (patch_midi: None, caplog: pytest.LogCaptureFixture) -> None:

	"""A complete piece must start quietly."""

	composition = _with_form([("verse", 2), ("bridge", 2)], ["verse", "bridge"])

	with caplog.at_level(logging.WARNING):
		composition._warn_about_sections_with_no_chords()

	assert caplog.text == ""


def test_nothing_is_said_when_harmony_can_fill_the_gaps (patch_midi: None, caplog: pytest.LogCaptureFixture) -> None:

	"""With a live engine an unbound section generates, which is the documented behaviour."""

	composition = _with_form([("verse", 2), ("bridge", 2)], ["verse"])
	composition.harmony("functional_major")

	with caplog.at_level(logging.WARNING):
		composition._warn_about_sections_with_no_chords()

	assert caplog.text == ""


def test_a_form_that_names_its_sections_lazily_is_not_guessed_at (patch_midi: None, caplog: pytest.LogCaptureFixture) -> None:

	"""A generator form has no section list to check against, so it must not invent one."""

	composition = subsequence.Composition(bpm = 120, key = "C", output_device = "Dummy MIDI")

	def endless () -> typing.Iterator[typing.Tuple[str, int]]:
		while True:
			yield ("verse", 2)
			yield ("bridge", 2)

	composition.form(endless())
	composition.section_chords("verse", ["C", "F"])

	with caplog.at_level(logging.WARNING):
		composition._warn_about_sections_with_no_chords()

	assert caplog.text == ""


# ---------------------------------------------------------------------------
# A pin that cannot resolve
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spec", [9, 8, 15])
def test_a_degree_outside_the_scale_is_refused_where_it_is_written (patch_midi: None, spec: int) -> None:

	"""It used to raise out of the clock mid-performance and take the whole clock with it."""

	composition = subsequence.Composition(bpm = 120, key = "C", output_device = "Dummy MIDI")

	with pytest.raises(ValueError, match = "does not name a chord"):
		composition.pin_chord(3, spec)

	assert 3 not in composition._pinned_chords


@pytest.mark.parametrize("spec", [1, 3, "V", "bVII7", "Am"])
def test_a_pin_that_does_resolve_is_still_accepted (patch_midi: None, spec: typing.Any) -> None:

	"""The refusal must not catch anything a musician would reasonably write."""

	composition = subsequence.Composition(bpm = 120, key = "C", output_device = "Dummy MIDI")
	composition.pin_chord(3, spec)

	assert composition._resolve_pin(3) is not None


def test_the_refusal_says_the_bar_the_spec_and_the_key (patch_midi: None) -> None:

	"""A message that names none of them sends the musician hunting."""

	composition = subsequence.Composition(bpm = 120, key = "F", output_device = "Dummy MIDI")

	with pytest.raises(ValueError) as raised:
		composition.pin_chord(7, 9)

	message = str(raised.value)

	assert "7" in message
	assert "9" in message
	assert "F" in message


def test_a_pin_that_stops_resolving_later_does_not_kill_the_clock (patch_midi: None, caplog: pytest.LogCaptureFixture) -> None:

	"""A section can re-key under a pin that was fine when it was written."""

	composition = subsequence.Composition(bpm = 120, key = "C", output_device = "Dummy MIDI")
	composition.pin_chord(3, 7)

	# Re-key the pin's world to a scale with fewer degrees than it needs.
	composition._pinned_chords[3] = subsequence.progressions.parse_element(11, beats = 4.0)

	with caplog.at_level(logging.WARNING):
		resolved = composition._resolve_pin(3)

	assert resolved is None, "an unresolvable pin must be skipped, not raised"
	assert "ignoring the pin" in caplog.text
