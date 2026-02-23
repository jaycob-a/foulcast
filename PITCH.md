# FoulCast - Foul Ball Prediction Technology

## The Problem

Every MLB game produces 30-40 foul balls into the stands. Fans in the right seats have a 10-15x higher chance of catching one, but there's no tool that tells you *which* seats those are for any given matchup. Ticket platforms sell 100M+ tickets per year with zero foul ball data.

## The Product

FoulCast uses trajectory simulation to predict where foul balls will land for any MLB matchup. Given two teams, it runs thousands of Monte Carlo simulations accounting for:

- **Every batter in both lineups** (exit velocity, launch angle, handedness, pull tendency)
- **Starting pitcher pitch mix** (breaking balls foul differently than fastballs)
- **Per-batter foul rate weighting** (real fouls-per-PA from Statcast plate appearance data)
- **Stadium geometry** (real section numbers, altitude, temperature, field dimensions)
- **3D ballistic physics** (gravity, aerodynamic drag, altitude/temperature air density correction)

The output: a stadium heat map showing the best sections to sit in, ranked by catchable foul ball probability.

## How It Works

1. Pull both real lineups from MLB API
2. For each batter, simulate 400 foul balls using their personal EV/LA distributions
3. Side determination (1B vs 3B) driven by batter handedness + Statcast pull tendency data
4. Spray angle (how far into stands) driven by pull tendency, launch angle, pitch type, and pitch location
5. 3D trajectory simulation with gravity + drag, adjusted for stadium altitude and temperature
6. Map landing positions to real stadium sections
7. Weight results by per-batter foul rate (contact hitters weighted higher)

## Validation

| Metric | Value |
|--------|-------|
| Distance prediction correlation (r) | **0.986** |
| Mean absolute error (distance) | **15.6 feet** |
| Median prediction error | **10.1 feet** |
| Validation data | **19,558 real Statcast foul balls** (Aug 2024) |
| Batter pull profiles | **497 MLB batters** (from real hc_x/hc_y coordinates) |
| Stadiums modeled | **All 30 MLB parks** |
| Real section mapping | Yankee Stadium, Fenway Park, Dodger Stadium |

**Important note:** The r=0.986 validates distance prediction (how far the ball travels). Section-level accuracy depends on spray angle and side assignment, which have wider uncertainty (~15 degrees). Relative section rankings (which side is better) are more reliable than absolute foul counts per section.

## What Exists Today

- Working web application (Flask + vanilla JS)
- Live MLB roster integration via statsapi
- Today's Games feed with one-click predictions
- Shareable prediction URLs
- Responsive design (mobile + desktop)
- Per-batter pull tendency from real Statcast fair-ball coordinate data
- Per-batter foul rate weighting by contact quality
- All 30 MLB stadiums with real field dimensions

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
- Per-stadium section mapping

## What's Needed to Ship

1. **Real section maps for all 30 stadiums** (3 done, 27 remaining) - 2-3 weeks
2. **Production deployment** (cloud hosting, API rate limiting) - 1 week
3. **API documentation** for integration partners - 1 week

## Known Limitations

Transparency on what the model does and doesn't do:

- **Magnus force is a simplified heuristic.** The spin model estimates backspin/sidespin from exit velocity and launch angle using empirical brackets, not a full omega-cross-v aerodynamic computation. This affects trajectory shape at the margins but not landing distance (validated separately).
- **Bat speed data is not yet incorporated.** The `bat_speed_mean`/`bat_speed_std` fields exist on batter profiles but are not used in the current simulation. Future versions could use bat speed to refine exit velocity sampling.
- **Spray angle has ~15-17 degrees of uncertainty.** The model uses batter pull tendency, pitch type, launch angle, and exit velocity to estimate spray direction, but foul ball spray is inherently noisy. Relative section rankings (which side is better) are more reliable than absolute per-section foul counts.
- **Side probability is heuristic, not learned from foul-side data.** Statcast doesn't track which side (1B vs 3B) a foul ball lands on. Side probability is derived from batter handedness and fair-ball pull tendency, which is directionally correct but not calibrated to actual foul-side frequencies.
- **Section-level accuracy is not independently validated.** The r=0.986 metric validates how far the ball travels (distance), not which section it lands in. Section mapping depends on spray angle estimation, which has wider uncertainty.
- **27 of 30 stadiums use generic section geometry.** Only Yankee Stadium, Fenway Park, and Dodger Stadium have real section-by-section mapping. Other stadiums use parameterized sections based on real field dimensions.

## Technical Stack

- Python (Flask, NumPy, statsapi)
- Vanilla JavaScript (SVG stadium rendering, Canvas trajectory animation)
- Statcast data pipeline (pybaseball)
- No external dependencies beyond MLB's public API

## Contact

Built by a solo developer. Technology is ready for licensing or acquisition. All code, data pipelines, and validation methodology included.
