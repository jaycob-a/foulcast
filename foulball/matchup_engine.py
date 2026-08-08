"""
Matchup Prediction Engine.

Given a lineup (list of batters) and an opposing pitcher,
predicts the expected foul ball distribution for the game.
Combines batter foul profiles with pitcher pitch mix tendencies.
"""
import numpy as np
from dataclasses import dataclass, field
from .batter_profiles import BatterFoulProfile
from .trajectory import simulate_foul_ball, TrajectoryResult
from .stadium import Stadium, SeatSection, find_landing_section
from .log import get_logger, _warn_once
from .validators import validate_trajectory, validate_sample, validate_monte_carlo_completeness, validate_side_consistency

logger = get_logger(__name__)


@dataclass
class FoulBallEvent:
    """A single simulated foul ball event."""
    batter_name: str
    batter_side: str
    pitch_type: str
    exit_velocity: float
    launch_angle: float
    trajectory: TrajectoryResult
    landing_side: str          # '1B' or '3B'
    section: SeatSection | None
    landing_distance: float
    landing_height: float
    is_catchable: bool         # did it land in the seats (not too high/far)?
    weight: float = 1.0        # per-batter foul rate scaling


@dataclass
class SectionPrediction:
    """Prediction for a specific stadium section."""
    section: SeatSection
    expected_fouls: float      # expected number of foul balls landing here
    pct_of_total: float        # percentage of all fouls
    catchable_fouls: float     # fouls a fan could realistically catch
    danger_rating: float       # 0-10 scale of how fast balls come in
    top_batters: list[str]     # batters most likely to foul here
    avg_exit_velocity: float
    # 90% confidence intervals (5th–95th percentile from per-batter bootstrap)
    pct_ci_low: float = 0.0   # 5th percentile of pct_of_total
    pct_ci_high: float = 0.0  # 95th percentile of pct_of_total


@dataclass
class GamePrediction:
    """Full game foul ball prediction."""
    home_team: str
    away_team: str
    stadium_name: str
    pitcher_name: str
    total_simulated_fouls: int
    section_predictions: list[SectionPrediction]
    all_events: list[FoulBallEvent]
    top_sections: list[SectionPrediction]  # sorted by catchable fouls
    # Per-batter section weights for combined bootstrap CI
    batter_section_counts: dict[str, dict[str, float]] = field(default_factory=dict)


def predict_game_fouls(
    lineup: list[BatterFoulProfile],
    pitcher_name: str,
    pitcher_pitch_mix: dict[str, float],
    stadium: Stadium,
    simulations_per_batter: int = 300,
    plate_appearances_per_batter: float = 4.0,
) -> GamePrediction:
    """
    Simulate one lineup's worth of foul balls.

    This is HALF A GAME. It takes a single lineup, so its expected_fouls totals
    cover one team's plate appearances. Anything compared against a real-world
    per-game figure (~30-40 fouls into the stands) has to sum both halves, the
    way webapp_v2 does. Reading one call's total as a game total is a 2x error,
    and was part of what AUDIT.md P2 recorded as a 4x shortfall.

    Args:
        lineup: List of 9 BatterFoulProfile objects
        pitcher_name: Name of opposing pitcher
        pitcher_pitch_mix: Dict of pitch_type -> frequency (should sum to ~1.0)
        stadium: Stadium geometry
        simulations_per_batter: Monte Carlo simulations per batter
        plate_appearances_per_batter: Average PAs per batter per game
    """
    all_events: list[FoulBallEvent] = []
    section_hits: dict[str, list[FoulBallEvent]] = {}
    # Per-batter section counts for bootstrap CI
    batter_section_counts: dict[str, dict[str, float]] = {}
    failed_sims = 0
    skipped_short = 0
    skipped_invalid = 0
    failed_examples: list[str] = []  # first few exception details for debugging

    # League-average foul rates by pitch type (fallback when batter has no data).
    PITCH_FOUL_RATES = {
        'FF': 0.17, 'SI': 0.16, 'FC': 0.18, 'SL': 0.22, 'CU': 0.20,
        'CH': 0.19, 'ST': 0.21, 'FS': 0.20, 'KC': 0.20, 'SV': 0.21,
    }

    # Guard against empty pitch mix (would crash np.random.choice)
    if not pitcher_pitch_mix:
        pitcher_pitch_mix = {'FF': 0.30, 'SL': 0.20, 'CH': 0.15, 'SI': 0.15, 'CU': 0.10, 'FC': 0.10}

    # Pitcher pitch mix (shared across batters)
    pitch_types = list(pitcher_pitch_mix.keys())
    pitch_weights = np.array([pitcher_pitch_mix.get(pt, 0) for pt in pitch_types])

    # League-average fallback weights
    league_foul_rates = np.array([PITCH_FOUL_RATES.get(pt, 0.18) for pt in pitch_types])
    league_combined = pitch_weights * league_foul_rates
    if league_combined.sum() > 0:
        league_combined /= league_combined.sum()
    else:
        league_combined = np.ones(len(pitch_types)) / len(pitch_types)

    # Pre-compute section lookup acceleration: group by side
    sections_by_side: dict[str, list[SeatSection]] = {'1B': [], '3B': [], 'HOME': []}
    for sec in stadium.sections:
        if sec.side in sections_by_side:
            sections_by_side[sec.side].append(sec)

    for batter in lineup:
        batter_key = batter.player_name
        batter_section_counts[batter_key] = {}

        # Guard degenerate profile fields — use local copies to avoid mutating
        # the caller's BatterFoulProfile objects across multiple runs.
        ev_std = batter.ev_std
        la_std = batter.la_std
        if ev_std <= 0:
            _warn_once(logger, f"ev_std_{batter.player_name}",
                       f"{batter.player_name}: ev_std={ev_std}, using default 13.0")
            ev_std = 13.0
        if la_std <= 0:
            _warn_once(logger, f"la_std_{batter.player_name}",
                       f"{batter.player_name}: la_std={la_std}, using default 36.0")
            la_std = 36.0

        # Per-batter pitch type weighting: combine pitcher's pitch mix with
        # this batter's per-pitch-type foul tendency (from real Statcast data).
        if batter.foul_rates:
            if batter.foul_rates_kind == 'p_foul_given_pitch':
                # True conditional P(foul|pitch): weight = P(pitch) * P(foul|pitch)
                batter_foul_tendency = np.array([
                    batter.foul_rates.get(pt, PITCH_FOUL_RATES.get(pt, 0.18))
                    for pt in pitch_types
                ])
                batter_combined = pitch_weights * batter_foul_tendency
            else:
                # Fallback P(pitch|foul): this distribution already reflects the
                # pitch environment the batter faced. Using it directly avoids
                # double-counting the pitcher mix. For pitch types not in the
                # batter's foul data, fall back to the pitcher's mix share.
                batter_share = np.array([
                    batter.foul_rates.get(pt, pitch_weights[i])
                    for i, pt in enumerate(pitch_types)
                ])
                batter_combined = batter_share
            if batter_combined.sum() > 0:
                batter_combined /= batter_combined.sum()
            else:
                batter_combined = league_combined
        else:
            batter_combined = league_combined

        # Per-batter fouls/PA from real Statcast data (foul events / plate appearances).
        # Falls back to league average 0.80 if not computed yet.
        fouls_per_pa = batter.fouls_per_pa if batter.fouls_per_pa > 0 else 0.80

        # Per-batter weight: how many real fouls this batter's sims represent
        batter_weight = fouls_per_pa * plate_appearances_per_batter / simulations_per_batter

        # Pre-draw all pitch types and plate_x values for this batter (vectorized)
        all_pitch_types = np.random.choice(pitch_types, size=simulations_per_batter, p=batter_combined)
        all_plate_x = batter.avg_plate_x_on_foul + np.random.normal(0, 0.3, size=simulations_per_batter)

        for sim_idx in range(simulations_per_batter):
            pitch_type = all_pitch_types[sim_idx]
            plate_x = all_plate_x[sim_idx]

            # Sample foul ball characteristics from batter's distribution
            sample = batter.sample_foul(plate_x=plate_x,
                                        ev_std_override=ev_std if ev_std != batter.ev_std else None,
                                        la_std_override=la_std if la_std != batter.la_std else None)

            # Validate sample
            sample_violations = validate_sample(sample)
            if sample_violations:
                skipped_invalid += 1
                continue

            # Simulate trajectory with per-batter pull tendency
            try:
                traj, _ = simulate_foul_ball(
                    exit_velocity_mph=sample['exit_velocity'],
                    launch_angle_deg=sample['launch_angle'],
                    batter_side=sample['batter_side'],
                    pitch_location_x=sample['pitch_location_x'],
                    altitude_ft=stadium.altitude_ft,
                    temperature_f=stadium.avg_temperature_f,
                    pitch_type=pitch_type,
                    fair_pull_pct=sample['fair_pull_pct'],
                )
            except Exception as exc:
                failed_sims += 1
                if len(failed_examples) < 3:
                    failed_examples.append(
                        f"{batter.player_name}/{pitch_type}: {type(exc).__name__}: {exc}"
                    )
                continue

            # Guard empty trajectory
            if len(traj.positions) == 0:
                failed_sims += 1
                continue

            # Validate trajectory invariants
            traj_violations = validate_trajectory(traj)
            if traj_violations:
                skipped_invalid += 1
                continue

            # Derive side from trajectory geometry: the y-axis is signed
            # so that y > 0 = 1B side, y < 0 = 3B side.
            side = '1B' if traj.landing_y >= 0 else '3B'

            # Validate side consistency
            side_violations = validate_side_consistency(traj.landing_y, side)
            if side_violations:
                skipped_invalid += 1
                continue

            # Map to stadium section
            distance = traj.landing_distance
            if distance < 5:
                skipped_short += 1
                continue  # ball didn't go anywhere meaningful

            # Angle from foul line (0 = along foul line toward outfield, 90 = behind plate)
            # When landing_x < 0 the ball drifted behind home plate; angle should exceed 90.
            lx = traj.landing_x
            ly = abs(traj.landing_y)
            if lx >= 0:
                angle = np.degrees(np.arctan2(ly, lx))
            else:
                # Ball behind plate: 90 + arctan(|x| / |y|) gives 90-180 range
                angle = 90.0 + np.degrees(np.arctan2(-lx, max(ly, 0.01)))

            # Assign the section whose exposed deck surface the trajectory
            # actually comes down on. Search only matching-side + HOME sections.
            horiz_dists = np.sqrt(traj.positions[:, 0]**2 + traj.positions[:, 1]**2)
            candidates = sections_by_side.get(side, []) + sections_by_side.get('HOME', [])
            section = find_landing_section(candidates, angle, horiz_dists,
                                           traj.positions[:, 2])

            # Is it catchable? (reasonable speed and in the stands)
            is_catchable = (
                section is not None and
                traj.landing_speed < 95 and  # not a missile
                distance > 15 and
                distance < 350
            )

            event = FoulBallEvent(
                batter_name=batter.player_name,
                batter_side=batter.batter_side,
                pitch_type=pitch_type,
                # The speed the ball actually came off the bat at, which is
                # below the sampled value for fouls deflected backward.
                exit_velocity=traj.exit_velocity,
                launch_angle=sample['launch_angle'],
                trajectory=traj,
                landing_side=side,
                section=section,
                landing_distance=distance,
                landing_height=traj.landing_z,
                is_catchable=is_catchable,
                weight=batter_weight,
            )
            all_events.append(event)

            if section:
                sid = section.section_id
                if sid not in section_hits:
                    section_hits[sid] = []
                section_hits[sid].append(event)
                # Track per-batter section counts for CI
                batter_section_counts[batter_key][sid] = (
                    batter_section_counts[batter_key].get(sid, 0) + batter_weight
                )

    total_attempted = simulations_per_batter * len(lineup)
    if failed_sims > 0:
        logger.warning("%d/%d simulations failed (%.1f%%)",
                       failed_sims, total_attempted, failed_sims / total_attempted * 100)
        for ex in failed_examples:
            logger.warning("  Example: %s", ex)
    if skipped_short > 0:
        logger.info("Skipped %d sims with distance < 5 ft", skipped_short)
    if skipped_invalid > 0:
        logger.warning("Skipped %d sims due to validation failures", skipped_invalid)

    # Monitor near-zero landing_y (could indicate spray angle clamping bug)
    if all_events:
        near_zero_y = sum(1 for e in all_events if abs(e.trajectory.landing_y) < 0.5)
        near_zero_pct = near_zero_y / len(all_events) * 100
        if near_zero_pct > 5.0:
            logger.warning(
                "%.1f%% of events have |landing_y| < 0.5 (%d/%d) — possible spray angle issue",
                near_zero_pct, near_zero_y, len(all_events),
            )

    # MC completeness check
    mc_violations = validate_monte_carlo_completeness(
        len(lineup), simulations_per_batter,
        len(all_events), failed_sims, skipped_short + skipped_invalid,
    )
    if mc_violations:
        for v in mc_violations:
            logger.error("MC completeness violation: %s", v)

    # Build section predictions
    total_events = len(all_events)

    # Use per-batter weights for expected foul counts
    # Only count events that could potentially match a section (not behind-plate fouls)
    # to avoid diluting section percentages below 100%
    total_weighted = sum(e.weight for e in all_events if e.section is not None) or 1

    # Bootstrap CI: resample batters 200 times, compute section % each time
    n_bootstrap = 200
    batter_keys = list(batter_section_counts.keys())
    all_section_ids = list(section_hits.keys())

    bootstrap_pcts: dict[str, list[float]] = {sid: [] for sid in all_section_ids}
    if batter_keys and all_section_ids:
        for _ in range(n_bootstrap):
            resampled = np.random.choice(batter_keys, size=len(batter_keys), replace=True)
            boot_totals: dict[str, float] = {}
            boot_grand = 0.0
            for bk in resampled:
                for sid, wt in batter_section_counts[bk].items():
                    boot_totals[sid] = boot_totals.get(sid, 0) + wt
                    boot_grand += wt
            if boot_grand > 0:
                for sid in all_section_ids:
                    bootstrap_pcts[sid].append(
                        boot_totals.get(sid, 0) / boot_grand * 100
                    )
            else:
                for sid in all_section_ids:
                    bootstrap_pcts[sid].append(0.0)

    section_predictions = []
    for section in stadium.sections:
        events = section_hits.get(section.section_id, [])
        if not events:
            continue

        # Weighted counts: each event scaled by its batter's foul rate
        weighted_fouls = sum(e.weight for e in events)
        weighted_catchable = sum(e.weight for e in events if e.is_catchable)

        evs = [e.exit_velocity for e in events]
        batter_counts: dict[str, float] = {}
        for e in events:
            batter_counts[e.batter_name] = batter_counts.get(e.batter_name, 0) + e.weight

        top_batters = sorted(batter_counts, key=batter_counts.get, reverse=True)[:3]
        avg_ev = np.mean(evs) if evs else 0

        # Danger rating: based on average EV of balls landing here
        danger = min(10, avg_ev / 10) if avg_ev > 0 else 0

        # Confidence interval from bootstrap
        pct_mean = weighted_fouls / total_weighted * 100 if total_weighted > 0 else 0
        sid = section.section_id
        if sid in bootstrap_pcts and bootstrap_pcts[sid]:
            ci_low = float(np.percentile(bootstrap_pcts[sid], 5))
            ci_high = float(np.percentile(bootstrap_pcts[sid], 95))
        else:
            ci_low = pct_mean
            ci_high = pct_mean

        pred = SectionPrediction(
            section=section,
            expected_fouls=weighted_fouls,
            pct_of_total=pct_mean,
            catchable_fouls=weighted_catchable,
            danger_rating=danger,
            top_batters=top_batters,
            avg_exit_velocity=avg_ev,
            pct_ci_low=ci_low,
            pct_ci_high=ci_high,
        )
        section_predictions.append(pred)

    # Sort by catchable fouls
    top_sections = sorted(section_predictions, key=lambda p: p.catchable_fouls, reverse=True)

    return GamePrediction(
        home_team=stadium.team,
        away_team='',  # filled by caller
        stadium_name=stadium.name,
        pitcher_name=pitcher_name,
        total_simulated_fouls=total_events,
        section_predictions=section_predictions,
        all_events=all_events,
        top_sections=top_sections,
        batter_section_counts=batter_section_counts,
    )


def bootstrap_combined_ci(
    predictions: list[GamePrediction],
    n_bootstrap: int = 200,
) -> dict[str, tuple[float, float]]:
    """Compute 90% bootstrap CI on section percentages across combined half-game predictions.

    Merges batter_section_counts from all predictions, resamples batters,
    and returns {section_id: (ci_low, ci_high)} as percentages.
    """
    # Merge all batter section counts, prefixing keys to avoid name collisions
    # across halves (e.g., same batter could appear in both if traded mid-season)
    combined: dict[str, dict[str, float]] = {}
    for i, pred in enumerate(predictions):
        for batter_key, sec_counts in pred.batter_section_counts.items():
            unique_key = f"{i}:{batter_key}"
            combined[unique_key] = sec_counts

    batter_keys = list(combined.keys())
    if not batter_keys:
        return {}

    all_sids: set[str] = set()
    for sec_counts in combined.values():
        all_sids.update(sec_counts.keys())

    sid_list = sorted(all_sids)
    boot_pcts: dict[str, list[float]] = {sid: [] for sid in sid_list}

    for _ in range(n_bootstrap):
        resampled = np.random.choice(batter_keys, size=len(batter_keys), replace=True)
        boot_totals: dict[str, float] = {}
        boot_grand = 0.0
        for bk in resampled:
            for sid, wt in combined[bk].items():
                boot_totals[sid] = boot_totals.get(sid, 0) + wt
                boot_grand += wt
        if boot_grand > 0:
            for sid in sid_list:
                boot_pcts[sid].append(boot_totals.get(sid, 0) / boot_grand * 100)
        else:
            for sid in sid_list:
                boot_pcts[sid].append(0.0)

    result = {}
    for sid in sid_list:
        if boot_pcts[sid]:
            result[sid] = (
                float(np.percentile(boot_pcts[sid], 5)),
                float(np.percentile(boot_pcts[sid], 95)),
            )
        else:
            result[sid] = (0.0, 0.0)
    return result
