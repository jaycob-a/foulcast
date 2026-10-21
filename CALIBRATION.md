# CALIBRATION.md — the back-foul rate, fitted to 710 real fouls

*Step 29, 2026-10-21, branch `step-29`. The method was fixed in
`CALIBRATION_PLAN.md` and committed before the model was run at any rate other
than 0.28; nothing in the method was changed afterwards. The run is
reproducible with `python calibrate_back_rate.py` (about 25 minutes on seven
cores), and its output is in `.cache/calibration_back_rate.json` and
`.cache/calibration_back_rate.txt`.*

## The short version

`BACK_FOUL_BASE_RATE`, the share of fouls that leave the bat travelling
backward, was 0.28: a constant tuned so the seats behind the plate would come
out busiest, with no source. `VALIDATION.md` (Step 28) found the model putting
40% of its fouls behind the plate against 31% observed, at every park.

This step fitted that one constant to FiveThirtyEight's observed fouls and
asked whether the fitted model predicts a park it was not fitted on better
than the old one did.

**Decision, by the rule fixed in advance: the rate changes to 0.17.** With
the rate fitted on seven parks and the eighth predicted blind, the held-out
model is closer to the observed distribution than the 0.28 model at **seven
of the eight parks**, and its pooled distance to the observations is **half**
the old model's (0.056 against 0.113). All three conditions of the
pre-registered rule hold.

What did not change:

- The model still does not tell the parks apart. Its behind-plate share is
  now 29.1–29.3% at every park where it was 39.8–40.1%; the observed share
  runs 24% to 51%. The league average of the other seven parks still predicts
  each park better than the model does (the model wins 2 of 8), so the
  verdict word is the same as Step 28's: **mixed: better than guessing, no
  better than a constant**.
- The dugout strip is still too full relative to the stretch from the dugout
  to the pole. The back-foul rate cannot move that ratio, and did not; see
  "What the fit points at" below.
- The camera-confirmed subset is fitted worse by the new rate, at all eight
  parks. `VALIDATION_PLAN.md` fixed before any result that this subset is
  selected toward the backstop (62% behind the plate against 31% in the full
  set), and `CALIBRATION_PLAN.md` said in advance that a rate fitted to where
  fouls land would score worse against it and that it would not veto the
  decision. It did, and it does not.

**The rate is now fitted to this data.** After this step the all-eight fit
has used every observation the project has, and the figures the current model
produces at these eight parks are in-sample: they measure how well one knob
can be bent to a sample, not how well the model predicts. The leave-one-out
figures below are the honest measure of fit, and they are what `VALIDATION.md`
now quotes.

## The run

Exactly as `calibrate_back_rate.py` and `CALIBRATION_PLAN.md` say: the eight
compared parks, one standard game each (eighteen league-lineup batters,
standard RHP mix, seed 42, 400 simulations per batter), at every rate from
0.06 to 0.36 in steps of 0.01; zones by distance along the foul line with
dugout ends at 50 and 130 ft; the full set (710 fouls by `used_zone`) as the
fitting set, the camera-confirmed set (307) scored alongside.

The 0.28 run reproduced `VALIDATION.md`'s zone shares exactly (maximum
difference 0.0 at every park and group), so the "original" column below is
Step 28's model to the digit.

## The fitted rates

| Fit | Held-out park | Fitted rate (max. likelihood) | Fitted rate (min. distance) |
|---|---|---|---|
| Leave one out | T-Mobile Park | 0.21 | 0.21 |
| Leave one out | Camden Yards | 0.17 | 0.17 |
| Leave one out | PNC Park | 0.17 | 0.17 |
| Leave one out | Dodger Stadium | 0.21 | 0.21 |
| Leave one out | American Family Field | 0.17 | 0.17 |
| Leave one out | Citizens Bank Park | 0.21 | 0.21 |
| Leave one out | Truist Park | 0.17 | 0.17 |
| Leave one out | Yankee Stadium | 0.21 | 0.17 |
| **All eight** | — | **0.17** | 0.17 |

The eight held-out fits split four and four between 0.17 and 0.21, and the
reason is visible in the training curve: the pooled log-likelihood over all
eight parks has two nearly equal local maxima, −1.0941 per ball at 0.17 and
−1.0947 at 0.21. That difference is 0.0006 per ball, about 0.4 units of
log-likelihood over 710 balls, which is nothing. Hold out one of the four
parks with a low observed behind-plate share (T-Mobile, Dodger, Citizens
Bank at 24%, Yankee at 30%) and the remaining seven prefer 0.21; hold out one
of the four with a higher share (Miller Park 51%, PNC 34%, Truist 32%,
Camden 29%) and they prefer 0.17. The total variation distance is less
ambiguous (0.061 at 0.17, 0.068 at 0.21, with a single minimum), and the
pre-registered tie rule was never needed: 0.17 is the maximum-likelihood
value on all eight parks by the plan's own criterion.

What the data does constrain: every rate from 0.13 to 0.24 is within 0.009
per ball of the maximum (the curve is bumpy in that range, which is
simulation noise of about a point in a share), and everything at or above
0.25, including the old 0.28, is clearly worse (0.28 is 0.017 per ball below
the maximum, about 12 units of log-likelihood over 710 balls). The honest
statement of the fit is "somewhere between about 0.13 and 0.24, and 0.17 is
the best single value"; the eight held-out rates, all 0.17 or 0.21, say the
same.

Neither fit touched an edge of the grid.

## The held-out model against the original and the baselines

Shares are behind plate / dugout strip / dugout to pole / past pole. "Held
out" is each park predicted at the rate fitted on the other seven. Distance is
total variation distance (0 perfect, 1 disjoint); log-likelihood is per ball,
higher is better. Dugout ends 50 and 130 ft.

### Pooled over the eight parks

| | Behind plate | Dugout strip | Dugout to pole | Past pole |
|---|---|---|---|---|
| **Observed, all 710** | 31.0% | 18.6% | 49.2% | 1.3% |
| **Observed, camera-confirmed 307** | 61.9% | 4.9% | 30.0% | 3.3% |
| **Held-out model** | 30.9% | 24.2% | 43.8% | 1.1% |
| Original model (0.28) | 39.9% | 21.0% | 37.9% | 1.2% |
| Current model, in-sample (0.17 on all eight) | 29.2% | 24.7% | 45.0% | 1.0% |

| Against the full set (710 balls) | Distance | Log-likelihood | Parks where the held-out model is closer | Rule |
|---|---|---|---|---|
| Held-out model | 0.056 | −1.091 | | |
| Original model (0.28) | 0.113 | −1.108 | 7 of 8 | **beats** |
| Even split (B1) | 0.301 | −1.386 | 8 of 8 | beats |
| Seven-zone even split (B2) | 0.373 | −1.468 | 8 of 8 | beats |
| League average, leave-one-out (B3) | 0.000 | −1.080 | 2 of 8 | does not beat |

| Against the camera-confirmed set (307 balls) | Distance | Log-likelihood | Parks where the held-out model is closer | Rule |
|---|---|---|---|---|
| Held-out model | 0.332 | −1.191 | | |
| Original model (0.28) | 0.241 | −1.080 | 0 of 8 | does not beat |
| Even split (B1) | 0.419 | −1.386 | 8 of 8 | beats |
| Seven-zone even split (B2) | 0.490 | −1.682 | 8 of 8 | beats |
| League average, leave-one-out (B3) | 0.002 | −0.917 | 1 of 8 | does not beat |

The chi-square test against the held-out shares, for information: pooled
p = 0.003 on the full set (the original model's was 0.00000001), and it still
rejects at most parks individually. As `VALIDATION_PLAN.md` said, rejection
is not the test.

### Park by park, full set

| Park | n | Observed | Held-out (rate) | Original | Distance: held-out / original / even / league avg |
|---|---|---|---|---|---|
| T-Mobile Park | 100 | 24 / 21 / 53 / 2 | 33 / 24 / 43 / 1 (0.21) | 40 / 21 / 38 / 1 | 0.115 / 0.161 / 0.280 / 0.081 |
| Camden Yards | 113 | 29 / 20 / 47 / 4 | 29 / 25 / 45 / 1 (0.17) | 40 / 21 / 38 / 1 | 0.047 / 0.117 / 0.261 / 0.048 |
| PNC Park | 111 | 34 / 14 / 50 / 2 | 29 / 26 / 44 / 1 (0.17) | 40 / 23 / 36 / 1 | 0.115 / 0.138 / 0.338 / 0.050 |
| Dodger Stadium | 86 | 24 / 24 / 50 / 1 | 33 / 20 / 46 / 2 (0.21) | 40 / 18 / 41 / 2 | 0.087 / 0.158 / 0.250 / 0.076 |
| American Family Field | 85 | 51 / 8 / 41 / 0 | 29 / 26 / 45 / 1 (0.17) | 40 / 22 / 38 / 1 | **0.215 / 0.142** / 0.418 / 0.223 |
| Citizens Bank Park | 75 | 24 / 25 / 51 / 0 | 33 / 24 / 43 / 1 (0.21) | 40 / 21 / 38 / 1 | 0.099 / 0.169 / 0.260 / 0.092 |
| Truist Park | 73 | 32 / 18 / 51 / 0 | 29 / 24 / 46 / 1 (0.17) | 40 / 20 / 39 / 1 | 0.070 / 0.115 / 0.322 / 0.023 |
| Yankee Stadium | 67 | 30 / 18 / 52 / 0 | 33 / 25 / 40 / 2 (0.21) | 40 / 22 / 36 / 2 | 0.123 / 0.167 / 0.321 / 0.034 |

The one park the held-out model loses is Miller Park (American Family
Field), the day with the highest observed behind-plate share in the data,
51%. Fitted without it, the other seven ask for 0.17, which puts 29% behind
the plate there; the old 0.28 happened to be nearer. Whether Miller Park's
51% is the park, the day's hitters (the camera-confirmed subset there is 89%
behind the plate, the highest in the data by a distance) or 85 balls of noise,
this data cannot say, and a model with one rate for all parks cannot follow
it either way.

### Park by park, camera-confirmed set

| Park | n | Observed | Held-out | Original | Distance: held-out / original / even / league avg |
|---|---|---|---|---|---|
| T-Mobile Park | 46 | 52 / 7 / 37 / 4 | 33 / 24 / 43 / 1 | 40 / 21 / 38 / 1 | 0.228 / 0.158 / 0.391 / 0.114 |
| Camden Yards | 55 | 53 / 7 / 33 / 7 | 29 / 25 / 45 / 1 | 40 / 21 / 38 / 1 | 0.298 / 0.190 / 0.355 / 0.112 |
| PNC Park | 47 | 70 / 2 / 23 / 4 | 29 / 26 / 44 / 1 | 40 / 23 / 36 / 1 | 0.440 / 0.331 / 0.452 / 0.110 |
| Dodger Stadium | 40 | 48 / 8 / 43 / 3 | 33 / 20 / 46 / 2 | 40 / 18 / 41 / 2 | 0.157 / 0.100 / 0.400 / 0.174 |
| American Family Field | 37 | 89 / 3 / 8 / 0 | 29 / 26 / 45 / 1 | 40 / 22 / 38 / 1 | 0.601 / 0.493 / 0.642 / 0.310 |
| Citizens Bank Park | 25 | 48 / 8 / 40 / 4 | 33 / 24 / 43 / 1 | 40 / 21 / 38 / 1 | 0.181 / 0.130 / 0.380 / 0.151 |
| Truist Park | 30 | 73 / 3 / 23 / 0 | 29 / 24 / 46 / 1 | 40 / 20 / 39 / 1 | 0.442 / 0.335 / 0.483 / 0.127 |
| Yankee Stadium | 27 | 67 / 0 / 33 / 0 | 33 / 25 / 40 / 2 | 40 / 22 / 36 / 2 | 0.339 / 0.267 / 0.500 / 0.089 |

Worse everywhere, by 0.05 to 0.11, exactly as a lower behind-plate share
must be against a set that is 62% behind the plate. If the camera-confirmed
balls were a fair sample of fouls, this step would have made the model worse;
Step 28 recorded before any model run why they are not (the centre-field
camera follows balls into the backstop and almost never into the dugout
strips: 3 camera-confirmed balls in the dugout zones against 176 in the full
set), and this step's plan said the fit would go the other way on it. Both
are reported so that nobody has to take the choice of set on trust.

## Sensitivity to the dugout estimate

The fit was made at dugout ends of 50 and 130 ft. Scored at the other two
pre-registered settings with the same held-out rates:

| Dugout ends | Held-out shares (pooled) | Held-out distance, full set | Original's distance | Parks held-out is closer | Rule vs original | Camera-set distance, held-out / original |
|---|---|---|---|---|---|---|
| 40 / 110 ft | 29 / 19 / 51 / 1 | **0.020** | 0.074 | 6 of 8 | beats | 0.349 / 0.255 |
| **50 / 130 ft** (fit) | 31 / 24 / 44 / 1 | 0.056 | 0.113 | 7 of 8 | beats | 0.332 / 0.241 |
| 60 / 150 ft | 33 / 32 / 34 / 1 | 0.154 | 0.200 | 7 of 8 | beats | 0.311 / 0.231 |

The held-out model beats the original at all three settings on the full set
and loses at all three on the camera set. At the shortest dugouts the pooled
held-out distribution is within two points of the observed one in every band
and the pooled chi-square no longer rejects (p = 0.69). That is partly the
model and partly that 40/110 happens to move the dugout boundary to where the
observed dugout share sits; it is reported, not claimed.

## Simulation noise

Six seeds (the site's 42, then 1–5) at 400 simulations per batter, dugout
ends 50 and 130 ft, pooled over the eight parks.

| Rate | Behind plate | Dugout strip | Dugout to pole | Past pole | Distance to full set | Distance to camera set |
|---|---|---|---|---|---|---|
| 0.17 (new) | 29.2–29.8% | 24.6–25.1% | 44.3–45.0% | 1.0–1.3% | 0.060–0.065 | 0.341–0.349 |
| 0.28 (old) | 39.9–41.4% | 19.7–21.1% | 36.8–38.1% | 1.0–1.2% | 0.113–0.125 | 0.226–0.241 |

The gain (0.113 to 0.056 held-out, or to 0.061 in-sample) is ten times the
seed-to-seed spread at either rate. This is not a seed effect.

## What the fit points at, and did not touch

The residual, pooled over the eight parks on the full set, model minus
observed, in points:

| Rate | Behind plate | Dugout strip | Dugout to pole | Past pole |
|---|---|---|---|---|
| 0.28 (old) | +8.9 | +2.4 | −11.2 | −0.1 |
| 0.17 (new) | −1.8 | +6.1 | −4.1 | −0.2 |

Lowering the rate moved about 11 points of fouls out of the behind-plate
band and spread them over the forward bands in the model's forward
proportions. That fixed the behind-plate excess. It did not fix the split
between the dugout strip and the stretch from the dugout to the pole, and
could not have: the ratio of the two forward bands is a property of the
forward fouls, and it is **0.55 in the model at either rate against 0.38
observed**. The model's forward fouls come down too close to the plate. Three
things could be responsible, and this test cannot separate them:

1. **The forward spray model** (`estimate_spray_angle`: base 27° ± 15° off
   the foul line, with pull-side and opposite-side shifts of 4° and 6°), all
   hand-set (`LIMITATIONS.md` §2.5). A wider mean spray angle puts more balls
   square to the plate; a narrower one sends them down the line, past the
   dugout.
2. **How far forward fouls carry**, which is the exit-velocity and
   launch-angle sampling plus the flight model. The flight model was checked
   against Statcast distance on 6,000 fouls in Step 27 (bias 15 ft, which is
   the ball flying short), and a ball that lands 15 ft short lands in the
   dugout strip rather than past it more often than it should.
3. **The dugout estimate itself.** At 40/110 ft the forward ratio comes right
   (model 0.37 against 0.38). The 50 and 130 ft ends were my estimate from
   the rule-book layout, and the comparison cannot tell a dugout that is 20 ft
   shorter than I drew it from a model that lands its fouls 20 ft short.

None of these was changed. The plan allowed one parameter to move and said
anything else would be reported, and this is the report. If the project
wants to go further, the next parameter to look at is the forward spray
angle, and the next piece of evidence to find is a published dugout length.

Two other figures moved with the rate, for the record:

| | 0.28 (old) | 0.17 (new) |
|---|---|---|
| Fouls landing behind the plane of the plate (`x < 0`) | 30.9% | 18.7% |
| Fouls reaching a seat, range over the eight parks | 73–81% | 71–80% |
| Fouls per game | 50.9 | 51.0 |

Fewer backward fouls means slightly fewer balls into a seat, because the
backstop seats were the most reliable catchers of a simulated foul; the
difference is a point or two. The game total is unchanged, as it has to be:
the rate decides where a foul goes, not whether one happens.

## What this does to the site

The site was rebuilt (`python site_build.py`; the model fingerprint changed,
so all 31 parks re-simulated, dated 2026-10-21). Old against new, from
`.cache/site/park_stats.json` at the previous commit and now:

| | 0.28 (old) | 0.17 (new) |
|---|---|---|
| Fouls a game, every park | 50.9 | 51.0 |
| Fouls reaching a seat, range over 31 parks | 21.8–42.4 | 19.7–41.9 |
| Behind-home areas' share of the fouls that reach a seat | 37–53% | 24–38% |
| Parks where a behind-home area is the busiest | 31 of 31 | 6 of 31 |

The behind-home areas lose about a third of their fouls at every park, and
those fouls go to the field boxes and the decks down the lines, which is
where the data said they were missing. The second-row consequence is the one
to notice: **the busiest area changed at 25 of 31 parks.** `LIMITATIONS.md`
§2.3 said the old rate "decides that the seats behind home plate are the
busiest area at all 31 parks"; it did, and with the rate fitted they are not.
At most parks the new leader is a dugout-box area; at nine parks (American
Family, Chase, Globe Life, loanDepot, Minute Maid, Petco, PNC, Tropicana,
Truist) it is the upper deck down the third-base line, and at Fenway the
Loge behind the net. Those upper-deck leaders are not a finding about any
upper deck. At those parks the top four or five areas are now within a
fraction of a foul of each other (PNC: 4.8, 4.7, 4.4, 4.2, 4.0), the
upper-deck areas were already third and fourth before this step, and the
reason they are large is the one `LIMITATIONS.md` §2.2 gives: every park
shares one bowl template, and at the parks with eight-section tables the
upper deck is drawn as one wide area. The old rate hid that by piling fouls
behind the plate; the fitted rate exposes it. `test_plausibility.py`, which
checks that the top five areas at Yankee Stadium are lower-bowl, still
passes, because Yankee Stadium's table is finer. Nothing was done about it
here, and the site's own copy about the template is unchanged and still
true.

The behind-plate area still leads at Yankee Stadium, Progressive Field, and
the four parks with no foul-territory areas or heavy roof cover (Las Vegas,
Oakland, Target Field, Wrigley), where there is little else to lead.

## Tests

The full suite passes: **2365 tests**, none skipped. Two test files changed, both in what they expect, neither in what they
check:

- **`tests/test_golden_games.py`**: the five locked games were relocked with
  the documented command. The relock note in the file records every change
  and why it is the size it is: mean landing distance up 8–13 ft at every
  game (a backward foul carries the glancing-contact penalty and lands short;
  the same ball hit forward keeps its speed), `no_section` up 30–87 at four
  games (the backstop seats caught nearly every ball sent at them; forward
  balls land in the template's gaps more often), side counts moving 20–50
  each way (a backward foul had its pull tendency compressed; forward it
  follows the batter), `total` moving −24 to +57 (the 5 ft floor), and
  HOME-B dropping from second to third or fourth with the dugout boxes
  rising. The leader is unchanged at all five games and the netted lists are
  identical.
- **`tests/test_netting.py`**, one assertion. The test that a netted section
  keeps its fouls also asserted that HOME-F at Fenway was *the* busiest
  section in the park. It was, because the old rate was tuned to make it so;
  at 0.17 it is fourth in that half-game, 1.78 fouls against the leading
  Loge box's 2.56. The assertion now requires HOME-F to rank in the top five,
  with a comment saying why; what the test guards (netting does not delete
  the fouls; the netted area still has a positive count and danger rating)
  is unchanged and still asserted.

Tests that `CALIBRATION_PLAN.md` named as likely to move and did not:
`test_plausibility.py` (behind-home at Yankee Stadium is still busier than
the upper decks down the lines and more than 0.4 of the lower bowl, and
HOME-F is still in the top three, now at 4.5 fouls against 6.9),
`test_distributions.py` (18.7% of fouls land behind the plane of the plate,
inside its 15–45% band), and `test_guardrails.py`. `test_site.py`'s checks
that the committed cache and pages come from the current model pass because
both were rebuilt.

## The limits of this fit, stated plainly

- **One knob, four bands, eight days.** The rate was fitted to the four-band
  distribution of 710 fouls from one day at each of eight parks in 2019, with
  that day's hitters, against a model run with eighteen 2025–26 batters.
  Everything `VALIDATION.md` lists under "The limits of this test" applies.
- **The fitted value is a range, not a point.** 0.13 to 0.24 are all nearly
  as good; 0.17 is the best single value by the pre-registered criterion, and
  the eight held-out fits say 0.17 or 0.21. A different day at these parks
  could move it a few hundredths.
- **The held-out figures are the only independent evidence there is.** Every
  figure the current model produces at these eight parks is in-sample. There
  is no more public landing data to test the fitted rate on, and the project
  should not describe the model as validated on the strength of this step.
- **Nothing finer than four bands.** No seating area, section or deck has
  been checked. The behind-plate areas on the site are about a quarter less
  busy than they were, and that is a fit, not a measurement of any seat.
- **The model still has no park information.** The league average of the
  other parks beats it at six of eight parks. Lowering the rate moved every
  park by the same amount; it was never going to change that.
- **The camera-confirmed set says the opposite.** It is selected, the
  selection was documented before any model was run, and the decision was
  pre-registered to rest on the full set; but a reader who trusts the camera
  set over the eyeballed zones should read this step as a step backward, and
  the figures to make that case are above.

## What should now change on the site, and has not

Not changed in this step, because the instruction was to change one
parameter and the pages' copy is pinned by tests that would have to change
with it:

- The About page heading "The model has never been checked against a real
  foul ball" and the park-page limit "No foul ball has ever been checked
  against it" were already untrue after Step 28 and are more so now.
- The park-page limit "The rate of balls hit straight back is a guess" is now
  wrong in a different way: the rate is fitted, to one day at each of eight
  parks. The honest replacement says that, and says that the fitted model
  still puts the dugout strip too full and does not tell parks apart.

`VALIDATION.md` carries the suggested wording.

## Reproducing this

```
python calibrate_back_rate.py --report .cache/calibration_back_rate.txt
```

About 25 minutes on seven cores (209 CPU-minutes of simulation: 31 rates and
eight parks, then two rates, five seeds and eight parks). `CALIBRATION_PLAN.md`
is the method; `VALIDATION_PLAN.md` and `validate_538.py` are the zone mapping
and the scoring, reused unchanged.
