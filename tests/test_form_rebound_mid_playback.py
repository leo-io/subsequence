"""Binding or re-binding form() mid-playback (#3084).

M3 of the 2026-09-19 review: "Re-binding form().  It isn't treated as a
section change: entry detection is keyed on the index alone, on_section stays
silent, transition mutes aren't lifted, and bound chords continue from the old
anchor. ... A form bound for the FIRST time during playback never advances at
all; it stayed at ('verse', 0) for 8 bars."

Two separate faults, and only one of them was where the review put it.

**A first form never advanced** because `_run()` registers clocks only for
sources it can see at play() time, so a form arriving later had no clock at
all.  Measured: `('verse', 0)` for seven bars, `on_section` never fired.  Same
shape as the harmonic clock's H7/#2998, fixed the same way.

**A re-bind stayed silent** because entry detection compares a section index,
and one form's section 0 looks exactly like another's.  Measured: re-binding
during a running `intro` went straight from `intro` to `chorus` in the
`on_section` log — the new form's `verse` was never announced, so a listener
never ran and transition mutes were never lifted.

The verification note's extra claim — "a re-bound form loses its first bar" —
does **NOT** reproduce.  It came from a probe that read the section from a
*scheduled function*, which fires a beat before the bar line, so its bar
labels were off by one.  Read from a pattern's `p.section`, an unfixed tree
gives the re-bound verse exactly the three bars it declares.  These tests
therefore pin the bar counts too, because that is the property a wrong fix
here breaks — and one did, until this was measured properly.
"""

import pathlib
import typing

import pytest

import subsequence


def _sections_per_bar (
	comp: "subsequence.Composition", bars: int, tmp_path: pathlib.Path
) -> typing.List[typing.Tuple[int, typing.Optional[str]]]:

	"""Render; report (bar, section name) as each bar's pattern cycle saw it."""

	seen: typing.List[typing.Tuple[int, typing.Optional[str]]] = []

	@comp.pattern(channel = 1, bars = 1)
	def melody (p: typing.Any) -> None:
		name = None if p.section is None else getattr(p.section, "name", str(p.section))
		seen.append((p.bar, name))
		p.note(pitch = 60, beat = 0, velocity = 100, duration = 1)

	comp.render(bars = bars, filename = str(tmp_path / "f.mid"))

	return seen


def _runs (seen: typing.List[typing.Tuple[int, typing.Optional[str]]]) -> typing.List[typing.Tuple[typing.Optional[str], int]]:

	"""Consecutive runs of the same section, as (name, bar count)."""

	runs: typing.List[typing.List[typing.Any]] = []

	for _bar, name in seen:
		if runs and runs[-1][0] == name:
			runs[-1][1] += 1
		else:
			runs.append([name, 1])

	return [(name, count) for name, count in runs]


# ---------------------------------------------------------------------------
# A FIRST form arriving mid-playback
# ---------------------------------------------------------------------------

def test_a_first_form_bound_mid_playback_advances (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""It stayed at ('verse', 0) for seven bars, because it had no clock."""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 5)
	called: typing.Dict[str, int] = {}

	def watch () -> None:
		beat = comp._sequencer.pulse_count / comp._sequencer.pulses_per_beat
		bar = int(beat // comp.bar_beats) + 1

		if bar == 3 and not called:
			comp.form([("verse", 2), ("chorus", 2), ("bridge", 2)])
			called["bar"] = bar

	comp.schedule(watch, cycle_beats = int(comp.bar_beats))

	seen = _sections_per_bar(comp, 12, tmp_path)

	assert called, "form() was never called — the test proves nothing"

	names = [name for _bar, name in seen if name is not None]
	distinct = sorted(set(names))

	assert distinct == ["bridge", "chorus", "verse"], (
		f"the form did not advance through its sections: saw {distinct}.  "
		f"The whole reading was {seen}"
	)


def test_a_first_form_bound_mid_playback_gives_each_section_its_bars (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""Advancing is not enough — each section must get the bars it declares."""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 5)
	called: typing.Dict[str, int] = {}

	def watch () -> None:
		beat = comp._sequencer.pulse_count / comp._sequencer.pulses_per_beat
		bar = int(beat // comp.bar_beats) + 1

		if bar == 3 and not called:
			comp.form([("verse", 2), ("chorus", 2), ("bridge", 2)])
			called["bar"] = bar

	comp.schedule(watch, cycle_beats = int(comp.bar_beats))

	seen = _sections_per_bar(comp, 12, tmp_path)
	played = [(name, count) for name, count in _runs(seen) if name is not None]

	assert played == [("verse", 2), ("chorus", 2), ("bridge", 2)], (
		f"the sections did not get their declared bars: {played}.  "
		f"The whole reading was {seen}"
	)


def test_a_first_form_bound_mid_playback_announces_its_sections (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""on_section never fired at all, because the clock was never registered."""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 5)
	entered: typing.List[typing.Optional[str]] = []
	called: typing.Dict[str, int] = {}

	@comp.on_section
	def _entered (name: typing.Any, index: typing.Any = None, **kw: typing.Any) -> None:
		entered.append(None if name is None else getattr(name, "name", str(name)))

	def watch () -> None:
		beat = comp._sequencer.pulse_count / comp._sequencer.pulses_per_beat
		bar = int(beat // comp.bar_beats) + 1

		if bar == 3 and not called:
			comp.form([("verse", 2), ("chorus", 2)])
			called["bar"] = bar

	comp.schedule(watch, cycle_beats = int(comp.bar_beats))

	_sections_per_bar(comp, 10, tmp_path)

	assert called, "form() was never called — the test proves nothing"

	announced = [name for name in entered if name is not None]

	assert "verse" in announced and "chorus" in announced, (
		f"on_section did not announce the new form's sections: {entered}"
	)


# ---------------------------------------------------------------------------
# RE-binding a form that is already playing
# ---------------------------------------------------------------------------

def _rebind_run (
	comp: "subsequence.Composition", tmp_path: pathlib.Path
) -> typing.Tuple[typing.List[typing.Optional[str]], typing.List[typing.Tuple[int, typing.Optional[str]]]]:

	"""intro is playing; a verse/chorus form is bound during bar 4."""

	entered: typing.List[typing.Optional[str]] = []
	called: typing.Dict[str, int] = {}

	@comp.on_section
	def _entered (name: typing.Any, index: typing.Any = None, **kw: typing.Any) -> None:
		entered.append(None if name is None else getattr(name, "name", str(name)))

	def watch () -> None:
		beat = comp._sequencer.pulse_count / comp._sequencer.pulses_per_beat
		bar = int(beat // comp.bar_beats) + 1

		if bar == 4 and not called:
			comp.form([("verse", 3), ("chorus", 3)])
			called["bar"] = bar

	comp.schedule(watch, cycle_beats = int(comp.bar_beats))

	seen = _sections_per_bar(comp, 12, tmp_path)

	assert called, "form() was never re-bound — the test proves nothing"

	return entered, seen


def test_a_re_bind_announces_the_new_form_s_first_section (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""The review's real fault: intro went straight to chorus, verse unannounced.

	Entry detection compares a section index, and the old form's section 0
	looks exactly like the new form's section 0 — so the one entry that
	matters, into the section the musician just asked for, was the one that
	went unreported.
	"""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 5)
	comp.form([("intro", 8)])

	entered, seen = _rebind_run(comp, tmp_path)

	assert "verse" in entered, (
		f"the re-bound form's first section was never announced: {entered}.  "
		f"The sections played were {_runs(seen)}"
	)


def test_a_re_bind_still_gives_each_section_its_declared_bars (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""The guard that caught a wrong fix.

	Treating the swap as "the new form has not started yet" and skipping its
	advance gives the first section a bar too many — measured at 4 where 3
	were declared.  The new state is read through a getter from the moment it
	is bound, so it must advance normally from there.
	"""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 5)
	comp.form([("intro", 8)])

	_entered, seen = _rebind_run(comp, tmp_path)

	played = [(name, count) for name, count in _runs(seen) if name is not None]
	after_intro = [(name, count) for name, count in played if name != "intro"]

	assert after_intro == [("verse", 3), ("chorus", 3)], (
		f"the re-bound sections did not get their declared bars: "
		f"{after_intro}.  The whole reading was {seen}"
	)


def test_a_re_bind_is_a_section_change_for_the_harmony_clock (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""The harmonic clock keys section entry on a token, not a bare index.

	One form's section 0 and another's are both index 0, so an int cannot
	tell them apart, the section anchor is never moved, and the new section's
	chords are walked from the OLD section's start.

	The verse takes THREE chords on purpose.  With two, the stale anchor's
	offset (16 beats, against an 8-beat progression) divides exactly and the
	walk lands on the first chord anyway — the test passed on an unfixed tree
	and pinned nothing.  Sixteen against twelve leaves a remainder of four, so
	an unmoved anchor starts the verse on its SECOND chord.
	"""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 5)
	comp.form([("intro", 8)])
	comp.section_chords("intro", ["C"])
	comp.section_chords("verse", ["Am", "Dm", "G"])

	chords: typing.List[typing.Tuple[int, typing.Optional[str]]] = []
	called: typing.Dict[str, int] = {}

	@comp.pattern(channel = 1, bars = 1)
	def melody (p: typing.Any) -> None:
		chord = None if p.harmony is None or p.harmony.chord is None else p.harmony.chord.name()
		chords.append((p.bar, chord))
		p.note(pitch = 60, beat = 0, velocity = 100, duration = 1)

	def watch () -> None:
		beat = comp._sequencer.pulse_count / comp._sequencer.pulses_per_beat
		bar = int(beat // comp.bar_beats) + 1

		if bar == 4 and not called:
			comp.form([("verse", 4)])
			called["bar"] = bar

	comp.schedule(watch, cycle_beats = int(comp.bar_beats))

	comp.render(bars = 10, filename = str(tmp_path / "f.mid"))

	assert called, "form() was never re-bound — the test proves nothing"

	# The verse's own chords must start at the bar the verse starts at, from
	# the top of its progression.
	intro_bars = sum(1 for _bar, chord in chords if chord == "C")
	verse_start = intro_bars

	assert verse_start < len(chords), f"the verse never played: {chords}"

	walked = [chord for _bar, chord in chords[verse_start:verse_start + 3]]

	assert walked == ["Am", "Dm", "G"], (
		f"the re-bound section's progression was walked from the OLD "
		f"section's anchor: it played {walked} where Am, Dm, G were due.  "
		f"The whole reading was {chords}"
	)
