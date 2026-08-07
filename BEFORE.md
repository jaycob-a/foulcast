# BEFORE — Yankee Stadium foul-ball prediction (baseline)

Snapshot of the current (pre-fix) model output, captured before any changes 
from the AUDIT.md work plan. Used as the before/after comparison point for the 
P1 section-matching fix.

## Run configuration

- **Stadium:** Yankee Stadium (`yankee_stadium`)
- **Lineup:** built-in `YANKEES_2024_PROFILES` standard 9-batter lineup (Judge, Soto, Volpe, Stanton, Chisholm Jr., Wells, Rizzo, Torres, Verdugo)
- **Opposing pitcher:** Standard RHP, league-average pitch mix (FF .30 / SL .20 / CH .15 / SI .15 / CU .10 / FC .10)
- **Simulations per batter:** 400
- **RNG seed:** 42 (reproducible)
- **Total expected fouls reaching stands (all 15 sections):** ~7.6

## Top 10 sections by expected foul count

| Rank | Section | Side | Level | Expected fouls | Catchable fouls |
|-----:|---------|------|-------|---------------:|----------------:|
| 1 | 1B Upper (Sec 307-316) (`1B-UB`) | 1st Base side | upper | 1.01 | 1.01 |
| 2 | 3B Dugout Box (Sec 126-131) (`3B-DUG`) | 3rd Base side | field | 0.99 | 0.99 |
| 3 | 1B Dugout Box (Sec 109-114) (`1B-DUG`) | 1st Base side | field | 0.98 | 0.98 |
| 4 | 3B Upper (Sec 324-331) (`3B-UB`) | 3rd Base side | upper | 0.97 | 0.97 |
| 5 | 1B Field MVP (Sec 115-118) (`1B-FB1`) | 1st Base side | field | 0.67 | 0.67 |
| 6 | 3B Field MVP (Sec 122-125) (`3B-FB1`) | 3rd Base side | field | 0.62 | 0.62 |
| 7 | 3B Lower Reserve (Sec 229-234) (`3B-LR`) | 3rd Base side | lower | 0.51 | 0.51 |
| 8 | 1B Main Level (Sec 211-217) (`1B-LB1`) | 1st Base side | lower | 0.51 | 0.51 |
| 9 | 1B Lower Reserve (Sec 205-210) (`1B-LR`) | 1st Base side | lower | 0.49 | 0.49 |
| 10 | 3B Main Level (Sec 223-228) (`3B-LB1`) | 3rd Base side | lower | 0.33 | 0.33 |

## Expected fouls by side (all sections)

- **1st Base side:** 3.82
- **3rd Base side:** 3.59
- **Behind home plate:** 0.21

> Note: per AUDIT.md P1, the current section-matching logic is physically inverted (upper decks over-weighted) and P2 notes absolute counts run ~4x low. These numbers are the baseline to be corrected, not ground truth.
