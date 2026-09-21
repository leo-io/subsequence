"""A re-call of `harmony()` changes only what it names, and `None` unbinds (#3088).

M3 of the 2026-09-19 review: "Calling it with some parameters keeps the style
but resets cycle_beats, gravity, lookahead and the rest to their defaults.
After harmony(style="aeolian_minor", cycle_beats=8, gravity=0.4), a later
re-call gave cycle_beats None, gravity 1.0.  There is also no way to unbind a
bound progression."

Measured before the fix, with `harmony(key_pull=0.4)` following a full call:
`cycle_beats` 8 → None, `reschedule_lookahead` 4 → 1, `nir_strength` 0.9 → 0.5
and `root_diversity` 1.0 → 0.4, all silently.  The style already survived —
`_last_harmony_style` had been given exactly this treatment, and its comment
makes exactly this argument — so the fix is that reasoning carried through to
the rest.

`gravity` is retired; `key_pull` replaces it and runs the other way round, so
the engine's `key_gravity_blend` is `1 - key_pull`.
"""

import pathlib
import typing

import pytest

import subsequence
import subsequence.composition
import subsequence.harmonic_state


FULL_CALL = dict(
	style = "aeolian_minor",
	cycle_beats = 8,
	key_pull = 0.6,
	nir_strength = 0.9,
	root_diversity = 1.0,
	minor_turnaround_weight = 0.3,
	dominant_7th = False,
	reschedule_lookahead = 4,
)


def _configured (comp: "subsequence.Composition") -> typing.Dict[str, typing.Any]:

	"""Everything harmony() configures, read where the engine will use it."""

	hs = comp._harmonic_state
	assert hs is not None, "the probe needs a configured engine"

	return {
		"style": comp._harmony_style,
		"cycle_beats": comp._harmony_cycle_beats,
		"lookahead": comp._harmony_reschedule_lookahead,
		"key_gravity_blend": hs.key_gravity_blend,
		"nir_strength": hs.nir_strength,
		"root_diversity": hs.root_diversity,
		"minor_turnaround_weight": hs.minor_turnaround_weight,
	}


@pytest.fixture
def configured () -> "subsequence.Composition":
	comp = subsequence.Composition(key = "C", bpm = 120)
	comp.harmony(**FULL_CALL)
	return comp


# ---------------------------------------------------------------------------
# What a re-call keeps
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("setting, expected", [
	("cycle_beats", 8),
	("lookahead", 4),
	("nir_strength", 0.9),
	("root_diversity", 1.0),
	("minor_turnaround_weight", 0.3),
	("style", "aeolian_minor"),
])
def test_a_re_call_keeps_what_it_did_not_name (
	configured: "subsequence.Composition", setting: str, expected: typing.Any
) -> None:

	"""One named parameter must not reset the others."""

	configured.harmony(key_pull = 0.4)

	assert _configured(configured)[setting] == expected


def test_a_re_call_applies_what_it_does_name (
	configured: "subsequence.Composition"
) -> None:

	"""Keeping the rest must not turn into keeping everything."""

	before = _configured(configured)["key_gravity_blend"]

	configured.harmony(key_pull = 0.4)

	after = _configured(configured)["key_gravity_blend"]

	assert before == pytest.approx(0.4)		# key_pull 0.6
	assert after == pytest.approx(0.6)		# key_pull 0.4
	assert after != before


def test_dominant_7ths_stay_out_across_a_re_call () -> None:

	"""dominant_7th is spent building the graph, so it needs remembering.

	Read through the graph rather than a stored flag: what matters is that no
	V7 is reachable, not that a boolean survived somewhere.
	"""

	comp = subsequence.Composition(key = "C", bpm = 120)
	comp.harmony(style = "functional_major", dominant_7th = False)

	def sevenths (comp: "subsequence.Composition") -> typing.Set[str]:
		graph = comp._harmonic_state.graph
		return {
			chord.name() for chord in graph.nodes()
			if chord.name().endswith("7") and not chord.name().endswith("maj7")
		}

	assert sevenths(comp) == set(), "the first call should have excluded them"

	comp.harmony(key_pull = 0.5)

	assert sevenths(comp) == set(), "a re-call must not let V7 back in"


def test_a_re_call_that_names_a_setting_changes_it_for_the_next_one (
	configured: "subsequence.Composition"
) -> None:

	"""What is kept is the LAST value given, not the first."""

	configured.harmony(cycle_beats = 2)
	configured.harmony(key_pull = 0.1)

	assert _configured(configured)["cycle_beats"] == 2


# ---------------------------------------------------------------------------
# Unbinding
# ---------------------------------------------------------------------------

def test_omitting_progression_leaves_a_binding_alone () -> None:

	"""A parameter-only re-call must not unbind."""

	comp = subsequence.Composition(key = "C", bpm = 120)
	comp.harmony(progression = subsequence.progression(["C", "F"]))

	comp.harmony(key_pull = 0.5)

	assert comp._bound_progression is not None


def test_progression_none_unbinds () -> None:

	"""An explicit None is how a musician gets the live engine back."""

	comp = subsequence.Composition(key = "C", bpm = 120)
	comp.harmony(style = "functional_major", progression = subsequence.progression(["C", "F"]))

	assert comp._bound_progression is not None

	comp.harmony(progression = None)

	assert comp._bound_progression is None


def test_unbinding_leaves_the_rest_of_the_harmony_configured () -> None:

	"""Unbinding is not a reset."""

	comp = subsequence.Composition(key = "C", bpm = 120)
	comp.harmony(**FULL_CALL)
	comp.harmony(progression = subsequence.progression(["C", "F"]))

	comp.harmony(progression = None)

	# Assert the unbinding actually happened, or this test passes on a tree
	# where progression=None does nothing at all — which is how the break
	# harness first found it.
	assert comp._bound_progression is None

	kept = _configured(comp)

	assert kept["style"] == "aeolian_minor"
	assert kept["cycle_beats"] == 8
	assert kept["nir_strength"] == 0.9


# ---------------------------------------------------------------------------
# The clock side: what the unbinding does to the walk
# ---------------------------------------------------------------------------

def _chords_per_bar (comp: "subsequence.Composition", bars: int, tmp_path: pathlib.Path) -> typing.List[str]:

	"""Render and report the chord each bar's pattern cycle was built against."""

	seen: typing.List[str] = []

	@comp.pattern(channel = 1, bars = 1)
	def melody (p: typing.Any) -> None:
		chord = None if p.harmony is None else p.harmony.chord
		seen.append("-" if chord is None else chord.name())
		p.note(pitch = 60, beat = 0, velocity = 100, duration = 1)

	comp.render(bars = bars, filename = str(tmp_path / "r.mid"))

	return seen


def test_re_binding_the_same_progression_after_an_unbind_starts_from_its_top (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""The walk is anchored on IDENTITY, so an unbind has to forget what it saw.

	Without clearing it, re-binding the very same Progression object matches
	the identity the clock still holds, no re-anchor happens, and the walk
	carries on from its old offset instead of its first chord.
	"""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 5)
	shared = subsequence.progression(["C", "F", "G", "Am"])

	comp.harmony(style = "functional_major", progression = shared)

	state: typing.Dict[str, int] = {}

	def switch () -> None:
		beat = comp._sequencer.pulse_count / comp._sequencer.pulses_per_beat
		bar = int(beat // comp.bar_beats) + 2

		if bar == 3 and "off" not in state:
			comp.harmony(progression = None)
			state["off"] = bar
		elif bar == 6 and "on" not in state:
			comp.harmony(progression = shared)
			state["on"] = bar

	comp.schedule(switch, cycle_beats = int(comp.bar_beats))

	seen = _chords_per_bar(comp, 10, tmp_path)

	assert state.get("off") == 3, "the unbind never happened"
	assert state.get("on") == 6, "the re-bind never happened"

	# From the re-bind onward the progression must be heard from its top.
	after = seen[state["on"] - 1:]

	assert after, "nothing played after the re-bind"
	assert after[0] == "C", (
		f"the re-bound progression resumed at {after[0]!r} instead of its first "
		f"chord; the whole reading was {seen}"
	)
