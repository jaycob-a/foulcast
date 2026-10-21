"""
site_diagram.py — the plan-view schematic that sits above each park's
distribution table.

Home plate at the bottom, the two foul lines running out, the seating the
model tracks drawn as segments of an arc behind them, shaded in four bands —
most, more, fewer, fewest — by how many fouls a game the model puts in each
against the busiest area at the same park. Inline SVG, no images, no scripts,
no external requests: the same one-request-per-page rule the rest of the site
keeps.

WHAT THE DRAWING IS ALLOWED TO CLAIM
------------------------------------
The site's standing rule is that **no figure is ever drawn as a length** — no
bars, no filled shares, no meters — because every number on these pages comes
out of estimated geometry that has never been compared with a foul ball, and a
drawn length puts it on a scale and says it was measured to that scale. This
file does not break that rule, and the way it stays inside it is the whole
design:

* **The model's figures are carried by fill, in four discrete bands.** Not by
  area, not by radius, not by a continuous ramp. A smooth gradient would be a
  length by another name: it would assert that the difference between 2.1 and
  2.3 fouls a game is a real difference this model can resolve. It is not —
  the run is 400 simulations a batter off a generic bowl, and the honest
  resolution is a band, so the reader gets bands.

  The bands are relative, and since Step 26 they are also what the table
  prints: an area's band is where its figure falls against the busiest area
  at the same park, in quarters (`BAND_EDGES`), and the table under the
  drawing says "most", "more", "fewer" or "fewest" where it used to print the
  figure to a tenth of a ball. The figures themselves are under Details.

  Relative to the park, not to the fleet. The steps used to have fixed
  boundaries in fouls a game, so that a quiet park would look quiet beside a
  busy one. But the parks are barely different — the simulated total is the
  same at every park, and 27 of 31 put between 30 and 33 fouls a game into
  seats — and what difference there is comes mostly from the one bowl shape
  they all share (`LIMITATIONS.md` 2.7). Shading the 31 against one another
  compared the template with itself. Within one park, which areas the model
  puts more balls into than others is the thing it does say, so that is what
  the shade now carries.
* **The lengths in the drawing are the sourced ones.** Radial distance is feet
  from home plate, and where a zone's front and back edges sit comes from
  `stadium.py`'s section table after `_apply_sourced_params` has stretched it
  by this park's published foul-territory area and pinned it to this park's
  published backstop. Those are measurements somebody published, not model
  output, and drawing them as distances is what a plan view is for.
* **The feet are shared by all 31 parks.** `frame()` sizes one coordinate
  system from the whole fleet and every park is drawn inside it, in the same
  feet, so Wrigley's 16,500 sq ft really does draw smaller than Rogers
  Centre's 30,500 rather than being normalised back up to the same picture.
  Two parks with different foul territory cannot produce the same drawing.

  Where that shared size is *shown* is the home page, because that is the one
  place the 31 parks are put next to each other: every tile carries the whole
  fleet viewBox, so the grid is a comparison of size, which is sourced. It is
  not a comparison of shade: each tile's bands are against its own busiest
  area, for the reason given above. A park page shows one park and
  compares it with nothing, and there a fleet-sized frame bought nothing and
  cost the drawing half its width in blank margin — the park's own page
  therefore crops the identical paths to that park's own extent (`park_box`).
  Same drawing, same coordinates, same feet; only the window onto them
  changes, and the window is not a claim.

WHAT IT IS NOT ALLOWED TO CLAIM
-------------------------------
1. **No section numbers, and no printed labels.** Nothing in the emitted markup
   carries a `section_id`: the only classes on a wedge are `z0`-`z4`, the step
   it fell in. `tests/test_site.py` greps the finished page for printed ranges
   and prefixed labels, and a path full of `1B-LB1` would sail straight into
   it.
2. **No negative numbers in path data.** Same test greps for `\\d{2,3}-\\d{2,3}`
   as a printed seat range, and `M 119-121` is indistinguishable from one.
   The origin is placed so that every coordinate the drawing emits is positive,
   and `_n` clamps.
3. **No side is named where the sides are not established.** The foul-line
   labels are emitted only when `p['sides']['named']` is true. At the other
   fifteen parks both lines are drawn and neither is labelled.
4. **The two foul lines always carry the same shade, at every park.** Every
   park in `stadium.py` is built as an exact left-right mirror, so the
   difference between a park's `1B-LB1` row and its `3B-LB1` row is simulation
   noise and nothing else. A *map* that shaded them differently would assert a
   left-right asymmetry the geometry does not contain, and at a park whose
   sides are folded it would leak a side. So a matched pair is shaded by the
   mean of the two, which is exactly the figure the folded row already
   carries, and the table gives both halves of a named pair that same band.
   The third-base half of the drawing is the first-base half mirrored
   coordinate by coordinate — see `_mirror` for why it is not an SVG `<use>`.
5. **No netting.** Until Step 26 a heavy dashed line along the front of an
   area meant the club's page put those seats behind netting. It was drawn on
   this model's template geometry, at the position of this model's seat
   labels, which the parks' own maps say are in the wrong place at most of
   the parks where a mark appeared. The club's own sentence, quoted directly
   under the drawing, is what replaced it.

WHAT IT DELIBERATELY DOES NOT DRAW
----------------------------------
Anything that would make it read as a seating chart: no section numbers, no
real bowl outline, no dugouts, no field, no aisle or row structure, no
attempt at the shape of the actual building. Every park gets the same generic
270-degree arc, because that is the only shape the model has — nobody
publishes the angle of a seating section off the foul line at any ballpark —
and drawing a plausible-looking bowl would claim a survey that does not exist.

HOW THE GEOMETRY MAPS
---------------------
`stadium.py` measures a section's angle from the foul line, 0 down the line
and 90 square behind the plate, on a per-side axis. In a real plan view the
two foul lines are 90 degrees apart, so the foul ground behind one of them
sweeps 135 degrees from the line round to the backstop bisector, and the two
sides together sweep the full 270. `_phi` is that mapping and nothing more:
model angle 0 lands on the foul line, model angle 90 lands straight back, and
the arc in between is spread evenly. It is a schematic, and the caption says
so.

Which band of the radius a zone owns at a given angle is not read off
`distance_min`/`distance_max` — those overlap heavily and are not a partition.
It is read off `exposed_bands`, the same function the simulation uses to
decide which deck a descending ball comes down on. So the drawing is a picture
of the surface the model actually matched balls against, not a picture of the
raw table.
"""
import html
import math

from foulball.stadium import STADIUMS, exposed_bands

# ============================================================
# The four bands
# ============================================================
#
# Boundaries as fractions of the busiest area's figure at the same park:
# "most" is at least three quarters of it, "more" at least half, "fewer" at
# least a quarter, "fewest" anything below. Quarters because they are the
# plainest boundaries that can be said out loud, and because across the
# registry they leave every band populated — the top area alone, or with
# near-equals, in "most"; the lower bowl behind the plate and its like in
# "more"; most foul-line areas in "fewer"; the upper decks in "fewest". The
# module docstring says why the bands are relative to the park and not fixed
# across the fleet.
BAND_EDGES = (0.25, 0.5, 0.75)

# Lowest to highest, indexed by band. The table prints these words and the
# legend is built from them, so neither can drift from the shading.
BAND_WORDS = ('Fewest', 'Fewer', 'More', 'Most')

# What the table prints for an area the model puts no ball in at all. Not a
# band: at Wrigley Field it is the whole upper deck, which is entirely under a
# roof this model treats as stopping every ball, and "fewest" would say the
# model sends some there.
NONE_WORD = 'None'


def band_of(fouls: float, top: float) -> int:
    """Which band a figure falls in, against the park's busiest figure."""
    share = fouls / top if top > 0 else 0.0
    return sum(1 for edge in BAND_EDGES if share >= edge)


# ============================================================
# Turning a park into wedges
# ============================================================

def _phi(theta: float) -> float:
    """Model angle (0 = foul line, 90 = behind the plate) as a plan bearing.

    Radians, measured from straight back off home plate, positive toward the
    first-base side. The 135 is the real geometry: the two foul lines are 90
    degrees apart, so the foul ground behind one of them is a 135-degree
    sweep from the line round to the line straight back through the plate.
    """
    return math.radians((90.0 - theta) * 1.5)


def wedges(stadium) -> list[tuple[float, float, tuple]]:
    """The right-hand half of the bowl, as (angle_from, angle_to, bands).

    Only the first-base side is computed. Every park in `stadium.py` is an
    exact mirror and `_sector` draws the third-base half by reflecting this
    one, so there is nothing to compute twice — see note 4 in the module
    docstring for why the two sides are never drawn differently in any case.

    The candidate pool is same-side plus behind-plate, which is the pool
    `matchup_engine` searches for a ball on this side. Breakpoints are the
    section angle boundaries, because `exposed_bands` is piecewise constant
    between them; each interval is evaluated at its midpoint and runs of
    identical bands are merged, which takes a park from about forty wedges to
    about ten.

    A deck entirely under a blocking cover (`fully_covered`; Wrigley Field's
    upper deck) is left off. The simulation still tests a ball against its
    surface to see whether the ball dived under its front edge, but no ball
    is ever credited to it, so it is not ground anything lands on, and the
    table prints "none" against its areas.
    """
    pool = [s for s in stadium.sections if s.side in ('1B', 'HOME')]
    cuts = {0.0, 90.0}
    for s in pool:
        for a in (s.angle_min, s.angle_max):
            if 0.0 < a < 90.0:
                cuts.add(float(a))

    out: list[list] = []
    edges = sorted(cuts)
    for a0, a1 in zip(edges, edges[1:]):
        bands = tuple((s.section_id, b0, b1)
                      for s, b0, b1 in exposed_bands(pool, (a0 + a1) / 2.0)
                      if not s.fully_covered)
        if out and out[-1][2] == bands:
            out[-1][1] = a1
        else:
            out.append([a0, a1, bands])
    return [(a0, a1, b) for a0, a1, b in out if b]


# ============================================================
# The frame every park is drawn in
# ============================================================
#
# One viewBox for the whole site. A per-park frame would scale each park up to
# fill it, which is the one thing this drawing must not do: the point of
# taking the radii from the sourced foul area and backstop is that a park with
# more foul ground draws bigger, and normalising would hand every park the
# same picture again.
_MARGIN = 26.0          # feet of clear ground round the widest park
_FRAME: dict[str, float] = {}


def frame() -> dict[str, float]:
    """viewBox and origin, in feet, sized to the whole registry.

    Cached: it walks all 31 parks, and every page asks. Rounded up to ten feet
    so that a small change to one park's published figures does not move the
    frame — and therefore every coordinate on every other page — by a foot.
    """
    if not _FRAME:
        x = y_up = y_down = 0.0
        for key in STADIUMS:
            for a0, a1, bands in wedges(STADIUMS[key]()):
                # `_phi` falls as the model angle rises, and cosine falls with
                # it, so the extremes of a sector's outer arc in y are its two
                # ends. In x they are not: an arc that crosses due sideways is
                # widest at the radius itself, not at either end.
                p0, p1 = _phi(a0), _phi(a1)
                r = max(b1 for _, _, b1 in bands)
                y_up = max(y_up, -r * math.cos(p0))
                y_down = max(y_down, r * math.cos(p1))
                x = max(x, r if p1 <= math.pi / 2 <= p0
                        else max(r * math.sin(p0), r * math.sin(p1)))
        ceil10 = lambda v: math.ceil((v + _MARGIN) / 10.0) * 10.0
        ox, up, down = ceil10(x), ceil10(y_up), ceil10(y_down)
        _FRAME.update(ox=ox, oy=up, w=2 * ox, h=up + down)
    return _FRAME


# ============================================================
# The three words on the drawing, and where they sit
# ============================================================
#
# Type sizes live here rather than in `CSS` and are substituted into it, so
# that the geometry that keeps a label clear of a foul line and the type that
# decides how wide the label is cannot drift apart. The first version of this
# drawing set "HOME PLATE" seventeen feet above the plate and the two foul
# lines ran straight through the word, which is the failure this arrangement
# is here to make impossible rather than to notice again.
_FS_SIDE = 10.0         # the two foul-line labels
_SIDE_TRACK = 0.10      # letter-spacing, em
_FS_PLATE = 9.0
_PLATE_TRACK = 0.06
_PLATE_LABEL = 'Home plate'
_LINE_OVER = 1.07       # how far the drawn foul lines run past the last deck


def _text_half(text: str, fs: float, tracking: float) -> float:
    """Half the width of one label, in feet.

    An estimate, and deliberately a generous one: every label on this drawing
    is set in the page's own sans at an upper-case transform, where 0.68 em is
    a fair average advance and no real string exceeds it by much. It is used
    to hold the labels off the foul lines and to size the crop, so erring wide
    costs a few feet of margin and erring narrow costs a collision.
    """
    return len(text) * (0.68 + tracking) * fs / 2.0


def _plate_label() -> tuple[float, float]:
    """Where "Home plate" goes: up the bisector, clear of both foul lines.

    The only empty ground in the frame is fair territory — the 90-degree wedge
    between the two lines, opening upward from the plate — and a label set in
    it has to be far enough up the wedge that the wedge is wider than the
    label. At a distance `d` above the plate the lines are `d` either side of
    the bisector, so the clearance from the nearer bottom corner of the label
    to the line it faces is `(d - half width) / sqrt(2)`. Solving that for a
    comfortable ten feet is the whole of the arithmetic below, and
    `tests/test_site.py` checks the result at all 31 parks rather than
    trusting it.
    """
    f = frame()
    return f['ox'], f['oy'] - (_text_half(_PLATE_LABEL, _FS_PLATE,
                                          _PLATE_TRACK) + 14.0)


def _side_label(outer: float) -> tuple[float, float]:
    """Where "First base" goes: along its own line, on the fair side of it.

    Beside the line rather than at the end of it, so that it is the line being
    named and not a corner of the picture. The third-base label is this point
    mirrored.
    """
    f = frame()
    d = math.sqrt(0.5)
    r = outer * 0.62
    return f['ox'] + (r - 19) * d, f['oy'] - (r + 19) * d


# ============================================================
# The window one park's own page looks through
# ============================================================
#
# The frame above is the whole fleet's, and the home page keeps it: 31 tiles
# in one viewBox is what makes the grid a comparison. A park page compares
# nothing, and there the fleet frame is a park drawn inside the largest park's
# margins — at most parks a third of the width was blank on both sides and the
# drawing sat a long way below its own title.
#
# So the park page crops. Not rescales: the coordinates, the radii and the
# paths are the same objects the tile carries, and only the viewBox changes.
# Everything the drawing ever claimed by size it still claims, in the one place
# those claims can be read, which is the grid where the parks sit side by side.
_CROP = 9.0             # feet of clear ground inside a park page's own frame
_BOX: dict[str, dict[str, float]] = {}


def park_box(stadium, named: bool) -> dict[str, float]:
    """viewBox for one park on its own page, in the fleet's coordinates.

    Everything the drawing puts on the page is measured here and nothing is
    assumed: the outer arc of every wedge, the foul lines drawn past it, the
    plate, and the labels — `named` is what decides whether the two foul-line
    labels are on the page to be measured at all.

    Kept symmetric about home plate. The drawing is a mirror and a crop that
    was two feet wider on one side would tilt it, which is exactly the kind of
    left-right difference the rest of this file exists to keep out.
    """
    key = f'{stadium.name}|{named}'
    if key in _BOX:
        return _BOX[key]
    f = frame()
    ox, oy = f['ox'], f['oy']
    half, top, bottom, outer = 7.0, oy - 7.0, oy + 9.0, 0.0   # the plate glyph
    for a0, a1, bands in wedges(stadium):
        p0, p1 = _phi(a0), _phi(a1)
        r = max(b1 for _, _, b1 in bands)
        # As in `frame()`: the y extremes of an arc are its two ends, the x
        # extreme is the radius itself where the arc crosses due sideways.
        top = min(top, oy + r * math.cos(p0))
        bottom = max(bottom, oy + r * math.cos(p1))
        half = max(half, r if p1 <= math.pi / 2 <= p0
                   else max(r * math.sin(p0), r * math.sin(p1)))
        if a0 <= 0.0:
            outer = max(outer, r)

    tip = _pt(0.0, outer * _LINE_OVER)
    half, top = max(half, tip[0] - ox), min(top, tip[1])

    px, py = _plate_label()
    half = max(half, _text_half(_PLATE_LABEL, _FS_PLATE, _PLATE_TRACK))
    top = min(top, py - _FS_PLATE)

    if named:
        lx, ly = _side_label(outer)
        reach = (_text_half('First base', _FS_SIDE, _SIDE_TRACK)
                 + _FS_SIDE) * math.sqrt(0.5)
        half, top = max(half, lx + reach - ox), min(top, ly - reach)

    box = {'x': max(0.0, ox - half - _CROP), 'y': max(0.0, top - _CROP),
           'w': 2 * (half + _CROP)}
    box['h'] = bottom + _CROP - box['y']
    _BOX[key] = box
    return box


# ============================================================
# Emitting the SVG
# ============================================================

def _n(v: float) -> str:
    """One coordinate, as a non-negative integer.

    Integers because a foot is well under a pixel at every width this page is
    read at, and because `tests/test_site.py` reads `\\d{2,3}-\\d{2,3}` as a
    printed seat range — so no coordinate in this file is ever allowed to
    carry a minus sign. The clamp is belt and braces on top of the frame
    margin.
    """
    return str(max(0, int(round(v))))


def _pt(theta: float, r: float) -> tuple[float, float]:
    """A model angle and a radius, as a point in the frame."""
    f = frame()
    p = _phi(theta)
    return f['ox'] + r * math.sin(p), f['oy'] + r * math.cos(p)


def _mirror(pt: tuple[float, float]) -> tuple[float, float]:
    """A point on the first-base side, as the same point on the third-base one.

    The mirror is done here, coordinate by coordinate, and not with an SVG
    `<use>` and a negative scale. `<use>` clones into a shadow tree, and only
    *inherited* properties cross into one reliably — a class selector setting
    `stroke-width` and `stroke-dasharray` on the netting mark did not, so the
    third-base half of the first build came out with a hairline where the
    first-base half had a net. Every mark on this drawing has to mean the same
    thing on both sides of the plate, and that is not a thing to leave to how
    a browser styles shadow content.
    """
    return frame()['w'] - pt[0], pt[1]


def _sector(a0: float, a1: float, r0: float, r1: float) -> str:
    """One zone's ground, on both sides of the plate, as path subpaths.

    Sweep flags are constant on the first-base side: the model angle rising
    from `a0` to `a1` turns the point clockwise on screen, so the outer arc
    sweeps 1 and the inner arc, walked back, sweeps 0. Mirroring reverses the
    orientation, so the third-base copy flips both. Nothing here spans more
    than 180 degrees, so the large-arc flag is always 0.

    A band that reaches straight back off the plate (`a1` at 90) is drawn as
    one symmetric sector across the middle rather than as two halves meeting
    at the centre line. It is one block of seats behind home plate, not two,
    and a seam down the middle of it would read as a division that is not
    there. Those sectors are the only ones that can grow large: one spans
    twice its own bearing, and the widest in the registry is 105 degrees,
    which is why the large-arc flag can stay 0. The assertion is there because
    a zone table that started its behind-plate group below 30 would silently
    turn every one of them inside out.
    """
    assert a1 < 90.0 or a0 > 30.0, 'behind-plate sector would exceed a half turn'
    def one(pa, pb, pc, pd, s_out, s_in):
        return (f'M{_n(pa[0])} {_n(pa[1])}A{_n(r1)} {_n(r1)} 0 0 {s_out} '
                f'{_n(pb[0])} {_n(pb[1])}L{_n(pc[0])} {_n(pc[1])}'
                f'A{_n(r0)} {_n(r0)} 0 0 {s_in} {_n(pd[0])} {_n(pd[1])}Z')

    a, b = _pt(a0, r1), _pt(a1, r1)
    c, d = _pt(a1, r0), _pt(a0, r0)
    if a1 >= 90.0:
        return one(a, _mirror(a), _mirror(d), d, 1, 0)
    return (one(a, b, c, d, 1, 0)
            + one(_mirror(a), _mirror(b), _mirror(c), _mirror(d), 0, 1))


# ============================================================
# Joining the drawing to what the table prints
# ============================================================

def _rows(p: dict) -> dict[str, dict]:
    """Every row of the distribution table, by the id it was built under."""
    return {z['id']: z for z in p['zones']}


def shade_figure(sid: str, rows: dict[str, dict]) -> float | None:
    """The figure a zone is **shaded** by, and so the figure its band is of.

    A behind-plate zone is shaded by its own figure. A foul-line zone is half
    of a matched pair, and the pair is always read as one thing:

    * at a park whose sides are folded, the pair is already one row, carrying
      the mean of the two;
    * at a park whose sides are named, the two rows are still drawn with one
      shade, from the mean of the two figures, and the table gives both rows
      the band of that mean.

    Note 4 in the module docstring is why. The foul-line case is tested
    *before* the direct lookup, and that ordering is the point of the function
    rather than a detail: at a park whose sides are named both halves are real
    rows, so a direct lookup would find `1B-LB1` and shade the drawing — both
    sides of it — from the first-base row alone, which is the asymmetry the
    mean exists to avoid, only hidden behind a symmetrical picture.
    """
    if sid[:3] not in ('1B-', '3B-'):
        row = rows.get(sid)
        return row['fouls'] if row else None
    suffix = sid[3:]
    folded = rows.get('LINES-' + suffix)
    if folded is not None:
        return folded['fouls']
    a, b = rows.get('1B-' + suffix), rows.get('3B-' + suffix)
    if a is None or b is None:
        return (a or b)['fouls'] if (a or b) else None
    return (a['fouls'] + b['fouls']) / 2.0


def _row_for(sid: str, rows: dict[str, dict]) -> dict | None:
    """The table row a drawn wedge belongs to.

    Its own row, or the folded `LINES-` row its pair became. At a park whose
    sides are named a first-base wedge returns the first-base row; both rows
    of a pair carry the same band (`shade_figure`), so which half answers does
    not change the shade.
    """
    if sid[:3] in ('1B-', '3B-') and 'LINES-' + sid[3:] in rows:
        return rows['LINES-' + sid[3:]]
    return rows.get(sid)


# ============================================================
# The figure
# ============================================================

def _alt(p: dict) -> str:
    """What the drawing says, for a reader who is not looking at it.

    The areas in the top two bands, by name and band, in the order the table
    below has them, because that ordering is the one thing the shading is
    for. No figures: the drawing carries none, so its description does not
    either.
    """
    said = []
    for band in (3, 2):
        names = [z['heading'][0].lower() + z['heading'][1:]
                 for z in p['zones'] if z['band'] == band and z['fouls'] > 0]
        if names:
            said.append(f'{BAND_WORDS[band]}: {"; ".join(names)}.')
    sides = ('First base is drawn on the right, third base on the left.'
             if p['sides']['named'] else
             'Neither line is labelled: nothing establishes which is which.')
    return (f'Schematic plan of the foul ground at {p["name"]}, home plate at '
            f'the bottom and the seating areas drawn as bands of an arc '
            f'behind the two foul lines, shaded in four bands by fouls a game '
            f'against the busiest area here. {" ".join(said)} {sides}')


def _legend() -> str:
    """The key to the drawing, and nothing else.

    The four bands are what a reader needs in order to read the picture at
    all, so they sit directly under it, darkest first, in the words the table
    uses. Everything the drawing has to admit to beyond that — that it is one
    generic bowl, why the two foul lines are shaded alike, where the band
    boundaries fall — is prose about the drawing rather than the drawing
    itself, and it lives on the site's one explanatory page
    (`site_build.about_page`) instead of under every one of the 31 drawings.
    """
    swatches = ''.join(f'<span><i class="z{i}"></i>{BAND_WORDS[i]}</span>'
                       for i in reversed(range(len(BAND_WORDS))))
    return (f'<p class="leg"><b>Foul balls, against the busiest area here</b>'
            f'{swatches}</p>')


def park_svg(p: dict, mini: bool = False) -> str:
    """The drawing itself, as one inline `<svg>`.

    `p` is what `site_build.build_park` produced, and the shading comes off
    `p['zones']` — the same bands, row for row, that the table under the
    drawing prints. That is the invariant worth keeping: a drawing that
    disagreed with the table beneath it would be worse than no drawing.

    `mini` is the home-page tile: the same paths in the same feet, with no
    text, and in the whole fleet's viewBox so that the 31 of them together are
    a comparison. At tile size the words would not be legible, and the tile's
    own caption carries the park's name. It is hidden from assistive
    technology for the same reason — the link it sits in already says which
    park it is.

    The park page emits those same paths cropped to this park (`park_box`).
    Nothing in the drawing moves; the window does.
    """
    stadium = p['stadium']
    rows = _rows(p)
    f = frame()
    ox, oy = f['ox'], f['oy']

    # Subpaths, gathered per band rather than per zone. Every wedge in a band
    # is one `<path>`, which is both smaller and truer: the band is the only
    # thing the fill means, and one element per zone would invite a future
    # edit to hang a zone's identity off it.
    steps: dict[int, list[str]] = {}
    outer = 0.0
    for a0, a1, bands in wedges(stadium):
        for sid, r0, r1 in bands:
            row = _row_for(sid, rows)
            if row is None:
                continue
            steps.setdefault(row['band'], []).append(_sector(a0, a1, r0, r1))
            if a0 <= 0.0:
                outer = max(outer, r1)

    paths = [f'<path class="z{i}" d="{"".join(subs)}"/>'
             for i, subs in sorted(steps.items())]

    # The foul lines run out along the outer angular edge of the bowl, which is
    # where they are: the stands on a side begin at the line. Drawn a little
    # past the back of the last deck so each reads as a line running out of the
    # picture rather than as the edge of a shape.
    tip = _pt(0.0, outer * _LINE_OVER)
    mtip = _mirror(tip)
    paths.append(f'<path class="fl" d="M{_n(ox)} {_n(oy)}'
                 f'L{_n(tip[0])} {_n(tip[1])}M{_n(ox)} {_n(oy)}'
                 f'L{_n(mtip[0])} {_n(mtip[1])}"/>')

    # Home plate. It sits in the open wedge of fair territory, which is the
    # only empty ground in the frame.
    paths.append(f'<path class="hp" d="M{_n(ox - 7)} {_n(oy - 7)}'
                 f'L{_n(ox + 7)} {_n(oy - 7)}L{_n(ox + 7)} {_n(oy + 2)}'
                 f'L{_n(ox)} {_n(oy + 9)}L{_n(ox - 7)} {_n(oy + 2)}Z"/>')

    if mini:
        return (f'<svg class="mini" viewBox="0 0 {_n(f["w"])} {_n(f["h"])}" '
                f'aria-hidden="true">{"".join(paths)}</svg>')

    # The one label the drawing needs in order to be read at all, set far
    # enough up the fair-territory wedge that the wedge is wider than the word
    # — see `_plate_label`, which is also what the crop and the test measure.
    px, py = _plate_label()
    labels = [f'<text class="pl" x="{_n(px)}" y="{_n(py)}" '
              f'text-anchor="middle">{_PLATE_LABEL}</text>']

    # Constraint 5, in the one place a drawing could break it. Sixteen parks
    # have a source that names a side alongside specific seats; at the other
    # fifteen both lines are drawn and neither is named.
    #
    # The words run along their own line, set just off it on the fair side —
    # the only empty ground the frame has, since every seating area drawn here
    # is behind a line by definition. Beside the line rather than at the end of
    # it, so that it is the line being named and not a corner of the picture.
    if p['sides']['named']:
        lx, ly = _side_label(outer)
        labels.append(f'<text x="{_n(lx)}" y="{_n(ly)}" text-anchor="middle" '
                      f'transform="rotate(315 {_n(lx)} {_n(ly)})">'
                      f'First base</text>')
        rx = f['w'] - lx
        labels.append(f'<text x="{_n(rx)}" y="{_n(ly)}" text-anchor="middle" '
                      f'transform="rotate(45 {_n(rx)} {_n(ly)})">'
                      f'Third base</text>')

    box = park_box(stadium, p['sides']['named'])
    return (f'<svg viewBox="{_n(box["x"])} {_n(box["y"])} {_n(box["w"])} '
            f'{_n(box["h"])}" role="img" aria-label="{_esc(_alt(p))}">'
            f'{"".join(paths)}{"".join(labels)}</svg>')


def park_diagram(p: dict) -> str:
    """The centrepiece of a park page: drawing, key, one-line caption.

    The caption is the drawing's own label and says the one thing a reader
    could otherwise get wrong at a glance — that this is a schematic and not
    a seating chart. Everything else the drawing has to explain is on the
    site's explanatory page, one link away, rather than under all 31 of them.
    """
    return (f'<figure class="dia">{park_svg(p)}{_legend()}'
            f'<figcaption class="dcap">Schematic, not to scale and not a '
            f'seating chart</figcaption></figure>')


def park_tile(p: dict) -> str:
    """The home-page tile's drawing: the same picture, small, no text."""
    return f'<figure class="dia mini">{park_svg(p, mini=True)}</figure>'


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


# ============================================================
# The styling
# ============================================================
#
# Served on every page: the 31 park pages carry one drawing each and the home
# page carries all 31 as tiles. The ramp is the site's one accent teal at the
# top band and three steps down to near-paper, because the accent is already
# what this site uses for "the thing you are being pointed at" and a second
# hue would read as a second meaning. The same four classes colour the
# swatches beside each band in the table, which is what ties a row to its
# shade without printing a figure.
#
# Everything here is in viewBox units, which are feet, and a park page now
# crops to about two thirds of the fleet frame's width — so a line that was
# set for the old frame comes out half as heavy again on the page. The weights
# and the two type sizes below are set for the cropped frame; the tile, which
# still carries the whole fleet frame at a fifth of the width, overrides them
# and is set heavier to come out at about the same weight on screen.
#
# The type sizes are substituted from the constants the label geometry uses,
# so that the size a label is set at and the room the drawing leaves for it
# cannot be changed independently.
CSS = r"""
.dia{margin:0}
.dia svg{display:block;width:100%;height:auto;margin:0 auto}
.dia path{stroke:#fff;stroke-width:1.1;stroke-linejoin:round}
.z0{fill:#e1ecee;background:#e1ecee}
.z1{fill:#9fcbd1;background:#9fcbd1}
.z2{fill:#4f9aa4;background:#4f9aa4}
.z3{fill:#0b6a74;background:#0b6a74}
.dia path.fl{fill:none;stroke:#8a919c;stroke-width:1.5;stroke-dasharray:4 4}
.dia path.hp{fill:#16181d;stroke:none}
.dia text{fill:#5b6270;font-size:__FS_SIDE__px;font-weight:700;
 font-family:inherit;letter-spacing:__SIDE_TRACK__em;text-transform:uppercase}
.dia text.pl{font-size:__FS_PLATE__px;font-weight:600;
 letter-spacing:__PLATE_TRACK__em;fill:#7b828e}
.dia svg.mini path{stroke-width:2.5}
.dia svg.mini path.fl{stroke-width:3.5;stroke-dasharray:9 9}
.leg{display:flex;flex-wrap:wrap;justify-content:center;align-items:center;
 gap:.25rem .85rem;font-size:.76rem;line-height:1.5;color:#4a505c;
 margin:.55rem 0 0}
.leg+.leg{margin-top:.2rem}
.leg b{font-size:.64rem;letter-spacing:.09em;text-transform:uppercase;
 color:#5b6270;margin-right:.15rem}
.leg span{display:flex;align-items:center;gap:.38rem}
.leg i{display:block;width:1.3rem;height:.72rem;border-radius:2px;
 border:1px solid rgba(22,24,29,.14)}
.dcap{text-align:center;font-size:.7rem;letter-spacing:.03em;color:#8a919c;
 margin:.5rem 0 0}
@media (prefers-color-scheme:dark){
 .dia path{stroke:#101216}
 .grid .dia path{stroke:#171a20}
 .z0{fill:#1f434e;background:#1f434e}
 .z1{fill:#2a6773;background:#2a6773}
 .z2{fill:#3a91a0;background:#3a91a0}
 .z3{fill:#4fb6c0;background:#4fb6c0}
 .dia path.fl{stroke:#6d7482}
 .dia path.hp{fill:#e4e7ee}
 .dia text{fill:#98a0b0}
 .dia text.pl{fill:#6d7482}
 .leg,.leg b,.dcap{color:#98a0b0}
 .leg i{border-color:rgba(228,231,238,.14)}
}
"""

# The one place the drawing's type size is written down is the constants at
# the top; this is how the stylesheet gets it. A number in both places would
# have drifted the first time either moved, and the failure that follows is a
# label overrunning the line it was measured to clear.
for _token, _value in (('__FS_SIDE__', _FS_SIDE), ('__FS_PLATE__', _FS_PLATE),
                       ('__SIDE_TRACK__', _SIDE_TRACK),
                       ('__PLATE_TRACK__', _PLATE_TRACK)):
    CSS = CSS.replace(_token, f'{_value:g}')
assert '__' not in CSS, 'a token in the diagram stylesheet was never filled in'
