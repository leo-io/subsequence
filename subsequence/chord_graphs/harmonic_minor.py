import typing

import subsequence.chord_graphs
import subsequence.chords
import subsequence.weighted_graph


WEIGHT_STRONG = subsequence.chord_graphs.WEIGHT_STRONG
WEIGHT_MEDIUM = subsequence.chord_graphs.WEIGHT_MEDIUM
WEIGHT_COMMON = subsequence.chord_graphs.WEIGHT_COMMON
WEIGHT_DECEPTIVE = subsequence.chord_graphs.WEIGHT_DECEPTIVE
WEIGHT_WEAK = subsequence.chord_graphs.WEIGHT_WEAK

# Semitones above the tonic, and the harmonic-minor chord on each.
DEGREES: typing.Dict[str, typing.Tuple[int, str]] = {
	"i":         (0, "minor"),
	"i(maj7)":   (0, "minor_major_7th"),
	"iiø7":      (2, "half_diminished_7th"),
	"iv":        (5, "minor"),
	"V7":        (7, "dominant_7th"),
	"bVI":       (8, "major"),
	"vii°7":     (11, "diminished_7th"),
}


class HarmonicMinor (subsequence.chord_graphs.ChordGraph):

	"""Minor chord graph on the harmonic minor's leading tone, for suspense.

	Scale: 1, 2, b3, 4, 5, b6, 7.
	Chords: i, i(maj7), iiø7, iv, V7, ♭VI, vii°7 - all inside the scale.

	The tonic is a minor chord that keeps sliding to its own minor-major
	seventh and back (the "James Bond" chord), and the dominant side -
	V7 and the diminished seventh on the leading tone - keeps pressing on
	it.  Resolutions come, but rarely settle for long: tension without the
	tonic ever disappearing.
	"""

	def build (self, key_name: str) -> typing.Tuple[subsequence.weighted_graph.WeightedGraph[subsequence.chords.Chord], subsequence.chords.Chord]:

		"""Build the harmonic-minor suspense graph."""

		key_pc = subsequence.chord_graphs.validate_key_name(key_name)
		chord = {
			name: subsequence.chords.Chord(root_pc=(key_pc + offset) % 12, quality=quality)
			for name, (offset, quality) in DEGREES.items()
		}

		graph: subsequence.weighted_graph.WeightedGraph[subsequence.chords.Chord] = subsequence.weighted_graph.WeightedGraph()

		# --- i ↔ i(maj7): the suspended tonic ---
		graph.add_transition(chord["i"], chord["i(maj7)"], WEIGHT_STRONG)
		graph.add_transition(chord["i(maj7)"], chord["i"], WEIGHT_MEDIUM)

		# --- The dominant side presses on the tonic ---
		graph.add_transition(chord["i"], chord["vii°7"], WEIGHT_COMMON)
		graph.add_transition(chord["i(maj7)"], chord["vii°7"], WEIGHT_COMMON)
		graph.add_transition(chord["vii°7"], chord["i"], WEIGHT_STRONG)
		graph.add_transition(chord["vii°7"], chord["V7"], WEIGHT_COMMON)
		graph.add_transition(chord["V7"], chord["i"], WEIGHT_STRONG)
		graph.add_transition(chord["V7"], chord["bVI"], WEIGHT_DECEPTIVE)

		# --- Pre-dominants ---
		graph.add_transition(chord["i"], chord["iv"], WEIGHT_COMMON)
		graph.add_transition(chord["i(maj7)"], chord["iv"], WEIGHT_COMMON)
		graph.add_transition(chord["iv"], chord["V7"], WEIGHT_MEDIUM)
		graph.add_transition(chord["iv"], chord["vii°7"], WEIGHT_COMMON)
		graph.add_transition(chord["i"], chord["iiø7"], WEIGHT_WEAK)
		graph.add_transition(chord["iiø7"], chord["V7"], WEIGHT_STRONG)

		# --- bVI: the deceptive landing, back towards the dominant ---
		graph.add_transition(chord["bVI"], chord["V7"], WEIGHT_MEDIUM)
		graph.add_transition(chord["bVI"], chord["iiø7"], WEIGHT_WEAK)
		graph.add_transition(chord["i"], chord["bVI"], WEIGHT_WEAK)

		return graph, chord["i"]

	def gravity_sets (self, key_name: str) -> typing.Tuple[typing.Set[subsequence.chords.Chord], typing.Set[subsequence.chords.Chord]]:

		"""Return the graph's chords, and i, V7 and vii°7 as its functional set."""

		key_pc = subsequence.chord_graphs.validate_key_name(key_name)
		chord = {
			name: subsequence.chords.Chord(root_pc=(key_pc + offset) % 12, quality=quality)
			for name, (offset, quality) in DEGREES.items()
		}

		return set(chord.values()), {chord["i"], chord["V7"], chord["vii°7"]}
