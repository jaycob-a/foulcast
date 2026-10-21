# CALIBRATION_PLAN.md — pre-registration for recalibrating the back-foul rate

*Written 2026-10-21 on branch `step-29`, before the model was run at any rate
other than the one it has. Committed before `CALIBRATION.md` exists and before
`calibrate_back_rate.py` is run. The method below is not to be changed after
the results are seen; if something in it turns out to be unworkable,
`CALIBRATION.md` says what was changed and why, and reports the
pre-registered version too.*

## What is being done, and why

`VALIDATION.md` (Step 28) compared the model with FiveThirtyEight's 906
observed fouls and found one systematic error at every one of the eight
compared parks: too many fouls behind the plate (39.9% of the model's fouls
against 31.0% observed, pooled) and too few between the dugout and the foul
pole (37.9% against 49.2%). The likeliest single cause is
`BACK_FOUL_BASE_RATE` in `foulball/trajectory.py`: the share of fouls that
leave the bat travelling backward. It is 0.28, a constant the code itself
describes as tuned so that the seats behind the plate would come out busiest,
with no source (`LIMITATIONS.md` §2.3, `NOTES.md` item 1).

This step fits that one constant to the FiveThirtyEight data and asks whether
the fitted model predicts a park it was **not** fitted on better than the
original model does. Fitting to all eight parks and then scoring on the same
eight would measure how well a parameter can be bent to a sample; the
leave-one-park-out figures are the honest measure of fit and are the ones the
decision rests on.

## What has already been seen, and what has not

Seen: everything in `VALIDATION.md`, including the per-park and pooled zone
shares of the model at the current rate, the observed counts, and the
baselines. Those shares were produced at 0.28 and are the starting point.

Not seen: any model output at any other value of `BACK_FOUL_BASE_RATE`. I
have not run the model at another rate, have not computed what fraction of
the model's behind-plate band is backward fouls (`x < 0`) as opposed to
forward fouls landing within 50 ft of the plate, and have not worked out
which rate the data would prefer. The grid below is wide on purpose so that
it does not encode a guess.

## What is changed and what is not

Exactly one parameter is a candidate for change: `BACK_FOUL_BASE_RATE`. The
multipliers inside `back_foul_probability` (launch angle, exit velocity,
pitch type), the backward spray draw, the glancing-contact speed penalty, the
forward spray model, the lineups, the geometry and the engine are all held as
they are. If the results point at another parameter, `CALIBRATION.md` says
so and nothing is done about it in this step.

## The observed data and the zone mapping

As in `VALIDATION_PLAN.md`, unchanged: the same eight compared parks, the
same CSV, the same zones mapped by where the model says each ball comes down
(band of distance along the foul line), dugout ends at 50 and 130 ft, four
groups (behind the plate; dugout strip; dugout to pole; past the pole),
Arlington and Oakland excluded. The code that does this is `validate_538.py`
and is reused as-is; nothing in it is altered.

**Which observed set the fit uses.** The fit is to the **full set** (all
fouls by `used_zone`, 710 balls at the eight parks). `VALIDATION_PLAN.md`
fixed, before any result was seen, that the full set is the fairer test,
because the camera-confirmed subset is selected toward the backstop (62%
behind the plate against 31% in the full set; 3 balls in the dugout strips
against 176). A rate fitted to the camera set would be fitted to a camera
operator's habits. The camera set is **scored and reported** for every fit
below, but nothing is fitted to it and it does not enter the decision.

## The model run

One standard game at each park exactly as `validate_538.py` runs it: the
eighteen league-lineup batters, the standard RHP pitch mix, seed 42, 400
simulations per batter, every kept foul counted and weighted as the engine
weights it, whether or not it reached a seat. Only `BACK_FOUL_BASE_RATE` is
set differently, at run time, before each simulation.

The engine makes its backward-or-forward draw for every ball by comparing one
uniform random number with the ball's probability, and it makes that draw
whether the ball goes back or not. Changing the rate therefore does not
change the random stream: at a lower rate, the same balls are simulated with
the same exit velocities, launch angles and pitches, and only the balls whose
uniform fell between the old and new probability change branch. Runs at
different rates share their random numbers, which is why the grid below can
be as fine as it is without the fit chasing noise between adjacent rates.

## The grid

`BACK_FOUL_BASE_RATE` is run at every value from **0.06 to 0.36 in steps of
0.01** (31 values; 0.28, the current value, is one of them). Each value is
run at all eight parks, so the fit on any seven parks and the prediction for
the eighth both come from actual simulations at the chosen rate, with no
interpolation.

If the fitted rate falls on an edge of the grid (0.06 or 0.36), the grid is
extended by 0.10 in that direction and the fit is redone; `CALIBRATION.md`
records that this happened.

## The fit

For a set of training parks `T` and a candidate rate `r`, the **training
score** is the pooled mean log-likelihood of the training parks' observed
full-set group counts under the model's group shares at rate `r`:

    S_T(r) = (1 / N_T) Σ_{k∈T} Σ_g n_{k,g} · ln q_{k,g}(r)

where `q_{k,g}(r)` is the model's share of group `g` at park `k` and rate
`r`, floored at 0.5% and renormalised exactly as `validate_538.py` floors
every share before a log. This is the multinomial maximum-likelihood fit of
one parameter to the four-group counts. The **fitted rate** `r*_T` is the
grid value that maximises `S_T`; if two grid values tie, the one nearer 0.28
is taken (and if they are equidistant, the lower).

The grid value that minimises the pooled total variation distance on the
training parks is also recorded, for information. It does not decide
anything.

**Leave-one-park-out.** For each compared park `h`, `T` is the other seven.
The held-out prediction for `h` is the model's group shares at park `h` at
rate `r*_T`. Eight held-out predictions, one per park, each from a rate that
never saw that park's fouls. The eight fitted rates are reported with their
spread: if they differ by more than a couple of grid steps, the fit is being
driven by individual parks and the report says so.

**All eight.** `T` is all eight parks. This fitted rate is the one that
would be written into the model if the decision below says to change it. It
is not used for any held-out figure.

## The comparison

The held-out model is scored, per park and pooled, exactly as
`VALIDATION_PLAN.md` scores the model, with the same functions:

- **Total variation distance** (primary), **mean log-likelihood per ball**
  (floored at 0.5%), and **chi-square** (3 degrees of freedom, for
  information), on the full set and on the camera-confirmed set.
- **Pooled** figures sum the observed counts over the eight parks; the pooled
  held-out model share is the count-weighted mean of the eight held-out
  per-park shares. This is a legitimate pooled figure because every one of
  the eight shares was predicted without its own park's data.

It is compared against four references:

- **M0, the original model** at 0.28, the same run as `VALIDATION.md` (the
  grid includes 0.28, so this is reproduced in the same run and should
  match `VALIDATION.md` to the digit; if it does not, the report says so
  first).
- **B1, even split** over the four groups, 25% each.
- **B2, even split over the seven zones**, 1/7, 2/7, 2/7, 2/7 after grouping.
- **B3, league average, leave-one-park-out**: each park predicted by the
  pooled observed shares of the other seven, computed separately for each
  observed set. This is the fair opponent for a leave-one-out fit: both know
  the other seven parks' fouls and nothing about the held-out park.

The rule for **beats**, from `VALIDATION_PLAN.md`, is unchanged and is
applied to the held-out model against each reference on each observed set:
all three of (1) pooled total variation distance lower, (2) pooled mean
log-likelihood higher, (3) per-park total variation distance lower at at
least 5 of the 8 parks. One or two of the three is **mixed**; none is **does
not beat**.

The verdict words for the model as a whole (against B1 and B3) are the same
table as `VALIDATION_PLAN.md`: good / mixed: better than guessing, no better
than a constant / mixed / bad. They are reported for the held-out model so
the reader can set them beside the original model's "mixed".

## The decision

`BACK_FOUL_BASE_RATE` is changed **only if the held-out model beats M0 on the
full set** by the three-condition rule above. "Mixed" against M0 means the
model is left as it is. The camera-confirmed set is reported alongside and,
because it was fixed in advance as the selected set, does not veto the
decision: a rate fitted to where fouls land is expected to score worse
against a set that over-represents the backstop, and that is recorded here
so it cannot be read as a surprise later.

If the model is changed, the new value is `r*` fitted on **all eight parks**,
written into `foulball/trajectory.py` as a plain constant with its source
stated in the comment beside it. The leave-one-out figures, not the all-eight
figures, are what `VALIDATION.md` will quote as the measure of fit, because
the all-eight figures are in-sample by construction.

If the model is not changed, `CALIBRATION.md` reports the held-out results
and says the model is unchanged.

## What this fit cannot do

- It moves one knob. If the behind-plate excess and the dugout-to-pole
  shortfall have different causes (for example, forward fouls that do not
  carry far enough, which the back-foul rate cannot fix), the fit will split
  the difference and the residual pattern will show it. The report tabulates
  the residual per group at the fitted rate and names any parameter the
  pattern points at, without changing it.
- It cannot give the parks different rates, and does not try: one constant
  for all 31 parks is what the model has, and the data (67–113 balls a park,
  one day each) could not support per-park rates.
- It fits to four coarse bands from one day at each park in 2019, with the
  hitters of that day, against a model run with eighteen 2025–26 batters.
  Everything `VALIDATION.md` lists under "The limits of this test" applies to
  the fit as well.
- A fitted parameter is not a validated one. After this step, the only
  independent evidence about the rate will be the held-out comparisons here;
  the all-eight fit uses every observation the project has, and there is
  nothing left to test it on.

## Also reported, for information

- The share of the model's fouls landing behind the plane of the plate
  (`x < 0`), the share reaching a seat, and fouls per game, at 0.28 and at
  the fitted rate.
- Held-out results at the two sensitivity dugout settings (40, 110) and
  (60, 150), scored with the rate fitted at (50, 130). The fit itself is at
  (50, 130) only.
- Simulation noise: seeds 1–5 at 0.28 and at the all-eight fitted rate, as
  the range of pooled shares and pooled distances, so the gain (if any) can be
  set against the seed-to-seed spread `VALIDATION.md` measured
  (0.113–0.125 pooled distance at 0.28).

## Consequences for the tests, stated in advance

If the rate changes, these are the tests expected to move, and what is
allowed:

- `tests/test_golden_games.py` locks five games at seed 42 to the digit. A
  changed rate changes which balls go backward, so `total`, `mean_dist`,
  `mean_angle`, side counts, `no_section` and `top10` will all move. The
  baselines are relocked with the documented command, and the relock note
  states the new rate and the direction of every change.
- `tests/test_site.py` requires the committed site and its model cache to
  come from the current model. The site is rebuilt with `--refresh`.
- `tests/test_plausibility.py` requires the behind-home group at Yankee
  Stadium to be busier than the upper decks and at least 0.4 of the lower
  bowl, with a behind-home section in the top three; and
  `tests/test_distributions.py` requires 15–45% of fouls to land behind the
  plane of the plate. These encode the belief the constant was tuned to. If
  the fitted rate fails one of them, the test's threshold is the thing being
  tested by real data for the first time, and the report explains the change
  to the expectation rather than nudging the rate back.
- Any other test that moves is reported individually.

## Outputs

`calibrate_back_rate.py` runs the grid, the fits and the scoring and writes
`.cache/calibration_back_rate.json` plus text tables. `CALIBRATION.md`
reports the results in plain English: the eight held-out rates, the held-out
model against M0, B1, B2 and B3 on both observed sets, the all-eight fitted
rate, the residuals, the decision, and (if the rate changed) the new
`VALIDATION.md` wording.
