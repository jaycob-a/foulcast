"""Shared test fixtures, and the two claim patterns more than one module
reads for.

`SAFE_WORD` and `ACCURACY_CLAIM` live here rather than beside the tests that
grep with them because the rules they carry are not about the built pages in
particular — they are about anything this project puts in front of a visitor.
`tests/test_site.py` applies them to the 33 built pages and
`tests/test_endpoints.py` applies them to every public URL the server answers
on. Two copies of either pattern would be two definitions of the constraint.
"""
import re

import numpy as np
import pytest

from foulball.batter_profiles import (
    BatterFoulProfile,
    YANKEES_2024_PROFILES,
    RED_SOX_2024_PROFILES,
    PITCHER_PROFILES,
)
from foulball.stadium import STADIUMS

# Word-bounded, so it catches safe/safer/safest/safety and does not fire on
# "SafecoField.html" — the filename of Clem's T-Mobile Park page, which is a
# real source URL and stays.
SAFE_WORD = re.compile(r'(?i)\bsafe(?:r|st|ty|ly|guard(?:ed|s)?)?\b')

# "precise" is deliberately absent: one club's own statement, quoted on the
# Kauffman page, is that its map cannot show "the precise location of the
# netting" — which is the opposite of an accuracy claim.
ACCURACY_CLAIM = re.compile(
    r'(?i)\b(accurate|accuracy|proven|guaranteed|reliable|'
    r'correlation|r\s*=\s*0\.\d)\b')


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
