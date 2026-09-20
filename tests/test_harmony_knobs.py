"""Two harmony knobs that did the opposite of what they said (#3043).

**`gravity`** blended functional pull against full diatonic pull, and at its
default of 1.0 the boost was "is this chord diatonic?" — true of every chord
in a single-key style, so every candidate got the same boost and the knob did
nothing where it was left. Lowering it strengthened the pull, while the
docstring said "High values stay closer to the root chord". Measured over 6000
seeds, chords following the tonic in pop_major: G went 0.274 → 0.385 as the
value fell from 1.0 to 0.0.

Decision 10 of #2991 retires it for `key_pull`, which reads the natural way
round — 0.0 is no pull, 1.0 the strongest — with `key_pull = 1 - gravity`.
A rename, not a redefinition (#1460), so `gravity=` raises and its message
carries the conversion.

**`root_diversity=0.0`**, documented as maximum diversity, produced the most
repetition. `0.0 ** n` is exactly zero for any root heard in the last four
chords, so in a style with few roots every candidate was suppressed,
`choose_next` found nothing to choose, and it returned the source — the chord
already sounding. Measured over 40 steps: 29 self-repeats in "suspended", 15
in "phrygian_minor", 10 in "aeolian_minor", 0 at the 0.4 default.
"""

import random
import typing

import pytest

import subsequence
import subsequence.harmonic_state
import subsequence.weighted_graph


STYLES = [
	"functional_major", "aeolian_minor", "lydian_major", "dorian_minor",
	"hooktheory_major", "pop_major", "phrygian_minor", "chromatic_mediant",
	"suspended", "mixolydian", "whole_tone", "diminished",
]


# ---------------------------------------------------------------------------
# gravity is retired
# ---------------------------------------------------------------------------

def test_gravity_is_refused (patch_midi: None) -> None:

	"""A rename is a hard break here — no alias, no quiet acceptance."""

	composition = subsequence.Composition(bpm = 120, key = "C")

	with pytest.raises(TypeError) as refusal:
		composition.harmony(style = "pop_major", gravity = 0.8)		# type: ignore[call-arg]

	assert "gravity" in str(refusal.value)


def test_the_refusal_carries_the_conversion (patch_midi: None) -> None:

	"""A bare TypeError names the parameter; it cannot say the numbers invert.

	That is the whole reason harmony() catches the old spelling instead of
	letting Python refuse it.
	"""

	composition = subsequence.Composition(bpm = 120, key = "C")

	with pytest.raises(TypeError) as refusal:
		composition.harmony(style = "pop_major", gravity = 0.8)		# type: ignore[call-arg]

	message = str(refusal.value)

	assert "key_pull" in message
	assert "1 - gravity" in message


def test_an_ordinary_typo_still_refuses (patch_midi: None) -> None:

	"""Catching retired names must not turn the signature into a free-for-all."""

	composition = subsequence.Composition(bpm = 120, key = "C")

	with pytest.raises(TypeError, match = "unexpected keyword"):
		composition.harmony(style = "pop_major", nir_strngth = 0.5)	# type: ignore[call-arg]


@pytest.mark.parametrize("value", [-0.1, 1.5])
def test_key_pull_outside_zero_to_one_is_refused (value: float, patch_midi: None) -> None:

	"""It is a proportion, and it is new, so it may as well be checked."""

	composition = subsequence.Composition(bpm = 120, key = "C")

	with pytest.raises(ValueError, match = "key_pull"):
		composition.harmony(style = "pop_major", key_pull = value)


def test_key_pull_reaches_the_engine_the_other_way_round (patch_midi: None) -> None:

	"""The engine still blends from the far end: blend = 1 - key_pull."""

	composition = subsequence.Composition(bpm = 120, key = "C")
	composition.harmony(style = "pop_major", key_pull = 0.6)

	assert composition._harmonic_state is not None
	assert composition._harmonic_state.key_gravity_blend == pytest.approx(0.4)


def test_the_default_is_the_sound_every_existing_piece_has (patch_midi: None) -> None:

	"""key_pull=0.0 must be what gravity=1.0 did, or every piece changes."""

	composition = subsequence.Composition(bpm = 120, key = "C")
	composition.harmony(style = "pop_major")

	assert composition._harmonic_state is not None
	assert composition._harmonic_state.key_gravity_blend == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# key_pull pulls
# ---------------------------------------------------------------------------

def _boost (key_pull: float, chord_name: str) -> float:

	"""The modifier the walk applies to one candidate, with NIR held out of it."""

	state = subsequence.harmonic_state.HarmonicState(
		key_name = "C", graph_style = "pop_major",
		key_gravity_blend = 1.0 - key_pull, rng = random.Random(0),
	)

	target = next(
		node for node in state.graph.nodes() if node.name() == chord_name
	)

	is_function = 1.0 if target in state._function_chords else 0.0
	is_diatonic = 1.0 if target in state._diatonic_chords else 0.0

	return (1.0 - state.key_gravity_blend) * is_function + state.key_gravity_blend * is_diatonic


def test_at_no_pull_every_diatonic_chord_is_weighted_alike () -> None:

	"""Which is why the old default did nothing at all."""

	assert _boost(0.0, "G") == pytest.approx(_boost(0.0, "Am"))
	assert _boost(0.0, "F") == pytest.approx(_boost(0.0, "Em"))


def test_at_full_pull_the_keys_centres_win () -> None:

	"""G is a function chord in C; Em is diatonic and is not."""

	assert _boost(1.0, "G") > _boost(1.0, "Em")


def test_more_pull_means_more_dominant (patch_midi: None) -> None:

	"""The direction, measured the way a listener would hear it.

	G followed the tonic 27.4% of the time at no pull and 38.5% at full pull.
	Asserting the direction with room to spare rather than the exact figure,
	which is a property of the graph's weights and not of this knob.
	"""

	def share_of_g (key_pull: float, trials: int = 1500) -> float:

		hits = 0

		for seed in range(trials):

			# Through harmony(), not by building a HarmonicState by hand: the
			# knob a musician turns is the public one, and a version of this
			# that constructed the state itself passed happily with the
			# wiring in composition.py inverted.
			composition = subsequence.Composition(bpm = 120, key = "C", seed = seed)
			composition.harmony(style = "pop_major", key_pull = key_pull)

			state = composition._harmonic_state
			assert state is not None

			chosen = state.graph.choose_next(
				state.current_chord, random.Random(seed),
				weight_modifier = state._transition_weight,
			)
			hits += chosen.name() == "G"

		return hits / trials

	loose = share_of_g(0.0)
	tight = share_of_g(1.0)

	assert tight > loose + 0.05, f"no pull {loose:.3f} vs full pull {tight:.3f}"


# ---------------------------------------------------------------------------
# root_diversity=0.0 means diversity
# ---------------------------------------------------------------------------

def _self_repeats (style: str, root_diversity: float, steps: int = 40) -> int:

	state = subsequence.harmonic_state.HarmonicState(
		key_name = "C", graph_style = style,
		root_diversity = root_diversity, rng = random.Random(3),
	)

	walk = []

	for _ in range(steps):
		state.step()
		walk.append(state.current_chord.name())

	return sum(1 for a, b in zip(walk, walk[1:]) if a == b)


@pytest.mark.parametrize("style", STYLES)
def test_maximum_diversity_does_not_repeat (style: str) -> None:

	"""0.0 is documented as maximum diversity and produced the most repetition."""

	repeats = _self_repeats(style, 0.0)

	assert repeats == 0, f"{style} repeated itself {repeats} times in 39 steps at root_diversity=0.0"


def test_the_worst_style_is_the_one_the_review_measured () -> None:

	"""`suspended` gave 29 self-repeats in 39 steps — named so a regression is recognisable."""

	assert _self_repeats("suspended", 0.0) == 0


@pytest.mark.parametrize("style", STYLES)
def test_the_default_still_does_not_repeat (style: str) -> None:

	"""The control: 0.4 was already fine, and must stay fine."""

	assert _self_repeats(style, 0.4) == 0


# ---------------------------------------------------------------------------
# What the graph does when everything is suppressed
# ---------------------------------------------------------------------------

def test_a_modifier_that_rejects_everything_falls_back_to_the_raw_weights () -> None:

	"""It used to return the source, which is the one answer it did not ask for."""

	graph: subsequence.weighted_graph.WeightedGraph[str] = subsequence.weighted_graph.WeightedGraph()
	graph.add_transition("a", "b", 3)
	graph.add_transition("a", "c", 1)

	chosen = {
		graph.choose_next("a", random.Random(seed), weight_modifier = lambda s, t, w: 0.0)
		for seed in range(40)
	}

	assert "a" not in chosen, "it stayed on the node it was already on"
	assert chosen == {"b", "c"}


def test_the_fallback_still_respects_the_weights () -> None:

	"""Falling back must mean the graph's weights, not a coin toss."""

	graph: subsequence.weighted_graph.WeightedGraph[str] = subsequence.weighted_graph.WeightedGraph()
	graph.add_transition("a", "b", 9)
	graph.add_transition("a", "c", 1)

	picks = [
		graph.choose_next("a", random.Random(seed), weight_modifier = lambda s, t, w: 0.0)
		for seed in range(400)
	]

	share_of_b = picks.count("b") / len(picks)

	assert 0.8 < share_of_b < 0.98, f"b took {share_of_b:.2f} of a 9:1 split"


def test_a_node_with_no_transitions_at_all_still_stays_put () -> None:

	"""The control: there is genuinely nowhere to go, and that is not this bug."""

	graph: subsequence.weighted_graph.WeightedGraph[str] = subsequence.weighted_graph.WeightedGraph()
	graph.add_transition("a", "b", 1)

	assert graph.choose_next("b", random.Random(0)) == "b"


def test_an_ordinary_modifier_is_untouched () -> None:

	"""The other control: the fallback must not fire when something survives."""

	graph: subsequence.weighted_graph.WeightedGraph[str] = subsequence.weighted_graph.WeightedGraph()
	graph.add_transition("a", "b", 1)
	graph.add_transition("a", "c", 1)

	def only_c (source: str, target: str, weight: int) -> float:
		return 1.0 if target == "c" else 0.0

	chosen = {
		graph.choose_next("a", random.Random(seed), weight_modifier = only_c)
		for seed in range(20)
	}

	assert chosen == {"c"}
