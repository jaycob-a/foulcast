"""
Stadium Geometry Layer.

Models MLB stadium seating bowls as seat sections with heights, distances and
angles, and maps 3D trajectory landing positions onto them.

MODULE PROVENANCE — READ BEFORE TRUSTING ANY PER-SECTION NUMBER
================================================================

**The seat geometry in this file is estimated. None of it is surveyed, and
none of it is digitized from a published seating chart.** This applies to all
31 parks equally. Every `SeatSection` carries six numbers — `distance_min`,
`distance_max`, `angle_min`, `angle_max`, `height_min`, `height_max` — and the
*shape* of every park is still one shared template, not a measurement.

What changed in Step 9, and what did not
----------------------------------------

The template's distance bands are now **positioned per park by three published
parameters**: foul-territory area, backstop distance and deck overhang. See
the "Sourced per-park physical parameters" block below and `PARK_PARAMS.md`
for the citation behind every figure. That makes the parks differ from each
other for a sourced reason instead of by accident:

- 31 parks now resolve to **31 distinct geometry signatures**, up from 27.
  Busch/Kauffman/Nationals/Rate and Great American/Petco are no longer
  byte-identical to each other.
- Distance values are drawn from **418 distinct numbers**, up from a
  fleet-wide pool of 62 shared values covering all six parameters. (Angles
  still come from 15 shared values and heights from 19 — see below.)
- `backstop_distance` is sourced at **30 of 31 parks** (Clem), where it was
  previously a default 55 at 21 of them. It is also no longer inert: it sets
  the radial scale of the behind-plate bands, and it now anchors them
  absolutely — the front row behind the plate sits one seat-setback behind the
  backstop fence at every park, where the template had it 2.7 to 23.0 ft *in
  front* of the fence (median 6.8 ft).
- The published deck-overhang percentages are applied **uncapped where the
  cover is a deck or a grandstand canopy, and discarded where it is a dome or
  a retractable roof** 150+ ft overhead, which a foul pop flies under rather
  than into. That classification is a judgment call, not a source; it is
  recorded and argued per park in the `PARK_PARAMS` entries below. It
  replaces a flat 0.60 cap that split the difference and was wrong in both
  directions.

**Angles and heights are unchanged, deliberately.** No source publishes a
foul-territory split by side, a behind-plate-vs-down-the-line split, or any
deck elevation in feet, so nothing here invents one. Every park therefore
remains exactly mirror-symmetric, and the angular vocabulary is still shared:
`HOME-F` spans `angle 55-90` in all 31 parks, `1B-UB`/`3B-UB` span `10-45` in
29 of 31, `1B-DUG` spans `0-25` in 30 of 31. Real bowls are neither.

So the parks now differ in *depth* on sourced grounds, and still do not differ
in *shape* at all. Park-to-park differences in output remain partly an
artefact of how coarse each park's section table is.

`SOURCED_DATA.md` records the search that established the underlying gap: no
public source publishes distance-from-home-plate or angle-off-the-foul-line
for any stadium section. Team sites, ticket resellers and seat-review sites
describe seating positionally and give row/seat numbering, but never survey
coordinates. Closing this properly needs a different class of source — a
stadium survey, a CAD/GIS drawing, or Statcast's park geometry files.

What *is* real in this file, and can be relied on:

- Outfield wall distances (`lf_distance`, `cf_distance`, `rf_distance`) and
  `altitude_ft` on the `Stadium` factories. These are published figures.
- Section *names* and deck levels, which track real seating charts.
- `backstop_distance` at 30 parks, and the per-park scale factors derived
  from `PARK_PARAMS`. Las Vegas Ballpark is the sole park with no published
  parameter of any kind; Sutter Health Park has a backstop but no foul area,
  so its bands are unscaled. Both are labelled at their factories.
- The behind-plate bowl front, which is now the backstop distance plus a 1 ft
  seat setback rather than a template value — at the 30 parks where the
  backstop is sourced, that one number is a measurement, and the setback is a
  documented floor over it. Las Vegas is anchored too, but
  against its unsourced default of 52 ft; it is the one place in this file
  where an unsourced number moves geometry, and it is done because a bowl
  standing in front of its own backstop is wrong whether or not anyone has
  measured the backstop.

Two consequences of the anchor worth stating, because they look like
regressions and are not:

- More fouls now match no section. Pushing the behind-plate bowl back off the
  plate opens a real annulus of foul ground between the plate and the front
  row, and short backward fouls that die in it correctly match nothing
  instead of being caught by seats that cannot exist there. The model has no
  screen or backstop-net surface to hand them to, so they are simply lost.
- Wrigley's upper deck now owns no exposed ground at all, because Clem's
  100% is applied in full. That is the intended reading of a grandstand
  wholly under a roof, but it means the model has nowhere to put a ball that
  hits that roof and comes back down.

The landing-section geometry helpers below (`exposed_bands`,
`find_landing_section`) are sound; they are correct machinery operating on
estimated inputs.
"""
import math

import numpy as np
from dataclasses import dataclass, field


@dataclass
class SeatSection:
    """A section of stadium seating."""
    name: str
    section_id: str
    side: str              # '1B', '3B', 'HOME', 'LF', 'RF'
    level: str             # 'field', 'lower', 'upper', 'bleachers'

    # Boundaries in stadium coordinates (feet from home plate)
    distance_min: float    # closest point to home plate
    distance_max: float    # farthest point from home plate
    angle_min: float       # degrees from foul line (0 = foul line, 90 = behind plate)
    angle_max: float

    # Vertical
    height_min: float      # bottom of section (feet above field)
    height_max: float      # top of section

    # Metadata
    num_seats: int = 200
    avg_ticket_price: float = 0.0


@dataclass
class Stadium:
    """Full stadium geometry model."""
    name: str
    city: str
    team: str
    altitude_ft: float = 0
    avg_temperature_f: float = 72

    # Field dimensions
    lf_distance: float = 330    # left field wall distance
    cf_distance: float = 400    # center field
    rf_distance: float = 330    # right field
    backstop_distance: float = 60  # home plate to backstop

    sections: list[SeatSection] = field(default_factory=list)

    # Section matching: matchup_engine.py calls find_landing_section() below,
    # which intersects the trajectory with the exposed deck surfaces.


# ============================================================
# Landing-section geometry
# ============================================================

def _deck_mid_height(sec: SeatSection) -> float:
    """Sort key height for a deck. NaN-height sections (distance-only
    matching) sort in front of everything so they claim their band."""
    if np.isnan(sec.height_min) or np.isnan(sec.height_max):
        return -1.0
    return 0.5 * (sec.height_min + sec.height_max)


def _surface_heights(sec: SeatSection, dists: np.ndarray) -> np.ndarray:
    """Height of a section's sloped deck surface at each horizontal distance.

    The deck rises linearly from (distance_min, height_min) to
    (distance_max, height_max). NaN-height sections match at any height,
    modeled as an infinitely tall surface.
    """
    if np.isnan(sec.height_min) or np.isnan(sec.height_max):
        return np.full_like(dists, np.inf, dtype=float)
    span = sec.distance_max - sec.distance_min
    if span <= 0:
        return np.full_like(dists, 0.5 * (sec.height_min + sec.height_max), dtype=float)
    frac = np.clip((dists - sec.distance_min) / span, 0.0, 1.0)
    return sec.height_min + frac * (sec.height_max - sec.height_min)


def exposed_bands(
    sections: list[SeatSection], angle: float,
) -> list[tuple[SeatSection, float, float]]:
    """Partition the distance axis into non-overlapping exposed deck bands.

    Candidates are the sections whose angle range contains the ball's
    spray angle; balls behind the plate (angle > 90) belong to the
    sections that reach the backstop (angle_max >= 90).

    Section footprints overlap heavily in the raw data. Where they do,
    the lowest deck owns the ground: a ball cannot come straight down
    onto an upper deck at a horizontal position where a lower deck sits
    beneath it. Each section keeps only the parts of its distance range
    not claimed by a lower deck, so the result is a true partition.

    Returns (section, start, end) bands sorted by start, non-overlapping.
    """
    def _contains(s: SeatSection) -> bool:
        return (s.angle_min <= angle <= s.angle_max) \
            or (angle > 90 and s.angle_max >= 90)

    candidates = [s for s in sections if _contains(s)]

    # The bowl wraps around the foul corner continuously, but raw zone data
    # can leave angular gaps within a deck level (e.g. main level ends at 45
    # degrees while behind-plate main starts at 55). A ball in the gap still
    # comes down on that deck level, so admit the angularly nearest section
    # of each uncovered level, within a modest tolerance.
    ANGLE_GAP_TOLERANCE = 15.0
    covered_levels = {s.level for s in candidates}
    fillers: dict[str, tuple[float, str, SeatSection]] = {}
    for s in sections:
        if s.level in covered_levels:
            continue
        gap = s.angle_min - angle if angle < s.angle_min else angle - s.angle_max
        if gap <= ANGLE_GAP_TOLERANCE:
            cur = fillers.get(s.level)
            if cur is None or (gap, s.section_id) < (cur[0], cur[1]):
                fillers[s.level] = (gap, s.section_id, s)
    candidates.extend(s for _, _, s in fillers.values())

    candidates.sort(key=lambda s: (_deck_mid_height(s), s.distance_min, s.section_id))
    if not candidates:
        return []

    # The lowest deck is the front of the bowl: no stands exist nearer to the
    # plate than where it begins. Elevated decks whose raw distance ranges
    # start in front of it (data noise) are clipped back to the bowl front,
    # otherwise upper decks claim balls that come down over foul ground.
    bowl_front = float(candidates[0].distance_min)

    bands: list[tuple[SeatSection, float, float]] = []
    for sec in candidates:
        gaps = [(max(float(sec.distance_min), bowl_front), float(sec.distance_max))]
        for _, b0, b1 in bands:
            remaining = []
            for g0, g1 in gaps:
                if b1 <= g0 or b0 >= g1:
                    remaining.append((g0, g1))
                    continue
                if g0 < b0:
                    remaining.append((g0, b0))
                if b1 < g1:
                    remaining.append((b1, g1))
            gaps = remaining
        for g0, g1 in gaps:
            if g1 - g0 > 1e-9:
                bands.append((sec, g0, g1))

    bands.sort(key=lambda b: b[1])
    return bands


def find_landing_section(
    sections: list[SeatSection],
    angle: float,
    horiz_dists: np.ndarray,
    heights: np.ndarray,
) -> SeatSection | None:
    """Assign a foul ball to the section its trajectory actually comes down in.

    Walks the trajectory from its apex to find the contact point: the first
    moment the ball is at or below the exposed deck surface at its horizontal
    position. Mid-flight altitude never matches a section — only where the
    ball comes down counts. The contact point is then assigned to the nearest
    exposed deck surface, so a ball that dives under a deck facade belongs to
    the section in front of it, not the deck overhead.

    Returns None if the ball never reaches any stands surface.
    """
    bands = exposed_bands(sections, angle)
    if not bands:
        return None

    apex = int(np.argmax(heights))
    d = horiz_dists[apex:]
    z = heights[apex:]

    contact_idx = None
    for sec, b0, b1 in bands:
        in_band = (d >= b0) & (d <= b1)
        if not in_band.any():
            continue
        hit = in_band & (z <= _surface_heights(sec, d))
        if hit.any():
            first = int(np.argmax(hit))
            if contact_idx is None or first < contact_idx:
                contact_idx = first
    if contact_idx is None:
        return None

    cd = float(d[contact_idx])
    cz = float(z[contact_idx])
    best = None
    best_dist = np.inf
    for sec, b0, b1 in bands:
        nd = min(max(cd, b0), b1)
        if np.isnan(sec.height_min) or np.isnan(sec.height_max):
            nz = cz  # distance-only section: no vertical component
        else:
            nz = float(_surface_heights(sec, np.array([nd]))[0])
        dist = float(np.hypot(cd - nd, cz - nz))
        if dist < best_dist:
            best = sec
            best_dist = dist
    return best


# ============================================================
# Sourced per-park physical parameters
# ============================================================
#
# Every *figure* in this block comes from `PARK_PARAMS.md` (research date
# 2026-08-09), which carries its citation. None of them is derived,
# interpolated or estimated by this file; where a source publishes nothing,
# the field is None.
#
# Two things in this block are not figures and are not sourced, and both are
# called out where they appear:
#
#   - `upper_cover`, which decides whether a park's published upper-deck
#     overhang is treated as an obstruction at all. Clem publishes the
#     percentage and never says what casts it. See `UpperCover` below.
#   - The backstop anchor at Las Vegas Ballpark, the one park with no
#     published backstop. It is anchored anyway, against the factory's
#     unsourced 52 ft, because the anchor encodes a physical constraint rather
#     than a park-to-park difference. See `las_vegas_ballpark()`.
#
# Three published parameters are available per park:
#
#   foul_area_sqft   Whole-park foul territory, square feet. Effectively
#                    single-sourced: Clem's estimate off his own scale
#                    diagrams, cross-checked against Lowry's *Green
#                    Cathedrals* via Seamheads. Good to roughly +/-1,000 sq
#                    ft, not the +/-100 the figures imply. See PARK_PARAMS.md
#                    "Foul territory area is effectively single-sourced".
#
#   backstop_ft      Home plate to the fence behind it. **Clem only**, by
#                    deliberate choice: his figures are the only set that is
#                    internally consistent across all 31 parks and that
#                    documents renovations (Kauffman 1999, Fenway) the club
#                    and Wikipedia figures miss. Sources genuinely disagree
#                    here — at 12 parks, by up to 14 ft — and the disagreement
#                    is definitional (Clem measures to the rear fence,
#                    Seamheads to the stands, clubs define nothing). Mixing
#                    sources per park would mean mixing reference points, so
#                    no park takes a non-Clem value even where two other
#                    sources outvote him. See PARK_PARAMS.md Part 2.
#                    Where Clem's park page is newer than his master table
#                    and they differ, the page wins (Fenway, Angel, Target);
#                    for the four parks whose page predates the table
#                    (Tropicana, Oracle, T-Mobile, loanDepot) the table wins,
#                    and there they agree anyway.
#
#   lower/upper_overhang
#                    Percentage of that deck covered by a roof or the deck
#                    above, from the 2016-10-18 Wayback snapshot of Clem's
#                    master table — he has since removed the columns. Clem's
#                    legend: "only the main portion of the grandstand
#                    situated relatively close to the infield is counted",
#                    which is exactly the region this model cares about.
#                    2016 vintage: renovations since are not reflected.
#
# How they are used (`_apply_sourced_params` below):
#
#   1. Radial scale. Foul-territory area scales as the square of a linear
#      dimension, so the linear scale is sqrt(area / reference). Behind the
#      plate the depth of foul ground is set by the backstop instead, so that
#      band scales on backstop / reference. Each section is scaled by a blend
#      of the two, weighted by its own mid-angle, which keeps the bowl front
#      continuous as it sweeps from the foul line round to the backstop.
#
#   2. Backstop anchor. The backstop is the near boundary of the behind-plate
#      seating: no seat behind the plate can sit closer to home than the fence
#      in front of it. The behind-plate group is therefore *translated* so its
#      front row lands one seat-setback behind the backstop distance — Clem's
#      figure measures to the fence, and seats stand behind a fence, not in it
#      (see `_SEAT_SETBACK_FT`). The shift tapers to nothing down the foul line
#      so the bowl front stays continuous through the corner. This is an
#      absolute anchor, not a scale — it is what makes `backstop_ft` a position
#      rather than only a ratio, and it is applied at all 31 parks including
#      the two the scale step skips.
#
#   3. Overhang. A deck that is covered cannot receive a ball coming straight
#      down, so each deck's rear extent is pulled in by the covered fraction
#      of the depth it actually owns, decks resolved front to back so that
#      "the depth it owns" means its physical footprint. The two directions
#      differ in effect and that is correct: pulling in the *lower* deck hands
#      its rear to the upper deck, which is what a cantilevered upper deck
#      physically does; pulling in the *upper* deck leaves the space unowned,
#      because at most parks nothing sits above it. Whether the published
#      percentage counts as cover at all depends on what is casting it — see
#      `UpperCover` below.
#
# What is NOT done here, because no source supports it:
#   - No angles are changed. No source publishes foul territory split 1B/3B
#     or behind-plate vs down-the-line (PARK_PARAMS.md gaps 3 and 4), so
#     every park stays mirror-symmetric and keeps the template's angles.
#   - No heights are changed. Deck elevations in feet are unpublished for
#     every park by every source (PARK_PARAMS.md gap 12).
#   - Row counts are not converted into deck heights; that needs a riser
#     dimension nobody publishes.


# What is casting the shade Clem's upper-deck overhang percentage measures.
#
# NOT SOURCED. Clem publishes one percentage per deck and never says what is
# over those seats, so this classification is a judgment call — the largest one
# in this block, and it is recorded per park at each `ParkParams` entry below.
# It exists because the percentage alone cannot answer the only question the
# model needs answered: would a foul pop arriving from above be stopped before
# it reached the seats?
#
#   'deck'          The deck above, at grandstand height. Blocks.
#   'canopy'        A grandstand roof sitting directly over those seats, tens
#                   of feet up. Blocks.
#   'stadium_roof'  A dome or retractable roof 150+ ft overhead. Does NOT
#                   block: a foul pop flies under it. Clem is measuring shade,
#                   and shade from that height is not an obstruction.
#
# The rule used, so the classification is not per-park taste: it follows
# Clem's own "decks near the infield" column (PARK_PARAMS.md Part 3). Every
# park he labels "split upper" is 'deck'; every park he labels "(roof)" or
# "(dome)" is 'stadium_roof'; the rest are 'canopy'. Chase Field is the one
# documented exception — Clem labels it plainly "3", but it is a
# retractable-roof park and its 75% behaves like the other five, so it is
# classified 'stadium_roof'.
#
# Two empirical checks that the split is not circular:
#   - The six 'stadium_roof' upper figures are 100/100/100/100/93/75, the top
#     of the fleet distribution — consistent with whole-bowl shade.
#   - Those same parks' *lower* figures are 5/25/25/30/30/30, squarely inside
#     the 10-55 band the open-air parks occupy. So the lower-deck percentage is
#     measuring the deck above even at the domed parks, which is why lower
#     overhang is applied everywhere and never needs this classification.
UpperCover = str    # 'deck' | 'canopy' | 'stadium_roof'

_UPPER_COVER_BLOCKS: dict[UpperCover, bool] = {
    'deck': True,
    'canopy': True,
    'stadium_roof': False,
}


@dataclass(frozen=True)
class ParkParams:
    """Published physical parameters for one park. None means unpublished."""
    foul_area_sqft: float | None
    backstop_ft: float | None
    lower_overhang: float | None    # percent of the lower deck under cover
    upper_overhang: float | None    # percent of the upper deck under cover
    upper_cover: UpperCover | None = None   # what casts it; None if no figure
    note: str = ''


# Reference park for the radial scale: the fleet median, so the shared
# template stands for the median park and the scale factors are centred on
# 1.0 rather than on an arbitrary park.
#   22,900 sq ft is the median of the 29 sourced foul areas (Kauffman).
#   52 ft is the median of the 30 sourced Clem backstops.
_REF_FOUL_AREA_SQFT = 22_900.0
_REF_BACKSTOP_FT = 52.0

# There is no ceiling on the overhang fraction a deck may lose. The flat
# 0.60 cap this replaces existed only to stop the six roofed parks' 93-100%
# from deleting their upper decks outright; classifying the cover (above)
# removes those six from the calculation entirely, so the cap has nothing left
# to protect and its cost — understating Wrigley's genuine 100% canopy — is
# gone with it. A blocking cover of 100% now does what it says: that deck owns
# no exposed ground.


PARK_PARAMS: dict[str, ParkParams] = {
    # foul area / backstop / lower overhang / upper overhang / upper cover
    'yankee_stadium': ParkParams(19_700, 52, 20, 55, 'deck'),
    # Clem table, page and Seamheads all agree on both figures.
    # Cover: split upper deck, 7+14 rows. The 55% is the rear portion sitting
    # over the front portion — grandstand height, blocks.
    'fenway_park': ParkParams(18_100, 52, 40, 60, 'canopy'),
    # Smallest foul territory in MLB. Backstop 52 is Clem's park page
    # (2026-07-17), which supersedes his master table's 54; Wikipedia's 60 is
    # the pre-shortening figure and is not used.
    # Cover: the 1934 grandstand roof over the upper rows, the lowest roof
    # line in MLB and the one balls demonstrably clatter off. Blocks.
    'dodger_stadium': ParkParams(19_300, 53, 15, 30, 'canopy'),
    # 19,300 is the current era; Clem records 33,500 for 1969-99, "the
    # squeezing of the once-vast foul territory yields far fewer pop foul
    # outs". Backstop 53 over Seamheads 57 / Wikipedia 55.
    # Cover: the wavy canopy over the top deck. Not a split deck — Clem's
    # three-column schema cannot represent Dodger's four levels (PARK_PARAMS.md
    # Part 3 note †), so 'canopy' is the residual call, not a positive reading.
    'wrigley_field': ParkParams(16_500, 55, 55, 100, 'canopy'),
    # 16,500 is Clem's park page and Seamheads; his master table's 18.6 is
    # pre-2016, before ~2,000 sq ft of seats went in. Smallest in MLB.
    # Cover: THE canopy case. 100% is the 1922 upper-deck grandstand roof, a
    # low structure directly over the seats, not a stadium roof. Applied in
    # full, which leaves Wrigley's upper deck owning no exposed ground — the
    # intended reading, and the reason the old flat cap was removed.
    'coors_field': ParkParams(24_900, 50, 20, 35, 'deck'),
    # Backstop 50 (Clem + Seamheads) over Wikipedia's 56.
    # Cover: split upper deck, 9+16 rows.
    'chase_field': ParkParams(25_500, 55, 30, 75, 'stadium_roof'),
    # Overhang figures are Clem's parenthesised "variable profile" values.
    # Cover: retractable roof, ~170 ft over the field. This is the one park
    # that breaks the "follow Clem's decks column" rule — he labels it plainly
    # "3", not "(roof)" — but the physical fact is the same as the other five
    # and 75% of the upper deck is not shaded by anything at seat height.
    # It is also the weakest of the six calls: 75% overlaps the range the
    # split-upper parks occupy, so this one is decided by the roof, not the
    # number.
    'truist_park': ParkParams(22_300, 53, None, None),
    # Backstop is Clem's own estimate, "(53)". Opened 2017, after the 2016
    # overhang snapshot, so no overhang figures exist for it. No figure, so no
    # cover classification: nothing to classify.
    'camden_yards': ParkParams(23_600, 54, 25, 45, 'canopy'),
    # Foul territory unaffected by the 2022 left-field expansion.
    # Cover: single 25-row upper deck with a roof canopy over its rear.
    'citizens_bank': ParkParams(24_500, 50, 15, 35, 'deck'),
    # Cover: split upper deck, 16+8 rows.
    'great_american': ParkParams(23_600, 50, 30, 30, 'canopy'),
    # Backstop 50 (Clem) over Seamheads 51 / Wikipedia 55.
    # Cover: single 28-row upper deck; Clem marks the 30% "^", his notation
    # for a bare frame roof extension — a structure at grandstand height.
    'progressive_field': ParkParams(21_900, 60, 20, 55, 'canopy'),
    # Backstop 60 (Clem + Wikipedia) over Seamheads 65. Joint-longest in MLB.
    # Cover: single 27-row upper deck, 55% "^" — same bare-frame roof notation.
    'comerica_park': ParkParams(26_500, 55, 25, 30, 'canopy'),
    # Largest open-air foul territory in MLB. Backstop 55 (Clem) over
    # Seamheads 52.
    # Cover: two decks plus a token mezzanine; the 30% over the 26-row upper
    # deck is its roof canopy, there being no deck above it.
    'minute_maid': ParkParams(21_000, 49, 30, 100, 'stadium_roof'),
    # Daikin Park. Cover: retractable roof, Clem's own "3 (roof)". The 100% is
    # whole-bowl shade from ~240 ft up and does not obstruct a foul pop.
    'kauffman_stadium': ParkParams(22_900, 45, 25, 40, 'canopy'),
    # Backstop 45, not Wikipedia's 60: Clem documents the 1999 box seats that
    # cut it "from 60 feet to about 50", and his table now carries 45 with
    # Seamheads agreeing. The Wikipedia infobox is 27 years stale.
    # This park is the fleet-median foul area, i.e. the reference.
    # Cover: single (40)-row upper deck under its own roof canopy.
    'angel_stadium': ParkParams(21_500, 56, 35, 45, 'canopy'),
    # Backstop 56 is Clem's park page (2026-08-06) for the 1999- era; his
    # master table's 59, Seamheads' 60 and Wikipedia's 60.5 are all rejected
    # under the single-source rule. Widest four-way disagreement in the file.
    # Cover: single 24-row upper deck, roof canopy above it.
    'citi_field': ParkParams(20_700, 46, 20, 30, 'deck'),
    # Cover: split upper deck, 17+6 rows.
    'oakland_coliseum': ParkParams(None, 58, None, None,
        note='Sutter Health Park: foul area and overhang UNSOURCED'),
    # Clem has a park page but leaves the fair/foul cells blank, as does
    # Seamheads; only "a very constricted foul territory" qualitatively. No
    # overhang either (2-deck park with no upper deck at all, opened to MLB
    # after the 2016 snapshot), so no cover to classify. Radial scaling is
    # skipped for want of a foul area, but the backstop IS sourced — Clem's
    # "(58)", an estimate, with Seamheads and Wikipedia both at 58 — so the
    # backstop anchor does apply here.
    'las_vegas_ballpark': ParkParams(None, None, None, None,
        note='Las Vegas Ballpark: ENTIRELY UNSOURCED — no park parameter '
             'published by any source'),
    # Not in Clem's registry (he covers MLB venues), not in Seamheads, and
    # Wikipedia gives no foul area, backstop or deck detail. No scaling and no
    # overhang. The backstop anchor still applies, because it enforces a
    # physical constraint rather than a sourced difference — but it does so
    # against this park's unsourced default of 52 ft, which is the one place
    # in this file where an unsourced number now moves geometry. Flagged in
    # PARK_PARAMS.md and in the factory below.
    'pnc_park': ParkParams(22_200, 51, 30, 30, 'canopy'),
    # Cover: two decks plus a token 2-row mezzanine; the 30% over the 30-row
    # upper deck is its own roof, nothing sits above it.
    'petco_park': ParkParams(23_900, 45, 40, 30, 'deck'),
    # Backstop 45 corroborated in Clem's prose: "the backstop is only 45 feet
    # from home plate, so most fans are close to the action".
    # Cover: split upper deck, 21+6 rows. Clem also marks it "^", but the
    # split deck is the nearer structure either way — both block.
    'oracle_park': ParkParams(25_500, 54, 20, 30, 'canopy'),
    # Clem's page predates his master table here, so the table's 54 stands;
    # Wikipedia's 48 is rejected under the single-source rule.
    # Cover: single 25-row upper deck with a roof canopy.
    'tmobile_park': ParkParams(24_300, 56, 30, 55, 'canopy'),
    # The worst conflict in the file: Clem 56, Seamheads 55, and the
    # Mariners' own published 69 carried by Wikipedia. The 13-14 ft gap is
    # almost certainly two different reference points (rear wall vs front of
    # the seating bowl). Clem's 56 is taken because it is the reference point
    # every other park in this table uses, not because it is more likely
    # right. Foul area 24,300 is the master table (the page predates it).
    # Cover: the borderline call of the 31. T-Mobile has a retractable roof,
    # but it is a parking roof — when open it sits over the railway outside
    # the stadium and covers nothing, and the model has no roof-state input,
    # so it would be classified 'stadium_roof' only under a closed roof. Clem
    # labels the park "3", not "(roof)", and 55% is mid-range rather than the
    # 93-100% the genuinely roof-shaded parks show. Classified 'canopy' —
    # taking the 55% as the upper deck's own roof structure — but this is the
    # call most likely to be wrong.
    'busch_stadium': ParkParams(25_200, 52, 20, 60, 'deck'),
    # Foul area: Clem table and page (25.2) over Seamheads (25.4).
    # Cover: split upper deck, 9+11 rows.
    'tropicana_field': ParkParams(25_300, 50, 25, 100, 'stadium_roof'),
    # Seamheads' latest row is 2024 — the Rays did not play here in 2025.
    # Cover: the fixed dome, Clem's own "3 (dome)". 100% shade from a canopy
    # ~225 ft up that a foul pop passes well beneath.
    'globe_life': ParkParams(23_100, 42, None, None),
    # Shortest backstop in MLB, all sources agreeing. Opened 2020, after the
    # 2016 overhang snapshot, so no overhang figures exist for it — and so no
    # cover classification, even though it is a retractable-roof park and
    # would obviously be 'stadium_roof' if a figure existed.
    'rogers_centre': ParkParams(30_500, 54, 5, 100, 'stadium_roof'),
    # Largest foul territory in MLB; 30,500 is Clem's park page (2026-07-24),
    # superseding his master table's 29.0. Backstop 54 (Clem) over
    # Wikipedia's 60. Cover: the retractable dome, Clem's own "3 (dome)",
    # 282 ft at its peak. Note the 5% lower-deck figure, the smallest in the
    # fleet — the dome is plainly not what that column is measuring.
    'target_field': ParkParams(20_700, 45, 35, 75, 'deck'),
    # Foul area: Clem table and page (20.7) over Seamheads (20.4). Backstop
    # 45 is Clem's park page, which flags it "(Backstop distance is
    # estimated.)"; his master table and Seamheads both say 48.
    # Cover: split upper deck, 14+7 rows. Its 75% equals Chase Field's, and
    # the two are classified oppositely — the reason is the structure, not the
    # number.
    'guaranteed_rate': ParkParams(25_000, 60, 15, 70, 'canopy'),
    # Rate Field. Joint-longest backstop in MLB, all sources agreeing. Note
    # the 2002 renovation replaced the netted-roof backstop with a "roofless"
    # one that lets fouls drop into the seats behind the plate — not modelled
    # here, and it pushes the same way as the long backstop.
    # Cover: the 2004 renovation cut eight rows off the upper deck and put a
    # roof canopy over what remained. That canopy is the 70%. Blocks.
    'loan_depot': ParkParams(21_000, 50, 25, 100, 'stadium_roof'),
    # Foul area 21,000 is the master table plus Seamheads; Clem's page
    # (2023-05-24) predates the table. Backstop 50 is Clem over Seamheads and
    # Wikipedia, which both say 47. Cover: retractable roof, Clem's "3 (roof)".
    'american_family': ParkParams(21_100, 56, 30, 93, 'stadium_roof'),
    # Cover: the fan-shaped retractable roof, Clem's "3 (roof)". 93% rather
    # than 100% because the roof's pivot leaves a wedge open; either way it is
    # ~200 ft up and not an obstruction at seat height.
    'nationals_park': ParkParams(22_800, 45, 10, 55, 'deck'),
    # Foul area 22,800 is Clem's park page (2026-07-15), superseding his
    # master table's 23.1. Cover: split upper deck, 9+13 rows.
}


def _behind_plate_weight(sec: SeatSection) -> float:
    """How behind-the-plate a section is: 0 down the foul line, 1 square back.

    Taken from the section's mid-angle, in the engine's convention where 0 is
    the foul line and 90 is square to the plate. Both backstop-driven
    adjustments — the radial blend and the anchor — use this same weight, so
    they taper through the foul corner in step with each other.
    """
    mid = 0.5 * (sec.angle_min + sec.angle_max)
    return min(max(mid / 90.0, 0.0), 1.0)


def _blend_scale(sec: SeatSection, area_scale: float, backstop_scale: float) -> float:
    """Radial scale for one section, blended by where it sits around the bowl.

    Foul-ground depth down the line is set by foul-territory area; behind the
    plate it is set by the backstop. A section's mid-angle says which regime
    it is in (0 = down the foul line, 90 = square behind the plate), and the
    linear blend keeps the bowl front continuous through the corner instead
    of stepping at whatever angle the two groups happen to meet.
    """
    w = _behind_plate_weight(sec)
    return (1.0 - w) * area_scale + w * backstop_scale


# Clearance between the backstop fence and the first row of seats behind it.
#
# NOT SOURCED, and it is a floor rather than an estimate. The direction is not
# in doubt: Clem defines his figure as "the distance from home plate to the
# fence in the rear" (PARK_PARAMS.md Part 2), so seats sit *behind* that
# number, never on it. The magnitude is not recoverable from anything
# published.
#
# The one handle the sources offer is that Seamheads defines its backstop
# differently — "Distance from Home Plate to Stands" — so at the 30 parks
# where both publish, Seamheads minus Clem measures fence-to-stands directly.
# It does not behave like a real offset:
#
#   - 21 of the 30 agree to the foot, i.e. give no gap at all.
#   - The mean difference is +0.40 ft and the median is 0.
#   - The nine disagreements run both ways (Comerica and loanDepot are -3),
#     which is source conflict, not a definitional step.
#
# So the gap is smaller than the resolution either source publishes at. One
# foot is the smallest increment they could have expressed, and it rounds the
# observed +0.40 ft mean up rather than down, erring toward the direction the
# physical constraint requires. It is deliberately too small to matter: it
# moves each park's total by well under a tenth of a foul per game, which is
# the honest scale of the correction, not a hedge. If a survey ever puts real
# seats behind real fences, this is the constant to replace, and PARK_PARAMS.md
# gap 7 is where the argument lives.
_SEAT_SETBACK_FT = 1.0


def _anchor_to_backstop(sections: list[SeatSection], backstop_ft: float) -> float:
    """Translate the bowl so the behind-plate front row sits behind the backstop.

    A backstop is the near wall of the behind-plate seating: no seat back there
    can be closer to home than the fence in front of it. The template ignores
    that — it puts `HOME-F` at 45-50 ft at every park regardless — so the
    backstop only ever acted as a ratio. This pins it as a position.

    The front row lands at `backstop_ft + _SEAT_SETBACK_FT`, not on
    `backstop_ft` itself. Clem's figure is the distance to the *fence*, and
    seats stand behind a fence rather than in it; see the constant above for
    why the clearance is 1 ft and why that number is a floor.

    Three properties, all deliberate:

    - It **translates, it does not compress.** Pushing the front row back does
      not make the deck shallower, so `distance_max` moves with
      `distance_min` and every deck keeps its depth.
    - It is applied to the *bowl front as `exposed_bands` defines it* — the
      lowest deck reaching behind the plate — not to the smallest
      `distance_min` in the group. Elevated behind-plate decks whose raw
      ranges start in front of the lowest deck are already clipped back to it
      when bands are resolved, so anchoring on them would under-push the row
      that actually faces the plate.
    - The shift **tapers down the foul line**, by the same behind-plate weight
      the radial blend uses, scaled so the behind-plate group gets it in full.
      Down-the-line front rows are set by foul-ground width, not the backstop;
      the taper is there to keep the bowl front continuous round the corner,
      not to claim the backstop reaches the dugout boxes.

    Membership of the behind-plate group is `angle_max >= 90`, the same test
    `exposed_bands` applies to a ball behind the plate, so a section that never
    receives one is never anchored as though it did. That puts Yankee
    Stadium's `HOME-U` (angle 20-55, the fleet-convention outlier the park
    sweep flags) on the taper rather than in the group, which is right for the
    angles it carries whether or not those angles are.

    Returns the signed shift applied to the behind-plate group, in feet.
    """
    behind = [s for s in sections if s.angle_max >= 90]
    if not behind:
        return 0.0

    # Same ordering exposed_bands() uses to pick its bowl front.
    front_sec = min(behind, key=lambda s: (_deck_mid_height(s), s.distance_min,
                                           s.section_id))
    delta = backstop_ft + _SEAT_SETBACK_FT - front_sec.distance_min
    w_ref = _behind_plate_weight(front_sec)
    if w_ref <= 0:
        return 0.0

    for s in sections:
        share = 1.0 if s.angle_max >= 90 \
            else min(_behind_plate_weight(s) / w_ref, 1.0)
        shift = share * delta
        # Defensive only: every park's delta is positive (the template's
        # behind-plate front is short of the backstop everywhere, by 2.7 ft at
        # Yankee to 23.0 ft at Dodger), so nothing is pulled toward home
        # in practice. The floor keeps a hypothetical negative delta from
        # putting seats on top of the plate.
        s.distance_min = max(1.0, s.distance_min + shift)
        s.distance_max = max(s.distance_min + 1.0, s.distance_max + shift)

    return delta


def _mean_exposed_depth(sections: list[SeatSection], sec: SeatSection,
                        angle_step: float = 2.0) -> float:
    """Mean radial depth this section actually owns, over its own angle span.

    The raw rectangles overlap heavily, so a section's `distance_max` minus
    `distance_min` is not what it owns — `exposed_bands` resolves that, and
    this measures the result. Sampling the section's own angle range mirrors
    what the engine searches: same-side sections plus the shared behind-plate
    group. Angles where the section owns nothing (it is entirely hidden
    behind a lower deck there) are excluded rather than averaged in as zero.
    """
    if sec.side in ('1B', '3B'):
        pool = [s for s in sections if s.side in (sec.side, 'HOME')]
    else:
        # Behind-plate sections are shared; either side gives the same answer
        # because every park in this file is mirror-symmetric.
        pool = [s for s in sections if s.side in ('1B', 'HOME')]

    depths = []
    angle = sec.angle_min + angle_step / 2.0
    while angle < sec.angle_max:
        owned = sum(b1 - b0 for s, b0, b1 in exposed_bands(pool, angle)
                    if s.section_id == sec.section_id)
        if owned > 0:
            depths.append(owned)
        angle += angle_step
    return sum(depths) / len(depths) if depths else 0.0


# Adjusted (distance_min, distance_max) per section, per park. The template
# geometry is a constant, so the adjustment is too; the factories rebuild
# sections on every call and this keeps that cheap.
_SOURCED_BAND_CACHE: dict[str, dict[str, tuple[float, float]]] = {}


def _sourced_bands(park_key: str, sections: list[SeatSection], p: ParkParams,
                   backstop_ft: float) -> dict[str, tuple[float, float]]:
    """Distance bands for one park after the sourced parameters are applied.

    `backstop_ft` is the stadium's own `backstop_distance`, which equals
    `p.backstop_ft` wherever that is published; the anchor uses it rather than
    `p` so that it still runs at the one park with no published figure.
    """
    cached = _SOURCED_BAND_CACHE.get(park_key)
    if cached is not None:
        return cached

    # 1) Radial scale. Needs both published parameters; skipped at the two
    #    parks missing a foul area, which keep the template's proportions.
    if p.foul_area_sqft is not None and p.backstop_ft is not None:
        area_scale = math.sqrt(p.foul_area_sqft / _REF_FOUL_AREA_SQFT)
        backstop_scale = p.backstop_ft / _REF_BACKSTOP_FT
        for s in sections:
            k = _blend_scale(s, area_scale, backstop_scale)
            s.distance_min *= k
            s.distance_max *= k

    # 2) Backstop anchor. Runs at every park.
    _anchor_to_backstop(sections, backstop_ft)

    # 3) Overhang.
    #
    #    Lower-deck cover is always the deck above and always blocks. Upper-deck
    #    cover is applied only where `upper_cover` says something at grandstand
    #    height is casting it; at the six roofed parks the published percentage
    #    is whole-bowl shade from 150+ ft up and is discarded entirely.
    #
    #    Decks are resolved **front to back, in the order `exposed_bands` walks
    #    them**, and each deck's depth is measured against the bowl as the
    #    decks in front of it have already left it. That ordering is not a
    #    detail — it is what makes the percentage mean what Clem says it means.
    #    A deck's *physical* footprint runs from where the deck in front stops
    #    being exposed to its own rear, which is only known after the deck in
    #    front has been pulled in. Measuring every deck against the un-overhung
    #    bowl instead (as this step used to) credits an upper deck with the
    #    wrong span, and the error is worst exactly where the cover is
    #    heaviest: at 100% the deck would keep whatever the lower deck's
    #    retreat handed it, so a fully roofed deck stayed reachable. With the
    #    walk in order, 100% means what it says and the deck owns nothing.
    pct_for_level = {'lower': p.lower_overhang, 'upper': p.upper_overhang}
    if p.upper_cover is not None and not _UPPER_COVER_BLOCKS[p.upper_cover]:
        pct_for_level['upper'] = None

    front_to_back = sorted(sections, key=lambda s: (_deck_mid_height(s),
                                                    s.distance_min,
                                                    s.section_id))
    for s in front_to_back:
        pct = pct_for_level.get(s.level)
        if pct is None:
            continue
        frac = pct / 100.0
        pulled = s.distance_max - frac * _mean_exposed_depth(sections, s)
        s.distance_max = max(pulled, s.distance_min + 1.0)

    bands = {s.section_id: (s.distance_min, s.distance_max) for s in sections}
    _SOURCED_BAND_CACHE[park_key] = bands
    return bands


def _apply_sourced_params(stadium: Stadium, park_key: str) -> None:
    """Write the sourced parameters for `park_key` into a built stadium.

    Called at the end of every factory. Each of the three steps runs only
    where its input exists, so a park with no published foul area still gets
    the backstop anchor, and a park with no overhang figure still gets both of
    the others. The point of this layer is to move numbers that have a source
    behind them, not to invent differences for parks nobody has measured — the
    one exception being the anchor at Las Vegas Ballpark, which enforces a
    physical constraint against an unsourced backstop because a bowl in front
    of its own backstop is wrong whether or not anyone has measured it.
    """
    p = PARK_PARAMS[park_key]

    if p.backstop_ft is not None:
        assert stadium.backstop_distance == p.backstop_ft, (
            f'{park_key}: factory says backstop {stadium.backstop_distance}, '
            f'PARK_PARAMS says {p.backstop_ft}'
        )

    bands = _sourced_bands(park_key, stadium.sections, p,
                           stadium.backstop_distance)
    for s in stadium.sections:
        s.distance_min, s.distance_max = bands[s.section_id]


# ============================================================
# Stadium Definitions (estimated geometry — see MODULE PROVENANCE)
# ============================================================

def _make_yankee_stadium_sections() -> list[SeatSection]:
    """Section analogue for Yankee Stadium (opened 2009).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.

    The most detailed table in the file at 16 sections, but detail is not
    provenance: the Grandstand and Lower Reserve bands are estimates like
    everything else. The 1B-UB angle_max note below is an internal
    consistency fix, not a measurement.
    """
    sections = []

    # === FIELD LEVEL ===
    # 1B Dugout area (Sec 109-114)
    sections.append(SeatSection(
        name='1B Dugout Box (Sec 109-114)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=150, avg_ticket_price=350,
    ))
    # 1B Field MVP (Sec 115-118)
    sections.append(SeatSection(
        name='1B Field MVP (Sec 115-118)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=60, distance_max=120,
        angle_min=25, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=400,
    ))
    # Behind Plate Field (Sec 119-121)
    sections.append(SeatSection(
        name='Behind Plate Field (Sec 119-121)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=50, distance_max=90,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=200, avg_ticket_price=500,
    ))
    # 3B Field MVP (Sec 122-125)
    sections.append(SeatSection(
        name='3B Field MVP (Sec 122-125)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=60, distance_max=120,
        angle_min=25, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=400,
    ))
    # 3B Dugout area (Sec 126-131)
    sections.append(SeatSection(
        name='3B Dugout Box (Sec 126-131)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=150, avg_ticket_price=350,
    ))

    # === MAIN LEVEL (200s) ===
    # Behind Plate Lower / Main 200s (Sec 218-222)
    sections.append(SeatSection(
        name='Behind Plate Main (Sec 218-222)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=60, distance_max=120,
        angle_min=55, angle_max=90,
        height_min=15, height_max=40,
        num_seats=350, avg_ticket_price=200,
    ))
    # 1B Main Level (Sec 211-217)
    sections.append(SeatSection(
        name='1B Main Level (Sec 211-217)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=30, distance_max=180,
        angle_min=15, angle_max=45,
        height_min=10, height_max=35,
        num_seats=500, avg_ticket_price=150,
    ))
    # 3B Main Level (Sec 223-228)
    sections.append(SeatSection(
        name='3B Main Level (Sec 223-228)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=30, distance_max=180,
        angle_min=15, angle_max=45,
        height_min=10, height_max=35,
        num_seats=500, avg_ticket_price=150,
    ))
    # 1B Lower Reserve (Sec 205-210)
    sections.append(SeatSection(
        name='1B Lower Reserve (Sec 205-210)', section_id='1B-LR',
        side='1B', level='lower',
        distance_min=180, distance_max=280,
        angle_min=5, angle_max=35,
        height_min=12, height_max=40,
        num_seats=800, avg_ticket_price=80,
    ))
    # 3B Lower Reserve (Sec 229-234)
    sections.append(SeatSection(
        name='3B Lower Reserve (Sec 229-234)', section_id='3B-LR',
        side='3B', level='lower',
        distance_min=180, distance_max=280,
        angle_min=5, angle_max=35,
        height_min=12, height_max=40,
        num_seats=800, avg_ticket_price=80,
    ))

    # === TERRACE / UPPER (300s) ===
    # Behind Plate Terrace (Sec 317-323)
    sections.append(SeatSection(
        name='Behind Plate Terrace (Sec 317-323)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=20, angle_max=55,
        height_min=35, height_max=70,
        num_seats=500, avg_ticket_price=75,
    ))
    # 1B Upper (Sec 307-316)
    # angle_max is 45, not the 55 this entry originally carried. 28 of 31 parks
    # use 10-45 for *-UB, and the extra 10 degrees put an upper deck into the
    # 45-55 wedge, which is opposite-field territory. That made Yankee Stadium
    # the only park whose handedness swing fell outside the fleet range —
    # 40.77 pp against a median of 43.4 — because sided capture in the
    # opposite-field wedge dilutes the pull-side share. See NOTES_STEP7.md.
    sections.append(SeatSection(
        name='1B Upper (Sec 307-316)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=40, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=35, height_max=80,
        num_seats=600, avg_ticket_price=60,
    ))
    # 3B Upper (Sec 324-331)
    sections.append(SeatSection(
        name='3B Upper (Sec 324-331)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=40, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=35, height_max=80,
        num_seats=600, avg_ticket_price=60,
    ))

    # === GRANDSTAND (400s) ===
    # Behind Plate Grand (Sec 419-421)
    sections.append(SeatSection(
        name='Behind Plate Grandstand (Sec 419-421)', section_id='HOME-G',
        side='HOME', level='upper',
        distance_min=40, distance_max=140,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=400, avg_ticket_price=30,
    ))
    # 1B Grandstand (Sec 407-418)
    sections.append(SeatSection(
        name='1B Grandstand (Sec 407-418)', section_id='1B-UR',
        side='1B', level='upper',
        distance_min=130, distance_max=250,
        angle_min=10, angle_max=40,
        height_min=40, height_max=80,
        num_seats=900, avg_ticket_price=35,
    ))
    # 3B Grandstand (Sec 422-429)
    sections.append(SeatSection(
        name='3B Grandstand (Sec 422-429)', section_id='3B-UR',
        side='3B', level='upper',
        distance_min=130, distance_max=250,
        angle_min=10, angle_max=40,
        height_min=40, height_max=80,
        num_seats=900, avg_ticket_price=35,
    ))

    return sections


def _make_fenway_park_sections() -> list[SeatSection]:
    """Section analogue for Fenway Park (opened 1912).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.

    The factory below multiplies every distance here by 0.85 to close a gap
    between decks. That multiplier is a fudge tuned to make section matching
    behave, not a measured property of Fenway's foul territory.
    """
    sections = []

    # === FIELD BOX LEVEL ===
    # 1B Field Box (Sec FB9-FB16)
    sections.append(SeatSection(
        name='1B Field Box (Sec FB9-FB16)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=100, distance_max=200,
        angle_min=0, angle_max=30,
        height_min=0, height_max=8,
        num_seats=150, avg_ticket_price=250,
    ))
    # 1B Infield Field Box (Sec FB17-FB29)
    sections.append(SeatSection(
        name='1B Infield Field Box (Sec FB17-FB29)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=60, distance_max=120,
        angle_min=25, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=350,
    ))
    # Behind Plate Field Box (Sec FB31-FB49)
    sections.append(SeatSection(
        name='Behind Plate Field Box (Sec FB31-FB49)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=50, distance_max=90,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=200, avg_ticket_price=450,
    ))
    # 3B Infield Field Box (Sec FB51-FB69)
    sections.append(SeatSection(
        name='3B Infield Field Box (Sec FB51-FB69)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=60, distance_max=120,
        angle_min=25, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=350,
    ))
    # 3B Field Box / LF (Sec FB71-FB82)
    sections.append(SeatSection(
        name='3B Field Box (Sec FB71-FB82)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=100, distance_max=200,
        angle_min=0, angle_max=30,
        height_min=0, height_max=8,
        num_seats=150, avg_ticket_price=250,
    ))

    # === LOGE LEVEL ===
    # 1B Loge (Sec LB101-LB124)
    sections.append(SeatSection(
        name='1B Loge (Sec LB101-LB124)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=100, distance_max=250,
        angle_min=0, angle_max=45,
        height_min=10, height_max=35,
        num_seats=600, avg_ticket_price=120,
    ))
    # Behind Plate Loge (Sec LB125-LB136)
    sections.append(SeatSection(
        name='Behind Plate Loge (Sec LB125-LB136)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=60, distance_max=120,
        angle_min=55, angle_max=90,
        height_min=10, height_max=35,
        num_seats=350, avg_ticket_price=200,
    ))
    # 3B Loge (Sec LB137-LB155)
    sections.append(SeatSection(
        name='3B Loge (Sec LB137-LB155)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=100, distance_max=250,
        angle_min=0, angle_max=45,
        height_min=10, height_max=35,
        num_seats=600, avg_ticket_price=120,
    ))

    # === GRANDSTAND LEVEL ===
    # 1B Grandstand (Sec G5-G11)
    sections.append(SeatSection(
        name='1B Grandstand (Sec G5-G11)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=40, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=35, height_max=70,
        num_seats=600, avg_ticket_price=60,
    ))
    # Behind Plate Grandstand (Sec G12-G21)
    sections.append(SeatSection(
        name='Behind Plate Grandstand (Sec G12-G21)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=140,
        angle_min=50, angle_max=90,
        height_min=35, height_max=70,
        num_seats=500, avg_ticket_price=75,
    ))
    # 3B Grandstand (Sec G22-G28)
    sections.append(SeatSection(
        name='3B Grandstand (Sec G22-G28)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=40, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=35, height_max=70,
        num_seats=600, avg_ticket_price=60,
    ))

    return sections


def _make_dodger_stadium_sections() -> list[SeatSection]:
    """Section analogue for Dodger Stadium (opened 1962).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    # === FIELD LEVEL ===
    # Behind Plate Dugout Club (Sec DG1-DG15)
    sections.append(SeatSection(
        name='Dugout Club (Sec DG1-DG15)', section_id='HOME-DC',
        side='HOME', level='field',
        distance_min=30, distance_max=60,
        angle_min=55, angle_max=90,
        height_min=0, height_max=8,
        num_seats=100, avg_ticket_price=800,
    ))
    # Behind Plate Field MVP (Sec FD1-FD10)
    sections.append(SeatSection(
        name='Behind Plate Field (Sec FD1-FD10)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=40, distance_max=80,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=200, avg_ticket_price=500,
    ))
    # 1B Infield Field (Sec FD12-FD24, even)
    sections.append(SeatSection(
        name='1B Infield Field (Sec FD12-FD24)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=80, distance_max=180,
        angle_min=0, angle_max=30,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=250,
    ))
    # 3B Infield Field (Sec FD11-FD25, odd)
    sections.append(SeatSection(
        name='3B Infield Field (Sec FD11-FD25)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=80, distance_max=180,
        angle_min=0, angle_max=30,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=250,
    ))
    # 1B Baseline (Sec FD26-FD44, even)
    sections.append(SeatSection(
        name='1B Baseline Field (Sec FD26-FD44)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=180, distance_max=300,
        angle_min=0, angle_max=25,
        height_min=0, height_max=12,
        num_seats=400, avg_ticket_price=180,
    ))
    # 3B Baseline (Sec FD27-FD45, odd)
    sections.append(SeatSection(
        name='3B Baseline Field (Sec FD27-FD45)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=180, distance_max=300,
        angle_min=0, angle_max=25,
        height_min=0, height_max=12,
        num_seats=400, avg_ticket_price=180,
    ))

    # === LOGE LEVEL ===
    # Behind Plate Loge (Sec 101-110)
    sections.append(SeatSection(
        name='Behind Plate Loge (Sec 101-110)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=60, distance_max=120,
        angle_min=55, angle_max=90,
        height_min=15, height_max=40,
        num_seats=350, avg_ticket_price=200,
    ))
    # 1B Loge (Sec 112-136, even)
    sections.append(SeatSection(
        name='1B Loge (Sec 112-136)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=30, distance_max=180,
        angle_min=15, angle_max=45,
        height_min=10, height_max=35,
        num_seats=500, avg_ticket_price=150,
    ))
    # 3B Loge (Sec 111-135, odd)
    sections.append(SeatSection(
        name='3B Loge (Sec 111-135)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=30, distance_max=180,
        angle_min=15, angle_max=45,
        height_min=10, height_max=35,
        num_seats=500, avg_ticket_price=150,
    ))

    # === RESERVE LEVEL ===
    # Behind Plate Reserve (Sec RS1-RS10)
    sections.append(SeatSection(
        name='Behind Plate Reserve (Sec RS1-RS10)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=35, height_max=70,
        num_seats=500, avg_ticket_price=75,
    ))
    # 1B Reserve (Sec RS12-RS36, even)
    sections.append(SeatSection(
        name='1B Reserve (Sec RS12-RS36)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=40, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=35, height_max=70,
        num_seats=600, avg_ticket_price=60,
    ))
    # 3B Reserve (Sec RS11-RS35, odd)
    sections.append(SeatSection(
        name='3B Reserve (Sec RS11-RS35)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=40, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=35, height_max=70,
        num_seats=600, avg_ticket_price=60,
    ))

    return sections


def _make_wrigley_field_sections() -> list[SeatSection]:
    """Section analogue for Wrigley Field (opened 1914).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.

    The factory below multiplies every distance here by 0.88, on the same
    basis as Fenway's 0.85 — a matching fudge, not a measurement.
    """
    sections = []

    # === FIELD BOX (100s) ===
    # 1B Field Box (Sec 123-134) — down RF foul line
    sections.append(SeatSection(
        name='1B Field Box (Sec 123-134)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=300,
    ))
    # 1B Infield Field Box (Sec 115-122)
    sections.append(SeatSection(
        name='1B Infield Field Box (Sec 115-122)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=400,
    ))
    # Behind Plate Field Box (Sec 112-114)
    sections.append(SeatSection(
        name='Behind Plate Field Box (Sec 112-114)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=12,
        num_seats=150, avg_ticket_price=500,
    ))
    # 3B Infield Field Box (Sec 105-111)
    sections.append(SeatSection(
        name='3B Infield Field Box (Sec 105-111)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=400,
    ))
    # 3B Field Box (Sec 101-104) — down LF foul line
    sections.append(SeatSection(
        name='3B Field Box (Sec 101-104)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=300,
    ))

    # === TERRACE LEVEL (200s) ===
    # 1B Terrace (Sec 225-233)
    sections.append(SeatSection(
        name='1B Terrace (Sec 225-233)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=10, angle_max=45,
        height_min=12, height_max=35,
        num_seats=500, avg_ticket_price=120,
    ))
    # Behind Plate Terrace (Sec 213-224)
    sections.append(SeatSection(
        name='Behind Plate Terrace (Sec 213-224)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=55, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=35,
        num_seats=400, avg_ticket_price=180,
    ))
    # 3B Terrace (Sec 202-212)
    sections.append(SeatSection(
        name='3B Terrace (Sec 202-212)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=10, angle_max=45,
        height_min=12, height_max=35,
        num_seats=500, avg_ticket_price=120,
    ))

    # === UPPER DECK (300s) ===
    # 1B Upper (Sec 319R-331R)
    sections.append(SeatSection(
        name='1B Upper (Sec 319R-331R)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=45, distance_max=240,
        angle_min=10, angle_max=50,
        height_min=38, height_max=75,
        num_seats=600, avg_ticket_price=55,
    ))
    # Behind Plate Upper (Sec 308L-318R)
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 308L-318R)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=45, angle_max=90,
        height_min=38, height_max=75,
        num_seats=500, avg_ticket_price=65,
    ))
    # 3B Upper (Sec 303L-307L)
    sections.append(SeatSection(
        name='3B Upper (Sec 303L-307L)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=45, distance_max=240,
        angle_min=10, angle_max=50,
        height_min=38, height_max=75,
        num_seats=600, avg_ticket_price=55,
    ))

    # === UPPER RESERVED (400s) ===
    # 1B Upper Reserved (Sec 420R-431R)
    sections.append(SeatSection(
        name='1B Upper Reserved (Sec 420R-431R)', section_id='1B-UR',
        side='1B', level='upper',
        distance_min=130, distance_max=250,
        angle_min=5, angle_max=40,
        height_min=45, height_max=85,
        num_seats=800, avg_ticket_price=30,
    ))
    # Behind Plate Upper Reserved (Sec 409-419)
    sections.append(SeatSection(
        name='Behind Plate Upper Reserved (Sec 409-419)', section_id='HOME-G',
        side='HOME', level='upper',
        distance_min=45, distance_max=140,
        angle_min=45, angle_max=90,
        height_min=45, height_max=85,
        num_seats=500, avg_ticket_price=35,
    ))
    # 3B Upper Reserved (Sec 403L-408L)
    sections.append(SeatSection(
        name='3B Upper Reserved (Sec 403L-408L)', section_id='3B-UR',
        side='3B', level='upper',
        distance_min=130, distance_max=250,
        angle_min=5, angle_max=40,
        height_min=45, height_max=85,
        num_seats=800, avg_ticket_price=30,
    ))

    return sections


def _make_coors_field_sections() -> list[SeatSection]:
    """Section analogue for Coors Field (opened 1995).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.

    The 5,200 ft altitude on the factory is real and drives the air-density
    correction. The section geometry it is paired with is not.
    """
    sections = []

    # === FIELD LEVEL (100s) ===
    # 1B Baseline (Sec 141-150) — down RF foul line
    sections.append(SeatSection(
        name='1B Baseline (Sec 141-150)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=250, avg_ticket_price=150,
    ))
    # 1B Infield (Sec 133-140)
    sections.append(SeatSection(
        name='1B Infield (Sec 133-140)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=60, distance_max=130,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=350, avg_ticket_price=250,
    ))
    # Behind Plate (Sec 127-132, Coors Club)
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 127-132)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=90,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=200, avg_ticket_price=350,
    ))
    # 3B Infield (Sec 118-126)
    sections.append(SeatSection(
        name='3B Infield (Sec 118-126)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=60, distance_max=130,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=350, avg_ticket_price=250,
    ))
    # 3B Baseline (Sec 110-117) — down LF foul line
    sections.append(SeatSection(
        name='3B Baseline (Sec 110-117)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=250, avg_ticket_price=150,
    ))

    # === CLUB LEVEL (200s) ===
    # 1B Club (Sec 237-247)
    sections.append(SeatSection(
        name='1B Club (Sec 237-247)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=200,
        angle_min=10, angle_max=45,
        height_min=12, height_max=38,
        num_seats=500, avg_ticket_price=120,
    ))
    # Behind Plate Club (Sec 225-236)
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 225-236)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=55, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=12, height_max=38,
        num_seats=400, avg_ticket_price=180,
    ))
    # 3B Club (Sec 214-224)
    sections.append(SeatSection(
        name='3B Club (Sec 214-224)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=200,
        angle_min=10, angle_max=45,
        height_min=12, height_max=38,
        num_seats=500, avg_ticket_price=120,
    ))

    # === UPPER DECK (300s) ===
    # 1B Upper (Sec 333-347)
    sections.append(SeatSection(
        name='1B Upper (Sec 333-347)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=260,
        angle_min=10, angle_max=50,
        height_min=40, height_max=85,
        num_seats=700, avg_ticket_price=35,
    ))
    # Behind Plate Upper (Sec 321-332)
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 321-332)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=45, distance_max=140,
        angle_min=45, angle_max=90,
        height_min=40, height_max=85,
        num_seats=550, avg_ticket_price=45,
    ))
    # 3B Upper (Sec 301-320)
    sections.append(SeatSection(
        name='3B Upper (Sec 301-320)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=260,
        angle_min=10, angle_max=50,
        height_min=40, height_max=85,
        num_seats=700, avg_ticket_price=35,
    ))

    return sections


def _make_citi_field_sections() -> list[SeatSection]:
    """Section analogue for Citi Field (opened 2009).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    # === FIELD LEVEL (100s) ===
    # 1B Baseline (Sec 104-110)
    sections.append(SeatSection(
        name='1B Baseline Box (Sec 104-110)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=100, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=200,
    ))
    # 1B Infield (Sec 111-114)
    sections.append(SeatSection(
        name='1B Infield Field (Sec 111-114)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=25, angle_max=55,
        height_min=0, height_max=10,
        num_seats=250, avg_ticket_price=350,
    ))
    # Behind Plate (Sec 115-120)
    sections.append(SeatSection(
        name='Behind Plate (Sec 115-120)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=90,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=200, avg_ticket_price=500,
    ))
    # 3B Infield (Sec 121-125)
    sections.append(SeatSection(
        name='3B Infield Field (Sec 121-125)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=25, angle_max=55,
        height_min=0, height_max=10,
        num_seats=250, avg_ticket_price=350,
    ))
    # 3B Baseline (Sec 126-132)
    sections.append(SeatSection(
        name='3B Baseline Box (Sec 126-132)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=100, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=200,
    ))

    # === EXCELSIOR LEVEL (300s) ===
    # 1B Excelsior (Sec 309-316)
    sections.append(SeatSection(
        name='1B Excelsior (Sec 309-316)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=190,
        angle_min=15, angle_max=45,
        height_min=12, height_max=38,
        num_seats=450, avg_ticket_price=130,
    ))
    # Behind Plate Excelsior (Sec 317-325)
    sections.append(SeatSection(
        name='Behind Plate Excelsior (Sec 317-325)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=55, distance_max=120,
        angle_min=55, angle_max=90,
        height_min=12, height_max=38,
        num_seats=350, avg_ticket_price=180,
    ))
    # 3B Excelsior (Sec 326-329)
    sections.append(SeatSection(
        name='3B Excelsior (Sec 326-329)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=190,
        angle_min=15, angle_max=45,
        height_min=12, height_max=38,
        num_seats=450, avg_ticket_price=130,
    ))

    # === PROMENADE LEVEL (500s) ===
    # 1B Promenade (Sec 506-514)
    sections.append(SeatSection(
        name='1B Promenade (Sec 506-514)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=35,
    ))
    # Behind Plate Promenade (Sec 515-523)
    sections.append(SeatSection(
        name='Behind Plate Promenade (Sec 515-523)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=140,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=45,
    ))
    # 3B Promenade (Sec 524-531)
    sections.append(SeatSection(
        name='3B Promenade (Sec 524-531)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=35,
    ))

    return sections


def _make_citizens_bank_sections() -> list[SeatSection]:
    """Section analogue for Citizens Bank Park (opened 2004).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    # === FIELD LEVEL (100s) ===
    # 1B Diamond Club (Sec 115-119)
    sections.append(SeatSection(
        name='1B Diamond Club (Sec 115-119)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=250,
    ))
    # 1B Infield (Sec 120-126)
    sections.append(SeatSection(
        name='1B Infield (Sec 120-126)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=300,
    ))
    # Behind Plate (Sec 127-131)
    sections.append(SeatSection(
        name='Behind Plate (Sec 127-131)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=180, avg_ticket_price=400,
    ))
    # 3B Infield (Sec 132-138)
    sections.append(SeatSection(
        name='3B Infield (Sec 132-138)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=300,
    ))
    # 3B Baseline (Sec 139-145)
    sections.append(SeatSection(
        name='3B Baseline (Sec 139-145)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=250,
    ))

    # === HALL OF FAME CLUB (200s) ===
    # 1B Club (Sec 215-222)
    sections.append(SeatSection(
        name='1B Hall of Fame Club (Sec 215-222)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=35, distance_max=180,
        angle_min=15, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=140,
    ))
    # Behind Plate Club (Sec 223-229)
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 223-229)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=55, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=180,
    ))
    # 3B Club (Sec 230-237)
    sections.append(SeatSection(
        name='3B Hall of Fame Club (Sec 230-237)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=35, distance_max=180,
        angle_min=15, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=140,
    ))

    # === TERRACE DECK (300s) ===
    # 1B Terrace (Sec 315-322)
    sections.append(SeatSection(
        name='1B Terrace (Sec 315-322)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=75,
        num_seats=600, avg_ticket_price=35,
    ))
    # Behind Plate Terrace (Sec 323-329)
    sections.append(SeatSection(
        name='Behind Plate Terrace (Sec 323-329)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=38, height_max=75,
        num_seats=500, avg_ticket_price=45,
    ))
    # 3B Terrace (Sec 330-336)
    sections.append(SeatSection(
        name='3B Terrace (Sec 330-336)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=75,
        num_seats=600, avg_ticket_price=35,
    ))

    return sections


def _make_truist_park_sections() -> list[SeatSection]:
    """Section analogue for Truist Park (opened 2017).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    # === FIELD LEVEL ===
    # 1B Dugout (Sec 115-121)
    sections.append(SeatSection(
        name='1B Dugout Box (Sec 115-121)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=180,
    ))
    # 1B Infield (Sec 122-128)
    sections.append(SeatSection(
        name='1B Infield (Sec 122-128)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=280,
    ))
    # Behind Plate (Sec 129-133)
    sections.append(SeatSection(
        name='Behind Plate (Sec 129-133)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=180, avg_ticket_price=400,
    ))
    # 3B Infield (Sec 134-140)
    sections.append(SeatSection(
        name='3B Infield (Sec 134-140)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=280,
    ))
    # 3B Dugout (Sec 141-147)
    sections.append(SeatSection(
        name='3B Dugout Box (Sec 141-147)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=180,
    ))

    # === TERRACE LEVEL (200s) ===
    # 1B Terrace (Sec 218-226)
    sections.append(SeatSection(
        name='1B Terrace (Sec 218-226)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=100,
    ))
    # Behind Plate Terrace (Sec 227-235)
    sections.append(SeatSection(
        name='Behind Plate Terrace (Sec 227-235)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=55, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=150,
    ))
    # 3B Terrace (Sec 236-244)
    sections.append(SeatSection(
        name='3B Terrace (Sec 236-244)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=100,
    ))

    # === UPPER LEVEL (300s) ===
    # 1B Upper (Sec 320-331)
    sections.append(SeatSection(
        name='1B Upper (Sec 320-331)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=650, avg_ticket_price=30,
    ))
    # Behind Plate Upper (Sec 332-340)
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 332-340)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=38, height_max=78,
        num_seats=500, avg_ticket_price=40,
    ))
    # 3B Upper (Sec 341-350)
    sections.append(SeatSection(
        name='3B Upper (Sec 341-350)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=650, avg_ticket_price=30,
    ))

    return sections


def _make_oracle_park_sections() -> list[SeatSection]:
    """Section analogue for Oracle Park (opened 2000).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    # === FIELD LEVEL (100s) ===
    # 1B Club (Sec 117-123) — down RF line toward McCovey Cove
    sections.append(SeatSection(
        name='1B Club Box (Sec 117-123)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=195,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=250,
    ))
    # 1B Infield (Sec 110-116)
    sections.append(SeatSection(
        name='1B Infield (Sec 110-116)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=115,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=350,
    ))
    # Behind Plate (Sec 107-109)
    sections.append(SeatSection(
        name='Behind Plate (Sec 107-109)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=450,
    ))
    # 3B Infield (Sec 103-106)
    sections.append(SeatSection(
        name='3B Infield (Sec 103-106)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=115,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=350,
    ))
    # 3B Baseline (Sec 101-102)
    sections.append(SeatSection(
        name='3B Baseline (Sec 101-102)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=195,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=250,
    ))

    # === CLUB LEVEL (200s) ===
    # 1B Club (Sec 216-226)
    sections.append(SeatSection(
        name='1B Club (Sec 216-226)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=12, angle_max=45,
        height_min=10, height_max=35,
        num_seats=450, avg_ticket_price=140,
    ))
    # Behind Plate Club (Sec 209-215)
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 209-215)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=55, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=10, height_max=35,
        num_seats=350, avg_ticket_price=200,
    ))
    # 3B Club (Sec 202-208)
    sections.append(SeatSection(
        name='3B Club (Sec 202-208)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=12, angle_max=45,
        height_min=10, height_max=35,
        num_seats=450, avg_ticket_price=140,
    ))

    # === VIEW LEVEL (300s) ===
    # 1B View (Sec 317-327)
    sections.append(SeatSection(
        name='1B View Reserve (Sec 317-327)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=75,
        num_seats=600, avg_ticket_price=30,
    ))
    # Behind Plate View (Sec 308-316)
    sections.append(SeatSection(
        name='Behind Plate View (Sec 308-316)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=38, height_max=75,
        num_seats=500, avg_ticket_price=40,
    ))
    # 3B View (Sec 302-307)
    sections.append(SeatSection(
        name='3B View Reserve (Sec 302-307)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=75,
        num_seats=600, avg_ticket_price=30,
    ))

    return sections


def _make_daikin_park_sections() -> list[SeatSection]:
    """Section analogue for Daikin Park (opened 2000, formerly Minute Maid).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    # === FIELD LEVEL (100s) ===
    # 1B Baseline (Sec 128-134) — toward RF/Crawford Boxes side
    sections.append(SeatSection(
        name='1B Baseline (Sec 128-134)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=180,
    ))
    # 1B Infield (Sec 121-127)
    sections.append(SeatSection(
        name='1B Infield (Sec 121-127)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=300,
    ))
    # Behind Plate (Sec 117-120, Diamond Club)
    sections.append(SeatSection(
        name='Behind Plate Diamond (Sec 117-120)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=40, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=180, avg_ticket_price=450,
    ))
    # 3B Infield (Sec 111-116)
    sections.append(SeatSection(
        name='3B Infield (Sec 111-116)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=300,
    ))
    # 3B Baseline (Sec 105-110) — toward LF
    sections.append(SeatSection(
        name='3B Baseline (Sec 105-110)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=180,
    ))

    # === CLUB / MEZZANINE (200s) ===
    # 1B Mezzanine (Sec 224-232)
    sections.append(SeatSection(
        name='1B Mezzanine (Sec 224-232)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=110,
    ))
    # Behind Plate Mezzanine (Sec 216-223)
    sections.append(SeatSection(
        name='Behind Plate Mezzanine (Sec 216-223)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=160,
    ))
    # 3B Mezzanine (Sec 206-215)
    sections.append(SeatSection(
        name='3B Mezzanine (Sec 206-215)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=110,
    ))

    # === UPPER DECK (400s) ===
    # 1B Upper (Sec 427-434)
    sections.append(SeatSection(
        name='1B Upper Deck (Sec 427-434)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=25,
    ))
    # Behind Plate Upper (Sec 418-426)
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 418-426)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=35,
    ))
    # 3B Upper (Sec 408-417)
    sections.append(SeatSection(
        name='3B Upper Deck (Sec 408-417)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=25,
    ))

    return sections


def _make_tropicana_field_sections() -> list[SeatSection]:
    """Section analogue for Tropicana Field (opened 1990). Indoor dome.

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.

    Flagged separately as unverified after the Step 5-6 venue repairs; see
    NOTES_STEP5_6.md item 6.
    """
    sections = []

    # === LOWER LEVEL (100s) ===
    # 1B Lower (Sec 113-118)
    sections.append(SeatSection(
        name='1B Lower Box (Sec 113-118)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=190,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=180, avg_ticket_price=80,
    ))
    # 1B Infield Lower (Sec 107-112)
    sections.append(SeatSection(
        name='1B Infield Lower (Sec 107-112)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=50, distance_max=110,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=250, avg_ticket_price=150,
    ))
    # Behind Plate Lower (Sec 104-106)
    sections.append(SeatSection(
        name='Behind Plate Lower (Sec 104-106)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=40, distance_max=80,
        angle_min=55, angle_max=90,
        height_min=0, height_max=12,
        num_seats=150, avg_ticket_price=200,
    ))
    # 3B Infield Lower (Sec 100-103)
    sections.append(SeatSection(
        name='3B Infield Lower (Sec 100-103)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=50, distance_max=110,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=250, avg_ticket_price=150,
    ))
    # 3B Lower (Sec 125-130)
    sections.append(SeatSection(
        name='3B Lower Box (Sec 125-130)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=190,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=180, avg_ticket_price=80,
    ))

    # === PRESS LEVEL (200s) ===
    # 1B Press (Sec 211-216)
    sections.append(SeatSection(
        name='1B Press Level (Sec 211-216)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=175,
        angle_min=12, angle_max=45,
        height_min=10, height_max=32,
        num_seats=400, avg_ticket_price=60,
    ))
    # Behind Plate Press (Sec 205-210)
    sections.append(SeatSection(
        name='Behind Plate Press (Sec 205-210)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=110,
        angle_min=55, angle_max=90,
        height_min=10, height_max=32,
        num_seats=300, avg_ticket_price=80,
    ))
    # 3B Press (Sec 217-224)
    sections.append(SeatSection(
        name='3B Press Level (Sec 217-224)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=175,
        angle_min=12, angle_max=45,
        height_min=10, height_max=32,
        num_seats=400, avg_ticket_price=60,
    ))

    # === UPPER LEVEL (300s) ===
    # 1B Upper (Sec 310-316)
    sections.append(SeatSection(
        name='1B Upper (Sec 310-316)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=45, distance_max=230,
        angle_min=10, angle_max=45,
        height_min=35, height_max=70,
        num_seats=550, avg_ticket_price=20,
    ))
    # Behind Plate Upper (Sec 303-309)
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 303-309)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=35, height_max=70,
        num_seats=450, avg_ticket_price=25,
    ))
    # 3B Upper (Sec 317-322)
    sections.append(SeatSection(
        name='3B Upper (Sec 317-322)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=45, distance_max=230,
        angle_min=10, angle_max=45,
        height_min=35, height_max=70,
        num_seats=550, avg_ticket_price=20,
    ))

    return sections


def _make_chase_field_sections() -> list[SeatSection]:
    """Section analogue for Chase Field (opened 1998). Retractable roof.

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    # === FIELD LEVEL (100s) ===
    sections.append(SeatSection(
        name='1B Baseline (Sec 112-118)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=205,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 105-111)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 101-104)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=180, avg_ticket_price=300,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 125-131)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 132-138)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=205,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=120,
    ))

    # === CLUB / SUITE LEVEL (200s) ===
    sections.append(SeatSection(
        name='1B Club (Sec 208-216)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 200-207)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 217-225)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=100,
    ))

    # === UPPER DECK (300s) ===
    sections.append(SeatSection(
        name='1B Upper (Sec 316-326)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=600, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 306-315)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=38, height_max=78,
        num_seats=500, avg_ticket_price=35,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 327-336)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=600, avg_ticket_price=25,
    ))

    return sections


def _make_camden_yards_sections() -> list[SeatSection]:
    """Section analogue for Oriole Park at Camden Yards (opened 1992).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    # === FIELD LEVEL (lower 0-99) ===
    sections.append(SeatSection(
        name='1B Field Box (Sec 56-68)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 44-55)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 38-43)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=48, distance_max=90,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=180, avg_ticket_price=350,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 26-37)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='3B Field Box (Sec 14-25)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=150,
    ))

    # === CLUB LEVEL (200s) ===
    sections.append(SeatSection(
        name='1B Club (Sec 252-264)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 242-251)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=55, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 228-241)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=100,
    ))

    # === UPPER DECK (300s) ===
    sections.append(SeatSection(
        name='1B Upper (Sec 362-376)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=650, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 348-361)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=38, height_max=78,
        num_seats=500, avg_ticket_price=35,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 332-347)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=650, avg_ticket_price=25,
    ))

    return sections


def _make_great_american_sections() -> list[SeatSection]:
    """Section analogue for Great American Ball Park (opened 2003).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.

    The bands built here are identical to Petco Park's, number for number: the
    two share one template instance. They no longer *stay* identical — the
    factory applies each park's sourced parameters afterwards, and Great
    American's foul area (23,600 vs 23,900) and backstop (50 vs 45) separate
    them. What is still shared, at these two parks as at all 31, is the shape:
    every angle and every height.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 128-136)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 120-127)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 116-119)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=300,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 109-115)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 101-108)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=120,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 220-228)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=90,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 213-219)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=130,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 205-212)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=90,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 420-430)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=600, avg_ticket_price=20,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 412-419)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=38, height_max=78,
        num_seats=500, avg_ticket_price=30,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 401-411)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=600, avg_ticket_price=20,
    ))

    return sections


def _make_progressive_field_sections() -> list[SeatSection]:
    """Section analogue for Progressive Field (opened 1994).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 162-172)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 153-161)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 148-152)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=170, avg_ticket_price=280,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 139-147)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 130-138)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 453-461)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 446-452)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 437-445)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=80,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 556-568)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=18,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 546-555)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 534-545)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=18,
    ))

    return sections


def _make_comerica_park_sections() -> list[SeatSection]:
    """Section analogue for Comerica Park (opened 2000).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 120-130)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 113-119)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 109-112)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=280,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 103-108)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 137-145)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 218-228)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=190,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 210-217)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 229-238)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=190,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 318-330)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=18,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 308-317)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 331-340)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=18,
    ))

    return sections


def _make_kauffman_stadium_sections() -> list[SeatSection]:
    """Section analogue for Kauffman Stadium (opened 1973).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.

    The bands built here are identical to Busch, Nationals Park and Rate
    Field, number for number: one template instance shared across four parks.
    They no longer *stay* identical — the factory applies each park's sourced
    parameters afterwards, and the four now span 45 to 60 ft of backstop and
    22,900 to 25,200 sq ft of foul territory. What is still shared, at these
    four parks as at all 31, is the shape: every angle and every height.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Dugout (Sec 121-131)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 114-120)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 110-113)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 103-109)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='3B Dugout (Sec 133-143)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B Loge (Sec 221-231)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=70,
    ))
    sections.append(SeatSection(
        name='Behind Plate Loge (Sec 213-220)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='3B Loge (Sec 232-243)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=70,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 421-431)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=15,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 413-420)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=22,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 432-443)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=15,
    ))

    return sections


def _make_angel_stadium_sections() -> list[SeatSection]:
    """Section analogue for Angel Stadium (opened 1966).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Field (Sec 121-129)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 114-120)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 110-113)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=300,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 103-109)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='3B Field (Sec 133-141)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=120,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 221-229)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 213-220)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 230-239)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 421-433)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=18,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 413-420)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 434-445)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=18,
    ))

    return sections


def _make_sutter_health_sections() -> list[SeatSection]:
    """Section analogue for Sutter Health Park, the Athletics' primary 2026 home.

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.

    One of the two coarsest tables in the file: 8 sections over two levels,
    and it produces one of the two lowest game totals in the fleet. Whether
    that is a real small-park effect or an artefact of the coarse table
    cannot be separated without a seating chart (NOTES_STEP7.md).

    SOURCED_DATA.md also records an unresolved conflict between MLB.com and
    A View From My Seat over which sections sit behind home plate, so even
    the section-to-field-position mapping here is uncertain.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Field (Sec 112-118)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=85, distance_max=190,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=180, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 106-111)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=50, distance_max=110,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=240, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 103-105)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=40, distance_max=80,
        angle_min=55, angle_max=90,
        height_min=0, height_max=12,
        num_seats=120, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 125-130)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=50, distance_max=110,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=240, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='3B Field (Sec 131-137)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=85, distance_max=190,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=180, avg_ticket_price=80,
    ))

    # Sutter Health is a minor-league park — only 2 levels
    sections.append(SeatSection(
        name='1B Upper (Sec 206-212)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=40, distance_max=180,
        angle_min=10, angle_max=45,
        height_min=15, height_max=45,
        num_seats=400, avg_ticket_price=40,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 200-205)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=35, distance_max=100,
        angle_min=50, angle_max=90,
        height_min=15, height_max=45,
        num_seats=300, avg_ticket_price=60,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 213-220)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=40, distance_max=180,
        angle_min=10, angle_max=45,
        height_min=15, height_max=45,
        num_seats=400, avg_ticket_price=40,
    ))

    return sections


def _make_las_vegas_ballpark_sections() -> list[SeatSection]:
    """Section analogue for Las Vegas Ballpark, the Athletics' secondary 2026 home.

    GEOMETRY IS AN ANALOGUE, NOT A SEATING CHART. Las Vegas Ballpark is a
    ~10,000-seat Triple-A park with the same two-level bowl arrangement as
    Sutter Health Park, so the deck structure here is Sutter Health's scaled
    down by the ratio of the two capacities. The field dimensions and the
    altitude on the factory below are real; these seat boundaries are not
    digitized from a published chart, and no numbers produced for this park
    should be read as better than "same class of park, same class of answer."

    This is the same evidence class as the Tropicana Field caveat in
    NOTES_STEP5_6.md, and it is flagged for the same reason.

    This docstring was written as an exception to a file of supposedly real
    layouts. It is not an exception — the provenance trace recorded in MODULE
    PROVENANCE found every park in this file to be an analogue. What is
    unusual here is only that the analogue was documented at the time.
    """
    sections = []

    # Bowl footprint scaled from Sutter Health (14,000 seats) to Las Vegas
    # (~10,000): a smaller park brings the stands in toward the plate.
    S = 0.92

    sections.append(SeatSection(
        name='1B Field (Sec 111-117)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=85 * S, distance_max=190 * S,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=170, avg_ticket_price=55,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 105-110)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=50 * S, distance_max=110 * S,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=220, avg_ticket_price=95,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 102-104)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=40 * S, distance_max=80 * S,
        angle_min=55, angle_max=90,
        height_min=0, height_max=12,
        num_seats=110, avg_ticket_price=160,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 118-123)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=50 * S, distance_max=110 * S,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=220, avg_ticket_price=95,
    ))
    sections.append(SeatSection(
        name='3B Field (Sec 124-130)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=85 * S, distance_max=190 * S,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=170, avg_ticket_price=55,
    ))

    # Two levels only, as at Sutter Health.
    sections.append(SeatSection(
        name='1B Upper (Sec 205-211)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=40 * S, distance_max=180 * S,
        angle_min=10, angle_max=45,
        height_min=15, height_max=42,
        num_seats=330, avg_ticket_price=30,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 200-204)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=35 * S, distance_max=100 * S,
        angle_min=50, angle_max=90,
        height_min=15, height_max=42,
        num_seats=250, avg_ticket_price=45,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 212-219)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=40 * S, distance_max=180 * S,
        angle_min=10, angle_max=45,
        height_min=15, height_max=42,
        num_seats=330, avg_ticket_price=30,
    ))

    return sections


def _make_pnc_park_sections() -> list[SeatSection]:
    """Section analogue for PNC Park (opened 2001).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 119-128)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=195,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 112-118)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=115,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 108-111)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=280,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 101-107)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=115,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 130-139)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=195,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 216-224)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=12, angle_max=45,
        height_min=12, height_max=35,
        num_seats=450, avg_ticket_price=70,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 209-215)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=12, height_max=35,
        num_seats=350, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 225-233)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=12, angle_max=45,
        height_min=12, height_max=35,
        num_seats=450, avg_ticket_price=70,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 316-325)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=235,
        angle_min=10, angle_max=45,
        height_min=38, height_max=75,
        num_seats=550, avg_ticket_price=18,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 308-315)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=125,
        angle_min=50, angle_max=90,
        height_min=38, height_max=75,
        num_seats=450, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 326-335)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=235,
        angle_min=10, angle_max=45,
        height_min=38, height_max=75,
        num_seats=550, avg_ticket_price=18,
    ))

    return sections


def _make_petco_park_sections() -> list[SeatSection]:
    """Section analogue for Petco Park (opened 2004).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.

    The bands built here are identical to Great American Ball Park's, number
    for number: the two share one template instance. They no longer *stay*
    identical — the factory applies each park's sourced parameters afterwards,
    and Petco's shorter backstop (45 vs 50) separates them. What is still
    shared, at these two parks as at all 31, is the shape: every angle and
    every height.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 117-126)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 110-116)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 106-109)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=400,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 101-105)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 128-137)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=150,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 210-218)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 203-209)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 219-227)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 310-320)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=600, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 302-309)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=38, height_max=78,
        num_seats=500, avg_ticket_price=35,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 321-330)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=600, avg_ticket_price=25,
    ))

    return sections


def _make_tmobile_park_sections() -> list[SeatSection]:
    """Section analogue for T-Mobile Park (opened 1999). Retractable roof.

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 118-128)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 112-117)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 108-111)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=320,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 133-138)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 139-148)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=120,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 218-228)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 210-217)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 229-239)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 318-330)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=20,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 308-317)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=30,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 331-343)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=20,
    ))

    return sections


def _make_busch_stadium_sections() -> list[SeatSection]:
    """Section analogue for Busch Stadium (opened 2006).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.

    The bands built here are identical to Kauffman, Nationals Park and Rate
    Field, number for number: one template instance shared across four parks.
    They no longer *stay* identical — the factory applies each park's sourced
    parameters afterwards, and the four now span 45 to 60 ft of backstop and
    22,900 to 25,200 sq ft of foul territory. What is still shared, at these
    four parks as at all 31, is the shape: every angle and every height.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 145-155)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=130,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 138-144)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=220,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 134-137)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=350,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 127-133)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=220,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 157-167)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=130,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 245-255)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=90,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 237-244)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=140,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 256-266)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=90,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 345-358)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=22,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 336-344)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=32,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 359-370)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=22,
    ))

    return sections


def _make_globe_life_sections() -> list[SeatSection]:
    """Section analogue for Globe Life Field (opened 2020). Retractable roof.

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 12-19)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 6-11)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 1-5)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=400,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 25-30)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 31-37)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=150,
    ))

    sections.append(SeatSection(
        name='1B Mezzanine (Sec 112-119)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=90,
    ))
    sections.append(SeatSection(
        name='Behind Plate Mezzanine (Sec 105-111)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=130,
    ))
    sections.append(SeatSection(
        name='3B Mezzanine (Sec 120-128)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=90,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 212-222)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=22,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 204-211)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=30,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 223-233)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=22,
    ))

    return sections


def _make_rogers_centre_sections() -> list[SeatSection]:
    """Section analogue for Rogers Centre (opened 1989). Retractable roof.

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 118-126)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 112-117)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 108-111)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=300,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 126-131)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 132-140)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B 200 Level (Sec 218-226)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=65,
    ))
    sections.append(SeatSection(
        name='Behind Plate 200 Level (Sec 210-217)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='3B 200 Level (Sec 227-237)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=65,
    ))

    sections.append(SeatSection(
        name='1B 500 Level (Sec 518-528)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=45, height_max=90,
        num_seats=650, avg_ticket_price=18,
    ))
    sections.append(SeatSection(
        name='Behind Plate 500 Level (Sec 510-517)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=45, distance_max=140,
        angle_min=50, angle_max=90,
        height_min=45, height_max=90,
        num_seats=500, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='3B 500 Level (Sec 529-538)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=45, height_max=90,
        num_seats=650, avg_ticket_price=18,
    ))

    return sections


def _make_target_field_sections() -> list[SeatSection]:
    """Section analogue for Target Field (opened 2010).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Field (Sec 110-120)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 104-109)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 101-103, Diamond Box)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=280,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 121-127)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='3B Field (Sec 128-137)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 210-218)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=70,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 203-209)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=110,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 219-228)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=70,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 310-320)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=40, height_max=78,
        num_seats=600, avg_ticket_price=18,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 303-309)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=40, height_max=78,
        num_seats=500, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 321-330)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=40, height_max=78,
        num_seats=600, avg_ticket_price=18,
    ))

    return sections


def _make_rate_field_sections() -> list[SeatSection]:
    """Section analogue for Rate Field (opened 1991).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.

    The bands built here are identical to Busch, Kauffman and Nationals Park,
    number for number: one template instance shared across four parks. They no
    longer *stay* identical — the factory applies each park's sourced
    parameters afterwards, and Rate Field's 60 ft backstop is the longest in
    MLB against Kauffman's and Nationals' 45, the shortest of the four. What
    is still shared, at these four parks as at all 31, is the shape: every
    angle and every height.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Lower (Sec 122-132)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 116-121)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 112-115)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=220,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 137-142)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='3B Lower (Sec 143-153)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=80,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 222-232)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=55,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 214-221)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 233-243)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=55,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 522-534)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=12,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 514-521)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=18,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 535-546)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=12,
    ))

    return sections


def _make_loan_depot_sections() -> list[SeatSection]:
    """Section analogue for loanDepot park (opened 2012). Retractable roof.

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 10-17)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=205,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 4-9)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 1-3)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=150, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 23-28)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 29-37)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=205,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=80,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 210-218)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=55,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 203-209)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=300, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 219-227)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=55,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 310-320)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=40, height_max=78,
        num_seats=600, avg_ticket_price=15,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 303-309)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=40, height_max=78,
        num_seats=500, avg_ticket_price=22,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 321-330)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=40, height_max=78,
        num_seats=600, avg_ticket_price=15,
    ))

    return sections


def _make_american_family_sections() -> list[SeatSection]:
    """Section analogue for American Family Field (opened 2001). Retractable roof.

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Field (Sec 113-122)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 107-112)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 103-106)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=280,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 125-130)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='3B Field (Sec 131-140)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B Loge (Sec 213-222)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=190,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=70,
    ))
    sections.append(SeatSection(
        name='Behind Plate Loge (Sec 206-212)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='3B Loge (Sec 223-232)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=190,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=70,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 413-424)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=40, height_max=82,
        num_seats=650, avg_ticket_price=15,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 405-412)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=82,
        num_seats=500, avg_ticket_price=22,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 425-436)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=40, height_max=82,
        num_seats=650, avg_ticket_price=15,
    ))

    return sections


def _make_nationals_park_sections() -> list[SeatSection]:
    """Section analogue for Nationals Park (opened 2008).

    Estimated geometry, not a digitized seating chart. See MODULE PROVENANCE.

    The bands built here are identical to Busch, Kauffman and Rate Field,
    number for number: one template instance shared across four parks. They no
    longer *stay* identical — the factory applies each park's sourced
    parameters afterwards, and the four now span 45 to 60 ft of backstop and
    22,800 to 25,200 sq ft of foul territory. What is still shared, at these
    four parks as at all 31, is the shape: every angle and every height.
    """
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 115-124)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 108-114)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 104-107, PNC Diamond Club)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=350,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 127-133)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 134-143)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=120,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 215-224)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 207-214)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 225-235)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 315-326)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=20,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 307-314)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=28,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 327-337)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=20,
    ))

    return sections


def yankee_stadium() -> Stadium:
    """Yankee Stadium geometry (opened 2009)."""
    stadium = Stadium(
        name='Yankee Stadium',
        city='New York',
        team='New York Yankees',
        altitude_ft=23,
        avg_temperature_f=75,
        lf_distance=318,
        cf_distance=408,
        rf_distance=314,
        backstop_distance=52,   # Clem; Seamheads and Wikipedia agree
    )
    stadium.sections = _make_yankee_stadium_sections()
    _apply_sourced_params(stadium, 'yankee_stadium')
    return stadium


def fenway_park() -> Stadium:
    """Fenway Park geometry (opened 1912)."""
    stadium = Stadium(
        name='Fenway Park',
        city='Boston',
        team='Boston Red Sox',
        altitude_ft=21,
        avg_temperature_f=72,
        lf_distance=310,  # Green Monster
        cf_distance=390,
        rf_distance=302,  # Pesky's Pole
        backstop_distance=52,   # Clem park page (was 60, the pre-shortening figure)
    )
    stadium.sections = _make_fenway_park_sections()
    # The old hand-tuned `scale = 0.85` here is gone. Fenway's 18,100 sq ft of
    # foul territory — the smallest in MLB — now produces its own scale from
    # the sourced area, which lands at 0.889.
    _apply_sourced_params(stadium, 'fenway_park')
    return stadium


def dodger_stadium() -> Stadium:
    """Dodger Stadium geometry."""
    stadium = Stadium(
        name='Dodger Stadium',
        city='Los Angeles',
        team='Los Angeles Dodgers',
        altitude_ft=515,
        avg_temperature_f=78,
        lf_distance=330,
        cf_distance=395,
        rf_distance=330,
        backstop_distance=53,   # Clem (was 55, Wikipedia's figure)
    )
    stadium.sections = _make_dodger_stadium_sections()
    _apply_sourced_params(stadium, 'dodger_stadium')
    return stadium


def wrigley_field() -> Stadium:
    """Wrigley Field geometry."""
    stadium = Stadium(
        name='Wrigley Field',
        city='Chicago',
        team='Chicago Cubs',
        altitude_ft=600,
        avg_temperature_f=73,
        lf_distance=355,
        cf_distance=400,
        rf_distance=353,
        backstop_distance=55,   # Clem; Seamheads and Wikipedia agree (was 56)
    )
    stadium.sections = _make_wrigley_field_sections()
    # The old hand-tuned `scale = 0.88` here is gone. Wrigley's 16,500 sq ft
    # produces 0.849 from the sourced area instead.
    _apply_sourced_params(stadium, 'wrigley_field')
    return stadium


def coors_field() -> Stadium:
    """Coors Field geometry (high altitude!)."""
    stadium = Stadium(
        name='Coors Field',
        city='Denver',
        team='Colorado Rockies',
        altitude_ft=5200,  # Field level elevation (5280 is upper deck purple row)
        avg_temperature_f=76,
        lf_distance=347,
        cf_distance=415,
        rf_distance=350,
        backstop_distance=50,   # Clem + Seamheads (was 56, Wikipedia's figure)
    )
    stadium.sections = _make_coors_field_sections()
    _apply_sourced_params(stadium, 'coors_field')
    return stadium


# All 30 MLB Stadiums (real dimensions from public park data)
def chase_field():
    stadium = Stadium(name='Chase Field', city='Phoenix', team='Arizona Diamondbacks',
        altitude_ft=1086, avg_temperature_f=78,
        lf_distance=330, cf_distance=407, rf_distance=335,
        backstop_distance=55)   # Clem + Seamheads (was 54); Wikipedia silent
    stadium.sections = _make_chase_field_sections()
    _apply_sourced_params(stadium, 'chase_field')
    return stadium

def truist_park():
    stadium = Stadium(
        name='Truist Park', city='Atlanta', team='Atlanta Braves',
        altitude_ft=1050, avg_temperature_f=78,
        lf_distance=335, cf_distance=400, rf_distance=325,
        backstop_distance=53,   # Clem's own estimate, "(53)" (was 55)
    )
    stadium.sections = _make_truist_park_sections()
    _apply_sourced_params(stadium, 'truist_park')
    return stadium

def camden_yards():
    stadium = Stadium(name='Oriole Park at Camden Yards', city='Baltimore', team='Baltimore Orioles',
        altitude_ft=130, avg_temperature_f=76,
        lf_distance=333, cf_distance=410, rf_distance=318,
        backstop_distance=54)   # Clem + Seamheads (was 57)
    stadium.sections = _make_camden_yards_sections()
    _apply_sourced_params(stadium, 'camden_yards')
    return stadium

def citizens_bank():
    stadium = Stadium(
        name='Citizens Bank Park', city='Philadelphia', team='Philadelphia Phillies',
        altitude_ft=20, avg_temperature_f=76,
        lf_distance=329, cf_distance=401, rf_distance=330,
        backstop_distance=50,   # Clem + Seamheads (was the default 55)
    )
    stadium.sections = _make_citizens_bank_sections()
    _apply_sourced_params(stadium, 'citizens_bank')
    return stadium

def great_american():
    stadium = Stadium(name='Great American Ball Park', city='Cincinnati', team='Cincinnati Reds',
        altitude_ft=683, avg_temperature_f=76,
        lf_distance=328, cf_distance=404, rf_distance=325,
        backstop_distance=50)   # Clem (was 54); Seamheads 51, Wikipedia 55
    stadium.sections = _make_great_american_sections()
    _apply_sourced_params(stadium, 'great_american')
    return stadium

def progressive_field():
    stadium = Stadium(name='Progressive Field', city='Cleveland', team='Cleveland Guardians',
        altitude_ft=620, avg_temperature_f=73,
        lf_distance=325, cf_distance=405, rf_distance=325,
        backstop_distance=60)   # Clem + Wikipedia (was the default 55); Seamheads 65
    stadium.sections = _make_progressive_field_sections()
    _apply_sourced_params(stadium, 'progressive_field')
    return stadium

def comerica_park():
    stadium = Stadium(name='Comerica Park', city='Detroit', team='Detroit Tigers',
        altitude_ft=585, avg_temperature_f=73,
        lf_distance=342, cf_distance=412, rf_distance=330,
        backstop_distance=55)   # Clem, unchanged; Seamheads 52
    stadium.sections = _make_comerica_park_sections()
    _apply_sourced_params(stadium, 'comerica_park')
    return stadium

def daikin_park():
    stadium = Stadium(
        name='Daikin Park', city='Houston', team='Houston Astros',
        altitude_ft=30, avg_temperature_f=82,
        lf_distance=315, cf_distance=409, rf_distance=326,
        backstop_distance=49,   # Clem; Seamheads and Wikipedia agree (was 54)
    )
    stadium.sections = _make_daikin_park_sections()
    _apply_sourced_params(stadium, 'minute_maid')
    return stadium

def kauffman_stadium():
    stadium = Stadium(name='Kauffman Stadium', city='Kansas City', team='Kansas City Royals',
        altitude_ft=750, avg_temperature_f=77,
        lf_distance=330, cf_distance=410, rf_distance=330,
        backstop_distance=45)   # Clem + Seamheads post-1999 (was 55); Wikipedia's 60 is as-built
    stadium.sections = _make_kauffman_stadium_sections()
    _apply_sourced_params(stadium, 'kauffman_stadium')
    return stadium

def angel_stadium():
    stadium = Stadium(name='Angel Stadium', city='Anaheim', team='Los Angeles Angels',
        altitude_ft=160, avg_temperature_f=75,
        lf_distance=330, cf_distance=400, rf_distance=330,
        backstop_distance=56)   # Clem park page, 1999- era (was 55); table 59, Seamheads 60
    stadium.sections = _make_angel_stadium_sections()
    _apply_sourced_params(stadium, 'angel_stadium')
    return stadium

def citi_field():
    stadium = Stadium(
        name='Citi Field', city='New York', team='New York Mets',
        altitude_ft=54, avg_temperature_f=75,
        lf_distance=335, cf_distance=408, rf_distance=330,
        backstop_distance=46,   # Clem + Seamheads (was the default 55)
    )
    stadium.sections = _make_citi_field_sections()
    _apply_sourced_params(stadium, 'citi_field')
    return stadium

def sutter_health_park():
    """Sutter Health Park — SECTION GEOMETRY UNSOURCED.

    Neither Clem nor Seamheads publishes a foul-territory area for this park
    (both leave the cell blank) and no overhang figures exist, so the bands
    keep the shared template's proportions: neither the radial scale nor the
    overhang pull-in runs here. What does run is the backstop anchor, off
    Clem's sourced "(58)" — the longest in the fleet — which pushes the whole
    bowl back 18.0 ft, the second-largest shift of the 31.
    """
    stadium = Stadium(name='Sutter Health Park', city='Sacramento', team='Athletics',
        altitude_ft=33, avg_temperature_f=80,
        lf_distance=330, cf_distance=403, rf_distance=325,
        backstop_distance=58)   # Clem's estimate "(58)"; Seamheads and Wikipedia agree (was 55)
    stadium.sections = _make_sutter_health_sections()
    _apply_sourced_params(stadium, 'oakland_coliseum')
    return stadium

def las_vegas_ballpark():
    """Las Vegas Ballpark — the Athletics' secondary home park in 2026.

    Six of the club's 2026 home dates are here rather than at Sutter Health
    Park. Field dimensions and altitude are real; the seating geometry is an
    analogue of Sutter Health Park's — see _make_las_vegas_ballpark_sections.

    EVERY PARK PARAMETER IS UNSOURCED. No source publishes a foul-territory
    area, backstop distance or deck configuration for this park: it is not in
    Clem's registry, not in Seamheads, and Wikipedia gives none of the three.
    Neither the radial scale nor the overhang pull-in runs here.

    The backstop anchor does, and this is the one place in the file where an
    unsourced number moves geometry: the bowl is pinned to `backstop_distance`
    below, which nobody has published. It is done anyway because the anchor
    encodes a physical constraint — seats cannot stand in front of the fence
    that protects them — rather than a park-to-park difference, and leaving
    this park alone would mean deliberately keeping a geometry the rest of the
    file treats as impossible. The 15.2 ft shift it produces is an artefact of
    an unsourced 52, not a finding about Las Vegas.
    """
    stadium = Stadium(name='Las Vegas Ballpark', city='Las Vegas', team='Athletics',
        altitude_ft=2030, avg_temperature_f=88,
        lf_distance=328, cf_distance=415, rf_distance=328,
        backstop_distance=52)   # UNSOURCED — no published figure exists
    stadium.sections = _make_las_vegas_ballpark_sections()
    _apply_sourced_params(stadium, 'las_vegas_ballpark')
    return stadium

def pnc_park():
    stadium = Stadium(name='PNC Park', city='Pittsburgh', team='Pittsburgh Pirates',
        altitude_ft=730, avg_temperature_f=73,
        lf_distance=325, cf_distance=399, rf_distance=320,
        backstop_distance=51)   # Clem; Seamheads and Wikipedia agree (was 54)
    stadium.sections = _make_pnc_park_sections()
    _apply_sourced_params(stadium, 'pnc_park')
    return stadium

def petco_park():
    stadium = Stadium(name='Petco Park', city='San Diego', team='San Diego Padres',
        altitude_ft=13, avg_temperature_f=72,
        lf_distance=334, cf_distance=396, rf_distance=322,
        backstop_distance=45)   # Clem + Seamheads, and Clem's prose (was 55)
    stadium.sections = _make_petco_park_sections()
    _apply_sourced_params(stadium, 'petco_park')
    return stadium

def oracle_park():
    stadium = Stadium(
        name='Oracle Park', city='San Francisco', team='San Francisco Giants',
        altitude_ft=63, avg_temperature_f=65,
        lf_distance=339, cf_distance=399, rf_distance=309,
        backstop_distance=54,   # Clem table + Seamheads (was 55); Wikipedia 48
    )
    stadium.sections = _make_oracle_park_sections()
    _apply_sourced_params(stadium, 'oracle_park')
    return stadium

def tmobile_park():
    stadium = Stadium(name='T-Mobile Park', city='Seattle', team='Seattle Mariners',
        altitude_ft=17, avg_temperature_f=65,
        lf_distance=331, cf_distance=405, rf_distance=326,
        backstop_distance=56)   # Clem (was 55, Seamheads); the club publishes 69
    stadium.sections = _make_tmobile_park_sections()
    _apply_sourced_params(stadium, 'tmobile_park')
    return stadium

def busch_stadium():
    stadium = Stadium(name='Busch Stadium', city='St. Louis', team='St. Louis Cardinals',
        altitude_ft=465, avg_temperature_f=77,
        lf_distance=336, cf_distance=400, rf_distance=335,
        backstop_distance=52)   # Clem + Seamheads (was the default 55)
    stadium.sections = _make_busch_stadium_sections()
    _apply_sourced_params(stadium, 'busch_stadium')
    return stadium

def tropicana_field():
    stadium = Stadium(
        name='Tropicana Field', city='St. Petersburg', team='Tampa Bay Rays',
        altitude_ft=45, avg_temperature_f=72,
        lf_distance=315, cf_distance=404, rf_distance=322,
        backstop_distance=50,   # Clem; Seamheads and Wikipedia agree (was 55)
    )
    stadium.sections = _make_tropicana_field_sections()
    _apply_sourced_params(stadium, 'tropicana_field')
    return stadium

def globe_life():
    stadium = Stadium(name='Globe Life Field', city='Arlington', team='Texas Rangers',
        altitude_ft=616, avg_temperature_f=78,
        lf_distance=329, cf_distance=407, rf_distance=326,
        backstop_distance=42)   # Clem; Seamheads and Wikipedia agree. Shortest in MLB (was 55)
    stadium.sections = _make_globe_life_sections()
    _apply_sourced_params(stadium, 'globe_life')
    return stadium

def rogers_centre():
    stadium = Stadium(name='Rogers Centre', city='Toronto', team='Toronto Blue Jays',
        altitude_ft=250, avg_temperature_f=72,
        lf_distance=328, cf_distance=400, rf_distance=328,
        backstop_distance=54)   # Clem + Seamheads (was 55); Wikipedia 60
    stadium.sections = _make_rogers_centre_sections()
    _apply_sourced_params(stadium, 'rogers_centre')
    return stadium

def target_field():
    stadium = Stadium(name='Target Field', city='Minneapolis', team='Minnesota Twins',
        altitude_ft=815, avg_temperature_f=72,
        lf_distance=339, cf_distance=404, rf_distance=328,
        backstop_distance=45)   # Clem park page, flagged as his estimate (was 55); table 48
    stadium.sections = _make_target_field_sections()
    _apply_sourced_params(stadium, 'target_field')
    return stadium

def rate_field():
    stadium = Stadium(name='Rate Field', city='Chicago', team='Chicago White Sox',
        altitude_ft=595, avg_temperature_f=73,
        lf_distance=330, cf_distance=400, rf_distance=335,
        backstop_distance=60)   # Clem; Seamheads and Wikipedia agree. Longest in MLB (was 55)
    stadium.sections = _make_rate_field_sections()
    _apply_sourced_params(stadium, 'guaranteed_rate')
    return stadium

def loan_depot():
    stadium = Stadium(name='loanDepot park', city='Miami', team='Miami Marlins',
        altitude_ft=15, avg_temperature_f=83,
        lf_distance=340, cf_distance=400, rf_distance=335,
        backstop_distance=50)   # Clem (was 55); Seamheads and Wikipedia both 47
    stadium.sections = _make_loan_depot_sections()
    _apply_sourced_params(stadium, 'loan_depot')
    return stadium

def american_family():
    stadium = Stadium(name='American Family Field', city='Milwaukee', team='Milwaukee Brewers',
        altitude_ft=600, avg_temperature_f=72,
        lf_distance=344, cf_distance=400, rf_distance=345,
        backstop_distance=56)   # Clem; Seamheads and Wikipedia agree (was 55)
    stadium.sections = _make_american_family_sections()
    _apply_sourced_params(stadium, 'american_family')
    return stadium

def nationals_park():
    stadium = Stadium(name='Nationals Park', city='Washington', team='Washington Nationals',
        altitude_ft=30, avg_temperature_f=77,
        lf_distance=336, cf_distance=403, rf_distance=335,
        backstop_distance=45)   # Clem + Seamheads (was the default 55)
    stadium.sections = _make_nationals_park_sections()
    _apply_sourced_params(stadium, 'nationals_park')
    return stadium


STADIUMS = {
    'yankee_stadium': yankee_stadium,
    'fenway_park': fenway_park,
    'dodger_stadium': dodger_stadium,
    'wrigley_field': wrigley_field,
    'coors_field': coors_field,
    'chase_field': chase_field,
    'truist_park': truist_park,
    'camden_yards': camden_yards,
    'citizens_bank': citizens_bank,
    'great_american': great_american,
    'progressive_field': progressive_field,
    'comerica_park': comerica_park,
    'minute_maid': daikin_park,
    'kauffman_stadium': kauffman_stadium,
    'angel_stadium': angel_stadium,
    'citi_field': citi_field,
    # Key kept as 'oakland_coliseum' for URL and golden-fixture compatibility;
    # the Athletics have not played in Oakland since 2024. Their primary 2026
    # home is Sutter Health Park, with six dates at Las Vegas Ballpark below.
    'oakland_coliseum': sutter_health_park,
    'las_vegas_ballpark': las_vegas_ballpark,
    'pnc_park': pnc_park,
    'petco_park': petco_park,
    'oracle_park': oracle_park,
    'tmobile_park': tmobile_park,
    'busch_stadium': busch_stadium,
    'tropicana_field': tropicana_field,
    'globe_life': globe_life,
    'rogers_centre': rogers_centre,
    'target_field': target_field,
    'guaranteed_rate': rate_field,
    'loan_depot': loan_depot,
    'american_family': american_family,
    'nationals_park': nationals_park,
}
