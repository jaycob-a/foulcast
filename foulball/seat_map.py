"""
Printed seat labels <-> model zones.

WHY THIS MODULE EXISTS
======================

`foulball/stadium.py` carries two very different classes of information, and
its MODULE PROVENANCE block is explicit about which is which:

  - The six geometry numbers on every `SeatSection` (`distance_min/max`,
    `angle_min/max`, `height_min/max`) are **estimated**. Not surveyed, not
    digitized. All 31 parks are analogues off one template.
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

WHAT THIS MODULE DOES NOT ESTABLISH
===================================

That a printed section belongs to a zone's *number range* says nothing about
whether the zone's distance/angle bands are right. The ranges come from the
same names the provenance block calls real, but the bands they are attached to
do not. This module improves the bookkeeping, not the geometry.
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
