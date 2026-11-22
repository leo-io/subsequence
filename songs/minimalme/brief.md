# minimalme

## Request
> create a 64 beat loop of a elaborated minimal techno song and save it to songs/minimalme

## Progress

| Workflow | Goal | Status | Approved on | Evidence |
|---|---|---|---|---|
| Entry | song, variant, seed | approved | 2026-11-13 | this brief |
| Concept | idea + signature motif | approved | 2026-11-13 | this brief |
| Form | meter/tempo/key, single 16-bar section | approved (implied by request) | 2026-11-13 | live_patterns.py |
| Groove | drum pattern | approved | 2026-11-13 | render OK; 61 kicks; syncopation ~0.68-0.71 per cell |
| Groove | feel (swing 56%) | approved | 2026-11-13 | odd 16ths pushed ~0.04 beat; kick and off-beat 8ths on grid |
| Groove | velocity dynamics | approved | 2026-11-13 | kick 112 on bars 1/5/9/13 else 100; open hat 78/60 pulse |
| Groove | bass hook rule | approved | 2026-11-13 | 15 bars, steps 2 3 6 10 11 14, no kick clash |
| Groove | kick lock + dead-spot map | approved | 2026-11-13 | 0 bass-on-kick clashes; riff slots 1 5 7 9 13 15 |
| Groove | ghosts, fills (4 seams) | approved | 2026-11-13 | read-back of last beat of bars 4/8/12/16 |
| Groove | audition + workflow sign-off | approved | 2026-11-13 | 401 notes, 64 beats; lead-masking check deferred to after the riff |
| Melody | 1 riff rhythm | approved | 2026-11-13 | A 7 9 13 � A' 1 7 9 13 � B 5 9 13 15 � A'' 7 9 13; no overlap with kick/bass |
| Melody | 2 motif identity | approved | 2026-11-13 | core 5-b3-1 = D#4 B3 G#3; lead-ins G#4 (A') and F#4 (B) |
| Melody | 3 phrase architecture | approved | 2026-11-13 | per cell: bars 1-3 riff, bar 4 re-pitched; Form loops |
| Melody | 4 register + climax | approved | 2026-11-13 | range 52-70, unique peak A#4 in bar 12 |
| Melody | 5-7 outline, audition, workflow sign-off | approved | 2026-11-13 | all cells strictly descending; solo file saved |
| Harmony | 1 source + style (written i i bVI i) | approved | 2026-11-13 | |
| Harmony | 2-3 rhythm + chart | approved | 2026-11-13 | i7 32 beats / bVImaj7 16 / i7 16 = 64 |
| Harmony | 4-8 cadence, colour, voicing (pad), audition | done at user's request to finish without further approval | 2026-11-13 | pad MIDI 44-54, vl_distance 2, bar 16 silent |
| Arrangement | layering, seams, loop | done (no further approval, per user) | 2026-11-13 | 514 notes, 64 beats, form loops |

## Decisions
- Instrumental, folder `songs/minimalme/`, seed 1, render only (`python songs/minimalme/live_init.py --render`).
- Variant: Groove / Riff First (Groove → Melody → Harmony).
- 124 BPM, G# aeolian, 4/4; 64 beats = 16 bars, one seamless loop.
- Central idea: "A hypnotic, nearly static loop where small changes carry the interest."
- Signature motif: 3–4 note off-beat riff, narrow register, fixed pitches; rhythm and accents shift every 4 bars.
- Cells: A core · A' hat/perc density · B motif rhythm mutated · A'' drop-out then return into bar 1.
- Sound: 4/4 kick, off-beat hat, rim/clap, euclidean perc, rolling sub-bass hook, chord-stab drone, one riff.

### Groove & Bass (ch05)
| Cell | Kick | Rim | Open hat | Closed hat | Perc (low_conga) |
|---|---|---|---|---|---|
| A (bars 1-4) | 0 4 8 12 | 12 | 2 6 10 14 | euclid 7/16 | euclid 3/16 |
| A' (5-8) | same | 7 12 | same | euclid 9/16 + ghost_fill 0.2 | euclid 5/16 |
| B (9-12) | same | 4 12 | 2 6 10 | euclid 5/16 rot 2 | euclid 3/16 rot 5 |
| A'' (13-16) | same; bar 16 only step 12 | 12 | same; bar 16 none | euclid 7/16; bar 16 none | euclid 3/16; bar 16 only step 15 |

- Feel: shared `FEEL = Groove.swing(56)` (user chose 56% over the proposed 52%), applied to the drums; bass and riff will reuse it.
- Velocity: flat levels, no ramps. Kick accent 112 on cell turns (bars 1, 5, 9, 13), else 100. Open hat 78 on steps 2/10, 60 on 6/14. Closed hat/rim/conga keep their ranges; `randomize` skipped (whole-pattern, would wobble the kick).
- Bass: 1-bar rolling riff on steps 2 3 6 10 11 14 via Motif.generate (aeolian, valley, tonic pinned, max 3 pitches, root G#1, 0.2-beat notes, vel 85-105). B cell: `.vary(3, keep_contour=True)` changes one pitch (the note at beat 2.5). Bar 16 silent. No `su.mask` needed because the rhythm avoids kick steps by construction.
- Dead spots: the riff (Melody) lives only on steps 1 5 7 9 13 15 (no kick, no bass); recheck with choke against bass steps after the riff exists.
- Seams (last beat of each cell): bar 4 closed-hat 16th run doubled by ratchet; bar 8 bass cut (motif span 3.0), kick continues; bar 12 conga stack on 13/14/15 not already hit; bar 16 gap (silent bass, lone kick, conga pickup 15). No velocity builds.

### Melody (ch03)
| Cell | Riff steps | Register | Pins | Notes |
|---|---|---|---|---|
| A | 7 9 13 | TBD | TBD | core figure |
| A' | 1 7 9 13 | TBD | TBD | adds lead-in |
| B | 5 9 13 15 | TBD | TBD | shifted, rolls to next bar |
| A'' | 7 9 13 | TBD | TBD | bar 16 silent |
- Riff identity: Motif.generate per cell, aeolian, descending, pins on the last three notes = 5, b3, 1 (D#4, B3, G#3), root G#3, 0.3-beat notes, vel 75-95. Lead-in pitch is free: G#4 in A', F#4 in B. Bar 16 silent.
- Phrase: Phrase.develop(riff, bars=4, plan=[a,a,a,b]) per cell, flattened and joined into a 16-bar line placed with p.phrase(align='section'). Form now loops (loop=True), needed for section-aligned placement in the 17th bar.

### Harmony (ch04)
| Cells | Chord | Beats | Source |
|---|---|---|---|
| A + A' (bars 1-8) | G#m7 (i7) | 32 | written progression bound in live_init.py |
| B (bars 9-12) | Emaj7 (bVImaj7) | 16 | same |
| A'' (bars 13-16) | G#m7 (i7) | 16 | same |

- Harmony voice: quiet held 4-note pad (channel 3), `p.chord(chord, root=C3, count=4, voice_leading=True)`, vel 45-60, one chord per bar, silent in bar 16. Voicing only lands at 44-54 or 56-66; 56-66 sits on the riff's core pitches, so C3 (44-54) was kept; its bottom G#2 (44) doubles the bass's top note.
- After the Harmony 4-7 proposal the user asked to finish without further approval, so the pad, arrangement check and revision pass were completed in one go.

### Arrangement (ch06)
All four parts (drums ch10, bass ch2, pad ch3, riff ch4) play the whole loop; the cells differ by density (A'), rhythm (B) and the bar-16 gap (A''). Seams: bar 4 hat stutter, bar 8 bass cut, bar 12 conga stack, bar 16 gap (bass, riff, pad out; kick on 12 and conga pickup 15 remain). Form loops, so bar 17 is bar 1.

## Subsequence Feature Map for This Song
| Subsequence feature | Used? | Role |
|---|---|---|
| Composition, Form/Section, form(loop=True) | yes | 16-bar seamless loop |
| hit_steps, sequence, ghost_fill, ratchet, generate_euclidean_sequence, rotate | yes | drums, kick/open-hat accents, euclid hats and perc, seams |
| Groove.swing / p.groove | yes | shared 56% feel |
| Motif.generate / .vary / Motif.join / Phrase.develop / p.motif / p.phrase | yes | bass hook and riff |
| progression, composition.harmony(progression=) , p.chord voice_leading | yes | written i7 / bVImaj7 chart and pad |
| seed_for | yes | every generated stream |
| sequence_utils.syncopation, cseg, vl_distance | yes | checks |
| energy, transition, conductor, freeze, section_cadence | no | fixed-level loop, nothing to ramp |
| su.mask / choke | no | rhythms avoid the kick and each other by construction |
| randomize | no | whole-pattern, would wobble the kick |

## Gaps & How They Were Handled
| Workflow item | Gap | Option chosen | Code written |
|---|---|---|---|
| Euclid step list from a pulse count | euclidean pattern verbs can't be rotated per voice | glue: `euclid_steps()` over su.generate_euclidean_sequence + su.rotate | live_patterns.py |
| Per-step velocity | hit_steps takes one value or a range | used p.sequence(velocities=) | live_patterns.py |
