# Song description — three lines from you, the rest from the agent

You only have to write the **three mandatory fields** below.  Everything else
can be left as `<<…>>`.  The agent asks you about whatever it can't work out,
then fills in the rest of the file.

1. **Compose:** fill in the mandatory fields, then ask `/conga-composer` to
   **"fill songs/<folder>/song.md"**.  The agent follows the *Agent intake
   protocol* below, then runs its seven steps (mood seed → genre / key / mode
   → section arc → progressions → bass, voicing, rhythm → modulation and
   ending → validation) and writes every section of this file.
2. **Generate:** ask `/subseq-dev` to **"generate songs/<folder> from
   song.md"**.  It rewrites the `<<GENERATE …>>` blocks in `live_init.py` and
   `live_patterns.py` to match this file.  If you edit this file later and ask
   again, those blocks are **regenerated**, so put musical decisions here
   rather than in the code.

---

### Mandatory: you write these

* **Description:** <<at least 2 sentences: what the track is, how it feels and how it travels from start to end. Genre, mood words, instruments and reference tracks are welcome here and are used as seeds>>
* **BPM:** <<e.g. 122>>
* **Duration:** <<e.g. 6:00 (mm:ss)>>

### Optional seeds: fill only what you care about

Anything you write here is a **constraint**: the agent keeps it and builds
around it.  Anything you leave as `<<…>>`, the agent either works out from the
description or proposes itself.  You can also seed any field further down
(a section's chords, a part, a reference).

* **Title:** <<…>>
* **Mood / feel:** <<any language: "uplifting but sad, builds to euphoric">>
* **Genre / references:** <<e.g. soulful house; Mr. Fingers – Can You Feel It>>
* **Home key / mode:** <<e.g. F Dorian>>
* **Time signature:** <<4/4>>
* **Parts / instruments:** <<e.g. drums, bass, Rhodes pad, lead synth, vocal>>
* **Vocal / lead range:** <<e.g. alto F3–D5, or "instrumental">>
* **Output:** <<MIDI device name pattern, or "default">>
* **Generative vs fixed:** <<"evolving" or "fixed take">>

---

### Agent intake protocol (for `/conga-composer`)

1. **Check the mandatory fields.**  If the description is missing or shorter
   than 2 sentences, or the BPM or duration is missing, ask for those and stop.
   Don't compose anything until all three are there.
2. **Collect the minimum data.**  The agent needs these six items before it
   can write the file:

   | Item | Why it's needed | Where the agent looks, in order |
   | :--- | :--- | :--- |
   | Mood / feel (≥1 KB seed) | Every later choice comes from it (`01` M.3) | Seed → mood words in the description → ask |
   | Genre profile | Sets voice-leading, harmonic rhythm, dominant use and ending (`06` §13) | Seed → genre or reference in the description → ask |
   | Mood arc direction | How the sections travel | Seed → "into / builds to / vira / até" in the description → genre default arc (A/B/C) |
   | Home key / mode | Register limits, Camelot | Seed → derived from mood valence and genre key defaults → *propose* |
   | Parts | Which patterns get generated | Seed → instruments in the description → genre default line-up → *propose* |
   | Vocal or instrumental | Lift and range checks (`05` §10) | Seed → description → ask |

   Only the items marked *ask* can produce a question, and only when neither
   a seed nor the description answers them.  The agent asks them all at once,
   in one round (one question per item, at most 4).  Each question offers
   the agent's own proposal as the first option, so a quick "yes" or
   "you choose" accepts it.
3. **Keep the seeds.**  The agent never overwrites a seeded value.  If a seed
   breaks a KB rule (rule priority, `06` §13), the agent keeps the seed and
   adds a one-line note on the trade-off under *Validation*.
4. **Propose everything else.**  The agent fills every remaining `<<…>>`
   from the KB.  Each value it writes in the song card gets one of three
   origin tags: `(seed)`, `(from description)` or `(proposed)`.  BPM and
   duration are always `(seed)`.
5. **Work out the bar count.**  Total bars = duration in seconds × BPM ÷ 60
   ÷ beats per bar.  For house and techno, round to 16-bar blocks and record
   the new duration (e.g. *6:00 @ 122 = 183 bars → 192 bars = 6:18*).
   Section bars must add up to that total.
6. **Record the seed input.**  The agent leaves the *Mandatory* and
   *Optional seeds* blocks exactly as you wrote them.  It copies them,
   unchanged, into *Seed input* below, together with any seeds written
   further down in the file and every intake question with your answer.  On
   a rerun it replaces that block with the current input, so the block always
   shows the input behind the song card under it.
7. **Recap.**  After writing the file, the agent sums up in a few lines what
   it proposed, so you can change any of it and ask again.

---

### Seed input (agent-copied, verbatim — do not edit; edit the blocks above)

*Generated <<YYYY-MM-DD>> by `/conga-composer`.*

```text
<<Description, BPM and Duration exactly as written above>>
<<every filled Optional seed, exactly as written, one per line ("Field: value"); unfilled seeds are left out>>
<<seeds written further down the file, as "Section › field: value">>
```

**Intake questions and answers**

| Question | Agent's proposal | Your answer |
| :--- | :--- | :--- |
| <<question, or "none — all minimum data came from seeds and description">> | <<…>> | <<verbatim>> |

---

### **<<Title>>**  ·  song card (agent-filled)

**Step 1: Mood seed** (`01-mood` M.3, M.6)
* **Mood text:** <<the mood words from the seed or description>>
* **Seeds + weights:** <<e.g. Uplifting 0.6 + Melancholic 0.4 — one of the 16 KB seeds, ≤2 per section>>
* **Compound strategy:** <<dimension split / layer split / time split / ambivalent chords / none>> — <<who carries what: "melancholic → valence (mode, chord quality); uplifting → energy (bass, top line, groove)">>
* **Color tag:** <<none / mystical / nostalgic / sensual / spiritual / cinematic / mechanical>>
* **Targets:** V <<−3…+3>> · E <<0…4>> · T <<0…5>>
* **Arc:** <<template A soulful house / B gospel / C deep-techno / custom — one line; tag "journey" if the end need not return home>>

**Step 2: Genre, key, tempo** (`06` §13 profiles, `02` §1, `05` Camelot)
* **Genre profile:** <<gospel / soulful house / deep-Detroit / Afro-Latin-bossa / cinematic / techno>>
* **Genre / references:** <<e.g. techy microhouse, deep house>>
* **Home key / mode:** <<e.g. F Dorian — dance default Eb, F, G; gospel also Ab, Db, Bb>>
* **Camelot:** <<e.g. 4A>>
* **BPM:** <<from the mandatory field>> (seed)
* **Time signature:** <<4/4, or 12/8 for a gospel ballad>>
* **Length:** <<duration → N bars (rounded to 16-bar blocks for dance) = actual mm:ss>>
* **Vocal / lead range:** <<e.g. alto F3–D5, or "instrumental">>
* **Output:** <<MIDI device name pattern, or "default">>
* **Generative vs fixed:** <<"evolving" (default, no seed) or "fixed take">>

---

### Step 3 — Mood arc

One row per section.  Bars must add up to the length (house: 16- or 32-bar
blocks, DJ-friendly intro and outro).  V/E/T are the KB targets; **Energy**
is the 0.0–1.0 value Subsequence uses for arrangement density (default E ÷ 4).
**Sub mood** is the Subsequence mood the section runs with — it sets the
harmony style, and the scale when Key / Mode gives only a key (see the
mapping below).

| # | Section | Bars | KB mood (≤2 + color) | V / E / T | Energy | Sub mood | Key / Mode | Main move |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **<<Intro>>** | **<<1–32>>** | <<Introspective>> | <<−1 / 1 / 1>> | <<0.25>> | <<introspective>> | **<<F Dorian>>** | <<tonic pedal, m9 only>> |
| 2 | **<<Section 2>>** | **<<…>>** | <<…>> | <<…>> | <<…>> | <<…>> | **<<…>>** | <<…>> |
| 3 | **<<Section 3>>** | **<<…>>** | <<…>> | <<…>> | <<…>> | <<…>> | **<<…>>** | <<…>> |
| 4 | **<<Outro>>** | **<<…>>** | <<…>> | <<…>> | <<…>> | <<…>> | **<<…>>** | <<mirrors the intro>> |

Arc rules (`01` M.5): the 4–8 bars before a release carry more tension than
the peak; a build scores above both neighbours; the last section returns to
the opening mood family unless tagged "journey"; a recurring loop keeps its
top note when its mood changes; at most one valence jump >2 per 32 bars, and
any jump >2 names its transition technique in *Main move*.

**KB seed → Subsequence mood.**  The Sub mood is the KB seed id (lower
case); any KB synonym is accepted too.  Each sets the scale (the seed's first
KB mode) and a harmony style.  Where the section's mode differs from that
scale (e.g. Uplifting in Mixolydian, Dark in Aeolian), write the mode in
*Key / Mode* explicitly — an explicit scale wins over the mood's.

| Sub mood | Scale · harmony style | Sub mood | Scale · harmony style |
| :--- | :--- | :--- | :--- |
| uplifting | ionian · functional_major | introspective | dorian · dorian_minor |
| joyful | ionian · functional_major | melancholic | aeolian · aeolian_minor |
| hopeful | ionian · functional_major | dark | phrygian · phrygian_minor |
| nostalgic | ionian · functional_major | tense | harmonic_minor · diminished |
| sensual | dorian · dorian_minor | aggressive | phrygian · phrygian_minor |
| cool | dorian · dorian_minor | mysterious | lydian · chromatic_mediant |
| bittersweet | melodic_minor · aeolian_minor | dreamy | lydian · lydian_major |
| spiritual | ionian · functional_major | triumphant | ionian · chromatic_mediant |

---

### Step 4 — Harmonic blueprint

One row per section.  Store Roman numerals with explicit quality and render
them in the section's key; each chord carries its duration in bars, function
(T / PD / D / color) and tension score (`05` §11: +2 dominant, +1 per altered
tension, +1 sus/unresolved, +1 bass not on root, −1 root-position tonic).
Every loop ends in a turnaround or is tagged *modal vamp*.

| Section | Roman (bars) | Chords (bars) | Function | Tension → mean | Turnaround / vamp | Loop | Idiom source |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **<<Intro>>** | <<`i9` (4)>> | <<**Fm9** (4)>> | <<T>> | <<0 → 0.0>> | <<modal vamp>> | <<8x 4-bar loop>> | <<`04` §8 deep house>> |
| **<<Section 2>>** | <<`i9` (2) → `IV13` (2)>> | <<**Fm9** (2) → **Bb13** (2)>> | <<T, color>> | <<…>> | <<…>> | <<…>> | <<`04` §7 Dorian sway>> |
| **<<…>>** | <<…>> | <<…>> | <<…>> | <<…>> | <<…>> | <<…>> | <<…>> |

Custom chords the parser may not spell (altered dominants, `7sus4b9`…) are
registered by the generator.

---

### Step 5 — Bass, voicing, rhythm per section

| Section | Harmonic rhythm | Bass (archetype, root register) | Voicing (family, mode, top-note contour) | Comping + groove | Mood levers used |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **<<Intro>>** | <<1 chord / 4 bars>> | <<pedal, F1 (MIDI 29) — never below Eb1 / 27>> | <<m9 rootless A, planing, top note C5 held>> | <<pad swells, house grid, anticipate on step 15>> | <<register low, density thin>> |
| **<<…>>** | <<…>> | <<…>> | <<…>> | <<…>> | <<max 2 per 4 bars; 4 at a "contrast" boundary>> |

---

### Step 6 — Modulations and ending

* **Lifts:** <<none / bar N: semitone via V7 of new key (Camelot +7) / whole step via ii–V (Camelot +2) / "truck-driver">> — <<vocal peak after lift>>
* **Ending:** <<unresolved loop (house/techno) / plagal "amen" or I6/9 (gospel) / i6 or Imaj7(9) (bossa)>>

---

### Step 7 — Validation (`06` §13 checklist)

Pass, fail (and the fix), or *not evaluated at outline level*.

| Check | Result |
| :--- | :--- |
| Every chord symbol parses | <<…>> |
| Low-interval limits, registers, bass ≥ Eb1 | <<…>> |
| No sustained avoid notes; no illegal minor 9ths | <<…>> |
| Loops end in a turnaround or are tagged modal vamp | <<…>> |
| Builds score above their neighbours in tension | <<…>> |
| Intro and outro in the home key; Camelot recorded | <<…>> |
| Vocal / lead peak in range after all lifts | <<…>> |
| Measured valence (0.5 × mode + 0.5 × mean chord) vs target, per section | <<e.g. Drop: −0.3 vs 0 ✓>> |
| Compound mood not averaged (strategy visible) | <<…>> |

---

### Parts

One row per instrument.  Delete rows you don't want; add rows for more parts.
Registers follow Step 5.  **Mood** pins a part's pitches to a mood's scale
(`@composition.pattern(mood=…)`), e.g. a Lydian pad over a Dorian song —
leave empty to follow the section.

| Part | MIDI ch | Register | Enters at energy ≥ | Mood (optional) | Character / generative idea |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Drums** | <<10>> | — | <<0.0>> | — | <<e.g. four-on-the-floor, ghost hats rising with energy, swing 57>> |
| **Bass** | <<2>> | <<F1–F3>> | <<0.0>> | <<…>> | <<e.g. house bass on the root, octave pops, mono>> |
| **Pad / Chords** | <<3>> | <<F3–F5>> | <<0.0>> | <<…>> | <<e.g. voice-led m9 pads, top note held across sections>> |
| **Lead** | <<4>> | <<F4–F5>> | <<0.4>> | <<…>> | <<e.g. MelodicState melody on chord tones, rising contour into drops>> |

---

### Song references (optional)

Tracks to learn from.  One row per musical aspect you want to borrow — the
same track can appear on several rows.  Aspects: groove, drums, bassline,
harmony, melody, arrangement, energy curve, tempo, sound / texture.  The
composer may add KB anchor tracks here ("sounds like X") to explain a choice.

| Reference (artist – title) | Musical aspect | What to take | Comments / things to consider |
| :--- | :--- | :--- | :--- |
| <<Artist – Title>> | <<groove>> | <<e.g. swung 16th hats, off-beat open hat>> | <<e.g. keep the kick dry; swing lighter than the reference>> |
| <<Artist – Title>> | <<harmony>> | <<e.g. minor 9 vamp with bII colour>> | <<e.g. only in the intro; drops go major>> |
| <<…>> | <<…>> | <<…>> | <<…>> |

---

### Notes for the generator (optional)

* <<anything else: transitions, fills, risers, CC automation, tempo ramps, hotkeys…>>
* <<machine-readable: ask the composer to append the `06` §13 JSON schema below if you want exact per-chord data (bass_midi, voicing_midi, smoothness)>>
