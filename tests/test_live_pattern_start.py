"""A part added mid-flight comes in on the grid, not where the save landed (#3000).

New patterns were anchored at whatever pulse the save happened to reach the
engine, and the sequencer repeated them from there — so a four-beat snare added
at beat 5 played on beat-in-bar 1 for the rest of the performance, and a chord
part added at beat k clashed with the harmony on k beats of every bar.

Decision 4 of #2991: the start is the next whole multiple of the pattern's own
length on the song's timeline, and a boundary already inside the pattern's
lookahead is skipped for the one after.
"""

import asyncio
import typing

import pytest

import subsequence
import subsequence.composition
import subsequence.constants


PPQ = subsequence.constants.MIDI_QUARTER_NOTE


def _composition () -> subsequence.Composition:

	"""A composition whose sequencer is parked, ready to graduate patterns."""

	return subsequence.Composition(bpm = 120, output_device = "Dummy MIDI")


def _pending (composition: subsequence.Composition, source: str) -> typing.Any:

	"""Declare a pattern from source and hand back its pending registration."""

	composition.load_patterns(source)

	return composition._pending_patterns[-1]


# ---------------------------------------------------------------------------
# The rule itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("beats, now, expected", [
	(4.0, 0, 96),				# at the very top, the next bar
	(4.0, 120, 192),			# a beat into bar 2 → bar 3
	(4.0, 100, 192),			# a hair past a boundary → the next one
	(8.0, 120, 192),			# a two-bar part lands on a two-bar line
	(16.0, 120, 384),			# a four-bar part on a four-bar line
	(2.0, 100, 144),			# a half-bar part on its own half-bar
])
def test_a_new_part_starts_on_a_multiple_of_its_own_length (beats: float, now: int, expected: int) -> None:

	"""The same counting a groove's slot uses: the song's timeline, not the save's."""

	composition = _composition()
	pending = _pending(composition, f"@composition.pattern(channel=1, beats={beats})\ndef part (p): pass\n")

	assert composition._next_start_pulse(pending, now) == expected


def test_a_boundary_inside_the_lookahead_is_skipped () -> None:

	"""There is no time to build for a cycle that starts in less than the lookahead."""

	composition = _composition()
	pending = _pending(
		composition,
		"@composition.pattern(channel=1, beats=4, reschedule_lookahead=2)\ndef part (p): pass\n",
	)

	# Pulse 84 is half a beat short of the bar line at 96, and the lookahead is
	# two beats (48 pulses), so the part waits for the bar after.
	assert composition._next_start_pulse(pending, 84) == 192
	assert composition._next_start_pulse(pending, 24) == 96


def test_a_part_added_on_a_boundary_waits_for_the_next_one () -> None:

	"""Arriving exactly on the bar line is already too late to start on it."""

	composition = _composition()
	pending = _pending(composition, "@composition.pattern(channel=1, beats=4)\ndef part (p): pass\n")

	assert composition._next_start_pulse(pending, 96) == 192


def test_a_part_with_no_lookahead_still_starts_ahead_of_now () -> None:

	"""With nothing to skip for, the rule itself has to look forward.

	Every other case is rescued by the lookahead check — the boundary already
	past is always closer than the lookahead, so it is pushed on by one length
	either way.  At ``reschedule_lookahead=0`` there is no rescue, and a rule
	that counted to the boundary *behind* would schedule at the current pulse:
	the very fault this fixes.
	"""

	composition = _composition()
	pending = _pending(
		composition,
		"@composition.pattern(channel=1, beats=4, reschedule_lookahead=0)\ndef part (p): pass\n",
	)

	assert composition._next_start_pulse(pending, 96) == 192
	assert composition._next_start_pulse(pending, 120) == 192


# ---------------------------------------------------------------------------
# Through the graduation path a save, load_patterns() and the REPL all use
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_part_graduated_mid_bar_is_scheduled_on_the_bar (patch_midi: None) -> None:

	"""The whole point: a snare added at beat 5 plays on beat 1, not beat 2."""

	composition = _composition()
	composition.load_patterns(
		"@composition.pattern(channel=1, beats=4)\n"
		"def snare (p):\n"
		"\tp.note(38, beat=0, duration=1)\n"
	)

	composition._sequencer._event_loop = asyncio.get_event_loop()
	composition._sequencer.pulse_count = 120		# a beat into bar 2

	await composition._activate_new_pending_patterns()

	pattern = composition._running_patterns["snare"]

	assert pattern._cycle_start_pulse == 192
	assert pattern._cycle_start_pulse % (4 * PPQ) == 0


@pytest.mark.asyncio
async def test_each_new_part_lands_on_its_own_grid (patch_midi: None) -> None:

	"""A one-bar part and a four-bar part added together start in different places."""

	composition = _composition()
	composition.load_patterns(
		"@composition.pattern(channel=1, beats=4)\n"
		"def short (p): pass\n"
		"@composition.pattern(channel=2, bars=4)\n"
		"def long (p): pass\n"
	)

	composition._sequencer._event_loop = asyncio.get_event_loop()
	composition._sequencer.pulse_count = 120

	await composition._activate_new_pending_patterns()

	assert composition._running_patterns["short"]._cycle_start_pulse == 192
	assert composition._running_patterns["long"]._cycle_start_pulse == 384


@pytest.mark.asyncio
async def test_the_note_itself_is_queued_on_the_bar_line (patch_midi: None) -> None:

	"""What a listener hears: the snare's first hit lands on the bar, not a beat late."""

	composition = _composition()
	composition.load_patterns(
		"@composition.pattern(channel=1, beats=4)\n"
		"def snare (p):\n"
		"\tp.note(38, beat=0, duration=1)\n"
	)

	composition._sequencer._event_loop = asyncio.get_event_loop()
	composition._sequencer.pulse_count = 120

	await composition._activate_new_pending_patterns()

	queued = sorted(
		(event.pulse, event.message_type)
		for event in composition._sequencer.event_queue
		if getattr(event, "note", None) == 38
	)

	assert queued == [(192, "note_on"), (216, "note_off")]
