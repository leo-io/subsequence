"""A seed reaches the one-shots too, and says so when it arrives too late (#3049).

`trigger()` built with a fresh `random.Random()` — a comment even said so — so
a seeded composition did not render the same file twice. Measured over three
renders of one seeded piece, reading the velocities a triggered
`sequence(velocities=(40, 100))` placed:

    run 1: [89, 43, 73, 87, 59, 56, 67, 100, 95, 89, 74, 58]
    run 2: [70, 89, 67, 42, 71, 45, 42, 55, 95, 76, 73, 68]
    run 3: [45, 64, 91, 43, 98, 61, 42, 55, 75, 51, 53, 41]

Transition fills were already seeded, so the two paths disagreed.

Decision 13 of #2991: seeded per trigger, from the seed, the function's name
and its trigger count. An unseeded composition keeps fresh randomness.

Separately, `harmony()`, `form()` and `freeze()` deal their streams when they
are called, so `comp.seed = 5` afterwards never reaches them — and a piece
reproducible in some parts and not others is worse than either. Nothing can be
un-drawn, so it warns.
"""

import pathlib
import typing
import unittest.mock

import mido
import pytest

import subsequence
import subsequence.composition


def _triggered_velocities (
	tmp_path: pathlib.Path,
	seed: typing.Optional[int],
	run: int,
	bars: int = 4,
) -> typing.List[int]:

	"""Render a piece whose one-shot draws from a velocity range."""

	filename = str(tmp_path / f"run_{run}.mid")
	composition = subsequence.Composition(bpm = 480, seed = seed)

	@composition.pattern(channel = 1, beats = 4)
	def pad (p: typing.Any) -> None:
		p.note(beat = 0, pitch = 36, velocity = 100)

	def fire () -> None:
		composition.trigger(
			lambda t: t.sequence(
				steps = [0, 2, 4, 6, 8],
				pitches = [60, 62, 64, 65, 67],
				velocities = (40, 100),
			),
			channel = 2,
			beats = 4,
		)

	composition.schedule(fire, cycle_beats = 4)
	composition.render(bars = bars, filename = filename)

	return [
		message.velocity
		for track in mido.MidiFile(filename).tracks
		for message in track
		if message.type == "note_on" and message.velocity > 0 and message.note >= 60
	]


def test_a_seeded_piece_triggers_the_same_way_every_time (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""The finding: three renders of one seed gave three different one-shots."""

	runs = [_triggered_velocities(tmp_path, 7, run) for run in range(3)]

	assert runs[0], "no triggered notes were rendered at all — this proves nothing"
	assert runs[0] == runs[1] == runs[2], f"the same seed gave {runs}"


def test_the_one_shot_is_still_random_within_a_run (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""Seeding must not flatten the range it draws from.

	A `trigger_rng` that always returned the same number would satisfy the
	test above perfectly.
	"""

	velocities = _triggered_velocities(tmp_path, 7, 0)

	assert len(set(velocities)) > 3, f"the draw collapsed: {velocities}"
	assert all(40 <= velocity <= 100 for velocity in velocities)


def test_a_different_seed_gives_a_different_one_shot (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""The other half of "seeded": the seed has to matter."""

	one = _triggered_velocities(tmp_path, 7, 0)
	two = _triggered_velocities(tmp_path, 8, 1)

	assert one and two
	assert one != two


def test_an_unseeded_piece_keeps_fresh_randomness (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""Decision 13 says so explicitly, and it is what every other verb does."""

	runs = [_triggered_velocities(tmp_path, None, run) for run in range(3)]

	assert runs[0], "no triggered notes were rendered at all"
	assert not (runs[0] == runs[1] == runs[2]), "an unseeded piece repeated itself exactly"


def test_successive_triggers_differ_from_each_other (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""The stream is named for the trigger COUNT, so the tenth is not the first.

	Without the count, every firing of one function would draw the same
	numbers — a one-shot that sounds identical every bar, which is precisely
	the complaint `scratch()` had under a seed (#2962).
	"""

	velocities = _triggered_velocities(tmp_path, 7, 0, bars = 6)

	assert len(velocities) >= 10, f"too few notes to compare firings: {velocities}"

	first, second = velocities[:5], velocities[5:10]

	assert first != second, f"every firing drew the same numbers: {velocities[:10]}"


def test_adding_a_second_trigger_does_not_move_the_first (tmp_path: pathlib.Path, patch_midi: None) -> None:

	"""What naming the stream for the FUNCTION buys, and it is not "they differ".

	Two triggers differ from each other however the stream is named, because
	the count separates them — an earlier version of this test asserted that
	and passed happily with the name thrown away. The name's real job is that
	each function counts on its own, so adding a trigger somewhere else in
	the piece leaves every existing one sounding exactly as it did.
	"""

	def render (with_second: bool, run: int) -> typing.List[int]:

		filename = str(tmp_path / f"two_{run}.mid")
		composition = subsequence.Composition(bpm = 480, seed = 3)

		@composition.pattern(channel = 1, beats = 4)
		def pad (p: typing.Any) -> None:
			p.note(beat = 0, pitch = 36, velocity = 100)

		def sparkle (t: typing.Any) -> None:
			t.sequence(steps = [0, 2, 4, 6], pitches = [60, 62, 64, 65], velocities = (40, 100))

		def rumble (t: typing.Any) -> None:
			t.sequence(steps = [0, 2], pitches = [36, 38], velocities = (40, 100))

		def fire_sparkle () -> None:
			composition.trigger(sparkle, channel = 2, beats = 4)

		def fire_rumble () -> None:
			composition.trigger(rumble, channel = 3, beats = 4)

		composition.schedule(fire_sparkle, cycle_beats = 4)

		if with_second:
			composition.schedule(fire_rumble, cycle_beats = 4)

		composition.render(bars = 4, filename = filename)

		return [
			message.velocity
			for track in mido.MidiFile(filename).tracks
			for message in track
			if message.type == "note_on" and message.velocity > 0 and message.channel == 1
		]

	alone = render(with_second = False, run = 0)
	beside = render(with_second = True, run = 1)

	assert alone, "the first trigger placed nothing — this proves nothing"
	assert alone == beside, \
		f"adding a second trigger changed the first: {alone} became {beside}"


# ---------------------------------------------------------------------------
# A seed that arrives too late
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("built", ["harmony", "form", "freeze"])
def test_a_seed_set_after_a_subsystem_has_dealt_warns (built: str, patch_midi: None) -> None:

	"""It cannot reach what has already drawn, so it must not look as if it did."""

	composition = subsequence.Composition(bpm = 480, key = "C", scale = "major")

	if built == "harmony":
		composition.harmony(style = "pop_major")
	elif built == "form":
		composition.form([("verse", 2), ("chorus", 2)])
	else:
		composition.harmony(style = "pop_major")
		composition.freeze(4)

	with unittest.mock.patch.object(subsequence.composition.logger, "warning") as warned:
		composition.seed = 5

	said = " ".join(str(call) for call in warned.call_args_list)

	assert warned.called, f"setting a seed after {built}() said nothing"
	assert "seed" in said


def test_the_warning_names_what_it_is_too_late_for (patch_midi: None) -> None:

	"""A warning a musician cannot act on is only half a fix."""

	composition = subsequence.Composition(bpm = 480, key = "C", scale = "major")
	composition.harmony(style = "pop_major")

	with unittest.mock.patch.object(subsequence.composition.logger, "warning") as warned:
		composition.seed = 5

	said = " ".join(str(call) for call in warned.call_args_list)

	assert "harmony()" in said, said
	assert "Composition(" in said, said


def test_a_seed_set_before_anything_is_silent (patch_midi: None) -> None:

	"""The control. Warning on the ordinary case would train people to ignore it."""

	composition = subsequence.Composition(bpm = 480, key = "C", scale = "major")

	with unittest.mock.patch.object(subsequence.composition.logger, "warning") as warned:
		composition.seed = 5

	composition.harmony(style = "pop_major")

	assert not warned.called, f"an ordinary seed warned: {warned.call_args_list}"


def test_clearing_the_seed_is_silent (patch_midi: None) -> None:

	"""`comp.seed = None` asks for fresh randomness; nothing is too late for that."""

	composition = subsequence.Composition(bpm = 480, key = "C", scale = "major", seed = 5)
	composition.harmony(style = "pop_major")

	with unittest.mock.patch.object(subsequence.composition.logger, "warning") as warned:
		composition.seed = None

	assert not warned.called
