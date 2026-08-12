# Seating-map read vs. `stadium.py` zone tables

Five published seating maps in `seating_maps/` were read directly and compared
against the `_make_*_sections()` tables in `foulball/stadium.py`. **No code was
changed.** This file records what the maps say, what the model says, and where
they disagree.

Method: each image was cropped and upsampled (2x–8x) around the plate, both foul
lines, and the deck edges, and read at that magnification. Every claim below is
from a label I could actually resolve; anything I could not resolve is marked as
such rather than inferred.

Source files, as delivered:

| Park | File | Pixels | Type | Legibility |
|---|---|---|---|---|
| Truist Park | `truist_park.png` | 2568x1445 | flat plan | excellent |
| Sutter Health Park | `sutter_health.jpg` | 2208x2208 | flat plan | excellent |
| Chase Field | `chase_field.jpg` | 1536x864 | flat plan | good |
| Oriole Park | `oriole_park.jfif` | 2568x1445 | **3D isometric** | poor–fair |
| Fenway Park | `fenway_park.jpg` | 800x830 | flat plan, rotated | poor |

> Note: `oriole_park.jfif` is not read as an image by extension. It is a plain
> JPEG and had to be re-encoded before it could be opened.

---

## Summary of mismatches

> **Update (2026-08-11):** the Oriole Park finding below is now enforced in
> code. `seat_map.SIDE_ANCHORS` + `check_side_anchors()` is a fifth guard on
> the netting join, and Camden has moved from `mapped` to
> `join_gap / sides_flipped`. See "The flip check" at the end of this file for
> what it covers and, more importantly, what it does not.

| Park | Plate zone | Section ordering | Severity |
|---|---|---|---|
| Chase Field | **Wrong** — model's `HOME-F` is in the right-field corner | **1B side inverted**; 3B side roughly right | Severe |
| Sutter Health Park | **Wrong** — model's `HOME-F` is on the 1B line | Both lines run the same way from a plate at the low end; **14 of 24 field sections do not exist** | Severe |
| Oriole Park | Half-zone off | **1B and 3B swapped** on all three decks | Severe |
| Truist Park | **Wrong** — model's `HOME-F` is 4–6 sections up the 3B line | Direction correct on both sides | Moderate |
| Fenway Park | Shifted ~4–6 sections toward 1B on all three rings | Direction correct on both sides | Mild |

Two independent corroborations worth noting:

- The model **already flags Chase Field**. `join_park()` returns
  `status='join_gap'`, `gap_kind='labels_contradict_model'`, with the reason
  "HOME-F is the behind-plate zone … and the published extent leaves it
  not_netted". The map explains exactly why: `HOME-F` is labelled `101-104`,
  and 101–104 are the bleachers beside the swimming pool in right-centre.
- The model **did not flag Oriole Park** — `join_park()` returned
  `status='mapped'`. It could not: the table is mirror-symmetric, so a
  left/right swap passed every structural check while still being wrong. Camden
  is the case that showed the join's checks were necessary but not sufficient,
  and it is what the fifth guard was written for. It now returns
  `join_gap / sides_flipped`.

---

## 1. Truist Park — `truist_park.png`

Flat plan, home plate at bottom-centre, standard orientation (1B right, 3B
left). The cleanest map of the five; everything below is high confidence.

### Behind home plate

Three concentric products sit behind the plate, innermost first:

- **Truist Club** (red), bare numbers, `5` dead centre: `9 8 7 6 5 4 3 2 1`
  running 3B→1B.
- **Chairman Seats** (blue), bare numbers: `30 29 28 27 26 25 24 23 22`
  running 3B→1B.
- **100 level** (gold), the ring the model actually names: centre falls between
  **125 and 126**. Behind-plate block ≈ **122–128**.

Further out, still behind the plate: Executive Seats (1–10), Champions Suites
(1–8), Delta Sky360 Club, then Xfinity Club 220–231.

### Lower bowl outward from the plate

- **1B line, descending:** `125 124 123 122 120 118 116 114 113 112 111 110 109
  108 107` → RF corner (then Chop House 156–160 in the outfield).
- **3B line, ascending:** `126 127 128 130 131 133 135 137 138 140 141 142 143`
  → then Home Run Porch Low `144 145 146 147 148 149 150 151` → LF.
- **Field-level bare-number ring:** 1B `21 20 19 … 11 10` descending to the RF
  corner; 3B `31 32 33 … 41 42` ascending to the LF corner.

**Numbers that do not appear anywhere on this map:** `115, 117, 119, 121` on the
1B side and `129, 132, 134, 136, 139` on the 3B side. Verified at 4x on the
Diamond Infield band, where 122 → 120 → 118 → 116 → 114 → 113 are consecutive
wedges with no intervening label and no room for one. Sections `101-106` are
also not shown (the ring starts at 107); they may exist off-map rather than not
exist.

### Netting

The map carries an explicit legend: a hatched swatch labelled **"Netting Located
at Front of Section"**. The hatch is drawn over each section's own fill colour
and is unambiguous at 3x.

Hatched:
- the whole bare-number field ring, **10 through 42**;
- the 100 level, **107 through 143** (i.e. 107–114, 116, 118, 120, 122–128,
  130, 131, 133, 135, 137, 138, 140–143).

Not hatched, and adjacent to the ends of the run: `156-160` (Chop House, RF
side, immediately beyond 107) and `144-151` (Home Run Porch Low, LF side,
immediately beyond 143). No hatch anywhere on the 200 or 300 levels.

**This is wider than what `netting.py` records.** That entry cites the Braves
A-Z guide for "Sections 10-42 and 111-141". The bare-number run matches exactly;
the 100-level run does not — the map hatches 107–110 at the 1B end and 142–143
at the 3B end, which the A-Z text excludes. Source-vs-source discrepancy, not a
model error.

### Deck levels

Per the legend graphic bottom-right: **100 Lower Level**, **200 Lexus Level**,
**300 Vista Level**, **400 Grandstand Level**. Observed ranges: 100s 107–160;
200s 210–259; 300s 311–350; 400s 410–444.

### vs. `stadium.py` (`_make_truist_park_sections`, line 1854)

| Zone | Model label | What the map puts there |
|---|---|---|
| `HOME-F` | Sec 129-133 | **129 does not exist**; 130/131/133 are Diamond Infield **3B**, several sections up the third-base line |
| `1B-FB1` | Sec 122-128 | correct side; this is actually the **behind-plate** block plus the first 1B sections |
| `1B-DUG` | Sec 115-121 | **none of 115/117/119/121 exist**; only 116, 118, 120 do |
| `3B-FB1` | Sec 134-140 | 134/136/139 do not exist; 135/137/138/140 are 3B mid-line |
| `3B-DUG` | Sec 141-147 | 141–143 are the 3B corner (netted); 144–147 are Home Run Porch (not netted) |

**Mismatch: the plate zone is offset about +4 sections toward 3B.** The true
behind-plate block is ≈122–128; the model calls that `1B-FB1` and puts `HOME-F`
at 129–133.

**Section ordering is correct.** Numbers increase toward the plate on 1B and
increase away from the plate on 3B, which is what the map shows. The model's
`3B-DUG` coming out `partially_netted` is also the right shape — the map does
show the net ending part-way through that block — though the map ends it at 143
where the model's data ends it at 141.

Upper decks: `HOME-U` Sec 332-340 and `HOME-B` Sec 227-235 were not checked
against the map in detail; the 200/300 labels behind the plate are 210-series
and 326-327 respectively on the overview, so these are likely offset too.

---

## 2. Chase Field — `chase_field.jpg`

Flat plan. Orientation established from two landmarks, not from the dugout
labels: **"D-BACKS POOL"** and **"HOME RUN PORCH R"** are both on the right of
the frame, and the Chase Field pool is in right-centre. So **right = right field
= 1B side**, left = 3B. (The map's "VISITOR DUGOUT" is therefore on the 1B side
and "HOME DUGOUT" on 3B.)

### Behind home plate

- **Innermost ring is lettered, not numbered:** `J` dead centre behind the
  plate, `I H G F E D C B A` running toward 1B, `K L M N O P Q R S` running
  toward 3B. These are the Clubhouse Box / Homeplate Box / Dugout Box products
  in the legend.
- **100 level:** **122** dead centre. Behind-plate block ≈ **119–126**.

### Lower bowl outward from the plate

- **1B line, descending:** `122 121 120 119 118 117 116 115 114 113 112 111 110
  109 108 107 106 105 104 103 102 101` → RF corner / pool.
- **3B line, ascending:** `123 124 125 … 143 144 145` → LF corner.

So 101 is the RF foul-pole end and 145 the LF foul-pole end, with the plate in
the middle at 122/123.

### Netting

**None shown.** The legend is a 16-entry price/product key (Clubhouse Box,
Homeplate Box, Dugout Box, 1st/3rd Base Box, … Outfield Reserve) with no netting
entry, and there is no hatching, screen line, or annotation anywhere on the
drawing. Nothing on this map can confirm or contradict `netting.py`'s
"Sections 111-133".

### Deck levels

- **100s** field level: 101–145, plus standing areas `100W` and `145W`.
- **Lettered** A–S: premium infield boxes in front of the 100s behind the plate.
- **200s** club: 200–209 (1B side), **210A–210I** behind the plate (210A at the
  1B end, 210I at the 3B end), 211–224 (3B side), plus `224W`. **Maximum is
  224** — there is no 225.
- **300s** upper: 300–332, plus `300W` / `332W`. Behind the plate is **316**
  (315/314/313 toward 1B, 317/318/319 toward 3B). **Maximum is 332** — there is
  no 333–336.

### vs. `stadium.py` (`_make_chase_field_sections`, line 2317)

| Zone | Model label | What the map puts there |
|---|---|---|
| `HOME-F` | Sec 101-104 | **the right-field corner bleachers**, beside the pool — about as far from the plate as a foul-territory section gets |
| `1B-FB1` | Sec 105-111 | the outer right-field line (Bullpen Reserve / Baseline Reserve) |
| `1B-DUG` | Sec 112-118 | the 1B **infield** — i.e. *nearer* the plate than `1B-FB1` |
| `3B-FB1` | Sec 125-131 | 3B infield/mid — roughly right |
| `3B-DUG` | Sec 132-138 | outer 3B line — roughly right |
| `HOME-B` | Sec 200-207 | the 1B-side club level; the plate is at 210A–210I |
| `1B-LB1` | Sec 208-216 | spans from the 1B side **across the plate** onto the 3B side |
| `3B-LB1` | Sec 217-225 | 3B side, but **225 does not exist** |
| `HOME-U` | Sec 306-315 | the 1B-side upper deck; the plate is at 316 |
| `1B-UB` | Sec 316-326 | the plate **and** the 3B upper deck |
| `3B-UB` | Sec 327-336 | 327–332 exist; **333–336 do not** |

**Mismatch (plate zone): severe.** Every deck's behind-plate zone is placed on
the 1B/RF side, and at field level it lands in the outfield corner.

**Mismatch (ordering): the 1B side is inverted.** The model has `1B-DUG`
(112-118, the far/dugout zone) numbered *above* `1B-FB1` (105-111, the near
zone); the map has 112–118 closer to the plate than 105–111. The 3B side's
direction is correct.

The table reads as a template that assumed the numbering starts at 101 behind
the plate and runs outward both ways, leaving 119–124 unassigned. Chase's real
numbering is a single arc with the plate at its midpoint.

---

## 3. Oriole Park at Camden Yards — `oriole_park.jfif`

**3D isometric render viewed from beyond the outfield, looking back at home
plate.** This is the hardest map of the five: labels are small, foreshortened,
and radially displaced by the projection.

Orientation is nevertheless certain, from two independent landmarks: the **B&O
Warehouse** (beyond right field) runs down the **left** of the frame, and the
**"RF PORCH"** label is on the **left**. So **left = right field = 1B side**,
right = 3B. The "ORIOLES" dugout on the left is consistent (Baltimore's dugout
is on the 1B side).

### Behind home plate

Lower bowl centre is **36 / 38**. Behind-plate block ≈ **30–46** (even).

Directly above/behind them are the lettered club boxes **C31 C33 C35 C37 C39
C41 C43**, which occupy the club level behind the plate in place of numbered
sections.

### Lower bowl outward from the plate

- **1B/RF line, descending:** `34 32 30 28 26 24 22 20 18 16 14 12 10 8 6` →
  RF corner.
- **3B/LF line, ascending:** `40 42 44 46 48 50 52 54 56 58 60 62 64 66 68 70
  72` → LF corner.
- A second tier sits **behind** the first, carrying the **odd** numbers:
  `3 5 7 9 11 13 15 17 19 23 27 29` on the 1B side and
  `45 47 49 53 55 59 61 65 67 69 71 73 75` on the 3B side.

The even-front / odd-behind reading is **moderate confidence only** — see
"Where I am least confident" below.

### Netting

**None shown.** No legend, no hatch, no screen line. `netting.py`'s
"Section 6 → Section 70" cannot be checked against this image, though it is at
least *coherent* with the map's numbering: 6 is the RF corner and 70 the LF
corner, so the run passes through the plate at 36/38 as an arc should.

### Deck levels

- **Lower bowl:** bare numbers, ~1–98 (98 appears in right field on the
  overview), plus lettered club boxes C31–C43 behind the plate.
- **Club level (200s):** 204 … 230 on the 1B side, then C31–C43 behind the
  plate, then 242 … 270 on the 3B side. **232–240 do not appear** — the club
  boxes replace them.
- **Upper (300s):** 306 … 388. Behind the plate is **336 / 338**. Two tiers
  again (a front box row and a reserve row behind).

### vs. `stadium.py` (`_make_camden_yards_sections`, line 2421)

| Zone | Model label | What the map puts there |
|---|---|---|
| `HOME-F` | Sec 38-43 | 38 *is* at the plate, but 39–43 run up the **3B** line — the zone is about half a block off toward 3B |
| `1B-FB1` | Sec 44-55 | **3B** infield |
| `1B-DUG` | Sec 56-68 | **3B** line |
| `3B-FB1` | Sec 26-37 | **1B** infield |
| `3B-DUG` | Sec 14-25 | **1B** line |
| `HOME-B` | Sec 242-251 | **3B**-side club level; the plate is C31–C43 |
| `1B-LB1` | Sec 252-264 | **3B** side |
| `3B-LB1` | Sec 228-241 | **1B** side |
| `HOME-U` | Sec 348-361 | **3B**-side upper; the plate is 336/338 |
| `1B-UB` | Sec 362-376 | **3B** side |
| `3B-UB` | Sec 332-347 | straddles the plate |

**Mismatch: 1B and 3B are swapped on all three decks.** The model treats the
numbering as increasing toward first base; the map has it increasing toward
third. The plate zone itself is only slightly off (38-43 vs a true ~30-46), so
this is a mirror error, not a translation error.

This is the park to watch, because it is currently `status='mapped'` in the
netting join — the swap is invisible to every check in `netting.py` since the
zone table is mirror-symmetric.

---

## 4. Fenway Park — `fenway_park.jpg`

Flat plan, **rotated**: home plate is at the left edge, centre field to the
right, the Green Monster along the top. So **top = left field = 3B side**,
bottom = right field = 1B side. Confirmed independently by the "Red Sox" dugout
label (bottom / 1B, correct for Boston) and "Visitor" (top / 3B), and by the
"Third Base SRO" / "First Base SRO" banners.

800px wide with 6–8px label text. This is the least legible map of the five;
several claims below are explicitly hedged.

### Behind home plate

The behind-plate direction was computed as the bisector of the two foul lines
extended backward from the plate marker, then read off along that ray. Dead
centre behind the plate:

| Ring | Centre section | Behind-plate block |
|---|---|---|
| Field Box (innermost) | **46** | ≈ 42–50 |
| Loge Box | **133** | ≈ 129–137 |
| Grandstand (outermost) | **22** | ≈ 20–24 |

The **"Home Plate SRO"** banner sits radially outside grandstand 19–22,
consistent with this.

### Rings outward from the plate

All three rings **ascend toward 3B/left field and descend toward 1B/right
field**:

- **Field Box** — 1B: `39 38 37 32 31 26 25 20 19 14` …; 3B: `49 50 53 54 59 60
  64 65 70 71 77 78 82`.
- **Loge Box** — 1B: `129 128 125 124 119 118 113 112 107 106` …; 3B: `136 137
  141 142 146 147 150 151 155 156 159 160`.
- **Grandstand** — 1B: `20 19 18 17 16 15 14 13` …; 3B: `23 24 25 26 27 28 29`.

The Field Box labels are **not consecutive as printed** — I read 14, 19, 20, 25,
26, 31, 32, 37, 38, 39 on the 1B side with narrow unlabelled wedges between
them. Those wedges are almost certainly the missing numbers, dropped because
there is no room for a label at this resolution. I did not treat the gaps as
missing sections (contrast Truist, where the gaps are real and verifiable).

### Netting

**None shown.** The legend is a 12-entry price key (Lower Bleachers, Infield
Grandstand, Right Field Box, Dugout Box, Loge Box, Right Field Roof Box, EMC
Club, Outfield Grandstand, Upper Bleachers, Field Box, Pavilion Box, "No tickets
available in this section"). No netting entry and no hatching.

`netting.py`'s "Field Box 79 → Field Box 9" is at least **coherent with the
map's ordering**: FB9 is far down the 1B line and FB79 far up the 3B line, so
the run is a proper arc through the plate. It also confirms the model's
`3B-DUG` (FB71-FB82) is the correct zone to come out `partially_netted`, since
the extent stops at 79 and the map shows Field Boxes continuing to at least 82
on that side.

### Deck levels

- **Field Box** (innermost, green): ~9–89.
- **Loge Box**: ~101–166.
- **Grandstand**: 1–33.
- Plus, not modelled at all: Dugout Box, EMC Club, Pavilion Box (Third Base
  Pavilion / First Base Pavilion), Right Field Box, Right Field Roof Box, Lower
  and Upper Bleachers (34–43), EMC Suites L1-L23 / R1-R21, and the K1-K4 and
  B1-B4 blocks.

### vs. `stadium.py` (`_make_fenway_park_sections`, line 1116)

| Zone | Model label | Map centre | Offset |
|---|---|---|---|
| `HOME-F` | Sec FB31-FB49 (centre ≈ 40) | 46 | ~6 sections toward 1B; 31–41 are the 1B line |
| `HOME-B` | Sec LB125-LB136 (centre ≈ 130) | 133 | ~3 sections toward 1B |
| `HOME-U` | Sec G12-G21 (centre ≈ 16) | 22 | ~6 sections toward 1B |

Also: `3B-LB1` stops at LB155 where the map shows Loge continuing to 160+, and
`3B-UB` stops at G28 where the grandstand runs to 33.

**Mismatch: the plate anchor is shifted toward 1B by ~4–6 sections in all three
rings.** `G22-G28` in particular is labelled 3B when 22 is dead behind the
plate.

**Section ordering is correct** — all three rings ascend toward 3B in both the
model and the map. Fenway is the best-matching of the five.

---

## 5. Sutter Health Park — `sutter_health.jpg`

Flat plan, plate at the bottom, standard orientation. Very clean drawing.
Orientation confirmed from the base markers (third base left, first base right)
— **not** from the dugout labels, which put "ATHLETICS" on 3B and "VISITOR" on
1B.

### Behind home plate

**112**, dead centre. Behind-plate block ≈ **110–114**.

### Lower bowl outward from the plate

- **1B line, descending:** `112 111 110 109 108 107 106 105 104 103 102 101` →
  RF corner.
- **3B line, ascending:** `113 114 115 116 117 118 119 120 121 122 123` → LF
  corner.

**The lower bowl ends at 123.** There is no 124 and nothing above it.

### Netting

**None shown.** No legend and no hatching. The solid black arc immediately
behind the plate is the backstop wall, and the white diagonal-hatched block
beside 101/102 is an unavailable/non-seating area (it abuts the concourse, not
the field). This matches `netting.py`, which records Sutter Health as
`gap_kind='no_source_at_all'`.

### Deck levels

- **100 level:** 101–123, a single continuous bowl.
- **200 level:** **201–206 only** — six sections, all on the **1B/right-field
  side**, sitting behind 100-level sections 102–106 next to the Sky River
  Casino and Solon Club. There is **no 200-level seating behind the plate and
  none on the 3B side.**
- Luxury Suites run behind the bowl on both lines; Gilt Edge Club at the 3B end.

### vs. `stadium.py` (`_make_sutter_health_sections`, line 3044)

| Zone | Model label | What the map puts there |
|---|---|---|
| `HOME-F` | Sec 103-105 | the **1B line**, roughly between first base and the RF corner |
| `1B-FB1` | Sec 106-111 | 1B line — roughly right |
| `1B-DUG` | Sec 112-118 | 112 is **dead behind the plate**; 113–118 are the **3B** line |
| `3B-FB1` | Sec 125-130 | **does not exist** (bowl ends at 123) |
| `3B-DUG` | Sec 131-137 | **does not exist** |
| `HOME-U` | Sec 200-205 | 200 does not exist; 201–205 are on the **1B side**, not behind the plate |
| `1B-UB` | Sec 206-212 | 206 exists; **207–212 do not** |
| `3B-UB` | Sec 213-220 | **does not exist** |

**Mismatch (plate zone): severe.** The plate is 112, not 103–105.

**Mismatch (ordering): severe.** The model numbers both foul lines *upward* from
a plate at the low end of the series (103-105 → 112-118 → 125-137). The map is a
single arc with the plate at its midpoint. This is exactly the shape
`netting.py`'s G4 check calls structurally impossible ("both lines run the same
way from a plate at the end of the series"), and the reason it was never caught
is that Sutter Health is a `no_source_at_all` source gap, so the join returns
before the structural checks run.

**14 of the 24 named field-level sections and 13 of the 21 named upper-level
sections do not exist.** The real bowl has 23 lower sections and 6 upper; the
model's table names sections up to 137 and 220.

Also worth recording, though not a map finding: `sutter_health_park()` calls
`_apply_sourced_params(stadium, 'oakland_coliseum')`, so `Stadium.park_key` for
this park is `'oakland_coliseum'`. The netting entry under that key does
describe Sutter Health, so this appears intentional, but it makes the park key
misleading.

---

## Where I am least confident

Ordered most to least worrying.

1. **Oriole Park's two-tier even/odd structure.** I am confident the lower bowl
   centres on 36/38 and ascends toward 3B — that rests on the warehouse and
   "RF PORCH" landmarks plus a clean read of 34-36-38-40-42 across the plate.
   I am *not* confident that the odd numbers form a separate tier behind the
   even ones. In an isometric projection, labels for narrow sections get pushed
   radially outward to stay readable, which produces exactly this appearance.
   At 8x, sections 60/62/64 (green, field-adjacent) and 61/65 (blue, behind)
   really do look like different rings — but 66 and 68 also sit in the "behind"
   band, which the rule does not explain. **Do not act on the even/odd split
   without a flat 2D Camden chart.** The 1B/3B swap finding does not depend on
   it.

2. **Fenway's Field Box numbering.** At 800px the Field Box wedges are 5–8px
   wide and only about half carry a legible label. I read 14/19/20/25/26/31/32/
   37/38/39 on the 1B side and 42/45/46/49/50/53/54/59/60/64/65/70/71/77/78/82
   on the 3B side. The unlabelled wedges between them are probably the missing
   integers, but I cannot prove it from this image, so my "plate at FB46" is
   really "plate at the wedge labelled 46, ±1 wedge". The Loge and Grandstand
   reads are firmer.

3. **Fenway's behind-plate direction.** Because the map is rotated, I derived
   the perpendicular from the plate as the bisector of the two foul lines
   measured off the drawing, then read the sections along it. That is a
   construction, not a label. It agrees with the "Home Plate SRO" banner's
   position, which is why I trust it, but a 5° error in my bisector moves the
   answer by about one grandstand section.

4. **Truist's netting extent at the ends of the run.** The hatch on 107–110
   (bright red Dugout Corner 1B) and 142–143 (brown Diamond Corner 3B) is
   visible and the neighbouring sections are plainly solid, so I believe the
   extent is 107–143. But this contradicts the club's own A-Z text (111–141)
   that `netting.py` cites. One of the two club sources is stale and I cannot
   tell which from the image alone. The bare-number run 10–42 matches both.

5. **Chase Field's left/right orientation.** I resolved it from the pool and
   "HOME RUN PORCH R" being on the same side, which is decisive. But note the
   map's dugout labels put "VISITOR DUGOUT" on the 1B side, which is the
   opposite of the convention most parks use, so anyone re-checking this will
   hit the same moment of doubt I did. The landmarks, not the dugouts, are the
   evidence.

6. **Sections I called non-existent.** For Truist (115/117/119/121, 129, 132,
   134, 136, 139) and Sutter Health (124+) I checked at 4x and there is no room
   for an unlabelled wedge. For Chase (225, 333–336) I read the maxima at
   overview resolution only and did not zoom the far corners of the 200/300
   rings. Chase's 225/333–336 are therefore lower confidence than the others.

7. **What I did not check.** Truist's 200- and 300-level behind-plate zones
   (`HOME-B` Sec 227-235, `HOME-U` Sec 332-340) were not compared section by
   section against the map — the overview suggests they are offset like the
   field level, but I did not confirm it. Fenway's non-modelled products
   (Pavilion, EMC Club, Bleachers, Roof Boxes) are listed above but not measured.

---

## The flip check (added 2026-08-11)

The Oriole Park finding above was invisible to every guard the netting join
had. This section records the check added for it and what it found.

### Why the existing guards could not see it

Every geometry number in `stadium.py` is mirror-symmetric — the module's own
provenance block says so: `1B-FB1` and `3B-FB1` carry identical distances,
angles and heights at all 31 parks. So swapping a park's two sides changes
nothing any of G1–G4 measures:

| Guard | What it measures | Under a 1B/3B swap |
|---|---|---|
| G1 | how many published labels match any zone | unchanged |
| G2 | whether the behind-plate zone is netted | the plate is on neither side |
| G3 | coverage descending outward on each side | angles are mirror-equal, so the same profile appears on the other side and still descends |
| G4 | each side's labels below/above the plate's | a swap maps 'below' to 'above' on the other side; neither straddle nor plate-at-end changes |

Camden was `mapped`, with a citation, with its sides swapped.

### What the check uses

Only one kind of evidence can detect a mirror: **a source that names a side
next to a section number.** Three families exist in this repo, and nothing
else does. They are transcribed into `seat_map.SIDE_ANCHORS`:

1. **Club netting pages that name a side.** Dodgers "section 40 (1B) and
   section 41 (3B)"; Tigers "Section 116 (1B line) and Section 142 (3B line)";
   Blue Jays "the first and third baseline walls to Sections 113C and 130C
   respectively"; Yankees "Section 011 (1B/RF side) → Section 029 (3B/LF)".
2. **Club pages that name a side-bearing product.** Busch's "Lower RF Box
   132-134" places those sections in right field, and right field is the 1B
   side; its "1B Field Box"/"3B Field Box" rows say it outright.
3. **The five seating maps in `seating_maps/`,** read at magnification with the
   landmark that fixed each map's orientation recorded on the anchor.

**A published netting extent is not such a source, however asymmetric it is.**
"Section 6 → Section 70" tells you the run is longer on one side of the plate
than the other; it does not tell you which foul line either end is on. That is
why coverage is thin rather than universal, and no amount of extent asymmetry
closes the gap.

**Dugout locations are the same story.** Which side a club's dugout sits on
does differ by park and would anchor the sides — but only once some source ties
that dugout to section numbers. Exactly one park in this repo has that: Fenway,
from a compilation `SOURCED_DATA.md` explicitly could not confirm. It is
carried at `secondary_unverified` strength, which can raise a flag but never
reject a join. (It agrees with the map read, for what that is worth: two
unrelated sources putting the low Field Box numbers on the first-base side.)

### Results across all 31 parks

Eleven parks are testable. Twenty have no side-naming source at all.

| Verdict | Parks |
|---|---|
| **flipped** | **`camden_yards`** |
| **inconsistent** | `busch_stadium`, `oakland_coliseum` (Sutter Health) |
| ok | `chase_field`, `comerica_park`, `dodger_stadium`, `fenway_park`, `rogers_centre`, `truist_park` |
| untestable, anchors exist but unusable | `petco_park`, `yankee_stadium` |
| untestable, no anchor | the other 20 |

- **`camden_yards` — flipped.** All 30 anchored sections land on the opposite
  side from the map, none on the named side. Now
  `join_gap / sides_flipped`; mapped parks drop from 11 to 10.
- **`busch_stadium` — inconsistent, not mirrored.** 138-140 and 161-165 agree
  with the club; "Lower RF Box 132-134" does not — the model has 132-133 on the
  3B side. A swap would not fix this. Busch was already a gap via G3, which
  found the same thing from the extent and names it more precisely, so G3 keeps
  precedence and G5 runs after it.
- **`oakland_coliseum` (Sutter Health) — inconsistent, not mirrored.** 106-110
  agree; 114-118 do not, because the model's `1B Field (Sec 112-118)` straddles
  the plate onto the third-base line. Already a source gap for netting, but the
  anchor check runs independently of the netting join, so this park is still
  testable. This also **resolves the conflict `SOURCED_DATA.md` records** for
  Sutter Health in MLB.com's favour: the plate is at 112, inside MLB.com's
  108-116, not at A View From My Seat's 103-104.
- **`petco_park` — untestable by design.** The club's page names 111-115 as
  "1B side" and 112-116 as "3B side". A section is on one foul line or the
  other, so the wording is not describing sides in a way that can be tested.
  The check declines rather than picking an endpoint.
- **`yankee_stadium` — untestable.** The anchors are sections 011 and 029; the
  zone table numbers that deck 109-131, so no anchored label is claimed by any
  zone. Already a G1 gap for exactly this reason.

### Which of the still-mapped parks might be flipped

Ten parks remain `mapped`. Three have had their sides confirmed:
`fenway_park`, `dodger_stadium`, `truist_park`.

**Seven have never been tested and could be mirrored:**

| Park | Published extent | Why it cannot be tested |
|---|---|---|
| `coors_field` | Sections 112-147 | bare numeric arc, no side named |
| `citizens_bank` | Field Level 109-138 | bare numeric arc |
| `great_american` | Sections 1-5, 22-25, 111-135 | three bare runs, no side named |
| `progressive_field` | Sections 128-174 | bare numeric arc |
| `minute_maid` (Daikin) | Sections 112-126 | bare numeric arc |
| `oracle_park` | Sections 101-135 | bare numeric arc |
| `guaranteed_rate` (Rate Field) | 108-156, pole to pole | bare numeric arc |

These now carry a `sides untested` flag on the join rather than silence,
because "passed every check" and "passed every check that exists" are
different claims and only the second is true of them.

Three are worth suspecting more than the others, on the weak evidence that
their `_join_flags` coverage asymmetry always runs the same way round — 1B
fully netted, 3B partly:

- `citizens_bank` (100% 1B vs 50% 3B)
- `great_american` (94% vs 36%)
- `truist_park` (100% vs 57%) — but Truist's sides are *confirmed*, so its
  asymmetry is the extent's, which is evidence that the pattern is not
  diagnostic of a flip on its own.

The cheapest way to close the remaining seven is a seating map each, read the
way the five in `seating_maps/` were. Nothing else available reaches them.

### What a passing anchor check does not mean

It means the table is **not mirrored**. It does not mean the table is right.
Chase Field passes — and its `HOME-F` is still in the right-field corner.
Truist passes — and its plate zone is still four sections up the third-base
line. Every one of the five parks in this file disagrees with its zone table;
only one of them disagrees by a mirror.
