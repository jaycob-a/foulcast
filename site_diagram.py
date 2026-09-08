"""
site_diagram.py — the plan-view schematic that sits above each park's
distribution table.

Home plate at the bottom, the two foul lines running out, the seating the
model tracks drawn as segments of an arc behind them, shaded in five discrete
steps by how many fouls a game the model puts in each. Inline SVG, no images,
no scripts, no external requests: the same one-request-per-page rule the rest
of the site keeps.

WHAT THE DRAWING IS ALLOWED TO CLAIM
------------------------------------
The site's standing rule is that **no figure is ever drawn as a length** — no
bars, no filled shares, no meters — because every number on these pages comes
out of estimated geometry that has never been compared with a foul ball, and a
drawn length puts it on a scale and says it was measured to that scale. This
file does not break that rule, and the way it stays inside it is the whole
design:

* **The model's figures are carried by fill, in five discrete steps.** Not by
  area, not by radius, not by a continuous ramp. A smooth gradient would be a
  length by another name: it would assert that the difference between 2.1 and
  2.3 fouls a game is a real difference this model can resolve. It is not —
  the run is 400 simulations a batter off a generic bowl, and the honest
  resolution is a band, so the reader gets bands and the boundaries are
  printed.
* **The lengths in the drawing are the sourced ones.** Radial distance is feet
  from home plate, and where a zone's front and back edges sit comes from
  `stadium.py`'s section table after `_apply_sourced_params` has stretched it
  by this park's published foul-territory area and pinned it to this park's
  published backstop. Those are measurements somebody published, not model
  output, and drawing them as distances is what a plan view is for.
* **The scale is shared by all 31 parks.** `frame()` sizes one viewBox from the
  whole fleet and every park is drawn inside it, so Wrigley's 16,500 sq ft
  really does draw smaller than Rogers Centre's 30,500 rather than being
  normalised back up to the same picture. Two parks with different foul
  territory cannot produce the same drawing.

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
   noise and nothing else. The table prints both because the table prints what
   the run produced; a *map* that shaded them differently would assert a
   left-right asymmetry the geometry does not contain, and at a park whose
   sides are folded it would leak a side. So a matched pair is shaded by the
   mean of the two, which is exactly the figure the folded row already
   prints, and the third-base half of the drawing is the first-base half
   mirrored coordinate by coordinate — see `_mirror` for why it is not an
   SVG `<use>`.
5. **Netting is marked only where it is sourced onto specific seats.** The
   heavy dashed line on the front edge of a zone means the club's own page
   places that seating fully behind netting. A zone that is partly netted,
   unverified, or netted on one line and not the other gets no mark at all,
   and the legend says which of those applies here. There is no mark that
   means "no netting", because at 24 of the 31 parks the site does not know
   that either — the absence of a mark is the absence of a source, and the
   legend line is what carries it.

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
# The five steps
# ============================================================
#
# Boundaries in fouls a game, fixed across the fleet rather than computed per
# park. A per-park quantile ramp would put a dark step on the busiest area at
# every park including the quiet ones, which reads as "this is where it is bad
# here" and flattens the real differences between parks. Fixed boundaries let
# a quiet park look quiet.
#
# The whole registry's zone figures run from 0 to about 6.8 a game with the
# mass between 1 and 4.5, so four boundaries at whole numbers split it into
# five steps that are all populated and all sayable out loud.
STEPS = (1.0, 2.0, 3.0, 4.0)

# Read out of `STEPS` so the legend cannot drift from the shading. Written
# with "to" rather than an en dash: `tests/test_site.py` reads any
# `\d{2,3}-\d{2,3}` on a page as a printed seat range.
STEP_WORDS = ('under 1', '1 to 2', '2 to 3', '3 to 4', '4 or more')


def step_of(fouls: float) -> int:
    """Which of the five discrete steps a figure falls in."""
    n = 0
    for b in STEPS:
        if fouls < b:
            return n
        n += 1
    return n


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
                      for s, b0, b1 in exposed_bands(pool, (a0 + a1) / 2.0))
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


def _arc(a0: float, a1: float, r: float) -> str:
    """The front edge of a zone, both sides, for the netting mark."""
    a, b = _pt(a0, r), _pt(a1, r)
    if a1 >= 90.0:
        m = _mirror(a)
        return f'M{_n(a[0])} {_n(a[1])}A{_n(r)} {_n(r)} 0 0 1 {_n(m[0])} {_n(m[1])}'
    ma, mb = _mirror(a), _mirror(b)
    return (f'M{_n(a[0])} {_n(a[1])}A{_n(r)} {_n(r)} 0 0 1 {_n(b[0])} {_n(b[1])}'
            f'M{_n(ma[0])} {_n(ma[1])}A{_n(r)} {_n(r)} 0 0 0 {_n(mb[0])} {_n(mb[1])}')


# ============================================================
# Joining the drawing to what the table prints
# ============================================================

def _rows(p: dict) -> dict[str, dict]:
    """Every row of the distribution table, by the id it was built under."""
    return {z['id']: z for z in p['zones']}


def _row_for(sid: str, rows: dict[str, dict]) -> dict | None:
    """The table row a drawn wedge takes its shade and its mark from.

    A behind-plate zone is its own row. A foul-line zone is half of a matched
    pair, and the pair is always read as one thing:

    * at a park whose sides are folded, the pair is already one row, carrying
      the mean of the two and a status that is `split` if the halves disagree;
    * at a park whose sides are named, the two rows are still drawn with one
      shade, from the mean of the two figures, and marked as netted only if
      both halves are.

    Note 4 in the module docstring is why. The returned dict is a row-shaped
    view, not necessarily a row object.

    The foul-line case is tested *before* the direct lookup, and that ordering
    is the whole point of the function rather than a detail. At a park whose
    sides are named both halves are real rows, so a direct lookup would find
    `1B-LB1` and shade the drawing — both sides of it — from the first-base
    row alone, which is the same asymmetry the mean exists to avoid, only
    hidden behind a symmetrical picture.
    """
    if sid[:3] not in ('1B-', '3B-'):
        return rows.get(sid)
    suffix = sid[3:]
    folded = rows.get('LINES-' + suffix)
    if folded is not None:
        return folded
    a, b = rows.get('1B-' + suffix), rows.get('3B-' + suffix)
    if a is None or b is None:
        return a or b
    both = {a['status'], b['status']}
    return {'fouls': (a['fouls'] + b['fouls']) / 2.0,
            'heading': a['heading'],
            'status': both.pop() if len(both) == 1 else 'split'}


# ============================================================
# The figure
# ============================================================

def _alt(p: dict) -> str:
    """What the drawing says, for a reader who is not looking at it.

    The busiest areas by name and figure, in the order the table below has
    them, because that ordering is the one thing the shading is for.
    """
    busy = [z for z in p['zones'] if z['fouls'] >= 0.05][:3]
    if busy:
        bits = '; then '.join(
            f'{z["heading"][0].lower() + z["heading"][1:]}, about '
            f'{z["fouls"]:.1f}' for z in busy)
        heaviest = f'Darkest: {bits}.'
    else:
        heaviest = 'The model puts no fouls in any area it tracks here.'
    sides = ('First base is drawn on the right, third base on the left.'
             if p['sides']['named'] else
             'Neither line is labelled: nothing establishes which is which.')
    return (f'Schematic plan of the foul ground at {p["name"]}, home plate at '
            f'the bottom and the seating areas drawn as bands of an arc '
            f'behind the two foul lines, shaded in five steps by fouls a '
            f'game. {heaviest} {sides}')


def _legend(p: dict, marked: bool) -> str:
    """The step boundaries, and what the netting mark does and does not cover.

    The netting line is not decoration. At 24 of the 31 parks there is no mark
    anywhere on the drawing, and a reader has to be told that this means the
    site could not attach a published net to these seats — not that there is
    no net.
    """
    swatches = ''.join(f'<span><i class="z{i}"></i>{w}</span>'
                       for i, w in enumerate(STEP_WORDS))
    out = [f'<p class="leg"><b>Fouls a game</b>{swatches}</p>']

    if marked:
        note = ('the club\'s own page puts these seats behind netting')
        others = [w for w, present in (
            ('partly netted', any(z['status'] == 'partially_netted'
                                  for z in p['zones'])),
            ('unverified', any(z['status'] == 'unknown' for z in p['zones'])),
            ('netted on one foul line and not the other',
             any(z['status'] == 'split' for z in p['zones'])),
        ) if present]
        tail = (f' Areas that are {" or ".join(others)} carry no mark.'
                if others else '')
        out.append(f'<p class="leg"><span><i class="nm"></i>{note}</span></p>'
                   f'<p class="dcap">The mark runs along the front of an area '
                   f'the club places fully behind netting.{tail} No mark is '
                   f'not no net: it is no published extent this site could '
                   f'attach to those seats.</p>')
    else:
        out.append('<p class="dcap"><strong>No netting is marked here</strong>, '
                   'because nothing published could be attached to these '
                   'seating areas. Read the absence as a missing source, not '
                   'as a missing net.</p>')
    return ''.join(out)


def park_diagram(p: dict) -> str:
    """The whole figure: drawing, legend, caption.

    `p` is what `site_build.build_park` produced, and the shading comes off
    `p['zones']` — the same figures, row for row, that the table under the
    drawing prints. That is the invariant worth keeping: a drawing that
    disagreed with the table beneath it would be worse than no drawing.
    """
    stadium = p['stadium']
    rows = _rows(p)
    f = frame()
    ox, oy = f['ox'], f['oy']

    # Subpaths, gathered per step rather than per zone. Every wedge in a step
    # is one `<path>`, which is both smaller and truer: the step is the only
    # thing the fill means, and one element per zone would invite a future
    # edit to hang a zone's identity off it.
    steps: dict[int, list[str]] = {}
    marks: list[str] = []
    outer = 0.0
    for a0, a1, bands in wedges(stadium):
        for sid, r0, r1 in bands:
            row = _row_for(sid, rows)
            if row is None:
                continue
            steps.setdefault(step_of(row['fouls']), []).append(
                _sector(a0, a1, r0, r1))
            if row['status'] == 'netted':
                marks.append(_arc(a0, a1, r0))
            if a0 <= 0.0:
                outer = max(outer, r1)

    paths = [f'<path class="z{i}" d="{"".join(subs)}"/>'
             for i, subs in sorted(steps.items())]
    if marks:
        paths.append(f'<path class="nm" d="{"".join(marks)}"/>')

    # The foul lines run out along the outer angular edge of the bowl, which is
    # where they are: the stands on a side begin at the line. Drawn a little
    # past the back of the last deck so each reads as a line running out of the
    # picture rather than as the edge of a shape.
    tip = _pt(0.0, outer * 1.07)
    mtip = _mirror(tip)
    paths.append(f'<path class="fl" d="M{_n(ox)} {_n(oy)}'
                 f'L{_n(tip[0])} {_n(tip[1])}M{_n(ox)} {_n(oy)}'
                 f'L{_n(mtip[0])} {_n(mtip[1])}"/>')

    # Home plate, and the one label the drawing needs in order to be read at
    # all. It sits in the open wedge of fair territory, which is the only
    # empty ground in the frame.
    paths.append(f'<path class="hp" d="M{_n(ox - 7)} {_n(oy - 7)}'
                 f'L{_n(ox + 7)} {_n(oy - 7)}L{_n(ox + 7)} {_n(oy + 2)}'
                 f'L{_n(ox)} {_n(oy + 9)}L{_n(ox - 7)} {_n(oy + 2)}Z"/>')
    labels = [f'<text class="pl" x="{_n(ox)}" y="{_n(oy - 17)}" '
              f'text-anchor="middle">Home plate</text>']

    # Constraint 5, in the one place a drawing could break it. Sixteen parks
    # have a source that names a side alongside specific seats; at the other
    # fifteen both lines are drawn and neither is named.
    #
    # The words run along their own line, set just off it on the fair side —
    # the only empty ground the frame has, since every seating area drawn here
    # is behind a line by definition. Beside the line rather than at the end of
    # it, so that it is the line being named and not a corner of the picture.
    if p['sides']['named']:
        d = math.sqrt(0.5)
        r = outer * 0.62
        lx, ly = ox + (r - 19) * d, oy - (r + 19) * d
        labels.append(f'<text x="{_n(lx)}" y="{_n(ly)}" text-anchor="middle" '
                      f'transform="rotate(315 {_n(lx)} {_n(ly)})">'
                      f'First base</text>')
        rx = f['w'] - lx
        labels.append(f'<text x="{_n(rx)}" y="{_n(ly)}" text-anchor="middle" '
                      f'transform="rotate(45 {_n(rx)} {_n(ly)})">'
                      f'Third base</text>')

    svg = (f'<svg viewBox="0 0 {_n(f["w"])} {_n(f["h"])}" role="img" '
           f'aria-label="{_esc(_alt(p))}">'
           f'{"".join(paths)}{"".join(labels)}</svg>')

    return (f'<figure class="dia">{svg}'
            f'{_legend(p, bool(marks))}'
            f'<figcaption class="dcap">Schematic, not to scale and not a '
            f"seating chart: one generic bowl, its depth set by this park's "
            f'published foul territory and backstop, on a scale shared by all '
            f'31 parks. Shade carries the figures and size does not, and both '
            f'foul lines are always shaded alike &mdash; the model builds them '
            f'as exact mirrors, so the gap between the two rows below is '
            f'simulation noise.</figcaption></figure>')


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


# ============================================================
# The styling
# ============================================================
#
# Served on the 31 park pages, alongside `site_build.CSS`. The ramp is the site's one accent teal at the
# top step and four steps down to near-paper, because the accent is already
# what this site uses for "the thing you are being pointed at" and a second
# hue would read as a second meaning. Red is not in it: red on this site means
# one thing, a seating area the club's own statement places outside its
# netting, and a shading ramp must not borrow it.
CSS = """
.dia{margin:.8rem 0 .2rem}
.dia svg{display:block;width:100%;max-width:31rem;height:auto;margin:0 auto}
.dia path{stroke:#fff;stroke-width:1.5;stroke-linejoin:round}
.z0{fill:#dfebed;background:#dfebed}
.z1{fill:#b4d5da;background:#b4d5da}
.z2{fill:#7fbac2;background:#7fbac2}
.z3{fill:#44909c;background:#44909c}
.z4{fill:#0b6a74;background:#0b6a74}
.dia path.nm{fill:none;stroke:#16181d;stroke-width:7;stroke-dasharray:10 7}
.dia path.fl{fill:none;stroke:#7b828e;stroke-width:2;stroke-dasharray:6 6}
.dia path.hp{fill:#16181d;stroke:none}
.dia text{fill:#5b6270;font-size:20px;font-weight:700;font-family:inherit;
 letter-spacing:.05em}
.dia text.pl{font-size:15px;font-weight:400;letter-spacing:.02em;fill:#7b828e}
.leg{display:flex;flex-wrap:wrap;align-items:center;gap:.15rem .75rem;
 font-size:.76rem;line-height:1.5;color:#4a505c;margin:.4rem 0}
.leg b{font-size:.66rem;letter-spacing:.07em;text-transform:uppercase;
 color:#5b6270}
.leg span{display:flex;align-items:center;gap:.32rem}
.leg i{display:block;width:1.2rem;height:.6rem;border:1px solid #c8ced6}
.leg i.nm{background:none;border:0;border-top:.28rem dashed #16181d;
 height:.28rem;width:1.4rem}
.dcap{font-size:.76rem;line-height:1.45;color:#5b6270;margin:.35rem 0 0;
 max-width:72ch}
.dcap strong{color:#16181d}
@media (prefers-color-scheme:dark){
 .dia path{stroke:#101216}
 .z0{fill:#1f434e;background:#1f434e}
 .z1{fill:#245762;background:#245762}
 .z2{fill:#2f7783;background:#2f7783}
 .z3{fill:#3c96a2;background:#3c96a2}
 .z4{fill:#4fb6c0;background:#4fb6c0}
 .dia path.nm{stroke:#e4e7ee}
 .dia path.fl{stroke:#6d7482}
 .dia path.hp{fill:#e4e7ee}
 .dia text{fill:#98a0b0}
 .dia text.pl{fill:#6d7482}
 .leg,.leg b,.dcap{color:#98a0b0}
 .leg i{border-color:#3a414d}
 .leg i.nm{border-top-color:#e4e7ee}
 .dcap strong{color:#e4e7ee}
}
"""
