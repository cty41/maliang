# Little Orange: from one sentence to an adopted sprite

[简体中文](README.zh-CN.md)

A real MaLiang run in Cursor (2026-10-22). The host was `cursor-desktop`
(GenerateImage, model unknown); receipts are `host-agent-attested`, not
machine-observed. Images are kept as delivered, including rejected ones, to show
the decisions rather than a flawless final drawing. The production event store
stays in the private `work/` project; this sample keeps the inputs, records,
prompts, and images.

## 1. The request and intake

The user said only: “请为我画一个 小橙子 agent 的形象 它是一个程序员 他快乐又毒舌”
(draw a Little Orange agent; it is a programmer, happy and sharp-tongued).

The agent announced the MaLiang route, then asked the intake questions one
dimension at a time. [intake.json](intake.json) holds the answers: game assets,
2D, RPG, front view, chibi, line-flat render, dual track (concept art plus
production sprite), classical line concept style, promo first, bright palette,
modern theme. A first intake picked the wrong genre; answered dimensions are
immutable, so a new intake replaced it.

## 2. Concept track

| Concept | Prompt | Image | Human decision |
|---|---|---|---|
| `little-orange-base` | [concept-prompt.txt](concept-prompt.txt) | [concept/base.jpg](concept/base.jpg) | rejected |
| `little-orange-base-v2` | [concept-prompt-v2.txt](concept-prompt-v2.txt) | [concept/base-v2.jpg](concept/base-v2.jpg) | approved |

The v1 revise note, kept in [records/concept-base.json](records/concept-base.json):
the peel was too photoreal, the hoodie was a stereotype, and the body should be
the orange itself with tiny Q-version hands and feet. Those three points became
style rules in [records/concept-style-guide.json](records/concept-style-guide.json)
and the v2 prompt. Concept prompts are not frozen or hashed (a known gap).

From the approved v2, [records/identity-markers.json](records/identity-markers.json)
was frozen: required orange body, tilted leaf cowlick, square glasses with one
glare, chibi hands and feet; optional laptop; palette `#F7931E`, `#4CAF50`,
`#3FD3E0`.

## 3. Production track

[design/family-contract.json](design/family-contract.json) and
[design/draft.json](design/draft.json) compile to
[design/design.json](design/design.json). Its `prompt` is the exact text passed
to GenerateImage; no concept image is a reference input (`imageInputs` is empty).

| Attempt | Image | Result |
|---|---|---|
| `orange-front-001` | [candidates/orange-front-001.jpg](candidates/orange-front-001.jpg) | Painted checkerboard instead of alpha, a fruit logo on the laptop; technical failed, human rejected |
| `orange-front-002` | none | Agent typo in character and provider; recorded as operator error, never sent |
| `orange-front-003` | [candidates/orange-front-003.jpg](candidates/orange-front-003.jpg) | Flat magenta key background, no logo; JPEG without alpha, so technical failed as expected |
| `orange-front-003-sprite` | [candidates/orange-front-003-sprite.png](candidates/orange-front-003-sprite.png) | `derive --operation matte-resize --tolerance 40`, key `#F50696` from the corners; technical passed, human passed with `review-quick`, adopted |

The design shown here is the 003 revision: it adds the `flat-key-background`
rule and prohibits `checkerboard-background` and `brand-logo`. Cursor
GenerateImage has no transparent-background option, so a flat key color plus
deterministic matting is the route to a real alpha channel.

## What this run changed in MaLiang

- `review-quick`: the user only chooses pass or not pass, with optional issues
  and a note; the reviewer and time are filled automatically.
- `preview`: absolute paths and a correctly named viewing copy, because the chat
  could not display images from `work/`.
- The `orange-front-002` typo led to the `--new-character` guard.
