import typing

import subsequence.chord_graphs
import subsequence.chords
import subsequence.weighted_graph


WEIGHT_STRONG = subsequence.chord_graphs.WEIGHT_STRONG
WEIGHT_MEDIUM = subsequence.chord_graphs.WEIGHT_MEDIUM
WEIGHT_COMMON = subsequence.chord_graphs.WEIGHT_COMMON
WEIGHT_WEAK = subsequence.chord_graphs.WEIGHT_WEAK

# Semitones above the tonic, and the melodic-minor chord on each.
DEGREES: typing.Dict[str, typing.Tuple[int, str]] = {
	"i":       (0, "minor"),
	"i(maj7)": (0, "minor_major_7th"),
	"i6":      (0, "minor_6th"),
	"ii7":     (2, "minor_7th"),
	"IV7":     (5, "dominant_7th"),
	"V7":      (7, "dominant_7th"),
	"viø7":    (9, "half_diminished_7th"),
	"viiø7":   (11, "half_diminished_7th"),
}


class MelodicMinor (subsequence.chord_graphs.ChordGraph):

	"""Minor chord graph in the melodic minor, bittersweet rather than sad.

	Scale: 1, 2, b3, 4, 5, 6, 7.
	Chords: i, i(maj7), i6, ii7, IV7, V7, viø7, viiø7 - all inside the scale.

	The tonic's inner voice climbs (i → i(maj7) → i6): a minor chord whose
	sixth and seventh are raised, so the sadness carries a lift.  The major
	IV7 and the ii7 – V7 pair are the bright side the tonic keeps leaning
	towards.
	"""

	def build (self, key_name: str) -> typing.Tuple[subsequence.weighted_graph.WeightedGraph[subsequence.chords.Chord], subsequence.chords.Chord]:

		"""Build the melodic-minor graph."""

		key_pc = subsequence.chord_graphs.validate_key_name(key_name)
		chord = {
			name: subsequence.chords.Chord(root_pc=(key_pc + offset) % 12, quality=quality)
			for name, (offset, quality) in DEGREES.items()
		}

		graph: subsequence.weighted_graph.WeightedGraph[subsequence.chords.Chord] = subsequence.weighted_graph.WeightedGraph()

		# --- i → i(maj7) → i6: the climbing inner voice ---
		graph.add_transition(chord["i"], chord["i(maj7)"], WEIGHT_STRONG)
		graph.add_transition(chord["i(maj7)"], chord["i6"], WEIGHT_STRONG)
		graph.add_transition(chord["i(maj7)"], chord["i"], WEIGHT_WEAK)

		# --- i6 opens onto the bright side ---
		graph.add_transition(chord["i6"], chord["IV7"], WEIGHT_MEDIUM)
		graph.add_transition(chord["i6"], chord["ii7"], WEIGHT_COMMON)
		graph.add_transition(chord["i6"], chord["i"], WEIGHT_WEAK)
		graph.add_transition(chord["IV7"], chord["i"], WEIGHT_MEDIUM)
		graph.add_transition(chord["IV7"], chord["V7"], WEIGHT_COMMON)

		# --- ii7 – V7 – i ---
		graph.add_transition(chord["ii7"], chord["V7"], WEIGHT_STRONG)
		graph.add_transition(chord["V7"], chord["i"], WEIGHT_STRONG)
		graph.add_transition(chord["V7"], chord["i(maj7)"], WEIGHT_WEAK)

		# --- Half-diminished colours ---
		graph.add_transition(chord["i"], chord["viø7"], WEIGHT_WEAK)
		graph.add_transition(chord["viø7"], chord["ii7"], WEIGHT_COMMON)
		graph.add_transition(chord["viø7"], chord["V7"], WEIGHT_WEAK)
		graph.add_transition(chord["IV7"], chord["viiø7"], WEIGHT_WEAK)
		graph.add_transition(chord["viiø7"], chord["i"], WEIGHT_MEDIUM)

		return graph, chord["i"]

	def gravity_sets (self, key_name: str) -> typing.Tuple[typing.Set[subsequence.chords.Chord], typing.Set[subsequence.chords.Chord]]:

		"""Return the graph's chords, and i, IV7 and V7 as its functional set."""

		key_pc = subsequence.chord_graphs.validate_key_name(key_name)
		chord = {
			name: subsequence.chords.Chord(root_pc=(key_pc + offset) % 12, quality=quality)
			for name, (offset, quality) in DEGREES.items()
		}

		return set(chord.values()), {chord["i"], chord["IV7"], chord["V7"]}
