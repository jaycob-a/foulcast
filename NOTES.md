# NOTES — Step 3: straight-back fouls and volume calibration

Date: 2026-08-07. Branch `step-3`. Follows the P1 section-matching fix recorded in
`BEFORE.md` / `AFTER.md`.

---

## What was actually wrong

`AUDIT.md` P2 called this a 4x shortfall in absolute foul counts. Two separate
things were tangled up in that number.

**1. The spray model could not produce a backward foul.** `estimate_spray_angle()`
clamped every launch direction to 0-85 degrees off the foul line, and
`simulate_foul_ball()` clamped it again. Nothing ever crossed behind the plane of
home plate: across 3,350 simulated fouls the maximum landing angle was 85.0
degrees and the count above 90 was exactly zero. Foul tips, nicks off the edge of
the bat and swings late enough to deflect the ball back over the catcher — a
large share of every game's fouls, and the reason there is a screen back there —
had no representation at all. The seats behind the plate consequently ranked
*last* in the model, which is close to the opposite of the truth.

**2. Half a game was being read as a whole game.** `predict_game_fouls()` takes
one lineup. `webapp_v2.py` calls it twice and sums, which is what a game is. The
~16.6 figure was one lineup; the full game was already 32.7. So the residual
volume gap after the P1 fix was a units error, not a physics error. This is now
pinned down by `test_each_half_is_about_half_the_game` and a note in the
`predict_game_fouls` docstring, so it cannot be misread again.

The volume was therefore *not* fixed by scaling anything. No multiplier was
added, `fouls_per_pa` was not touched, and `plate_appearances_per_batter` is
still 4.0.

---

## What changed

All in `foulball/trajectory.py`.

**A second spray mode.** Spray angle in this codebase is measured from the foul
line of whichever side the ball went to. The two foul lines are 90 degrees apart,
so each side owns 135 degrees of foul territory: 0 is down the line, 90 is square
to it, and `BEHIND_PLATE_ANGLE = 135` is dead behind the catcher, where the two
sides meet. `simulate_foul_ball()` now draws a mode before anything else:

- `back_foul_probability()` — how likely this contact was a deflection rather
  than a drive. Raised for steep launch (caught the underside or edge), weak
  contact, and breaking pitches; cut for choppers and hard line drives, which are
  squared up and go out in front. Base rate `BACK_FOUL_BASE_RATE = 0.28`.
- `estimate_back_spray_angle()` — draws an offset off dead-back toward the near
  foul line, so density peaks straight back and thins toward the corners of the
  backstop. Mirrored across the two sides by the caller's side draw, that fills
  the wedge real backward fouls fill.
- Pull tendency is compressed toward 50/50 on backward fouls. A deflected ball
  barely knows which way the bat was going, so the backstop fills near-evenly
  rather than following the batter's pull side.

**Glancing-contact speed penalty.** `oblique_contact_speed_factor()` scales exit
velocity from 0.85 (square to the plate) to 0.58 (dead back), and is exactly 1.0
for anything hit in front. Without it a sampled 95 mph became a foul carrying 300
ft straight back out of the stadium — 190 such events per half-game in the first
cut. The justification is that the batter profiles are built from Statcast-tracked
fouls, and tracking is at its worst on precisely the balls that vanish into the
backstop screen, so the sampled speed is drawn from a population of squarer
contact than this branch represents.

`TrajectoryResult` gained an `exit_velocity` field carrying the speed the ball
actually left the bat at, and `matchup_engine` records that on the event instead
of the raw sample, so section EV averages and danger ratings reflect the real
number.

`stadium.py` and the section geometry were **not** touched. The existing
`angle > 90 -> sections reaching the backstop` rule in `exposed_bands()` routed
the new backward fouls correctly with no change.

Also fixed in passing: `--regen-golden` never worked. `pytest_addoption` was
declared in `tests/test_golden_games.py`, and pytest only reads it from the
rootdir conftest, so the documented regeneration command failed with
"unrecognized arguments". Moved to `conftest.py`.

---

## Before and after

Yankee Stadium, Red Sox at Yankees, both lineups, league-average RHP mix, seed 42,
400 sims/batter. This is a full game — what `webapp_v2` reports.

| Section | Before | After | Rank before → after |
|---|---:|---:|---|
| `HOME-F` Behind Plate Field (119-121) | 0.52 | **6.72** | 13 → **1** |
| `HOME-B` Behind Plate Main (218-222) | 0.56 | **4.00** | 11 → **2** |
| `1B-LR` 1B Lower Reserve (205-210) | 4.08 | 2.95 | 2 → 3 |
| `3B-LR` 3B Lower Reserve (229-234) | 4.11 | 2.88 | 1 → 4 |
| `1B-DUG` 1B Dugout Box (109-114) | 3.69 | 2.57 | 3 → 5 |
| `3B-DUG` 3B Dugout Box (126-131) | 3.69 | 2.48 | 4 → 6 |
| `1B-FB1` 1B Field MVP (115-118) | 3.19 | 2.24 | 6 → 7 |
| `1B-LB1` 1B Main Level (211-217) | 3.17 | 2.19 | 7 → 8 |
| `3B-FB1` 3B Field MVP (122-125) | 3.34 | 2.02 | 5 → 9 |
| `3B-LB1` 3B Main Level (223-228) | 2.94 | 1.95 | 8 → 10 |
| `1B-UB` 1B Upper (307-316) | 1.60 | 1.18 | 9 → 11 |
| `3B-UB` 3B Upper (324-331) | 1.44 | 1.03 | 10 → 12 |
| `HOME-G` Behind Plate Grandstand (419-421) | 0.23 | 0.75 | 14 → 13 |
| `HOME-U` Behind Plate Terrace (317-323) | 0.10 | 0.06 | 12 → 14 |
| **Total into stands** | **32.66** | **33.02** | |

By group:

| Group | Before | After |
|---|---:|---:|
| Behind home (4 zones) | 1.41 (4.3%) | **11.53 (34.9%)** |
| Lower bowl (8 zones) | 28.21 (86.4%) | 19.28 (58.4%) |
| Upper down the lines (2 zones) | 3.04 (9.3%) | 2.21 (6.7%) |
| 1B side / 3B side | 15.73 / 15.52 | 11.13 / 10.36 |

Landing direction, one lineup, ~3,340 simulated fouls (0 = down the line, 90 =
square to the plate, 135 = dead behind the catcher):

| Angle band | Before | After |
|---|---:|---:|
| 0-15 | 22.8% | 17.0% |
| 15-30 | 32.7% | 24.0% |
| 30-45 | 29.2% | 22.3% |
| 45-60 | 12.4% | 8.8% |
| 60-90 | 2.9% | 1.8% |
| 90-135 (behind the plate) | **0.0%** | **26.1%** |
| max angle observed | 85.0 | 135.0 |

The total barely moved (32.66 → 33.02) — it was already inside the 30-40 band
once counted per game rather than per lineup. What moved is the shape. On the
`yanks_vs_cole_yankee` golden game, mean landing distance dropped from 154.4 ft
to 131.0 ft, because backward fouls come off the bat slower and come down nearer
the plate.

Stability: across all 30 parks the full-game total runs 22.7 to 34.1, mean 32.7.
Across six seeds at Yankee Stadium, 32.3 to 33.0. Behind-home ranks first or
second in every park.

---

## Tests

`tests/test_plausibility.py`
- `test_total_fouls_into_stands_in_realistic_range` — **fails outside 25-45** on a
  full game, as asked. Currently 33.0.
- `test_each_half_is_about_half_the_game` — guards the units error above.
- `test_behind_home_is_the_busiest_group`, `test_a_behind_home_section_ranks_in_the_top_three`
  — replace the old group-level behind-home assertions, which were deliberately
  weak because the straight-back wedge was empty.

`tests/test_distributions.py`
- `TestStraightBackFouls` — three tests: a fifth to a third of fouls must land
  behind the plate, they must spread across the wedge peaking dead-back and never
  cross into the other side's territory, and pull tendency must wash out on
  deflections (checked per handedness, since a mixed lineup's cancels in
  aggregate).
- `test_back_fouls_come_off_the_bat_slower` — the glancing-contact penalty.
- `test_ev_sampler_matches_profile` / `test_forward_foul_ev_mean_near_profile` —
  split from the old single EV test, which compared post-contact speed against
  the profile mean and would now fail for the right reason.

Golden baselines relocked. 425 tests pass.

---

## What still needs fixing

**1. The back-foul rate is a guess.** `BACK_FOUL_BASE_RATE = 0.28` is the single
biggest unvalidated number in the model. Statcast cannot supply it: its `foul_tip`
event only counts tips the catcher holds, and everything that flies into the
screen is logged as a plain `foul` with no direction. 0.28 was chosen because it
puts a game in the 30-40 band with the behind-home group on top; that is a
consistency argument, not evidence. The Step 8 logging feature is what would turn
it into a measured quantity, and it should be the first thing calibrated when
real landing data exists.

**2. There is no netting.** `HOME-F` spans 50-90 ft behind the plate at 0-15 ft
high, which at Yankee Stadium is entirely behind the backstop screen. The model
counts a ball arriving there as reaching the seats. That is why it is now the
top-ranked section at 20% of a half-game. Until Step 9 lands, behind-home numbers
should be read as "balls that come at these seats", not "balls a fan could
catch", and the UI should not describe them as souvenirs.

**3. Behind-home zone geometry is too coarse.** At angles past 90, Yankee Stadium
offers only three bands — `HOME-F` 50-90 ft, `HOME-B` 90-120, `HOME-G` 120-140 —
so `HOME-F` absorbs everything that lands in a 40-foot-deep ring. Subdividing the
backstop zones would spread that concentration and is cheap to do.

**4. Two parks fall outside the band.** `oakland_coliseum` 22.7 and `fenway_park`
28.1, against a 30-park mean of 32.7. Both look like zone-geometry gaps rather
than physics — Oakland also sends 30% of its fouls to the upper deck, which is
not credible. Step 7 covers this.

**5. Deep fouls have nowhere to land.** 137 events per half-game come down past
300 ft and match nothing, because no park models the outfield foul-corner
sections near the poles. Those balls currently vanish.

**6. Absolute volume is still only checked against a league-wide expectation.**
30-40 per game is a number from `PITCH.md`, not from a backtest. Step 6 is what
would make the total an evidence-backed figure rather than a plausible one.

**7. Nothing here validates section-level accuracy.** Backward fouls now exist and
land somewhere sensible, and the rankings are no longer inverted or empty behind
the plate. Whether the specific split between `HOME-F` and `HOME-B` is right is
unknown and unknowable from public data. That remains the moat described in
`AUDIT.md`, and it still needs Step 8.

**8. The section geometry itself is estimated — added 2026-08-09, and it
outranks everything above it.** Items 1-7 treat `stadium.py` as the fixed
reference every other number is measured against. It is not one. All 31 parks'
seat boundaries are analogues off a shared template, not surveyed or digitized
from seating charts. The provenance trace is recorded in the module docstring
of `foulball/stadium.py`; the short version is that 2,064 geometry values
across 31 parks are drawn from 62 distinct values, four parks are byte-identical
to each other, and every park is exactly mirror-symmetric to the last decimal.

Three things above need re-reading in that light:

- Item 3 calls the behind-home zones "too coarse." They are, but subdividing
  invented bands produces finer invented bands. That fix raises resolution,
  not accuracy.
- Item 4 attributes the Oakland and Fenway outliers to "zone-geometry gaps
  rather than physics." That is right, and now has a cause: those two parks
  have the coarsest tables in the file. Fenway's numbers also pass through a
  blanket 0.85 distance multiplier that exists to make deck matching behave.
- The 30-park mean of 32.7 in the stability check is a mean over one template,
  not over 30 parks. It should not be read as evidence that the geometry
  generalizes.

`SOURCED_DATA.md` records why this is not a quick fix: no public source
publishes distance-from-home-plate or angle-off-the-foul-line for any stadium
section. This is a data-acquisition problem, not a modelling one, and it is
upstream of Step 8 — hand-logged fouls with real section labels cannot
calibrate section geometry that was never measured.

**9. The logging feature exists now — added 2026-08-09.** `step-8` ships
`/log`, `foulball/foul_log.py` and `calibrate_log.py`. Details in
`NOTES_STEP8.md`. What this changes for the items above:

- Items 1 and 7 name Step 8 as the thing that would settle the back-foul rate
  and section-level accuracy. The mechanism is now built, but the log is
  empty. Nothing is settled until observations are in it, and the season ends
  2026-09-27.
- Item 8's last paragraph stands unchanged and is the reason the schema stores
  printed section numbers rather than zone IDs. Logging still cannot calibrate
  geometry that was never measured. What it can do is bank observations keyed
  to something that survives a boundary re-cut, so they are still usable when
  real seating geometry turns up.
- Item 2 (no netting) now has a data field ahead of the model: entries record
  whether a ball hit the netting, but the model still assigns those balls to
  the zone behind the net. Netting comparisons are not meaningful until Step 9.

**10. The section geometry is now sourced in depth — added 2026-08-10. Item 8
is out of date and this replaces its numbers.** Item 8's evidence was that
2,064 geometry values across 31 parks came from 62 distinct values, that four
parks were byte-identical, and that every park was exactly mirror-symmetric.
Step 9 changed the first two on purpose. It deliberately did not change the
third.

What is true now:

- 2,064 geometry values draw on **452 distinct numbers**: 418 distances, 15
  angles, 19 heights. The distances are no longer invented — each park's bands
  are positioned by its published foul-territory area, its backstop distance
  and its deck-overhang percentages, every figure cited in `PARK_PARAMS.md`.
- **No two parks are byte-identical.** 31 parks, 31 distinct geometry
  signatures, where there were 27. Busch/Kauffman/Nationals/Rate and Great
  American/Petco all separate.
- **The angles and heights did not move, and every park is still exactly
  mirror-symmetric to the last decimal.** No source publishes a foul-territory
  split by side, a behind-plate-vs-down-the-line split, or a deck elevation in
  feet, so nothing was invented to fill those. `HOME-F` still spans 55-90
  degrees at all 31 parks.

So item 8's headline holds and its arithmetic does not. The bowls are placed;
the bowls are not shaped. That is the half that still needs a survey, and
`SOURCED_DATA.md` still records why no public source closes it.

Re-reading item 8's three sub-points in that light:

- Its remark that Fenway's numbers "pass through a blanket 0.85 distance
  multiplier that exists to make deck matching behave" is **fixed**. That
  multiplier and Wrigley's 0.88 are gone, replaced by sourced scales (Fenway
  0.889 from an 18,100 sq ft foul area, the smallest in MLB).
- Its remark that the behind-home zones are "too coarse" stands, but the front
  of them is no longer arbitrary: it is pinned to the park's own backstop.
- Its warning about reading a fleet mean as evidence of generalization
  stands unchanged, and the sweep below is the reason.

**11. What the re-run sweep says — 2026-08-10.** 31 parks, standard lineup,
seed 42, 400 sims/batter, both lineups summed.

| | fouls into stands |
|---|---:|
| median (31 parks) | **31.4** |
| 27 parks fall between | 30.1 and 33.1 |
| Target Field | 25.2 |
| Wrigley Field | 24.1 |
| Sutter Health Park | 22.1 |
| Las Vegas Ballpark | 20.4 |

Against Step 7's template run, which had 28 parks inside 1.7 fouls: the main
group is now 27 parks inside **3.0** fouls, and the outlier set has grown from
three to four. That is a real widening and it is still nowhere near enough.
Sixty feet of sourced bowl depth moves a park's total by about three fouls a
game, because the behind-plate group dominates the count and is still shaped
identically at every park. The volume model's dynamic range problem from
Step 6 (`r = -0.045`) is untouched by any of this.

Two of the four low outliers are new, and both are the model being right
rather than the model breaking:

- **Wrigley (32.7 → 24.1)** and **Target Field (30.8 → 25.2)** carry the
  heaviest published deck cover in the fleet (Wrigley 55%/100%, Target
  35%/75%). Their covered decks now genuinely own no exposed ground, so fouls
  that would have landed there match nothing. The model has no roof surface to
  hand those balls to — it loses them. Wrigley's unmatched share goes 36% →
  52% on that account.
- The **six roofed parks moved the other way** (Tropicana, loanDepot, Daikin,
  Chase, American Family, Rogers, +0.3 to +0.8 each), because their 93-100%
  is dome shade from 150+ ft up and is now discarded rather than capped at
  60%. Their upper decks are reachable again.

Decomposing the change at the two parks that moved most, holding everything
else fixed:

| | Wrigley | Target |
|---|---:|---:|
| Step 9 baseline | 32.7 | 30.8 |
| + roof/canopy classification, cap removed | −0.5 | −0.6 |
| + decks resolved front to back | **−7.7** | **−4.7** |
| + backstop anchor | −0.4 | −0.3 |

The ordering fix dominates, and it was not the requested change — it became
necessary once the cap came off. Measuring every deck's depth against the
un-overhung bowl credited an upper deck with the wrong footprint, and the
error was largest exactly where the cover was heaviest: at 100% the deck kept
whatever the lower deck's retreat handed it, so a fully roofed deck stayed
reachable and "apply Wrigley's canopy" would have been a no-op. Resolving
decks front to back is what makes the published percentage mean what Clem
says it means.

The backstop anchor costs 0.2 to 1.1 fouls a game at every park and raises the
fleet-median unmatched share from 37% to 38%. That is the intended sign: it
opens a real annulus of foul ground between the plate and the front row, and
short backward fouls that die in it now match nothing instead of being caught
by seats that could not exist there.

Five parks carry flags, against two before. Three are the outlier/unmatched
pairs above plus Sutter and Las Vegas. The fifth is new and is a finding about
the section table rather than the parameters: **Yankee Stadium's `1B-UR` now
receives nothing and `3B-UR` almost nothing.** Upper Reserve survives only as a
9-foot sliver in the 35-40 degree wedge, hidden everywhere else beneath Upper
Box and Lower Reserve. That was always true of the table; deepening the bowl
made it visible.

Unchanged, and worth stating because it is the clearest evidence the shape did
not move: the 1B share of sided fouls spans **0.66 pp** across all 31 parks
(51.56% to 52.22%) against a seed-to-seed sampling band of **1.11 pp**. Park
geometry still contributes nothing measurable to the left/right split, exactly
as mirror-symmetric geometry must.

**12. The backstop anchor now clears the fence — added 2026-08-10.** Item 11
described the anchor as pinning the behind-plate front row *onto* the backstop
distance. That was a contradiction with this repo's own source analysis and it
is fixed.

`PARK_PARAMS.md` §2 records that Clem defines his backstop figure as *"the
distance from home plate to the fence in the rear"*, and the model adopts Clem
at 30 of 31 parks. Pinning the first row of seats onto that number therefore
asserted that Clem measures to the seating bowl — the opposite of what the
source says, and it put the seats inside the fence. The anchor now targets
`backstop_ft + _SEAT_SETBACK_FT`.

**The setback is 1.0 ft, and the reasoning is in the sources rather than in
taste.** Seamheads defines its own backstop differently — *"Distance from Home
Plate to Stands"* — so Seamheads minus Clem is a direct measurement of the
fence-to-stands gap wherever both publish:

| | |
|---|---:|
| Parks where both publish | 30 |
| Agreeing to the foot (no gap at all) | **21** |
| Mean difference | **+0.40 ft** |
| Median difference | 0 ft |
| Disagreements, positive / negative | 6 / 3 |

Three of the nine disagreements are *negative* — Comerica and loanDepot both
put the stands 3 ft nearer than the fence — which no reference-point offset
can produce. Those are the source conflicts §2.1 already catalogues, not a
definitional step. So the real gap is below the resolution either source
publishes at, and 1 ft is the smallest increment they could have expressed,
rounding the observed +0.40 ft mean up rather than down.

**It is nearly inert, and that is the finding.** Re-running the sweep, no park
moves by more than 0.1 fouls a game; the median stays 31.4, the 27-park main
band goes 30.1-33.2 to 30.1-33.1, and the flag set is unchanged. The five
golden games move by +1, +7, +5, +3 and +5 unmatched fouls out of ~2,490. The
contradiction in gap 7 was real but it was definitional: the anchor had the
right magnitude and the wrong reference point, and correcting the reference
point costs almost nothing.

What is still open is the *variation*. A park with a photographers' well behind
the plate has metres of setback; a park with dugout-club seats against the wall
has almost none. Nothing published distinguishes them, so the 1 ft is uniform
across all 31 parks and should be read as fixing the sign of the error rather
than its size.
