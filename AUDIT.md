# FoulCast — Code & Approach Audit

Date: 2026-08-07
Scope: full repo read + dependency install + test run + live smoke test of the prediction engine.

---

## Verdict: CONTINUE. Do not restart.

The codebase is in materially better shape than a typical AI-assisted prototype. It is worth
keeping and fixing, not rebuilding.

**Evidence it's healthy:**

- 11,354 lines of Python, cleanly separated into a `foulball/` package (trajectory, stadium,
  matchup engine, batter profiles, MLB API, validators) plus research scripts and a web app.
- Dependencies still install cleanly on Python 3.13 with no version conflicts.
- **408 tests pass.** There is a real test suite with golden-game fixtures, guardrails,
  distribution checks, and endpoint tests.
- There is a `validators.py` module doing runtime sanity checks on trajectories and samples.
- Deployment is already configured and coherent: Dockerfile, `railway.json`, `railway.toml`,
  gunicorn start command, healthcheck path. All three agree on `webapp_v2:app` port 8080.
- The engine runs end-to-end offline. A synthetic 9-batter lineup at Yankee Stadium produces
  ranked sections with bootstrap confidence intervals.
- `PITCH.md` contains an honest Known Limitations section. That is rare and it is an asset.

Rebuilding this would destroy months of work to re-derive the same architecture.

---

## The three real problems

Ranked by how much they threaten the product. Fix in this order.

### P1 — Section matching is physically wrong (CRITICAL)

**Where:** `foulball/matchup_engine.py`, the candidate loop around lines 250–270.

**What it does now:** for each candidate section, it takes the section's *mid-distance*, finds
the point on the trajectory closest to that horizontal distance, reads the ball's *altitude at
that moment*, and assigns the ball to the section if that altitude falls inside the section's
height band. First match wins (`break`).

**Why that's wrong:** it tests where the ball *was in flight*, not where it *came down*. A high
fly ball heading for the lower bowl passes through 35–80 ft of altitude on its way. The upper
deck band claims it.

**Confirming symptom:** at Yankee Stadium the top two predicted sections are `3B Upper` and
`1B Upper` — the upper decks. In reality upper decks down the lines receive relatively few
foul balls; the lower bowl and the area behind home plate receive most of them. The model is
inverted.

**Compounding issue — overlapping bands.** Section geometry is defined as independent
distance/angle/height ranges that overlap heavily:

```
1B-UB   1B  upper   dist  40-250   ang 10-55   ht 35-80
1B-UR   1B  upper   dist 130-250   ang 10-40   ht 40-80
1B-LB1  1B  lower   dist  30-180   ang 15-45   ht 10-35
```

`1B-UB` spans 40–250 ft and overlaps nearly every other 1B section. Because matching is
first-match-wins over an unordered list, assignment depends on list order, not geometry.

**Fix direction:** model each section as a physical surface (a distance/angle footprint at a
given deck height) and find where the trajectory actually *intersects* it, or where it lands.
Then pick the nearest matching section rather than the first. Make the section set a partition
that does not overlap.

### P2 — Absolute foul counts are off by roughly 4x

Summed across all 16 Yankee Stadium zones, the model predicts **8.5 fouls into the stands per
game**. `PITCH.md` itself states the real figure is 30–40. Many simulated balls match no
section at all and vanish.

This is partly downstream of P1 — fix the geometry and more balls will land somewhere. But the
per-batter weighting (`fouls_per_pa * PA / sims`) also needs recalibration against a known
total. Until this is right, only *relative* section rankings mean anything, and any absolute
number shown in the UI is misleading.

### P3 — The headline validation number does not validate the product

**Where:** `backtest.py`.

**What it measures:** it simulates each real Statcast foul with `spray_angle_deg=0` and
correlates the resulting distance against Statcast's `hit_distance_sc`.

**Why r=0.986 is not meaningful:** both sides of that comparison are functions of the same two
inputs (exit velocity and launch angle), and `hit_distance_sc` is itself substantially a
model output rather than a raw measurement. The correlation mostly demonstrates that this drag
model agrees with MLB's drag model given identical inputs. High correlation was close to
guaranteed. It says nothing about which *section* a ball lands in — which is the product.

**A separate, worse problem in the same file** (and in `04_spray_angle_research.py`, Approach 2):

```python
ratio = actual_dist / pred_dist
spray_angle = np.degrees(np.arccos(ratio))
```

This assumes a foul travels a shorter radial distance *because* it went sideways. That is not
how the geometry works — in an unobstructed flat model, radial distance from home plate is
essentially invariant to spray angle. The shortfall is caused by mishits and by the ball
hitting stands, netting, or structure. So this computes model error and mislabels it as spray
angle.

**Mitigating fact:** this back-solve was **removed** from the production path.
`rebuild_spray_profiles.py` says so explicitly, and the live `.cache/spray_profiles.json`
contains only `fair_pull_pct`, `fouls_per_pa`, and EV/LA moments — no arccos-derived values.
The flawed method is confined to research scripts. **Delete those code paths** so they can
never be cited or reused.

---

## Secondary issues

| Issue | Detail | Effort |
|---|---|---|
| Stale player data | `spray_profiles.json` is from Jun–Aug **2024**. It is now Aug 2026. Sample lineups return Charlie Blackmon, David Peralta, Justin Turner, Martín Maldonado — largely retired. | Re-run `rebuild_spray_profiles.py` on 2025–26 data |
| Stale venues | Registry maps `oakland_coliseum` → Sutter Health Park and `minute_maid` → Daikin Park (good), but `tropicana_field` needs review after the Rays' relocation, and key order should be refreshed. | 1 hour |
| Dead code | `webapp.py` (616 lines) is superseded by `webapp_v2.py`. Nothing deploys it. | Delete |
| Tests don't test physics | 408 passing tests check internal consistency and guardrails, not physical plausibility. None caught P1. | Add a "lower bowl > upper deck" style plausibility test |
| Pitch overstates granularity | `PITCH.md` implies per-section precision. Reality is **16 broad zones** per park (e.g. "3B Upper, Sec 324–331", 600 seats). All 30 parks have hand-built zone geometry — more than the pitch claims — but at zone, not seat, resolution. | Rewrite pitch |

---

## What "ready to sell" actually requires

The current pitch targets $50K–$200K B2B licences to ticket platforms. The first question any
buyer asks is section-level accuracy. Today there is no answer, and P1 means the current
answer would be wrong.

**The missing asset is ground truth.** There is no public database of foul ball landing
locations — FiveThirtyEight had to hand-log 906 of them for a single story. Statcast does not
record which side a foul lands on. Nobody has this data.

That is the moat. A few thousand hand-logged or crowdsourced fouls with real section labels
would let you calibrate the model, validate it honestly, and own something no competitor can
replicate from public sources. It converts the project from "a simulation that might be right"
into "the only validated dataset in existence."

---

## Work plan

**Phase 1 — Correctness (do not skip, do not reorder)**
1. Rewrite section matching as true landing-point intersection; make zones non-overlapping.
2. Add plausibility tests that would have caught the inversion.
3. Recalibrate so total fouls-into-stands lands in the 30–40 range.
4. Refresh spray profiles to 2025–26 data.
5. Delete `webapp.py` and the arccos back-solve code paths.

**Phase 2 — Ship**
6. Deploy `webapp_v2` to Railway. Config is already correct.
7. Rewrite `PITCH.md`: drop r=0.986, describe zone-level output honestly, state what is and
   isn't validated.

**Phase 3 — Validate**
8. Build foul ball logging (self-logged from broadcasts, or crowdsourced in-app).
9. Calibrate against it. *Then* the accuracy claim is real and the B2B conversation is possible.

**Do not** map more stadiums until Phase 1 is done. That work only pays off once the matching
logic is correct.
