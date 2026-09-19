"""Tests for `p.scratch()` — an empty builder sharing this pattern's context.

Two properties carry the whole design.  A scratch must see everything a
generator reads, or a node behaves differently inside a patch than on a
pattern.  And it must **not** draw from the parent's random stream: doing so
would advance it, so the parent's later draws would depend on how many
scratches were made — invisible, and it would quietly break `lock()`'s promise
that a locked pattern realises identically each cycle.
"""

import logging
import random
import typing

import pytest

import subsequence.pattern
import subsequence.pattern_builder
import subsequence.sequencer


def _builder (
	stream_seed: typing.Optional[int] = 12345,
	rng: typing.Optional[random.Random] = None,
	**context: typing.Any,
) -> subsequence.pattern_builder.PatternBuilder:

	"""A PatternBuilder over a bare 4-beat pattern (no MIDI required)."""

	pattern = subsequence.pattern.Pattern(channel=3, length=4, device=2)

	return subsequence.pattern_builder.PatternBuilder(
		pattern, cycle=0, rng=rng or random.Random(7), stream_seed=stream_seed, **context,
	)


# ---------------------------------------------------------------------------
# The stream — the part that would be silently wrong if guessed
# ---------------------------------------------------------------------------

def test_making_scratches_does_not_change_the_parents_draws () -> None:

	"""The property the whole design exists for.

	If a scratch drew from the parent's stream, this pattern's notes would move
	according to how many nodes a patch happened to contain — and `lock()`
	promises identical realisation every cycle, which would then hold only for
	a fixed number of them.
	"""

	def parent_after (scratches: int) -> typing.List[int]:

		builder = _builder()

		for index in range(scratches):
			builder.scratch(f"node_{index}").ghost_fill(42, density=0.6)

		builder.ghost_fill(60, density=0.5)

		return sorted(note.position for note in builder.placed())

	assert parent_after(0) == parent_after(3) == parent_after(10)


def test_the_same_name_draws_the_same_numbers () -> None:

	"""Reproducible: set a seed once at the top and a scratch under it repeats."""

	first = _builder().scratch("hats").ghost_fill(42, density=0.5)
	again = _builder().scratch("hats").ghost_fill(42, density=0.5)

	assert [n.position for n in first.placed()] == [n.position for n in again.placed()]


def test_different_names_draw_differently () -> None:

	"""Two nodes in one patch are two streams, not one shared by accident."""

	builder = _builder()

	hats = builder.scratch("hats").ghost_fill(42, density=0.5)
	perc = builder.scratch("perc").ghost_fill(42, density=0.5)

	assert [n.position for n in hats.placed()] != [n.position for n in perc.placed()]


def test_a_different_composition_seed_gives_a_different_scratch () -> None:

	"""The child hangs off the composition seed, so re-seeding reaches it."""

	one = _builder(stream_seed=12345).scratch("hats").ghost_fill(42, density=0.5)
	two = _builder(stream_seed=999).scratch("hats").ghost_fill(42, density=0.5)

	assert [n.position for n in one.placed()] != [n.position for n in two.placed()]


def test_an_unseeded_composition_gives_an_unseeded_scratch () -> None:

	"""No seed means no reproducibility, here as everywhere else — not a crash."""

	scratch = _builder(stream_seed=None).scratch("hats")

	assert isinstance(scratch.rng, random.Random)
	assert scratch._stream_seed is None


# ---------------------------------------------------------------------------
# The context — everything a generator reads
# ---------------------------------------------------------------------------

def test_a_scratch_carries_the_musical_context () -> None:

	"""A generator must behave the same on a scratch as on the pattern itself."""

	builder = _builder(
		key = "F",
		scale = "dorian",
		bar = 5,
		energy = 0.75,
		time_signature = (7, 8),
		drum_note_map = {"kick": 36},
		data = {"shared": 1},
	)

	scratch = builder.scratch()

	assert scratch.key == "F"
	assert scratch.scale == "dorian"
	assert scratch.bar == 5
	assert scratch.energy == 0.75
	assert scratch.time_signature == (7, 8)
	assert scratch.cycle == builder.cycle
	assert scratch._drum_note_map == {"kick": 36}
	assert scratch.data is builder.data		# the same dict, not a copy


def test_a_scratch_sits_at_the_same_place_in_the_bar () -> None:

	"""Harmony is anchored on the absolute beat axis.

	A scratch starting elsewhere would resolve a degree against a different
	chord than the pattern it is standing in for.
	"""

	builder = _builder()
	builder._pattern._cycle_start_pulse = 384

	assert builder.scratch()._pattern._cycle_start_pulse == 384


def test_a_scratch_matches_the_pattern_it_came_from () -> None:

	"""Same length, channel and device — and empty."""

	builder = _builder()
	scratch = builder.scratch()

	assert scratch._pattern.length == builder._pattern.length
	assert scratch._pattern.channel == builder._pattern.channel
	assert scratch._pattern.device == builder._pattern.device
	assert scratch.placed() == []


def test_what_a_scratch_places_does_not_sound () -> None:

	"""It has its own pattern, so the parent is untouched."""

	builder = _builder()
	builder.hit(36, [0.0, 2.0])

	builder.scratch("hats").euclidean(42, 7)

	assert len(builder.placed()) == 2


def test_a_scratch_can_be_read_back_and_placed () -> None:

	"""The round trip the method exists for: generate, capture, place."""

	builder = _builder()

	layer = builder.scratch("hats").euclidean(42, 5)
	builder.motif(layer.capture(0.0, 4.0))

	assert len(builder.placed()) == 5


def test_a_scratch_of_a_scratch_keeps_deriving () -> None:

	"""Nesting works, and a nested stream is still its own."""

	builder = _builder()
	inner = builder.scratch("outer").scratch("inner")

	assert inner._stream_seed is not None
	assert inner._stream_seed != builder._stream_seed


# ---------------------------------------------------------------------------
# Across cycles: a scratch varies exactly when its parent does (#2962)
# ---------------------------------------------------------------------------

def _cycles (fresh_stream_each_cycle: bool, cycles: int = 4) -> typing.List[typing.Tuple[int, ...]]:

	"""Each cycle's scratch layer, as a pattern rebuilt `cycles` times would place it.

	An unlocked pattern's stream runs on from cycle to cycle, and the parent
	draws from it; a locked one is re-dealt from its seed before every build.
	"""

	stream = random.Random(7)
	layers = []

	for cycle in range(cycles):

		if fresh_stream_each_cycle:
			stream = random.Random(7)

		pattern = subsequence.pattern.Pattern(channel=3, length=4)
		builder = subsequence.pattern_builder.PatternBuilder(pattern, cycle=cycle, rng=stream, stream_seed=12345)
		builder.ghost_fill(60, density=0.5)
		layer = builder.scratch("hats").ghost_fill(42, density=0.5)
		layers.append(tuple(note.position for note in layer.placed()))

	assert all(layers), "a scratch placed nothing"

	return layers


def test_a_scratch_varies_from_cycle_to_cycle_as_its_parent_does () -> None:

	"""Seeded and unlocked, the parent moves every cycle, and so does its scratch."""

	assert len(set(_cycles(fresh_stream_each_cycle=False))) == 4


def test_a_scratch_under_a_locked_pattern_repeats_every_cycle () -> None:

	"""lock() re-deals the stream before each build, and a scratch under it realises identically too."""

	assert len(set(_cycles(fresh_stream_each_cycle=True))) == 1


def test_a_varying_scratch_still_repeats_run_to_run () -> None:

	"""The variation is part of the seed's take: two runs with one seed give the same cycles."""

	assert _cycles(fresh_stream_each_cycle=False) == _cycles(fresh_stream_each_cycle=False)


def _rendered_bars (tmp_path: typing.Any, locked: bool, name: str) -> typing.List[typing.Tuple[int, ...]]:

	"""Each bar's scratch-placed hats, rendered through the engine with a composition seed."""

	import mido
	import subsequence

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, seed=3)

	@composition.pattern(channel=10, beats=4)
	def kit (p: typing.Any) -> None:
		p.ghost_fill(36, density=0.3)
		p.motif(p.scratch("hats").ghost_fill(42, density=0.5).capture(0.0, 4.0))

	if locked:
		composition.lock("kit")

	path = str(tmp_path / f"{name}.mid")
	composition.render(bars=4, filename=path)

	now, bars = 0, [[] for _ in range(4)]

	for message in mido.MidiFile(path).tracks[0]:
		now += message.time
		if message.type == "note_on" and message.velocity > 0 and message.note == 42:
			bars[now // 1920].append(now % 1920)

	assert all(bars), "a bar had no scratch hats"

	return [tuple(bar) for bar in bars]


def test_through_the_engine_a_scratch_moves_with_its_pattern_and_holds_under_lock (patch_midi: None, tmp_path: typing.Any) -> None:

	"""Unlocked, the scratch's hats change bar to bar and repeat run to run; locked, every bar is the same."""

	free = _rendered_bars(tmp_path, locked=False, name="free")

	assert len(set(free)) > 1
	assert free == _rendered_bars(tmp_path, locked=False, name="free-again")
	assert len(set(_rendered_bars(tmp_path, locked=True, name="locked"))) == 1


# ---------------------------------------------------------------------------
# The destinations: a scratch plays where its pattern plays (#2968)
# ---------------------------------------------------------------------------

def _kit_builder () -> subsequence.pattern_builder.PatternBuilder:

	"""A kit on channel 10 whose mirror carries a kit of its own, including a voice this one lacks."""

	pattern = subsequence.pattern.Pattern(
		channel = 9,
		length = 4,
		mirrors = [(0, 10, {"kick": 60, "snare": 62, "clap": 65})],
	)

	return subsequence.pattern_builder.PatternBuilder(
		pattern, cycle=0, rng=random.Random(7), stream_seed=12345,
		drum_note_map = {"kick": 36, "snare": 38},
	)


def test_a_scratch_carries_its_pattern_s_mirrors () -> None:

	"""A generator behaves the same on a scratch as on the pattern, which includes where its voices can sound."""

	parent = _kit_builder()
	scratch = parent.scratch("layer")

	assert scratch._pattern.mirrors == parent._pattern.mirrors


def test_a_voice_only_a_mirror_maps_survives_a_scratch (caplog: pytest.LogCaptureFixture) -> None:

	"""Captured from a scratch and placed, a clap the primary kit lacks still reaches the mirror that has it."""

	parent = _kit_builder()

	with caplog.at_level(logging.WARNING, logger="subsequence.pattern_builder"):
		layer = parent.scratch("layer")
		layer.hit("clap", [0.0], duration=0.25)
		parent.motif(layer.capture(0.0, 4.0))

	placed = [note for pulse in sorted(parent._pattern.steps) for note in parent._pattern.steps[pulse].notes]
	mirror = subsequence.sequencer._MirrorTarget(0, 10, {"kick": 60, "snare": 62, "clap": 65})

	assert [(note.origin, note.primary_unmapped) for note in placed] == [("clap", True)]
	assert subsequence.sequencer._destination_pitch(placed[0], mirror, primary=False) == 65
	assert subsequence.sequencer._destination_pitch(placed[0], mirror, primary=True) is None
	assert "clap" not in caplog.text


def test_a_name_no_destination_maps_is_warned_about_once_across_a_scratch_and_its_pattern (caplog: pytest.LogCaptureFixture) -> None:

	"""One pattern as far as warnings go, and the message names the pattern, not a channel."""

	parent = _kit_builder()
	parent._pattern._builder_fn = lambda p: None
	parent._pattern._builder_fn.__name__ = "drums"

	with caplog.at_level(logging.WARNING, logger="subsequence.pattern_builder"):
		parent.scratch("layer").hit("triangle", [0.0])
		parent.hit("triangle", [1.0])

	warnings = [record.getMessage() for record in caplog.records if "triangle" in record.getMessage()]

	assert len(warnings) == 1
	assert "pattern 'drums'" in warnings[0]
