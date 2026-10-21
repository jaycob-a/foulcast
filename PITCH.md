# FoulCast — what it is, and what it is not yet

*Rewritten 2026-10-20 (Step 26). The previous version of this document opened
with figures nobody had sourced and carried a "validation" table that validated
nothing a buyer would care about. `LIMITATIONS.md` lists what was wrong with it.
Everything below is either sourced, or stated as the estimate it is.*

## What exists today

A public reference site of 31 ballpark pages — the 30 clubs' home parks, with
the Athletics at Sutter Health Park, plus Las Vegas Ballpark — and one page
explaining how they were made. It is static HTML, served by a small Flask app
(`webapp_v2.py`) that answers on five URLs and nothing else.

Each ballpark page has:

- **The club's own statement of where its protective netting runs**, quoted
  word for word, with a link to the club's page. 25 clubs say where their
  netting runs; one club's page says two things that cannot both be true, and
  both are quoted; at the other five nothing the club publishes says.
- **A plan-view drawing and a table** showing, area by area, where a physics
  model puts foul balls — as four bands (most, more, fewer, fewest) against the
  busiest area at that park, not as figures. The figures are one click down.
- **The park's published measurements** — foul-territory area and backstop
  distance — with every disagreement between sources stated.
- **What the park's own seating map says about the model's seat labels.**

## What is sourced

- **Netting statements**, from the clubs' own pages, read on 2026-08-09 and
  again for the quotations on 2026-10-20. Recorded in `SOURCED_DATA.md` Part 2
  and 2b.
- **Foul-territory area (29 parks) and backstop distance (30 parks)**, from
  Andrew Clem's stadium statistics, cross-checked against the Seamheads
  ballpark database. Clem's areas are his own estimates off his own diagrams,
  good to about a thousand square feet.
- **The largest public record of where foul balls land**: FiveThirtyEight's
  906 fouls, one day at each of ten parks in 2019, placed into broad zones by
  eye. It is cited, not used: it is too coarse to test a seat-level model.

## What is modelled, and has never been checked

**No foul ball has ever been compared with this model, at any park.** There is
no public dataset of where foul balls land seat by seat, so there is nothing to
compare with. Every number the model produces is an estimate, and the site says
so on every page.

What the estimate rests on, all of it unverified:

- **One bowl shape for every park.** Nobody publishes the angle of a seating
  section off the foul line or the height of a deck, for any ballpark. The two
  published measurements stretch and place one template; they do not shape it.
  Every park is an exact left-right mirror.
- **A tuned constant decides the headline result.** The rate of balls hit
  straight back over the catcher was set so that a game looks plausible, and it
  is why the seats behind home plate come out busiest at every park.
- **Hand-typed batters.** The site simulates 18 batters from two 2024 lineups,
  typed into the code and not regenerated from data. Pull tendency is left at
  the default for all of them. A computed set of per-batter profiles from
  2025–26 Statcast exists in the repository and is not used by the site.
- **Hand-set spray and contact rules** — spray angle, side, pitch-type effects
  and the speed lost on a backward foul are constants chosen by the author.
- **Seat labels that are mostly wrong.** Thirty parks' own seating maps have
  been read against the model's section tables, and 27 disagree: foul lines
  reversed or crossed, the area called "behind home plate" up one of the lines,
  sections that do not exist. None of it has been corrected in the model. The
  site prints no model section number, and at those 27 parks says, under the
  table, that the areas may be mislabelled.
- **A third or more of the simulated fouls are dropped** at every park — 35% to
  60% — because they land where the template has no seats.
- **The parks barely differ.** The model puts the same number of fouls into
  every game at every park, and 27 of the 31 parks put between 30 and 33 of
  them into seats. What difference there is comes mostly from the shared
  template.

## What it is not

- **It is not a seat recommender.** It names no best section and no side to sit
  on, because it cannot support one.
- **It is not validated.** The ball-flight physics has been compared with one
  thing: Statcast's own computed distance for the same batted balls. Both
  numbers are calculated from the same two inputs, so agreement between them
  says the drag model is consistent, not that any ball reaches any seat.

## What it would take to become a product

In order:

1. **A record of where foul balls actually land, seat by seat.** The site's
   foul-ball log was built to collect one — an observer at a game records where
   each foul comes down — and is shelved with nothing collected; the season it
   was built for ended on 2026-09-27. A season of observations at even a few
   parks would be the first test this model has ever had. Until it exists there
   is nothing to tell a buyer about how often the model is right.
2. **Corrected seat labels** at the 27 parks whose own maps disagree with the
   model.
3. **Surveyed seat geometry** — section angles and deck heights. No public
   source has them; this means a licensing conversation with MLB or the clubs,
   or measurement in the field.
4. **Batter inputs regenerated from data**, starting with the computed profiles
   already in the repository.

Any commercial use before step 1 — a "foul ball score" on a ticket listing, a
"best seats for a souvenir" filter — would be selling a claim this project has
no evidence for.

## Technical

- Python and NumPy: the model is in `foulball/`, the site is generated by
  `site_build.py`, `site_diagram.py` and `site_data.py`.
- No JavaScript, images or external requests on any page.
- The test suite guards against regressions and against overclaiming on the
  site. Not one test compares the model with a real foul ball, because there is
  nothing to compare it with.
