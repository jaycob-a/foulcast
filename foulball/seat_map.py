"""
Printed seat labels <-> model zones.

WHY THIS MODULE EXISTS
======================

`foulball/stadium.py` carries two very different classes of information, and
its MODULE PROVENANCE block is explicit about which is which:

  - The six geometry numbers on every `SeatSection` (`distance_min/max`,
    `angle_min/max`, `height_min/max`) are **estimated**. Not surveyed, not
    digitized. Since Step 9 the two distances are positioned per park by
    published foul-area, backstop and overhang figures, so they are no longer
    invented — but the four angles and heights still come from one shared
    template at all 31 parks, and the bowl's *shape* is entirely unsourced.
  - The section *names* and deck levels **track real seating charts**. Every
    one of the 344 sections in the file carries a printed-section range in its
    name — `(Sec 109-114)`, `(Sec FB17-FB29)`, `(Sec 12L-14R)`.

A fan logging a foul ball can read the number printed on their own section
sign. That number is a fact about the physical stadium. The zone it currently
falls into is an estimate. So the log stores **both**, and this module is the
only place the two are joined.

Storing the printed label is what makes the log able to correct zone
boundaries later rather than only score the current ones. If observations were
stored as zone IDs alone, every observation would inherit the boundary
estimate it was supposed to test, and re-cutting the boundaries would
retroactively invalidate the whole log. Printed labels survive a re-cut;
zone IDs do not.

`zone_map_fingerprint()` stamps each logged observation with a hash of the
park's section table. When `stadium.py` changes, old rows keep their old
stamp, so a later analysis can tell which mapping produced which row instead
of silently re-reading history through the new one.

SIDE ANCHORS
============

The second half of this module holds `SIDE_ANCHORS` — every source in the repo
that names a **foul-line side** next to a **printed section number** — and
`check_side_anchors`, which tests a park's zone table against them.

It lives here rather than in `netting.py` because a side anchor is a statement
about labels and zones, which is this module's subject, and not about netting.
`netting._check_join` calls it as its fifth guard, but the check is deliberately
usable on its own: Sutter Health Park has no netting source of any kind and is
still testable this way.

What it is for: catching a zone table whose 1B and 3B label ranges are swapped.
Nothing else in the repo can. See the comment block above `SIDE_ANCHORS` for
why the netting guards are all blind to a mirror, and why a published netting
extent — however asymmetric — cannot substitute for a source that says "1B".

WHAT THIS MODULE DOES NOT ESTABLISH
===================================

That a printed section belongs to a zone's *number range* says nothing about
whether the zone's distance/angle bands are right. The ranges come from the
same names the provenance block calls real, but the bands they are attached to
do not. This module improves the bookkeeping, not the geometry.

The same caveat binds the side anchors, and harder. An anchor that passes says
the table is not mirrored. It does not say the zone boundaries are right, that
the behind-plate block is in the right place, or that the sections exist. Every
one of the eleven parks in `MAP_FINDINGS.md` disagrees with its zone table
in some way; four of them disagree by a mirror.
"""
import hashlib
import re
from dataclasses import dataclass

# Bumped by hand when the *interpretation* of printed labels changes.
# Park table changes are caught by the per-park fingerprint instead.
SEAT_MAP_VERSION = "1"

# Matches the "(Sec ...)" body every section name in stadium.py carries.
_SEC_BODY = re.compile(r"\(Sec\s+([^)]+)\)", re.IGNORECASE)

# One endpoint of a printed range: optional alpha prefix, digits, optional
# alpha suffix. Covers "109", "FB17", "12R".
_ENDPOINT = re.compile(r"^([A-Za-z]*)(\d+)([A-Za-z]*)$")


@dataclass(frozen=True)
class PrintedRange:
    """An inclusive range of printed section labels, e.g. FB17..FB29."""
    prefix: str
    start: int
    end: int
    suffixes: tuple[str, ...]
    raw: str

    def labels(self) -> list[str]:
        """Every printed label this range covers, normalized."""
        out = []
        for n in range(self.start, self.end + 1):
            for suf in self.suffixes:
                out.append(normalize_label(f"{self.prefix}{n}{suf}"))
        return out

    def display(self) -> str:
        return self.raw


def normalize_label(label: str) -> str:
    """Canonical form of a printed section label.

    Fans type "sec 214", "214", " 214 " and "Section 214" for the same seat.
    Everything upper-cases, loses whitespace/punctuation, and loses a leading
    SEC/SECTION word.
    """
    if label is None:
        return ""
    s = str(label).strip().upper()
    s = re.sub(r"[^A-Z0-9]", "", s)
    # Strip a leading SECTION/SECT/SEC with no word boundary required, because
    # "SECTION214" survives the punctuation strip above as one token. Longest
    # first. No park in stadium.py prefixes a section with S, so this cannot
    # eat a real label.
    s = re.sub(r"^(SECTION|SECT|SEC)(?=[0-9A-Z])", "", s)
    return s


def parse_printed_ranges(section_name: str) -> list[PrintedRange]:
    """Pull printed-section ranges out of a `SeatSection.name`.

    Handles the four shapes present in stadium.py:
        (Sec 109-114)               plain numeric
        (Sec FB17-FB29)             alpha-prefixed (Fenway)
        (Sec 12L-14R)               left/right suffixed
        (Sec 108-112, Diamond Box)  range plus a descriptive tail

    Descriptive tails are ignored rather than guessed at.
    """
    m = _SEC_BODY.search(section_name or "")
    if not m:
        return []

    ranges = []
    for part in m.group(1).split(","):
        part = part.strip()
        if "-" not in part and "–" not in part:
            # A bare single section, e.g. "(Sec 119)".
            em = _ENDPOINT.match(part)
            if em:
                pre, num, suf = em.group(1), int(em.group(2)), em.group(3)
                ranges.append(PrintedRange(pre.upper(), num, num,
                                           (suf.upper(),), part))
            continue

        lo_raw, hi_raw = re.split(r"[-–]", part, maxsplit=1)
        lo, hi = _ENDPOINT.match(lo_raw.strip()), _ENDPOINT.match(hi_raw.strip())
        if not lo or not hi:
            continue  # descriptive tail like "Diamond Box"

        lo_pre, lo_num, lo_suf = lo.group(1).upper(), int(lo.group(2)), lo.group(3).upper()
        hi_pre, hi_num, hi_suf = hi.group(1).upper(), int(hi.group(2)), hi.group(3).upper()

        if lo_pre != hi_pre or lo_num > hi_num:
            continue  # e.g. "FB9-LB12" — not a range we can enumerate

        # "12L-14R" numbers each seat block twice, once per side of the aisle.
        suffixes = (lo_suf,) if lo_suf == hi_suf else tuple(
            s for s in (lo_suf, hi_suf) if s
        )
        ranges.append(PrintedRange(lo_pre, lo_num, hi_num, suffixes or ("",), part))

    return ranges


def build_printed_index(stadium) -> dict[str, list[str]]:
    """Map every printed label in a park to the zone ID(s) claiming it.

    A label mapping to more than one zone is ambiguous and is resolved by deck
    level at lookup time; if that does not resolve it, the lookup returns None
    rather than picking one. A guessed zone is worse than a missing one — the
    whole point of the log is to hold observations the model cannot fake.
    """
    index: dict[str, list[str]] = {}
    for sec in stadium.sections:
        for rng in parse_printed_ranges(sec.name):
            for label in rng.labels():
                index.setdefault(label, [])
                if sec.section_id not in index[label]:
                    index[label].append(sec.section_id)
    return index


def zone_for_printed_section(stadium, label: str, level: str | None = None,
                             side: str | None = None) -> str | None:
    """Zone ID for a printed section label, or None if unknown/ambiguous.

    None is a first-class answer. A printed section that no zone claims is the
    most informative row in the log: it marks a real seat the park model does
    not cover.
    """
    norm = normalize_label(label)
    if not norm:
        return None
    candidates = build_printed_index(stadium).get(norm, [])
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    by_id = {s.section_id: s for s in stadium.sections}
    if level:
        narrowed = [c for c in candidates if by_id[c].level == level]
        if len(narrowed) == 1:
            return narrowed[0]
        candidates = narrowed or candidates
    if side:
        narrowed = [c for c in candidates if by_id[c].side == side]
        if len(narrowed) == 1:
            return narrowed[0]
    return None


def printed_range_display(section) -> str:
    """Human label for the printed range(s) a zone covers, for the log UI."""
    ranges = parse_printed_ranges(section.name)
    return ", ".join(r.display() for r in ranges)


def zone_map_fingerprint(stadium) -> str:
    """Short hash of a park's zone table.

    Covers section IDs, names and the six geometry numbers, so any edit to
    stadium.py that could change where an observation lands changes the
    fingerprint stamped on new rows.
    """
    h = hashlib.sha1()
    for sec in sorted(stadium.sections, key=lambda s: s.section_id):
        h.update("|".join([
            sec.section_id, sec.name, sec.side, sec.level,
            f"{sec.distance_min:g}", f"{sec.distance_max:g}",
            f"{sec.angle_min:g}", f"{sec.angle_max:g}",
            f"{sec.height_min:g}", f"{sec.height_max:g}",
        ]).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()[:12]


def zone_map_version(stadium) -> str:
    """Stamp stored on every logged observation: `<map version>:<park hash>`."""
    return f"{SEAT_MAP_VERSION}:{zone_map_fingerprint(stadium)}"


def zone_catalog(stadium) -> list[dict]:
    """Zone list for the logging UI — one entry per tappable zone."""
    out = []
    for sec in stadium.sections:
        out.append({
            "zone_id": sec.section_id,
            "name": sec.name,
            "side": sec.side,
            "level": sec.level,
            "printed": printed_range_display(sec),
            "num_seats": sec.num_seats,
        })
    return out


# ============================================================
# Side anchors — the only evidence that can catch a mirrored table
# ============================================================
#
# WHY THIS EXISTS
# ---------------
#
# `netting._check_join` has four guards, and a left/right flip survives all
# four. Every park's zone table in `stadium.py` is exactly mirror-symmetric —
# the provenance block says so outright: the angular vocabulary is shared, and
# `1B-FB1` and `3B-FB1` carry identical angles, heights and distances. So
# swapping the two sides' printed labels changes nothing any of G1-G4 measures:
#
#   G1 counts matched labels               — unchanged by a swap
#   G2 tests the HOME zone                 — the plate is on neither side
#   G3 walks each side outward by angle    — the angles are mirror-equal, so
#                                            the same profile appears on the
#                                            other side and still descends
#   G4 tests below/above the plate's span  — a swap maps 'below' to 'above' on
#                                            the other side; neither straddle
#                                            nor plate_at_end changes
#
# Oriole Park is the case that exposed this: its seating map shows the lower
# bowl ascending toward third base, the zone table has it ascending toward
# first, and the park is nonetheless `status='mapped'`. Symmetric geometry
# cannot detect a mirror; only an asymmetric fact can.
#
# WHAT COUNTS AS AN ASYMMETRIC FACT
# ---------------------------------
#
# Exactly one thing: a source that names a **side** next to a **section
# number**. Three families of them exist in this repo, and nothing else does:
#
#   1. Netting pages that name the side of an endpoint. "section 40 (1B) and
#      section 41 (3B)" (Dodgers), "Sections 113C and 130C respectively" after
#      "the first and third baseline walls" (Blue Jays), "Section 116 (1B line)
#      and Section 142 (3B line)" (Tigers).
#   2. Netting pages that name a **side-bearing product**. Busch's "Lower RF
#      Box 132-134" places 132-134 in right field, and right field is the 1B
#      side. Busch's own "1B Field Box"/"3B Field Box" rows are the same kind
#      of statement.
#   3. Seating maps read directly, where a landmark fixes the orientation and
#      the numbers can then be read off each foul line. See `MAP_FINDINGS.md`
#      for the eleven read so far, including which landmark fixed each one.
#
# A published netting *extent* on its own is not such a fact, however
# asymmetric it is. "Sections 6 → 70" tells you the run is longer on one side
# of the plate than the other; it does not tell you which side that is. That
# asymmetry is real and useless here, and it is why this check has thin
# coverage rather than universal coverage.
#
# Dugout locations are the same story. Which side a club's dugout sits on does
# differ by park and would anchor the sides — but it only helps once some
# source ties that dugout to section numbers. One park in this repo has that
# (Fenway, and only from an unverified compilation), so it is carried at
# `secondary_unverified` strength and can flag but never reject.
#
# WHAT AN ANCHOR DOES NOT ESTABLISH
# ---------------------------------
#
# That the zone *boundaries* are right. An anchor says "printed section N is on
# the 1B side"; it cannot say which zone N should fall in, how far from the
# plate it sits, or where the behind-plate block starts and ends. Truist Park
# passes every anchor below and its plate zone is still four sections up the
# third-base line. A park that passes has failed to be mirrored — nothing more.

# How much weight an anchor carries.
#   'primary'               the club's own page named the side
#   'map_read'              read off a published seating map at magnification,
#                           with the landmark that fixed the orientation named
#   'secondary_unverified'  a compilation nobody could confirm on a primary page
ANCHOR_KINDS = ('primary', 'map_read', 'secondary_unverified')

# Anchors at these strengths are allowed to reject a join. An unverified
# compilation is not: it can raise a flag and nothing more.
DECIDING_ANCHOR_KINDS = frozenset({'primary', 'map_read'})


@dataclass(frozen=True)
class SideAnchor:
    """A source statement putting printed sections on a named foul-line side.

    `raw` is the source's own wording, kept verbatim so the entry can be
    checked without decoding this dataclass — same discipline as
    `netting.NettedRange`. `basis` records the reasoning where turning the
    wording into a side took one (a product name implying a side, a landmark
    fixing a map's orientation); it is empty when the source said "1B" or "3B"
    in those words.
    """
    prefix: str
    start: int
    end: int
    side: str                   # '1B' or '3B'
    raw: str
    source: str
    source_kind: str
    retrieved: str
    basis: str = ''

    def numbers(self) -> range:
        return range(self.start, self.end + 1)


@dataclass(frozen=True)
class SideCheck:
    """Result of testing one park's zone table against its side anchors.

    `status` is one of:
      'ok'          every anchored label lands on the side its source names
      'flipped'     every anchored label lands on the opposite side
      'inconsistent' some agree and some do not — not a clean mirror, so the
                    table is wrong in a way a swap would not fix
      'untestable'  no anchor, or no anchored label that any zone claims
    """
    park_key: str
    status: str
    agree: tuple[str, ...] = ()
    disagree: tuple[str, ...] = ()
    unmatched: tuple[str, ...] = ()
    detail: str = ''
    # True when a deciding-strength anchor drove the verdict. A 'flipped' on
    # secondary evidence alone must not reject a join.
    deciding: bool = False


SIDE_ANCHORS: dict[str, tuple[SideAnchor, ...]] = {

    # --- Family 1: the club's netting page names the side ------------------

    'dodger_stadium': (
        SideAnchor('FD', 40, 40, '1B',
                   'end of baseline section 40 (1B)',
                   'https://www.mlb.com/dodgers/ballpark/netting',
                   'primary', '2026-08-09',
                   basis='the club gives bare numbers and the model numbers '
                         'the same field boxes FD; see the netting entry\'s '
                         'series_corroborated for why the two are one series'),
        SideAnchor('FD', 41, 41, '3B',
                   'section 41 (3B)',
                   'https://www.mlb.com/dodgers/ballpark/netting',
                   'primary', '2026-08-09'),
    ),

    'comerica_park': (
        SideAnchor('', 116, 116, '1B', 'Section 116 (1B line)',
                   'https://www.mlb.com/tigers/ballpark/netting',
                   'primary', '2026-08-09'),
        SideAnchor('', 142, 142, '3B', 'Section 142 (3B line)',
                   'https://www.mlb.com/tigers/ballpark/netting',
                   'primary', '2026-08-09'),
    ),

    'rogers_centre': (
        SideAnchor('', 113, 113, '1B',
                   'down the first and third baseline walls to Sections 113C '
                   'and 130C respectively',
                   'https://www.mlb.com/bluejays/ballpark/netting',
                   'primary', '2026-08-09',
                   basis='"respectively" binds 113C to the first baseline; '
                         'the C suffix splits one printed section across an '
                         'aisle and is dropped, per _zone_numbers'),
        SideAnchor('', 130, 130, '3B',
                   'down the first and third baseline walls to Sections 113C '
                   'and 130C respectively',
                   'https://www.mlb.com/bluejays/ballpark/netting',
                   'primary', '2026-08-09',
                   basis='"respectively" binds 130C to the third baseline'),
    ),

    'yankee_stadium': (
        SideAnchor('', 11, 11, '1B', 'Section 011 (1B/RF side)',
                   'https://www.mlb.com/yankees/ballpark/netting',
                   'primary', '2026-08-09'),
        SideAnchor('', 29, 29, '3B', 'Section 029 (3B/LF side)',
                   'https://www.mlb.com/yankees/ballpark/netting',
                   'primary', '2026-08-09'),
    ),

    # --- Family 2: the club names a side-bearing product -------------------

    'busch_stadium': (
        SideAnchor('', 135, 140, '1B', '1B Field Box 135-140',
                   'https://www.mlb.com/cardinals/ballpark/netting',
                   'primary', '2026-08-09'),
        SideAnchor('', 161, 165, '3B', '3B Field Box 161-165',
                   'https://www.mlb.com/cardinals/ballpark/netting',
                   'primary', '2026-08-09'),
        SideAnchor('', 132, 134, '1B', 'Lower RF Box 132-134',
                   'https://www.mlb.com/cardinals/ballpark/netting',
                   'primary', '2026-08-09',
                   basis='right field is the first-base side; the club names '
                         'the product, not the side, so this is one inference '
                         'step past the wording'),
    ),

    # Petco's netting page names both sides, but the two runs it names overlap
    # (111-115 "1B side" and 112-116 "3B side" share 112-115). A label cannot
    # be on both foul lines, so the wording is either describing net panels
    # rather than sides or the numbering interleaves in a way nothing here
    # explains. Recorded so the gap is visible, and deliberately not turned
    # into anchors: `_overlapping_prefixes` makes this park untestable rather
    # than letting a half-read of an ambiguous sentence reject a join.
    'petco_park': (
        SideAnchor('', 111, 115, '1B',
                   'angled net coverage 111-115 (1B side)',
                   'https://www.mlb.com/padres/ballpark/netting',
                   'primary', '2026-08-09'),
        SideAnchor('', 112, 116, '3B',
                   'angled net coverage 112-116 (3B side)',
                   'https://www.mlb.com/padres/ballpark/netting',
                   'primary', '2026-08-09'),
    ),

    # --- Family 3: read off a published seating map ------------------------
    #
    # Each entry names the landmark that fixed the map's orientation, because
    # that landmark is the whole basis for the side claim. See MAP_FINDINGS.md.

    'camden_yards': (
        SideAnchor('', 20, 34, '1B',
                   'lower bowl descending from the plate at 36/38 toward the '
                   'right-field corner',
                   'seating_maps/oriole_park.jfif (Orioles seating map)',
                   'map_read', '2026-08-11',
                   basis='orientation fixed by the B&O Warehouse and the "RF '
                         'PORCH" label, both on the same side of the frame; '
                         'the render is isometric, viewed from beyond the '
                         'outfield, so left/right are reversed from a plan '
                         'view and the landmarks are what settle it'),
        SideAnchor('', 40, 58, '3B',
                   'lower bowl ascending from the plate at 36/38 toward the '
                   'left-field corner',
                   'seating_maps/oriole_park.jfif (Orioles seating map)',
                   'map_read', '2026-08-11',
                   basis='same landmarks as the 1B anchor above'),
    ),

    'truist_park': (
        SideAnchor('', 116, 120, '1B',
                   '100 level descending from the plate at 125/126 toward the '
                   'right-field corner',
                   'seating_maps/truist_park.png (Braves seating map)',
                   'map_read', '2026-08-11',
                   basis='flat plan, standard orientation; corroborated by the '
                         'Chop House (right field) sitting beyond section 107'),
        SideAnchor('', 135, 143, '3B',
                   '100 level ascending from the plate at 125/126 toward the '
                   'left-field corner',
                   'seating_maps/truist_park.png (Braves seating map)',
                   'map_read', '2026-08-11',
                   basis='same map; Home Run Porch Low (left field) sits '
                         'beyond section 143'),
    ),

    'chase_field': (
        SideAnchor('', 106, 118, '1B',
                   '100 level descending from the plate at 122/123 toward the '
                   'right-field corner',
                   'seating_maps/chase_field.jpg (Diamondbacks seating map)',
                   'map_read', '2026-08-11',
                   basis='orientation fixed by the D-backs pool and "Home Run '
                         'Porch R", both on the same side; the map\'s dugout '
                         'labels are not used, as they read the other way'),
        SideAnchor('', 127, 138, '3B',
                   '100 level ascending from the plate at 122/123 toward the '
                   'left-field corner',
                   'seating_maps/chase_field.jpg (Diamondbacks seating map)',
                   'map_read', '2026-08-11',
                   basis='same landmarks as the 1B anchor above'),
    ),

    'oakland_coliseum': (
        SideAnchor('', 105, 110, '1B',
                   'lower bowl descending from the plate at 112 toward the '
                   'right-field corner',
                   'seating_maps/sutter_health.jpg (Athletics seating map)',
                   'map_read', '2026-08-11',
                   basis='flat plan; orientation fixed by the base markers '
                         '(third base left, first base right), not by the '
                         'dugout labels, which read the other way. This also '
                         'resolves the MLB.com vs A View From My Seat conflict '
                         'recorded in SOURCED_DATA.md in MLB.com\'s favour: '
                         'the plate is at 112, inside MLB.com\'s 108-116'),
        SideAnchor('', 114, 123, '3B',
                   'lower bowl ascending from the plate at 112 toward the '
                   'left-field corner',
                   'seating_maps/sutter_health.jpg (Athletics seating map)',
                   'map_read', '2026-08-11',
                   basis='same map; the bowl ends at 123'),
    ),

    'fenway_park': (
        SideAnchor('FB', 19, 39, '1B',
                   'Field Box descending from the plate at FB46 toward the '
                   'right-field corner',
                   'seating_maps/fenway_park.jpg (Red Sox seating map)',
                   'map_read', '2026-08-11',
                   basis='orientation fixed by the "Red Sox"/"Visitor" dugout '
                         'labels and the "First Base SRO"/"Third Base SRO" '
                         'banners, which agree. The map is 800px wide and only '
                         'about half the Field Box wedges carry a legible '
                         'label, so the range is anchored on the ones that do'),
        SideAnchor('FB', 49, 82, '3B',
                   'Field Box ascending from the plate at FB46 toward the '
                   'left-field corner',
                   'seating_maps/fenway_park.jpg (Red Sox seating map)',
                   'map_read', '2026-08-11',
                   basis='same map and banners'),
        # The independent dugout statement, at the strength the source has.
        # It agrees with the map read above, which is worth recording: two
        # unrelated sources putting the low Field Box numbers on 1B.
        SideAnchor('FB', 21, 28, '1B',
                   "the Red Sox dugout fronts sections 21-28",
                   'fromthisseat.com / TickPick, via web-search summary '
                   '(SOURCED_DATA.md Part 1, Fenway)',
                   'secondary_unverified', '2026-08-09',
                   basis='the Red Sox dugout is on the first-base side. '
                         'SOURCED_DATA.md could not confirm this on a primary '
                         'page and flags a nearby search summary as '
                         'demonstrably wrong, so it can flag but never reject'),
        SideAnchor('FB', 62, 69, '3B',
                   "the visitors' dugout fronts sections 62-69",
                   'fromthisseat.com / TickPick, via web-search summary '
                   '(SOURCED_DATA.md Part 1, Fenway)',
                   'secondary_unverified', '2026-08-09',
                   basis='the visiting dugout at Fenway is on the third-base '
                         'side; same unverified source as above'),
    ),
    # --- Family 3, second read (2026-09-07): the six parks that were flagged
    # "sides untested" because their published extent is a bare numeric arc.
    # Read the same way as the five above; see MAP_FINDINGS.md, Step 12.

    'coors_field': (
        SideAnchor('', 110, 127, '1B',
                   'lower bowl descending from the plate block 128-132 toward '
                   'the right-field corner: 127 126 ... 120 (Infield Box), '
                   '119-116 (Outfield Box), 115-111 (Corner Outfield Box), '
                   '110-105 (Right Field Box)',
                   'seating_maps/coors_field.jpg (Rockies seating map)',
                   'map_read', '2026-09-07',
                   basis='flat plan, plate at lower left. Orientation fixed by '
                         'the map\'s own legend: the "Right Field Box" colour '
                         'is on 105-110 and "Right Field Mezzanine" on '
                         '201-209, both at the low-numbered end. Corroborated '
                         'by the foul-pole distances printed on the field '
                         '(347\' beside 150/151, 350\' beside 109/110; Coors\' '
                         'left-field line is the shorter of the two) and by '
                         'the "Rockies Dugout" label along 120-126. The 200 '
                         'and 300 levels run the same way: 214-227 and '
                         '314-321 on this side, 234-247 and 326-347 on the '
                         'other'),
        SideAnchor('', 133, 150, '3B',
                   'lower bowl ascending from the plate block 128-132 toward '
                   'the left-field corner: 133 134 135 (Infield Box), '
                   '136-141 (Midfield Box), 142-150 (Outfield / Corner '
                   'Outfield Box)',
                   'seating_maps/coors_field.jpg (Rockies seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks as the 1B anchor above; the '
                         '"Visitors Dugout" label runs along 136-139'),
    ),

    'citizens_bank': (
        SideAnchor('', 101, 118, '1B',
                   'lower bowl descending toward the right-field corner: '
                   '118 117 116 115 (beyond the 119-121 shoulder of the '
                   'behind-plate arc) ... 102 101',
                   'seating_maps/citizensbank_park.jpg (Phillies seating map)',
                   'map_read', '2026-09-07',
                   basis='flat plan, plate at bottom. Orientation fixed by the '
                         'map\'s own "FIRST BASE GATE" (right of frame) and '
                         '"THIRD BASE GATE" (left) labels; the "Phillies" '
                         'dugout on the right and "VISITORS" on the left '
                         'agree. The lettered Diamond Club A-G sits directly '
                         'behind the plate with 122-125 behind it; 119-121 '
                         'and 126-128 are the two shoulders and are left out '
                         'of the anchors. 640px source, read at 3x'),
        SideAnchor('', 129, 148, '3B',
                   'lower bowl ascending toward the left-field corner: 129 '
                   '130 131 132 (Infield Box) 133-135 136-139 140-148',
                   'seating_maps/citizensbank_park.jpg (Phillies seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks as the 1B anchor above'),
    ),

    'great_american': (
        SideAnchor('', 101, 118, '3B',
                   'lower bowl ascending from the plate toward the left-field '
                   'corner: 113-118 stacked along the third-base line '
                   '(Infield Box), 106-112 (Field Box), 101-105 (Terrace '
                   'Outfield)',
                   'seating_maps/great_american.png (Reds seating map)',
                   'map_read', '2026-09-07',
                   basis='flat plan, plate at lower left. Orientation fixed by '
                         'the legend\'s "Sun Deck/Moon Deck" colour on 140-144 '
                         'at the far end of the high-numbered line (the '
                         'Sun/Moon Deck is Great American\'s right-field '
                         'deck) and by the drawn diamond, whose first-base '
                         'corner is the lower-right one. The premium wedges '
                         '1-5 and 22-25 sit dead behind the plate, with '
                         '122-126 behind them; 119-121 and 127 flank. '
                         '1024px source, read at 4x'),
        SideAnchor('', 127, 139, '1B',
                   'lower bowl descending toward the right-field corner: '
                   '127 128 ... 133 (Infield Box), 134-137 (Field Box), '
                   '138-139, then the Sun/Moon Deck 140-144',
                   'seating_maps/great_american.png (Reds seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks as the 3B anchor above'),
    ),

    'progressive_field': (
        SideAnchor('', 103, 113, '1B',
                   'right-field corner, Lower Reserved / Lower Box Outfield: '
                   '103 107 108 109 111 113',
                   'seating_maps/progressive_field.png (Guardians seating map)',
                   'map_read', '2026-09-07',
                   basis='flat plan, plate at lower left. Orientation fixed by '
                         'the map\'s own "LEFT FIELD DISTRICT" (left of '
                         'frame) and "RIGHT FIELD DISTRICT" / "RIGHT FIELD '
                         'GATE" (right) labels; the "HOME DUGOUT" along '
                         '158-165 and "AWAY DUGOUT" along 138-142 agree'),
        SideAnchor('', 117, 131, '1B',
                   'first-base line descending toward the corner: 131 130 '
                   '129 128 125 117 (only these six carry a label; '
                   '118-124 and 126-127 do not appear)',
                   'seating_maps/progressive_field.png (Guardians seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks. Deliberately stops at 131: the '
                         'numbers 134 through 150 are printed twice on this '
                         'map, once on the first-base field boxes (134 136 '
                         '138 ... 148 149 150) and once on the third-base '
                         'suite columns (132-162), so a bare label in that '
                         'range is on both lines and cannot anchor'),
        SideAnchor('', 153, 179, '3B',
                   'lower bowl ascending from the plate block 150-152 '
                   '(Lexus Carnegie Club 1-4 behind it) toward the '
                   'left-field corner: 153 154 ... 158 (Field Box), 159-164 '
                   '165-174 (Lower Box), 175 178 179',
                   'seating_maps/progressive_field.png (Guardians seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks. 153-162 are also suite numbers on '
                         'this map, but the suites carrying them are on this '
                         'same side, so the label is on the third-base line '
                         'whichever product it names'),
    ),

    'oracle_park': (
        SideAnchor('', 101, 112, '1B',
                   'lower bowl descending from the plate block 113-118 toward '
                   'the right-field corner: 112 110 109 108 107 (Field Club) '
                   '106 105 104 (Lower Box) 103 102 101',
                   'seating_maps/oracle_park.jpg (Giants seating map)',
                   'map_read', '2026-09-07',
                   basis='flat plan, plate at bottom. Orientation fixed by the '
                         'map\'s own legend: "Arcade" and "Coors Light Cove" '
                         'colours on 145-152 beyond the low-numbered end (the '
                         'arcade is the right-field wall over McCovey Cove), '
                         'and "Club Left Field" / "View Reserve Left Field" '
                         'colours on 232-234 and 332-336 beyond the '
                         'high-numbered end. 115 is dead centre behind the '
                         'plate. 640px source, read at 4x'),
        SideAnchor('', 119, 135, '3B',
                   'lower bowl ascending from the plate block 113-118 toward '
                   'the left-field corner: 119 121 122 123 (Field Club) '
                   '124-128 (Lower Box) 129-135 (Lower Box Outfield)',
                   'seating_maps/oracle_park.jpg (Giants seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks as the 1B anchor above'),
    ),

    'guaranteed_rate': (
        SideAnchor('', 108, 129, '1B',
                   'lower bowl descending from the plate at 132 toward the '
                   'right-field corner: 129 128 ... 109 108',
                   'seating_maps/rate_field.gif (White Sox seating map)',
                   'map_read', '2026-09-07',
                   basis='flat plan, plate at bottom, 132 dead centre behind '
                         'the "CIBC Scout Club". Orientation fixed by the '
                         'drawn diamond alone: the plate is at the bottom of '
                         'the frame and the mound above it, so first base is '
                         'on the viewer\'s right. This map names no '
                         'left-field or right-field landmark, so this is the '
                         'least corroborated read of the six; the gate '
                         'numbers around the frame were not relied on'),
        SideAnchor('', 135, 156, '3B',
                   'lower bowl ascending from the plate at 132 toward the '
                   'left-field corner: 135 136 ... 155 156',
                   'seating_maps/rate_field.gif (White Sox seating map)',
                   'map_read', '2026-09-07',
                   basis='same basis as the 1B anchor above'),
    ),

}


def _overlapping_prefixes(anchors) -> set[str]:
    """Prefixes where anchors of opposite sides claim the same number.

    A printed section is on one foul line or the other. When a park's anchors
    say both, the source has been misread or is describing something other
    than sides, and the honest answer is that the park cannot be tested — not
    that whichever anchor sorts first wins.
    """
    bad = set()
    for i, a in enumerate(anchors):
        for b in anchors[i + 1:]:
            if a.prefix != b.prefix or a.side == b.side:
                continue
            if a.start <= b.end and b.start <= a.end:
                bad.add(a.prefix)
    return bad


def _zone_side_for(stadium, prefix: str, number: int) -> str | None:
    """Which foul-line side the zone table puts a printed label on.

    Returns None when no zone claims the label, when only a HOME zone does (the
    plate is on neither side, so it carries no mirror information), or when
    zones on both sides claim it and the tie does not break (ambiguous, and an
    ambiguous label must not decide a flip).

    The tie-break is parity. A few parks number one foul line even and the
    other odd from a shared block — Dodger Stadium's field boxes are FD12-FD24
    on 1B against FD11-FD25 on 3B — so the two ranges overlap as integer
    intervals while sharing no actual section. Where exactly one of the
    claiming ranges has both endpoints of the label's own parity, that range is
    the one that really contains it. This only ever breaks a tie; it never
    creates one, and a range spanning both parities is left alone.
    """
    claims: list[tuple[str, bool]] = []
    for sec in stadium.sections:
        if sec.side not in ('1B', '3B'):
            continue
        for rng in parse_printed_ranges(sec.name):
            if rng.prefix == prefix and rng.start <= number <= rng.end:
                parity_match = (rng.start % 2 == rng.end % 2 == number % 2)
                claims.append((sec.side, parity_match))

    sides = {side for side, _ in claims}
    if len(sides) == 1:
        return sides.pop()
    if not sides:
        return None

    parity_sides = {side for side, matched in claims if matched}
    if len(parity_sides) == 1:
        return parity_sides.pop()
    return None


def check_side_anchors(stadium, park_key: str) -> SideCheck:
    """Test a park's zone table against every side anchor recorded for it.

    This is deliberately independent of the netting join. Anchors are
    statements about labels and sides, not about netting, so a park whose
    netting is a source gap can still be tested — Sutter Health Park has no
    netting source of any kind and is checkable here.
    """
    anchors = SIDE_ANCHORS.get(park_key, ())
    if not anchors:
        return SideCheck(park_key, 'untestable', detail=(
            'no source in this repo names a side alongside a section number '
            'for this park. A published netting extent alone cannot do it: it '
            'gives the run\'s endpoints, not which foul line each end is on'))

    skip = _overlapping_prefixes(anchors)
    if skip:
        return SideCheck(park_key, 'untestable', detail=(
            f'anchors of opposite sides claim the same printed numbers in '
            f'series {sorted(skip)!r}, so the source is not describing sides '
            f'in a way that can be tested'))

    agree, disagree, unmatched = [], [], []
    deciding = False
    for a in anchors:
        for n in a.numbers():
            label = _label_of(a.prefix, n)
            model_side = _zone_side_for(stadium, a.prefix, n)
            if model_side is None:
                unmatched.append(label)
                continue
            # `deciding` means a deciding-strength anchor took part in the
            # verdict, whichever way it went — so an 'ok' from a club page can
            # be told apart from an 'ok' resting only on an unverified
            # compilation, not just a 'flipped'.
            if a.source_kind in DECIDING_ANCHOR_KINDS:
                deciding = True
            entry = f'{label}: source {a.side}, table {model_side}'
            (agree if model_side == a.side else disagree).append(entry)

    if not agree and not disagree:
        return SideCheck(park_key, 'untestable', unmatched=tuple(unmatched),
                         detail=('no anchored printed section is claimed by a '
                                 '1B or 3B zone in this park\'s table, so the '
                                 'anchors have nothing to test against'))

    if disagree and not agree:
        return SideCheck(
            park_key, 'flipped', tuple(agree), tuple(disagree),
            tuple(unmatched), deciding=deciding,
            detail=(f'all {len(disagree)} anchored printed sections land on '
                    f'the opposite side from the one their source names, and '
                    f'none land on the named side. That is a mirrored table: '
                    f'the 1B and 3B label ranges are swapped'))

    if disagree:
        return SideCheck(
            park_key, 'inconsistent', tuple(agree), tuple(disagree),
            tuple(unmatched), deciding=deciding,
            detail=(f'{len(agree)} anchored printed sections land on the side '
                    f'their source names and {len(disagree)} land on the '
                    f'other. A swap would not fix this, so the table is wrong '
                    f'in some way other than a mirror'))

    return SideCheck(park_key, 'ok', tuple(agree), (), tuple(unmatched),
                     deciding=deciding,
                     detail=(f'all {len(agree)} anchored printed sections land '
                             f'on the side their source names. This rules out '
                             f'a mirrored table and nothing else — it says '
                             f'nothing about where the zone boundaries fall'))


def _label_of(prefix: str, number: int) -> str:
    return f'{prefix}{number}'


def side_anchor_audit(stadiums: dict) -> list[SideCheck]:
    """Run `check_side_anchors` across a registry of parks.

    `stadiums` maps park key to a zero-argument factory or a built Stadium.
    Returned in a fixed order: flipped first, then inconsistent, then
    untestable, then ok — worst news at the top.
    """
    rank = {'flipped': 0, 'inconsistent': 1, 'untestable': 2, 'ok': 3}
    out = []
    for key, entry in stadiums.items():
        st = entry() if callable(entry) else entry
        out.append(check_side_anchors(st, key))
    return sorted(out, key=lambda c: (rank[c.status], c.park_key))
