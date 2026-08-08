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
