"""A pattern that takes a chord, with no chord to give it, says so once and waits (#3019).

``def pad (p, chord)`` in a piece with no harmony was called with one argument, so it raised
``TypeError: pad() missing 1 required positional argument: 'chord'`` on every cycle, and each one
was logged with a traceback about Python's argument count, never about the harmony it lacked.  A
builder that gives ``chord`` a default still decides for itself.
"""

import logging
import pathlib
import typing

import mido
import pytest

import subsequence


def _render (tmp_path: pathlib.Path, builder: typing.Callable[..., None], harmony: bool = False) -> typing.List[int]:

	"""Render four bars with *builder* as the only part; the pitches it sounded."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=480, key="C")

	if harmony:
		composition.harmony(style="functional_major", cycle_beats=4)

	composition.pattern(channel=1, beats=4)(builder)

	filename = tmp_path / "part.mid"
	composition.render(bars=4, filename=str(filename))

	return [message.note for track in mido.MidiFile(str(filename)).tracks for message in track if message.type == "note_on" and message.velocity > 0]


def test_it_says_what_is_missing_once_and_plays_nothing (tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture) -> None:

	def pad (p: typing.Any, chord: typing.Any) -> None:
		p.note(chord.root_note(60), beat=0, duration=4)

	with caplog.at_level(logging.WARNING, logger="subsequence"):
		played = _render(tmp_path, pad)

	said = [record.getMessage() for record in caplog.records if "takes a chord, and there is none" in record.getMessage()]
	tracebacks = [record for record in caplog.records if record.exc_info]

	assert played == []
	assert len(said) == 1
	assert "'pad'" in said[0] and "composition.harmony(" in said[0]
	assert tracebacks == []


def test_a_builder_that_gives_chord_a_default_still_decides (tmp_path: pathlib.Path) -> None:

	"""A guard: chord=None is called with one argument, as before #3019."""

	def pad (p: typing.Any, chord: typing.Any = None) -> None:
		p.note(60 if chord is None else chord.root_note(60), beat=0, duration=4)

	assert _render(tmp_path, pad) == [60, 60, 60, 60]


def test_with_harmony_the_chord_arrives (tmp_path: pathlib.Path) -> None:

	"""A guard: the two-parameter convention itself.  This passed before #3019 as well."""

	def pad (p: typing.Any, chord: typing.Any) -> None:
		p.note(chord.root_note(60), beat=0, duration=4)

	assert len(_render(tmp_path, pad, harmony=True)) == 4
