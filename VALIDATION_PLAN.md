# VALIDATION_PLAN.md — pre-registration for the first test against real fouls

*Written 2026-10-21 on branch `step-28`, before the model was run for this
test. Committed before `VALIDATION.md` exists. The method below is not to be
changed after the results are seen; if something in it turns out to be
unworkable, `VALIDATION.md` says what was changed and why, and reports the
pre-registered version too.*

## What is being tested

The site publishes, for every park, a distribution of simulated foul balls
over seating areas. It has never been compared with a real foul ball. The one
public record of where real fouls land is FiveThirtyEight's set of 906 fouls
from the most foul-heavy day at each of ten parks in 2019 (`SOURCED_DATA.md`
Part 3; a copy is in `data/fivethirtyeight_foul_balls.csv`). This step
compares the model's distribution over FiveThirtyEight's zones with the
observed one, per park and pooled, against baselines fixed below.

This is a test, not a tuning step. No model code, parameter, lineup or
geometry is changed in this step.

## What has already been seen, and what has not

Before writing this file I read the FiveThirtyEight CSV and its story text
(zone definitions, the zone diagram, the ten game dates), and tabulated the
observed counts per park and per zone, because the park list and the sample
sizes below come from it. I have **not** run the model for this comparison
and have not looked at any model zone share. The site's cached park figures
(`.cache/site/park_stats.json`) are by seating area, not by these zones, and
were not consulted for this plan beyond the single fact, already in
`LIMITATIONS.md`, that every park simulates 50.8 fouls a game.

## The observed data

906 fouls, one day at each of ten parks (one day was a doubleheader), March
to June 2019, excluding foul tips and fouls caught for outs. Each ball has a
`used_zone` (1–7); 393 of them also have a `camera_zone`, where a camera
followed the ball to where it landed. FiveThirtyEight's eyeballed zone
matched the camera on 381 of the 393, and `used_zone` equals `camera_zone`
on 392 of 393.

**Zones**, from the story's text and diagram. The diagram is a generic
stadium viewed from behind the plate, outfield up: zone 2 is on the left
(third-base side), zone 3 on the right (first-base side); likewise 4/5 and
6/7. Every zone boundary is a straight line **perpendicular to a foul line**:

| Zone | Where |
|---|---|
| 1 | behind home plate: everything on the plate side of a line across each foul line at the near end of the dugout, seats and foul ground alike |
| 2, 3 | the dugout strip: between the near and far ends of the dugout, seats behind the dugout and the foul ground beside it |
| 4, 5 | from the far end of the dugout to the foul pole, seats and foul ground |
| 6, 7 | past the foul pole |

Grounders are in the data (226 of 906) and land in zones 1–5 on the field;
"batter hits self" (17) are all in zone 1; all 54 pop-ups are in zone 1.

**Two observed sets.** As instructed, the camera-confirmed 393 are the
primary comparison. I record here, before any model run, that this subset
is not a random sample of the 906: it is 61% zone 1 (the full set is 31%),
because the broadcast's centre-field camera sees the backstop and does not
follow balls into the dugout strips (3 camera-confirmed balls in zones 2+3
against 176 in the full set). A model that matched the 906 would therefore
fail against the 393, and the reverse. Both comparisons are run; the one I
regard as the fairer test of the model is the **full 906 by `used_zone`**,
because FiveThirtyEight's own check puts the eyeballed zones at 97% agreement
with the camera where both exist. That judgment is fixed now, not after
results. The verdict reports both and says which is which.

## The parks

The venue of each game day was checked today against the MLB schedule API
(`statsapi.mlb.com`, hydrate=venue); the home team is listed first in the
CSV's `matchup` and every game was at its park.

| CSV matchup | 2019 venue | Registry key | Status in this test |
|---|---|---|---|
| Seattle Mariners VS Minnesota Twins (5/18) | T-Mobile Park | `tmobile_park` | compared |
| Baltimore Orioles VS Minnesota Twins (4/20, doubleheader) | Oriole Park at Camden Yards | `camden_yards` | compared |
| Pittsburgh Pirates VS Milwaukee Brewers (6/1) | PNC Park | `pnc_park` | compared |
| Oakland A's vs Houston Astros (6/2) | Oakland Coliseum | none | **not run**: the registry's `oakland_coliseum` key is Sutter Health Park, a different building |
| Texas Rangers vs Toronto Blue Jays (5/3) | Globe Life Park in Arlington | `globe_life` | **run and reported separately, excluded from the verdict**: the registry park is Globe Life Field, opened 2020, a different building |
| Los Angeles Dodgers vs Arizona Diamondbacks (3/29) | Dodger Stadium | `dodger_stadium` | compared |
| Milwaukee Brewers vs New York Mets (5/4) | Miller Park | `american_family` | compared (same building, renamed 2021) |
| Philadelphia Phillies vs Miami Marlins (4/27) | Citizens Bank Park | `citizens_bank` | compared |
| Atlanta Braves vs New York Mets (4/14) | SunTrust Park | `truist_park` | compared (same building, renamed 2020) |
| New York Yankees vs Baltimore Orioles (3/31) | Yankee Stadium | `yankee_stadium` | compared |

So the verdict rests on **eight parks**. Observed balls per park (all /
camera-confirmed): Camden 113/55, PNC 111/47, T-Mobile 100/46, Dodger 86/40,
Miller 85/37, Citizens Bank 75/25, SunTrust 73/30, Yankee 67/27. Total
710/307 in the eight; 906/393 in the ten.

## Mapping the zones onto the model

The model does not have FiveThirtyEight's zones, and its seating-area labels
are known to be misplaced at most parks (`MAP_FINDINGS.md`). The mapping
therefore uses **where the model says each ball comes down**, not which
section label it was given. Every simulated foul carries a landing point in
a frame tied to the foul line on its side: `x` is feet along the foul line
from the plate (positive toward the outfield, negative behind the plate),
`y` is feet perpendicular to it into foul territory. FiveThirtyEight's
boundaries are perpendicular to the foul line, so a zone is a band of `x`:

| Model landing | FiveThirtyEight zone |
|---|---|
| `x < NEAR` (including every ball behind the plate, `x < 0`) | 1 |
| `NEAR ≤ x < FAR` | 2 (3B side) or 3 (1B side) |
| `FAR ≤ x < POLE` | 4 (3B side) or 5 (1B side) |
| `x ≥ POLE` | 6 (3B side) or 7 (1B side) |

with **NEAR = 50 ft** and **FAR = 130 ft** (the near and far ends of the
dugout, measured along the foul line), and **POLE** the park's published
foul-line distance on that side (`lf_distance` / `rf_distance` in the
registry). No source publishes dugout positions; 50 and 130 are my estimate
from the rule-book layout (on-deck circles 37 ft from the plate in front of
the dugout's near end; dugouts running to about first and third base and a
little past). Because they are an estimate, the comparison is **also run at
(40, 110) and (60, 150)** as a sensitivity check. The verdict uses (50, 130)
only; the other two are reported.

For a ball the model says reached a seat, `x` is taken at the point where
the trajectory met the deck (the first point after the apex at or below the
recorded arrival height), not where it would have hit the ground. For a ball
that reached no seat, `x` is the ground landing point. Every foul the engine
keeps counts, weighted as the engine weights it, whether or not it reached a
seat: the observed zones include foul ground, so the model's unmatched fouls
belong in the comparison. The engine discards balls that travel under 5 ft;
FiveThirtyEight kept 17 "batter hits self" balls, all in zone 1. They stay
in the observed counts. This is a small bias against the model in zone 1
and is accepted.

**Pairs, not sides.** The model builds every park as an exact mirror and the
project does not trust its own labelling of which foul line is which. The
comparison is therefore on **four groups**: zone 1; zones 2+3; zones 4+5;
zones 6+7. Seven-zone figures are reported for information only.

## The model run

One standard game at each park, exactly as the site builds it: the eighteen
league-lineup batters (`site_build.standard_lineups`), the standard RHP pitch
mix, seed 42, 400 simulations per batter. The lineups are 2025–26 profiles,
not the 2019 teams; the test is of the park-level distribution the site
publishes, so the lineups are held as the site holds them. Seeds 1–5 at the
same settings are run too, to show how much the shares move with simulation
noise. The verdict uses seed 42.

## Baselines

- **B1, even split over the four groups:** 25% each. The primary baseline.
- **B2, even split over the seven zones:** 1/7, 2/7, 2/7, 2/7 after
  grouping. Reported because those are the zones as drawn.
- **B3, league average, leave-one-park-out:** for each park, the pooled
  observed shares of the other seven parks (computed separately for the
  camera set and the full set). This baseline knows where fouls go on
  average and nothing about the park. A model that beats B1 but not B3 is
  better than guessing and no better than a constant.

## Metrics

For each park and observed set, with `p` the model's or a baseline's group
shares and `o` the observed shares (counts `n_g`, total `N`):

- **Total variation distance** (primary): `½ Σ |p_g − o_g|`. 0 is perfect,
  1 is disjoint.
- **Mean log-likelihood per ball**: `(1/N) Σ n_g · ln p_g`, with every share
  floored at 0.5% and renormalised before the log (applied identically to
  the model and the baselines) so a zero share cannot produce −∞.
- **Chi-square against the model's shares**, 3 degrees of freedom, for
  information. With N in the tens to hundreds and a template geometry it is
  expected to reject at most parks; rejection is not the test.

**Pooled** figures sum the observed counts over the eight parks; the pooled
model share is the count-weighted mean of the per-park model shares, and the
same for each baseline.

## What counts as beating a baseline

On a given observed set, the model **beats** a baseline when all three hold:

1. pooled total variation distance is lower than the baseline's;
2. pooled mean log-likelihood is higher than the baseline's;
3. per-park total variation distance is lower at **at least 5 of the 8**
   parks.

If one or two of the three hold, the result against that baseline is
**mixed**. If none, the model **does not beat** it.

Verdict words, fixed now:

| Against B1 (even split) | Against B3 (league average) | Word |
|---|---|---|
| beats | beats | good |
| beats | mixed or not | mixed: better than guessing, no better than a constant |
| mixed | any | mixed |
| does not beat | any | bad |

If the camera set and the full set give different words, the result is
reported as **mixed**, with both words and the reason recorded above (the
camera subset's selection) stated plainly.

## Things this test cannot say

- Nothing about seating areas or sections. The zones are coarse strips;
  agreement here does not validate any per-area figure on the site, and the
  known label errors are untouched.
- Nothing about Oakland. Nothing about Arlington: Globe Life Field is run
  against Globe Life Park's fouls only to show what the stand-in would give,
  and is excluded from every pooled figure and from the verdict.
- Nothing about 2026. The fouls are from 2019, from the most foul-heavy day
  at parks chosen for producing the most fouls, with the hitters of that day.
  Netting has been extended at most of these parks since; the model moves no
  geometry for netting and neither do the zones, so that does not enter the
  comparison, but renovations to seating would, and I have not surveyed
  them.
- Per-park sample sizes are 67–113 balls (25–55 camera-confirmed). Two
  distributions that differ by ten points in one group are inside the noise
  of a 30-ball sample.
- The dugout ends are estimates; the sensitivity runs bound the effect.

## Outputs

`validate_538.py` runs the comparison and writes a JSON file plus tables.
`VALIDATION.md` reports the results in plain English with the per-park and
pooled tables, the sensitivity runs, the seed band, and the verdict by the
rule above.
