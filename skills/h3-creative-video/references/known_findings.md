# Known Findings — proven, disproven, unsolved

**Read this before proposing an experiment.** Most of its value is in the *disproven* column:
those are rounds you don't have to spend again.

Evidence tiers: 🟢 two seeds, same direction · 🟡 single sample or indirect · ⚪ inherited from docs

---

## 1. 🟢 Proven

| Finding | Consequence |
| --- | --- |
| **Prompts govern motion; keyframes govern form** | Ask first: *does the thing I want exist in the two frames?* If not, the prompt is the wrong lever |
| **Photorealism is decided at image generation** | Realism wording in the video prompt: no change across two seeds |
| **The final shot's action must have no endpoint** | Endpoint-free actions perform to the end; endpoint-bearing ones finish early and hold |
| **The model performs ~65–87 % of a shot, then holds** | Shortening a shot shrinks the action proportionally — it doesn't fix the hold |
| **Framing is controllable only at the endpoints** | Name concrete start/end framing; to control the middle, add a cut |
| **Cuts must carry new information** | Two near-identical shots ⇒ the model invents something to fill the cut |
| **The last frame's *composition* sets the ending pose** | A "finished pose" last frame produces a finished-looking ending |
| **One shot, one action** | Two actions in one long shot ⇒ a self-inflicted jump mid-shot |
| **Score instrumentation is directable** | Write instrument + tempo + dynamics; confirm by ear |
| **Multi-shot keeps audio continuous** | Separate generations always break at the seam |
| **Structured three-field format beats prose** | Adopting the official format improved results |

## 2. 🔴 Disproven — do not re-run these

| Attempt | Result |
| --- | --- |
| Realism wording in the **video** prompt | Two seeds: pores/light/depth unchanged |
| "Never pull back / never widen", strongest phrasing | Two seeds: frames ~identical to control |
| Swapping camera-move keywords or amplitude adverbs | Two seeds: indistinguishable |
| Rewriting the ending wording to stop the freeze | Two seeds failed |
| Adding background motion to stop the freeze | Two seeds failed — the last frame anchors the whole image |
| Single shot instead of two, to fix the ending | **Worse** than two shots |
| `never stops` vs a purely positive clause | **Equivalent** — four clips, two paired seeds, identical freeze onset; effect ~8× below the seed noise floor |
| Exceeding the frame ceiling for a longer piece | **Silent NaN**, all black |
| Displacement magnitude as the driver of "performs to the end" | Backwards — a small displacement passed, a large one failed. **Endpoint presence** is the real variable |

> **On negation:** the failures attributed to "negation backfiring" were cases where a negation was
> the **only** instruction (`NOT smiling`) or was fighting a strong model prior. A negation
> *supported by a positive clause* is fine — that combination produced the best tail result on record.
> **Don't ban negation; ban unsupported negation.**

## 3. 🔴 Unsolved

| Problem | Tried | Remaining ideas |
| --- | --- | --- |
| **~0.7 s tail freeze** | Wording (no effect, 4 clips identical) · last-frame composition (seeds disagreed: one better, one worse) | Shorten the final shot · a last frame that isn't near the action's end · accept it (~6 % of an 11.5 s clip) |
| **Smile decay compresses to a hold** | Explicit rise→peak→decay wording | Time anchors instead of more facial detail · shorten that shot |
| **Cut lands slightly early** | Logged only | Once several samples agree on the offset, calibrate the written timestamp |

## 4. Criteria that were themselves wrong

Kept as a warning: **the measurement failed more often than the model did.**

| Criterion | Failure | Fix |
| --- | --- | --- |
| Cut detection by counting over-threshold frames | Reported **19 cuts** for one continuous camera move | Detect **isolated narrow spikes** only |
| Tail activity as a pure ratio | Passed a known-bad clip at **0.50** while absolute motion was 1/11 of good | Add an **absolute floor** |
| "Close-up detector" | Reported zero close-ups in footage full of them | **Deleted**, not tuned |
| Thumbnail judgments of "is X present" | Wrong **four times**, both directions | Judge at full resolution |
| Monitor that only matched success | Silent on crash; silence looks like "running" | Match failure signatures too |
| Local pose checks on the last frame | All passed while the overall silhouette read as a finished pose | Judge the **whole composition** |

## 5. Method rules earned here

1. **Calibrate a criterion in both directions before using it**; delete it if it can't separate.
2. **Any ÷median metric: can the denominator collapse?** Two criteria here were fooled that way.
3. **Establish the seed noise floor** before believing any effect.
4. **Two seeds must agree in direction**; disagreement is noise, not a win.
5. **A number crossing a line ≠ better** — it may be satisfied by content the model invented.
6. **Failure must not look like success** — configs, probes, monitors, and self-checks alike.
7. **Verify through the real execution path.** A check that runs a different path proves nothing.
8. **Record negative results**; they define the boundary.
9. **Whoever generated it shouldn't be the only one to accept it.**
