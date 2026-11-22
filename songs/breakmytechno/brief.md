# Break My Techno

## Request
Detroit minimal techno version of "Break My Soul": 115 BPM, G# minor, 256 bars (~8:54), 16-bar blocks, drums-only edges for DJ mixing. One B major triad stab on top almost throughout; mood changes only through the bass beneath it.

## Defaults taken (no interview, per the brief's detail)
Instrumental; Groove/Riff First variant (bass hook first, harmony is fixed); seed 1; channels: drums 10, bass 2, stab 3, pad 4, strings 5, vocal hook 6; filter = CC74, reverb send = CC91; no live harmony engine.

## Form Map
| Bars | Section | Content |
|---|---|---|
| 1-16 | edge_in | kick, hat, rim clave only |
| 17-64 | cook1 | stab + bass G#/A creep (A on bar 4 of each 4); pad enters bar 49 on D#; filter 36->56 |
| 65-128 | cook2 | A on bars 3-4 of each 4; pad D#->D (73)->C# (81)->C (89) freezes; filter 56->72 |
| 129-144 | rise | kick out; bass D# then A (halves in last 4 bars); hats stutter, last bar cut after 2 beats; filter opens to 127 |
| 145-192 | shine | pad C->C#; stab gains C# (add9); bass E, F#, B, G# loop; kick+clap+open hat+strings+vocal hook on bar 145 |
| 193-240 | tense | G#/A pedal (A on bars 2-4), pad back on C, ghost echoes of shine stab, filter 100->18 |
| 241-256 | edge_out | kick, hat, rim clave |

## Decisions
- Frozen dissonance = C: a semitone over B, a tritone over F#. It resolves up to C# (the 9th), so the shine is "B triad + 9th".
- Vocal hook is in the G# minor pentatonic (G#, B, C#, D#, F#): a pure chord-tone + 9th line.
- No clap/snare anywhere outside the shine. Rise has no kick.
- Bass A-pin uses `Degree(2, chroma=-1)` (A natural is not in G# aeolian).

## Subsequence features
| Feature | Used? | Role |
|---|---|---|
| Form / Section / energy | yes | 256-bar form |
| Motif.generate, Motif.notes, Motif.preset, .then/.vary/.answer | yes | bass hook, vocal hook, clave |
| euclidean (sequence_utils) | yes | stab rhythms |
| cc_ramp / cc | yes | filter sweep, dry reverb |
| ratchet, hit_steps, ghost_fill, swing | yes | drums |
| harmony engine / Progression | no | one fixed triad; bass carries the harmony |

## Render
`python songs/breakmytechno/live_init.py --render [--seed N]` -> `breakmytechno.mid` (8.9 min).
