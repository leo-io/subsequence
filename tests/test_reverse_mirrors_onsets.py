"""Motif.reverse() mirrors onsets around the downbeat, with ramps and control writes mirrored too (#3457).

It mirrored each note's end, so a figure of short notes came back off the grid and
a tie was clamped to beat 0.  ``p.reverse()`` mirrors onsets, and so does this now:
Simon's call (#3423).  A ramp's ends swapped but its curve and its slice window did
not, so an ease_in sweep read the wrong values and half a sweep played the other
half.  And a control write, which holds until the next one, was mirrored as a
point, so a stepped gesture looped as the original steps.
"""

import typing

from subsequence.motifs import Motif as M


def _onsets (m: M) -> typing.List[float]:

	return [event.beat for event in m.events]


def _value (m: M, beat: float) -> float:

	"""The control value a looped motif holds at *beat*, from its events alone.

	The last event at or before *beat* decides it - a ramp still running reads
	its curve, anything else its final value - and before the first event of a
	cycle, the last one of the cycle before still holds, a write on the length
	included.
	"""

	controls = sorted(m.controls, key=lambda c: c.beat)
	earlier = [c for c in controls if c.beat <= beat + 1e-9]

	if not earlier:
		last = controls[-1]
		return last.start if last.end is None else last.end

	current = earlier[-1]

	if current.end is not None and beat < current.beat + current.span:
		return current._value_at((beat - current.beat) / current.span)

	return current.start if current.end is None else current.end


def test_a_figure_of_short_notes_stays_on_the_grid () -> None:

	"""The son clave with tenth-of-a-beat notes: [0.9, 1.4, 2.4, 3.15, 3.9] was the old mirror, all off the grid."""

	clave = M.hits("clave", beats=[0, 0.75, 1.5, 2.5, 3.0], length=4)

	assert _onsets(clave.reverse()) == [0.0, 1.0, 1.5, 2.5, 3.25]


def test_a_line_reverses_around_its_downbeat () -> None:

	"""1 2 3 4 comes back as 1 4 3 2, on the beats whatever the notes' lengths (Simon's call)."""

	for durations in (1.0, 0.5):
		reversed_line = M.degrees([1, 2, 3, 4], durations=durations).reverse()

		assert [(event.beat, event.pitch.step) for event in reversed_line.events] == [(0.0, 1), (1.0, 4), (2.0, 3), (3.0, 2)]


def test_a_tie_over_the_barline_keeps_its_mirrored_onset () -> None:

	"""A note ringing past the end mirrors by its onset: 3.5 comes back at 0.5, not clamped to 0."""

	tied = M.notes([60, 64, 67], beats=[0, 2, 3.5], durations=[1, 1, 1.5], length=4)

	assert [(event.beat, event.pitch) for event in tied.reverse().events] == [(0.0, 60), (0.5, 67), (2.0, 64)]


def test_an_eased_sweep_reverses_along_its_own_curve () -> None:

	"""An ease_in rise, reversed, falls along the same curve: 56.25 a quarter of the way, not 93.75."""

	sweep = M.cc_ramp(74, 0, 100, 0, 4, shape="ease_in").reverse()
	ramp = sweep.controls[0]

	assert ramp.shape == "ease_out"
	assert [ramp._value_at(t) for t in (0.0, 0.25, 0.5, 0.75, 1.0)] == [100.0, 56.25, 25.0, 6.25, 0.0]


def test_a_curve_of_your_own_reverses_and_comes_back () -> None:

	"""A callable curve plays backwards, and reversing again hands back the very function."""

	def steep (t: float) -> float:
		return t ** 4

	sweep = M.cc_ramp(74, 0, 100, 0, 4, shape=steep)
	ramp = sweep.reverse().controls[0]

	assert abs(ramp._value_at(0.25) - 100 * steep(0.75)) < 1e-9
	assert sweep.reverse().reverse().controls[0].shape is steep


def test_half_a_sweep_reverses_as_that_half () -> None:

	"""The first half of an eight-beat rise plays 0 to 50; reversed it plays 50 to 0, not 100 to 50."""

	half = M.cc_ramp(74, 0, 100, 0, 8).slice(0, 4).reverse()
	ramp = half.controls[0]

	assert (ramp._value_at(0.0), ramp._value_at(1.0)) == (50.0, 0.0)


def test_stepped_writes_come_back_in_reverse_order () -> None:

	"""10 for two beats then 100 for two reverses to 100 then 10; it used to loop as the same steps."""

	stepped = M.cc(74, [10, 100], beats=[0, 2], length=4).reverse()

	assert [(c.beat, c.start) for c in stepped.controls] == [(0.0, 100), (2.0, 10)]
	assert [_value(stepped, beat) for beat in (0.5, 1.5, 2.5, 3.5)] == [100, 100, 10, 10]


def test_a_write_on_the_length_closes_the_gesture_and_stays () -> None:

	"""10 through the bar and 100 handed on at its end is its own mirror, so it stays as it is."""

	closing = M.cc(74, [10, 100], beats=[0, 2])

	assert closing.length == 2
	assert closing.reverse() == closing


def test_a_ramp_and_the_value_it_holds_reverse_together () -> None:

	"""10, a rise to 100 over beat 2, then 100 held: reversed, 100 is held first, then the fall to 10.

	The hold after the rise was nobody's event, so the old mirror lost it and
	the reversed bar began on the 10 left over from the cycle before.
	"""

	gesture = M.cc(74, [10], beats=[0], length=4) & M.cc_ramp(74, 10, 100, 2, 3, length=4)
	backwards = gesture.reverse()

	assert [_value(backwards, beat) for beat in (0.0, 0.5, 1.5, 2.5, 3.5)] == [100, 100, 55.0, 10, 10]
	assert backwards.reverse() == gesture


def test_reversing_twice_gives_back_every_kind_of_gesture () -> None:

	"""Notes, an eased ramp, a slice of one, a custom curve, stepped writes and a closing write, together."""

	def steep (t: float) -> float:
		return t ** 4

	figure = (
		M.hits("clave", beats=[0, 0.75, 1.5, 2.5, 3.0], length=4)
		& M.cc_ramp(74, 0, 100, 0, 3, shape="ease_in", length=4)
		& M.cc_ramp(71, 0, 100, 0, 8).slice(0, 4)
		& M.cc_ramp(10, 20, 90, 1, 2, shape=steep, length=4)
		& M.cc(7, [10, 100, 50], beats=[0, 1.5, 3], length=4)
		& M.cc(1, [30, 90], beats=[1, 4], length=4)
	)

	assert figure.reverse().reverse() == figure



def test_a_write_replaced_on_its_own_beat_stays_unheard () -> None:

	"""Two writes on one beat: only the second is ever heard, and the mirror keeps it that way.

	100 holds from beat 1 to 3 and 20 from 3 round to 1.  Mirrored as a point,
	the 50 that 100 replaced at once would land on beat 3 beside the 20, and
	win there, being the larger.
	"""

	crowded = M.cc(74, [50, 100, 20], beats=[1, 1, 3], length=4)
	backwards = crowded.reverse()

	assert [_value(crowded, beat) for beat in (0.5, 2.0, 3.5)] == [20, 100, 20]
	assert [_value(backwards, beat) for beat in (0.5, 2.0, 3.5)] == [20, 100, 20]
