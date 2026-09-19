"""A live save applies the decorator arguments it changed, from the pattern's next cycle, except the device (#2905)."""

import asyncio
import logging
import pathlib
import typing

import mido
import pytest

import subsequence


def _saved_in_bar_zero (composition: subsequence.Composition, save: typing.Callable[[], None]) -> None:

	"""Make *save* at the lookahead before bar 1, as a watched file's save lands between cycles."""

	def at_the_lookahead (p: typing.Any) -> None:
		if p.cycle == 1:
			save()

	composition.schedule(at_the_lookahead, cycle_beats=4)


def _render (composition: subsequence.Composition, tmp_path: pathlib.Path, bars: int = 4) -> typing.List[typing.Tuple[int, str, int, int]]:

	"""Render and return the file's notes as (tick, kind, note, 1-16 channel)."""

	path = str(tmp_path / "save.mid")
	composition.render(bars=bars, filename=path)

	now = 0
	notes = []

	for message in mido.MidiFile(path).tracks[0]:
		now += message.time
		if message.type in ("note_on", "note_off"):
			kind = "on" if message.type == "note_on" and message.velocity > 0 else "off"
			notes.append((now, kind, message.note, message.channel + 1))

	assert notes, "the render played nothing"

	return notes


def _live () -> subsequence.Composition:

	"""A composition as watch() leaves it: saves hot-swap running patterns."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)
	composition._is_live = True

	return composition


def test_a_save_that_moves_a_part_s_channel_is_heard_from_its_next_cycle_and_releases_its_drone (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Channel 1 to 2 between bars 0 and 1: bar 1 plays on 2, and the drone left on 1 is released as bar 1 starts."""

	composition = _live()

	def part (p: typing.Any) -> None:
		if p.cycle == 0:
			p.drone(40)
		p.note(60, beat=0, duration=1)

	composition.pattern(channel=1, beats=4)(part)
	_saved_in_bar_zero(composition, lambda: composition.pattern(channel=2, beats=4)(part))

	notes = _render(composition, tmp_path)
	onsets = [(tick, channel) for tick, kind, note, channel in notes if kind == "on" and note == 60]

	assert onsets == [(0, 1), (1920, 2), (3840, 2), (5760, 2)]
	assert [(tick, channel) for tick, kind, note, channel in notes if note == 40 and kind == "off"] == [(1920, 1)]


def test_a_save_that_raises_min_energy_gates_the_part_from_its_next_cycle (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""The report's case: min_energy 0.2 raised to 0.9 at energy 0.5 silences the part, where it used to play on."""

	composition = _live()

	def part (p: typing.Any) -> None:
		p.note(60, beat=0, duration=1)

	composition.pattern(channel=1, beats=4, min_energy=0.2)(part)
	_saved_in_bar_zero(composition, lambda: composition.pattern(channel=1, beats=4, min_energy=0.9)(part))

	assert [tick for tick, kind, note, channel in _render(composition, tmp_path) if kind == "on"] == [0]


def test_a_save_that_changes_the_length_plays_the_new_length_from_the_next_cycle (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Four beats to three: bar 0 is whole, and every cycle after it is three beats long."""

	composition = _live()

	def part (p: typing.Any) -> None:
		p.note(60, beat=0, duration=1)

	composition.pattern(channel=1, beats=4)(part)
	_saved_in_bar_zero(composition, lambda: composition.pattern(channel=1, beats=3)(part))

	assert [tick for tick, kind, note, channel in _render(composition, tmp_path) if kind == "on"] == [0, 1920, 3360, 4800, 6240]


def _running (composition: subsequence.Composition, part: typing.Callable[[typing.Any], None], **declared: typing.Any) -> typing.Any:

	"""Declare *part* and build it as play() would, so a second declaration is a save."""

	composition.pattern(**declared)(part)
	running = composition._build_pattern_from_pending(composition._pending_patterns[-1])
	composition._running_patterns[part.__name__] = running

	return running


def test_a_save_keeps_what_the_performance_did_to_an_argument_it_left_alone (patch_midi: None) -> None:

	"""A mirror() made while playing survives a save that does not touch mirrors=, and gives way to one that does."""

	composition = _live()

	def part (p: typing.Any) -> None:
		p.note(60, beat=0)

	running = _running(composition, part, channel=1, beats=4, min_energy=0.2)
	composition.mirror("part", device=0, channel=5)

	composition.pattern(channel=1, beats=4, min_energy=0.3)(part)

	assert running._min_energy == 0.3
	assert [tuple(entry[:2]) for entry in running.mirrors] == [(0, 4)]

	composition.pattern(channel=1, beats=4, min_energy=0.3, mirrors=[(0, 7)])(part)

	assert [tuple(entry[:2]) for entry in running.mirrors] == [(0, 6)]


def test_a_save_that_names_another_device_says_it_waits_for_a_restart (patch_midi: None, caplog: pytest.LogCaptureFixture) -> None:

	"""The device is the one argument a save does not apply, and it says so rather than going quiet."""

	composition = _live()

	def part (p: typing.Any) -> None:
		p.note(60, beat=0)

	running = _running(composition, part, channel=1, beats=4)

	with caplog.at_level(logging.WARNING, logger="subsequence.composition"):
		composition.pattern(channel=1, beats=4, device=1)(part)

	assert running.device == 0
	assert "Pattern 'part' now names a different device, which it moves to when the piece restarts" in caplog.text


def test_a_save_whose_length_its_lookahead_cannot_fit_is_refused_and_changes_nothing (patch_midi: None) -> None:

	"""Half a beat under a one-beat lookahead is refused as a first declaration would be, and the old body and length play on."""

	composition = _live()

	def part (p: typing.Any) -> None:
		p.note(60, beat=0)

	running = _running(composition, part, channel=1, beats=4)
	before = running._builder_fn

	def edited (p: typing.Any) -> None:
		p.note(62, beat=0)

	edited.__name__ = "part"

	with pytest.raises(ValueError, match="cannot exceed"):
		composition.pattern(channel=1, beats=0.5)(edited)

	assert running._builder_fn is before and running.length == 4


def test_unmirror_releases_a_drone_held_on_the_mirror (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""A mirror taken away while it holds a drone releases it as the next cycle starts, where it used to ring on."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)

	def part (p: typing.Any) -> None:
		if p.cycle == 0:
			p.drone(40)

	composition.pattern(channel=1, beats=4, mirrors=[(0, 3)])(part)
	_saved_in_bar_zero(composition, lambda: composition.unmirror("part", device=0, channel=3))

	releases = [(tick, channel) for tick, kind, note, channel in _render(composition, tmp_path) if note == 40 and kind == "off"]

	assert (1920, 3) in releases and (1920, 1) not in releases


def test_a_save_that_changes_a_phrase_part_applies_it_as_for_every_other_declaration (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""phrase_part() saved with a two-bar cycle and a mirror: both are heard from its next cycle, as pattern(), layer() and chords() are (#2961)."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, key="C")
	composition._is_live = True
	composition.section_motifs("verse", subsequence.motif([1, 2, 3, 4, 5, 6, 7, 8]), part="lead")
	composition.form([("verse", 16)], loop=True)
	composition.phrase_part(channel=4, part="lead", beats=4)

	def save () -> None:
		# A save's reload starts from no declared names, so the part keeps its own.
		composition._declared_names = set()
		composition.phrase_part(channel=4, part="lead", beats=8, mirrors=[(0, 5)])

	_saved_in_bar_zero(composition, save)

	notes = _render(composition, tmp_path)
	running = [pattern for name, pattern in composition._running_patterns.items() if name.startswith("phrase@lead")]

	assert len(running) == 1 and running[0].length == 8
	assert {channel for tick, kind, note, channel in notes if kind == "on" and tick < 1920} == {4}
	assert {channel for tick, kind, note, channel in notes if kind == "on" and tick >= 1920} == {4, 5}


@pytest.mark.asyncio
async def test_a_reloaded_source_s_phrase_part_takes_its_new_length_and_mirrors (patch_midi: None) -> None:

	"""Through load_patterns(), the path watch() takes: the running phrase part is re-declared, not duplicated."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, key="C")
	source = (
		"composition.section_motifs('verse', subsequence.motif([1, 2, 3, 4]), part='lead')\n"
		"composition.phrase_part(channel=4, part='lead', beats={beats}{mirrors})\n"
	)

	composition.load_patterns(source.format(beats=4, mirrors=""), source_label="song")
	composition._sequencer._event_loop = asyncio.get_event_loop()
	await composition._activate_new_pending_patterns()

	await asyncio.to_thread(composition.load_patterns, source.format(beats=8, mirrors=", mirrors=[(0, 5)]"), "song")

	running = [pattern for name, pattern in composition._running_patterns.items() if name.startswith("phrase@lead")]

	assert len(running) == 1
	assert running[0].length == 8
	assert running[0].mirrors == [(0, 4)]
	assert not composition._pending_patterns
