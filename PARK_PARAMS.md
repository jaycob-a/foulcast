# PARK_PARAMS.md

Real per-park physical parameters for the 31-park registry in
`foulball/stadium.py`: **foul territory area**, **backstop distance**, and
**deck configuration near the infield**.

Every number below carries a citation. Where a figure is not published, it is
listed as a gap rather than estimated.

**Status: applied.** As of Step 9 these figures are written into
`foulball/stadium.py`, in the "Sourced per-park physical parameters" block.
What was adopted, and how:

- **Backstop distance** — Clem only, at 30 of 31 parks, chosen as a single
  source so that every park uses one reference point rather than mixing
  definitions (§2). Where his park page is newer than his master table and
  they differ, the page wins.
  Backstop distance is also applied **absolutely**: the front row of the
  behind-plate sections is pinned to it at all 31 parks, where the template
  had that row 2.7 ft (Yankee) to 23.0 ft (Dodger) in front of the backstop at
  every park, median 6.8 ft. This is what makes the figure a position and not
  only a ratio. Clem's figure is the distance to the *fence*, so the anchor
  targets `backstop_ft + 1.0 ft` and the seats stand behind the fence rather
  than on it; that 1 ft setback is a documented floor, not a measurement — see
  gap 7.
- **Foul territory area** — the Adopt column of Part 1, at 29 parks. Used as
  `sqrt(area / 22,900)` — 22,900 sq ft being the fleet median — to set each
  park's radial scale down the lines. Backstop distance sets it behind the
  plate; sections in between take a mid-angle blend of the two.
- **Overhang** — the 2016 percentages of Part 3, at 27 parks, pulling each
  deck's rear extent in by the covered fraction of the depth it actually owns.
  Applied **uncapped**, but only where the cover is something a foul pop would
  actually hit. Which parks those are is a judgment call and not a sourced
  one, because Clem publishes a percentage and never says what is casting it:

  | Cover | Parks | Applied? |
  |---|---|---|
  | Deck above (Clem's "split upper") | Yankee, Coors, Citizens Bank, Citi, Petco, Busch, Target, Nationals — 8 | yes |
  | Grandstand canopy | Fenway, Dodger, Wrigley, Camden, Great American, Progressive, Comerica, Kauffman, Angel, PNC, Oracle, T-Mobile, Rate — 13 | yes |
  | Dome / retractable roof, 150+ ft up | Chase, Daikin, Tropicana, Rogers, loanDepot, American Family — 6 | **no** |
  | No published figure | Truist, Globe Life, Sutter Health, Las Vegas — 4 | n/a |

  The rule is Clem's own "decks near the infield" column: "split upper" ⇒
  deck, "(roof)"/"(dome)" ⇒ stadium roof, everything else ⇒ canopy. Chase
  Field is the one exception — he labels it plainly "3", but it is a
  retractable-roof park. Two checks that the split is not circular: the six
  roof parks' upper figures are 100/100/100/100/93/75, the top of the fleet;
  and their *lower* figures are 5/25/25/30/30/30, squarely inside the range
  the open-air parks occupy, which is why lower-deck overhang is applied
  everywhere without needing the classification at all.

  This replaces a flat 60% cap, which existed only to stop the six roofed
  parks' 93–100% from deleting their upper decks, and which paid for that by
  understating Wrigley's 100% — a genuine low grandstand roof. Wrigley's upper
  deck now owns no exposed ground, which is the intended reading.
- **Nothing angular or vertical was applied**, because gaps 3, 4 and 12 below
  mean no source supports it. Every park stays mirror-symmetric.
- **The two gap parks keep the template's proportions, and are labelled.**
  Neither the radial scale nor the overhang pull-in runs at Las Vegas Ballpark
  or Sutter Health Park. The backstop anchor does run at both — at Sutter off
  Clem's sourced "(58)", and at Las Vegas off an unsourced default of 52 ft.
  That last is the one place in `stadium.py` where an unsourced number moves
  geometry; it is done because the anchor encodes a physical constraint rather
  than a park-to-park difference, and it is flagged at the factory.

Research date: **2026-08-09**. All pages retrieved that day.

Three rules I held to:

1. **No derived numbers.** I did not compute foul-territory area from outfield
   dimensions, and I did not convert row counts into deck heights. If a source
   did not state the figure, it is a gap.
2. **Provenance over count.** Where two sources agree, I checked whether they
   are actually independent before treating the agreement as confirmation. In
   this domain they usually are not — see below.
3. **Conflicts are reported, not resolved.** Where sources disagree materially
   I give all values side by side and say which I'd weight, rather than
   silently picking one.

---

## The source landscape, stated up front

### Foul territory area is effectively single-sourced

Three sites publish per-park foul-territory square footage. They are not three
sources:

- **[Clem's Baseball — Stadium Statistics](http://www.andrewclem.com/Baseball/Stadium_statistics.html)**
  (last modified 2026-04-19). Clem states his method plainly: *"Fair & foul
  territory, measured in 1,000 square feet, rounded to the nearest 100 feet, are
  estimates based on the diagrams. ALL data in these columns are subject to
  revision."* The diagrams are his own scale drawings. Sources credited at the
  foot of the page: Lowry (2019), Ritter (1992), ESPN Sports Almanac.
- **[Seamheads.com Ballparks Database](https://www.seamheads.com/ballparks/index.php)**.
  Its [about page](https://www.seamheads.com/ballparks/about.php) names
  *"Green Cathedrals by Phillip Lowry — primary source of Park Configuration
  data"*, and warns the configuration data *"should be understood to be based on
  many reported measurements which may be unreliable and may conflict with other
  reported measurements."* Its foul-territory column matches Clem's to the
  decimal at 26 of 28 parks where both publish a figure.
- **[FanGraphs, "Ballpark Playing Surfaces Are Shrinking in a Surprising Way"](https://blogs.fangraphs.com/ballpark-playing-surfaces-are-shrinking-in-a-surprising-way/)**
  (Travis Sawchik, 2018-01-30). Sawchik credits the figures to Clem's site
  explicitly. Not an independent measurement.

So: **there is one estimate of MLB foul-territory area in public circulation**,
Clem's, cross-checked against Lowry's *Green Cathedrals*. It is a careful
estimate by a careful person, but it is an estimate off diagrams, not a survey.
Treat the numbers as good to roughly ±1,000 sq ft, not to the ±100 sq ft the
decimal place implies.

I found **no** surveyed or CAD-derived foul-territory figures, and nothing from
MLB or Statcast. Statcast publishes park outlines for fair territory only.

### Backstop distance is genuinely contested

Here there *are* independent sources — Clem, Seamheads, and club/Wikipedia
infobox figures — and **they disagree at 11 of the 20 parks where all three
publish a value.** The disagreements are not rounding; they run to 13 feet.

The likely cause is definitional. The three sources measure different things:

| Source | Stated definition |
|---|---|
| Clem | *"Backstop is simply the distance from home plate to the fence in the rear."* ([Stadium Statistics](http://www.andrewclem.com/Baseball/Stadium_statistics.html)) |
| Seamheads | *"Backstop: Distance from Home Plate to Stands"* ([about](https://www.seamheads.com/ballparks/about.php)) |
| Club / Wikipedia infobox | Undefined; usually the club's published figure, and frequently the **as-built** number rather than the current one |

The as-built problem is real and demonstrable. Wikipedia's
[Kauffman Stadium](https://en.wikipedia.org/wiki/Kauffman_Stadium) infobox gives
*"Backstop – 60 ft (1973–present)"*, but Clem's
[Kauffman page](http://www.andrewclem.com/Baseball/KauffmanStadium.html) records
that *"In 1999 a few rows of high-class box seats were squeezed in behind home
plate, cutting the backstop distance from 60 feet to about 50"* — and his current
table says 45. The infobox is 27 years stale. The same pattern shows at Fenway,
where [Wikipedia](https://en.wikipedia.org/wiki/Fenway_Park) notes the backstop
*"was shortened from 68 feet to 60 feet"* and stops there.

For a foul-ball model, **backstop distance is the parameter that most directly
sets how many fouls are catchable behind the plate**, and it is the parameter
whose sources least agree. That is the main finding of this document.

### Clem's per-park pages are newer than his master table

His master table was last modified 2026-04-19. Twenty-five of the 30 park pages
were modified *after* that date (I read `Last-Modified` headers directly). Where
they differ I have taken the newer page and said so. Four pages are older than
the table — Tropicana Field (2019-07-09), Oracle Park (2019-12-19), T-Mobile Park
(2023-07-13), loanDepot park (2023-05-24) — and for those the table wins.

### Retrieval note

`andrewclem.com` is HTTP-only and its TLS certificate is issued to a different
host (`server292.com`), so any fetcher that force-upgrades to HTTPS will fail on
a cert-name mismatch. It must be read over plain HTTP.

---

## Part 1 — Foul territory area

Clem/Seamheads units are 1,000 sq ft. The **Adopt** column is the value I would
use, with the reason.

| # | Park (`stadium.py` key) | Clem table (04/2026) | Clem park page | Seamheads 2025 | **Adopt (sq ft)** | Basis |
|---|---|---|---|---|---|---|
| 1 | Yankee Stadium `yankee_stadium` | 19.7 | 19.7 | 19.7 | **19,700** | all agree |
| 2 | Fenway Park `fenway_park` | 18.1 | 18.1 | 18.1 | **18,100** | all agree; smallest in MLB |
| 3 | Dodger Stadium `dodger_stadium` | 19.3 | 19.3 | 19.3 | **19,300** | all agree |
| 4 | Wrigley Field `wrigley_field` | 18.6 | **16.5** | 16.5 | **16,500** | page + Seamheads; table is pre-2016 |
| 5 | Coors Field `coors_field` | 24.9 | 24.9 | 24.9 | **24,900** | all agree |
| 6 | Chase Field `chase_field` | 25.5 | 25.5 | 25.5 | **25,500** | all agree |
| 7 | Truist Park `truist_park` | 22.3 | 22.3 | 22.3 | **22,300** | all agree |
| 8 | Camden Yards `camden_yards` | 23.6 | 23.6 | 23.6 | **23,600** | all agree |
| 9 | Citizens Bank Park `citizens_bank` | 24.5 | 24.5 | 24.5 | **24,500** | all agree |
| 10 | Great American Ball Park `great_american` | 23.6 | 23.6 | 23.6 | **23,600** | all agree |
| 11 | Progressive Field `progressive_field` | 21.9 | 21.9 | 21.9 | **21,900** | all agree |
| 12 | Comerica Park `comerica_park` | 26.5 | 26.5 | 26.5 | **26,500** | all agree; largest open-air park |
| 13 | Daikin Park `minute_maid` | 21.0 | 21.0 | 21.0 | **21,000** | all agree |
| 14 | Kauffman Stadium `kauffman_stadium` | 22.9 | 22.9 | 22.9 | **22,900** | all agree |
| 15 | Angel Stadium `angel_stadium` | 21.5 | 21.5 | 21.5 | **21,500** | all agree |
| 16 | Citi Field `citi_field` | 20.7 | 20.7 | 20.7 | **20,700** | all agree |
| 17 | Sutter Health Park `oakland_coliseum` | — | — (blank) | — (blank) | **GAP** | see §1.1 |
| 18 | Las Vegas Ballpark `las_vegas_ballpark` | not listed | no page | not listed | **GAP** | see §1.1 |
| 19 | PNC Park `pnc_park` | 22.2 | 22.2 | 22.2 | **22,200** | all agree |
| 20 | Petco Park `petco_park` | 23.9 | 23.9 | 23.9 | **23,900** | all agree |
| 21 | Oracle Park `oracle_park` | 25.5 | 25.5 | 25.5 | **25,500** | all agree |
| 22 | T-Mobile Park `tmobile_park` | **24.3** | 23.9 (2023) | 24.3 | **24,300** | table + Seamheads; page predates |
| 23 | Busch Stadium `busch_stadium` | 25.2 | 25.2 | 25.4 | **25,200** | Clem ×2 over Seamheads |
| 24 | Tropicana Field `tropicana_field` | 25.3 | 25.3 | 25.3 | **25,300** | all agree |
| 25 | Globe Life Field `globe_life` | 23.1 | 23.1 | 23.1 | **23,100** | all agree |
| 26 | Rogers Centre `rogers_centre` | 29.0 | **30.5** | not published | **30,500** | newer page; largest in MLB |
| 27 | Target Field `target_field` | 20.7 | 20.7 | 20.4 | **20,700** | Clem ×2 over Seamheads |
| 28 | Rate Field `guaranteed_rate` | 25.0 | 25.0 | 25.0 | **25,000** | all agree |
| 29 | loanDepot park `loan_depot` | **21.0** | 19.1 (2023) | 21.0 | **21,000** | table + Seamheads; page predates |
| 30 | American Family Field `american_family` | 21.1 | 21.1 | 21.1 | **21,100** | all agree |
| 31 | Nationals Park `nationals_park` | 23.1 | **22.8** | not published | **22,800** | newer page |

Sources for the columns above, per park: Clem's
[Stadium Statistics](http://www.andrewclem.com/Baseball/Stadium_statistics.html)
table; the individual Clem park page (URLs in §4); and the Seamheads
[ballpark configuration](https://www.seamheads.com/ballparks/index.php) row for
2025 (Tropicana Field's latest row is 2024 — the Rays did not play there in 2025).

Range across the 29 sourced parks: **16,500 sq ft (Wrigley) to 30,500 sq ft
(Rogers Centre)** — a factor of 1.85. For comparison, the Oakland Coliseum, which
the Athletics left after 2024, carried **40,700 sq ft**, by far the largest of
the modern era ([Clem](http://www.andrewclem.com/Baseball/Stadium_statistics.html)).

### 1.1 Foul territory gaps

**Sutter Health Park** — Clem has a
[park page](http://www.andrewclem.com/Baseball/SutterHealthPark.html) but leaves
the fair and foul territory cells blank (`-`), as does
[Seamheads](https://www.seamheads.com/ballparks/ballpark.php?parkID=SAC01).
Qualitative only, from Clem's page: *"The playing field at Sutter Health Park has
a very constricted foul territory, though the sharply acute angle of the
grandstand does provide more room between home plate and the dugouts."*
[Grokipedia's Sutter Health Park page](https://grokipedia.com/page/Sutter_Health_Park)
also describes *"limited foul territory"* relative to permanent MLB parks, but
gives no measurement and is not a citable source for a figure.

**Las Vegas Ballpark** — no foul-territory figure anywhere. Not in Clem's
registry (he covers MLB venues; the nearest entry is
[Cashman Field](http://www.andrewclem.com/Baseball/CashmanField.html), the
Aviators' former home), not in Seamheads, not in
[Wikipedia](https://en.wikipedia.org/wiki/Las_Vegas_Ballpark).

### 1.2 Foul territory changes worth knowing

- **Wrigley Field.** Clem's footnote: *"Foul territory shrunk by about 2,000
  square feet after 2016"* — four rows of seats added along the third-base side
  and one row between the dugouts and along the first-base side, where the
  visitors' bullpen had been. He also notes the asymmetry: *"foul territory is
  quite asymmetrical, with more room on the first base side than on the third
  base side."* ([Clem, Wrigley Field](http://www.andrewclem.com/Baseball/WrigleyField.html))
  This is the only per-park statement of foul-territory **asymmetry** I found
  anywhere, and it is qualitative.
- **Dodger Stadium.** Clem records three eras: 27,900 sq ft (1962–68), *"from
  1969 until 1999, Dodger Stadium had one of the roomiest foul territories of any
  stadium: about 33,500 square feet foul territory and 110,500 square feet
  fair,"* and 19,300 today. His comment is directly on point for this model:
  *"The squeezing of the once-vast foul territory yields far fewer pop foul outs."*
  ([Clem, Dodger Stadium](http://www.andrewclem.com/Baseball/DodgerStadium.html))
- **Camden Yards.** Fair territory grew from 108,100 to 111,900 sq ft with the
  2022 left-field expansion, partially reduced in 2025; Clem now marks fair as a
  tentative `~110~` on the park page while the master table still says 108.1.
  Foul territory is unaffected at 23.6.
  ([Clem, Camden Yards](http://www.andrewclem.com/Baseball/CamdenYards.html))
- **League-wide trend.** *"Foul territory has diminished by 20.5%, or about 5,500
  square feet on average"* across parks replaced in the modern era, while fair
  territory fell only 1.4%
  ([FanGraphs](https://blogs.fangraphs.com/ballpark-playing-surfaces-are-shrinking-in-a-surprising-way/)).

---

## Part 2 — Backstop distance

All values in feet. **Model** is the value `foulball/stadium.py` carried
*before* Step 9. Every park except Las Vegas Ballpark now carries the Clem
column instead.

| # | Park | Clem table | Clem page | Seamheads | Club / Wikipedia | Model | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Yankee Stadium | 52 | 52 | 52 | **52 ft 4 in** [w](https://en.wikipedia.org/wiki/Yankee_Stadium) | 52 | ✅ all agree |
| 2 | Fenway Park | 54 | **52** | 54 | **60** [w](https://en.wikipedia.org/wiki/Fenway_Park) | 60 | ⚠️ 52 / 54 / 60 |
| 3 | Dodger Stadium | 53 | 53 | **57** | **55** [w](https://en.wikipedia.org/wiki/Dodger_Stadium) | 55 | ⚠️ 53 / 55 / 57 |
| 4 | Wrigley Field | 55 | 55 | 55 | **55** [w](https://en.wikipedia.org/wiki/Wrigley_Field) | 56 | ✅ all agree at 55 |
| 5 | Coors Field | 50 | 50 | 50 | **56** [w](https://en.wikipedia.org/wiki/Coors_Field) | 56 | ⚠️ 50 vs 56 |
| 6 | Chase Field | 55 | 55 | 55 | not published | 54 | ✅ Clem+SH agree |
| 7 | Truist Park | (53) est. | (53) est. | 53 | not published | 55 | ✅ but Clem marks estimate |
| 8 | Camden Yards | 54 | 54 | 54 | not published | 57 | ✅ Clem+SH agree |
| 9 | Citizens Bank Park | 50 | 50 | 50 | not published | 55 | ✅ Clem+SH agree |
| 10 | Great American Ball Park | 50 | 50 | **51** | **55** [w](https://en.wikipedia.org/wiki/Great_American_Ball_Park) | 54 | ⚠️ 50 / 51 / 55 |
| 11 | Progressive Field | 60 | 60 | **65** | **60** [w](https://en.wikipedia.org/wiki/Progressive_Field) | 55 | ⚠️ 60 vs 65 |
| 12 | Comerica Park | 55 | 55 | **52** | not published | 55 | ⚠️ 52 vs 55 |
| 13 | Daikin Park | 49 | 49 | 49 | **49** [w](https://en.wikipedia.org/wiki/Daikin_Park) | 54 | ✅ all agree |
| 14 | Kauffman Stadium | 45 | 45 | 45 | 60 (as-built) [w](https://en.wikipedia.org/wiki/Kauffman_Stadium) | 55 | ✅ 45 — Wikipedia stale, see below |
| 15 | Angel Stadium | 59 | **56** | **60** | **60.5** [w](https://en.wikipedia.org/wiki/Angel_Stadium) | 55 | ⚠️ 56 / 59 / 60 / 60.5 |
| 16 | Citi Field | 46 | 46 | 46 | not published | 55 | ✅ Clem+SH agree |
| 17 | Sutter Health Park | — | (58) est. | 58 | **58** [w](https://en.wikipedia.org/wiki/Sutter_Health_Park) | 55 | ✅ 58, but Clem marks estimate |
| 18 | Las Vegas Ballpark | — | — | — | not published | 52 | ❌ **GAP** |
| 19 | PNC Park | 51 | 51 | 51 | **51** [w](https://en.wikipedia.org/wiki/PNC_Park) | 54 | ✅ all agree |
| 20 | Petco Park | 45 | 45 | 45 | not published | 55 | ✅ Clem+SH agree; prose confirms |
| 21 | Oracle Park | 54 | 54 | 54 | **48** [w](https://en.wikipedia.org/wiki/Oracle_Park) | 55 | ⚠️ 48 vs 54 |
| 22 | T-Mobile Park | 56 | 56 | **55** | **69** [w](https://en.wikipedia.org/wiki/T-Mobile_Park) | 55 | ⚠️ **55 / 56 / 69** — worst conflict |
| 23 | Busch Stadium | 52 | 52 | 52 | not published | 55 | ✅ Clem+SH agree |
| 24 | Tropicana Field | 50 | 50 | 50 | **50** [w](https://en.wikipedia.org/wiki/Tropicana_Field) | 55 | ✅ all agree |
| 25 | Globe Life Field | 42 | 42 | 42 | **42** [w](https://en.wikipedia.org/wiki/Globe_Life_Field) | 55 | ✅ all agree; shortest in MLB |
| 26 | Rogers Centre | 54 | 54 | 54 | **60** [w](https://en.wikipedia.org/wiki/Rogers_Centre) | 55 | ⚠️ 54 vs 60 |
| 27 | Target Field | 48 | **(45) est.** | 48 | not published | 55 | ⚠️ 45 / 48, Clem flags estimate |
| 28 | Rate Field | 60 | 60 | 60 | **60** [w](https://en.wikipedia.org/wiki/Rate_Field) | 55 | ✅ all agree; longest in MLB |
| 29 | loanDepot park | 50 | 50 | **47** | **47** [w](https://en.wikipedia.org/wiki/LoanDepot_Park) | 55 | ⚠️ 47 (×2) vs 50 |
| 30 | American Family Field | 56 | 56 | 56 | **56** [w](https://en.wikipedia.org/wiki/American_Family_Field) | 55 | ✅ all agree |
| 31 | Nationals Park | 45 | 45 | 45 | not published | 55 | ✅ Clem+SH agree |

Clem's figures are from the
[master table](http://www.andrewclem.com/Baseball/Stadium_statistics.html) and
each park's own page (URLs in §4). Seamheads figures are the `Back` column of the
2025 configuration row on each
[ballpark page](https://www.seamheads.com/ballparks/index.php) (Tropicana: 2024).

**Tally.** All available sources agree at 18 parks. They conflict at 12. One park
(Las Vegas Ballpark) has no source at all.

**Against the current model:** `stadium.py` matches **Clem's** value at just two
parks — Yankee Stadium (52) and Comerica Park (55). It matches *some* source at
six: those two plus Fenway (60, Wikipedia), Dodger (55, Wikipedia), Coors (56,
Wikipedia) and T-Mobile (55, Seamheads) — and at four of those six the agreement
is with the source the other two contradict, so it is closer to coincidence than
corroboration. Twenty-one parks currently carry the default 55. Sourced values run from **42 ft (Globe Life Field) to 60 ft (Rate
Field, Progressive Field)**, a spread the flat 55 erases entirely.

### 2.1 Notes on specific conflicts

- **Kauffman Stadium — resolved in Clem's favour.** Wikipedia's 60 ft is the
  1973 as-built figure. Clem documents the 1999 change (*"cutting the backstop
  distance from 60 feet to about 50"*) and his table now carries 45; Seamheads
  independently carries 45. Use 45.
  ([Clem](http://www.andrewclem.com/Baseball/KauffmanStadium.html))
- **T-Mobile Park — unresolved, and the largest gap.** 69 ft is the Mariners'
  officially published dimension, carried by
  [Wikipedia](https://en.wikipedia.org/wiki/T-Mobile_Park) and repeated by
  [Ballparks of Baseball](https://www.ballparksofbaseball.com/ballparks/t-mobile-park/).
  Clem says 56, Seamheads 55. A 13–14 ft discrepancy is too large for
  measurement error and almost certainly reflects two different reference points
  (rear wall vs. front of the seating bowl). I would not adopt either without
  deciding which the model's `backstop_distance` is supposed to represent.
- **Angel Stadium — four different values.** Clem's page adds the useful note:
  *"Another issue is the distance to the backstop: Most sources state that it was
  originally 55 feet and then raised to 60."* His own current-era row (1999–) says
  56. ([Clem](http://www.andrewclem.com/Baseball/AngelStadium.html))
- **Target Field — Clem flags his own figure.** The park page carries a
  parenthetical *"(Backstop distance is estimated.)"* next to 45, while his master
  table and Seamheads both say 48.
  ([Clem](http://www.andrewclem.com/Baseball/TargetField.html))
- **Petco Park — corroborated in prose.** *"the backstop is only 45 feet from
  home plate, so most fans are close to the action."*
  ([Clem](http://www.andrewclem.com/Baseball/PETCOPark.html))
- **Rate Field — a structural detail that matters for foul balls.** In the 2002
  renovation, the *"Old backstop with netted roof was replaced with a new
  'roofless' backstop which allows foul balls to drop into seats directly behind
  home plate."* ([Wikipedia, Rate Field](https://en.wikipedia.org/wiki/Rate_Field))
  Rate Field also has the longest backstop in MLB at 60 ft. Both facts push the
  same way: it should be an outlier for balls reaching seats behind the plate.
- **Sutter Health Park — parenthesised.** Clem writes the 58 as `(58)`, his
  notation for an estimate, though Wikipedia and Seamheads both state 58 flat.

---

## Part 3 — Deck configuration near the infield

Clem's row counts are explicitly infield-referenced: *"Seating rows refer to a
'typical' portion of the grandstand in the vicinity of the infield."*
([Stadium Statistics](http://www.andrewclem.com/Baseball/Stadium_statistics.html))

The **overhang** columns are the more useful pair for a foul-ball model — they
measure how much of each deck is roofed over by the deck above, which determines
whether a high foul can reach those seats at all. Clem removed them from the live
table (*"Overhang / shade of upper deck and lower deck is no longer showed on this
page"*), so they are recovered from the
[2016-10-18 Wayback snapshot](https://web.archive.org/web/20161018114847/http://www.andrewclem.com:80/Baseball/Stadium_statistics.html).
That snapshot's legend is precisely on point:

> *"Overhang / shade is an estimate of how much the upper deck and lower deck
> were covered by a roof or higher-level deck. … For purposes of making overhang
> estimates, only the main portion of the grandstand situated relatively close to
> the infield is counted."*

Notation, per Clem's legend: `(parentheses)` = variable grandstand profile,
figure is typical; `a+b` = split upper deck, rows in each portion; `a/b` = the
profile varies between those two counts; `^` = bare frame roof extension.

| # | Park | Lower deck rows | Mezz / 2nd deck rows | Upper deck rows | Lower overhang | Upper overhang | Decks near infield |
|---|---|---|---|---|---|---|---|
| 1 | Yankee Stadium | 28 | 23 | 7+14 | 20% | 55% | 3 (split upper) |
| 2 | Fenway Park | 45 | 4 | 11 | 40% | 60% | 3 (tiny mezz) |
| 3 | Dodger Stadium | 24+16 | 20 | 20/16 † | 15% | 30% | 4+ — see note |
| 4 | Wrigley Field | 56 | 2 | 21 | 55% | 100% | 2 + token mezz |
| 5 | Coors Field | 38 | 14 | 9+16 | 20% | 35% | 3 (split upper) |
| 6 | Chase Field | 39 | 10 | 32/40 | (30%) | (75%) | 3 |
| 7 | Truist Park | 33 | 19 | 13+12 | **GAP** | **GAP** | 3 (split upper) |
| 8 | Camden Yards | 42 | 9 | 25 | 25% | 45% | 3 |
| 9 | Citizens Bank Park | 35 | 9 | 16+8 | 15% | 35% | 3 (split upper) |
| 10 | Great American Ball Park | 38 | 14 | 28 | 30% | 30% ^ | 3 |
| 11 | Progressive Field | 32 | (18) | 27 | 20% | 55% ^ | 3 |
| 12 | Comerica Park | 43 | 3 | 26 | 25% | 30% | 2 + token mezz |
| 13 | Daikin Park | 38 | 11 | 26 | 30% | 100% | 3 (roof) |
| 14 | Kauffman Stadium | 38 | 6 | (40) | 25% | (40%) | 3 |
| 15 | Angel Stadium | 33 | 12 | 24 | 35% | 45% | 3 |
| 16 | Citi Field | 38 | 12 | 17+6 | 20% | 30% | 3 (split upper) |
| 17 | Sutter Health Park | 30 | (6) | **none** | **GAP** | **GAP** | **2** |
| 18 | Las Vegas Ballpark | **GAP** | **GAP** | **GAP** | **GAP** | **GAP** | ~2 (qualitative) |
| 19 | PNC Park | 44 | 2 | 30 | 30% | 30% | 2 + token mezz |
| 20 | Petco Park | 38 | 15 | 21+6 | 40% | 30% ^ | 3 (split upper) |
| 21 | Oracle Park | 36 | 12 | 25 | 20% | 30% | 3 |
| 22 | T-Mobile Park | 42 | 12 | 26 | 30% | (55%) | 3 |
| 23 | Busch Stadium | (36) | 13 | 9+11 | (20%) | 60% | 3 (split upper) |
| 24 | Tropicana Field | 38 | 8 | 28/43 | 25% | 100% | 3 (dome) |
| 25 | Globe Life Field | 22 | 18 | 11+12 | **GAP** | **GAP** | 3 (split upper) |
| 26 | Rogers Centre | (30) | 12 | (24) | 5% | 100% | 3 (dome) |
| 27 | Target Field | 42 | 12 | 14+7 | 35% | 75% | 3 (split upper) |
| 28 | Rate Field | 38 | 5 | 21 | 15% | 70% | 2 + token mezz |
| 29 | loanDepot park | 40 | 10 | (22) | 25% | 100% | 3 (roof) |
| 30 | American Family Field | 27 | 21, 7 | 20+ | 30% | 93% | 3 (roof) |
| 31 | Nationals Park | 41 | 11 | 9+13 | 10% | 55% | 3 (split upper) |

Row counts are from each park's own Clem page (URLs in §4), which supersede the
master table where they differ (see §3.1). Overhang percentages are from the
[2016 snapshot](https://web.archive.org/web/20161018114847/http://www.andrewclem.com:80/Baseball/Stadium_statistics.html)
of the same table.

† **Dodger Stadium is ambiguous and I did not resolve it.** Clem's page carries
two eras in one row, with the original 1962–68 layout italicised, and the
italics do not survive text extraction. The raw cells read lower `24+16`,
mezzanine `20`, upper `29` and `20/16`. Dodger Stadium physically has more than
three seating levels near the infield (field, loge, reserve, top deck), which
Clem's three-column schema cannot represent. Treat this row as unresolved.
([Clem, Dodger Stadium](http://www.andrewclem.com/Baseball/DodgerStadium.html))

### 3.1 Where the park page and the master table disagree on rows

Reported for completeness; in each case I took the park page, which is newer.

| Park | Master table (04/2026) | Park page | Page modified |
|---|---|---|---|
| Fenway Park | 45 / 4 / 10 | 45 / 4 / **11** | 2026-07-17 |
| Chase Field | 39 / **11** / (40) | 39 / **10** / 32/40 | 2026-07-31 |
| Rate Field | 38 / **4** / 21 | 38 / **5** / 21 | 2026-07-20 |
| Coors Field | 38 / 14 / **25** | 38 / 14 / **9+16** | 2026-07-28 |
| Target Field | **40 / 13 / 21** | **42 / 12 / 14+7** | 2026-07-11 |
| loanDepot park | 40 / 10 / (22) | 42 / 12 / (22) | 2023-05-24 — *table is newer here, take 40 / 10 / (22)* |
| Citizens Bank Park | 35 / 9 / **24** | 35 / 9 / **16+8** | 2026-07-15 |
| Petco Park | 38 / 15 / **27** | 38 / 15 / **21+6** | 2026-07-31 |
| Busch Stadium | (36) / 13 / **20** | (36) / 13 / **9+11** | 2026-08-04 |
| Nationals Park | 41 / 11 / **22** | 41 / 11 / **9+13** | 2026-07-15 |
| Citi Field | 38 / 12 / **23** | 38 / 12 / **17+6** | 2026-07-16 |

Most of these are the same total expressed as a split (16+8 = 24, 21+6 = 27,
9+11 = 20, 9+13 = 22, 17+6 = 23, 9+16 = 25) — the park pages carry the finer
breakdown. Fenway, Chase, Rate and Target are genuine numeric revisions.

### 3.2 Deck configuration gaps

- **Las Vegas Ballpark** — no row counts, no overhang, from any source. What is
  published: capacity 8,196 (10,000 with standing room), *"22 suites, 400
  club-level seats and 350 party deck seats"*
  ([Wikipedia](https://en.wikipedia.org/wiki/Las_Vegas_Ballpark)). That implies a
  main bowl plus a suite/club level, but the page does not describe the deck
  structure and I will not infer row counts from it.
- **Sutter Health Park overhang** — not published. Structure is sourced:
  *"The main lower seating deck stretches from the left field foul pole to home
  plate and across to the right field foul pole,"* above which *"a smaller second
  deck includes a club seating area and 36 luxury suites"*
  ([Ballparks of Baseball](https://www.ballparksofbaseball.com/ballparks/sutter-health-park/),
  undated, references the 2025 season). Clem gives lower 30 rows, second deck
  `(6)`, no upper deck.
- **Truist Park and Globe Life Field overhang** — both opened after the 2016
  snapshot (2017 and 2020), so the recovered overhang table does not cover them,
  and Clem has not republished the columns. Row counts are available; overhang is
  a gap.
- **Four-plus deck parks** — Clem's schema has exactly three seating columns.
  Dodger Stadium, Truist Park and Globe Life Field all have more distinct levels
  near the infield than that. The row counts are usable; the *number of decks*
  implied by the schema is not reliable for these.
- **Deck heights above field level** — not published for any park, by anyone.
  This is the same gap `SOURCED_DATA.md` records for section geometry: Clem gives
  row *counts* and a graphical
  [Stadium profiles](http://www.andrewclem.com/Baseball/Stadium_profiles.html)
  page showing grandstand silhouettes, but no elevations in feet. The profiles
  page is images only; it says slope estimates *"may"* be added in future.

---

## Part 4 — Per-park source URLs (Clem)

All on `http://www.andrewclem.com/Baseball/`, plain HTTP only. `Last-Modified`
read from the server on 2026-08-09.

| Park | Page | Last modified |
|---|---|---|
| Yankee Stadium | `YankeeStadium_II.html` | 2026-07-16 |
| Fenway Park | `FenwayPark.html` | 2026-07-17 |
| Dodger Stadium | `DodgerStadium.html` | 2026-07-31 |
| Wrigley Field | `WrigleyField.html` | 2026-07-21 |
| Coors Field | `CoorsField.html` | 2026-07-28 |
| Chase Field | `ChaseField.html` | 2026-07-31 |
| Truist Park | `TruistPark.html` | 2026-08-04 |
| Camden Yards | `CamdenYards.html` | 2026-07-15 |
| Citizens Bank Park | `CitizensBankPark.html` | 2026-07-15 |
| Great American Ball Park | `GreatAmericanBallpark.html` | 2026-07-20 |
| Progressive Field | `ProgressiveField.html` | 2026-07-19 |
| Comerica Park | `ComericaPark.html` | 2026-07-03 |
| Daikin Park | `MinuteMaidPark.html` | 2026-08-04 |
| Kauffman Stadium | `KauffmanStadium.html` | 2026-08-06 |
| Angel Stadium | `AngelStadium.html` | 2026-08-06 |
| Citi Field | `CitiField.html` | 2026-07-16 |
| Sutter Health Park | `SutterHealthPark.html` | 2026-08-01 |
| PNC Park | `PNCPark.html` | 2026-07-17 |
| Petco Park | `PETCOPark.html` | 2026-07-31 |
| Oracle Park | `ATTPark.html` | **2019-12-19** |
| T-Mobile Park | `SafecoField.html` | **2023-07-13** |
| Busch Stadium | `BuschStadium_III.html` | 2026-08-04 |
| Tropicana Field | `TropicanaField.html` | **2019-07-09** |
| Globe Life Field | `GlobeLifeField.html` | 2026-08-04 |
| Rogers Centre | `RogersCentre.html` | 2026-07-24 |
| Target Field | `TargetField.html` | 2026-07-11 |
| Rate Field | `RateField.html` | 2026-07-20 |
| loanDepot park | `MarlinsPark.html` | **2023-05-24** |
| American Family Field | `MillerPark.html` | 2026-07-15 |
| Nationals Park | `NationalsPark.html` | 2026-07-15 |
| *(master table)* | `Stadium_statistics.html` | 2026-04-19 |

Bolded dates are older than the master table; for those four parks the table wins.

Seamheads park IDs, for
`https://www.seamheads.com/ballparks/ballpark.php?parkID=<ID>`:
`NYC21` Yankee · `BOS07` Fenway · `LOS03` Dodger · `CHI11` Wrigley · `DEN02`
Coors · `PHO01` Chase · `ATL03` Truist · `BAL12` Camden · `PHI13` Citizens Bank ·
`CIN09` Great American · `CLE08` Progressive · `DET05` Comerica · `HOU03` Daikin ·
`KAN06` Kauffman · `ANA01` Angel · `NYC20` Citi · `SAC01` Sutter Health ·
`PIT08` PNC · `SAN02` Petco · `SFO03` Oracle · `SEA03` T-Mobile · `STL10` Busch ·
`STP01` Tropicana · `ARL03` Globe Life · `TOR02` Rogers · `MIN04` Target ·
`CHI12` Rate · `MIA02` loanDepot · `MIL06` American Family · `WAS11` Nationals.
Las Vegas Ballpark is not in the database.

---

## Consolidated gap list

**Foul territory**

1. **Sutter Health Park** — Clem and Seamheads both leave the cell blank.
   Qualitative descriptions only ("very constricted").
2. **Las Vegas Ballpark** — no figure anywhere; the park is in neither registry.
3. **Foul territory split by side (1B vs 3B)** — not published for any park.
   Wrigley is the sole park with even a qualitative statement of asymmetry.
   Every published figure is a single whole-park total, so the model cannot get
   a per-side value from any source.
4. **Foul territory behind the plate vs. down the lines** — not published for any
   park. Same reason.

**Backstop distance**

5. **Las Vegas Ballpark** — no source.
6. **Twelve parks where sources conflict** (see §2): Fenway, Dodger, Coors,
   Great American, Progressive, Comerica, Angel, Oracle, T-Mobile, Rogers,
   Target, loanDepot. Of these, T-Mobile (55/56/69), Angel (56/59/60/60.5) and
   Fenway (52/54/60) are the widest.
7. **Definitional ambiguity — narrowed, not closed.** Club figures still define
   nothing. But Clem and Seamheads each *do* state a reference point, and they
   state different ones, which is enough to settle the direction the model
   needs and to bound the magnitude it cannot recover.

   | Source | Reference point |
   |---|---|
   | Clem | *"the distance from home plate to the fence in the rear"* |
   | Seamheads | *"Distance from Home Plate to Stands"* |

   The model adopts Clem at 30 parks, so `backstop_distance` is **the fence**,
   and the front row of seats must sit behind it. When the backstop anchor
   first went in it pinned the front row *onto* that figure, which silently
   asserted the opposite — that Clem measures to the seating bowl. That is now
   fixed: the anchor targets `backstop_ft + 1.0 ft`, and `_SEAT_SETBACK_FT` in
   `stadium.py` carries the argument.

   **Why 1 ft, and why it is a floor rather than an estimate.** Seamheads minus
   Clem is a direct measurement of fence-to-stands at the 30 parks where both
   publish. It does not behave like a real offset:

   | | |
   |---|---:|
   | Parks where both publish | 30 |
   | Parks agreeing to the foot (no gap at all) | **21** |
   | Mean difference | **+0.40 ft** |
   | Median difference | 0 ft |
   | Disagreements, positive / negative | 6 / 3 |

   The nine disagreements run both ways — Comerica Park and loanDepot park are
   −3, i.e. Seamheads puts the *stands* nearer than Clem puts the *fence*,
   which no definitional offset can produce. So these are source conflicts
   (§2.1), not a reference-point step, and the true fence-to-stands gap is
   below the resolution both sources publish at. One foot is the smallest
   increment either could have expressed, and it rounds the observed +0.40 ft
   mean up rather than down, erring toward the direction the physical
   constraint requires.

   **What is still open.** The real setback at a given park is unpublished and
   is certainly not uniform: a park with a photographers' well behind the plate
   has metres of it, and a park with dugout-club seats against the wall has
   almost none. Nothing here distinguishes them. The 1 ft is small enough to be
   nearly inert — under a tenth of a foul per game per park — which is the
   honest scale of what the sources support, and it should be read as fixing
   the *sign* of the error, not its size.
8. **Backstop height and net geometry** — not published anywhere for any park,
   and not covered by `SOURCED_DATA.md` either. Relevant, since Rate Field's
   roofless backstop demonstrates that two parks with equal backstop distance can
   behave completely differently.

**Deck configuration**

9. **Las Vegas Ballpark** — no row counts or overhang.
10. **Overhang for Truist Park, Globe Life Field, Sutter Health Park, Las Vegas
    Ballpark** — post-dates or falls outside the 2016 archived table.
11. **Overhang currency** — the 27 parks that do have figures have 2016 figures.
    Renovations since then (Rogers Centre's 2023–24 100-level rebuild, Camden's
    2022 left field, Wrigley's post-2016 seat additions) are not reflected.
11a. **What is casting the overhang** — not stated for any park. Clem gives one
    percentage per deck and never names the structure, so the deck / canopy /
    stadium-roof classification the model applies (see "Status: applied") is
    inferred from his decks column and from what each park physically is. It
    decides whether a published figure is used at all, which makes it the
    highest-leverage unsourced call in the layer. Chase Field (75%, classified
    stadium roof) and Target Field (75%, classified deck) are the pair that
    shows the classification, not the number, is doing the work; T-Mobile Park
    (55%, a retractable-roof park classified canopy because its roof covers
    nothing when open) is the call most likely to be wrong.
12. **Deck elevations in feet** — not published for any park by any source. Row
    counts are a proxy at best; converting them to heights requires a riser
    dimension nobody publishes.
13. **Dodger Stadium deck rows** — Clem's two-era row cannot be split reliably
    from extracted text, and Dodger Stadium has more infield decks than his
    three-column schema holds.

**Out of scope but noticed**

14. `stadium.py` gives Las Vegas Ballpark `lf=328, rf=328`;
    [Wikipedia](https://en.wikipedia.org/wiki/Las_Vegas_Ballpark) says 340 and
    340, with LCF/RCF 380 and CF 415.
15. `stadium.py` gives Las Vegas Ballpark `altitude_ft=2030`; the Athletics'
    own [ballpark page](https://www.mlb.com/athletics/news/featured/visit-las-vegas-ballpark-home-of-the-las-vegas-aviators)
    puts it at 3,000 ft (it sits in Summerlin, above the valley floor).
16. Kauffman Stadium's power alleys changed for 2026, from 387 ft to 379 ft
    ([MLB.com](https://www.mlb.com/news/royals-moving-outfield-walls-at-kauffman-stadium)).
    `stadium.py` carries `cf_distance=410`, which is unaffected, but the alleys
    are not modelled.
