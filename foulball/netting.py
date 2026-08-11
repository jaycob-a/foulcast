"""
Protective netting: what the clubs publish, and where it lands on the model.

MODULE PROVENANCE — READ BEFORE TRUSTING ANY ENTRY
==================================================

Every netting extent in `PARK_NETTING` below is transcribed from
`SOURCED_DATA.md` Part 2, which recorded a browser read of each club's own
netting or seating-map page on **2026-08-09**. Nothing here is estimated,
interpolated, or carried over from a park that looks similar. Each entry
carries its source, its kind (*primary* club page vs *secondary — unverified*
compilation), the date it was retrieved and the vintage year of the page.

Where `SOURCED_DATA.md` records a gap, this file records the same gap. There
are six of them, and they are entries in their own right rather than empty
fields:

  - Wrigley Field       — club describes the extent in words, publishes no
                          section numbers.
  - Kauffman Stadium    — club states outright that it will not publish
                          section-level netting locations.
  - Citi Field          — no netting text on the club's own pages.
  - loanDepot park      — netting published only as an image.
  - Sutter Health Park  — no park-specific source of any kind.
  - Las Vegas Ballpark  — no park-specific source of any kind.

Tropicana Field is a seventh case of a different sort: the club's own page
carries two statements that cannot both describe the same installation, so it
is recorded as a conflict rather than resolved in this file.

THE THREE-WAY SPLIT THE TASK USUALLY WANTS, AND WHY IT IS NOT HERE
==================================================================

"Fully behind netting / partially covered / exposed" is not what the clubs
publish. Almost every club uses the same formula — some amount of netting or
screening in front of the listed sections, height and coverage varying by
section — and then warns that fans in those sections are still exposed to
objects leaving the field. So the published fact is binary at the level of a
*printed section*: listed, or not listed. Exactly one club in the league
publishes a partial flag (Target Field section 126), and it is carried on that
entry as `partial_labels`.

The `partially_netted` status this module emits therefore means something
narrower and entirely model-side: **a model zone spans several printed
sections and the published extent covers only some of them.** That is
arithmetic on the source, not a claim the source did not make.

WHAT THE JOIN CAN AND CANNOT ESTABLISH
======================================

Netting extents are published as printed section numbers. The model's zones
each cover a *range* of printed sections, recorded in the zone name and parsed
by `seat_map.parse_printed_ranges`. Joining the two is therefore label
arithmetic, and it inherits every weakness of the labels. See `seat_map` for
why printed labels are the right join key.

The join is only accepted for a park when it survives three coherence checks
(`_check_join` below). They do not validate the labels — a park that passes
has merely failed to contradict itself. What they catch is the opposite case:
a published extent that is flatly incompatible with the printed sections the
model has written down for that park. When that happens the netting data is
not what is wrong; the model's labels are. The park is reported as a gap with
the contradiction attached, because a join the model cannot verify is a gap
and not a fact.

Fourteen of the 31 parks currently pass. Of the 17 that do not, six are the
source gaps listed above, one is the Tropicana conflict, one is an unresolved
arc (Comerica), and **nine are the model's own printed labels contradicting a
perfectly good club page**. That last group is the most useful thing in this
file: it is a list of parks whose zone tables need fixing, discovered by
external data rather than by inspection.

HOW THIS IS USED, IN TWO OPPOSITE DIRECTIONS
============================================

A netted section cannot produce a souvenir and can still produce an injury
warning, so the same status drives two conclusions:

  - `matchup_engine` marks a foul landing in a `netted` zone **not catchable**,
    which removes that zone from every souvenir ranking downstream, and keeps
    `expected_fouls` untouched so the ball is still counted where it lands.
  - Safety-facing output reads the same field the other way round: netted
    zones are highlighted, and the published netting *height* — the only real
    geometric constraint in this dataset, and published at just seven parks —
    is carried for them.

`unknown` is never silently folded into either answer. A zone the sources do
not cover stays in the ranking and is flagged as unrankable-with-confidence,
because dropping it would be an unpublished claim that it is netted, and
counting it clean would be an unpublished claim that it is not.
"""
from dataclasses import dataclass, field

from .seat_map import parse_printed_ranges

# Bumped by hand when the *interpretation* of a published extent changes —
# a new alias, a changed guard, a re-read of a source. Data corrections that
# only add or edit a park entry do not need it.
NETTING_MAP_VERSION = "1"

# Every primary row was read in a browser on this date (SOURCED_DATA.md Part 2).
RETRIEVED = "2026-08-09"

# The vintage claim behind `year=2026` on the primary rows. Stated fleet-wide
# in SOURCED_DATA.md rather than verified page by page — the wording there is
# that *most* of those pages carry a "© 2026 MLB Advanced Media" footer — so
# the year is the year the page was read and published, not a per-page
# copyright reading.
PRIMARY_YEAR_BASIS = (
    "club page read live 2026-08-09; MLB club pages carry a © 2026 MLB "
    "Advanced Media footer (SOURCED_DATA.md states this fleet-wide, not per "
    "page)"
)

# The only netting authority that reaches Sutter Health Park and Las Vegas
# Ballpark. It is a requirement placed on the clubs, not an observation of
# either installation, so it is recorded as context on those two entries and
# is never turned into section numbers.
PDL_RULE = (
    "Professional Development League clubs must install netting foul pole to "
    "foul pole 'unless the configuration of the ballpark makes such coverage "
    "unnecessary', height standardized from behind home plate to the end of "
    "each dugout, no later than 2025 Opening Day"
)
PDL_RULE_SOURCE = (
    "Ballpark Digest 2022-12-07; Sen. Durbin press release 2022-12-07"
)
PDL_RULE_YEAR = 2022


# ============================================================
# Data model
# ============================================================

# Why a park has no usable section-level extent. Only ever set on parks the
# join could not map.
#   'club_publishes_no_sections'  club describes the extent without numbers
#   'club_declines_to_publish'    club states it will not give section numbers
#   'no_primary_source'           nothing on the club's own pages
#   'no_source_at_all'            no park-specific source of any kind
#   'source_conflict'             the club's own page contradicts itself
#   'arc_endpoints_unresolved'    endpoints given on a numbering that wraps
#                                 behind the plate, with the wrap unpublished
#   'labels_contradict_model'     extent is fine; the model's printed labels
#                                 for this park cannot be reconciled with it
GapKind = str

SourceKind = str        # 'primary' | 'secondary_unverified' | 'none'
ParkStatus = str        # 'mapped' | 'source_gap' | 'join_gap'
ZoneStatus = str        # 'netted' | 'partially_netted' | 'not_netted' | 'unknown'


@dataclass(frozen=True)
class NettedRange:
    """One inclusive run of printed section labels stated as netted.

    `prefix` is the printed-label prefix the run belongs to ('' for a bare
    number). `raw` is the source's own wording, kept verbatim so the entry can
    be checked against `SOURCED_DATA.md` without decoding this dataclass.

    `interpretation` is non-empty exactly when turning the source's wording
    into a numeric run took a judgment call — an arc read as an interval, a
    prefix supplied to match the model's series. Those calls are the only
    places this file goes beyond transcription, and they are listed in
    `interpretations()` so they can be audited as a group.
    """
    prefix: str
    start: int
    end: int
    raw: str
    interpretation: str = ""

    def contains(self, prefix: str, number: int) -> bool:
        return prefix == self.prefix and self.start <= number <= self.end


@dataclass(frozen=True)
class ParkNetting:
    """Published netting for one park, exactly as far as a source goes."""
    park_key: str
    park_name: str
    published: str                      # the extent, in the source's words
    ranges: tuple[NettedRange, ...] = ()
    height: str | None = None           # published height, verbatim
    source: str = ""
    source_kind: SourceKind = "none"
    retrieved: str = RETRIEVED
    year: int | None = None
    year_basis: str = ""
    # Netted products the source names without numbers ("Diamond Club A-G").
    # Real netting the join cannot place, which is why a zone in an
    # unenumerated series is `unknown` rather than `not_netted`.
    unenumerable: tuple[str, ...] = ()
    # Printed labels the club itself marks as only partially covered. One
    # entry league-wide: Target Field 126.
    partial_labels: tuple[str, ...] = ()
    # Set when the source cannot yield section numbers at all. A park with a
    # gap_kind is never joined, whatever ranges it carries.
    gap_kind: GapKind | None = None
    notes: tuple[str, ...] = ()
    # A weaker figure that exists but is not applied. Recorded so the gap can
    # be closed later by re-checking one source rather than starting over.
    secondary: str | None = None
    secondary_source: str | None = None
    secondary_year: int | None = None


@dataclass(frozen=True)
class ZoneNetting:
    """Netting status of one model zone, with the source that decided it."""
    zone_id: str
    status: ZoneStatus
    reason: str
    park: ParkNetting
    netted_labels: tuple[str, ...] = ()
    exposed_labels: tuple[str, ...] = ()

    @property
    def blocks_catch(self) -> bool:
        """Whether a souvenir ranking must exclude this zone.

        Only a fully netted zone does. `partially_netted` keeps its place and
        is flagged as an upper bound — part of it is open, and splitting the
        zone's fouls between the netted and open halves would need a
        seat-level distribution nobody publishes. `unknown` keeps its place
        for the reason given in the module docstring.
        """
        return self.status == "netted"

    @property
    def source_line(self) -> str:
        """One-line provenance, for any UI that shows the status."""
        p = self.park
        year = p.year if p.year is not None else "undated"
        return f"{p.source} ({p.source_kind}, {year}, retrieved {p.retrieved})"


@dataclass(frozen=True)
class ParkJoin:
    """Result of joining one park's published extent onto its zone table."""
    park_key: str
    status: ParkStatus
    park: ParkNetting
    zones: dict[str, ZoneNetting] = field(default_factory=dict)
    gap_kind: GapKind | None = None
    gap_detail: str = ""
    # Non-fatal observations. A flagged park is still mapped.
    flags: tuple[str, ...] = ()
    # Published labels that match no zone in this park's table.
    unmatched_published: tuple[str, ...] = ()


# ============================================================
# The data — SOURCED_DATA.md Part 2, transcribed
# ============================================================
#
# Registry keys match `stadium.STADIUMS`. `oakland_coliseum` is the Athletics'
# key and now points at Sutter Health Park, as it does everywhere else in the
# repo.

PARK_NETTING: dict[str, ParkNetting] = {

    'yankee_stadium': ParkNetting(
        park_key='yankee_stadium',
        park_name='Yankee Stadium',
        published='Section 011 (1B/RF side) → behind home → Section 029 '
                  '(3B/LF side)',
        ranges=(
            NettedRange('', 11, 29, 'Section 011 → Section 029',
                        interpretation='the club states two endpoints either '
                                       'side of home plate; read as the '
                                       'inclusive run between them, and the '
                                       'printed zero padding (011) dropped '
                                       'to compare as a number'),
        ),
        height="31 ft above the field wall behind the plate (Sections "
               "018-021B); 11'6\" above the wall in front of 017B and 022; "
               "9 ft above the dugouts, retractable up 3 ft pregame; 11'6\" "
               "above the wall at 025 and 015A; ~14 ft above field (~11'6\" "
               "above walls) from 014B→011 and 026→029",
        source='https://www.mlb.com/yankees/ballpark/netting',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        notes=(
            'The most detailed netting page in the league, and the one whose '
            'section numbers the model cannot place: the club numbers the '
            'infield field level 011-029, and this park\'s zone table numbers '
            'it 109-131. See the join gap.',
        ),
    ),

    'fenway_park': ParkNetting(
        park_key='fenway_park',
        park_name='Fenway Park',
        published='Field Box 79 → Field Box 9',
        ranges=(
            NettedRange('FB', 9, 79, 'Field Box 79 → Field Box 9',
                        interpretation='endpoints read as the inclusive run '
                                       'between them; the source names the '
                                       'Field Box product, which is the FB '
                                       'prefix the zone table uses'),
        ),
        height='~12 ft 8 in above the playing field, varying',
        source='https://www.mlb.com/redsox/ballpark/netting',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        notes=(
            'RateYourSeats gives the full Field Box inventory as FB1-FB82, so '
            'the extent stopping at FB79 leaves the last few boxes on one '
            'side open. That asymmetry is the source\'s, not the join\'s.',
        ),
    ),

    'dodger_stadium': ParkNetting(
        park_key='dodger_stadium',
        park_name='Dodger Stadium',
        published='Behind home plate → end of baseline section 40 (1B) and '
                  'section 41 (3B)',
        ranges=(
            NettedRange('FD', 1, 41,
                        'behind home plate → section 40 (1B) / 41 (3B)',
                        interpretation='the club gives bare numbers; the '
                                       'model numbers the same field boxes '
                                       'with an FD prefix, and the club\'s '
                                       'even-to-1B / odd-to-3B split matches '
                                       'the zone table\'s parity exactly '
                                       '(FD12-FD24 on 1B, FD11-FD25 on 3B), '
                                       'so the two are the same series. The '
                                       'arc from behind the plate is read as '
                                       'starting at the lowest FD number, '
                                       'which the zone table places behind '
                                       'the plate'),
        ),
        height=None,
        source='https://www.mlb.com/dodgers/ballpark/netting',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        notes=(
            'The Dugout Club (DG series) sits in front of the field boxes '
            'behind the plate and is not named on the netting page, so it is '
            'unknown rather than exposed.',
        ),
    ),

    'wrigley_field': ParkNetting(
        park_key='wrigley_field',
        park_name='Wrigley Field',
        published='"along the first and third base lines to the outfield '
                  'edge of each dugout" — no section numbers given',
        height=None,
        source='https://www.mlb.com/cubs/ballpark/information/guide '
               '(Wrigley Field A-Z guide, "Netting")',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        gap_kind='club_publishes_no_sections',
        notes=(
            'The A-Z wording may itself be stale: 2020 reporting had the '
            'netting extended from 340 ft to 560 ft, past the dugouts toward '
            'both corners. Two incompatible descriptions, neither with '
            'section numbers, so nothing is written down.',
        ),
    ),

    'coors_field': ParkNetting(
        park_key='coors_field',
        park_name='Coors Field',
        published='front of Sections 112-147',
        ranges=(NettedRange('', 112, 147, 'Sections 112-147'),),
        height=None,
        source='Coors Field seating chart, reached via '
               'https://www.mlb.com/rockies/ballpark/netting',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
    ),

    'chase_field': ParkNetting(
        park_key='chase_field',
        park_name='Chase Field',
        published='Sections 111-133',
        ranges=(NettedRange('', 111, 133, 'Sections 111-133'),),
        height='~30 ft',
        source='https://www.mlb.com/dbacks/ballpark/netting',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        notes=(
            'Materially wider than the 115-129 reported in 2019.',
        ),
    ),

    'truist_park': ParkNetting(
        park_key='truist_park',
        park_name='Truist Park',
        published='Sections 10-42 and 111-141',
        ranges=(
            NettedRange('', 10, 42, 'Sections 10-42'),
            NettedRange('', 111, 141, 'Sections 111-141'),
        ),
        height=None,
        source='https://www.mlb.com/braves/ballpark/information/guide '
               '(Truist Park A-Z guide)',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
    ),

    'camden_yards': ParkNetting(
        park_key='camden_yards',
        park_name='Oriole Park at Camden Yards',
        published='Section 6 → Section 70',
        ranges=(
            NettedRange('', 6, 70, 'Section 6 → Section 70',
                        interpretation='endpoints read as the inclusive run '
                                       'between them'),
        ),
        height=None,
        source='https://www.mlb.com/orioles/ballpark/seating-map',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
    ),

    'citizens_bank': ParkNetting(
        park_key='citizens_bank',
        park_name='Citizens Bank Park',
        published='Diamond Club A-G; Field Level 109-138',
        ranges=(NettedRange('', 109, 138, 'Field Level 109-138'),),
        height='varies by section',
        source='https://www.mlb.com/phillies/ballpark/netting',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        unenumerable=('Diamond Club A-G',),
    ),

    'great_american': ParkNetting(
        park_key='great_american',
        park_name='Great American Ball Park',
        published='Sections 1-5, 22-25, and 111-135',
        ranges=(
            NettedRange('', 1, 5, 'Sections 1-5'),
            NettedRange('', 22, 25, 'Sections 22-25'),
            NettedRange('', 111, 135, 'Sections 111-135'),
        ),
        height='varies by section',
        source='https://www.mlb.com/reds/ballpark/netting',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
    ),

    'progressive_field': ParkNetting(
        park_key='progressive_field',
        park_name='Progressive Field',
        published='Sections 128-174 (enumerated individually on the page)',
        ranges=(NettedRange('', 128, 174, 'Sections 128-174'),),
        height='varies by section',
        source='https://www.mlb.com/guardians/ballpark/netting',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
    ),

    'comerica_park': ParkNetting(
        park_key='comerica_park',
        park_name='Comerica Park',
        published='behind home plate → Section 116 (1B line) and Section 142 '
                  '(3B line)',
        height=None,
        source='https://www.mlb.com/tigers/ballpark/netting '
               '(Comerica Park seating map)',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        gap_kind='arc_endpoints_unresolved',
        notes=(
            'The two endpoints sit on a numbering that wraps behind the '
            'plate — this park\'s zone table has 103-108 and 137-145 both on '
            'the 3B side — so the netted run is not one interval, and where '
            'it breaks is not published. Reading it as 116-142 would net the '
            'far end of the 3B line and leave the plate open, which is '
            'plainly wrong; reading it the other way needs a wrap point no '
            'source gives.',
            'The page also describes the netting as "20 percent more narrow" '
            'than the prior system, with no absolute height.',
        ),
    ),

    'minute_maid': ParkNetting(
        park_key='minute_maid',
        park_name='Daikin Park (formerly Minute Maid Park)',
        published='Sections 112-126 and the Diamond Club',
        ranges=(NettedRange('', 112, 126, 'Sections 112-126'),),
        height=None,
        source='https://www.mlb.com/astros/ballpark/seat-map',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        unenumerable=('Diamond Club',),
    ),

    'kauffman_stadium': ParkNetting(
        park_key='kauffman_stadium',
        park_name='Kauffman Stadium',
        published='no section numbers published — the club states only that '
                  'the map shows "the general location where additional '
                  'netting has been installed" and that "it is not possible '
                  'for a map like this to show the precise location of the '
                  'netting"',
        height=None,
        source='https://www.mlb.com/royals/ballpark/seating-map',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        gap_kind='club_declines_to_publish',
        secondary='Sections 107-148',
        secondary_source='RateYourSeats, "Protective Netting Locations at '
                         'Every MLB Stadium" (published 2018-06-11, updated '
                         '2020-03-20)',
        secondary_year=2020,
        notes=(
            'The 2019 snapshot had 120-135, so the secondary figure has '
            'already moved once and is six years old. Not applied.',
        ),
    ),

    'angel_stadium': ParkNetting(
        park_key='angel_stadium',
        park_name='Angel Stadium',
        published='Sections 103-133',
        ranges=(NettedRange('', 103, 133, 'Sections 103-133'),),
        height=None,
        source='https://www.mlb.com/angels/ballpark/netting',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        notes=(
            'Materially wider than the 110-126 reported in 2019, which is the '
            'clearest case in the fleet for preferring the current club page '
            'over the 2019-2020 compilations.',
        ),
    ),

    'citi_field': ParkNetting(
        park_key='citi_field',
        park_name='Citi Field',
        published='no official statement found — the club\'s /ballpark/'
                  'netting and seat-map pages carry no netting text '
                  '(checked 2026-08-09)',
        height=None,
        source='https://www.mlb.com/mets/ballpark/netting (no netting text)',
        source_kind='none',
        year=None,
        year_basis='nothing published to date',
        gap_kind='no_primary_source',
        secondary='netting in front of sections 107-128, with the net proper '
                  '111-124 and a protective fence continuing to 107 and 128',
        secondary_source='RateYourSeats Citi Field pages, via web search '
                         '(undated)',
        secondary_year=None,
        notes=(
            'The secondary figure is the only one in the file that '
            'distinguishes net from fence, which is exactly the distinction '
            'the primary sources never make — and it is unverified. Not '
            'applied.',
        ),
    ),

    'oakland_coliseum': ParkNetting(
        park_key='oakland_coliseum',
        park_name='Sutter Health Park',
        published='no club statement found — the A\'s A-Z guide has no '
                  'netting entry and the Sutter Health Park ballpark-map page '
                  'carries no netting text (both checked 2026-08-09)',
        height=None,
        source=f'{PDL_RULE_SOURCE} — league rule only, no park-specific '
               f'source',
        source_kind='none',
        year=PDL_RULE_YEAR,
        year_basis='the PDL rule is dated 2022-12-07 and takes effect by 2025 '
                   'Opening Day; it is a requirement on the club, not an '
                   'observation of this installation',
        gap_kind='no_source_at_all',
        notes=(
            f'Only applicable authority: {PDL_RULE}.',
            'A rule that a net must exist does not say which sections it '
            'covers at this park, so no sections are written down.',
        ),
    ),

    'las_vegas_ballpark': ParkNetting(
        park_key='las_vegas_ballpark',
        park_name='Las Vegas Ballpark',
        published='no park-specific source found — the A-to-Z guide tells '
                  'guests to stay behind "railings and protective netting" '
                  'without describing its extent',
        height=None,
        source=f'{PDL_RULE_SOURCE} — league rule only, no park-specific '
               f'source',
        source_kind='none',
        year=PDL_RULE_YEAR,
        year_basis='the PDL rule is dated 2022-12-07 and takes effect by 2025 '
                   'Opening Day; it is a requirement on the club, not an '
                   'observation of this installation',
        gap_kind='no_source_at_all',
        notes=(
            f'Only applicable authority: {PDL_RULE} (the Aviators are '
            f'Triple-A).',
            'A web-search summary attributed "nets extend to the far ends of '
            'the dugouts and are extremely high" to a Las Vegas '
            'Review-Journal article; fetching that article (2018-02-01) found '
            'no park-specific detail, so the claim is unsupported and is not '
            'carried.',
        ),
    ),

    'pnc_park': ParkNetting(
        park_key='pnc_park',
        park_name='PNC Park',
        published='Section 101 → Section 130',
        ranges=(
            NettedRange('', 101, 130, 'Section 101 → Section 130',
                        interpretation='endpoints read as the inclusive run '
                                       'between them'),
        ),
        height='varies by section',
        source='https://www.mlb.com/pirates/ballpark/seat-map '
               '(PNC Park 3D seating chart)',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
    ),

    'petco_park': ParkNetting(
        park_key='petco_park',
        park_name='Petco Park',
        published='All Lexus Home Plate Club sections; Field VIP 101-106; '
                  'full square net coverage 109-110; angled net coverage '
                  '111-115 (1B side) and 112-116 (3B side)',
        ranges=(
            NettedRange('', 101, 106, 'Field VIP 101-106'),
            NettedRange('', 109, 110, 'full square net coverage 109-110'),
            NettedRange('', 111, 115, 'angled net coverage 111-115 (1B side)'),
            NettedRange('', 112, 116, 'angled net coverage 112-116 (3B side)'),
        ),
        height=None,
        source='https://www.mlb.com/padres/ballpark/netting',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        unenumerable=('Lexus Home Plate Club (all sections)',),
        notes=(
            'The only club in the league that distinguishes net *geometry* — '
            'square vs angled — by section. That distinction is carried here '
            'in the range wording and is not modelled: the model has no net '
            'surface, only a per-zone status.',
            'The numbered ranges skip 107-108, which is very likely the '
            'unenumerated Lexus Home Plate Club; the join cannot assume that.',
        ),
    ),

    'oracle_park': ParkNetting(
        park_key='oracle_park',
        park_name='Oracle Park',
        published='Sections 101-135',
        ranges=(NettedRange('', 101, 135, 'Sections 101-135'),),
        height='varies by section',
        source='https://www.mlb.com/giants/ballpark/seat-map',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
    ),

    'tmobile_park': ParkNetting(
        park_key='tmobile_park',
        park_name='T-Mobile Park',
        published='Sections 115-146',
        ranges=(NettedRange('', 115, 146, 'Sections 115-146'),),
        height='27 ft in front of Sections 126-134; 13.5 ft above field level '
               'for 115-125 and 135-146',
        source='https://www.mlb.com/mariners/ballpark/seat-map',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        notes=(
            'One of two clubs publishing height by sub-range. The 27 ft run '
            '(126-134) is the club\'s own marker for where the plate is, and '
            'it disagrees with this park\'s zone table, which numbers the '
            'behind-plate zone 108-111. See the join gap.',
        ),
    ),

    'busch_stadium': ParkNetting(
        park_key='busch_stadium',
        park_name='Busch Stadium',
        published='By product: Cardinals Club 1-8; Home Field Box 145-155; '
                  'Diamond Box 140-145 and 155-160; Infield Field Box 141-144 '
                  'and 156-160; Dugout Box 132, 135-139, 161-165; 1B Field '
                  'Box 135-140; 3B Field Box 161-165; Lower RF Box 132-134',
        ranges=(
            NettedRange('', 1, 8, 'Cardinals Club 1-8'),
            NettedRange('', 132, 134, 'Lower RF Box 132-134'),
            NettedRange('', 132, 132, 'Dugout Box 132'),
            NettedRange('', 135, 139, 'Dugout Box 135-139'),
            NettedRange('', 135, 140, '1B Field Box 135-140'),
            NettedRange('', 140, 145, 'Diamond Box 140-145'),
            NettedRange('', 141, 144, 'Infield Field Box 141-144'),
            NettedRange('', 145, 155, 'Home Field Box 145-155'),
            NettedRange('', 155, 160, 'Diamond Box 155-160'),
            NettedRange('', 156, 160, 'Infield Field Box 156-160'),
            NettedRange('', 161, 165, 'Dugout Box 161-165'),
            NettedRange('', 161, 165, '3B Field Box 161-165'),
        ),
        height='varies by section',
        source='https://www.mlb.com/cardinals/ballpark/netting',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        notes=(
            'Published by ticket product rather than as one run, so the ranges '
            'overlap; their union is 132-165 plus the Cardinals Club 1-8.',
        ),
    ),

    'tropicana_field': ParkNetting(
        park_key='tropicana_field',
        park_name='Tropicana Field',
        published='"Protective netting extends from home plate to the foul '
                  'poles located in Sections 137 and 138." Enumerated netted '
                  'sections: 101-138. The same page then says "protective '
                  'netting of varying heights is used in the Stadium from '
                  'Section 125 to behind home plate to Section 126."',
        height='varies by section',
        source='https://www.mlb.com/rays/ballpark/netting',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        gap_kind='source_conflict',
        notes=(
            'The two statements cannot both describe the same installation — '
            'pole to pole across 101-138 against a run from 125 to 126 — and '
            'the second reads as stale boilerplate. Picking one would be an '
            'assumption, so neither is applied.',
            'The park reopened for 2026 after ~$60M of hurricane repairs '
            'including a new roof, so the page may predate the reopening. '
            'That is a reason to re-read it, not a reason to prefer either '
            'sentence.',
        ),
    ),

    'globe_life': ParkNetting(
        park_key='globe_life',
        park_name='Globe Life Field',
        published='Sections 1-26',
        ranges=(NettedRange('', 1, 26, 'Sections 1-26'),),
        height='varies by section',
        source='https://www.mlb.com/rangers/ballpark/seat-map',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
    ),

    'rogers_centre': ParkNetting(
        park_key='rogers_centre',
        park_name='Rogers Centre',
        published='Down the first and third baseline walls to Sections 113C '
                  'and 130C respectively, "tapering off to the curve before '
                  'the foul poles"',
        ranges=(
            NettedRange('', 113, 130, 'to Sections 113C and 130C',
                        interpretation='endpoints read as the inclusive run '
                                       'between them, and the printed block '
                                       'suffix C dropped — the zone table '
                                       'carries these sections without a '
                                       'suffix'),
        ),
        height='30 ft (matching the height previously in place behind home '
               'plate)',
        source='https://www.mlb.com/bluejays/ballpark/netting',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
    ),

    'target_field': ParkNetting(
        park_key='target_field',
        park_name='Target Field',
        published='Sections 7-10; 1-6 and 11-17; 109-119; 105-108 and '
                  '120-123; 103-104 and 124-125; Section 126 "Partially '
                  'covered"',
        ranges=(
            NettedRange('', 7, 10, 'Sections 7-10'),
            NettedRange('', 1, 6, 'Sections 1-6'),
            NettedRange('', 11, 17, 'Sections 11-17'),
            NettedRange('', 109, 119, 'Sections 109-119'),
            NettedRange('', 105, 108, 'Sections 105-108'),
            NettedRange('', 120, 123, 'Sections 120-123'),
            NettedRange('', 103, 104, 'Sections 103-104'),
            NettedRange('', 124, 125, 'Sections 124-125'),
            NettedRange('', 126, 126, 'Section 126 — "Partially covered"'),
        ),
        height='varies by section',
        source='https://www.mlb.com/twins/ballpark/seat-map',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        partial_labels=('126',),
        notes=(
            'The only explicit partial-coverage flag published anywhere in '
            'the league. It is carried as `partial_labels` and is the one '
            'place in this file where "partially covered" is the club\'s own '
            'word rather than the join\'s arithmetic.',
        ),
    ),

    'guaranteed_rate': ParkNetting(
        park_key='guaranteed_rate',
        park_name='Rate Field',
        published='49 sections: 108-156 (enumerated individually on the page)',
        ranges=(NettedRange('', 108, 156, 'Sections 108-156'),),
        height='varies by section',
        source='https://www.mlb.com/whitesox/ballpark/seat-map',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        notes=(
            'The White Sox were the first club with netting foul pole to foul '
            'pole, in July 2019, which is why this extent covers the whole '
            'lower bowl rather than the infield.',
        ),
    ),

    'loan_depot': ParkNetting(
        park_key='loan_depot',
        park_name='loanDepot park',
        published='no text published — the club\'s seat-map page has a '
                  '"loanDepot park Netting" heading whose content is an image '
                  'with no section list (checked 2026-08-09)',
        height=None,
        source='https://www.mlb.com/marlins/ballpark/seat-map '
               '(netting shown only as an image)',
        source_kind='none',
        year=None,
        year_basis='the image carries no readable date and no section list',
        gap_kind='no_primary_source',
        secondary='Sections 8-21',
        secondary_source='RateYourSeats loanDepot park pages, via web search; '
                         'consistent with the 2020 RateYourSeats table (8-21)',
        secondary_year=2020,
        notes=(
            'Not applied. An unverified six-year-old figure is not a current '
            'state, and the netting either side of it has moved at other '
            'parks over the same period.',
        ),
    ),

    'american_family': ParkNetting(
        park_key='american_family',
        park_name='American Family Field',
        published='Sections 108-128',
        ranges=(NettedRange('', 108, 128, 'Sections 108-128'),),
        height='~33 ft, measured from the warning-track surface',
        source='https://www.mlb.com/brewers/ballpark/netting',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
    ),

    'nationals_park': ParkNetting(
        park_key='nationals_park',
        park_name='Nationals Park',
        published='Terra Club A-E; PNC Diamond Club 119-126; Sections 109-118 '
                  'and 127-135',
        ranges=(
            NettedRange('', 119, 126, 'PNC Diamond Club 119-126'),
            NettedRange('', 109, 118, 'Sections 109-118'),
            NettedRange('', 127, 135, 'Sections 127-135'),
        ),
        height='varies by section',
        source='https://www.mlb.com/nationals/ballpark/netting',
        source_kind='primary',
        year=2026,
        year_basis=PRIMARY_YEAR_BASIS,
        unenumerable=('Terra Club A-E',),
        notes=(
            'The club puts the PNC Diamond Club at 119-126; this park\'s zone '
            'table puts it at 104-107. One of the two is wrong about the same '
            'named product, which is as direct a contradiction as this file '
            'contains. See the join gap.',
            'Page text references the 2026 season explicitly.',
        ),
    ),
}


# ============================================================
# Joining published extents onto a park's zone table
# ============================================================

# Levels at the front of the bowl. A zone here whose printed series the source
# never mentions is `unknown`: netting hangs in front of the front row, so an
# unlisted field-level series could be either side of it. Behind the front
# level the same silence means exposed — a net in front of the field boxes
# does not screen the deck above them, and no club lists an upper deck as
# netted.
_FRONT_LEVELS = frozenset({'field'})


def _zone_numbers(section) -> dict[str, list[int]]:
    """Printed section numbers a zone covers, grouped by label prefix.

    Suffixed labels (Wrigley's 319R, Rogers' 113C) collapse to their number:
    the suffix splits one printed section across an aisle and never changes
    which section the sign says.
    """
    out: dict[str, list[int]] = {}
    for rng in parse_printed_ranges(section.name):
        out.setdefault(rng.prefix, [])
        for n in range(rng.start, rng.end + 1):
            if n not in out[rng.prefix]:
                out[rng.prefix].append(n)
    return out


def _label(prefix: str, number: int) -> str:
    return f"{prefix}{number}"


def _classify_zone(section, park: ParkNetting) -> ZoneNetting:
    """Status of one zone against one park's netted ranges."""
    numbers = _zone_numbers(section)
    if not numbers:
        return ZoneNetting(
            section.section_id, 'unknown',
            'zone name carries no printed section range to join on', park,
        )

    prefixes_in_extent = {r.prefix for r in park.ranges}
    netted: list[str] = []
    exposed: list[str] = []
    unspoken_prefixes: list[str] = []

    for prefix, nums in numbers.items():
        if prefix not in prefixes_in_extent:
            unspoken_prefixes.append(prefix or '(bare)')
            continue
        for n in nums:
            label = _label(prefix, n)
            if any(r.contains(prefix, n) for r in park.ranges):
                netted.append(label)
            else:
                exposed.append(label)

    if unspoken_prefixes and not netted and not exposed:
        series = ', '.join(sorted(unspoken_prefixes))
        if section.level in _FRONT_LEVELS:
            return ZoneNetting(
                section.section_id, 'unknown',
                f'printed series {series} is not named anywhere in the '
                f'published extent, and this zone is at the front of the '
                f'bowl where the net hangs', park,
            )
        return ZoneNetting(
            section.section_id, 'not_netted',
            f'printed series {series} appears nowhere in the published '
            f'extent, and this zone sits behind the front of the bowl', park,
            exposed_labels=tuple(
                _label(p, n) for p, ns in numbers.items() for n in ns
            ),
        )

    if netted and not exposed:
        return ZoneNetting(
            section.section_id, 'netted',
            f'all {len(netted)} printed sections in this zone are inside the '
            f'published extent', park, tuple(netted), (),
        )
    if netted and exposed:
        return ZoneNetting(
            section.section_id, 'partially_netted',
            f'{len(netted)} of {len(netted) + len(exposed)} printed sections '
            f'in this zone are inside the published extent '
            f'({", ".join(netted)} netted; {", ".join(exposed)} not)',
            park, tuple(netted), tuple(exposed),
        )
    return ZoneNetting(
        section.section_id, 'not_netted',
        'no printed section in this zone is inside the published extent',
        park, (), tuple(exposed),
    )


def _netted_fraction(z: ZoneNetting) -> float | None:
    total = len(z.netted_labels) + len(z.exposed_labels)
    if total == 0:
        return None
    return len(z.netted_labels) / total


def _check_join(stadium, zones: dict[str, ZoneNetting]) -> tuple[str, str]:
    """Coherence checks on a completed join. Returns (detail, '') if it holds.

    Three ways a join is rejected. None of them tests whether the model's
    labels are *right* — they test whether the published extent and the
    labels can both be true at once.

      G1  Nothing matched. Every published label falls outside every zone, so
          the two are numbering different things. Yankee Stadium: the club
          nets 011-029 and the zone table numbers the same deck 109-131.

      G2  A behind-the-plate zone at the front of the bowl is not fully
          netted. Every extent in this file is described as running from
          behind home plate outward, and the league has required netting
          behind the plate at all 30 clubs since 2020, so a join that leaves
          the plate open has mismatched the labels, not found an uncovered
          backstop.

      G3  Coverage rises as you move away from the plate on one side. Netting
          starts behind the plate and stops somewhere down the line; it cannot
          skip the near zone and resume at the far one. When this fires the
          zone table has usually put one label range on the wrong side of the
          park — Busch, where 127-133 and 157-167 are both marked 3B.

    Returns ('', '') when the join holds, otherwise (gap_kind, detail).
    """
    determinate = [z for z in zones.values()
                   if z.status in ('netted', 'partially_netted', 'not_netted')]
    if not any(z.status in ('netted', 'partially_netted') for z in determinate):
        return ('labels_contradict_model',
                'no printed section in any zone falls inside the published '
                'extent, so the club and the zone table are numbering this '
                'park differently')

    by_id = {s.section_id: s for s in stadium.sections}

    for z in zones.values():
        sec = by_id.get(z.zone_id)
        if sec is None or sec.side != 'HOME' or sec.level not in _FRONT_LEVELS:
            continue
        if z.status in ('netted', 'unknown'):
            continue
        return ('labels_contradict_model',
                f'{z.zone_id} is the behind-plate zone at the front of the '
                f'bowl and the published extent leaves it {z.status} '
                f'({z.reason}); every extent in this file runs from behind '
                f'the plate outward, so the labels cannot both be right')

    for side in ('1B', '3B'):
        ordered = sorted(
            (z for z in zones.values()
             if by_id.get(z.zone_id) is not None
             and by_id[z.zone_id].side == side
             and by_id[z.zone_id].level in _FRONT_LEVELS
             and _netted_fraction(z) is not None),
            # Mid-angle descending: 90 is square behind the plate, 0 is down
            # the foul line, so this walks outward from the plate.
            key=lambda z: -0.5 * (by_id[z.zone_id].angle_min
                                  + by_id[z.zone_id].angle_max),
        )
        for near, far in zip(ordered, ordered[1:]):
            f_near, f_far = _netted_fraction(near), _netted_fraction(far)
            if f_far > f_near + 1e-9:
                return ('labels_contradict_model',
                        f'on the {side} side the published extent covers '
                        f'{f_far:.0%} of {far.zone_id} but only {f_near:.0%} '
                        f'of {near.zone_id}, which is nearer the plate; '
                        f'netting cannot skip the near zone and resume at the '
                        f'far one, so one of these label ranges is on the '
                        f'wrong side')

    return ('', '')


def _unmatched_published(stadium, park: ParkNetting) -> tuple[str, ...]:
    """Published labels that no zone in this park's table claims.

    Usually harmless — an extent reaching sections the zone table simply does
    not enumerate — but it is the difference between "the model says these
    seats are exposed" and "the model has never heard of these seats".
    """
    claimed: set[tuple[str, int]] = set()
    for sec in stadium.sections:
        for prefix, nums in _zone_numbers(sec).items():
            for n in nums:
                claimed.add((prefix, n))

    out = []
    for r in park.ranges:
        missing = [n for n in range(r.start, r.end + 1)
                   if (r.prefix, n) not in claimed]
        if missing:
            out.append(f'{r.raw}: no zone covers '
                       f'{", ".join(_label(r.prefix, n) for n in missing)}')
    return tuple(out)


# One join per park. The zone table for a key is a constant — the factories
# rebuild identical sections on every call — so the join is too, and the
# factories are called per web request. Same assumption `stadium.py` makes for
# its band cache.
_JOIN_CACHE: dict[str, ParkJoin] = {}


def join_park(stadium, park_key: str) -> ParkJoin:
    """Join a park's published netting onto its zone table.

    Returns a `ParkJoin` whose `zones` maps every zone ID in the stadium to a
    `ZoneNetting`, whatever the outcome — a rejected join yields `unknown` for
    every zone with the rejection as the reason, never a missing key.
    """
    cached = _JOIN_CACHE.get(park_key)
    if cached is not None:
        return cached
    result = _join_park_uncached(stadium, park_key)
    _JOIN_CACHE[park_key] = result
    return result


def _join_park_uncached(stadium, park_key: str) -> ParkJoin:
    park = PARK_NETTING[park_key]

    def _all_unknown(reason: str) -> dict[str, ZoneNetting]:
        return {s.section_id: ZoneNetting(s.section_id, 'unknown', reason, park)
                for s in stadium.sections}

    if park.gap_kind is not None:
        detail = {
            'club_publishes_no_sections':
                'the club publishes an extent in words but no section numbers',
            'club_declines_to_publish':
                'the club states it will not publish section-level locations',
            'no_primary_source':
                'no netting text on the club\'s own pages',
            'no_source_at_all':
                'no park-specific netting source of any kind',
            'source_conflict':
                'the club\'s own page carries two incompatible statements',
            'arc_endpoints_unresolved':
                'the club gives arc endpoints on a numbering that wraps '
                'behind the plate, and the wrap point is unpublished',
        }[park.gap_kind]
        return ParkJoin(park_key, 'source_gap', park,
                        _all_unknown(f'no netting data to apply: {detail}'),
                        gap_kind=park.gap_kind, gap_detail=detail)

    zones = {s.section_id: _classify_zone(s, park) for s in stadium.sections}
    gap_kind, detail = _check_join(stadium, zones)
    unmatched = _unmatched_published(stadium, park)

    if gap_kind:
        return ParkJoin(
            park_key, 'join_gap', park,
            _all_unknown(f'published extent could not be reconciled with this '
                         f'park\'s printed section labels: {detail}'),
            gap_kind=gap_kind, gap_detail=detail,
            unmatched_published=unmatched,
        )

    return ParkJoin(park_key, 'mapped', park, zones,
                    flags=_join_flags(stadium, zones, park),
                    unmatched_published=unmatched)


def _join_flags(stadium, zones: dict[str, ZoneNetting],
                park: ParkNetting) -> tuple[str, ...]:
    """Non-fatal observations about an accepted join."""
    by_id = {s.section_id: s for s in stadium.sections}
    flags: list[str] = []

    if park.unenumerable:
        flags.append(
            'the club also nets products it does not number ('
            + '; '.join(park.unenumerable)
            + '), so an unlisted zone at the front of the bowl may be netted '
              'without appearing here'
        )

    def side_cover(side: str) -> float | None:
        fracs = [_netted_fraction(z) for z in zones.values()
                 if by_id.get(z.zone_id) is not None
                 and by_id[z.zone_id].side == side
                 and by_id[z.zone_id].level in _FRONT_LEVELS
                 and _netted_fraction(z) is not None]
        return sum(fracs) / len(fracs) if fracs else None

    c1, c3 = side_cover('1B'), side_cover('3B')
    if c1 is not None and c3 is not None and abs(c1 - c3) > 0.25:
        flags.append(
            f'coverage is markedly asymmetric — {c1:.0%} of the 1B field '
            f'zones against {c3:.0%} of the 3B. Real installations are '
            f'sometimes asymmetric, so this is reported rather than rejected'
        )

    if park.partial_labels:
        flags.append(
            'the club marks '
            + ', '.join(f'section {s}' for s in park.partial_labels)
            + ' as only partially covered; the join treats it as netted like '
              'any other listed section'
        )
    return flags


def zone_netting_map(stadium, park_key: str) -> dict[str, ZoneNetting]:
    """Per-zone netting status for a park, keyed by zone ID."""
    return join_park(stadium, park_key).zones


def interpretations() -> list[tuple[str, str, str]]:
    """Every place turning a source's wording into numbers took a judgment.

    (park_key, the source's wording, what was decided). This is the whole
    audit surface between `SOURCED_DATA.md` and the ranges above.
    """
    out = []
    for key, park in PARK_NETTING.items():
        for r in park.ranges:
            if r.interpretation:
                out.append((key, r.raw, r.interpretation))
    return out


def netting_report(stadiums: dict) -> str:
    """Fleet-wide netting coverage, one line per park plus the gap detail.

    `stadiums` is the `stadium.STADIUMS` factory registry, passed in rather
    than imported so this module stays free of a cycle.
    """
    lines: list[str] = []
    counts = {'mapped': 0, 'source_gap': 0, 'join_gap': 0}
    zone_counts = {'netted': 0, 'partially_netted': 0,
                   'not_netted': 0, 'unknown': 0}

    lines.append(f'{"park":<22} {"status":<11} {"net":>4} {"part":>5} '
                 f'{"open":>5} {"?":>4}  source')
    lines.append('-' * 100)

    for key, factory in stadiums.items():
        st = factory()
        j = join_park(st, key)
        counts[j.status] += 1
        tally = {'netted': 0, 'partially_netted': 0,
                 'not_netted': 0, 'unknown': 0}
        for z in j.zones.values():
            tally[z.status] += 1
            zone_counts[z.status] += 1
        year = j.park.year if j.park.year is not None else 'undated'
        lines.append(
            f'{key:<22} {j.status:<11} {tally["netted"]:>4} '
            f'{tally["partially_netted"]:>5} {tally["not_netted"]:>5} '
            f'{tally["unknown"]:>4}  {j.park.source_kind}, {year}'
        )

    lines.append('')
    lines.append(f'parks: {counts["mapped"]} mapped, '
                 f'{counts["source_gap"]} source gap, '
                 f'{counts["join_gap"]} join gap')
    lines.append(f'zones: {zone_counts["netted"]} netted, '
                 f'{zone_counts["partially_netted"]} partially netted, '
                 f'{zone_counts["not_netted"]} not netted, '
                 f'{zone_counts["unknown"]} unknown')

    lines.append('')
    lines.append('Gaps')
    lines.append('-' * 100)
    for key, factory in stadiums.items():
        st = factory()
        j = join_park(st, key)
        if j.status == 'mapped':
            continue
        lines.append(f'{key} [{j.gap_kind}]')
        lines.append(f'    {j.gap_detail}')

    lines.append('')
    lines.append('Flags on mapped parks')
    lines.append('-' * 100)
    for key, factory in stadiums.items():
        st = factory()
        j = join_park(st, key)
        for f in j.flags:
            lines.append(f'{key}: {f}')

    return '\n'.join(lines)


if __name__ == '__main__':      # pragma: no cover - operator convenience
    from .stadium import STADIUMS
    print(netting_report(STADIUMS))
