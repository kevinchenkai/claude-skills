# T2VA Source-Prompt Intake

Use for text-only work. No generated keyframes, placeholder images, endpoint comparisons, or
Picture-alignment line are needed. A picture mentioned as a scene object is not a conditioning file.

| Input | Treatment |
| --- | --- |
| Already canonical | Validate; preserve byte-for-byte unless optimization was requested |
| Detailed prose | Extract hard requirements, then normalize using [prompt_authoring.md](prompt_authoring.md) |
| Short brief | Expand into a visible/audible timeline; disclose material creative choices |

Retain the source and final prompts separately, with hashes for production. Preserve named
subjects/objects, exclusions, shot/cut constraints, and every character and punctuation mark of
dialogue, lyrics, and visible text. Write rewritten descriptive prose in English without
translating those exact strings.

## Resolve contradictions visibly

Compare stated shot count with timed blocks, requested duration with the timeline end, and aspect
ratio with legal output dimensions. Record discrepancies and their resolution before submission.
Prefer a specific timeline over an approximate summary count when defensible, but disclose the
choice; ask when the ambiguity materially changes the required result. Never silently drop a shot.

Historical example: “seven shots, roughly 12 seconds” accompanied eight blocks ending at 14s.
Following the timeline and dropping a block produce different videos; neither is an invisible edit.

Before production, map each hard requirement to its shot/time and evidence method. Review identity,
wardrobe, objects, and spatial continuity across cuts because no endpoint images anchor them.
The common acceptance workflow owns the full matrix and status rules.
