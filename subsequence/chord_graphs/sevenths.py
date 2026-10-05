import typing

import subsequence.chord_graphs
import subsequence.chords
import subsequence.intervals
import subsequence.weighted_graph


# A triad's quality, the semitones from its root a diatonic seventh can sit,
# and the seventh chord each one makes.
SEVENTHS: typing.Dict[str, typing.Dict[int, str]] = {
	"major":      {11: "major_7th", 10: "dominant_7th"},
	"minor":      {10: "minor_7th", 11: "minor_major_7th"},
	"diminished": {10: "half_diminished_7th", 9: "diminished_7th"},
}


class Sevenths (subsequence.chord_graphs.ChordGraph):

	"""Another chord graph with a diatonic seventh stacked on each of its triads.

	The seventh is the one *scale* holds (the piece's scale where the
	chords play), or, without one, the scale of the wrapped graph's own
	diatonic chords (``gravity_sets``).  So C in C major becomes Cmaj7, G
	becomes G7 and Am becomes Am7, while C in C mixolydian becomes C7.  A
	triad with no seventh in that scale, or more than one (a borrowed
	chord), stays a triad, and chords that are not triads (sevenths, sixths, sus, power,
	augmented) are left as they are.  Two chords that map to the same
	seventh chord merge, their transition weights adding.

	Used by ``composition.harmony(sevenths=True)``.
	"""

	def __init__ (self, inner: subsequence.chord_graphs.ChordGraph, scale: typing.Optional[str] = None) -> None:

		"""Wrap *inner*, taking sevenths from *scale* when it is given."""

		self.inner = inner
		self.scale = scale

	def _colour (self, key_name: str) -> typing.Callable[[subsequence.chords.Chord], subsequence.chords.Chord]:

		"""A function giving each chord its diatonic seventh in the scale."""

		if self.scale is not None:
			scale_pcs = set(subsequence.intervals.scale_pitch_classes(subsequence.chords.key_name_to_pc(key_name), self.scale))
		else:
			diatonic, _ = self.inner.gravity_sets(key_name)
			scale_pcs = {(chord.root_pc + interval) % 12 for chord in diatonic for interval in chord.intervals()}

		def colour (chord: subsequence.chords.Chord) -> subsequence.chords.Chord:

			"""*chord* with its diatonic seventh, or unchanged when it has none or several."""

			options = SEVENTHS.get(chord.quality, {})
			found = [quality for gap, quality in options.items() if (chord.root_pc + gap) % 12 in scale_pcs]

			if len(found) != 1:
				return chord

			return subsequence.chords.Chord(root_pc=chord.root_pc, quality=found[0])

		return colour

	def build (self, key_name: str) -> typing.Tuple[subsequence.weighted_graph.WeightedGraph[subsequence.chords.Chord], subsequence.chords.Chord]:

		"""Build the inner graph and colour every chord in it."""

		inner_graph, tonic = self.inner.build(key_name)
		colour = self._colour(key_name)

		graph: subsequence.weighted_graph.WeightedGraph[subsequence.chords.Chord] = subsequence.weighted_graph.WeightedGraph()

		for source in inner_graph.nodes():
			for target, weight in inner_graph.get_transitions(source):
				if colour(source) == colour(target):
					# A triad and its own seventh (G and G7) would loop onto one chord.
					continue
				graph.add_transition(colour(source), colour(target), weight, inner_graph.get_label(source, target))

		return graph, colour(tonic)

	def gravity_sets (self, key_name: str) -> typing.Tuple[typing.Set[subsequence.chords.Chord], typing.Set[subsequence.chords.Chord]]:

		"""Return the inner graph's sets, coloured the same way."""

		diatonic, functional = self.inner.gravity_sets(key_name)
		colour = self._colour(key_name)

		return {colour(chord) for chord in diatonic}, {colour(chord) for chord in functional}
