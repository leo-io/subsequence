"""The ARP 1601 Sequencer, as a sequencer model.

Written as a musician writes their own model: a function called once a step with
``s``, its controls its annotated parameters.  Where the hardware leaves a behaviour
open, the docstring says which way the model goes.  The facts are from ARP's own
owner's manual for the 1601.
"""

import typing

# The engine under the name a musician's own model file gives the package, so a
# packaged model reads as theirs does.  The dotted name cannot be reached while the
# package's __init__ is importing this module; the "as" form can.
import subsequence.plugins.sequencers.engine as sequencers


Bus = typing.Literal["1", "2", "3"]

SliderLane = sequencers.Lane[sequencers.Knob]
BusLane = sequencers.Lane[Bus]

# The quantised outputs' range: two octaves of semitones across the sliders' travel.
QUANTISED_SEMITONES = 24


@sequencers.model(
	stages = 16,
	inputs = {
		"step": sequencers.TRIGGER,
		"reset": sequencers.TRIGGER,
		"start": sequencers.TRIGGER,
		"stop": sequencers.TRIGGER,
		"cv_in": sequencers.CV,
		"quantiser_a": sequencers.CV,
		"quantiser_b": sequencers.CV,
	},
	outputs = {
		"out_a": sequencers.CV,
		"out_b": sequencers.CV,
		"quantised_a": sequencers.CV,
		"quantised_b": sequencers.CV,
		"bus1": sequencers.GATE,
		"bus2": sequencers.GATE,
		"bus3": sequencers.GATE,
		"position_1": sequencers.TRIGGER,
		"clocked_bus1": sequencers.TRIGGER,
	},
	normals = [("out_a", "quantiser_a", None), ("out_b", "quantiser_b", None)],
	patch = [("clock.out", "@.step"), ("clock.out", "midi.trigger"), ("@.quantised_a", "midi.pitch")],
	label = "ARP 1601 Sequencer",
)
def arp_1601 (
	s: sequencers.StepContext,
	slider: SliderLane = 0.0,
	bus: BusLane = "1",
	bus_3: typing.Literal["skip", "off", "reset"] = "off",
	split: typing.Literal["16/1", "8/2"] = "16/1",
	order: typing.Literal["sequential", "random"] = "sequential",
) -> None:

	"""Sixteen sliders on three gate buses, bus 3 skipping or resetting, two quantisers, 16/1 or 8/2.

	Reaching a step on bus 3 with ``bus_3`` on reset goes straight to step 1, so the reset step
	takes no time and never sounds.  In 8/2 the halves run side by side to A and B, and a bus
	switch in either half acts.  The sliders themselves are unquantised (``out_a``, ``out_b``);
	each quantiser is normalled from its output and rounds to semitones over two octaves, and
	``cv_in`` is added after both, so a keyboard transposes by exact semitones.  Random order
	draws from the module's own seeded stream.
	"""

	span = 8 if split == "8/2" else 16

	if s.stage > span:
		s.stage = (s.stage - 1) % span + 1

	def buses (n: int) -> typing.Set[str]:
		found = {bus[n - 1]}
		if span == 8:
			found.add(bus[n + 7])
		return found

	if s.received("stop"):
		s.memory["running"] = False
	if s.received("start"):
		s.memory["running"] = True

	moved = False

	if s.received("reset"):
		s.stage, moved = 1, True
	elif s.received("step") and s.memory.get("running", True):
		n = s.stage
		for _ in range(span):
			n = s.rng.randrange(span) + 1 if order == "random" else n % span + 1
			if "3" in buses(n) and bus_3 == "skip":
				continue
			if "3" in buses(n) and bus_3 == "reset":
				n = 1
			break
		s.stage, moved = n, True
		if "1" in buses(n):
			s.fire("clocked_bus1")

	if moved and s.stage == 1:
		s.fire("position_1")

	if s.stage:
		s.send("out_a", slider[s.stage - 1])
		s.send("out_b", slider[s.stage + 7] if span == 8 else slider[s.stage - 1])

	on = buses(s.stage) if s.stage else set()

	for b in ("1", "2", "3"):
		s.send(f"bus{b}", b in on)

	for side in ("a", "b"):
		raw = min(1.0, max(0.0, s.read(f"quantiser_{side}")))
		s.send(f"quantised_{side}", round(raw * QUANTISED_SEMITONES) / sequencers.SEMITONES + s.read("cv_in"))


sequencers.register(arp_1601)
