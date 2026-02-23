"""
Stadium Geometry Layer.

Models real MLB stadium geometries with seat sections, heights, and distances.
Maps 3D trajectory landing positions to specific stadium sections.
"""
import numpy as np
from dataclasses import dataclass, field


@dataclass
class SeatSection:
    """A section of stadium seating."""
    name: str
    section_id: str
    side: str              # '1B', '3B', 'HOME', 'LF', 'RF'
    level: str             # 'field', 'lower', 'upper', 'bleachers'

    # Boundaries in stadium coordinates (feet from home plate)
    distance_min: float    # closest point to home plate
    distance_max: float    # farthest point from home plate
    angle_min: float       # degrees from foul line (0 = foul line, 90 = behind plate)
    angle_max: float

    # Vertical
    height_min: float      # bottom of section (feet above field)
    height_max: float      # top of section

    # Metadata
    num_seats: int = 200
    avg_ticket_price: float = 0.0


@dataclass
class Stadium:
    """Full stadium geometry model."""
    name: str
    city: str
    team: str
    altitude_ft: float = 0
    avg_temperature_f: float = 72

    # Field dimensions
    lf_distance: float = 330    # left field wall distance
    cf_distance: float = 400    # center field
    rf_distance: float = 330    # right field
    backstop_distance: float = 60  # home plate to backstop

    sections: list[SeatSection] = field(default_factory=list)

    # Section matching is done in matchup_engine.py which uses trajectory
    # position interpolation for height estimation (more accurate than a
    # single height value). See matchup_engine.py lines 160-176.


# ============================================================
# Real Stadium Definitions
# ============================================================

def _make_yankee_stadium_sections() -> list[SeatSection]:
    """Real section layout for Yankee Stadium (opened 2009)."""
    sections = []

    # === FIELD LEVEL ===
    # 1B Dugout area (Sec 109-114)
    sections.append(SeatSection(
        name='1B Dugout Box (Sec 109-114)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=150, avg_ticket_price=350,
    ))
    # 1B Field MVP (Sec 115-118)
    sections.append(SeatSection(
        name='1B Field MVP (Sec 115-118)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=60, distance_max=120,
        angle_min=25, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=400,
    ))
    # Behind Plate Field (Sec 119-121)
    sections.append(SeatSection(
        name='Behind Plate Field (Sec 119-121)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=50, distance_max=90,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=200, avg_ticket_price=500,
    ))
    # 3B Field MVP (Sec 122-125)
    sections.append(SeatSection(
        name='3B Field MVP (Sec 122-125)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=60, distance_max=120,
        angle_min=25, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=400,
    ))
    # 3B Dugout area (Sec 126-131)
    sections.append(SeatSection(
        name='3B Dugout Box (Sec 126-131)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=150, avg_ticket_price=350,
    ))

    # === MAIN LEVEL (200s) ===
    # Behind Plate Lower / Main 200s (Sec 218-222)
    sections.append(SeatSection(
        name='Behind Plate Main (Sec 218-222)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=60, distance_max=120,
        angle_min=55, angle_max=90,
        height_min=15, height_max=40,
        num_seats=350, avg_ticket_price=200,
    ))
    # 1B Main Level (Sec 211-217)
    sections.append(SeatSection(
        name='1B Main Level (Sec 211-217)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=30, distance_max=180,
        angle_min=15, angle_max=45,
        height_min=10, height_max=35,
        num_seats=500, avg_ticket_price=150,
    ))
    # 3B Main Level (Sec 223-228)
    sections.append(SeatSection(
        name='3B Main Level (Sec 223-228)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=30, distance_max=180,
        angle_min=15, angle_max=45,
        height_min=10, height_max=35,
        num_seats=500, avg_ticket_price=150,
    ))
    # 1B Lower Reserve (Sec 205-210)
    sections.append(SeatSection(
        name='1B Lower Reserve (Sec 205-210)', section_id='1B-LR',
        side='1B', level='lower',
        distance_min=180, distance_max=280,
        angle_min=5, angle_max=35,
        height_min=12, height_max=40,
        num_seats=800, avg_ticket_price=80,
    ))
    # 3B Lower Reserve (Sec 229-234)
    sections.append(SeatSection(
        name='3B Lower Reserve (Sec 229-234)', section_id='3B-LR',
        side='3B', level='lower',
        distance_min=180, distance_max=280,
        angle_min=5, angle_max=35,
        height_min=12, height_max=40,
        num_seats=800, avg_ticket_price=80,
    ))

    # === TERRACE / UPPER (300s) ===
    # Behind Plate Terrace (Sec 317-323)
    sections.append(SeatSection(
        name='Behind Plate Terrace (Sec 317-323)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=20, angle_max=55,
        height_min=35, height_max=70,
        num_seats=500, avg_ticket_price=75,
    ))
    # 1B Upper (Sec 307-316)
    sections.append(SeatSection(
        name='1B Upper (Sec 307-316)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=40, distance_max=250,
        angle_min=10, angle_max=55,
        height_min=35, height_max=80,
        num_seats=600, avg_ticket_price=60,
    ))
    # 3B Upper (Sec 324-331)
    sections.append(SeatSection(
        name='3B Upper (Sec 324-331)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=40, distance_max=250,
        angle_min=10, angle_max=55,
        height_min=35, height_max=80,
        num_seats=600, avg_ticket_price=60,
    ))

    # === GRANDSTAND (400s) ===
    # Behind Plate Grand (Sec 419-421)
    sections.append(SeatSection(
        name='Behind Plate Grandstand (Sec 419-421)', section_id='HOME-G',
        side='HOME', level='upper',
        distance_min=40, distance_max=140,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=400, avg_ticket_price=30,
    ))
    # 1B Grandstand (Sec 407-418)
    sections.append(SeatSection(
        name='1B Grandstand (Sec 407-418)', section_id='1B-UR',
        side='1B', level='upper',
        distance_min=130, distance_max=250,
        angle_min=10, angle_max=40,
        height_min=40, height_max=80,
        num_seats=900, avg_ticket_price=35,
    ))
    # 3B Grandstand (Sec 422-429)
    sections.append(SeatSection(
        name='3B Grandstand (Sec 422-429)', section_id='3B-UR',
        side='3B', level='upper',
        distance_min=130, distance_max=250,
        angle_min=10, angle_max=40,
        height_min=40, height_max=80,
        num_seats=900, avg_ticket_price=35,
    ))

    return sections


def _make_fenway_park_sections() -> list[SeatSection]:
    """Real section layout for Fenway Park (opened 1912)."""
    sections = []

    # === FIELD BOX LEVEL ===
    # 1B Field Box (Sec FB9-FB16)
    sections.append(SeatSection(
        name='1B Field Box (Sec FB9-FB16)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=100, distance_max=200,
        angle_min=0, angle_max=30,
        height_min=0, height_max=8,
        num_seats=150, avg_ticket_price=250,
    ))
    # 1B Infield Field Box (Sec FB17-FB29)
    sections.append(SeatSection(
        name='1B Infield Field Box (Sec FB17-FB29)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=60, distance_max=120,
        angle_min=25, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=350,
    ))
    # Behind Plate Field Box (Sec FB31-FB49)
    sections.append(SeatSection(
        name='Behind Plate Field Box (Sec FB31-FB49)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=50, distance_max=90,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=200, avg_ticket_price=450,
    ))
    # 3B Infield Field Box (Sec FB51-FB69)
    sections.append(SeatSection(
        name='3B Infield Field Box (Sec FB51-FB69)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=60, distance_max=120,
        angle_min=25, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=350,
    ))
    # 3B Field Box / LF (Sec FB71-FB82)
    sections.append(SeatSection(
        name='3B Field Box (Sec FB71-FB82)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=100, distance_max=200,
        angle_min=0, angle_max=30,
        height_min=0, height_max=8,
        num_seats=150, avg_ticket_price=250,
    ))

    # === LOGE LEVEL ===
    # 1B Loge (Sec LB101-LB124)
    sections.append(SeatSection(
        name='1B Loge (Sec LB101-LB124)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=100, distance_max=250,
        angle_min=0, angle_max=45,
        height_min=10, height_max=35,
        num_seats=600, avg_ticket_price=120,
    ))
    # Behind Plate Loge (Sec LB125-LB136)
    sections.append(SeatSection(
        name='Behind Plate Loge (Sec LB125-LB136)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=60, distance_max=120,
        angle_min=55, angle_max=90,
        height_min=10, height_max=35,
        num_seats=350, avg_ticket_price=200,
    ))
    # 3B Loge (Sec LB137-LB155)
    sections.append(SeatSection(
        name='3B Loge (Sec LB137-LB155)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=100, distance_max=250,
        angle_min=0, angle_max=45,
        height_min=10, height_max=35,
        num_seats=600, avg_ticket_price=120,
    ))

    # === GRANDSTAND LEVEL ===
    # 1B Grandstand (Sec G5-G11)
    sections.append(SeatSection(
        name='1B Grandstand (Sec G5-G11)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=40, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=35, height_max=70,
        num_seats=600, avg_ticket_price=60,
    ))
    # Behind Plate Grandstand (Sec G12-G21)
    sections.append(SeatSection(
        name='Behind Plate Grandstand (Sec G12-G21)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=140,
        angle_min=50, angle_max=90,
        height_min=35, height_max=70,
        num_seats=500, avg_ticket_price=75,
    ))
    # 3B Grandstand (Sec G22-G28)
    sections.append(SeatSection(
        name='3B Grandstand (Sec G22-G28)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=40, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=35, height_max=70,
        num_seats=600, avg_ticket_price=60,
    ))

    return sections


def _make_dodger_stadium_sections() -> list[SeatSection]:
    """Real section layout for Dodger Stadium."""
    sections = []

    # === FIELD LEVEL ===
    # Behind Plate Dugout Club (Sec DG1-DG15)
    sections.append(SeatSection(
        name='Dugout Club (Sec DG1-DG15)', section_id='HOME-DC',
        side='HOME', level='field',
        distance_min=30, distance_max=60,
        angle_min=55, angle_max=90,
        height_min=0, height_max=8,
        num_seats=100, avg_ticket_price=800,
    ))
    # Behind Plate Field MVP (Sec FD1-FD10)
    sections.append(SeatSection(
        name='Behind Plate Field (Sec FD1-FD10)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=40, distance_max=80,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=200, avg_ticket_price=500,
    ))
    # 1B Infield Field (Sec FD12-FD24, even)
    sections.append(SeatSection(
        name='1B Infield Field (Sec FD12-FD24)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=80, distance_max=180,
        angle_min=0, angle_max=30,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=250,
    ))
    # 3B Infield Field (Sec FD11-FD25, odd)
    sections.append(SeatSection(
        name='3B Infield Field (Sec FD11-FD25)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=80, distance_max=180,
        angle_min=0, angle_max=30,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=250,
    ))
    # 1B Baseline (Sec FD26-FD44, even)
    sections.append(SeatSection(
        name='1B Baseline Field (Sec FD26-FD44)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=180, distance_max=300,
        angle_min=0, angle_max=25,
        height_min=0, height_max=12,
        num_seats=400, avg_ticket_price=180,
    ))
    # 3B Baseline (Sec FD27-FD45, odd)
    sections.append(SeatSection(
        name='3B Baseline Field (Sec FD27-FD45)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=180, distance_max=300,
        angle_min=0, angle_max=25,
        height_min=0, height_max=12,
        num_seats=400, avg_ticket_price=180,
    ))

    # === LOGE LEVEL ===
    # Behind Plate Loge (Sec 101-110)
    sections.append(SeatSection(
        name='Behind Plate Loge (Sec 101-110)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=60, distance_max=120,
        angle_min=55, angle_max=90,
        height_min=15, height_max=40,
        num_seats=350, avg_ticket_price=200,
    ))
    # 1B Loge (Sec 112-136, even)
    sections.append(SeatSection(
        name='1B Loge (Sec 112-136)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=30, distance_max=180,
        angle_min=15, angle_max=45,
        height_min=10, height_max=35,
        num_seats=500, avg_ticket_price=150,
    ))
    # 3B Loge (Sec 111-135, odd)
    sections.append(SeatSection(
        name='3B Loge (Sec 111-135)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=30, distance_max=180,
        angle_min=15, angle_max=45,
        height_min=10, height_max=35,
        num_seats=500, avg_ticket_price=150,
    ))

    # === RESERVE LEVEL ===
    # Behind Plate Reserve (Sec RS1-RS10)
    sections.append(SeatSection(
        name='Behind Plate Reserve (Sec RS1-RS10)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=35, height_max=70,
        num_seats=500, avg_ticket_price=75,
    ))
    # 1B Reserve (Sec RS12-RS36, even)
    sections.append(SeatSection(
        name='1B Reserve (Sec RS12-RS36)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=40, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=35, height_max=70,
        num_seats=600, avg_ticket_price=60,
    ))
    # 3B Reserve (Sec RS11-RS35, odd)
    sections.append(SeatSection(
        name='3B Reserve (Sec RS11-RS35)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=40, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=35, height_max=70,
        num_seats=600, avg_ticket_price=60,
    ))

    return sections


def _make_wrigley_field_sections() -> list[SeatSection]:
    """Real section layout for Wrigley Field (opened 1914)."""
    sections = []

    # === FIELD BOX (100s) ===
    # 1B Field Box (Sec 123-134) — down RF foul line
    sections.append(SeatSection(
        name='1B Field Box (Sec 123-134)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=300,
    ))
    # 1B Infield Field Box (Sec 115-122)
    sections.append(SeatSection(
        name='1B Infield Field Box (Sec 115-122)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=400,
    ))
    # Behind Plate Field Box (Sec 112-114)
    sections.append(SeatSection(
        name='Behind Plate Field Box (Sec 112-114)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=12,
        num_seats=150, avg_ticket_price=500,
    ))
    # 3B Infield Field Box (Sec 105-111)
    sections.append(SeatSection(
        name='3B Infield Field Box (Sec 105-111)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=400,
    ))
    # 3B Field Box (Sec 101-104) — down LF foul line
    sections.append(SeatSection(
        name='3B Field Box (Sec 101-104)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=300,
    ))

    # === TERRACE LEVEL (200s) ===
    # 1B Terrace (Sec 225-233)
    sections.append(SeatSection(
        name='1B Terrace (Sec 225-233)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=10, angle_max=45,
        height_min=12, height_max=35,
        num_seats=500, avg_ticket_price=120,
    ))
    # Behind Plate Terrace (Sec 213-224)
    sections.append(SeatSection(
        name='Behind Plate Terrace (Sec 213-224)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=55, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=35,
        num_seats=400, avg_ticket_price=180,
    ))
    # 3B Terrace (Sec 202-212)
    sections.append(SeatSection(
        name='3B Terrace (Sec 202-212)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=10, angle_max=45,
        height_min=12, height_max=35,
        num_seats=500, avg_ticket_price=120,
    ))

    # === UPPER DECK (300s) ===
    # 1B Upper (Sec 319R-331R)
    sections.append(SeatSection(
        name='1B Upper (Sec 319R-331R)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=45, distance_max=240,
        angle_min=10, angle_max=50,
        height_min=38, height_max=75,
        num_seats=600, avg_ticket_price=55,
    ))
    # Behind Plate Upper (Sec 308L-318R)
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 308L-318R)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=45, angle_max=90,
        height_min=38, height_max=75,
        num_seats=500, avg_ticket_price=65,
    ))
    # 3B Upper (Sec 303L-307L)
    sections.append(SeatSection(
        name='3B Upper (Sec 303L-307L)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=45, distance_max=240,
        angle_min=10, angle_max=50,
        height_min=38, height_max=75,
        num_seats=600, avg_ticket_price=55,
    ))

    # === UPPER RESERVED (400s) ===
    # 1B Upper Reserved (Sec 420R-431R)
    sections.append(SeatSection(
        name='1B Upper Reserved (Sec 420R-431R)', section_id='1B-UR',
        side='1B', level='upper',
        distance_min=130, distance_max=250,
        angle_min=5, angle_max=40,
        height_min=45, height_max=85,
        num_seats=800, avg_ticket_price=30,
    ))
    # Behind Plate Upper Reserved (Sec 409-419)
    sections.append(SeatSection(
        name='Behind Plate Upper Reserved (Sec 409-419)', section_id='HOME-G',
        side='HOME', level='upper',
        distance_min=45, distance_max=140,
        angle_min=45, angle_max=90,
        height_min=45, height_max=85,
        num_seats=500, avg_ticket_price=35,
    ))
    # 3B Upper Reserved (Sec 403L-408L)
    sections.append(SeatSection(
        name='3B Upper Reserved (Sec 403L-408L)', section_id='3B-UR',
        side='3B', level='upper',
        distance_min=130, distance_max=250,
        angle_min=5, angle_max=40,
        height_min=45, height_max=85,
        num_seats=800, avg_ticket_price=30,
    ))

    return sections


def _make_coors_field_sections() -> list[SeatSection]:
    """Real section layout for Coors Field (opened 1995). High altitude!"""
    sections = []

    # === FIELD LEVEL (100s) ===
    # 1B Baseline (Sec 141-150) — down RF foul line
    sections.append(SeatSection(
        name='1B Baseline (Sec 141-150)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=250, avg_ticket_price=150,
    ))
    # 1B Infield (Sec 133-140)
    sections.append(SeatSection(
        name='1B Infield (Sec 133-140)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=60, distance_max=130,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=350, avg_ticket_price=250,
    ))
    # Behind Plate (Sec 127-132, Coors Club)
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 127-132)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=90,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=200, avg_ticket_price=350,
    ))
    # 3B Infield (Sec 118-126)
    sections.append(SeatSection(
        name='3B Infield (Sec 118-126)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=60, distance_max=130,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=350, avg_ticket_price=250,
    ))
    # 3B Baseline (Sec 110-117) — down LF foul line
    sections.append(SeatSection(
        name='3B Baseline (Sec 110-117)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=250, avg_ticket_price=150,
    ))

    # === CLUB LEVEL (200s) ===
    # 1B Club (Sec 237-247)
    sections.append(SeatSection(
        name='1B Club (Sec 237-247)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=200,
        angle_min=10, angle_max=45,
        height_min=12, height_max=38,
        num_seats=500, avg_ticket_price=120,
    ))
    # Behind Plate Club (Sec 225-236)
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 225-236)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=55, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=12, height_max=38,
        num_seats=400, avg_ticket_price=180,
    ))
    # 3B Club (Sec 214-224)
    sections.append(SeatSection(
        name='3B Club (Sec 214-224)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=200,
        angle_min=10, angle_max=45,
        height_min=12, height_max=38,
        num_seats=500, avg_ticket_price=120,
    ))

    # === UPPER DECK (300s) ===
    # 1B Upper (Sec 333-347)
    sections.append(SeatSection(
        name='1B Upper (Sec 333-347)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=260,
        angle_min=10, angle_max=50,
        height_min=40, height_max=85,
        num_seats=700, avg_ticket_price=35,
    ))
    # Behind Plate Upper (Sec 321-332)
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 321-332)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=45, distance_max=140,
        angle_min=45, angle_max=90,
        height_min=40, height_max=85,
        num_seats=550, avg_ticket_price=45,
    ))
    # 3B Upper (Sec 301-320)
    sections.append(SeatSection(
        name='3B Upper (Sec 301-320)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=260,
        angle_min=10, angle_max=50,
        height_min=40, height_max=85,
        num_seats=700, avg_ticket_price=35,
    ))

    return sections


def _make_citi_field_sections() -> list[SeatSection]:
    """Real section layout for Citi Field (opened 2009)."""
    sections = []

    # === FIELD LEVEL (100s) ===
    # 1B Baseline (Sec 104-110)
    sections.append(SeatSection(
        name='1B Baseline Box (Sec 104-110)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=100, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=200,
    ))
    # 1B Infield (Sec 111-114)
    sections.append(SeatSection(
        name='1B Infield Field (Sec 111-114)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=25, angle_max=55,
        height_min=0, height_max=10,
        num_seats=250, avg_ticket_price=350,
    ))
    # Behind Plate (Sec 115-120)
    sections.append(SeatSection(
        name='Behind Plate (Sec 115-120)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=90,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=200, avg_ticket_price=500,
    ))
    # 3B Infield (Sec 121-125)
    sections.append(SeatSection(
        name='3B Infield Field (Sec 121-125)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=25, angle_max=55,
        height_min=0, height_max=10,
        num_seats=250, avg_ticket_price=350,
    ))
    # 3B Baseline (Sec 126-132)
    sections.append(SeatSection(
        name='3B Baseline Box (Sec 126-132)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=100, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=200,
    ))

    # === EXCELSIOR LEVEL (300s) ===
    # 1B Excelsior (Sec 309-316)
    sections.append(SeatSection(
        name='1B Excelsior (Sec 309-316)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=190,
        angle_min=15, angle_max=45,
        height_min=12, height_max=38,
        num_seats=450, avg_ticket_price=130,
    ))
    # Behind Plate Excelsior (Sec 317-325)
    sections.append(SeatSection(
        name='Behind Plate Excelsior (Sec 317-325)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=55, distance_max=120,
        angle_min=55, angle_max=90,
        height_min=12, height_max=38,
        num_seats=350, avg_ticket_price=180,
    ))
    # 3B Excelsior (Sec 326-329)
    sections.append(SeatSection(
        name='3B Excelsior (Sec 326-329)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=190,
        angle_min=15, angle_max=45,
        height_min=12, height_max=38,
        num_seats=450, avg_ticket_price=130,
    ))

    # === PROMENADE LEVEL (500s) ===
    # 1B Promenade (Sec 506-514)
    sections.append(SeatSection(
        name='1B Promenade (Sec 506-514)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=35,
    ))
    # Behind Plate Promenade (Sec 515-523)
    sections.append(SeatSection(
        name='Behind Plate Promenade (Sec 515-523)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=140,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=45,
    ))
    # 3B Promenade (Sec 524-531)
    sections.append(SeatSection(
        name='3B Promenade (Sec 524-531)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=35,
    ))

    return sections


def _make_citizens_bank_sections() -> list[SeatSection]:
    """Real section layout for Citizens Bank Park (opened 2004)."""
    sections = []

    # === FIELD LEVEL (100s) ===
    # 1B Diamond Club (Sec 115-119)
    sections.append(SeatSection(
        name='1B Diamond Club (Sec 115-119)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=250,
    ))
    # 1B Infield (Sec 120-126)
    sections.append(SeatSection(
        name='1B Infield (Sec 120-126)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=300,
    ))
    # Behind Plate (Sec 127-131)
    sections.append(SeatSection(
        name='Behind Plate (Sec 127-131)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=180, avg_ticket_price=400,
    ))
    # 3B Infield (Sec 132-138)
    sections.append(SeatSection(
        name='3B Infield (Sec 132-138)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=300,
    ))
    # 3B Baseline (Sec 139-145)
    sections.append(SeatSection(
        name='3B Baseline (Sec 139-145)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=250,
    ))

    # === HALL OF FAME CLUB (200s) ===
    # 1B Club (Sec 215-222)
    sections.append(SeatSection(
        name='1B Hall of Fame Club (Sec 215-222)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=35, distance_max=180,
        angle_min=15, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=140,
    ))
    # Behind Plate Club (Sec 223-229)
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 223-229)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=55, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=180,
    ))
    # 3B Club (Sec 230-237)
    sections.append(SeatSection(
        name='3B Hall of Fame Club (Sec 230-237)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=35, distance_max=180,
        angle_min=15, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=140,
    ))

    # === TERRACE DECK (300s) ===
    # 1B Terrace (Sec 315-322)
    sections.append(SeatSection(
        name='1B Terrace (Sec 315-322)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=75,
        num_seats=600, avg_ticket_price=35,
    ))
    # Behind Plate Terrace (Sec 323-329)
    sections.append(SeatSection(
        name='Behind Plate Terrace (Sec 323-329)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=38, height_max=75,
        num_seats=500, avg_ticket_price=45,
    ))
    # 3B Terrace (Sec 330-336)
    sections.append(SeatSection(
        name='3B Terrace (Sec 330-336)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=75,
        num_seats=600, avg_ticket_price=35,
    ))

    return sections


def _make_truist_park_sections() -> list[SeatSection]:
    """Real section layout for Truist Park (opened 2017)."""
    sections = []

    # === FIELD LEVEL ===
    # 1B Dugout (Sec 115-121)
    sections.append(SeatSection(
        name='1B Dugout Box (Sec 115-121)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=180,
    ))
    # 1B Infield (Sec 122-128)
    sections.append(SeatSection(
        name='1B Infield (Sec 122-128)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=280,
    ))
    # Behind Plate (Sec 129-133)
    sections.append(SeatSection(
        name='Behind Plate (Sec 129-133)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=180, avg_ticket_price=400,
    ))
    # 3B Infield (Sec 134-140)
    sections.append(SeatSection(
        name='3B Infield (Sec 134-140)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=280,
    ))
    # 3B Dugout (Sec 141-147)
    sections.append(SeatSection(
        name='3B Dugout Box (Sec 141-147)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=180,
    ))

    # === TERRACE LEVEL (200s) ===
    # 1B Terrace (Sec 218-226)
    sections.append(SeatSection(
        name='1B Terrace (Sec 218-226)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=100,
    ))
    # Behind Plate Terrace (Sec 227-235)
    sections.append(SeatSection(
        name='Behind Plate Terrace (Sec 227-235)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=55, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=150,
    ))
    # 3B Terrace (Sec 236-244)
    sections.append(SeatSection(
        name='3B Terrace (Sec 236-244)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=100,
    ))

    # === UPPER LEVEL (300s) ===
    # 1B Upper (Sec 320-331)
    sections.append(SeatSection(
        name='1B Upper (Sec 320-331)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=650, avg_ticket_price=30,
    ))
    # Behind Plate Upper (Sec 332-340)
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 332-340)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=38, height_max=78,
        num_seats=500, avg_ticket_price=40,
    ))
    # 3B Upper (Sec 341-350)
    sections.append(SeatSection(
        name='3B Upper (Sec 341-350)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=650, avg_ticket_price=30,
    ))

    return sections


def _make_oracle_park_sections() -> list[SeatSection]:
    """Real section layout for Oracle Park (opened 2000)."""
    sections = []

    # === FIELD LEVEL (100s) ===
    # 1B Club (Sec 117-123) — down RF line toward McCovey Cove
    sections.append(SeatSection(
        name='1B Club Box (Sec 117-123)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=195,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=250,
    ))
    # 1B Infield (Sec 110-116)
    sections.append(SeatSection(
        name='1B Infield (Sec 110-116)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=115,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=350,
    ))
    # Behind Plate (Sec 107-109)
    sections.append(SeatSection(
        name='Behind Plate (Sec 107-109)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=450,
    ))
    # 3B Infield (Sec 103-106)
    sections.append(SeatSection(
        name='3B Infield (Sec 103-106)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=115,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=350,
    ))
    # 3B Baseline (Sec 101-102)
    sections.append(SeatSection(
        name='3B Baseline (Sec 101-102)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=195,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=250,
    ))

    # === CLUB LEVEL (200s) ===
    # 1B Club (Sec 216-226)
    sections.append(SeatSection(
        name='1B Club (Sec 216-226)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=12, angle_max=45,
        height_min=10, height_max=35,
        num_seats=450, avg_ticket_price=140,
    ))
    # Behind Plate Club (Sec 209-215)
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 209-215)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=55, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=10, height_max=35,
        num_seats=350, avg_ticket_price=200,
    ))
    # 3B Club (Sec 202-208)
    sections.append(SeatSection(
        name='3B Club (Sec 202-208)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=12, angle_max=45,
        height_min=10, height_max=35,
        num_seats=450, avg_ticket_price=140,
    ))

    # === VIEW LEVEL (300s) ===
    # 1B View (Sec 317-327)
    sections.append(SeatSection(
        name='1B View Reserve (Sec 317-327)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=75,
        num_seats=600, avg_ticket_price=30,
    ))
    # Behind Plate View (Sec 308-316)
    sections.append(SeatSection(
        name='Behind Plate View (Sec 308-316)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=38, height_max=75,
        num_seats=500, avg_ticket_price=40,
    ))
    # 3B View (Sec 302-307)
    sections.append(SeatSection(
        name='3B View Reserve (Sec 302-307)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=75,
        num_seats=600, avg_ticket_price=30,
    ))

    return sections


def _make_daikin_park_sections() -> list[SeatSection]:
    """Real section layout for Daikin Park (opened 2000, formerly Minute Maid)."""
    sections = []

    # === FIELD LEVEL (100s) ===
    # 1B Baseline (Sec 128-134) — toward RF/Crawford Boxes side
    sections.append(SeatSection(
        name='1B Baseline (Sec 128-134)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=180,
    ))
    # 1B Infield (Sec 121-127)
    sections.append(SeatSection(
        name='1B Infield (Sec 121-127)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=300,
    ))
    # Behind Plate (Sec 117-120, Diamond Club)
    sections.append(SeatSection(
        name='Behind Plate Diamond (Sec 117-120)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=40, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=180, avg_ticket_price=450,
    ))
    # 3B Infield (Sec 111-116)
    sections.append(SeatSection(
        name='3B Infield (Sec 111-116)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=300,
    ))
    # 3B Baseline (Sec 105-110) — toward LF
    sections.append(SeatSection(
        name='3B Baseline (Sec 105-110)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=180,
    ))

    # === CLUB / MEZZANINE (200s) ===
    # 1B Mezzanine (Sec 224-232)
    sections.append(SeatSection(
        name='1B Mezzanine (Sec 224-232)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=110,
    ))
    # Behind Plate Mezzanine (Sec 216-223)
    sections.append(SeatSection(
        name='Behind Plate Mezzanine (Sec 216-223)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=160,
    ))
    # 3B Mezzanine (Sec 206-215)
    sections.append(SeatSection(
        name='3B Mezzanine (Sec 206-215)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=110,
    ))

    # === UPPER DECK (400s) ===
    # 1B Upper (Sec 427-434)
    sections.append(SeatSection(
        name='1B Upper Deck (Sec 427-434)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=25,
    ))
    # Behind Plate Upper (Sec 418-426)
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 418-426)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=35,
    ))
    # 3B Upper (Sec 408-417)
    sections.append(SeatSection(
        name='3B Upper Deck (Sec 408-417)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=25,
    ))

    return sections


def _make_tropicana_field_sections() -> list[SeatSection]:
    """Real section layout for Tropicana Field (opened 1990). Indoor dome."""
    sections = []

    # === LOWER LEVEL (100s) ===
    # 1B Lower (Sec 113-118)
    sections.append(SeatSection(
        name='1B Lower Box (Sec 113-118)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=190,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=180, avg_ticket_price=80,
    ))
    # 1B Infield Lower (Sec 107-112)
    sections.append(SeatSection(
        name='1B Infield Lower (Sec 107-112)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=50, distance_max=110,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=250, avg_ticket_price=150,
    ))
    # Behind Plate Lower (Sec 104-106)
    sections.append(SeatSection(
        name='Behind Plate Lower (Sec 104-106)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=40, distance_max=80,
        angle_min=55, angle_max=90,
        height_min=0, height_max=12,
        num_seats=150, avg_ticket_price=200,
    ))
    # 3B Infield Lower (Sec 100-103)
    sections.append(SeatSection(
        name='3B Infield Lower (Sec 100-103)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=50, distance_max=110,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=250, avg_ticket_price=150,
    ))
    # 3B Lower (Sec 125-130)
    sections.append(SeatSection(
        name='3B Lower Box (Sec 125-130)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=190,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=180, avg_ticket_price=80,
    ))

    # === PRESS LEVEL (200s) ===
    # 1B Press (Sec 211-216)
    sections.append(SeatSection(
        name='1B Press Level (Sec 211-216)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=175,
        angle_min=12, angle_max=45,
        height_min=10, height_max=32,
        num_seats=400, avg_ticket_price=60,
    ))
    # Behind Plate Press (Sec 205-210)
    sections.append(SeatSection(
        name='Behind Plate Press (Sec 205-210)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=110,
        angle_min=55, angle_max=90,
        height_min=10, height_max=32,
        num_seats=300, avg_ticket_price=80,
    ))
    # 3B Press (Sec 217-224)
    sections.append(SeatSection(
        name='3B Press Level (Sec 217-224)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=175,
        angle_min=12, angle_max=45,
        height_min=10, height_max=32,
        num_seats=400, avg_ticket_price=60,
    ))

    # === UPPER LEVEL (300s) ===
    # 1B Upper (Sec 310-316)
    sections.append(SeatSection(
        name='1B Upper (Sec 310-316)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=45, distance_max=230,
        angle_min=10, angle_max=45,
        height_min=35, height_max=70,
        num_seats=550, avg_ticket_price=20,
    ))
    # Behind Plate Upper (Sec 303-309)
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 303-309)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=35, height_max=70,
        num_seats=450, avg_ticket_price=25,
    ))
    # 3B Upper (Sec 317-322)
    sections.append(SeatSection(
        name='3B Upper (Sec 317-322)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=45, distance_max=230,
        angle_min=10, angle_max=45,
        height_min=35, height_max=70,
        num_seats=550, avg_ticket_price=20,
    ))

    return sections


def _make_chase_field_sections() -> list[SeatSection]:
    """Real section layout for Chase Field (opened 1998). Retractable roof."""
    sections = []

    # === FIELD LEVEL (100s) ===
    sections.append(SeatSection(
        name='1B Baseline (Sec 112-118)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=205,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 105-111)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 101-104)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=180, avg_ticket_price=300,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 125-131)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 132-138)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=205,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=120,
    ))

    # === CLUB / SUITE LEVEL (200s) ===
    sections.append(SeatSection(
        name='1B Club (Sec 208-216)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 200-207)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 217-225)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=100,
    ))

    # === UPPER DECK (300s) ===
    sections.append(SeatSection(
        name='1B Upper (Sec 316-326)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=600, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 306-315)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=38, height_max=78,
        num_seats=500, avg_ticket_price=35,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 327-336)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=600, avg_ticket_price=25,
    ))

    return sections


def _make_camden_yards_sections() -> list[SeatSection]:
    """Real section layout for Oriole Park at Camden Yards (opened 1992)."""
    sections = []

    # === FIELD LEVEL (lower 0-99) ===
    sections.append(SeatSection(
        name='1B Field Box (Sec 56-68)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 44-55)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 38-43)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=48, distance_max=90,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=180, avg_ticket_price=350,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 26-37)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='3B Field Box (Sec 14-25)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=150,
    ))

    # === CLUB LEVEL (200s) ===
    sections.append(SeatSection(
        name='1B Club (Sec 252-264)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 242-251)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=55, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 228-241)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=100,
    ))

    # === UPPER DECK (300s) ===
    sections.append(SeatSection(
        name='1B Upper (Sec 362-376)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=650, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 348-361)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=38, height_max=78,
        num_seats=500, avg_ticket_price=35,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 332-347)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=650, avg_ticket_price=25,
    ))

    return sections


def _make_great_american_sections() -> list[SeatSection]:
    """Real section layout for Great American Ball Park (opened 2003)."""
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 128-136)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 120-127)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 116-119)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=300,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 109-115)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 101-108)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=120,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 220-228)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=90,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 213-219)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=130,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 205-212)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=90,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 420-430)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=600, avg_ticket_price=20,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 412-419)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=38, height_max=78,
        num_seats=500, avg_ticket_price=30,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 401-411)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=600, avg_ticket_price=20,
    ))

    return sections


def _make_progressive_field_sections() -> list[SeatSection]:
    """Real section layout for Progressive Field (opened 1994)."""
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 162-172)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 153-161)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 148-152)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=170, avg_ticket_price=280,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 139-147)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=300, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 130-138)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 453-461)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 446-452)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 437-445)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=80,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 556-568)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=18,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 546-555)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 534-545)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=18,
    ))

    return sections


def _make_comerica_park_sections() -> list[SeatSection]:
    """Real section layout for Comerica Park (opened 2000)."""
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 120-130)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 113-119)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 109-112)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=280,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 103-108)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 137-145)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 218-228)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=190,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 210-217)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 229-238)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=190,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 318-330)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=18,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 308-317)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 331-340)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=18,
    ))

    return sections


def _make_kauffman_stadium_sections() -> list[SeatSection]:
    """Real section layout for Kauffman Stadium (opened 1973)."""
    sections = []

    sections.append(SeatSection(
        name='1B Dugout (Sec 121-131)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 114-120)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 110-113)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 103-109)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='3B Dugout (Sec 133-143)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B Loge (Sec 221-231)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=70,
    ))
    sections.append(SeatSection(
        name='Behind Plate Loge (Sec 213-220)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='3B Loge (Sec 232-243)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=70,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 421-431)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=15,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 413-420)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=22,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 432-443)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=15,
    ))

    return sections


def _make_angel_stadium_sections() -> list[SeatSection]:
    """Real section layout for Angel Stadium (opened 1966)."""
    sections = []

    sections.append(SeatSection(
        name='1B Field (Sec 121-129)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 114-120)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 110-113)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=300,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 103-109)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='3B Field (Sec 133-141)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=120,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 221-229)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 213-220)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 230-239)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 421-433)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=18,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 413-420)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 434-445)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=18,
    ))

    return sections


def _make_sutter_health_sections() -> list[SeatSection]:
    """Real section layout for Sutter Health Park (temporary A's home)."""
    sections = []

    sections.append(SeatSection(
        name='1B Field (Sec 112-118)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=85, distance_max=190,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=180, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 106-111)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=50, distance_max=110,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=240, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 103-105)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=40, distance_max=80,
        angle_min=55, angle_max=90,
        height_min=0, height_max=12,
        num_seats=120, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 125-130)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=50, distance_max=110,
        angle_min=22, angle_max=55,
        height_min=0, height_max=10,
        num_seats=240, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='3B Field (Sec 131-137)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=85, distance_max=190,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=180, avg_ticket_price=80,
    ))

    # Sutter Health is a minor-league park — only 2 levels
    sections.append(SeatSection(
        name='1B Upper (Sec 206-212)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=40, distance_max=180,
        angle_min=10, angle_max=45,
        height_min=15, height_max=45,
        num_seats=400, avg_ticket_price=40,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 200-205)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=35, distance_max=100,
        angle_min=50, angle_max=90,
        height_min=15, height_max=45,
        num_seats=300, avg_ticket_price=60,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 213-220)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=40, distance_max=180,
        angle_min=10, angle_max=45,
        height_min=15, height_max=45,
        num_seats=400, avg_ticket_price=40,
    ))

    return sections


def _make_pnc_park_sections() -> list[SeatSection]:
    """Real section layout for PNC Park (opened 2001)."""
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 119-128)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=195,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 112-118)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=115,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 108-111)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=280,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 101-107)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=115,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 130-139)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=195,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 216-224)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=12, angle_max=45,
        height_min=12, height_max=35,
        num_seats=450, avg_ticket_price=70,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 209-215)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=12, height_max=35,
        num_seats=350, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 225-233)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=180,
        angle_min=12, angle_max=45,
        height_min=12, height_max=35,
        num_seats=450, avg_ticket_price=70,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 316-325)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=235,
        angle_min=10, angle_max=45,
        height_min=38, height_max=75,
        num_seats=550, avg_ticket_price=18,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 308-315)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=125,
        angle_min=50, angle_max=90,
        height_min=38, height_max=75,
        num_seats=450, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 326-335)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=235,
        angle_min=10, angle_max=45,
        height_min=38, height_max=75,
        num_seats=550, avg_ticket_price=18,
    ))

    return sections


def _make_petco_park_sections() -> list[SeatSection]:
    """Real section layout for Petco Park (opened 2004)."""
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 117-126)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 110-116)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 106-109)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=400,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 101-105)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 128-137)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=150,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 210-218)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 203-209)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 219-227)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 310-320)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=600, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 302-309)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=38, height_max=78,
        num_seats=500, avg_ticket_price=35,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 321-330)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=38, height_max=78,
        num_seats=600, avg_ticket_price=25,
    ))

    return sections


def _make_tmobile_park_sections() -> list[SeatSection]:
    """Real section layout for T-Mobile Park (opened 1999). Retractable roof."""
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 118-128)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 112-117)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 108-111)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=320,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 133-138)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 139-148)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=120,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 218-228)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 210-217)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=115,
        angle_min=55, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 229-239)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 318-330)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=20,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 308-317)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=30,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 331-343)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=20,
    ))

    return sections


def _make_busch_stadium_sections() -> list[SeatSection]:
    """Real section layout for Busch Stadium (opened 2006)."""
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 145-155)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=130,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 138-144)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=220,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 134-137)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=350,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 127-133)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=220,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 157-167)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=130,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 245-255)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=90,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 237-244)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=140,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 256-266)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=90,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 345-358)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=22,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 336-344)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=32,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 359-370)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=22,
    ))

    return sections


def _make_globe_life_sections() -> list[SeatSection]:
    """Real section layout for Globe Life Field (opened 2020). Retractable roof."""
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 12-19)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 6-11)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 1-5)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=400,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 25-30)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 31-37)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=150,
    ))

    sections.append(SeatSection(
        name='1B Mezzanine (Sec 112-119)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=90,
    ))
    sections.append(SeatSection(
        name='Behind Plate Mezzanine (Sec 105-111)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=130,
    ))
    sections.append(SeatSection(
        name='3B Mezzanine (Sec 120-128)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=90,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 212-222)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=22,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 204-211)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=30,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 223-233)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=22,
    ))

    return sections


def _make_rogers_centre_sections() -> list[SeatSection]:
    """Real section layout for Rogers Centre (opened 1989). Retractable roof."""
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 118-126)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 112-117)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 108-111)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=300,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 126-131)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 132-140)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B 200 Level (Sec 218-226)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=65,
    ))
    sections.append(SeatSection(
        name='Behind Plate 200 Level (Sec 210-217)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='3B 200 Level (Sec 227-237)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=65,
    ))

    sections.append(SeatSection(
        name='1B 500 Level (Sec 518-528)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=45, height_max=90,
        num_seats=650, avg_ticket_price=18,
    ))
    sections.append(SeatSection(
        name='Behind Plate 500 Level (Sec 510-517)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=45, distance_max=140,
        angle_min=50, angle_max=90,
        height_min=45, height_max=90,
        num_seats=500, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='3B 500 Level (Sec 529-538)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=45, height_max=90,
        num_seats=650, avg_ticket_price=18,
    ))

    return sections


def _make_target_field_sections() -> list[SeatSection]:
    """Real section layout for Target Field (opened 2010)."""
    sections = []

    sections.append(SeatSection(
        name='1B Field (Sec 110-120)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 104-109)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 101-103, Diamond Box)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=280,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 121-127)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='3B Field (Sec 128-137)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 210-218)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=70,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 203-209)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=110,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 219-228)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=70,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 310-320)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=40, height_max=78,
        num_seats=600, avg_ticket_price=18,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 303-309)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=40, height_max=78,
        num_seats=500, avg_ticket_price=25,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 321-330)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=40, height_max=78,
        num_seats=600, avg_ticket_price=18,
    ))

    return sections


def _make_rate_field_sections() -> list[SeatSection]:
    """Real section layout for Rate Field (opened 1991)."""
    sections = []

    sections.append(SeatSection(
        name='1B Lower (Sec 122-132)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 116-121)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 112-115)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=220,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 137-142)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='3B Lower (Sec 143-153)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=80,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 222-232)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=55,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 214-221)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 233-243)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=55,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 522-534)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=12,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 514-521)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=18,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 535-546)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=650, avg_ticket_price=12,
    ))

    return sections


def _make_loan_depot_sections() -> list[SeatSection]:
    """Real section layout for loanDepot park (opened 2012). Retractable roof."""
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 10-17)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=205,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 4-9)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 1-3)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=150, avg_ticket_price=250,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 23-28)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=150,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 29-37)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=205,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=80,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 210-218)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=55,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 203-209)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=300, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 219-227)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=450, avg_ticket_price=55,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 310-320)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=40, height_max=78,
        num_seats=600, avg_ticket_price=15,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 303-309)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=130,
        angle_min=50, angle_max=90,
        height_min=40, height_max=78,
        num_seats=500, avg_ticket_price=22,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 321-330)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=240,
        angle_min=10, angle_max=45,
        height_min=40, height_max=78,
        num_seats=600, avg_ticket_price=15,
    ))

    return sections


def _make_american_family_sections() -> list[SeatSection]:
    """Real section layout for American Family Field (opened 2001). Retractable roof."""
    sections = []

    sections.append(SeatSection(
        name='1B Field (Sec 113-122)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=95, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 107-112)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 103-106)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=280,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 125-130)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=180,
    ))
    sections.append(SeatSection(
        name='3B Field (Sec 131-140)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=95, distance_max=210,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=220, avg_ticket_price=100,
    ))

    sections.append(SeatSection(
        name='1B Loge (Sec 213-222)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=190,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=70,
    ))
    sections.append(SeatSection(
        name='Behind Plate Loge (Sec 206-212)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=100,
    ))
    sections.append(SeatSection(
        name='3B Loge (Sec 223-232)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=190,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=70,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 413-424)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=40, height_max=82,
        num_seats=650, avg_ticket_price=15,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 405-412)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=82,
        num_seats=500, avg_ticket_price=22,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 425-436)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=250,
        angle_min=10, angle_max=45,
        height_min=40, height_max=82,
        num_seats=650, avg_ticket_price=15,
    ))

    return sections


def _make_nationals_park_sections() -> list[SeatSection]:
    """Real section layout for Nationals Park (opened 2008)."""
    sections = []

    sections.append(SeatSection(
        name='1B Baseline (Sec 115-124)', section_id='1B-DUG',
        side='1B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='1B Infield (Sec 108-114)', section_id='1B-FB1',
        side='1B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='Behind Plate (Sec 104-107, PNC Diamond Club)', section_id='HOME-F',
        side='HOME', level='field',
        distance_min=45, distance_max=85,
        angle_min=55, angle_max=90,
        height_min=0, height_max=15,
        num_seats=160, avg_ticket_price=350,
    ))
    sections.append(SeatSection(
        name='3B Infield (Sec 127-133)', section_id='3B-FB1',
        side='3B', level='field',
        distance_min=55, distance_max=120,
        angle_min=20, angle_max=55,
        height_min=0, height_max=10,
        num_seats=280, avg_ticket_price=200,
    ))
    sections.append(SeatSection(
        name='3B Baseline (Sec 134-143)', section_id='3B-DUG',
        side='3B', level='field',
        distance_min=90, distance_max=200,
        angle_min=0, angle_max=25,
        height_min=0, height_max=8,
        num_seats=200, avg_ticket_price=120,
    ))

    sections.append(SeatSection(
        name='1B Club (Sec 215-224)', section_id='1B-LB1',
        side='1B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))
    sections.append(SeatSection(
        name='Behind Plate Club (Sec 207-214)', section_id='HOME-B',
        side='HOME', level='lower',
        distance_min=50, distance_max=120,
        angle_min=50, angle_max=90,
        height_min=12, height_max=36,
        num_seats=350, avg_ticket_price=120,
    ))
    sections.append(SeatSection(
        name='3B Club (Sec 225-235)', section_id='3B-LB1',
        side='3B', level='lower',
        distance_min=40, distance_max=185,
        angle_min=12, angle_max=45,
        height_min=12, height_max=36,
        num_seats=480, avg_ticket_price=80,
    ))

    sections.append(SeatSection(
        name='1B Upper (Sec 315-326)', section_id='1B-UB',
        side='1B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=20,
    ))
    sections.append(SeatSection(
        name='Behind Plate Upper (Sec 307-314)', section_id='HOME-U',
        side='HOME', level='upper',
        distance_min=40, distance_max=135,
        angle_min=50, angle_max=90,
        height_min=40, height_max=80,
        num_seats=500, avg_ticket_price=28,
    ))
    sections.append(SeatSection(
        name='3B Upper (Sec 327-337)', section_id='3B-UB',
        side='3B', level='upper',
        distance_min=50, distance_max=245,
        angle_min=10, angle_max=45,
        height_min=40, height_max=80,
        num_seats=600, avg_ticket_price=20,
    ))

    return sections


def yankee_stadium() -> Stadium:
    """Yankee Stadium geometry (opened 2009)."""
    stadium = Stadium(
        name='Yankee Stadium',
        city='New York',
        team='New York Yankees',
        altitude_ft=23,
        avg_temperature_f=75,
        lf_distance=318,
        cf_distance=408,
        rf_distance=314,
        backstop_distance=52,
    )
    stadium.sections = _make_yankee_stadium_sections()
    return stadium


def fenway_park() -> Stadium:
    """Fenway Park geometry (opened 1912)."""
    stadium = Stadium(
        name='Fenway Park',
        city='Boston',
        team='Boston Red Sox',
        altitude_ft=21,
        avg_temperature_f=72,
        lf_distance=310,  # Green Monster
        cf_distance=390,
        rf_distance=302,  # Pesky's Pole
        backstop_distance=60,
    )
    stadium.sections = _make_fenway_park_sections()
    # Fenway-specific: compact foul territory — scale ALL sections proportionally
    # to avoid gaps between field and upper levels
    scale = 0.85
    for s in stadium.sections:
        s.distance_min *= scale
        s.distance_max *= scale
    return stadium


def dodger_stadium() -> Stadium:
    """Dodger Stadium geometry."""
    stadium = Stadium(
        name='Dodger Stadium',
        city='Los Angeles',
        team='Los Angeles Dodgers',
        altitude_ft=515,
        avg_temperature_f=78,
        lf_distance=330,
        cf_distance=395,
        rf_distance=330,
        backstop_distance=55,
    )
    stadium.sections = _make_dodger_stadium_sections()
    return stadium


def wrigley_field() -> Stadium:
    """Wrigley Field geometry."""
    stadium = Stadium(
        name='Wrigley Field',
        city='Chicago',
        team='Chicago Cubs',
        altitude_ft=600,
        avg_temperature_f=73,
        lf_distance=355,
        cf_distance=400,
        rf_distance=353,
        backstop_distance=56,
    )
    stadium.sections = _make_wrigley_field_sections()
    # Wrigley-specific: compact foul territory — scale ALL sections proportionally
    scale = 0.88
    for s in stadium.sections:
        s.distance_min *= scale
        s.distance_max *= scale
    return stadium


def coors_field() -> Stadium:
    """Coors Field geometry (high altitude!)."""
    stadium = Stadium(
        name='Coors Field',
        city='Denver',
        team='Colorado Rockies',
        altitude_ft=5200,  # Field level elevation (5280 is upper deck purple row)
        avg_temperature_f=76,
        lf_distance=347,
        cf_distance=415,
        rf_distance=350,
        backstop_distance=56,
    )
    stadium.sections = _make_coors_field_sections()
    return stadium


# All 30 MLB Stadiums (real dimensions from public park data)
def chase_field():
    stadium = Stadium(name='Chase Field', city='Phoenix', team='Arizona Diamondbacks',
        altitude_ft=1086, avg_temperature_f=78,
        lf_distance=330, cf_distance=407, rf_distance=335, backstop_distance=54)
    stadium.sections = _make_chase_field_sections()
    return stadium

def truist_park():
    stadium = Stadium(
        name='Truist Park', city='Atlanta', team='Atlanta Braves',
        altitude_ft=1050, avg_temperature_f=78,
        lf_distance=335, cf_distance=400, rf_distance=325, backstop_distance=55,
    )
    stadium.sections = _make_truist_park_sections()
    return stadium

def camden_yards():
    stadium = Stadium(name='Oriole Park at Camden Yards', city='Baltimore', team='Baltimore Orioles',
        altitude_ft=130, avg_temperature_f=76,
        lf_distance=333, cf_distance=410, rf_distance=318, backstop_distance=57)
    stadium.sections = _make_camden_yards_sections()
    return stadium

def citizens_bank():
    stadium = Stadium(
        name='Citizens Bank Park', city='Philadelphia', team='Philadelphia Phillies',
        altitude_ft=20, avg_temperature_f=76,
        lf_distance=329, cf_distance=401, rf_distance=330, backstop_distance=55,
    )
    stadium.sections = _make_citizens_bank_sections()
    return stadium

def great_american():
    stadium = Stadium(name='Great American Ball Park', city='Cincinnati', team='Cincinnati Reds',
        altitude_ft=683, avg_temperature_f=76,
        lf_distance=328, cf_distance=404, rf_distance=325, backstop_distance=54)
    stadium.sections = _make_great_american_sections()
    return stadium

def progressive_field():
    stadium = Stadium(name='Progressive Field', city='Cleveland', team='Cleveland Guardians',
        altitude_ft=620, avg_temperature_f=73,
        lf_distance=325, cf_distance=405, rf_distance=325, backstop_distance=55)
    stadium.sections = _make_progressive_field_sections()
    return stadium

def comerica_park():
    stadium = Stadium(name='Comerica Park', city='Detroit', team='Detroit Tigers',
        altitude_ft=585, avg_temperature_f=73,
        lf_distance=342, cf_distance=412, rf_distance=330, backstop_distance=55)
    stadium.sections = _make_comerica_park_sections()
    return stadium

def daikin_park():
    stadium = Stadium(
        name='Daikin Park', city='Houston', team='Houston Astros',
        altitude_ft=30, avg_temperature_f=82,
        lf_distance=315, cf_distance=409, rf_distance=326, backstop_distance=54,
    )
    stadium.sections = _make_daikin_park_sections()
    return stadium

def kauffman_stadium():
    stadium = Stadium(name='Kauffman Stadium', city='Kansas City', team='Kansas City Royals',
        altitude_ft=750, avg_temperature_f=77,
        lf_distance=330, cf_distance=410, rf_distance=330, backstop_distance=55)
    stadium.sections = _make_kauffman_stadium_sections()
    return stadium

def angel_stadium():
    stadium = Stadium(name='Angel Stadium', city='Anaheim', team='Los Angeles Angels',
        altitude_ft=160, avg_temperature_f=75,
        lf_distance=330, cf_distance=400, rf_distance=330, backstop_distance=55)
    stadium.sections = _make_angel_stadium_sections()
    return stadium

def citi_field():
    stadium = Stadium(
        name='Citi Field', city='New York', team='New York Mets',
        altitude_ft=54, avg_temperature_f=75,
        lf_distance=335, cf_distance=408, rf_distance=330, backstop_distance=55,
    )
    stadium.sections = _make_citi_field_sections()
    return stadium

def sutter_health_park():
    stadium = Stadium(name='Sutter Health Park', city='Sacramento', team='Athletics',
        altitude_ft=33, avg_temperature_f=80,
        lf_distance=330, cf_distance=403, rf_distance=325, backstop_distance=55)
    stadium.sections = _make_sutter_health_sections()
    return stadium

def pnc_park():
    stadium = Stadium(name='PNC Park', city='Pittsburgh', team='Pittsburgh Pirates',
        altitude_ft=730, avg_temperature_f=73,
        lf_distance=325, cf_distance=399, rf_distance=320, backstop_distance=54)
    stadium.sections = _make_pnc_park_sections()
    return stadium

def petco_park():
    stadium = Stadium(name='Petco Park', city='San Diego', team='San Diego Padres',
        altitude_ft=13, avg_temperature_f=72,
        lf_distance=334, cf_distance=396, rf_distance=322, backstop_distance=55)
    stadium.sections = _make_petco_park_sections()
    return stadium

def oracle_park():
    stadium = Stadium(
        name='Oracle Park', city='San Francisco', team='San Francisco Giants',
        altitude_ft=63, avg_temperature_f=65,
        lf_distance=339, cf_distance=399, rf_distance=309, backstop_distance=55,
    )
    stadium.sections = _make_oracle_park_sections()
    return stadium

def tmobile_park():
    stadium = Stadium(name='T-Mobile Park', city='Seattle', team='Seattle Mariners',
        altitude_ft=17, avg_temperature_f=65,
        lf_distance=331, cf_distance=405, rf_distance=326, backstop_distance=55)
    stadium.sections = _make_tmobile_park_sections()
    return stadium

def busch_stadium():
    stadium = Stadium(name='Busch Stadium', city='St. Louis', team='St. Louis Cardinals',
        altitude_ft=465, avg_temperature_f=77,
        lf_distance=336, cf_distance=400, rf_distance=335, backstop_distance=55)
    stadium.sections = _make_busch_stadium_sections()
    return stadium

def tropicana_field():
    stadium = Stadium(
        name='Tropicana Field', city='St. Petersburg', team='Tampa Bay Rays',
        altitude_ft=45, avg_temperature_f=72,
        lf_distance=315, cf_distance=404, rf_distance=322, backstop_distance=55,
    )
    stadium.sections = _make_tropicana_field_sections()
    return stadium

def globe_life():
    stadium = Stadium(name='Globe Life Field', city='Arlington', team='Texas Rangers',
        altitude_ft=616, avg_temperature_f=78,
        lf_distance=329, cf_distance=407, rf_distance=326, backstop_distance=55)
    stadium.sections = _make_globe_life_sections()
    return stadium

def rogers_centre():
    stadium = Stadium(name='Rogers Centre', city='Toronto', team='Toronto Blue Jays',
        altitude_ft=250, avg_temperature_f=72,
        lf_distance=328, cf_distance=400, rf_distance=328, backstop_distance=55)
    stadium.sections = _make_rogers_centre_sections()
    return stadium

def target_field():
    stadium = Stadium(name='Target Field', city='Minneapolis', team='Minnesota Twins',
        altitude_ft=815, avg_temperature_f=72,
        lf_distance=339, cf_distance=404, rf_distance=328, backstop_distance=55)
    stadium.sections = _make_target_field_sections()
    return stadium

def rate_field():
    stadium = Stadium(name='Rate Field', city='Chicago', team='Chicago White Sox',
        altitude_ft=595, avg_temperature_f=73,
        lf_distance=330, cf_distance=400, rf_distance=335, backstop_distance=55)
    stadium.sections = _make_rate_field_sections()
    return stadium

def loan_depot():
    stadium = Stadium(name='loanDepot park', city='Miami', team='Miami Marlins',
        altitude_ft=15, avg_temperature_f=83,
        lf_distance=340, cf_distance=400, rf_distance=335, backstop_distance=55)
    stadium.sections = _make_loan_depot_sections()
    return stadium

def american_family():
    stadium = Stadium(name='American Family Field', city='Milwaukee', team='Milwaukee Brewers',
        altitude_ft=600, avg_temperature_f=72,
        lf_distance=344, cf_distance=400, rf_distance=345, backstop_distance=55)
    stadium.sections = _make_american_family_sections()
    return stadium

def nationals_park():
    stadium = Stadium(name='Nationals Park', city='Washington', team='Washington Nationals',
        altitude_ft=30, avg_temperature_f=77,
        lf_distance=336, cf_distance=403, rf_distance=335, backstop_distance=55)
    stadium.sections = _make_nationals_park_sections()
    return stadium


STADIUMS = {
    'yankee_stadium': yankee_stadium,
    'fenway_park': fenway_park,
    'dodger_stadium': dodger_stadium,
    'wrigley_field': wrigley_field,
    'coors_field': coors_field,
    'chase_field': chase_field,
    'truist_park': truist_park,
    'camden_yards': camden_yards,
    'citizens_bank': citizens_bank,
    'great_american': great_american,
    'progressive_field': progressive_field,
    'comerica_park': comerica_park,
    'minute_maid': daikin_park,
    'kauffman_stadium': kauffman_stadium,
    'angel_stadium': angel_stadium,
    'citi_field': citi_field,
    'oakland_coliseum': sutter_health_park,
    'pnc_park': pnc_park,
    'petco_park': petco_park,
    'oracle_park': oracle_park,
    'tmobile_park': tmobile_park,
    'busch_stadium': busch_stadium,
    'tropicana_field': tropicana_field,
    'globe_life': globe_life,
    'rogers_centre': rogers_centre,
    'target_field': target_field,
    'guaranteed_rate': rate_field,
    'loan_depot': loan_depot,
    'american_family': american_family,
    'nationals_park': nationals_park,
}
