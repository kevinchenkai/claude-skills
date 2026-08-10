# Acceptance Criteria

> 🔴 **In this project, criteria were wrong 6+ times and finished clips 0 times.**
> Treat every criterion as suspect until it has been calibrated in both directions.
> **A criterion can only falsify. It can never prove the video is good.**

---

## 1. Order of checks (stop at the first failure)

| Layer | Question | Tool |
| --- | --- | --- |
| ① **Pixels** | Is there a picture at all? | `h3_verify.py` |
| ② **Numbers** | Does the ending move? Did it cut where intended? | `h3_freeze.py`, `h3_cutdetect.py` |
| ③ **Eyes** | Did it perform the intended thing? | `filmstrip.py` |
| ④ **Ears** | Is the music what was asked for? | listen |

**Never skip ③.** Layers ① and ② only exclude failures.

---

## 2. ① Pixel validity — the silent-NaN gate

Require: expected **frame count**, **zero blank frames**, **`nan=False`**, valid audio.

> 🔴 **`status=success` means nothing.** A silent-NaN clip reports success, decodes cleanly,
> yields the right frame count — and every pixel is 0. Blankness is `std() < 1.0` per frame.
>
> ⚠️ Files land on disk with a lag. An empty `ls` right after completion is usually stale
> metadata, **not** a missing output — query the server's own history for the reported path.

## 3. ② Tail activity — **ratio and absolute, both**

Tail activity = mean frame-difference over the last 2 s ÷ the clip's median frame-difference.

> 🔴 **The ratio self-normalizes, so a uniformly slow clip passes while frozen.**
> Measured: a known-bad clip scored **0.50** (above the 0.40 line) while its absolute tail motion
> was **0.20** — about **1/11** of a known-good clip's 2.31. The whole clip was slow, so the
> denominator collapsed and the ratio looked healthy.

**Require both**: ratio ≥ line **and** absolute tail motion ≥ floor. Calibrate the floor from your
own known-good and known-bad samples; don't inherit a number blindly.

**For freeze onset specifically, use an absolute threshold.** A relative one shrinks with the clip
and understates a real freeze. Frozen frames sit far below normal motion — the separation is wide,
so the threshold is not delicate.

> ⚠️ Reporting wording matters: calling a 0.7–1.0 s dead ending "a low-motion segment under one
> second" is technically true and **materially misleading.** Say freeze, and give the number.

## 4. ② Cut detection — and its blind spot

A true hard cut is an **isolated narrow spike**: one or two frames far above median, with both
sides quiet.

> 🔴 **Counting frames over a threshold is wrong.** It once reported **19 cuts** for what was a
> continuous push-in plus a head turn — nearly leading to the wrong seed being chosen. *Nineteen
> consecutive spikes prove it is **not** a cut.*
>
> 🔴 **Relative thresholds aren't comparable across clips** with different motion levels.
>
> 🔴 **Dissolves are invisible to this.** In near-static clips the model's invented transitions are
> gradual, and the detector reports 0. **"0" does not mean "one cut" — only eyes settle that.**

Also log **written cut time vs actual**. Calibrate only after several samples agree on an offset.

## 5. ③ The human-eye pass — not optional

Build a filmstrip and ask, in order:

1. **Can you retell the intended story from it?**
2. Did the model **invent** anything — an unrequested close-up, an expression contradicting the brief?
3. Does the **ending still move**, or is it held?
4. **At the cut**: does anything pop — proportion, wardrobe, background?
5. **Identity**: same person throughout; no morphing during large motion.

> 🔴 **A number crossing its line ≠ improvement.** Real case: a motion criterion rose 0.241 → 0.358
> and all three numeric layers passed — the filmstrip showed the model had added a front-facing
> close-up and made her smile when the prompt said she never smiles. **The extra motion came from
> invented content.**

**The cut region deserves extra attention**: the first frame anchors the opening and the last frame
anchors the ending, so **the area around the cut has the least anchoring** and the most freedom.

## 6. Calibrating a new criterion (mandatory before use)

1. Write down **what you claim**, and **what the data should look like if it's true**.
2. Choose metric — must match the claim's *shape*. Averages can't detect rhythm; envelope
   correlation can't detect a sustained score.
3. Run it on a **known-good** and a **known-bad** sample.
4. **Both directions must separate.** If not, **delete it** — do not tune until it looks right.
5. Note the **blind spots** in the tool itself, so the next reader doesn't over-trust it.

> A discarded example: a "close-up detector" reported zero close-ups in footage where they were
> plainly visible. It was dropped rather than tuned, and the observation rested on the filmstrip.

**Any ÷median criterion: ask whether the denominator can collapse.** Two independent criteria here
have already been fooled that way.

## 7. Comparing two versions

- **Single variable**, and assert it programmatically — diff the configs, confirm only the intended
  key differs, and confirm the prompts are byte-identical otherwise.
- **Two seeds, paired.** Same seed on both arms.
- 🔴 **Establish the noise floor**: the difference between two seeds of the *same* prompt. If your
  variable's effect is smaller than that, **you have no effect.** Measured once at ~8× — the
  variable was pure noise.
- **Seeds must agree in direction.** If they disagree, that is noise, not a win.
- Ports/GPUs are **lanes, not variables** — the same tag on two cards yields the same clip.

## 8. Delivery report

State plainly: what passed, what failed, **what could not be verified**, and which known issues
remain. A report claiming everything passed is the one to re-check first.

> An honest "not applicable — this couldn't be measured" is worth more than a green check.
