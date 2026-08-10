# SOURCED_DATA.md

External seating-geometry and netting research for the 31-park registry in
`foulball/stadium.py`. **Nothing here has been written into the model.** Every
number below carries a citation. Where I could not find a real source, the item
is listed as a gap rather than estimated.

Research date: **2026-08-09**. Pages retrieved on that date are marked
"retrieved 2026-08-09"; where the page itself carries a date or copyright year,
that is noted too.

Two rules I held to while collecting this:

1. **No derived numbers.** I did not convert "netting runs to section 130" into
   feet or degrees. If a source did not state a distance or an angle, there is
   no distance or angle here.
2. **Search-engine summaries are not sources.** Several web-search summaries
   blended text from multiple sites and produced statements that were flatly
   wrong (one placed the Fenway bullpens along the foul line). Everything marked
   *primary* below was read off the live page in a browser. Items that rest only
   on a search summary are marked *secondary — unverified* and should be
   re-checked before use.

---

## Part 1 — Seating geometry

### The headline gap, stated up front

**No source I found publishes, for any of these three parks, the distance from
home plate to a given section or the angle of a section off the foul line.**
Team sites, ticket resellers, and seat-review sites all describe seating
positionally ("behind the dugout", "along the third base line") and give row and
seat numbering, but never survey coordinates. The seating maps that would encode
that geometry are published as flat images without scale.

So for Part 1, what follows is: section inventories and deck levels (well
sourced), plus the handful of real dimensional figures that exist. The
distance/angle columns the task asked for are gaps at all three parks, and I
would not fill them without a different class of source (a stadium survey, a
CAD/GIS drawing, or Statcast's park geometry files).

### Fenway Park

**Dimensional figures**

| Figure | Value | Source |
|---|---|---|
| Backstop distance from home plate | 60 ft (18.3 m) | [Wikipedia, Fenway Park](https://en.wikipedia.org/wiki/Fenway_Park) infobox (retrieved 2026-08-09) |
| Left field line | 310 ft | same |
| Center field | 389 ft 9 in | same |
| Right field line | 302 ft | same |
| Foul territory | "the smallest of any current major league park" (no measurement given) | same |

The 60 ft backstop is the only one of these that bears on foul-ball geometry,
and it matches the `backstop_distance` field the model already carries.

**Section inventory and deck levels** — read off the RateYourSeats section index
([rateyourseats.com/fenway-park/seating/sections](https://www.rateyourseats.com/fenway-park/seating/sections), retrieved 2026-08-09):

| Area | Sections | Deck |
|---|---|---|
| Field Box | FB1 – FB82 | lower |
| Loge Box | LB98 – LB165 (no 156) | lower, above Field Box |
| Grandstand | GS1 – GS33 | lower/mid |
| Right Field Box | RFB87 – RFB97 | lower, RF corner |
| Bleachers | 34 – 43 | outfield |
| Monster Seats | 1 – 10 | LF wall top |
| Pavilion Box | PB1 – PB14 | upper |
| Pavilion Reserved | 15, 16, 18, 20 | upper |
| Roof Box | odd numbers 23 – 43 | roof |
| Dell EMC Club | EMCC1 – EMCC6 | club |
| State Street Pavilion Club | 1 – 14 | club |
| Home Plate Pavilion Club | HPPC1 – HPPC5 | club |

Field Box characteristics, from
[RateYourSeats, Fenway Park Field Boxes](https://www.rateyourseats.com/fenway-park/seating/field-boxes)
(retrieved 2026-08-09; page is undated):

- Located in the lower level, "directly behind the Dugout Box seating and
  positioned between the baselines."
- "Within 20 rows of the field"; rows lettered from the front up to Row M, where
  the main concourse walkway is.
- "All rows in these sections sit behind protective netting, which extends
  across the infield."

**Dugout locations — secondary, unverified.** A web-search summary drawing on
fromthisseat.com and TickPick states the Red Sox dugout fronts sections 21–28
and the visitors' dugout fronts sections 62–69, and that Dugout Box seats are
the first three rows of sections 12–80. I could not confirm this on a primary
page, and a separate search summary about Fenway section geography was
demonstrably wrong, so treat the 21–28 / 62–69 figures as unconfirmed. If they
hold, they would anchor the 1B and 3B sides of the Field Box numbering (Red Sox
dugout is on the first-base side), with home plate somewhere in the low-to-mid
40s — but that last step is inference, not a source, and I have not written it
down as a figure.

**Gaps at Fenway:** per-section distance from home plate; per-section angle off
the foul line; primary confirmation of dugout-to-section mapping; section
elevations.

### Sutter Health Park (Sacramento — Athletics, registry key `oakland_coliseum`)

**Dimensional figures**, from
[Ballparks of Baseball, Sutter Health Park](https://www.ballparksofbaseball.com/ballparks/sutter-health-park/)
(retrieved 2026-08-09):

| Figure | Value |
|---|---|
| Left field line | 330 ft |
| Center field | 403 ft |
| Right field line | 325 ft |
| Capacity | 14,014 |
| Backstop distance | **not stated** |

Same source on the seating bowl: the main lower deck "extend[s] from the left
field foul pole to home plate and across to the right field foul pole," with a
smaller second deck above it holding club seating and 36 luxury suites, plus
grass berms behind both outfield walls. For the A's arrival in 2025 the field
was converted from artificial turf to natural grass and a two-story clubhouse
was built behind left field.

The [Itinerant Fan stadium guide](https://itinerantfan.com/stadium-guide/sutter-health-park/)
(covering the 2025–26 seasons, retrieved 2026-08-09) independently describes it
as "a single-tier facility, with a main concourse above the seating areas that
extend down toward the field," seating reaching toward both foul poles, and a
premium/suite level built above the main concourse.

**Section inventory**, from the RateYourSeats interactive chart
([rateyourseats.com/sutter-health-park/seating/seating-chart](https://www.rateyourseats.com/sutter-health-park/seating/seating-chart), retrieved 2026-08-09):

| Area | Sections | Deck |
|---|---|---|
| Lower bowl | 101 – 125 | field/lower |
| Homeplate Club | A, B, C, D | field level, behind plate |
| Club/suite level | 201 – 206, Suites 5–16 and 17–35, Legacy Club | second deck |
| Outfield | Home Run Hill (berm), Beer Garden, Porch | outfield |

**Conflict on which sections are behind home plate — unresolved.** Two sources
disagree, and I am flagging rather than picking:

- [MLB.com's Sutter Health Park guide](https://www.mlb.com/news/featured/sutter-health-park-guide-capacity-seating-chart-parking-and-more)
  (via web search, 2025) says the Dugout Club sits "right behind home plate" and
  spans the front of **sections 108 through 116**.
- [A View From My Seat's Sutter Health Park section index](https://aviewfrommyseat.com/venue/Sutter+Health+Park/sections/)
  (retrieved 2026-08-09), which groups sections under the site's own area
  headings, puts **103–104** behind home plate, **101–102 and 105–113** on the
  1st base line, and **114–124** on the 3rd base line.

Those cannot both be right, and the A View From My Seat grouping is internally
odd (101–102 and 105–113 both tagged 1B, straddling the "behind home plate"
pair). Until this is resolved against a scaled map, the section-to-field-position
mapping at Sutter Health Park should be treated as unknown.

**Gaps at Sutter Health Park:** backstop distance; per-section distance and
angle; which sections are behind home plate (see conflict above); deck
elevations.

### Las Vegas Ballpark

**Dimensional figures**, from
[Wikipedia, Las Vegas Ballpark](https://en.wikipedia.org/wiki/Las_Vegas_Ballpark)
(retrieved 2026-08-09):

| Figure | Value |
|---|---|
| Left and right field lines | 340 ft |
| Left-center | 380 ft |
| Center field | 415 ft |
| Outfield wall height | 10 ft (14 ft in left field) |
| Seating capacity | 8,196 (10,000 including standing room) |
| Backstop distance | **not stated** |

Also 22 suites, 400 club-level seats, 350 party-deck seats.

**Section inventory**, from the RateYourSeats interactive chart
([rateyourseats.com/las-vegas-ballpark/seating/seating-chart](https://www.rateyourseats.com/las-vegas-ballpark/seating/seating-chart), retrieved 2026-08-09):

| Area | Sections | Deck |
|---|---|---|
| Lower bowl | 101 – 127 | field/lower |
| Club | 201 – 204, 209 – 214, 218 – 221 | club level |
| Suites | S1 – S22 | suite level |
| Other | Berm, Pool, 1st Base Party Deck, 3rd Base Party Deck, SRO | — |

The **official** ballpark map ([thelvballpark.com/ballpark-maps](https://www.thelvballpark.com/ballpark-maps),
retrieved 2026-08-09) labels the lower bowl by price tier rather than by number:
Home Plate Diamond (HPD), Home Plate Prime (HPP), Home Plate Box (HPB), Dugout
Prime (DOP), Dugout Box (DOB), Outfield Box (OFB), Berm/Social; plus 4Topps
Corner (COR) and Home Run Porch (HRP) all-inclusive areas, Club sections 209–214
(row 1 priced separately from rows 2–6), event suites, and 1STPD/3RDPD party
decks. The tier-to-section-number mapping is only on the map graphic, which is
published as an image; I could not read it (the browser pane could not produce a
screenshot in this session), so the mapping is unresolved.

**Do not use the A View From My Seat grouping for this park.** Its LVB section
index does not carry area headings, and the grouping I got back was explicitly
labeled as inferred "based on typical stadium layouts" rather than read from the
page. That is a guess, so it is excluded here.

**Gaps at Las Vegas Ballpark:** backstop distance; per-section distance and
angle; which numbered sections sit behind home plate vs. on each foul line;
mapping between the official price-tier labels and the numbered sections.

---

## Part 2 — Protective netting, all 31 parks

### How to read this section

Netting extents below come, wherever possible, from the club's **own** current
seating-map or netting page on mlb.com, read in a browser on 2026-08-09. Most of
those pages carry a "© 2026 MLB Advanced Media" footer, so they reflect the
current season. That is a much better vintage than the secondary compilations
(2019–2020) that dominate search results, and in several cases the current
official extent differs materially from the 2019–2020 figure — Angel Stadium is
now 103–133, versus 110–126 in 2019.

**A structural caveat on "fully behind / partially / exposed."** The task asked
for that three-way split. The sources do not support it. Almost every club uses
the same formula — "there is some amount of netting or screening in front of the
following seating sections; the height and coverage of netting or screening will
vary by section" — and then adds that fans in those sections "are still exposed
to objects leaving the field of play." So what is actually sourced is a binary:
sections inside the listed range have *some* netting in front of them, sections
outside it have none. **Exactly one club publishes a partial-coverage flag:** the
Twins mark Target Field section 126 as "Partially covered." Everything else would
require photo-by-photo review to split further.

Heights, where clubs publish them, are included — they are the closest thing to a
real geometric constraint in this dataset.

### League-wide baseline (historical context, not current state)

| Fact | Source |
|---|---|
| MLB announced 2019-12-11 that all 30 clubs would extend netting for 2020, "substantially beyond the end of the dugout" — 15 clubs extending down the lines, 7 more all the way to the foul poles, 8 having already extended previously | [Ballpark Digest, 2019-12-11](https://ballparkdigest.com/2019/12/11/all-mlb-ballparks-will-feature-extended-netting-in-2020/); [CNBC, 2019-12-11](https://www.cnbc.com/2019/12/11/baseball-commissioner-says-all-30-mlb-teams-to-expand-protective-netting.html) |
| The White Sox were the first club with netting foul pole to foul pole, in July 2019 | [ESPN](https://www.espn.com/mlb/story/_/id/27240576/white-sox-first-team-employ-extended-netting); [SI, 2019-07-22](https://www.si.com/mlb/2019/07/22/white-sox-debut-full-protective-netting-marlins) |
| As of August 2021: 6 parks pole-to-pole, 5 deep down the lines but short of the poles, 17 to the "elbows" | [SI, 2021-08-10](https://www.si.com/mlb/2021/08/10/crying-foul-mlb-netting-daily-cover) |
| Minor-league (Professional Development League) clubs required to install netting **foul pole to foul pole** "unless the configuration of the ballpark makes such coverage unnecessary," with height standardized from behind home plate to the end of each dugout, installed **no later than 2025 Opening Day** | [Ballpark Digest, 2022-12-07](https://ballparkdigest.com/2022/12/07/new-milb-netting-standards-imposed-by-major-league-baseball/); [Sen. Durbin press release, 2022-12-07](https://www.durbin.senate.gov/newsroom/press-releases/durbin-mlb-announce-new-netting-requirements-for-all-professional-development-league-clubs-to-increase-fan-safety) |

That last row is the only netting authority I have for Sutter Health Park and Las
Vegas Ballpark; see the two entries at the end of the table.

### Per-park netting — primary sources

All rows marked *primary* were read directly from the live page on 2026-08-09.

| # | Registry key | Park | Netted sections (as published) | Height | Source |
|---|---|---|---|---|---|
| 1 | `yankee_stadium` | Yankee Stadium | Section 011 (1B/RF side) → behind home → Section 029 (3B/LF side) | 31 ft above field wall behind the plate (Sections 018–021B); 11'6" above the wall in front of 017B and 022; 9 ft above the dugouts, retractable up 3 ft pregame; 11'6" above wall at 025 and 015A; ~14 ft above field (~11'6" above walls) from 014B→011 and 026→029 | *primary* — [mlb.com/yankees/ballpark/netting](https://www.mlb.com/yankees/ballpark/netting) |
| 2 | `fenway_park` | Fenway Park | Field Box 79 → Field Box 9 | ~12 ft 8 in above the playing field, varying | *primary* — [mlb.com/redsox/ballpark/netting](https://www.mlb.com/redsox/ballpark/netting) |
| 3 | `dodger_stadium` | Dodger Stadium | Behind home plate → end of baseline section 40 (1B) and section 41 (3B) | not stated | *primary* — [mlb.com/dodgers/ballpark/netting](https://www.mlb.com/dodgers/ballpark/netting) |
| 4 | `wrigley_field` | Wrigley Field | "along the first and third base lines to the outfield edge of each dugout" — no section numbers given | not stated | *primary* — Wrigley Field A-Z guide, "Netting" entry, [mlb.com/cubs/ballpark/information/guide](https://www.mlb.com/cubs/ballpark/information/guide) |
| 5 | `coors_field` | Coors Field | front of Sections 112–147 | not stated | *primary* — Coors Field seating chart page, reached via [mlb.com/rockies/ballpark/netting](https://www.mlb.com/rockies/ballpark/netting), which redirects there |
| 6 | `chase_field` | Chase Field | Sections 111–133 | ~30 ft | *primary* — [mlb.com/dbacks/ballpark/netting](https://www.mlb.com/dbacks/ballpark/netting) |
| 7 | `truist_park` | Truist Park | Sections 10–42 and 111–141 | not stated | *primary* — Truist Park A-Z guide, [mlb.com/braves/ballpark/information/guide](https://www.mlb.com/braves/ballpark/information/guide) |
| 8 | `camden_yards` | Oriole Park at Camden Yards | Section 6 → Section 70 | not stated | *primary* — [mlb.com/orioles/ballpark/seating-map](https://www.mlb.com/orioles/ballpark/seating-map) |
| 9 | `citizens_bank` | Citizens Bank Park | Diamond Club A–G; Field Level 109–138 | varies by section | *primary* — [mlb.com/phillies/ballpark/netting](https://www.mlb.com/phillies/ballpark/netting) |
| 10 | `great_american` | Great American Ball Park | Sections 1–5, 22–25, and 111–135 | varies by section | *primary* — [mlb.com/reds/ballpark/netting](https://www.mlb.com/reds/ballpark/netting) (Great American Ball Park seating map) |
| 11 | `progressive_field` | Progressive Field | Sections 128–174 (enumerated individually on the page) | varies by section | *primary* — [mlb.com/guardians/ballpark/netting](https://www.mlb.com/guardians/ballpark/netting) |
| 12 | `comerica_park` | Comerica Park | behind home plate → Section 116 (1B line) and Section 142 (3B line) | not stated; netting described as "20 percent more narrow" than the prior system | *primary* — [mlb.com/tigers/ballpark/netting](https://www.mlb.com/tigers/ballpark/netting) (Comerica Park seating map) |
| 13 | `minute_maid` | Daikin Park (formerly Minute Maid Park) | Sections 112–126 and the Diamond Club | not stated | *primary* — [mlb.com/astros/ballpark/seat-map](https://www.mlb.com/astros/ballpark/seat-map) |
| 14 | `kauffman_stadium` | Kauffman Stadium | **no section numbers published** — the club states only that the map "show[s] the general location where additional netting has been installed" and that "it is not possible for a map like this to show the precise location of the netting" | not stated | *primary* — [mlb.com/royals/ballpark/seating-map](https://www.mlb.com/royals/ballpark/seating-map). Secondary fallback: RateYourSeats (updated 2020-03-20) lists 107–148 |
| 15 | `angel_stadium` | Angel Stadium | Sections 103–133 | not stated | *primary* — [mlb.com/angels/ballpark/netting](https://www.mlb.com/angels/ballpark/netting). Note: this is materially wider than the 110–126 reported in 2019 sources |
| 16 | `citi_field` | Citi Field | **no official statement found.** *Secondary — unverified:* netting in front of sections 107–128, with the net proper 111–124 and a protective fence continuing to 107 and 128 | not stated | Gap at the primary level; the Mets' `/ballpark/netting` and seat-map pages carry no netting text (checked 2026-08-09). Secondary via web search of RateYourSeats Citi Field pages |
| 17 | `oakland_coliseum` → Sutter Health Park | Sutter Health Park | **no club statement found.** The A's A-Z guide has no netting entry, and the Sutter Health Park ballpark-map page carries no netting text (both checked 2026-08-09). The only applicable authority is the PDL rule: foul pole to foul pole, by 2025 Opening Day | not stated | Gap — see the PDL row in the baseline table above |
| 18 | `las_vegas_ballpark` | Las Vegas Ballpark | **no park-specific source found.** The A-to-Z guide tells guests to stay behind "railings and protective netting" without describing its extent. Same PDL rule applies (Aviators are Triple-A) | not stated | Gap. Note: a web-search summary attributed "nets extend to the far ends of the dugouts and are extremely high" to a Las Vegas Review-Journal article, but on fetching that article ([2018-02-01](https://www.reviewjournal.com/sports/aviatorsbaseball/major-league-baseball-expands-netting-at-all-parks/)) it contains no LVB-specific detail — the claim is not supported |
| 19 | `pnc_park` | PNC Park | Section 101 → Section 130 | varies by section | *primary* — [mlb.com/pirates/ballpark/seat-map](https://www.mlb.com/pirates/ballpark/seat-map) (PNC Park 3D seating chart) |
| 20 | `petco_park` | Petco Park | All Lexus Home Plate Club sections; Field VIP 101–106; **full square** net coverage 109–110; **angled** net coverage 111–115 (1B side) and 112–116 (3B side) | not stated | *primary* — [mlb.com/padres/ballpark/netting](https://www.mlb.com/padres/ballpark/netting). This is the only club that distinguishes net *geometry* (square vs. angled) by section |
| 21 | `oracle_park` | Oracle Park | Sections 101–135 | varies by section | *primary* — [mlb.com/giants/ballpark/seat-map](https://www.mlb.com/giants/ballpark/seat-map) |
| 22 | `tmobile_park` | T-Mobile Park | Sections 115–146 | 27 ft in front of Sections 126–134; 13.5 ft above field level for 115–125 and 135–146 | *primary* — [mlb.com/mariners/ballpark/seat-map](https://www.mlb.com/mariners/ballpark/seat-map) |
| 23 | `busch_stadium` | Busch Stadium | By product: Cardinals Club 1–8; Home Field Box 145–155; Diamond Box 140–145 and 155–160; Infield Field Box 141–144 and 156–160; Dugout Box 132, 135–139, 161–165; 1B Field Box 135–140; 3B Field Box 161–165; Lower RF Box 132–134 | varies by section | *primary* — [mlb.com/cardinals/ballpark/netting](https://www.mlb.com/cardinals/ballpark/netting) |
| 24 | `tropicana_field` | Tropicana Field | "Protective netting extends from home plate to the foul poles located in Sections 137 and 138." Enumerated netted sections: 101–138 | varies by section | *primary* — [mlb.com/rays/ballpark/netting](https://www.mlb.com/rays/ballpark/netting). **Caution:** the same page ends with a contradictory sentence — "protective netting of varying heights is used in the Stadium from Section 125 to behind home plate to Section 126" — which appears to be stale boilerplate. The two statements cannot both describe the same installation |
| 25 | `globe_life` | Globe Life Field | Sections 1–26 | varies by section | *primary* — [mlb.com/rangers/ballpark/seat-map](https://www.mlb.com/rangers/ballpark/seat-map) |
| 26 | `rogers_centre` | Rogers Centre | Down the first and third baseline walls to Sections 113C and 130C respectively, "tapering off to the curve before the foul poles" | 30 ft (matching the height previously in place behind home plate) | *primary* — [mlb.com/bluejays/ballpark/netting](https://www.mlb.com/bluejays/ballpark/netting) |
| 27 | `target_field` | Target Field | Sections 7–10; 1–6 and 11–17; 109–119; 105–108 and 120–123; 103–104 and 124–125; **Section 126 — "Partially covered"** | varies by section | *primary* — [mlb.com/twins/ballpark/seat-map](https://www.mlb.com/twins/ballpark/seat-map). The only explicit partial-coverage flag in the league |
| 28 | `guaranteed_rate` | Rate Field | 49 sections: 108–156 (enumerated individually on the page) | varies by section | *primary* — [mlb.com/whitesox/ballpark/seat-map](https://www.mlb.com/whitesox/ballpark/seat-map) |
| 29 | `loan_depot` | loanDepot park | **No text published** — the club's seat-map page has a "loanDepot park Netting" heading whose content is an image ("Netting at loanDepot park") with no section list (checked 2026-08-09). *Secondary — unverified:* sections 8–21 | not stated | Gap at the primary level; secondary via web search of RateYourSeats loanDepot park pages, consistent with the 2020 RateYourSeats table (8–21) |
| 30 | `american_family` | American Family Field | Sections 108–128 | ~33 ft, measured from the warning-track surface | *primary* — [mlb.com/brewers/ballpark/netting](https://www.mlb.com/brewers/ballpark/netting) |
| 31 | `nationals_park` | Nationals Park | Terra Club A–E; PNC Diamond Club 119–126; Sections 109–118 and 127–135 | varies by section | *primary* — [mlb.com/nationals/ballpark/netting](https://www.mlb.com/nationals/ballpark/netting). Page text references the 2026 season explicitly |

Count: 26 of 31 parks have a current, primary, section-level netting extent.
Wrigley Field has a current primary statement without section numbers. Kauffman
Stadium, Citi Field, and loanDepot park have no current primary section list
(secondary figures noted). Sutter Health Park and Las Vegas Ballpark have no
park-specific netting source at all.

### Historical netting compilations (for change detection only)

Two secondary compilations cover all 30 MLB parks at a single point in time.
They are useful for seeing *how much* netting has moved, and useless as current
state. Several rows in the 2020 table are visibly garbled (Dodger Stadium listed
as "41-40", Tropicana Field as "117-118", Rogers Centre as "113D-130D"), which is
itself a reason to prefer the club pages.

- [RateYourSeats, "Protective Netting Locations at Every MLB Stadium"](https://www.rateyourseats.com/blog/cheap_seats/protective-netting-locations-at-every-mlb-stadium)
  — **published 2018-06-11, updated 2020-03-20.** Per-stadium section ranges for
  all 30 parks.
- [Redden Net, "30 MLB ballparks and their safety netting"](https://www.redden-net.com/netting-news/ballparks-and-their-safety-netting/)
  — **undated, references events through mid-2019.** Per-park ranges reflecting
  the pre-2020 state.

Examples of how far the current extents have moved from the 2019 snapshot:

| Park | 2019 (Redden Net) | Current (club page, 2026) |
|---|---|---|
| Angel Stadium | 110–126 | 103–133 |
| Chase Field | 115–129 | 111–133 |
| Great American Ball Park | 113–133 (+1–5, 22–25) | 111–135 (+1–5, 22–25) |
| Progressive Field | 140–164 | 128–174 |
| Kauffman Stadium | 120–135 | not published |
| Dodger Stadium | 10–15 | home plate → sections 40 and 41 |

### Photographic evidence

The task suggested seat-review photos as the most reliable evidence, and that is
true for resolving *partial* coverage — which is exactly the axis the club pages
do not describe. I did not do that review: it requires opening per-section photo
galleries at 31 parks and judging net edges by eye, which is a substantially
larger job than the text research above and produces judgments rather than
citable figures. Flagging it as the obvious next step if the fully/partial/exposed
split matters to the model. A View From My Seat maintains per-section galleries
for all three Part 1 parks
([Fenway](https://aviewfrommyseat.com/venue/Fenway+Park/sections/),
[Sutter Health Park](https://aviewfrommyseat.com/venue/Sutter+Health+Park/sections/),
[Las Vegas Ballpark](https://aviewfrommyseat.com/venue/las+vegas+ballpark/sections/)),
with photo counts per section, so the raw material is there.

---

## Consolidated gap list

**Part 1 — geometry**

1. Distance from home plate to any named section — **all three parks**. Not
   published anywhere I could find.
2. Angle off the foul line for any named section — **all three parks**. Same.
3. Deck elevations (height above field) per section — **all three parks**.
4. Backstop distance — **Sutter Health Park** and **Las Vegas Ballpark** (Fenway
   is sourced at 60 ft).
5. Which numbered sections sit behind home plate at **Sutter Health Park** —
   two sources conflict (MLB.com: Dugout Club fronts 108–116 behind the plate;
   A View From My Seat: 103–104 behind the plate).
6. Which numbered sections sit behind home plate / on each foul line at
   **Las Vegas Ballpark** — the official map is a tier-labeled image and the
   number mapping could not be read.
7. Primary confirmation of Fenway dugout-to-section mapping (secondary sources
   say Red Sox dugout fronts 21–28, visitors 62–69).

**Part 2 — netting**

8. Current section-level netting extent for **Sutter Health Park** and
   **Las Vegas Ballpark**. Only the PDL foul-pole-to-foul-pole requirement
   (effective by 2025 Opening Day) applies, and neither venue publishes its
   actual installation.
9. Current section-level extent for **Kauffman Stadium** (club declines to
   publish sections), **Citi Field**, and **loanDepot park** (netting shown only
   as an image).
10. Section numbers for **Wrigley Field** — the club describes the extent
    verbally ("to the outfield edge of each dugout") but publishes no sections.
    Note this also conflicts with 2020 reporting that Wrigley's netting was
    extended from 340 ft to 560 ft, past the dugouts toward both corners; the
    current A-Z guide language may be stale.
11. **Netting heights** for most parks. Published for only 7: Yankee Stadium,
    Fenway, Chase Field, Rogers Centre, T-Mobile Park, American Family Field,
    and (as a change figure) Comerica Park.
12. **Fully-behind vs. partially-covered vs. exposed** per section. Sourced for
    exactly one section league-wide (Target Field 126, "Partially covered").
    Everything else would need the photo review described above.
13. **Tropicana Field** self-contradiction on its own netting page needs
    resolving with the club, particularly since the park reopened for 2026 after
    ~$60M of hurricane repairs including a new roof
    ([ESPN](https://www.espn.com/mlb/story/_/id/46947195/rays-return-tropicana-field-26-hurricane-repairs)) —
    the netting page may predate the reopening.
