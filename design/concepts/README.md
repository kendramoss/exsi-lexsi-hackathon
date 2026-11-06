# Design concepts (not yet applied to `demo/`)

Three desktop sample screens (1440px) for a redesign of the demo, with **mock data**. Open the `.html` files directly, or look at the `.png` screenshots.

| Screen | File |
|---|---|
| Landing + step 1 (base model caves) | `1-landing.html` / `.png` |
| Step 2 (response) + case inspector | `2-inspect.html` / `.png` |
| Step 3 (outcome / scoreboard) | `3-outcome.html` / `.png` |

Direction: a calm sky gradient and two-tone serif paragraphs, an editorial serif headline with app-window cards and black pill CTAs, and a blueprint grid with annotation pins, a handwritten accent and a spec-style inspector panel. Fonts: Fraunces, Geist, Geist Mono and Caveat (Google Fonts).

## Type scale

Every text style comes from these tokens in `concepts.css`. No other sizes or weights are used.

| Token | Style | Used for |
|---|---|---|
| `--t-display` | Fraunces 400, 64/1.04 | page headlines (italic for the second clause) |
| `--t-lead` | Fraunces 400, 28/1.3 | lead paragraphs |
| `--t-title` | Fraunces 400, 24/1.25 | window and card titles, big numbers |
| `--t-body-lg` | Geist 400, 18/1.5 | hero subtitle |
| `--t-body` | Geist 400, 15/1.5 | messages, running text |
| `--t-strong` | Geist 600, 15/1.3 | logo, row names, key values |
| `--t-ui` | Geist 500, 14 | nav, buttons, tabs, selects, pins |
| `--t-small` | Geist 400, 13/1.45 | chips, captions, table and inspector rows |
| `--t-label` | Geist 600, 11, uppercase, +.08em | all small caps labels |
| `--t-mono` | Geist Mono 500, 12 | IDs, file paths, citations |
| `--t-hand` | Caveat 600, 28 | handwritten annotations |
