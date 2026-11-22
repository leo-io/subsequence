# Melody: F Minor Call and Response

## Request
> /subsequence-composer read C:\Users\user\code\subsequence\songs\melody scripts and fix any errors, and improve code organization

## Refined spec (music-composer)
- **Intent / feeling:** A driving, conversational F minor deep house / melodic techno piece over a four-on-the-floor groove. Piano and guitar engage in an intimate call-and-response conversation, while a high synth lead delivers expressive, arching phrases cushioned by swelling strings.
- **Key / mode:** F Aeolian (minor), chosen for its serious, epic, and emotionally compelling harmonic color.
- **Tempo / metre:** 118 BPM, 4/4 time signature, sitting right in Wayne Chase's 115–128 BPM energetic dance arousal band.
- **Groove:** Four-on-the-floor kick, backbeat snare on beats 2 and 4 (73% backbeat alignment), 8th-note closed hi-hats with dynamic ghost snares on higher energy sections.

| Section | Bars | Energy | Key | Chase numbers | Subsequence source | Close | Why (root motion, borrowing) |
|---|---|---|---|---|---|---|---|
| intro | 4 | 0.3 | F minor | 6m 4 3(7) 6m | `["i", "VI", "V7", "i"]` | authentic | Establishes the tonic home and introduces the piano call |
| build | 4 | 0.6 | F minor | 6m 2m 4 3(7) | `["i", "iv", "VI", "V7"]` | half | Circular harmonic gravity moving to dominant V7 open question |
| main | 4 | 1.0 | F minor | 6m 4 2m 3(7) | `["i", "VI", "iv", "V7"]` | half | High momentum with open dominant drive for maximum tension |
| outro | 4 | 0.4 | F minor | 4 2m 3(7) 6m | `["VI", "iv", "V7", "i"]` | authentic | Definitive 5 -> 1 resolution bringing the conversation home |

- **Melody plan:**
  - *Piano*: 4-beat question-and-answer signature call motif `[1, 3, 5, 4, None, 3, 2, 1]` on even bars; quiet strummed chord accompaniment on odd bars.
  - *Guitar*: Broken chord arpeggios answering on odd bars; silent on even bars during the piano call.
  - *Synth Lead*: Vocal-melodic (VM) phrases of 6 notes restricted to bars 0 and 2 of 4-bar units. Accented non-chord appoggiatura dissonance on metric beat 2.0 resolving by step; climaxes placed strictly at the 66%–75% mark (bar 2 at 67%); 100% Narmour leap recovery.
  - *Strings*: Harmonically supportive pad swelling in the vocal gaps (bars 1 and 3) as the acoustic answer.
  - *Bass*: Dynamic adaptation to drum syncopation — moving arpeggio on straight drums, heavy grounded root arpeggio when ghost fills add syncopation or energy >= 0.8.

## Acceptance criteria
Each criterion names the analyzer fact that checks it.

| # | Criterion | Target | Analyzer fact |
|---|---|---|---|
| 1 | Key reads as intended | F minor in top 1 | `key.detected_top3` |
| 2 | Intro ends with strong close | authentic cadence | `cadences.intro` |
| 3 | Build ends open | half cadence | `cadences.build` |
| 4 | Outro ends home | authentic cadence | `cadences.outro` |
| 5 | VM phrase length | 100% phrases between 5-10 notes | `melody.phrases_with_5_to_10_notes_pct` |
| 6 | VM phrase gaps | 100% gaps between 1.5-4.0 s | `melody.gaps_1_5_to_4_s_pct` |
| 7 | Narmour leap recovery | >= 70% leaps recovered by opposite step | `melody.leaps_recovered_by_opposite_step_pct` |
| 8 | Melodic climax position | 66% - 75% of section | `melody.climax_by_section` |
| 9 | Call-and-response separation | Guitar answers on odd bars (silent on even bars) | Track note counts & channels |
| 10 | Low register clarity | 0 close intervals below Eb3 | `close_intervals_below_Eb3` |

## Implementation
- Folder: `songs/melody/` (`live_init.py`, `live_patterns.py`, `melody.mid`, `facts.json`)
- Cleaned and organized codebase into standard architectural sections:
  1. MIDI channel assignments matching the Ableton project (`mel.als`).
  2. Structural definitions (`FORM`, `composition.form(..., loop=True)` with `applied_form` guard).
  3. Harmonic progressions (`SECTION_CHORDS`, `composition.section_chords`).
  4. Melodic motifs and appoggiatura figures (`PIANO_CALL`, `BUILD_LEAD`, `MAIN_LEAD`).
  5. Pattern definitions with corrected call/response logic and dynamic bass syncopation response.

## Validation
Render: `python songs/melody/live_init.py --render [--seed N]`
Analyze: `python <skill>/scripts/analyze_midi.py songs/melody/melody.mid --form "intro:4,build:4,main:4,outro:4" --key "F minor" --melody 4 --bass 2 --json songs/melody/facts.json`

| Round | Change | Failed criteria |
|---|---|---|
| 1 | Baseline analysis of original code | Guitar always playing (#9: 192 notes, no response gap); period slicing bug (consequent never played); leap recovery only 11% (#7); climax at 0% and 6% (#8); dead code in bass syncopation; outro ending on unresolved Edim (#4). |
| 2 | Fixed guitar gating (`if not piano_call_active`); fixed `PIANO_CALL` as a 4-beat motif with `p.motif`; bound explicit section progressions with authentic/half cadences; sculpted synth lead with 66-75% climax, appoggiaturas on beat 2.0, and 100% leap recovery; adjusted bass syncopation threshold to 0.58. | None (10/10 passed). |

| # | Target | Measured (final) | Pass |
|---|---|---|---|
| 1 | F minor rank 1 | F minor rank 1 (0.90) | PASS |
| 2 | Intro authentic | authentic (5 -> 1: strong close) | PASS |
| 3 | Build half | half (ends on 5: open, a question) | PASS |
| 4 | Outro authentic | authentic (5 -> 1: strong close) | PASS |
| 5 | Phrases 5-10 notes | 100% (all phrases 6 notes) | PASS |
| 6 | Phrase gaps 1.5-4.0 s | 100% (median 2.58 s) | PASS |
| 7 | Leap recovery >= 70% | 100% (2/2 leaps recovered by opposite step) | PASS |
| 8 | Climax 66-75% | Build: 67% (F5); Main: 67% (Ab5) | PASS |
| 9 | Guitar answers on odd bars | Guitar 96 notes (plays only on odd bars) | PASS |
| 10 | Mud below Eb3: 0 | 0 clashes | PASS |

**Verdict (music-composer):** 10/10 criteria pass across seeds 1 and 2. The call-and-response conversation between piano and guitar is restored, the synth lead features emotional appoggiatura sighs and climaxes placed precisely at Wayne Chase's golden ratio (67%), and the harmonic framework moves with natural acoustic gravity.
