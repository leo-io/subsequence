"""Mood - the sixteen conga-composer mood seeds as harmonic presets.

The names, modes, harmonic rhythms and V/E/T targets follow the
conga-composer knowledge base (§M.2 seed library, §M.3 synonym map).  A
mood is harmonic only - it never touches tempo, rhythm, dynamics or
voicing - and translates to:

- a **scale** (for pitch resolution, key-relative content and snap_to_scale);
- a **harmony style** (the live chord graph);
- a **harmonic rhythm** (how many bars each live chord lasts, from the KB's
  "1 per bar", "1 per 2 bars", "slow", "static" column);
- **sevenths** or triads (whether the live chords carry their diatonic
  sevenths, as the seed's signature chords do);
- a **key pull** from its tension: a settled seed is drawn to the key's
  centres, an unresolved one walks freely.

Valence is carried by the scale and the style; energy is the section's own
``energy=`` (a mood never changes it).  The V/E/T numbers stay on each seed
as data, for the caller to compare against.

A mood is one seed.  The KB's compound moods ("uplifting but sad") and
arcs ("builds to euphoric") are written as sections, each with its seed.

Each seed is named by its KB id (``"uplifting"``, ``"melancholic"``,
``"dark"``…).  Any word from the KB synonym map, English or Portuguese, and
the seed's full label (``"Dark / hypnotic"``) resolve to the same seed, so
``"euphoric"``, ``"triste"`` and ``"saudade"`` are all valid mood names.

Usage::

	# Song level - sets scale and pre-seeds the harmony defaults
	composition = subsequence.Composition(bpm=120, key="F", mood="cool")
	composition.harmony()   # dorian_minor, sevenths, a chord every 2 bars

	# Or call it live to shift the whole piece
	composition.mood("tense")

	# Section level - scale override, plus the live harmony settings for the
	# section's duration when composition.harmony() is on (a mood never
	# turns it on)
	S = subsequence.Section
	composition.form([
	    S("intro",  8, mood="introspective"),
	    S("drop",   8, mood="uplifting"),
	    S("break",  4, mood="melancholic"),
	])

	# Pattern level - pitch only: the mood's scale, with the sounding
	# chord's own tones kept (auto snap after each rebuild)
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

	"""One KB mood seed and the harmonic settings it stands for.

	Attributes:
		id: The KB seed id (e.g. ``"introspective"``).
		label: The KB seed label (e.g. ``"Introspective / deep"``).
		scale: Mode name for snap_to_scale and key-relative resolution
			(e.g. ``"dorian"``) - the KB mode that holds the signature's chords.
		harmony_style: Chord-graph style name for
			``composition.harmony(style=...)`` (e.g. ``"dorian_minor"``).
		modes: Every mode the KB lists for the seed, ``scale`` among them.
			An explicit ``scale=`` outside these is a different mood.
		bars_per_chord: The KB harmonic rhythm - bars each live chord
			lasts (``0.5`` = two chords a bar).
		sevenths: Whether the live chords carry their diatonic sevenths
			(``composition.harmony(sevenths=)``).
		valence: KB valence target, −3 (dark) to +3 (bright).
		energy: KB energy target, 0 (calm) to 4 (intense).
		tension: KB tension target, 0 (settled) to 5 (unresolved).
	"""

	id: str
	label: str
	scale: str
	harmony_style: str
	modes: typing.Tuple[str, ...]
	bars_per_chord: float
	sevenths: bool
	valence: int
	energy: int
	tension: int

	@property
	def key_pull (self) -> float:

		"""The ``harmony(key_pull=)`` the seed's tension asks for.

		Settled seeds (tension 0-2) are drawn to the key's centres, 0.6 down
		to 0.2; unresolved ones (3 and up) walk freely at 0.0.
		"""

		return round(max(0, 3 - self.tension) * 0.2, 1)


# KB §M.2 seed library: id → spec.  The comment is the KB signature harmony.
# The scale is the KB mode that holds the signature's chords (the first one
# listed, unless the signature needs another: sensual's major tonic, the
# bVI of introspective, the bVII of triumphant), and the harmony style is a
# chord graph that can play the signature's root motion.  Bars per chord
# read the KB rhythm column: "1 per bar" → 1, "1 per 2 bars" / "slow" → 2,
# "1 per 2-4 bars" / "static" → 4, "2-4 per bar" / "1-2 per bar" → 0.5,
# and 1 where it names no rate.  Sevenths follow the signature's chord
# qualities (maj9, m9, m11 → on; triads, power chords → off).
MOODS: typing.Dict[str, MoodSpec] = {spec.id: spec for spec in (
	#        id               label                     scale             harmony_style        modes                                    bars  7ths    V   E  T
	MoodSpec("uplifting",     "Uplifting",              "ionian",         "functional_major",  ("ionian", "mixolydian"),                1,    True,   2, 3, 2),  # IVmaj9 – V9sus4 – iii7 – vi9
	MoodSpec("joyful",        "Joyful",                 "ionian",         "functional_major",  ("ionian",),                             0.5,  False,  2, 4, 1),  # I – IV – I/5 – V7 shout vamp, 6/9 tonic
	MoodSpec("hopeful",       "Hopeful",                "ionian",         "functional_major",  ("ionian", "mixolydian"),                1,    True,   1, 2, 2),  # vi9 – IVmaj9 – Iadd9 – V9sus4
	MoodSpec("nostalgic",     "Nostalgic / warm",       "ionian",         "minor_plagal",      ("ionian",),                             1,    True,   1, 1, 1),  # Imaj9 – IVmaj7 – iv6 – Imaj9
	MoodSpec("sensual",       "Sensual / romantic",     "ionian",         "functional_major",  ("dorian", "ionian"),                    2,    True,   0, 1, 2),  # ii9 – V13sus4 – Imaj9, m11 pendulums
	MoodSpec("cool",          "Cool / laid-back",       "dorian",         "dorian_minor",      ("dorian",),                             2,    True,   0, 2, 1),  # i9 – IV13 sway
	MoodSpec("bittersweet",   "Bittersweet / longing",  "melodic_minor",  "melodic_minor",     ("melodic_minor", "ionian"),             1,    False,  0, 1, 2),  # IVmaj7 – iv6 – Imaj7; i(maj7) – i6
	MoodSpec("introspective", "Introspective / deep",   "aeolian",        "aeolian_minor",     ("dorian", "aeolian"),                   4,    True,  -1, 1, 1),  # i9 – bVImaj9, quartal stacks
	MoodSpec("melancholic",   "Melancholic / sad",      "aeolian",        "aeolian_minor",     ("aeolian",),                            2,    False, -2, 1, 1),  # i – bVI – bIII – bVII, line cliché
	MoodSpec("dark",          "Dark / hypnotic",        "phrygian",       "phrygian",          ("phrygian", "aeolian"),                 4,    False, -2, 3, 3),  # i – bII vamp, static ostinato
	MoodSpec("tense",         "Tense / suspenseful",    "harmonic_minor", "harmonic_minor",    ("harmonic_minor",),                     1,    False, -1, 2, 4),  # i – i(maj7) over a dominant pedal, °7 chains
	MoodSpec("aggressive",    "Aggressive / driving",   "phrygian",       "phrygian_power",    ("phrygian",),                           1,    False, -2, 4, 3),  # no-3rd riffs, bII stabs
	MoodSpec("mysterious",    "Mysterious / mystical",  "lydian",         "lydian_major",      ("lydian", "augmented", "whole_tone"),   2,    True,   0, 1, 3),  # Imaj7#11 – II7, PL cycle (§15)
	MoodSpec("dreamy",        "Dreamy / floating",      "lydian",         "lydian_major",      ("lydian",),                             2,    True,   2, 1, 1),  # Imaj9#11 – II/I over a tonic pedal
	MoodSpec("spiritual",     "Spiritual / devotional", "ionian",         "minor_plagal",      ("ionian",),                             0.5,  False,  1, 2, 1),  # IV – iv6 – I, walk-ups, 6/9
	MoodSpec("triumphant",    "Triumphant / epic",      "mixolydian",     "heroic",            ("ionian", "mixolydian"),                1,    False,  2, 4, 2),  # bVI – bVII – I hero cadence
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


def fits_mood (spec: MoodSpec, scale: str) -> bool:

	"""Whether *scale* is one of the modes the KB lists for *spec* (by pitch content, so aliases match)."""

	import subsequence.intervals

	pcs = set(subsequence.intervals.scale_pitch_classes(0, scale))

	return any(pcs == set(subsequence.intervals.scale_pitch_classes(0, mode)) for mode in spec.modes)


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
