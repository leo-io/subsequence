"""Mood - the sixteen conga-composer mood seeds as (scale, harmony_style) pairs.

The names, modes and V/E/T targets follow the conga-composer knowledge base
(§M.2 seed library, §M.3 synonym map).  A mood translates to a mode (for
pitch resolution and snap_to_scale) and a harmony style (for the chord
engine).  Nothing else changes - tempo, rhythm and expression are untouched;
the valence / energy / tension targets are carried as data for the caller.

Each seed is named by its KB id (``"uplifting"``, ``"melancholic"``,
``"dark"``…).  Any word from the KB synonym map, English or Portuguese, and
the seed's full label (``"Dark / hypnotic"``) resolve to the same seed, so
``"euphoric"``, ``"triste"`` and ``"saudade"`` are all valid mood names.

Usage::

	# Song level - sets scale and pre-seeds the harmony default
	composition = subsequence.Composition(bpm=120, key="F", mood="cool")
	composition.harmony(cycle_beats=4)   # uses dorian_minor automatically

	# Or call it live to shift the whole piece
	composition.mood("tense")

	# Section level - scale override + harmony style for the section's duration
	S = subsequence.Section
	composition.form([
	    S("intro",  8, mood="introspective"),
	    S("drop",   8, mood="uplifting"),
	    S("break",  4, mood="melancholic"),
	])

	# Pattern level - pitch only (auto snap_to_scale after each rebuild)
	@composition.pattern(channel=3, beats=4, mood="dreamy")
	def lead (p, chord):
	    p.arpeggio(chord, root=72, count=4, spacing=0.25)
"""

from __future__ import annotations

import dataclasses
import difflib
import typing
import unicodedata


@dataclasses.dataclass(frozen=True)
class MoodSpec:

	"""One KB mood seed and the harmonic axes it controls.

	Attributes:
		id: The KB seed id (e.g. ``"introspective"``).
		label: The KB seed label (e.g. ``"Introspective / deep"``).
		scale: Mode name for snap_to_scale and key-relative resolution
			(e.g. ``"dorian"``) - the first mode the KB lists for the seed.
		harmony_style: Chord-graph style name for
			``composition.harmony(style=...)`` (e.g. ``"dorian_minor"``).
		valence: KB valence target, −3 (dark) to +3 (bright).
		energy: KB energy target, 0 (calm) to 4 (intense).
		tension: KB tension target, 0 (settled) to 5 (unresolved).
	"""

	id: str
	label: str
	scale: str
	harmony_style: str
	valence: int
	energy: int
	tension: int


# KB §M.2 seed library: id → spec.  The comment is the KB signature harmony;
# the harmony style is the nearest built-in chord graph to it.
MOODS: typing.Dict[str, MoodSpec] = {spec.id: spec for spec in (
	#        id               label                     scale             harmony_style        V   E  T
	MoodSpec("uplifting",     "Uplifting",              "ionian",         "functional_major",   2, 3, 2),  # IVmaj9 – V9sus4 – iii7 – vi9
	MoodSpec("joyful",        "Joyful",                 "ionian",         "functional_major",   2, 4, 1),  # I – IV – I/5 – V7 shout vamp, 6/9 tonic
	MoodSpec("hopeful",       "Hopeful",                "ionian",         "functional_major",   1, 2, 2),  # vi9 – IVmaj9 – Iadd9 – V9sus4
	MoodSpec("nostalgic",     "Nostalgic / warm",       "ionian",         "functional_major",   1, 1, 1),  # Imaj9 – IVmaj7 – iv6 – Imaj9
	MoodSpec("sensual",       "Sensual / romantic",     "dorian",         "dorian_minor",       0, 1, 2),  # ii9 – V13sus4 – Imaj9, m11 pendulums
	MoodSpec("cool",          "Cool / laid-back",       "dorian",         "dorian_minor",       0, 2, 1),  # i9 – IV13 sway
	MoodSpec("bittersweet",   "Bittersweet / longing",  "melodic_minor",  "aeolian_minor",      0, 1, 2),  # IVmaj7 – iv6 – Imaj7; i(maj7) – i6
	MoodSpec("introspective", "Introspective / deep",   "dorian",         "dorian_minor",      -1, 1, 1),  # i9 – bVImaj9, quartal stacks
	MoodSpec("melancholic",   "Melancholic / sad",      "aeolian",        "aeolian_minor",     -2, 1, 1),  # i – bVI – bIII – bVII, line cliché
	MoodSpec("dark",          "Dark / hypnotic",        "phrygian",       "phrygian_minor",    -2, 3, 3),  # i – bII vamp, static ostinato
	MoodSpec("tense",         "Tense / suspenseful",    "harmonic_minor", "diminished",        -1, 2, 4),  # i – i(maj7) over a dominant pedal, °7 chains
	MoodSpec("aggressive",    "Aggressive / driving",   "phrygian",       "phrygian_minor",    -2, 4, 3),  # no-3rd riffs, bII stabs
	MoodSpec("mysterious",    "Mysterious / mystical",  "lydian",         "chromatic_mediant",  0, 1, 3),  # Imaj7#11 – II7, PL cycle (§15)
	MoodSpec("dreamy",        "Dreamy / floating",      "lydian",         "lydian_major",       2, 1, 1),  # Imaj9#11 – II/I over a tonic pedal
	MoodSpec("spiritual",     "Spiritual / devotional", "ionian",         "functional_major",   1, 2, 1),  # IV – iv6 – I, walk-ups, 6/9
	MoodSpec("triumphant",    "Triumphant / epic",      "ionian",         "chromatic_mediant",  2, 4, 2),  # bVI – bVII – I hero cadence
)}

# KB §M.3 synonym map: seed id → English and Portuguese words.
SYNONYMS: typing.Dict[str, typing.Tuple[str, ...]] = {
	"uplifting":     ("euphoric", "anthemic", "soaring", "peak-time", "edificante", "eufórico", "pra cima"),
	"joyful":        ("happy", "celebratory", "festive", "party", "alegre", "feliz", "festivo"),
	"hopeful":       ("optimistic", "rising", "sunrise", "esperançoso", "otimista"),
	"nostalgic":     ("warm", "sentimental", "nostálgico", "aconchegante"),
	"sensual":       ("romantic", "intimate", "sexy", "late-night", "romântico", "íntimo"),
	"cool":          ("chill", "smooth", "groovy", "laid-back", "tranquilo", "suave", "de boa"),
	"bittersweet":   ("longing", "yearning", "agridoce", "saudade"),
	"introspective": ("deep", "reflective", "contemplative", "introspectivo", "profundo", "reflexivo"),
	"melancholic":   ("sad", "blue", "mournful", "heartbroken", "triste", "melancólico", "sofrido"),
	"dark":          ("brooding", "ominous", "hypnotic", "sombrio", "escuro", "hipnótico"),
	"tense":         ("anxious", "uneasy", "suspense", "tenso", "ansioso"),
	"aggressive":    ("driving", "relentless", "angry", "agressivo", "pesado", "intenso"),
	"mysterious":    ("mystical", "magical", "otherworldly", "misterioso", "místico", "mágico"),
	"dreamy":        ("ethereal", "hazy", "floating", "etéreo", "sonhador"),
	"spiritual":     ("worship", "gospel", "prayerful", "espiritual", "louvor", "adoração"),
	"triumphant":    ("epic", "heroic", "victorious", "épico", "heróico", "triunfante"),
}


def _normalize (word: str) -> str:

	"""Lower-case, trim and strip accents, so ``"Eufórico"`` matches ``"euforico"``."""

	decomposed = unicodedata.normalize("NFKD", word.strip().lower())
	return "".join(c for c in decomposed if not unicodedata.combining(c))


def _build_index () -> typing.Dict[str, str]:

	"""Map every accepted spelling (id, label, synonym) to its seed id."""

	index: typing.Dict[str, str] = {}

	for seed_id, spec in MOODS.items():
		for word in (seed_id, spec.label, *SYNONYMS.get(seed_id, ())):
			index[_normalize(word)] = seed_id

	return index


_INDEX: typing.Dict[str, str] = _build_index()


def resolve_mood (name: str) -> MoodSpec:

	"""Return the :class:`MoodSpec` for *name*, raising :class:`ValueError` on unknown names.

	*name* may be a KB seed id, its label, or any English or Portuguese word
	from the KB synonym map; case and accents are ignored.  The sixteen seed
	ids are ``"uplifting"``, ``"joyful"``, ``"hopeful"``, ``"nostalgic"``,
	``"sensual"``, ``"cool"``, ``"bittersweet"``, ``"introspective"``,
	``"melancholic"``, ``"dark"``, ``"tense"``, ``"aggressive"``,
	``"mysterious"``, ``"dreamy"``, ``"spiritual"``, ``"triumphant"``.
	"""

	key = _normalize(name)
	seed_id = _INDEX.get(key)

	if seed_id is None:
		nearest = difflib.get_close_matches(key, sorted(_INDEX), n = 1)
		guess = f"Did you mean {_INDEX[nearest[0]]!r}? " if nearest else ""
		raise ValueError(
			f"Unknown mood {name!r}. {guess}"
			f"Valid moods: {', '.join(MOODS)} (or a KB synonym of one)"
		)

	return MOODS[seed_id]
