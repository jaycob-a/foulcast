# NOTES — Step 27: four accuracy questions from the audit

Date: 2026-10-20. Branch `step-27`. Follows `LIMITATIONS.md` (the cold audit)
and Step 26.

This step is about whether the model's numbers are computed the way the
model says they are. Four claims from the audit were investigated before
anything was changed. Two were right and are fixed (the Magnus force pointed
the wrong way; catchability read the ball's speed at the ground rather than
at the seat). One was right about the inputs and is fixed by replacing them
(the hand-typed 2024 lineups). One was a reasonable reading of a docstring
that turns out to be wrong about what the code is doing (the deck-overlap
rule), and it is left alone, with the evidence below.

---

## 1. Deck overlap — `exposed_bands` gives overlapping ground to the lowest deck

**The claim.** A ball descending from above would hit the upper deck first,
so letting the lowest deck own ground that two decks' footprints both cover
is backwards for most fouls.

**What the overlap is.** It is not an overhang. In every park's section table
the upper decks are drawn as rectangles that cover almost the whole bowl:
Yankee Stadium's `1B-UB` runs 40-250 ft from the plate at 35-80 ft up, over a
main level that runs 30-180 ft. Measured across every angle at every park,
ground covered by a higher deck's raw footprint is 100-200% of the ground the
lower decks own (it exceeds 100% where two upper decks overlap the same
lower deck). An upper deck whose front edge really sat 40 ft from the plate
at 35 ft up, 10 ft behind the first row, would be a wall, not a grandstand.
The footprints are the template's way of saying "this deck exists behind
that one", and `exposed_bands` turns them into the stair the heights
describe: each deck starts where the one in front of it ends, at the height
where the one in front of it ends. Decks in the template meet with no
vertical gap (the lower deck's `height_max` is the upper deck's
`height_min` at every pair), so there is no facade for a ball to pass under.

**What a real overhang does in this model.** The published lower-deck cover
percentage (Clem) is applied separately, in `_sourced_bands` step 3: it
pulls the lower deck's rear forward by that share of its depth, and the
upper deck's band begins where the lower deck now ends. A ball descending
over that ground is credited to the upper deck, which is what the audit
asks for. A ball flat enough to come in under the upper deck's front edge
is found by `find_landing_contact`'s dive test and credited to the deck in
front — the same section whose covered rows it would have reached.

**What flipping the rule does.** Letting the highest deck own the overlap
(sorting `_deck_mid_height` the other way) was run as a full site game at
all 31 parks:

| | current | flipped |
|---|---|---|
| median upper-deck share of fouls reaching seats | 17% | 94% |
| parks where upper decks take every seated foul | 0 | 9 |
| Yankee Stadium upper share | 9% | 88% |
| Fenway Park upper share | 10% | 69% |

That is the P1 inversion `tests/test_plausibility.py` was written to kill,
and it contradicts the one external fact this project has about where fouls
go (FiveThirtyEight's 906 observed fouls, overwhelmingly in the lower
zones). The rule is not backwards; the docstring's "a ball cannot come
straight down onto an upper deck at a horizontal position where a lower deck
sits beneath it" describes the template's stair, not a physical overhang.

**What is still imperfect, and left.** Pulling a lower deck's rear forward
also re-slopes the deck, so its last exposed row meets the upper deck's
front edge exactly and the covered rows have no surface of their own. A
flat ball that would in reality pass under the front edge and land on the
covered rows is credited to the right section (the deck in front) but at
the wrong depth, and the opening it passes through is slightly too small.
Counted at three parks with the lower deck's original slope restored, such
balls are 0.4 a game at Yankee Stadium (20% cover), 1.1 at Fenway (40%) and
1.3 at Wrigley (55%), 1-6% of seated fouls, and none of them is currently
being credited to an upper deck. Modelling the opening properly needs the
height of each upper deck's front edge above the rows beneath it, which no
source publishes.

**Change:** none to the rule. `find_landing_section` now has a sibling,
`find_landing_contact`, that also returns *where along the flight* the ball
met the deck, for item 4.

---

## 2. Magnus force — the comment says perpendicular, the code is not

**The claim is right.** `simulate_trajectory` added
`magnus_factor * spin_factor * speed * backspin_frac` to the vertical
acceleration and `... * sidespin_frac` to the lateral one, at every step,
whatever direction the ball was moving. That is a fixed upward lift and a
fixed push toward the stands, not a force perpendicular to the velocity: on
the way up it should lean backward, on the way down forward, and on a steep
pop-up it should be mostly horizontal.

**Fix.** The spin axis is now built once at contact — backspin about the
horizontal axis perpendicular to the launch direction, sidespin about the
vertical — and held fixed in space (a spinning ball is a gyroscope). The
acceleration is `magnus_factor * r * (omega x v)`, perpendicular to the
velocity at every step by construction. For pure backspin the magnitude is
unchanged from before, so the lift coefficient and spin model are as they
were; only the direction moved. For sidespin about the vertical the lateral
force now scales with horizontal speed, so a near-vertical pop-up is no
longer pushed sideways.

**Effect on landing distance.** Every ball lands slightly shorter, because
lift with a horizontal component is a little less lift and a little more
drag on the way up. On a grid of forward fouls the shift is 0 to -6.5 ft,
largest for hard contact at 40 degrees, under 2% everywhere. Over 6,000
tracked 2025-26 fouls from the cached Statcast pull the mean shift is
-1.6 ft (never more than 8 ft on one ball) and the match to Statcast's own
`hit_distance_sc` improves slightly:

| | bias | MAE | RMSE | r |
|---|---|---|---|---|
| before | +16.7 ft | 20.1 ft | 27.1 ft | 0.9689 |
| after | +15.1 ft | 18.8 ft | 25.8 ft | 0.9691 |

The golden games moved by 0.9-1.0 ft in mean distance and 6-9 fewer balls
(of ~2,500) carrying past the last deck. Relocked with a note.

**A finding not acted on.** The lift coefficient is small: `Cl = 0.18 x S`
gives `Cl ≈ 0.03` for a typical fly ball where the literature puts it at
0.15-0.25. The model is a low-lift, high-drag fit to Statcast distance; the
+15 ft bias above suggests the pair was never tuned jointly. Raising lift
would need drag retuned against the same data and is a separate step.

---

## 3. Batter inputs — hand-typed 2024 Yankees and Red Sox, pull left at 50%

**The claim is right**, and `LIMITATIONS.md` 2.4 has the detail. The
eighteen profiles in `batter_profiles.py` were typed, cannot be regenerated,
ran a fifth above the computed foul rates, and every one carried the
`fair_pull_pct` default, so the spray model's pull term was inert on the
site.

**Fix.** `build_league_lineup.py` reads `.cache/spray_profiles.json` (698
batters, Statcast 2025-04-01 to 2026-08-06, built by
`rebuild_spray_profiles.py`) and writes `foulball/league_lineup.py`, which the
site and the park sweep now simulate. The eighteen are real hitters chosen by
a rule, not a club:

- **Population:** every batter who appeared in 2026 and has at least 200
  tracked fouls in the window — 308 batters, 158 right-handed and 150
  left-handed by the side they actually stood on (switch-hitters fall on the
  side they bat most, which is left against the right-handed pitch mix the
  site uses).
- **The league:** each statistic's mean weighted by plate appearances in the
  window, reconstructed as tracked fouls over fouls per plate appearance.
  Plate appearances split 50.6% right / 49.4% left, so nine a side.
- **Spanning the range:** within each side the batters are sorted by fouls
  per plate appearance and cut into nine strata of equal plate-appearance
  share; one batter is taken from each, so the lineup covers the league's
  range of the one statistic that sets how many fouls a game produces
  instead of clustering at the median.
- **Sitting on the league:** in each stratum the batter taken is the one
  whose exit velocity, launch angle (mean and spread of each) and pull share
  are nearest the league means in units of the between-batter spread. No
  batter is used twice.

How the eighteen compare with the league (PA-weighted population means):

| | league | lineup |
|---|---|---|
| fouls per PA | 0.71 | 0.71 |
| exit velocity, mean | 77.9 | 77.8 |
| exit velocity, spread | 11.8 | 11.9 |
| launch angle, mean | 35.8 | 35.6 |
| launch angle, spread | 24.3 | 24.4 |
| pull share | 58.9% | 57.5% |

The old lineup's typed fouls per PA averaged 0.76 against this 0.71, so the
game total falls by about 7%. `tests/test_league_lineup.py` holds the module
to the rule: regenerating from the committed cache must reproduce it, every
profile must be computed rather than defaulted, and the lineup's means must
sit within half a between-batter standard deviation of the league's.

The typed profiles stay in `batter_profiles.py` for the demo, the golden
games and the plausibility tests, which were written against them and still
pass; the site no longer reads them.

---

## 4. Catch speed — catchability used the speed at the ground

**The claim is right.** `simulate_trajectory` integrates until the ball
reaches ground level and `landing_speed` is the speed there. A ball that
reaches a seat stops earlier and higher; the engine tested
`landing_speed < 95` for a ball that had notionally fallen another 15-50 ft
and been slowed by drag over that extra flight. At Yankee Stadium the
difference runs 6-12 mph, in both directions: a 75 mph / 35° fly ball
arrives at the upper deck at 44 mph where the ground figure was 51; a
100 mph / 12° line drive arrives in the field boxes at 77 mph where the
ground figure was 65.

**Fix.** `TrajectoryResult` carries the speed at every step;
`find_landing_contact` returns the step at which the ball met the deck; the
engine reads the speed there (`FoulBallEvent.arrival_speed`) and tests that.
`landing_height` is now the height at the seat rather than 0.

**Effect.** None on any figure the site prints: the pages print fouls per
area and exit speed off the bat, neither of which depends on arrival speed.
It moves `catchable_fouls` and so the engine's ranking by a rank or two
where a few hard line drives cross 95 mph at the seat (two neighbour swaps
in the golden top-tens).

---

## What the site's figures did

Rebuilt from a fresh 31-park run (400 simulations per batter, seed 42) under
the new physics and the new lineup. Baseline is the committed Step 26 run.
Figures are foul balls a game; `>` separates before and after.

| Park | into seats, before > after | unmatched share | behind-plate fouls | upper decks | busiest row |
|---|---|---|---|---|---|
| Rogers Centre | 33.1 > 42.4 (+9.4) | 35% > 17% | 11.7 > 15.8 | 4.9 > 8.2 | field level |
| American Family Field | 32.6 > 41.3 (+8.7) | 36% > 19% | 11.5 > 15.4 | 6.7 > 10.9 | field level |
| Chase Field | 32.4 > 41.0 (+8.6) | 36% > 19% | 11.5 > 15.3 | 6.6 > 10.5 | field level |
| Comerica Park | 32.1 > 40.6 (+8.5) | 37% > 20% | 11.4 > 15.1 | 5.0 > 8.4 | field level |
| Rate Field | 31.0 > 39.3 (+8.3) | 39% > 23% | 11.3 > 15.1 | 3.9 > 6.5 | field level |
| Truist Park | 32.4 > 40.6 (+8.2) | 36% > 20% | 11.8 > 15.5 | 6.0 > 10.0 | field level > deck above |
| Coors Field | 31.9 > 40.1 (+8.1) | 37% > 21% | 11.5 > 14.9 | 5.0 > 8.6 | field level > deck above |
| Progressive Field | 30.8 > 38.9 (+8.1) | 39% > 23% | 11.0 > 14.7 | 4.6 > 7.7 | field level |
| Daikin Park | 32.4 > 40.5 (+8.1) | 36% > 20% | 11.8 > 15.3 | 7.1 > 11.5 | field level |
| Oracle Park | 31.5 > 39.6 (+8.0) | 38% > 22% | 11.1 > 14.6 | 5.5 > 9.0 | field level |
| T-Mobile Park | 31.2 > 39.2 (+8.0) | 39% > 23% | 11.0 > 14.5 | 4.7 > 7.9 | field level |
| Angel Stadium | 31.2 > 39.1 (+7.9) | 39% > 23% | 11.0 > 14.6 | 5.5 > 9.2 | field level |
| loanDepot park | 31.9 > 39.8 (+7.9) | 37% > 22% | 11.5 > 14.9 | 6.5 > 10.5 | field level > deck above |
| Tropicana Field | 31.8 > 39.5 (+7.7) | 37% > 22% | 11.5 > 14.8 | 7.4 > 11.8 | field level > deck above |
| Camden Yards | 31.5 > 39.2 (+7.7) | 38% > 23% | 11.2 > 14.8 | 5.2 > 8.7 | field level |
| Busch Stadium | 31.2 > 38.9 (+7.7) | 38% > 23% | 11.3 > 14.7 | 4.4 > 7.5 | field level > deck above |
| Citizens Bank Park | 31.4 > 39.1 (+7.7) | 38% > 23% | 11.3 > 14.6 | 5.3 > 8.8 | field level > deck above |
| Citi Field | 31.7 > 39.2 (+7.6) | 38% > 23% | 11.5 > 14.8 | 5.5 > 9.1 | field level |
| Great American Ball Park | 31.5 > 39.0 (+7.5) | 38% > 23% | 11.2 > 14.5 | 5.8 > 9.4 | field level |
| Dodger Stadium | 30.8 > 38.2 (+7.5) | 39% > 25% | 12.5 > 15.8 | 3.0 > 5.1 | dugout club > deck above |
| Globe Life Field | 32.2 > 39.6 (+7.4) | 37% > 22% | 11.8 > 14.8 | 5.9 > 9.9 | field level > deck above |
| Petco Park | 31.0 > 38.3 (+7.3) | 39% > 25% | 11.2 > 14.2 | 6.0 > 9.8 | field level |
| Fenway Park | 30.1 > 37.3 (+7.2) | 41% > 27% | 10.8 > 14.0 | 3.1 > 5.2 | field level |
| PNC Park | 30.8 > 38.0 (+7.1) | 39% > 25% | 11.1 > 14.3 | 6.1 > 9.8 | field level |
| Kauffman Stadium | 31.4 > 38.5 (+7.0) | 38% > 24% | 11.5 > 14.6 | 5.6 > 9.1 | field level > deck above |
| Nationals Park | 31.3 > 38.2 (+6.9) | 38% > 25% | 11.5 > 14.6 | 4.7 > 7.9 | field level > deck above |
| Yankee Stadium | 30.3 > 37.2 (+6.9) | 40% > 27% | 11.1 > 14.5 | 2.8 > 4.4 | field level |
| Target Field | 25.2 > 29.2 (+4.0) | 50% > 43% | 10.8 > 13.7 | 2.9 > 4.6 | field level > deck above |
| Sutter Health Park | 22.1 > 25.2 (+3.0) | 56% > 50% | 9.3 > 12.1 | 6.6 > 10.0 | field level |
| Wrigley Field | 21.3 > 23.9 (+2.6) | 58% > 53% | 9.8 > 12.7 | 0.0 > 0.0 | field level |
| Las Vegas Ballpark | 20.4 > 21.8 (+1.4) | 60% > 57% | 9.0 > 11.0 | 6.0 > 8.8 | field level |

**Which change did what.** The physics fixes (items 2 and 4) barely touch the
site: run with the old typed lineup under the new code, Yankee Stadium goes
from 30.3 to 30.5 fouls into seats and its busiest row from 6.7 to 6.8.
Everything in the table is the lineup (item 3), and it is the launch-angle
moments that do it. The typed profiles carried launch angle 21 +/- 35
degrees, close to the class defaults of 23 +/- 36; the computed 2025-26
profiles carry 36 +/- 24 for the same statistic. Under the typed spread, 15.6
fouls a game were drawn with launch angles that put them down within 80 ft
of the plate, in the gap in front of the first row; under the computed
spread 6.2 are. Those balls now carry into the bowl, so:

- Fouls reaching seats rise by 7-9 a game at 27 parks (median +7.7) and by
  1.4-4.0 at the four parks with little or no foul-ground data (Wrigley,
  Sutter Health, Las Vegas, Target). The share of fouls the model throws
  away falls from 35-60% to 17-57%, median 23% (`LIMITATIONS.md` 2.6 said
  35-60%, and most of that was the typed launch angles, not the template).
- The game total is unchanged at 50.9 (was 50.8), by coincidence: the
  lineup's fouls per plate appearance are 7% lower (0.71 against 0.76), and
  7% fewer draws are discarded for travelling under 5 ft (about 25 per
  lineup of 3,600 against 275).
- Behind-plate fouls rise by about a third everywhere (11 to 15 a game),
  but the rise is on the deck above the field boxes: `HOME-B` nearly doubles
  (3.6 to 6.3 at Yankee Stadium) while `HOME-F` barely moves (6.8 to 6.9).
  Pop-ups that go back now carry higher and further.
- Upper decks down the lines take 60% more (4.4 at Yankee Stadium, 10.0 at
  Truist), for the same reason, though still a minor share.
- Pull tendency is live for the first time (57.5% against the inert 50%),
  and nothing visible came of it: every park is a mirror, and the lineup is
  nine and nine, so the pull-side lean cancels across the two foul lines by
  construction. It would matter for a single lineup or a real game.

**Does "behind home plate is busiest" still hold?** Yes, at all 31 parks:
the busiest row is a behind-the-plate area at every one. But *which*
behind-the-plate row changed. Before, the field-level seats behind the plate
led at all 31 (at Dodger Stadium, the Dugout Club). Now they lead at 20, and
at the other 11 (Truist, Coors, loanDepot, Tropicana, Busch, Citizens Bank,
Dodger, Globe Life, Kauffman, Nationals, Target) the deck above them leads,
by margins of 0.1 to 1.6 fouls a game — inside the noise the pages already
refuse to print. Why it holds: the straight-back share of fouls is a tuned
constant (`BACK_FOUL_BASE_RATE`, `LIMITATIONS.md` 2.3), and nothing in this
step touched it; with 28% of fouls going back into a wedge that two or
three rows share, those rows lead wherever the bowl is a stair of the same
shape. Why the leader moved: the computed launch angles are steeper, so
more of the straight-back balls clear the field boxes and come down on the
deck behind them. The About page's sentence on this is now computed from
the run (`site_build.busiest_sentence`) rather than asserted, and says
"at field level at 20 of them, and on the deck above at the other 11".

---

## Tests

All existing tests pass unchanged except the five golden-game locks, which
are snapshots of the model's output and were relocked for the physics
changes (`tests/test_golden_games.py`, with a note on what moved and why:
mean distance -0.9 to -1.0 ft, 6-9 fewer unsectioned balls of ~2,500, two
neighbour swaps in the catchable ranking). No threshold anywhere was
loosened. New: `tests/test_league_lineup.py` (the generated lineup is what
the rule produces, every profile is computed, the lineup sits on the league)
and `tests/test_arrival_speed.py` (per-step speeds, the contact row, the two
directions the seat speed moves, the Magnus direction).

The plausibility tests now run the league lineups at Yankee Stadium, the
site's own configuration, rather than the typed Yankees profiles the site no
longer reads. Eleven of the twelve passed as they were. The twelfth,
`test_every_lower_bowl_section_beats_every_upper_section`, required all 32
pairs of (upper deck down the line, lower-bowl section) to go the lower
bowl's way on one half-game, and failed: with computed launch angles the
pull-side upper deck and the smallest opposite-field field-box slice are a
near tie (1.5-1.7 fouls a game each) that goes either way with the seed (3
of 5 seeds pass). The all-pairs claim held before only because the typed
profiles' launch-angle spread starved the upper decks; it was a property of
the old inputs, not of the geometry the test guards. It is replaced by
`test_every_upper_section_is_below_the_lower_bowl`: on the whole game, the
busiest upper deck is under the lower bowl's per-section mean (1.7 against
2.4; under 2.0 at every seed tried). The other eleven, including "lower
bowl plus behind-plate is at least five times the upper decks" (eleven
times, as it happens) and "the top five are all lower bowl", are untouched.

The About page's model limitations gained a sixth entry, on the lift
coefficient finding in item 2: the flight model gives the ball about a fifth
of the measured lift and makes it up with drag, so distances match Statcast
while arcs run flatter and lower than a real foul's.
