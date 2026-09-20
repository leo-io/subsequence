"""The chord a pattern is handed voices itself as its span does (#3007).

``_InjectedChord`` rebuilt the voicing from ``intervals()`` and a root, so a
span's inversion, spread and slash bass were lost on the way into a builder: a
pattern played a plain C triad while ``chord.name()`` said ``C/G``, a bass line
over a slash chord took the root, and a ``PitchSet`` section raised
``AttributeError`` every bar and sounded nothing.

Under ``voice_leading=True`` every voice is led, the slash note among them, per
decision 7 of #2991 — it may move inward rather than staying the lowest note.
"""

import pathlib
import typing

import mido
import pytest

import subsequence
import subsequence.composition
import subsequence.progressions
import subsequence.voicings


def _injected (span: subsequence.progressions.ChordSpan, leading: bool = False) -> typing.Any:

	"""The chord object a two-parameter builder receives for this span."""

	chord = subsequence.progressions.DecoratedChord(span) if span.is_decorated else span.chord

	return subsequence.composition._InjectedChord(
		chord,
		voice_leading_state = subsequence.voicings.VoiceLeadingState() if leading else None,
	)


def _span (progression: subsequence.progressions.Progression, index: int = 0) -> subsequence.progressions.ChordSpan:

	"""One span of a concrete progression."""

	return progression.spans[index]


# ---------------------------------------------------------------------------
# The voicing a builder is handed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("build", [
	lambda: subsequence.progression(["C", "F"]).over("G").inversions(1).spread("open"),
	lambda: subsequence.progression(["C", "F"]).over("G"),
	lambda: subsequence.progression(["Am", "F"]).inversions(2),
	lambda: subsequence.progression(["C", "F"]).spread("wide"),
	lambda: subsequence.progression(["C", "F"]).extend(9),
	lambda: subsequence.progression(["C", "F"]),
])
def test_the_chord_a_pattern_is_given_voices_it_as_its_span_does (build: typing.Callable[[], typing.Any]) -> None:

	"""Whatever decoration a span carries arrives intact — the span does the voicing."""

	for index in (0, 1):
		span = _span(build(), index)

		assert _injected(span).tones(60) == span.tones(60)


def test_a_slash_chord_is_not_a_plain_triad () -> None:

	"""The case from the review: C/G played C E G, and said C/G while it did."""

	span = _span(subsequence.progression(["C", "F"]).over("G").inversions(1).spread("open"))
	chord = _injected(span)

	assert chord.name() == "C/G"
	assert chord.tones(60) == [43, 55, 64, 72]
	assert chord.tones(60) != [60, 64, 67]


def test_count_still_cycles_the_voicing_into_higher_octaves () -> None:

	"""count= is the arpeggiator's contract, and it now cycles the decorated voicing."""

	span = _span(subsequence.progression(["C", "F"]).over("G"))

	assert _injected(span).tones(60, count = 6) == span.tones(60, count = 6)


# ---------------------------------------------------------------------------
# The bass a bass line is given
# ---------------------------------------------------------------------------

def test_a_slash_bass_is_the_bass () -> None:

	"""C/G gives a bass line G, not C — that is what the slash is for."""

	span = _span(subsequence.progression(["C", "F"]).over("G"))
	chord = _injected(span)

	assert chord.bass_note(60) == 43			# G2, an octave under the voicing's own G
	assert chord.bass_note(60) == subsequence.progressions.DecoratedChord(span).bass_note(60)


def test_a_plain_chord_still_gives_its_root_an_octave_down () -> None:

	"""Nothing changes where there is no slash: C gives C, an octave below."""

	span = _span(subsequence.progression(["C", "F"]))

	assert _injected(span).bass_note(60) == 48


def test_an_inverted_chord_still_gives_its_root_as_the_bass () -> None:

	"""An inversion is a voicing choice for the pad — the bass line keeps the root.

	Am in second inversion voices E A C, so the *lowest voiced note* is an E.
	The bass is still the A, which is why this asks the chord rather than
	reading the bottom of the voicing.
	"""

	span = _span(subsequence.progression(["Am", "F"]).inversions(2))
	chord = _injected(span)

	assert chord.tones(60)[0] % 12 == 4					# the voicing starts on E
	assert chord.bass_note(60) % 12 == 9					# the bass is the A
	assert chord.bass_note(60) == subsequence.progressions.DecoratedChord(span).bass_note(60)


# ---------------------------------------------------------------------------
# A PitchSet, which has no root at all
# ---------------------------------------------------------------------------

def test_a_pitch_set_section_sounds () -> None:

	"""It raised AttributeError on root_note every bar, so the part was silent."""

	span = _span(subsequence.progression([subsequence.progressions.PitchSet([60, 65, 70])]))
	chord = _injected(span)

	assert chord.tones(60) == [60, 65, 70]
	assert chord.root_midi(60) == 60
	assert chord.bass_note(60) == 48


def test_a_pitch_set_is_left_where_it_is_under_voice_leading () -> None:

	"""Its pitches are absolute: the register was chosen when the pitches were.

	The state is primed with a chord two octaves up first, because leading a
	*first* chord returns root position anyway — which is the pitch set
	unchanged, and would have passed whatever the code did.
	"""

	state = subsequence.voicings.VoiceLeadingState()
	high = subsequence.progression(["C"]).spans[0].chord

	subsequence.composition._InjectedChord(high, voice_leading_state = state).tones(84)

	span = _span(subsequence.progression([subsequence.progressions.PitchSet([60, 65, 70])]))
	chord = subsequence.composition._InjectedChord(span.chord, voice_leading_state = state)

	assert chord.tones(60) == [60, 65, 70]


# ---------------------------------------------------------------------------
# Voice leading: every voice, the slash note among them (decision 7 of #2991)
# ---------------------------------------------------------------------------

def test_an_undecorated_chord_voices_as_it_always_did_under_leading () -> None:

	"""The regression pin: plain triads lead exactly as before the change."""

	progression = subsequence.progression(["C", "F", "G", "C"])
	chord = subsequence.composition._InjectedChord(
		progression.spans[0].chord,
		voice_leading_state = subsequence.voicings.VoiceLeadingState(),
	)

	state = chord._voice_leading_state
	voiced = [
		subsequence.composition._InjectedChord(span.chord, voice_leading_state = state).tones(60)
		for span in progression.spans
	]

	assert voiced == [[60, 64, 67], [60, 65, 69], [59, 62, 67], [60, 64, 67]]


def test_under_voice_leading_the_slash_note_may_move_inward () -> None:

	"""Simon's call: the slash note joins the pool rather than being pinned lowest."""

	pedal = subsequence.progression(["C", "F", "G", "Am"]).over("D")
	state = subsequence.voicings.VoiceLeadingState()

	led = [
		subsequence.composition._InjectedChord(
			subsequence.progressions.DecoratedChord(span),
			voice_leading_state = state,
		).tones(60)
		for span in pedal.spans
	]

	plain = [subsequence.progressions.DecoratedChord(span).tones(60) for span in pedal.spans]

	assert all(voicing[0] % 12 == 2 for voicing in plain)		# unled, the D is always lowest
	assert any(voicing[0] % 12 != 2 for voicing in led)		# led, it moves inward
	assert all(2 in {pitch % 12 for pitch in voicing} for voicing in led)	# and it is always still there


def test_voice_leading_never_lands_two_voices_on_one_pitch () -> None:

	"""A pedal on a chord tone doubles it at the octave; rotating that collided."""

	pedal = subsequence.progression(["C", "F", "G", "Am"]).over("D")
	state = subsequence.voicings.VoiceLeadingState()

	for span in pedal.spans:
		voicing = subsequence.composition._InjectedChord(
			subsequence.progressions.DecoratedChord(span),
			voice_leading_state = state,
		).tones(60)

		assert len(set(voicing)) == len(voicing), f"{span.label()} voiced {voicing}"


# ---------------------------------------------------------------------------
# End to end, through a render
# ---------------------------------------------------------------------------

def test_a_render_plays_the_slash_bass_it_was_given (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""The pitch classes that reach the file are the span's, slash bass and all."""

	filename = str(tmp_path / "slash.mid")
	composition = subsequence.Composition(output_device = "Dummy MIDI", bpm = 480)

	# C/D, not C/G: a G is already a C chord tone, so a slash that goes
	# missing leaves the same pitch classes behind and proves nothing.
	composition.harmony(progression = subsequence.progression(["C", "F"]).over("D"))

	@composition.pattern(channel = 1, beats = 4)
	def pad (p, chord) -> None:
		for pitch in chord.tones(60):
			p.note(pitch, beat = 0, duration = 4)

	composition.render(bars = 1, filename = filename)

	played = {
		message.note
		for track in mido.MidiFile(filename).tracks
		for message in track
		if not isinstance(message, mido.MetaMessage) and message.type == "note_on" and message.velocity > 0
	}

	assert played == {50, 60, 64, 67}		# D2 under C E G, at the register the span voiced
