# NOTES — Step 7: all 30 parks, heat-mapped, plus the Athletics venue gap

Date: 2026-08-09. Branch `step-7`. Follows `NOTES_STEP5_6.md`.

New files: `park_sweep.py` (runs a standard lineup through every park, renders
the maps, computes the flags), `park_coverage.py` (pure-geometry coverage
diagnostic, no simulation), `tests/test_park_sweep.py`.

Outputs land in `.cache/park_sweep/`: `park_heatmaps.html` and
`park_sweep.json`.

---

## How the maps are drawn, and why not the obvious way

The engine works in a per-side polar frame: angle 0 is down *that side's* foul
line, 90 is square to the plate, 135 is dead behind the catcher. The maps
unroll that onto a real plan view by reading the angle as a bearing measured
away from fair territory — `theta = ±(45 + angle)` from the centre-field axis.
At angle 135 both sides land on `theta = ±180`, which is the same point, so the
backstop closes up instead of overlapping itself. `tests/test_park_sweep.py`
pins this: foul lines 90 degrees apart, the two sides mirrored, distance from
home preserved, and both sides converging dead behind the plate.

What is shaded is **not** the raw section rectangles from `stadium.py`. Those
overlap heavily — at Yankee Stadium six sections claim the ground at 15 degrees
— and `exposed_bands()` resolves the overlap before anything is matched, giving
the lowest deck the ground. Drawing the raw rectangles would show a park the
engine never uses. The maps draw the resolved partition, per side, at the angle
resolution the partition actually changes at.

Red dots are simulated fouls that matched no section at all. They are the point
of the picture: the shading shows what the model credits, the dots show what it
loses.

---

## The single biggest finding: a third of every park's fouls land nowhere

`park_coverage.py` replays **one** landing sample — generated once, at Citi
Field's air, and held constant — through all 31 park geometries. Physics is
identical across the rows, so every difference is the zone layout.

| | capture rate |
|---|---:|
| median park | **65.5%** |
| best (Coors, Rogers Centre) | 67.0% |
| Fenway Park | **55.3%** |
| Sutter Health Park | **45.1%** |
| Las Vegas Ballpark | **41.9%** |

**About a third of all simulated fouls match no section at even a healthy
park.** That is not a Fenway problem or an Oakland problem; it is the baseline.
`NOTES.md` item 5 recorded a version of this — "137 events per half-game come
down past 300 ft and match nothing" — but had the magnitude and the cause
wrong. The losses are mostly *short*, not long.

Every uncaught ball falls into exactly one of three buckets, and the third is
empty everywhere:

| bucket | meaning | median park |
|---|---|---:|
| short | came down in front of where the bowl starts at that angle | 85% |
| past | carried beyond the outermost deck at that angle | 15% |
| over | inside the covered span but still matched nothing | **0%** |

`over = 0` at all 31 parks is a genuinely reassuring result: there are no
interior holes. `coverage_gaps()` confirms it independently — no park has an
unowned band *between* two owned bands, on either side, at any sampled angle.
Whatever is wrong with these parks, balls are not falling through the middle of
the bowl.

A large "short" fraction is **not automatically a bug.** A foul that comes down
25 feet from the plate is on the field, and the model is right to credit it to
nobody. What is a bug is the down-the-line wedge: at angles under about 25
degrees most parks have no section starting before 85–100 ft, because the only
candidate there is the dugout-level box that begins that far out. Balls landing
40 ft down the line at seat height are on the field at some parks and in the
first row at others, and the geometry cannot currently tell those cases apart.

The "past" fraction is where the outlier parks separate. It tracks one number
almost exactly — the mean outermost owned distance:

| park | mean bowl back | past% | capture |
|---|---:|---:|---:|
| Las Vegas Ballpark | 113 ft | 54% | 41.9% |
| Sutter Health Park | 123 ft | 49% | 45.1% |
| Fenway Park | 145 ft | 36% | 55.3% |
| typical park | 155–180 ft | 10–20% | 64–67% |
| Yankee Stadium | 179 ft | 14% | 65.2% |

---

## Fenway (Step 3 flagged it at 28.1)

Two separate problems, and the smaller one is the one that looks deliberate.

**1. A blanket 0.85 scale is applied to the wrong end of the bowl.**
`fenway_park()` multiplies *both* `distance_min` and `distance_max` of every
section by 0.85, with the comment "compact foul territory." Compact foul
territory means the stands are closer to the *field* — the front of the bowl
moves in. It does not mean the seating bowl is 15% shallower. Shrinking
`distance_max` moves the back of the stands toward the plate, so balls that
should land in the deep seats fly over the entire park.

Measured on the shared sample:

| Fenway variant | bowl front | bowl back | capture |
|---|---:|---:|---:|
| raw sections, unscaled | 59.7 ft | 170.6 ft | 58.6% |
| **shipped: 0.85 on both ends** | 50.8 ft | 145.0 ft | **55.3%** |
| 0.85 on `distance_min` only | 50.8 ft | 170.6 ft | 61.0% |
| 0.85 on `distance_max` only | 59.7 ft | 145.0 ft | 52.8% |

The scale pulls the front in by 9 ft, which is the intended effect, and the
back in by 26 ft, which is not. Applying it only to `distance_min` — the
change the comment describes — recovers 5.8 points of capture.

**2. The raw table already has Fenway's stands too far out.** Even unscaled,
Fenway's bowl front averages 59.7 ft against Citi Field's 54.3 and the 30-park
norm of about 53. The park whose defining feature is the smallest foul
territory in baseball is entered as having the *deepest* front-of-bowl of any
park in the file. The 0.85 scale looks like it was added to compensate for
that, and it compensates in the right direction by the wrong mechanism.

Fixing this properly means the real section distances, not another multiplier.

## Oakland / Sutter Health Park (Step 3 flagged it at 22.7)

**Sutter Health has no lower deck.** It carries 8 sections across 2 levels —
`field` and `upper` — where every full-size park has 11 to 16 across 3 or 4.
The missing level is `lower` (`*-LB1`), which at other parks spans roughly
40–190 ft and is what carries coverage outward down the lines. Without it the
mean outermost owned distance is 123 ft against a 155–180 ft norm, and 49% of
everything the lineup fouls carries past the last deck.

Behind the plate it is worse in a way that matters more after Step 3. Sutter
Health's backstop group is `HOME-F` (40–80 ft) and `HOME-U` (35–100 ft), so
coverage dead behind the plate stops at 100 ft. Yankee Stadium has four
behind-plate sections reaching 140 ft. Step 3 made 26% of all fouls land behind
the plate; at Sutter Health every one of them past 100 ft disappears.

**This is partly real.** Sutter Health is a Triple-A park; it genuinely has
less seating depth than Yankee Stadium, and a foul carrying 200 ft into foul
territory there really does leave the stands. Some of the 22.7 is a true park
effect. But 8 sections and 2 levels is also the coarsest table in the file, and
a park modelled at half the resolution of its neighbours will under-report for
reasons that have nothing to do with the park.

I did not rewrite either park's geometry. Doing that credibly needs real
seating charts; doing it from memory would put invented numbers into the one
file that everything else is measured against, which is the failure mode this
project's audit trail exists to prevent.

---

## The 30-park comparison table

Standard lineup, seed 42, 400 sims/batter, both lineups summed. Totals are
fouls landing in a modelled zone per game.

| | fouls into stands |
|---|---:|
| median (31 parks) | **32.8** |
| 28 parks fall between | 32.0 and 33.7 |
| Fenway Park | 28.0 |
| Sutter Health Park | 22.7 |
| Las Vegas Ballpark | 20.8 |

The tightness of the main group is itself worth noting: 28 of 31 parks land
within 1.7 fouls of each other. Park geometry that varies by 60 feet of bowl
depth moves the total by under 2 fouls a game, because the behind-plate group —
which is nearly identical at every park — dominates. Real parks do not produce
foul counts that uniform, and the reason the model's do is the same reason the
Step 6 backtest found r = -0.045: the volume model has almost no dynamic range.

Reproducing the Step 3 figures: `oakland_coliseum` 22.7 (was 22.7) and
`fenway_park` 28.0 (was 28.1). Both reproduce, so the Step 3 flags were real
and are not artefacts of the P1/P2 fixes.

## What the maps do not show

Three of the four things worth flagging came back clean, and the clean results
are as useful as the flags:

**No hard edges.** The check is per-square-foot foul density across shared zone
boundaries, computed from the area each zone actually owns in the resolved
partition rather than its raw rectangle. No boundary at any park reaches the
20x threshold. Density varies smoothly across the bowl at all 31 parks.

**No unexplained asymmetry — at any park.** The 1B share of sided fouls is
between 51.50% and 51.97% at all 31 parks, against a seed-to-seed sampling band
of 1.19 pp. The spread across parks (0.47 pp) is a third of the noise on a
single measurement, so park geometry contributes nothing measurable to the
left/right split. That is expected and now verified:
`tests/test_park_sweep.py::TestMirrorDetection` checks all 31 parks and every
one is exactly mirror-symmetric, to the last decimal, in all six geometry
parameters.

The 1.6 pp lean toward 1B is the lineup, not the parks. The standard lineup is
9 left-handed and 9 right-handed batters, but the left-handers foul more: their
`fouls_per_pa` sums to 7.09 against 6.64: 51.6% of expected fouls come from
left-handed bats. At the model's measured 71.6% pull rate that predicts a 50.7%
1B share, against 51.6% observed — inside the 1.19 pp band.

**Dead zones: only two, and they are the same two sections at two parks.**
`1B-UR` / `3B-UR` at Yankee Stadium and `1B-UB` / `3B-UB` at Fenway receive
exactly zero. Both are upper decks whose distance range lies entirely inside a
lower deck's, so `exposed_bands()` correctly gives the ground to the deck below
and they own no area at all. They are not under-served; they are unreachable by
construction. A ball cannot come down on an upper deck at a horizontal position
where a lower deck sits beneath it, so this is the geometry working as designed
— but a section that can never be hit should not be in the table advertising
seats.

## One real geometry bug, found by comparing parks rather than inspecting them

Section IDs are a shared vocabulary across `stadium.py`, so the same ID should
mean roughly the same place everywhere. `section_convention_audit()` checks
that, and it found a genuine error that no single park's map would reveal:

**`1B-UB` / `3B-UB` at Yankee Stadium span angles 10–55. At 28 of 31 parks they
span 10–45.**

The effect is measurable and specific. Yankee Stadium is the only park whose
handedness swing falls outside the fleet range — 40.77 pp against a median of
43.4 and a spread of 42.6–44.6 everywhere else. Setting `UB` back to 10–45
moves it to **43.36**, the fleet median almost exactly. The extra 10 degrees put
an upper deck into the 45–55 wedge, which is opposite-field territory, so it
captures opposite-field fouls as sided and dilutes the pull-side share.

**Applied 2026-08-09.** `angle_max` is now 45 on both `1B-UB` and `3B-UB`.
Confirmed after the change:

| | before | after | fleet |
|---|---:|---:|---:|
| handedness swing | 40.77 pp | **43.36 pp** | median 43.38 |
| 1B share of sided fouls | 51.80% | **51.61%** | median 51.61% |
| total into stands | 33.0 | 32.1 | median 32.7 |
| rank by swing (1 = lowest of 31) | 1 | **15** | — |

Yankee goes from the extreme outlier to the middle of the pack, and the
fleet-wide swing range tightens from 40.77–44.63 to 42.59–44.63.

Two golden baselines were relocked (`yanks_vs_cole_yankee`,
`sox_vs_cortes_yankee`). The relock is the reassuring kind: `total`,
`mean_dist`, `mean_angle`, `n_1b` and `n_3b` are all byte-identical, which is
the signature of a change that touched section assignment and nothing else.
What moved is `no_section` (921 -> 957 and 878 -> 916) and a rank swap between
`*-FB1` and `*-LB1`, which were already adjacent.

The cost is honest and small: removing a deck from the 45–55 wedge means about
36 more simulated fouls per run match nothing, so Yankee's total drops 0.9 and
its unmatched share rises about a point. Yankee is now slightly below the fleet
median on total rather than slightly above. That is the right trade — the
alternative is a park keeping an inflated total by claiming balls in a wedge
where 28 other parks have no deck.

Two smaller convention breaks, both flagged and neither with a measured effect:
`HOME-U` is angle 20–55 at Yankee against 50–90 at 28 parks, and `1B-DUG` is
0–30 at Fenway against 0–25 elsewhere. The Yankee `HOME-U` case is inert —
patching it to 50–90 changes the swing by 0.00 pp, because that section sits at
35–70 ft with lower decks under all of it and receives 0.06 fouls a game.

---

## Handedness: is the 1B/3B split a real effect or a rounding error?

Every park run twice more, with the same 18 batters and `batter_side` forced to
`R` in one run and `L` in the other. Exit velocity, launch angle, per-pitch foul
rates, `fouls_per_pa`, plate location and pull tendency are all untouched, so
the direction model is the only thing that differs.
`tests/test_park_sweep.py::TestHandednessLineups` checks that field by field,
and checks that the module-level profiles are not mutated in the process.

**It is a real effect in the model, and it is enormous.**

| | 1B share of sided fouls |
|---|---:|
| all-RHB lineup | **28.3%** (sd across parks 0.30) |
| all-LHB lineup | **71.6%** (sd across parks 0.30) |
| swing | **43.4 pp** (range 40.8–44.6) |
| seed-to-seed sampling band on this statistic | 1.19 pp (1 sd) |

43 percentage points against a 1.2 pp noise band is roughly 36 sigma. Whatever
else is uncertain, this is not a rounding error, and the answer does not depend
on the park: the swing varies by ±1 pp across 31 parks with wildly different
geometry. Total fouls into the stands is unchanged between the two runs at every
park — handedness moves *where*, not *how many*, exactly as it should.

The model is also almost perfectly mirror-symmetric under the flip: the midpoint
of the two shares is 49.95%, against 50.00% for a perfectly symmetric model.

### The part that matters more than the number

**28.3 / 71.6 is the hardcoded constant read back out.** `trajectory.py` sets

```python
base_pull_pct = 0.72 + pull_factor * 0.10   # 62-82% to pull side
```

and `pull_factor` is zero for every batter in the standard lineup, because all
eighteen carry the default `fair_pull_pct = 50.0`. So the model was told 72% of
fouls go to the pull side, and it reports 71.6%. The launch-angle and
exit-velocity modifiers and the back-foul washout very nearly cancel.

This is worth stating plainly because of what Step 4 deleted. The side-split
metric was removed because its "actual" value was `actual_r * 0.28 +
actual_l * 0.72` — a hand-picked 72/28 assumption with no observation behind it.
**The model's own directional constant is the same 0.72.** The metric was
scored against the model's own prior and unsurprisingly scored well; deleting
the metric was right, and it did not touch the assumption, which is still doing
all the work.

So: lineup handedness is a real effect *in the model*, of a size set entirely by
one unvalidated constant. Whether 43 pp is the real-world number is exactly as
unknown as it was before this run. Statcast does not record which side a foul
lands on, so nothing in this repository can currently distinguish a true 43 pp
swing from a true 20 pp one. That is the Step 8 logging feature's job, and this
run sharpens why it matters: the constant it would calibrate is not a detail,
it is the single largest lever on the model's directional output.

A second consequence, visible only because every batter has the default: **the
model has no per-batter directional variation at all.** `fair_pull_pct` is
50.0 for all 18 hardcoded profiles, so two right-handers with very different
real spray tendencies produce identical side distributions. The rebuilt
`spray_profiles.json` from Step 5 does carry real per-batter pull data, so the
live path is better off than this test lineup — but any conclusion drawn from
`YANKEES_2024_PROFILES` or `RED_SOX_2024_PROFILES` about direction is a
conclusion about one constant.

### How handedness compares to every other directional input

The rebuilt `spray_profiles.json` carries real per-batter pull tendency for all
698 players (`fair_pull_pct`: median 58.5, sd 6.6, range 34.4–77.3), so the
live path does vary by batter. It just varies far less than handedness does.
`pull_factor` is clipped to ±1 and scaled by 0.10, so the whole league maps onto
a narrow band of pull share:

| directional input | effect on pull share |
|---|---:|
| handedness (R vs L) | **43.4 pp** |
| batter pull tendency, p10 to p90 of the league | 3.3 pp |
| batter pull tendency, most extreme to most extreme | 8.6 pp |

Handedness is 13x the p10–p90 spread of every other per-batter directional
signal combined. If a fan wants to know which side of the park to sit on, the
only input that matters in this model is how many left-handers are in the
lineup. Everything else is inside the noise of a single game.

That is a clean, sellable statement — and it rests entirely on `0.72`.

---

## The Athletics venue gap

`NOTES_STEP5_6.md` flagged it: the Athletics have 51 of their 2026 home dates at
Sutter Health Park and 6 at Las Vegas Ballpark, and `TEAM_STADIUM_MAP` is keyed
by club alone, so all 57 simulate against Sutter Health.

**A second home park is not a neutral site, and the existing guard was
discarding these games entirely.** `neutral_site_game_pks()` drops any game
played away from the home team's modal venue. Sutter Health is the modal venue
with 51 dates, so all six Las Vegas games matched that rule. Before this change
they were not being simulated against the wrong park in the backtest — they were
being deleted from the sample, silently, by the guard added to catch Mexico City
and the Little League Classic. The web app's live path *was* using the wrong
park.

The fix keeps the club-keyed map and adds a venue-aware layer over it:

- `ALTERNATE_HOME_VENUES` in `mlb_api.py`, keyed by `(team_id, normalized venue
  substring)` so a venue string only redirects for the club it belongs to.
  Matching is on a normalized substring, for the same reason
  `neutral_site_game_pks` compares modal venues: MLB lists the Dodgers' park as
  "UNIQLO Field at Dodger Stadium" in 2026, and sponsor prefixes move.
- `resolve_stadium_key(home_id, venue_name)` prefers the venue actually played
  at and falls back to the club's primary park when the venue is unknown or is
  that primary park under any name. Callers holding only two team IDs — a
  hypothetical matchup — omit the venue and get the old behaviour exactly.
- `neutral_site_game_pks()` no longer drops a game whose venue resolves to a
  park the model has geometry for.
- `select_games()` resolves per game via a new `game_venues()` helper, and
  records the venue on each selected game.
- `webapp_v2._run_prediction()` takes an optional `venue_name`; the live
  endpoint passes the venue from the game feed. `get_todays_games()` resolves
  it for every scheduled game, which fixes `predict.py` too.

The registry key stays `oakland_coliseum`. Renaming it touches `TEAM_STADIUM_MAP`,
the golden fixtures and any saved URLs, and it is orthogonal to this bug — it is
still flagged, still not done, and now carries a comment saying so.

### Las Vegas Ballpark geometry — read this before trusting its numbers

Field dimensions (328/415/328) and altitude (~2,030 ft) are real. **The seating
geometry is not.** It is Sutter Health Park's deck structure scaled by 0.92 for
the capacity difference (~10,000 against 14,000), because both are two-level
Triple-A parks. No published seating chart went into it.

That puts Las Vegas in the same evidence class as the Tropicana Field caveat in
`NOTES_STEP5_6.md`, and it inherits Sutter Health's defects wholesale: 8
sections, 2 levels, and the worst capture rate of any park in the file at 41.9%.
Its 20.8 fouls per game is the lowest total of the 31 and should be read as "a
park shaped like Sutter Health, only smaller" rather than as a measurement of
Las Vegas Ballpark. Six games a season now route to a park whose numbers are
approximately as good as the park they were previously — wrongly — routed to.
The venue plumbing is correct; the geometry it points at is a placeholder.

Tests: `tests/test_stadium_geometry.py::TestSecondHomeParks`, 8 tests covering
the primary-park fallback, both Athletics venues, a sponsorship rename, the
"a venue must not hijack another club's park" case, an unknown venue, and a
check that the two Athletics parks are actually different objects.

`test_all_30_stadiums_build` asserted `len(STADIUMS) == 30` and would now fail
for the right reason. It is replaced by three tests that check what actually
matters: every factory builds, all 30 *clubs* map to a park with geometry, and
no stadium key is orphaned. `/api/stadiums`'s test did the same thing and got
the same treatment.

---

## Tests

`tests/test_park_sweep.py` — 175 tests, no simulation, sub-second. The sweep's
conclusions rest on pure-geometry helpers, so those are pinned directly rather
than inferred from Monte Carlo output.

- The plan-view mapping: foul lines 90 degrees apart, the two sides mirrored
  about the centre line, distance from home preserved, both sides converging
  dead behind the plate, and down-the-line drawn toward the outfield. If this
  is wrong every map is wrong in a way that still looks plausible.
- `owned_bands()` per park: bands never overlap, only same-side and HOME
  sections are ever offered, and something owns the ground past 90 degrees at
  every park — a park with no behind-plate coverage would silently discard the
  26% of fouls Step 3 put there.
- `zone_owned_area()` against the closed-form annulus, and the case that
  matters: a section hidden under a lower deck is credited zero area, so the
  density used by the hard-edge check does not make buried upper decks look
  artificially sparse.
- `geometry_mirror_delta()` on all 31 parks (every one exactly symmetric),
  plus injected asymmetry and an injected unpaired section.
- `coverage_gaps()` on all 31 parks: no interior holes.
- The handedness lineups change handedness and nothing else, field by field,
  and do not mutate the module-level profiles.

Full suite: **638 pass** (442 before this step).

---

## What I did not do

**I did not fix any park's geometry.** Step 7's brief in `NEXT_STEPS.md` says to
fix the flagged parks; the request for this run was to flag them. That split
suits the evidence: for Fenway and Sutter Health the honest fix is real section
distances from real seating charts, and generating those from memory would put
invented numbers into the file every other measurement is taken against. The
Yankee `UB` angle range is the one exception where the fix is unambiguous and
one line, and it is left as the owner's call for the reason given above.

**I did not add outfield foul-corner sections.** `NOTES.md` item 5 is still
open, and the coverage numbers here size it: 15% of every park's uncaught fouls
carry past the last modelled deck.

---

## Least confident

Ordered by how much they could change a conclusion above.

**1. Two of the three outlier parks are outliers because I have no data for
them.** Sutter Health's 8-section table and Las Vegas's scaled copy of it are
the two coarsest geometries in the file, and they produce the two lowest totals.
I have argued the low totals are partly a modelling artefact and partly a real
small-park effect, but I cannot separate those two without a seating chart. It
is entirely possible that Sutter Health's true answer is close to 22.7 and the
"defect" I described is the model correctly representing a small park. The
Fenway case is stronger, because there the mechanism is visible in the code
rather than inferred from a section count.

**2. The capture-rate comparison holds air constant but not the landing
distribution's dependence on it.** `park_coverage.py` generates one sample at
Citi Field's altitude and temperature and replays it everywhere, which is what
makes the rows comparable. But Coors Field really is a mile up, and its real
landing distribution is longer than the one it was scored on. The 67.0% capture
I report for Coors is "Coors geometry against sea-level physics," not Coors.
For the outlier diagnosis this is the right control; for any absolute claim
about a specific park it is not.

**3. "No hard edges" is a statement about a threshold I chose.** The check is
per-square-foot density across shared boundaries with a 20x cutoff, a 500 sq ft
minimum area, and a 0.05-fouls floor. Nothing at any park came close to 20x, so
the conclusion is not sensitive at the margin — but I picked 20x before seeing
the distribution and did not go back and tighten it, which I should say out
loud. The underlying density ratios are in `park_sweep.json` if a different bar
is wanted.

**4. The heat maps show ownership, not landing probability.** Each zone is
shaded by its total expected fouls, as asked, and a zone's total depends on how
much ground it owns as much as on how the balls fall. A large pale zone and a
small dark zone can represent the same physical density. The red unmatched-ball
dots are the only part of the picture drawn from actual landings. Read the
shading as "what the model credits here" and the dots as "what it drops."

**5. The 43 pp handedness swing is a property of one constant, and I have
checked it is not a property of anything else.** What I have not checked is
whether the constant is right, because nothing available can check it. If the
true pull rate is 0.60 rather than 0.72 the swing is roughly 20 pp instead of
43, and every directional claim in the product scales with it. The number is
robust *given the model*; the model is unvalidated on exactly this axis.

**6. The Yankee `UB` finding rests on one seed.** 40.77 to 43.36 pp from a
single geometry change at seed 42, against a seed-to-seed band of 1.19 pp on
the underlying share. The move is about twice the noise and it lands exactly on
the fleet median, which is persuasive, but I did not repeat it across seeds. My
first hypothesis for that outlier — Yankee's odd `HOME-U` angle range — was
wrong, and I only found that out by testing it, which is a reason to hold the
second hypothesis less tightly than the clean number suggests.

**7. The standard lineup is 2024 hardcoded profiles, not the rebuilt Step 5
data.** It was chosen to stay comparable with the Step 3 park sweep and the
`BEFORE.md` baseline, and that comparability is real — Fenway 28.0 against 28.1,
Sutter Health 22.7 against 22.7. But it means the whole sweep runs on 18 batters
with identical default pull tendency, which is why the handedness experiment
isolates so cleanly and also why it cannot say anything about how real lineups
differ from each other.

**8. Nothing here validates a single section number.** This step checked that
the geometry is internally coherent — no overlaps, no interior holes, symmetric,
no hard edges — and coherence is not accuracy. Every caveat in `AUDIT.md` about
section-level accuracy being unvalidated survives this run untouched. The maps
make it much easier to see *what* the model claims; they add no evidence that
any of it is right.

---

## Final flag summary

31 parks, seed 42, 400 sims/batter, **after** the Yankee `UB` fix.
**4 parks flagged, 27 clean.** Fleet median total 32.7.

| park | flags |
|---|---|
| Las Vegas Ballpark | outlier total (20.8, robust z -25.9); 59% unmatched vs fleet 35% |
| Sutter Health Park | outlier total (22.7, robust z -21.8); 55% unmatched vs fleet 35% |
| Fenway Park | outlier total (28.0, robust z -10.3); 45% unmatched vs fleet 35%; 2 dead zones |
| Yankee Stadium | 2 dead zones (`1B-UR`, `3B-UR`) |

Yankee's dead zones survive the `UB` fix and are unrelated to it: `1B-UR` and
`3B-UR` are upper decks whose distance range lies entirely inside a lower
deck's, so `exposed_bands()` correctly gives the ground below them away and
they own no area at any angle. They cannot be hit by construction. Yankee no
longer draws an unmatched flag — 36% against a fleet median of 35%.

Zero parks flagged for hard edges. Zero flagged for asymmetry. No park has an
angular blind spot — every angle from 0 to 180 owns at least one band on both
sides — and no park has an interior radial hole. The white space on the maps is
real dead area in front of the bowl and beyond the last deck, not a gap in the
drawing.

Fleet-level, from `section_convention_audit()`:

```
1B/3B-UB  is 10-55 at yankee_stadium          but 10-45 at 28/31 parks
1B/3B-UB  is 10-50 at wrigley_field, coors    but 10-45 at 28/31 parks
1B/3B-DUG is  0-30 at fenway_park             but  0-25 at 30/31 parks
HOME-U    is 20-55 at yankee_stadium          but 50-90 at 28/31 parks
HOME-U    is 45-90 at wrigley_field, coors    but 50-90 at 28/31 parks
```

Only the first has a measured effect (Yankee's handedness swing, 40.77 -> 43.36
when corrected). The Yankee `HOME-U` case is inert. The rest are untested
5-degree differences.

---

## Where the unmatched third actually goes

`park_coverage.py` now reports the loss breakdown in fouls per game rather than
percentages, and subdivides both buckets — because neither bucket means one
thing.

At the average park, out of **50.7** fouls the lineup produces per game:

| | fouls/game | share of losses |
|---|---:|---:|
| landed in a modelled zone | 31.9 | — |
| **short** of the bowl front | **14.8** | **79%** |
| — unambiguously on the field (>15 ft short) | 12.9 | 69% |
| — within 15 ft of the bowl front | 1.8 | 10% |
| **past** the last deck | **3.9** | **21%** |
| — still inside 330 ft of the plate | 2.9 | 15% |
| — beyond 330 ft | 1.0 | 5% |

**The short bucket is mostly correct.** 12.9 fouls a game come down well in
front of where the stands begin — that is foul ground, and crediting them to no
section is the right answer. The 1.8 that land within 15 ft of the bowl front
are the ones whose answer depends on the bowl front being in the right place,
which is exactly what is wrong at Fenway.

**The past bucket is mostly *not* balls leaving the stadium.** Only 1.0 foul per
game — 2% of all fouls, 5% of the losses — comes down beyond 330 ft, past where
any real park has seating. The other 2.9 land between the last modelled deck
and the foul poles, and every real park has stands there. That is `NOTES.md`
item 5 — no park models the outfield foul-corner sections — and it is now
sized: about 2.9 fouls per game per park.

### Are the trajectories carrying too far?

Barely, and not enough to matter here. The model's landing distances against
159,740 tracked Statcast fouls from the cached 2025–26 pull:

| percentile | real | model | diff |
|---|---:|---:|---:|
| p50 | 188 ft | 122 ft | −66 |
| p90 | 267 ft | 274 ft | +7 |
| p95 | 297 ft | 308 ft | +11 |
| p99 | 358 ft | 364 ft | +6 |
| p99.9 | 407 ft | 418 ft | +11 |
| max | 439 ft | 451 ft | +12 |

| | real | model |
|---|---:|---:|
| share beyond 330 ft | 2.15% | 2.73% |
| share beyond 400 ft | 0.16% | 0.27% |

The tail runs 5–12 ft long between p90 and the maximum, against a typical
quantile error of 28.5 ft (`NOTES_STEP5_6.md`). If the tail were calibrated
exactly, the share beyond 330 ft would fall from 2.73% to 2.15% — **0.3 fouls
per game**, out of 18.7 unmatched. Over-carrying trajectories account for
roughly 1.6% of the losses.

So the ranking of causes for the unmatched third is:

1. **On the field, correctly dropped** — 12.9 fouls/game (69%)
2. **Missing foul-corner geometry** — 2.9 fouls/game (15%)
3. **Bowl front possibly misplaced** — 1.8 fouls/game (10%)
4. **Genuinely out of the stadium** — 0.7 fouls/game (4%)
5. **Trajectories carrying too far** — 0.3 fouls/game (2%)

The headline "a third of every park's fouls land nowhere" is real but reads
worse than it is: about seven tenths of it is the model correctly declining to
put a ball on the field into a seat.

**The p50 gap is the interesting anomaly, and it points the other way.** The
model's median foul travels 66 ft shorter than the real median. That is
dominated by a known measurement bias rather than a model error: Statcast
tracks 85% of fouls and the missing 15% are disproportionately the weak
backstop contact the model produces in quantity (`NOTES_STEP5_6.md` caveat 2),
so the real distribution here is biased long by construction. The comparison
cannot be taken at face value in the middle — only in the tail, where tracking
is near-complete and where the question about carrying too far actually lives.

### Per-park variation

The short bucket barely moves: 14.0–15.4 fouls/game across all 31 parks. It is
a property of the physics and of where bowls start, both of which are nearly
identical everywhere.

The past bucket is where parks separate, and it is the whole story of the three
outliers:

| park | past, fouls/game | of which beyond 330 ft |
|---|---:|---:|
| Las Vegas Ballpark | 16.1 | 1.4 |
| Sutter Health Park | 13.9 | 1.4 |
| Fenway Park | 8.1 | 1.4 |
| typical park | 2.2–4.0 | 0.7–1.4 |
| Coors Field (lowest) | 1.8 | 0.7 |

The beyond-330 ft column is essentially constant at 0.7–1.4 across every park,
which is what it should be — that is the physics tail, and it does not care
about the seating chart. Everything that distinguishes Las Vegas (16.1) from
Coors (1.8) is balls coming down inside 330 ft where the park has no modelled
deck. The outliers are a geometry-coverage problem, start to finish, and not a
trajectory problem.
