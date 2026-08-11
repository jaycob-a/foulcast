# NOTES — Step 10: protective netting, and two opposite readings of it

Date: 2026-08-10. Branch `step-10`. Follows `NOTES_STEP8.md` and the Step 9
sections of `NOTES.md`. This delivers what `NEXT_STEPS.md` calls "Step 9 — Add
netting boundaries"; the commit numbering ran ahead of the plan document at
Step 8. Its three permanent presentation rules are followed and are worth
restating, because they shaped the code rather than just the copy: never the
word "safe", netting leads and the model's ranking follows it, and the
uncertainty is stated wherever the estimate is.

Step 9 sourced *where the bowls sit*. This one adds the only other externally
published fact about a seat that changes what a foul ball means when it gets
there: whether there is a net in front of it.

The data is `SOURCED_DATA.md` Part 2, collected 2026-08-09 by reading each
club's own netting or seating-map page in a browser. Nothing was re-researched
for this step and nothing was estimated. The work here is transcription
(`foulball/netting.py`), a join onto the model's zone tables, and making the
same status produce opposite conclusions in the two places it matters.

---

## 1. What was added

`foulball/netting.py` — one `ParkNetting` entry per registry key, all 31.
Each carries the extent in the source's own words, the netted section ranges
where the source gives numbers, the published height where there is one, the
source URL, whether it is primary or secondary, the retrieval date and the
vintage year.

`Stadium` gains three fields, set by the same factory hook Step 9 uses:

```
park_key      registry key
netting       the ParkNetting entry
zone_netting  {zone_id: ZoneNetting}, one per section, always populated
```

`Stadium.is_netted(zone_id)` is the single question the rest of the model
asks. It is True only for a zone the sources place *entirely* behind the net.

Nothing about the geometry moved. `zone_map_fingerprint` — the hash stamped on
every logged observation — deliberately does not cover netting, so Step 8's
log keeps its history and no existing row is re-read through the new data.

## 2. Where the data lands

| | parks | zones |
|---|---:|---:|
| Mapped — extent joined onto the zone table | **11** | 121 |
| Source gap — `SOURCED_DATA.md` has nothing usable | **8** | 106 |
| Join gap — good club page, irreconcilable labels | **12** | 117 |

Of the 344 zones fleet-wide: **41 netted, 10 partially netted, 70 not netted,
223 unknown.** Every one of the 41 is at field level, which is the right
answer for a screen that hangs in front of the first row.

The 11 mapped parks and what came out of them:

| park | netted zones | partially netted |
|---|---|---|
| `camden_yards` | all 5 field zones | — |
| `progressive_field` | all 5 | — |
| `oracle_park` | all 5 | — |
| `guaranteed_rate` | all 5 | — |
| `fenway_park` | 4 | 3B-DUG (FB71-79 of FB71-82) |
| `truist_park` | 4 | 3B-DUG |
| `citizens_bank` | 4 | — |
| `dodger_stadium` | 3 | 1B-DUG, 3B-DUG |
| `coors_field` | 3 | 1B-DUG, 3B-DUG |
| `great_american` | 2 | 1B-DUG, 3B-FB1 |
| `minute_maid` | 1 | 1B-FB1, 3B-FB1 |

Rate Field nets its entire field level, which is correct: the White Sox were
the first club in the league to run netting foul pole to foul pole, in July
2019.

## 3. The four statuses, and why there are four

Sources support a binary at the level of a *printed section*: listed as netted,
or not listed. Exactly one club in the league publishes anything finer — the
Twins mark Target Field section 126 "Partially covered" — and that flag is
carried on its entry as `partial_labels`.

The model's zones each span a range of printed sections, so the join produces
one more state than the source has:

- **`netted`** — every printed section in the zone is inside the extent.
- **`partially_netted`** — some are. This is arithmetic on the source, not a
  claim the source made, and it is the *zone table's* coarseness showing
  through, not a description of the net.
- **`not_netted`** — none are, at a zone behind the front of the bowl, where
  a club's enumeration of netted sections not mentioning it means what it says.
- **`unknown`** — the sources do not reach this zone. Never folded into either
  of the two answers below.

## 4. Same output, opposite conclusions

`matchup_engine` writes the status into every `SectionPrediction` and then
reads it twice:

**Souvenir ranking.** A foul landing in a `netted` zone is `is_catchable =
False`, and the zone is removed from `top_sections` entirely rather than left
in it with a zero. A zero would read as "no fouls land here", which is the
opposite of true. `predict.py`, `webapp_v2.py` and the ranking chart all
filter the same way, including the best-value-per-dollar list.

**Safety.** The same zones are in `netted_sections`, sorted by expected fouls,
with the published netting height attached. Their `expected_fouls`,
`avg_exit_velocity` and `danger_rating` are untouched — the balls still arrive.

Fenway, one half-game, is the whole idea in one park:

```
souvenir ranking          safety view
1  3B Loge      6.00      Behind Plate Field Box  6.96 fouls  danger 5.0  screened
2  Behind Plate Loge 5.63 1B Field Box            1.96        danger 7.5  screened
3  1B Loge      4.66      3B Infield Field Box    1.22        danger 7.2  screened
4  3B Field Box 3.81 *    1B Infield Field Box    0.87        danger 7.3  screened
   * partly netted — upper bound
```

The section that led every Fenway ranking before this step — Behind Plate
Field Box, at 6.96 fouls a game — is now the top line of the safety panel and
appears nowhere in the ranking. Same simulation, same landing points, two
answers.

`partially_netted` zones stay in the ranking, flagged as an upper bound.
Splitting their fouls between the netted and open halves would need a
seat-level distribution nobody publishes; dropping them whole would be as
unsourced as ignoring the net.

## 5. The join is guarded, and the guards found something

A published extent is only applied when it survives four checks. None of
them tests whether the model's labels are *right*; they test whether the club
page and the labels can both be true at once, and whether the answer depends
on parts of the table that cannot be checked at all.

- **G1 — nothing matched.** Every published label falls outside every zone.
- **G2 — the plate is left open.** A behind-plate zone at the front of the
  bowl is not fully netted. Every extent in the file is described as running
  from behind home plate outward, and the league has required netting behind
  the plate at all 30 clubs since 2020.
- **G3 — coverage rises away from the plate.** Netting starts behind the plate
  and stops somewhere down the line. It cannot skip the near zone and resume
  at the far one.
- **G4 — the zone table cannot describe a bowl, and the answer depends on it.**
  Added after the first pass; §5a explains why and what it caught.

Twelve parks fail. In every case the club page is fine and the model's printed
labels are not. Nine are caught by the extent:

| park | what the club says | what the zone table says | verdict |
|---|---|---|---|
| `yankee_stadium` | nets 011-029 | numbers the same deck 109-131 | G1 |
| `chase_field` | nets 111-133 | behind plate is 101-104 | G2 |
| `tmobile_park` | 27 ft of net at 126-134 | behind plate is 108-111 | G2 |
| `rogers_centre` | to 113C and 130C | behind plate is 108-111 | G2 |
| `american_family` | nets 108-128 | behind plate is 103-106 | G2 |
| `nationals_park` | PNC Diamond Club is 119-126 | PNC Diamond Club is 104-107 | G2 |
| `target_field` | nets 103-126 (+1-17) | behind plate is 101-103 | G2 |
| `petco_park` | nets 101-106, 109-116 | behind plate is 106-109 | G2 |
| `busch_stadium` | nets 132-165 | 127-133 and 157-167 both marked 3B | G3 |

That table is the most useful thing this step produced. It is a list of parks
whose zone tables are wrong about their own printed section numbers, found by
external data rather than by inspection. Nationals Park is the sharpest: the
club and the model disagree about where the same *named product* is.
`seat_map.py` already warned that a printed label is only as good as the name
it was parsed from; this is the first evidence of how often it is not good
enough.

## 5a. Three more, found by pulling on the asymmetry flag

The first pass mapped 14 parks and flagged six of them as "markedly
asymmetric" — Truist, Citizens Bank, Great American, Angel, PNC and Globe
Life, every one of them with the 1B field zones fully netted and the 3B side
only partly. Always that way round. A heuristic that fires six times in the
same direction is describing something, and it was not netting.

The check that settled it reads only the zone table and asks whether its
printed labels could describe a continuous seating bowl. A real lower bowl is
numbered round the ring, so one foul line carries numbers below the plate's
and the other carries numbers above. Fleet-wide the tables come in three
shapes:

| shape | what it means | parks |
|---|---|---|
| **ring** — sides on opposite sides of the plate's numbers | describes a real bowl | 12, incl. Fenway, Camden, Coors, Truist, Citizens Bank, Great American |
| **straddle** — one side has numbers both below *and* above the plate's | the numbering wraps at an unpublished point | 7: Angel, PNC, Comerica, Kauffman, Petco, Busch, Tropicana |
| **plate-at-end** — both sides above the plate's numbers | numbered outward from the plate, not round the bowl | 12, incl. Dodger, Globe Life, Rate Field |

The corroboration is that this test, which never looks at a netting extent,
independently condemns almost every park the extent-based guards had already
rejected: five of the seven straddle parks were gaps already, and six of the
plate-at-end parks were rejected by G2. So the three shapes are not an
artefact of how I drew them.

Applying it to the six flagged parks:

- **Angel Stadium** and **PNC Park** straddle. Angel's 3B zones are 103-109
  and 133-141 with the plate at 110-113; PNC's are 101-107 and 130-139 with
  the plate at 108-111. In both, one 3B zone sits on the far side of the
  plate's numbers from the other, so the numbering wraps somewhere no source
  gives. Reading "103-133" or "101 → 130" as an arc then nets the *far* end of
  the 3B line while leaving the near end open, which cannot be a real
  installation. **Now gaps** (`labels_wrap_unpublished`).
- **Globe Life Field** is plate-at-end: the plate zone is 1-5, the 1B zones
  run 6-19, the 3B zones run 25-37, and 20-24 belongs to nothing. Which block
  is which side is not established anywhere, and the published extent (1-26)
  covers only part of the series, so the answer depends entirely on that
  unestablished split. **Now a gap** (`sides_unverifiable`).
- **Truist**, **Citizens Bank** and **Great American** are ring-shaped and
  clean: no straddle, both sides adjacent to the plate zone, numbering
  monotone outward. Their asymmetry is the published extent's, and they stay
  mapped.

Two parks share Globe Life's unverifiable shape and keep their mapping for
reasons recorded on their entries:

- **Rate Field** — the extent (108-156) covers *every* field-level label in
  the park, so which side each block is on cannot change any answer. That is
  not luck; the White Sox net pole to pole, and a pole-to-pole net is exactly
  the case where the sides stop mattering.
- **Dodger Stadium** — the club itself states the split, "section 40 (1B) and
  section 41 (3B)", and the zone table splits the same series the same way
  (FD12-FD24 on 1B, FD11-FD25 on 3B). Two sources agreeing on the parity is
  the corroboration Globe Life has none of. It is recorded as
  `series_corroborated` and it is the only one in the file.

What remains on the three still-mapped parks is a smaller, honest doubt. The
published extent at each is off-centre relative to the plate zone — Truist
reaches 18 sections one way and 8 the other, Citizens Bank 18 and 7, Great
American 5 and 16 — where the other ring-numbered parks sit near even (Coors
15/15, Minute Maid 5/6, Progressive 20/22, Camden 32/27, Fenway 22/30). That
is either a genuinely lopsided net or a zone table whose plate is a few
sections off the real one. Nothing in the sources separates the two, so it is
a flag carrying both numbers, not a gap.

Comerica Park is a tenth failure of a different kind and is recorded as a
source gap, not a join gap: the club gives two arc endpoints (116 and 142) on
a numbering that wraps behind the plate, and the wrap point is unpublished.
Reading it as 116-142 would net the far end of the 3B line and leave the plate
open. Reading it the other way needs a number no source gives.

## 6. The gaps, kept as gaps

Eight parks where `SOURCED_DATA.md` itself has nothing to apply:

| park | why |
|---|---|
| `wrigley_field` | club describes the extent in words, publishes no numbers |
| `kauffman_stadium` | club states outright it will not publish section locations |
| `citi_field` | no netting text on the club's own pages |
| `loan_depot` | netting published only as an image |
| `tropicana_field` | the club's own page contradicts itself |
| `comerica_park` | arc endpoints on a wrapping numbering |
| `oakland_coliseum` (Sutter Health Park) | no park-specific source of any kind |
| `las_vegas_ballpark` | no park-specific source of any kind |

Three of them have a weaker figure available — Kauffman 107-148 and loanDepot
8-21 from the 2020 RateYourSeats table, Citi Field 107-128 undated from the
same site. All three are recorded on the entry as `secondary`, and none is
applied. The Angel Stadium row is why: its current club page says 103-133
where 2019 sources said 110-126, so a six-year-old unverified range is not a
current state, it is a former one.

Sutter Health Park and Las Vegas Ballpark have only the PDL rule — netting
foul pole to foul pole by 2025 Opening Day — which is a requirement placed on
the club, not an observation of the installation. It says a net exists. It
does not say which sections it covers, so no sections are written down.

Tropicana Field is the one place a *choice* would have closed a gap. Its page
says both "from home plate to the foul poles ... Sections 101-138" and "from
Section 125 to behind home plate to Section 126". Those cannot both describe
one installation. Picking the broader one would exclude most of the park's
lower bowl from every souvenir ranking on the strength of a sentence the same
page contradicts, so neither is applied and both are recorded.

At all 17 gap parks the behaviour is identical and deliberate: every zone is
`unknown`, nothing is excluded from any ranking, nothing is highlighted as
protected, and the ranking prints why. A park with no netting data does not
look like a park with no netting.

## 7. Six places wording became numbers

Everything else in the file is transcription. These six are the whole
editorial surface, and `netting.interpretations()` lists them so a seventh
cannot be added quietly:

| park | source wording | decision |
|---|---|---|
| `yankee_stadium` | "Section 011 → Section 029" | inclusive run between the endpoints; zero padding dropped for numeric comparison |
| `fenway_park` | "Field Box 79 → Field Box 9" | inclusive run; the source names the Field Box product, which is the model's FB prefix |
| `dodger_stadium` | "behind home plate → section 40 (1B) and 41 (3B)" | the club's bare numbers are the model's FD series, and the arc starts at the lowest FD number |
| `camden_yards` | "Section 6 → Section 70" | inclusive run |
| `pnc_park` | "Section 101 → Section 130" | inclusive run |
| `rogers_centre` | "to Sections 113C and 130C" | inclusive run; printed block suffix C dropped |

The Dodger one is the only one that supplies a prefix the source does not
carry, and it is corroborated rather than assumed: the club says 40 is on the
1B side and 41 on the 3B, and the model's FD series splits the same way —
FD12-FD24 on 1B, FD11-FD25 on 3B. Even parities agreeing across two
independent sources is not a coincidence, so they are the same numbering.

## 8. What did not move

Golden baselines were relocked, and what did *not* change is the point:
`total`, `mean_dist`, `mean_angle`, `n_1b`, `n_3b` and `no_section` are
byte-identical at all five games. No ball landed anywhere different. Only what
a landing means changed.

Three of the five games moved, two did not:

- Both Fenway games drop from 10 ranked sections to 7 and gain a four-section
  safety list.
- The Dodger game drops from 10 to 9. `HOME-DC` keeps the top rank — the
  Dugout Club is a DG-series product the netting page never names, so it is
  `unknown`, and an unknown zone is flagged rather than excluded.
- Neither Yankee game moves at all, because Yankee Stadium is a join gap. The
  identical baselines are the proof that a gap behaves like a gap.

The park sweep and the game backtest are untouched: neither reads
`is_catchable`. `calibrate_log.py`'s comparison is untouched for the same
reason — a netted zone receives exactly the fouls it always did, so observed
vs expected is unaffected.

## 9. What the log can now test

`calibrate_log.py` gains a fifth section. The observation log is the only
evidence in this repo that can test the netting join from outside it, because
`landing_type='netting'` has been a logged field since Step 8:

- a net strike logged in a section the club publishes as unnetted, or a catch
  logged in a section published as netted, contradicts either the club page or
  the park's printed labels;
- a net strike logged at one of the 17 gap parks is evidence a net exists
  there, and is reported as exactly that — it does not close the gap, because
  one observer seeing a net does not establish which sections it covers.

Nothing is scored yet; the log has no rows at a mapped park.

## 10. What is still open

1. **Twelve parks need their zone tables corrected** — nine against their own
   club netting pages (§5), three because the tables cannot describe a bowl
   (§5a). Until then those parks exclude nothing, and their printed-section
   labels should not be trusted for the foul log either. Seven more parks have
   the same structural defects but are already gaps for source reasons, so the
   real count of suspect tables is nineteen.
2. **Three mapped parks are off-centre and still mapped** — Truist (18/8),
   Citizens Bank (18/7), Great American (5/16), against a ring-numbered fleet
   that sits near even. Their labels pass every structural check, so this is
   the extent's asymmetry unless their plate zone is a few sections off. These
   are the mapped results most likely to be wrong, and the cheapest way to
   settle them is to read the same club seating maps again for where home
   plate is.
3. **Fully-behind vs partially-covered per printed section** is unsourced
   league-wide bar one section. Closing it needs the per-section photo review
   `SOURCED_DATA.md` describes and did not do.
4. **Netting heights exist for 7 parks.** They are the closest thing to a real
   geometric constraint in this dataset and nothing uses them yet: the model
   has no net surface, only a per-zone status. A ball that would clear a
   13.5 ft net and one that would not are treated identically.
5. **Tropicana Field's page needs re-reading** with the club, particularly
   after the 2026 reopening.
6. **Sutter Health Park and Las Vegas Ballpark** have no netting source at
   all, which is now the third thing those two parks are missing after foul
   area and (at Las Vegas) backstop distance.
