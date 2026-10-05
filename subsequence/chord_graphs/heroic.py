import typing

import subsequence.chord_graphs
import subsequence.chords
import subsequence.weighted_graph


WEIGHT_STRONG = subsequence.chord_graphs.WEIGHT_STRONG
WEIGHT_MEDIUM = subsequence.chord_graphs.WEIGHT_MEDIUM
WEIGHT_COMMON = subsequence.chord_graphs.WEIGHT_COMMON
WEIGHT_WEAK = subsequence.chord_graphs.WEIGHT_WEAK

# Semitones above the tonic, and the chord on each.  bVI is borrowed from
# the parallel minor; the minor i opens the minor-key version of the cadence.
DEGREES: typing.Dict[str, typing.Tuple[int, str]] = {
	"I":    (0, "major"),
	"i":    (0, "minor"),
	"IV":   (5, "major"),
	"bVI":  (8, "major"),
	"bVII": (10, "major"),
}


class Heroic (subsequence.chord_graphs.ChordGraph):

	"""Major-key chord graph built on the ♭VI – ♭VII – I hero cadence.

	Chords: I, IV, ♭VII and ♭VI, plus a minor i that opens the minor-key
	form i – ♭VI – ♭VII – I.  All major triads but the i: open, bright, and
	rising into the tonic from a whole step below - the film-score and
	anthem cadence.  ♭VII does the dominant's work, so there is no V.

	I, IV and ♭VII are Mixolydian; ♭VI and the i are borrowed from the
	parallel minor, and ♭VI is what gives the cadence its lift.
	"""

	def build (self, key_name: str) -> typing.Tuple[subsequence.weighted_graph.WeightedGraph[subsequence.chords.Chord], subsequence.chords.Chord]:

		"""Build the hero-cadence graph."""

		key_pc = subsequence.chord_graphs.validate_key_name(key_name)
		chord = {
			name: subsequence.chords.Chord(root_pc=(key_pc + offset) % 12, quality=quality)
			for name, (offset, quality) in DEGREES.items()
		}

		graph: subsequence.weighted_graph.WeightedGraph[subsequence.chords.Chord] = subsequence.weighted_graph.WeightedGraph()

		# --- bVI → bVII → I: the hero cadence ---
		graph.add_transition(chord["bVI"], chord["bVII"], WEIGHT_STRONG)
		graph.add_transition(chord["bVII"], chord["I"], WEIGHT_STRONG)
		graph.add_transition(chord["I"], chord["bVI"], WEIGHT_MEDIUM)

		# --- i → bVI: the minor-key opening of the same cadence ---
		graph.add_transition(chord["I"], chord["i"], WEIGHT_WEAK)
		graph.add_transition(chord["i"], chord["bVI"], WEIGHT_STRONG)
		graph.add_transition(chord["i"], chord["bVII"], WEIGHT_WEAK)

		# --- Plain major motion between cadences ---
		graph.add_transition(chord["I"], chord["IV"], WEIGHT_COMMON)
		graph.add_transition(chord["IV"], chord["bVII"], WEIGHT_COMMON)
		graph.add_transition(chord["IV"], chord["I"], WEIGHT_MEDIUM)
		graph.add_transition(chord["IV"], chord["bVI"], WEIGHT_WEAK)
		graph.add_transition(chord["bVII"], chord["IV"], WEIGHT_WEAK)

		return graph, chord["I"]

	def gravity_sets (self, key_name: str) -> typing.Tuple[typing.Set[subsequence.chords.Chord], typing.Set[subsequence.chords.Chord]]:

		"""Return the graph's chords, and I, bVI and bVII as its functional set."""

		key_pc = subsequence.chord_graphs.validate_key_name(key_name)
		chord = {
			name: subsequence.chords.Chord(root_pc=(key_pc + offset) % 12, quality=quality)
			for name, (offset, quality) in DEGREES.items()
		}

		return set(chord.values()), {chord["I"], chord["bVI"], chord["bVII"]}
