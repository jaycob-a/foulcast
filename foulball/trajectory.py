"""
3D Ballistic Trajectory Model for Foul Balls.

Takes exit velocity, launch angle, and spray angle and simulates
the ball's flight path accounting for gravity and air drag.
Returns the full trajectory and landing position in stadium coordinates.
"""
import numpy as np
from dataclasses import dataclass
from .log import get_logger

logger = get_logger(__name__)


@dataclass
class TrajectoryResult:
    """Result of a trajectory simulation.

    Coordinate convention (when returned from simulate_foul_ball):
        - x: feet from home plate along foul line (positive = toward outfield)
        - y: feet perpendicular to foul line, SIGNED by side:
              positive = 1B side (right field foul territory)
              negative = 3B side (left field foul territory)
        - z: height in feet (positive = up)

    Side is encoded in the geometry: sign(landing_y) determines the side.
    """
    positions: np.ndarray       # Nx3 array of (x, y, z) positions in feet
    landing_x: float            # feet from home plate along foul line axis
    landing_y: float            # feet perpendicular to foul line (signed: +1B, -3B)
    landing_z: float            # height at landing (0 = ground level)
    landing_distance: float     # total distance from home plate
    max_height: float           # peak height of trajectory
    flight_time: float          # seconds in air
    landing_speed: float        # speed at landing (mph) — danger indicator
    # Speed the ball actually left the bat at in this simulation. For a foul
    # driven out in front this is the sampled exit velocity; for one deflected
    # backward it is the sampled value after the glancing-contact penalty in
    # oblique_contact_speed_factor(). Downstream code should report this rather
    # than the raw sample.
    exit_velocity: float = 0.0


# Physical constants
GRAVITY = 32.174                # ft/s^2
AIR_DENSITY_SEA_LEVEL = 0.0023769  # slugs/ft^3
BALL_MASS = 0.3125 / GRAVITY    # slugs (5.125 oz = 0.3125 lb; mass = weight/g)
BALL_CIRCUMFERENCE = 9.125      # inches
BALL_RADIUS = BALL_CIRCUMFERENCE / (2 * np.pi) / 12  # feet
BALL_CROSS_SECTION = np.pi * BALL_RADIUS ** 2  # ft^2
DRAG_COEFFICIENT = 0.35         # typical for baseball
MAGNUS_COEFFICIENT = 0.18       # lift coefficient per unit spin factor

# --- Straight-back fouls -------------------------------------------------
# Spray angle here is measured from the foul line of whichever side the ball
# went to. The two foul lines are 90 degrees apart, so each side owns 135
# degrees of foul territory: 0 is straight down the line, 90 is square to it
# (level with home plate), and 135 is dead behind the catcher, where the two
# sides meet. Anything past 90 has crossed behind the plane of home plate.
BEHIND_PLATE_ANGLE = 135.0

# Share of fouls that leave the bat travelling backward — foul tips, nicks off
# the edge of the bat, and swings late enough that the ball is deflected rather
# than driven. Statcast cannot supply this number: its `foul_tip` event only
# counts tips the catcher holds onto, while everything that flies back into the
# screen is logged as a plain `foul` with no direction. So this is a calibration
# constant, set from the requirement that a typical game puts 30-40 fouls in the
# stands with the seats behind the plate among the busiest. It is the single
# biggest unvalidated assumption in the model — see NOTES.md.
BACK_FOUL_BASE_RATE = 0.28


def _estimate_spin(exit_velocity_mph: float, launch_angle_deg: float) -> tuple[float, float, float]:
    """
    Estimate spin rate and axis from exit velocity and launch angle.

    Returns (spin_rate_rpm, backspin_fraction, sidespin_fraction).

    Based on simplified Nathan (2008) model:
    - Line drives (low LA, high EV): high backspin (~2000-2500 rpm)
    - High popups (high LA): moderate backspin (~1500-2000 rpm)
    - Ground-level fouls (negative LA): topspin
    - Weak contact: lower spin rates
    """
    la = launch_angle_deg

    # Base spin rate scales with exit velocity (harder contact = more spin)
    base_spin = 800 + exit_velocity_mph * 15  # ~1900 rpm at 75 mph

    # Launch angle modifies spin rate and type
    if la < -10:
        # Topspin grounders
        spin_rate = base_spin * 0.6
        backspin_frac = -0.8  # negative = topspin (pushes ball down)
        sidespin_frac = 0.2
    elif la < 15:
        # Low line drives: strong backspin
        spin_rate = base_spin * 1.0
        backspin_frac = 0.9
        sidespin_frac = 0.3
    elif la < 45:
        # Mid-angle: moderate backspin
        spin_rate = base_spin * 0.85
        backspin_frac = 0.7
        sidespin_frac = 0.2
    elif la < 70:
        # High popups: less effective spin
        spin_rate = base_spin * 0.6
        backspin_frac = 0.4
        sidespin_frac = 0.1
    else:
        # Near-vertical: minimal spin effect
        spin_rate = base_spin * 0.3
        backspin_frac = 0.1
        sidespin_frac = 0.05

    return spin_rate, backspin_frac, sidespin_frac


def simulate_trajectory(
    exit_velocity_mph: float,
    launch_angle_deg: float,
    spray_angle_deg: float,
    start_height_ft: float = 3.0,
    altitude_ft: float = 0,
    temperature_f: float = 72,
    dt: float = 0.005,
    max_time: float = 15.0,
) -> TrajectoryResult:
    """
    Simulate a foul ball trajectory in 3D.

    Coordinate system (looking from above, catcher's perspective):
        - x: along the foul line toward outfield (positive = away from plate)
        - y: perpendicular to foul line into the stands (positive = into stands)
        - z: vertical (positive = up)

    Args:
        exit_velocity_mph: Ball speed off the bat in mph
        launch_angle_deg: Vertical angle off the bat (-90 to 90)
        spray_angle_deg: Horizontal angle. 0 = straight down foul line,
                        positive = deeper into stands, negative = toward fair
                        territory. Past 90 the ball is travelling back behind
                        the plane of home plate (x goes negative); 135 is dead
                        behind the catcher. See BEHIND_PLATE_ANGLE.
        start_height_ft: Height of bat contact (typically ~3 feet)
        altitude_ft: Stadium altitude above sea level (affects air density)
        temperature_f: Temperature in Fahrenheit (affects air density)
        dt: Time step in seconds
        max_time: Maximum simulation time
    """
    # Adjust air density for altitude and temperature
    temp_k = (temperature_f - 32) * 5/9 + 273.15
    air_density = AIR_DENSITY_SEA_LEVEL * np.exp(-altitude_ft / 27000) * (293.15 / temp_k)

    # Drag factor: F_drag = 0.5 * Cd * rho * A * v^2
    drag_factor = 0.5 * DRAG_COEFFICIENT * air_density * BALL_CROSS_SECTION / BALL_MASS

    # Magnus (spin) factor: F_magnus = 0.5 * Cl * rho * A * v^2
    spin_rate, backspin_frac, sidespin_frac = _estimate_spin(exit_velocity_mph, launch_angle_deg)
    omega = spin_rate * 2 * np.pi / 60  # rpm to rad/s
    spin_factor = BALL_RADIUS * omega  # characteristic spin speed (ft/s)
    magnus_factor = 0.5 * MAGNUS_COEFFICIENT * air_density * BALL_CROSS_SECTION / BALL_MASS

    # Convert inputs
    ev = exit_velocity_mph * 5280 / 3600  # mph to ft/s
    la = np.radians(launch_angle_deg)
    sa = np.radians(spray_angle_deg)

    # Initial velocity components
    horizontal_speed = ev * np.cos(la)
    vx = horizontal_speed * np.cos(sa)  # along foul line
    vy = horizontal_speed * np.sin(sa)  # into stands
    vz = ev * np.sin(la)               # vertical

    # State
    x, y, z = 0.0, 0.0, start_height_ft
    positions = [(x, y, z)]
    t = 0.0

    while t < max_time:
        speed = np.sqrt(vx**2 + vy**2 + vz**2)
        if speed < 0.1:
            break

        # Drag acceleration (opposes velocity)
        drag = drag_factor * speed
        ax = -drag * vx
        ay = -drag * vy
        az = -drag * vz - GRAVITY

        # Magnus acceleration (perpendicular to velocity)
        # F_magnus = 0.5 * Cl * rho * A * v^2, where Cl ~ spin_factor/v
        # So a_magnus = magnus_factor * spin_factor * speed
        if speed > 1:
            mag_strength = magnus_factor * spin_factor * speed
            az += mag_strength * backspin_frac
            ay += mag_strength * sidespin_frac

        # Update velocity
        vx += ax * dt
        vy += ay * dt
        vz += az * dt

        # Update position
        x += vx * dt
        y += vy * dt
        z += vz * dt
        t += dt

        positions.append((x, y, z))

        # Stop if ball hits ground or a reasonable stand height
        if z < 0:
            # Interpolate to ground level
            prev = positions[-2]
            frac = prev[2] / (prev[2] - z) if prev[2] != z else 0
            x = prev[0] + frac * (x - prev[0])
            y = prev[1] + frac * (y - prev[1])
            z = 0
            positions[-1] = (x, y, z)
            # Interpolate velocity to the same contact moment
            # (pre-step velocities = current minus this step's delta)
            vx_prev = vx - ax * dt
            vy_prev = vy - ay * dt
            vz_prev = vz - az * dt
            vx = vx_prev + frac * (vx - vx_prev)
            vy = vy_prev + frac * (vy - vy_prev)
            vz = vz_prev + frac * (vz - vz_prev)
            break

    pos_array = np.array(positions)
    landing_speed_fps = np.sqrt(vx**2 + vy**2 + vz**2)

    return TrajectoryResult(
        positions=pos_array,
        landing_x=x,
        landing_y=y,
        landing_z=z,
        landing_distance=np.sqrt(x**2 + y**2),
        max_height=pos_array[:, 2].max(),
        flight_time=t,
        landing_speed=landing_speed_fps * 3600 / 5280,  # back to mph
        exit_velocity=exit_velocity_mph,
    )


def estimate_spray_angle(
    batter_side: str,
    pitch_location_x: float = 0.0,
    exit_velocity_mph: float = 75.0,
    launch_angle_deg: float = 30.0,
    pitch_type: str = 'FF',
) -> float:
    """
    Estimate the spray angle for a foul ball.

    Models how far "into the stands" a foul goes based on contact quality
    and pitch characteristics. Pull tendency is NOT handled here — it drives
    the side probability and per-side shift in simulate_foul_ball() instead,
    avoiding double-counting.

    Returns spray angle in degrees (0 = straight down foul line, positive = into stands).
    """
    # STEP 1: Base angle — typical foul ball spray
    base_angle = np.random.normal(27.0, 15.0)

    # STEP 2: Pitch location adjustment
    # Inside pitches → contact out front → more down the line (lower spray)
    if batter_side == 'R':
        inside_factor = -pitch_location_x  # negative plate_x = inside to RHB
    else:
        inside_factor = pitch_location_x   # positive plate_x = inside to LHB
    base_angle += inside_factor * 5

    # STEP 3: Launch angle adjustment
    if launch_angle_deg > 60:
        base_angle += np.random.normal(8, 4)   # high popups go more backward
    elif launch_angle_deg > 40:
        base_angle += np.random.normal(4, 3)
    elif launch_angle_deg < -10:
        base_angle -= np.random.normal(5, 3)   # grounders stay near foul line
    elif launch_angle_deg < 10:
        base_angle -= np.random.normal(2, 2)

    # STEP 4: Exit velocity adjustment
    if exit_velocity_mph > 95:
        base_angle -= np.random.normal(5, 2)   # hard contact → down the line
    elif exit_velocity_mph > 85:
        base_angle -= np.random.normal(2, 2)
    elif exit_velocity_mph < 50:
        base_angle += np.random.normal(5, 3)

    # STEP 5: Pitch type adjustment
    if pitch_type in ('CU', 'SL', 'ST', 'KC', 'SV'):
        base_angle += np.random.normal(3, 2)   # breaking balls → more behind
    elif pitch_type in ('CH', 'FS'):
        base_angle += np.random.normal(2, 1)

    # Clamp to >= 0: negative spray means fair territory, which violates
    # the stands-frame assumption (y > 0 = into stands) used downstream.
    return np.clip(base_angle, 0, 85)


def back_foul_probability(
    exit_velocity_mph: float,
    launch_angle_deg: float,
    pitch_type: str = 'FF',
) -> float:
    """Probability that a foul leaves the bat travelling back past home plate.

    Direction, not speed, is what makes a foul go backward: the ball glances off
    the bat instead of being driven off it. The exit velocity distribution the
    batter profiles are sampled from already contains those weak, nicked balls —
    it is measured off real fouls — so this conditions *where* a ball goes on how
    it was hit rather than changing how hard it was hit.

    Raises the rate for the contact that produces backward deflections (steep
    pop-ups off the top of the ball, weak contact, breaking pitches that beat the
    swing) and lowers it for the contact that cannot (choppers and hard line
    drives, which are squared up and go out in front).
    """
    p = BACK_FOUL_BASE_RATE

    # Steep launch means the bat caught the underside or edge — those go up and
    # back over the catcher. Balls hit downward stay in front and skip away.
    if launch_angle_deg > 60:
        p *= 1.6
    elif launch_angle_deg > 40:
        p *= 1.25
    elif launch_angle_deg < 0:
        p *= 0.35

    # Weak contact is a glancing blow; hard contact is a square one.
    if exit_velocity_mph < 55:
        p *= 1.5
    elif exit_velocity_mph > 90:
        p *= 0.55

    # Breaking and offspeed pitches are late-swing pitches.
    if pitch_type in ('CU', 'SL', 'ST', 'KC', 'SV'):
        p *= 1.15
    elif pitch_type in ('CH', 'FS'):
        p *= 1.10

    return float(np.clip(p, 0.0, 0.85))


def estimate_back_spray_angle(launch_angle_deg: float = 30.0) -> float:
    """Spray angle for a foul deflected back behind the plane of home plate.

    Drawn as an offset off BEHIND_PLATE_ANGLE (dead behind the catcher) toward
    the near foul line, so the density peaks straight back and thins out toward
    the corners of the backstop — which, mirrored across the two sides by the
    caller's side draw, is the wedge real backward fouls fill.

    Steeply-hit balls barely change direction on the way up and stay near the
    midline; flatter deflections carry further around toward the corner.
    """
    spread = 22.0 if launch_angle_deg > 45 else 30.0
    offset = abs(np.random.normal(0.0, spread))
    return float(np.clip(BEHIND_PLATE_ANGLE - offset, 90.5, BEHIND_PLATE_ANGLE))


def oblique_contact_speed_factor(spray_angle_deg: float) -> float:
    """Exit-speed multiplier for the glancing contact that sends a ball backward.

    A ball only leaves the bat travelling back over the catcher if the collision
    was tangential rather than square. Most of the bat's momentum passes it by,
    and what it does pick up goes largely into spin and friction, so it comes off
    far slower than the same swing hit out in front.

    The batter profiles cannot supply that on their own: they are built from
    Statcast-tracked fouls, and tracking is at its worst exactly on the balls
    that disappear into the backstop screen, so the sampled exit velocity is
    drawn from a population of squarer contact than this branch represents. Left
    uncorrected, a sampled 95 mph turns into a foul carrying 300 ft straight back
    out of the stadium, which is not a thing that happens.

    Returns 1.0 for anything hit out in front (spray <= 90).
    """
    if spray_angle_deg <= 90.0:
        return 1.0
    frac = np.clip((spray_angle_deg - 90.0) / (BEHIND_PLATE_ANGLE - 90.0), 0.0, 1.0)
    return float(0.85 - 0.27 * frac)  # 0.85 square to the plate, 0.58 dead back


def simulate_foul_ball(
    exit_velocity_mph: float,
    launch_angle_deg: float,
    batter_side: str,
    pitch_location_x: float = 0.0,
    altitude_ft: float = 0,
    temperature_f: float = 72,
    pitch_type: str = 'FF',
    fair_pull_pct: float = 50.0,
) -> tuple[TrajectoryResult, str]:
    """
    Full foul ball simulation with spray angle estimation.

    Side is determined from batter tendencies, then the trajectory is
    simulated and its y-axis is signed to encode side geometrically:
        y > 0 → 1B side (right field foul territory)
        y < 0 → 3B side (left field foul territory)

    The returned side string is derived from the trajectory geometry
    (sign of landing_y), making side a geometric outcome rather than
    an independent label.

    Returns (trajectory_result, side) where side is '1B' or '3B'.
    """
    # STEP 1: Determine which side from batter data.
    # RHB fouls predominantly to 3B side (pull-side fouls).
    # LHB fouls predominantly to 1B side.
    # Switch hitters should be resolved upstream (webapp resolves based on pitcher hand).
    # Defensive fallback: treat unresolved 'S' as 'R'.
    if batter_side not in ('L', 'R'):
        batter_side = 'R'

    # STEP 0: does this foul go forward into foul territory, or straight back
    # over the catcher? These are two different contact events, not two ends of
    # one distribution, so the mode is drawn first and then drives both the side
    # draw and the spray angle below.
    is_back_foul = np.random.random() < back_foul_probability(
        exit_velocity_mph, launch_angle_deg, pitch_type,
    )

    # Pull tendency increases directional consistency.
    pull_factor = np.clip((fair_pull_pct - 50) / 50, -1, 1)
    base_pull_pct = 0.72 + pull_factor * 0.10  # 62-82% to pull side

    # High popups are less directional (more random)
    if launch_angle_deg > 60:
        pull_pct = 0.50 + (base_pull_pct - 0.50) * 0.3
    elif launch_angle_deg > 40:
        pull_pct = 0.50 + (base_pull_pct - 0.50) * 0.6
    else:
        pull_pct = base_pull_pct

    # Hard contact is more consistently directional
    if exit_velocity_mph > 90:
        pull_pct = 0.50 + (pull_pct - 0.50) * 1.15
    elif exit_velocity_mph < 55:
        pull_pct = 0.50 + (pull_pct - 0.50) * 0.7

    # A ball deflected backward barely knows which way the bat was going, so
    # pull tendency almost washes out — the backstop fills near-symmetrically.
    if is_back_foul:
        pull_pct = 0.50 + (pull_pct - 0.50) * 0.35

    pull_pct = np.clip(pull_pct, 0.30, 0.90)

    if batter_side == 'R':
        goes_to_3b = np.random.random() < pull_pct
    else:
        goes_to_3b = np.random.random() >= pull_pct

    # STEP 2: Estimate spray angle (magnitude), conditioned on which side.
    # Pull-side fouls tend to go more down the foul line (lower spray angle).
    # Opposite-side fouls tend to go more behind the plate (higher spray angle).
    is_pull_side = (
        (batter_side == 'R' and goes_to_3b) or
        (batter_side == 'L' and not goes_to_3b)
    )

    if is_back_foul:
        # Behind the plate: the pull/opposite shift does not apply, because the
        # ball's direction came from the deflection, not from where the barrel
        # was pointed.
        spray_angle = estimate_back_spray_angle(launch_angle_deg)
    else:
        spray_angle = estimate_spray_angle(
            batter_side, pitch_location_x, exit_velocity_mph, launch_angle_deg,
            pitch_type=pitch_type,
        )

        # Shift spray based on pull vs opposite side
        if is_pull_side:
            spray_angle -= np.random.normal(4, 2)  # pull-side: more down the line
        else:
            spray_angle += np.random.normal(6, 3)  # opposite-side: more behind plate

        # Clamp to [0, 85]: forward fouls stay in front of the plate. Negative
        # spray would produce y < 0 (fair territory), which inverts side
        # assignment after the 3B sign-flip. The straight-back wedge is the
        # other branch's job, not something this one should drift into.
        spray_angle = np.clip(spray_angle, 0, 85)

    # STEP 3: Simulate trajectory in foul-line-relative frame (y always positive).
    # A ball sent backward left the bat on a glancing blow and comes off slower
    # than the sampled speed; one hit out in front keeps it unchanged.
    contact_ev = exit_velocity_mph * oblique_contact_speed_factor(spray_angle)
    result = simulate_trajectory(
        exit_velocity_mph=contact_ev,
        launch_angle_deg=launch_angle_deg,
        spray_angle_deg=spray_angle,
        altitude_ft=altitude_ft,
        temperature_f=temperature_f,
    )

    # STEP 4: Encode side in the trajectory geometry by signing the y-axis.
    # simulate_trajectory() works in a foul-line-relative frame where y > 0
    # always means "into stands." Here we sign it so the trajectory carries
    # left/right information:
    #   y > 0  →  1B side (right field foul territory)
    #   y < 0  →  3B side (left field foul territory)
    # This makes side a geometric property of the trajectory, not a label.
    if goes_to_3b:
        result.positions[:, 1] *= -1
        result.landing_y *= -1
        # Force a small negative to ensure -0.0 doesn't classify as 1B
        if result.landing_y == 0.0:
            result.landing_y = -0.001

    # Derive side from the signed geometry
    side = '3B' if result.landing_y < 0 else '1B'

    # Post-condition: side must match sign of landing_y
    if (side == '1B' and result.landing_y < 0) or (side == '3B' and result.landing_y > 0):
        logger.warning("Side/landing_y mismatch: side=%s, landing_y=%.1f", side, result.landing_y)

    return result, side
