"""An NRPN ramp stays pointed at its own parameter (#3070, M15 of the 2026-09-19 review).

A ramp selects its parameter once at `beat_start` and then sends only Data
Entry. That is correct MIDI and cheap — a synth holds the last parameter
selected on a channel — but nothing defended it, so any other NRPN or RPN
write inside the window took the selection and every later step of the ramp
landed somewhere else.

Measured on `f89c590`, replaying the CC stream the way a synth reads it:

**Two ramps over one window** — the first reached its own parameter on 1 of 5
steps; the other four went to the second ramp's parameter.

**A one-shot `p.nrpn()` inside the window** — worse, because its default
`null_reset=True` deselects: three of five steps landed on the NULL parameter
and did nothing at all.

The tests here read the stream the same way, because *which parameter a Data
Entry lands on* is the whole behaviour and it is not visible in any single
event: it is the running state of the CCs before it.
"""

import typing

import pytest

import pymididefs.cc
import pymididefs.rpn

import subsequence
import subsequence.pattern
import subsequence.pattern_builder


NULL = (127, 127)


def _builder (length: float = 4.0) -> subsequence.pattern_builder.PatternBuilder:

	pattern = subsequence.pattern.Pattern(channel = 0, length = length, device = 0)
	return subsequence.pattern_builder.PatternBuilder(pattern, cycle = 0)


def _data_entry_destinations (
	builder: subsequence.pattern_builder.PatternBuilder,
) -> typing.List[typing.Tuple[int, typing.Optional[typing.Tuple[str, int]]]]:

	"""Follow the CC stream as a synth would; return (pulse, parameter) per Data Entry MSB.

	``None`` means the value landed on the NULL parameter or on nothing — in
	both cases the synth does nothing with it.

	Same-pulse events are read in the order they were appended, because that is
	the order the engine sends them: ``_push_event`` stamps a rising sequence
	and ``MidiEvent`` compares on ``(pulse, rank, priority, sequence)``.
	"""

	builder._finish_build()

	events = builder._pattern.cc_events
	order = sorted(range(len(events)), key = lambda index: (events[index].pulse, index))

	half: typing.Dict[str, typing.Dict[str, int]] = {"nrpn": {}, "rpn": {}}
	selected: typing.Optional[typing.Tuple[str, int]] = None

	landed = []

	for index in order:

		event = events[index]

		if event.control == pymididefs.cc.NRPN_MSB:
			half["nrpn"]["msb"] = event.value
		elif event.control == pymididefs.cc.NRPN_LSB:
			half["nrpn"]["lsb"] = event.value
		elif event.control == pymididefs.cc.RPN_MSB:
			half["rpn"]["msb"] = event.value
		elif event.control == pymididefs.cc.RPN_LSB:
			half["rpn"]["lsb"] = event.value
		elif event.control == pymididefs.cc.DATA_ENTRY_MSB:
			landed.append((event.pulse, selected))
			continue
		else:
			continue

		kind = "nrpn" if event.control in (pymididefs.cc.NRPN_MSB, pymididefs.cc.NRPN_LSB) else "rpn"

		if "msb" in half[kind] and "lsb" in half[kind]:
			pair = (half[kind]["msb"], half[kind]["lsb"])
			selected = None if pair == NULL else (kind, (pair[0] << 7) | pair[1])

	return landed


def _reaching (
	landed: typing.List[typing.Tuple[int, typing.Optional[typing.Tuple[str, int]]]],
	parameter: typing.Tuple[str, int],
) -> int:

	return sum(1 for _, where in landed if where == parameter)


# ---------------------------------------------------------------------------
# The control: one ramp alone was always right, and must stay cheap
# ---------------------------------------------------------------------------

def test_a_ramp_on_its_own_reaches_its_parameter (patch_midi: None) -> None:

	"""It always did. Here so "they all reach it" cannot pass by re-selecting blindly."""

	builder = _builder()
	builder.nrpn_ramp(10, 0, 16383, beat_start = 0, beat_end = 4, resolution = 24)

	landed = _data_entry_destinations(builder)

	assert landed, "the ramp emitted no data entry at all"
	assert _reaching(landed, ("nrpn", 10)) == len(landed), (
		f"a ramp alone misfired: {landed}"
	)


def test_a_ramp_on_its_own_still_selects_its_parameter_only_once (patch_midi: None) -> None:

	"""The bandwidth argument in the docstring has to stay true.

	Re-selecting before every step would fix the collisions too, and double
	the traffic of every ramp anybody has ever written. The repair only fires
	where the selection has actually drifted.
	"""

	builder = _builder()
	builder.nrpn_ramp(10, 0, 16383, beat_start = 0, beat_end = 4, resolution = 4)

	builder._finish_build()

	selects = [
		event for event in builder._pattern.cc_events
		if event.control in (pymididefs.cc.NRPN_MSB, pymididefs.cc.NRPN_LSB)
	]

	assert len(selects) == 2, (
		f"a lone ramp emitted {len(selects)} parameter-select CCs where two "
		f"(one MSB, one LSB) is the whole selection"
	)


# ---------------------------------------------------------------------------
# Something else takes the selection
# ---------------------------------------------------------------------------

def test_two_ramps_over_one_window_both_reach_their_parameters (patch_midi: None) -> None:

	"""The review's case: the first ramp used to reach its parameter once in five."""

	builder = _builder()
	builder.nrpn_ramp(10, 0, 16383, beat_start = 0, beat_end = 4, resolution = 24)
	builder.nrpn_ramp(20, 0, 16383, beat_start = 0, beat_end = 4, resolution = 24)

	landed = _data_entry_destinations(builder)

	assert landed, "no data entry at all"

	to_ten = _reaching(landed, ("nrpn", 10))
	to_twenty = _reaching(landed, ("nrpn", 20))

	assert to_ten == to_twenty == len(landed) // 2, (
		f"parameter 10 got {to_ten} steps and 20 got {to_twenty}, of {len(landed)}: {landed}"
	)


def test_a_one_shot_inside_the_window_does_not_derail_the_ramp (patch_midi: None) -> None:

	"""The worst case: a one-shot's default null_reset sent the rest to NULL.

	Three of five steps did nothing at all, with no warning anywhere.
	"""

	builder = _builder()
	builder.nrpn_ramp(10, 0, 16383, beat_start = 0, beat_end = 4, resolution = 24)
	builder.nrpn(20, 64, beat = 1)

	landed = _data_entry_destinations(builder)

	lost = [(pulse, where) for pulse, where in landed if where is None]

	assert not lost, f"{len(lost)} data entries landed on NULL and did nothing: {lost}"

	assert _reaching(landed, ("nrpn", 10)) == len(landed) - 1, (
		f"the ramp lost steps to the one-shot: {landed}"
	)
	assert _reaching(landed, ("nrpn", 20)) == 1, f"the one-shot did not land: {landed}"


def test_an_rpn_ramp_beside_an_nrpn_ramp_keeps_them_apart (patch_midi: None) -> None:

	"""They use different select CCs and still collide, because the synth has one pointer."""

	builder = _builder()
	builder.nrpn_ramp(10, 0, 16383, beat_start = 0, beat_end = 4, resolution = 24)
	builder.rpn_ramp(0, 0, 16383, beat_start = 0, beat_end = 4, resolution = 24)

	landed = _data_entry_destinations(builder)

	to_nrpn = _reaching(landed, ("nrpn", 10))
	to_rpn = _reaching(landed, ("rpn", 0))

	assert to_nrpn == to_rpn == len(landed) // 2, (
		f"nrpn 10 got {to_nrpn} and rpn 0 got {to_rpn}, of {len(landed)}: {landed}"
	)


def test_three_ramps_at_once_all_arrive (patch_midi: None) -> None:

	"""The control on the arithmetic: nothing here is written for exactly two."""

	builder = _builder()

	for parameter in (10, 20, 30):
		builder.nrpn_ramp(parameter, 0, 16383, beat_start = 0, beat_end = 4, resolution = 24)

	landed = _data_entry_destinations(builder)

	for parameter in (10, 20, 30):
		assert _reaching(landed, ("nrpn", parameter)) == len(landed) // 3, (
			f"parameter {parameter} got {_reaching(landed, ('nrpn', parameter))} of {len(landed)}"
		)


# ---------------------------------------------------------------------------
# What is deliberately left alone
# ---------------------------------------------------------------------------

def test_a_plain_data_entry_cc_is_left_where_the_user_put_it (patch_midi: None) -> None:

	"""`p.cc(6, …)` carries no parameter and must not have one invented for it.

	It addresses whatever the user last selected — that is what the docstrings
	have always said, and repairing it would be this guessing at intent.
	"""

	builder = _builder()
	builder.nrpn_ramp(10, 0, 16383, beat_start = 0, beat_end = 4, resolution = 24)
	builder.cc(pymididefs.cc.DATA_ENTRY_MSB, 99, beat = 1)

	builder._finish_build()

	plain = [
		event for event in builder._pattern.cc_events
		if event.control == pymididefs.cc.DATA_ENTRY_MSB and event.value == 99
	]

	assert len(plain) == 1, f"the plain CC 6 was duplicated or lost: {len(plain)}"
	assert plain[0].parameter is None, (
		"a plain data-entry CC was given a parameter it never asked for"
	)


def test_a_pattern_with_no_nrpn_at_all_is_untouched (patch_midi: None) -> None:

	"""The repair must be a no-op for the overwhelming majority of patterns."""

	builder = _builder()
	builder.cc(74, 100, beat = 0)
	builder.cc(71, 40, beat = 2)

	before = list(builder._pattern.cc_events)

	builder._finish_build()

	assert builder._pattern.cc_events == before, "a pattern with no NRPN was rewritten"


def test_a_hand_built_pattern_is_repaired_too (patch_midi: None) -> None:

	"""The Direct Pattern API has no engine to finish its build (#2959).

	A ramp registers the build itself for exactly this reason: without it the
	repair would run only for patterns the engine built, and a hand-built one
	would keep the bug.
	"""

	pattern = subsequence.pattern.Pattern(channel = 0, length = 4.0, device = 0)
	builder = subsequence.pattern_builder.PatternBuilder(pattern, cycle = 0)

	builder.nrpn_ramp(10, 0, 16383, beat_start = 0, beat_end = 4, resolution = 24)
	builder.nrpn(20, 64, beat = 1)

	assert pattern._unfinished_builds, (
		"the ramp did not register its build, so nothing would repair it"
	)

	pattern._finish_builds()

	landed = _data_entry_destinations(builder)

	assert not [where for _, where in landed if where is None], (
		f"a hand-built pattern kept the fault: {landed}"
	)
