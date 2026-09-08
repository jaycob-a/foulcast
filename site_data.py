"""
site_data.py — the copy layer for the public site.

Everything the 31 park pages say about a *source* lives here, transcribed by
hand from `PARK_PARAMS.md` (foul territory, backstop, deck cover) and
`SOURCED_DATA.md` Part 2 (netting). `site_build.py` renders it; this file is
what a reader would have to check to audit a claim.

Three rules this file holds to, and the reasons they exist:

1. **No section numbers, anywhere.** `MAP_FINDINGS.md` now settles this rather
   than merely suspecting it: every seating map this project holds has been read
   against the zone tables in `foulball/stadium.py`, thirty maps covering thirty
   of the 31 parks, and twenty-seven of those tables disagree with their own
   club's drawing. A printed section number on a public page would be
   the one claim on it most likely to be wrong, and the one a reader would most
   reasonably act on. So zones are described in words, and where a source's own
   wording is a section range, it is paraphrased rather than quoted.

   This costs something and it is worth naming: it means a published netting
   height that the club states per section ("31 ft behind Sections 018-021B")
   has to be re-expressed positionally, which loses the club's precision. Those
   rewrites are held in `NET_HEIGHT_WORDS` below, one per park, next to the
   verbatim string they replace, so the two can be compared.

2. **The word "safe" does not appear on the site.** Netting is not safety.
   `SOURCED_DATA.md` records that almost every club's own wording is that fans
   in netted sections "are still exposed to objects leaving the field of play",
   and this model has never seen a real foul ball land. The site says "behind
   netting" / "not behind netting" for what is sourced, and "higher risk" /
   "lower risk" for what is modelled. `tests/test_site.py` enforces it.

3. **A figure with no source is a gap, not a default.** Two parks have no
   published foul territory (Sutter Health Park, Las Vegas Ballpark) and one has
   no published backstop (Las Vegas Ballpark). Their pages say so.

4. **No page names a foul line at a park whose sides are not established.**
   `MAP_FINDINGS.md` records a park — Oriole Park — that was `mapped`, cited,
   and had its two sides the wrong way round, invisibly, because every geometry
   number in `stadium.py` is mirror-symmetric. Only a source that names a side
   next to a section number can catch that, and `seat_map.SIDE_ANCHORS` shows
   how many of those exist: after the thirty map reads, sixteen parks of 31
   have their sides established. At the other fifteen, the two foul lines are
   shown as one seating area rather than as a first-base area and a third-base
   one, because naming them would be a claim this project cannot make.
   `PAIR_ZONE_WORDS` holds the side-neutral phrasing and `SIDE_STATE_WORDS`
   states each park's position outright. Neither count is written out in the
   site copy — `site_build.side_counts()` computes both, because they moved
   five times across Steps 11 to 16.

Source landscape, which every park page has to carry in some form:

- **Foul territory area is effectively single-sourced.** Andrew Clem estimates
  it off his own scale diagrams and says so; Seamheads credits Lowry's *Green
  Cathedrals*, and its column matches Clem at 26 of the 28 parks where both
  publish; FanGraphs credits Clem explicitly. Three sites, one estimate. Good to
  roughly +/-1,000 sq ft, not to the +/-100 the decimal implies.
- **Backstop distance is genuinely contested**, and the sources disagree at 12
  of the 31 parks, by up to 14 ft, because they measure different things: Clem
  to the rear fence, Seamheads to the stands, clubs to nothing stated. The model
  adopts Clem everywhere it can, for one reference point rather than the best
  number.
- **Deck overhang is a 2016 figure** recovered from a Wayback snapshot, and Clem
  never says what is casting the cover. Whether a park's percentage counts as an
  obstruction is a judgment call made in `stadium.py`, not a sourced fact.
"""

# ============================================================
# Source URLs
# ============================================================

CLEM_TABLE = 'http://www.andrewclem.com/Baseball/Stadium_statistics.html'
CLEM_BASE = 'http://www.andrewclem.com/Baseball/'
CLEM_OVERHANG_SNAPSHOT = (
    'https://web.archive.org/web/20161018114847/'
    'http://www.andrewclem.com:80/Baseball/Stadium_statistics.html'
)
SEAMHEADS_BASE = 'https://www.seamheads.com/ballparks/ballpark.php?parkID='
SEAMHEADS_ABOUT = 'https://www.seamheads.com/ballparks/about.php'

# Read on this date, for every figure in this file.
RESEARCH_DATE = '2026-08-09'

# The standing caveats on the three published figures. One sentence of
# provenance and one of doubt: the reader needs the size of the doubt, not the
# history of how it was established.
FOUL_AREA_CAVEAT = (
    "One source in public circulation, not three: Clem estimates it from his "
    "own diagrams and says the figures \u201care subject to revision\u201d, "
    "Seamheads matches him at 26 of the 28 parks where both publish, FanGraphs "
    "credits him. Good to about a thousand square feet, not to the hundred the "
    "figure implies."
)

BACKSTOP_CAVEAT = (
    "The figure the sources least agree on, because they measure different "
    "things &mdash; Clem to the fence at the rear, Seamheads to the stands, "
    "clubs define nothing. Clem is used throughout, for one reference point "
    "across all parks rather than the best number at each."
)

OVERHANG_CAVEAT = (
    "A 2016 figure, recovered from an archived copy of Clem\u2019s table after "
    "he stopped publishing the column, so renovations since are not in it. He "
    "gives a percentage and never says what casts the cover; whether it is "
    "something a foul ball would hit is a judgment made here, not a sourced "
    "fact."
)


# ============================================================
# Per-park sourced figures
# ============================================================
#
# Keys are `foulball.stadium.STADIUMS` keys. Fields:
#
#   slug            URL path segment for the public page
#   clem_page       filename under CLEM_BASE, or None if he has no page
#   seamheads       Seamheads park ID, or None if the park is not in the database
#   foul_area       adopted square feet, or None if unpublished
#   foul_area_basis one sentence on why that value, naming the sources
#   backstop        adopted feet, or None if unpublished
#   backstop_basis  one sentence on why that value, naming the sources
#   backstop_conflict   set when sources materially disagree; stated plainly
#   extra           optional park-specific fact worth carrying, sourced

PARK_SOURCES: dict[str, dict] = {

    'yankee_stadium': dict(
        slug='yankee-stadium',
        clem_page='YankeeStadium_II.html', seamheads='NYC21',
        foul_area=19_700,
        foul_area_basis="Clem's master table, his Yankee Stadium page and "
                        "Seamheads' 2025 row all give 19,700 sq ft.",
        backstop=52,
        backstop_basis="Clem, Seamheads and the club all agree; the club's "
                       "published figure is 52 ft 4 in.",
    ),

    'fenway_park': dict(
        slug='fenway-park',
        clem_page='FenwayPark.html', seamheads='BOS07',
        foul_area=18_100,
        foul_area_basis="Clem, his park page and Seamheads all give 18,100 sq "
                        "ft — the smallest foul territory in the majors.",
        backstop=52,
        backstop_basis="Clem's park page, updated July 2026, which supersedes "
                       "his own master table's 54 ft.",
        backstop_conflict="Wikipedia's 60 ft is the figure from before the "
                          "backstop was shortened, and is not used here. The "
                          "three published values are 52, 54 and 60 ft.",
    ),

    'dodger_stadium': dict(
        slug='dodger-stadium',
        clem_page='DodgerStadium.html', seamheads='LOS03',
        foul_area=19_300,
        foul_area_basis="Clem, his park page and Seamheads agree on 19,300 sq "
                        "ft for the current configuration.",
        backstop=53,
        backstop_basis="Clem's table and park page.",
        backstop_conflict="Seamheads says 57 ft and Wikipedia 55 ft.",
        extra="Clem records that this park had about 33,500 sq ft of foul "
              "territory from 1969 to 1999 — nearly twice what it has now — "
              "and that \"the squeezing of the once-vast foul territory yields "
              "far fewer pop foul outs\".",
    ),

    'wrigley_field': dict(
        slug='wrigley-field',
        clem_page='WrigleyField.html', seamheads='CHI11',
        foul_area=16_500,
        foul_area_basis="Clem's park page and Seamheads. His master table's "
                        "larger figure predates the seats added after 2016, "
                        "which he records as cutting about 2,000 sq ft.",
        backstop=55,
        backstop_basis="Clem, Seamheads and Wikipedia all agree.",
        extra="This is the only park with any published statement that its "
              "foul territory is lopsided: Clem writes that there is \"more "
              "room on the first base side than on the third base side\". It "
              "is a sentence, not a measurement, and this model cannot use it "
              "— every park here is modelled as symmetric.",
    ),

    'coors_field': dict(
        slug='coors-field',
        clem_page='CoorsField.html', seamheads='DEN02',
        foul_area=24_900,
        foul_area_basis="Clem, his park page and Seamheads all agree.",
        backstop=50,
        backstop_basis="Clem and Seamheads agree at 50 ft.",
        backstop_conflict="Wikipedia says 56 ft.",
    ),

    'chase_field': dict(
        slug='chase-field',
        clem_page='ChaseField.html', seamheads='PHO01',
        foul_area=25_500,
        foul_area_basis="Clem, his park page and Seamheads all agree.",
        backstop=55,
        backstop_basis="Clem and Seamheads agree; the club publishes no figure.",
    ),

    'truist_park': dict(
        slug='truist-park',
        clem_page='TruistPark.html', seamheads='ATL03',
        foul_area=22_300,
        foul_area_basis="Clem, his park page and Seamheads all agree.",
        backstop=53,
        backstop_basis="Clem and Seamheads agree, but Clem writes his figure "
                       "in parentheses, his own notation for an estimate.",
    ),

    'camden_yards': dict(
        slug='oriole-park-at-camden-yards',
        clem_page='CamdenYards.html', seamheads='BAL12',
        foul_area=23_600,
        foul_area_basis="Clem, his park page and Seamheads all agree. The 2022 "
                        "left-field rebuild changed fair territory, not foul.",
        backstop=54,
        backstop_basis="Clem and Seamheads agree; the club publishes no figure.",
    ),

    'citizens_bank': dict(
        slug='citizens-bank-park',
        clem_page='CitizensBankPark.html', seamheads='PHI13',
        foul_area=24_500,
        foul_area_basis="Clem, his park page and Seamheads all agree.",
        backstop=50,
        backstop_basis="Clem and Seamheads agree; the club publishes no figure.",
    ),

    'great_american': dict(
        slug='great-american-ball-park',
        clem_page='GreatAmericanBallpark.html', seamheads='CIN09',
        foul_area=23_600,
        foul_area_basis="Clem, his park page and Seamheads all agree.",
        backstop=50,
        backstop_basis="Clem's table and park page.",
        backstop_conflict="Seamheads says 51 ft and Wikipedia 55 ft.",
    ),

    'progressive_field': dict(
        slug='progressive-field',
        clem_page='ProgressiveField.html', seamheads='CLE08',
        foul_area=21_900,
        foul_area_basis="Clem, his park page and Seamheads all agree.",
        backstop=60,
        backstop_basis="Clem and Wikipedia agree at 60 ft — joint-longest in "
                       "the majors.",
        backstop_conflict="Seamheads says 65 ft.",
    ),

    'comerica_park': dict(
        slug='comerica-park',
        clem_page='ComericaPark.html', seamheads='DET05',
        foul_area=26_500,
        foul_area_basis="Clem, his park page and Seamheads all agree — the "
                        "largest foul territory of any open-air park.",
        backstop=55,
        backstop_basis="Clem's table and park page.",
        backstop_conflict="Seamheads says 52 ft, i.e. it puts the stands "
                          "nearer than Clem puts the fence behind them. That "
                          "cannot be a difference of definition, so one of the "
                          "two is simply wrong.",
    ),

    'minute_maid': dict(
        slug='daikin-park',
        clem_page='MinuteMaidPark.html', seamheads='HOU03',
        foul_area=21_000,
        foul_area_basis="Clem, his park page and Seamheads all agree.",
        backstop=49,
        backstop_basis="Clem, Seamheads and Wikipedia all agree.",
    ),

    'kauffman_stadium': dict(
        slug='kauffman-stadium',
        clem_page='KauffmanStadium.html', seamheads='KAN06',
        foul_area=22_900,
        foul_area_basis="Clem, his park page and Seamheads all agree. This is "
                        "also the median of the 29 parks with a published "
                        "figure, which makes it the reference the model scales "
                        "every other park against.",
        backstop=45,
        backstop_basis="Clem and Seamheads agree at 45 ft. Clem documents the "
                       "1999 box seats that cut the backstop \"from 60 feet to "
                       "about 50\", and has since revised further.",
        backstop_conflict="Wikipedia's 60 ft is the 1973 as-built figure and "
                          "is 27 years stale.",
    ),

    'angel_stadium': dict(
        slug='angel-stadium',
        clem_page='AngelStadium.html', seamheads='ANA01',
        foul_area=21_500,
        foul_area_basis="Clem, his park page and Seamheads all agree.",
        backstop=56,
        backstop_basis="Clem's park page, updated August 2026, for the current "
                       "era of the park.",
        backstop_conflict="The widest disagreement in the file: Clem's own "
                          "master table says 59 ft, Seamheads 60 ft and "
                          "Wikipedia 60.5 ft. Clem notes that most sources "
                          "have the backstop originally at 55 ft and later "
                          "raised to 60.",
    ),

    'citi_field': dict(
        slug='citi-field',
        clem_page='CitiField.html', seamheads='NYC20',
        foul_area=20_700,
        foul_area_basis="Clem, his park page and Seamheads all agree.",
        backstop=46,
        backstop_basis="Clem and Seamheads agree; the club publishes no figure.",
    ),

    'oakland_coliseum': dict(
        slug='sutter-health-park',
        clem_page='SutterHealthPark.html', seamheads='SAC01',
        foul_area=None,
        foul_area_basis="Not published. Clem has a page for this park but "
                        "leaves the foul-territory cell blank, as does "
                        "Seamheads. All that exists is his sentence that the "
                        "park has \"a very constricted foul territory, though "
                        "the sharply acute angle of the grandstand does "
                        "provide more room between home plate and the "
                        "dugouts\". The model does not scale this park's "
                        "seating bands, because there is nothing to scale them "
                        "by.",
        backstop=58,
        backstop_basis="Clem, Seamheads and Wikipedia all give 58 ft, though "
                       "Clem writes his in parentheses to mark it an estimate.",
    ),

    'las_vegas_ballpark': dict(
        slug='las-vegas-ballpark',
        clem_page=None, seamheads=None,
        foul_area=None,
        foul_area_basis="Not published anywhere. The park is in neither Clem's "
                        "registry nor the Seamheads database, and Wikipedia "
                        "gives no figure. The model does not scale this park's "
                        "seating bands.",
        backstop=None,
        backstop_basis="Not published anywhere. This is the one park where the "
                       "model positions the seats behind the plate off an "
                       "unsourced number — 52 ft — because the position has to "
                       "be somewhere. Treat every distance on this page as "
                       "weaker than at the other 30 parks.",
    ),

    'pnc_park': dict(
        slug='pnc-park',
        clem_page='PNCPark.html', seamheads='PIT08',
        foul_area=22_200,
        foul_area_basis="Clem, his park page and Seamheads all agree.",
        backstop=51,
        backstop_basis="Clem, Seamheads and Wikipedia all agree.",
    ),

    'petco_park': dict(
        slug='petco-park',
        clem_page='PETCOPark.html', seamheads='SAN02',
        foul_area=23_900,
        foul_area_basis="Clem, his park page and Seamheads all agree.",
        backstop=45,
        backstop_basis="Clem and Seamheads agree, and Clem's own prose "
                       "corroborates it: \"the backstop is only 45 feet from "
                       "home plate, so most fans are close to the action\".",
    ),

    'oracle_park': dict(
        slug='oracle-park',
        clem_page='ATTPark.html', seamheads='SFO03',
        foul_area=25_500,
        foul_area_basis="Clem's master table and Seamheads. His park page is "
                        "from 2019 and is older than the table, so the table "
                        "is taken.",
        backstop=54,
        backstop_basis="Clem's master table and Seamheads.",
        backstop_conflict="Wikipedia says 48 ft.",
    ),

    'tmobile_park': dict(
        slug='t-mobile-park',
        clem_page='SafecoField.html', seamheads='SEA03',
        foul_area=24_300,
        foul_area_basis="Clem's master table and Seamheads. His park page is "
                        "from 2023 and is older than the table.",
        backstop=56,
        backstop_basis="Clem's master table and park page.",
        backstop_conflict="The worst disagreement of the 31 parks. Seamheads "
                          "says 55 ft; the Mariners' own published dimension, "
                          "carried by Wikipedia and Ballparks of Baseball, is "
                          "69 ft. A gap of 13 to 14 ft is too large for "
                          "measurement "
                          "error and is almost certainly two different "
                          "reference points. Clem's 56 ft is used because it "
                          "is the reference point every other park here uses, "
                          "not because it is more likely to be right.",
    ),

    'busch_stadium': dict(
        slug='busch-stadium',
        clem_page='BuschStadium_III.html', seamheads='STL10',
        foul_area=25_200,
        foul_area_basis="Clem's master table and park page both give 25,200 sq "
                        "ft; Seamheads gives 25,400.",
        backstop=52,
        backstop_basis="Clem and Seamheads agree; the club publishes no figure.",
    ),

    'tropicana_field': dict(
        slug='tropicana-field',
        clem_page='TropicanaField.html', seamheads='STP01',
        foul_area=25_300,
        foul_area_basis="Clem, his park page and Seamheads all agree. "
                        "Seamheads' most recent configuration row is 2024, "
                        "because the Rays did not play here in 2025.",
        backstop=50,
        backstop_basis="Clem, Seamheads and Wikipedia all agree.",
        extra="The park reopened for 2026 after roughly $60M of hurricane "
              "repairs, including a new roof. None of the figures on this page "
              "have been re-measured since.",
    ),

    'globe_life': dict(
        slug='globe-life-field',
        clem_page='GlobeLifeField.html', seamheads='ARL03',
        foul_area=23_100,
        foul_area_basis="Clem, his park page and Seamheads all agree.",
        backstop=42,
        backstop_basis="Clem, Seamheads and Wikipedia all agree — the shortest "
                       "backstop in the majors.",
    ),

    'rogers_centre': dict(
        slug='rogers-centre',
        clem_page='RogersCentre.html', seamheads='TOR02',
        foul_area=30_500,
        foul_area_basis="Clem's park page, updated July 2026, superseding his "
                        "master table's smaller figure. Seamheads does not "
                        "publish one. This is the largest foul territory in "
                        "the majors.",
        backstop=54,
        backstop_basis="Clem's table and park page.",
        backstop_conflict="Wikipedia says 60 ft.",
    ),

    'target_field': dict(
        slug='target-field',
        clem_page='TargetField.html', seamheads='MIN04',
        foul_area=20_700,
        foul_area_basis="Clem's master table and park page both give 20,700 sq "
                        "ft; Seamheads gives 20,400.",
        backstop=45,
        backstop_basis="Clem's park page — which flags the figure itself: "
                       "\"Backstop distance is estimated.\"",
        backstop_conflict="Clem's own master table and Seamheads both say 48 ft.",
    ),

    'guaranteed_rate': dict(
        slug='rate-field',
        clem_page='RateField.html', seamheads='CHI12',
        foul_area=25_000,
        foul_area_basis="Clem, his park page and Seamheads all agree.",
        backstop=60,
        backstop_basis="Clem, Seamheads and Wikipedia all agree — joint-longest "
                       "in the majors.",
        extra="One structural detail here bears directly on foul balls and is "
              "not in the model: the 2002 renovation replaced the old "
              "netted-roof backstop with a \"roofless\" one that lets fouls "
              "drop into the seats directly behind home plate. Together with "
              "the long backstop, both facts push the same way, and the model "
              "captures only the second of them.",
    ),

    'loan_depot': dict(
        slug='loandepot-park',
        clem_page='MarlinsPark.html', seamheads='MIA02',
        foul_area=21_000,
        foul_area_basis="Clem's master table and Seamheads. His park page is "
                        "from 2023 and is older than the table.",
        backstop=50,
        backstop_basis="Clem's table and park page.",
        backstop_conflict="Seamheads and Wikipedia both say 47 ft — again "
                          "placing the stands nearer than Clem places the "
                          "fence behind them, which no difference of "
                          "definition can produce.",
    ),

    'american_family': dict(
        slug='american-family-field',
        clem_page='MillerPark.html', seamheads='MIL06',
        foul_area=21_100,
        foul_area_basis="Clem, his park page and Seamheads all agree.",
        backstop=56,
        backstop_basis="Clem, Seamheads and Wikipedia all agree.",
    ),

    'nationals_park': dict(
        slug='nationals-park',
        clem_page='NationalsPark.html', seamheads='WAS11',
        foul_area=22_800,
        foul_area_basis="Clem's park page, updated July 2026, superseding his "
                        "master table. Seamheads does not publish one.",
        backstop=45,
        backstop_basis="Clem and Seamheads agree; the club publishes no figure.",
    ),
}


# ============================================================
# Deck cover, in words
# ============================================================
#
# The percentages are Clem's 2016 columns (PARK_PARAMS.md Part 3); the
# classification — deck, canopy, or stadium roof — is the judgment call
# `stadium.py` makes and `PARK_PARAMS.md` gap 11a flags as the
# highest-leverage unsourced decision in the layer. Both are stated, so a
# reader can see which one is doing the work.

COVER_WORDS = {
    'deck': 'the back of the deck above it',
    'canopy': 'a grandstand roof directly over the seats',
    'stadium_roof': 'the stadium roof, well over a hundred feet up',
}

COVER_APPLIED = {
    'deck': True,
    'canopy': True,
    'stadium_roof': False,
}


# ============================================================
# Published netting heights, re-expressed without section numbers
# ============================================================
#
# Two clubs publish their net heights against section numbers. Rule 1 above
# forbids printing those numbers, so both statements are re-expressed
# positionally here, verbatim source alongside. Everything else either
# publishes a single figure (safe to quote) or says only "varies by section".

NET_HEIGHT_WORDS = {
    'yankee_stadium': (
        'about 31 ft above the field wall directly behind the plate, stepping '
        'down to roughly 11 ft 6 in above the wall on either side of that, '
        '9 ft above each dugout — raised a further 3 ft before the game — and '
        'about 14 ft above the field along the rest of the run',
        # verbatim source string, for comparison:
        "31 ft above the field wall behind the plate (Sections 018-021B); "
        "11'6\" above the wall in front of 017B and 022; 9 ft above the "
        "dugouts, retractable up 3 ft pregame; 11'6\" above the wall at 025 "
        "and 015A; ~14 ft above field (~11'6\" above walls) from 014B->011 and "
        "026->029",
    ),
    'tmobile_park': (
        '27 ft through the infield stretch behind and beside home plate, and '
        '13.5 ft above field level along the rest of each line',
        '27 ft in front of Sections 126-134; 13.5 ft above field level for '
        '115-125 and 135-146',
    ),
}


# ============================================================
# Zones, in words
# ============================================================
#
# `stadium.py` gives every zone a printed-label name ("1B Dugout Box (Sec
# 109-114)"). The numbers in those names are the part `AUDIT.md` condemns, so
# the site never shows them. What survives is the grouping and the deck level,
# which is the part the audit's revised claim still credits — and even that is
# credited only "at the level of grouping and deck level", so these phrases are
# deliberately positional rather than precise.
#
# `ZONE_WORDS` is keyed by the zone ID and gives (heading, level phrase). The
# park's own area word — Loge, Terrace, Grandstand, Club — is appended by
# `site_build.py` where it adds something, with the same hedge.

ZONE_WORDS: dict[str, tuple[str, str]] = {
    'HOME-DC':  ('The club seats at field level behind home plate',
                 'field level, the closest rows behind the plate'),
    'HOME-F':   ('The seats at field level behind home plate',
                 'field level, behind the plate'),
    'HOME-B':   ('The lower bowl behind home plate',
                 'one deck above field level, behind the plate'),
    'HOME-U':   ('The upper deck behind home plate',
                 'upper deck, behind the plate'),
    'HOME-G':   ('The top deck behind home plate',
                 'top deck, behind the plate'),

    '1B-FB1':   ('The infield boxes on the first-base side',
                 'field level, between the plate and the dugout'),
    '1B-DUG':   ('The dugout boxes and field seats down the first-base line',
                 'field level, from the dugout outward'),
    '1B-LB1':   ('The second level on the first-base side',
                 'one deck above field level, first-base side'),
    '1B-LR':    ('The lower reserved seats down the first-base line',
                 'one deck above field level, well down the line'),
    '1B-UB':    ('The upper deck on the first-base side',
                 'upper deck, first-base side'),
    '1B-UR':    ('The back of the upper deck on the first-base side',
                 'upper deck, rear rows'),

    '3B-FB1':   ('The infield boxes on the third-base side',
                 'field level, between the plate and the dugout'),
    '3B-DUG':   ('The dugout boxes and field seats down the third-base line',
                 'field level, from the dugout outward'),
    '3B-LB1':   ('The second level on the third-base side',
                 'one deck above field level, third-base side'),
    '3B-LR':    ('The lower reserved seats down the third-base line',
                 'one deck above field level, well down the line'),
    '3B-UB':    ('The upper deck on the third-base side',
                 'upper deck, third-base side'),
    '3B-UR':    ('The back of the upper deck on the third-base side',
                 'upper deck, rear rows'),
}

# The same zones, for the twenty-two parks where nothing establishes which
# foul line is which. Keyed by the zone ID's suffix, so `1B-DUG` and `3B-DUG`
# fold into one row described as both lines at once.
#
# This is not a softening of `ZONE_WORDS`; it is a different claim. "The
# dugout boxes on the first-base side" asserts a side. "The dugout boxes down
# the two foul lines" asserts only that there are two of them, which is what
# the model's table actually supports at these parks. The figure shown against
# a folded row is what reaches *one* line, so it stays comparable with the
# behind-plate rows beside it rather than being twice their size.

PAIR_ZONE_WORDS: dict[str, tuple[str, str]] = {
    'FB1': ('The infield boxes down the two foul lines',
            'field level, between the plate and the dugouts'),
    'DUG': ('The dugout boxes and field seats down the two foul lines',
            'field level, from the dugouts outward'),
    'LB1': ('The second level down the two foul lines',
            'one deck above field level, off the infield'),
    'LR':  ('The lower reserved seats down the two foul lines',
            'one deck above field level, well down the lines'),
    'UB':  ('The upper deck down the two foul lines',
            'upper deck, off the infield'),
    'UR':  ('The back of the upper deck down the two foul lines',
            'upper deck, rear rows'),
}

# Area words worth appending to a zone heading. Anything not listed here is
# either a bare deck word the heading already says ("Upper", "Field") or a
# number-derived label ("200 Level", "500 Level") that would reintroduce
# section numbering by the back door.
AREA_WORDS = {
    'Loge': 'the loge',
    'Terrace': 'the terrace',
    'Grandstand': 'the grandstand',
    'Club': 'the club level',
    'Mezzanine': 'the mezzanine',
    'Promenade': 'the promenade',
    'Excelsior': 'the Excelsior level',
    'Hall of Fame Club': 'the Hall of Fame Club',
    'Press Level': 'the press level',
    'Press': 'the press level',
    'Diamond Club': 'the Diamond Club',
    'Dugout Club': 'the Dugout Club',
    'Diamond': 'the Diamond boxes',
    'Field MVP': 'the Field MVP boxes',
    'View Reserve': 'the View Reserved seats',
    'View': 'the View level',
    'Reserve': 'the Reserved level',
}


# ============================================================
# Netting gap reasons, in words
# ============================================================
#
# `netting.ParkJoin.gap_detail` states each reason precisely, and several of
# those statements quote section numbers. These are the public rewrites: same
# reason, no numbers, and no softening. A reader has to be able to tell the
# difference between "nobody published this" and "somebody published it and it
# does not fit".

GAP_WORDS: dict[str, tuple[str, str]] = {
    # gap_kind: (short label, the reason, in two sentences at most). The
    # sentence every one of these used to end on — that nothing on the page is
    # marked as behind netting — is said once, by the panel, rather than ten
    # times here.
    'club_publishes_no_sections': (
        'The club describes its netting but names no seating areas',
        "It states how far the netting runs in words, without saying which "
        "seats that covers. There is no way to attach the statement to a part "
        "of this ballpark without guessing.",
    ),
    'club_declines_to_publish': (
        'The club declines to publish where its netting is',
        "It states outright that it will not give the locations: its own map, "
        "it says, shows only the general area, and \u201cit is not possible for "
        "a map like this to show the precise location of the netting\u201d.",
    ),
    'no_primary_source': (
        'The club publishes no netting information',
        "Nothing on the club's own pages describes the netting. A second-hand "
        "figure exists but has never been checked against a primary source, so "
        "it is not used here.",
    ),
    'no_source_at_all': (
        'No netting information exists for this park',
        "Neither the club nor the ballpark publishes anything about the extent "
        "of its netting. The one authority that reaches this park is a rule "
        "placed on the club, not an observation of what is installed.",
    ),
    'source_conflict': (
        "The club's own netting page contradicts itself",
        "It carries two statements that cannot both describe the same "
        "installation &mdash; one running the netting the full length of both "
        "foul lines, the other stopping it near the plate. One of them appears "
        "to be stale text nobody removed.",
    ),
    'arc_endpoints_unresolved': (
        'The published endpoints sit on a numbering that wraps behind the plate',
        "The club gives the two ends of its netting run, but this park's seat "
        "numbering wraps behind home plate at a point nobody publishes. "
        "Without that wrap point, the run between the endpoints cannot be read "
        "off.",
    ),
    'labels_contradict_model': (
        "The club's netting map and this model's seating labels disagree",
        "The club does publish where its netting runs. Under the labels this "
        "model carries, that netting would either miss the seats behind home "
        "plate or skip a nearer area and resume at a further one, and netting "
        "does neither &mdash; so the club's page is the sourced side of the "
        "disagreement and this model is the unsourced one.",
    ),
    'labels_wrap_unpublished': (
        "This model's own seating labels cannot describe a continuous bowl here",
        "They put one foul line on both sides of the plate at once, so the "
        "numbering has to wrap somewhere no source states. Any published range "
        "read against them would net the far end of a foul line and leave the "
        "near end open, which is not how netting is installed.",
    ),
    'sides_unverifiable': (
        'Nothing establishes which side of this park is which',
        "The labels run outward from the plate in both directions rather than "
        "around the bowl, and no source says which of the two blocks is the "
        "first-base side. The published netting stops short of the whole field "
        "level, so the answer would change which seats came out behind it.",
    ),
    'sides_flipped': (
        "This model has this park's two sides the wrong way round",
        "The ballpark's own map numbers the lower bowl one way around the "
        "plate and this model's labels run the opposite way, so every area it "
        "calls first-base side is in fact on the third-base side. The map is "
        "the sourced side of that disagreement.",
    ),
}


# ============================================================
# Which foul line is which, park by park
# ============================================================
#
# `seat_map.check_side_anchors` returns one of four verdicts per park. These
# are the public rewrites, and the distinction they have to carry is the one
# `MAP_FINDINGS.md` was written around: **passing is not the same as not being
# tested.** Oriole Park spent Step 10 in the mapped list, cited, with its two
# sides swapped, because nothing in the repo could tell the difference. Sixteen
# of the 31 parks are still in the position Oriole Park was in — untested, not
# vindicated — and their pages have to say which.
#
# Keyed by verdict: (short label, paragraph).

SIDE_STATE_WORDS: dict[str, tuple[str, str]] = {
    'confirmed': (
        'Established, against a source that names a side',
        "A source outside this model says which foul line is which &mdash; the "
        "club naming a side beside specific seats, or the park's own seating "
        "map read with a landmark fixing which way round the drawing runs "
        "&mdash; and every seat label this model puts on one line lands on "
        "that line in the source. That is why this page names the two sides. "
        "It establishes nothing else: not where the boundaries between areas "
        "fall, not whether the areas exist.",
    ),
    'untested': (
        'Never tested \u2014 this model could have the two lines swapped',
        "Nothing available for this park says which foul line is which. A "
        "published netting range cannot settle it, and neither can this "
        "model's own figures: every park here is built as an exact left-right "
        "mirror, so a park with its sides swapped produces figures identical "
        "to one the right way round. That exact silence hid a real reversal at "
        "another park for the whole of this model's life. So the two lines are "
        "shown here as one seating area, and neither is named.",
    ),
    'flipped': (
        'Reversed \u2014 and this page will not print the labels backwards',
        "A source settles which foul line is which and this model gets it "
        "wrong: not one of the seat labels the ballpark's own map anchors "
        "lands where the map puts it. Because that is a clean reversal rather "
        "than a drift, the <em>figures</em> are unaffected &mdash; the mirror "
        "gives both lines the same distribution whichever way round they are "
        "labelled. The labelling is what is affected, so neither line is named "
        "here.",
    ),
    'inconsistent': (
        'Contradicted, and not by a simple reversal',
        "Some of this model's seat labels land on the side their source names "
        "and some land on the other, so swapping the two sides would not fix "
        "it. The table is wrong in a way that has no single correction, and "
        "neither foul line is named here.",
    ),
}


# ============================================================
# What the published seating maps say
# ============================================================
#
# Every seating map in `seating_maps/` has now been read directly, at
# magnification, and compared with the zone table this model carries for that
# park. That is thirty maps covering thirty of the 31 parks. `MAP_FINDINGS.md`
# is the full record, including what could not be resolved and how confident
# each read is; this is the public statement of what each one found.
#
# Twenty-seven of the thirty disagree with their zone table. Three do not:
# Daikin Park, Yankee Stadium and Dodger Stadium come out right on both
# questions a map can settle — which foul line is which, and where the seats
# behind home plate are. Those three are written up here in the same place and
# at the same length as the twenty-seven, because they were checked the same
# way and an agreement that is not published reads as an absence of evidence.
#
# Las Vegas Ballpark is the one park with no map in the folder at all. Its page
# says so rather than leaving the silence to read as a pass.
#
# The rule against printing section numbers binds here too, and hardest — a map
# finding is *about* section numbers. So every finding below is stated
# positionally: how far off, in which direction, on which deck. "Positions"
# always means printed seat labels counted along the bowl, never the labels
# themselves.
#
# Fields:
#
#   map_of    the source, in a noun phrase that starts the sentence
#   landmark  what fixes which way round the drawing runs, and how strong it is
#   quality   how legible the drawing is, as a source
#   read_on   the date it was read
#   outcome   'disagrees' or 'agrees' — the three agreements are not findings
#             of nothing, and the page has to be able to say which it is
#   findings  (heading, paragraph) pairs, positional throughout

# Step 11 read five maps; Steps 12 to 16 read the remaining twenty-five.
MAP_READ_DATE = '2026-08-11'
LATER_READ_DATE = '2026-09-07'

MAP_READS: dict[str, dict] = {

    'truist_park': dict(
        map_of="the Braves' published seating map",
        landmark='a flat plan in standard orientation, with the right-field '
                 'restaurant and the left-field porch confirming which way '
                 'round it runs',
        quality='among the cleanest of the thirty maps read',
        read_on=MAP_READ_DATE,
        outcome='disagrees',
        findings=[
            ('The area this page calls the seats behind home plate is not '
             'behind home plate',
             'On the map, the block dead behind the plate at field level is '
             'about four sections further toward first base than the block '
             'this model labels as the behind-plate area. What this model '
             'calls the behind-plate seats is really the first stretch up the '
             'third-base line, and what it calls the first-base infield boxes '
             'are really the seats behind the plate. The behind-plate figure '
             'in the model section is therefore attached to the wrong '
             'seats, and it is the largest figure on this page.'),
            ('Several of the seat labels this model carries here do not exist',
             'At field level the map runs a block of consecutive sections with '
             'no room for an unlabelled one between them, and four of the '
             'numbers this model uses on the first-base side and five on the '
             'third-base side are not among them. Three of the areas '
             'are partly built out of labels with nothing behind them, one of '
             'them more than half.'),
            ('The club\'s map and the club\'s own written guide disagree about '
             'how far the netting runs',
             'The map marks netting over a longer stretch of field level than '
             'the written guide this site uses — several sections further at '
             'each end. Both are the club\'s own current publications, so one '
             'of them is stale, and nothing in the map says which. The netting '
             'above uses the written guide, which is the shorter claim of the '
             'two.'),
        ],
    ),

    'chase_field': dict(
        map_of="the Diamondbacks' published seating map",
        landmark='a flat plan whose orientation is fixed by the swimming pool '
                 'and the right-field porch sitting on the same side of the '
                 'drawing — not by its dugout labels, which read the other way',
        quality='good, though a smaller drawing than the best of the thirty',
        read_on=MAP_READ_DATE,
        outcome='disagrees',
        findings=[
            ('The area this page calls the seats behind home plate is in the '
             'outfield corner',
             'The map puts this model\'s behind-plate labels at the far end of '
             'the right-field line, beside the pool — about as far from home '
             'plate as a foul-territory section gets. The plate on the map '
             'sits at the midpoint of a single arc of numbers, and this '
             'model\'s table was built as though the numbering started behind '
             'the plate and ran outward in both directions. The behind-plate '
             'area and both first-base areas are attached to seats '
             'somewhere else in the building; only the third-base pair is '
             'roughly where its name says.'),
            ('The two field-level areas on the first-base side are in the '
             'wrong order',
             'This model puts the dugout-and-outward area further from the '
             'plate than the infield boxes; the map has them the other way '
             'round. The third-base side runs the right way.'),
            ('This is the park the netting join already rejected, and the map '
             'says why',
             'The club does publish where its netting runs, and this model '
             'reported the two as irreconcilable before any map was read. The '
             'map supplies the reason: the netting range the club publishes '
             'and the labels this model carries are describing different parts '
             'of the building.'),
        ],
    ),

    'oakland_coliseum': dict(
        map_of="the Athletics' published seating map for Sutter Health Park",
        landmark='a flat plan whose orientation is fixed by the base markers '
                 '— not by its dugout labels, which read the other way',
        quality='a very clean drawing',
        read_on=MAP_READ_DATE,
        outcome='disagrees',
        findings=[
            ('More than half the seat labels this model carries at field level '
             'are not in the building',
             'The map shows a single ring of twenty-three sections at field '
             'level and nothing above it. This model\'s table for this park '
             'names twenty-four field-level sections and fourteen of them are '
             'numbered past where the ring ends; of the twenty-one labels it '
             'carries above field level, thirteen do not exist either. The '
             'consequence for this page is direct: every area shown as a '
             'pair of foul lines is really one block of seats that exists and '
             'one that does not, because the model\'s second line is numbered '
             'past the end of the bowl. In the upper-deck pair, one label of '
             'the fifteen is in the building.'),
            ('The only real upper seating at this ballpark is not behind the '
             'plate',
             'The map has six upper sections, all of them together on one side '
             'of the park, and none at all behind home plate. This model has '
             'an upper area behind the plate and a further pair down the two '
             'lines. The behind-plate one is those six real sections, put in '
             'the wrong place; the pair is very nearly all labels with nothing '
             'behind them.'),
            ('The area this page calls the seats behind home plate is out on a '
             'foul line',
             'The map\'s behind-plate section falls inside a different area of '
             'this model\'s table altogether. The behind-plate figure — '
             'the largest on the page — belongs to seats some way down a line.'),
            ('The labels run outward from a plate at the end of the series, '
             'which a real bowl does not do',
             'The map is a single arc with home plate at its midpoint. This '
             'model numbers both foul lines upward from a plate placed near '
             'the bottom of the range, which is the shape this project\'s own '
             'structural check calls impossible. It was never caught here '
             'because that check only runs on parks with a netting source, and '
             'this park has none.'),
        ],
    ),

    'camden_yards': dict(
        map_of="the Orioles' published seating map",
        landmark='a three-dimensional render seen from beyond the outfield, so '
                 'left and right are reversed from a plan view; the orientation '
                 'is fixed by the warehouse and the right-field porch, both on '
                 'the same side of the frame',
        quality='one of the hardest of the thirty to read — small, foreshortened '
                'labels on a three-dimensional render',
        read_on=MAP_READ_DATE,
        outcome='disagrees',
        findings=[
            ('This model has the two sides of this park the wrong way round',
             'The map has the lower bowl ascending toward third base and this '
             'model has it ascending toward first, on all three decks. Thirty '
             'anchored labels land on the opposite side from the map and none '
             'land on the named side, which is a mirror rather than a drift. '
             'This is why the netting above is reported as a gap: the club '
             'publishes a perfectly good netting range, and this model cannot '
             'be trusted to say which line either end of it is on.'),
            ('It was reported as matched, with a citation, until the map was '
             'read',
             'Every check this project had was blind to it. Every distance, '
             'angle and height in this model is identical on the two sides of '
             'every park, so a park with its sides swapped passes each of them '
             'by construction. Only a source naming a side could catch it, and '
             'this map is that source. Every ballpark on this site but one has now '
             'had its own map read, and this is the kind of error only a map '
             'could ever have found.'),
            ('The behind-plate area is also about half a block off',
             'Separately from the reversal, the map\'s behind-plate block is '
             'wider than this model\'s and centred a little further toward the '
             'third-base line. Correcting the reversal would not fix that.'),
        ],
    ),

    'fenway_park': dict(
        map_of="the Red Sox published seating map",
        landmark='a flat plan rotated so home plate is at one edge; the '
                 'orientation is fixed by the dugout labels and the two '
                 'standing-room banners, which agree with each other',
        quality='among the least legible of the thirty — a small drawing with '
                'label text a few pixels high, so the reads below are the firm '
                'ones',
        read_on=MAP_READ_DATE,
        outcome='disagrees',
        findings=[
            ('A close match on the sides, and still not a match on the plate',
             'The seat labels run the right way round on both lines here, '
             'which is why this page names them. What is off is where the '
             'plate sits within them.'),
            ('This model puts the behind-plate areas toward first base of '
             'where the map has them, on all three levels',
             'On each of the three rings the map has the block dead behind the '
             'plate a handful of sections further toward third base than this '
             'model does — enough that at the top level the area this model '
             'calls a third-base area is the one actually behind the plate. '
             'The behind-plate figures are attached to seats that sit '
             'somewhat toward the first-base side of the plate.'),
            ('Two areas stop short of where the map keeps going',
             'On the third-base side the map runs the second level and the top '
             'level several sections further than this model\'s labels do, so '
             'those two areas are short at the outer end.'),
        ],
    ),

    # --- Step 12: the six parks whose sides nothing had ever tested ---------

    'coors_field': dict(
        map_of="the Rockies' published seating map",
        landmark='a flat plan in standard orientation, fixed by the map\'s own '
                 'legend, which puts the right-field products at one end of '
                 'the bowl, and corroborated by the two foul-pole distances '
                 'printed on the drawing — the shorter of them is at the other '
                 'end, which is where this park\'s left-field line is',
        quality='the largest and cleanest drawing read for this site',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('This model has the two sides of this park the wrong way round',
             'The map has the lower bowl running up toward third base where '
             'this model has it running up toward first, on all three decks. '
             'Thirty-five anchored labels land on the opposite line from the '
             'map and none land on the line the model names, which is a mirror '
             'rather than a drift. Because it is a clean reversal the '
             'figures are unaffected — every park here is built '
             'as an exact left-right mirror, so the two lines carry the same '
             'distribution whichever way round they are labelled. What is '
             'affected is the labelling, which is why no area on this page is '
             'called first-base or third-base.'),
            ('The seats behind home plate are in the right place, and that is '
             'the whole of what the map confirms here',
             'On all three decks this model\'s behind-plate area sits where '
             'the map puts the plate, give or take a position. The reversal is '
             'the entire error, and it is the one error a mirror-symmetric '
             'model cannot detect from the inside.'),
            ('Part of one club-level area is labels with nothing behind them',
             'At the club level the map has no numbered seating directly '
             'behind the plate at all — a press box and two clubs occupy that '
             'arc — so six of the labels this model carries in its '
             'behind-plate club area are not printed anywhere on the drawing. '
             'That area\'s figure is attached to a block that is part '
             'real seats on each side of the plate and part nothing.'),
        ],
    ),

    'citizens_bank': dict(
        map_of="the Phillies' published seating map",
        landmark='a flat plan in standard orientation, fixed by the map\'s own '
                 'gate names, which label the first-base and third-base gates '
                 'on opposite sides of the frame',
        quality='poor to fair — a small drawing whose bowl labels needed three '
                'to four times magnification, though all of them resolved',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('The seat labels run the right way round on both lines, which is '
             'why this page names them',
             'The order of the seating areas along each foul line matches the '
             'map on all three decks. What is off is where the plate sits '
             'within them.'),
            ('The area this page calls the seats behind home plate is up the '
             'third-base line',
             'The map\'s behind-plate block at field level is about five '
             'positions further toward first base than the block this model '
             'labels as the behind-plate area. What this model calls its '
             'first-base infield boxes straddles the plate — part of it is on '
             'the first-base side, part is the plate block itself, and part is '
             'the third-base shoulder. The behind-plate figure is the '
             'largest on this page and it is attached to seats up a foul line.'),
            ('The two upper decks are off the same way, by three to five '
             'positions',
             'On both upper rings the behind-plate area sits toward third base '
             'of the block the map has behind the plate. The direction is the '
             'same on all three decks, which is what a table built by dividing '
             'each ring into equal arcs does.'),
            ('The map draws its netting, and cannot confirm the club\'s '
             'published endpoints either way',
             'The hatch on the drawing reads one position short of the club\'s '
             'published run at one end and two short at the other, at a '
             'resolution where a hatch on a wedge that small is at the limit '
             'of what can be resolved. The two are not in conflict; the map '
             'simply cannot settle the boundary. The netting above uses the '
             'club\'s published statement.'),
        ],
    ),

    'great_american': dict(
        map_of="the Reds' published seating map",
        landmark='a flat plan in standard orientation, fixed by the legend, '
                 'whose named right-field deck colour falls at one end of the '
                 'bowl and agrees with the drawn diamond',
        quality='fair — a small bowl inside a large legend, needing three to '
                'four times magnification',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('The seat labels run the right way round on both lines',
             'The order of the areas along each foul line matches the map at '
             'field level and on the upper deck, which is why this page names '
             'them.'),
            ('The area this page calls the seats behind home plate is up the '
             'third-base line',
             'It sits about six positions further toward third base than the '
             'block the map has dead behind the plate — far enough that it is '
             'really the first stretch of infield boxes stacked along the '
             'third-base line. What this model calls its first-base infield '
             'straddles the plate. This is the same shape of error the '
             'Braves\' map showed, in the other direction.'),
            ('The upper-deck behind-plate area is on the third-base side too, '
             'and one upper area is mostly the left-field bleachers',
             'The map\'s upper ring has its plate block several positions '
             'toward first base of where this model puts it, and the area this '
             'model calls the third-base upper deck begins with six positions '
             'that are bleachers out in left field rather than seating down a '
             'foul line.'),
            ('The second deck could not be read at all',
             'It is drawn as a row of club boxes whose labels are a few pixels '
             'high, and they did not resolve at any magnification. The three '
             'areas this page shows on that deck are therefore not checked — '
             'neither confirmed nor contradicted. That is stated rather than '
             'left out, because an unchecked deck sitting next to a checked '
             'one would otherwise read as having passed.'),
        ],
    ),

    'progressive_field': dict(
        map_of="the Guardians' published seating map",
        landmark='a flat plan in standard orientation, fixed by the map\'s own '
                 'left-field and right-field district headings on opposite '
                 'sides of the frame, with a compass rose agreeing',
        quality='good — a large drawing, readable at two to three times '
                'magnification',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('This model has the two sides of this park the wrong way round',
             'On all three decks the map runs the bowl the opposite way from '
             'this model. Twenty-two anchored labels land on the other line '
             'and none land on the line the model names, which is a mirror '
             'rather than a drift. The figures are unaffected, because '
             'every park here is an exact left-right mirror; the labelling is, '
             'which is why no area on this page is called first-base or '
             'third-base.'),
            ('The same seat labels are printed twice in this building, on '
             'opposite foul lines',
             'A run of labels appears both on the field-level bowl down one '
             'foul line and on two suite columns down the other. A bare label '
             'in that range cannot say which line it is on, so nothing outside '
             'this model can settle those positions either way — the check '
             'that caught the reversal had to stop short of them.'),
            ('The seats behind home plate are roughly in the right place on '
             'each deck',
             'One or two positions toward first base of where the map has the '
             'plate, on all three rings. The reversal is the error here; the '
             'plate block is not.'),
            ('The map\'s lower bowl skips many of the labels this model '
             'carries',
             'Along both foul lines the drawing prints numbers with gaps in '
             'them, and nine of the labels this model uses on one line and six '
             'on the other are not printed anywhere on the bowl. So several of '
             'the areas are partly built out of labels with nothing '
             'behind them.'),
        ],
    ),

    'oracle_park': dict(
        map_of="the Giants' published seating map",
        landmark='a flat plan in standard orientation, fixed by the legend — '
                 'the arcade and cove products fall beyond one end of the bowl '
                 'and two named left-field products beyond the other',
        quality='poor to fair — bowl labels a few pixels high, needing four '
                'times magnification',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('Contradicted, and not by a simple reversal',
             'Almost every anchored label lands on the opposite line from the '
             'one this model names — eleven of them — but three at the near '
             'end of the first-base run land on the side the model names. So '
             'swapping the two sides would put those three wrong while fixing '
             'the rest. The table is wrong here in a way that has no single '
             'correction, and no area on this page is called first-base or '
             'third-base.'),
            ('The area this page calls the seats behind home plate is out on '
             'the first-base line',
             'The map puts it about six positions down toward the cove, past '
             'the near end of the club ring. The behind-plate figure is '
             'the largest on this page and it belongs to seats some way down a '
             'foul line.'),
            ('The zone table names a right-field landmark for a run of seats '
             'the map puts on the third-base side',
             'This model\'s own comment for one of the areas describes '
             'it as running down the right-field line toward the cove. On the '
             'map that run is on the opposite foul line, and the cove is '
             'beyond the other end of the bowl entirely.'),
            ('The map prints the netting extent in words, and it matches the '
             'club\'s published statement exactly',
             'So the netting claim for this park is sound as far as it goes. '
             'What the map contradicts is this model\'s labelling of the seats '
             'that run is attached to, which is why the netting above is '
             'reported as a gap rather than mapped onto areas.'),
        ],
    ),

    'guaranteed_rate': dict(
        map_of="the White Sox published seating map",
        landmark='a flat plan in standard orientation — and this is the one '
                 'map read for this site that names no left-field or '
                 'right-field feature anywhere, so which way round it runs '
                 'rests on the drawn diamond alone, which is the weakest basis '
                 'of the thirty',
        quality='excellent — the most legible drawing of its round, every '
                'lower-bowl label large and clean',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('The seat labels run the right way round on both lines',
             'Both foul-line blocks land on the lines this model names, at '
             'field level and on the top deck, which is why this page names '
             'them. Read that alongside the orientation note above: it rules '
             'out a mirror against a drawing whose own orientation rests on '
             'the diamond it draws.'),
            ('The area this page calls the seats behind home plate is far down '
             'the first-base line',
             'About eighteen positions toward the right-field corner. This '
             'model has the plate near the bottom of the numbering with both '
             'foul lines running the same way from it; the map has one '
             'continuous run from pole to pole with the plate in the middle of '
             'it. The behind-plate figure — the largest on this page — '
             'is attached to seats out toward a foul pole.'),
            ('The top deck is off the same way, by twelve to seventeen '
             'positions',
             'Its behind-plate area sits on the first-base side of the plate '
             'the map draws, in the same direction and for the same reason.'),
            ('This model\'s entire second deck at this ballpark names seats '
             'that are not in the building',
             'The map has no second deck at all — the drawing goes from field '
             'level straight to the club ring. Three of the areas, '
             'including one behind-plate area, are built entirely out of '
             'labels with nothing behind them.'),
            ('The map draws its netting and labels it, and it matches the '
             'club\'s published run exactly',
             'A drawn line along the field edge with a printed legend giving '
             'the same extent the club publishes in words. That is the club '
             'agreeing with itself. It says nothing about this model\'s '
             'labelling, which is what the netting above is a gap for.'),
        ],
    ),

    # --- Step 13: the six remaining named maps, including the first three
    #     tables a map has agreed with -----------------------------------

    'minute_maid': dict(
        map_of="the Astros' published seating map",
        landmark='a flat plan with the field rotated, fixed by the left-field '
                 'porch, whose legend colour matches four sections at one end '
                 'of the bowl and nothing else on the sheet — corroborated '
                 'independently by the batter\'s eye, which is in dead centre '
                 'by definition and falls where a centre-field axis through '
                 'that porch would put it',
        quality='excellent — lower-bowl labels clean at three times '
                'magnification',
        read_on=LATER_READ_DATE,
        outcome='agrees',
        findings=[
            ('The map agrees with this model on both questions it can settle',
             'The two foul lines are the right way round, and the seats behind '
             'home plate are where this model puts them — measured as the '
             'bearing from the plate opposite the mound, the map\'s central '
             'wedges fall inside this model\'s behind-plate area. The same is '
             'true one deck up. This is the first of three ballparks whose '
             'table has come out right, and it was checked the same way as the '
             'twenty-seven that did not.'),
            ('The top deck\'s behind-plate area is two or three positions '
             'toward first base, which is not called an error here',
             'That is inside the resolution of deciding which wedge sits on '
             'the plate\'s axis on a ring that far out. It is recorded rather '
             'than reported as a mismatch.'),
            ('The map has a numbering defect of its own, and some of this '
             'model\'s labels cannot be found on it',
             'Four labels are each printed on two adjacent wedges and five are '
             'never printed at all — checked at twelve times magnification, '
             'the repeats really are repeats. So a handful of the labels this '
             'model carries here have nothing on the drawing to match, though '
             'not because the model put them in the wrong place. The '
             'boundaries between the areas are softer than the drawing '
             'makes them look.'),
            ('The map draws no netting, and does not contradict what the club '
             'publishes',
             'The field-to-seat boundary is a plain band at every '
             'magnification and the legend has no netting entry. The club\'s '
             'published run is centred on the plate block the map reads, which '
             'is what a run behind the plate should look like.'),
        ],
    ),

    'wrigley_field': dict(
        map_of="the Cubs' published seating map",
        landmark='a flat plan in standard orientation, settled outright by the '
                 'street grid the map prints — the two streets it names run '
                 'behind left field and behind right field — with the map\'s '
                 'own left-field and right-field gates agreeing',
        quality='excellent — a large drawing with a full product legend',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('The seat labels run the right way round on all four decks',
             'Both foul-line blocks land on the lines this model names, on '
             'every ring, which is why this page names them. On the two upper '
             'decks the map settles it twice over: it suffixes its own labels '
             'left and right, and the suffix switches directly behind the '
             'plate.'),
            ('The area this page calls the seats behind home plate is up the '
             'third-base line',
             'About five positions. The map groups its own behind-plate '
             'sections into one named product band, and this model\'s '
             'behind-plate area is the third-base end of that band rather than '
             'its middle. What this model calls its first-base infield is most '
             'of the rest of the band — part third-base shoulder, part the '
             'plate itself, and only its far end actually on the first-base '
             'side.'),
            ('The two upper decks are three to four positions the same way, '
             'and the second deck is right',
             'The behind-plate areas on the two top rings sit toward third '
             'base of the switch the map\'s own suffixes put behind the plate. '
             'The second deck\'s behind-plate area is centred where the map '
             'has it.'),
            ('The map draws no netting, so this park\'s netting gap is '
             'unchanged',
             'Checked at six times magnification along the field-to-seat '
             'boundary on both foul lines: a plain band, no hatch, no dotted '
             'line, and no netting entry in a legend of thirty-four products. '
             'The heavy ring visible around the bowl is a suite level, not a '
             'net. A drawing that shows no netting is not evidence that a park '
             'has none.'),
        ],
    ),

    'yankee_stadium': dict(
        map_of="the Yankees' published seating map",
        landmark='a flat plan in standard orientation, fixed by the batter\'s '
                 'eye deck at top centre and by the map\'s own printed netting '
                 'note, whose two named endpoints the club\'s netting page '
                 'independently assigns to a side each',
        quality='fair — by far the densest drawing read here, five concentric '
                'numbered rings with labels down to a few pixels, read at '
                'seven to eight times magnification',
        read_on=LATER_READ_DATE,
        outcome='agrees',
        findings=[
            ('The map agrees with this model on both questions it can settle, '
             'on all four rings',
             'Every area this model names is on the line the map puts it on, '
             'and every behind-plate area is centred on the map\'s own plate '
             'block. All four rings put the plate at the same position in '
             'their own numbering, which is the cleanest internal consistency '
             'of any drawing read for this site.'),
            ('The map is what made this park testable, and no new source had '
             'to be trusted to do it',
             'The club\'s netting page has named a side alongside specific '
             'seats since long before any map was read, and it was useless '
             'here: the seats it names are on an inner ring this model does '
             'not number, so nothing could be compared. The map states the '
             'same fact again on the ring this model does number.'),
            ('The map draws and names its netting, and it matches the club\'s '
             'published run exactly at both ends',
             'A drawn band along the field edge from a named position on one '
             'foul line, round behind the plate, to a named position on the '
             'other, with the same statement printed in words alongside it. '
             'This is the first map read here to confirm a club\'s netting '
             'endpoints on both foul lines at once.'),
            ('What the map does not close is why the netting above is still a '
             'gap',
             'The run the club publishes names seats on an inner ring this '
             'model does not number, so no label in any area falls '
             'inside the published extent. That gap is about which series of '
             'seat labels this model chose to carry, not about the sides, and '
             'a map cannot fix it.'),
            ('This model\'s areas stop short of the outfield end on every ring',
             'The map runs each ring further toward the foul poles than this '
             'model\'s labels do. Every area it does name is in the right '
             'place; there are simply seats past the end of each of them that '
             'the figures do not cover.'),
        ],
    ),

    'dodger_stadium': dict(
        map_of="the Dodgers' published seating map",
        landmark='a flat plan in standard orientation, fixed by the map\'s own '
                 'left-field and right-field pavilion headings, each printed '
                 'over the sections it names',
        quality='excellent — the clearest lower-bowl typography of its round',
        read_on=LATER_READ_DATE,
        outcome='agrees',
        findings=[
            ('The map agrees with this model on both questions it can settle, '
             'on every ring',
             'Each area is on the line the map puts it on, and each '
             'behind-plate area is symmetric about the pair of sections the '
             'map has dead behind the plate. This is one of three ballparks '
             'whose table has come out right.'),
            ('This ballpark numbers one foul line odd and the other even, so a '
             'bare seat label carries its own side',
             'Every ring runs outward from a pair behind the plate, odd one '
             'way and even the other. That is what makes this park checkable '
             'at all: at most ballparks a label says nothing about which line '
             'it is on without a position to go with it, and here it does. It '
             'is also why two of this model\'s areas having overlapping label '
             'ranges is not a contradiction.'),
            ('The map draws no netting, and corroborates the part of the '
             'club\'s statement the netting above rests on',
             'The field-to-seat boundary is plain behind the plate and down '
             'both lines, and there is no legend. What the map does confirm is '
             'the parity — even to first base, odd to third — which is the '
             'part of the club\'s published run this model actually uses.'),
            ('This model\'s areas stop short of the outfield end on each ring, '
             'and one whole ring is unmodelled',
             'The middle ring runs about a third further toward the poles on '
             'the map than in this model, and the map\'s club and suite ring '
             'has no area on this page at all. Neither is a side or plate '
             'error; both mean the figures cover less of the ballpark '
             'than the drawing does.'),
        ],
    ),

    'busch_stadium': dict(
        map_of="the Cardinals' published seating map",
        landmark='a flat plan in standard orientation that states the side '
                 'outright at both ends of the bowl in its own product names — '
                 'left-field and right-field boxes, bleachers and pavilions, '
                 'and first-base and third-base field boxes — with no '
                 'inference step at all',
        quality='excellent — a large drawing with every product named on the '
                'sheet itself',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('Contradicted, and not by a reversal: third base appears at both '
             'ends of this model\'s arc',
             'One of the areas this model calls third-base infield is out in '
             'right field, on the first-base line, while the area it calls the '
             'third-base baseline is correctly on third base. Thirty anchored '
             'labels agree with the map and thirteen disagree, and the '
             'thirteen are precisely those two defects. Swapping the two sides '
             'would fix two areas and break two others. The whole arc has to '
             'be re-laid, which is why no area on this page is called '
             'first-base or third-base.'),
            ('The area this page calls the seats behind home plate is about '
             'fourteen positions down the first-base line',
             'The map names its own behind-plate product outright, and two '
             'more rings name theirs, and all three agree with each other. '
             'Where this model puts the plate, the map has the first-base '
             'dugout boxes. What this model calls the first-base baseline '
             'straddles the real plate block and runs on into the third-base '
             'seats beyond it.'),
            ('The two upper rings are about ten positions the same way',
             'Both behind-plate areas sit short of the block the map names on '
             'their own ring, on the first-base side, and one first-base area '
             'straddles the plate in the same way the field level does.'),
            ('The club\'s netting page and the club\'s map agree wedge for '
             'wedge, and they were gathered independently',
             'Three named products in the club\'s published netting statement '
             'land on exactly the map\'s wedges of those names. The club is '
             'self-consistent about its own building. It is this model\'s '
             'labelling that is out, which is what the netting above is a gap '
             'for.'),
        ],
    ),

    'nationals_park': dict(
        map_of="the Nationals' published seating map",
        landmark='a flat plan in standard orientation, fixed by sampling the '
                 'legend\'s right-field terrace colour and finding it on one '
                 'side of the frame and nowhere else, with the scoreboard '
                 'pavilion on the same side',
        quality='excellent — the largest drawing of its round, with an '
                'explicit netting key',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('This model has the two sides of this park the wrong way round at '
             'field level',
             'Twenty-eight anchored labels land on the opposite line from the '
             'map and none land on the line this model names. Because that is '
             'a clean reversal the figures are unaffected — every park '
             'here is an exact left-right mirror — but no area on this page '
             'can be called first-base or third-base.'),
            ('On top of the reversal, the behind-plate area is about seventeen '
             'positions up the third-base line',
             'And it is worse than a position error: this model names one of '
             'the club\'s own premium products by name in that area, and both '
             'the club\'s netting page and the club\'s map put that product '
             'seventeen positions from where this model does. The '
             'contradiction was already recorded in this project before any '
             'map was read; the map decides it in the club\'s favour.'),
            ('The two upper rings are wrong in a third way again',
             'There this model is not mirrored at all. It places the plate at '
             'the low end of the numbering and runs both foul lines upward '
             'from it, so both end up on the first-base side and nothing is '
             'claimed below the plate. That is a different defect from the one '
             'at field level, in the same park: the three rings disagree with '
             'each other as well as with the map.'),
            ('One upper area names seats that are not in the building',
             'The upper deck at this ballpark does not wrap behind the plate — '
             'the map has two separate arms with a gap between them — and the '
             'area this model calls the third-base upper deck falls entirely '
             'inside that gap. Part of another upper area does too.'),
            ('The map draws its netting with a key, and matches the club\'s '
             'published run exactly on both endpoints',
             'That is the second independent confirmation of a club\'s netting '
             'numbers by its own drawing. Which makes the point sharper rather '
             'than softer: the club is self-consistent, and it is this model '
             'that is out.'),
        ],
    ),

    # --- Step 14: six maps, five of which share one wrong assumption --------

    'comerica_park': dict(
        map_of="the Tigers' published seating map",
        landmark='a flat plan in standard orientation, fixed by the map\'s own '
                 'right-field balcony heading, printed along a strip drawn '
                 'directly outboard of the sections at one end of the bowl, '
                 'with the legend\'s right-field grandstand colour filling the '
                 'same sections',
        quality='excellent',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('This is the one ballpark on the site whose map took a foul-line '
             'name away',
             'Until the map was read, this page named its two foul lines. It '
             'was allowed to because the club\'s netting page names a side '
             'alongside two specific seats, one on each line, and both of them '
             'land where this model puts them. The map adds a run at one end '
             'of the bowl that its own right-field heading places in right '
             'field, and this model calls that run third-base infield. So the '
             'two sources now disagree and this page names nothing. Two '
             'anchored positions agreeing was never evidence about the other '
             'forty, and this is the first time that has cost a park rather '
             'than saved one.'),
            ('The area this page calls the seats behind home plate is about '
             'seventeen positions up the first-base line',
             'The map has one ring wrapping behind the plate with the numbers '
             'descending down one line and ascending down the other; this '
             'model has the plate near the low end with both lines running the '
             'same way from it. What this model calls the first-base baseline '
             'is the block that actually straddles the plate.'),
            ('More than half of this model\'s second deck at this ballpark is '
             'not in the building, and all of what is left is on one line',
             'The map\'s second deck is a short mezzanine entirely on the '
             'first-base side, about ten positions long. This model divides '
             'that deck into three areas spanning nearly thirty positions, '
             'including a behind-plate one and a third-base one. On the third '
             'deck about a third of the labels this model carries are not '
             'printed either.'),
            ('The netting gap already recorded for this park had half-noticed '
             'this',
             'The note behind it says that this model has two separate runs '
             'both on the third-base side, so the club\'s published netting '
             'cannot be one continuous stretch of seats. The map says which of '
             'the two is misplaced.'),
        ],
    ),

    'pnc_park': dict(
        map_of="the Pirates' published seating map",
        landmark='a rotated plan with the plate at the middle left, fixed by '
                 'two headings printed inside the image — a named left-field '
                 'lounge along one arm and the right-field gate at the outer '
                 'end of the other',
        quality='good',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('Contradicted: two of the five field-level areas are on the wrong '
             'foul line, and three are right',
             'What this model calls the third-base infield is the right-field '
             'arm, ending at the map\'s own right-field gate. What it calls '
             'the first-base baseline is the left-field arm, past the home '
             'dugout. The other three land correctly. Nine anchored labels '
             'agree and two disagree, and because some agree and some do not, '
             'swapping the two sides would not fix it. No area on this page is '
             'called first-base or third-base.'),
            ('The area this page calls the seats behind home plate is about '
             'seven positions up the first-base line',
             'And one of the labels it is built from is not printed anywhere '
             'on the map. What this model calls the first-base infield is '
             'mostly the plate block itself.'),
            ('The club\'s published netting run only makes sense on the map\'s '
             'numbering',
             'On the map it is one continuous stretch from a foul pole, '
             'through the plate, to a point down the other line — which is '
             'what a netting extent looks like. On this model\'s numbering the '
             'same stretch would begin on the third-base side, cross the plate '
             'and both first-base areas, and end on the third-base side again. '
             'The map\'s reading is the one that makes the club\'s own '
             'sentence coherent.'),
        ],
    ),

    'target_field': dict(
        map_of="the Twins' published seating map",
        landmark='a rotated plan with the plate at the middle left, fixed by a '
                 'named right-field patio printed immediately outboard of the '
                 'sections at one end of the bowl, with the map\'s own '
                 'left-field entrance gate at the other',
        quality='fair — the smallest drawing read for this site, with bowl '
                'labels a few pixels high needing five times magnification',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('The seat labels run the right way round on both lines',
             'Both foul-line blocks land on the lines this model names, which '
             'is why this page names them. That rules out a mirror and nothing '
             'else — the plate error is real and a side check cannot see '
             'it.'),
            ('The area this page calls the seats behind home plate is at the '
             'right-field foul pole',
             'About twelve positions up the first-base line. The map runs one '
             'ring from pole to pole with the plate in the middle of it; this '
             'model has the plate at the low end with both lines running the '
             'same way from it. The behind-plate figure is the largest '
             'on this page and it is attached to seats at a corner of the '
             'ballpark.'),
            ('The second and third decks have their behind-plate areas on the '
             'first-base side too',
             'On the second deck the map settles it with no geometry at all: '
             'its own legend names a taproom by the sections behind the plate, '
             'and those sections are eight or nine positions from where this '
             'model puts its behind-plate area.'),
            ('Two areas run off the end of their foul line',
             'Four positions this model calls the first-base baseline are on '
             'the third-base side of the bend, past the visitors\' dugout. And '
             'the area this model calls the third-base baseline is partly the '
             'left-field bleachers and partly centre and right-centre field — '
             'not a foul line at all.'),
        ],
    ),

    'tmobile_park': dict(
        map_of="the Mariners' published seating map",
        landmark='a rotated plan with the plate at the lower left, fixed by '
                 'two headings printed inside the image on opposite arms — a '
                 'named right-field restaurant with the right-field gate '
                 'beyond it, and a third-base entry with the left-field gate '
                 'beyond that',
        quality='excellent',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('The seat labels run the right way round on both lines',
             'Both foul-line blocks land on the lines this model names, which '
             'is why this page names them. It rules out a mirror and nothing '
             'else.'),
            ('The area this page calls the seats behind home plate is in the '
             'right-field corner',
             'It sits in front of the named restaurant the map draws at the '
             'outfield end of the first-base arm — seventeen to twenty '
             'positions up the line from the plate. The range is honest: the '
             'map puts the plate at one wedge by tracing the radial through '
             'the backstop bend, and the club\'s own published net heights '
             'centre on the next one along. The direction and the size are not '
             'in doubt; the exact figure is.'),
            ('The club\'s own published net heights corroborate the offset, '
             'from a source this site already carried',
             'The club publishes a tall run and a lower run at stated heights '
             'against named stretches of seats. On the map\'s numbering the '
             'tall run sits over and just past the plate, which is what a tall '
             'run is for. Centred on this model\'s behind-plate area instead, '
             'it would be out in right field.'),
            ('The third deck is off about the same way, and the second deck '
             'spans an arc the map does not number',
             'The map\'s third ring has its plate about seventeen positions '
             'from where this model puts its behind-plate area, in the same '
             'direction. On the second deck the map has two separate arms with '
             'a press band between them, and the labels this model carries '
             'across the middle of that deck are not printed.'),
            ('One position this model calls the first-base baseline is on the '
             'third-base side',
             'A boundary error rather than a side error, and small — recorded '
             'because the rest of that area is right.'),
        ],
    ),

    'angel_stadium': dict(
        map_of="the Angels' published seating map",
        landmark='a flat plan in standard orientation, fixed twice over by the '
                 'legend, which names a left-field pavilion and a right-field '
                 'pavilion and colours them at opposite ends of the bowl',
        quality='good',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('Contradicted: what this page would call the third-base baseline '
             'is the far end of the opposite foul line',
             'The map puts the first three positions of that area at the '
             'outfield end of the right-field arm — not near the plate, and '
             'not on third base. The rest of that area names seats that are '
             'not in the building at field level at all. Fourteen anchored '
             'labels agree with the map and three disagree, so this is not a '
             'mirror and a swap would not fix it. No area on this page is '
             'called first-base or third-base.'),
            ('The area this page calls the seats behind home plate is about '
             'six positions up the third-base line',
             'What this model calls the first-base infield is the plate block '
             'itself — the map names it as a single club arc — and part of '
             'what it calls the first-base baseline is behind the plate too.'),
            ('Two published runs from this club, disagreeing on length, agree '
             'exactly on where the plate is',
             'The map prints a netting extent in words, and the club\'s '
             'netting page publishes a longer one. They are centred on the '
             'same position, and that position is the middle of the plate '
             'block the map draws. Two independent statements from the same '
             'club, both putting the plate where this model does not.'),
            ('The club\'s published netting run, on this model\'s numbering, '
             'would begin and end on the same foul line',
             'It would start in a third-base area, cross the plate and both '
             'first-base areas, and finish inside another third-base area — a '
             'run that passes through one foul line to get from one end of the '
             'other to itself. On the map\'s numbering it is one continuous '
             'stretch through the plate. That is the netting gap on this page, '
             'stated as geometry.'),
            ('Two areas on the upper rings are at the wrong end, or not in the '
             'building',
             'The area this model calls the third-base club level begins at '
             'the first-base end of that ring, and the area it calls the '
             'third-base upper deck begins at the first-base end of that one '
             'and then runs past where the ring stops.'),
        ],
    ),

    'petco_park': dict(
        map_of="the Padres' published seating map",
        landmark='a flat plan in standard orientation, fixed by a named '
                 'left-field building drawn at the head of one arm, with the '
                 'map\'s own right-field home run deck at the head of the '
                 'other',
        quality='excellent — the clearest drawing of its round and the '
                'furthest from its table',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('This ballpark numbers one foul line odd and the other even, and '
             'every area on this page spans both',
             'The two lines run outward from a shared block behind the plate, '
             'one taking the odd labels and the other the even. This model '
             'builds its areas from runs of consecutive labels, so every '
             'field-level area here is half one foul line and half the other. '
             'That is not an error a position offset describes; the ring is '
             'not the shape this model thinks it is, and no area on this page '
             'describes a single foul line.'),
            ('An offset figure for the seats behind home plate is not worth '
             'quoting here',
             'At the other ballparks the finding is how far the behind-plate '
             'block is from the plate. Here the block is not a block: it is '
             'two positions on one foul line and two on the other, split by '
             'parity, so there is nothing for a distance to be measured '
             'between.'),
            ('The map resolves what looked like a contradiction in the club\'s '
             'own netting statement',
             'The club publishes two overlapping runs, one named for each foul '
             'line, and this project has declined to test this park ever since '
             'on the grounds that a seat is on one line or the other. On the '
             'map they overlap only as numbers: the odd ones are on one arm '
             'and the even ones on the other, and the club\'s sentence is '
             'exactly right. The check still declines, because it reasons '
             'about ranges and these ranges are not testable as ranges. So '
             'this page still says nothing was ever established, and now there '
             'is a reason on the record rather than a silence.'),
            ('The map draws an unlabelled marking along a run of section '
             'edges, and it is not netting',
             'On one arm it runs along the concourse edge rather than the '
             'field-facing edge, and the same marking appears out at the third '
             'ring and along a terrace where no netting can be. There is no '
             'key on this drawing to say what it is. What it is not is '
             'recorded; what it is, the map does not say.'),
        ],
    ),

    # --- Step 15: six maps, two of which rest on the plan convention alone ---

    'american_family': dict(
        map_of="the Brewers' published seating map",
        landmark='a flat plan in standard orientation — and this drawing names '
                 'no field and no base anywhere on the sheet, so which way '
                 'round it runs rests on the plan convention alone: a plan '
                 'drawn with home plate at the bottom and the outfield at the '
                 'top puts first base on the right. The map\'s dugout labels '
                 'agree with that and do not establish it; two other clubs\' '
                 'maps read for this site draw the home dugout on the '
                 'third-base side',
        quality='excellent — every label resolved at three times magnification',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('The seat labels run the right way round on all four rings',
             'Both foul-line blocks land on the lines this model names, which '
             'is why this page names them. Read that against the orientation '
             'note above, which is the weakest of the thirty maps alongside '
             'one other.'),
            ('The area this page calls the seats behind home plate is in the '
             'right-field corner',
             'About thirteen positions up the first-base line, out by the '
             'visitors\' bullpen, and one of the labels it is built from is '
             'not printed anywhere on the map. The map runs one ring from pole '
             'to pole with the plate in the middle; this model has the plate '
             'at the low end with both lines running the same way from it. The '
             'behind-plate figure is the largest on this page.'),
            ('The two upper rings are nine to eleven positions the same way',
             'Both behind-plate areas sit on the first-base side of the block '
             'the map has behind the plate on their own ring, and the top '
             'ring\'s area begins with two labels that are not in the building '
             '— the map\'s top ring starts further along than this model\'s '
             'does.'),
            ('What this page calls the first-base baseline straddles the plate '
             'on every ring',
             'On all three rings that area runs from the first-base side, '
             'across the plate block, and on into the third-base seats beyond '
             'it. So the same area is partly one foul line, partly behind the '
             'plate, and partly the other foul line.'),
            ('The map draws its netting, and the run is symmetric about the '
             'plate block it draws',
             'Seven or eight positions each side of the plate, in the fill the '
             'legend names for netting. That corroborates the plate reading '
             'from inside the drawing itself, independently of any geometry.'),
        ],
    ),

    'loan_depot': dict(
        map_of="the Marlins' published seating map",
        landmark='a rotated plan with the plate at the lower right, fixed '
                 'three times over inside the image: the legend names its two '
                 'dugout clubs by side and by label, the map prints a '
                 'first-base entrance outside one arm and a third-base '
                 'entrance outside the other, and a home-plate entrance is '
                 'drawn directly outboard of the upper ring\'s plate block',
        quality='excellent — the largest drawing read for this site',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('The seat labels run the right way round on both the bowl and the '
             'upper ring',
             'Both foul-line blocks land on the lines this model names, which '
             'is why this page names them. Worth stating how that was settled: '
             'the map draws the home dugout on the third-base arm, so anyone '
             'reading this drawing by the dugout would have mirrored the park. '
             'The legend decided it instead.'),
            ('The area this page calls the seats behind home plate is in the '
             'right-field corner',
             'About thirteen positions up the first-base line, at the far end '
             'of the bowl by the bullpen. The map runs one ring from pole to '
             'pole with the plate in the middle of it; this model has the '
             'plate at the low end. The behind-plate figure is the '
             'largest on this page.'),
            ('The middle ring has no behind-plate seating at all, and this '
             'model gives it an area anyway',
             'On the map a suite band occupies that whole arc. So the area '
             'this page calls the behind-plate seats on that ring names seats '
             'that are not there, and most of one of the two foul-line areas '
             'on that ring is unprinted labels too. Only two positions of it '
             'are real.'),
            ('The upper ring is about seven positions off, against a block the '
             'map names by an entrance',
             'The drawing prints a home-plate entrance directly outboard of '
             'two sections on that ring, which fixes the plate there with no '
             'geometry at all. This model\'s behind-plate area on that ring '
             'sits seven positions toward first base of it, and its first-base '
             'area straddles the plate.'),
            ('Two areas run past the end of a foul line',
             'What this model calls the third-base baseline runs five '
             'positions past where that arm stops, into a run that crosses the '
             'outfield; the top ring\'s third-base area runs three positions '
             'past where that ring stops.'),
            ('The map draws its netting, and the run is symmetric about the '
             'plate the drawn foul lines converge on',
             'It runs from a position on one line, through the plate, to a '
             'position on the other, and its midpoint is where the two drawn '
             'foul lines meet. That corroborates the plate reading from inside '
             'the drawing.'),
        ],
    ),

    'rogers_centre': dict(
        map_of="the Blue Jays' published seating map",
        landmark='a flat plan in standard orientation that draws the diamond '
                 'explicitly, with the bases marked — but what fixed it is the '
                 'club\'s own netting page, which has named a side alongside a '
                 'specific seat on each foul line since long before any map '
                 'was read, and the map agrees with both',
        quality='good',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('The sides were already established here, and the map extends the '
             'evidence from two positions to twenty-six',
             'This is the one ballpark of its round that did not need a map to '
             'name its foul lines. What the map adds is breadth: instead of '
             'one anchored seat on each line it now supplies a long run on '
             'each. It also draws the home dugout on the third-base arm — '
             'another map that would have mirrored the park if a dugout label '
             'had been trusted.'),
            ('The area this page calls the seats behind home plate is about '
             'thirteen positions up the first-base line',
             'The map runs one closed ring with the plate in the middle of it; '
             'this model has the plate at the low end with both foul lines '
             'running the same way from it. The behind-plate figure is '
             'the largest on this page and it is attached to seats on a foul '
             'line.'),
            ('The two upper rings are about seven positions the same way',
             'Both behind-plate areas sit on the first-base side of the block '
             'the map has behind the plate on their own ring, and on all three '
             'rings the first-base baseline area straddles the plate and runs '
             'on into the third-base seats.'),
            ('This model claims the same seat label on both foul lines at once',
             'One printed label at field level appears in both a first-base '
             'area and a third-base area of this model\'s table. It is '
             'resolved to the first-base side by a tie-break rule rather than '
             'by anything about the ballpark, which is worth knowing when '
             'reading where one area ends and the next begins.'),
            ('The map draws no netting, so this park\'s netting position is '
             'unchanged by it',
             'There is no netting entry in the legend and no line along the '
             'field edge. A pale arc does run behind one stretch of seats, but '
             'it is on the concourse side and carries an accessible-seating '
             'icon, so it is a platform edge. A drawing that shows no netting '
             'is not evidence that a park has none.'),
        ],
    ),

    'kauffman_stadium': dict(
        map_of="the Royals' published seating map",
        landmark='a flat plan in standard orientation — and this drawing, like '
                 'the Brewers\', names no field and no base anywhere on the '
                 'sheet, so which way round it runs rests on the plan '
                 'convention alone. Its two dugout labels are not evidence; '
                 'two other maps read for this site draw the home dugout on '
                 'the third-base side',
        quality='excellent',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('Contradicted: two field-level areas are on the wrong foul line '
             'and two are on the right one',
             'What this model calls the first-base infield, and most of what '
             'it calls the first-base baseline, are on the third-base line. '
             'What it calls the third-base baseline is the middle of the '
             'first-base arm. Seven anchored labels agree with the map and '
             'twenty disagree. Swapping the two sides would fix two areas and '
             'break two others, so there is no single correction, and no area '
             'on this page is called first-base or third-base.'),
            ('The area this page calls the seats behind home plate is about '
             'sixteen positions up the third-base line',
             'It sits past the visitors\' end of the infield, and what this '
             'model calls the first-base baseline is the block that actually '
             'straddles the plate.'),
            ('The middle ring has no behind-plate seating, and this model\'s '
             'three areas on it are on the wrong sides of the gap',
             'A club occupies that arc on the map. This model\'s behind-plate '
             'area on that ring is on the third-base side of it, its '
             'first-base area is mostly third base, and its third-base area is '
             'the first-base side of the ring. Two more of the labels it '
             'carries there are not printed.'),
            ('The top ring\'s behind-plate area is nearly right, and that is a '
             'coincidence',
             'It falls close to where the map puts the plate on that ring. Two '
             'rings of different lengths divided into equal arcs will '
             'occasionally line up; nothing about the top deck was done more '
             'carefully than the rest.'),
            ('This club declines to publish section numbers for its netting — '
             'and its own seating map draws the netting and labels it',
             'That is why the netting above is a gap: the recorded reason is '
             'that the club will not give the seats. The drawing has a heavy '
             'line along the field edge with the words "protective netting" '
             'printed along it twice, and both ends read cleanly at high '
             'magnification, eighteen positions one side of the plate and '
             'nineteen the other. This site does not treat that as a published '
             'extent and nothing here was changed on the strength of it: it is '
             'a line on a drawing whose ends were read off pixels, not a '
             'sentence a club has committed to. The gap above is not closed. '
             'But a reader of that gap should know the drawing exists.'),
        ],
    ),

    'globe_life': dict(
        map_of="the Rangers' published seating map",
        landmark='a rotated plan drawn in mild perspective, fixed by '
                 'measurement rather than by eye: the legend\'s third-base box '
                 'colour was sampled and the drawing searched for that exact '
                 'fill, which returns five adjacent blocks and nothing else, '
                 'all on one arm. The legend\'s left-field deck colour returns '
                 'five more at the head of the same arm',
        quality='fair — the densest drawing of its round, five concentric '
                'label rings at a few pixels each',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('Contradicted: the two infield areas are on each other\'s foul '
             'lines',
             'What this model calls the first-base infield is the third-base '
             'box the map\'s own legend names by colour. What it calls the '
             'third-base infield is on the first-base line and then runs into '
             'the outfield ring. Six anchored labels agree and nineteen '
             'disagree, and because some agree, a swap would not fix it. No '
             'area on this page is called first-base or third-base.'),
            ('The area this page calls the seats behind home plate is at the '
             'left-field foul pole',
             'About ten positions up the third-base line, drawn past the far '
             'end of the third-base boxes. The mezzanine\'s behind-plate area '
             'is about nine positions the same way. The behind-plate figure '
             'below is the largest on this page.'),
            ('Two areas name seats that are not in the building, and two more '
             'are the outfield ring',
             'What this model calls the third-base baseline runs four '
             'positions past where the bowl stops; what remains of it, and the '
             'outer part of the third-base infield area, are the run that '
             'crosses the outfield rather than a foul line at all.'),
            ('This is the only map read for this site that publishes a netted '
             'range in its own key',
             'The legend states the extent in words and draws it as a dotted '
             'line around the bowl edge. Its midpoint is the plate block the '
             'map draws, which corroborates the plate reading independently of '
             'the perspective tracing that produced it.'),
            ('The recorded reason for this park\'s netting gap has changed',
             'It used to be that nothing could establish which foul line was '
             'which here, so the netting could not be attached to seats. Now '
             'the check runs and this model fails it. The gap is the same '
             'size; what is behind it is no longer an absence.'),
        ],
    ),

    'tropicana_field': dict(
        map_of="the Rays' published seating map",
        landmark='a flat plan in standard orientation, and the most explicit '
                 'side statement on any of the thirty maps: it prints which '
                 'arm is first base and which is third, in words, with an '
                 'arrowhead into each ring. No landmark, no colour and no '
                 'geometry were needed',
        quality='good',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('This ballpark numbers one foul line odd and the other even, and '
             'every area on this page spans both',
             'The two lines run outward from a pair behind the plate, one '
             'taking the odd labels and the other the even, and the second '
             'deck and the suite ring do the same. This model builds its areas '
             'from runs of consecutive labels, so every field-level and '
             'second-deck area here is half one foul line and half the other. '
             'The ring is not the shape this model thinks it is, and an offset '
             'figure for the plate would not describe it.'),
            ('The seats behind home plate are a pair this model puts in a '
             'third-base area',
             'The map has two adjacent sections dead behind the plate. This '
             'model\'s behind-plate area is a different block entirely — two '
             'positions of it on one foul line and one on the other — and one '
             'label it carries at field level is not in the building at all.'),
            ('This model\'s entire top deck at this ballpark names seats that '
             'are not in the building',
             'There is no third-level ring around this bowl on the map. The '
             'only seating at that level is a short strip out in left field, '
             'and none of the labels this model carries for its three '
             'top-deck areas appears anywhere on the drawing.'),
            ('The map settled the sides outright, and this model still fails '
             'the check',
             'Three anchored labels agree with the map and three disagree — '
             'which is what a parity split does to a table built out of '
             'consecutive runs. The anchors are single positions rather than '
             'runs, because any run here would claim seats on the other line.'),
        ],
    ),

    # --- Step 16: the last unread map --------------------------------------

    'citi_field': dict(
        map_of="the Mets' published seating map",
        landmark='a flat plan in standard orientation that names no base and '
                 'no field anywhere on the sheet — every word on it was '
                 'magnified and read. Which way round it runs was settled by '
                 'measuring the drawn outfield against this park\'s published '
                 'dimensions: the drawn wall is deeper on one side at every '
                 'angle from twenty degrees out, matching a ballpark whose '
                 'right-centre is forty feet deeper than its left-centre, and '
                 'a mirrored drawing misses that fit by about forty feet on '
                 'both sides at once',
        quality='excellent — every number resolved at three to eight times '
                'magnification',
        read_on=LATER_READ_DATE,
        outcome='disagrees',
        findings=[
            ('The mildest disagreement of the thirty maps read, and the only '
             'ballpark whose behind-plate area at field level is already '
             'centred on the plate',
             'The map puts the plate on the boundary between the two middle '
             'positions of this model\'s behind-plate area, with an equal '
             'number of positions each side. No other park on this site can '
             'say that. Worth stating plainly given what the twenty-nine other '
             'reads found.'),
            ('The seat labels run the right way round on all three rings this '
             'model numbers',
             'Forty-six anchored labels agree with the map and none disagree, '
             'across field level and both upper rings. That is why this page '
             'names its foul lines.'),
            ('One ring up the behind-plate area is about two positions toward '
             'third base, and two rings up it is about five',
             'On the top ring every one of that area\'s nine positions is on '
             'the third-base side of the plate. The drift is in the same '
             'direction on both rings, and there is a reason for it in the '
             'building: the rings at this ballpark are not concentric with '
             'each other, so a table that divides each of them into three '
             'roughly equal arcs will drift the same way on every ring it does '
             'not measure.'),
            ('This model is silent about most of this ballpark',
             'The map prints two hundred and twenty-five seat labels across '
             'five numbered rings and three premium rings behind the plate. '
             'This model names about a third of them and says nothing at all '
             'about two whole rings. The figures are a shape across the '
             'part of the ballpark this model carries, not a census of it.'),
            ('A netting compilation this site holds for this park is symmetric '
             'about the same plate boundary the map draws',
             'It was arrived at by an unrelated route and it agrees, which is '
             'worth recording. It says nothing about which foul line is which, '
             'and it does not close the netting gap above: this club publishes '
             'nothing about its netting, and the compilation is not the club.'),
        ],
    ),
}

# The one park with no map at all. The complement still matters, and it is now
# a single page rather than twenty-six: a park with no map read has not passed
# anything, and its page has to say so in the same place the thirty say what
# their map found.
NO_MAP_READ = (
    "No published seating map has been read for this ballpark &mdash; the only "
    "one of the 31 for which that is true, because there is no map for it in "
    "this project's collection at all. The other thirty were read at "
    "magnification against the seat labels this model carries, and "
    "twenty-seven of them disagreed. This park has not been checked, which is "
    "not the same as having passed."
)


# ============================================================
# The standing statement of what the model does not know
# ============================================================
#
# Every park page carries this. It is the thing `AUDIT.md` says a buyer asks
# first and the thing this project cannot yet answer.

MODEL_LIMITS = [
    (
        'No foul ball has ever been checked against it',
        "This model has never been compared with a record of where real foul "
        "balls landed, at this park or any other, and no such record exists "
        "publicly &mdash; Statcast logs that a foul happened, not where it "
        "came down. The largest hand-collected set anyone has published is "
        "FiveThirtyEight's <a href=\"https://github.com/fivethirtyeight/data/"
        "tree/master/foul-balls\" rel=\"nofollow\">906 fouls</a>, one game at "
        "each of ten parks, placed by eye off camera footage into broad zones. "
        "Everything here is an estimate from physics and published dimensions."
    ),
    (
        'The seating shape is not surveyed',
        "The park's published foul territory and backstop figures set how far "
        "each area sits from home plate. The <em>angles</em> and "
        "<em>heights</em> are published nowhere, for any ballpark, so every "
        "park here shares one bowl shape, scaled and placed by its own "
        "measurements. Every park is also modelled as an exact left-right "
        "mirror, which one club's published statement about its own lopsided "
        "foul ground says is wrong."
    ),
    (
        'Some fouls land where the model has no seats',
        "A substantial share come down where there is no seating area to put "
        "them &mdash; deep near the poles, in the gap in front of the first "
        "row, or under a covered deck. They are counted in the park total and "
        "then dropped. The share is stated on this page, and it is large "
        "enough that these figures are a shape, not a census."
    ),
    (
        'The rate of balls hit straight back is a guess',
        "Roughly a quarter to a third of the fouls here are deflections "
        "carrying back over the catcher, which is what fills the seats behind "
        "the plate. The rate driving that was chosen because it produces a "
        "plausible game, not because anything measured it. It is the single "
        "largest unvalidated number in the model, and it lands exactly there."
    ),
    (
        'One foul line is not distinguishable from the other',
        "The mirror leaves the two lines at a park differing only by "
        "simulation noise, so read a matching pair of areas as one number "
        "rather than two. Worse, at {unnamed_sides} of the 31 parks nothing "
        "available establishes which of the two lines is which &mdash; and "
        "because the mirror makes a reversed park produce figures identical to "
        "a correct one, this model cannot detect the difference from the "
        "inside. It went undetected at one park for the whole of this model's "
        "life until the ballpark's own map was read."
    ),
]
