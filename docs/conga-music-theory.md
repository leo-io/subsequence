# Music-Theory Knowledge Base for Harmony Agents (v2)

Sep 30, 2026 · @leonardo soares silva

## 0. Purpose and order of use

This knowledge base tells a harmony agent which chords to choose, how to voice and connect them, and how to check its own output. Target genres are gospel, soulful house and deep house, with Afro-Latin and bossa influences. Rules are written as constraints; §13 says which rule wins when two conflict.

Generation order:

1. Set the mood seed and the per-section mood arc (§M), then pick key, mode and genre profile (§1, §13).
2. Choose a progression from the idiom bank (§8) or build one from functions and frameworks (§2, §7).
3. Assign a chord-scale to every chord and pick legal tensions (§3).
4. Voice each chord (§4) and connect the voicings (§5).
5. Write the bass against the harmony (§6).
6. Set harmonic rhythm and comping rhythm (§9, §12).
7. Check against the melody (§10) and the section plan (§11).
8. Run the validation checklist (§13) and fix every failure before output.

Corrections from v1: the tumbao pattern was wrong; the son clave 2-side was wrong; "avoid triads" was too absolute; pad and lead registers overlapped with no collision rule; semitone modulation had no preparation; the backdoor cadence was defined for major only; E♭1 (38.9 Hz) sits at the bottom edge of most club subs rather than in a sweet spot.

## M. Mood: the top-level planning layer

Mood is the agent's first input. A mood seed resolves into concrete parameters (mode, chord vocabulary, tension, harmonic rhythm, register, voicing density, bass motion), and every later section executes those parameters.

### M.1 Mood model

Every mood is a point on three axes plus an optional color tag. Each axis is carried by different musical dimensions, which is what makes compound moods possible (M.6).

| Axis | Scale | Main carriers | Secondary carriers |
| --- | --- | --- | --- |
| Valence (dark ↔ bright) | −3 to +3 | Mode, chord quality, melody intervals (major vs minor 3rds and 6ths) | Register (higher = brighter), borrowed chords |
| Energy (calm ↔ intense) | 0 to 4 | Tempo, harmonic rhythm, rhythmic density, bass motion | Voicing width, register, dynamics |
| Tension (settled ↔ unresolved) | 0 to 5 | Dominant function, altered tensions, sus chords, pedals | Unresolved loop endings, dissonant ostinato |

Color tags (optional, one per section): mystical, nostalgic, sensual, spiritual, cinematic, mechanical.

### Mode brightness ladder

| Mode | Valence | Characteristic note | Mood words |
| --- | --- | --- | --- |
| Lydian | +3 | ♯4 | Dreamy, wonder, floating |
| Ionian | +2 | natural 4 and 7 | Happy, warm, resolved |
| Mixolydian | +1 | ♭7 | Earthy, confident, festive |
| Dorian | 0 | natural 6 in minor | Cool, soulful, hopeful-minor |
| Aeolian | −1 | ♭6 | Sad, melancholic, reflective |
| Phrygian | −2 | ♭2 | Dark, exotic, menacing |
| Locrian | −3 | ♭5 | Unstable, horror (rarely a tonic) |

**Reference tracks**

- Lydian — "The Simpsons Theme", Danny Elfman: the opening motif sits on the ♯4.
- Ionian — "Lovely Day", Bill Withers: plain major, warm and resolved.
- Mixolydian — "Sweet Home Alabama", Lynyrd Skynyrd: the ♭VII in the three-chord riff.
- Dorian — "Oye Como Va", Santana: the Am7 – D7 organ vamp, natural 6 in a minor key.
- Aeolian — "Losing My Religion", R.E.M.: ♭6, reflective, no leading tone.
- Phrygian — "Wherever I May Roam", Metallica: the ♭2 in the intro.
- Locrian — "Army of Me", Björk: unstable, never settling on a tonic.

Other scales: melodic minor (≈0, bittersweet, sophisticated); harmonic minor (−1.5, dramatic, exotic); whole-tone (dreamlike, suspended); hexatonic (mystical, §15); octatonic / diminished (tense, suspense).

### Chord-quality moods

| Quality | Valence | Mood words |
| --- | --- | --- |
| Major triad, 6/9 | +2 | Joyful, resolved, church warmth |
| add9 | +2 | Open, hopeful |
| maj7, maj9 | +1 | Warm, tender, nostalgic |
| maj7♯11 | +1 | Dreamy, wonder |
| 7sus4, 9sus4, 13sus4 | +1 | Open, uplifting, unresolved |
| 9, 13 (dominant) | +1 | Funky, confident |
| 7 (plain dominant) | 0 | Earthy, bluesy, forward motion |
| Quartal, power (no 3rd) | 0 | Spacious, neutral, modern |
| m7, m9, m11 | −1 | Cool, mellow, deep, sensual |
| m6 | −1 | Bittersweet, noir |
| 7♭9, 7alt | −1 | Urgent, dramatic, yearning |
| Augmented | −1 | Unsettled, dreamlike |
| Minor triad | −2 | Sad, plain |
| m(maj7) | −2 | Mystery, suspense |
| m7♭5 | −2 | Melancholy, searching |
| °7 | −3 | Anxious, dread, transitional |

**Reference tracks**

- Major triad, 6/9 — "Total Praise", Richard Smallwood: the 6/9 church tonic.
- add9 — "Every Breath You Take", The Police: the add9 guitar shapes.
- maj7, maj9 — "The Girl from Ipanema", Jobim: the opening Fmaj7.
- maj7♯11 — "Flying Theme" from E.T., John Williams: Lydian tonic.
- 7sus4 / 9sus4 / 13sus4 — "I Believe I Can Fly", R. Kelly: gospel sus dominants.
- 9, 13 — "Superstition", Stevie Wonder: the clavinet riff.
- 7 (plain dominant) — "Green Onions", Booker T. & the M.G.'s: bluesy forward motion.
- Quartal, no 3rd — "So What", Miles Davis: the 4th-stack named in §4.
- m7, m9, m11 — "Can You Feel It", Mr. Fingers: the m9 pad that defines deep house.
- m6 — "Michelle", The Beatles: the m6 that ends the descending line.
- 7♭9, 7alt — "Georgia on My Mind", Ray Charles: dramatic, yearning dominants.
- Augmented — "Oh! Darling", The Beatles: the opening augmented chord.
- Minor triad — "Billie Jean", Michael Jackson: a plain minor vamp.
- m(maj7) — "James Bond Theme": the held minor-major signature chord.
- m7♭5 — "Autumn Leaves": the minor ii–V into the tonic.
- °7 — "Oh Happy Day", Edwin Hawkins Singers: the passing °7 in the walk-up.

Measured valence of a passage (heuristic) = 0.5 × mode valence + 0.5 × mean chord valence. The agent compares it with the target and adjusts levers (M.4) when the gap exceeds 1.

### M.2 Mood seed library

Sixteen classic moods, each mapped to a harmonic preset. V = valence (−3 to +3), E = energy (0–4), T = tension (0–5). The agent starts from the preset and refines with levers (M.4).

| Seed | V | E | T | Modes | Signature harmony | Rhythm, voicing, bass |
| --- | --- | --- | --- | --- | --- | --- |
| Uplifting | +2 | 3 | 2 | Ionian, Mixolydian | IVmaj9 – V9sus4 – iii7 – vi9; sus chords resolving to major | 1 chord per bar; wide voicings; top line rising; walk-up bass |
| Joyful | +2 | 4 | 1 | Ionian | I – IV – I/5 – V7 shout vamp (§8); 6/9 tonic | 2–4 chords per bar; bright triads; root–5th bass |
| Hopeful | +1 | 2 | 2 | Ionian, Mixolydian | vi9 – IVmaj9 – Iadd9 – V9sus4 | 1 per bar; add9 colors; top voice rising |
| Nostalgic / warm | +1 | 1 | 1 | Ionian + borrowed iv | Imaj9 – IVmaj7 – iv6 – Imaj9 | 1 per bar; mid-register Rhodes; descending inner line |
| Sensual / romantic | 0 | 1 | 2 | Dorian, Ionian | ii9 – V13sus4 – Imaj9; m11 pendulums | 1 per 1–2 bars; close low-mid voicings |
| Cool / laid-back | 0 | 2 | 1 | Dorian | i9 – IV13 sway (§7) | 1 per 2 bars; one-voice moves |
| Bittersweet / longing | 0 | 1 | 2 | Melodic minor; major with borrowed iv | IVmaj7 – iv6 – Imaj7; i(maj7) – i6 | 1 per bar; chromatic inner line |
| Introspective / deep | −1 | 1 | 1 | Dorian, Aeolian | i9 – ♭VImaj9; quartal stacks | 1 per 2–4 bars; sparse, few voices |
| Melancholic / sad | −2 | 1 | 1 | Aeolian | i – ♭VI – ♭III – ♭VII; descending line cliché | Slow; low register; descending bass |
| Dark / hypnotic | −2 | 3 | 3 | Phrygian, Aeolian | i – ♭II vamp; static ostinato (§16) | Static; planing; mono low riff |
| Tense / suspenseful | −1 | 2 | 4 | Harmonic minor, octatonic | i – i(maj7) over a dominant pedal; °7 chains | Pedal bass; chromatic inner motion |
| Aggressive / driving | −2 | 4 | 3 | Phrygian, power chords | No-3rd riffs; ♭II stabs; dissonant ostinato | Fast; short stabs; mono bass |
| Mysterious / mystical | 0 | 1 | 3 | Lydian, hexatonic, whole-tone | Imaj7♯11 – II7; PL cycle; Em – G♯m (§15) | Slow; wide spread; common-tone links |
| Dreamy / floating | +2 | 1 | 1 | Lydian | Imaj9♯11 – II/I over a tonic pedal; planed maj9 shapes | Slow; pedal bass; planing |
| Spiritual / devotional | +1 | 2 | 1 | Ionian (gospel) | IV – iv6 – I; walk-ups; 6/9 (§8) | 1–2 per bar; church voicings |
| Triumphant / epic | +2 | 4 | 2 | Ionian, Mixolydian | ♭VI – ♭VII – I hero; i – ♭VI – ♭VII – I (§15) | Open triads; octave bass; rising top voice |

**Reference tracks per seed**

- Uplifting — "Lovely Day", Bill Withers.
- Joyful — "Sir Duke", Stevie Wonder: the bright brass interlude.
- Hopeful — "Optimistic", Sounds of Blackness.
- Nostalgic / warm — "Summer Madness", Kool & the Gang: the warm pad.
- Sensual / romantic — "Let's Get It On", Marvin Gaye.
- Cool / laid-back — "Moondance", Van Morrison: the Dorian sway in the verse.
- Bittersweet / longing — "Don't Know Why", Norah Jones.
- Introspective / deep — "Mystery of Love", Mr. Fingers.
- Melancholic / sad — "Someone Like You", Adele.
- Dark / hypnotic — "Angel", Massive Attack: static bass, one pitch set.
- Tense / suspenseful — "Jaws" main title, John Williams.
- Aggressive / driving — "Da Funk", Daft Punk.
- Mysterious / mystical — "Twin Peaks Theme", Angelo Badalamenti.
- Dreamy / floating — "Porcelain", Moby: pedal bass under floating pads.
- Spiritual / devotional — "Amazing Grace", Aretha Franklin.
- Triumphant / epic — "Star Wars" main title, John Williams.

### M.3 Seed format and synonym map

The agent accepts free text, maps every mood word to one of the 16 seeds, and stores the result in a fixed JSON structure.

| Seed | English words | Portuguese words |
| --- | --- | --- |
| Uplifting | uplifting, euphoric, anthemic, soaring, peak-time | edificante, eufórico, pra cima |
| Joyful | happy, celebratory, festive, party | alegre, feliz, festivo |
| Hopeful | optimistic, rising, sunrise | esperançoso, otimista |
| Nostalgic / warm | warm, nostalgic, sentimental | nostálgico, aconchegante |
| Sensual / romantic | romantic, intimate, sexy, late-night | sensual, romântico, íntimo |
| Cool / laid-back | chill, smooth, groovy, laid-back | tranquilo, suave, de boa |
| Bittersweet / longing | bittersweet, longing, yearning | agridoce, saudade |
| Introspective / deep | deep, reflective, contemplative | introspectivo, profundo, reflexivo |
| Melancholic / sad | sad, blue, mournful, heartbroken | triste, melancólico, sofrido |
| Dark / hypnotic | dark, brooding, ominous, hypnotic | sombrio, escuro, hipnótico |
| Tense / suspenseful | tense, anxious, uneasy, suspense | tenso, ansioso, suspense |
| Aggressive / driving | aggressive, driving, relentless, angry | agressivo, pesado, intenso |
| Mysterious / mystical | mysterious, mystical, magical, otherworldly | misterioso, místico, mágico |
| Dreamy / floating | dreamy, ethereal, hazy, floating | etéreo, sonhador |
| Spiritual / devotional | spiritual, worship, gospel, prayerful | espiritual, louvor, adoração |
| Triumphant / epic | epic, heroic, victorious, triumphant | épico, heróico, triunfante |

Parsing rules:

- "and", "but", "yet", "e", "mas" join moods into a compound for the same section (M.6).
- "into", "then", "builds to", "vira", "até" create an arc across sections (M.5).
- "slightly", "a bit", "levemente" give a weight of 0.3; "very", "muito" give 0.7. Without weights, the first-named mood gets 0.6.
- A section holds at most 2 moods plus one color tag; weights sum to 1.
- An unknown word maps to the nearest seed by meaning; if none fits, the agent asks once.

### Seed JSON

```json
{
  "mood_seed": {
    "text": "uplifting but sad, builds to euphoric",
    "global": {
      "moods": [
        { "id": "uplifting", "weight": 0.6 },
        { "id": "melancholic", "weight": 0.4 }
      ],
      "color": null
    },
    "allocation": { "valence": "melancholic", "energy": "uplifting", "tension": "uplifting" },
    "arc": [
      { "section": "intro", "moods": [{ "id": "introspective", "weight": 1 }], "energy": 1 },
      { "section": "build", "moods": [{ "id": "hopeful", "weight": 1 }], "energy": 3 },
      { "section": "drop", "moods": [{ "id": "uplifting", "weight": 0.6 }, { "id": "melancholic", "weight": 0.4 }], "energy": 4 }
    ],
    "targets": { "valence": 0, "energy": 3, "tension": 2 }
  }
}
```

### M.4 Mood levers and transitions

The agent moves a section toward its target mood by pulling levers, one or two at a time. Each lever mainly affects one axis.

| Lever | Brighter | Darker | More energy | Less energy |
| --- | --- | --- | --- | --- |
| Mode | One step up the ladder (Aeolian → Dorian) | One step down (Dorian → Aeolian) | — | — |
| Chord quality | Minor → major (P), 6/9, sus resolving to major | Major → minor, m6, ♭9 colors | — | — |
| Borrowed chords | ♭VII, IV (Dorian) in minor | iv, ♭VI in major | — | — |
| Bass direction | Ascending | Descending | Ascending, faster | Pedal or static |
| Register | Raise pad and top voice | Lower them | Widen the spread | Narrow it |
| Harmonic rhythm | — | — | Double it | Halve it |
| Voicing density | — | — | More voices, full voicings | Shells, fewer voices |
| Tension | Resolve to a major tonic | End on unresolved minor | Sus or dominant pedal before the peak | Remove dominants |
| Key | Lift +1 or +2 semitones | — | Lift | — |
| Top-voice contour | Rising | Falling | Rising to a peak | Falling or held |

### Transition techniques

| Technique | How | Mood effect | Example |
| --- | --- | --- | --- |
| Parallel shift | Keep the root, switch major ↔ minor | Large valence change, same tonic | Cm9 → Cmaj9 |
| Relative shift | Same notes, new tonic | Valence change with very smooth harmony | C – G – Am → Am – F – C (tonic moves to vi) |
| One-note mode step | Change only the characteristic note | Small valence change | C Ionian → C Lydian (F → F♯) |
| Common-tone bridge | Hold the top voice across the change | Smooth color change | Wormhole (§7) |
| Tension spike | One bar of sus, dominant or °7 before the new mood | Dramatic shift | V7sus4 → new section |
| Pedal hand-off | Keep the bass pedal while the upper harmony changes | Gradual shift | Breakdowns |
| Key lift | +1 or +2 semitones with preparation (§11) | Brighter, higher energy | Final chorus |

Rules:

- Within a section, change at most 2 levers per 4 bars. At a boundary tagged "contrast", up to 4.
- A valence jump larger than 2 points needs a transition technique, unless the boundary is tagged "hard cut".
- Energy may drop instantly (breakdowns) but should rise over at least 4 bars.

### M.5 Mood arcs through song sections

A song is planned as a mood arc: one mood (or compound) per section, with valence, energy and tension targets the agent must hit. Energy follows the §11 tension rules; valence can move freely but makes at most one jump larger than 2 points per 32 bars.

**Template A: soulful house, "euphoric melancholy"**

| Section | Mood | V | E | T | Main move |
| --- | --- | --- | --- | --- | --- |
| Intro | Introspective | −1 | 1 | 1 | Tonic pedal, m9 only |
| Verse | Cool | 0 | 2 | 1 | Dorian sway |
| Build | Hopeful | +1 | 3 | 3 | Ascending bass, sus chords |
| Drop | Uplifting + melancholic | 0 | 4 | 2 | Minor loop with rising bass and top line (M.6) |
| Breakdown | Bittersweet | 0 | 1 | 2 | Same loop reharmonized with iv6 and borrowed chords; same top note |
| Drop 2 | Uplifting | +1 | 4 | 2 | Last chord of the loop switched to major (parallel shift) |
| Outro | Introspective | −1 | 1 | 1 | Mirrors the intro |

**Template B: gospel build**

| Section | Mood | V | E | T | Main move |
| --- | --- | --- | --- | --- | --- |
| Intro | Spiritual | +1 | 1 | 1 | Free-time plagal chords |
| Verse | Hopeful | +1 | 2 | 2 | Sus 2-5-1s, walk-ups |
| Pre-chorus | Tense (light) | 0 | 3 | 3 | Backcycle, secondary dominants |
| Chorus | Joyful | +2 | 3 | 1 | Strong I arrivals, 6/9 |
| Vamp | Triumphant | +2 | 4 | 2 | Shout vamp with semitone lifts |
| Ending | Spiritual | +1 | 1 | 0 | IV – iv6 – I "amen" |

**Template C: deep / techno journey**

| Section | Mood | V | E | T | Main move |
| --- | --- | --- | --- | --- | --- |
| Intro | Dark | −2 | 2 | 2 | Ostinato and rumble only |
| Groove | Dark / hypnotic | −2 | 3 | 3 | Fixed pitch set, filter movement |
| Break | Mysterious | 0 | 1 | 3 | Lydian or hexatonic pad over a pedal |
| Peak | Aggressive | −2 | 4 | 4 | Dissonant ostinato, denser percussion |
| Outro | Introspective | −1 | 2 | 1 | Pad thins out, ostinato returns |

Arc rules:

- In dance and gospel arcs, the 4–8 bars before a release peak carry higher tension than the peak itself (the release is the peak). Techno peaks may hold tension instead of releasing it.
- The last section of the arc returns to the opening mood family, unless the arc is tagged "journey".
- A recurring loop keeps its top note when its mood changes, so listeners hear the same idea in a new light.

### M.6 Compound moods (aggregation)

Never average a compound mood. Uplifting (V +2) and sad (V −2) average to a neutral 0, which sounds like neither. Instead, give each mood its own carriers: different axes, different layers, or different moments.

**Step 1. Classify the pair.**

- Cross-axis: the moods differ mainly on different axes (sad = low valence; uplifting = high energy and rising motion). Combine them directly with a dimension split.
- Same-axis: the moods pull the same axis in opposite directions (calm vs aggressive on energy; joyful vs melancholic with equal weight on valence). Use a layer split, a time split or ambivalent chords.

**Step 2. Pick a strategy.**

| Strategy | How | Best for |
| --- | --- | --- |
| Dimension split | Primary mood takes the valence carriers (mode, chord quality); secondary takes energy and motion carriers (groove, bass direction, top-line contour, harmonic rhythm) | Uplifting + sad, dark + driving |
| Layer split | Different instruments carry different moods | Calm + tense, sensual + dark |
| Time split within a loop | Mood A on most chords, mood B on the turn or final chord | Sad + hopeful, triumphant + sad |
| Time split across sections | Mood A in one section, mood B in the next | Pairs that cannot share a section |
| Ambivalent chords | Chords that contain both moods: maj7 = major triad + minor triad on its 3rd; m9 = minor triad + major 7th chord on its ♭3 | Bittersweet, joyful + nostalgic |

**Step 3. Apply the weights.**

- Primary mood (weight ≥ 0.6) owns the mode and the tonic chord quality.
- Secondary at 0.4: gets the energy and motion carriers plus about 1 color chord per 4 bars.
- Secondary at 0.2–0.3: gets only the top-line contour or 1 borrowed chord per 8 bars.
- Equal weights (0.5 / 0.5): use ambivalent chords or a time split within the loop.

### Compound recipes

| Compound | Strategy | Recipe | Example (A minor / C major) |
| --- | --- | --- | --- |
| Uplifting + sad ("euphoric melancholy") | Dimension split | Aeolian chords; bass rising ♭VI – ♭VII – i; top line rising; driving four-on-the-floor | Fmaj9 – G(add9) – Am9 – Am9 |
| Hopeful + melancholic (bittersweet) | Ambivalent chords | Major key that avoids long I chords; IVmaj7 – iv6 – Imaj7 | Fmaj7 – Fm6 – Cmaj7 |
| Joyful + nostalgic | Ambivalent + time split | Church turnaround with borrowed iv6 | C – C7/E – F – Fm6 – C |
| Dark + sensual | Dimension split | Minor 11 pendulum; slow harmonic rhythm; close low-mid voicings | Am11 – Dm11 |
| Calm + tense | Layer split | Static m9 pad over a pedal; a dissonant ostinato above it | Am9 pad + E–F ostinato |
| Mysterious + uplifting | Dimension split | Lydian harmony; rising arpeggio and bass energy | Cmaj7♯11 – D/C |
| Triumphant + sad | Time split within loop | Minor chords, then a hero cadence to a major tonic as the loop's last bar | Am – F – G – A |
| Spiritual + sad (lament) | Ambivalent chords | Minor gospel cadence with plagal color | Bm7♭5 – E7♭9 – Am9 – Dm6 – Am9 |
| Aggressive + uplifting | Dimension split | No-3rd riffs for energy; Mixolydian major stabs for valence | A5 riff + A – G – D stabs |

### Same-axis conflicts

| Pair | Why it conflicts | Resolution |
| --- | --- | --- |
| Calm + aggressive | Both on energy, opposite ends | Layer split (calm harmony, aggressive drums) or time split across sections |
| Joyful + melancholic, equal weights | Both on valence | Ambivalent chords, or melancholic loop with a joyful final chord |
| Settled + tense | Both on tension | Settled pedal bass with tension in the upper voices, resolved late |

### Compound validation

- Measured valence (M.1) of the harmony must match the mood assigned to the valence carriers, within ±1.
- Harmonic rhythm, bass direction and density must match the mood assigned to the energy carriers.
- If the measured valence lands near the average of the two moods (within ±0.5) and neither strategy is visible, the agent has averaged by mistake. Regenerate with an explicit split.

## 1. Tonal blueprint, registers and spacing limits

Pitch convention: scientific pitch, C4 = MIDI 60 = middle C (Ableton displays this as C3). MIDI = 12 × (octave + 1) + pitch class.

### Key selection

- Dance-floor default keys: E♭, F, G (major or minor). Gospel also favours A♭, D♭ and B♭, which sit well on piano and for vocal range.
- Sub-bass roots should fall between about 38 Hz and 75 Hz (E♭1 to D2, MIDI 27–38). E♭1 = 38.9 Hz is the lowest safe fundamental on most club systems; F1 = 43.7 Hz and G1 = 49.0 Hz are safer.
- If a root falls below E♭1 (C1 = 32.7 Hz, D1 = 36.7 Hz), play it an octave higher or let the 5th carry the sub.

### Register allocation

| Layer | Range | MIDI | Content | Max voices |
| --- | --- | --- | --- | --- |
| Sub/bass | E♭1–B2 | 27–47 | Root, 5th, octave, walk-ups, counter-lines | 1 |
| Low shell (optional) | C3–B3 | 48–59 | Guide tones (3rd, 7th) only | 2 |
| Chord/pad | E3–G5 | 52–79 | Extended voicings, drop-2, quartal, upper structures | 3–5 |
| Lead/vocal | C4–C6 | 60–84 | Hooks, vocal line, top-line fills | 1 |

Collision rule: while the melody sounds, the pad's top voice stays at least 3 semitones below the melody note. If it would not, drop that pad voice an octave or omit it. Never double the melody in unison inside the pad.

### Low-interval limits

The lower note of each interval must be at or above the listed pitch, or the interval turns to mud. With a heavy sub layer underneath, add a safety margin of about 5 semitones.

| Interval | Lowest allowed lower note | MIDI |
| --- | --- | --- |
| Minor 2nd | E3 | 52 |
| Major 2nd | E♭3 | 51 |
| Minor 3rd | C3 | 48 |
| Major 3rd | B♭2 | 46 |
| Perfect 4th | B♭2 | 46 |
| Tritone | B2 | 47 |
| Perfect 5th | B♭1 | 34 |
| Minor 6th | G2 | 43 |
| Major 6th | F2 | 41 |
| Minor 7th | F2 | 41 |
| Major 7th | F2 | 41 |
| Minor 9th | E2 | 40 |
| Major 9th | E♭2 | 39 |

### Spacing

- Wide intervals at the bottom, tight intervals at the top (overtone-series principle).
- The lowest pad note sits at least an octave above the bass note, unless the pad is deliberately playing a shell in the low-shell layer.
- Adjacent upper voices are never more than an octave apart.
- Keep no more than 4 chord voices between 200 and 500 Hz (about G3 to B4).

## 2. Functional harmony foundation

Every chord the agent writes must carry a function label (tonic, predominant, dominant, or color). Substitutions in §7 replace functions, so they only work once this layer exists.

### Diatonic 7th chords per mode

| Degree | Ionian | Dorian | Aeolian | Mixolydian | Lydian | Harmonic minor | Melodic minor |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Imaj7 | i7 | i7 | I7 | Imaj7 | i(maj7) | i(maj7) |
| 2 | ii7 | ii7 | iiø7 | ii7 | II7 | iiø7 | ii7 |
| 3 | iii7 | ♭IIImaj7 | ♭IIImaj7 | iiiø7 | iii7 | ♭IIImaj7♯5 | ♭IIImaj7♯5 |
| 4 | IVmaj7 | IV7 | iv7 | IVmaj7 | ♯ivø7 | iv7 | IV7 |
| 5 | V7 | v7 | v7 | v7 | Vmaj7 | V7 | V7 |
| 6 | vi7 | viø7 | ♭VImaj7 | vi7 | vi7 | ♭VImaj7 | viø7 |
| 7 | viiø7 | ♭VIImaj7 | ♭VII7 | ♭VIImaj7 | vii7 | vii°7 | viiø7 |

### Function categories

| Function | Major key | Minor key | Role |
| --- | --- | --- | --- |
| Tonic | I, iii, vi | i, ♭III, ♭VI (weak) | Rest, arrival |
| Predominant | ii, IV | iiø, iv, ♭VI | Departure, sets up dominant |
| Dominant | V, vii° | V (raised 3rd), vii°7 | Tension that wants the tonic |
| Subdominant-minor (color) | iv, ♭VI, ♭VII, ♭II | same | Soft, plagal-style pull to tonic |

Default motion: T → PD → D → T. D → PD (retrogression) is allowed only when tagged as a deliberate modal or pop move.

### Root-motion strength

1. Down a 5th (up a 4th): strongest; default for chains.
2. Up a 2nd: strong, needs careful voice leading (no parallel 5ths in contrapuntal mode).
3. Down a 3rd: smooth, shares two common tones; good for prolonging a function.
4. Down a 2nd / up a 3rd: weaker; typical of modal and pop loops.
5. Chromatic, tritone, chromatic-mediant: color moves; require a common-tone or guide-tone link (§5).

### Secondary dominants

| Secondary | In C | Resolves to | Related ii |
| --- | --- | --- | --- |
| V7/ii | A7 | Dm7 | Em7♭5 – A7 |
| V7/iii | B7 | Em7 | F♯m7♭5 – B7 |
| V7/IV | C7 | Fmaj7 | Gm7 – C7 |
| V7/V | D7 | G7 | Am7 – D7 |
| V7/vi | E7 | Am7 | Bm7♭5 – E7 |

**Reference tracks**

- V7/V — "Take the A Train", Billy Strayhorn: the II7 that pulls into V.
- V7/IV — "Oh Happy Day", Edwin Hawkins Singers: the I7 that turns the tonic into a dominant of IV.
- Chained secondaries (3-6-2-5-1) — gospel backcycles; see §8 and "Total Praise", Richard Smallwood.

A secondary dominant resolves down a 5th to its target, or chromatically via its tritone substitute. Its 3rd is the temporary leading tone of the target.

Chains: 3-6-2-5-1 = iii7 – VI7 – ii7 – V7 – I (backcycle); 7-3-6 = viiø7 – III7 – vi7.

### Modal interchange (borrowed from the parallel minor)

| Chord | In C | Typical use |
| --- | --- | --- |
| iv7 / iv6 | Fm7 / Fm6 | IV → iv → I "church" plagal |
| ♭VImaj7 | A♭maj7 | Deceptive target, ♭VI – ♭VII – I |
| ♭VII7 | B♭7 | Backdoor dominant |
| ♭IIImaj7 | E♭maj7 | Bright lift in a major loop |
| iiø7 | Dm7♭5 | Darker predominant before V7♭9 |
| ♭IImaj7 | D♭maj7 | Neapolitan, half-step approach to I |
| v7 | Gm7 | Mixolydian softening of V |

**Reference tracks**

- iv7 / iv6 (IV → iv → I) — "Creep", Radiohead: the major-to-minor IV is the hook; the same move is the gospel "holy" plagal in §8.
- ♭VImaj7 — "Just the Two of Us", Grover Washington Jr. with Bill Withers: the ♭VI that opens the loop.
- ♭VI – ♭VII – I — "Star Wars" throne-room cadence, John Williams: the hero release of §15.
- ♭II (Neapolitan) — "The Girl from Ipanema", Jobim: the ♭II7 that slides back to the tonic.

### Chromatic mediants

I can move to ♭III, III, ♭VI or VI (major or maj7 quality) when at least one common tone is held in the same voice. Example: Cmaj7 → A♭maj7 holds C and G.

## 3. Chord-scale theory: available tensions and avoid notes

Each chord gets a scale from its function and context; the scale decides which extensions are legal. An avoid note may appear only as a short passing tone (≤ 1/8 note, weak beat), never as a sustained voicing tone.

| Chord / context | Scale | Available tensions | Avoid notes |
| --- | --- | --- | --- |
| Imaj7 (tonic) | Ionian | 9, 13 (6) | 11 (♭9 above the 3rd) |
| IVmaj7, ♭VImaj7, ♭IImaj7 | Lydian | 9, ♯11, 13 | none |
| maj7♯5 | Lydian augmented | 9, ♯11, 13 | none |
| ii7, i7 in Dorian vamp | Dorian | 9, 11, 13 | none (13 is the Dorian color) |
| vi7, i7 in Aeolian | Aeolian | 9, 11 | ♭13 |
| iii7 | Phrygian | 11 | ♭9, ♭13 |
| m(maj7), m6 tonic | Melodic minor | 9, 11, 13 | none |
| V7 → major target | Mixolydian | 9, 13 | 11 (unless the 3rd is removed: sus) |
| ♭VII7, IV7 (blues), tritone subs, non-resolving II7 | Lydian dominant | 9, ♯11, 13 | none |
| V7 → minor target | Phrygian dominant (harm. minor mode 5) | ♭9, ♭13 | 11 |
| V7alt | Altered | ♭9, ♯9, ♯11, ♭13 | natural 9, natural 5 |
| V7♭9 with natural 13 | Half-whole diminished | ♭9, ♯9, ♯11, 13 | natural 9 |
| V7sus4 | Mixolydian | 9, 13 (♭9 = Phrygian sus) | 3rd (except as resolution) |
| m7♭5 (iiø) | Locrian | 11, ♭13 | ♭9 |
| m7♭5 with natural 9 | Locrian ♮2 (mel. minor mode 6) | 9, 11, ♭13 | none |
| °7 | Whole-half diminished | a whole step above each chord tone | none |

### Tension rules

- Never combine a natural and altered form of the same degree (9 with ♭9, 5 with ♯5) in one voicing. Exception: ♭9 and ♯9 together on an altered dominant.
- Dominant into a major target: natural 9 and 13 by default; altered tensions are color.
- Dominant into a minor target: ♭9 and ♭13 by default.
- A minor 9th between any two voices is forbidden, except the ♭9 above the root (or bass) of a dominant chord.
- ♯11 replaces 11 on major and dominant chords; natural 11 belongs to minor and sus chords.

## 4. Voicing rules

A voicing must contain the 3rd and 7th (guide tones) unless it is a sus, quartal or power voicing. When the bass plays the root, the pad goes rootless.

### General rules

- Omit in this order when thinning: root (if bass has it), then 5th (unless altered), then 11 or 13.
- Never double the leading tone, the chordal 7th, or any altered tension. Doubling root or 5th is fine.
- Pure root-position triads are not used as the only harmony in the pad. Triads are allowed as upper-structure triads, over a moving or slash bass, and in gospel shout sections.
- Clusters (adjacent 2nds) only above C4 and only where the low-interval limits allow (§1).
- The top voice is a melody: it should move by step or hold whenever possible.

### Rootless A/B voicings (default for ii–V–I and soulful keys)

| Form | Minor 7 | Dominant 7 | Major 7 |
| --- | --- | --- | --- |
| A | 3–5–7–9 | 3–13–7–9 | 3–5–7–9 |
| B | 7–9–3–5 | 7–9–3–13 | 6/7–9–3–5 |

Alternating A → B → A across root motion by 5ths keeps every voice within 2 semitones. In C: Dm9 (F A C E) → G13 (F A B E) → Cmaj9 (E G B D).

### Drop-2 and drop-2-4

- Drop-2: take a close-position 4-note chord and drop the second voice from the top by an octave. Cmaj7 close (C E G B) becomes G C E B.
- Drop-2-4: also drop the fourth voice from the top. Use for wide pad spreads over a sub bass.
- The lowest drop voice must still respect the low-interval limits.

### Quartal voicings

- Stack perfect 4ths from the mode's notes (3–4 voices). Over Dorian, any diatonic 4th-stack is legal and can plane stepwise inside the mode.
- "So What" voicing: three 4ths plus a major 3rd on top (E A D G B over Em7).
- A diatonic 4th-stack containing the tritone (F–B in C) implies a dominant; avoid it on a tonic minor vamp.

### Upper-structure triads over a dominant shell

Left hand plays the 3rd and ♭7 (for C7: E3 and B♭3); right hand plays a triad.

| Triad over C7 shell | Tensions added | Resulting chord | Scale |
| --- | --- | --- | --- |
| D major (II) | 9, ♯11, 13 | C13♯11 | Lydian dominant |
| A major (VI) | 13, ♭9, 3 | C13♭9 | Half-whole diminished |
| E♭ major (♭III) | ♯9, 5, ♭7 | C7♯9 | Half-whole / blues |
| A♭ major (♭VI) | ♭13, root, ♯9 | C7♯9♭13 | Altered |
| G♭ major (♭V) | ♯11, ♭7, ♭9 | C7♭9♯11 | Half-whole diminished |

On non-dominant chords: D/Cmaj7 = Cmaj9♯11; B♭/Cm = Cm11; F/G = G9sus4 (the gospel "4 over 5").

## 5. Voice-leading rules

The agent connects voicings by moving the fewest semitones, with guide tones leading. Rules apply to the pad and keys layers; the bass is governed by §6.

1. **Guide-tone lines.** On root motion down a 5th, the 7th of chord A falls by step to the 3rd of chord B, and the 3rd of A is held as the 7th of B. Dm7 → G7 → Cmaj7: C → B → B and F → F → E.
2. **Common tones.** A note shared by two consecutive chords stays in the same voice.
3. **Movement budget.** Each upper voice moves at most 2 semitones per change. One voice per change may move up to 4. Larger leaps only in the top voice, followed by a step in the opposite direction.
4. **Tendency tones.**
   - Chordal 7th resolves down by step.
   - Leading tone resolves up to the tonic when it is in an outer voice at V → I.
   - ♭9 resolves down a semitone to the target's 5th.
   - ♯9 (written ♭10) resolves down a semitone to the target's 9th, or is held.
   - ♭13 resolves down a semitone to the target's 9th (on a major target, it may rise to the 3rd).
   - ♯11 resolves down a semitone to the target's root, or is held as the target's 7th or 9th.
5. **Cadences.** Bass and top voice move in contrary motion at V → I and IV → I.
6. **Voice crossing.** Not allowed inside the pad. A lead line in a different timbre may cross the pad.

### Parallel-motion modes

The genre profile (§13) sets one of two modes per layer.

| Mode | Rules | Where |
| --- | --- | --- |
| Contrapuntal | No parallel 5ths or octaves between outer voices; voices move independently; rules 1–5 enforced | Gospel ballads and verses, neo-soul inner voices, bossa |
| Planing | The whole voicing moves in parallel; interval structure is locked; rules 1–4 relaxed | House stabs, organ chops, Detroit pads, quartal vamps |

### Smoothness score

Sum the absolute semitone movement of every upper voice between two chords (exclude the bass). Prefer the voicing with the lowest score. Break ties by the top-voice contour you want (holding or stepping toward the section's melodic peak).

## 6. Bass–harmony relationship

The bass owns the root by default and is monophonic below C3. In gospel and soulful house the bass is half the harmony: a slash bass changes the chord's meaning.

### Slash chords and inversions

| Symbol | In C | Meaning | Use |
| --- | --- | --- | --- |
| I/3 | C/E | First inversion | Passing step in walk-ups |
| I/5 | C/G | Cadential 6/4 | Before V in gospel cadences |
| IV/5 | F/G | G9sus4 / G11 | Gospel "4 over 5" dominant |
| ii7/5 | Dm7/G | G9sus4 | Soft dominant in house |
| ♭VII/1 | B♭/C | C9sus4 | House vamps, tonic pedal |
| iv/1 | Fm/C | Plagal over pedal | Church "amen" color |
| V/4 | G/F | Third inversion V7 | Resolves to I/3 (bass F → E) |
| ♭VI/♭VII | A♭/B♭ | B♭9sus4 | Lift into I (gospel, game-music cadence) |
| I7/3 | C7/E | Secondary dominant, inverted | Bass E → F into IV |

**Reference tracks**

- I/5 before V — "Oh Happy Day", Edwin Hawkins Singers: the cadential 6/4 in the church turnaround.
- IV/5 ("4 over 5") — "I Believe I Can Fly", R. Kelly: the sus dominant with no 3rd.
- ♭VII/1 over a tonic pedal — "Your Love", Frankie Knuckles: the floating house vamp.
- I/3 as a passing step — "Lean on Me", Bill Withers: the stepwise climb out of the tonic.

### Pedal points

- Tonic pedal: hold the root while the upper harmony moves (I – IV/1 – ♭VII/1 – I). Standard for intros and breakdowns.
- Dominant pedal: hold the 5th of the key under changing chords to build tension before a drop.
- Pair pedals with filter sweeps and percussion density (§11) rather than chord changes.

Reference: "Jump", Van Halen — the synth intro holds the bass on the tonic while the upper chords move.

### Bass-motion archetypes

| Archetype | Bass line (in C) | Chords |
| --- | --- | --- |
| Root–5th | C – G | Any |
| Diatonic walk-up | C – D – E – F | C – Dm7 – C/E – F |
| Chromatic walk-up | F – F♯ – G | F – F♯°7 – C/G |
| Descending line | C – B – B♭ – A | C – C/B – C7/B♭ – F/A |
| Tritone step-down | D – D♭ – C | Dm7 – D♭7 – Cmaj7 |
| Chromatic approach | Half-step below or above the target, last 8th or 16th of the bar | Any target |

**Reference tracks**

- Root–5th — "Billie Jean", Michael Jackson: one bass figure, no harmonic motion.
- Diatonic walk-up — "Lean on Me", Bill Withers: the verse climbs stepwise out of I.
- Descending line — "A Whiter Shade of Pale", Procol Harum: the bass walks down under a held harmony.
- Chromatic approach — any soulful-house bassline that lands the target root on the last 16th of the bar.

### Gospel walk-up

I – I/3 – IV – ♯IV°7 – I/5 – V7sus4 – V7 – I. In C: C – C/E – F – F♯°7 – C/G – G7sus4 – G7 – C.

### House bass

- One note at a time; root on offbeat 8ths or syncopated 16ths; octave jumps allowed.
- Bass and kick should not both sustain on beat 1 with full sub energy; either duck the bass or start it after the kick.

## 7. Progression frameworks and reharmonization

Each framework replaces or prolongs a function from §2. Examples are in C (or C minor) for readability; store them as Roman numerals.

| Framework | Formula | Example | Link rule | Genres |
| --- | --- | --- | --- | --- |
| Dorian sway | i9/i11 → IV13 | Cm11 → F13 | One-voice move: the minor 3rd stays, only the 7th of i’s voicing shifts (§14 ex. 2) | Funk, deep house, techno |
| Backdoor (major) | iv7 → ♭VII7 → Imaj7 | Fm7 → B♭7 → Cmaj7 | A♭ → G, D held | Gospel, bossa, disco |
| Backdoor (minor) | iv7 → ♭VII7 → i9 | Fm7 → B♭7 → Cm9 | B♭7 is diatonic in Aeolian; resolves without a leading tone | Soulful house |
| Tritone substitution | V7 → ♭II7(♯11) → I | G7 → D♭7♯11 → Cmaj7 | Shares guide tones B/C♭ and F; bass steps down chromatically | Gospel, jazz, deep house |
| Secondary tritone sub | V7/x → sub → x | A7 → E♭7 → Dm7 | Same rule applied to any secondary dominant | Gospel, neo-soul |
| Ascending passing °7 | I → ♯I°7 → ii7; ii7 → ♯ii°7 → iii7; IV → ♯IV°7 → I/5 | C → C♯°7 → Dm7 | °7 root a half-step below the target root (it is a rootless V7♭9 of the target) | Gospel, worship, house |
| Descending passing °7 | iii7 → ♭iii°7 → ii7 | Em7 → E♭°7 → Dm7 | Chromatic bass descent | Gospel, jazz |
| Common-tone °7 | I → °7/1 → I | C → C°7 → C | Bass held; upper voices neighbor by half-step | Gospel, ballads |
| Parallel planing | Fixed voicing moved by root motion | Cm9 → B♭m9 → A♭m9 | Interval structure locked; choose root motion diatonically or chromatically | Detroit techno, deep house |
| Major/minor shape switch | Imaj9 ↔ im9; IVmaj7 → iv7 | Gmaj9 → Gm9 | Only the 3rd (and 7th) move by a half-step | Classic and minimal house |
| Wormhole (common-tone link) | Any two distant chords sharing ≥ 2 tones | Cm11 ↔ A♭m11 | Hold E♭ (♭3 of Cm, 5 of A♭m) and B♭ (♭7 of Cm, 9 of A♭m) in the same voices | Neo-soul, deep house |
| Chromatic approach chord | Same quality, half-step above the target | D♭maj9 → Cmaj9 | Whole voicing slides down a semitone | Gospel, neo-soul |
| Line cliché | i → i(maj7) → i7 → i6 | Cm → Cm(maj7) → Cm7 → Cm6 | One inner voice descends C – B – B♭ – A | Gospel, soul ballads |
| Sus resolution | V9sus4 → V7♭9 → I | G9sus4 → G7♭9 → C | C (sus) → B; A → A♭ → G | Gospel, soulful house |
| Turnarounds | I – vi – ii – V; I – VI7 – ii – V; I – ♭III – ♭VI – ♭II | Cmaj7 – E♭maj7 – A♭maj7 – D♭maj7 | Last chord must point back to bar 1 (§9) | All |

**Reference tracks**

- Dorian sway — "Oye Como Va", Santana: the two-chord organ groove; "Moondance", Van Morrison, is the same sway in a song form.
- Tritone substitution — "The Girl from Ipanema", Jobim: the ♭II7 that replaces V on the way back to the tonic.
- Ascending passing °7 — "Oh Happy Day", Edwin Hawkins Singers: the ♯IV°7 inside the walk-up.
- Major/minor shape switch — "Creep", Radiohead: only the 3rd moves when the major chord turns minor.
- Line cliché — "Michelle", The Beatles, and "Stairway to Heaven", Led Zeppelin: one inner voice descends chromatically.
- Sus resolution — "I Believe I Can Fly", R. Kelly: 9sus4 into the altered dominant, then the tonic.
- Turnarounds — "Blue Moon": the textbook I – vi – ii – V pointing back to bar 1.
- Wormhole (common-tone link) — "Just the Two of Us", Grover Washington Jr.: distant chords tied by shared tones.

### Top-down melody reharmonization

Hold one melody pitch and change the bass so the note takes a new role. Every role must be a chord tone or an available tension (§3). For melody note C:

| Bass | Chord | Role of C |
| --- | --- | --- |
| C | Cmaj7 | Root |
| A | Am7 | ♭3 |
| A♭ | A♭maj7 | 3rd |
| F | Fmaj9 | 5th |
| D | Dm7 | ♭7 |
| D♭ | D♭maj7 | Major 7th |
| B♭ | B♭9sus4 | 9th |
| G | G9sus4 | 11th (sus) |
| E♭ | E♭13 | 13th |
| G♭ | G♭7♯11 | ♯11 |
| B | B7♭9 | ♭9 |

Invalid example: C over Emaj7 (C is the ♭13 of E, an avoid note on a major 7th). The agent must reject it.

### Line cliché scale mapping

The line cliché changes one inner voice per step, so the scale for melodies and solos must change with it. In C minor:

| Step | Chord | Moving voice | Scale | Melody must avoid |
| --- | --- | --- | --- | --- |
| 1 | Cm | C | Aeolian (Dorian if the loop is Dorian) | — |
| 2 | Cm(maj7) | B | Harmonic minor (melodic minor if the line continues to i6) | B♭ |
| 3 | Cm7 | B♭ | Aeolian or Dorian | B natural |
| 4 | Cm6 | A | Dorian or melodic minor | A♭ |

Reference: "Michelle", The Beatles — the descending inner voice over a held minor chord; "My Funny Valentine" is the same device in a standard, and "Stairway to Heaven" in a guitar intro.

Rule: the scale on each step must contain the moving voice, and the melody never sustains the pitch a half-step from it. The ascending form (i6 → i7 → i(maj7) → i) uses the same mapping in reverse.

## 8. Genre idiom banks

These are the progressions the agent should reach for first; generic theory alone will not produce them. Gospel examples are in E♭ major; house examples in F minor / A♭ major; Afro-Latin in F.

### Gospel (E♭)

| Idiom | Roman numerals | Example | Notes |
| --- | --- | --- | --- |
| Shout vamp (1-4-5) | I – IV – I/5 – V7 | E♭ – A♭ – E♭/B♭ – B♭7 | Triads allowed; 2–4 chords per bar |
| Sus 2-5-1 | ii9 – V9sus4 – V7♭9 – Imaj9 | Fm9 – B♭9sus4 – B♭7♭9 – E♭maj9 | See §14 ex. 1 |
| Backcycle (3-6-2-5-1) | iii7 – VI7♭9 – ii9 – V13 – I6/9 | Gm7 – C7♭9 – Fm9 – B♭13 – E♭6/9 | Turnaround or ending |
| 7-3-6 | viiø7 – III7♭9 – vi9 | Dm7♭5 – G7♭9 – Cm9 | Lands on relative minor |
| "Holy" plagal | IVmaj7 – iv6 – I | A♭maj7 – A♭m6 – E♭ | The C → C♭ inner line is the hook |
| 4 over 5 | IV/V – I | A♭/B♭ – E♭ | Sus dominant without a 3rd |
| ♭VI over ♭VII | ♭VI/♭VII – I | C♭/D♭ – E♭ | Big lift into a final chorus |
| Half-step approach | ♯I / ♭II same quality – I | Emaj9 – E♭maj9 | Whole voicing slides down |
| Church turnaround | I – I7/3 – IV – iv6 – I/5 – V7 – I | E♭ – E♭7/G – A♭ – A♭m6 – E♭/B♭ – B♭7 – E♭ | Bass walks G – A♭ |
| Walk-up | I – I/3 – IV – ♯IV°7 – I/5 – V7sus4 – V7 – I | E♭ – E♭/G – A♭ – A°7 – E♭/B♭ – B♭7sus4 – B♭7 – E♭ | See §14 ex. 3 |
| Minor "Sunday" cadence | iiø7 – V7♭9 – i9 | Dm7♭5 – G7♭9 – Cm9 | Relative minor of E♭ |
| Shout lift | Vamp I – IV, then V7 of new key | … E♭ – A♭ – B7 → E – A | +1 semitone every 4 or 8 bars |

**Reference tracks**

- Shout vamp and walk-up — "Oh Happy Day", Edwin Hawkins Singers: the 1-4-5 vamp and the passing °7 climb.
- Sus 2-5-1 and "4 over 5" — "I Believe I Can Fly", R. Kelly: sus dominants that never show a 3rd.
- Backcycle and church turnaround — "Total Praise", Richard Smallwood: the chained secondary dominants into the final cadence.
- "Holy" plagal (IVmaj7 – iv6 – I) — "Creep", Radiohead, carries the same IV → iv inner line outside the church.
- Minor "Sunday" cadence — "Autumn Leaves": the iiø7 – V7♭9 – i that lands on the relative minor.
- Shout lift — "Love on Top", Beyoncé: the stacked semitone modulations at the end.
- Devotional ballad voicing — "Amazing Grace", Aretha Franklin: 12/8 feel, wide church voicings.

Gospel voicing colors: 6/9 on the tonic, maj9♯11 on IV, 7♯9 and 13♭9 on dominants, °7 used as a rootless V7♭9 (D°7 = B♭7♭9 without its root), clusters in the right hand above C4.

### Soulful and deep house (F minor / A♭ major)

| Idiom | Roman numerals | Example | Notes |
| --- | --- | --- | --- |
| Minor-9 pendulum | i9 – iv9 | Fm9 – B♭m9 | Aeolian; 1 chord per 1–2 bars |
| Dorian sway | i11 – IV13 | Fm11 – B♭13 | See §14 ex. 2 |
| Dorian ♭VII | i9 – ♭VIImaj9 | Fm9 – E♭maj9 | Floating, no dominant |
| Larry Heard move | i9 – ♭VImaj9 | Fm9 – D♭maj9 | Shared tones A♭, C, E♭ |
| Sus 2-5-1 | ii9 – V13sus4 – Imaj9 | B♭m9 – E♭13sus4 – A♭maj9 | House default resolution |
| 6-2-5-1 | vi9 – ii9 – V13sus4 – Imaj9 | Fm9 – B♭m9 – E♭13sus4 – A♭maj9 | 4- or 8-bar loop |
| 4-3-6 | IVmaj9 – iii7 – vi9 | D♭maj9 – Cm7 – Fm9 | Descending, melancholic |
| "Just the Two of Us" family | ♭VImaj7 – V7♯9 – i7 – (♭vii7 – ♭III7) | D♭maj7 – C7♯9 – Fm7 – E♭m7 – A♭7 | Last two chords are ii–V back to ♭VI |
| Major/minor pendulum | Imaj9 – iv9 | A♭maj9 – D♭m9 | Borrowed iv |
| Organ stab planing | One m7 or 7sus4 shape on every bass note | Fm7 shape on F – E♭ – D♭ – C | Planing mode, short stabs |

**Reference tracks**

- Minor-9 pendulum — "Mystery of Love", Mr. Fingers: one m9 shape rocking between two roots.
- Larry Heard move (i9 – ♭VImaj9) — "Can You Feel It", Mr. Fingers: the shared-tone lift that defines deep house.
- Dorian ♭VII — "Your Love", Frankie Knuckles: two chords, no dominant, endless float.
- Sus 2-5-1 and 6-2-5-1 — "Gypsy Woman (She's Homeless)", Crystal Waters: the house loop resolving through a sus dominant.
- Organ stab planing — "Show Me Love", Robin S: one shape moved onto every bass note.
- "Just the Two of Us" family — the original, Grover Washington Jr. with Bill Withers: ♭VImaj7 – V7♯9 – i7 with a ii–V back to ♭VI.

### Afro-Latin and bossa (F)

| Idiom | Roman numerals | Example | Notes |
| --- | --- | --- | --- |
| Montuno vamp | ii7 – V7 | Gm7 – C7 | 2-bar cycle aligned to clave |
| Salsa cycle | I – IV – V7 – IV | F – B♭ – C7 – B♭ | Triads acceptable in montuno |
| Bossa major | Imaj7 – II7♯11 – ii7 – ♭II7 – Imaj7 | Fmaj7 – G7♯11 – Gm7 – G♭7 – Fmaj7 | II7 is non-resolving (Lydian dominant) |
| Minor bossa | i6 – iiø7 – V7♭9 – i6 | Dm6 – Em7♭5 – A7♭9 – Dm6 | Relative minor of F |

**Reference tracks**

- Montuno vamp — "Oye Como Va", Tito Puente, in Santana's reading: a two-bar ii–V cycle locked to clave.
- Salsa cycle — "La Vida Es Un Carnaval", Celia Cruz: triadic montuno over a tumbao bass.
- Bossa major — "The Girl from Ipanema", Jobim: Imaj7, the non-resolving II7♯11, then the ♭II7 turn home.
- Minor bossa — "Manhã de Carnaval" (Black Orpheus), Luiz Bonfá: i6 – iiø7 – V7♭9 – i6.

### Neo-soul: "3 Doors Up" borrowing (C major)

While in a major key, borrow minor-9th (and maj9) chords from the major key 3 half-steps up. In C, that key is E♭ major, which shares its notes with C minor, so this is modal interchange from the parallel minor (§2) used as a fast lookup. The borrowed chords darken the atmosphere at once and create dramatic tension.

| Borrowed chord | Role in E♭ | Role in C | Typical move |
| --- | --- | --- | --- |
| Fm9 | ii9 | iv9 | Fmaj9 → Fm9 → Cmaj9 |
| Gm9 | iii9 | v9 | Gm9 → C9 → Fmaj9 (v as a soft ii of IV) |
| Cm9 | vi9 | i9 | Cmaj9 → Cm9 (shape switch, §7) |
| E♭maj9 | Imaj9 | ♭IIImaj9 | Cmaj9 → E♭maj9 lift |
| A♭maj9 | IVmaj9 | ♭VImaj9 | A♭maj9 → B♭9 → Cmaj9 (hero/backdoor) |
| B♭9 | V9 | ♭VII9 | Backdoor dominant |

Reference: "Brown Sugar", D'Angelo, and "On & On", Erykah Badu — major tonic centers coloured by borrowed minor-9 and ♭III/♭VI shapes rather than by functional dominants.

Rule: borrow for 1–2 bars, then return through a common tone or a backdoor resolution. While a borrowed chord sounds, the melody must not sustain a pitch a half-step from one of its chord tones (E over Cm9, A over Fm9, B over Gm9).

## 9. Harmonic rhythm and comping

Harmonic rhythm is how often the chord changes; comping rhythm is when and how long each chord sounds. Both are set per section and genre.

### Harmonic-rhythm defaults

| Context | Chords per bar | Loop length | Notes |
| --- | --- | --- | --- |
| Deep house groove | 1 per 2–4 bars | 2, 4 or 8 bars | Static or modal |
| Soulful house groove | 1 per 1–2 bars | 4 or 8 bars | Sus 2-5-1 loops |
| Gospel verse | 1–2 | 4 or 8 bars | Passing chords on beat 4 |
| Gospel shout | 2–4 | 1 or 2 bars | Lifts every 4 or 8 bars |
| Bossa / Afro-Latin | 1–2 | 2, 4 or 8 bars | Montuno vamps 2 bars |

### Timing rules

- **Anticipation.** In house and gospel, keys and pads change chord on the "and" of 4 (16th step 15) of the previous bar, or on its last 16th (step 16). The kick stays on beat 1.
- **Cadential acceleration.** The last bar of an 8- or 16-bar phrase may double the harmonic rhythm.
- **Turnaround.** The last 1–2 beats of a loop must hold a chord pointing back to bar 1: V7, ♭II7, ♭VII7, IV/V, or a half-step-above approach. Exception: a static modal vamp tagged as such.
- **Loop closure.** Bar 1 of every loop is the strongest arrival; avoid repeating the bar-1 chord in the final bar unless it is a one-chord vamp.

### Comping patterns

16th-note grid, steps 1–16 per bar (step 1 = beat 1, step 3 = 1&, step 5 = beat 2, step 15 = 4&).

| Pattern | Hits (steps) | Duration | Velocity | Genre |
| --- | --- | --- | --- | --- |
| Offbeat stab | 3, 7, 11, 15 | 30–50% of an 8th | 90–110 | Classic house |
| Dotted-8th organ (3-3-3-3-4) | 1, 4, 7, 10, 13 | Short, staccato | 85–105 | Organ house, garage |
| Anticipated pad | Starts on step 15 of the previous bar, holds | Legato 95–100% | 60–80 | Soulful and deep house |
| Rhodes breathing | 1, re-attack on 7 (2&) | Long, release before next | 55–80, re-attack softer | Soulful house, neo-soul |
| Gospel piano | LH octave on 1 and 9 with pickups on 8 and 16; RH voicing on 3, 7, 11, 15 | RH short, LH long | RH 70–95, LH 90–110 | Gospel uptempo |
| Gospel ballad | 12/8 feel: RH triplet 8ths, LH dotted quarters | Legato | 50–90 with swells | Gospel ballad |

**Reference tracks**

- Offbeat stab — "Show Me Love", Robin S: short organ hits on the 8th offbeats.
- Rhodes breathing — "Brown Sugar", D'Angelo: long chords re-attacked softly on the 2&.
- Gospel piano — "Oh Happy Day", Edwin Hawkins Singers: left-hand octaves with right-hand offbeat voicings.
- Gospel ballad — "Amazing Grace", Aretha Franklin: 12/8 triplets with swells.

## 10. Melody–harmony interaction

Every melody note on a strong beat, and every note of a quarter or longer, must be a chord tone or an available tension of the chord under it (§3).

### Rules

- Strong beats (1 and 3; every beat for 8th-note melodies): chord tone or available tension.
- Avoid notes only as passing or neighbor tones, on weak 8ths or 16ths, lasting ≤ 1/8 note.
- No minor 9th between the melody and any chord voice, except the ♭9 above the root of a dominant.
- The pad's top voice never doubles the melody in unison; an octave below is acceptable.
- The highest melody note of the song belongs in the chorus or drop. The chord under it is stable (I, IV, vi) or a deliberate tension chord resolved within one bar.

### Resolving conflicts

| What is fixed | Agent action |
| --- | --- |
| Melody (vocal hook, sample) | Reharmonize the chord: pick a bass that makes the note legal (top-down table, §7) |
| Harmony (loop already approved) | Move the melody note by step to the nearest chord tone or available tension |
| Neither | Prefer changing the chord; melodies are harder to replace |

### Vocal ranges

| Voice | Comfortable | Belt / peak |
| --- | --- | --- |
| Female lead (alto/mezzo) | A3–C5 | up to F5 |
| Female lead (soprano) | C4–E5 | up to A5 |
| Male lead (baritone) | A2–D4 | up to F4 |
| Male lead (tenor) | C3–G4 | up to B♭4–C5 |

After every modulation, recheck the melody's peak: each +1 semitone lift adds up. If the peak exceeds the belt range, start the song lower or reduce the number of lifts.

## 11. Macrostructure, tension, modulation and DJ keys

Harmony must follow the arrangement's energy: tension rises into the drop or chorus, then resets. Tracks are built in 16- or 32-bar blocks with DJ-friendly intro and outro.

### Section templates

| Section | Bars | Harmonic content | Harmonic rhythm | Target tension (0–5) |
| --- | --- | --- | --- | --- |
| Intro (DJ) | 16–32 | Drums and bass pedal, or one chord without its 3rd | None or very slow | 1 |
| Verse | 16 | Main loop, thin voicings (shells, 3–4 voices) | 1 per 1–2 bars | 2 |
| Pre-chorus / build | 8 | Rising bass, secondary dominants, sus chords, dominant pedal | Accelerating | 3–4 |
| Chorus / drop | 16–32 | Hook loop, full voicings, strongest resolution | As main loop | 4 |
| Breakdown | 16 | Main loop reharmonized, pads only, filter automation | Slower | 2, rising to 4 |
| Bridge / vamp (gospel) | 8–16 | Relative key or modal interchange; shout vamp with lifts | Fast | 5 |
| Outro (DJ) | 16–32 | Mirrors intro; unresolved loop | None or very slow | 1 |

Motif rule: a breakdown reharmonizes the same loop and keeps its top note (top-down reharm, §7), so the drop reads as a return rather than new material.

### Tension score per chord

- +2 dominant function (V, vii°, secondary dominant, tritone sub)
- +1 per altered tension (♭9, ♯9, ♯11, ♭13)
- +1 sus or unresolved chord
- +1 bass not on the root
- −1 tonic function in root position

Section tension = mean score of its chords. A build section must score above both of its neighbors.

When the key cannot change (house), raise energy with low-pass filter sweeps over a pedal, percussion density and voicing width instead.

### Modulation toolkit

| Technique | How | Example (from E♭) | Genre |
| --- | --- | --- | --- |
| Semitone lift | V7 of the new key on the last 1–2 beats | … B7 → E | Gospel, pop |
| Whole-step lift | ii–V of the new key, or V7sus4 of the new key | … Gm7 – C7 → F | Gospel |
| Chromatic climb | Repeat the vamp, lift +1 every 4 or 8 bars | E♭ → E → F → F♯ | Gospel shout |
| Pivot chord | A chord diatonic to both keys, reinterpreted | Cm7 (vi in E♭ = ii in B♭) → F7 → B♭ | All |
| Relative / parallel | Shift tonic between I and vi, or I and i | E♭ ↔ Cm; E♭ ↔ E♭m | House breakdowns |
| Chromatic mediant | New tonic a 3rd away, linked by a held common tone | E♭ → C♭ (hold E♭) | Neo-soul, cinematic |

**Reference tracks**

- Semitone lift — "Love on Top", Beyoncé: four consecutive half-step modulations in the outro.
- Whole-step lift — "Man in the Mirror", Michael Jackson: the final chorus lifted by a tone.
- Chromatic climb — gospel shout sections, where the same vamp rises every four or eight bars.
- Relative / parallel shift — "Creep", Radiohead: the tonic chord switching quality without changing root.

An unprepared lift (no pivot or dominant) is only allowed when tagged as an intentional "truck-driver" effect.

### DJ key compatibility (Camelot)

| Key | Camelot | Key | Camelot |
| --- | --- | --- | --- |
| E♭ major | 5B | E♭ minor | 2A |
| F major | 7B | F minor | 4A |
| G major | 9B | G minor | 6A |
| A♭ major | 4B | C minor | 5A |
| B♭ major | 6B | A minor | 8A |
| D♭ major | 3B | B♭ minor | 3A |

- Compatible mixes: same code; ±1 number with the same letter; same number with the other letter (relative key).
- A semitone lift moves +7 on the wheel (E♭ major 5B → E major 12B); a whole-step lift moves +2 (5B → F major 7B).
- Intro and outro must be in the track's home key. If the track ends after a lift, either return home in the outro or tag the outro key in metadata.

### Endings

- House, techno, funk: end on an unresolved loop (i9 vamp, IV/V, sus chord, ♭VII).
- Gospel ballad: plagal "amen" (IV – iv6 – I) or a held I6/9.
- Bossa: i6 or Imaj7(9).

## 12. Groove and rhythm patterns

All patterns use the 16th grid from §9 (steps 1–16 per 4/4 bar). Harmony changes must line up with these accents.

### Afro-Cuban

| Pattern | Bar 1 | Bar 2 | Rule |
| --- | --- | --- | --- |
| Son clave 3–2 | 1, 7, 13 | 5, 9 | 3-side: beat 1, 2&, beat 4. 2-side: beats 2 and 3 |
| Son clave 2–3 | 5, 9 | 1, 7, 13 | Same pattern, bars swapped |
| Rumba clave 3–2 | 1, 7, 15 | 5, 9 | Third stroke moves to 4& |
| Tumbao bass | 7, 13 | 7, 13 | 2& and beat 4; beat 4 anticipates the next chord's root and ties over the bar line, so beat 1 is silent |
| Piano montuno | 8th-note ostinato | — | Chord changes are anticipated on 4& (step 15) of the previous bar and follow the clave direction |

Reference: "Oye Como Va", Tito Puente / Santana — clave, tumbao and piano montuno in their plainest form; "Mambo No. 5", Pérez Prado, for the 2–3 side.

### House and techno

| Element | Steps | Rule |
| --- | --- | --- |
| Kick | 1, 5, 9, 13 | Four on the floor, always on grid |
| Clap / snare | 5, 13 | Beats 2 and 4 |
| Open hat | 3, 7, 11, 15 | Offbeat 8ths, on grid |
| Closed hat / shaker | All 16ths | Swing applies here |
| Swing | Even steps (2, 4, 6 … 16) | Delay by 54–62% (MPC-style); kick and offbeat hats stay on grid |

Reference: "I Feel Love", Donna Summer — four on the floor with offbeat 8ths; "Your Love", Frankie Knuckles, for the same grid under a house pad.

### Brazilian

| Pattern | Steps | Rule |
| --- | --- | --- |
| Samba surdo | Accent on beat 2 of each 2/4 bar (steps 5 and 13 in 4/4) | The open surdo answers on beat 2 |
| Samba syncopation (telecoteco / partido alto) | Phrases start on the 16th pickup before the downbeat | Chord stabs follow the same pickups |
| Bossa bass | 1, 7, 9, 15 | Root on 1, 5th anticipated on 2&; repeats on 3 and 4& |

Reference: "Mas Que Nada", Jorge Ben, for samba accents; "The Girl from Ipanema", João Gilberto, for the bossa bass and its anticipated 5th.

### Gospel

- Ballads: 12/8 or heavy triplet swing; chord changes on dotted-quarter beats.
- Uptempo and praise break: straight or lightly swung 16ths, chords stabbed on offbeats, fast 2–4 chords per bar.

## 13. Agent infrastructure

The agent stores progressions as Roman numerals, renders them to a key, resolves rule conflicts by a fixed priority, and validates before output.

### Notation standard

- Chord symbol grammar: root + accidental + quality + highest natural extension + alterations in ascending order + optional /bass. Qualities: maj7, m7, 7, m7b5, dim7, m(maj7), 6, m6, sus2, sus4, 7sus4. Examples: Fm9, Bb13sus4, C7b9#11, Ab/Bb, F#dim7.
- ASCII in data (b and #); Unicode (♭ ♯) only in display text.
- Storage: Roman numerals relative to key and mode with explicit quality (`ii9 V9sus4 V7b9 Imaj9`). Transpose at render time.
- Spelling: name chord tones by interval from the root (the ♭9 of C is D♭, never C♯). Flat keys use flats; sharp keys use sharps. An enharmonic respelling (F♭7 shown as E7) is allowed in display text only.

### Rule priority (highest wins)

1. Physical and mix limits: low-interval limits, register ranges, monophonic bass (§1, §6).
2. Melody legality: fixed melody notes must be chord tones or available tensions (§10).
3. Chord-scale legality: no sustained avoid notes (§3).
4. Genre profile: idioms of the selected genre override general voice-leading preferences (planing in house, triads in a gospel shout).
5. Voice-leading smoothness and tendency-tone resolution (§5).
6. Color preferences: extensions over triads, preferred voicing types (§4).

### Genre profiles

| Parameter | Gospel | Soulful house | Deep / Detroit | Afro-Latin / bossa |
| --- | --- | --- | --- | --- |
| Voice-leading mode | Contrapuntal (planing in shout stabs) | Contrapuntal pads, planing stabs | Planing | Contrapuntal |
| Harmonic rhythm | 1–2 per bar; 2–4 in shout | 1 per 1–2 bars | 1 per 2–4 bars | 1–2 per bar |
| Dominant use | High, altered | Medium, sus preferred | Low, modal | High |
| Triads in pad | Yes over moving bass and in shout | Only as upper structures or slash chords | No | Montuno only |
| Modulation | Frequent lifts | Rare, breakdown only | None | Occasional |
| Ending | Plagal or I6/9, or vamp | Unresolved loop | Unresolved loop | i6 or Imaj7 |

### Validation checklist

The agent runs every check after generating; any failure is fixed and the check rerun.

- [ ] Every chord symbol parses under the grammar.
- [ ] No interval below its low-interval limit; no voice outside its register.
- [ ] Pad top voice stays ≥ 3 semitones below the melody; no unison doubling.
- [ ] No avoid note sustained ≥ 1/8 on a strong beat.
- [ ] No illegal minor 9ths or mixed natural/altered tensions.
- [ ] Movement budget respected; smoothness score reported per change.
- [ ] Tendency tones resolve (contrapuntal mode).
- [ ] No doubled leading tone, 7th or altered tension.
- [ ] Every melody note on a strong beat is legal against its chord.
- [ ] Every loop ends with a turnaround or is tagged as a modal vamp.
- [ ] Build sections score higher in tension than their neighbors.
- [ ] Intro and outro sit in the home key; Camelot code recorded.
- [ ] Vocal peak within range after all lifts.

### Output schema

```json
{
  "key": "Eb",
  "mode": "ionian",
  "camelot": "5B",
  "genre_profile": "gospel",
  "sections": [
    {
      "name": "chorus",
      "bars": 16,
      "target_tension": 4,
      "loop": [
        {
          "bar": 1, "beat": 1.0, "duration_beats": 2,
          "roman": "ii9", "symbol": "Fm9", "function": "PD",
          "scale": "dorian",
          "bass_midi": 29,
          "voicing_midi": [56, 60, 63, 67],
          "tension_score": 0,
          "smoothness_from_prev": null
        }
      ]
    }
  ],
  "validation": { "passed": true, "failures": [] }
}
```

## 14. Worked examples (exact MIDI)

Each example passes the §13 checklist. Smoothness = total semitone movement of the upper voices from the previous chord. Use these as few-shot references for the agent.

### Ex. 1: Gospel sus 2-5-1 in E♭

| Chord | Bass | Voicing | MIDI | Smoothness |
| --- | --- | --- | --- | --- |
| Fm9 | F1 (29) | A♭3 C4 E♭4 G4 | 56 60 63 67 | — |
| B♭9sus4 | B♭1 (34) | A♭3 C4 E♭4 F4 | 56 60 63 65 | 2 |
| B♭7♭9 | B♭1 (34) | A♭3 C♭4 D4 F4 | 56 59 62 65 | 2 |
| E♭maj9 | E♭1 (27) | G3 B♭3 D4 F4 | 55 58 62 65 | 2 |

Tendency tones: A♭ (♭7) falls to G; C♭ (♭9) falls to B♭ (the target's 5th); D is held as the major 7th.

### Ex. 2: Dorian sway in F minor (deep house)

| Chord | Bass | Voicing | MIDI | Smoothness |
| --- | --- | --- | --- | --- |
| Fm11 | F1 (29) | A♭3 C4 E♭4 G4 B♭4 | 56 60 63 67 70 | — |
| B♭13 | B♭1 (34) | A♭3 C4 D4 G4 B♭4 | 56 60 62 67 70 | 1 |

Only E♭ (♭7 of Fm) moves, falling to D (3rd of B♭13). Loop it for 2 or 4 bars per chord with the anticipated-pad pattern (§9).

### Ex. 3: Gospel walk-up in E♭

| Chord | Bass | Voicing | MIDI | Smoothness |
| --- | --- | --- | --- | --- |
| E♭ | E♭2 (39) | B♭3 E♭4 G4 | 58 63 67 | — |
| E♭/G | G2 (43) | B♭3 E♭4 G4 | 58 63 67 | 0 |
| A♭ | A♭2 (44) | C4 E♭4 A♭4 | 60 63 68 | 3 |
| A°7 | A2 (45) | C4 E♭4 G♭4 | 60 63 66 | 2 |
| E♭/B♭ | B♭2 (46) | B♭3 E♭4 G4 | 58 63 67 | 3 |
| B♭7sus4 | B♭1 (34) | A♭3 E♭4 F4 | 56 63 65 | 4 |
| B♭7 | B♭1 (34) | A♭3 D4 F4 | 56 62 65 | 1 |
| E♭ | E♭2 (39) | G3 E♭4 G4 | 55 63 67 | 4 |

Triads are legal here because the bass is moving (§4, gospel profile). Harmonic rhythm: 2 chords per bar.

### Ex. 4: Passing diminished in E♭

| Chord | Bass | Voicing | MIDI | Smoothness |
| --- | --- | --- | --- | --- |
| E♭maj9 | E♭2 (39) | G3 B♭3 D4 F4 | 55 58 62 65 | — |
| E°7 | E2 (40) | G3 B♭3 D♭4 E4 | 55 58 61 64 | 2 |
| Fm9 | F2 (41) | G3 A♭3 C4 E♭4 | 55 56 60 63 | 4 |

E°7 works as a rootless C7♭9 (V7/ii), so it resolves up a half-step to Fm9. The G3–A♭3 minor 2nd sits above the E3 limit.

### Ex. 5: Tritone step-down into E♭

| Chord | Bass | Voicing | MIDI | Smoothness |
| --- | --- | --- | --- | --- |
| Fm9 | F1 (29) | A♭3 C4 E♭4 G4 | 56 60 63 67 | — |
| E9 (tritone sub of B♭7) | E1 (28) | G♯3 B3 D4 F♯4 | 56 59 62 66 | 3 |
| E♭maj9 | E♭1 (27) | G3 B♭3 D4 F4 | 55 58 62 65 | 3 |

The bass descends F – E – E♭ chromatically; G♯/A♭ and D carry the shared guide tones. E9 is spelled F♭9 in strict theory; the sharp spelling is used for readability.

## 15. Cinematic and film-scoring frameworks

Film harmony often moves between triads by voice leading, with no home key. The cinematic profile switches off the functional rules (T → PD → D, §2) and the triad restriction (§4), but keeps spacing, low-interval and voice-leading rules (§1, §5).

| Profile parameter | Cinematic |
| --- | --- |
| Voice-leading mode | Contrapuntal |
| Harmonic rhythm | 1 chord per 1–4 bars |
| Triads | Allowed and preferred (open, doubled root and 5th) |
| Functional rules | Off; motion judged by common tones |
| Avoid-note check | On, except between polytonal layers |

### Neo-Riemannian transformations

Each operation keeps two common tones (or one, for compounds) and moves the rest by step.

| Op | Definition | Example | Voice movement |
| --- | --- | --- | --- |
| P (Parallel) | Major ↔ minor on the same root | C ↔ Cm | 3rd moves a semitone (E ↔ E♭) |
| R (Relative) | Major ↔ its relative minor | C ↔ Am | 5th up a whole step (G → A) |
| L (Leittonwechsel, leading-tone) | Major ↔ minor a major 3rd up | C ↔ Em | Root down a semitone (C → B) |
| N (Nebenverwandt = R, L, P) | Major ↔ minor iv | C ↔ Fm | E → F, G → A♭; C held |
| S (Slide = L, P, R) | Major ↔ minor a semitone up | C ↔ C♯m | Root and 5th up a semitone; 3rd held |
| H (Hexatonic pole = L, P, L) | Major ↔ minor a major 3rd down | C ↔ A♭m | All three voices move a semitone |

**Reference tracks**

- P (major ↔ minor on one root) — "Creep", Radiohead: the 3rd moves a semitone, everything else holds.
- L and major-3rd relations — "Star Wars" main title, John Williams: triads a third apart linked by a common tone.
- H (hexatonic pole) — "Neptune" from The Planets, Holst, already cited below.
- R (relative) — "Losing My Religion", R.E.M.: the pivot between a major chord and its relative minor.

"F" is not a standard Neo-Riemannian label. If the source library defines it, the agent maps it to its compound of P, L and R before use.

Cycles to use as ready-made sequences:

- PL (hexatonic) cycle: C – Cm – A♭ – A♭m – E – Em – C.
- PR (octatonic) cycle: C – Cm – E♭ – E♭m – G♭ – F♯m – A – Am – C.

Tonnetz rule: on the Tonnetz grid (5ths on one axis, major and minor 3rds on the diagonals), each triad is a triangle and P, L, R flip it across a shared edge. Harmonic distance = number of P/L/R steps; the agent prefers paths of 1–2 steps between consecutive chords and holds every common tone in the same voice.

### Hexatonic (augmented) scale

The scale alternates minor 3rds and semitones (C E♭ E G A♭ B). Each collection holds three major and three minor triads whose roots lie a major 3rd apart, which gives a mystical, supernatural color.

| Collection | Major triads | Minor triads |
| --- | --- | --- |
| C E♭ E G A♭ B | C, E, A♭ | Cm, Em, G♯m |
| C♯ E F G♯ A C | C♯, F, A | C♯m, Fm, Am |
| D F F♯ A B♭ C♯ | D, F♯, B♭ | Dm, F♯m, B♭m |
| E♭ F♯ G B♭ B D | E♭, G, B | E♭m, Gm, Bm |

- Minor triads a major 3rd apart (Gm – E♭m – Bm) stay inside one collection.
- Hexatonic pole pairs (C ↔ G♯m, E ↔ Cm) are the most uncanny move; Holst's "Neptune" alternates Em and G♯m.
- The melody draws only on the same collection while the cue lasts.

### Hero cadence and third relations

Epic releases come from ♭VI and ♭VII or root motion by major 3rds, not from V → I.

| Move | Example | Use |
| --- | --- | --- |
| ♭VI – ♭VII – I | A♭ – B♭ – C | Classic hero release |
| i – ♭VI – ♭VII – I | Cm – A♭ – B♭ – C | Minor-to-major triumph |
| Major-3rd step-down | C → A♭ (→ E → C) | Expanding, majestic |
| ♭VII – I or IV – I | B♭ – C; F – C | Plagal grandeur |

**Reference tracks**

- ♭VI – ♭VII – I — "Star Wars" throne-room cadence, John Williams: the classic hero release.
- i – ♭VI – ♭VII – I — the minor-to-major turn heard across game victory fanfares.
- Major-3rd step-down — "Superman" march, John Williams: expanding third relations under a held line.
- Plagal grandeur (♭VII – I, IV – I) — "Hey Jude" coda, The Beatles: the ♭VII that falls home without a dominant.

Voice the arrival as an open root-position triad with doubled root, octave bass, and a top voice rising by step into the tonic's root or 3rd.

### Polytonality and bitonality

Two triads from different keys sound at once, each internally consonant, so the ear hears two key centers rather than noise.

- Separate the layers by register (lower triad C3–C4, upper triad from C5) or by clearly different timbres.
- Pairs ranked mild to harsh: minor + major a whole step up (Em under F♯); major + major a tritone apart (C + F♯, the "Petrushka" chord); major + major a semitone apart.
- Resolve by collapsing one layer into the other's key, or by fading one layer out.
- The avoid-note check (§3) is skipped between layers; low-interval limits still apply.

### Chromatic looping (fixed melody)

Hold one melody note or short motif and cycle a non-functional chromatic loop under it. Every chord must keep the held note legal (top-down table, §7).

Example under a held G: E♭maj7 (G = 3rd) – D7sus4 (G = 4th) – D♭maj7♯11 (G = ♯11) – Cm9 (G = 5th). The bass descends E♭ – D – D♭ – C.

Loop rules: 2–4 chords, 1–2 bars each, bass moving by semitone or whole tone; chord qualities may change freely.

## 16. Techno: atonal ostinato and timbral harmony

In techno the kick, rumble and hats are largely atonal, and relentless repetition makes even dissonant synth intervals sound intentional. The techno profile therefore judges ostinato layers by consistency and timbre, not by chord-scale legality.

| Profile parameter | Techno |
| --- | --- |
| Voice-leading mode | Planing |
| Harmonic rhythm | One pitch set per 16–32 bars |
| Avoid-note and melody checks | Off for layers tagged ostinato |
| Modulation | None |
| Ending | Unresolved loop |

### Atonal ostinato rules

- A layer is tagged ostinato when one riff repeats unchanged for at least 8 bars. It is exempt from the avoid-note and minor-9th checks (§3) and the melody-legality check (§10).
- Still enforced: low-interval limits and the mono sub rule (below).
- Establish the dissonance early, within the layer's first 4–8 bars, so repetition can normalize it. Keep the pitch set fixed for the layer's duration.
- Vary the ostinato through filter, envelope, accent, note length and rhythm, not pitch. Change the pitch set only at 16- or 32-bar boundaries.
- Tune the kick and rumble to the track's root or 5th, or leave them clearly atonal. The riff's lowest note must not sit a semitone from the kick's fundamental.
- Typical dissonant ostinato material: minor 2nds, tritones, stacked minor 9ths, Phrygian ♭2 riffs.

Reference: "The Bells", Jeff Mills — one riff held unchanged while filter and accent carry the arrangement; "Spastik", Plastikman, for rhythm-only variation, and "Da Funk", Daft Punk, for a dissonant riff normalised by repetition.

### Timbre as harmony

Oscillator detune, oscillator intervals and pitch modulation are harmonic choices and are stored in the output schema (fields `detune_cents`, `osc_intervals`, `lfo_pitch_cents`, `lfo_rate_hz`).

| Parameter | Range | Harmonic effect | Agent rule |
| --- | --- | --- | --- |
| Unison detune | 3–15 cents | Thickening; heard as one pitch with beating | Default for pads and leads |
| Wide detune | 15–30 cents | Sour, unstable | Tension sections only |
| Quarter-tone detune | about 50 cents | Heard as a microtonal interval | Treat as a dissonant interval |
| Oscillator intervals | +3, +5, +7, +12 semitones | Every note becomes a parallel chord | Planing mode; check low-interval limits for the stacked interval |
| LFO vibrato | 5–30 cents at 4–7 Hz | Expressive only | Ignore in harmony checks |
| Wide LFO pitch mod | 100 cents or more | A moving interval between pitch classes | Run legality checks on both extremes, unless ostinato-exempt |
| Pitch envelope | ±12–24 semitones, fast decay | Percussive zap | Atonal; exempt |

- Beating rate equals the frequency difference: 10 cents of detune at A4 (440 Hz) beats at about 2.5 Hz.
- Below about 120 Hz (roughly B2), oscillators stay mono and undetuned, or detune cancels the sub's phase.
