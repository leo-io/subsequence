"""What the internal clock does after something holds its loop (#3374).

The clock's inner loop plays every overdue pulse in one pass, so a stall used to come back as a
burst: eight hats in 0.2 ms after a one-second stall at 120 BPM.  Simon's decision: a stall
longer than a beat is treated like a pause, carrying on from where it stopped, and a shorter one
still plays through, as the Link clock's does.  These run against the real wall clock, as the
pause tests do, and hold the loop the way a slow build does: with a call that blocks it.
"""

import asyncio
import time
import typing

import pytest

import subsequence.sequencer


# 600 BPM at 24 PPQN is a 4.17 ms pulse, so a beat - the line between the two behaviours - is
# 100 ms: a 200 ms stall is two beats, and a 50 ms stall half of one.
_TEST_BPM = 600


def _running_sequencer () -> subsequence.sequencer.Sequencer:

	"""A sequencer that keeps its clock running with nothing scheduled (the pause tests' own shape)."""

	sequencer = subsequence.sequencer.Sequencer(output_device_name="Dummy MIDI", initial_bpm=_TEST_BPM)
	sequencer._jitter_log = []

	return sequencer


async def _pulses_across_a_stall (seconds: float) -> int:

	"""Hold the clock's loop for this long, and count the pulses played from the stall to 30 ms after it."""

	sequencer = _running_sequencer()
	await sequencer.start()

	try:
		await asyncio.sleep(0.05)
		at_stall = sequencer.pulse_count

		# A blocking call on the loop is exactly what a slow build is.
		asyncio.get_running_loop().call_soon(time.sleep, seconds)
		await asyncio.sleep(0)
		await asyncio.sleep(0.03)

		return sequencer.pulse_count - at_stall

	finally:
		await sequencer.stop()


@pytest.mark.asyncio
async def test_a_stall_longer_than_a_beat_is_not_played_back_in_a_burst (patch_midi: None) -> None:

	"""Two beats held: the 48 pulses it missed used to be played at once when the loop came back.

	Real time after the stall allows about 7 pulses; the bound is loose for a busy machine and
	still well under the burst.
	"""

	played = await _pulses_across_a_stall(0.2)

	assert played <= 20, f"a burst of {played} pulses after the stall"


@pytest.mark.asyncio
async def test_a_stall_shorter_than_a_beat_still_plays_through (patch_midi: None) -> None:

	"""Half a beat held: its 12 pulses are played, not dropped - the same line the Link clock draws."""

	played = await _pulses_across_a_stall(0.05)

	assert played >= 12, f"only {played} pulses: the short stall was dropped rather than played through"
