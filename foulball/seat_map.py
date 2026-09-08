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
the behind-plate block is in the right place, or that the sections exist. Of
the seventeen parks read in `MAP_FINDINGS.md`, fourteen disagree with their
zone table in some way and four disagree by a mirror. The other three — Daikin
Park, Yankee Stadium and Dodger Stadium — came out right on the sides *and* the
plate block, which is a stronger result than any anchor here can report: they
were read for both, and the anchor only records the first.
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
#      for the seventeen read so far, including which landmark fixed each one.
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
        # Read off the seating map (2026-09-07). Single sections rather than
        # runs, because this park interleaves the sides by parity and a range
        # spanning both would claim the other line's sections too. These four
        # test the Loge ring, which the netting page never reaches.
        SideAnchor('', 111, 111, '3B',
                   'Loge 111, first odd section up the left-field line from '
                   'the 101/102 pair behind the plate',
                   'seating_maps/dodger_stadium.jpg (Dodgers seating map)',
                   'map_read', '2026-09-07',
                   basis='flat plan, plate at the bottom. Orientation fixed '
                         'by the map\'s own SPECTRUM LEFT FIELD PAVILION '
                         '(odd 301-315, upper left) and RIGHT FIELD PAVILION '
                         '(even 302-316, upper right) headings. Every ring '
                         'runs odd to the left and even to the right from a '
                         'pair behind the plate - 1/2 at field level, '
                         '101/102 on the Loge, 1/2 again on the Reserve and '
                         'Top Deck - so the parity is the side. The DODGER '
                         'DUGOUT label sits on the odd side and the VISITORS '
                         'DUGOUT on the even side, which agrees'),
        SideAnchor('', 112, 112, '1B',
                   'Loge 112, first even section down the right-field line '
                   'from the 101/102 pair behind the plate',
                   'seating_maps/dodger_stadium.jpg (Dodgers seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks as the 3B anchor above'),
        SideAnchor('', 135, 135, '3B',
                   'Loge 135, well up the left-field line; the ring runs on '
                   'to 167 on this side',
                   'seating_maps/dodger_stadium.jpg (Dodgers seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks as the 3B anchor above'),
        SideAnchor('', 136, 136, '1B',
                   'Loge 136, well down the right-field line; the ring runs '
                   'on to 168 on this side',
                   'seating_maps/dodger_stadium.jpg (Dodgers seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks as the 3B anchor above'),
    ),

    'comerica_park': (
        SideAnchor('', 116, 116, '1B', 'Section 116 (1B line)',
                   'https://www.mlb.com/tigers/ballpark/netting',
                   'primary', '2026-08-09'),
        SideAnchor('', 142, 142, '3B', 'Section 142 (3B line)',
                   'https://www.mlb.com/tigers/ballpark/netting',
                   'primary', '2026-08-09'),
        # Step 14. The club page anchored one section per line and both of
        # them land right. The map read below covers the rest of the ring and
        # does not: 103-108 is in right field, not on the third-base line.
        SideAnchor('', 101, 106, '1B',
                   'outfield grandstand at the end of the right-field arm, '
                   'the arm running 106 105 104 103 102 101 away from the '
                   'plate block at 126-129',
                   'seating_maps/comerica_park.jpg (Comerica Park seating '
                   'map)',
                   'map_read', '2026-09-07',
                   basis='flat plan, plate at the bottom. Orientation fixed '
                         'by the map\'s own labels: "RIGHT FIELD BALCONY" is '
                         'printed along the RF1-RF4 strip drawn directly '
                         'outboard of 101-106, with "Comerica Landing" and '
                         'the "Right Field Pitcher\'s Pub" beyond it, and the '
                         'legend colour filling 101-106 is "Right Field '
                         'Grandstand". Nothing outside the image was needed'),
        SideAnchor('', 133, 140, '3B',
                   'lower bowl ascending from the plate block at 126-129 '
                   'toward the left-field corner: 130 131 132 133 ... 140, '
                   'then the "Left Field Baseline Box" colour at 141-143 and '
                   'the Pavilion at 144-151',
                   'seating_maps/comerica_park.jpg (Comerica Park seating '
                   'map)',
                   'map_read', '2026-09-07',
                   basis='same frame as the 1B anchor above; this arm ends in '
                         'the legend colour the map names "Left Field '
                         'Baseline Box", which is the opposite corner from '
                         'the Right Field Balcony'),
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
        # Read off the seating map (2026-09-07). The two club anchors above
        # are on the inner Legends ring, which no zone in this park's table
        # claims, so they leave the park untestable. These two are on the
        # Field MVP ring, which the table does number.
        SideAnchor('', 105, 118, '1B',
                   'Field MVP ring descending from the plate block 120A/120B '
                   'toward the right-field corner: 119 118 117B 117A 116 115 '
                   '114B 114A 113 112 111 110 109 108 107 106 105',
                   'seating_maps/yankee_stadium.jpg (Yankees seating map)',
                   'map_read', '2026-09-07',
                   basis="flat plan, plate at the bottom with the Mastercard "
                         "Batter's Eye Deck at top centre, so the foul lines "
                         "run down-left and down-right. Which of those is "
                         "first base is fixed by the map's own printed note, "
                         "'protective netting of varying heights is used in "
                         "the Stadium from Section 011 to behind home plate "
                         "to Section 029', read with the netting band the "
                         "map draws: the band ends at the top edge of 011 on "
                         "the side labelled YANKEES dugout, and the club's "
                         "netting page - the anchor above - calls 011 the "
                         "1B/RF side"),
        SideAnchor('', 122, 136, '3B',
                   'Field MVP ring ascending from the plate block 120A/120B '
                   'toward the left-field corner: 121A 121B 122 123 124 125 '
                   '126 127A 127B 128 129 130 131 132 133 134 135 136',
                   'seating_maps/yankee_stadium.jpg (Yankees seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks as the 1B anchor above; the netting '
                         'band ends at the top edge of 029 on this side, '
                         'beside 128'),
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
        # Read off the seating map (2026-09-07). The club anchors above cover
        # eleven sections; the map covers the whole lower bowl and names the
        # side outright at both ends.
        SideAnchor('', 127, 148, '1B',
                   'lower bowl descending from the Home Plate Box 149-151 '
                   'toward the right-field corner: 148-145 (Cardinals Home '
                   'Box) 144-141 (Cardinals Infield Box) 140-135 (1st Base '
                   'Field Box / Cardinals Dugout Box) 134-130 (Right Field '
                   'Box / Lower Right Field Box) 129-127 (Home Run Box), '
                   'then the Lower Right Field Bleachers 101-111 odd',
                   'seating_maps/busch_stadium.png (Cardinals seating map)',
                   'map_read', '2026-09-07',
                   basis="flat plan, plate at lower left. Orientation fixed "
                         "by the map's own product names, which say the side "
                         "outright at both ends of the bowl: LOWER RIGHT "
                         "FIELD BLEACHERS / RIGHT FIELD BOX / 1st BASE FIELD "
                         "BOX on this side, LEFT FIELD BOX / LEFT FIELD "
                         "PAVILION / LOWER LEFT FIELD BLEACHERS / 3rd BASE "
                         "FIELD BOX on the other. The club's netting page "
                         "corroborates wedge by wedge: its '1B Field Box "
                         "135-140', '3B Field Box 161-165' and 'Lower RF Box "
                         "132-134' land on the map's wedges of those names, "
                         "and its 'Home Field Box 145-155' straddles the "
                         "map's HOME PLATE BOX 149-151"),
        SideAnchor('', 152, 167, '3B',
                   'lower bowl ascending from the Home Plate Box 149-151 '
                   'toward the left-field corner: 152-155 (Visitors Home '
                   'Box) 156-159 (Visitors Infield Box) 160-165 (3rd Base '
                   'Field Box) 163-167 (Left Field Box)',
                   'seating_maps/busch_stadium.png (Cardinals seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks as the 1B anchor above. Several '
                         'numbers in 160-167 are printed on more than one '
                         'product here, but every product carrying them sits '
                         'on this same side, so the label is on the '
                         'third-base line whichever one it names'),
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
        # Step 14. The map explains the club page's apparent contradiction:
        # Petco numbers one foul line odd and the other even from a shared
        # block, so 111-115 and 112-116 share no actual section. The anchors
        # below are single numbers because a range spanning both parities
        # would be a claim about sections on the other line. They do not make
        # this park testable — `_overlapping_prefixes` still trips on the two
        # club-page ranges above, by design — they are recorded evidence.
        SideAnchor('', 122, 122, '3B',
                   'even arm ascending from the plate block at 101-104: 106 '
                   '108 110 112 114 116 118 120 122 124 126 128 130 132',
                   'seating_maps/petco_park.jpg (Petco Park seating map)',
                   'map_read', '2026-09-07',
                   basis='flat plan, plate at the bottom. Orientation fixed '
                         'by the map\'s own label "WESTERN METAL SUPPLY CO. '
                         'BUILDING", which stands at the left-field foul '
                         'pole and is drawn at the head of this arm, next to '
                         'the "FOUL POLE SUITE" label. The even/odd split is '
                         'the map\'s, not an inference'),
        SideAnchor('', 134, 134, '3B',
                   'even arm, last full section before the Western Metal '
                   'Supply Co. Building at the foul pole',
                   'seating_maps/petco_park.jpg (Petco Park seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmark as the 122 anchor above'),
        SideAnchor('', 125, 125, '1B',
                   'odd arm ascending from the plate block at 101-104: 105 '
                   '107 109 111 113 115 117 119 121 123 125 127 129 131',
                   'seating_maps/petco_park.jpg (Petco Park seating map)',
                   'map_read', '2026-09-07',
                   basis='the arm opposite the Western Metal Supply Co. '
                         'Building; the "T-MOBILE HOME RUN DECK" label runs '
                         'along its outfield end, past 131-137'),
        SideAnchor('', 137, 137, '1B',
                   'odd arm, last section along the T-Mobile Home Run Deck',
                   'seating_maps/petco_park.jpg (Petco Park seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmark as the 125 anchor above'),
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

    # --- Family 3, third read (2026-09-07): the six parks of Step 13. Three
    # of them (Yankee Stadium, Dodger Stadium, Busch Stadium) already carried
    # club-page anchors; the map read is appended to those entries above,
    # because it reaches rings and sections the club page does not.
    # See MAP_FINDINGS.md, Step 13.

    'minute_maid': (
        SideAnchor('', 105, 114, '3B',
                   'field level ascending from the plate block 118-120 '
                   'toward the left-field corner: 114 113 112 111 110 109 '
                   '108 107 106 105, then 104 and the Crawford Boxes 100-103',
                   'seating_maps/daikin_park.jpg (Astros seating map)',
                   'map_read', '2026-09-07',
                   basis="flat plan, plate at lower left. Orientation fixed "
                         "by Landry's Crawford Boxes on 100-103 - the legend "
                         "colour matches those four wedges to within a few "
                         "RGB counts, and the Crawford Boxes are Daikin "
                         "Park's left-field porch. Corroborated by the "
                         "Batters Eye Box, which sits on the plate-to-centre "
                         "axis with the Crawford Boxes about 40 degrees to "
                         "its left, and by the Bullpen Boxes 150-156 at the "
                         "other end. The behind-plate block reads 118-120, "
                         "inside the club's published netted run 112-126"),
        SideAnchor('', 124, 129, '1B',
                   'field level descending from the plate block 118-120 '
                   'toward the right-field corner: 122 122 124 125 126 127 '
                   '128 129',
                   'seating_maps/daikin_park.jpg (Astros seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks as the 3B anchor above. The anchor '
                         'starts at 124 because this map prints 122 on two '
                         'adjacent wedges and never prints 123, the same '
                         'defect it has at 116/117 and 120/121'),
        SideAnchor('', 131, 134, '1B',
                   'field level continuing toward the right-field corner: '
                   '131 132 133 134 (Field Box IV is labelled Sec. 132-134 '
                   'in the legend), then the Bullpen Boxes 150-156',
                   'seating_maps/daikin_park.jpg (Astros seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks. Split from the anchor above '
                         'because 130 is not printed: the wedge after 129 '
                         'carries 131'),
    ),

    'wrigley_field': (
        SideAnchor('', 101, 111, '3B',
                   'lower bowl ascending from the plate toward the '
                   'left-field corner: 111 110 109 (Field Box Infield) '
                   '108 ... 101 (Field Box Outfield), ending at the Left '
                   'Field Gate',
                   'seating_maps/wrigley_field.jpg (Cubs seating map)',
                   'map_read', '2026-09-07',
                   basis="flat plan. Orientation fixed by the street names "
                         "the map prints around the frame: W. Waveland Ave. "
                         "runs behind left field and is along the top, N. "
                         "Sheffield Ave. runs behind right field and is down "
                         "the right side. The Left Field Gate (by 101/203) "
                         "and the Wintrust Right Field Gate (by 134/232) "
                         "agree, as do the HOME and VISITORS dugout labels. "
                         "The anchors stop at 111 and start at 123 because "
                         "the map's own Field Box Home Plate colour covers "
                         "112-122 - sampled and matched against the legend "
                         "swatch - so those eleven are the map's "
                         "behind-plate group, and a shoulder of the "
                         "behind-plate group is not a statement about a foul "
                         "line"),
        SideAnchor('', 123, 134, '1B',
                   'lower bowl descending toward the right-field corner: '
                   '123 124 125 126 (Field Box Infield) 127 ... 134 (Field '
                   'Box Outfield), ending at the Wintrust Right Field Gate',
                   'seating_maps/wrigley_field.jpg (Cubs seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks as the 3B anchor above'),
    ),

    'nationals_park': (
        SideAnchor('', 101, 118, '3B',
                   'lower bowl ascending from the PNC Diamond Club block '
                   '119-126 toward the left-field corner: 118 117 116 '
                   '(Infield Box) 115-109 (Baseline / Corner) 108 (Corner '
                   'Reserved) 107-101 (Outfield Reserved)',
                   'seating_maps/nationals_park.jpg (Nationals seating map)',
                   'map_read', '2026-09-07',
                   basis="flat plan, plate at the bottom. Orientation fixed "
                         "by the map's own legend: the Right Field Terrace "
                         "colour sits on 222-230, sampled and matched to the "
                         "swatch, and those are on the far side of the frame "
                         "from this anchor. The NATIONALS and VISITORS "
                         "dugout labels agree - the Nationals dugout is on "
                         "the first-base side, and it is drawn opposite this "
                         "anchor. The map also draws the netting as a dotted "
                         "line running 109 to behind the plate to 135, which "
                         "is the club's published extent to the section"),
        SideAnchor('', 127, 143, '1B',
                   'lower bowl descending from the PNC Diamond Club block '
                   '119-126 toward the right-field corner: 127 128 129 130 '
                   '131 (Infield Box) 132-135 (Baseline Reserved / Corner) '
                   '136 137 (Corner Reserved) 138-143 (Outfield Reserved, '
                   'past the Nationals bullpen)',
                   'seating_maps/nationals_park.jpg (Nationals seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks as the 3B anchor above'),
    ),

    # --- Step 14 ------------------------------------------------------------
    #
    # Six maps, and the shape of the defect is the same at five of them: the
    # zone table numbers the bowl outward from a plate block in the middle,
    # and the park numbers it monotonically along the bowl from one foul pole
    # to the other. Where the park's ring happens to run low-at-1B the table's
    # two side blocks still land right and only the plate block is misplaced;
    # where it runs the other way, or wraps, one of the side blocks lands on
    # the wrong foul line and the anchors catch it.

    'pnc_park': (
        SideAnchor('', 101, 101, '1B',
                   'first section of the right-field arm, at the foul pole',
                   'seating_maps/pnc_park.jpg (PNC Park seating map)',
                   'map_read', '2026-09-07',
                   basis='rotated plan, plate at the middle left and the '
                         'outfield opening to the lower right. Orientation '
                         'fixed by the map\'s own labels: "RIGHT FIELD GATE" '
                         'is printed alongside this end of the arm, the '
                         '"MILLER LITE SKULL BAR" and "RIVERWALK" sit under '
                         'it, and the right-field bleachers 147 146 145 144 '
                         '143 142 run from immediately past 101 along the '
                         'outfield wall'),
        SideAnchor('', 107, 110, '1B',
                   'right-field arm descending from the plate block at '
                   '114-119: 113 112 110 109 108 107 105 103 101 (111 is not '
                   'printed), with field boxes 1 2 4 5 6 7 8 9 10 inboard',
                   'seating_maps/pnc_park.jpg (PNC Park seating map)',
                   'map_read', '2026-09-07',
                   basis='same landmarks as the 101 anchor above. The range '
                         'stops at 110 because 111 is not printed on this '
                         'map and an anchor may not claim a section it did '
                         'not read'),
        SideAnchor('', 130, 138, '3B',
                   'left-field arm ascending from the plate block at 114-119: '
                   '120 121 123 124 125 127 128 129 130 131 132 133 134 135 '
                   '136 137 138, with field boxes 20-32 inboard',
                   'seating_maps/pnc_park.jpg (PNC Park seating map)',
                   'map_read', '2026-09-07',
                   basis='orientation fixed by the map\'s own label "JIM BEAM '
                         'LEFT FIELD LOUNGE", printed vertically alongside '
                         '135-138 and the 235-238 deck above them. The '
                         '"PIRATES DUGOUT" label lies on this same arm and '
                         'agrees, but the lounge is the deciding landmark '
                         'because it names the field'),
    ),

    'target_field': (
        SideAnchor('', 101, 106, '1B',
                   'right-field arm descending from the plate block at '
                   '112-116: 111 110 109 108 107 106 105 104 103 102 101, '
                   'with field boxes 7 6 5 4 3 2 1 and lettered boxes E D C '
                   'B A inboard',
                   'seating_maps/target_field.jpg (Target Field seating map)',
                   'map_read', '2026-09-07',
                   basis='rotated plan, plate at the middle left. Orientation '
                         'fixed by the map\'s own label "Corona Right Field '
                         'Field Patio 139, 140", drawn immediately outboard '
                         'of section 101 at the foul pole, with "Gate 29 '
                         'Right Field Entrance" beyond it. The map\'s own '
                         'legend line "Home Plate Taproom presented by Pryes '
                         'Brewing (Section 213-216)" fixes the plate block on '
                         'the ring above and agrees'),
        SideAnchor('', 121, 127, '3B',
                   'left-field arm ascending from the plate block at 112-116: '
                   '117 118 119 120 121 122 123 124 125 126 127, then the '
                   'left-field bleachers 128 129 130 131',
                   'seating_maps/target_field.jpg (Target Field seating map)',
                   'map_read', '2026-09-07',
                   basis='the arm ends under "Gate 6 Left Field Entrance". '
                         'The range starts at 121 rather than 117 to stay '
                         'clear of the bend behind the plate, though 117-120 '
                         'are plainly on this side of it, past the VISITORS '
                         'DUGOUT label - see MAP_FINDINGS.md'),
    ),

    'tmobile_park': (
        SideAnchor('', 114, 127, '1B',
                   'right-field arm descending from the plate block at the '
                   'bend: 127 126 125 124 123 122 121 120 119 118 117 116 '
                   '115 114 112 111 110, past the MARINERS dugout (113 is '
                   'not printed)',
                   'seating_maps/tmobile_park.jpg (T-Mobile Park seating map)',
                   'map_read', '2026-09-07',
                   basis='rotated plan, plate at the lower left. Orientation '
                         'fixed by the map\'s own label "Hit it Here Cafe", '
                         'printed along the outfield sections 105-110 at the '
                         'end of this arm - that cafe is the right-field '
                         'landmark - with "RF GATE" beyond. The map also '
                         'prints "3B ENTRY" against 330-333 on the opposite '
                         'arm, which is the same statement made the other '
                         'way round'),
        SideAnchor('', 133, 144, '3B',
                   'left-field arm ascending from the plate block at the '
                   'bend: 128 129 131 132 133 ... 144, then 146 147 148 149 '
                   '150 (130 and 145 are not printed), past the VISITORS '
                   'dugout toward the LF GATE',
                   'seating_maps/tmobile_park.jpg (T-Mobile Park seating map)',
                   'map_read', '2026-09-07',
                   basis='the map prints "3B ENTRY" outside 330-333, which '
                         'sit on the same radials as 129-133; "LF GATE" is '
                         'printed over the far end of the same arm. The range '
                         'starts at 133 and stops at 144 so that every '
                         'number in it is one the map actually prints'),
    ),

    'angel_stadium': (
        SideAnchor('', 103, 109, '3B',
                   'left-field arm descending toward the plate block at '
                   '114-122: 101 102 103 ... 113, then the Lexus Diamond '
                   'Club arc 114-122 behind the plate',
                   'seating_maps/angel_stadium.jpg (Angel Stadium seating '
                   'map)',
                   'map_read', '2026-09-07',
                   basis='flat plan, plate at the bottom. Orientation fixed '
                         'by the map\'s own legend: the swatch labelled '
                         '"Left Field Pavilion" is the orange filling '
                         '256-260 at the head of this arm, and the swatch '
                         'labelled "Right Field Pavilion" is the yellow '
                         'filling 241-249 at the head of the other. The '
                         'ANGELS and VISITOR dugout labels agree. The map '
                         'also prints "Protective netting extends from '
                         'SECTIONS 109 - 127", which is centred on 118 and '
                         'so corroborates the plate block'),
        SideAnchor('', 123, 135, '1B',
                   'right-field arm ascending from the Lexus Diamond Club '
                   'arc: 123 124 125 ... 135, ending at the foul pole under '
                   'the Right Field Pavilion',
                   'seating_maps/angel_stadium.jpg (Angel Stadium seating '
                   'map)',
                   'map_read', '2026-09-07',
                   basis='same legend swatches as the 3B anchor above. This '
                         'is the anchor the zone table fails: it carries '
                         '133-141 as "3B Field", and 133 134 135 are the '
                         'last three sections of the right-field arm'),
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
