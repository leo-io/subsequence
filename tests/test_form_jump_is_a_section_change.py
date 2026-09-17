"""A form jump is a section change: on_section hears it, and transition mutes for the skipped boundary lift (#2800)."""

import asyncio
import pathlib
import threading
import typing

import mido

import subsequence


def _looping_form (composition: subsequence.Composition) -> None:

	"""Sections a, b and c, four bars each, looping."""

	composition.form([("a", 4), ("b", 4), ("c", 4)], loop=True)


def test_on_section_hears_the_section_a_jump_lands_on_before_anything_is_built_there (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Jumped to c from a: c is announced ahead of its first build, and the form then carries on to a and b."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)
	_looping_form(composition)
	log: typing.List[typing.Tuple[str, str]] = []
	composition.on_section(lambda info: log.append(("section", info.name if info else "end")))

	async def jump (p: typing.Any) -> None:
		if p.cycle == 1:
			composition.form_jump("c")

	composition.schedule(jump, cycle_beats=4)

	@composition.pattern(channel=1, beats=4)
	def part (p: typing.Any) -> None:
		log.append(("build", p.section.name))
		p.note(60, beat=0)

	composition.render(bars=12, filename=str(tmp_path / "jump.mid"))

	sections = [name for kind, name in log if kind == "section"]
	first_c_build = log.index(("build", "c"))

	assert sections == ["a", "c", "a", "b"]
	assert log.index(("section", "c")) < first_c_build


def test_a_jump_lifts_the_mutes_a_transition_made_for_the_boundary_it_skipped (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Hats muted in b's last bar for the approach to c; a jump back to a on that bar's downbeat brings them straight back."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)
	_looping_form(composition)
	composition.transition(before="c", mute=["hats"])

	async def jump (p: typing.Any) -> None:
		if p.cycle == 7:
			composition.form_jump("a")

	composition.schedule(jump, cycle_beats=4, reschedule_lookahead=0)

	@composition.pattern(channel=10, beats=4)
	def hats (p: typing.Any) -> None:
		p.note(42, beat=0)

	@composition.pattern(channel=1, beats=4)
	def clock (p: typing.Any) -> None:
		p.note(60, beat=0)

	path = str(tmp_path / "mutes.mid")
	composition.render(bars=14, filename=path)

	now = 0
	bars: typing.Dict[int, typing.Set[int]] = {60: set(), 42: set()}

	for message in mido.MidiFile(path).tracks[0]:
		now += message.time
		if message.type == "note_on" and message.velocity > 0:
			bars[message.note].add(now // 1920)

	assert sorted(bars[60]) == list(range(14))
	assert sorted(bars[42]) == [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13]


def test_a_jump_from_another_thread_is_announced_on_the_clock_s_loop (patch_midi: None) -> None:

	"""The live-coding server and OSC call form_jump off the loop; on_section still runs on the loop's thread."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)
	_looping_form(composition)
	heard: typing.List[typing.Tuple[bool, str]] = []
	done = threading.Event()

	loop = asyncio.new_event_loop()
	clock_thread = threading.Thread(target=loop.run_forever, daemon=True)
	clock_thread.start()

	def on_section (info: typing.Any) -> None:
		heard.append((threading.current_thread() is clock_thread, info.name))
		done.set()

	composition.on_section(on_section)
	composition._sequencer._event_loop = loop
	composition._sequencer.running = True

	try:
		composition.form_jump("c")
		assert done.wait(timeout=5), "the jump was never announced"
	finally:
		composition._sequencer.running = False
		loop.call_soon_threadsafe(loop.stop)
		clock_thread.join(timeout=5)
		loop.close()

	assert heard == [(True, "c")]


def test_a_jump_before_play_announces_nothing_itself (patch_midi: None) -> None:

	"""play() announces the section it starts in, so a jump made first is not announced twice."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)
	_looping_form(composition)
	heard: typing.List[str] = []
	composition.on_section(lambda info: heard.append(info.name))

	composition.form_jump("b")

	assert heard == []
	assert composition.form_state is not None and composition.form_state.get_section_info().name == "b"
