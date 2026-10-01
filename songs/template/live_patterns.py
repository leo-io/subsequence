"""Live patterns — form, section chords and parts.  Hot-swapped on every save.

TEMPLATE: every ``<<GENERATE …>>`` block is a placeholder, rewritten from
``song.md``.  Until then the file runs as one silent 4-bar section on the
tonic, so ``live_init.py`` starts cleanly.

Runs in a fresh namespace holding only ``composition`` and ``subsequence``.
"""

import logging
import pathlib

import subsequence.constants.instruments.gm_drums as gm_drums
import subsequence.constants.midi_notes as notes


log = logging.getLogger(f"{pathlib.Path(__file__).parent.name}.patterns")


# <<GENERATE part constants: channels and registers from song.md "Parts">>
DRUMS_CHANNEL = 10
BASS_CHANNEL = 2
PAD_CHANNEL = 3
LEAD_CHANNEL = 4

BASS_ROOT = notes.C2
PAD_ROOT = notes.C3
LEAD_LOW = notes.C4
LEAD_HIGH = notes.C5
# <</GENERATE>>


# <<GENERATE custom chord qualities: register_chord_quality(...) for any chart
# chord the parser has no spelling for (altered dominants etc.)>>
# <</GENERATE>>


# <<GENERATE section progressions: one subsequence.progression([...]).with_rhythm([...])
# per section from song.md "Blueprint" (durations in beats: bars x beats-per-bar)>>
SECTION_1 = subsequence.progression([1]).with_rhythm([16])
# <</GENERATE>>


# <<GENERATE long-lived generative state: created once, kept across saves>>
if "lead_state" not in composition.data:
	composition.data["lead_state"] = subsequence.MelodicState(low=LEAD_LOW, high=LEAD_HIGH)
	log.info("lead_state created")
# <</GENERATE>>


# <<GENERATE form: one Section(name, bars, energy=, key=, scale=, mood=) per blueprint row>>
FORM = subsequence.Form([
	subsequence.Section("section_1", 4, energy=0.5),
])

SECTION_CHORDS = {
	"section_1": SECTION_1,
}
# <</GENERATE>>

composition.data["form_bars"] = FORM.bars  # read by live_init.py to size the preview render
composition.form(FORM, loop=True)

for section_name, section_progression in SECTION_CHORDS.items():
	composition.section_chords(section_name, section_progression)

log.info("live patterns loaded: %d section(s), %d bars", len(FORM), FORM.bars)


def section_energy (p) -> float:

	"""The current section's energy, or a neutral 0.5 outside a form."""

	return p.section.energy if p.section else 0.5


def bar_chords (p, chord):

	"""The chords under this bar as (chord, beat, beats) - two where a chord changes mid-bar."""

	change = p.harmony.until_change

	if change is None or change >= p.bar_beats:
		return [(chord, 0.0, p.bar_beats)]

	return [(chord, 0.0, change), (p.harmony.chord_at(change), change, p.bar_beats - change)]


# One pattern per row of song.md "Parts".  Add or delete patterns to match.

@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def drums (p):

	"""<<GENERATE drums: from song.md Parts/Drums>>"""


@composition.pattern(channel=BASS_CHANNEL, beats=4)
def bass (p, chord):

	"""<<GENERATE bass: from song.md Parts/Bass — use bar_chords(p, chord) and BASS_ROOT>>"""


@composition.pattern(channel=PAD_CHANNEL, beats=4, voice_leading=True)
def pad (p, chord):

	"""<<GENERATE pad: from song.md Parts/Pad — use bar_chords(p, chord) and PAD_ROOT>>"""


@composition.pattern(channel=LEAD_CHANNEL, beats=4)
def lead (p, chord):

	"""<<GENERATE lead: from song.md Parts/Lead — composition.data["lead_state"], gated by section_energy(p)>>"""
