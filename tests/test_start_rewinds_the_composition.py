"""A MIDI Start rewinds the whole composition, not only the transport (#3089).

Simon's call, 2026-09-21.  The MIDI specification is the argument: Start means
*start at the beginning of the song*, and Continue is the message that resumes
where a Stop left off — which is what a DAW does too.

Before this, #3053 put every part back on cycle 0 and left the harmony and the
form where they were, so a Start was heard as the piece from the top played
over whatever chord happened to be sounding, in whatever section it had
reached.  Measured: a piece four bars into a looping verse/chorus/bridge form
stayed in `bridge` on `Dm`.

Two halves, tested where each lives.  The Sequencer knows nothing about form
or harmony, so it asks through `on_restart`; the Composition answers.

Note for anyone extending this: do NOT drive `_restart_from_the_top()` from
inside a `render()`.  A render has no external transport, so the restart puts
`pulse_count` back to 0 while the render's own bar counter carries on, and
every reading after that is of a state no real session can reach.  The first
probe for this ticket did exactly that and reported nonsense.
"""

import asyncio
import pathlib
import typing

import pytest

import subsequence
import subsequence.form_state
import subsequence.sequencer


# ---------------------------------------------------------------------------
# The Sequencer's half: it asks, and it asks at the right moment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_restart_asks_the_composition_to_rewind (patch_midi: None) -> None:

	"""The hook is awaited on a Start."""

	seq = subsequence.sequencer.Sequencer(output_device_name = "Dummy MIDI", initial_bpm = 120)

	asked: typing.List[str] = []

	async def rewind () -> None:
		asked.append("asked")

	seq.on_restart = rewind

	# Past the first-Start guard: something has played.
	seq.pulse_count = 480
	seq.current_bar = 4

	await seq._restart_from_the_top()

	assert asked == ["asked"], "the restart never asked the composition to rewind"


@pytest.mark.asyncio
async def test_the_rewind_happens_before_the_parts_are_re_anchored (patch_midi: None) -> None:

	"""Order matters: the clocks are re-placed around an already-rewound piece.

	Re-anchoring first would schedule the harmonic clock around the OLD
	position and then move the composition underneath it.
	"""

	seq = subsequence.sequencer.Sequencer(output_device_name = "Dummy MIDI", initial_bpm = 120)

	order: typing.List[str] = []

	async def rewind () -> None:
		order.append("rewound")

	real_reanchor = seq._reanchor_on_cycle_zero

	async def watched_reanchor () -> None:
		order.append("re-anchored")
		await real_reanchor()

	seq.on_restart = rewind
	seq._reanchor_on_cycle_zero = watched_reanchor		# type: ignore[method-assign]

	seq.pulse_count = 480
	seq.current_bar = 4

	await seq._restart_from_the_top()

	assert order == ["rewound", "re-anchored"], f"wrong order: {order}"


@pytest.mark.asyncio
async def test_a_bare_sequencer_restarts_with_no_hook (patch_midi: None) -> None:

	"""The guard: a Sequencer without a Composition has nothing to rewind."""

	seq = subsequence.sequencer.Sequencer(output_device_name = "Dummy MIDI", initial_bpm = 120)

	assert seq.on_restart is None

	seq.pulse_count = 480
	seq.current_bar = 4

	await seq._restart_from_the_top()		# must not raise

	assert seq.pulse_count == 0


# ---------------------------------------------------------------------------
# The Composition's half: what actually goes back
# ---------------------------------------------------------------------------

def _advance_then_rewind (
	comp: "subsequence.Composition",
	tmp_path: pathlib.Path,
	rewind_at_bar: int = 5,
	bars: int = 8,
) -> typing.Dict[str, typing.Dict[str, typing.Any]]:

	"""Render far enough to leave the first section, then rewind; read either side."""

	readings: typing.Dict[str, typing.Dict[str, typing.Any]] = {}

	def read (label: str) -> None:
		info = comp._form_state.get_section_info() if comp._form_state else None
		hs = comp._harmonic_state
		readings[label] = {
			"section": None if info is None else info.name,
			"section_bar": None if info is None else info.bar,
			"chord": None if hs is None or hs.current_chord is None else hs.current_chord.name(),
			"history": 0 if hs is None else len(hs.history),
		}

	@comp.pattern(channel = 1, bars = 1)
	def melody (p: typing.Any) -> None:
		p.note(pitch = 60, beat = 0, velocity = 100, duration = 1)

	async def watch () -> None:
		beat = comp._sequencer.pulse_count / comp._sequencer.pulses_per_beat
		bar = int(beat // comp.bar_beats) + 1

		if bar == rewind_at_bar and "before" not in readings:
			read("before")
			await comp._rewind_to_the_top()
			read("after")

	comp.schedule(watch, cycle_beats = int(comp.bar_beats))
	comp.render(bars = bars, filename = str(tmp_path / "s.mid"))

	assert "before" in readings, "the rewind point was never reached"
	assert "after" in readings, "the rewind never ran"

	return readings


def test_a_rewind_puts_the_form_back_to_its_first_section (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""bridge, bar 1 -> verse, bar 0."""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 5)
	comp.form([("verse", 2), ("chorus", 2), ("bridge", 2)], at_end = "loop")
	comp.section_chords("verse", ["C", "F"])
	comp.section_chords("chorus", ["Am", "G"])
	comp.section_chords("bridge", ["Dm", "E"])

	readings = _advance_then_rewind(comp, tmp_path)

	assert readings["before"]["section"] != "verse", (
		f"the piece never left its first section, so the test proves nothing: "
		f"{readings['before']}"
	)

	assert readings["after"]["section"] == "verse", (
		f"the form did not go back to its first section: {readings['after']}"
	)
	assert readings["after"]["section_bar"] == 0, (
		f"the form went back to the right section but not to its first bar: "
		f"{readings['after']}"
	)


def test_a_rewind_puts_a_live_harmony_back_to_the_tonic (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""The engine's chord and its history both go back.

	Leaving the history behind would have the walk's next step weighted by
	chords from before the Start — the piece would open on its own tonic and
	then move as though it were mid-phrase.
	"""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 5)
	comp.form([("verse", 4), ("chorus", 4)], at_end = "loop")
	comp.harmony(style = "functional_major")

	readings = _advance_then_rewind(comp, tmp_path, rewind_at_bar = 6, bars = 10)

	assert readings["before"]["history"] > 0, (
		"the engine never walked anywhere, so the test proves nothing"
	)

	assert readings["after"]["chord"] == "C", (
		f"the harmony did not go back to the tonic: {readings['after']}"
	)
	assert readings["after"]["history"] == 0, (
		f"the walk kept its history across the Start: {readings['after']}"
	)


def test_a_rewind_replays_the_same_seeded_path (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""A restart is the same piece again, not a different arrangement.

	The form is rebuilt on the same stream salt, so a seeded graph walks the
	path it walked the first time.  Rebuilding on a fresh salt would re-deal
	the piece on every Start, which is not what "from the top" means.

	This walks the rebuilt state directly rather than through a render.  Two
	earlier attempts compared rendered bars either side of the rewind and were
	both defeated by the lookahead: the rewind lands partway through a bar, so
	the seam falls where no fixed index finds it, and after a rewind the two
	runs legitimately diverge anyway — one replays the opening while the other
	carries on.  The claim is about which stream the rebuild uses, and that is
	what this asks.

	The graph BRANCHES at every section on purpose.  One outgoing edge per
	node walks the same path whatever the RNG does, so the salt could not
	matter — which is what the break harness reported when it was first
	written that way.  Measured here: the salt first changes anything at the
	THIRD section, so a shorter walk would prove nothing either.
	"""

	graph = {
		"verse": (2, [("chorus", 1), ("bridge", 1)]),
		"chorus": (2, [("verse", 1), ("bridge", 1)]),
		"bridge": (2, [("verse", 1), ("chorus", 1)]),
	}

	def walk (state: "subsequence.form_state.FormState", sections: int = 6) -> typing.List[typing.Optional[str]]:
		"""The section names this state enters, in order."""
		seen: typing.List[typing.Optional[str]] = []
		for _ in range(sections * 2):			# two bars a section
			info = state.get_section_info()
			name = None if info is None else info.name
			if not seen or seen[-1] != name:
				seen.append(name)
			state.advance()
		return seen

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 5)
	comp.form(graph, start = "verse")

	# What the piece plays from its opening, on the salt form() used.
	reference = walk(
		subsequence.form_state.FormState(
			graph, start = "verse", rng = comp._stream("form:1"), at_end = "stop"
		)
	)

	assert len(reference) >= 3, (
		f"the walk did not reach a third section, where the seed first "
		f"decides anything: {reference}"
	)

	# Move the live form somewhere else entirely, then rewind.
	for _ in range(7):
		comp._form_state.advance()

	moved = comp._form_state.get_section_info()

	assert moved is not None and moved.name != "verse" or moved.bar != 0, (
		"the form never left its opening, so the test proves nothing"
	)

	asyncio.run(comp._rewind_to_the_top())

	after = walk(comp._form_state)

	assert after == reference, (
		f"the rewound form walked a different path from the one the piece "
		f"opens with: {after} against {reference}"
	)


def test_a_composition_registers_the_hook_when_it_plays (
	patch_midi: None, tmp_path: pathlib.Path
) -> None:

	"""Without this, everything above is unreachable from a real MIDI Start."""

	comp = subsequence.Composition(key = "C", bpm = 480, seed = 5)
	comp.form([("verse", 2)])

	registered: typing.List[bool] = []

	@comp.pattern(channel = 1, bars = 1)
	def melody (p: typing.Any) -> None:
		registered.append(comp._sequencer.on_restart is not None)
		p.note(pitch = 60, beat = 0, velocity = 100, duration = 1)

	comp.render(bars = 2, filename = str(tmp_path / "h.mid"))

	assert registered and all(registered), (
		"the Sequencer was never told how to rewind the composition"
	)
