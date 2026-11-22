# Drum Lab

## Request
> Multiple hot-reload Subsequence files to study the drum generators by jamming and changing parameters on the fly.
> Target structure: **Cell** = 2 bars (bar 1 call, bar 2 response); **Phrase** = 4 bars, bar 4 gets a small variation
> (stutter chop, reversed hit, open hat, or a dropped kick on beat 4). Drums only.
> House music, 118 BPM, Todd Terry groove (`toody terry.agr`). The final patterns should feel like a collaboration
> between Todd Terry, Kenny Dope and J Dilla.

## Engine (`live_init.py`)
- 118 BPM, 4/4, GM kit on channel 10, seed 1.
- `composition.data["groove"]` = `Groove.from_agr("toody terry.agr", grid=0.25)`: about 0.05 beat late on every
  off-16th, velocities almost flat. Loaded once.
- **Groove is global (user, 2026-10-23):** every pattern in every lab applies it, at one shared `GROOVE` strength knob,
  after placing its hits (and before any `ratchet`, in the labs that use one). Subsequence has no composition-wide groove, so "global" = every
  `p.groove()` call reads the same template and the same knob.
- `--lab NN[,NN]` picks the labs to watch (layering), `--list`, `--render` (8 bars = 2 phrases, `drum-lab_labNN.mid`).
- The render clock is 24 ticks per beat, so the 0.05 drag comes out as 0.042 (one tick).

## Frame
| Unit | Length | Native |
|---|---|---|
| Cell | 2 bars | `p.bar_cycle(2)`: `.first` = call, `.last` = response |
| Phrase | 4 bars | `p.bar_cycle(4).last` switches on the bar-4 variation |

**Revised (user, 2026-10-23): no ratchet in the frame.** Call, response and bar 4 are built from aggressive steps,
mutes, solos and drum fills:
- Call / response: per-voice step lists (`CALL`, `RESPONSE`), plus `*_MUTE = {voice: (from, to)}` and
  `*_SOLO = (voice, from, to)` per bar of the cell.
- Bar 4: the kit cuts at `FILL_FROM` (12 = beat 4, 8 = beat 3; `FILL_KEEP` voices play through) and a fill from
  `FILLS` takes over with `p.sequence(steps, pitches, velocities)`: tom_run, snare_roll, kick_roll, clap_stab,
  dead_stop, open_hat.

## Style blend: Todd Terry × Kenny Dope × J Dilla (proposed defaults)
| Who | What they bring | Native mapping |
|---|---|---|
| Todd Terry | NY house swing, tough four-on-the-floor kick, hard fills into the downbeat | the `.agr` groove on the whole kit; bar-4 fills |
| Kenny Dope | break-style kick/snare syncopation on top of the house pulse, ghost snares | extra syncopated kicks per cell; `ghost_fill(bias="before")` on the snare |
| J Dilla | loose timing, a snare/clap that drags, uneven dynamics | `p.randomize(timing=, velocity=)`; a dragged snare from a hand-made `Groove(offsets=…)` layered on top of the global Terry groove |

Every voice gets its own pattern; all of them ride the global Terry groove, and Dilla's drag is an extra layer per voice.
`groove`, `rotate`, `dropout`, `thin` and `randomize` only change the notes already in their own pattern.

## Labs (one hot-reload file each, `live_patterns_labNN_<topic>.py`)
| # | Lab | Feature |
|---|---|---|
| 00 | frame | the cell/phrase frame + bar-4 menu on a fixed `hit_steps` kit |
| 01 | euclidean | `p.euclidean` per voice |
| 02 | bresenham_poly | the whole kit from one weights dict |
| 03 | cellular_1d | Wolfram rules, fixed vs evolving generation |
| 04 | cellular_2d | Life-like rules across voices |
| 05 | ghost_fill | density, the 8 bias modes |
| 06 | ratchet | rolls, stutters, velocity ramps |
| 07 | boundaries | `bar_cycle().last` vs `p.section.last_bar` vs `transition(fill=)` |
| 08 | thin | strategy, amount |
| 09 | rotate_dropout | displacement, gaps, transform order |
| 10 | rebuilds | `p.cycle`, `p.energy`, `p.data` |
| 11 | jam | the Terry × Dope × Dilla collaboration |

Each lab: docstring (what to listen for), KNOBS block, Experiments checklist.

**Shared frame (`frame.py`):** mutes, solos, the bar-4 cut and fill library, and the global groove live in one
module that every lab imports and `importlib.reload`s on save. A lab places each voice with the generator it studies,
then calls `frame.finish(p, voice, FRAME)`: the cut steps go through `p.thin(strategy=[1.0 on cut steps, 0.0 elsewhere],
amount=1.0)`, which removes exactly those steps whatever generator placed them, then `p.groove(...)`.

## Progress
| Goal | Status | Approved on |
|---|---|---|
| High-level plan | approved | 2026-10-23 |
| Engine (`live_init.py` + groove) | approved | 2026-10-23 |
| Lab 00 frame | approved | 2026-10-23 |
| Shared frame (`frame.py`) | built; lab 00 moved onto it, same onsets and pitches as approved | |
| Lab 01 euclidean | built, rendered, awaiting review | |
| Lab 02 bresenham_poly | not started | |

## Findings
- The Terry groove drags only the odd 16ths; even steps (the kick, the clap, the off-beat 8th hats) are untouched.
  Proof that it reaches the kick: a kick moved to step 11 renders at 11.17.

## Subsequence features
| Feature | Used? | Role |
|---|---|---|
| `Groove.from_agr`, `p.groove` | yes | Todd Terry swing, shared from the engine |
| `composition.watch` | yes | hot reload per lab |
| `p.thin` (per-step list, amount 1.0) | yes | the frame's mutes, solos and fill cut |
| `p.sequence` | yes | bar-4 fills (steps, pitches, velocities) |
| `p.bar_cycle` | yes | cell (2) and phrase (4) |
| `p.euclidean`, `p.rotate` | yes | lab 01 voices |
| step mode (`steps=`, `step_duration=`) | yes | lab 01 rim on a 12-step triplet grid |
| `p.randomize` | planned | Dilla looseness |

## Gaps & how they were handled
| Gap | Handling |
|---|---|
| Sub-tick groove detail | the render clock is 24 ticks per beat; the 0.05 drag is rounded to 0.042 |
