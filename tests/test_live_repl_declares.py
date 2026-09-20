"""What is typed at the live REPL is a declaration, and is acted on as one (#2999).

A submission used to be run on a worker thread and then dropped: a new
``@composition.pattern`` was answered with ``OK`` and never heard, because it
went into ``_pending_patterns`` and nothing graduated it; a re-declared
``layer()`` came back as a second layer with a ``#2`` on its name, because the
names declared at startup were still standing; and the bundled client could not
send a decorated function at all, which is what ``live()`` is for.

These drive a real socket, because the fault lived in the path between the
socket and the composition.
"""

import asyncio
import threading
import typing

import pytest

import subsequence
import subsequence.composition
import subsequence.constants
import subsequence.live_client
import subsequence.live_server


SENTINEL = b"\x04"

PPQ = subsequence.constants.MIDI_QUARTER_NOTE


async def _playing (port: int = 0) -> typing.Tuple[subsequence.Composition, subsequence.live_server.LiveServer, int]:

	"""A composition mid-performance with its live server listening.

	Everything ``play()`` would have done to reach the point where a performer
	types something: the loop is attached, the devices are open, the startup
	patterns are running, and the server is up.
	"""

	composition = subsequence.Composition(bpm = 120, output_device = "Dummy MIDI")
	composition.live(port = port)

	loop = asyncio.get_running_loop()
	composition._event_loop = loop
	composition._sequencer._event_loop = loop

	composition._open_output_devices()

	server = composition._live_server
	assert server is not None

	await server.start()
	await composition._activate_new_pending_patterns()

	return composition, server, server._server.sockets[0].getsockname()[1]


async def _type (port: int, code: str) -> str:

	"""Type one submission at the server over a real socket, and read the answer."""

	reader, writer = await asyncio.open_connection("127.0.0.1", port)

	try:
		writer.write(code.encode("utf-8") + SENTINEL)
		await writer.drain()

		chunks: typing.List[bytes] = []

		while True:
			chunk = await asyncio.wait_for(reader.read(4096), timeout = 5.0)

			if not chunk:
				break

			if SENTINEL in chunk:
				chunks.append(chunk.partition(SENTINEL)[0])
				break

			chunks.append(chunk)

		return b"".join(chunks).decode("utf-8")

	finally:
		writer.close()
		await writer.wait_closed()


# ---------------------------------------------------------------------------
# A new part typed live actually plays
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_pattern_typed_live_starts_playing (patch_midi: None) -> None:

	"""The whole point of the REPL: type a part, hear the part."""

	composition, server, port = await _playing()

	answer = await _type(port, (
		"@composition.pattern(channel=2, beats=4)\n"
		"def added_live (p):\n"
		"	p.note(72, beat=0.0)\n"
	))

	assert "Traceback" not in answer

	assert "added_live" in composition._running_patterns, \
		"the server said OK and the part never came in"

	await server.stop()


@pytest.mark.asyncio
async def test_a_part_typed_live_is_scheduled_on_the_grid (patch_midi: None) -> None:

	"""It comes in on a bar line, by the rule #3000 gave every mid-flight part."""

	composition, server, port = await _playing()

	composition._sequencer.pulse_count = 100

	await _type(port, (
		"@composition.pattern(channel=3, beats=4)\n"
		"def late_part (p):\n"
		"	p.note(60, beat=0.0)\n"
	))

	assert "late_part" in composition._running_patterns, "the part never came in at all"

	pattern = composition._running_patterns["late_part"]

	assert pattern._cycle_start_pulse % (4 * PPQ) == 0, \
		f"a four-beat part came in at pulse {pattern._cycle_start_pulse}, off the bar grid"
	assert pattern._cycle_start_pulse > 100

	await server.stop()


@pytest.mark.asyncio
async def test_a_part_typed_live_leaves_nothing_pending (patch_midi: None) -> None:

	"""What was graduated is gone from the queue, so a later reload cannot raise it again."""

	composition, server, port = await _playing()

	await _type(port, (
		"@composition.pattern(channel=2, beats=4)\n"
		"def added_live (p):\n"
		"	p.note(72, beat=0.0)\n"
	))

	assert [pending.builder_fn.__name__ for pending in composition._pending_patterns] == []

	await server.stop()


@pytest.mark.asyncio
async def test_a_submission_that_raises_starts_nothing (patch_midi: None) -> None:

	"""A half-built declaration is not a part: the traceback comes back, the queue stays put."""

	composition, server, port = await _playing()

	answer = await _type(port, (
		"@composition.pattern(channel=2, beats=4)\n"
		"def broken (p):\n"
		"	pass\n"
		"raise ValueError('not finished')\n"
	))

	assert "ValueError" in answer
	assert "broken" not in composition._running_patterns

	await server.stop()


@pytest.mark.asyncio
async def test_a_part_typed_live_hot_swaps_on_the_second_pass (patch_midi: None) -> None:

	"""Typing the same name again changes the part that is playing, not its count."""

	composition, server, port = await _playing()

	await _type(port, "@composition.pattern(channel=2, beats=4)\ndef riff (p):\n	p.note(60, beat=0.0)\n")

	assert "riff" in composition._running_patterns, "the part never came in at all"

	first = composition._running_patterns["riff"]

	await _type(port, "@composition.pattern(channel=2, beats=4)\ndef riff (p):\n	p.note(67, beat=0.0)\n")

	assert composition._running_patterns["riff"] is first, \
		"a re-typed part was scheduled again instead of swapping its body in"
	assert len(composition._pending_patterns) == 0

	await server.stop()


@pytest.mark.asyncio
async def test_a_submission_runs_on_the_loop_that_owns_the_composition (patch_midi: None) -> None:

	"""Off on a worker thread it raced the clock that was reading what it changed."""

	composition, server, port = await _playing()

	answer = await _type(port, "import threading\ncomposition._typed_by = threading.get_ident()\n")

	assert "Traceback" not in answer, answer

	assert composition._typed_by == threading.get_ident(), \
		"the submission ran on a thread of its own, beside the loop"

	await server.stop()


# ---------------------------------------------------------------------------
# A re-declared layer is the same layer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_re_declared_layer_does_not_double (patch_midi: None) -> None:

	"""Its name was taken by its own startup declaration, so it came back as a second one."""

	composition = subsequence.Composition(bpm = 120, output_device = "Dummy MIDI")
	composition.live(port = 0)

	loop = asyncio.get_running_loop()
	composition._event_loop = loop
	composition._sequencer._event_loop = loop

	def bass (p: typing.Any) -> None:
		p.note(36, beat = 0.0)

	def hat (p: typing.Any) -> None:
		p.note(42, beat = 0.0)

	composition.layer(bass, hat, channel = 3, beats = 4)

	composition._open_output_devices()

	server = composition._live_server
	assert server is not None

	await server.start()
	await composition._activate_new_pending_patterns()

	port = server._server.sockets[0].getsockname()[1]

	started_as = sorted(composition._running_patterns)
	assert len(started_as) == 1

	server._namespace["bass"] = bass
	server._namespace["hat"] = hat

	await _type(port, "composition.layer(bass, hat, channel=3, beats=4)")

	assert sorted(composition._running_patterns) == started_as, \
		f"the layer came back as {sorted(composition._running_patterns)}"
	assert not any("#" in name for name in composition._declared_names)
	assert composition._pending_patterns == []

	await server.stop()


@pytest.mark.asyncio
async def test_two_different_layers_in_one_submission_still_get_their_own_names (patch_midi: None) -> None:

	"""Clearing the declared names per submission must not merge distinct layers."""

	composition, server, port = await _playing()

	server._namespace["bass"] = lambda p: p.note(36, beat = 0.0)
	server._namespace["hat"] = lambda p: p.note(42, beat = 0.0)

	await _type(port, (
		"composition.layer(bass, hat, channel=3, beats=4)\n"
		"composition.layer(hat, bass, channel=3, beats=4)\n"
	))

	assert len(composition._running_patterns) == 2, \
		f"two layers on one channel collapsed into {sorted(composition._running_patterns)}"

	await server.stop()


# ---------------------------------------------------------------------------
# What the REPL declares belongs to the REPL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_what_is_typed_belongs_to_the_repl (patch_midi: None) -> None:

	"""A source owns it, so it is on the record rather than nobody's."""

	composition, server, port = await _playing()

	await _type(port, "@composition.pattern(channel=2, beats=4)\ndef typed (p):\n	p.note(72, beat=0.0)\n")

	assert "typed" in composition._source_declared[subsequence.live_server.REPL_SOURCE]

	await server.stop()


@pytest.mark.asyncio
async def test_the_repl_remembers_every_submission_not_just_the_last (patch_midi: None) -> None:

	"""Each line declares one thing; forgetting the line before would disown it."""

	composition, server, port = await _playing()

	await _type(port, "@composition.pattern(channel=2, beats=4)\ndef first (p):\n	p.note(60, beat=0.0)\n")
	await _type(port, "@composition.pattern(channel=3, beats=4)\ndef second (p):\n	p.note(67, beat=0.0)\n")

	owned = composition._source_declared[subsequence.live_server.REPL_SOURCE]

	assert {"first", "second"} <= owned

	await server.stop()


@pytest.mark.asyncio
async def test_a_file_save_leaves_what_was_typed_alone (patch_midi: None) -> None:

	"""The performer's typing is not the watched file's to tear down."""

	composition, server, port = await _playing()

	await _type(port, "@composition.pattern(channel=2, beats=4)\ndef typed (p):\n	p.note(72, beat=0.0)\n")

	assert "typed" in composition._running_patterns, \
		"it has to be playing before a save can be accused of removing it"

	source = "@composition.pattern(channel=4, beats=4)\ndef from_file (p):\n	p.note(48, beat=0.0)\n"

	# Twice: the first save has nothing to diff against, so only the second
	# can tear anything down.
	for _ in range(2):
		await composition._apply_source_async(
			compile(source, "piece.py", "exec"),
			composition._build_live_namespace(),
			source_key = "piece.py",
		)

	assert "typed" in composition._running_patterns, \
		"a save of an unrelated file removed the part the performer had typed"

	assert "typed" not in composition._source_declared["piece.py"], \
		"the file claimed the performer's typing as its own to remove"

	await server.stop()


@pytest.mark.asyncio
async def test_a_second_submission_does_not_tear_down_the_first (patch_midi: None) -> None:

	"""One line is one declaration, not a statement about everything else."""

	composition, server, port = await _playing()

	await _type(port, "@composition.pattern(channel=2, beats=4)\ndef first (p):\n	p.note(60, beat=0.0)\n")
	await _type(port, "@composition.pattern(channel=3, beats=4)\ndef second (p):\n	p.note(67, beat=0.0)\n")

	assert "first" in composition._running_patterns, \
		"typing a second part removed the first"
	assert "second" in composition._running_patterns

	await server.stop()


# ---------------------------------------------------------------------------
# The bundled client can send what the REPL is for
# ---------------------------------------------------------------------------

def _accumulate (typed: typing.Sequence[str]) -> str:

	"""Replay the client's input loop over lines the performer types."""

	lines = [typed[0]]
	in_block = subsequence.live_client._is_incomplete(typed[0])
	index = 1

	while in_block or subsequence.live_client._is_incomplete("\n".join(lines)):

		if index >= len(typed):
			break

		continuation = typed[index]
		index += 1

		if in_block and continuation.strip() == "":
			break

		lines.append(continuation)

	return "\n".join(lines)


def test_the_client_keeps_a_decorator_with_what_it_decorates () -> None:

	"""It went off alone as a SyntaxError, and the def after it arrived undecorated."""

	sent = _accumulate([
		"@composition.pattern(channel=2, beats=4)",
		"def added_live (p):",
		"	p.note(72, beat=0.0)",
		"",
	])

	assert sent.startswith("@composition.pattern")
	assert "def added_live" in sent
	assert "p.note(72" in sent


def test_a_decorator_alone_is_never_complete () -> None:

	"""Python compiles it happily as an expression, which is why it was sent."""

	assert subsequence.live_client._is_incomplete("@composition.pattern(channel=1, beats=4)")
	assert subsequence.live_client._is_incomplete("@composition.pattern")


@pytest.mark.parametrize("code", [
	"def hat (p):",
	"for i in range(4):",
	"x = (1,",
	"x = '''still open",
	"p.note(60, \\",
])
def test_the_client_waits_for_the_rest (code: str) -> None:

	"""Anything Python cannot run yet keeps the continuation prompt up."""

	assert subsequence.live_client._is_incomplete(code)


@pytest.mark.parametrize("code", [
	"composition.set_bpm(128)",
	"composition.live_info()",
	"x = (1, 2)",
	"2 + 2",
])
def test_the_client_sends_a_finished_line_at_once (code: str) -> None:

	"""A complete statement must not strand the performer at a "..." prompt."""

	assert not subsequence.live_client._is_incomplete(code)


def test_a_block_body_is_kept_together () -> None:

	"""Sending the header alone was the older fault; the body must ride with it."""

	sent = _accumulate(["def hat (p):", "	p.note(42, beat=0.0)", "	p.note(46, beat=2.0)", ""])

	assert sent.count("p.note") == 2


@pytest.mark.parametrize("code", ["def (p):", "x = 'unterminated", "1 +* 2"])
def test_code_that_can_never_compile_is_sent_rather_than_held (code: str) -> None:

	"""The server's traceback tells the performer what is wrong; a stuck prompt does not."""

	assert not subsequence.live_client._is_incomplete(code)
