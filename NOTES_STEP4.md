# NOTES — Step 4: make the game backtest honest

Date: 2026-08-07. Branch `step-4`. Follows `NOTES.md` (Step 3).

All changes are in `game_backtest.py`, plus one field added to
`foulball/matchup_engine.py` and one stale claim removed from the web UI.

---

## 1. The side-split metric is deleted

It computed the model's 1B/3B share and compared it against this:

```python
# RHB fouls ~72% to 3B (28% to 1B), LHB fouls ~72% to 1B
actual_1b_est = (actual_r * 0.28 + actual_l * 0.72) / max(actual_total, 1) * 100
```

There is no observation anywhere in that line. Statcast records the batter's
handedness and nothing about where the foul went, so `actual_1b_est` is a
constant (72/28) applied to the lineup's handedness mix. The "error" it
reported was the distance between the model's side split and a hand-picked
assumption. A model that reproduced the assumption exactly would have scored
perfectly while being arbitrarily wrong, and a correct model would have been
marked down for disagreeing with a guess.

It was also the more misleading of the two fake metrics, because it scored
**well** — 4.4pp mean error — and that number had propagated into the product.
`webapp_v2.py` shipped `'mean_side_error': 4.4` in its methodology payload and
`templates/demo.html` rendered it as a validation badge reading "4.4pp side
error". Both are gone. The demo now states outright that section-level accuracy
is not validated.

`tests/test_game_backtest.py::TestSideSplitIsGone` fails if the keys reappear.

## 2. The per-batter correlation is really computed

It was `batter_corr = np.nan` under a comment explaining that predictions were
keyed by name and Statcast by ID. The join now happens on ID: `FoulBallEvent`
carries a `batter_id` (`matchup_engine.py`), copied from the profile the event
was simulated from, so predicted weights sum per player ID and join directly
against `all_fouls.groupby('batter')`.

Two details that decide whether the number means anything:

- **Batters who fouled nothing are scored as zero, not dropped.** They are the
  cases the model most often gets wrong; excluding them would flatter the
  correlation.
- **`safe_pearson` returns `None`, never a fabricated value.** Fewer than three
  batters, or no variance in either series, means there is no correlation to
  report. Silently emitting a number there is how `np.nan` became `4.4`-style
  UI copy in the first place.

Per game this is 18 points with counts of roughly 0–6 each, which is mostly
Poisson noise, so the aggregate report pools every batter-game across the
backtest and reports that as the headline, with the per-game median beside it.
Lineup coverage is reported too: fouls hit by pinch hitters and by anyone past
the ninth distinct batter of a half-inning are fouls the model was never asked
to predict.

## 3. New: predicted vs actual total fouls per game

The metric the file was missing. Each simulated event carries
`weight = fouls_per_pa * PA / sims`, so the weighted sum over both lineups is
the model's estimate of how many fouls the game produces — and Statcast logs
every one of them. Correlation (Pearson r across games) and mean absolute error
in fouls per game are both reported, plus median absolute error and signed bias.

Supporting numbers, so a miss can be attributed rather than just observed:

- **Assumed PA vs real PA.** The prediction assumes 4.0 PA per batter (72 per
  game). The real count comes from `at_bat_number`. A total that is off because
  the game went twelve innings is a different failure from one that is off
  because `fouls_per_pa` is wrong, and the report separates them by also
  printing predicted and actual fouls per PA.
- **Predicted fouls into modelled zones**, printed next to the validated total
  and explicitly labelled as having no Statcast counterpart. This is the number
  Step 3's `BACK_FOUL_BASE_RATE = 0.28` moves, and it is exactly the number
  nobody can check.

Panel 3 of `backtest_games.png` is now this scatter instead of the side-split
bars. (Its legend, and panel 2's, bound labels to artists in the wrong order —
`ax.legend([...])` assigns by artist order, so "Perfect" was labelling the
scatter. Both now label at the point of drawing.)

### What this does and does not validate

It validates the volume model: `fouls_per_pa` per batter, the 4.0 PA
assumption, and the pitch-mix weighting that decides how often a simulated
plate appearance produces a foul at all.

It does **not** validate the 0.28 back-foul rate, despite that rate being part
of Step 3's volume work. 0.28 governs *direction*, not *count* — a deflection
backward and a drive down the line are both one foul in the total. It moves
only "fouls into modelled zones", which has no observed counterpart. Step 3's
`NOTES.md` item 1 stands unchanged: 0.28 needs the Step 8 logging feature. The
total-foul check is the only external check available on volume, and this is
the honest limit of it.

## Counting rules

Two actual-foul frames now reach `compare_game`, and they are not
interchangeable:

- `tracked_fouls` (has `launch_speed`/`launch_angle`/`hit_distance_sc`) drives
  the distance metrics, because only these have distances. It is a biased
  subset — tracking is worst on exactly the weak contact that vanishes into the
  backstop.
- `all_fouls` (every foul bar foul tips) drives the counting metrics: game
  total, per-batter, pitch type. This is the same population `fouls_per_pa` was
  built from, so the comparison is like for like.

The pitch-type cosine moved from tracked to all fouls as part of this. It was
comparing every simulated foul against only the tracked ones.

## Tests

`tests/test_game_backtest.py`, 17 tests, no Statcast pull required —
`compare_game` runs on synthetic events and a minimal Statcast-shaped frame.
Full suite: 442 pass.

Covered: the weighted total equals the sum of event weights; the actual total
counts untracked fouls that the distance metrics can't see; per-batter
correlation matches a hand-computed Pearson r; zero-foul batters are kept; the
join survives two batters sharing a name; coverage catches a pinch hitter's
fouls; `batter_id` survives a real `predict_game_fouls` run; and the
side-split keys stay gone.

## Not done here

`game_backtest.py` has not been run end to end — there is no cached Statcast
data in `.cache/game_backtest/`, and a run needs a multi-minute pull of
Apr–Aug 2024. Producing the actual r and MAE is Step 6. The stale
`game_backtest` numbers still in `webapp_v2.py` (`median_ks: 0.194`,
`mean_pitch_cosine: 0.938`, `mean_dist_bias: 0.8`) predate the P1 and P2 fixes
and should be regenerated then; they are flagged with a comment in place.
