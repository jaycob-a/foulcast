"""Root conftest — ensures foulball package is importable."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def pytest_addoption(parser):
    """Register --regen-golden here: pytest only reads pytest_addoption from the
    rootdir conftest, so declaring it inside tests/test_golden_games.py left the
    documented regeneration command failing with 'unrecognized arguments'."""
    parser.addoption("--regen-golden", action="store_true", default=False)
