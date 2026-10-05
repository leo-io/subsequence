"""Tests for moods — the conga-composer KB seeds at song, section and pattern level."""

import pathlib

import mido
import pytest

import subsequence
import subsequence.harmonic_state
import subsequence.intervals
import subsequence.mood


KB_SEEDS = [
	"uplifting", "joyful", "hopeful", "nostalgic", "sensual", "cool", "bittersweet", "introspective",
	"melancholic", "dark", "tense", "aggressive", "mysterious", "dreamy", "spiritual", "triumphant",
]


def test_the_moods_are_the_sixteen_kb_seeds () -> None:

	"""The table is keyed by the KB §M.2 seed ids, each carrying its V/E/T targets in range."""

	assert list(subsequence.mood.MOODS) == KB_SEEDS
	assert list(subsequence.mood.SYNONYMS) == KB_SEEDS

	for seed_id, spec in subsequence.mood.MOODS.items():
		assert spec.id == seed_id
		assert -3 <= spec.valence <= 3
		assert 0 <= spec.energy <= 4
		assert 0 <= spec.tension <= 5


@pytest.mark.parametrize("seed_id", KB_SEEDS)
def test_every_seed_names_a_real_mode_and_style (seed_id: str) -> None:

	"""Each scale works with harmony and snap_to_scale, and each style builds a chord graph."""

	spec = subsequence.mood.MOODS[seed_id]

	assert spec.scale in subsequence.intervals.SCALE_MODE_MAP
	subsequence.intervals.scale_pitch_classes(0, spec.scale)
	subsequence.harmonic_state._resolve_graph_style(spec.harmony_style, True, 0.5)


def test_mode_follows_the_kb_valence_ladder () -> None:

	"""Brighter seeds sit on brighter modes: a spot check of the M.1 ladder against M.2."""

	scale = {seed_id: spec.scale for seed_id, spec in subsequence.mood.MOODS.items()}

	assert scale["dreamy"] == "lydian"
	assert scale["joyful"] == "ionian"
	assert scale["cool"] == "dorian"
	assert scale["melancholic"] == "aeolian"
	assert scale["dark"] == "phrygian"
	assert scale["tense"] == "harmonic_minor"
	assert scale["bittersweet"] == "melodic_minor"


def test_synonyms_labels_and_accents_resolve_to_their_seed () -> None:

	"""English and Portuguese synonyms, the KB label, case and accents all reach the seed."""

	resolve = subsequence.mood.resolve_mood

	assert resolve("euphoric").id == "uplifting"
	assert resolve("Dark / hypnotic").id == "dark"
	assert resolve("hypnotic").id == "dark"
	assert resolve("triste").id == "melancholic"
	assert resolve("saudade").id == "bittersweet"
	assert resolve("Eufórico").id == "uplifting"
	assert resolve("euforico").id == "uplifting"
	assert resolve("pra cima").id == "uplifting"
	assert resolve("  EPIC ").id == "triumphant"


def test_no_synonym_belongs_to_two_seeds () -> None:

	"""A word maps to exactly one seed, so the index never silently overwrites one."""

	seen: dict = {}

	for seed_id, words in subsequence.mood.SYNONYMS.items():
		for word in (seed_id, subsequence.mood.MOODS[seed_id].label, *words):
			key = subsequence.mood._normalize(word)
			assert seen.setdefault(key, seed_id) == seed_id, f"{word!r} names {seen[key]} and {seed_id}"


def test_an_unknown_mood_is_refused_with_a_suggestion () -> None:

	"""A typo raises ValueError naming the nearest spelling; retired ad-hoc names are refused."""

	with pytest.raises(ValueError, match = "Did you mean 'melancholic'"):
		subsequence.mood.resolve_mood("melancolic")

	with pytest.raises(ValueError, match = "Unknown mood"):
		subsequence.mood.resolve_mood("anointed")


def test_section_stores_the_seed_id_and_derives_its_scale () -> None:

	"""A synonym is normalised to the seed id; an explicit scale wins over the mood's."""

	section = subsequence.Section("drop", 8, mood="chill")

	assert section.mood == "cool"
	assert section.scale == "dorian"

	explicit = subsequence.Section("groove", 8, mood="dark", scale="aeolian")

	assert explicit.mood == "dark"
	assert explicit.scale == "aeolian"


def test_composition_mood_sets_scale_and_default_style (patch_midi: None) -> None:

	"""Composition(mood=) and composition.mood() set the seed's scale and harmony style."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, key="F", mood="cool")

	assert composition.scale == "dorian"
	assert composition._last_harmony_style == "dorian_minor"

	composition.mood("tense")

	assert composition.scale == "harmonic_minor"
	assert composition._last_harmony_style == "harmonic_minor"


def test_pattern_mood_snaps_every_note_into_the_mood_scale (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""A chromatic run on a mood="dark" pattern renders only C Phrygian pitch classes."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, key="C", seed=3)

	@composition.pattern(channel=1, beats=4, mood="sombrio")
	def run (p):

		"""Twelve chromatic notes, one per sixteenth."""

		for step in range(12):
			p.note(60 + step, beat=step * 0.25, duration=0.2)

	filename = tmp_path / "mood.mid"
	composition.render(bars=1, filename=str(filename))

	played = {
		message.note % 12
		for message in mido.MidiFile(str(filename))
		if message.type == "note_on" and message.velocity > 0
	}

	assert played
	assert played <= set(subsequence.intervals.scale_pitch_classes(0, "phrygian"))


def _render_chords (composition: subsequence.Composition, bars: int, tmp_path: pathlib.Path) -> list:

	"""Render *bars* and return (section name, chord, harmony key, style) for every cycle of a probe pattern."""

	seen = []

	@composition.pattern(channel=1, beats=4)
	def probe (p, chord):

		"""Record what the live harmony gives each section."""

		name = p.section.name if p.section else None
		seen.append((name, chord, composition._harmonic_state.key_name, composition._last_harmony_style))
		p.note(60, beat=0)

	composition.render(bars=bars, filename=str(tmp_path / "chords.mid"))

	return seen


def test_section_key_moves_the_live_chords (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Section(key="Ab", mood="uplifting") plays Ab major chords in an F minor song, then F minor again after."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, key="F", scale="aeolian", seed=1)
	composition.harmony(style="aeolian_minor")
	composition.form([
		subsequence.Section("verse", 2),
		subsequence.Section("chorus", 4, key="Ab", mood="uplifting"),
		subsequence.Section("outro", 2),
	], loop=False)

	seen = _render_chords(composition, 8, tmp_path)
	ab_major = set(subsequence.intervals.scale_pitch_classes(8, "ionian"))
	chorus = [row for row in seen if row[0] == "chorus"]

	assert chorus
	for _, chord, key, style in chorus:
		assert (key, style) == ("Ab", "functional_major")
		assert {tone % 12 for tone in chord.tones(60)} <= ab_major

	assert {(key, style) for name, _, key, style in seen if name in ("verse", "outro")} == {("F", "aeolian_minor")}


def test_leaving_a_mood_section_returns_to_the_authors_style (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""A section without a mood plays harmony(style=) again, not the mood section's style."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, key="C", seed=1)
	composition.harmony(style="dorian_minor")
	composition.form([
		subsequence.Section("a", 2),
		subsequence.Section("b", 2, mood="dark"),
		subsequence.Section("c", 2),
	], loop=False)

	styles = {name: style for name, _, _, style in _render_chords(composition, 6, tmp_path) if name}

	assert styles == {"a": "dorian_minor", "b": "phrygian", "c": "dorian_minor"}


def test_a_style_named_after_composition_mood_is_the_one_returned_to (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""harmony(style=) after Composition(mood=) replaces the mood's style as the one a moodless section plays."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, key="C", mood="cool", seed=1)
	composition.harmony(style="mixolydian")
	composition.form([
		subsequence.Section("a", 2, mood="dreamy"),
		subsequence.Section("b", 2),
	], loop=False)

	styles = {name: style for name, _, _, style in _render_chords(composition, 4, tmp_path) if name}

	assert styles == {"a": "lydian_major", "b": "mixolydian"}


def test_sections_sharing_a_mood_and_key_keep_one_chord_graph (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Consecutive sections with the same mood and key do not rebuild the harmony."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, key="C", seed=1)
	composition.harmony()
	composition.form([
		subsequence.Section("a", 2, mood="cool"),
		subsequence.Section("b", 2, mood="chill"),
		subsequence.Section("c", 2, mood="cool"),
	], loop=True)

	_render_chords(composition, 6, tmp_path)

	# One build from harmony(), one when "a" switches to dorian_minor; "b" and "c" reuse it.
	assert composition._harmony_count == 2


def test_pattern_mood_leaves_drum_notes_alone (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""A drum pattern with mood="dark" keeps its kit pieces: snare 38 and closed hat 42 are not snapped to C Phrygian."""

	import subsequence.constants.instruments.gm_drums as gm_drums

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, key="C")

	@composition.pattern(channel=10, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP, mood="dark")
	def drums (p):

		"""Kick, snare and closed hat - two of them outside C Phrygian as pitches."""

		p.hit_steps("kick_1", [0, 8])
		p.hit_steps("snare_1", [4, 12])
		p.hit_steps("hi_hat_closed", [2, 6])

	filename = tmp_path / "drums.mid"
	composition.render(bars=1, filename=str(filename))

	played = {
		message.note
		for message in mido.MidiFile(str(filename))
		if message.type == "note_on" and message.velocity > 0
	}

	assert played == {gm_drums.GM_DRUM_MAP[name] for name in ("kick_1", "snare_1", "hi_hat_closed")}


def test_a_section_mood_does_not_turn_live_harmony_on (patch_midi: None, tmp_path: pathlib.Path) -> None:

	"""Without harmony(), a mood section sets its scale and leaves live harmony off."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, key="C")
	composition.form([subsequence.Section("a", 1), subsequence.Section("b", 1, mood="dreamy")], loop=False)
	scales = {}

	@composition.pattern(channel=1, beats=4)
	def probe (p):

		"""Record the scale each section gives the builder."""

		scales[p.section.name if p.section else None] = p.scale
		p.note(60, beat=0)

	composition.render(bars=2, filename=str(tmp_path / "off.mid"))

	assert scales["b"] == "lydian"
	assert composition._harmonic_state is None


def test_harmony_turned_on_inside_a_mood_section_starts_on_its_style (patch_midi: None) -> None:

	"""A first harmony() with no style, inside a mood section, uses the section's mood."""

	import types

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120, key="C")
	composition._handle_section_harmony(types.SimpleNamespace(name="b", mood="dreamy", key=None, scale="lydian"))
	composition.harmony()

	assert composition._last_harmony_style == "lydian_major"
	assert composition._base_harmony_style is None


def test_a_mood_section_with_no_key_warns_once_instead_of_raising (patch_midi: None, tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture) -> None:

	"""A mood with no key anywhere is named once in a warning; no listener error is logged."""

	composition = subsequence.Composition(output_device="Dummy MIDI", bpm=120)
	composition.form([subsequence.Section("a", 1, mood="dark"), subsequence.Section("b", 1)], loop=True)

	@composition.pattern(channel=1, beats=4)
	def probe (p):

		"""One note, so the render has something to play."""

		p.note(60, beat=0)

	with caplog.at_level("WARNING"):
		composition.render(bars=4, filename=str(tmp_path / "keyless.mid"))

	warned = [record for record in caplog.records if "no key resolves" in record.getMessage()]

	assert len(warned) == 1
	assert "'a'" in warned[0].getMessage()
	assert not [record for record in caplog.records if record.levelname == "ERROR"]


# The chords (in C) each seed's KB signature moves between, which its chord
# graph must contain.  Bittersweet, nostalgic and spiritual are absent: their
# signatures turn on chords (major tonic in melodic minor; borrowed iv6) no
# built-in graph has yet.
SIGNATURE_CHORDS = {
	"uplifting":     ["F", "G", "Em", "Am"],         # IVmaj9 – V9sus4 – iii7 – vi9
	"joyful":        ["C", "F", "G7"],               # I – IV – I/5 – V7
	"hopeful":       ["Am", "F", "C", "G"],          # vi9 – IVmaj9 – Iadd9 – V9sus4
	"sensual":       ["Dm", "G", "C"],               # ii9 – V13sus4 – Imaj9
	"cool":          ["Cm", "F"],                    # i9 – IV13
	"introspective": ["Cm", "Ab"],                   # i9 – bVImaj9
	"melancholic":   ["Cm", "Ab", "Eb", "Bb"],       # i – bVI – bIII – bVII
	"dark":          ["Cm", "Db"],                   # i – bII
	"tense":         ["Cm", "Cm(maj7)", "Bdim7"],    # i – i(maj7), °7
	"aggressive":    ["C5", "Db5"],                  # no-3rd riffs, bII stabs
	"mysterious":    ["C", "D"],                     # Imaj7#11 – II7
	"dreamy":        ["C", "D"],                     # Imaj9#11 – II/I
	"triumphant":    ["Ab", "Bb", "C", "Cm"],        # bVI – bVII – I; i – bVI – bVII – I
}


@pytest.mark.parametrize("seed_id", sorted(SIGNATURE_CHORDS))
def test_each_seeds_graph_can_play_its_signature (seed_id: str) -> None:

	"""The seed's chord graph, built in C, holds every chord of its KB signature's root motion."""

	import subsequence.chords

	spec = subsequence.mood.MOODS[seed_id]
	graph, _ = subsequence.harmonic_state._resolve_graph_style(spec.harmony_style, True, 0.5).build("C")
	nodes = set(graph.nodes())

	missing = [name for name in SIGNATURE_CHORDS[seed_id] if subsequence.chords.parse_chord(name) not in nodes]

	assert not missing, f"{seed_id} ({spec.harmony_style}) cannot play {missing}"
