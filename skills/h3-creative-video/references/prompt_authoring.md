# Writing the H3 Video Prompt

Ordered by **decision sequence**, not by field order. Each decision constrains the next.

## Contents

0. Photoreal versus stylized
1. Official structure
2. Shots and cuts
3. Final-shot continuation
4. Camera endpoints
5. Expression trajectory
6. Conditioning entropy
7. Disproven prompt paths
8. Audio

---

## 0. First fork: **photoreal or stylized?**

**This is a fork, not a dial. Getting it wrong wastes the whole round.**

| Goal | Style wording | Use for |
| --- | --- | --- |
| **Stylized / genre** | `cinematic`, film-stock and camera-body language, dramatic lighting | Action, fantasy, wuxia — the point is *looking good* |
| **Photoreal / lifelike** | 🔴 **None of the above.** Candid-documentary language instead | Romance, slice-of-life, portrait — the point is *being believable* |

> 🔴 **Cinematic ≠ realistic.** `cinematic` / cinema-camera names / `shallow depth of field`
> push the model toward **commercial-ad look — and that polish is exactly what viewers call
> "AI-looking."** A run of 21 clips each passed its own criteria and was rejected wholesale as
> "very AI" because no criterion was testing *believability*.

**Test for any adjective: does it describe a fact or a feeling?**
Fact (`35mm`, `overcast`, `uneven`) → keep. Feeling (`radiant`, `stunning`, `perfect`) → cut.

> 🔴 Base photorealism is primarily owned by the keyframes. Realism wording in the *video* prompt
> did not improve pores/light/depth across two seeds. The video stage can still introduce morphing,
> synthetic hair, temporal texture, or motion artifacts.

---

## 1. Official structure (follow it exactly)

Alignment line **first**, one blank line, then three named fields:

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the
0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of
the target video.

integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

| Rule | Detail |
| --- | --- |
| Alignment line | **Must be the first line**, followed by a blank line |
| `S.SS` | Effective duration, **exactly two decimals** (`frames ÷ 24`) |
| Last frame belongs to the **final** shot | Write `(from Shot N)` — **not** `(from Shot 1)` |
| `[Shot 1]` | **No timestamp** |
| `[Shot 2+]` | Strictly increasing `At 00:MM.SSS`, within duration |
| Empty fields | Write `N/A` — don't omit the field |

Write **prose in the fields, not a bag of tags.**

---

## 2. Shots: how many, and where to cut

Official guidance: **FL2VA generally favors a single shot**, so the model can interpolate
continuously; use multiple shots only when explicitly wanted.

**We deliberately deviate — here is the condition and the reason:**

| Situation | Do |
| --- | --- |
| First and last frame are **one continuous action** | **Single shot** — follow the official default |
| The piece needs **two different actions** (e.g. an expression beat, then a movement) | **Cut.** One long shot holding two actions makes the model jump mid-way on its own |
| You need the **mid-shot framing** to change | **Cut** — that's the only lever (see §4) |

Keep each shot **~5–6 s, performing one primary state transition**. Secondary wind, fabric, gaze,
or environmental reactions may support that transition without becoming competing plot beats.
Multi-shot cut timing has landed within a few frames of the written time in the recorded profile.

> ⚠️ Observed cuts have landed on both sides of the written timestamp. Log target versus actual
> every run; only calibrate an offset once several comparable samples agree.

---

## 3. 🔴 The final shot needs semantic and compositional continuation

Avoiding an early semantic endpoint is useful, but **an endpoint-free verb is not sufficient**.
In paired V3 human review, “still turning” still reached a visually settled subject state before
the end; reinforcing the wording and adding stronger wind did not improve that observation. The
published 1.04–2.12s global low-motion runs were in the opening, so do not use those numbers as
tail-freeze evidence.

Use two tests:

| Final-shot design | Risk | Response |
| --- | --- | --- |
| Arrives, poses, completes a turn, finishes a smile | explicit semantic endpoint | redesign unless an intentional hold is acceptable |
| Keeps walking, passes through, continues turning | no named endpoint | better starting point, **not a freeze guarantee** |
| Last frame has an exit vector, asymmetric weight transfer, unresolved crop/direction | compositional continuation | strongest available design affordance; still measure paired seeds |
| Last frame reads as a balanced hero pose or settled silhouette | compositional endpoint | redesign the image, not just the clause |

If the brief *asks* for an endpoint action ("she spins around"), **keep the look, remove the
endpoint**: end mid-rotation instead of back at front. Say plainly that a completed 360° will
likely freeze — that's the user's call, not a silent rewrite.

If paired seeds still exceed the freeze gate, stop wording-only reinforcement. Change the final
frame's spatial affordance, shorten the final interpolation window, split the visual generation
with an audio-post plan, or label the result a prototype.

---

## 4. Camera: endpoints only

| Attempt | Result |
| --- | --- |
| Changing the camera-move keyword | ❌ No difference across seeds |
| Changing amplitude adverbs | ❌ No difference |
| **Naming concrete start/end framing** ("waist-up" → "knees-up") | ✅ **This is what actually decides it** |
| Forbidding mid-shot widening, in the strongest wording | ❌ **Disproven, two seeds** |

**Mechanism:** the mid-shot camera path is *interpolation between your two frames*. Endpoints are
yours; the middle is not. **To control the middle, add an endpoint — i.e. cut.**

Constraining a *character's* action across a whole shot does work. Constraining *camera* movement
does not. Different things.

---

## 5. Expression: write the trajectory, not the anatomy

**Negation alone fails.** `NOT smiling` excludes one state without naming a replacement, and the
model picks from everything left. Say what the face *does*.

But don't over-correct into muscle-by-muscle choreography — percentages and named muscles are not
things a video model reliably executes.

> **Test: could a viewer tell true from false at a glance?**
> `closed-lip` ✅ keep. `smile decays by half` ❌ cut.

For a smile, all three beats must be written — **rise → peak → ease back down**. Leave out the
fall and it holds at peak, which reads as a mask.

> ⚠️ Even written correctly, the decay is often compressed into a hold. If it matters, consider
> **shortening that shot** rather than adding more facial wording.

---

## 6. Reduce conditioning entropy

Fewer, cleaner controls beat more wording.

- **One primary state transition per shot.** Wind, hair, and fabric are *secondary* motion — they add life
  without competing.
- **Let the last frame define the end state.** Describing the final pose in words *and* supplying
  it as an image creates two slightly different targets.
- **Drop control dimensions already known not to work** — they only dilute.
- **Prefer positive phrasing.** A negation is acceptable *only* with a positive clause carrying the
  action; it must never be the sole instruction.

---

## 7. 🔴 Already disproven — **do not spend a round on these**

| Don't | Evidence |
| --- | --- |
| Put realism wording in the **video** prompt | Two seeds: no change in pores/light/depth |
| Forbid mid-shot pull-back | Two seeds: frames essentially identical to control |
| Swap camera-move keywords | Two seeds: indistinguishable |
| Rewrite ending wording to stop the freeze | Two seeds failed; and later, four clips identical |
| Add background motion to stop the freeze | Two seeds failed — the last frame anchors the whole image |
| Treat `still turning` as a guaranteed freeze fix | V3 paired seeds still froze; stronger wording/wind was worse |
| Pile up negations (`never A, never B, never C`) | No measurable gain over one positive clause |
| Exceed the frame ceiling for a longer piece | **Silent NaN**, all black |

**Positive/negative phrasing of the "keep moving" clause is *equivalent*** — four clips, two paired
seeds, identical freeze onset. Either is fine; **a negation just needs a positive clause under it.**

---

## 8. Audio

| Field | Controllability |
| --- | --- |
| `overall_soundscape` | Weak. Worth writing; don't count on it |
| `non_diegetic_music` | ✅ **Verified controllable** — write **instrumentation + tempo + dynamics** |

Match the ending to the picture: if the visual deliberately doesn't land, ask for music that
**doesn't resolve** — no final cadence. A resolving chord under an unfinished motion fights itself.

> Metrics can show *music exists* and roughly how loud. **Only ears confirm it's the instrument
> you asked for.**

For work longer than the validated single-generation duration, choose the audio architecture before
generation. Independent H3 clips have produced audible seams. Either rebuild a continuous ambient
bed/score in post, deliver intentional silence, or shorten the piece when native continuous audio
is mandatory. Prompt wording cannot repair an edit between independently generated audio streams.
