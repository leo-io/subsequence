"""A quantized one-shot is built against the chord it lands on (#3087).

M3 of the 2026-09-19 review: "Quantized trigger().  trigger(chord=True,
quantize=…) is built against the chord at call time, not the chord sounding
where the one-shot plays; every call in the test was a bar off."

`start_pulse` was already computed before the build — with a comment saying it
is done there so the builder knows where on the song's timeline it will play
(#2788, for grooves).  The harmony was the one thing still reading the
playhead.  Measured before the fix, firing near the end of each bar quantized
to the next: **4 of 4** one-shots were handed the chord of the bar *before*
their own.

The same anchor carries `p.harmony`, so ChordTone and Approach inside a
one-shot resolve where it sounds too.
"""

import pathlib
import typing

import pytest

import subsequence


PROGRESSION = ["C", "F", "G", "Am", "Dm", "E", "C", "F"]


def _chord_of_bar (bar: int) -> str:
	"""A chord a bar, from a bound progression: bar 1 is C, bar 2 is F, …"""
	return PROGRESSION[(bar - 1) % len(PROGRESSION)]


def _fire_each_bar (
	comp: "subsequence.Composition",
	quantize: float,
	bars: int,
	tmp_path: pathlib.Path,
	first_bar: int = 2,
	last_bar: int = 5,
) -> typing.List[typing.Tuple[int, typing.Optional[str]]]:

	"""Fire a one-shot near the end of each bar; report (landing bar, chord handed)."""

	handed: typing.List[typing.Tuple[int, typing.Optional[str]]] = []
	lands: typing.List[int] = []

	def one_shot (p: typing.Any, chord: typing.Any = None) -> None:
		handed.append((lands[len(handed)], None if chord is None else chord.name()))
		p.note(pitch = 60, beat = 0, velocity = 100, duration = 1)

	def watch () -> None:
		beat = comp._sequencer.pulse_count / comp._sequencer.pulses_per_beat
		bar = int(beat // comp.bar_beats) + 1

		if first_bar <= bar <= last_bar:
			# Quantized to the next bar, so it sounds in bar + 1.
			lands.append(bar + 1)
			comp.trigger(one_shot, channel = 1, beats = 1, quantize = quantize, chord = True)

	comp.schedule(watch, cycle_beats = int(comp.bar_beats))
	comp.render(bars = bars, filename = str(tmp_path / "t.mid"))

	return handed


def test_a_bar_quantized_one_shot_gets_the_chord_of_the_bar_it_sounds_in (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""The review's case, with the chord of every bar known in advance."""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 5)
	comp.harmony(progression = subsequence.progression(PROGRESSION))

	handed = _fire_each_bar(comp, quantize = comp.bar_beats, bars = 8, tmp_path = tmp_path)

	assert handed, "no one-shot was ever built — the test proves nothing"

	wrong = [
		(bar, got, _chord_of_bar(bar))
		for bar, got in handed
		if got != _chord_of_bar(bar)
	]

	assert not wrong, (
		f"{len(wrong)} of {len(handed)} one-shots were built against the wrong "
		f"chord (landing bar, handed, should be): {wrong}"
	)


def test_an_immediate_one_shot_still_gets_the_chord_sounding_now (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""The guard: quantize=0 lands now, so "where it lands" is the playhead."""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 5)
	comp.harmony(progression = subsequence.progression(PROGRESSION))

	handed = _fire_each_bar(comp, quantize = 0, bars = 8, tmp_path = tmp_path)

	assert handed, "no one-shot was ever built — the test proves nothing"

	# Fired near the end of bar N and landing immediately, it sounds in bar N.
	wrong = [
		(bar, got, _chord_of_bar(bar - 1))
		for bar, got in handed
		if got != _chord_of_bar(bar - 1)
	]

	assert not wrong, (
		f"an immediate one-shot was built against the wrong chord "
		f"(landing bar, handed, should be): {wrong}"
	)


def test_the_harmony_view_is_anchored_where_the_one_shot_lands (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""p.harmony carries the same anchor, so ChordTone and Approach follow it.

	Asserting only the injected `chord` would leave the view reading the
	playhead and nobody would notice until a triggered approach tone resolved
	to the wrong chord.
	"""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 5)
	comp.harmony(progression = subsequence.progression(PROGRESSION))

	seen: typing.List[typing.Tuple[int, typing.Optional[str], typing.Optional[str]]] = []
	lands: typing.List[int] = []

	def one_shot (p: typing.Any, chord: typing.Any = None) -> None:
		view = None if p.harmony is None or p.harmony.chord is None else p.harmony.chord.name()
		seen.append((lands[len(seen)], view, None if chord is None else chord.name()))
		p.note(pitch = 60, beat = 0, velocity = 100, duration = 1)

	def watch () -> None:
		beat = comp._sequencer.pulse_count / comp._sequencer.pulses_per_beat
		bar = int(beat // comp.bar_beats) + 1

		if 2 <= bar <= 5:
			lands.append(bar + 1)
			comp.trigger(one_shot, channel = 1, beats = 1,
			             quantize = comp.bar_beats, chord = True)

	comp.schedule(watch, cycle_beats = int(comp.bar_beats))
	comp.render(bars = 8, filename = str(tmp_path / "t.mid"))

	assert seen, "no one-shot was ever built — the test proves nothing"

	wrong = [
		(bar, view, _chord_of_bar(bar))
		for bar, view, _injected in seen
		if view != _chord_of_bar(bar)
	]

	assert not wrong, (
		f"p.harmony was anchored at the call, not the landing "
		f"(landing bar, view said, should be): {wrong}"
	)

	# And the two agree with each other, which is the whole point.
	disagreeing = [(bar, view, injected) for bar, view, injected in seen if view != injected]

	assert not disagreeing, (
		f"the injected chord and p.harmony disagree: {disagreeing}"
	)


def test_a_beat_quantized_one_shot_follows_a_faster_harmonic_rhythm (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""A chord every two beats, quantized to the beat: the landing beat decides.

	With one chord a bar and bar quantization, the landing chord is always the
	NEXT one, so an off-by-one-boundary fix would pass.  A two-beat harmonic
	rhythm with beat quantization puts the landing inside the same chord as
	often as not, and only reading the actual landing beat gets both right.
	"""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 5)
	comp.harmony(progression = subsequence.progression(["C", "F", "G", "Am"], beats = 2))

	seen: typing.List[typing.Tuple[float, typing.Optional[str]]] = []
	landing_beats: typing.List[float] = []

	def one_shot (p: typing.Any, chord: typing.Any = None) -> None:
		seen.append((landing_beats[len(seen)], None if chord is None else chord.name()))
		p.note(pitch = 60, beat = 0, velocity = 100, duration = 1)

	def watch () -> None:
		pulse = comp._sequencer.pulse_count
		per_beat = comp._sequencer.pulses_per_beat
		landing_pulse = ((pulse // per_beat) + 1) * per_beat
		landing_beats.append(landing_pulse / per_beat)
		comp.trigger(one_shot, channel = 1, beats = 1, quantize = 1, chord = True)

	comp.schedule(watch, cycle_beats = 1)
	comp.render(bars = 4, filename = str(tmp_path / "t.mid"))

	assert seen, "no one-shot was ever built — the test proves nothing"

	expected = ["C", "F", "G", "Am"]

	wrong = [
		(beat, got, expected[int(beat // 2) % 4])
		for beat, got in seen
		if got != expected[int(beat // 2) % 4]
	]

	assert not wrong, (
		f"{len(wrong)} of {len(seen)} one-shots missed the chord at their "
		f"landing beat (beat, handed, should be): {wrong}"
	)
