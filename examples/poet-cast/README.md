# Tutorial: prove the pose before generating the sprite

This real project sample examines one Five-red Chow Poet Cast visual moment,
including a cheap stick-figure choice and the later reviewed sprite. Those two
artifacts belong to the same design investigation but are **not a single direct
generation lineage**. The sample demonstrates decisions and strategy changes;
it is not presented as a flawless final drawing.

## 1. Start with the gameplay visual moment

The Draft describes a `down-right` Cast at `action-peak`. The Sprite needs to
read as a compact pre-release focus pose. Release and magic remain VFX
responsibilities rather than being baked into the character image.

## 2. Compare cheap pose options

`draft.json` contains three orange stick-figure options:

- A: one forward guide paw and one chest anchor;
- B: both paws gathered around a compact focus;
- C: a taller raised-paw silhouette.

Render the board and 128 previews before any expensive image-generation call:

```console
maliang-art pose render-options \
  --spec examples/poet-cast/draft.json \
  --output .tmp/poet-cast/options.png \
  --preview-dir .tmp/poet-cast/previews
```

The historical review board is retained in the fixture store for provenance.
Temporary rerenders belong under `.tmp/` and should not become production
Attempts or published artwork records.

## 3. Record the human choice

The human reviewer selected B because its two-paw chest focus, grounded base,
and equipment axis were easier to read. A and C remain rejection summaries;
their full temporary review geometry does not need a production lifecycle.

The selected Action Card lives at:

```text
store/Tools/artworks/poet_five_red_chow/pose-proofs/
  poet_cast_dr_sheathed_focus_v1.json
```

An Action Card records the pose decision. **It is not a visual reference to
send to an image model.** Identity, body volume, equipment form, measurable
composition, and final style still require their own authoritative sources.

### The real branch after B

B described a compact diagonal/mid-body focus and informed an early ImageGen
attempt. Retry feedback discarded that B strategy and its prepared candidate;
the source Attempt record itself remained `prepared`, not `rejected`. The project
then changed strategy: a later human revision used a v07 vertical-guard guide,
and the displayed final sprite was adopted through reviewed-import. The committed
Action Card is a historical backfill of the earlier B decision; it must not be
read as direct authorization or provenance for the later vertical-guard image.
Source records `job-5ceb11280e5973fa-a001`, `feedback-3284abb54c9e7b62`, and
`feedback-addendum-05fce1681fbed9df` preserve that branch decision.

This is a useful production lesson: a valid Pose Proof can close one decision
without guaranteeing that the subsequent generation strategy succeeds. A
strategy change needs its own Composition/Pose Guide and evidence.

## 4. Keep source responsibilities separate

- Idle DR supplies Five-red Chow identity, volume, palette, four-paw topology,
  and the fully sheathed ring-pommel dao relationship.
- Pose Proof supplies timing, force line, weight, contacts, negative space, and
  rough silhouette.
- A Composition/Pose Guide should supply measurable baseline, grips, equipment
  endpoints, occlusion, and safe zones.
- The reviewed final sprite is the production result, not proof that every
  input responsibility was perfectly isolated by the model.

## 5. Read approval honestly

The final Cast DR master and 128 preview were accepted in Wooftactics through a
reviewed-import path. This tutorial does not invent an Invocation or Delivery
that did not occur. The accepted sprite also retains known deviations: long
front limbs, a staff-like floor contact, imperfect grip placement, and some
identity drift.

That distinction is intentional:

- `examples/poet-cast/` teaches a real human-in-the-loop pose and review case;
- `examples/synthetic/` demonstrates a complete provider-neutral lifecycle
  without pretending synthetic records came from this artwork session.

## Licensing

See `ATTRIBUTION.md` and `assets.json`. The sample is CC BY 4.0; MaLiang code is
MIT.
