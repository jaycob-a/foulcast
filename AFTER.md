# AFTER — Yankee Stadium foul-ball prediction (post P1 fix)

Same configuration as BEFORE.md, regenerated after the section-matching rewrite
(trajectory landing-point intersection, non-overlapping zone partition,
nearest-surface assignment).

## Run configuration (identical to BEFORE.md)

- **Stadium:** Yankee Stadium (`yankee_stadium`)
- **Lineup:** built-in `YANKEES_2024_PROFILES` standard 9-batter lineup (Judge, Soto, Volpe, Stanton, Chisholm Jr., Wells, Rizzo, Torres, Verdugo)
- **Opposing pitcher:** Standard RHP, league-average pitch mix (FF .30 / SL .20 / CH .15 / SI .15 / CU .10 / FC .10)
- **Simulations per batter:** 400
- **RNG seed:** 42 (reproducible — the simulated trajectories are bit-identical to BEFORE.md; only section assignment changed)
- **Total expected fouls reaching stands:** ~16.6 (was ~7.6 — fewer balls now vanish unmatched; full 30–40 calibration is Step 3)

## Top 10 sections by expected foul count

| Rank | Section | Side | Level | Expected fouls | Catchable fouls | BEFORE rank |
|-----:|---------|------|-------|---------------:|----------------:|------------:|
| 1 | 3B Lower Reserve (Sec 229-234) (`3B-LR`) | 3rd Base side | lower | 2.03 | 2.03 | 7 |
| 2 | 1B Dugout Box (Sec 109-114) (`1B-DUG`) | 1st Base side | field | 1.93 | 1.93 | 3 |
| 3 | 1B Lower Reserve (Sec 205-210) (`1B-LR`) | 1st Base side | lower | 1.91 | 1.90 | 9 |
| 4 | 3B Dugout Box (Sec 126-131) (`3B-DUG`) | 3rd Base side | field | 1.90 | 1.90 | 2 |
| 5 | 1B Main Level (Sec 211-217) (`1B-LB1`) | 1st Base side | lower | 1.82 | 1.82 | 8 |
| 6 | 1B Field MVP (Sec 115-118) (`1B-FB1`) | 1st Base side | field | 1.52 | 1.52 | 5 |
| 7 | 3B Field MVP (Sec 122-125) (`3B-FB1`) | 3rd Base side | field | 1.51 | 1.51 | 6 |
| 8 | 3B Main Level (Sec 223-228) (`3B-LB1`) | 3rd Base side | lower | 1.47 | 1.47 | 10 |
| 9 | 3B Upper (Sec 324-331) (`3B-UB`) | 3rd Base side | upper | 0.95 | 0.92 | 4 |
| 10 | 1B Upper (Sec 307-316) (`1B-UB`) | 1st Base side | upper | 0.87 | 0.83 | **1** |

Remaining sections: HOME-B 0.24, HOME-F 0.24, HOME-G 0.20, HOME-U 0.05,
1B-UR 0.00, 3B-UR 0.00 (the 400-level grandstand down the lines is fully
shadowed by the decks in front of it).

## Expected fouls by side (all sections)

- **1st Base side:** 8.05 (was 3.82)
- **3rd Base side:** 7.85 (was 3.59)
- **Behind home plate:** 0.74 (was 0.21)

## What changed vs BEFORE

- The upper decks were ranked #1 and #4 (`1B-UB` 1.01, `3B-UB` 0.97); they are
  now #9–10 at ~0.9, fed only by genuinely high, deep fouls that come down
  where no lower deck extends. The inversion described in AUDIT.md P1 is gone.
- All eight lower-bowl 1B/3B sections now rank above every upper-deck section.
- Unmatched ("vanished") events dropped from 2,363/3,350 to 1,202/3,350; most
  of the remainder are short fouls that legitimately come down in foul ground
  (d < 60 ft) — relevant to the Step 3 calibration work.

## Known limitation

The behind-home group (0.74 total) still trails the two 300-level sections
(~0.9 each) because the spray model produces **zero** balls in the
straight-back wedge (angle > 90° never occurs in simulation). Real games send
a large share of fouls straight back. That is a trajectory/spray issue, not a
section-matching issue, and is left for the calibration steps; the
plausibility tests document it and enforce behind-home dominance at the group
level in the meantime.
