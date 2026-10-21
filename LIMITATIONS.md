# LIMITATIONS.md — a cold audit of FoulCast

*Written 2026-10-20 on the `audit` branch, by someone who did not build this and has no reason to defend it. Report only: no code was changed.*

## What was done

- Read `PROJECT_SUMMARY.md`, `AUDIT.md`, `MAP_FINDINGS.md`, `PARK_PARAMS.md`, `SOURCED_DATA.md`, then the code in `foulball/`, `site_build.py`, `site_diagram.py`, `site_data.py` and `webapp_v2.py`, and the test suite.
- Rebuilt the site with `python site_build.py`. It took 3.6 seconds, ran no simulation (the stored run's fingerprint matched the code), and changed exactly one line on 32 of the 33 pages: the "Model figures rebuilt" date. I have restored those 32 files so this branch differs from `main` only by this report.
- Ran the full test suite: **2,246 passed, 0 failed, in 3 minutes 13 seconds.** (`PROJECT_SUMMARY.md` says 2,230; the difference is cosmetic.)
- Probed the server as it would deploy: 38 URL paths, plus GET/HEAD/POST/PUT/DELETE/OPTIONS on each public one, through the Flask app `Dockerfile` and `railway.toml` start. Results below.
- Re-read, live, today: the Angels, Dodgers, Padres and Cardinals netting pages; eight rows of Andrew Clem's stadium statistics table; the FiveThirtyEight foul-ball data README. Everything I re-read matched the repository's transcription word for word.
- Did **not**: re-read the other 22 club pages, re-read Seamheads, re-read any of the 30 seating-map images, or see the live deployment (no public URL is recorded anywhere in the repository, so I could only test the app as it would deploy, not the one that is deployed).

Confidence words used below: **high** means I checked it myself today; **medium** means I checked that the project's own record is internally consistent and spot-checked part of it; **low** means I am relying on the project's own description.

---

## 1. What is verified

These are the things that were checked against something real, and what they were checked against.

**1.1 The netting statements are what the clubs published.**
The 26 clubs that publish a section-level netting extent, plus Wrigley's wording, are transcribed in `foulball/netting.py` from `SOURCED_DATA.md` Part 2. I re-read four club pages today (Angels 103–133; Dodgers "behind home plate to the end of baseline section 40 (first base side) and 41 (third base side)"; Padres; Cardinals, product by product) and all four match the transcription exactly, including the clubs' own "fans are still exposed" sentence. Each park page links to the page it was read from and prints the read date, 2026-08-09.
*Confidence: high for the four I re-read; medium for the other 22, which rest on one person's browser read on one day.*
*Evidence: `foulball/netting.py` (`PARK_NETTING`), `SOURCED_DATA.md` Part 2, the "Source:" line under Details on every park page.*

**1.2 The two park measurements are what Andrew Clem publishes, and the page prints exactly what the model uses.**
Foul-territory area (29 parks) and backstop distance (30 parks) are taken from Clem's table and park pages. I fetched his table today and the rows for Fenway, Yankee Stadium, Wrigley, Rogers Centre, Globe Life, Rate Field, Kauffman and Truist all match `PARK_PARAMS.md`, including the parenthesised "(53)" at Truist that marks an estimate, and the sentence that these figures "are estimates based on the diagrams." A test holds every printed figure equal to the figure the model actually uses.
*Confidence: high for the eight rows I re-read and for the page-equals-model check; medium for the rest.*
*Evidence: `PARK_PARAMS.md` Parts 1–2, `foulball/stadium.py` (`PARK_PARAMS`), `tests/test_site.py::test_sourced_figures_match_what_the_model_uses`.*

**1.3 The one real foul-ball dataset is correctly described.**
The site says the largest published record of where fouls actually land is FiveThirtyEight's 906 balls, one day at each of ten parks in 2019, placed into broad zones by eye. The data repository's README says exactly that today.
*Confidence: high.* *Evidence: `SOURCED_DATA.md` Part 3; the "906 fouls" link on the About page.*

**1.4 The published pages are the current output of the current code.**
The committed pages were rebuilt from the stored simulation and matched byte for byte apart from the date line, and the stored simulation carries the fingerprint of today's model code. Before Step 18 the pages had sat five rounds of changes behind the generator; that cannot now happen silently.
*Confidence: high.* *Evidence: my rebuild (32 one-line diffs, all dates); `tests/test_site.py::test_the_committed_site_matches_a_fresh_render` and `::test_the_committed_cache_came_from_the_current_model`.*

**1.5 The server answers on exactly five URL patterns and nothing else.**
The old demo, its five prediction endpoints and the foul-log form all return plain 404s. `/` redirects to `/parks/`; `/parks`, `/parks/about` and `/parks/<park>` without a trailing slash redirect to the slashed form; wrong-case slugs, `index.html` suffixes, `/static/...`, `/.env`, path traversal, `/health`, `/api/` all 404; POST/PUT/DELETE return 405. The Docker image copies only `foulball/`, `templates/foul_log.html`, `webapp_v2.py`, `site/` and `site_data.py`, so nothing else can be served. A test pins the route list to exactly those five rules.
*Confidence: high for the app as built; I could not reach the live host.* *Evidence: my probe of 38 paths; `tests/test_endpoints.py::test_the_public_route_list_is_exactly_this`; `Dockerfile`.*

**1.6 Which foul line is which, at 16 of 31 parks.**
At 16 parks a source that names a side next to a section number (a club page, or the park's own seating map read with a landmark) agrees with the model's labelling of the two sides. At four parks the same check found the sides reversed and at nine it found them scrambled; those 13 parks, and the two untestable ones, do not name a foul line anywhere on their pages.
*Confidence: medium. The anchors were transcribed by one person from map images, and `MAP_FINDINGS.md` records its own doubts (Fenway's labels are "5–8 px wide", Citi Field's orientation "has no label behind it"). I re-ran the check and it reports what the pages say; I did not re-read the images.*
*Evidence: `foulball/seat_map.py` (`SIDE_ANCHORS`, `check_side_anchors`), `MAP_FINDINGS.md` "The flip check" and Steps 12–16.*

**1.7 The site is internally consistent, and tests keep it so.**
The drawing's shading comes from the same figures the table prints; the netting marks on the drawing equal the rows the table calls netted; no section number, no form of the word "safe", no accuracy claim and no seat recommendation appears on any page; the netting sentence sits above the model on every page. All of that is enforced by tests, and all of it passed today.
*Confidence: high — but note what this is. It verifies that the site agrees with itself, not that any of it is true.*
*Evidence: `tests/test_site.py`, `tests/test_endpoints.py`.*

**1.8 The ball-flight physics reproduces Statcast's own distance figure.**
Given the same exit velocity and launch angle, the drag model's distance correlates 0.986 with Statcast's `hit_distance_sc` over 19,558 fouls (per `PITCH.md`). `AUDIT.md` is right that this is weak evidence: both sides are computed from the same two inputs, and the comparison says nothing about where a ball lands sideways or which seat it reaches. I did not re-run the backtest.
*Confidence: medium that the number is real; low that it means anything for the product.* *Evidence: `backtest.py`, `AUDIT.md` P3, `PITCH.md` "Validation" table.*

---

## 2. What is estimated

Things that are plausible but have never been checked against a real observation, and what each one rests on.

**2.1 Every "fouls a game" figure on every page.**
No foul-ball landing has ever been compared with this model, at any park. The site says so on every page, and it is true: there is no public dataset to compare against (1.3). Every number in every table and every shade in every drawing is a simulation output. What it rests on is everything below.
*Confidence that it is unvalidated: high. Confidence that any individual figure is right: unknowable, and the project says so.*
*Evidence: the caveat line on every page; `site_data.MODEL_LIMITS`; About page "The model has never been checked".*

**2.2 The shape of every ballpark is one shared template.**
All 31 parks use the same angles (15 distinct values in the whole file) and the same deck heights (19 values). The behind-plate area spans 55–90 degrees at every park. Every park is an exact left-right mirror, which the one club with a published statement on the matter (Wrigley: "more room on the first base side") says is wrong. The two published measurements only stretch and position this one shape. Nobody publishes the angle of a seating section or the height of a deck for any ballpark, so there is nothing to replace it with.
*Confidence: high that this is how it works.* *Evidence: `foulball/stadium.py` MODULE PROVENANCE block; `PARK_PARAMS.md` gaps 3, 4, 12; `PITCH.md` Known Limitations.*

**2.3 The rate of balls hit straight back is a tuned constant.**
`BACK_FOUL_BASE_RATE = 0.28` was, in the code's own words, "set from the requirement that a typical game puts 30–40 fouls in the stands with the seats behind the plate among the busiest." It decides that the seats behind home plate are the busiest area at all 31 parks. The 30–40 figure it was tuned to hit comes from `PITCH.md` and has no source (`NOTES.md` item 6 says so).
*Confidence: high that it is tuned, not measured.* *Evidence: `foulball/trajectory.py` lines 62–70; `NOTES.md` "What still needs fixing" items 1 and 6.*

**2.4 The 18 batters are hand-typed numbers, not the computed profiles.**
The site simulates the 2024 Yankees and Red Sox lineups from `YANKEES_2024_PROFILES` and `RED_SOX_2024_PROFILES`. These are literal values typed into `batter_profiles.py` ("based on actual 2024 Statcast data from our research"); nothing in the repository regenerates them, and they are suspiciously round (quartiles like 72.0 and 30.0, foul-rate tables that differ by a hundredth or two from batter to batter). The project does have a computed, dated set of per-batter profiles from 2025–26 Statcast in `.cache/spray_profiles.json` (690 batters), but the site never loads it. Consequences:
- Pull tendency is left at the 50% default for all 18 batters, so the per-batter spray data the `PITCH.md` boasts about plays no part in the site's figures.
- The typed fouls-per-plate-appearance values run 0.63–1.02; the computed 2025–26 values for the same players are lower (Judge 0.58 vs 0.85 typed; Soto 0.54 vs 1.02; fleet median 0.71). The site's game total of 50.8 fouls rests on the typed values, and would be roughly a fifth to a quarter lower on the computed ones.
*Confidence: high.* *Evidence: `foulball/batter_profiles.py` lines 254–425; `site_build.standard_lineups`; `.cache/spray_profiles.json`; nothing in `site_build.py` calls `enrich_with_spray_profiles`.*

**2.5 The spray-angle and contact model is hand-set throughout.**
Base spray 27° ± 15°, a 62–82% pull-side probability, pitch-type nudges of 2–3 degrees, a 0.85→0.58 exit-speed penalty on backward fouls, 4.0 plate appearances per batter, and a league foul rate per pitch type are all constants chosen by the author. The repository is honest that side probability is "heuristic, not learned from foul-side data."
*Confidence: high.* *Evidence: `foulball/trajectory.py` (`estimate_spray_angle`, `back_foul_probability`, `oblique_contact_speed_factor`), `foulball/matchup_engine.py` (`PITCH_FOUL_RATES`), `PITCH.md` Known Limitations.*

**2.6 Between 35% and 60% of simulated fouls are thrown away at every park.**
They land where the template has no seats: in the gap the backstop anchor opened in front of the first row, deep near the poles, or under a covered deck. The share is printed on each page. It is a property of the template, not of the ballpark, and it is why the authors themselves say the figures are "a shape rather than a census."
*Confidence: high.* *Evidence: `.cache/site/park_stats.json` (`unmatched`), each page's "About N% of the fouls" line.*

**2.7 The parks barely differ, and the home-page comparison mostly compares the template.**
The simulated total is 50.8 fouls at every park, by construction (it depends only on the lineups). Fouls reaching seats run 20.4 to 33.1, but 27 parks sit in a 3-foul band (30.1–33.1), and the four outliers are outside for model reasons the project itself names: two parks with 8-section tables and no foul area, two with heavy published roof cover. The behind-plate area is the busiest at all 31 parks "partly" as "an artefact of every park sharing one bowl shape", in the About page's own words.
*Confidence: high.* *Evidence: `PITCH.md` Known Limitations ("Park-to-park differences are still mostly not about the parks"); my tabulation of the stored run.*

**2.8 The per-area netting verdicts are arithmetic on seat labels the maps say are wrong.**
At the 7 parks where netting is "mapped", each area's "behind netting / partly / not" is computed by checking whether the section numbers the model wrote into that area's name fall inside the club's published range. At 5 of those 7 parks the project's own map reads say the model's section numbers are shifted 4–18 positions from where the plate really is. See the netting assessment at the end.
*Confidence: high.* *Evidence: `foulball/netting.py` (`_classify_zone`); `MAP_FINDINGS.md` Steps 11–13; `site_data.MAP_READS`.*

**2.9 "Not behind netting" for the decks above field level is inferred from silence.**
The join marks any deck behind the front row as "not behind netting" when the club's list does not mention its section series. No club says those seats are unnetted; the site decides that "a net in front of the field boxes does not screen the deck above them." It is printed with the site's one red mark. At Fenway, the row "the lower bowl behind home plate — the loge" carries that red mark on the strength of the Red Sox not listing Loge sections, which is not what the club's page says.
*Confidence: high that it is an inference; medium that it is wrong at specific parks (I did not survey decks).* *Evidence: `foulball/netting.py` lines 972–978 and 1026–1042; `site_build.status_tag` docstring, which admits "not behind netting is this project's inference from the edge of a club's sentence."*

**2.10 Deck cover, seat setback, and Las Vegas.**
Whether a published overhang percentage counts as something a ball would hit is a judgment call (deck or canopy: yes; dome: no) and decides whether a sourced figure is used at all. The 1 ft between fence and front row is a floor, not a measurement. Las Vegas Ballpark has no published foul area, backstop, overhang or map; its backstop is an unsourced 52 ft; and `PARK_PARAMS.md` itself records that the model's outfield distances (328 ft) and altitude (2,030 ft) for that park disagree with published figures (340 ft and about 3,000 ft) — recorded as "out of scope" and never fixed.
*Confidence: high.* *Evidence: `foulball/stadium.py` (`UpperCover`, `_SEAT_SETBACK_FT`, `las_vegas_ballpark()`); `PARK_PARAMS.md` gaps 7, 11a, 14, 15.*

**2.11 The "off the bat" speeds in the risk reading are model on model.**
Exit speeds printed per area come from the typed profiles (2.4), reduced by the hand-set backward-contact factor (2.5). The 50 mph shown for every behind-plate row at every park is that factor at work.
*Confidence: high.* *Evidence: each page's "Each area in full" table; `foulball/trajectory.py` (`oblique_contact_speed_factor`).*

---

## 3. What does not work

Tested and failed, or known to be wrong.

**3.1 The seat-section labels are wrong at 27 of the 30 parks that have been checked.**
Thirty seating maps were read against the model's section tables. Four parks have the two foul lines reversed, nine have them crossed in a way no swap fixes, two number their lines odd/even so every model area is half one line and half the other, and at most parks the block the model calls "behind home plate" is several sections up one line (Rate Field: about 18 sections, nearly at the right-field corner; Sutter Health: 14 of 24 field sections do not exist; Truist and Rate Field name whole decks that are not in the building). Three parks agree (Daikin, Yankee Stadium, Dodger Stadium). **Nothing has been corrected in the model.** The site's response was to stop printing section numbers and to describe areas by position — but the figures are still attached to the mislabelled areas, and the row called "the seats at field level behind home plate" is, at Truist, Rate Field, Great American and others, a row of seats somewhere else.
*Confidence: high that this is the project's own finding; medium on each individual read.* *Evidence: `MAP_FINDINGS.md` (whole file); `site_data.MAP_READS`; the "What this ballpark's own seating map shows" panel under Details on every page.*

**3.2 The netting join fails at 16 parks where the club publishes perfectly good information.**
Including Yankee Stadium, which has the most detailed netting page in the league and whose map agrees with the model on every ring — the join still fails because the club numbers an inner ring the model does not carry. Every row at those 16 parks says "netting not verified."
*Confidence: high.* *Evidence: `python -m foulball.netting` report; About page "The club publishes its netting and this model cannot use it (16)".*

**3.3 The foul-ball log — the only thing that could ever validate the model — is shelved with an empty dataset.**
The observation form was built, the season it was built for ended on 27 September 2026, and nothing was collected. The calibration code has never run on real data.
*Confidence: high.* *Evidence: `webapp_v2.py` lines 173–197; `PROJECT_SUMMARY.md`; `NOTES_STEP8.md`.*

**3.4 The provenance date on every page is wrong in spirit.**
Every page says "Model figures rebuilt 2026-10-20" (or whatever day the HTML was last rendered). The figures were not rebuilt that day: the simulation behind them was run and committed on 2026-09-08 (Step 18) and is reused from a cache. The date is the render date, and the test that compares committed pages with a fresh render deliberately ignores it, so it can drift forever without anything noticing. My own rebuild today changed this line on 32 pages and nothing else.
*Confidence: high.* *Evidence: `site_build.py` line 174 (`BUILT = date.today()`); `git log -- .cache/site/park_stats.json`; `tests/test_site.py` `_BUILD_DATE` normalisation.*

**3.5 Two parks are filed under "nothing usable is published" when the club did publish something usable.**
Comerica Park: the Tigers publish "behind home plate to Section 116 (1B line) and Section 142 (3B line)", a statement with sides; the reason it cannot be used is that the *model's* numbering for Comerica wraps in a way the map read later showed to be scrambled. Wrigley: the Cubs publish "along the first and third base lines to the outfield edge of each dugout"; the site's own area vocabulary ("between the plate and the dugout", "from the dugout outward") could carry that sentence, but the page says "Nothing published says where the netting runs at Wrigley Field in a form that can be attached to a seat."
*Confidence: high.* *Evidence: `foulball/netting.py` entries for `comerica_park` and `wrigley_field`; `site_build.GROUPS`; `site_data.ZONE_WORDS`.*

**3.6 Dodger Stadium's busiest row is marked "netting not verified" though the club's sentence plainly covers it.**
The Dodgers say netting "extends from behind home plate." The model's top row at Dodger Stadium, "the club seats at field level behind home plate — the Dugout Club" (4.5 fouls a game), is marked "netting not verified" because the club's sentence does not mention the Dugout Club by name. This is at one of only three parks whose map agrees with the model.
*Confidence: high.* *Evidence: `site/dodger-stadium/index.html` table; `foulball/netting.py` `dodger_stadium` notes.*

**3.7 Small defects.**
- Every HTML response carries `Content-Type: text/html; charset=utf-8; charset=utf-8` (the charset is added twice in `webapp_v2._site_response`). Browsers cope; it is still wrong.
- 404s are Flask's unstyled default page, so a mistyped park URL drops a visitor out of the site's look entirely.
- `webapp.py`, the original demo server with the 0.986 claim and seat recommendations, is still in the repository. It is not in the Docker image, but it runs if someone starts it.
- `PITCH.md` still opens with "30-40 foul balls into the stands" and "10-15x higher chance of catching one" with no source, and still carries the r=0.986 validation table. It is not on the site, but it is the document a buyer would be handed.
*Confidence: high.* *Evidence: my probe output; `webapp_v2.py` line 589; `webapp.py`; `PITCH.md` lines 5 and 31–40.*

---

## Problems found

Ranked by how much it would matter to a visitor.

**P1. The table above the fold attaches figures to seats the ballpark's own map says are somewhere else, and the page admits it only two clicks down.**
At Truist Park the top row, "the seats at field level behind home plate — 6.4 a game — behind netting", describes seats the Braves' map puts up the third-base line, and "the infield boxes on the first-base side" are actually the seats behind the plate. At Rate Field the "behind home plate" row is about 18 sections toward right field. The site's visible page (drawing, sentence, table) does not hint at this; the Details panel does, in full and honestly. A visitor who reads the table and leaves — which is what the Step 23 redesign was built for — takes away the wrong seats. (Sections 3.1, 2.8.)

**P2. "Behind netting / not behind netting" marks on the table are label arithmetic on those same wrong labels, and the red mark is sometimes an inference from silence.**
At 5 of the 7 "mapped" parks the plate block is offset, so which area gets which verdict is unreliable; and the red "not behind netting" on upper decks behind the plate is something no club said. Red is the loudest mark on the site and it is on the least-supported claim. (Sections 2.8, 2.9, 3.6.)

**P3. The one tuned number decides the headline finding, and the test that checks it was written to the number it was tuned to.**
The back-foul rate (0.28) was set so that a game lands in 30–40 fouls with the plate busiest; `test_total_fouls_into_stands_in_realistic_range` then asserts 25–45. The 30–40 target has no source. The "seats behind home plate are busiest at all 31 parks" finding is that constant. (Section 2.3.)

**P4. The batter inputs are not what the documentation implies.**
Hand-typed 2024 numbers, pull tendency defaulted to 50% for every batter, fouls per plate appearance a fifth to a quarter above the computed 2025–26 values that sit unused in the repository. The About page says "the same 18 batters at every park" without saying who or what they are. (Section 2.4.)

**P5. Checks that could pass while the output is wrong.**
- *Golden-game snapshots* lock whatever the model currently produces; they catch change, not error.
- *Plausibility tests* run at Yankee Stadium only, with thresholds set after the model was tuned to meet them.
- *Committed-site-matches-render* and the *drawing-equals-table* tests prove the site agrees with itself.
- *The model fingerprint* detects edits to the code, not whether the geometry in it is right.
- *The side-anchor "ok"* rules out a mirror and nothing else; Truist passes it with its plate four sections off.
- *The "no section numbers" tests* stop the wrong labels being printed; they do nothing about the figures being attached to them.
- *The word budgets* keep the page short, which also keeps the caveats out of sight.
Not one test in 2,246 compares any output with a real foul ball, because there is nothing to compare with. The suite is excellent at preventing regressions and overclaims; it cannot tell the owner whether the product works.

**P6. "Model figures rebuilt <today>" misstates when the figures were produced.** (Section 3.4.)

**P7. The home-page grid invites a comparison the figures cannot support.**
Tiles are sized by published foul area and shaded by model output, but 27 parks sit within a 3-foul band and the total is identical everywhere. The grid is a comparison of one template stretched 31 ways. (Section 2.7.)

**P8. Netting gaps are miscategorised at Comerica and Wrigley, and the Dodgers' plainest sentence is marked unverified.** (Sections 3.5, 3.6.)

**P9. Las Vegas Ballpark's dimensions and altitude are recorded as wrong in the project's own notes and left as they are.** (Section 2.10.)

**P10. Minor: duplicated charset header, unstyled 404 page, old demo server still in the repo, PITCH.md still carries unsourced and retracted claims, test count in the summary off by 16.** (Section 3.7.)

What a skeptical visitor would object to, in one breath: *"You tell me where fouls land to a tenth of a ball per game, in seats you admit you have mislabelled at 27 of 30 parks, from a model you admit has never seen a foul ball, with a red dot telling me which seats are unprotected that the club never said."* The Details panel and the About page answer every part of that honestly. The visible page does not.

---

## The netting layer

**How often is the mapping of club netting onto the model's seating areas correct?**

| Outcome | Parks | What the visitor sees |
|---|---|---|
| Per-area verdicts trustworthy | 3 — Daikin, Dodger, Rate Field | Dodger still marks its busiest row "not verified" (3.6); Daikin's Diamond Club is unenumerated; Rate Field survives only because the netting is pole to pole |
| Sentence roughly right, per-area verdicts attached to offset labels | 4 — Fenway, Truist, Citizens Bank, Great American | A correct-sounding sentence and a table whose "partly"/"not" rows are on the wrong seats |
| Club publishes usable data, model cannot use it | 16 | Every row "netting not verified", including Yankee Stadium |
| Club publishes nothing usable | 6 — Kauffman, Citi, loanDepot, Tropicana (self-contradicting), Sutter Health, Las Vegas | Every row "netting not verified" — correct |
| Club publishes it in words, site rejects it | 2 — Wrigley, Comerica | "Nothing published" — misleading |

So the per-zone mapping is cleanly right at **3 of 31**, roughly right at the sentence level at 4 more, produces nothing at 22, and actively misdescribes the sources at 2. The project's own count of "7 mapped" is honest about the machinery and generous about the result.

**Where it could mislead a visitor.**
1. The red "not behind netting" on any deck above field level, at all 7 mapped parks: an inference, printed as a club fact.
2. "Partly netted" rows whose boundary depends on which section numbers the model assigned, at the 4 offset parks.
3. "Netting not verified" on the Dodger Dugout Club and on all of Yankee Stadium, where the club's statement is plain.
4. The dashed netting mark on the drawing, placed on template geometry at parks whose plate block is in the wrong place.
5. "Nothing published says where the netting runs" at Wrigley and Comerica.

**Would one sentence per park plus a link be more honest?** Yes, and by a wide margin.

- It would be correct at every park with a primary source — 27 of 31, counting Wrigley's words and Comerica's endpoints — instead of trustworthy at 3. The club's own numbers, quoted verbatim, are sourced; the rule against section numbers exists because the *model's* numbers are wrong, and a verbatim quotation of the club does not inherit that problem. The rule would need one stated exception: "section numbers appear on this site only inside a quotation from the club."
- It would delete the three least-supported things on the page: the red dot, the "partly" rows, and the netting mark on the drawing.
- It would restore Yankee Stadium's excellent club statement to the Yankee Stadium page.
- It costs the "If you want to catch a ball" exclusion list and the per-area netting column — the parts that rest on the mislabelled zones anyway. The "same figures read two ways" panel would become one reading.

If the per-zone join is kept anywhere, keep it only where the park's own map agrees with the model (Daikin, Dodger) and at Rate Field, and say so on the page. Keeping it at Fenway, Truist, Citizens Bank and Great American while the project's own map reads say the plate block is in the wrong place is the one place this site asserts a club fact about the wrong seats.

---

## What I could not check, and what a next audit should

- The live deployment. No URL is in the repository. Someone should fetch `https://<live host>/`, `/parks/`, `/api/predict` and `/log` from outside and confirm the responses match what I saw from the test client (302, 200, 404, 404).
- 22 of the 26 primary netting pages, Seamheads, and all 30 seating-map images, which I did not re-read.
- Whether the hand-typed batter profiles were ever derived from data. Nothing in the repository can regenerate them.
- Anything about where foul balls actually land. Nobody can; that is the whole problem.
