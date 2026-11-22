# New Hope

## Request
> Define in two paragraphs a harmony definition of a 6-minute house track at 118 BPM in F minor key. Define only the melody, bass, hook, and pad parts. (`song.md`)

## Refined spec (music-composer)
- **Intent / feeling:** a hypnotic, hopeful-but-somber club track: a four-bar loop that never quite stops cycling, with the flat-six sighing onto the fifth as its emotional centre.
- **Key / mode:** F aeolian (epic/somber), reference `song.md`.
- **Tempo / metre:** 118 BPM, 4/4, house band; 176 bars is about 5:58.
- **Groove:** four on the floor, off-beat open hat, clap on 2 and 4, light 54% swing.

| Section | Bars | Energy | Harmony source | Close |
|---|---|---|---|---|
| intro | 16 | 0.2 → 0.45 | live walk, high key pull | open |
| groove | 32 | 0.55 → 0.7 | live walk; hook enters at bar 17 | open |
| breakdown | 16 | 0.35 → 0.25 | live walk, high root diversity, no kick | open |
| build | 8 | 0.5 → 1.0 | live walk, V favoured at bar 4 | open (hang on V) |
| drop | 32 | 0.95 | live walk, hook + melody | soft (iv → i) |
| breakdown | 16 | as above | | open |
| build | 8 | as above | | open |
| drop | 32 | 0.95 | | soft |
| outro | 16 | 0.5 → 0.05 | live walk, key pull 0.9 | strong (V → i) |

- **Melody plan:** high register (root F5), conjunct, 8-bar line grown a-b-a-c from a 2-bar idea with a one-beat breath. Every idea opens on a downbeat appoggiatura (♭6 → 5 by default, or 4 → 3, 2 → 1) and resolves by step. Contour: arch in drops, ascending in builds, valley in breakdowns, descending in the outro.
- **Hook plan:** register around F4. Period: 2-bar antecedent ends on 2 or 5, 2-bar consequent restates it and lands on 1.
- **Bass / pad plan:** bass is the root in F1–F3 (octave bounce on the off-beats, chromatic approach into the next root). Pad is four-note, voice-led voicings with 7ths when the engine offers them, kept in 53–79.

## Engine plan (reference → generative engine)
- **Pinned identity:** bar 1 of every four-bar loop is i; bar 4 is a dominant-function chord (v, V or bVII); every section close is a cadence request; hook antecedent/consequent degrees; the sigh pins on the melody's first two notes.
- **Left to chance (and bounds):** every other chord (aeolian_minor graph walk, dials per section); hook and melody pitches and euclidean rhythms (per seed); which hook/melody variant a pass plays; bass syncopation and approach notes (probability scaled by energy); hats, shaker and tambourine density.

| Subsequence feature | Used? | Role |
|---|---|---|
| live harmony (`harmony`, `pin_chord`, `section_cadence`, `on_section` retune) | yes | the whole chord stream; per-section key_pull / root_diversity / dominant_7th |
| `freeze`, `request_cadence` | no | `section_cadence` covers the standing closes; freezing would fix a walk |
| melody (`Motif.generate`, `.vary`, `.answer`, `.then`, `Phrase.develop`, `p.phrase`) | yes | hook period and 8-bar melody lines |
| `MelodicState` | no | it ignores phrase and climax targets; generated motifs fit the brief |
| rhythm (`Motif.euclidean`, `ghost_fill`, `bresenham_poly`, `ratchet`) | yes | motif rhythms, hats, perc |
| evolution (`every`, `dropout`) | yes | ratchet every 8 cycles, energy-scaled dropout |
| `evolve` / `markov` / `lsystem` | no | the hook and melody are already developed by `Phrase.develop` |
| form and energy (`Form`, `energy`, `transition`) | yes | 176-bar form, ramps, snare-roll fill before each drop |
| feel (`swing`, `cc_ramp`) | yes | 54% swing, pad filter sweep in builds |
| control (`seed`, `seed_for`) | yes | every stream derived from the composition seed |

## Implementation
- Folder: `songs/new-hope/` (`live_init.py`, `live_patterns.py`)
- Render: `python songs/new-hope/live_init.py --render [--seed N]`
- This repo version has no `mood=`; the per-section temperament is the `harmony_dials` table, applied by an `on_section` callback in `live_init.py` (so it hot-reloads).
- Deliberate rule-breaking: the melody places an unresolved scale tone on the downbeat (`fit=0`) on purpose, as the appoggiatura the spec asks for.
