"""
site_build.py — generate the public FoulCast site: 31 park pages plus a home
page, as static HTML.

Static because the pages have to be fast on a phone on stadium wifi and have to
be indexable, and because nothing on them changes between requests: the model
run is deterministic (fixed lineup, fixed seed) and the sources behind the
netting and park figures were read on one day and are dated on the page.

    python site_build.py                     # build into ./site
    python site_build.py --sims 100          # faster, noisier model run
    python site_build.py --base-url https://example.com   # emit canonical tags
    python site_build.py --no-model          # re-render copy from the cache

The model run is the slow part (about 15 seconds a park), so it is cached to
`.cache/site/park_stats.json` and reused unless `--refresh` is passed. Copy
changes rebuild in under a second.

WHAT THIS FILE IS NOT ALLOWED TO DO
-----------------------------------
Four constraints come out of `AUDIT.md` and `NOTES.md` and are enforced by
`tests/test_site.py` rather than by care:

1. **No printed section numbers.** Nineteen of the 31 zone tables in
   `stadium.py` are suspect on their numbering (`AUDIT.md`, Step 10 update):
   nine contradicted by the club's own seating map, ten more carrying labels
   that cannot describe a continuous bowl. Zones are named in words.
2. **Netting leads; the model follows.** The netting section is above the model
   section on every page, because netting is sourced and the model is an
   estimate. Where netting is a gap the page says so in the same position, at
   the same size.
3. **The word "safe" never appears.** Netting is not safety — the clubs' own
   pages say fans in netted sections remain exposed to balls leaving the field.
   The site says "behind netting" / "not behind netting" and "higher risk" /
   "lower risk".
4. **No accuracy claims.** The model has never been compared with observed foul
   landings, and every page has to be readable by someone who knows that.
"""
import argparse
import html
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from foulball.batter_profiles import YANKEES_2024_PROFILES, RED_SOX_2024_PROFILES
from foulball.matchup_engine import predict_game_fouls
from foulball.stadium import STADIUMS, PARK_PARAMS
from foulball.netting import join_park, PDL_RULE
from site_data import (
    PARK_SOURCES, ZONE_WORDS, AREA_WORDS, GAP_WORDS, NET_HEIGHT_WORDS,
    COVER_WORDS, COVER_APPLIED, MODEL_LIMITS, RESEARCH_DATE,
    FOUL_AREA_CAVEAT, BACKSTOP_CAVEAT, OVERHANG_CAVEAT,
    CLEM_TABLE, CLEM_BASE, CLEM_OVERHANG_SNAPSHOT, SEAMHEADS_BASE,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, 'site')
CACHE = os.path.join(ROOT, '.cache', 'site', 'park_stats.json')

# Same configuration as tests/test_plausibility.py and park_sweep.py, so the
# numbers on the site are the numbers the rest of the repo checks.
STANDARD_RHP_MIX = {'FF': 0.30, 'SL': 0.20, 'CH': 0.15,
                    'SI': 0.15, 'CU': 0.10, 'FC': 0.10}
SEED = 42
SIMS = 400

BUILT = date.today().isoformat()


# ============================================================
# The model run
# ============================================================

def standard_lineups():
    """The two lineups that make one game. Held identical across all parks so
    the only thing varying between pages is the park."""
    return [list(RED_SOX_2024_PROFILES.values()),
            list(YANKEES_2024_PROFILES.values())]


def run_park(park_key: str, sims: int) -> dict:
    """One full game at one park: both lineups, summed.

    A single `predict_game_fouls` call covers one team's plate appearances and
    is half a game — the units error `NOTES.md` records at the top.
    """
    np.random.seed(SEED)
    stadium = STADIUMS[park_key]()

    fouls: dict[str, float] = {}
    ev_weight: dict[str, float] = {}
    total = 0.0
    matched = 0.0

    for lineup in standard_lineups():
        pred = predict_game_fouls(lineup, 'Standard RHP', STANDARD_RHP_MIX,
                                  stadium, simulations_per_batter=sims)
        for e in pred.all_events:
            total += e.weight
            if e.section is None:
                continue
            matched += e.weight
            sid = e.section.section_id
            fouls[sid] = fouls.get(sid, 0.0) + e.weight
            ev_weight[sid] = ev_weight.get(sid, 0.0) + e.weight * e.exit_velocity

    for sec in stadium.sections:
        fouls.setdefault(sec.section_id, 0.0)

    return {
        'park': park_key,
        'sims': sims,
        'seed': SEED,
        'zone_fouls': fouls,
        'zone_ev': {sid: (ev_weight.get(sid, 0.0) / w if w > 0 else 0.0)
                    for sid, w in fouls.items()},
        'into_seats': matched,
        'total_fouls': total,
        'unmatched': total - matched,
    }


def load_stats(refresh: bool, sims: int, cache_path: str = CACHE) -> dict:
    """Model stats for every park, from cache where possible."""
    cached: dict = {}
    if os.path.exists(cache_path) and not refresh:
        with open(cache_path, encoding='utf-8') as fh:
            cached = json.load(fh)

    keys = list(STADIUMS)
    out = dict(cached)
    for i, key in enumerate(keys, 1):
        entry = cached.get(key)
        if entry and entry.get('sims') == sims and not refresh:
            continue
        print(f'  [{i}/{len(keys)}] simulating {key} ...', flush=True)
        out[key] = run_park(key, sims)

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=1)
    return out


# ============================================================
# Turning a zone into words
# ============================================================

_PAREN = re.compile(r'\s*\(.*\)\s*$')
_SIDE_PREFIX = re.compile(r'^(1B|3B|Behind Plate)\s*')


def area_word(section) -> str:
    """The seating-area word from this park's own label, numbers stripped.

    `AUDIT.md`'s revised claim is that the section names track real seating
    charts "at the level of grouping and deck level" and that their numeric
    ranges are unverified everywhere and wrong at nine parks. This function
    keeps the first half and discards the second: the parenthesised section
    range goes, the product word stays, and only product words that carry
    location meaning survive `AREA_WORDS`.
    """
    name = _SIDE_PREFIX.sub('', _PAREN.sub('', section.name)).strip()
    return AREA_WORDS.get(name, '')


def zone_words(section) -> tuple[str, str, str]:
    """(heading, level phrase, area word) for one zone."""
    heading, level = ZONE_WORDS[section.section_id]
    return heading, level, area_word(section)


# ============================================================
# Assembling one park
# ============================================================

NETTING_CLUB_CAVEAT = (
    'Clubs describe their netting the same way and it is worth reading '
    'literally: there is "some amount of netting or screening" in front of the '
    'listed seats, its "height and coverage will vary by section", and fans '
    'sitting behind it "are still exposed to objects leaving the field of '
    'play". Behind netting is not the same as fully protected, and no seat on '
    'this site is described as protected outright.'
)


def build_park(park_key: str, stats: dict) -> dict:
    """Everything one page needs, resolved from the model and the sources."""
    stadium = STADIUMS[park_key]()
    src = PARK_SOURCES[park_key]
    join = join_park(stadium, park_key)
    params = PARK_PARAMS[park_key]
    st = stats[park_key]

    by_id = {s.section_id: s for s in stadium.sections}
    missing = set(by_id) - set(ZONE_WORDS)
    if missing:
        raise SystemExit(f'{park_key}: no plain-words phrase for {sorted(missing)}')

    into = st['into_seats']
    zones = []
    for sid, fouls in st['zone_fouls'].items():
        sec = by_id[sid]
        heading, level, area = zone_words(sec)
        zn = stadium.zone_netting.get(sid)
        zones.append({
            'id': sid,
            'heading': heading,
            'level': level,
            'area': area,
            'fouls': fouls,
            'share': (fouls / into * 100) if into else 0.0,
            'ev': st['zone_ev'].get(sid, 0.0),
            'status': zn.status if zn else 'unknown',
            'blocks_catch': bool(zn and zn.blocks_catch),
        })
    zones.sort(key=lambda z: -z['fouls'])

    # Netting, in the three states a reader has to be able to tell apart.
    net = {'state': join.status, 'park': join.park}
    if join.status == 'mapped':
        net['netted'] = [z for z in zones if z['status'] == 'netted']
        net['partial'] = [z for z in zones if z['status'] == 'partially_netted']
        net['open'] = [z for z in zones if z['status'] == 'not_netted']
        net['unknown'] = [z for z in zones if z['status'] == 'unknown']
        # Where the published extent lands differently on the two foul lines,
        # the page is making a claim about *which* side is which. That claim
        # rests on the zone table's printed labels, which `AUDIT.md`'s revised
        # position holds to be unverified at every park — so it has to be
        # hedged where it is load-bearing, and only there.
        by_side = {}
        for z in zones:
            if z['id'][:3] in ('1B-', '3B-'):
                by_side.setdefault(z['id'][:2], {})[z['id'][3:]] = z['status']
        net['sides_differ'] = (len(by_side) == 2
                               and by_side['1B'] != by_side['3B'])
    else:
        net['gap_label'], net['gap_text'] = GAP_WORDS[join.gap_kind]

    height = None
    if park_key in NET_HEIGHT_WORDS:
        height = NET_HEIGHT_WORDS[park_key][0]
    elif join.park.height and join.park.height != 'varies by section':
        height = join.park.height
    elif join.park.height == 'varies by section':
        height = 'published only as varying by section'

    return {
        'key': park_key,
        'slug': src['slug'],
        'name': stadium.name,
        'city': stadium.city,
        'team': stadium.team,
        'src': src,
        'params': params,
        'join': join,
        'net': net,
        'net_height': height,
        'zones': zones,
        'into_seats': into,
        'total_fouls': st['total_fouls'],
        'unmatched_pct': (st['unmatched'] / st['total_fouls'] * 100)
                         if st['total_fouls'] else 0.0,
        'sims': st['sims'],
    }


# ============================================================
# Formatting helpers
# ============================================================

def fouls_str(x: float) -> str:
    # An area the model never reaches is worth saying plainly: at a couple of
    # parks it is a finding about the zone table rather than about the park.
    if x <= 0.0:
        return 'none'
    if x < 0.05:
        return 'under 0.1'
    return f'{x:.1f}'


def share_str(x: float) -> str:
    if x < 0.5:
        return '<1%'
    return f'{x:.0f}%'


def zone_label(z: dict) -> str:
    """Heading plus the park's own area word, where it adds something."""
    if z['area']:
        return f"{z['heading']} <span class=\"area\">&mdash; {z['area']}</span>"
    return z['heading']


def e(s) -> str:
    return html.escape(str(s), quote=True)


# ============================================================
# The page shell
# ============================================================

CSS = """
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,
 "Helvetica Neue",Arial,sans-serif;color:#16181d;background:#fff;
 word-wrap:break-word}
main,header,footer{max-width:44rem;margin:0 auto;padding:0 1.1rem}
header{padding-top:1.4rem}
h1{font-size:1.6rem;line-height:1.25;margin:.2rem 0 .3rem;letter-spacing:-.01em}
h2{font-size:1.18rem;line-height:1.3;margin:2.4rem 0 .6rem;letter-spacing:-.01em}
h3{font-size:1rem;margin:1.4rem 0 .4rem}
p{margin:.7rem 0}
a{color:#0b5cad}
a:hover{color:#083f77}
.sub{color:#5b6270;font-size:.94rem;margin:.1rem 0 0}
.lede{font-size:1.05rem}
.tag{display:inline-block;font-size:.76rem;line-height:1.4;padding:.1rem .45rem;
 border-radius:.25rem;border:1px solid currentColor;white-space:nowrap;
 vertical-align:.05rem}
.tag-net{color:#1a5e2a}
.tag-part{color:#8a5200}
.tag-open{color:#8c1f28}
.tag-unk{color:#4a5160}
.note{border-left:3px solid #c9ced8;padding:.05rem 0 .05rem .85rem;
 margin:1rem 0;color:#3b414d}
.warn{border-left:3px solid #b8802a;background:#fdf7ec;padding:.7rem .9rem;
 margin:1.1rem 0;border-radius:0 .25rem .25rem 0}
.gap{border-left:3px solid #8c1f28;background:#fdf1f1;padding:.7rem .9rem;
 margin:1.1rem 0;border-radius:0 .25rem .25rem 0}
.ok{border-left:3px solid #1a5e2a;background:#f0f7f1;padding:.7rem .9rem;
 margin:1.1rem 0;border-radius:0 .25rem .25rem 0}
.zones{list-style:none;padding:0;margin:1rem 0}
.zones li{padding:.6rem 0;border-top:1px solid #e5e8ee}
.zones li:last-child{border-bottom:1px solid #e5e8ee}
.zrow{display:flex;gap:.8rem;align-items:baseline;justify-content:space-between}
.zname{flex:1 1 auto;min-width:0}
.znum{flex:0 0 auto;font-variant-numeric:tabular-nums;text-align:right;
 font-size:.95rem;color:#3b414d}
.area{color:#5b6270;font-weight:400}
.zmeta{color:#5b6270;font-size:.84rem;margin-top:.15rem}
ol.ranked{padding-left:1.2rem}
ol.ranked li{margin:.5rem 0}
dl.figs{margin:1rem 0}
dl.figs dt{font-weight:600;margin-top:1.1rem}
dl.figs dd{margin:.25rem 0 0;color:#2c313b}
dl.figs dd.attrib{color:#5b6270;font-size:.9rem;margin-top:.35rem}
.big{font-size:1.5rem;font-weight:600;font-variant-numeric:tabular-nums}
.parklist{list-style:none;padding:0;margin:1rem 0}
.parklist li{border-top:1px solid #e5e8ee;padding:.62rem 0}
.parklist li:last-child{border-bottom:1px solid #e5e8ee}
.parklist a{font-weight:600;text-decoration:none}
.parklist a:hover{text-decoration:underline}
.parklist .sub{margin-top:.1rem}
footer{margin:3rem 0 2.5rem;color:#5b6270;font-size:.9rem}
footer p{margin:.5rem 0}
hr{border:0;border-top:1px solid #e5e8ee;margin:2.2rem 0}
@media (prefers-color-scheme:dark){
 body{background:#111318;color:#e6e8ee}
 a{color:#7db6f0}a:hover{color:#a8cff7}
 .sub,.zmeta,.area,dl.figs dd.attrib,footer{color:#98a0b0}
 .note{border-left-color:#3a414f;color:#c3c9d5}
 .warn{background:#241d10;border-left-color:#a8791f}
 .gap{background:#2a1416;border-left-color:#b3434d}
 .ok{background:#12241a;border-left-color:#2f7d45}
 .zones li,.parklist li,hr{border-color:#282d38}
 .znum,dl.figs dd{color:#c3c9d5}
 .tag-net{color:#6fce8b}.tag-part{color:#e0a850}
 .tag-open{color:#f08a92}.tag-unk{color:#98a0b0}
}
"""

# Whitespace is not free on a phone, and this is served static.
CSS_MIN = re.sub(r'\s*\n\s*', '', CSS).strip()


def page(title: str, description: str, body: str, canonical: str | None,
         base_url: str) -> str:
    head = [
        '<!doctype html>',
        '<html lang="en">',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f'<title>{e(title)}</title>',
        f'<meta name="description" content="{e(description)}">',
    ]
    if base_url and canonical is not None:
        head.append(f'<link rel="canonical" href="{e(base_url + canonical)}">')
    head.append(f'<style>{CSS_MIN}</style>')
    return '\n'.join(head) + '\n' + body + '\n</html>\n'


# ============================================================
# The park page
# ============================================================

def netting_section(p: dict) -> str:
    """Netting first, on every page, whatever its state.

    Three states, and a reader has to be able to tell them apart at a glance:
    the club published an extent and it fits this model's seating areas; the
    club published one and it does not fit; nobody published one at all.
    """
    net, join, name = p['net'], p['join'], p['name']
    out = ['<h2 id="netting">Protective netting</h2>']

    src_line = (f'<p class="sub">Source: <a href="{e(join.park.source)}" '
                f'rel="nofollow">{e(join.park.source)}</a> &mdash; '
                f'{e(join.park.source_kind.replace("_", " "))}, '
                f'{e(join.park.year) if join.park.year else "undated"}, '
                f'read {e(join.park.retrieved)}.</p>')

    if net['state'] == 'mapped':
        out.append(
            f'<div class="ok"><p><strong>Published, and it matches the seating '
            f'areas on this page.</strong> The club states where the netting '
            f'runs, and the areas it names line up with the areas this model '
            f'carries for {e(name)}. That is true at 11 of the 31 parks on '
            f'this site.</p></div>')

        def listing(zs, tag, tagcls, lead):
            if not zs:
                return ''
            items = ''.join(
                f'<li><div class="zrow"><div class="zname">{zone_label(z)}</div>'
                f'<div class="znum"><span class="tag {tagcls}">{tag}</span></div>'
                f'</div><div class="zmeta">{e(z["level"])}</div></li>'
                for z in zs)
            return f'<h3>{lead}</h3><ul class="zones">{items}</ul>'

        out.append(listing(net['netted'], 'behind netting', 'tag-net',
                           'Behind netting'))
        out.append(listing(net['partial'], 'partly netted', 'tag-part',
                           'Partly behind netting'))
        if net['partial']:
            out.append(
                '<p class="note">Partly means the published extent covers some '
                'of the area and not the rest. Nobody publishes where the edge '
                'falls within it, so this model cannot split the area in two '
                'and treats the whole of it as reachable.</p>')
        out.append(listing(net['open'], 'not behind netting', 'tag-open',
                           'Not behind netting'))
        out.append(listing(net['unknown'], 'not stated', 'tag-unk',
                           'Not mentioned either way'))
        if net['unknown']:
            out.append(
                '<p class="note">The club\'s statement does not name these '
                'areas at all. Not mentioned is not the same as not netted, so '
                'nothing is claimed about them here.</p>')
        if net['sides_differ']:
            out.append(
                '<div class="warn"><p><strong>The netting comes out different '
                'on the two foul lines here, and which line is which is the '
                'weakest claim on this page.</strong> The club\'s statement is '
                'sourced. Attaching it to the first-base side rather than the '
                'third rests on the seat labels this model carries, and those '
                'labels are unverified at every park on this site &mdash; '
                'contradicted outright by the club\'s own map at nine of them. '
                'If they are reversed here, so is everything below that '
                'distinguishes one foul line from the other. Read the two foul '
                'lines together; either one on its own is much weaker.</p>'
                '</div>')
    else:
        out.append(
            f'<div class="gap"><p><strong>Not verified at {e(name)}. '
            f'{e(net["gap_label"])}.</strong></p>'
            f'<p>{net["gap_text"]}</p></div>')
        out.append(
            '<p>This is a gap, and it is stated as one rather than left blank. '
            'It is also the normal case: 20 of the 31 parks on this site have '
            'no netting that can be attached to specific seats. Everything '
            'below this point should be read knowing that some of the areas '
            'the model puts fouls into may be entirely behind a net.</p>')
        if join.park.source_kind == 'none':
            out.append(
                f'<p class="sub">Checked {e(join.park.retrieved)}: '
                f'{e(join.park.source)}</p>')
            if join.gap_kind == 'no_source_at_all':
                out.append(f'<p class="note">The only rule that reaches this '
                           f'park: {e(PDL_RULE)}.</p>')
            return '\n'.join(x for x in out if x)

    if p['net_height']:
        out.append(f'<h3>Published net height</h3><p>{e(p["net_height"])}.</p>')
        if p['key'] in NET_HEIGHT_WORDS:
            out.append('<p class="note">The club states these heights against '
                       'section numbers. This site does not print section '
                       'numbers, for the reason given at the foot of the page, '
                       'so the same statement is given by position instead.</p>')

    out.append(src_line)
    out.append(f'<p class="note">{NETTING_CLUB_CAVEAT}</p>')
    return '\n'.join(x for x in out if x)


def zones_section(p: dict) -> str:
    tagmap = {
        'netted': ('behind netting', 'tag-net'),
        'partially_netted': ('partly netted', 'tag-part'),
        'not_netted': ('not behind netting', 'tag-open'),
        'unknown': ('netting not verified', 'tag-unk'),
    }
    items = []
    for z in p['zones']:
        tag, cls = tagmap[z['status']]
        ev = (f' &middot; leaving the bat at about {z["ev"]:.0f} mph'
              if z['fouls'] >= 0.05 else '')
        items.append(
            f'<li><div class="zrow"><div class="zname">{zone_label(z)}</div>'
            f'<div class="znum">{fouls_str(z["fouls"])}</div></div>'
            f'<div class="zmeta">{e(z["level"])} &middot; '
            f'{share_str(z["share"])} of the fouls that reach seats{ev} '
            f'&middot; <span class="tag {cls}">{tag}</span></div></li>')

    return f'''<h2 id="zones">Where the model puts the fouls</h2>
<p>One full game, both lineups, the same 18 batters at every park on this site
so that the park is the only thing that changes. Figures are foul balls per
game reaching each area, with the largest first.</p>
<ul class="zones">{''.join(items)}</ul>
<p class="sub">Model estimate. {p['sims']} simulations per batter, fixed seed.
Not a count of anything observed.</p>
<div class="warn"><p><strong>About {p['unmatched_pct']:.0f}% of the fouls this
model produces at {e(p['name'])} land where it has no seating area to put
them</strong> &mdash; deep down the lines near the poles, in the gap between
home plate and the front row, or under a covered deck. Those balls are counted
in the park's total and then dropped. It is why the figures above should be read
as a shape rather than a census.</p></div>'''


def readings_section(p: dict) -> str:
    """The same field, read two opposite ways.

    A netted zone is worth nothing to someone who wants a ball and is the best
    seat in the house to someone who does not want to be hit by one. Both
    readings come off `ZoneNetting.status`; neither is derived from the other.
    """
    mapped = p['net']['state'] == 'mapped'
    zones = p['zones']

    catchable = [z for z in zones if not z['blocks_catch'] and z['fouls'] >= 0.05]
    excluded = [z for z in zones if z['blocks_catch']]

    souvenir = ''.join(
        f'<li>{zone_label(z)} &mdash; about {fouls_str(z["fouls"])} a game'
        + (' <span class="tag tag-part">partly netted</span>'
           if z['status'] == 'partially_netted' else '')
        + (' <span class="tag tag-unk">netting not verified</span>'
           if z['status'] == 'unknown' else '')
        + '</li>'
        for z in catchable[:6])

    if mapped:
        if excluded:
            exc = ''.join(f'<li>{zone_label(z)} &mdash; about '
                          f'{fouls_str(z["fouls"])} a game arrive here, and a '
                          f'net stands in front of them</li>' for z in excluded)
            note = (f'<p>These areas are left out of the list above because the '
                    f'club\'s netting covers them. Balls still arrive &mdash; '
                    f'they just cannot be caught:</p><ul class="zones">{exc}</ul>')
        else:
            note = ('<p>Nothing is excluded here: the club\'s published netting '
                    'does not fully cover any of the areas this model tracks at '
                    'this park.</p>')
    else:
        note = ('<div class="gap"><p><strong>Nothing is excluded from this '
                'list, because this park\'s netting could not be verified.</strong> '
                'At a park where the netting is known, the areas behind it come '
                'off this list entirely. Here they cannot, so treat the top of '
                'the list as a list of where balls arrive, not where they can '
                'be caught.</p></div>')

    risk = ''.join(
        f'<li>{zone_label(z)} &mdash; about {fouls_str(z["fouls"])} a game, '
        f'leaving the bat at about {z["ev"]:.0f} mph. '
        + {'netted': '<span class="tag tag-net">behind netting</span>',
           'partially_netted': '<span class="tag tag-part">partly netted</span>',
           'not_netted': '<span class="tag tag-open">not behind netting</span>',
           'unknown': '<span class="tag tag-unk">netting not verified</span>',
           }[z['status']]
        + '</li>'
        for z in zones[:6] if z['fouls'] >= 0.05)

    if mapped:
        risk_note = (
            '<p>Areas marked as behind netting carry the same modelled foul '
            'traffic as they would without a net &mdash; the net does not stop '
            'balls being hit there, it stops them reaching the seats. Read the '
            'marking as lower risk, not as no risk: the clubs themselves say '
            'fans behind netting remain exposed to balls leaving the field.</p>')
    else:
        risk_note = (
            '<p>Every area here is marked as unverified, because this park\'s '
            'netting could not be attached to specific seats. That is not the '
            'same as saying there is no net &mdash; most of these parks '
            'certainly have one. It means this site cannot tell you which of '
            'these areas it stands in front of, and so cannot tell you which '
            'of them is lower risk than the order above suggests.</p>')

    return f'''<h2 id="readings">The same figures, read two ways</h2>
<p>Whether a net in front of a seat is good news depends entirely on why you
are asking. One field decides both readings, and they point opposite ways.</p>

<h3>If you want to catch a ball</h3>
<p>Areas ranked by modelled foul traffic, with anything the sources place fully
behind netting removed &mdash; a ball cannot be caught through a net.</p>
<ol class="ranked">{souvenir}</ol>
{note}

<h3>If you want to know what is coming at you</h3>
<p>The same areas, in the same order, with the netting shown rather than
removed. The speeds are how fast the ball left the bat, not how fast it arrives
&mdash; it slows on the way, by an amount this model computes but has never
checked against a measured landing.</p>
<ol class="ranked">{risk}</ol>
{risk_note}'''


def figures_section(p: dict) -> str:
    src, params = p['src'], p['params']
    name = p['name']
    out = [f'<h2 id="figures">The sourced figures behind this park</h2>',
           '<p>Two published measurements do the work of placing this park\'s '
           'seating in the model. Both are given here with where they came '
           'from and what disagrees with them.</p>',
           '<dl class="figs">']

    # Foul territory
    out.append('<dt>Foul territory area</dt>')
    if src['foul_area']:
        out.append(f'<dd><span class="big">{src["foul_area"]:,}</span> sq ft</dd>')
        out.append(f'<dd>{e(src["foul_area_basis"])}</dd>')
        out.append('<dd>The model uses it to scale how far this park\'s seating '
                   'bands sit from home plate down the lines, against a '
                   'fleet-median park of 22,900 sq ft.</dd>')
    else:
        out.append('<dd><strong>Not published.</strong></dd>')
        out.append(f'<dd>{e(src["foul_area_basis"])}</dd>')
    out.append(f'<dd class="attrib">{FOUL_AREA_CAVEAT}</dd>')

    # Backstop
    out.append('<dt>Backstop distance</dt>')
    if src['backstop']:
        out.append(f'<dd><span class="big">{src["backstop"]}</span> ft from '
                   f'home plate to the fence behind it</dd>')
        out.append(f'<dd>{e(src["backstop_basis"])}</dd>')
        if src.get('backstop_conflict'):
            out.append(f'<dd><strong>Sources disagree.</strong> '
                       f'{e(src["backstop_conflict"])}</dd>')
        out.append('<dd>The model pins the front row of the seats behind the '
                   'plate one foot beyond this figure &mdash; seats stand '
                   'behind a fence, not on it. That one foot is the smallest '
                   'increment the sources can express, not a measurement of '
                   'this park.</dd>')
    else:
        out.append('<dd><strong>Not published.</strong></dd>')
        out.append(f'<dd>{e(src["backstop_basis"])}</dd>')
    out.append(f'<dd class="attrib">{BACKSTOP_CAVEAT}</dd>')

    # Deck cover
    out.append('<dt>Deck cover</dt>')
    if params.upper_overhang is not None:
        applied = COVER_APPLIED.get(params.upper_cover, False)
        cast = COVER_WORDS.get(params.upper_cover, 'something unidentified')
        out.append(f'<dd>About {params.lower_overhang:.0f}% of the lower deck '
                   f'and {params.upper_overhang:.0f}% of the upper deck sit '
                   f'under cover.</dd>')
        if applied:
            out.append(f'<dd>This model treats the upper deck\'s cover as {cast}, '
                       f'which a high foul ball would hit. The covered part of '
                       f'that deck therefore receives nothing here.</dd>')
        else:
            out.append(f'<dd>This model treats the upper deck\'s cover as {cast} '
                       f'&mdash; a foul pop flies underneath it &mdash; so the '
                       f'figure is <em>not</em> applied and the whole deck stays '
                       f'reachable.</dd>')
        out.append(f'<dd class="attrib"><a href="{e(CLEM_OVERHANG_SNAPSHOT)}" '
                   f'rel="nofollow">Andrew Clem\'s overhang columns</a>. '
                   f'{OVERHANG_CAVEAT}</dd>')
    else:
        out.append('<dd><strong>Not published.</strong> No cover figure exists '
                   'for this park, so none is applied.</dd>')

    out.append('</dl>')

    if src.get('extra'):
        out.append(f'<div class="note"><p>{src["extra"]}</p></div>')

    links = [f'<a href="{e(CLEM_TABLE)}" rel="nofollow">Clem, Stadium '
             f'Statistics</a>']
    if src.get('clem_page'):
        links.append(f'<a href="{e(CLEM_BASE + src["clem_page"])}" '
                     f'rel="nofollow">Clem, {e(name)}</a>')
    if src.get('seamheads'):
        links.append(f'<a href="{e(SEAMHEADS_BASE + src["seamheads"])}" '
                     f'rel="nofollow">Seamheads ballpark database</a>')
    # A park with nothing published still gets its sources listed, but as
    # places that were checked rather than places a figure came from.
    lead = ('Checked on' if src['foul_area'] is None and src['backstop'] is None
            else 'Read')
    out.append(f'<p class="sub">{lead} {e(RESEARCH_DATE)}: '
               f'{" &middot; ".join(links)}.</p>')
    return '\n'.join(out)


def limits_section(p: dict) -> str:
    items = ''.join(f'<h3>{e(t)}</h3><p>{body}</p>' for t, body in MODEL_LIMITS)
    return f'''<h2 id="limits">What this model does not know</h2>
<p>Written out rather than buried, because a reader who does not know these
things will read the figures above as more than they are.</p>
{items}
<h3>Why there are no section numbers on this page</h3>
<p>This model carries a printed seat label for every area it tracks. Those
labels have been checked against the clubs' own current seating maps, and at
nine of the 31 parks the club's map contradicts them outright; at ten more, the
labels cannot describe a continuous seating bowl at all. Nineteen of 31 are
therefore not trustworthy, and there is no way to tell from the outside which
side of that line a given park falls on. So the areas on this page are described
by where they are, and no seat number is printed anywhere on this site.</p>'''


def park_page(p: dict, base_url: str) -> str:
    net_state = p['net']['state']
    if net_state == 'mapped':
        net_phrase = 'netting sourced from the club'
    else:
        net_phrase = 'netting not verified'

    title = f"{p['name']} foul balls by zone | FoulCast"
    desc = (f"Where foul balls land at {p['name']}, {p['city']} — a zone-by-zone "
            f"model estimate, {net_phrase}, and the park's sourced foul "
            f"territory and backstop figures. Never checked against real fouls.")
    if len(desc) > 300:
        desc = desc[:297] + '...'

    body = f'''<body>
<header>
<p class="sub"><a href="../">FoulCast</a></p>
<h1>Foul balls at {e(p['name'])}</h1>
<p class="sub">{e(p['team'])} &middot; {e(p['city'])}</p>
</header>
<main>
<p class="lede">This page estimates where foul balls come down at
{e(p['name'])}, area by area, and states what is known about the protective
netting in front of those areas.</p>
<div class="warn"><p><strong>None of it has been checked against a real foul
ball.</strong> No public record exists of where foul balls actually land at this
or any other ballpark. The netting below is sourced from the club. The
distribution below that is a physics model, and it has never been validated
against an observed landing &mdash; not here, not anywhere.</p></div>

{netting_section(p)}

{zones_section(p)}

{readings_section(p)}

{figures_section(p)}

{limits_section(p)}

<hr>
<footer>
<p><a href="../">All 31 ballparks</a></p>
<p>Netting read from club pages on {e(RESEARCH_DATE)}. Park dimensions from
Andrew Clem's stadium statistics, cross-checked against the Seamheads ballpark
database. Model figures rebuilt {e(BUILT)}.</p>
</footer>
</main>
</body>'''
    return page(title, desc, body, f'/{p["slug"]}/', base_url)


# ============================================================
# The home page
# ============================================================

def home_page(parks: list[dict], base_url: str) -> str:
    parks = sorted(parks, key=lambda p: p['name'])
    mapped = [p for p in parks if p['net']['state'] == 'mapped']
    gaps = [p for p in parks if p['net']['state'] != 'mapped']

    def row(p):
        if p['net']['state'] == 'mapped':
            tag = '<span class="tag tag-net">netting sourced</span>'
        else:
            tag = '<span class="tag tag-unk">netting not verified</span>'
        return (f'<li><a href="{e(p["slug"])}/">{e(p["name"])}</a> {tag}'
                f'<div class="sub">{e(p["city"])} &middot; {e(p["team"])}'
                f'<br>Model estimate: about {p["into_seats"]:.0f} foul balls a '
                f'game reach seats here</div></li>')

    title = 'Foul balls by ballpark — where they land, and what the netting covers | FoulCast'
    desc = ('Foul ball estimates for all 31 major and minor league ballparks: '
            'where they land by seating area, what each club publishes about '
            'its protective netting, and where that netting is unknown.')

    body = f'''<body>
<header>
<h1>Where foul balls land, ballpark by ballpark</h1>
<p class="sub">31 ballparks &middot; netting first, model second</p>
</header>
<main>
<p class="lede">Every page here does two things: it says what the club publishes
about the protective netting in front of a given set of seats, and it estimates
how many foul balls a game reach those seats. The first is sourced. The second
is a model.</p>

<div class="warn"><p><strong>The model has never been checked against a real
foul ball.</strong> There is no public record of where foul balls actually land
&mdash; Statcast logs that a foul happened, not where it came down. So the
distributions on these pages are estimates from physics and published park
dimensions, and no page here puts a number on how often the model gets it
right, because there is nothing to compute one from.</p></div>

<h2>What is sourced and what is not</h2>
<p><strong>Netting is sourced.</strong> Each club's own current netting or
seating page was read in a browser on {e(RESEARCH_DATE)}. Where the club
publishes an extent that can be matched to specific seating areas, those areas
are marked. That is true at <strong>{len(mapped)} of the 31 parks</strong>.</p>
<p><strong>At the other {len(gaps)} it is a gap</strong>, and the pages say so
in the same place, at the same size, rather than leaving a blank. Some clubs
publish nothing; one declines on principle; one contradicts itself; and at
twelve parks the club does publish an extent but this model's own seat labels
cannot be reconciled with it &mdash; which is a fault in the model, not in the
club.</p>
<p><strong>The park dimensions are sourced</strong> &mdash; foul territory area
and backstop distance, from Andrew Clem's stadium statistics, cross-checked
against the Seamheads ballpark database, with the disagreements between them
stated on each page. They place each park's seating. They do not shape it: no
public source gives the angle of a seating area off the foul line or the height
of a deck in feet, for any ballpark, so every park here shares one bowl shape
and every park is modelled as an exact left-right mirror.</p>
<p>One consequence is visible from the list below and worth saying out loud: the
seats at field level behind home plate come out busiest at all 31 parks. That is
partly a real effect &mdash; balls deflected back over the catcher have to land
somewhere, and it is why there is a screen there &mdash; and partly an artefact
of every park sharing one bowl shape. It is not a finding about any individual
ballpark.</p>

<h2>Why there are no section numbers here</h2>
<p>This model carries printed seat labels for every area it tracks. Checked
against the clubs' current seating maps, nine parks' labels are contradicted
outright and ten more cannot describe a continuous seating bowl. Nineteen of
31 are unreliable and there is no way to tell which. So seating is described by
position &mdash; the lower bowl behind the plate, the dugout boxes on the
third-base side &mdash; and no seat number appears anywhere on this site.</p>

<h2>The same figures read two ways</h2>
<p>A net in front of a seat means opposite things depending on why you are
asking. If you want to take a ball home, a netted area is worth nothing and
comes off the list. If you want to know what is coming at you, the same area is
the one with something standing in front of it. Every park page gives both
readings off the same field, and neither is derived from the other.</p>
<p>No seat on this site is described as protected outright, and none of them is
called a good bet either. The clubs' own netting pages say fans sitting behind
netting "are still exposed to objects leaving the field of play", and this model
has never seen a real foul ball. Seats are described as behind netting or not
behind netting; risk is described as higher or lower.</p>

<h2>Ballparks with sourced netting <span class="sub">({len(mapped)})</span></h2>
<ul class="parklist">{''.join(row(p) for p in mapped)}</ul>

<h2>Ballparks where netting is a gap <span class="sub">({len(gaps)})</span></h2>
<p>Each of these pages says which kind of gap it is.</p>
<ul class="parklist">{''.join(row(p) for p in gaps)}</ul>

<hr>
<footer>
<p>Netting read from club pages on {e(RESEARCH_DATE)}. Park dimensions from
Andrew Clem's stadium statistics and the Seamheads ballpark database. Model
figures rebuilt {e(BUILT)}.</p>
<p>FoulCast is a model of foul ball flight. It is not affiliated with Major
League Baseball or with any club, and nothing on it will keep a ball from
reaching you.</p>
</footer>
</main>
</body>'''
    return page(title, desc, body, '/', base_url)


# ============================================================
# Build
# ============================================================

def write(path: str, text: str) -> int:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    return len(text.encode('utf-8'))


def build(out_dir: str, base_url: str, sims: int, refresh: bool = False,
          no_model: bool = False, cache_path: str = CACHE) -> list[dict]:
    if no_model and not os.path.exists(cache_path):
        raise SystemExit('--no-model needs a cache; run once without it first.')
    if no_model:
        print('Using the cached model run as-is.')
        with open(cache_path, encoding='utf-8') as fh:
            stats = json.load(fh)
        missing = set(STADIUMS) - set(stats)
        if missing:
            raise SystemExit(f'cache is missing {sorted(missing)}')
    else:
        print('Model run:')
        stats = load_stats(refresh=refresh, sims=sims, cache_path=cache_path)

    parks = [build_park(k, stats) for k in STADIUMS]

    total = 0
    for p in parks:
        total += write(os.path.join(out_dir, p['slug'], 'index.html'),
                       park_page(p, base_url))
    total += write(os.path.join(out_dir, 'index.html'),
                   home_page(parks, base_url))

    if base_url:
        urls = ''.join(
            f'<url><loc>{e(base_url)}/{e(p["slug"])}/</loc></url>'
            for p in sorted(parks, key=lambda x: x['name']))
        total += write(os.path.join(out_dir, 'sitemap.xml'),
                       '<?xml version="1.0" encoding="UTF-8"?>\n'
                       '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                       f'<url><loc>{e(base_url)}/</loc></url>{urls}</urlset>\n')

    print(f'\n{len(parks) + 1} pages, {total / 1024:.0f} KB total, '
          f'{total / (len(parks) + 1) / 1024:.1f} KB average.')
    if not base_url:
        print('No --base-url given: canonical tags and sitemap.xml were '
              'skipped. webapp_v2 serves a sitemap off the live host instead.')
    return parks


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', default=OUT_DIR)
    ap.add_argument('--base-url', default=os.environ.get('FOULCAST_SITE_URL', ''),
                    help='absolute site root, e.g. https://foulcast.example')
    ap.add_argument('--sims', type=int, default=SIMS)
    ap.add_argument('--refresh', action='store_true',
                    help='re-run the model even if the cache is current')
    ap.add_argument('--no-model', action='store_true',
                    help='render copy from the cache without simulating')
    args = ap.parse_args()

    build(args.out, args.base_url.rstrip('/'), args.sims,
          args.refresh, args.no_model)


if __name__ == '__main__':
    main()
