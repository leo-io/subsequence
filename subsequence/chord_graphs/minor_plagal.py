import typing

import subsequence.chord_graphs
import subsequence.chords
import subsequence.intervals
import subsequence.weighted_graph


WEIGHT_STRONG = subsequence.chord_graphs.WEIGHT_STRONG
WEIGHT_MEDIUM = subsequence.chord_graphs.WEIGHT_MEDIUM
WEIGHT_COMMON = subsequence.chord_graphs.WEIGHT_COMMON
WEIGHT_DECEPTIVE = subsequence.chord_graphs.WEIGHT_DECEPTIVE
WEIGHT_WEAK = subsequence.chord_graphs.WEIGHT_WEAK

# Semitones above the tonic, and the chord on each.  The iv6 is borrowed
# from the parallel minor; everything else is the major key's own.
DEGREES: typing.Dict[str, typing.Tuple[int, str]] = {
	"I":   (0, "major"),
	"ii":  (2, "minor"),
	"IV":  (5, "major"),
	"iv6": (5, "minor_6th"),
	"V":   (7, "major"),
	"vi":  (9, "minor"),
}


class MinorPlagal (subsequence.chord_graphs.ChordGraph):

	"""Major-key chord graph that comes home through the borrowed iv6.

	Chords: I, ii, IV, V, vi, and iv6 from the parallel minor.

	The heaviest path is IV → iv6 → I: the major subdominant darkening to
	its minor before the tonic, the "amen" of gospel and the ache of soul
	ballads.  The ordinary major-key moves (vi – ii – V – I, IV – V) run
	between those returns.
	"""

	def build (self, key_name: str) -> typing.Tuple[subsequence.weighted_graph.WeightedGraph[subsequence.chords.Chord], subsequence.chords.Chord]:

		"""Build the minor-plagal graph."""

		key_pc = subsequence.chord_graphs.validate_key_name(key_name)
		chord = {
			name: subsequence.chords.Chord(root_pc=(key_pc + offset) % 12, quality=quality)
			for name, (offset, quality) in DEGREES.items()
		}

		graph: subsequence.weighted_graph.WeightedGraph[subsequence.chords.Chord] = subsequence.weighted_graph.WeightedGraph()

		# --- IV → iv6 → I: the minor plagal return ---
		graph.add_transition(chord["I"], chord["IV"], WEIGHT_STRONG)
		graph.add_transition(chord["IV"], chord["iv6"], WEIGHT_STRONG)
		graph.add_transition(chord["iv6"], chord["I"], WEIGHT_STRONG)
		graph.add_transition(chord["IV"], chord["I"], WEIGHT_COMMON)

		# --- Major-key motion between returns ---
		graph.add_transition(chord["I"], chord["vi"], WEIGHT_COMMON)
		graph.add_transition(chord["vi"], chord["IV"], WEIGHT_MEDIUM)
		graph.add_transition(chord["vi"], chord["ii"], WEIGHT_COMMON)
		graph.add_transition(chord["ii"], chord["V"], WEIGHT_MEDIUM)
		graph.add_transition(chord["ii"], chord["iv6"], WEIGHT_WEAK)
		graph.add_transition(chord["IV"], chord["V"], WEIGHT_COMMON)
		graph.add_transition(chord["V"], chord["I"], WEIGHT_STRONG)
		graph.add_transition(chord["V"], chord["vi"], WEIGHT_DECEPTIVE)
		graph.add_transition(chord["I"], chord["ii"], WEIGHT_WEAK)

		return graph, chord["I"]

	def gravity_sets (self, key_name: str) -> typing.Tuple[typing.Set[subsequence.chords.Chord], typing.Set[subsequence.chords.Chord]]:

		"""Return the major key's diatonic chords, and I, IV and iv6 as the functional set."""

		key_pc = subsequence.chord_graphs.validate_key_name(key_name)

		diatonic: typing.Set[subsequence.chords.Chord] = set(
			subsequence.chord_graphs.build_diatonic_chords(
				subsequence.intervals.scale_pitch_classes(key_pc, "ionian"),
				subsequence.intervals.IONIAN_QUALITIES
			)
		)

		functional = {
			subsequence.chords.Chord(root_pc=(key_pc + offset) % 12, quality=quality)
			for name, (offset, quality) in DEGREES.items()
			if name in ("I", "IV", "iv6")
		}

		return diatonic, functional
