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
	assert composition._last_harmony_style == "diminished"


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
