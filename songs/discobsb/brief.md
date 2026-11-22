# discobsb

## Request
> lets create a song in fminor 118bpm disco house with 6min lenght called discobsb

## Progress
| Goal | Status | Approved on |
|---|---|---|
| Entry · song, variant, delivery | approved | 2026-10-19 |
| Concept · 1/5 central idea | approved | 2026-10-19 |
| Concept · 2/5 signature motif | approved (defaults) | 2026-10-19 |
| Concept · 3/5 three-axis profile | approved (defaults) | 2026-10-19 |
| Concept · 4/5 perspective | n/a (instrumental) | |
| Concept · 5/5 profile → dials | approved (defaults) | 2026-10-19 |
| Form · 1/7 meter, tempo, key | approved (given) | 2026-10-19 |
| Form · 2/7 macro form and bars | approved | 2026-10-19 |
| Form · 3/7 energy per section | approved | 2026-10-19 |
| Form · 4/7 tonal strategy | approved | 2026-10-19 |
| Form · 5/7 contrast map | approved | 2026-10-19 |
| Form · 6/7 cadence plan | approved | 2026-10-19 |
| Form · 7/7 Form Map and describe() | approved | 2026-10-19 |
| Groove · 1/8 drum pattern | approved | 2026-10-19 |
| Groove · 2/8 feel | approved (56% swing, 16th grid) | 2026-10-19 |
| Groove · 3/8 velocity dynamics | approved | 2026-10-19 |
| Groove · 4/8 bass rule | earlier hooks rejected; v4 merged (four hand-written Chic-style bars: call, answer, call variation, turnaround), awaiting verdict | |

## Decisions
- Folder `songs/discobsb/`, new song, instrumental.
- Variant: Groove / Riff First (Groove → Melody → Harmony after Concept → Form).
- Delivery: `.mid` render plus live hot-reload; GM drums on ch10; one fixed seed, `seed_for` per part.
- F minor, 118 BPM, 4/4. 6:00 is 177 bars; target 176 bars (5:58.6).
- Central idea: a confident disco bassline carries the track, with string-like stabs answering it; classic 70s lift on a modern house kick.
- Signature motif: octave-bounce 16th bass riff (root-octave-root, syncopated gap, locked to kick). String-like stabs answer in call-and-response, hitting the riff's rests (off-beat "and" of 2 and 4).
- Profile: Evaluation 4 (positive), Potency 4 (assertive), Activity 4 (driving). Dials: F aeolian, `aeolian_minor` style, strong key_pull, high velocity range, high energy ceiling.
- Form (176 bars): intro 16, groove 16, strings break 16, build 8, drop 32, groove 2 16, mini break 8, build 2 8, drop 2 32, outro 24.
- Energy: intro .25→.50, groove .60→.70, strings break .35→.30, build .55→1.0, drop 1 .90, groove 2 .65→.60, mini break .30, build 2 .60→1.0, drop 2 1.0, outro .55→.05. Bass riff `min_energy` ≈ .45.
- Tonal strategy C: one bound loop in F aeolian, no key overrides, no drop-2 key lift. Chord detail is decided in Harmony.
- Contrast (approved): breaks move stabs and pad up to F4–F5 and drop the kick and bass; builds hang on V with a snare roll; drops put bass low (F1–F3) with stabs mid, drop 2 stabs up an octave; the outro peels off from the top. Harmonic rhythm: 1 chord per bar in drops and grooves, 2 bars in breaks and outro.
- Cadences: intro, groove, strings_break, build, groove_2, mini_break, build_2 open (builds hang on V); drop and drop_2 soft (iv → i); outro strong (V → i).
- Section names are unique (groove_2, build_2, drop_2) so repeats carry their own energy.

| Subsequence feature | Used? | Role |
|---|---|---|
| `Form` / `Section` / `composition.form` | yes | 10 sections, 176 bars |
| `composition.energy` | yes | per-section start→end ramps |
| `section_cadence` | yes | standing close per section |
| `hit_steps`, `ghost_fill` | yes | kick, clap, open hat, tambourine, crash; closed hat and shaker ghosts |

| `Motif.steps`, `Motif.then`, `Motif.euclidean` | yes | bass (v4): four hand-written bars (call, answer, call variation, turnaround) assembled with then; root-octave pulse in intro/outro, 16th pedal in builds. Not generative: v3 had Motif.generate for the same bars |
| `p.transpose(12)` | yes | drop 2 plays the bass hook an octave up |

| Gap | How handled |
|---|---|
