"""
site_data.py — the copy layer for the public site.

Everything the 31 park pages say about a *source* lives here, transcribed by
hand from `PARK_PARAMS.md` (foul territory, backstop, deck cover) and
`SOURCED_DATA.md` Part 2 (netting). `site_build.py` renders it; this file is
what a reader would have to check to audit a claim.

Three rules this file holds to, and the reasons they exist:

1. **No section numbers, anywhere.** `AUDIT.md`'s Step 10 update establishes
   that nineteen of the 31 zone tables in `foulball/stadium.py` are suspect on
   their numbering — nine contradicted outright by the club's own current
   seating map, ten more carrying printed labels that cannot describe a
   continuous seating bowl. A printed section number on a public page would be
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
   how few of those exist: nine parks of 31 have their sides established, six
   of them among the seven with sourced netting. At the other twenty-two, the
   two foul lines are shown as one seating area rather than as a first-base
   area and a third-base one, because naming them would be a claim this project
   cannot make. `PAIR_ZONE_WORDS` holds the side-neutral phrasing and
   `SIDE_STATE_WORDS` states each park's position outright.

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

# The standing caveat on every foul-territory figure on the site.
FOUL_AREA_CAVEAT = (
    'Foul territory area has one source in public circulation, not three. '
    'Andrew Clem estimates it from his own scale diagrams and states that the '
    'figures "are subject to revision"; Seamheads credits Philip Lowry\'s '
    '<em>Green Cathedrals</em> and matches Clem at 26 of the 28 parks where '
    'both publish; FanGraphs credits Clem. Read it as good to about a thousand '
    'square feet, not to the hundred the figure implies.'
)

# The standing caveat on every backstop figure on the site.
BACKSTOP_CAVEAT = (
    'Backstop distance is the figure the sources least agree on, and they '
    'disagree because they measure different things: Clem gives the distance '
    'to the fence at the rear, Seamheads the distance to the stands, and clubs '
    'define nothing. This site uses Clem wherever he publishes, for one '
    'reference point across all parks rather than the best number at each.'
)

# The standing caveat on every overhang figure on the site.
OVERHANG_CAVEAT = (
    'Deck cover is a 2016 figure, recovered from an archived copy of Clem\'s '
    'table after he stopped publishing the column, so renovations since then '
    'are not in it. Clem gives a percentage and never says what is casting the '
    'cover; whether a given park\'s figure counts as something a foul ball '
    'would hit is a judgment made in this model, not a sourced fact.'
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
    # gap_kind: (short label, full sentence)
    'club_publishes_no_sections': (
        'The club describes its netting but names no seating areas',
        'The club states how far its netting runs in words, but does not say '
        'which seating areas that covers. There is no way to attach the '
        'statement to a specific part of this ballpark without guessing, so '
        'nothing on this page is marked as behind netting.',
    ),
    'club_declines_to_publish': (
        'The club declines to publish where its netting is',
        'The club states outright that it will not give the locations — its '
        'own map, it says, shows only the general area, and "it is not '
        'possible for a map like this to show the precise location of the '
        'netting". So nothing on this page is marked as behind netting.',
    ),
    'no_primary_source': (
        'The club publishes no netting information',
        'Nothing on the club\'s own pages describes the netting. A '
        'second-hand figure exists but has not been verified against a primary '
        'source, so it is not used here and nothing on this page is marked as '
        'behind netting.',
    ),
    'no_source_at_all': (
        'No netting information exists for this park',
        'Neither the club nor the ballpark publishes anything about the extent '
        'of its netting. The only authority that reaches this park is a '
        'league-wide requirement that Professional Development League clubs '
        'install netting foul pole to foul pole "unless the configuration of '
        'the ballpark makes such coverage unnecessary", by the 2025 opener. '
        'That is a rule placed on the club, not an observation of what is '
        'actually installed, so it is not turned into seating areas here.',
    ),
    'source_conflict': (
        'The club\'s own netting page contradicts itself',
        'The club\'s netting page carries two statements that cannot both '
        'describe the same installation — one running the netting the full '
        'length of both foul lines, the other stopping it near the plate. One '
        'of the two appears to be stale text that was never removed. Until the '
        'club resolves it, nothing on this page is marked as behind netting.',
    ),
    'arc_endpoints_unresolved': (
        'The published endpoints sit on a numbering that wraps behind the plate',
        'The club gives the two ends of its netting run, but this park\'s seat '
        'numbering wraps around behind home plate at a point nobody publishes. '
        'Without that wrap point, the run between the endpoints cannot be read '
        'off, so nothing on this page is marked as behind netting.',
    ),
    'labels_contradict_model': (
        'The club\'s netting map and this model\'s seating labels disagree',
        'The club does publish where its netting runs. But the seat labels '
        'this model carries for this park cannot be reconciled with it — under '
        'the model\'s labels, the club\'s netting would either miss the seats '
        'behind home plate entirely or skip a nearer area and resume at a '
        'further one, and netting does not do either. The club\'s page is the '
        'sourced side of that disagreement and this model is the unsourced '
        'one, so nothing on this page is marked as behind netting.',
    ),
    'labels_wrap_unpublished': (
        'This model\'s own seating labels cannot describe a continuous bowl here',
        'A seating bowl is normally numbered so that one foul line runs below '
        'the seats behind the plate and the other runs above them. At this '
        'park, the labels this model carries put one foul line on both sides '
        'of the plate at once — so the numbering has to wrap somewhere no '
        'source states. Any published netting range read against those labels '
        'would net the far end of a foul line and leave the near end open, '
        'which is not how netting is installed. Nothing on this page is marked '
        'as behind netting.',
    ),
    'sides_unverifiable': (
        'Nothing establishes which side of this park is which',
        'The labels this model carries for this park run outward from home '
        'plate in both directions rather than around the bowl, and no source '
        'says which of the two blocks is the first-base side and which is the '
        'third. The published netting does not cover the whole field level, so '
        'the answer would change which seats came out behind netting. Nothing '
        'on this page is marked as behind netting.',
    ),
    'sides_flipped': (
        'This model has this park\'s two sides the wrong way round',
        'The ballpark\'s own seating map shows the lower bowl numbered one way '
        'around the plate, and the labels this model carries run the opposite '
        'way — so every seating area this model calls first-base side is in '
        'fact on the third-base side, and the reverse. The map is the sourced '
        'side of that disagreement and this model is the unsourced one. Until '
        'the labels are corrected, nothing on this page is marked as behind '
        'netting, and no area below is described as being on one line or the '
        'other &mdash; printing this model\'s own labels here would print them '
        'backwards.',
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
        'Something outside this model says which foul line is which here — '
        'either the club named a side alongside specific seats on its own '
        'page, or the park\'s published seating map was read directly with a '
        'landmark fixing which way round the drawing runs. Every seat label '
        'this model puts on one line lands on that same line in the source. '
        'That is why this page names the first-base and third-base sides at '
        'all. It establishes nothing else: not where the boundaries between '
        'areas fall, not whether the areas exist.',
    ),
    'untested': (
        'Never tested — this model could have the two lines swapped',
        'Nothing available for this park says which foul line is which. A '
        'published netting range cannot settle it: it gives the two ends of '
        'the run, not which line each end is on. Neither can this model\'s own '
        'figures, because every park here is built as an exact left-right '
        'mirror, so a park with its two sides swapped produces figures '
        'identical to one with them the right way round. At another park this '
        'exact silence hid a genuine reversal for the whole of the model\'s '
        'life. So the two foul lines are shown here as one seating area, and '
        'no area on this page is called first-base or third-base.',
    ),
    'flipped': (
        'Reversed — and this page will not print the labels backwards',
        'This is one of the ballparks where a source settles which foul line '
        'is which and this model gets it wrong. Not one of the seat '
        'labels the ballpark\'s own map anchors lands where the map puts it; '
        'they all land on the other line. Because that is a clean reversal '
        'rather than a drift, the <em>figures</em> below are unaffected — '
        'every park here is built as an exact left-right mirror, so the two '
        'lines carry the same distribution whichever way round they are '
        'labelled. What is affected is the labelling, which is why no area on '
        'this page is called first-base or third-base.',
    ),
    'inconsistent': (
        'Contradicted, and not by a simple reversal',
        'Some of this model\'s seat labels for this park land on the side '
        'their source names and some land on the other, so swapping the two '
        'sides would not fix it — the table is wrong in a way that has no '
        'single correction. No area on this page is called first-base or '
        'third-base.',
    ),
}


# ============================================================
# What the published seating maps say
# ============================================================
#
# Five clubs' seating maps were read directly, at magnification, and compared
# with the zone table this model carries for that park. `MAP_FINDINGS.md` is
# the full record, including what could not be resolved and how confident each
# read is. This is the public statement of what each one found.
#
# All five disagree with their zone table. That is the number worth carrying:
# five read, five wrong, in five different ways. It is also why the other
# twenty-six pages have to say that no map has been read for them rather than
# leaving the silence to read as a pass.
#
# The rule against printing section numbers binds here too, and hardest — a
# map finding is *about* section numbers. So every finding below is stated
# positionally: how far off, in which direction, on which deck.

MAP_READ_DATE = '2026-08-11'

MAP_READS: dict[str, dict] = {

    'truist_park': dict(
        map_of="the Braves' published seating map",
        landmark='a flat plan in standard orientation, with the right-field '
                 'restaurant and the left-field porch confirming which way '
                 'round it runs',
        quality='the cleanest of the five maps read',
        findings=[
            ('The area this page calls the seats behind home plate is not '
             'behind home plate',
             'On the map, the block dead behind the plate at field level is '
             'about four sections further toward first base than the block '
             'this model labels as the behind-plate area. What this model '
             'calls the behind-plate seats is really the first stretch up the '
             'third-base line, and what it calls the first-base infield boxes '
             'are really the seats behind the plate. The behind-plate figure '
             'in the model section below is therefore attached to the wrong '
             'seats, and it is the largest figure on this page.'),
            ('Several of the seat labels this model carries here do not exist',
             'At field level the map runs a block of consecutive sections with '
             'no room for an unlabelled one between them, and four of the '
             'numbers this model uses on the first-base side and five on the '
             'third-base side are not among them. Three of the areas below '
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
        quality='good, though a smaller drawing than the best of the five',
        findings=[
            ('The area this page calls the seats behind home plate is in the '
             'outfield corner',
             'The map puts this model\'s behind-plate labels at the far end of '
             'the right-field line, beside the pool — about as far from home '
             'plate as a foul-territory section gets. The plate on the map '
             'sits at the midpoint of a single arc of numbers, and this '
             'model\'s table was built as though the numbering started behind '
             'the plate and ran outward in both directions. The behind-plate '
             'area below and both first-base areas are attached to seats '
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
        findings=[
            ('More than half the seat labels this model carries at field level '
             'are not in the building',
             'The map shows a single ring of twenty-three sections at field '
             'level and nothing above it. This model\'s table for this park '
             'names twenty-four field-level sections and fourteen of them are '
             'numbered past where the ring ends; of the twenty-one labels it '
             'carries above field level, thirteen do not exist either. The '
             'consequence for this page is direct: every area below shown as a '
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
             'this model\'s table altogether. The behind-plate figure below — '
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
        quality='the hardest of the five to read — small, foreshortened labels',
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
             'this map is that source. Sixteen of the 31 parks have no such '
             'source at all.'),
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
        quality='the least legible of the five — a small drawing with label '
                'text a few pixels high, so the reads below are the firm ones',
        findings=[
            ('The best match of the five parks read, and still not a match',
             'The seat labels run the right way round on both lines here, '
             'which is why this page names them. What is off is where the '
             'plate sits within them.'),
            ('This model puts the behind-plate areas toward first base of '
             'where the map has them, on all three levels',
             'On each of the three rings the map has the block dead behind the '
             'plate a handful of sections further toward third base than this '
             'model does — enough that at the top level the area this model '
             'calls a third-base area is the one actually behind the plate. '
             'The behind-plate figures below are attached to seats that sit '
             'somewhat toward the first-base side of the plate.'),
            ('Two areas stop short of where the map keeps going',
             'On the third-base side the map runs the second level and the top '
             'level several sections further than this model\'s labels do, so '
             'those two areas are short at the outer end.'),
        ],
    ),
}

# Every other park. The complement matters as much as the five above: a park
# with no map read has not passed anything, and the page has to say so in the
# same place the five say what their map found.
NO_MAP_READ = (
    'No published seating map has been read for this ballpark. Five have been '
    'read so far, at magnification, against the seat labels this model '
    'carries — and all five disagreed with them, in five different ways: one '
    'with its two sides reversed, three with the seats behind home plate '
    'attached to the wrong block, one with more than half its field-level '
    'labels naming sections that are not in the building. This park has not '
    'been checked. That is not the same as having passed, and the difference '
    'is the whole reason this section exists.'
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
        'This model has never been compared with a record of where real foul '
        'balls actually landed, at this park or any other. No such record '
        'exists publicly — Statcast logs that a foul happened, not where it '
        'came down, and the largest hand-collected set anyone has published '
        'ran to about 900 balls for a single story. Everything below is an '
        'estimate from physics and published park dimensions. Nothing on this '
        'page is a measurement of foul balls.'
    ),
    (
        'The seating shape is not surveyed',
        'How far each seating area sits from home plate is set by the park\'s '
        'published foul territory and backstop figures. The <em>angles</em> '
        'and <em>heights</em> are not: no public source gives the angle of a '
        'seating area off the foul line or the elevation of a deck in feet for '
        'any ballpark, so every park here shares one bowl shape, scaled and '
        'placed by its own measurements. Every park is also modelled as an '
        'exact left-right mirror, which is certainly wrong — one park has a '
        'published statement that its foul ground is lopsided, and nothing '
        'measures the rest.'
    ),
    (
        'Some fouls land where the model has no seats',
        'A substantial share of the fouls this model produces come down '
        'somewhere it has no seating area to put them — deep down the lines '
        'near the poles, in the gap between the plate and the front row, or '
        'under a covered deck. Those balls are counted in the park total and '
        'then dropped. The share is stated on this page, and it is large '
        'enough that the zone figures should be read as a shape, not a census.'
    ),
    (
        'The rate of balls hit straight back is a guess',
        'Roughly a quarter to a third of the fouls in this model are '
        'deflections that carry back over the catcher, which is what fills the '
        'seats behind the plate. The rate driving that was chosen because it '
        'produces a plausible game, not because anything measured it. It is '
        'the single largest unvalidated number in the model, and the seats '
        'behind home plate are exactly where it lands.'
    ),
    (
        'One foul line is not distinguishable from the other',
        'Every park here is built as an exact left-right mirror, so the two '
        'foul lines at a given park differ only by simulation noise: across '
        'all 31 parks the split between them varies by less than two runs of '
        'the same park vary from each other. Read a matching pair of areas on '
        'the two lines as one number, not two. Worse, at twenty-two of the 31 '
        'parks nothing available establishes which of the two lines is which '
        '&mdash; and because the mirror makes a reversed park produce figures '
        'identical to a correct one, this model cannot detect the difference '
        'from the inside. It went undetected at one park for the whole of this '
        'model\'s life until the ballpark\'s own map was read.'
    ),
]
