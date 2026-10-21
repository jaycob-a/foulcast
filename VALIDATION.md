# VALIDATION.md — the model against 906 real foul balls

*Step 28, 2026-10-21, branch `step-28`. The method was fixed in
`VALIDATION_PLAN.md` and committed before the model was run; nothing in the
method was changed afterwards, and nothing in the model was changed in Step
28. The run's output is in `.cache/validation_538.json`; it is the record of
the model as it stood at `BACK_FOUL_BASE_RATE = 0.28`, and running
`python validate_538.py` today gives the fitted model's in-sample figures
instead (see the Step 29 note directly below).*

## Step 29 note: the back-foul rate is now calibrated to this data

*Added 2026-10-21 on branch `step-29`. Everything below this section
describes the model as it was tested in Step 28, before the change. It is
left as written because it is the record of the one test this model has had
that was not also a fit.*

**What changed.** Step 29 (`CALIBRATION_PLAN.md`, `CALIBRATION.md`) fitted
`BACK_FOUL_BASE_RATE`, the share of fouls that leave the bat travelling
backward, to the 710 fouls at the eight compared parks in this data. It was
0.28, a tuned constant with no source. It is now **0.17**, the
maximum-likelihood value for the four-band distribution of those 710 fouls.
Nothing else in the model was changed.

**What that means for this document.** The rate is now calibrated to the
same data this document tests the model against. The figures the current
model produces at these eight parks are therefore in-sample: they measure
how well one parameter can be bent to this sample, not how well the model
predicts, and they must not be quoted as validation. For the record, they
are: pooled shares 29.2 / 24.7 / 45.0 / 1.0 against 31.0 / 18.6 / 49.2 / 1.3
observed, distance 0.061, where the old model's was 0.113.

**The honest measure of fit is the leave-one-park-out result.** With the
rate fitted on seven parks and the eighth predicted blind, repeated for each
park:

| Held-out model, full set, pooled over eight parks | Distance | Log-likelihood | Parks where the held-out model is closer |
|---|---|---|---|
| Held-out model (fitted on the other seven each time) | 0.056 | −1.091 | |
| The old model (0.28), i.e. the tables below | 0.113 | −1.108 | 7 of 8 |
| Even split (B1) | 0.301 | −1.386 | 8 of 8 |
| League average of the other seven parks (B3) | 0.000 | −1.080 | 2 of 8 |

The held-out model beats the old one by the pre-registered rule (pooled
distance lower, pooled log-likelihood higher, closer at seven of eight parks)
and, like the old one, beats the even split everywhere and loses to the
league average, so **the verdict word is unchanged: mixed, better than
guessing and no better than a constant.** The model still does not tell the
parks apart (its behind-plate share is 29% at every park; the observed runs
24% to 51%). On the camera-confirmed set the fitted model is worse than the
old one at all eight parks (distance 0.332 against 0.241), as the plan said a
rate fitted to the full set would be against a subset that is 62% behind the
plate; the reasons that set was fixed as the secondary one are in
`VALIDATION_PLAN.md` and were written before any result.

**What the fit did not fix.** The model's forward fouls still come down too
near the plate: the dugout strip is 6 points too full and the stretch from
the dugout to the pole 4 points too empty, at the new rate as at the old,
and the back-foul rate cannot move that ratio. `CALIBRATION.md` names the
parameters it points at (the forward spray angle, forward carry, or the
dugout estimate itself) and changes none of them.

**What this licenses.** No more than before: no accuracy percentage, no claim
about a park or a seating area, and now also no claim that the behind-plate
figures are validated, because they are fitted. The site's copy, which says
the model has never been checked against a real foul and that the back-foul
rate is a guess, is wrong on both counts after Steps 28 and 29 and should
change; the suggested wording at the end of this document is updated for
that.

## The short version

This is the first time any figure from this model has been compared with a
foul ball that actually landed. The comparison is coarse: FiveThirtyEight's
906 fouls from one day at each of ten parks in 2019, placed by eye into seven
broad zones, folded here into four bands (behind the plate; the dugout strip;
dugout to foul pole; past the pole). Eight of the ten parks are in the
registry as the same building; Oakland Coliseum has no model and Globe Life
Park in Arlington has been replaced by a different building.

**Result, by the rule fixed in advance: mixed. The model is better than
guessing and no better than a constant.**

- Against an even split across the four bands, the model is closer to the
  observed distribution at **all eight parks**, on both observed sets. The
  pooled distance to the observations is about a third of the even split's.
- Against the league average (each park predicted by the pooled fouls of the
  other seven), the model loses at **seven of eight parks** on the full set
  and six of eight on the camera-confirmed set. The model's zone shares are
  almost the same at every park (behind-plate share 39.8–40.1% everywhere),
  so it carries no park information, and a constant that knows where fouls
  go on average beats it.
- The model's one systematic error is visible in every table: it puts **too
  many fouls behind the plate and too few down the lines**. Pooled over the
  eight parks, 40% of the model's fouls land behind the plate against 31%
  observed, and 38% land between the dugout and the pole against 49%.

The two observed sets give the same word, so there is no conflict to report
between them. Where they differ (the camera-confirmed set is 62% behind the
plate, the full set 31%), the plan recorded in advance why: the broadcast
camera follows balls into the backstop and almost never into the dugout
strips.

## What was compared

**Observed.** FiveThirtyEight's `foul-balls.csv` (`data/` carries a copy
with attribution). Every ball has a zone; 393 of 906 have a camera-confirmed
zone. Zones were mapped onto the model by where the model says each ball
comes down, as a band of distance along the foul line: behind the plate up
to the near end of the dugout (50 ft), the dugout strip (50–130 ft), dugout
to foul pole, and past the pole, on either side. The dugout ends are my
estimate; the comparison was also run at (40, 110) and (60, 150) and the
verdict does not change (below).

**Model.** One standard game at each park as the site builds it: the same
eighteen league-lineup batters at every park, seed 42, 400 simulations per
batter, every simulated foul counted whether or not it reached a seat (the
observed zones include foul ground). The model produces 50.9 fouls a game at
every park, of which 73–81% reach a seat.

**Observed fouls by zone and park** (zones 1–7 as FiveThirtyEight drew them:
1 behind the plate, 2/3 the dugouts, 4/5 dugout to pole, 6/7 past the pole;
even-numbered zones are the third-base side):

| Park (2019 game day) | All fouls 1 / 2 / 3 / 4 / 5 / 6 / 7 | Camera-confirmed 1 / 2 / 3 / 4 / 5 / 6 / 7 |
|---|---|---|
| Camden Yards (4/20, doubleheader) | 33 / 10 / 13 / 21 / 32 / 3 / 1 = 113 | 29 / 0 / 4 / 8 / 10 / 3 / 1 = 55 |
| PNC Park (6/1) | 38 / 10 / 6 / 30 / 25 / 0 / 2 = 111 | 33 / 0 / 1 / 7 / 4 / 0 / 2 = 47 |
| T-Mobile Park (5/18) | 24 / 16 / 5 / 33 / 20 / 1 / 1 = 100 | 24 / 1 / 2 / 7 / 10 / 1 / 1 = 46 |
| Dodger Stadium (3/29) | 21 / 7 / 14 / 25 / 18 / 1 / 0 = 86 | 19 / 1 / 2 / 7 / 10 / 1 / 0 = 40 |
| Miller Park, now American Family Field (5/4) | 43 / 3 / 4 / 16 / 19 / 0 / 0 = 85 | 33 / 0 / 1 / 0 / 3 / 0 / 0 = 37 |
| Citizens Bank Park (4/27) | 18 / 13 / 6 / 22 / 16 / 0 / 0 = 75 | 12 / 1 / 1 / 9 / 1 / 0 / 1 = 25 |
| SunTrust Park, now Truist Park (4/14) | 23 / 8 / 5 / 18 / 19 / 0 / 0 = 73 | 22 / 0 / 1 / 3 / 4 / 0 / 0 = 30 |
| Yankee Stadium (3/31) | 20 / 4 / 8 / 12 / 23 / 0 / 0 = 67 | 18 / 0 / 0 / 3 / 6 / 0 / 0 = 27 |
| *Globe Life Park, Arlington (5/3), building gone* | 30 / 10 / 4 / 22 / 19 / 1 / 1 = 87 | 24 / 0 / 1 / 2 / 7 / 1 / 1 = 36 |
| *Oakland Coliseum (6/2), no model* | 28 / 15 / 15 / 16 / 35 / 0 / 0 = 109 | 27 / 0 / 0 / 7 / 16 / 0 / 0 = 50 |

## The results, pooled over the eight parks

Shares are behind plate / dugout strip / dugout to pole / past pole. Distance
is total variation distance (0 perfect, 1 disjoint). Log-likelihood is per
ball, higher is better.

| | Behind plate | Dugout strip | Dugout to pole | Past pole |
|---|---|---|---|---|
| **Observed, all 710** | 31.0% | 18.6% | 49.2% | 1.3% |
| **Observed, camera-confirmed 307** | 61.9% | 4.9% | 30.0% | 3.3% |
| **Model** | 39.9% | 21.0% | 37.9% | 1.2% |
| Even split (B1) | 25% | 25% | 25% | 25% |
| Seven-zone even split (B2) | 14.3% | 28.6% | 28.6% | 28.6% |

| Against the full set (710 balls) | Distance | Log-likelihood | Parks where the model is closer |
|---|---|---|---|
| Model | 0.113 | −1.108 | |
| Even split (B1) | 0.301 | −1.386 | 8 of 8 |
| Seven-zone even split (B2) | 0.373 | −1.468 | 8 of 8 |
| League average, leave-one-out (B3) | 0.000 | −1.080 | 1 of 8 |

| Against the camera-confirmed set (307 balls) | Distance | Log-likelihood | Parks where the model is closer |
|---|---|---|---|
| Model | 0.241 | −1.080 | |
| Even split (B1) | 0.419 | −1.386 | 8 of 8 |
| Seven-zone even split (B2) | 0.490 | −1.682 | 8 of 8 |
| League average, leave-one-out (B3) | 0.002 | −0.917 | 2 of 8 |

The pooled distance for the league average is close to zero by
construction (the pooled leave-one-out shares are nearly the pooled observed
shares); the per-park column is the comparison that means something, and the
model loses it.

Applying the rule: the model **beats** B1 and B2 on both sets (pooled
distance lower, pooled log-likelihood higher, closer at at least five of
eight parks) and **does not beat** B3 on either (none of the three
conditions holds). The verdict table in the plan gives **"mixed: better than
guessing, no better than a constant"** for both sets.

## The results, park by park

Full set, all 906 by the zone FiveThirtyEight used. Model shares at (50, 130).

| Park | n | Observed | Model | Distance: model / even / league avg | Chi-square p |
|---|---|---|---|---|---|
| T-Mobile Park | 100 | 24 / 21 / 53 / 2 | 40 / 21 / 38 / 1 | 0.161 / 0.280 / 0.081 | 0.003 |
| Camden Yards | 113 | 29 / 20 / 47 / 4 | 40 / 21 / 38 / 1 | 0.117 / 0.261 / 0.048 | 0.010 |
| PNC Park | 111 | 34 / 14 / 50 / 2 | 40 / 23 / 36 / 1 | 0.138 / 0.338 / 0.050 | 0.020 |
| Dodger Stadium | 86 | 24 / 24 / 50 / 1 | 40 / 18 / 41 / 2 | 0.158 / 0.250 / 0.076 | 0.027 |
| American Family Field | 85 | 51 / 8 / 41 / 0 | 40 / 22 / 38 / 1 | 0.142 / 0.418 / 0.223 | 0.016 |
| Citizens Bank Park | 75 | 24 / 25 / 51 / 0 | 40 / 21 / 38 / 1 | 0.169 / 0.260 / 0.092 | 0.026 |
| Truist Park | 73 | 32 / 18 / 51 / 0 | 40 / 20 / 39 / 1 | 0.115 / 0.322 / 0.023 | 0.204 |
| Yankee Stadium | 67 | 30 / 18 / 52 / 0 | 40 / 22 / 36 / 2 | 0.167 / 0.321 / 0.034 | 0.029 |
| *Globe Life Field vs Globe Life Park's fouls* | 87 | 34 / 16 / 47 / 2 | 40 / 20 / 39 / 1 | 0.099 / 0.316 / 0.045 | 0.204 |

Camera-confirmed set.

| Park | n | Observed | Model | Distance: model / even / league avg | Chi-square p |
|---|---|---|---|---|---|
| T-Mobile Park | 46 | 52 / 7 / 37 / 4 | 40 / 21 / 38 / 1 | 0.158 / 0.391 / 0.114 | 0.004 |
| Camden Yards | 55 | 53 / 7 / 33 / 7 | 40 / 21 / 38 / 1 | 0.190 / 0.355 / 0.112 | <0.001 |
| PNC Park | 47 | 70 / 2 / 23 / 4 | 40 / 23 / 36 / 1 | 0.331 / 0.452 / 0.110 | <0.001 |
| Dodger Stadium | 40 | 48 / 8 / 43 / 3 | 40 / 18 / 41 / 2 | 0.100 / 0.400 / 0.174 | 0.373 |
| American Family Field | 37 | 89 / 3 / 8 / 0 | 40 / 22 / 38 / 1 | 0.493 / 0.642 / 0.310 | <0.001 |
| Citizens Bank Park | 25 | 48 / 8 / 40 / 4 | 40 / 21 / 38 / 1 | 0.130 / 0.380 / 0.151 | 0.180 |
| Truist Park | 30 | 73 / 3 / 23 / 0 | 40 / 20 / 39 / 1 | 0.335 / 0.483 / 0.127 | 0.002 |
| Yankee Stadium | 27 | 67 / 0 / 33 / 0 | 40 / 22 / 36 / 2 | 0.267 / 0.500 / 0.089 | 0.009 |
| *Globe Life Field vs Globe Life Park's fouls* | 36 | 67 / 3 / 25 / 6 | 40 / 20 / 39 / 1 | 0.311 / 0.417 / 0.071 | <0.001 |

The chi-square test rejects the model's shares at seven of eight parks on
the full set and six of eight on the camera set, as the plan said it would.
It is reported because it was promised, not because it decides anything: a
template geometry was never going to pass a goodness-of-fit test on a
hundred balls, and the question put to the data was whether the model is
nearer than a baseline, which the distance column answers.

The Globe Life Field row is a different building than the one the fouls
were hit in. It is the closest row in the full-set table, which says nothing
good about the Arlington model and something about how little the model's
shares depend on the park.

## What the model gets right and wrong

**Right.** The broad shape. Behind the plate is a large share and past the
poles a tiny one, in the data and in the model (1.3% observed past the
poles, 1.2% modelled). The even split, which is the baseline a reader would
reach for first, is beaten everywhere and by a wide margin.

**Wrong, consistently.** The model has 9 points too many behind the plate
(40% against 31%) and 11 points too few between the dugout and the pole (38%
against 49%), at every one of the eight parks. `LIMITATIONS.md` §2.3 already
records that the share of balls sent straight back is a tuned constant
(`BACK_FOUL_BASE_RATE = 0.28`) chosen so that the seats behind the plate
would come out busiest; this is the first external evidence that it is set
too high, or that the forward fouls do not carry far enough down the lines,
or both. Which of those it is cannot be told from four bands. Nothing was
changed in response in Step 28: this was a test. (Step 29 then fitted the rate
to this data: it is now 0.17, and the forward fouls are still short. See the
note at the top.)

**Absent.** Park-to-park variation. The observed behind-plate share runs
from 24% (T-Mobile, Dodger, Citizens Bank) to 51% (Miller Park); the model's
runs from 39.8% to 40.1%. The dugout-to-pole share runs 41–53% observed and
36–41% modelled. The parks differ in the data by far more than they differ
in the model, which is exactly what `LIMITATIONS.md` §2.7 says about the
shared template, now seen against observations. Some of the observed spread
is the day's hitters and some is sampling noise on 67–113 balls, and the
data cannot separate those from real park differences either; but the model
is not even in a position to try.

**Sides.** Within a pair, the model is symmetric by construction (zone 2
9.0–11.5% against zone 3 8.5–11.0%; zones 4 and 5 within 0.5 points). The
observed data is not: T-Mobile had 16 balls in zone 2 and 5 in zone 3, Dodger
Stadium 7 and 14. That is the day's lineups as much as the park, and the
comparison was folded into pairs in advance for this reason.

## Sensitivity to the dugout estimate

The verdict was fixed at dugout ends of 50 and 130 ft. The other two
settings move the model's shares but not the verdict, which is the same word
on both observed sets at all three settings.

| Dugout ends | Model shares (pooled) | Distance to full set | Distance to camera set | Verdict |
|---|---|---|---|---|
| 40 / 110 ft | 38 / 16 / 45 / 1 | 0.074 | 0.255 | same: mixed |
| **50 / 130 ft** (verdict) | 40 / 21 / 38 / 1 | 0.113 | 0.241 | mixed |
| 60 / 150 ft | 42 / 28 / 29 / 1 | 0.200 | 0.231 | same: mixed |

Shorter dugouts flatter the model on the full set, because they move balls
from the dugout band into the dugout-to-pole band where the model is short;
they do not touch the behind-plate excess, which is why the verdict holds.
At every setting the model beats the even split at all eight parks and loses
to the league average at six or more.

## Simulation noise

Six seeds (the site's 42, then 1–5) at 400 simulations per batter, dugout
ends 50 and 130 ft. The verdict seed reproduced exactly on the second run.

| | Behind plate | Dugout strip | Dugout to pole | Past pole | Distance to full set | Distance to camera set |
|---|---|---|---|---|---|---|
| Pooled model shares across six seeds | 39.9–41.4% | 19.7–21.1% | 36.8–38.1% | 1.0–1.2% | 0.113–0.125 | 0.226–0.241 |

Per park, the behind-plate share moves by at most 1.8 points between seeds
and the dugout-to-pole share by at most 1.3. The verdict is the same word on
both observed sets at every seed, the even split is beaten at all eight
parks at every seed, and the league average wins the same seven (full set)
or six (camera set) parks at every seed. Simulation noise is an order of
magnitude smaller than the gap to the observations, and smaller than the gap
between any two parks in the data.

The seed-band output is in `.cache/validation_538_seedband.json`.

## The limits of this test, stated plainly

- **It is 2019 data.** The hitters are the 2019 hitters of those days; the
  model's lineups are eighteen 2025–26 batters held the same at every park.
  The model was not asked to reproduce the day; it was asked whether the
  park-level distribution it publishes looks like a real one.
- **They were unusually foul-heavy days,** chosen because they produced the
  most fouls at the parks that produce the most fouls. A day with 113 fouls
  is not an ordinary day (one of them is two games). Whether a foul-heavy day
  sends balls to different places than an ordinary one is unknown.
- **The parks have changed.** Every club extended its netting for 2020
  (Ballpark Digest, 2019-12-11), several to the poles; netting changes where
  a ball stops, not where it is heading, and neither the zones nor the model
  move for it, so it should not bias this comparison, but it is a change.
  Camden Yards moved its left-field wall in 2022 and again in 2025 (outfield,
  no seats affected); Dodger Stadium rebuilt its centre-field plaza and
  pavilions for 2021 (outfield). Two names changed. I did not survey
  foul-territory seating changes at the eight parks, and the model's seating
  is a template in any case, so a real renovation would be invisible to it.
- **The zones are coarse.** Four bands. Agreement at this level says nothing
  about any seating area, section or deck on the site. The known seat-label
  errors (`MAP_FINDINGS.md`) are untouched and untested by this.
- **The zone boundaries are estimates.** FiveThirtyEight drew them on a
  generic diagram; the dugout ends were set at 50 and 130 ft by me from the
  rule-book layout, and the sensitivity runs show the full-set distance
  moving between 0.07 and 0.20 as they move.
- **The camera-confirmed subset is selected.** 62% behind the plate against
  31% in the full set, and 3 balls in the dugout strips against 176. It is
  the primary comparison because it was asked for, and it is reported in
  full; it is not a random sample of fouls, and I would not use it alone.
- **The samples are small.** Per park, 67–113 balls, 25–55 camera-confirmed.
  A ten-point gap in one band at one park is inside sampling noise at these
  sizes; the pooled 710 is what the verdict rests on.
- **Two of the ten parks are missing.** Oakland Coliseum is not modelled at
  all; Arlington's 2019 park no longer exists and its successor was run only
  to show what a wrong building gives.
- **The model was run once, at the site's seed.** The seed band above shows
  how much that matters.
- **"Beats the even split" is a low bar.** It was chosen as the primary
  baseline because it is the honest floor, and it is reported as such; the
  league-average baseline is the one that tells you whether the model knows
  anything about a given park, and it does not.

## How I would describe this on the site

The site currently says, on every park page and on the About page, that the
model "has never been checked against a real foul ball." After this step
that sentence is no longer true and should go. What I would put in its
place, in the same position and at the same size:

> **Checked once, coarsely, and found to be a shape, not a measurement.**
> Against the only public record of where real fouls land (FiveThirtyEight's
> 906 fouls, one day at each of ten parks in 2019, placed by eye into four
> broad bands), the model is closer than an even split at all eight parks it
> could be compared with, and puts too many balls behind the plate (40%
> against 31% observed) and too few down the lines (38% against 49%). It
> does not tell the parks apart: the average of the other parks predicts
> each park better than the model does. Nothing finer than four bands has
> been checked, so no seating-area figure on this page has been.

*(That was Step 28's wording, for the model at 0.28. After Step 29 the
honest version is:)*

> **Checked once, coarsely, then fitted to the check.** Against the only
> public record of where real fouls land (FiveThirtyEight's 906 fouls, one
> day at each of ten parks in 2019, placed by eye into four broad bands), the
> model was closer than an even split at all eight parks it could be compared
> with and put too many balls behind the plate. The one number that decides
> that, the share of fouls hit straight back, has since been fitted to those
> same fouls, so the behind-plate figures on this page agree with that data
> because they were made to. With the rate fitted on seven parks and the
> eighth predicted blind, the model is nearer the observed distribution than
> before at seven of eight parks, still puts too many balls just past the
> dugouts and too few further down the lines, and still does not tell the
> parks apart: the average of the other parks predicts each park better than
> the model does. Nothing finer than four bands has been checked, so no
> seating-area figure on this page has been.

Good, bad or mixed: **mixed**, and the word was fixed before the numbers. If
the site has to pick one sentence, it is the second half of the quote above,
not the first: "better than guessing" is true but is the kind of true that
invites a reader to trust the per-area figures, and this test gives them no
reason to.

What this test does not license, and the site should not say: any accuracy
percentage, any claim about a specific park, any claim about a seating area,
and any suggestion that the behind-plate figures have been validated (they
are the ones most wrong).

## Reproducing this

```
python validate_538.py --seeds 42 --out .cache/validation_538.json
python validate_538.py --seeds 42 1 2 3 4 5 --out seedband.json
```

About 40 seconds a park and seed. `VALIDATION_PLAN.md` is the method;
`data/FIVETHIRTYEIGHT_README.md` is the data's provenance and license.

Since Step 29 these commands run the fitted model (rate 0.17) and give its
in-sample figures, not the tables above. The committed
`.cache/validation_538.json` and `.cache/validation_538_seedband.json` are
the Step 28 run at 0.28 and are kept as its record; the fitted model's runs
at every rate, including 0.28 (which reproduced these files exactly) and
0.17, are in `.cache/calibration_back_rate.json`.
