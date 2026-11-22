# My Emotions

## Request
> A song in F minor, 118 BPM, deep house, 6 minutes long, called "my emotions".

## Decisions (defaults taken, not asked — change any of them)
- **Instrumental**, entry variant **Groove / Riff first** (deep house is groove-led); title is the concept.
- **Concept:** a slow, warm club track that holds a feeling it can't name: one chord loop that keeps turning over, with a flat-six sigh on top.
- **Profile:** Evaluation slightly negative (bittersweet), Potency gentle, Activity steady and moderate-low → minor aeolian, soft velocities (peak energy 0.8), 56% swing.
- **Key / tempo / metre:** F aeolian, 118 BPM, 4/4. 176 bars = 5:58 (rendered 358 s).
- **Tonal strategy C:** one static 4-chord loop, contrast through register, density and the breakdown turn.
- **Delivery:** `.mid` render plus live play. Seed 1. GM drum map. Channels: bass 2, pad 3, stabs 4, melody 5, drums 10.

| Section | Bars | Energy | Chords (1 per bar) | Close |
|---|---|---|---|---|
| intro | 16 | 0.15 → 0.4 | Fm9 Dbmaj9 Abmaj9 Eb7 | loop |
| groove | 32 | 0.5 → 0.65 | same; melody enters bar 17 | loop |
| breakdown | 16 | 0.3 → 0.2 | Fm9 Bbm9 Dbmaj9 C7; no kick until the last 4 bars | V |
| build | 8 | 0.45 → 0.85 | Bbm9 Dbmaj9 Bbm9 C7 (hangs on V) | V |
| main | 32 | 0.8 | main loop, melody + stabs | loop |
| breakdown | 16 | as above | | V |
| build | 8 | as above | | V |
| main | 32 | 0.8 | | loop |
| outro | 16 | 0.5 → 0.05 | Fm9 Dbmaj9 Bbm9 Fm9 | closes on i |

## Parts
- **Drums:** four-on-the-floor kick, side-stick on 2 and 4, off-beat open hat, ghost closed hats and shaker scaled by energy, snare roll into each main.
- **Bass:** root in F2–F3, off-beat octave bounce, ghost sixteenths with energy; held notes in breakdowns and the first 8 bars.
- **Pad:** 4-note voice-led chords, filter sweep (CC 74) in builds.
- **Stabs:** voice-led chord hits on the "and" of 2 and 4, gated by `min_energy=0.45`.
- **Melody:** 8-bar a-b-a-c line from a 2-bar sparse euclidean idea, opening on a ♭6→5 / 4→3 / 2→1 sigh (`fit=0`); arch in main, ascending in builds, valley in breakdowns, descending in the outro.

| Subsequence feature | Used? | Role |
|---|---|---|
| `section_chords` + `progression` | yes | all chords, the loop repeated to each section length |
| `harmony` (aeolian_minor) | yes | engine required by the piece; sections override it |
| `Motif.euclidean/generate`, `Phrase.develop`, `p.phrase` | yes | melody |
| `Form`, `energy`, `transition`, `min_energy` | yes | form, energy ramps, snare fill, stab gate |
| `swing`, `cc_ramp`, `ghost_fill`, `bresenham_poly` | yes | feel and percussion |
| `section_cadence`, `freeze` | no | chords are bound, so closes are written |

## Gaps & how they were handled
- A bound progression only covers its own bars, so the loop is repeated with a plain list multiply (glue, not a new engine).
- Unlike `new-hope`, no private attributes are touched on reload.

## Run
`python songs/my-emotions/live_init.py --render [--seed N]` → `songs/my-emotions/my-emotions.mid`
