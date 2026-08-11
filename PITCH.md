# FoulCast - Foul Ball Prediction Technology

## The Problem

Every MLB game produces 30-40 foul balls into the stands. Fans in the right seats have a 10-15x higher chance of catching one, but there's no tool that tells you *which* seats those are for any given matchup. Ticket platforms sell 100M+ tickets per year with zero foul ball data.

## The Product

FoulCast uses trajectory simulation to predict where foul balls will land for any MLB matchup. Given two teams, it runs thousands of Monte Carlo simulations accounting for:

- **Every batter in both lineups** (exit velocity, launch angle, handedness, pull tendency)
- **Starting pitcher pitch mix** (breaking balls foul differently than fastballs)
- **Per-batter foul rate weighting** (real fouls-per-PA from Statcast plate appearance data)
- **Stadium geometry** (real altitude, temperature and field dimensions; estimated section boundaries — see Known Limitations)
- **3D ballistic physics** (gravity, aerodynamic drag, altitude/temperature air density correction)

The output: a stadium heat map showing the best sections to sit in, ranked by catchable foul ball probability.

## How It Works

1. Pull both real lineups from MLB API
2. For each batter, simulate 400 foul balls using their personal EV/LA distributions
3. Side determination (1B vs 3B) driven by batter handedness + Statcast pull tendency data
4. Spray angle (how far into stands) driven by pull tendency, launch angle, pitch type, and pitch location
5. 3D trajectory simulation with gravity + drag, adjusted for stadium altitude and temperature
6. Map landing positions to stadium sections (real section names, estimated boundaries)
7. Weight results by per-batter foul rate (contact hitters weighted higher)

## Validation

| Metric | Value |
|--------|-------|
| Distance prediction correlation (r) | **0.986** |
| Mean absolute error (distance) | **15.6 feet** |
| Median prediction error | **10.1 feet** |
| Validation data | **19,558 real Statcast foul balls** (Aug 2024) |
| Batter pull profiles | **497 MLB batters** (from real hc_x/hc_y coordinates) |
| Stadiums modeled | **All 30 MLB clubs, 31 parks** |
| Parks with surveyed section geometry | **0 of 31** — all section boundaries are estimates |

**Important note:** The r=0.986 validates distance prediction (how far the ball travels). Section-level accuracy depends on spray angle and side assignment, which have wider uncertainty (~15 degrees). Relative section rankings (which side is better) are more reliable than absolute foul counts per section.

**Second important note:** No park in the file has surveyed seat geometry. Section names and deck levels are real, and field dimensions and altitudes are published figures, but the distance/angle/height boundaries every prediction is scored against are estimates off a shared template. This is the single biggest gap between what the engine looks like it knows and what it actually knows. See Known Limitations.

## What Exists Today

- Working web application (Flask + vanilla JS)
- Live MLB roster integration via statsapi
- Today's Games feed with one-click predictions
- Shareable prediction URLs
- Responsive design (mobile + desktop)
- Per-batter pull tendency from real Statcast fair-ball coordinate data
- Per-batter foul rate weighting by contact quality
- All 30 MLB clubs mapped to a park, with real field dimensions and altitudes

**Live demo:** `python webapp_v2.py` then open http://localhost:5000

## Business Opportunity

### For Ticket Platforms (SeatGeek, StubHub, Vivid Seats)
- Add "Foul Ball Score" badge to seat listings
- Premium filter: "Best sections for catching a foul ball"
- Differentiator in a commodity market where every platform sells the same seats

### For MLB Teams / Ballparks
- Premium experience upsell: "FoulCast Seats" package
- In-app feature for team apps during games
- Fan engagement metric for sponsorship value

### For Sports Media / Fantasy
- Pre-game content: "Tonight's best seats for foul balls"
- Integration with betting/DFS platforms
- Unique data angle for broadcasts

## Revenue Model

**B2B Licensing:** $50K-$200K annual license to ticket platforms
- API access to prediction engine
- White-label embeddable widget
- Per-stadium section mapping (contingent on the seat-survey work below)

## What's Needed to Ship

1. **Surveyed section geometry for all 31 parks** (0 done, 31 remaining) - not a 2-3 week task, and not a scraping task. No public source publishes distance-from-home-plate or angle-off-the-foul-line for any stadium section; the search behind that conclusion is in `SOURCED_DATA.md`. Closing it needs a different class of source — a stadium survey, CAD/GIS drawings, or Statcast's park geometry files — which means either a licensing conversation with MLB or field measurement. Scope and cost this before promising section-level precision to anyone.
2. **Production deployment** (cloud hosting, API rate limiting) - 1 week
3. **API documentation** for integration partners - 1 week

## Known Limitations

Transparency on what the model does and doesn't do:

- **Magnus force is a simplified heuristic.** The spin model estimates backspin/sidespin from exit velocity and launch angle using empirical brackets, not a full omega-cross-v aerodynamic computation. This affects trajectory shape at the margins but not landing distance (validated separately).
- **Bat speed data is not yet incorporated.** The `bat_speed_mean`/`bat_speed_std` fields exist on batter profiles but are not used in the current simulation. Future versions could use bat speed to refine exit velocity sampling.
- **Spray angle has ~15-17 degrees of uncertainty.** The model uses batter pull tendency, pitch type, launch angle, and exit velocity to estimate spray direction, but foul ball spray is inherently noisy. Relative section rankings (which side is better) are more reliable than absolute per-section foul counts.
- **Side probability is heuristic, not learned from foul-side data.** Statcast doesn't track which side (1B vs 3B) a foul ball lands on. Side probability is derived from batter handedness and fair-ball pull tendency, which is directionally correct but not calibrated to actual foul-side frequencies.
- **Section-level accuracy is not independently validated.** The r=0.986 metric validates how far the ball travels (distance), not which section it lands in. Section mapping depends on spray angle estimation, which has wider uncertainty.
- **All 31 parks use estimated section geometry. None is surveyed.** This limitation previously read "27 of 30 stadiums use generic section geometry — only Yankee Stadium, Fenway Park, and Dodger Stadium have real section-by-section mapping." That was wrong, and the correction is worth stating plainly: no park in the file has measured seat geometry, including those three. Every `SeatSection` carries six numbers — distance min/max, angle min/max, height min/max — and the *shape* of every park is one shared template. What is real: section names, deck levels, field dimensions, altitudes, and — since Step 9 — where each bowl sits radially. What is still estimated: the shape a prediction is actually scored against.
- **Step 9 moved the distances onto sources; it did not move the angles or heights.** Each park's distance bands are now positioned by three published parameters — foul-territory area, backstop distance and deck overhang — every one of them cited in `PARK_PARAMS.md`. The behind-plate front row is pinned to the park's own backstop, so a bowl at Globe Life (42 ft) genuinely starts 18 ft nearer the plate than one at Rate Field (60 ft). The fleet is no longer one template wearing 31 names: 31 parks now resolve to 31 distinct geometry signatures, up from 27, and the 2,064 geometry values draw on 418 distinct distances where the whole file once shared 62 numbers. No park is byte-identical to another any more — Busch/Kauffman/Nationals/Rate and Great American/Petco all separate. **The angles and heights did not move**, because nothing publishes them: `HOME-F` still spans 55-90 degrees in all 31 parks, all 2,064 values still draw on just 15 angles and 19 heights, and every park is still exactly mirror-symmetric to the last decimal. Real bowls are neither. So the parks now differ in depth for a sourced reason and still do not differ in shape at all.
- **Park-to-park differences are still mostly not about the parks.** This limitation previously read "the 31-park sweep finds every park landing within 1.7 fouls of every other." The sourced parameters widened that, but not by much and not for the reason that would matter. The current 31-park sweep runs 20.4 to 33.1 fouls into the stands, and the range is almost all outliers: 27 parks sit inside 30.1-33.1, a 3.0-foul band, up from 2.2 before the change. The four parks outside it are outside for reasons that are about the model, not the venue — Las Vegas Ballpark (20.4) and Sutter Health Park (22.1) have the two coarsest section tables in the file (8 sections each) and no published foul area; Wrigley Field (24.1) and Target Field (25.2) are the two parks whose published deck cover is heaviest, so most of their upper decks are correctly unreachable and the model has nowhere to send a ball that hits a roof. Sourcing the distances moved every park a little and the ordering between them hardly at all, because the behind-plate group still dominates the total and is still shaped identically everywhere. Left/right split is the clearest case: the 1B share spans 0.66 percentage points across all 31 parks against a 1.11-point sampling band, i.e. park geometry contributes nothing measurable to it — which is exactly what mirror-symmetric geometry has to produce.

## Technical Stack

- Python (Flask, NumPy, statsapi)
- Vanilla JavaScript (SVG stadium rendering, Canvas trajectory animation)
- Statcast data pipeline (pybaseball)
- No external dependencies beyond MLB's public API

## Contact

Built by a solo developer. Technology is ready for licensing or acquisition. All code, data pipelines, and validation methodology included.
