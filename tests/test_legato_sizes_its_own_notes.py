"""chord(legato=) and strum(legato=) size only their own notes, once the build is done (#3463, Simon's call on #3423).

Both called the pattern-wide ``p.legato()`` at the moment of the call, which set every
note in the pattern to a share of the gap to the next onset anywhere.  A strum's
strings each saw the next string, so all but the last lasted a pulse; a bass note
placed first was cut to one; a chord rang straight through a chord placed after it;
and a second legato call overwrote the first's ratio.

Now each call marks its notes, and when the build is done those notes, and only
those, ring for their ratio of the gap from the call's first onset to the next
attack after its last, wrapping round the cycle to where it plays again.  A strum is
one attack: every string lasts the same, so the last lets go at that point and the
earlier ones sooner.
"""

import typing

import subsequence.chords
import subsequence.pattern
import subsequence.pattern_builder

C = subsequence.chords.Chord(root_pc=0, quality="major")
F = subsequence.chords.Chord(root_pc=5, quality="major")
E_MINOR = subsequence.chords.Chord(root_pc=4, quality="minor")


def _builder () -> typing.Tuple[subsequence.pattern.Pattern, subsequence.pattern_builder.PatternBuilder]:

	pattern = subsequence.pattern.Pattern(channel=0, length=4)

	return pattern, subsequence.pattern_builder.PatternBuilder(pattern=pattern, cycle=0, default_grid=16)


def _durations (pattern: subsequence.pattern.Pattern) -> typing.Dict[int, typing.List[int]]:

	"""Each onset's note durations, in pulses."""

	return {position: sorted(note.duration for note in step.notes) for position, step in sorted(pattern.steps.items())}


def test_a_gentle_strum_rings_as_one_attack () -> None:

	"""The docstring's own gentle strum: three strings of 89 pulses, the last ending at 0.95 of the bar.

	Its strings were (1, 1, 89): the lower two lasted about 21 ms at 120 BPM.
	"""

	pattern, p = _builder()
	p.strum(E_MINOR, root=52, velocity=85, spacing=0.06, legato=0.95)
	p._finish_build()

	assert _durations(pattern) == {0: [89], 1: [89], 2: [89]}


def test_a_note_placed_before_a_strum_keeps_its_length () -> None:

	"""A bass note on the downbeat was cut to a pulse by the strum's legato."""

	pattern, p = _builder()
	p.note(40, beat=0, velocity=100, duration=4.0)
	p.strum(E_MINOR, root=52, velocity=85, spacing=0.06, legato=0.9)
	p._finish_build()

	assert sorted(note.duration for note in pattern.steps[0].notes if note.pitch == 40) == [96]


def test_a_chord_placed_later_cuts_one_placed_earlier () -> None:

	"""C with legato 0.9, then F on beat 3: the C lets go at 0.9 of the way to the F, not 0.9 of the bar.

	It rang 86 pulses, straight through the F at pulse 48.
	"""

	pattern, p = _builder()
	p.chord(C, root=60, legato=0.9)
	p.chord(F, root=60, beat=2)
	p._finish_build()

	assert _durations(pattern) == {0: [43, 43, 43], 48: [24, 24, 24]}


def test_each_call_keeps_its_own_ratio () -> None:

	"""0.5 on the first chord and 0.9 on the second: 24 and 43 pulses, where both got 43."""

	pattern, p = _builder()
	p.chord(C, root=60, legato=0.5)
	p.chord(F, root=60, legato=0.9, beat=2)
	p._finish_build()

	assert _durations(pattern) == {0: [24, 24, 24], 48: [43, 43, 43]}


def test_a_note_placed_after_a_strum_limits_it () -> None:

	"""A melody note on beat 4 comes after the strum was placed, and the strum still lets go before it."""

	pattern, p = _builder()
	p.strum(E_MINOR, root=52, velocity=85, spacing=0.06, legato=0.9)
	p.note(76, beat=3, velocity=100, duration=0.5)
	p._finish_build()

	assert _durations(pattern) == {0: [62], 1: [62], 2: [62], 72: [12]}		# the last string ends at 2 + 62 = 64 = int(72 * 0.9)


def test_a_note_inside_the_strum_does_not_cut_it () -> None:

	"""A hit between the strings belongs to the strum's own moment: the gap runs to the next attack after its last string."""

	pattern, p = _builder()
	p.strum(C, root=60, velocity=85, spacing=0.1, legato=0.9)
	p.note(42, beat=0.125, velocity=60, duration=0.1)
	p.chord(F, root=60, beat=2)
	p._finish_build()

	strum = sorted(note.duration for position in (0, 2, 4) for note in pattern.steps[position].notes)

	assert strum == [39, 39, 39]		# the last string, at pulse 4, ends at 43 = int(48 * 0.9)


def test_a_strum_swung_after_it_was_placed_still_rings_as_one () -> None:

	"""Swing copies the strings it moves; each copy keeps its place in the strum."""

	pattern, p = _builder()
	p.strum(C, root=60, velocity=85, spacing=0.25, legato=0.9)
	p.swing(75)
	p._finish_build()

	strings = {position: note.duration for position, step in pattern.steps.items() for note in step.notes}

	assert sorted(strings) == [0, 9, 12]		# the second string swung from 6 to 9
	assert set(strings.values()) == {74}		# the last, at 12, ends at 86 = int(96 * 0.9)


def test_p_legato_still_reshapes_the_whole_pattern_at_once () -> None:

	"""The public ``p.legato()`` is unchanged: every note, at the moment it is called.

	This passed before #3463 as well.
	"""

	pattern, p = _builder()
	p.note(60, beat=0, velocity=100, duration=0.1)
	p.note(62, beat=1, velocity=100, duration=0.1)
	p.legato(0.5)

	assert _durations(pattern) == {0: [12], 24: [36]}


def test_a_strum_lets_go_before_it_plays_again () -> None:

	"""Round the cycle the next attack is the strum's own, next time round, if nothing comes sooner.

	Only a hit between its strings follows it here, and that hit, next time
	round, comes a pulse after the strum's own attack: measured to the hit,
	the strings would ring a pulse into the strum's next strike.
	"""

	pattern, p = _builder()
	p.strum(E_MINOR, root=52, velocity=85, spacing=0.06, legato=0.9)
	p.note(42, beat=0.05, velocity=60, duration=0.02)		# pulse 1, between the strings
	p._finish_build()

	assert sorted(note.duration for position in (0, 2) for note in pattern.steps[position].notes if note.pitch != 42) == [84, 84]
