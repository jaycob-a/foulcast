"""Shared test fixtures."""
import numpy as np
import pytest

from foulball.batter_profiles import (
    BatterFoulProfile,
    YANKEES_2024_PROFILES,
    RED_SOX_2024_PROFILES,
    PITCHER_PROFILES,
)
from foulball.stadium import STADIUMS


@pytest.fixture
def seeded_rng():
    """Set a deterministic seed and restore state after the test."""
    state = np.random.get_state()
    np.random.seed(42)
    yield
    np.random.set_state(state)


@pytest.fixture
def yankees_lineup():
    """Full Yankees 2024 lineup as a list of BatterFoulProfile."""
    return list(YANKEES_2024_PROFILES.values())


@pytest.fixture
def red_sox_lineup():
    """Full Red Sox 2024 lineup as a list of BatterFoulProfile."""
    return list(RED_SOX_2024_PROFILES.values())


@pytest.fixture
def yankee_stadium():
    """Yankee Stadium instance."""
    return STADIUMS['yankee_stadium']()


@pytest.fixture
def fenway_park():
    """Fenway Park instance."""
    return STADIUMS['fenway_park']()


@pytest.fixture
def coors_field():
    """Coors Field instance."""
    return STADIUMS['coors_field']()


@pytest.fixture
def cole_pitch_mix():
    """Gerrit Cole's pitch mix."""
    return PITCHER_PROFILES['Gerrit Cole']['pitch_mix']


@pytest.fixture
def bello_pitch_mix():
    """Brayan Bello's pitch mix."""
    return PITCHER_PROFILES['Brayan Bello']['pitch_mix']
