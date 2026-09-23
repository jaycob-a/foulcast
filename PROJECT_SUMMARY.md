# FoulCast, in plain English

*Written 2026-09-08, updated 2026-09-22, for a reader who does not work on this code.*

---

## What it is

FoulCast is a website with 33 pages: one for each of 31 ballparks, a home
page, and one page that explains how the rest work. Each ballpark page answers
two questions about that ballpark:

1. **What does the club say about the protective netting** in front of a given
   block of seats?
2. **Roughly how many foul balls a game come down** in that block of seats?

The first answer is copied from what the club itself publishes. The second is
a guess produced by a physics simulation. The site is built so a visitor can
always tell which of the two they are looking at, and what the club says about
the netting always comes ahead of what the model guesses, because it is the
part that is sourced.

The site is built around its drawings, and the words on it are rationed.
The home page is a gallery: one headline, one sentence, and a grid of all 31
ballparks, each tile the park's own drawing, small, with its name and its
team. A ballpark page is the drawing, large, directly under the park's name
and team; then one plain sentence saying where the netting runs — "netting
covers the seats at field level behind home plate and runs out along both foul
lines past the dugouts"; then the table of figures, each row of it three
things and no more — which seating area, how many fouls a game, and what the
club says about netting in front of it, carried by a small coloured dot and
two or three lowercase words; then one line, "Model estimate, not observed
data", linking to the page that explains everything; then a one-line footer
back to the 31. That is the whole visible page, and a test holds it to sixty
words (forty on the home page), not counting the table and the drawing's own
labels.

Everything else about a ballpark — where the netting statement came from,
how the figures were produced, what the ballpark's own seating map says, the
two readings, the sourced figures — is behind one closed "Details" heading at
the foot of its page. Everything general — what is sourced and what is a
guess, whose the netting gaps are, why most pages will not name a foul line,
why no section number is printed, how to read the drawing, what the model
cannot do, the never-validated caveat in full — is on the "How this works"
page, once. None of it has been removed; none of it stands in front of the
answer.

There is no login, no ticket search, no live game data. It is 33 pages of
plain text, one drawing apiece, and a little styling — no images, no scripts.
A page loads in one request and works on a phone.

The drawing is a schematic plan of the ballpark's foul ground: home plate at
the bottom, the two foul lines running out, and the seating areas as segments
of an arc behind them, shaded in five steps by how busy the model thinks each
one is. Every park is drawn in the same feet, so on the home page — the one
place all 31 are side by side — a park with more foul ground really does draw
larger. A ballpark's own page compares it with nothing, so there the same
drawing is cropped to that ballpark and fills its frame. It is drawn as
geometry inside the
page rather than as a picture file, so it costs no extra request, scales to
any screen, and can be read aloud.

---

## What it knows

### It knows what the clubs published on one day

Every club's own netting or seating page was opened in a browser on
**9 August 2026** and read. That date is printed on every page, and each
ballpark page links to the exact club page it was read from. Nothing is
scraped on a schedule; if a club moves its netting next spring, this site will
not notice until somebody re-reads the pages.

### It knows two measurements of each ballpark

Two published numbers do the real work of placing seats in the model:

- **Foul territory area** — how much ground lies in foul ground. Published for
  **29 of the 31** ballparks.
- **Backstop distance** — how far the fence behind home plate sits from the
  plate. Published for **30 of the 31**.

Both come from Andrew Clem's stadium statistics pages, cross-checked against
the Seamheads ballpark database. Where the two sources disagree — and on
backstop distance they disagree at 12 ballparks, by as much as 14 feet — the
disagreement is printed on the page rather than hidden. A third figure, how
much of each deck sits under cover, is published for 27 ballparks.

Where a figure does not exist, the page says **"Not published"** instead of
quietly filling in an average.

### It knows what the simulation produced

Each page's distribution comes from one simulated game: the same 18 batters,
the same pitcher, the same random seed, at every ballpark — so the only thing
that changes from page to page is the ballpark itself. Four hundred simulated
swings per batter. The result is stated as foul balls per game reaching each
seating area, largest first.

### It knows where its own seat labels are wrong

This is the most unusual thing about the project, and worth understanding.

The model carries a printed seat-section label for every area it tracks —
"sections 109 to 114", that sort of thing. Somebody eventually checked those
labels against the ballparks' own published seating maps. **Thirty maps were
read. Twenty-seven of them disagreed with the model.** Some had the two foul
lines the wrong way round. Some put the "seats behind home plate" somewhere
else entirely. Some named whole decks that are not in the building.

None of that has been fixed in the model. What was done instead was to stop
the site from printing anything that depends on it:

- **No seat or section number appears anywhere on the site.** Areas are
  described by where they are — "the lower bowl behind home plate", "the dugout
  boxes down the first-base line" — never by number.
- **At 15 of the 31 ballparks the site will not say which foul line is which.**
  Every ballpark in the model is a perfect left-right mirror, so a ballpark
  written down backwards produces figures identical to one written down
  correctly. One ballpark — Oriole Park — really was backwards, and every
  automated check in the project passed it for a whole development cycle. So
  unless an outside source names a side next to specific seats, the two foul
  lines are shown folded into a single row. Sixteen ballparks clear that bar;
  fifteen do not.
- **Every page states its own position on this**, including the pages that have
  to say nothing has ever been tested.

The three ballparks whose maps *agreed* are shown in green and told so, in the
same place and at the same length, because an agreement nobody publishes reads
as an absence of evidence.

---

## What it does not know

### Whether any of the foul-ball numbers are right

**The model has never been compared with a real foul ball.** Not once, not
anywhere. There is no public record of where foul balls actually land — the
league's tracking system logs that a foul happened, not where it came down.
The largest hand-collected set anybody has published is FiveThirtyEight's 906
fouls, taken from one game at each of ten parks in 2019 and placed by eye, off
camera footage, into broad zones rather than seating areas. The site links that
dataset; `SOURCED_DATA.md` Part 3 records what it is and what it is not.

So the site puts no percentage on how often it is right, because there is
nothing to compute one from. Every page says this at the top and again at the
bottom. No page claims accuracy of any kind, and the word "safe" — in any
form, including "safety" and "safer" — appears nowhere on the site. Netting is
described as netting, and risk as higher or lower, never as absent.

### Where roughly a third of the fouls go

Between **35% and 60%** of the fouls the model produces at a given ballpark
land somewhere it has no seating area to put them: deep down the lines near the
foul poles, in the gap between home plate and the front row, or underneath a
covered deck. Those balls are counted in the ballpark's total and then dropped.
The share is printed on every page. It is why the figures should be read as a
shape — which areas get more than which — rather than as a count.

### The shape of any actual ballpark

Nobody publishes the angle of a seating section off the foul line, or how high
a deck sits, for any ballpark. So every ballpark in the model shares one
generic bowl, stretched and positioned by its own two published measurements.
Every ballpark is modelled as an exact left-right mirror, which is certainly
wrong — one ballpark has a published statement that its foul ground is
lopsided, and nobody has measured the rest.

### What the netting covers at most ballparks

Only **7 of the 31** ballparks have netting information the model can actually
attach to specific seats. At the other 24 it is a gap, and the site splits
those gaps into two honest groups:

- **8 ballparks** where nothing usable is published at all.
- **16 ballparks** where the club publishes perfectly good netting information
  and *this project's own seat labels cannot be reconciled with it.*

The larger group is the project's own fault, and the "How this works" page
says so in those words rather than leaving the reader to think 16 clubs were
negligent.

Even at the 7 that do match, "behind netting" is not "protected". The clubs'
own wording, quoted on the pages, is that fans behind netting "are still
exposed to objects leaving the field of play".

---

## How much you should trust it

A fair summary for a visitor:

- **The netting facts are as good as the club's own page was on 9 August 2026**,
  and every one of them links back to it.
- **The two ballpark measurements are as good as one estimator's published
  figures** — Clem estimates foul territory from his own scale drawings and
  says so. Good to roughly ±1,000 square feet, not to the ±100 the printed
  number implies.
- **The foul-ball distribution is an unvalidated physics estimate**, built on a
  generic bowl shape, with a third or more of its output discarded, attached in
  most cases to seat groupings the ballpark's own map contradicts.

The site is built to make all three of those legible at a glance, and there are
2,230 automated tests whose main job is to stop a future change from quietly
making a claim the project cannot support.

---

## What is checked automatically, and what is not

Four rules are enforced by tests rather than by care, on every page, every
build:

1. No section or seat numbers, anywhere.
2. Netting appears above the model on every page — sourced before estimated.
3. The word "safe" never appears.
4. No accuracy claim ever appears, and the absence of validation is stated on
   every page.

A fifth rule was added after the Oriole Park reversal: no page names a foul
line at a ballpark where nothing establishes which line is which.

A sixth was added on 8 September 2026, after the published pages were found
sitting five rounds of changes behind the code that generates them, showing
visitors stale counts with nothing catching it:

6. The published pages have to match what the generator produces today, and
   the stored simulation they were rendered from has to have come out of the
   simulation code as it stands today.

The first half rebuilds every page from the stored run and fails if a single
committed page differs by so much as a character. The second half fingerprints
the files the simulation actually reads, so editing a ballpark's dimensions
now discards the stored run instead of silently reusing it. Rebuilding after a
change is still a human step. Noticing that nobody did it is not.

The drawing added on 8 September 2026 is checked the same way, because a
picture can make a claim quietly in a way a sentence cannot. Its shading has
to come from exactly the figures printed in the table underneath it; it may
not name a foul line at any of the fifteen ballparks whose sides are
unestablished; it marks netting in front of every area the table beneath it
calls behind netting and in front of nothing else, and where it marks nothing
it says so in words rather than leaving a blank arc to be read as an open one;
nothing it draws may fall outside the frame it is cropped to; and two
ballparks with different published foul territory may not produce the same
drawing.

One judgement in that group is worth stating rather than burying. The two foul
lines are shaded identically at every ballpark, including the sixteen that may
name their sides. The model builds every ballpark as an exact left-right
mirror, so the small difference between a ballpark's two foul-line rows is
simulation noise; the table prints both because it prints what the run
produced, but a *map* that shaded them differently would be asserting a
lopsidedness the model does not contain.

The netting mark is the one exception, and it was got wrong first. A netting
extent is not model output — it is a sentence a club published, and a club may
net further down one foul line than the other. Fenway does. The drawing
originally folded a ballpark's two foul lines into one for the netting mark as
well as for the shade, so Fenway's page listed its first-base dugout boxes as
behind netting in the table and drew no net there, which is a sourced fact
dropped to protect a rule that exists for an unsourced one. The mark now
follows the table, area by area, on both sides of the plate, and a test holds
the two lists equal at all 31 ballparks. At the fifteen ballparks whose sides
are unestablished the two lines are still a single row carrying a single
status, so both sides are marked or neither is and no side can leak.
