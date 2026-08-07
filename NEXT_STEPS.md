# FoulCast — Step-by-Step Plan

Follow in order. Do not skip ahead to stadium coverage or deployment.
Each step has a paste-ready prompt. Run one step per Claude Code session — use `/clear`
between steps to reset context, or open a new session.

Interface: **Claude Code in the Claude Desktop app** (the Code tab). No terminal needed.

---

## Step 0 — Set up Claude Code (20 min, one time)

Use the **desktop app**, not the terminal. No Node.js, no npm, no command line.

1. Download Claude Desktop from https://claude.com/download and install it.
2. **Windows only:** install Git for Windows from https://git-scm.com/download/win first,
   then restart the app. (Mac users skip this.)
3. Launch Claude, sign in, and click the **Code** tab. The app has three tabs —
   Chat, Cowork, and Code. You want Code.
4. Point it at the project. Either open the `foulcast` folder if you already have it,
   or in a new Code session say:
   > Clone https://github.com/jaycob-a/foulcast.git into a folder and open it.
5. Drop `AUDIT.md` and `NEXT_STEPS.md` into that folder so Claude can read them.
   You can also drag files straight into the prompt box.

**Permission modes.** There's a mode selector next to the send button.
Start on **Manual** — Claude asks before each file edit or command, so you see exactly
what it's doing. Move to **Accept edits** once you trust it. The mode is remembered
per folder.

**Switching models:** use `/model` and pick from the list.
Use **Fable** for Step 2. Use **Opus** for everything else.

**Safety.** The desktop app creates isolated git worktrees for sessions automatically,
so you generally don't need to manage branches by hand. Before Step 2 specifically —
the big rewrite — still ask Claude to make a branch: *"create a branch called step-2
before you change anything."* If it goes wrong, ask it to switch back to main.

**Reviewing changes.** The app has a visual diff panel. Use it. After each step, look at
what actually changed rather than trusting the summary. You don't need to understand
every line — you're checking that the scope matches what you asked for.

---

## Step 1 — Baseline (Opus, ~20 min)

Confirm the project runs on your machine before changing anything.

> Read AUDIT.md. Don't fix anything yet. Set up a virtual environment, install
> requirements.txt, run the full test suite, and start webapp_v2 locally. Tell me
> whether all 408 tests pass and give me the local URL. If anything fails to
> install or run, fix only what's needed to get it running and tell me what you changed.

**Done when:** tests pass and you can open the app in your browser.

---

## Step 2 — Fix section matching (FABLE, the important one)

Switch model first: `/model` → Fable.

> Read AUDIT.md, especially problem P1. In foulball/matchup_engine.py, section
> assignment currently reads the ball's altitude as it passes a section's mid-distance,
> then takes the first section whose height band contains that altitude. This is wrong:
> it matches balls in mid-flight rather than where they come down, so high fly balls to
> the lower bowl get assigned to the upper deck.
>
> Rewrite it so a ball is assigned to the section its trajectory actually intersects or
> lands in. Make the section zones a non-overlapping partition rather than independent
> overlapping ranges, and choose the nearest match rather than the first match in list order.
>
> Then add plausibility tests to the test suite: at Yankee Stadium with a normal lineup,
> lower bowl and behind-home sections must receive more fouls than upper deck sections
> down the lines. Keep all 408 existing tests passing.
>
> Show me the top 10 sections before and after your change.

**Done when:** upper decks are no longer ranked #1, and tests pass.
**This is the gate. Nothing after this matters if this isn't right.**

---

## Step 3 — Fix the 4x calibration gap (Opus)

> Read AUDIT.md problem P2. Total predicted fouls into the stands is about 8.5 per game;
> reality is 30-40. Find where balls are being dropped — balls that match no section,
> the distance<5ft filter, and the fouls_per_pa weighting.
>
> Recalibrate so a typical game predicts 30-40 fouls into the stands. Add a test that
> fails if the total falls outside 25-45. Explain what was actually causing the shortfall.

---

## Step 4 — Make the game backtest honest (Opus)

> Read AUDIT.md. game_backtest.py has two fake metrics. The side-split comparison invents
> the "actual" value by assuming RHB fouls go 72% to 3B, so the model is being compared
> against an assumption, not data. And batter_corr is hardcoded to np.nan.
>
> Delete the side-split metric entirely — Statcast does not record which side a foul
> lands on, so it cannot be validated and pretending otherwise is misleading.
> Implement the per-batter foul count correlation properly by matching batter IDs.
>
> Add the metric that's missing and that CAN be validated: predicted total fouls per game
> vs actual total fouls per game, across all backtested games. Report correlation and
> mean absolute error.

---

## Step 5 — Refresh the data (Opus)

> spray_profiles.json is from June-August 2024. Re-run rebuild_spray_profiles.py against
> the 2025 season and 2026 season to date. Confirm current players appear and retired
> players like Charlie Blackmon and David Peralta drop out.
>
> Also review the STADIUMS registry in foulball/stadium.py for venue changes since 2024,
> especially the Rays and Athletics situations. Flag anything that looks stale.

---

## Step 6 — Backtest against recent games (Opus)

> Run game_backtest.py against 20 games from the 2026 season. Report: predicted vs actual
> total fouls per game (correlation and MAE), distance distribution KS test, and per-batter
> foul count correlation. Tell me plainly which parts of the model are validated by this
> and which are not.

**Read the output carefully.** If total foul counts correlate well, your volume model works.
Section-level accuracy is still unvalidated at this point — that needs Step 9.

---

## Step 7 — Verify all 30 parks (Opus)

Now this is high priority, not cleanup. Every park is a landing page. Coverage is the product.

> All 30 stadiums already have geometry in foulball/stadium.py. With the corrected matching
> logic, run a standard lineup through every park and produce a comparison table: total fouls,
> top 3 sections, and 1B/3B split for each.
>
> Flag any park whose output looks physically implausible — upper deck ranked first, extreme
> side imbalance, totals far outside 30-40, or sections receiving zero fouls. Fix the geometry
> for the parks that are flagged.

---

## Step 8 — Ship the logging feature (Opus) — HARD DEADLINE

**Do this before anything cosmetic.** The regular season ends September 27 and the
postseason ends October 31. After that there is no baseball until March 25, 2027.
Every week of delay costs a week of data you cannot get back.

This is the only genuinely scarce asset in the project. Nobody has published foul ball
landing data — Statcast does not record it, MLB does not release it, and IdealSeat's
10,000 logged balls disappeared into an acquisition in 2020.

> Build a foul ball logging feature. A simple mobile-friendly form: pick the game, the
> inning, the batter, and tap the section where the ball landed. Store each entry with a
> timestamp. Make it work well on a phone — people will use it from their seat.
>
> Then write a calibration script that compares logged fouls against model predictions
> for those same games, and reports where the model is over- and under-predicting by section.

Then start logging. Broadcasts work; you don't need to be at the park.

---

## Step 9 — Add netting boundaries (Opus)

The factual backbone of the safety framing. Verifiable, and nobody has compiled it well.

> For each of the 30 parks, record where the protective netting begins and ends — which
> sections are behind netting and which are exposed. Add this to the stadium data and
> surface it on each park's page.

Rules for how this gets presented, permanently:

- Never use the word "safe." Use "behind netting" / "not behind netting" and
  "higher risk" / "lower risk."
- Always lead with netting position, which is a fact. The model's zone ranking is an
  estimate and goes second.
- State the uncertainty plainly on every page. The model has 15-17 degrees of spray
  uncertainty across 16 broad zones. That is not precise enough to promise anyone safety.

---

## Step 10 — Thirty park pages, two framings (Opus)

One page per park. Same heat map, two headlines, two sets of search queries.

> Build a page per stadium. Each page answers two questions from the same data:
> where to sit for the best chance at a souvenir ball, and where to sit to keep kids
> away from them. Show the netting boundary, the zone heat map, and a plain-language
> explanation of how confident the model is.
>
> Make it fast, mobile-first, and shareable. Each page needs its own title and meta
> description targeting that stadium's name.

---

## Step 11 — Clean up and deploy (Opus)

> Delete webapp.py (dead code, superseded by webapp_v2.py). Delete the arccos spray-angle
> back-solve in backtest.py and in 04_spray_angle_research.py Approach 2 — the method is
> invalid and shouldn't be reusable.
>
> Then walk me through deploying to Railway step by step. The Dockerfile, railway.json
> and railway.toml are already configured correctly. Assume I have never deployed
> anything before.

Then rewrite the pitch honestly:

> Rewrite PITCH.md. Remove the r=0.986 headline — it correlates two physics models fed
> identical inputs and doesn't validate section prediction. Replace it with whatever the
> Step 6 backtest actually established. Describe the output as zone-level (16 zones per
> park), not seat-level. Keep and update the Known Limitations section.

---

## Step 12 — Affiliate signups (no code)

Sign up for ticket affiliate programs — SeatGeek, StubHub, Gametime, Vivid Seats.
Free, no negotiation, no procurement. Add links to each park page.

This is the entire monetization plan. Not licensing, not a subscription, not an app.

---

## Seven-week calendar

Today is August 7. Regular season ends September 27.

| Weeks | Work |
|---|---|
| 1-2 | Steps 1-3. Geometry fix and calibration. Nothing ships until this is right. |
| 3 | Steps 4-6. Honest backtest, fresh data, validated against real games. |
| 4 | Steps 7-8. All 30 parks verified. **Logging live and collecting.** |
| 5-6 | Steps 9-11. Netting, park pages, deployed. |
| 7+ | Step 12 and keep logging through the postseason. |

October onward is off-season: SEO, design, and writing up what the data shows.

---

## Decisions already made — don't relitigate these

- **Foul balls only.** Not a general seat guide. A View From My Seat has been running
  since 2010 and RateYourSeats rates 10 million seats across 300+ venues. You cannot win
  there. Nobody covers foul balls — that is the entire defense.
- **No B2B.** Not MLB, not ticket platforms, not at any price. Procurement cost doesn't
  scale down, teams already have Hawk-Eye, and foul balls are a liability topic no club
  lawyer will let marketing touch.
- **Minor league is blocked, not rejected.** No Statcast for MiLB means no batter profiles.
  Revisit if a data source appears.
- **Home runs add nothing.** 1-2 per game against 30-40 fouls.
- **Sponsorship and acquisition come later.** Both need an audience or a dataset.
  Steps 7-12 are how you get one.

---

## Order of operations, one line each

1. Get it running
2. **Fix the geometry (Fable)** <- gate
3. Fix the totals
4. Make the backtest honest
5. Refresh the data
6. Backtest recent games
7. Verify all 30 parks
8. **Ship logging** <- deadline
9. Netting boundaries
10. Thirty park pages
11. Deploy and rewrite the pitch
12. Affiliate links

Step 2 makes the product correct. Step 8 is the one with a clock on it.
