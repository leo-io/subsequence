"""A chord the style never goes to sounds, and the piece carries on (#2992).

`WeightedGraph.choose_next` returns its source unchanged when that source has
no outgoing edges, and the harmonic clock commits chords the graph has never
heard of: pins, the spans of bound and section progressions, cadences landed by
fiat.  So the walk repeated the foreign chord for ever — `pin_chord(8, "E7")`,
the docstring's own example, played `Dm E7 E7 E7 …` to the end of the song.

Decision 1 of #2991: same root, else home.  The next step is chosen as if the
chord were the graph chord on the same root — E7 continues like Em, Fm like F.
With no chord on that root anywhere in the style, the next chord is the tonic.
The foreign chord still sounds where it was placed.
"""

import collections
import typing
import unittest.mock

import pytest

import subsequence
import subsequence.chords
import subsequence.composition
import subsequence.harmonic_state


def _engine (key: str = "C", style: str = "functional_major", seed: int = 7) -> subsequence.harmonic_state.HarmonicState:

	"""A real engine — these faults all hid behind a stubbed one."""

	state = subsequence.harmonic_state.HarmonicState(key_name = key, graph_style = style)
	state.rng.seed(seed)

	return state


def _walk (state: subsequence.harmonic_state.HarmonicState, foreign: str, steps: int = 6) -> typing.List[str]:

	"""Land *foreign* on the engine and walk on from it."""

	state.commit_chord(subsequence.chords.parse_chord(foreign))

	return [state.step().name() for _ in range(steps)]


def _next_chords (foreign: str, key: str = "C", style: str = "functional_major", seeds: int = 120) -> collections.Counter:

	"""What follows *foreign*, counted over many seeds."""

	counted: collections.Counter = collections.Counter()

	for seed in range(seeds):
		state = _engine(key, style, seed)
		state.commit_chord(subsequence.chords.parse_chord(foreign))
		counted[state.step().name()] += 1

	return counted


# ---------------------------------------------------------------------------
# The freeze itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key, style, foreign", [
	("C", "functional_major", "E7"),		# pin_chord's own docstring example
	("C", "functional_major", "A#7"),		# the bVII7 bridge
	("C", "functional_major", "Fm"),		# a borrowed minor subdominant
	("C", "dorian_minor", "G"),				# where section_cadence("verse","open") lands
	("C", "mixolydian", "G"),
	("C", "phrygian_minor", "G"),
])
def test_a_chord_the_style_never_reaches_does_not_stop_the_piece (key: str, style: str, foreign: str) -> None:

	"""It sounded once and then played for ever, because a node with no edges walks to itself."""

	state = _engine(key, style)

	assert not state.graph.get_transitions(subsequence.chords.parse_chord(foreign)), \
		f"{foreign} has edges in {style} — this case does not exercise the fault"

	walked = _walk(state, foreign)

	assert walked[0] != foreign, f"the harmony stayed on {foreign}"
	assert len(set(walked)) > 1, f"the harmony froze: {' '.join(walked)}"


# ---------------------------------------------------------------------------
# Same root
# ---------------------------------------------------------------------------

def test_a_pinned_e7_continues_the_way_em_would () -> None:

	"""E7 is not in C major's graph; Em is, on the same root, and Em goes to Am or F."""

	after_e7 = set(_next_chords("E7"))
	after_em = set(_next_chords("Em"))

	assert after_e7 == after_em, f"E7 went to {sorted(after_e7)}, Em to {sorted(after_em)}"
	assert "Am" in after_e7


def test_a_borrowed_fm_continues_the_way_f_would () -> None:

	"""Fm is borrowed from the parallel minor; the style walks on as if it were F."""

	assert set(_next_chords("Fm")) == set(_next_chords("F"))


@pytest.mark.parametrize("foreign, plain", [("E7", "Em"), ("Fm", "F"), ("Cm", "C"), ("Dsus4", "Dm"), ("Gm", "G")])
def test_a_stand_in_is_chosen_by_root_alone (foreign: str, plain: str) -> None:

	"""Decision 1 says same root; the quality of the foreign chord does not narrow it."""

	state = _engine()
	foreign_chord = subsequence.chords.parse_chord(foreign)

	assert not state.graph.get_transitions(foreign_chord), \
		f"{foreign} is in the graph — this case does not reach the stand-in"

	assert set(_next_chords(foreign)) == set(_next_chords(plain)), \
		f"{foreign} did not continue the way {plain} does"


# ---------------------------------------------------------------------------
# Else home
# ---------------------------------------------------------------------------

def test_the_bridge_chord_goes_home () -> None:

	"""`harmony(progression=[1, 6, 3, "bVII7"])` gave `C Am Em A#7 A#7 A#7 …`."""

	state = _engine()

	assert not any(
		node.root_pc == subsequence.chords.parse_chord("A#7").root_pc
		for node in state.graph.nodes()
	), "C major's graph has an A# chord after all — this case does not exercise the fallback"

	assert set(_next_chords("A#7")) == {"C"}


def test_going_home_costs_no_draw () -> None:

	"""There is nothing to choose between, so the play stream must not be disturbed."""

	state = _engine()
	state.commit_chord(subsequence.chords.parse_chord("A#7"))

	before = state.rng.getstate()
	state.step()

	assert state.rng.getstate() == before, "the fallback drew from the play stream"


@pytest.mark.parametrize("key, foreign, home", [
	("C", "A#7", "C"),
	("F", "B7", "F"),
	("A#", "E7", "A#"),
	("G", "C#m", "G"),
])
def test_home_is_the_key_the_engine_was_built_in (key: str, foreign: str, home: str) -> None:

	"""Home is the style's own tonic, not whatever happened to be sounding."""

	state = _engine(key)
	root = subsequence.chords.parse_chord(foreign).root_pc

	assert not any(node.root_pc == root for node in state.graph.nodes()), \
		f"{key} major has a chord on {foreign}'s root — this case does not reach the fallback"

	assert set(_next_chords(foreign, key = key)) == {home}


# ---------------------------------------------------------------------------
# What the foreign chord must NOT lose
# ---------------------------------------------------------------------------

def test_the_foreign_chord_still_sounds_where_it_was_placed () -> None:

	"""Continuing from a stand-in must not silently replace what the musician asked for."""

	state = _engine()
	state.commit_chord(subsequence.chords.parse_chord("E7"))

	assert state.current_chord.name() == "E7"
	assert state.get_current_chord().name() == "E7"


def test_the_foreign_chord_is_what_enters_history () -> None:

	"""The stand-in is a way of walking on, not a rewrite of what was played."""

	state = _engine()
	state.commit_chord(subsequence.chords.parse_chord("E7"))
	state.step()

	assert state.history[-1].name() == "E7"


def test_planning_and_stepping_still_agree_through_a_foreign_chord () -> None:

	"""``commit_chord(plan_next())`` is draw-for-draw ``step()`` — including here."""

	for foreign in ["E7", "A#7", "Fm"]:

		stepped = _engine()
		stepped.commit_chord(subsequence.chords.parse_chord(foreign))

		planned = _engine()
		planned.commit_chord(subsequence.chords.parse_chord(foreign))

		for _ in range(5):
			stepped.step()
			planned.commit_chord(planned.plan_next())

		assert stepped.current_chord == planned.current_chord, foreign
		assert stepped.history == planned.history, foreign


@pytest.mark.parametrize("key, style", [
	("C", "functional_major"),
	("C", "aeolian_minor"),
	("C", "dorian_minor"),
	("C", "mixolydian"),
	("F#", "functional_major"),
])
def test_a_chord_the_style_knows_walks_exactly_as_it_did (key: str, style: str) -> None:

	"""Every node of the graph, not one: G and G7 share a root and do not share targets.

	G may go to G7; G7 may not go to G7.  A same-root search applied to chords
	the style already knows would walk G7 the way G walks, and G7 could then
	follow itself.
	"""

	for node in _engine(key, style).graph.nodes():

		allowed = {target.name() for target, _ in _engine(key, style).graph.get_transitions(node)}

		if not allowed:
			continue

		for seed in range(12):

			state = _engine(key, style, seed)
			state.current_chord = node

			assert state.step().name() in allowed, \
				f"{node.name()} went to {state.current_chord.name()}, which is not one of its own targets"


# ---------------------------------------------------------------------------
# Through the real clock, with a real pin
# ---------------------------------------------------------------------------

async def _capture_clock (**kwargs: typing.Any) -> typing.Tuple[typing.Callable[[int], typing.Optional[float]], "subsequence.composition._HarmonyHorizon"]:

	"""Schedule the real clock against a mock sequencer and hand back its callback."""

	captured: typing.Dict[str, typing.Any] = {}

	mock_seq = unittest.mock.MagicMock()
	mock_seq.pulses_per_beat = 24

	async def capture (callback: typing.Callable, start_pulse: int = 0, reschedule_lookahead: float = 1) -> None:
		captured["callback"] = callback

	mock_seq.schedule_callback_sequence = capture

	horizon = subsequence.composition._HarmonyHorizon()

	await subsequence.composition.schedule_harmonic_clock(
		sequencer = mock_seq,
		horizon = horizon,
		bar_beats = 4.0,
		**kwargs,
	)

	return captured["callback"], horizon


@pytest.mark.asyncio
async def test_the_pin_chord_docstring_example_carries_on (patch_midi: None) -> None:

	"""`pin_chord(8, "E7")` played E7 to the end of the song, in its own example."""

	state = _engine()
	pins = {8: subsequence.chords.parse_chord("E7")}

	callback, horizon = await _capture_clock(
		get_harmonic_state = lambda: state,
		cycle_beats = 4,
		get_pinned = pins.get,
	)

	heard = [horizon.chord_at(0.0).name()]

	for bar in range(1, 14):
		callback(bar * 4 * 24)
		heard.append(horizon.chord_at(bar * 4.0).name())

	assert heard[7] == "E7", f"the pin did not sound at bar 8: {heard}"

	after = heard[8:]

	assert "E7" not in after, f"the harmony froze on the pin: {' '.join(heard)}"
	assert len(set(after)) > 1, f"the harmony froze: {' '.join(heard)}"


@pytest.mark.asyncio
async def test_a_style_switch_drops_the_chord_the_old_style_had_drawn (patch_midi: None) -> None:

	"""The pre-committed chord outlived the engine that drew it, so a new style played it."""

	major = _engine("C", "functional_major", seed = 3)
	whole_tone = _engine("C", "whole_tone", seed = 3)

	whole_tone_chords = {node.name() for node in whole_tone.graph.nodes()}

	engine: typing.List[subsequence.harmonic_state.HarmonicState] = [major]

	callback, horizon = await _capture_clock(
		get_harmonic_state = lambda: engine[0],
		cycle_beats = 4,
	)

	callback(4 * 24)

	# The major engine has now pre-committed the chord for the next boundary.
	pre_committed = horizon._planned

	assert pre_committed is not None, "nothing was pre-committed, so nothing can outlive the switch"
	assert pre_committed[2].name() not in whole_tone_chords, \
		"the two styles overlap here — this case cannot tell the engines apart"

	engine[0] = whole_tone
	callback(8 * 24)

	sounded = horizon.chord_at(8.0)

	assert sounded.name() in whole_tone_chords, \
		f"after the switch the piece played {sounded.name()}, which only the old style knew"
