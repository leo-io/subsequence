"""A cadence approach belongs to the section it was walked in (#3085).

M3 of the 2026-09-19 review: "Interrupted cadences.  A cadence approach
interrupted by form_jump isn't discarded; its stale Bdim-C-Am-F-G replays in
the next live section."

`request_cadence` plans the remaining chord changes up to a bar as one
constrained walk, then commits them a boundary at a time.  That plan starts
from the chord sounding when it was drawn and counts boundaries to a bar — a
section change invalidates both, and a `form_jump` is exactly that.  The
section-entry block reset everything else about the walk and left the approach
queue alone, so the plan kept committing into a section it was never drawn for.

Measured before the fix, with a `form_jump` at bar 4 of an approach requested
at bar 2 for bar 8: the plan `G, C, F, G, Am, G, C` committed **verbatim**,
five of its seven chords landing in the chorus.

Where the arrival is still ahead, the *request* goes back rather than being
dropped — the musician asked for a cadence at a bar, not for those chords.
"""

import random
import typing
import unittest.mock

import pytest

import subsequence
import subsequence.cadences
import subsequence.chords
import subsequence.composition
import subsequence.harmonic_state
import subsequence.progressions
import subsequence.sequence_utils


BAR_BEATS = 4.0
PULSES_PER_BEAT = 24


class _Sections:

	"""A get_section_progression callable whose current section can be moved."""

	def __init__ (self, name: str = "verse", index: int = 0, bars: int = 8) -> None:
		self.name = name
		self.index = index
		self.bars = bars

	def enter (self, name: str, index: int) -> None:
		self.name = name
		self.index = index

	def __call__ (self) -> typing.Tuple[str, int, int, typing.Optional[typing.Any]]:
		return (self.name, self.index, self.bars, None)


async def _clock (**kwargs: typing.Any) -> typing.Tuple[
	typing.Callable[[int], typing.Optional[float]],
	"subsequence.composition._HarmonyHorizon",
]:

	"""Schedule the harmonic clock against a mock sequencer; return (callback, horizon)."""

	captured: typing.Dict[str, typing.Any] = {}

	mock_seq = unittest.mock.MagicMock()
	mock_seq.pulses_per_beat = PULSES_PER_BEAT

	async def capture (callback: typing.Callable, start_pulse: int = 0, reschedule_lookahead: float = 1) -> None:
		captured["callback"] = callback

	mock_seq.schedule_callback_sequence = capture

	horizon = subsequence.composition._HarmonyHorizon()

	await subsequence.composition.schedule_harmonic_clock(
		sequencer = mock_seq,
		horizon = horizon,
		bar_beats = BAR_BEATS,
		**kwargs,
	)

	return captured["callback"], horizon


def _major_resolver (key_pc: int = 0) -> typing.Callable[[str], typing.List["subsequence.chords.Chord"]]:

	def resolve (name: str) -> typing.List["subsequence.chords.Chord"]:
		spec = subsequence.cadences.cadence_formula(name)
		return [
			subsequence.progressions.resolve_constraint(element, key_pc, "ionian", "cadence")
			for element in spec.formula
		]

	return resolve


@pytest.fixture
def recorded_walk (monkeypatch: pytest.MonkeyPatch) -> typing.List[typing.List[str]]:

	"""Every constrained_walk the clock plans, as chord names."""

	plans: typing.List[typing.List[str]] = []
	real = subsequence.sequence_utils.constrained_walk

	def recording (*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
		result = real(*args, **kwargs)
		plans.append([chord.name() for chord in result])
		return result

	monkeypatch.setattr(subsequence.sequence_utils, "constrained_walk", recording)

	return plans


# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_section_change_discards_the_planned_approach (
	patch_midi: None, recorded_walk: typing.List[typing.List[str]]
) -> None:

	"""The plan must not keep committing once the music has left its section."""

	hs = subsequence.harmonic_state.HarmonicState(
		key_name = "C", graph_style = "functional_major", rng = random.Random(7)
	)
	sections = _Sections()
	requests = {8: "strong"}

	cb, horizon = await _clock(
		get_harmonic_state = lambda: hs,
		get_section_progression = sections,
		cycle_beats = BAR_BEATS,
		cadence_requests = requests,
		resolve_cadence = _major_resolver(0),
	)

	committed: typing.List[typing.Tuple[float, str, str]] = []

	for bar in range(1, 9):
		beat = (bar - 1) * BAR_BEATS

		if bar == 3:
			sections.enter("chorus", 1)		# the form_jump

		cb(int(beat * PULSES_PER_BEAT))

		chord = horizon.chord_at(beat)
		committed.append((beat, sections.name, "-" if chord is None else chord.name()))

	assert recorded_walk, "no approach was ever planned — the test proves nothing"

	plan = recorded_walk[0][1:]			# position 1 is the chord already sounding
	assert plan, "the planned approach was empty"

	sections_seen = {section for _b, section, _c in committed}
	assert "chorus" in sections_seen, "the section never changed — the test proves nothing"

	# Asking whether the WHOLE plan appears inside the chorus is the wrong
	# question: the first chords of it commit before the jump, legitimately, so
	# only a suffix is ever in the chorus and the check passes on a broken tree.
	# The decisive comparison is the committed run against the plan IN ORDER,
	# from the bar the plan was drawn.  Unfixed, they are identical.
	first_plan_bar = 2					# the plan is drawn at bar 2's boundary
	sounded = [chord for _b, _s, chord in committed[first_plan_bar - 1:]]
	against = plan[:len(sounded)]

	assert sounded != against, (
		f"the approach committed verbatim across the section change: planned "
		f"{against}, sounded {sounded}"
	)

	# And say where it diverged, so a regression is legible rather than a bare
	# inequality.
	divergence = next(
		(i for i, (a, b) in enumerate(zip(sounded, against)) if a != b),
		None,
	)
	jump_index = next(
		i for i, (_b, section, _c) in enumerate(committed[first_plan_bar - 1:])
		if section == "chorus"
	)

	assert divergence is not None and divergence <= jump_index, (
		f"the approach carried on past the section change: it first differed at "
		f"index {divergence}, the jump was at index {jump_index}"
	)


@pytest.mark.asyncio
async def test_an_arrival_still_ahead_is_re_planned_not_dropped (
	patch_midi: None, recorded_walk: typing.List[typing.List[str]]
) -> None:

	"""A request the musician made for a later bar survives the section change."""

	hs = subsequence.harmonic_state.HarmonicState(
		key_name = "C", graph_style = "functional_major", rng = random.Random(7)
	)
	sections = _Sections()
	requests = {8: "strong"}

	cb, horizon = await _clock(
		get_harmonic_state = lambda: hs,
		get_section_progression = sections,
		cycle_beats = BAR_BEATS,
		cadence_requests = requests,
		resolve_cadence = _major_resolver(0),
	)

	# Bars 1 and 2 plan the approach; bar 3 changes section while it is mid-flight.
	cb(0)
	cb(int(1 * BAR_BEATS * PULSES_PER_BEAT))

	assert recorded_walk, "no approach was planned before the section change"
	assert 8 not in requests, "the request should have been consumed by the plan"

	planned_before = len(recorded_walk)

	sections.enter("chorus", 1)
	cb(int(2 * BAR_BEATS * PULSES_PER_BEAT))

	# The request is handed back and RE-PLANNED inside the same callback — the
	# section-entry block puts it in the dict, and the live branch below
	# consumes it again a few lines later.  So the evidence is a second walk,
	# not a request left sitting in the dict; looking for the latter reads a
	# moment that never exists.
	assert len(recorded_walk) > planned_before, (
		"the request for bar 8 was dropped by the section change instead of "
		"being re-planned from where the harmony now stands"
	)
	assert recorded_walk[-1] != recorded_walk[0], (
		"the 're-plan' returned the identical walk, so nothing was re-drawn"
	)


@pytest.mark.asyncio
async def test_an_arrival_already_passed_is_not_resurrected (
	patch_midi: None, recorded_walk: typing.List[typing.List[str]],
	caplog: pytest.LogCaptureFixture,
) -> None:

	"""Handing the request back must not raise the dead.

	Checking the requests dict cannot see this: the expiry pass runs a few
	lines after the hand-back, inside the same callback, so a resurrected
	request is gone again by the time the callback returns either way.  What a
	resurrection actually produces is a WARNING about a request expiring
	unserved — for a request that was served, long ago.  That is the fault, so
	that is what this asserts.
	"""

	hs = subsequence.harmonic_state.HarmonicState(
		key_name = "C", graph_style = "functional_major", rng = random.Random(7)
	)
	sections = _Sections()
	requests = {3: "strong"}

	cb, horizon = await _clock(
		get_harmonic_state = lambda: hs,
		get_section_progression = sections,
		cycle_beats = BAR_BEATS,
		cadence_requests = requests,
		resolve_cadence = _major_resolver(0),
	)

	cb(0)
	cb(int(1 * BAR_BEATS * PULSES_PER_BEAT))

	assert recorded_walk, "no approach was planned — the test proves nothing"

	# Well past bar 3 now, and the section changes.
	sections.enter("chorus", 1)

	with caplog.at_level("WARNING", logger = "subsequence.composition"):
		cb(int(5 * BAR_BEATS * PULSES_PER_BEAT))

	expired = [
		record.getMessage() for record in caplog.records
		if "expired unserved" in record.getMessage()
	]

	assert not expired, (
		f"a request whose bar had already passed was handed back and then "
		f"warned about: {expired}"
	)
	assert 3 not in requests


@pytest.mark.asyncio
async def test_an_uninterrupted_approach_still_arrives (
	patch_midi: None, recorded_walk: typing.List[typing.List[str]]
) -> None:

	"""The guard: discarding on a section change must not break the ordinary case."""

	hs = subsequence.harmonic_state.HarmonicState(
		key_name = "C", graph_style = "functional_major", rng = random.Random(7)
	)
	sections = _Sections()
	requests = {4: "strong"}

	cb, horizon = await _clock(
		get_harmonic_state = lambda: hs,
		get_section_progression = sections,
		cycle_beats = BAR_BEATS,
		cadence_requests = requests,
		resolve_cadence = _major_resolver(0),
	)

	for bar in range(1, 5):
		cb(int((bar - 1) * BAR_BEATS * PULSES_PER_BEAT))

	# "strong" is V -> I: in C, the arrival at bar 4 is C.
	arrival = horizon.chord_at(3 * BAR_BEATS)

	assert arrival is not None, "nothing sounds at the arrival bar"
	assert arrival.name() == "C", f"the cadence arrived on {arrival.name()}, not C"


@pytest.mark.asyncio
async def test_a_section_change_with_no_approach_in_flight_changes_nothing (
	patch_midi: None
) -> None:

	"""No queue, nothing to discard, and no request invented."""

	hs = subsequence.harmonic_state.HarmonicState(
		key_name = "C", graph_style = "functional_major", rng = random.Random(7)
	)
	sections = _Sections()
	requests: typing.Dict[int, str] = {}

	cb, horizon = await _clock(
		get_harmonic_state = lambda: hs,
		get_section_progression = sections,
		cycle_beats = BAR_BEATS,
		cadence_requests = requests,
		resolve_cadence = _major_resolver(0),
	)

	cb(0)
	sections.enter("chorus", 1)
	cb(int(1 * BAR_BEATS * PULSES_PER_BEAT))

	assert requests == {}, "a section change invented a cadence request"
	assert horizon.chord_at(BAR_BEATS) is not None, "the clock stopped sounding chords"
