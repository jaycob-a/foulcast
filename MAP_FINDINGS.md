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


---

# Step 12 — the six "sides untested" parks

The seven parks left `mapped` with a `sides untested` flag at the end of Step
11 all publish a bare numeric netting arc with no side named, so a mirror flip
would pass every existing check. Six of the seven have a seating map in
`seating_maps/`; Daikin Park does not, and stays untested. The six were read
the same way as the five above — cropped and upsampled (2x–4x) around the
plate, both foul lines and the deck edges — and compared against
`_make_*_sections()` in `foulball/stadium.py`. **No geometry was changed.**
The only code change is six new entries in `seat_map.SIDE_ANCHORS` and the
test expectations that follow from them.

Every claim below is from a label I could resolve at magnification. Where the
map is too small to call a detail, that is said rather than guessed.

Source files, as delivered:

| Park | File | Pixels | Type | Legibility |
|---|---|---|---|---|
| Coors Field | `coors_field.jpg` | 2208x2208 | flat plan | excellent |
| Rate Field | `rate_field.gif` | 1536x1344 | flat plan | excellent |
| Progressive Field | `progressive_field.png` | 1536x864 | flat plan | good |
| Great American Ball Park | `great_american.png` | 1024x576 | flat plan | fair |
| Citizens Bank Park | `citizensbank_park.jpg` | 640x800 | flat plan | poor–fair |
| Oracle Park | `oracle_park.jpg` | 640x828 | flat plan | poor–fair |

All six are flat plans; none is isometric. On a flat plan viewed from above
with the plate at the bottom of the frame, first base is on the viewer's
right, so the drawn diamond is itself a landmark. At five of the six the map
also names a left-field or right-field feature that agrees with the diamond.
Rate Field is the exception and is called out below.

## Summary

| Park | Verdict | Sides | Plate zone, field level (map vs model `HOME-F`) |
|---|---|---|---|
| Coors Field | **Sides flipped** | reversed on all three decks | about right: map 128–132, model 127–132 |
| Progressive Field | **Sides flipped** | reversed on all three decks | about right: map 150–155, model 148–152 |
| Oracle Park | **Sides flipped, and plate zone offset** | reversed on all three decks | ≈6 sections toward 1B: map 113–118, model 107–109 |
| Citizens Bank Park | Plate zone offset | correct | ≈5 sections toward 3B: map 122–125, model 127–131 |
| Great American Ball Park | Plate zone offset | correct | ≈6 sections toward 3B: map 122–126, model 116–119 |
| Rate Field | Plate zone offset, badly | correct | ≈18 sections toward 1B: map 130–134, model 112–115 |

Three of the six were mirrored. That is the answer to the question this step
asked, and it is worse than the Step 11 write-up guessed: the three it
suspected on netting-coverage asymmetry (Citizens Bank, Great American, Truist)
all turned out to have their sides right, and the three that were actually
flipped were not on that list. Coverage asymmetry is not diagnostic of a flip,
which the Truist case had already hinted.

Six of six disagree with their zone table in some way. With the five above,
that is eleven maps read and eleven disagreements.

## Netting drawn on the maps

| Park | On the map | Published extent (`SOURCED_DATA.md`) |
|---|---|---|
| Rate Field | red line along the field edge, legend "Netting located in front of sections 108-156" | 108–156 — **matches exactly** |
| Oracle Park | no hatch; printed note "Protective netting extends from SECTIONS 101-135" | 101–135 — **matches exactly** |
| Citizens Bank Park | hatch, legend "NETTING LOCATED AT FRONT OF SECTION": Diamond Club A–G and **110 through 136** | Diamond Club A–G; 109–138 — the map's hatch reads one section short at the 1B end and two at the 3B end, at a resolution where a hatch on a 25px wedge is at the limit of what I can resolve; I would not call 109, 137 or 138 either way |
| Coors Field | none drawn, no legend entry | 112–147 |
| Great American Ball Park | none drawn, no legend entry | 1–5, 22–25, 111–135 |
| Progressive Field | none drawn, no legend entry | 128–174 |

---

## 6. Coors Field — `coors_field.jpg`

Flat plan, plate at lower-left, field extending to the upper right, compass
rose on the outfield. The largest and cleanest map of the six.

**Orientation.** Fixed by the map's own legend: the **"Right Field Box"**
colour is on 105–110 and **"Right Field Mezzanine"** on 201–209, both at the
low-numbered end of the bowl. Two corroborations, both printed on the map: the
foul-pole distances — **347'** at the corner beside 150/151 and **350'** beside
109/110, and Coors' left-field line is the shorter of the two — and the
**"Rockies Dugout"** label along 120–126 with **"Visitors Dugout"** along
136–139. So low numbers = right field = 1B; high numbers = left field = 3B.

### Behind home plate

The **Toyota Clubhouse** (a club, black on the map) sits directly behind the
plate. The 100 ring behind it: **129 130 131** dead centre, with 128 and 127
on the 1B shoulder and 132, 133 on the 3B shoulder. Behind-plate block ≈
**128–132**. At the 200 level the PNC Press Club / Legacy Club / Press Box
occupy the space behind the plate: the club level runs 214–227 on the 1B side
and 234–247 on the 3B side, and **228–233 are not printed anywhere**.

### Lower bowl outward from the plate

- **1B line, descending:** `127 126 125 124 123 122 121 120` (Infield Box)
  `119 118 117 116` (Outfield Box) `115 114 113 112 111` (Corner Outfield Box)
  `110 109 108 107 106 105` (Right Field Box) → RF corner at 350'.
- **3B line, ascending:** `133 134 135` (Infield Box) `136 137 138 139 140
  141` (Midfield Box) `142 143 144 145 146 147 148 149 150` (Outfield / Corner
  Outfield Box) → LF corner at 347'. Pavilion 151–160 runs across the outfield
  beyond.
- **200 level:** `214 … 227` along the 1B side; `234 … 247` up the 3B side.
- **300 level:** `301 … 309` Lower Rooftop Reserved in right field, `310–313`
  by Gate B, `314 … 321` along the 1B side, `323 325 326 327 328 … 347` up
  the 3B side to Gate E. A suite band numbered 1–45 sits between the 200 and
  300 levels, 1 at the RF end and 45 at the LF end.

### Deck levels

100s 105–160; 200s 201–209 (RF Mezzanine) and 214–247 (Club); 300s 301–347;
400s 401–403 (the Rockpile). Suites 1–45.

### vs. `stadium.py` (`_make_coors_field_sections`)

| Zone | Model label | What the map puts there |
|---|---|---|
| `HOME-F` | Sec 127-132 | about right; 127 is the first 1B shoulder section |
| `1B-FB1` | Sec 133-140 | **3B** — Infield/Midfield Box up the left-field line |
| `1B-DUG` | Sec 141-150 | **3B** — the left-field corner |
| `3B-FB1` | Sec 118-126 | **1B** — the Rockies-dugout run |
| `3B-DUG` | Sec 110-117 | **1B** — the right-field corner |
| `HOME-B` | Sec 225-236 | 225–227 are 1B club, 234–236 are 3B club, 228–233 do not exist |
| `1B-LB1` | Sec 237-247 | **3B** |
| `3B-LB1` | Sec 214-224 | **1B** |
| `HOME-U` | Sec 321-332 | straddles the plate: 321–327 bottom / 1B shoulder, 328–332 up the 3B side |
| `1B-UB` | Sec 333-347 | **3B** |
| `3B-UB` | Sec 301-320 | 301–309 are the right-field rooftop reserved, 314–320 the 1B upper deck — all **1B** side |

**Mismatch: the 1B and 3B label ranges are swapped on all three decks.** The
plate zone is in the right place. The zone-table comment in `stadium.py` even
says "1B Baseline (Sec 141-150) — down RF foul line"; the map puts 141–150 in
the left-field corner.

**Anchors added:** 1B 110–127, 3B 133–150. Check: **flipped**, 35 disagree, 0
agree, 127 unmatched (the model's `HOME-F` claims it). Join is now
`join_gap / sides_flipped`.

---

## 7. Citizens Bank Park — `citizensbank_park.jpg`

Flat plan, plate at bottom-centre. 640px wide; the section labels are 8–10px
tall and needed 3x–4x to read. Everything on the lower bowl resolved; the
netting hatch is at the limit.

**Orientation.** The map labels its own gates: **"FIRST BASE GATE"** on the
right of the frame, **"THIRD BASE GATE"** on the left, "LEFT FIELD GATE" top
left. The **"Phillies"** dugout is drawn on the right and **"VISITORS"** on the
left, which agrees. Right = 1B = low numbers.

### Behind home plate

The **Diamond Club is lettered, not numbered**: `A B C D E F G` running
3B→1B, `D` dead centre. Behind it the 100 ring reads `125 124 | 123 122`,
with the centre falling between 123 and 124. Shoulders: `121 120 119` beside
`G` on the 1B side, `126 127 128` beside `A` on the 3B side. Behind-plate
block ≈ **122–125**; the wider arc 119–128.

Further out: 200s `224 223 222 221 220` (222 centre); 300s `322 321 320 319`
(centre between 320 and 321); 400s `421 420 419`.

### Lower bowl outward from the plate

- **1B line, descending:** `121 120 119` (shoulder) `118 117 116 115` (Infield
  Box, red) `114 113 112` (purple) `111 110 109 108` (orange) `107 106 105 104
  103 102 101` (tan) → RF corner beside the out-of-town scoreboard.
- **3B line, ascending:** `126 127 128` (shoulder) `129 130 131 132` (red)
  `133 134 135` (purple) `136 137 138 139` (orange) `140 141 142 143 144 145`
  (tan) `146 147 148` → LF corner beside the Phanavision board.
- **200 level:** `201–205` (red, RF corner), `206–212` right, `215–219` 1B,
  `220–224` behind, `225–229` 3B, `230–237`, `241–245` (red, LF corner).
- **300 level:** `301–318` right, `319–322` behind, `323–333` left.
- **400 level:** `401–418` right, `419–421` behind, `422–434` left.

### Netting

Legend swatch **"NETTING LOCATED AT FRONT OF SECTION"**, a cross-hatch over
the section's own fill. Hatched: the Diamond Club `A–G`; `110 111` (orange),
`112 113 114` (purple), `115 116 117 118 119 120 121` (red), `123 124`, `126
127 128 129 130 131 132` (red), `133 134 135` (purple), `136` (orange). `109`
and `137` read plain. `122` and `125` are a lighter fill and I cannot tell
hatched from not. So the map shows **110–136** against a published 109–138.
At this resolution I would not argue the endpoints either way.

### Deck levels

100s 101–148 plus Diamond Club A–G; 200s 201–245; 300s 301–333; 400s
401–434. The map does not name its levels.

### vs. `stadium.py` (`_make_citizens_bank_sections`)

| Zone | Model label | What the map puts there |
|---|---|---|
| `HOME-F` | Sec 127-131 | **3B shoulder and line** — the plate block is 122–125 |
| `1B-FB1` | Sec 120-126 | **straddles the plate**: 120–121 are the 1B shoulder, 122–125 the plate block, 126 the 3B shoulder |
| `1B-DUG` | Sec 115-119 | 1B, correct side; these are the infield, not the dugout end |
| `3B-FB1` | Sec 132-138 | 3B, correct |
| `3B-DUG` | Sec 139-145 | 3B, correct |
| `HOME-B` | Sec 223-229 | 223–224 plate, 225–229 3B: ≈3 toward 3B |
| `1B-LB1` | Sec 215-222 | 1B, correct; 222 is dead centre |
| `3B-LB1` | Sec 230-237 | 3B, correct |
| `HOME-U` | Sec 323-329 | **3B** — the 300 plate block is 319–322 |
| `1B-UB` | Sec 315-322 | 1B, correct, running up to the plate |
| `3B-UB` | Sec 330-336 | 3B, correct |

**Mismatch: the plate zone is offset about +5 sections toward 3B at field
level,** and by 3–5 on the two upper decks. **Section ordering is correct on
both sides on all three decks.**

**Anchors added:** 1B 101–118, 3B 129–148. The shoulders 119–121 and 126–128
are deliberately left out, as at Truist: the check is for a mirror, and the
model's `1B-FB1` straddle is a boundary error the anchors are not meant to
adjudicate. Check: **ok**, 18 agree, 0 disagree. The map's numbers 101–114
and 146–148 fall outside every zone the model names (unmatched), as do 129–131
which only `HOME-F` claims.

---

## 8. Great American Ball Park — `great_american.png`

Flat plan, plate at lower-left, field extending to the upper right. 1024px
wide with a large legend taking a third of the frame; the bowl is about 600px
across and needed 3x–4x.

**Orientation.** The legend's **"Sun Deck/Moon Deck"** colour is on 140–144,
at the far end of the high-numbered line, and the Sun/Moon Deck is Great
American's right-field deck. The drawn diamond agrees: its first-base corner
is the lower-right one. So high numbers = right field = 1B; low numbers = 3B.
The bleachers `401–406` sit at the top of the frame beyond 101–105, in
left-centre.

### Behind home plate

Three premium wedges sit dead behind the plate, innermost first: **Diamond
Seats `1 2 3 4 5`** (pink; `3` on the plate's axis), **Scout Box `22 23 24
25`** (blue), then the 100 ring's **Scout `122 123 124 125 126`** (yellow;
`124` on the axis). Shoulders: `119 120 121` (red, 3B) and `127 128 129` (red,
1B). Behind-plate block on the 100 ring ≈ **122–126**. These match the
published netting's "1–5, 22–25" — those are the two premium wedges behind
the plate, not sections down a line.

The 200 level is a row of small club boxes; `221 222 223 224 225` are legible
to the 3B side of 122–126 and the rest are not. The 400 level behind the plate
is around `422–425` — the labels there are 6px and I would not pin it closer.

### Lower bowl outward from the plate

- **3B line, ascending:** `119 118 117 116 115 114 113` (Infield Box, red,
  stacked along the third-base line) `112 111 110 109` (Field Box, purple)
  `108 107` (Terrace Line) `106 105 104 103 102 101` (Terrace Outfield, green)
  → LF corner.
- **1B line, descending:** `127 128 129 130 131 132 133` (Infield Box, red)
  `134 135 136 137` (Field Box, purple) `138 139` (Terrace Line) → then the
  Sun/Moon Deck `140 141 142 143 144` and `145 146` in right field.
- **400 level:** `407 … 419` down the 3B side, `420 … 437` along the bottom
  and up the 1B side; `401–406` bleachers.
- **500 level:** `509 … 519` 3B side, `520 … 537` 1B side.

### Netting

**None drawn.** The legend is a 20-entry product key with no netting entry.

### Deck levels

100s 101–146 plus premium 1–5 and 22–25; 200s a row of small club boxes,
only 221–225 legible; 300s 301–307 on the 1B side; 400s 401–437; 500s
509–537.

### vs. `stadium.py` (`_make_great_american_sections`)

| Zone | Model label | What the map puts there |
|---|---|---|
| `HOME-F` | Sec 116-119 | **3B line** — the Infield Box wedges stacked along third base, 3–7 sections up from the plate block |
| `1B-FB1` | Sec 120-127 | **straddles the plate**: 120–121 3B shoulder, 122–126 plate block, 127 1B shoulder |
| `1B-DUG` | Sec 128-136 | 1B, correct |
| `3B-FB1` | Sec 109-115 | 3B, correct |
| `3B-DUG` | Sec 101-108 | 3B, correct |
| `HOME-B` / `1B-LB1` / `3B-LB1` | Sec 205-228 | **unreadable** — the 200 level is a row of 6px boxes |
| `HOME-U` | Sec 412-419 | **3B** — the 400 plate block is ≈422–425 |
| `1B-UB` | Sec 420-430 | 1B, correct, running from the plate |
| `3B-UB` | Sec 401-411 | 401–406 are the left-field bleachers; 407–411 are 3B upper |

**Mismatch: the plate zone is offset about +6 sections toward 3B at field
level.** Same shape as Truist. **Section ordering is correct on both sides.**

**Anchors added:** 3B 101–118, 1B 127–139. Check: **ok**, 25 agree, 0
disagree; 116–118 and 137–139 unmatched.

---

## 9. Progressive Field — `progressive_field.png`

Flat plan, plate at lower-left of the diamond, field extending up and to the
right. 1536px wide, of which the bowl is about 900px; readable at 2x–3x.

**Orientation.** The map labels **"LEFT FIELD DISTRICT"** on the left of the
frame and **"RIGHT FIELD DISTRICT"** and **"RIGHT FIELD GATE"** on the right,
with a NORTH arrow. The **"HOME DUGOUT"** is drawn along 158–165 and the
**"AWAY DUGOUT"** along 138–142, which agrees (Cleveland's dugout is on the
third-base side). So left = 3B = high numbers; right = 1B = low numbers.

### Behind home plate

The **Lexus Carnegie Club `1 2 3 4`** sits dead behind the plate. The 100
ring behind it: `150 151 152 | 153 154 155`, with the plate's axis falling
around 152–153 — the ring is not centred on the plate and I would not pin it
closer than ±1. Behind-plate block ≈ **150–155**. Diamond Box front row
(black) fronts 148–158.

### Lower bowl outward from the plate

- **1B line, descending:** `149 148 146 144 142 140` (Field Box, dark
  blue/orange) `138 136` (Lower Box Front, orange) `134 131 130 129 128`
  (Lower Box, red) `125 117` (Lower Box Outfield, pink) → the corner drink
  rails and Field View Bullpen → `113 111 109 108 107 103` (Lower Reserved /
  Lower Box Outfield) in the RF corner.
- **3B line, ascending:** `153 154 155 156 157 158` (Field Box) `159 160 162
  163 164` (Field Box Back / Middle) `165 167 169 170 171 172 174` (Lower Box)
  `175 178 179` (Lower Box Outfield) → LF corner; bleachers `180–185` beyond.
- **Numbers that do not appear on the lower bowl:** `132 133 135 137 139 141
  143 145 147` and `114–116 118–124 126 127` on the 1B side; `161 166 168 173
  176 177` on the 3B side.

**The same numbers are printed twice.** Two suite columns on the 3B side, up
against the press box, carry `132 133 134 136 138 139 140 142 144 146 147 148`
(dark blue) and `150 151 152 153 154 155 156 157 158 159 160 161 162` (light
blue, "Third Baseline Infield Suites"), plus a parallel `230 … 257`. So a bare
printed **134–150 is on both foul lines** — first-base field box or
third-base suite — and cannot anchor a side. The anchors below stop at 131.

- **400 level:** `427 428 429 430 431 432 434 436 437 438 440 442 444 446 447`
  (First Baseline Infield Suites, lavender) up the 1B side; `448 450 451 452
  453 454 455 456 457 458 459` (View Box, yellow) along the press box on the
  3B side, `461–472` beyond. The plate at this level is at the press box,
  between 447 and 448.
- **500 level:** `519 520 523 525 528 529 533 537 541 546 548` up the 1B side,
  `550 551 552 553 554 555 556 557 558 559` up the 3B side; plate ≈ 548–550.
- **300 level:** `303 304 307 309 311 316` (Pennant District, RF), `324 … 348`
  (Club Lounge / Club Infield) on the 1B side. None printed on the 3B side.

### Netting

**None drawn**, and no legend entry.

### Deck levels

100s 103–185; suites 132–162 and 230–257 (3B side); 300s 303–348; 400s
427–472 plus the KeyBank North Coast Social `1–20` in left field; 500s
519–559.

### vs. `stadium.py` (`_make_progressive_field_sections`)

| Zone | Model label | What the map puts there |
|---|---|---|
| `HOME-F` | Sec 148-152 | about right — one or two sections toward 1B of the plate block |
| `1B-FB1` | Sec 153-161 | **3B** — Field Box up the left-field line |
| `1B-DUG` | Sec 162-172 | **3B** — the home-dugout run |
| `3B-FB1` | Sec 139-147 | **1B** field boxes along the away dugout (and 3B suites: ambiguous numbers) |
| `3B-DUG` | Sec 130-138 | **1B** — 130, 131, 134, 136, 138 are the first-base Lower Box |
| `HOME-B` | Sec 446-452 | straddles the press box: 446–447 1B suites, 448–452 3B view box |
| `1B-LB1` | Sec 453-461 | **3B** |
| `3B-LB1` | Sec 437-445 | **1B** |
| `HOME-U` | Sec 546-555 | about right |
| `1B-UB` | Sec 556-568 | **3B** |
| `3B-UB` | Sec 534-545 | **1B** |

**Mismatch: the 1B and 3B label ranges are swapped on all three decks.** The
plate zone is roughly right on each.

**Anchors added:** 1B 103–113 and 117–131 (the sections that carry a label,
short of the duplicated range), 3B 153–179. Check: **flipped**, 22 disagree, 0
agree. 31 unmatched: the RF corner and 117–129 fall outside every zone the
model names, and 173–179 are past the model's 172.

---

## 10. Oracle Park — `oracle_park.jpg`

Flat plan, plate at bottom-centre. 640px wide; the lower-bowl labels are
7–9px and needed 4x. The section numbers resolved; the odd/even structure
near the plate is the least certain part of the read.

**Orientation.** Fixed by the legend. **"Arcade"** and **"Coors Light Cove:
Silver Seats"** colours are on `145–152`, beyond the low-numbered end of the
bowl — the arcade is the right-field wall over McCovey Cove. **"Club Left
Field"** is on `232–234` and **"View Reserve Left Field"** on `332–336`,
beyond the high-numbered end; the bleachers `136–143` run across left-centre.
So low numbers = right field = 1B; high numbers = 3B.

### Behind home plate

A small dark block (the legend's Dugout Club / Batter's Box) sits directly
behind the plate. The Field Club ring behind it: **`115` dead centre**, `117`
and `113` flanking. The numbering interleaves two rows: the Field Club (front)
reads `… 119 | 117 115 113 | 112 110 109 …` and the Premium Lower Box row
behind it reads `118 117 116 115 114 113`, the same numbers again — a section
number spans both products. Behind-plate block ≈ **113–118**; shoulders 112
and 119.

The 200 level behind the plate is the Diamond Seats arc `208 … 224`, with
`215 216` centre; the 300 level `314 315 317`, centre ≈315.

### Lower bowl outward from the plate

- **1B line, descending:** `112 110 109 108 107` (Field Club, red) `106 105
  104` (Lower Box, purple) `103 102 101` (Lower Box Outfield, light blue) →
  RF corner; arcade 145–152 beyond.
- **3B line, ascending:** `119 121 122 123` (Field Club) `124 125 126 127 128`
  (Lower Box) `129 130 131 132 133 134 135` (Lower Box Outfield, green) → LF
  corner; bleachers 136–143 beyond.
- **200 level:** `202 203 204 205 207` (orange, RF) `208 209 210 211` (1B)
  `212–224` (behind and 3B) `225 226 227 … 234` (3B / LF). A suite ring
  numbered `37 … 61` sits behind it.
- **300 level:** `302 304 305 307 308` (RF) `310 311` `314 315 317` (behind)
  `319 320 321` `324 … 336` (3B / LF).

### Netting

No hatch. A printed note on the map: **"Protective netting extends from
SECTIONS 101-135"** — matches the published extent word for word.

### Deck levels

100s 101–152 (101–135 lower box, 136–143 bleachers, 145–152 arcade); 200s
201–234 plus suites 37–61; 300s 302–336.

### vs. `stadium.py` (`_make_oracle_park_sections`)

| Zone | Model label | What the map puts there |
|---|---|---|
| `HOME-F` | Sec 107-109 | **1B line**, 4–8 sections down toward McCovey Cove |
| `1B-FB1` | Sec 110-116 | 110–112 are 1B (correct); 113–116 are the plate block |
| `1B-DUG` | Sec 117-123 | 117–118 plate block; **119–123 are 3B** |
| `3B-FB1` | Sec 103-106 | **1B** |
| `3B-DUG` | Sec 101-102 | **1B** — the right-field corner |
| `HOME-B` | Sec 209-215 | the 1B half of the Diamond Seats arc |
| `1B-LB1` | Sec 216-226 | **3B** |
| `3B-LB1` | Sec 202-208 | **1B** |
| `HOME-U` | Sec 308-316 | the 1B side of the 300 plate block |
| `1B-UB` | Sec 317-327 | **3B** |
| `3B-UB` | Sec 302-307 | **1B** |

**Mismatch: the sides are swapped on all three decks, and the field-level
plate zone is also about 6 sections down the first-base line.** The zone-table
comment says "1B Club (Sec 117-123) — down RF line toward McCovey Cove"; the
map puts 119–123 on the third-base side and McCovey Cove beyond 101.

**Anchors added:** 1B 101–112, 3B 119–135. Check: **inconsistent**, not
flipped — 3 agree (110, 111, 112: the model's `1B-FB1` starts far enough down
the right-field line to overlap the true 1B side) and 11 disagree. That is the
honest verdict: a swap alone would leave 110–112 on the wrong side, so the
table is wrong in a way a mirror would not fix. G5 passes it on as
`join_gap / labels_contradict_model`.

---

## 11. Rate Field — `rate_field.gif`

Flat plan, plate at bottom-centre, the White Sox logo across the outfield.
1536px wide and the most legible map of the six; every lower-bowl label is
20px tall.

**Orientation.** This is the one map of the six that **names no left-field or
right-field landmark**. The orientation rests on the drawn diamond alone: the
plate is at the bottom of the frame, the mound above it, so first base is on
the viewer's right. The gates around the frame (Gate 4 behind the plate, Gate
5 beside the high numbers, Gate 3 beside the low) and the named concourse
areas (Miller Lite Landing at the 105–108 corner, Wintrust Kids Zone at the
155–158 corner) are printed but do not say which field they are in, and were
not relied on. Read with that caveat: right = 1B = low numbers.

### Behind home plate

The **"CIBC Scout Club"** is drawn behind `130–134`, and **`132` is dead
centre**, `131` and `133` flanking. Behind-plate block ≈ **130–134**. At the
300 (club) level the Rate Club box sits between `330` and `334`, so 331–333
do not exist; at the 500 level `531` and `533` flank a centre gap.

### Lower bowl outward from the plate

- **1B line, descending:** `131 130 129 128 127 126 125 124 123 122 121 120
  119 118 117 116 115 114 113 112 111 110 109 108` → RF corner; then the
  Miller Lite Landing and `105 104 103 102 101 100` across the outfield.
- **3B line, ascending:** `133 134 135 136 … 154 155 156` → LF corner; then
  `157 158 159 160 161 162 163 164` across the outfield. Fully continuous
  100–164, every number present.
- **300 level:** `311 312 314 316 318 320 322 324 326 328 329 330` 1B side;
  `334 335 336 338 340 342 344 346 348 350 352 354 356 357` 3B side.
- **500 level:** `506 … 531` 1B side; `533 … 558` 3B side.

### Netting

**Drawn**: a red line along the field edge from 108 round to 156, with the
legend **"Netting located in front of sections 108-156"**. Matches the
published extent exactly.

### Deck levels

100s 100–164; 300s 311–357; 500s 506–558. **There is no 200 or 400 level on
this map.**

### vs. `stadium.py` (`_make_rate_field_sections`)

| Zone | Model label | What the map puts there |
|---|---|---|
| `HOME-F` | Sec 112-115 | **1B line, 17–20 sections down toward the right-field corner** |
| `1B-FB1` | Sec 116-121 | 1B, correct side; mid-line |
| `1B-DUG` | Sec 122-132 | 1B, correct side, running up to and including the plate |
| `3B-FB1` | Sec 137-142 | 3B, correct |
| `3B-DUG` | Sec 143-153 | 3B, correct |
| `HOME-B` / `1B-LB1` / `3B-LB1` | Sec 214-243 | **no 200 level exists on this map** |
| `HOME-U` | Sec 514-521 | **1B side**, 12–17 sections from the 500 plate at 531–533 |
| `1B-UB` | Sec 522-534 | 1B, correct (534 is the first 3B section) |
| `3B-UB` | Sec 535-546 | 3B, correct |

**Mismatch: the plate zone is offset about 18 sections toward 1B** — the
model has the plate at the low end of the 108–156 arc with both foul lines
running the same way from it, the Sutter Health shape. **The sides are
correct**, which is the question this step asked, but the 1B numbers run
*toward* the plate in the model where the map has them running away from it.
The model's whole 200 level names sections the map does not have.

**Anchors added:** 1B 108–129, 3B 135–156. Check: **ok**, 31 agree, 0
disagree; 108–115 unmatched (only `HOME-F` claims them), 135–136 and 154–156
unmatched.

---

## What the check now says, across all 31 parks

| Verdict | Parks |
|---|---|
| **flipped** | `camden_yards`, **`coors_field`**, **`progressive_field`** |
| **inconsistent** | `busch_stadium`, `oakland_coliseum`, **`oracle_park`** |
| ok | `chase_field`, `comerica_park`, `dodger_stadium`, `fenway_park`, `rogers_centre`, `truist_park`, **`citizens_bank`**, **`great_american`**, **`guaranteed_rate`** |
| untestable, anchors exist but unusable | `petco_park`, `yankee_stadium` |
| untestable, no anchor | the other 14 |

Fifteen parks are testable; sixteen are not. Mapped parks drop from ten to
**seven**: `fenway_park`, `dodger_stadium`, `truist_park`, `citizens_bank`,
`great_american`, `guaranteed_rate` with sides confirmed, and `minute_maid`
(Daikin) still `sides untested` — it is the one park on the Step 11 list with
no seating map in `seating_maps/`.

The test expectations in `tests/test_netting.py` (`MAPPED_PARKS`,
`JOIN_GAP_PARKS`, `STRUCTURAL_GAP_KINDS`) and `tests/test_site.py` move with
this. `site_data.MAP_READS` — the public, positional statement of each map
finding — still carries the five Step 11 parks only; the six above are not yet
written up for the site.

## What I am least confident about

1. **Rate Field's orientation.** It rests on the drawn diamond alone; no
   named left- or right-field feature on the map corroborates it. Every other
   map here has one. If the artist mirrored the plan, the anchor is wrong and
   the check would call a mirrored table "ok". I think that is unlikely for a
   map fans use to find their seats, and the diamond is drawn with its bases,
   but it is the weakest basis of the six.
2. **Citizens Bank's netting endpoints.** 110–136 as read against a published
   109–138; a hatch on a 25px wedge at 640px is not something I would testify
   to at the boundary sections. The sides and the plate block do not depend on
   it.
3. **Oracle Park's near-plate numbering.** `119 121 122 123` on the 3B side
   and `112 110 109 108 107` on the 1B side, read at 4x from 7–9px labels. An
   odd/even interleave means a misread digit moves a section one place, not
   across the plate, so the side calls survive it; the exact plate block
   (113–118) might be off by one.
4. **The plate centre at Great American and Progressive**, pinned to ±1
   section from where the plate's axis crosses the ring. Neither affects the
   side calls; both affect how large the offset is.
5. **Great American's 200 level.** Unreadable at 6px, so the model's
   `HOME-B` / `1B-LB1` / `3B-LB1` (205–228) are simply not checked.

---

# Step 13 — six more maps (2026-09-07)

Six further maps read the same way as the eleven above: cropped and upsampled
2x–12x around the plate, both foul lines and the deck edges, and read at that
magnification. Where a colour carried the argument, the legend swatch and the
section fill were sampled and compared as RGB rather than judged by eye; those
comparisons are named in the text. Anything I could not resolve is marked as
such rather than inferred.

**Nothing in `stadium.py` was changed.** The only code changes are entries in
`seat_map.SIDE_ANCHORS` and the count that `tests/test_site.py` asserts, which
moved from nine parks to twelve because three of these six became testable.

| Park | File | Pixels | Type | Legibility |
|---|---|---|---|---|
| Daikin Park | `daikin_park.jpg` | 1024x1322 | flat plan | excellent |
| Wrigley Field | `wrigley_field.jpg` | 1536x864 | flat plan | excellent |
| Yankee Stadium | `yankee_stadium.jpg` | 640x640 | flat plan | fair — dense, 6–9px labels |
| Dodger Stadium | `dodger_stadium.jpg` | 1536x1920 | flat plan | excellent |
| Busch Stadium | `busch_stadium.png` | 2208x2166 | flat plan | excellent |
| Nationals Park | `nationals_park.jpg` | 2208x2760 | flat plan | excellent |

Filenames differ from the park names in three cases: Minute Maid Park is
`daikin_park.jpg` under its current name, and Busch and Nationals are `.png`
and `.jpg` respectively. All six were present; none had to be re-encoded.

## Summary of Step 13

| Park | Sides | Plate zone | Severity |
|---|---|---|---|
| **Daikin Park** | **correct** | **correct** — map reads 118–120, model has 117–120 | none found |
| **Yankee Stadium** | **correct** | **correct** on all four rings — 120A/120B, 220B, 320B, 420B | none found |
| **Dodger Stadium** | **correct** | **correct** — the 1/2 and 101/102 pairs behind the plate | none found |
| Wrigley Field | **correct** | off ≈5 toward 3B at field level; 200 level correct; 300/400 off ≈3–4 toward 3B | Moderate |
| Busch Stadium | **scrambled** — 127–133 are right field, not 3B; 152–155 are 3B, not 1B | off ≈14 toward 1B at field level, ≈10 on the upper rings | Severe |
| Nationals Park | **flipped** — 1B and 3B swapped on the field-level ring | off ≈17 toward 3B; the 200 level is wrong in a different way again | Severe |

Three things are worth stating plainly, because the brief for this step was to
assume nothing until the map said so.

- **The streak breaks.** Every one of the eleven maps read before this step
  disagreed with its table somewhere. Daikin Park, Yankee Stadium and Dodger
  Stadium are the first three tables in this file that come out right on both
  counts — sides and plate zone. That is a finding, not an absence of one: it
  was checked the same way as the parks that failed.
- **Yankee Stadium was untestable for a reason that had nothing to do with
  evidence.** It has carried two `primary` anchors from the club's netting page
  since Step 8 (`011` = 1B/RF, `029` = 3B/LF), and they were unusable because
  they name sections on the inner Legends ring, which no zone in this park's
  table claims. The map supplies the same fact on the Field MVP ring — the ring
  the table does number — and the park becomes testable without any new source
  being trusted.
- **Nationals Park is the fifth mirrored table**, after Camden, Coors,
  Progressive and Oracle.

---

## 12. Daikin Park — `daikin_park.jpg`

Flat plan, plate at lower left, the field rotated so the plate-to-centre axis
runs up and to the right. 1024px wide; lower-bowl labels are 11–13px and read
cleanly at 3x.

**Orientation.** Fixed by **Landry's Crawford Boxes**, which are Daikin Park's
left-field porch. The legend swatch samples `(245,224,135)` and sections
`100`–`103` sample `(239,217,142)` — the same fill to within a few counts, and
no other product on the map carries it. So `100–103` are left field.
Corroborated independently by the **Batters Eye Box**, which by definition is
in dead centre: measured from the plate, the Crawford Boxes sit at −91°, the
batter's eye at −52°, and the `150–156` Bullpen Boxes at −5°. A centre-field
axis at −52° puts the foul lines at −97° and −7°, which is where those two
ends fall. The two landmarks agree, and neither is a dugout label.

### Behind home plate

The innermost ring is the **Phillips 66 Diamond Club**, lettered `AA A B C D E
F`, with `C`/`D` on the plate's axis. Behind it, on the numbered 100 ring,
**`119` and `120` are dead centre** — measured as the bearing from the plate
circle opposite the mound circle, which falls at 124.6° against 130.4° for
`119` and 117.9° for `120`. Behind-plate block ≈ **118–120**. This sits inside
the club's published netted run `112–126`, whose centre is 119.

### Lower bowl outward from the plate

- **3B line, ascending:** `118 118 116 116 114 113 112 111 110 109 108 107 106
  105 104` → the Crawford Boxes `103 102 101 100` in left field.
- **1B line, descending:** `122 122 124 125 126 127 128 129 131 132 133 134` →
  the Bullpen Boxes `150 151 152 153 154 155 156` in right field.
- **This map has a numbering defect.** `116`, `118`, `120` and `122` are each
  printed on two adjacent wedges, and `115`, `117`, `121`, `123` and `130` are
  never printed at all. Checked at 12x: both wedges really do read `116`, both
  really do read `122`, and the wedge after `129` really does read `131`. The
  anchors below are split to avoid claiming a number the map does not carry.
- **200 level:** `205 … 219` 3B side, `220 … 236` then `250–255` 1B side.
  Plate at ≈`219/220`.
- **300 level (Terrace/View):** `305 … 319` 3B, `320 … 334` 1B. Plate ≈`319/320`.
- **400 level (View Deck):** `405 … 419` 3B, `420 … 434` 1B. Plate ≈`419/420`.

### Netting

**None drawn.** The field-to-seat boundary is a plain grey band at every
magnification, and the legend has no netting entry. The club publishes
`112–126` plus the Diamond Club separately; the map neither shows nor
contradicts it, and the plate block the map reads is centred inside it.

### Deck levels

100s `100–156` (nothing between 135 and 149); 200s `205–255`; 300s `305–334`;
400s `405–434`; plus `397–399` (Coca-Cola Corner) in right field.

### vs. `stadium.py` (`_make_daikin_park_sections`)

| Zone | Model label | What the map puts there |
|---|---|---|
| `3B-DUG` | Sec 105-110 | 3B, correct |
| `3B-FB1` | Sec 111-116 | 3B, correct |
| `HOME-F` | Sec 117-120 | **behind the plate, correct** (map reads 118–120; 117 is not printed) |
| `1B-FB1` | Sec 121-127 | 1B, correct (121 and 123 are not printed) |
| `1B-DUG` | Sec 128-134 | 1B, correct (130 is not printed) |
| `3B-LB1` | Sec 206-215 | 3B, correct |
| `HOME-B` | Sec 216-223 | centred on 219.5 against a plate at 219/220 — **correct** |
| `1B-LB1` | Sec 224-232 | 1B, correct |
| `3B-UB` | Sec 408-417 | 3B, correct |
| `HOME-U` | Sec 418-426 | centred on 422 against a plate at 419/420 — ≈2–3 toward 1B |
| `1B-UB` | Sec 427-434 | 1B, correct |

**No mismatch of side or plate zone at field level or on the 200 ring.** The
400-level plate block is 2–3 sections toward first base, which is inside the
resolution of "which wedge is on the plate's axis" and is not called an error
here. The model has no 300 level, so the map's `305–334` ring is unmodelled;
the map has no sections `135–149`, which the model also does not claim.

**Anchors added:** 3B `105–114`; 1B `124–129` and `131–134`. Check: **ok**, 20
agree, 0 disagree, 0 unmatched.

---

## 13. Wrigley Field — `wrigley_field.jpg`

Flat plan, plate at the lower left of the field, 1536px wide, with a legend of
34 named products down the left third of the image.

**Orientation.** This map prints the street grid, which settles it outright:
**W. Waveland Ave.** runs along the top and **N. Sheffield Ave.** down the
right side. Waveland is behind left field and Sheffield behind right field.
The map's own gates agree — **Left Field Gate** beside `101`/`203` at the top,
**Wintrust Right Field Gate** beside `134`/`232` at the right — and so do the
`HOME` and `VISITORS` dugout labels, `VISITORS` running along `24–28` on the
first-base side. Three independent statements, none of them the drawn diamond.

### Behind home plate

Two answers, and they agree.

- **Geometrically:** the plate circle and the mound circle give a behind-plate
  bearing of 126.2°. On the 100 ring `118` falls at 125.5° and `117` at
  139.2°, so **`118` is dead centre**, block ≈ `117–119`. On the Club Box ring
  `18` is dead centre.
- **From the map's own product bands:** the legend's **Field Box Home Plate**
  swatch is `(25,188,185)`, and sections `112` through `122` all sample
  `(22–40, 186–191, 180–196)` — that colour and no other. `109–111` and
  `123–125` sample `(0–32, 123–133, 177–200)`, the **Field Box Infield**
  swatch. So the map itself groups **`112–122` as the behind-plate block**,
  centred on 117.

### Lower bowl outward from the plate

- **3B line, ascending:** `111 110 109` (Field Box Infield) `108 … 101` (Field
  Box Outfield) → Left Field Gate. Continuous, every number printed.
- **1B line, descending:** `123 124 125 126` (Field Box Infield) `127 … 134`
  (Field Box Outfield) → Wintrust Right Field Gate. Continuous.
- **Club Box ring:** `3 … 16` 3B side, `18 … 32` 1B side. `17` is not printed —
  `16` and `18` are adjacent wedges.
- **200 level:** `202 … 218` 3B, `220 … 233` 1B, plate at ≈`217/218`. `219` and
  `224` are not printed.
- **300 level:** `303L … 316L` 3B, `317R … 331R` 1B. The map's own **L/R suffix
  switches between `316L` and `317R`**, directly behind the plate, beside the
  Press Box.
- **400 level:** `403L … 415L` 3B, `419R … 431R` 1B.

The L/R suffix is itself a side statement, and it puts the switch at x16/x17 on
both upper decks — consistent with the plate at 117–118 on the 100 ring and
217–218 on the 200 ring.

### Netting

**None drawn.** Checked at 6x along the field-to-seat boundary on both foul
lines: a plain white band, no hatch, no dotted line, and no netting entry in a
34-item legend. The thick orange ring is the **eero Suite Level**, not netting
— the legend swatch matches. This leaves the repo's Wrigley netting gap
(`club_publishes_no_sections`) exactly where it was; the map does not close it.

### Deck levels

Club Box `3–32`; 100s `101–134`; bleachers `501–508`, `511–518`, `536–538`;
200s `202–233`; 300s `303L–331R`; 400s `403L–431R`.

### vs. `stadium.py` (`_make_wrigley_field_sections`)

| Zone | Model label | What the map puts there |
|---|---|---|
| `3B-DUG` | Sec 101-104 | 3B, correct |
| `3B-FB1` | Sec 105-111 | 3B, correct |
| `HOME-F` | Sec 112-114 | **the 3B end of the map's 112–122 home-plate band** — ≈5 short of the plate at 117–118 |
| `1B-FB1` | Sec 115-122 | **the rest of that band**: 115–116 are on the 3B side of the plate, 117–119 are the plate, only 120–122 are 1B |
| `1B-DUG` | Sec 123-134 | 1B, correct |
| `3B-LB1` | Sec 202-212 | 3B, correct |
| `HOME-B` | Sec 213-224 | centred on 218.5 against a plate at 217/218 — **correct** |
| `1B-LB1` | Sec 225-233 | 1B, correct |
| `3B-UB` | Sec 303L-307L | 3B, correct |
| `HOME-U` | Sec 308L-318R | centred on ≈313 against a switch at 316L/317R — ≈3–4 toward 3B |
| `1B-UB` | Sec 319R-331R | 1B, correct |
| `3B-UR` | Sec 403L-408L | 3B, correct |
| `HOME-G` | Sec 409-419 | centred on 414 against a switch at ≈415L/419R — ≈3 toward 3B |
| `1B-UR` | Sec 420R-431R | 1B, correct |

**Mismatch: the field-level plate zone is about 5 sections toward third base,**
and the two upper decks are 3–4 the same way. **The 200 level is right, and the
section ordering is correct on both sides on all four decks.**

**Anchors added:** 3B `101–111`, 1B `123–134`. Check: **ok**, 23 agree, 0
disagree, 0 unmatched. The eleven sections `112–122` are deliberately left out,
on the map's own authority rather than for convenience: they are one product
band that the map names *Field Box Home Plate*, and a shoulder of the
behind-plate group is not a statement about a foul line. Note what this costs.
Had the anchors run to the plate — 3B `101–116`, 1B `120–134` — the check would
say `inconsistent` on `115`/`116` alone, because the model puts them on first
base. That would be a true statement rendered in the wrong vocabulary: the
table is not scrambled, it is offset, and the anchors exist to catch mirrors.
The offset is recorded here instead, which is the only place it can be.

---

## 14. Yankee Stadium — `yankee_stadium.jpg`

Flat plan, plate at the bottom, 640x640 and by far the densest map of the six:
five concentric numbered rings plus a bare-number ring, with labels down to
6px. Read at 7–8x. The smallest source in this file that is nonetheless fully
legible where it matters.

**Orientation.** Three statements, converging.

1. The plate circle is at the bottom with the mound directly above it and the
   **Mastercard Batter's Eye Deck** at top centre, so the plate-to-centre axis
   is vertical and the foul lines run down-left and down-right.
2. The map prints its own netting note along the bottom edge: *"Please note
   that protective netting of varying heights is used in the Stadium from
   Section 011 to behind home plate to Section 029."* The drawn netting band
   ends at the top edge of `011` on the right of the frame and at the top edge
   of `029` on the left — read at 8x, both endpoints unambiguous.
3. The club's netting page, already an anchor in this repo since Step 8, calls
   `011` the **1B/RF side** and `029` the **3B/LF side**. The `011` end is also
   the side the map labels **YANKEES** dugout, which is the first-base side at
   this park.

So the right of the frame is first base. This is the one park of the six where
the side call leans on a source outside the image; the image supplies the
geometry and the section positions, the club page supplies which end is which.

### Behind home plate

**`120A` and `120B`** are dead centre on the Field MVP (100) ring, with `119`
and `121A/121B` flanking. On the ring outside it, **`220B`** is centre; on the
Terrace ring, **`320B`**; on the Grandstand ring, **`420B`**. On the inner
Legends ring, **`020`**. Every ring puts the plate at x20 — the cleanest
internal consistency of any map in this file.

### Lower bowl outward from the plate

- **1B line, descending:** `119 118 117B 117A 116 115 114B 114A 113 112 111 110
  109 108 107 106 105` → `104 103` at the right-field corner.
- **3B line, ascending:** `121A 121B 122 123 124 125 126 127A 127B 128 129 130
  131 132 133 134 135 136` → the left-field corner.
- **Legends ring:** `019 018 017B 017A 016 015B 015A 014B 014A 013 012 011` 1B;
  `021A 021B 022 023 024A 024B 025 026 027A 027B 028 029` 3B.
- **200 level:** `219 … 202` 1B; `221 … 238` 3B.
- **300 level:** `319 … 305` 1B; `321 … 334` 3B.
- **400 level:** `419 … 405` 1B; `421 … 434B` 3B.

Suffixed labels (`114A/114B`, `117A/117B`, `120A/120B`, `127A/127B`) split one
printed wedge across an aisle; `_zone_numbers` already collapses them.

### Netting

**Drawn, and named.** A dark navy band along the field edge running from the
top edge of section `011` on the first-base side, round behind the plate, to
the top edge of `029` on the third-base side. Beyond either endpoint the wall
is a plain brown line. The printed note says the same thing in words. This is
an exact match to the published extent already recorded in `netting.py`, and it
is the first time a map in this file has confirmed a club's netting endpoints
*section by section* on both sides at once.

### Deck levels

Legends `011–029` (with A/B suffixes); 100s `103–136`; 200s `202–238`; 300s
`305–334`; 400s `405–434B`; plus a bare Legends-numbering ring `1–67` that the
model does not use.

### vs. `stadium.py` (`_make_yankee_stadium_sections`)

| Zone | Model label | What the map puts there |
|---|---|---|
| `1B-DUG` | Sec 109-114 | 1B, correct |
| `1B-FB1` | Sec 115-118 | 1B, correct |
| `HOME-F` | Sec 119-121 | **behind the plate, correct** — 120A/120B are dead centre |
| `3B-FB1` | Sec 122-125 | 3B, correct |
| `3B-DUG` | Sec 126-131 | 3B, correct |
| `1B-LR` / `1B-LB1` | Sec 205-217 | 1B, correct |
| `HOME-B` | Sec 218-222 | centred on 220 against a plate at 220B — **correct** |
| `3B-LB1` / `3B-LR` | Sec 223-234 | 3B, correct |
| `1B-UB` | Sec 307-316 | 1B, correct |
| `HOME-U` | Sec 317-323 | centred on 320 — **correct** |
| `3B-UB` | Sec 324-331 | 3B, correct |
| `1B-UR` | Sec 407-418 | 1B, correct |
| `HOME-G` | Sec 419-421 | centred on 420 — **correct** |
| `3B-UR` | Sec 422-429 | 3B, correct |

**No mismatch of side or plate zone anywhere.** The table under-covers each
ring at the outfield end — the map runs to `136`, `238`, `334` and `434B` where
the model stops at `131`, `234`, `331` and `429` — but every zone it does name
is on the right side and in the right place.

The park's join still returns `join_gap / labels_contradict_model`, and
correctly: the club's netting sections `011–029` are on a ring the table does
not number, so no printed section in any zone falls inside the published
extent. That gap is about the *numbering series*, not about the sides, and this
map does not close it. What the map does close is the side question.

**Anchors added:** 1B `105–118`, 3B `122–136`. Check: **ok**, 20 agree, 0
disagree, 11 unmatched (`105–108` and `132–136`, which no zone claims). The
park moves from `untestable` to `ok`.

---

## 15. Dodger Stadium — `dodger_stadium.jpg`

Flat plan, plate at the bottom, 1536x1920. The clearest lower-bowl typography
of the six.

**Orientation.** The map prints **SPECTRUM LEFT FIELD PAVILION** over the odd
sections `301–315` at the upper left and **RIGHT FIELD PAVILION** over the even
sections `302–316` at the upper right. Nothing more is needed. The **DODGER
DUGOUT** label sits on the odd side and **VISITORS DUGOUT** on the even side,
which agrees.

### Behind home plate

Every ring at this park runs outward from a **pair**, and the pair is the plate
block:

- Field level: `1` and `2`, with the **Yaamava' Dugout Club** wrapping the
  backstop in front of them.
- Loge: `101` and `102`.
- Reserve and Top Deck: `1` and `2` again.

Odd numbers run left from the pair, even numbers run right. **Left is third
base, right is first base**, per the pavilion headings.

### Lower bowl outward from the plate

- **3B line (odd), ascending:** field `1 3 5 … 53`; Loge `101 103 105 … 167`;
  Reserve `1 3 … 61`; Top Deck `1 3 … 13`.
- **1B line (even), descending:** field `2 4 6 … 52`; Loge `102 104 106 … 168`;
  Reserve `2 4 … 60`; Top Deck `2 4 … 12`.

The parity *is* the side here, on all four rings. That is what makes this park
checkable at all — a bare number tells you the side without any position
information — and it is why the model's overlapping integer ranges
(`FD12-FD24` against `FD11-FD25`) are not a contradiction.

### Netting

**None drawn.** The field-to-seat boundary is plain at 3.5x behind the plate
and down both lines, and the map has no legend. The club's published extent
(behind the plate → `40` on 1B, `41` on 3B) is unaffected by this; the map
corroborates its *parity claim* — even to first base, odd to third — which is
the part of it the join actually relies on.

### Deck levels

Field `FD1–FD53`+ with the Dugout Club (`DG`) in front; Loge `101–168`; a Club
/ Suite ring in the 200s (`201–261`+, read only in outline); Reserve `1–61`;
Top Deck `1–13`.

### vs. `stadium.py` (`_make_dodger_stadium_sections`)

| Zone | Model label | What the map puts there |
|---|---|---|
| `HOME-DC` | Sec DG1-DG15 | the Yaamava' Dugout Club, in front of the plate — correct |
| `HOME-F` | Sec FD1-FD10 | behind the plate, symmetric about the 1/2 pair — **correct** |
| `1B-FB1` | Sec FD12-FD24 | even, 1B — correct |
| `3B-FB1` | Sec FD11-FD25 | odd, 3B — correct |
| `1B-DUG` | Sec FD26-FD44 | even, 1B — correct |
| `3B-DUG` | Sec FD27-FD45 | odd, 3B — correct |
| `HOME-B` | Sec 101-110 | behind the plate on the Loge, about the 101/102 pair — **correct** |
| `1B-LB1` | Sec 112-136 | even, 1B — correct |
| `3B-LB1` | Sec 111-135 | odd, 3B — correct |
| `HOME-U` | Sec RS1-RS10 | behind the plate on the Reserve — **correct** |
| `1B-UB` | Sec RS12-RS36 | even, 1B — correct |
| `3B-UB` | Sec RS11-RS35 | odd, 3B — correct |

**No mismatch of side or plate zone on any ring.** The table stops short of the
outfield end on each — the Loge runs to `167/168` on the map against `135/136`
in the model — and the map's 200-level Club/Suite ring is unmodelled. Neither
is a side or plate error.

**Anchors added:** four single sections on the Loge ring — 3B `111` and `135`,
1B `112` and `136` — rather than runs, because a range spanning both parities
would claim the other line's sections and `_overlapping_prefixes` would make
the park untestable. These test a ring the club's netting page never reaches.
Check: **ok**, 6 agree (up from 2), 0 disagree.

---

## 16. Busch Stadium — `busch_stadium.png`

Flat plan at 2208x2166, plate at the lower left, drawn as a "Seating Guide"
with streets, gates and a compass rose. Every product is named on the map
itself.

**Orientation.** The map says the side outright at both ends of the bowl, in
its own product names: **LOWER RIGHT FIELD BLEACHERS**, **RIGHT FIELD BOX**,
**LOWER RIGHT FIELD BOX**, **1st BASE FIELD BOX** on one side; **LEFT FIELD
BOX**, **LEFT FIELD PAVILION**, **LOWER LEFT FIELD BLEACHERS**, **3rd BASE
FIELD BOX** on the other. No inference step at all.

The club's netting page corroborates it wedge by wedge, which is worth
recording because the two sources were gathered independently: the page's *"1B
Field Box 135-140"*, *"3B Field Box 161-165"* and *"Lower RF Box 132-134"* land
on exactly the map's wedges of those names.

### Behind home plate

The map labels it: **HOME PLATE BOX = `149`, `150`, `151`** (purple). Flanking
it are **CARDINALS HOME BOX** `145–148` on the first-base side and **VISITORS
HOME BOX** `152–155` on the third-base side. Innermost is the **Community
America Cardinals Club**, bare `1–8`, with the plate on the `4`/`5` axis. The
club's *"Home Field Box 145-155"* straddles all three products and is centred
on 150.

### Lower bowl outward from the plate

- **1B line, descending:** `148 147 146 145` (Cardinals Home Box) `144–141`
  (Cardinals Infield Box) `140–135` (1st Base Field Box / Cardinals Dugout Box)
  `134–130` (Right Field Box / Lower Right Field Box) `129 128 127` (Home Run
  Box) → the **Lower Right Field Bleachers `101 103 105 107 109 111`**, odd
  only, in right field.
- **3B line, ascending:** `152–155` (Visitors Home Box) `156–159` (Visitors
  Infield Box) `160–165` (3rd Base Field Box) `163–167` (Left Field Box) →
  `170 171 172` (Home Run Box) and the **Lower Left Field Bleachers `189 191
  193 195 197`**, odd only, in left field.
- Several numbers in `160–167` are printed on more than one product. Every
  product carrying them is on the third-base side, so a bare label in that
  range is on that line whichever product it names — the same situation as
  Progressive's `153–162`.
- **Loge (200s):** `205 … 248` 1B side, then **HOME REDBIRD CLUB `249 250
  251`** — the map's own name for the behind-plate product, drawn radially
  outside the Home Plate Box — then `252 … 272` 3B side.
- **Pavilion (300s):** `302 … 348` 1B side, then **HOME PAVILION `349 350
  351`**, then `352 … 372` 3B side.
- **Terrace (400s):** `431 … 448` 1B side, plate at ≈`449–450`, `451 … 454`
  3B side. A short ring; it does not reach either outfield.

The 200 and 300 rings each name their behind-plate block on the map, and both
sit at x49–x51, directly outside the Home Plate Box at `149–151`. Three rings
agreeing on the plate's position is what makes the model's offset measurable
rather than estimated.

### Netting

**None drawn.** The field-to-seat boundary is the tan warning track and a
plain white band, at 2.4x behind the plate and down both lines. No legend
entry. The club's published product list stands on its own.

### Deck levels

100s `101–197` (sparse: odd-only in both outfields, nothing between 111 and
127, nothing between 172 and 189); 200s `205–272`; 300s `302–372`; 400s
`431–454`. The model has no 400 level for this park.

### vs. `stadium.py` (`_make_busch_stadium_sections`)

| Zone | Model label | What the map puts there |
|---|---|---|
| `3B-FB1` | Sec 127-133 | **right field** — Home Run Box and Right Field Box, on the 1B side |
| `HOME-F` | Sec 134-137 | **1B line** — Right Field Box / 1st Base Field Box / Cardinals Dugout Box, ≈14 sections down from the plate at 149–151 |
| `1B-FB1` | Sec 138-144 | 1B, correct side |
| `1B-DUG` | Sec 145-155 | **straddles the plate**: 145–148 are 1B, 149–151 are the Home Plate Box, 152–155 are the Visitors Home Box on 3B |
| `3B-DUG` | Sec 157-167 | 3B, correct |
| `1B-LB1` | Sec 245-255 | straddles the Home Redbird Club at 249–251 the same way |
| `HOME-B` | Sec 237-244 | **1B side**, ≈9 short of the Home Redbird Club |
| `3B-LB1` | Sec 256-266 | 3B, correct |
| `HOME-U` | Sec 336-344 | **1B side**, ≈10 short of the Home Pavilion at 349–351 |
| `1B-UB` | Sec 345-358 | straddles the 300 plate |
| `3B-UB` | Sec 359-370 | 3B, correct |

**Mismatch: the table is not mirrored, it is broken in two ways at once.** The
whole arc is shifted toward first base — about 14 sections at field level and
about 10 on the two upper rings — so the model's plate sits where the map has
the first-base dugout boxes. On top of
that, `3B-FB1` is placed *below* `HOME-F` — the model runs 3B down from 127
and 1B up to 155, then attaches `3B-DUG` at 157–167 on the far side. Third base
therefore appears at both ends of the model's arc, which no shift alone would
produce. A swap would not fix this park; the arc has to be re-laid.

**Anchors added:** 1B `127–148`, 3B `152–167`, on top of the three club-page
anchors already there. Check: **inconsistent** (unchanged in kind, much better
evidenced): 30 agree, 13 disagree, 9 unmatched. The thirteen are `127–133`
(source 1B, table 3B) and `152–155` (source 3B, table 1B) — precisely the two
defects above.

---

## 17. Nationals Park — `nationals_park.jpg`

Flat plan at 2208x2760, plate at the bottom, with a 21-item **SEATING AREA**
legend and — uniquely among the seventeen maps read so far — an explicit
**NETTING** key showing a dotted line.

**Orientation.** Fixed by the legend. The **Right Field Terrace** swatch
samples `(158,31,98)`; sections `222`, `224`, `226`, `228`, `230` sample
`(165,29,101)` and are all on the right of the frame. So the right of the frame
is right field, and `127–143` on the lower bowl are the first-base side. The
map's **NATIONALS** and **VISITORS** dugout labels agree — the Nationals dugout
is drawn on the right, and it is on the first-base side at this park. The
**Scoreboard Pavilion** (`231–243`, sampled and matched) is on the same side,
and the scoreboard at Nationals Park is in right-centre.

### Behind home plate

The **PNC Diamond Club**, lettered `A B C D E` on the innermost ring with `C`
on the plate's axis, and **`119–126`** behind it — one grey product band,
matched to the legend's *PNC Diamond Club* swatch, centred between `122` and
`123`. `118` and `127` flank it.

This is the same block the club's own netting page names (*"PNC Diamond Club
119-126"*), and `netting.py` already records the contradiction: *"The club puts
the PNC Diamond Club at 119-126; this park's zone table puts it at 104-107. One
of the two is wrong about the same named product."* **The map decides it in the
club's favour.**

### Lower bowl outward from the plate

- **3B line, ascending:** `118 117 116` (Infield Box) `115–109` (Baseline Box /
  Baseline Reserved / Corner) `108` (Corner Reserved) `107 … 101` (Outfield
  Reserved) → `100` at the left-field corner, past the **Visitors Bullpen**.
  Continuous, every number printed.
- **1B line, descending:** `127 128 129 130 131` (Infield Box) `132–135`
  (Baseline Reserved / Corner) `136 137` (Corner Reserved) `138 … 143`
  (Outfield Reserved) → the right-field corner, past the **Nationals Bullpen**.
  Continuous.
- **200 level:** `201 … 212` 3B, plate at `213/214`, `215 … 243` 1B (the run
  past `221` is the Right Field Terrace and Scoreboard Pavilion).
- **300 level:** `301 … 313` 3B, plate ≈`313/314`, `315 … 321` 1B. **The ring
  stops at `321`.** There is no `322`–`337` on this map.
- **400 level:** `401 … 409` 3B and `416 … 420` 1B. **The upper deck does not
  wrap behind the plate** — `410`–`415` do not exist.

### Netting

**Drawn, as a black dotted line, with a legend key.** It runs along the field
edge from the top corner of section **`109`** on the third-base side, round
behind the plate, to the top corner of section **`135`** on the first-base
side. Read at 2.4x at both ends; beyond either the wall is a plain brown line.

This matches the club's published extent — *"PNC Diamond Club 119-126;
Sections 109-118 and 127-135"* — **exactly, on both endpoints**, and it is the
second independent confirmation in this step (after Yankee Stadium) that a
club's netting numbers and its own seating map agree. Which makes the point
sharper, not softer: the club is self-consistent, and it is the model that is
out.

### Deck levels

100s `100–143` with the PNC Diamond Club `A–E` and Terra Club inside; 200s
`201–243`; 300s `301–321`; 400s `401–409` and `416–420`.

### vs. `stadium.py` (`_make_nationals_park_sections`)

| Zone | Model label | What the map puts there |
|---|---|---|
| `HOME-F` | Sec 104-107, PNC Diamond Club | **3B line, ≈17 sections up toward the left-field corner** — and the PNC Diamond Club is `119–126`, not this |
| `1B-FB1` | Sec 108-114 | **3B side** |
| `1B-DUG` | Sec 115-124 | **3B side** for 115–118; 119–124 are the plate block |
| `3B-FB1` | Sec 127-133 | **1B side** |
| `3B-DUG` | Sec 134-143 | **1B side** |
| `HOME-B` | Sec 207-214 | 207–212 are 3B, 213–214 are the 200 plate — ≈3 toward 3B |
| `1B-LB1` | Sec 215-224 | 1B, **correct** |
| `3B-LB1` | Sec 225-235 | **1B side** — the Right Field Terrace |
| `HOME-U` | Sec 307-314 | 307–313 are 3B, 314 is the 300 plate — ≈3 toward 3B |
| `1B-UB` | Sec 315-326 | 315–321 are 1B, **correct**; `322–326` **do not exist** |
| `3B-UB` | Sec 327-337 | **do not exist** |

**Mismatch: the field-level ring is mirrored — 1B and 3B are swapped — and the
plate zone is about 17 sections up the third-base line on top of it.** The
model's `HOME-F` names the PNC Diamond Club by name and puts it 17 sections
from where both the club and its map put it.

The 200 and 300 levels are wrong in a *third* way, which is worth separating
out. There the model is not mirrored: it places the plate at the low end and
then runs `1B` and `3B` both upward from it (`215–224` then `225–235`;
`315–326` then `327–337`), so both foul lines end up on the first-base side and
nothing is claimed below the plate. That is the Sutter Health shape, in a park
whose field level is a clean mirror. The three rings disagree with each other
as well as with the map.

**Anchors added:** 3B `101–118`, 1B `127–143` — the field-level ring only, and
deliberately so. The 200-level ring would add agreements (`215–224` really is
1B) that would turn a clean `flipped` verdict into `inconsistent` and obscure
the one thing a reader can act on: **at field level, swap the sides.** The
200/300 defects are recorded here instead, where they can be described rather
than compressed into a status word.

Check: **flipped**, 0 agree, 28 disagree, 7 unmatched (`101–107`, which only
`HOME-F` or no zone claims). Nationals Park is the fifth mirrored table.

Its `join_park` verdict stays `join_gap / labels_contradict_model` rather than
becoming `sides_flipped`, because guard G3 fires first — the published extent
already leaves `HOME-F` un-netted, and G3's message names the offending label
ranges directly. That ordering is deliberate and documented in `netting.py`;
the flip is recorded in the side check either way.

---

## What the check says after Step 13

This table supersedes "What the check now says, across all 31 parks" above,
which is the Step 12 state.

| Verdict | Parks |
|---|---|
| **flipped** | `camden_yards`, `coors_field`, `progressive_field`, **`nationals_park`** |
| **inconsistent** | `busch_stadium`, `oakland_coliseum`, `oracle_park` |
| ok | `chase_field`, `citizens_bank`, `comerica_park`, `dodger_stadium`, `fenway_park`, `great_american`, `guaranteed_rate`, `rogers_centre`, `truist_park`, **`minute_maid`**, **`wrigley_field`**, **`yankee_stadium`** |
| untestable, anchors exist but unusable | `petco_park` |
| untestable, no anchor | `american_family`, `angel_stadium`, `citi_field`, `globe_life`, `kauffman_stadium`, `las_vegas_ballpark`, `loan_depot`, `pnc_park`, `target_field`, `tmobile_park`, `tropicana_field` |

Twenty parks now carry an anchor and nineteen are testable, against fifteen
after Step 12. Parks that may name a foul line on the public site rise from
nine to **twelve**; `tests/test_site.py::test_only_twelve_parks_may_name_a_foul_line`
moves with them, and the count in the page text is computed, not written down.

Mapped parks are unchanged at **seven** — `fenway_park`, `dodger_stadium`,
`truist_park`, `citizens_bank`, `great_american`, `guaranteed_rate`,
`minute_maid` — but Daikin Park's entry no longer carries the `sides untested`
flag; it now reads *"sides confirmed against 20 anchored printed sections
(map_read)"*. No park changed `join_park` status in this step.

`site_data.MAP_READS`, the public positional statement of each map finding,
still carries the five Step 11 parks only. The eleven parks read in Steps 12
and 13 are not yet written up for the site.

## What I am least confident about, after Step 13

1. **Yankee Stadium's left/right, considered alone.** The map fixes the plate,
   the axis and every section position, but nothing *inside the image* says
   which foul line is which — no left- or right-field landmark, no distance
   marker, no named outfield product. The side call comes from the club's
   netting page naming `011` as 1B/RF and the map placing `011` on the right.
   That is a real chain and I believe it, but it is one link longer than the
   others in this step, and it is the same shape as the Rate Field weakness
   flagged after Step 12. If the artist mirrored the plan *and* the club page
   is right, both my anchors are wrong together and the check would say `ok`
   about a mirrored table. The YANKEES dugout label sitting on the `011` side
   is what makes me think that has not happened, since the Yankees dugout is on
   first base — but that is a fact I brought to the map, not one I read off it.
2. **Wrigley Field's field-level plate offset, as a number.** That the model is
   short of the plate is solid: the map's own *Field Box Home Plate* colour
   covers `112–122` and the model's `HOME-F` is `112–114`. But "about five
   sections" depends on treating the centre of that colour band as the plate,
   and the geometric measurement (`118` at 125.5° against a behind-plate
   bearing of 126.2°) is pinned to where I placed the plate and mound circles
   on a 1536px image. Four or six would not surprise me. The direction is not
   in doubt.
3. **Busch Stadium's shift, as a single number.** The field-level figure is
   firm: the map names its Home Plate Box `149–151` and the model's `HOME-F` is
   `134–137`, so about fourteen. But the 200 and 300 rings come out at about
   ten, and the model's arc is self-contradictory on top of that — third base
   appears at both ends of it. Any one figure makes this park sound more
   orderly than it is; the per-ring rows in the table above are the honest
   version, and re-laying the arc is not the same job as sliding it.
4. **Daikin Park's absent section numbers.** `115`, `117`, `121`, `123` and
   `130` are not printed anywhere I could find, and `116`, `118`, `120` and
   `122` are each printed twice. I checked five of those at 12x and they are
   what they look like. But "this number appears nowhere on the map" is a claim
   about the whole image, and I read the whole image at 1x and the bowl at 3–6x,
   not every wedge at 12x. If one of them is printed somewhere I did not
   magnify, the anchor split (`124–129` and `131–134`) is over-cautious rather
   than wrong, which is the direction I would rather err in.
5. **Nationals Park's 300 and 400 levels ending where I say they do.** `321`
   and `420` are the last labels I can find going clockwise, and the structure
   visibly stops there behind the K Street Boxes. That makes the model's
   `322–337` sections that do not exist. I am confident about the `400` gap
   (`409` and `416` are adjacent across an obvious break) and slightly less so
   about `321`, where the corner is busy with logos.
6. **Which map "no netting drawn" is a fact about.** Four of these six maps
   draw no netting: Daikin, Wrigley, Dodger, Busch. That is a statement about
   the image only. Three of those four clubs publish an extent in numbers
   anyway, and Wrigley's publishes one in words. A map that does not draw
   netting is not evidence that a park has none, and nothing here should be
   read that way.

---

# Step 14 — six more maps (2026-09-07)

Six further maps, read the same way as the seventeen above: cropped and
upsampled 2.5x–5x around the plate, both foul lines and the deck edges, and
read at that magnification. Where a colour carried the argument, the legend
swatch was read as printed text next to the fill it names. Anything I could
not resolve is marked as such rather than inferred.

**Nothing in `stadium.py` was changed.** The code changes are entries in
`seat_map.SIDE_ANCHORS`, the two recorded G4 gap kinds in
`tests/test_netting.py`, and the named-sides list and count in
`tests/test_site.py`.

Filenames matched the park names in all six cases; the folder was listed first
and no file had to be re-encoded.

| Park | File | Pixels | Type | Legibility |
|---|---|---|---|---|
| Comerica Park | `comerica_park.jpg` | 1536x864 | flat plan | excellent |
| PNC Park | `pnc_park.jpg` | 1024x1024 | rotated plan, plate at middle left | good |
| Target Field | `target_field.jpg` | 640x816 | rotated plan, plate at middle left | fair — smallest of the eighteen, 6–8px labels |
| T-Mobile Park | `tmobile_park.jpg` | 1536x1537 | rotated plan, plate at lower left | excellent |
| Angel Stadium | `angel_stadium.jpg` | 1024x1325 | flat plan | good |
| Petco Park | `petco_park.jpg` | 1024x1024 | flat plan | excellent |

## Summary of Step 14

| Park | Sides | Plate zone | Severity |
|---|---|---|---|
| **Target Field** | **correct** — low at 1B, high at 3B, on all three rings | off ≈12 toward 1B at field level, ≈8–9 on the 200 and 300 rings | Moderate |
| **T-Mobile Park** | **correct** — on both foul-line blocks | off ≈17–20 toward 1B at field level; the 300 ring is off about the same | Moderate |
| Angel Stadium | **scrambled** — `3B-DUG` (133–141) is the far end of the *right-field* arm | off ≈6 toward 3B at field level; the 400 ring's plate block is about right | Severe |
| Comerica Park | **scrambled** — `3B-FB1` (103–108) is the right-field grandstand | off ≈17 toward 1B; the 200 and 300 rings are numbered ranges this park does not have | Severe |
| PNC Park | **scrambled** — `3B-FB1` (101–107) is the right-field arm, `1B-DUG` (119–128) is the left-field arm | off ≈7 toward 1B | Severe |
| Petco Park | **scrambled in a way none of the others are** — the park numbers one foul line odd and the other even, and every zone range spans both | not a meaningful number on a parity-split ring | Severe |

None of the six was unreadable. Two details inside them were, and are marked
below.

### The shape the five share

Five of these six tables make the same assumption: that the bowl is numbered
outward from a plate block in the middle, low numbers running down one line and
high numbers down the other. None of these five parks is numbered that way.
All five number monotonically along the bowl from one foul pole to the other,
so the plate falls in the *middle* of the range, not at its start.

Where the park's ring happens to run low-at-first-base — Target Field, T-Mobile
Park — the table's two side blocks still land on the right foul lines and only
the plate block is misplaced. Where it runs the other way (Angel Stadium) or
wraps through the outfield (Comerica, PNC), one of the two side blocks lands on
the wrong line, and that is what the new anchors catch.

Petco is a sixth case again: it is numbered monotonically *by parity*, odd up
one line and even up the other, and no contiguous integer range describes
either line.

## Comerica Park — scrambled, plate off ≈17

Flat plan, plate at the bottom, standard orientation.

**Landmark that fixed it, named inside the image.** "RIGHT FIELD BALCONY" is
printed along the RF1–RF4 strip drawn directly outboard of sections 101–106,
with "Comerica Landing" and the "Right Field Pitcher's Pub" beyond it, and the
legend colour filling 101–106 is the one the key names "Right Field
Grandstand". The opposite arm ends in the key's "Left Field Baseline Box"
colour at 141–143 and the Pavilion at 144–151. Nothing outside the image was
needed; the TIGERS / VISITORS dugout labels agree but did not decide it.

**Behind the plate.** 126, 127, 128, 129 at the 100 level, with the navy
Priority Club boxes numbered 1–5 inside them and a second tan Terrace ring
(120A–129B) behind.

**Which way each line runs.** From the plate the numbers *descend* down the
first-base line — 125 124 123 … 116 … 107 … 101 — and *ascend* down the
third-base line — 130 131 … 140 141 142 143 144 … 151. The ring wraps behind
the plate; there is no low-number end on the third-base side at all.

**Deck levels as printed.** 100 level 101–151, plus the Terrace ring with A/B
suffixes and the Priority Club boxes 1–5. 200 level **210–219 only**, entirely
on the first-base side, labelled Mezzanine / Tiger Club with Party Decks #1–#3
outside it. 300 level **321–345**.

**Netting.** None drawn.

**Against the table.**

| Zone | Table says | Map says |
|---|---|---|
| `3B-FB1` 103–108 | 3B infield | **right-field grandstand and Kaline's Corner — 1B side** |
| `HOME-F` 109–112 | behind plate | up the first-base line, ≈17 sections short of the plate |
| `1B-FB1` 113–119 | 1B infield | 1B side, correct line, but these are corner and outfield boxes |
| `1B-DUG` 120–130 | 1B baseline | 120–125 on 1B, 126–129 **behind the plate**, 130 on 3B |
| `3B-DUG` 137–145 | 3B baseline | 3B side, correct |
| `HOME-B`/`1B-LB1`/`3B-LB1` 210–238 | three 200-level blocks | the 200 ring is 210–219 and **all of it is on the 1B side**; 220–238 do not exist |
| `HOME-U`/`1B-UB`/`3B-UB` 308–340 | three 300-level blocks | the 300 ring is 321–345; **308–320 do not exist** |

This is the one park in the file to move the *wrong* way down the named-sides
list. Comerica had two `primary` anchors from the club's netting page — Section
116 (1B line), Section 142 (3B line) — and both of them land right, so
`check_side_anchors` returned `ok` and the park was allowed to name its foul
lines on the site. The map read adds 101–106 on the first-base side and the
table calls 103–108 third base, so the verdict is now `inconsistent` and the
park may not name a line. Two anchored sections agreeing was never evidence
about the other forty; that is exactly what the module comment above
`SIDE_ANCHORS` says an `ok` does and does not mean, and this is the first time
it has cost a park rather than saved one.

`netting.py` had already half-noticed this. Its Comerica note reads *"this
park's zone table has 103-108 and 137-145 both on the 3B side — so the netted
run is not one int[erval]"*, and records `gap_kind='arc_endpoints_unresolved'`.
The map says which of the two is misplaced: 103–108.

## PNC Park — scrambled, plate off ≈7

Rotated plan. The plate sits at the middle left and the outfield opens to the
lower right; the third-base line runs to the right of the frame and the
first-base line runs down to the lower left.

**Landmarks that fixed it, both named inside the image.** "JIM BEAM LEFT FIELD
LOUNGE" is printed vertically alongside sections 135–138 and the 235–238 deck
above them. "RIGHT FIELD GATE" is printed alongside the other arm's outer end,
with the "MILLER LITE SKULL BAR" and "RIVERWALK" under it and the right-field
bleachers 147 146 145 144 143 142 running from immediately past section 101
along the outfield wall. The PIRATES DUGOUT label lies on the left-field arm
and agrees.

**Behind the plate.** 114–119 at the 100 level, with 115/116/117 most central,
and field boxes 14–19 inside them. The Pirates dugout begins at box 20.

**Which way each line runs.** First base descends: 113 112 110 109 108 107 105
103 101 — **111 is not printed**, and field box 3 is not printed either. Third
base ascends: 120 121 123 124 125 127 128 129 130 … 138, then the ring
continues round the outfield 139 140 141 (centre) and 142–147 (right field),
closing back on 101.

**Deck levels as printed.** Field boxes 1–32. 100 level 101–147, one continuous
ring. 200 level 201–238, with a Suite Level band between the 100 and 200 rings
on the infield, the World Series Suites at the third-base end and 235–238 in
left field. 300 level 301–339.

**Netting.** None drawn on this map.

**Against the table.**

| Zone | Table says | Map says |
|---|---|---|
| `3B-FB1` 101–107 | 3B infield | **the right-field arm, ending at the Right Field Gate — 1B side** |
| `HOME-F` 108–111 | behind plate | up the first-base line, ≈7 short; 111 is not printed at all |
| `1B-FB1` 112–118 | 1B infield | 112 and 113 on 1B; 114–117 **behind the plate** |
| `1B-DUG` 119–128 | 1B baseline | **the left-field arm past the Pirates dugout — 3B side** |
| `3B-DUG` 130–139 | 3B baseline | 130–138 correct; 139 is in centre field |

An independent cross-check falls out of this. `netting.py` records PNC's
published extent as *"Section 101 → Section 130"*. On the map's numbering that
is a single contiguous run from the right-field foul pole, through the plate,
to a point down the left-field line — which is what a netting extent looks
like. On the table's numbering it would start in `3B-FB1`, cross the plate, and
end in `3B-DUG`, having passed through the 1B blocks in between. The map's
reading is the one that makes the club's own sentence coherent.

## Target Field — sides correct, plate off ≈12

Rotated plan, plate at the middle left. The smallest image of the eighteen read
so far at 640x816; the bowl labels are 6–8px and needed 5x to read, and a few
of the 300-ring labels at the top of the frame I would not swear to.

**Landmark that fixed it, named inside the image.** "Corona Right Field Field
Patio 139, 140" is drawn immediately outboard of section 101 at the foul pole,
with "Gate 29 Right Field Entrance" beyond it. The other arm ends under "Gate 6
Left Field Entrance". A second, independent statement is in the map's own
legend: *"Home Plate Taproom presented by Pryes Brewing (Section 213-216)"*,
which fixes the plate block on the 200 ring without any geometry at all.

**Behind the plate.** 112–116 at the 100 level, 113/114/115 at the bend;
lettered Thrivent Club boxes F/G/H and Champions Club 8/9/10 inside them;
213–216 on the 200 ring, named by the map.

**Which way each line runs.** First base descends 111 110 109 … 101 to the
right-field pole, with boxes 7→1 and letters E D C B A inside. Third base
ascends 117 118 119 120 … 127 to the left-field pole, with boxes 10–17 and
letters J–V inside, then the left-field bleachers 128–131.

**Deck levels as printed.** Field level 101–140 plus numbered boxes 1–17 and
lettered boxes A–V. 200 level 201–240 (Home Plate Taproom 213–216, Treasure
Island Home Run Deck View 229–234). 300 level 301–334 (Home Run Deck Terrace
329–334). A light-blue arc runs between the club boxes and the 200 ring; the
map's key names that colour "Suite Level", so it is not netting.

**Netting.** None drawn.

**Against the table.**

| Zone | Table says | Map says |
|---|---|---|
| `HOME-F` 101–103 + Diamond Box | behind plate | **at the right-field foul pole**, ≈12 sections up the line |
| `1B-FB1` 104–109 | 1B infield | 1B side, correct |
| `1B-DUG` 110–120 | 1B baseline | 110–111 on 1B, 112–116 **behind the plate**, 117–120 on **3B** |
| `3B-FB1` 121–127 | 3B infield | 3B side, correct |
| `3B-DUG` 128–137 | 3B baseline | 128–131 are the left-field bleachers; 132–137 are centre and right-centre |
| `HOME-B` 203–209 | behind plate, 200 ring | on the 1B side; the map names 213–216 as the plate block |
| `HOME-U` 303–309 | behind plate, 300 ring | on the 1B side; the plate is ≈313–316 |

The anchor recorded for the third-base line is `121–127`, not `117–127`. That
is deliberate: 117–120 are plainly on the third-base side of the bend, past the
VISITORS DUGOUT label, and the table calls them `1B-DUG`, but they are close
enough to the plate that an anchor there would be arguing about a boundary
rather than about a side. The check therefore reports Target Field as `ok` —
which, as the module comment says, rules out a mirror and nothing else. The
plate offset above is the finding; the check is not the place it lives.

## T-Mobile Park — sides correct, plate off ≈17–20

Rotated plan, plate at the lower left, outfield to the upper right.

**Landmarks that fixed it, both named inside the image.** "Hit it Here Cafe" is
printed along the outfield sections 105–110 at the end of the low-number arm,
with "RF GATE" beyond it. On the opposite arm the map prints "3B ENTRY" against
sections 330–333, which sit on the same radials as 100-level 129–133, and "LF
GATE" over that arm's far end. Two labels, each naming a field, on opposite
arms.

**Behind the plate.** Diamond Club 25 / 27 / 33 / 35 hug the bend; behind them
the 100-level wedges 126–129, with 127 and 128 most central. **130 is not
printed.**

**Which way each line runs.** First base descends 126 125 124 … 114 112 111 110
… 102, past the MARINERS dugout — **113 is not printed**. Third base ascends
128 129 131 132 … 144 146 … 150 151, past the VISITORS dugout — **130 and 145
are not printed**.

**Deck levels as printed.** Diamond Club 21–35. 100 level: bowl 101–151, plus
180–187 (the T-Mobile 'Pen deck across the top of the frame) and 190–195 in
right-centre. 200 level 211–227 on the first-base side and 233–249 on the
third-base side, with 228–232 not printed — the Press Club band occupies that
arc — and suites s1–s69 outside them. 300 level 306–347.

**Netting.** None drawn. But `netting.py` already records the club's own
sub-range heights: *"27 ft in front of Sections 126-134; 13.5 ft above field
level for 115-125 and 135-146"*. On the map's numbering the tall run sits over
and just past the plate, which is what a tall run is for. Centred on the
model's `HOME-F` of 108–111 it would be seventeen sections out in right field.
That is independent corroboration of the offset from a source already in the
repo, and it is the reason the offset is given as a range: the map puts the
plate at 126–129 and the club's tall-net marker centres on 130.

**Against the table.**

| Zone | Table says | Map says |
|---|---|---|
| `HOME-F` 108–111 | behind plate | **the right-field corner, in front of the Hit it Here Cafe** |
| `1B-FB1` 112–117 | 1B infield | 1B side, correct |
| `1B-DUG` 118–128 | 1B baseline | 118–127 correct; 128 is on 3B |
| `3B-FB1` 133–138 | 3B infield | 3B side, correct |
| `3B-DUG` 139–148 | 3B baseline | 3B side, correct; 145 is not printed |
| `HOME-B` 210–217 etc. | three 200-level blocks | the 200 ring is 211–227 (1B) and 233–249 (3B); 228–232 do not exist |
| `HOME-U` 308–317 etc. | three 300-level blocks | the 300 ring runs 306–347 and its plate is ≈325–328, by the Home Plate Gate |

## Angel Stadium — scrambled, plate off ≈6

Flat plan, plate at the bottom, standard orientation.

**Landmark that fixed it, named inside the image, twice over.** The map's key
has a swatch labelled "Left Field Pavilion" and a swatch labelled "Right Field
Pavilion". The first is the orange filling sections 256–260 at the head of the
low-number arm; the second is the yellow filling 241–249 at the head of the
high-number arm. The ANGELS and VISITOR dugout labels agree. A third statement
is printed on the map in words: *"Protective netting extends from SECTIONS 109
– 127"*, which is centred on 118.

**Behind the plate.** The Lexus Diamond Club arc **114–122**, with 117/118/119
most central and the Diamond Table and Don Julio Club rings behind it.

**Which way each line runs.** Every ring at this park ascends monotonically
from the third-base end to the first-base end. Field level 101 (left-field
pole) → 118 (plate) → 135 (right-field pole). The 200, 300, 400 and 500 rings
all start their numbering at the same corner: 201/301/401/501 are all at the
third-base end of the frame.

**Deck levels as printed.** Field 101–135, plus numbered Diamond boxes 11–78
and the lettered L1–L3 / D1 club boxes. 200 level 201–233, then 236–240 (Right
Field Hall of Fame), 241–249 (Right Field Pavilion) and 256–260 (Left Field
Pavilion). 300 level 301–351. 400 level 401–436. 500 level 501–540.

**Netting.** The only one of the six that says anything. The map's own text
gives 109–127. `netting.py` carries the club page's 103–133. Those disagree in
extent — and they agree exactly on centre: both are centred on section 118,
which is the middle of the map's 114–122 plate block. Two published runs, from
the same club, independently confirming where the plate is.

**Against the table.**

| Zone | Table says | Map says |
|---|---|---|
| `3B-FB1` 103–109 | 3B infield | 3B side, correct |
| `HOME-F` 110–113 | behind plate | on the third-base line, ≈6 short of 114–122 |
| `1B-FB1` 114–120 | 1B infield | **this is the plate block** — the Lexus Diamond Club arc |
| `1B-DUG` 121–129 | 1B baseline | 121–122 behind the plate; 123–129 correct |
| `3B-DUG` 133–141 | 3B baseline | **133 134 135 are the last three sections of the right-field arm**; 136–141 do not exist at field level |
| `3B-LB1` 230–239 | 3B club | 230–233 are at the *first-base* end of the 200 ring; 234–235 are not printed |
| `HOME-U` 413–420 | behind plate, 400 ring | about right — the 400 ring runs 401–436 and its middle is ≈418 |
| `3B-UB` 434–445 | 3B upper | 434–436 are the first-base end of the 400 ring; 437–445 do not exist |

The `3B-DUG` error is what the new anchor catches, and it is a side error
rather than a boundary error: 133–135 are not near the plate, they are the far
end of the opposite foul line.

Note also what the netting extent does to the table. On the map's numbering
103–133 is one contiguous run from the third-base line through the plate to the
first-base line. On the table's numbering it starts in `3B-FB1`, crosses
`HOME-F` and both 1B blocks, and ends inside `3B-DUG` — a run that begins and
ends on the same foul line while passing through the other one.

## Petco Park — scrambled by parity

Flat plan, plate at the bottom, standard orientation. The clearest of the six
to read and the furthest from its table.

**Landmark that fixed it, named inside the image.** "WESTERN METAL SUPPLY CO.
BUILDING" is drawn at the head of the even-numbered arm, next to the "FOUL POLE
SUITE" label — that building stands at the left-field foul pole. The "T-MOBILE
HOME RUN DECK" label runs along the outfield end of the odd-numbered arm. The
VISITOR'S and PADRES' dugout labels agree.

**Behind the plate.** 101, 102, 103, 104 at field level, with the "LEXUS HOME
PLATE CLUB" strip drawn in front of them and lettered boxes A–L below.

**Which way each line runs — the finding.** Petco numbers **one foul line even
and the other odd**, from a shared block behind the plate:

- third base (left, toward the Western Metal Supply Co. Building):
  106 108 110 112 114 116 118 120 122 124 126 128 130 132 134
- first base (right, toward the T-Mobile Home Run Deck):
  105 107 109 111 113 115 117 119 121 123 125 127 129 131 133 135 137

The 200 ring does the same thing (201–233 splitting by parity onto the two
arms), and so does the 300 ring above the plate area.

This resolves what has looked like a contradiction in `netting.py` since Step
8. The club's page publishes *"angled net coverage 111-115 (1B side) and
112-116 (3B side)"*, and `check_side_anchors` has refused to test this park
ever since, because those two ranges overlap as integer intervals and a section
is on one foul line or the other. On the map they overlap only as integers:
111, 113, 115 are on the first-base arm and 112, 114, 116 are on the third-base
arm, and the club's sentence is exactly right. The guard is still correct to
decline — it is reasoning about integer ranges, and the ranges as written are
not testable — so Petco stays `untestable` and
`tests/test_netting.py::test_overlapping_side_claims_make_a_park_untestable`
still passes unchanged. The four map-read anchors added for this park are
single numbers (122 and 134 on 3B, 125 and 137 on 1B) because any range
spanning both parities would be a claim about sections on the other line. They
are recorded evidence, not a verdict.

**Deck levels as printed.** Field level 101–137 (two concentric rings sharing
the same numbers), lettered boxes A–L, and the TTS1–TTS36 terrace tables. 200
level 201–233. 300 level 300–328. Tower Lofts at both corners, Skyline Patio on
the third-base side.

**Netting — the detail I could not call.** The map draws an unlabelled magenta
edging along a run of section edges. It is *not* netting, and the reason is
positional: on the first-base arm it runs along the **outer** (concourse) edge
of 111–127, not the field-facing edge, and the same magenta appears out at the
300 ring and along the Toyota Terrace VIP Tables, where no netting can be.
There is no key on this image to say what it is. So: no netting drawn, and the
magenta is something else I cannot name.

**Against the table.** Every field-level zone range spans both foul lines:

| Zone | Table says | On the map |
|---|---|---|
| `3B-FB1` 101–105 | 3B infield | 101–104 behind the plate; 105 on 1B |
| `HOME-F` 106–109 | behind plate | 106, 108 on 3B; 107, 109 on 1B |
| `1B-FB1` 110–116 | 1B infield | 111, 113, 115 on 1B; 110, 112, 114, 116 on 3B |
| `1B-DUG` 117–126 | 1B baseline | odds on 1B, evens on 3B |
| `3B-DUG` 128–137 | 3B baseline | evens on 3B, odds on 1B |

An offset figure for the plate zone is not worth quoting here. The ring is not
the shape the table thinks it is.

## What changed in code

`seat_map.SIDE_ANCHORS` gains entries for four parks and grows at two more:

| Park | Anchors added | Verdict before | Verdict after |
|---|---|---|---|
| `comerica_park` | 101–106 → 1B, 133–140 → 3B (`map_read`) | `ok` | **`inconsistent`** |
| `pnc_park` | 101 → 1B, 107–110 → 1B, 130–138 → 3B | `untestable` | **`inconsistent`** |
| `target_field` | 101–106 → 1B, 121–127 → 3B | `untestable` | **`ok`** |
| `tmobile_park` | 114–127 → 1B, 133–144 → 3B | `untestable` | **`ok`** |
| `angel_stadium` | 103–109 → 3B, 123–135 → 1B | `untestable` | **`inconsistent`** |
| `petco_park` | 122, 134 → 3B; 125, 137 → 1B (single numbers) | `untestable` | `untestable` (by the overlap guard, as before) |

Every anchor range was restricted to numbers this map actually prints. That is
why PNC's first-base anchor stops at 110 (111 is not printed), why T-Mobile's
133–144 stops short of the unprinted 145, and why Petco's are single numbers.

Downstream, `tests/test_site.py::test_only_twelve_parks_may_name_a_foul_line`
becomes `..._thirteen_...`: Target Field and T-Mobile Park join the list,
Comerica Park leaves it, net +1. `STRUCTURAL_GAP_KINDS` in
`tests/test_netting.py` records Angel Stadium and PNC Park failing on
`labels_contradict_model` rather than `labels_wrap_unpublished` — both already
failed on the wrap, and the new anchors are the earlier and stronger reason.
No park changed `join_park` status, and the netting-gap count stays at 24.

`site_data.MAP_READS` still carries the five Step 11 parks only. The seventeen
parks read in Steps 12, 13 and 14 are not yet written up for the site.

## What I am least confident about, after Step 14

1. **T-Mobile Park's plate block, as a number.** That the model's `HOME-F` of
   108–111 is out in right field is not in doubt — 108, 109 and 110 are drawn
   beyond the outfield wall corner with the Hit it Here Cafe in front of them.
   But *where* the plate is I put at 126–129 by tracing the radial through the
   bend, and the club's own 27-ft netting marker (126–134) centres on 130.
   Those are not the same answer. The bend is drawn as a smooth curve with the
   Diamond Club sections 25/27/33/35 on top of it, and picking the wedge whose
   radial passes through the plate is a judgement about a curve, not a reading
   of a label. This is the one park of the six where I would not defend the
   plate block to the section; the offset could be 17 or it could be 20. The
   direction and the order of magnitude are solid.
2. **Target Field at 640x816.** It is the smallest map read in this file and
   the only one where I had to go to 5x to read the bowl at all. The plate
   block (112–116) and the two arms I am confident about, because the map's own
   legend independently names 213–216 as the Home Plate Taproom on the ring
   above and that lands where the geometry says it should. The 300-ring labels
   at the top of the frame — the 329–334 Home Run Deck Terrace range — I read
   from the legend text rather than from the wedges, because the wedges are
   under logos. If that range is wrong, it is wrong from the legend.
3. **Comerica's missing 200-level and 300-level ranges.** I claim 220–238 and
   308–320 do not exist. That is a statement about the whole image, and I read
   the whole image at 1x and the two arms and the upper deck at 2.5–4x, not
   every wedge at maximum. The 300-level claim I am fairly confident about
   (321 is clearly the first label going up the first-base side, and the arc
   below it is the Comerica Entry plaza). The 200-level claim is stronger
   still, because the mezzanine visibly ends at 219 with Party Deck #3 beyond
   it and there is no second-deck structure at all on the third-base side of
   this frame — but "no such number anywhere" is always the claim in this file
   I would most like a second reader for.
4. **Petco's magenta edging.** I have said what it is not, with a positional
   reason I believe: it is on the concourse edge, and it appears at the 300
   ring and along the Toyota Terrace. I have not said what it *is*, because the
   image has no key. If a future reader finds a keyed version of this map and
   it turns out the magenta marks netting after all, the reasoning above is
   where the error would be, and the sides read for Petco do not depend on it.
5. **Angel Stadium's 200-ring reading past 233.** The field, 400 and 500 rings
   I traced end to end. On the 200 ring I read 201–233 on the bowl and then
   236–240, 241–249 and 256–260 as separate outfield blocks, and I did not
   establish whether 234, 235, 250–255 are printed somewhere I did not
   magnify. The claim that `3B-LB1` (230–239) sits at the first-base end does
   not depend on that — 230–233 are visibly there — but "234–235 are not
   printed" does.
6. **What "no netting drawn" is a fact about — again.** Five of these six maps
   draw no netting: Comerica, PNC, Target Field, T-Mobile and Petco. Four of
   those five clubs publish an extent in numbers elsewhere, and this file has
   just used two of those published extents (PNC's 101→130, T-Mobile's 126–134)
   as evidence *about the map*. That works in this direction only. A map that
   does not draw netting is not evidence that a park has none.

---

# Step 15 — six more maps (2026-09-07)

Six further maps, read the same way as the twenty-three above: cropped and
upsampled 2.5x–12x around the plate, both foul lines, the deck edges and the
legend, and read at that magnification. Where a colour carried the argument it
was not eyeballed — the legend swatch was sampled for its RGB value and the map
searched for connected regions of that exact colour, so that "this fill appears
here and nowhere else" is a measurement rather than an impression. Anything I
could not resolve is marked as such rather than inferred.

**Nothing in `stadium.py` was changed.** The code changes are entries in
`seat_map.SIDE_ANCHORS` for five parks and an addition to a sixth, one recorded
gap kind in `tests/test_netting.py`, and the named-sides list and count in
`tests/test_site.py`.

The folder was listed first. All six files were present under names close to
but not identical with the park names: `american_field.jpg`,
`loandepot_park.png`, `kauffman_stadium.jpg`, `globe_life.jpg`,
`rogers_centre.jpg`, `tropicana_field.png`. No file had to be re-encoded.

| Park | File | Pixels | Type | Legibility |
|---|---|---|---|---|
| American Family Field | `american_field.jpg` | 1536x1920 | flat plan | excellent |
| loanDepot park | `loandepot_park.png` | 3300x2100 | rotated plan, plate at lower right | excellent |
| Kauffman Stadium | `kauffman_stadium.jpg` | 1536x1536 | flat plan | excellent |
| Globe Life Field | `globe_life.jpg` | 2208x2758 | rotated plan, mild perspective | fair — the densest of the twenty-nine, five concentric label rings |
| Rogers Centre | `rogers_centre.jpg` | 1536x1988 | flat plan | good |
| Tropicana Field | `tropicana_field.png` | 1024x1024 | flat plan | good |

## Summary of Step 15

| Park | Sides | Plate zone | Severity |
|---|---|---|---|
| **American Family Field** | **correct** — low at 1B, high at 3B, on all four rings | off ≈13 toward 1B at field level, ≈11 on the Loge, ≈9 on the Terrace | Moderate |
| **loanDepot park** | **correct** — on both bowl blocks and both Vista blocks | off ≈13 toward 1B in the bowl, ≈8 on the Legends ring, ≈7 on the Vista ring | Moderate |
| **Rogers Centre** | **correct** — and the club's own netting page already said so | off ≈13 toward 1B at the 100 level, ≈7 on the 200 and 500 rings | Moderate |
| Kauffman Stadium | **scrambled** — `1B Infield` (114–120) and `1B Dugout` (121–131) are the *third*-base line, `3B Dugout` (133–143) is the *first* | off ≈16 toward 3B at field level; the 400 ring's plate block is nearly right | Severe |
| Globe Life Field | **scrambled** — `1B Infield` (6–11) is the third-base line, `3B Infield` (25–30) is the first-base line and the right-field corner | off ≈10 toward 3B in the bowl, ≈9 on the mezzanine | Severe |
| Tropicana Field | **scrambled by parity** — the park numbers one foul line odd and the other even, and every zone range spans both | not a meaningful number on a parity-split ring | Severe |

None of the six was unreadable. A handful of details inside them were, and each
is marked where it appears and again at the end.

### Which convention each of the six uses

Step 14 found that most zone tables assume the bowl is numbered outward from a
plate block in the middle, while most parks number monotonically from one foul
pole to the other with the plate mid-range. All six of these parks number
monotonically. Not one numbers outward from the plate. What separates them is
which pole the low numbers are at — and Tropicana's third answer:

| Park | Low numbers at | Plate lands at |
|---|---|---|
| American Family Field | right field (1B) | 117/118 of 101–131 |
| loanDepot park | right field (1B) | 14/15 of 1–33 |
| Rogers Centre | right field (1B) | 123/124 of 101–148 |
| Kauffman Stadium | **left field (3B)** | 126–129 of 101–152 |
| Globe Life Field | **left field (3B)** | 13/14 of 1–33 |
| Tropicana Field | **neither — parity split** | 101/102, odds up 3B, evens up 1B |

That is the whole story of this step. The three parks whose rings run
low-at-first-base come out with their side blocks on the right foul lines and
only the behind-plate block misplaced, exactly as Target Field and T-Mobile
Park did. The two that run the other way have their two infield blocks on each
other's lines. Tropicana is a second Petco.

### The dugout label is worth nothing, and two of these maps prove it

`seat_map.SIDE_ANCHORS` has never used a HOME DUGOUT label as the landmark that
fixes a map, and this step is the first to show what that would have cost.
loanDepot park prints MARLINS DUGOUT on the **third-base** arm; Rogers Centre
prints BLUE JAYS DUGOUT on the **third-base** arm. Both readings are backed by
something better than a dugout — loanDepot by its own legend, Rogers by the Blue
Jays' netting page, a `primary` anchor in this repo since Step 8. Anyone reading
either map by "home dugout means first base" would have mirrored the park.

That matters here because two of these six maps have **nothing else**. See
"What I am least confident about, after Step 15".

## American Family Field — sides correct, plate off ≈13

Flat plan, plate at the bottom, outfield at the top, standard orientation. The
cleanest of the six to read; every number below was resolved at 3x or better.

**Landmark that fixed it — and this is the weak one.** This map names no field
and no base anywhere on the sheet. I magnified the outfield band, both corners
and the whole legend looking for a "Left Field" or "Right Field" heading of the
kind Comerica, Angel Stadium and Target Field supplied, and there is none. Its
only side-bearing labels are **HOME DUGOUT**, drawn against 112–115, and
**VISITORS DUGOUT**, drawn against 120–123 — and per the section above, a dugout
label is not a landmark. So the orientation here rests on the drawn plan alone:
the map draws the diamond with home plate at the bottom and the outfield at the
top, and in that projection first base is the right-hand arm. The dugout labels
agree with that; they do not establish it.

**Behind the plate.** 117 and 118 dead centre at the 100 level, in the Field
Diamond Platinum maroon, with the map's centre line falling in the gap between
them. 218/219 on the Loge ring, 329/330 on the Club ring, 420/421 on the
Terrace ring.

**Which way each line runs.** From the plate the numbers *descend* down the
first-base line — 116 115 114 … 107 106 — ending in the pink Field Bleachers 104
103 102 101 at the right-field corner, past the Visitors Bullpen and under the
Miller High Life Loft. **105 is not printed**; a navy Field Bleachers Box strip
occupies that arc. Going the other way the numbers *ascend* down the third-base
line — 119 120 … 125 … 131 — ending at 131 under J. Leinenkugel's Barrel Yard,
with the Home Bullpen and the Miller Lite Landing beyond.

**Deck levels as printed.** 100 level 101–131 (no 105). Loge 201–236, the
201–205 end being the yellow Loge Bleachers at the right-field corner and
233–236 the Loge Bleachers at the left-field corner. Club level 306–345, with
the gold Club Suites numbered 24–67 in a ring outside them (24 at the
right-field end, 67 at the left-field end) and the grey Johnsonville Party Deck
302–305 beyond the Loge Bleachers. Terrace 407–442. **The Terrace ring starts at
407** — 401–406 are not printed anywhere.

**Netting.** Drawn, in the red hatched fill the legend names "Netting", along
the field-facing edge of the field-level sections. Its first-base end is the
**109/110 boundary** and its third-base end is the **125/126 boundary**, so the
run is 110 → 125 through the plate: seven or eight sections each side of
117/118, which is symmetric and corroborates the plate block.

**Against the table.**

| Zone | Table says | Map says |
|---|---|---|
| `HOME-F` 103–106 | behind plate | **the right-field corner** — 103 and 104 are Field Bleachers by the Visitors Bullpen, ≈13 sections up the first-base line, and 105 is not printed |
| `1B-FB1` 107–112 | 1B infield | 1B side, correct |
| `1B-DUG` 113–122 | 1B baseline | 113–116 on 1B, 117–118 **behind the plate**, 119–122 on **3B** |
| `3B-FB1` 125–130 | 3B infield | 3B side, correct |
| `3B-DUG` 131–140 | 3B baseline | 131 is on 3B and is the last section of the ring; **132–140 do not exist** |
| `HOME-B` 206–212 | behind plate, Loge | on the 1B side; the Loge plate block is 218/219 |
| `1B-LB1` 213–222 | 1B Loge | 213–217 on 1B, 218–219 behind the plate, 220–222 on **3B** |
| `3B-LB1` 223–232 | 3B Loge | 3B side, correct |
| `HOME-U` 405–412 | behind plate, Terrace | 405 and 406 **do not exist**; 407–412 are on the 1B side, ≈9 short of the plate at 420/421 |
| `1B-UB` 413–424 | 1B Terrace | 413–419 on 1B, 420–421 behind the plate, 422–424 on **3B** |
| `3B-UB` 425–436 | 3B Terrace | 3B side, correct |

The anchors recorded are 101–114 and 201–216 on the first-base side and 123–131
and 223–236 on the third. The third-base anchors start at 123 and 223 rather
than 119 and 220. That is deliberate, and it is the call Target Field got:
119–122 and 220–222 are plainly on the third-base side of the bend, past the
VISITORS DUGOUT label, and the table calls them `1B Field` and `1B Loge`, but
they are close enough to the plate that an anchor there would be arguing about a
boundary rather than about a side. The check therefore reports American Family
Field as `ok`. The plate offset above is the finding; the check is not the place
it lives.

## loanDepot park — sides correct, plate off ≈13

Rotated plan. Home plate sits at the lower right of the field with the outfield
opening to the upper left; the first-base line runs up the right of the frame
and the third-base line runs to the lower left.

**Landmark that fixed it, named inside the image, three times over.** The legend
names two products *by side and by section label*: **"FIRST BASE DUGOUT CLUB |
FL1-FL3"** and **"THIRD BASE DUGOUT CLUB | FL9-FL11"**. FL1, FL2 and FL3 are
drawn along the upper-right arm; FL9, FL10 and FL11 along the lower-left arm.
Independently, the map prints **"1 FIRST BASE ENTRANCE"** outside the
upper-right arm, **"3 THIRD BASE ENTRANCE"** outside the lower-left arm, and
**"H HOME PLATE ENTRANCE"** directly outboard of Vista sections 316 and 317 —
which fixes the plate block on that ring by name, with no geometry at all.
Nothing outside the image was needed. The MARLINS DUGOUT label is on the
third-base arm and would have mirrored the park; it decided nothing.

**Behind the plate.** FL15 sits dead on the bisector of the two drawn foul
lines, with FL14 and FL16 either side and FL4–FL8 curving around inboard of
them. On the bowl ring the plate falls at **14/15**. On the Vista ring the map
names it: 316/317.

**Which way each line runs.** The bowl is one ring numbered 1 → 33. It starts at
1 and 2 in the right-field corner by the Bullpen Zone and The Social, ascends up
the first-base line past the VISITORS DUGOUT — 3 4 5 … 10 … 13 — to the plate at
14/15, continues down the third-base line past the MARLINS DUGOUT — 16 17 … 26 …
32 — and closes through the outfield 34–40, with the purple Home Run Porch
134–141 above that in left-centre. Each bowl section is drawn twice, as a front
wedge and a back wedge carrying the same number in different product colours;
the numbering is one series, not two.

**Deck levels as printed.** Field level FL1–FL11 and FL14–FL16 — **FL12 and FL13
are not printed anywhere I could find, at any magnification**. Bowl 1–32 plus
outfield 34–40 and Home Run Porch 134–141. Legends level 201–211 on the
first-base side and 219–228 on the third; **212–218 do not exist**, the suite
band S1–S14 and S23–S34 occupying that arc behind the plate, with S37–S42 beyond
219–222. Vista level 302–327, with the plate at 316/317 as labelled.

**Netting.** Drawn, in the diagonal hatch the legend names "Netting located at
front of section" — the only hatched entry in the key. It runs **3 → 26**: from
section 3 on the first-base side, through the plate, to section 26 on the third,
with 1, 2, 27 and everything beyond drawn solid. Its midpoint is 14.5, which is
where the drawn foul lines put the plate.

**Against the table.**

| Zone | Table says | Map says |
|---|---|---|
| `HOME-F` 1–3 | behind plate | **the right-field corner**, at the far end of the first-base line by the Bullpen Zone, ≈13 sections from the plate |
| `1B-FB1` 4–9 | 1B infield | 1B side, correct |
| `1B-DUG` 10–17 | 1B baseline | 10–13 on 1B, 14–15 **behind the plate**, 16–17 on **3B** |
| `3B-FB1` 23–28 | 3B infield | 3B side, correct |
| `3B-DUG` 29–37 | 3B baseline | 29–32 on 3B, correct; **33–37 are not on either foul line** — 34–40 run across the outfield |
| `HOME-B` 203–209 | behind plate, Legends | on the 1B side; the Legends ring has **no** behind-plate block at all, 212–218 being suites |
| `1B-LB1` 210–218 | 1B Legends | 210 and 211 are on 1B and correct; **212–218 do not exist** |
| `3B-LB1` 219–227 | 3B Legends | 3B side, correct |
| `HOME-U` 303–309 | behind plate, Vista | on the 1B side, ≈7 short of the 316/317 the map itself names |
| `1B-UB` 310–320 | 1B Vista | 310–315 on 1B, 316–317 **behind the plate**, 318–320 on **3B** |
| `3B-UB` 321–330 | 3B Vista | 321–327 on 3B, correct; **328–330 do not exist** |

The anchors start at 18 (bowl) and 321 (Vista) on the third-base side for the
same reason American Family's start at 123: 16, 17 and 318–320 are on the
third-base side of the bend and the table calls them first base, but that is a
boundary argument, not a side argument. loanDepot park reports `ok`.

## Rogers Centre — sides correct, plate off ≈13

Flat plan, plate at the bottom, standard orientation. The map draws the diamond
explicitly — home plate as a ringed circle at the bottom apex, first and third
base as white squares either side, second base as a white diamond at the top —
so the projection is not in doubt.

**Landmark that fixed it: the club's own netting page, which this repo already
holds.** Rogers Centre is the one park of the six that did not need the map to
establish its sides. `SIDE_ANCHORS` has carried *"down the first and third
baseline walls to Sections 113C and 130C respectively"* from
mlb.com/bluejays/ballpark/netting since Step 8, at `primary` strength. On the
map, 113 is on the right-hand arm and 130 on the left. The map and the club page
agree, and the map extends the coverage from two sections to twenty-six. The
map's own BLUE JAYS DUGOUT label is on the **third-base** arm and would have
mirrored the park.

**Behind the plate.** 123 and 124 at the 100 level, with 124 the more central —
home plate as drawn sits over the 124 radial, six pixels off its centre at
original scale against twenty-six for 123. 223/224 on the 200 ring, 523/524 on
the 500 ring. The 300 ring has no behind-plate section: the orange
**Ticketmaster Lounge** band occupies that arc between 329 and 335.

**Which way each line runs.** From the plate the numbers *descend* down the
first-base line — 122 121 … 113 … 109 — past the VISITORS' DUGOUT, and *ascend*
down the third-base line — 125 126 … 130 … 140 — past the BLUE JAYS DUGOUT and
the BLUE JAYS BULLPEN. The ring then closes through the outfield: 141–148 across
left field under the WestJet Flight Deck, "The Stop" gap, then 101 102 103 in
right field.

**Deck levels as printed.** Field level carries a separate short series — TD
Lounge 1–5 behind the plate, theScore Bet Baseline Box 16–23 on the first-base
side, Banner Club 24–32 on the third — which is not the 100 ring and is not what
the zone table numbers. 100 level 101–148, one closed ring. 200 level 205–249
with the plate at 223/224. 300 level 300–348 with the Ticketmaster Lounge in
place of a plate block. 400-series small numbers (roughly 432–472) run between
the 300 and 500 rings and the legend does not name that level at all. 500 level
to at least 540, plate at 523/524.

**Netting.** None drawn, and the legend has no netting entry. A light-blue arc
does run along the back edge of 121–127 and at two points by the dugout ends,
but it is on the concourse side of the sections rather than the field side and
carries the accessible-seating icon, so it is a platform edge, not a net.

**Against the table.**

| Zone | Table says | Map says |
|---|---|---|
| `HOME-F` 108–111 | behind plate | on the 1B side, ≈13 sections up the first-base line from 123/124 |
| `1B-FB1` 112–117 | 1B infield | 1B side, correct |
| `1B-DUG` 118–126 | 1B baseline | 118–122 on 1B, 123–124 **behind the plate**, 125–126 on **3B** |
| `3B-FB1` 126–131 | 3B infield | 3B side, correct — but the table claims **126 on both sides at once**, in `1B-DUG` and here |
| `3B-DUG` 132–140 | 3B baseline | 3B side, correct; 140 is the last before the ring turns into left field |
| `HOME-B` 210–217 | behind plate, 200 ring | on the 1B side; the 200 plate block is 223/224 |
| `1B-LB1` 218–226 | 1B 200 ring | 218–222 on 1B, 223–224 behind the plate, 225–226 on **3B** |
| `3B-LB1` 227–237 | 3B 200 ring | 3B side, correct |
| `HOME-U` 510–517 | behind plate, 500 ring | on the 1B side; the 500 plate block is 523/524 |
| `1B-UB` 518–528 | 1B 500 ring | 518–522 on 1B, 523–524 behind the plate, 525–528 on **3B** |
| `3B-UB` 529–538 | 3B 500 ring | 3B side, correct |

The 126 double-claim is worth naming on its own. `_zone_side_for` resolves it by
parity — `1B-DUG` 118–126 has both endpoints even, `3B-FB1` 126–131 does not —
so the check reads 126 as first base and no anchor trips over it. That is the
tie-break doing exactly what it was written for, on a case it was not written
for, and it is why the third-base anchor recorded here starts at 127.

## Kauffman Stadium — scrambled, plate off ≈16

Flat plan, plate at the bottom, outfield at the top, standard orientation.

**Landmark that fixed it — the second weak one.** Like American Family Field,
this map names no field and no base. GEORGE BRETT LOUNGE sits on the left arm
and FRANK WHITE LOUNGE on the right, which is suggestive and is not evidence.
Its only side-bearing labels are HOME DUGOUT against 131–134 and VISITOR DUGOUT
against 119–122, and a dugout label is not a landmark. The orientation rests on
the drawn plan alone.

**Behind the plate.** 126, 127, 128, 129 at the 100 level, with the
CommunityAmerica Crown Club boxes 1–6 inboard of them and the UMB Diamond Club
A–F outboard.

**Which way each line runs.** From the plate the numbers *descend* down the
third-base line — 125 124 … 121 … 114 … 107 106 105 — past the VISITOR DUGOUT
and VISITOR BULLPEN, ending 104 103 102 101 in the Sonic Slam Section at the
left-field corner. They *ascend* down the first-base line — 130 131 … 140 … 148
— past the HOME DUGOUT and HOME BULLPEN. **149 is not printed**; the arm ends
150 151 152 beyond the bullpen, under the Rivals and Blue Moon Taproom decks.

**Deck levels as printed.** 100 level 101–148 and 150–152. Plaza level 201–252,
with **226–229 absent** (the UMB Diamond Club occupies that arc) and **220 and
222 not printed** on the third-base arm, which runs …217 218 219 221 223 224
225. Loge level 301–311 on the third-base side and 312–325 on the first; there
is no behind-plate Loge section, the TRIPLE CROWN SUITES band taking that arc.
View level 401–439, plate at ≈419–421.

**Netting — and this is the find of the step.** The map draws it and labels it.
A heavy black line runs along the field-facing edge of the bowl with
**"PROTECTIVE NETTING"** printed along it in white, twice, once on each arm. At
12x the third-base end resolves cleanly: the line begins at the **107/108
boundary**, at the top corner of section 108. The first-base end terminates at
the top of **148**. So the drawn run is 108 → 148 through the plate at 126–129 —
eighteen sections one side, nineteen the other, which is symmetric and
corroborates the plate block independently of everything above.

That matters beyond this park's sides. `netting.py` records Kauffman Stadium as
`source_gap / club_declines_to_publish` — "club states it will not give section
numbers". The club's own seating map draws the extent with readable endpoints.
This is **not** a published extent and must not be treated as one: it is a line
on a drawing, whose ends I read off pixels, not a sentence a club has committed
to. But the recorded reason for that gap is that the club will not give section
numbers, and a reader of that gap should know this drawing exists. No code
change was made on the strength of it.

**Against the table.**

| Zone | Table says | Map says |
|---|---|---|
| `3B-FB1` 103–109 | 3B infield | 3B side, correct — and the only field-level block in this table that is |
| `HOME-F` 110–113 | behind plate | ≈16 sections up the **third-base** line, past the visitors' end of the infield |
| `1B-FB1` 114–120 | 1B infield | **the third-base line** — 114 through 120 sit between the plate and the visitors' dugout, on the left arm |
| `1B-DUG` 121–131 | 1B baseline | 121–125 on **3B**, 126–129 **behind the plate**, 130–131 on 1B |
| `3B-DUG` 133–143 | 3B baseline | **the first-base line** — the middle of the right arm, past the HOME DUGOUT |
| `HOME-B` 213–220 | behind plate, Loge | on the **3B** side of the Plaza ring; the Plaza has no plate block (226–229 absent) and 220 is not printed |
| `1B-LB1` 221–231 | 1B Loge | 221–225 on **3B**, 230–231 on 1B; 226–229 and 222 not printed |
| `3B-LB1` 232–243 | 3B Loge | **the first-base side** of the Plaza ring |
| `HOME-U` 413–420 | behind plate, upper | **nearly right** — the View ring's plate is ≈419–421 |
| `1B-UB` 421–431 | 1B upper | 1B side, correct |
| `3B-UB` 432–443 | 3B upper | 432–439 are on the **1B** side; 440–443 do not exist |

Kauffman is Comerica Park's problem in a mirror and reaches the same verdict
from the opposite direction. It is not a simple flip: `3B-FB1` (103–109) and
`1B-DUG`'s tail (130–131) land on the right lines while `1B-FB1` (114–120) and
`3B-DUG` (133–143) land on the wrong ones, so swapping the two label ranges
would fix two blocks and break two others. `check_side_anchors` returns
`inconsistent` — 7 anchored sections agreeing, 20 disagreeing.

The 400-ring result is the odd one and worth stating plainly: `HOME-U` 413–420
is very close to right. That is a coincidence of two rings having different
lengths, not evidence that the upper deck was done more carefully.

## Globe Life Field — scrambled, plate off ≈10

Rotated plan drawn in mild perspective, which is why the two drawn foul lines
meet at 117° rather than 90°. Five concentric label rings around the bowl —
HPFS suites, the numbered lower bowl in two rows, the FS/LS/CS/PS prefixed
rings, the mezzanine and the upper deck — at 6–8px each. The densest map read so
far.

**Landmark that fixed it, measured rather than eyeballed.** The legend's **"3rd
Base Box"** swatch is #d6ac01. Searching the map for connected regions within a
tight tolerance of that colour returns exactly five blocks above 400px, all
adjacent, all on the same arm: **sections 8, 9, 10, 11 and 12**. That arm is
therefore the third-base line, stated by the map's own key. Two independent
confirmations: the legend's **"Left Field Deck"** blue (#6ba9db) returns exactly
five blocks, 240–244, across the top of the sheet at the head of that same arm;
and the legend prints **"NETTING · Sections 2-25"**, whose midpoint is 13.5.

**Behind the plate.** Tracing the perpendicular from the drawn home plate, the
backstop apex falls at HPFS 07/08 — those two of the fourteen home-plate field
suites are 447 and 454 px from the plate against 477 and 488 for their
neighbours. Outboard of them the lower bowl reads **13/14** and the mezzanine
**114/115**. The 200 ring's plate block I put at **217–219** and would not swear
to; see the confidence list.

**Which way each line runs.** The lower bowl is one closed ring, 1 → 33. It
starts at 1 near the left-field pole, *descends* toward the plate — 2 3 … 8 9 10
11 12, the 3rd Base Box gold — reaches 13/14 behind the plate, *ascends* up the
first-base line — 15 16 … 25 26 — and closes through the outfield 27–33 back to
1. The mezzanine does the same thing one ring out: 101 at the left-field pole,
plate at 114/115, 133 at the right-field pole, outfield 134–142. So does the
upper deck: 201 near left field round to 244, which is the Left Field Deck, back
adjacent to 201.

**Deck levels as printed.** HPFS 01–14 innermost. Lower bowl 1–33, drawn as two
rows sharing one set of numbers (front rows Lexus Club green, back rows the
product the legend names). FS 101–110, LS 101–122, CS 201–243, PS 101–108, HOF
201b–207b, SB1–SB4 and TT 1–2 in intermediate rings. Mezzanine 101–142. Upper
201–244. Outermost 301–326.

**Netting.** Drawn as a black dotted line around the bowl edge, and the legend
states its extent in words: **"NETTING · Sections 2-25"**. That is the only one
of the twenty-nine maps read in this file to publish a netted section range in
its own key.

**Against the table.**

| Zone | Table says | Map says |
|---|---|---|
| `HOME-F` 1–5 | behind plate | at the **left-field pole**, ≈10 sections up the third-base line |
| `1B-FB1` 6–11 | 1B infield | **the third-base line** — this is the 3rd Base Box the legend names |
| `1B-DUG` 12–19 | 1B baseline | 12 on **3B**, 13–14 **behind the plate**, 15–19 on 1B |
| `3B-FB1` 25–30 | 3B infield | 25–26 are on the **first-base** line; 27–30 are the outfield ring |
| `3B-DUG` 31–37 | 3B baseline | 31–33 are outfield; **34–37 do not exist** |
| `HOME-B` 105–111 | behind plate, mezzanine | on the **3B** side, ≈9 short of 114/115 |
| `1B-LB1` 112–119 | 1B mezzanine | 112–113 on **3B**, 114–115 behind the plate, 116–119 on 1B |
| `3B-LB1` 120–128 | 3B mezzanine | **the first-base side** of the mezzanine ring |
| `HOME-U` 204–211 | behind plate, upper | on the **3B** side of the upper ring |
| `1B-UB` 212–222 | 1B upper | straddles the plate block |
| `3B-UB` 223–233 | 3B upper | **the first-base side** of the upper ring |

`check_side_anchors` returns `inconsistent` — 6 agreeing, 19 disagreeing. Globe
Life Field's recorded gap kind moves with it, from `sides_unverifiable` to
`labels_contradict_model`: it used to fail on the *absence* of a check and now
fails on the check itself. `tests/test_netting.py::STRUCTURAL_GAP_KINDS` records
the change.

## Tropicana Field — scrambled by parity

Flat plan, plate at the bottom, standard orientation.

**Landmark that fixed it, named inside the image, in so many words.** The map
prints **"200 LEVEL — APPROXIMATE 1ST BASE ▼"** along the right-hand arm and
**"200 LEVEL — APPROXIMATE 3RD BASE ▼"** along the left-hand arm, each with an
arrowhead into its own ring. This is the most explicit side statement on any of
the twenty-nine maps: no landmark, no colour, no geometry — the map simply says
which line is which. "LEFT FIELD TERRACE" at the head of the left arm and the
RAYS SCOREBOARD beyond the right arm's far end agree. The RAYS DUGOUT sits on
the first-base arm here, which happens to be the popular assumption and is still
not what decided it.

**Behind the plate.** **101 and 102**, a pair, with 101 fractionally left of the
centre line and 102 fractionally right. Inboard of them the white DEX Imaging
Home Plate Club sections and the orange Home Plate Box bands; outboard, the
lettered AAA BBB CCC DDD EEE FFF GGG and then the Press Box. **There is no
section 100.**

**Which way each line runs — the finding.** Tropicana numbers **one foul line
odd and the other even**, from the 101/102 pair behind the plate:

- third base (left, toward the Left Field Terrace):
  103 105 107 109 111 113 115 117 119 121 123 125 127 129 131, then the outfield
  133 135 137 139 141 143 145 147 149
- first base (right, past the Rays Dugout):
  104 106 108 110 112 114 116 118 120 122 124 126 128 130 132, then the outfield
  134 136 138 140 142 144 146 148 150

The 200 ring does the same thing — 203 205 207 … on the third-base side against
204 206 208 … on the first — and so does the outer suite ring (odd 1–45 left,
even 2–44 right, with one wedge labelled "32/36"). The Baldwin Group Club ring
on the first-base side repeats the even numbers of the sections it sits behind.

**Deck levels as printed.** Field level 101–132 in the bowl plus 133–150 across
the outfield, with a second concentric row on each arm repeating the same
numbers, and the lettered AAA–GGG behind the plate. 200 level 203–224. Suites
1–45 by parity. 300 level: **341 343 345 347 349 351 353 355 only**, the odd
Party Deck strip in left field. There is no 300-level ring around this bowl at
all.

**Netting.** None drawn, and the legend has no netting entry. The orange bands
around the home-plate club are the legend's "Home Plate Box" product.

**Against the table.** Every field-level zone range spans both foul lines:

| Zone | Table says | On the map |
|---|---|---|
| `3B-FB1` 100–103 | 3B infield | **100 does not exist**; 101 is behind the plate, 102 is on 1B, 103 is on 3B |
| `HOME-F` 104–106 | behind plate | 104 and 106 on 1B, 105 on 3B; the plate is 101/102 |
| `1B-FB1` 107–112 | 1B infield | 108, 110, 112 on 1B; 107, 109, 111 on 3B |
| `1B-DUG` 113–118 | 1B baseline | evens on 1B, odds on 3B |
| `3B-DUG` 125–130 | 3B baseline | odds on 3B, evens on 1B |
| `HOME-B`/`1B-LB1`/`3B-LB1` 205–224 | three 200-ring blocks | the ring is parity-split the same way |
| `HOME-U`/`1B-UB`/`3B-UB` 303–322 | three 300-ring blocks | **none of 303–322 exists**; the 300 level is 341–355 odd, in left field |

An offset figure for the plate zone is not worth quoting. The ring is not the
shape the table thinks it is.

Unlike Petco Park, Tropicana has no overlapping club-page wording for
`_overlapping_prefixes` to trip on, so the six single-number anchors recorded
here do decide a verdict: `inconsistent`, 3 agreeing and 3 disagreeing. They are
single numbers for the same reason Petco's are — a range spanning both parities
would be a claim about sections on the other line.

## What changed in code

`seat_map.SIDE_ANCHORS` gains entries for five parks and grows at a sixth:

| Park | Anchors added | Verdict before | Verdict after |
|---|---|---|---|
| `american_family` | 101–114 and 201–216 → 1B, 123–131 and 223–236 → 3B | `untestable` | **`ok`** |
| `loan_depot` | 1–13 and 302–313 → 1B, 18–32 and 321–327 → 3B | `untestable` | **`ok`** |
| `rogers_centre` | 109–121 → 1B, 127–140 → 3B (added to two `primary` anchors) | `ok` (2 sections) | `ok` (26 sections) |
| `kauffman_stadium` | 101–122 → 3B, 133–148 → 1B | `untestable` | **`inconsistent`** |
| `globe_life` | 2–11 and 105–113 → 3B, 17–26 and 117–128 → 1B | `untestable` | **`inconsistent`** |
| `tropicana_field` | 111, 117, 127 → 3B; 112, 116, 128 → 1B (single numbers) | `untestable` | **`inconsistent`** |

Every anchor range is restricted to numbers the map actually prints, and every
one stops clear of its park's plate bend. That is why American Family's
third-base anchor starts at 123 rather than 119, why loanDepot's starts at 18
rather than 16, why Kauffman's third-base anchor stops at 122 and its first-base
anchor at 148 rather than 152, and why Tropicana's are single numbers.

Downstream:

- `tests/test_site.py::test_only_thirteen_parks_may_name_a_foul_line` becomes
  `..._fifteen_...`. American Family Field and loanDepot park join the list;
  none left it. The index page's count moves from 13 to 15 of 31 on its own —
  the number is computed, not written down.
- `tests/test_netting.py::STRUCTURAL_GAP_KINDS` records `globe_life` at
  `labels_contradict_model` instead of `sides_unverifiable`, with a comment
  saying why.
- No park changed `join_park` status. The netting-gap count stays at 24.
- Across all 31 parks the side check now reads: 15 `ok`, 9 `inconsistent`, 4
  `flipped`, 3 `untestable`. The untestable three are Citi Field, Las Vegas
  Ballpark and Petco Park. Petco is untestable by the overlap guard, by design.
  Las Vegas Ballpark has no map in `seating_maps/` at all. Citi Field does —
  `citi_field.png` is the one file in that folder that no step has read yet, and
  it is the obvious next one.
- `site_data.MAP_READS` still carries the five Step 11 parks only. The
  twenty-four parks read in Steps 12–15 are not yet written up for the site.

## What I am least confident about, after Step 15

1. **American Family Field and Kauffman Stadium rest on the plan convention
   alone, and that is a real step down from the other four.** Neither map names
   a field, a base or a side anywhere on the sheet — I looked, at magnification,
   across the outfield band, both corners and the whole legend. What fixes them
   is that a plan view drawn with home plate at the bottom and the outfield at
   the top puts first base on the right, which is a fact about the projection
   rather than about the image. I believe it: both maps draw the diamond, both
   are the clubs' own sheets, and a mirrored publication would be an
   extraordinary error. But the other four parks in this step are anchored on
   something the image *says* — a legend that names a side, a printed "1ST
   BASE", a club page — and these two are not. If either turns out to be
   mirrored, both of that park's anchors flip together and Kauffman's
   `inconsistent` becomes a different kind of wrong. This is the single largest
   exposure in this step. The dugout labels do not help: this very step found
   two parks whose home dugout is on the third-base side.
2. **Globe Life Field's plate block as a number, and its 200-ring plate
   especially.** That `HOME-F` (1–5) is out at the left-field pole is not in
   doubt — 1 through 5 are drawn past the 3rd Base Box gold, at the far end of
   the arm. But *where* the plate is I put at 13/14 by tracing the perpendicular
   through a map drawn in perspective, with the drawn foul lines meeting at
   117°, and that tracing had a section of slack in it: the strict ray lands on
   13 and the backstop apex sits between HPFS 07 and 08. The legend's "Sections
   2-25" gives a midpoint of 13.5 and is what I would actually stand on. The
   200-ring plate at 217–219 is weaker again — I got it by following a radial
   out through two rings that are not concentric with each other, and I would
   not defend any single number in that range. The side verdict does not depend
   on it.
3. **"220 and 222 are not printed" at Kauffman.** I read the Plaza ring's
   third-base arm as …217 218 219 221 223 224 225, with wedges where 220 and 222
   would be but no labels on them. It is possible those wedges are double-width
   sections whose second number the map omits, or that the labels are there and
   I lost them to JPEG artefacts at 5x. The claim that 226–229 are absent I am
   confident about — the UMB Diamond Club visibly occupies that arc and is drawn
   as a single named block. The 220/222 claim is the weaker half of the same
   sentence.
4. **loanDepot's FL12 and FL13.** The legend names FL1–FL3 and FL9–FL11 by side,
   and I resolved FL4–FL8 and FL14–FL16 on the sheet. FL12 and FL13 I could not
   find at 8x anywhere around the plate or on either arm. They are probably
   drawn and unlabelled, or under a graphic. Nothing depends on them; it is
   recorded because "I could not find it" and "it is not there" are different
   claims and this file keeps them apart.
5. **Kauffman's drawn netting is a drawing.** I have read its ends off pixels at
   12x and I am confident about the third-base end at the 107/108 boundary,
   because the black line starts at a corner rather than fading. The first-base
   end at the top of 148 I am slightly less sure of, because the line there runs
   into the white gap before 150 at a shallower angle. Neither end is a published
   extent, and no code change was made from either. What I would not want a later
   reader to take from that section is that Kauffman's netting gap is closed. It
   is not. What has changed is that the recorded reason for it — "the club
   declines to publish section numbers" — now sits next to a club drawing that
   has section numbers on both sides of the net.
6. **The two-row rings.** Four of these six maps (American Family's Loge and
   Club rings, loanDepot's bowl, Globe Life's lower bowl and Tropicana's field
   level, plus Rogers' 300/400 bands) draw some rings as two concentric rows
   carrying the same section number in different product colours. I have read
   those as one numbering split by row, because the two rows sit on the same
   radials and the numbers line up. If any of them is instead two genuinely
   different series that happen to share numbers, the deck-level ranges I quote
   for that park would be describing two things at once. The side readings do
   not depend on it — both rows are on the same arm either way.

# Step 16 — the last map (2026-09-07)

## What was left

The folder was listed and cross-referenced against this file before anything
was read. `seating_maps/` holds **30 files**. Twenty-nine of them are written up
above: five in Step 11, six each in Steps 12, 13, 14 and 15. Exactly **one** had
never been read:

| Park | File | Pixels | Type | Legibility |
|---|---|---|---|---|
| Citi Field | `citi_field.png` | 1500x1520 | flat plan, palette PNG | excellent |

So this step reads one map, not six. Step 15's own closing notes already
predicted this — "`citi_field.png` is the one file in that folder that no step
has read yet, and it is the obvious next one". The two parks that remain
`untestable` after this step are Las Vegas Ballpark, which has no map in the
folder at all, and Petco Park, which is untestable by the overlap guard by
design. Neither is fixable by reading a file that is not there.

**Nothing in `stadium.py` was changed.** The code changes are six entries in
`seat_map.SIDE_ANCHORS` and the named-sides list, count and name of one test in
`tests/test_site.py`.

## Summary of Step 16

| Park | Sides | Plate zone | Severity |
|---|---|---|---|
| **Citi Field** | **correct** — on all three of the rings its table numbers | **field level ≈0** — `HOME-F` 115–120 is centred on the plate; Excelsior off ≈2 toward 3B; Promenade off ≈5 toward 3B | Mild |

This is the mildest verdict any park has drawn. It is also the only park in the
thirty whose behind-plate block at field level is already in the right place.

### Which convention it uses

Monotone from pole to pole with the plate mid-range, with the low numbers at
the **right-field (first-base) pole** — the same shape as American Family
Field, loanDepot park, Rogers Centre, Target Field and T-Mobile Park, and the
shape that produces correct side blocks. Every one of the five numbered rings
does it:

| Ring | Runs | Plate lands at |
|---|---|---|
| 100 (field) | 101 at the RF pole → 131 at the LF pole, then 132–143 close the loop through the outfield | boundary **117/118** |
| 200 | 201 (1B arm) → 239 (3B arm) | **222** |
| 300 (Excelsior) | 306 (1B arm) → 333, then 334–339 into the left-field bank; 301–305 drawn detached out in right field | **319** |
| 400 | 401 (1B arm) → 431, then 432–437 into the left-field bank | **414/415** |
| 500 (Promenade) | 501 (1B arm) → 532, then 533–538 into the left-field bank | **514** |

Note the loop. Citi Field is one of the few parks in the thirty whose field
level closes all the way round: 101 sits at the right-field foul-pole corner,
the numbers climb anticlockwise past the plate to 131 at the left-field corner,
carry on through left field as 132–139, and come back through right-centre as
140–143 to meet 101 again. The upper rings do not close — they stop dead at
401/501 on the first-base side and run on to 437/538 in left field, which is
why the drawn bowl is lopsided.

## Citi Field — `citi_field.png`

Flat plan, home plate at the bottom, outfield at the top. Excellent legibility:
every number below was resolved at 3x–8x, and the plate rings at 6x are sharp
enough to read the cell boundaries, not just the labels.

### The landmark problem, and how it was settled

**This map names no base and no field side anywhere on the sheet.** Every piece
of text on it was magnified and read. In full, they are: `TASTE OF THE CITY`,
`SCOREBOARD`, `BULLPEN`, `CADILLAC CLUB AT PAYSON'S`, `CAESARS SPORTSBOOK AT
THE METROPOLITAN MARKET`, `EMPIRE CLUB`, `HOME`, `VISITORS`, `PIAZZA 31 CLUB`,
`HUDSON WHISKEY NY CLUB`. There is no legend, no level names, no netting key
and no "1st Base" / "Left Field" heading of the kind Comerica, Angel Stadium,
Target Field, loanDepot and Tropicana supplied. On the face of it this is
American Family Field and Kauffman Stadium again — orientation resting on the
plan convention alone, which Step 15 called its single largest exposure.

It is not, quite, because this park's outfield is asymmetric and the asymmetry
is published. **The drawn field was measured rather than eyeballed.** Home
plate was located at the convergence of the two drawn foul lines, at
(754, 887); the two lines leave it at 48.9° and 44.3° from vertical, so the
centre-field axis is tilted 3.4° to the left of straight up and every angle
below is taken from that axis, not from the image's vertical. The playing
surface was flood-filled from its own two fill colours, its holes closed, and
rays cast out from the plate:

| Off the CF axis | 0° | 20° | 25° | 30° | 45° |
|---|---|---|---|---|---|
| Drawn left | 527 | 459 | 452 | 465 | 420 |
| Drawn right | 527 | **517** | **487** | **484** | **442** |

The drawn right side is deeper than the drawn left at every angle from 20°
out. Citi Field's published dimensions are LF 335, LCF 358, CF 408, RCF 398,
RF 330 — right-centre is 40 ft deeper than left-centre. Scaling dead centre
(527 px) to 408 ft gives 0.774 ft/px, and then:

- drawn left at 30° = **360 ft** against a published left-centre of **358**
- drawn right at 20° = **400 ft** against a published right-centre of **398**

Under the mirror hypothesis those same two readings would have to be 398 and
358, and each misses by about 40 ft. That is not proof — I chose the scale from
centre field, and the angles at which a club paints its alley markers are not
published — but it is a two-sided quantitative fit that the mirror fails, and
it is a great deal better than the plan convention on its own.

Two weaker things agree with it:

- **`BULLPEN`** is printed inside the image, in the grey wedge beyond the wall
  between section 143 and the field, on the right-hand side of centre. Citi
  Field's two bullpens are stacked in right-centre. It is the only bullpen
  drawn on the sheet.
- **`HOME`** is printed against the right-hand dugout and `VISITORS` against
  the left. The Mets' dugout is on the first-base line, so this agrees — but
  Step 15 found two parks whose home dugout is on the third-base side, and this
  file does not let a dugout label carry an orientation. It is recorded, not
  used.

One label does **not** obviously agree, and it is recorded rather than
explained away. See "What I am least confident about" below.

### Behind home plate

Six concentric products sit behind the plate. Innermost first, reading the
drawn arc left to right (3B side to 1B side):

- **Lettered club ring** (blue): `H G F E D C B A`. The plate ray passes at the
  **D/C** boundary; the ring is not quite symmetric because B and A are drawn
  wider than the rest.
- **Bare gold ring**: `19 18 17 16 15 14 13 12 11`. The plate ray passes
  through **15**, which is the middle section of the nine. Clean and symmetric.
- **Bare grey ring**: `10 9 8 7 6A 6 5 5A 4 3 2 1`. The plate ray passes at the
  **6/5** boundary. The four central cells — 6A, 6, 5, 5A — are drawn much
  deeper than the rest of the ring, and reach back to the same radius as the
  100-series sections beside them.
- **100 ring** (navy at this end): `… 120 119 118` on the left and
  `117 116 115 …` on the right, with the deep 6A/6/5/5A block filling the arc
  between them. **No 100-series section is directly behind the plate.** 118 and
  117 are the innermost pair, and the boundary between them is where the plate
  ray falls.
- **200 ring**: the plate ray passes through **222**, which sits dead centre —
  225/219, 224/220 and 223/221 are symmetric pairs about it.
- **300 ring**: the plate ray passes through **319**, in its left half.
  The `PIAZZA 31 CLUB` strip runs along the outside of 318–322.

Further out, the 400 ring's plate falls at the **414/415** boundary and the 500
ring's inside **514**, with the `HUDSON WHISKEY NY CLUB` strip under 514/515.

**A corroboration from outside the map.** `SOURCED_DATA.md` carries a
secondary, unverified compilation for Citi Field netting: sections 107–128,
with the net proper 111–124. Both ranges are exactly symmetric about **117.5**
— 107→117.5 is 10.5 sections and 117.5→128 is 10.5; 111→117.5 is 6.5 and
117.5→124 is 6.5. That is the boundary this map puts the plate on, arrived at
by an unrelated route. It says nothing about which side is which, and it does
not close the netting gap: `join_park` still returns `source_gap /
no_primary_source` for this park, because the Mets publish nothing.

### Lower bowl, pole to pole

Reading the 100 ring anticlockwise from the right-field foul pole:

- **101 102 103 104** (pink) sit past the foul-pole corner, facing the
  outfield. The `CADILLAC CLUB AT PAYSON'S` strip runs in front of 101–102.
- **105** sits on the corner itself, where the drawn wall makes its V.
- **106 107 108 109 110** (green) run down the first-base line. 108 is a narrow
  wedge squeezed between 107 and 109.
- **111 112 113 114** (yellow), the first-base infield, with a second thin
  orange row carrying the same four numbers between them and the `HOME` dugout.
- **115 116 117** (navy) into the backstop bend. **[plate]** **118 119 120**
  (navy) out of it.
- **121 122 123 124** (yellow), the third-base infield, with the same doubled
  thin orange row against the `VISITORS` dugout.
- **125 126 127 128 129 130 131** (green) up the third-base line; 127, like
  108, is a narrow wedge.
- **132 133** at the left-field foul-pole corner, then **134–139** (pink)
  across left field, the batter's eye and the Home Run Apple, then **140 141
  142 143** (teal) in right-centre above the bullpen, closing the loop at 101.

Both foul-line arms therefore run **toward** the plate in increasing numbers
from their own pole. There is no outward-from-the-plate block anywhere on this
map.

### Netting drawn on the map

**None.** No net line, no hatch, no shaded band, no legend entry. Checked at 6x
along the whole backstop arc and at 3x down both foul lines. This is the same
answer as most of the thirty; Kauffman is still the only map in the folder that
draws one.

### Deck levels and number ranges

| Level | Printed range | Count | Named by the table? |
|---|---|---|---|
| Lettered club ring | A–H | 8 | no |
| Gold field ring | 11–19 | 9 | no |
| Grey field ring | 1–10, plus 5A and 6A | 12 | no |
| 100 (field) | 101–143, a closed loop | 43 | 104–132 only |
| 200 | 201–239 | 39 | **no** |
| 300 (Excelsior) | 301–339; 301–305 detached in right field | 39 | 309–329 only |
| 400 | 401–437 | 37 | **no** |
| 500 (Promenade) | 501–538 | 38 | 506–531 only |

The map prints **225** section labels. `_make_citi_field_sections()` names
**76** of them across three rings and is silent about the 200 ring, the 400
ring and all three premium field rings. The level names in the table —
"Excelsior", "Promenade" — are Citi Field's real ones, but they do not come
from this map: it prints no level names at all.

### Against the zone table

`_make_citi_field_sections()` carries eleven zones. Set against the map:

| Zone | Table's label range | Table's side | Where the map puts it | Verdict |
|---|---|---|---|---|
| `1B-DUG` | 104–110 | 1B | right-hand arm (104 on the pole corner, 105–110 down the line) | **correct** |
| `1B-FB1` | 111–114 | 1B | right-hand arm, infield | **correct** |
| `HOME-F` | 115–120 | HOME | straddles the plate, 115–117 on the 1B side and 118–120 on the 3B side | **correct, and centred** |
| `3B-FB1` | 121–125 | 3B | left-hand arm, infield | **correct** |
| `3B-DUG` | 126–132 | 3B | left-hand arm up to the pole corner | **correct** |
| `1B-LB1` | 309–316 | 1B | right-hand arm | **correct** |
| `HOME-B` | 317–325 | HOME | plate is at 319; the block's midpoint is 321 | **off ≈2 toward 3B** |
| `3B-LB1` | 326–329 | 3B | left-hand arm | **correct** |
| `1B-UB` | 506–514 | 1B | right-hand arm; 514 is the plate section itself | **correct** |
| `HOME-U` | 515–523 | HOME | plate is at 514; the block's midpoint is 519, and every one of its nine sections is on the 3B side of the plate | **off ≈5 toward 3B** |
| `3B-UB` | 524–531 | 3B | left-hand arm | **correct** |

So: **sides correct** everywhere, and a plate block that is exact at the field
level, two sections out one ring up and five out two rings up. The drift is all
in the same direction, toward third base. The rings are not concentric with
each other at this park — the 400 ring's own centre of symmetry sits about
25 px to the right of the 200 and 300 rings' — so a table that divides each
ring into three equal-ish arcs will drift the same way on every ring it does
not measure.

`HOME-U` is the one worth naming. The table calls 515–523 the behind-plate
Promenade block, and all nine of those sections are up the third-base line.

## What changed in code

`seat_map.SIDE_ANCHORS` gains a `citi_field` entry with six anchors:

| Anchors added | Verdict before | Verdict after |
|---|---|---|
| 106–114, 306–316 and 506–513 → 1B; 121–130, 322–332 and 518–530 → 3B | `untestable` | **`ok`** (46 agreeing, 0 disagreeing, 16 unmatched) |

Every range is restricted to numbers the map prints and stops clear of its
ring's plate bend — which is why the first-base anchors stop at 114, 316 and
513 and the third-base ones start at 121, 322 and 518, and why 101–105 are left
out at the field level (101–104 are past the foul-pole corner and 105 is on
it).

Downstream:

- `tests/test_site.py::test_only_fifteen_parks_may_name_a_foul_line` becomes
  `..._sixteen_...`. Citi Field joins the list; none left it. The index page's
  count moves from 15 to 16 of 31 on its own — the number is computed.
- No park changed `join_park` status. Citi Field stays `source_gap /
  no_primary_source`; the netting-gap count stays at 24.
- Across all 31 parks the side check now reads: **16 `ok`, 9 `inconsistent`, 4
  `flipped`, 2 `untestable`**. The two untestable are Las Vegas Ballpark (no
  map in the folder) and Petco Park (untestable by the overlap guard, by
  design). Every map in `seating_maps/` has now been read.
- `site_data.MAP_READS` still carries the five Step 11 parks only. The
  twenty-five parks read in Steps 12–16 are not yet written up for the site.

## What I am least confident about, after Step 16

1. **The orientation still has no label behind it.** The dimension fit above is
   the best evidence in this step and I believe it, but it is a fit, not a
   printed word: I picked the scale from centre field, and where a club paints
   its 358 and 398 markers is not something the map or the club publishes as an
   angle. What makes me willing to sign it is that the mirror fails on both
   sides at once and by about 40 ft each — a mirrored sheet would have to make
   the shallow alley the deep one. If it is wrong anyway, all six anchors flip
   together and Citi Field goes straight from `ok` to `flipped`. This is the
   largest exposure in the step, and it is the same exposure American Family
   Field and Kauffman Stadium carry, only partly retired.
2. **`SCOREBOARD`, and I could not resolve it.** The map floats two grey
   label boxes above the top of the bowl, stacked: `TASTE OF THE CITY` and,
   under it, `SCOREBOARD`. The lower box spans x 684–968, and the centre-field
   axis at that height is at x≈714 — so it covers the axis and leans right, and
   would read as right-centre if it is meant geographically. I could not settle
   where Citi Field's main videoboard actually is well enough to say whether
   that agrees with my orientation or contradicts it, and the two boxes are
   drawn outside the seating footprint and attached to no section, which is how
   a legend behaves rather than how a map feature does. **I have therefore used
   it in neither direction.** It is the one thing on this sheet I looked at and
   could not turn into evidence, and a later reader should know I saw it rather
   than discover it themselves.
3. **"No 100-series section is directly behind the plate."** This rests on
   reading 6A, 6, 5 and 5A as unusually deep cells of the bare grey ring rather
   than as members of the 100 ring drawn without their hundreds digit. At 6x
   the cell boundaries favour the first reading — 7, 8, 9, 10 and 1, 2, 3, 4
   are visibly shallower cells with 118/119/120 and 117/116/115 behind them,
   while 6A through 5A run the full depth with nothing behind them — but I
   would not call it beyond argument. Nothing depends on it: both readings put
   the plate on the 117/118 boundary, and that is what the anchors and the
   `HOME-F` verdict use.
4. **The Promenade plate at 514, and so the "off ≈5".** I took the plate normal
   as the bisector of the two drawn foul lines, which is tilted 3.4° from the
   image's vertical. On the 500 ring, 3° of angle is most of a section wide. A
   plain vertical from the plate lands on the 514/515 boundary instead of
   inside 514, so the offset could as easily be ≈4 as ≈5. The direction —
   `HOME-U` sitting entirely up the third-base line — does not depend on which
   of those two it is.
5. **The 400 ring's plate at 414/415 is the weakest number in the section.**
   That ring's own centre of symmetry sits about 25 px right of the 200 and 300
   rings', so it is not concentric with them, and a single number for it is
   traced through two rings that disagree about where the middle is. No anchor
   and no verdict uses it; it is quoted because the ring exists and the table
   ignores it.
6. **Section 105.** I read it as sitting on the foul-pole corner itself, where
   the drawn wall makes its V, rather than cleanly on the first-base line or
   cleanly in the outfield. That is why the first-base field-level anchor
   starts at 106. If 105 is really on the line, the anchor is one section
   shorter than it could be, which costs nothing; if it were really in the
   outfield and I had included it, that would have been a false anchor. The
   conservative direction was the cheap one.
7. **The doubled orange rows at 111–114 and 121–124.** Each of those eight
   numbers is printed twice, once on a thin strip against the dugout and once
   on the wide block behind it, in different fills. I have read that as one
   numbering split across two rows, the same call Step 15 made for four other
   parks, because the two rows sit on the same radials and the numbers line up.
   If they are instead two different series sharing numbers, the field-level
   count of 43 is wrong. The side reading is not affected — both rows are on
   the same arm either way.

---

# Step 17 — the thirty reads, written up for the public site

Steps 12 to 16 each closed by noting that `site_data.MAP_READS` still carried
the five Step 11 parks only. Those three sentences (lines 2327, 2903 and 3228)
were true when written and are left in place as the record of each step's
state; **this section supersedes them.** `MAP_READS` now carries all thirty.

No map was re-read and nothing above was revised. This step is transcription:
each park's read, restated positionally for a page that may not print a section
number, plus the site-wide counts that moved as a result.

## What went into `MAP_READS`

Thirty entries, one per map in `seating_maps/`, covering thirty of the 31
parks. Las Vegas Ballpark has no map in the folder and falls through to
`NO_MAP_READ`, which now says it is the only park that does.

Two fields were added to the entry shape, because the five-park version could
not express what the thirty contain:

- **`read_on`** — the five Step 11 parks were read on 2026-08-11 and the other
  twenty-five on 2026-09-07. The page used to print one hard-coded date for
  every read.
- **`outcome`** — `'agrees'` at Daikin Park, Yankee Stadium and Dodger Stadium,
  `'disagrees'` at the other twenty-seven. The page rendered every finding in
  the same red box and led with "It disagrees with this model in the following
  ways", which would have printed three agreements as failures. Agreements now
  render green and lead with what they settle. `tests/test_site.py::
  test_the_three_agreeing_maps_are_not_dressed_as_failures` holds both ends.

Every finding is stated by position and deck. The constraint bit hardest here
of anywhere on the site, because a map finding is *about* section numbers: no
entry names a label, quotes a range, or prints a digit that could be read as
one. Counts are spelled out, and "positions" always means printed seat labels
counted along the bowl.

## Counts that moved on the site

| Statement | Was | Now |
|---|---|---|
| Maps read | five | **thirty** |
| Maps disagreeing | five of five | **twenty-seven of thirty** |
| Parks that may name a foul line | six on the built page | **sixteen** |
| Parks folding both foul lines into one row | twenty-five on the built page | **fifteen** |
| Netting sourced and joinable | ten on the built page | **seven** |
| Netting gaps | twenty-one on the built page | **twenty-four** |

The right-hand column is what the committed `site/` now serves. The middle
column is what it served before this step, and the gap is larger than this
step's own work: **`site/` had not been rebuilt since Step 11.** Every code
change from Steps 12 to 16 — the twenty-five new side anchors, the three joins
those anchors rejected, the ten parks that gained a foul-line name — was
committed but never rendered. Rebuilding was half of what this step changed on
the public pages, and it is worth separating from the copy.

## The count that had gone stale in three places

"Twenty-two of the 31 parks" — the number that cannot name a foul line — was
written out in prose in `site_data.MODEL_LIMITS`, in the side-asymmetric
netting hedge in `site_build.netting_section`, and in two module docstrings. It
moved five times between Step 11 and Step 16 and none of the four followed it.

It is now computed once, by `site_build.side_counts()`, the same way
`netting_counts()` already computed the netting figures and for the same
reason. `test_the_fleet_wide_side_count_is_computed_not_written_out` asserts
the rendered number against the built parks on all 31 pages, so a future step
that moves it again cannot leave one page behind.

## What this step did not do

- **No map was re-read**, and no reading above was revised or softened.
- **Nothing in `stadium.py` changed.** Twenty-seven zone tables disagree with
  their club's own drawing and all twenty-seven are still wrong in exactly the
  way this file records. Every park page says so, and says the figures below it
  are attached to the areas the model currently names.
- **No netting gap was closed.** Kauffman's drawn netting is described on its
  page as a line on a drawing rather than a published extent, in the same terms
  Step 15 recorded it.
