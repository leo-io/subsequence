"""Changes made from another thread reach what the clock reads only on the clock's own loop.

Typed code runs on the loop (#2999), but a synchronous `schedule()` function runs on an
executor thread, and a performer can start threads of their own.  The clock reads some state
several times within one pulse or one step, so a change from elsewhere landing between two
reads broke it: the review widened each window to catch it every time, and so do these tests.
"""

import asyncio
import threading
import time
import typing

import pytest

import subsequence
import subsequence.form_state


def _from_another_thread (fn: typing.Callable[[], typing.Any], after: float = 0.0) -> typing.Tuple[threading.Thread, typing.Dict[str, typing.Any]]:

	"""Run fn on a thread of its own, after a pause, keeping what it returned or raised."""

	box: typing.Dict[str, typing.Any] = {}

	def run () -> None:
		time.sleep(after)
		try:
			box["value"] = fn()
		except BaseException as error:
			box["error"] = error

	thread = threading.Thread(target=run)
	thread.start()

	return thread, box


def _slow_linear (x: float) -> float:

	"""A linear ramp that takes 50 ms to evaluate: the review's widening, which holds the clock mid-pulse."""

	time.sleep(0.05)

	return x


@pytest.fixture
def composition (patch_midi: None) -> subsequence.Composition:

	"""A composition with its devices open, as play() would leave it."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)
	composition._open_output_devices()

	return composition


def _playing (composition: subsequence.Composition) -> subsequence.Composition:

	"""Make the test's own running loop the clock's, as play() would: only a running test has one."""

	composition._sequencer._event_loop = asyncio.get_running_loop()

	return composition


@pytest.mark.asyncio
async def test_a_tempo_change_from_another_thread_never_lands_inside_a_pulse (composition: subsequence.Composition) -> None:

	"""set_bpm() from another thread mid-ramp ended the ramp between two of the clock's reads of it (#3381).

	The clock task raised AttributeError and died, which stops the music.  The change must still
	happen - after the pulse.
	"""

	playing = _playing(composition)
	sequencer = playing._sequencer
	sequencer.set_target_bpm(200, 4, _slow_linear)
	assert sequencer._bpm_transition is not None, "the ramp did not start, so this tests nothing"

	caller, box = _from_another_thread(lambda: playing.set_bpm(90), after=0.01)

	try:
		await sequencer._advance_pulse()
		crashed = None
	except Exception as error:
		crashed = error

	caller.join()
	await asyncio.sleep(0.05)

	assert crashed is None
	assert "error" not in box
	assert sequencer.current_bpm == 90
	assert sequencer._bpm_transition is None


@pytest.mark.asyncio
async def test_a_ramp_started_from_another_thread_waits_for_the_loop (composition: subsequence.Composition) -> None:

	"""The ramp is handed to the loop rather than made on the caller's thread: it exists only once the loop turns."""

	playing = _playing(composition)
	sequencer = playing._sequencer
	caller, box = _from_another_thread(lambda: sequencer.set_target_bpm(160, 2))
	caller.join()

	assert "error" not in box
	assert sequencer._bpm_transition is None

	await asyncio.sleep(0)

	assert sequencer._bpm_transition is not None
	assert sequencer._bpm_transition.target_bpm == 160


@pytest.mark.asyncio
async def test_a_bad_tempo_from_another_thread_is_still_heard_by_the_caller (composition: subsequence.Composition) -> None:

	"""Only the change waits for the loop; the checks do not, so the caller is told at once."""

	playing = _playing(composition)
	sequencer = playing._sequencer
	errors = []

	for bad in (lambda: playing.set_bpm(-1), lambda: sequencer.set_target_bpm(120, 0), lambda: sequencer.set_target_bpm(120, 2, "no_such_shape")):
		caller, box = _from_another_thread(bad)
		caller.join()
		errors.append(type(box.get("error")).__name__)

	assert errors == ["ValueError", "ValueError", "ValueError"]


@pytest.mark.asyncio
async def test_on_the_clock_s_loop_a_tempo_change_is_made_at_once (composition: subsequence.Composition) -> None:

	"""A hotkey, an OSC message or a typed line already runs on the loop, and waits for nothing."""

	playing = _playing(composition)
	playing.set_bpm(130)

	assert playing._sequencer.current_bpm == 130


def _with_a_form (composition: subsequence.Composition) -> subsequence.Composition:

	"""Five two-bar sections, looping, one bar in: the form's next advance() crosses A's boundary."""

	composition.form([("A", 2), ("B", 2), ("C", 2), ("D", 2), ("E", 2)], loop=True)
	assert composition._form_state is not None
	composition._form_state.advance()

	return composition


@pytest.mark.asyncio
async def test_a_jump_from_another_thread_is_not_lost_against_the_form_s_own_advance (composition: subsequence.Composition, monkeypatch: pytest.MonkeyPatch) -> None:

	"""A jump made on another thread landed inside advance() and was overwritten: the form went on to E (#3382).

	The form's step is slowed as the review slowed it, so the jump arrives mid-step every time.
	Every order the two could have run in gives D.
	"""

	playing = _playing(_with_a_form(composition))
	form = playing._form_state
	assert form is not None
	step = subsequence.form_state.FormState._sequence_next_position

	def _slow_step (self: subsequence.form_state.FormState) -> typing.Optional[int]:
		time.sleep(0.05)
		return step(self)

	monkeypatch.setattr(subsequence.form_state.FormState, "_sequence_next_position", _slow_step)
	caller, box = _from_another_thread(lambda: playing.form_jump("D"), after=0.01)
	form.advance()
	caller.join()
	await asyncio.sleep(0.05)

	assert "error" not in box
	info = form.get_section_info()
	assert info is not None and info.name == "D"


@pytest.mark.asyncio
async def test_a_section_queued_from_another_thread_waits_for_the_loop (composition: subsequence.Composition) -> None:

	"""form_next() is handed to the loop as a jump is: the queue changes only once the loop turns."""

	playing = _playing(_with_a_form(composition))
	form = playing._form_state
	assert form is not None
	before = form._next_section_name

	caller, box = _from_another_thread(lambda: playing.form_next("D"))
	caller.join()

	assert "error" not in box
	assert form._next_section_name == before != "D"

	await asyncio.sleep(0)

	assert form._next_section_name == "D"


@pytest.mark.asyncio
async def test_a_bad_section_from_another_thread_is_still_heard_by_the_caller (composition: subsequence.Composition) -> None:

	"""The name is checked on the caller's thread, with the same message as ever; only the move waits."""

	playing = _playing(_with_a_form(composition))
	messages = []

	for move in (lambda: playing.form_jump("nope"), lambda: playing.form_next("nope")):
		caller, box = _from_another_thread(move)
		caller.join()
		messages.append(str(box.get("error")).split(":")[0])

	assert messages == ["jump_to", "queue_next"]
