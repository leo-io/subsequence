import typing

import subsequence.chord_graphs
import subsequence.chords
import subsequence.weighted_graph


WEIGHT_STRONG = subsequence.chord_graphs.WEIGHT_STRONG
WEIGHT_MEDIUM = subsequence.chord_graphs.WEIGHT_MEDIUM
WEIGHT_COMMON = subsequence.chord_graphs.WEIGHT_COMMON
WEIGHT_WEAK = subsequence.chord_graphs.WEIGHT_WEAK

# Semitones above the tonic, and the Phrygian triad on each degree used.
# The diminished v is left out: it pulls towards a dominant the mode lacks.
DEGREES: typing.Dict[str, typing.Tuple[int, str]] = {
	"i":    (0, "minor"),
	"bII":  (1, "major"),
	"bIII": (3, "major"),
	"iv":   (5, "minor"),
	"bVI":  (8, "major"),
	"bvii": (10, "minor"),
}


class Phrygian (subsequence.chord_graphs.ChordGraph):

	"""Diatonic Phrygian chord graph built around the i ↔ ♭II vamp.

	Scale: 1, b2, b3, 4, 5, b6, b7.
	Chords: i (minor), ♭II (major), ♭III (major), iv (minor), ♭VI (major),
	♭vii (minor) - every one inside the mode, unlike ``phrygian_minor``,
	whose minor ♭ii and v are not.

	The major ♭II sitting a semitone over the tonic is the mode's colour,
	and the i ↔ ♭II shuttle is by far the strongest move: a static,
	hypnotic vamp the other chords only visit.

	With ``power_chords=True`` every chord is a root and fifth with no
	third (``"phrygian_power"``): the same motion as driving, no-third
	riffs and ♭II stabs.
	"""

	def __init__ (self, power_chords: bool = False) -> None:

		"""Store whether the chords drop their thirds."""

		self.power_chords = power_chords

	def _chord (self, key_pc: int, degree: str) -> subsequence.chords.Chord:

		"""The chord on *degree*, as a power chord when the graph asks for them."""

		offset, quality = DEGREES[degree]

		return subsequence.chords.Chord(root_pc=(key_pc + offset) % 12, quality="power_chord" if self.power_chords else quality)

	def build (self, key_name: str) -> typing.Tuple[subsequence.weighted_graph.WeightedGraph[subsequence.chords.Chord], subsequence.chords.Chord]:

		"""Build the Phrygian vamp graph."""

		key_pc = subsequence.chord_graphs.validate_key_name(key_name)
		chord = {degree: self._chord(key_pc, degree) for degree in DEGREES}

		graph: subsequence.weighted_graph.WeightedGraph[subsequence.chords.Chord] = subsequence.weighted_graph.WeightedGraph()

		# --- i ↔ bII: the vamp ---
		graph.add_transition(chord["i"], chord["bII"], WEIGHT_STRONG)
		graph.add_transition(chord["bII"], chord["i"], WEIGHT_STRONG)

		# --- Plagal colour ---
		graph.add_transition(chord["i"], chord["iv"], WEIGHT_COMMON)
		graph.add_transition(chord["iv"], chord["i"], WEIGHT_MEDIUM)
		graph.add_transition(chord["iv"], chord["bII"], WEIGHT_COMMON)

		# --- bVI and bvii descend back to the tonic ---
		graph.add_transition(chord["i"], chord["bVI"], WEIGHT_WEAK)
		graph.add_transition(chord["bVI"], chord["bII"], WEIGHT_MEDIUM)
		graph.add_transition(chord["bVI"], chord["bvii"], WEIGHT_COMMON)
		graph.add_transition(chord["bvii"], chord["i"], WEIGHT_MEDIUM)
		graph.add_transition(chord["i"], chord["bvii"], WEIGHT_WEAK)

		# --- bIII falls onto bII ---
		graph.add_transition(chord["i"], chord["bIII"], WEIGHT_WEAK)
		graph.add_transition(chord["bIII"], chord["bII"], WEIGHT_MEDIUM)
		graph.add_transition(chord["bIII"], chord["iv"], WEIGHT_WEAK)

		return graph, chord["i"]

	def gravity_sets (self, key_name: str) -> typing.Tuple[typing.Set[subsequence.chords.Chord], typing.Set[subsequence.chords.Chord]]:

		"""Return the mode's chords, and i and bII as its functional pair."""

		key_pc = subsequence.chord_graphs.validate_key_name(key_name)

		diatonic = {self._chord(key_pc, degree) for degree in DEGREES}
		functional = {self._chord(key_pc, "i"), self._chord(key_pc, "bII")}

		return diatonic, functional
