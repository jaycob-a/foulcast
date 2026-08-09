# NOTES — Steps 5 and 6: 2025-26 data refresh, and what the backtest actually says

Date: 2026-08-08. Branch `step-4`. Follows `NOTES_STEP4.md`.

One Statcast pull serves both steps: 2025-04-01 to 2026-08-08, regular season
only, 1,202,993 pitches, cached at
`.cache/game_backtest/statcast_2025-04-01_2026-08-08.parquet` (31 MB).
`rebuild_spray_profiles.py --parquet <path>` now reads it instead of pulling
again, and only the 25 columns anything downstream uses are kept — the full 119
would have cost several GB of RAM for no benefit.

---

## The headline: predicted vs actual total fouls per game

20 games from July 2026, one per park, profiles built only from data before
each game.

| | |
|---|---:|
| Correlation (Pearson r) | **-0.045** |
| Mean absolute error | **9.5 fouls/game** |
| Median absolute error | 6.8 fouls/game |
| Signed bias (pred - actual) | **-4.8 fouls/game** |
| Predicted, mean (sd) | 50.0 (1.9) |
| Actual, mean (sd) | 54.8 (11.4) |

**The correlation is zero, and the reason is visible in the standard
deviations.** Predicted totals span 46.4-54.2; actual totals span 37-77. The
model emits a nearly constant number while reality varies four times as much.
It is not mis-ranking games — it is barely ranking them at all.

That is a structural limit, not a tuning problem. A predicted total is
`sum(fouls_per_pa) x 4.0 PA` over 18 batters. Lineups differ, but averaging
nine hitters pulls every lineup toward the league mean of about 0.70 fouls/PA,
so the prediction cannot move much. Actual totals move because of game length
and per-plate-appearance randomness, neither of which the model models.

To check that this is the metric's ceiling rather than this sample's bad luck,
the same arithmetic was run over **all 371 July 2026 games** (no simulation,
just the volume model):

| | r | MAE | bias |
|---|---:|---:|---:|
| Volume model, 371 games | 0.071 | 9.6 | -4.5 |
| 20-game backtest (above) | -0.045 | 9.5 | -4.8 |

The 20-game figures are the 371-game figures plus noise. Nothing about the
sample is unlucky; this is what the model does.

For scale, on those same 371 games:

- Game length explains only 20% of the variance in foul count
  (`corr(PA, fouls) = 0.443`).
- A hypothetical model that **knew each game's true PA count** and applied the
  league foul rate would score r = 0.443, MAE 7.9. That is the ceiling for any
  approach built on rate x length.
On the same 20 games, predicting the July league mean of 55.2 fouls for every
game — a number available before any of them were played — scores **MAE 9.3,
bias +0.4**, against the model's 9.5 and -4.8.

That is the line that matters. On total foul count the model is currently beaten
by a constant, and the constant is simpler.

The bias decomposes cleanly. The model assumes 4.0 PA per batter, so 72 PA per
game; the real mean is 76.5. That alone accounts for about -2.7 of the -4.8.
Predicted fouls/PA (0.695) versus actual (0.716) accounts for most of the rest.
Both are fixable: the PA assumption could come from a team's actual pace, and
the fallback foul rate in `matchup_engine` is 0.80 against a measured league
mean of 0.70.

### What this does and does not establish

Validated: the per-plate-appearance foul rate is roughly right at the league
level (0.695 predicted vs 0.716 actual, a 3% error).

Not validated: anything game-specific. The model cannot yet tell a 40-foul game
from a 70-foul game.

Still not validated, and untouched by this run: which side a foul goes to, and
which section it lands in. Statcast records neither. The 0.28 back-foul rate
from Step 3 governs direction, not count, so no number here constrains it — see
`NOTES_STEP4.md`.

## Per-batter foul counts

Pooled over 360 batter-games: **r = 0.093**, MAE 1.67 fouls per batter per
game. Per-game r has median 0.066 and ranges -0.171 to 0.387. Predicted lineups
covered 91% of the fouls actually hit, the remaining 9% coming from pinch
hitters and batters past the ninth distinct one of a half-inning.

Weak but positive, and it is now a real number rather than the hardcoded
`np.nan` it was before Step 4. A single game gives 18 counts of 0-6 each, which
is mostly Poisson noise; pooling is what makes even this much signal visible.

## Distance distributions, and a correction to how they were measured

The first run reported a **+25.2 ft** mean distance error, against +0.8 ft in
the numbers the web app had been serving. Most of that gap was an artifact of
the comparison, not the model.

17.3% of tracked fouls in these 20 games carry `hit_distance_sc <= 5 ft`, and
those rows have a mean launch angle of **-36 degrees** — balls chopped straight
down into the dirt. `matchup_engine` discards any simulation landing under 5 ft
as "didn't go anywhere meaningful" (22 per lineup, under 1%), so the model
cannot produce that category at all. The backtest was scoring it against a
population one sixth of which it structurally excludes.

`MIN_DISTANCE_FT = 5.0` now applies the model's own floor to both sides or
neither, and the count excluded is printed rather than silently dropped.

Re-running with the floor applied symmetrically (161 of 932 tracked fouls
excluded, 17%):

| | before | after |
|---|---:|---:|
| Mean distance error | +25.2 ft | **-3.9 ft** |
| Median distance error | +25.9 ft | -8.9 ft |
| Median KS | 0.207 | 0.189 |
| Quantile MAE | 33.9 ft | 28.5 ft |

Total-foul and per-batter figures are untouched by this, as they should be.

The mean of -3.9 ft is the least useful number in that table. Per game the
distance error runs from **-32.2 ft to +42.3 ft**, so the small average is
cancellation, not accuracy. Quantile MAE of 28.5 ft is the honest measure of
typical error, and it is large.

The remaining caveat stands regardless: `hit_distance_sc` is itself
substantially a model output rather than a raw measurement (`AUDIT.md` P3), so
agreement here partly measures agreement between two drag models.

## Step 5: spray profiles rebuilt on 2025-26

`.cache/spray_profiles.json`: **497 profiles -> 698**. 263 players added, 62
dropped. Sample grew from 3 months of 2024 to 17 months across two seasons,
155,297 tracked fouls.

Retired players named in `AUDIT.md`: **Charlie Blackmon and David Peralta are
gone.** Martín Maldonado (last game 2025-07-30) and Justin Turner (2025-09-28)
remain, because the window the refresh was asked to cover includes 2025 and
both played in it.

Each profile now carries `last_game`, so staleness is inspectable instead of
inferred:

| last seen | profiles |
|---|---:|
| 2026 (active) | 580 |
| 2025 only | 118 |

Keeping the 118 is harmless — profiles are keyed by player ID and are only read
when that player appears in a lineup — but the field makes it possible to
filter them if that is ever wanted.

League mean is 0.704 fouls/PA (median 0.702, p10 0.571, p90 0.832). The
fallback in `matchup_engine` for batters with no data is **0.80**, which is
14% above the measured league mean and should come down.

## Venue registry review

Checked against MLB's own schedule rather than from memory: every regular-season
home game in 2026, grouped by venue.

**Rays — correct, and the `AUDIT.md` concern is resolved.** They played all 74
of their 2025 home games at George M. Steinbrenner Field after the hurricane,
and are back at Tropicana Field for all 61 home games in 2026. The registry's
`tropicana_field` is right for the current season. Not verifiable from schedule
data: whether the post-repair seating bowl matches the geometry in
`stadium.py`, which is documented as the 1990 layout. That needs a seating-chart
check before Tropicana numbers are trusted.

**Athletics — right venue, wrong key, and a real gap.** They played all 75 home
games at Sutter Health Park in 2025. In 2026 they have played **51 at Sutter
Health Park and 6 at Las Vegas Ballpark**. The registry maps them to Sutter
Health Park, which is correct for the large majority, but the 6 Las Vegas games
are simulated against the wrong park. The registry key is still
`oakland_coliseum`, three years after they left Oakland; renaming it touches
`TEAM_STADIUM_MAP`, golden fixtures and any saved URLs, so it is flagged, not
done.

**Two Statcast abbreviation changes that were silently deleting games.** From
2025 Statcast calls the Athletics `ATH` and Arizona `AZ`. `_SC_ABBREV_MAP` had
only `OAK` and `ARI`, and `select_games` skips any game whose home team it
cannot map — without a message. Every Athletics and Diamondbacks home game was
being dropped from the sample. Both codes are added, the old ones kept for
pre-2025 pulls, and unmapped teams now print a warning. Both clubs appear in the
20-game sample as a result.

**Neutral-site games.** 2026 has a handful: Mexico City (Diamondbacks x2),
Williamsport (Brewers x1), Field of Dreams (Twins x1). Statcast still labels one
club the home team, so the backtest would have simulated them against that
club's park. `neutral_site_game_pks()` drops any game played somewhere other
than the home team's modal venue for the season — robust to sponsorship renames,
which matters because the Dodgers' park is listed in 2026 as "UNIQLO Field at
Dodger Stadium". None fell in the July sample, but the guard is in place.

Everything else matches: 30 of 30 clubs map to a park with geometry, and no
registry key is orphaned.

## Web app accuracy claims

The `game_backtest` block in `webapp_v2.py` was regenerated from this run rather
than removed, because it can be stated honestly — but the copy around it could
not stay. It read "Validated against 20 real MLB games", and the r = -0.045
result does not support the word "validated" for anything game-specific.

| field | old (Aug 2024, pre-P1/P2) | new (July 2026) |
|---|---:|---:|
| `games` | 20 | 20 |
| `median_ks` | 0.194 | 0.189 |
| `mean_pitch_cosine` | 0.938 | 0.920 |
| `mean_dist_bias` | +0.8 ft | -3.9 ft |
| `mean_side_error` | 4.4 pp | **deleted** (Step 4) |
| `total_foul_r` | — | -0.045 |
| `total_foul_mae` | — | 9.5 |
| `dist_quantile_mae` | — | 28.5 ft |

The demo panel now leads with what the run actually showed: totals land within
about 9.5 fouls of a real game but do not track game-to-game variation, and
section-level accuracy is unvalidated.

Two claims elsewhere were left alone but should be dealt with in the `PITCH.md`
rewrite: the `backtest` block above it still serves r = 0.986 over 19,558 fouls,
which `AUDIT.md` P3 explains is close to guaranteed by construction. One
related fix was made, because it was not merely stale but wrong: the page footer
read "Validated against 20 real MLB games with r=0.986 physics correlation",
attributing the per-foul trajectory correlation to the 20-game backtest. Those
are two different tests and the 20-game run has never produced r = 0.986.

## Least confident

Ordered by how much they could change a conclusion above.

**1. The 5 ft distance floor moved the headline distance number by 29 ft.** It
is defensible — it is the model's own constant, applied to both sides — but it
is still a judgment call I made after seeing that the unfiltered number looked
bad, which is exactly the shape of a result worth distrusting. The raw figure
(+25.2 ft) and the filtered one (-3.9 ft) are both in this document for that
reason. What is not a judgment call: 17% of tracked fouls have a mean launch
angle of -36 degrees, and the model cannot produce those at all.

**2. The distance metric is weakest exactly where Step 3 changed the model.**
Statcast tracks 85% of fouls (932 of 1,096 here), and the missing 15% are
disproportionately the weak backstop contact that the straight-back foul work
was about. So the distribution being compared systematically under-samples the
new behaviour. A model that got backward fouls badly wrong could still score
well here.

**3. "No lookahead" is not literally true.** `build_profiles_for_game` builds
from pre-game data only, but `enrich_with_spray_profiles` then overwrites
EV, LA and pull tendency from `spray_profiles.json`, which spans the whole
17-month window including the game being predicted. Each game is roughly
1/500th of that sample, so the contamination is small, and it does not touch
`fouls_per_pa` — except for 3 of 360 batter slots (0.8%) that had under 20
pre-game PAs and fell back to the cached full-window rate. Small, but the
docstring overstates the guarantee.

**4. The lineup is an approximation.** "The lineup" is the first nine distinct
batters of each half-inning. Pinch hitters and everyone past the ninth are
outside it, and they hit 9% of the fouls in these games. That biases predicted
totals slightly low, on top of the 72-vs-76.5 PA gap.

**5. The 371-game replication is weaker evidence than it looks.** It confirms
the near-zero correlation is structural rather than a 20-game fluke, but it uses
full-window profiles (more lookahead than the backtest) and skips the physics
entirely — it is the volume arithmetic alone. It bounds the volume model, not
the simulation.

**6. Tropicana Field geometry is unverified after the repairs.** The Rays are
confirmed back there for 2026, but `stadium.py` documents the 1990 seating
layout and the park was rebuilt after hurricane damage. No Tropicana game was in
this sample, so nothing here would have caught a mismatch.

**7. The number closest to the product is still the least examined.** 38.6
fouls per game predicted to reach a modelled zone — 77% of all fouls — has no
observed counterpart anywhere in this run. It sits inside `PITCH.md`'s 30-40
band, which is reassuring and is not evidence. It also still counts balls
arriving at `HOME-F` as reaching seats when at Yankee Stadium that area is
behind the backstop screen (`NOTES.md` item 2).
