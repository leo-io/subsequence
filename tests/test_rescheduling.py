import pathlib
import typing

import pytest

import subsequence
import subsequence.pattern
import subsequence.sequencer


def _has_note_on_at_pulse (events: list[subsequence.sequencer.MidiEvent], pulse: int, note: int) -> bool:

	"""Check whether a note_on event exists at a given pulse."""

	for event in events:

		if event.pulse != pulse:
			continue

		if event.message_type != 'note_on':
			continue

		if event.note != note:
			continue

		return True

	return False


@pytest.mark.asyncio
async def test_reschedule_triggers_and_uses_updated_notes (patch_midi: None) -> None:

	"""Ensure rescheduling triggers at lookahead and uses updated pattern state."""

	sequencer = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", initial_bpm=120)

	class TestPattern (subsequence.pattern.Pattern):

		"""Pattern that changes its notes when rescheduled."""

		def __init__ (self) -> None:

			"""Initialize the test pattern with a short cycle."""

			super().__init__(channel=0, length=4, reschedule_lookahead=1)

			self.reschedule_calls = 0
			self._build(initial=True)


		def _build (self, initial: bool) -> None:

			"""Build either the initial or rescheduled note set."""

			self.steps = {}

			if initial:
				self.add_note(position=0, pitch=60, velocity=100, duration=6)

			else:
				self.add_note(position=12, pitch=61, velocity=100, duration=6)


		def on_reschedule (self) -> None:

			"""Switch to the rescheduled note layout."""

			self.reschedule_calls += 1
			self._build(initial=False)


	pattern = TestPattern()
	length_pulses = pattern.length * sequencer.pulses_per_beat
	lookahead_pulses = pattern.reschedule_lookahead * sequencer.pulses_per_beat
	reschedule_pulse = length_pulses - lookahead_pulses

	await sequencer.schedule_pattern_repeating(pattern, start_pulse=0)

	await sequencer._maybe_reschedule_patterns(reschedule_pulse - 1)
	assert pattern.reschedule_calls == 0

	await sequencer._maybe_reschedule_patterns(reschedule_pulse)
	assert pattern.reschedule_calls == 1

	next_start = length_pulses
	expected_note_pulse = next_start + 12

	events = list(sequencer.event_queue)
	assert _has_note_on_at_pulse(events, expected_note_pulse, 61)


@pytest.mark.asyncio
async def test_reschedule_lookahead_validation (patch_midi: None) -> None:

	"""Invalid lookahead values should raise when scheduling repeating patterns."""

	sequencer = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", initial_bpm=120)
	pattern = subsequence.pattern.Pattern(channel=0, length=2, reschedule_lookahead=3)

	with pytest.raises(ValueError):
		await sequencer.schedule_pattern_repeating(pattern, start_pulse=0)

@pytest.mark.asyncio
async def test_failing_reschedule_is_contained (patch_midi: None) -> None:

	"""A pattern whose rebuild raises must lose its cycle, not kill the clock.

	Regression: the reschedule loop had no containment, so a raising
	on_reschedule() (or a set_length() below the lookahead) propagated up and
	stopped every pattern.
	"""

	sequencer = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", initial_bpm=120)

	class BadPattern (subsequence.pattern.Pattern):

		"""Pattern that shrinks itself below the reschedule lookahead."""

		def __init__ (self) -> None:
			super().__init__(channel=0, length=4, reschedule_lookahead=1)
			self.add_note(position=0, pitch=60, velocity=100, duration=6)

		def on_reschedule (self) -> None:
			# Below the 1-beat lookahead - _get_pattern_timing raises.
			self.length = 0.5

	class GoodPattern (subsequence.pattern.Pattern):

		"""Healthy sibling that must keep rescheduling."""

		def __init__ (self) -> None:
			super().__init__(channel=0, length=4, reschedule_lookahead=1)
			self.reschedule_calls = 0
			self.add_note(position=0, pitch=62, velocity=100, duration=6)

		def on_reschedule (self) -> None:
			self.reschedule_calls += 1

	bad = BadPattern()
	good = GoodPattern()

	await sequencer.schedule_pattern_repeating(bad, start_pulse=0)
	await sequencer.schedule_pattern_repeating(good, start_pulse=0)

	reschedule_pulse = 4 * sequencer.pulses_per_beat - 1 * sequencer.pulses_per_beat

	# Must not raise, and the healthy pattern must still rebuild.
	await sequencer._maybe_reschedule_patterns(reschedule_pulse)

	assert good.reschedule_calls == 1

	# The failing pattern keeps its previous timing and stays in rotation.
	queued = [entry[2].pattern for entry in sequencer.reschedule_queue]
	assert bad in queued


def _spy_on_dispatch (sequencer: subsequence.sequencer.Sequencer) -> typing.List[typing.Tuple[int, subsequence.sequencer.MidiEvent]]:

	"""Record every event the sequencer dispatches, with the pulse it went out on."""

	dispatched: typing.List[typing.Tuple[int, subsequence.sequencer.MidiEvent]] = []
	original = sequencer._dispatch_with_compensation

	def _record (event: subsequence.sequencer.MidiEvent) -> None:
		dispatched.append((sequencer.pulse_count, event))
		original(event)

	sequencer._dispatch_with_compensation = _record  # type: ignore[method-assign]

	return dispatched


@pytest.mark.asyncio
async def test_a_note_on_a_rebuild_pulse_goes_out_before_the_rebuild (patch_midi: None) -> None:

	"""The notes due on a pulse must not wait for a rebuild due on the same pulse.

	With the default one-beat lookahead a one-bar pattern rebuilds on beat 4,
	which is also where a note on every beat lands.  That note was placed by
	the previous rebuild, so nothing the new one does can change it — and
	sending it after the rebuild made it late by the whole rebuild (#2534).
	"""

	sequencer = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", initial_bpm=120)
	dispatched = _spy_on_dispatch(sequencer)
	beat = sequencer.pulses_per_beat

	class FourBeats (subsequence.pattern.Pattern):

		"""A note on every beat, noting what had been sent when each rebuild ran."""

		def __init__ (self) -> None:
			super().__init__(channel=0, length=4, reschedule_lookahead=1)
			self.sent_at_rebuild: typing.List[typing.Tuple[int, typing.List[int]]] = []
			for position in range(4):
				self.add_note(position=position * beat, pitch=60, velocity=100, duration=6)

		def on_reschedule (self) -> None:
			sent = [event.pulse for _, event in dispatched if event.message_type == 'note_on']
			self.sent_at_rebuild.append((sequencer.pulse_count, sent))

	pattern = FourBeats()
	await sequencer.schedule_pattern_repeating(pattern, start_pulse=0)

	for _ in range(2 * 4 * beat):
		await sequencer._advance_pulse()

	rebuild_pulses = [pulse for pulse, _ in pattern.sent_at_rebuild]
	assert rebuild_pulses == [3 * beat, 7 * beat]

	for pulse, sent in pattern.sent_at_rebuild:
		assert pulse in sent, f"the beat-4 note at pulse {pulse} was still waiting when its rebuild ran"


@pytest.mark.parametrize("source", ["zero lookahead", "callback"])
@pytest.mark.asyncio
async def test_what_a_rebuild_places_on_its_own_pulse_still_goes_out_on_that_pulse (patch_midi: None, source: str) -> None:

	"""Dispatching before the rebuild must not push the rebuild's own notes a pulse late.

	A zero lookahead rebuilds on the cycle's first pulse and places that same
	pulse's downbeat; a scheduled callback can place a pattern on the pulse it
	fires on.  Either lands in the queue after the pulse's first dispatch, so
	it must be sent on the same pulse rather than about 20 ms later.
	"""

	sequencer = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", initial_bpm=120)
	dispatched = _spy_on_dispatch(sequencer)
	bar = 4 * sequencer.pulses_per_beat

	if source == "zero lookahead":
		downbeat = subsequence.pattern.Pattern(channel=0, length=4, reschedule_lookahead=0)
		downbeat.add_note(position=0, pitch=60, velocity=100, duration=6)
		await sequencer.schedule_pattern_repeating(downbeat, start_pulse=0)

	else:
		one_shot = subsequence.pattern.Pattern(channel=0, length=4)
		one_shot.add_note(position=0, pitch=60, velocity=100, duration=6)

		async def _place_on_this_pulse (pulse: int) -> None:
			if pulse > 0:
				await sequencer.schedule_pattern(one_shot, pulse)

		await sequencer.schedule_callback_repeating(_place_on_this_pulse, interval_beats=4, start_pulse=0, reschedule_lookahead=0)

	for _ in range(2 * bar + 1):
		await sequencer._advance_pulse()

	note_ons = [(sent_on, event.pulse) for sent_on, event in dispatched if event.message_type == 'note_on']
	later_bars = [(sent_on, due) for sent_on, due in note_ons if due >= bar]

	assert [due for _, due in later_bars] == [bar, 2 * bar]
	assert all(sent_on == due for sent_on, due in later_bars), later_bars


def test_every_event_in_a_composition_goes_out_on_its_own_pulse (patch_midi: None, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:

	"""Across the form, harmony and scheduling machinery, nothing a pulse sends slips to a later one.

	The rebuild step fires composition callbacks, the form and harmonic
	clocks, ``reschedule_pulse`` listeners and every due pattern.  Sending a
	pulse's notes before all of that is only safe if none of it places
	anything on the pulse being processed without it still going out there.
	"""

	dispatched: typing.List[typing.Tuple[int, int, str]] = []
	original = subsequence.sequencer.Sequencer._dispatch_with_compensation

	def _record (self: subsequence.sequencer.Sequencer, event: subsequence.sequencer.MidiEvent) -> None:
		dispatched.append((self.pulse_count, event.pulse, event.message_type))
		original(self, event)

	monkeypatch.setattr(subsequence.sequencer.Sequencer, "_dispatch_with_compensation", _record)

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, key="C", seed=7)
	composition.form([("verse", 2), ("chorus", 2)], loop=True)
	composition.harmony(style="diatonic_major", cycle_beats=4)

	fired: typing.List[int] = []
	composition.schedule(lambda: fired.append(1), cycle_beats=4)
	composition.on_event("reschedule_pulse", lambda pulse, patterns: None)

	@composition.pattern(channel=10, beats=4)
	def default_lookahead (p: typing.Any) -> None:
		p.hit_steps(36, [0, 4, 8, 12, 15])
		p.swing(60)

	@composition.pattern(channel=2, beats=4, reschedule_lookahead=1 / 24)
	def one_pulse_lookahead (p: typing.Any) -> None:
		p.euclidean(62, pulses=5)
		p.randomize(timing=0.05)

	@composition.pattern(channel=1, beats=4, reschedule_lookahead=0)
	def zero_lookahead (p: typing.Any, chord: typing.Any) -> None:
		p.chord(chord, root=60, duration=3.0)

	composition.render(bars=8, filename=str(tmp_path / "order.mid"))

	note_ons = [row for row in dispatched if row[2] == 'note_on']
	assert len(note_ons) > 50 and fired, "the render sent too little to show anything"

	slipped = [row for row in dispatched if row[0] != row[1]]
	assert not slipped, slipped[:5]


@pytest.mark.asyncio
async def test_stop_survives_crashed_loop_task (patch_midi: None) -> None:

	"""stop() must run its cleanup even when the loop task died with an exception.

	Regression: stop() awaited the task unguarded, so a crashed loop aborted
	shutdown before panic / port close / recording save.
	"""

	sequencer = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", initial_bpm=120)

	async def _doomed () -> None:
		raise RuntimeError("loop died")

	sequencer.task = __import__("asyncio").get_event_loop().create_task(_doomed())

	# Must not raise.
	await sequencer.stop()
