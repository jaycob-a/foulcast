"""
MLB Stats API Integration.

Pulls live schedules, lineups, probable pitchers, and rosters
for any upcoming MLB game.
"""
import statsapi
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from .log import get_logger

logger = get_logger(__name__)


TEAM_IDS = {
    'ARI': 109, 'ATL': 144, 'BAL': 110, 'BOS': 111, 'CHC': 112,
    'CWS': 145, 'CIN': 113, 'CLE': 114, 'COL': 115, 'DET': 116,
    'HOU': 117, 'KC': 118, 'LAA': 108, 'LAD': 119, 'MIA': 146,
    'MIL': 158, 'MIN': 142, 'NYM': 121, 'NYY': 147, 'OAK': 133,
    'PHI': 143, 'PIT': 134, 'SD': 135, 'SF': 137, 'SEA': 136,
    'STL': 138, 'TB': 139, 'TEX': 140, 'TOR': 141, 'WSH': 120,
}

TEAM_ID_TO_ABBREV = {v: k for k, v in TEAM_IDS.items()}

# Map team names to stadium keys (matches stadium.py)
TEAM_STADIUM_MAP = {
    109: 'chase_field',          110: 'camden_yards',        111: 'fenway_park',
    112: 'wrigley_field',        113: 'great_american',      114: 'progressive_field',
    115: 'coors_field',          116: 'comerica_park',       117: 'minute_maid',
    118: 'kauffman_stadium',     108: 'angel_stadium',       119: 'dodger_stadium',
    121: 'citi_field',           133: 'oakland_coliseum',    134: 'pnc_park',
    135: 'petco_park',           136: 'tmobile_park',        137: 'oracle_park',
    138: 'busch_stadium',        139: 'tropicana_field',     140: 'globe_life',
    141: 'rogers_centre',        142: 'target_field',        143: 'citizens_bank',
    144: 'truist_park',          145: 'guaranteed_rate',     146: 'loan_depot',
    147: 'yankee_stadium',       158: 'american_family',     120: 'nationals_park',
}


# Second home parks: venues where a club plays real home games that are not its
# primary park. TEAM_STADIUM_MAP is keyed by team alone and cannot express this,
# so those games silently simulate against the wrong geometry.
#
# The Athletics' 2026 schedule is the live case — 51 home dates at Sutter Health
# Park, 6 at Las Vegas Ballpark (NOTES_STEP5_6.md). Keys are
# (team_id, normalized venue substring) so a venue only redirects for the club
# it belongs to, and matching is on a substring of the normalized name so a
# sponsorship rename does not break the lookup.
ALTERNATE_HOME_VENUES = {
    (133, 'lasvegasballpark'): 'las_vegas_ballpark',
}


def _normalize_venue(name: str) -> str:
    """Lowercase and strip everything but letters and digits.

    Venue strings carry sponsor prefixes that change between seasons — MLB
    lists the Dodgers' park as "UNIQLO Field at Dodger Stadium" in 2026 — so
    matching is done on a normalized substring rather than equality.
    """
    return ''.join(ch for ch in name.lower() if ch.isalnum())


def alternate_home_stadium_key(home_id: int, venue_name: str | None) -> str | None:
    """Stadium key if this game is at a club's *second* home park, else None.

    Distinct from a neutral-site game: these are the home team's own dates,
    played at a park the model has geometry for.
    """
    if not venue_name:
        return None
    norm = _normalize_venue(venue_name)
    for (tid, needle), key in ALTERNATE_HOME_VENUES.items():
        if tid == home_id and needle in norm:
            return key
    return None


def resolve_stadium_key(
    home_id: int, venue_name: str | None = None,
    default: str | None = 'yankee_stadium',
) -> str | None:
    """Stadium key for a game, preferring the venue actually played at.

    Falls back to the club's primary park when the venue is unknown or is that
    primary park under any name. Callers that have a venue string should pass
    it; callers that do not get the old team-only behaviour.
    """
    alt = alternate_home_stadium_key(home_id, venue_name)
    if alt is not None:
        return alt
    return TEAM_STADIUM_MAP.get(home_id, default)


@dataclass
class GameInfo:
    """Information about an upcoming MLB game."""
    game_id: int
    game_date: str
    game_time: str
    status: str
    home_team: str
    home_team_id: int
    away_team: str
    away_team_id: int
    home_pitcher: str
    away_pitcher: str
    stadium_key: str
    venue_name: str


@dataclass
class LineupPlayer:
    """A player in a starting lineup."""
    name: str
    mlb_id: int
    position: str
    batting_order: int
    bats: str  # 'L', 'R', 'S'


def get_todays_games(date: str | None = None) -> list[GameInfo]:
    """Get all MLB games for a given date (default: today)."""
    if date is None:
        date = datetime.now().strftime('%m/%d/%Y')

    schedule = statsapi.schedule(date=date)
    games = []

    for g in schedule:
        home_id = g.get('home_id', 0)
        venue_name = g.get('venue_name', 'Unknown')
        games.append(GameInfo(
            game_id=g['game_id'],
            game_date=g.get('game_date', date),
            game_time=g.get('game_time', 'TBD') if 'game_time' in g else 'TBD',
            status=g.get('status', 'Unknown'),
            home_team=g.get('home_name', 'Unknown'),
            home_team_id=home_id,
            away_team=g.get('away_name', 'Unknown'),
            away_team_id=g.get('away_id', 0),
            home_pitcher=g.get('home_probable_pitcher', 'TBD'),
            away_pitcher=g.get('away_probable_pitcher', 'TBD'),
            stadium_key=resolve_stadium_key(home_id, venue_name),
            venue_name=venue_name,
        ))

    return games


def get_team_roster(team_id: int) -> list[dict]:
    """Get the active roster for a team."""
    try:
        data = statsapi.get('team_roster', {'teamId': team_id, 'rosterType': 'active'})
        players = []
        for entry in data.get('roster', []):
            person = entry.get('person', {})
            position = entry.get('position', {})
            players.append({
                'name': person.get('fullName', ''),
                'id': person.get('id', 0),
                'position': position.get('abbreviation', ''),
                'type': position.get('type', ''),
            })
        return players
    except Exception as e:
        logger.warning("Could not fetch roster for team %d: %s", team_id, e)
        return []


def get_player_info(player_id: int) -> dict:
    """Get detailed info for a single player (batting side, etc)."""
    try:
        data = statsapi.get('person', {'personId': player_id})
        person = data['people'][0] if data.get('people') else {}
        return {
            'name': person.get('fullName', ''),
            'id': player_id,
            'bats': person.get('batSide', {}).get('code', 'R'),
            'throws': person.get('pitchHand', {}).get('code', 'R'),
            'position': person.get('primaryPosition', {}).get('abbreviation', ''),
        }
    except Exception:
        return {'name': '', 'id': player_id, 'bats': 'R', 'throws': 'R', 'position': ''}


def get_lineup(game_id: int, team_id: int) -> list[LineupPlayer]:
    """
    Try to get the starting lineup for a game.
    Falls back to projected lineup from roster if lineup not yet posted.
    """
    # Try boxscore for posted lineups
    try:
        box = statsapi.boxscore_data(game_id)
        # Determine which side (home/away) corresponds to the requested team_id
        team_key = None
        for key in ['home', 'away']:
            team_info = box.get(key, {}).get('teamStats', box.get(f'{key}TeamStats', {}))
            box_team = box.get(f'{key}Team', box.get(key, {}))
            box_team_id = box_team.get('id', box_team.get('team', {}).get('id', 0))
            if box_team_id == team_id:
                team_key = key
                break

        if team_key:
            order = box.get(f'{team_key}BattingOrder', [])
            players = []
            for i, pid in enumerate(order):
                pinfo = get_player_info(pid)
                players.append(LineupPlayer(
                    name=pinfo['name'],
                    mlb_id=pid,
                    position=pinfo['position'],
                    batting_order=i + 1,
                    bats=pinfo['bats'],
                ))
            if players:
                return players
    except Exception:
        pass

    # Fallback: get roster and pick likely starters (position players)
    return get_projected_lineup(team_id)


def get_projected_lineup(team_id: int) -> list[LineupPlayer]:
    """Build a projected lineup from the active roster."""
    roster = get_team_roster(team_id)
    position_players = [p for p in roster if p['type'] in ('Infielder', 'Outfielder', 'Catcher', 'Hitter')]

    lineup = []
    for i, p in enumerate(position_players[:9]):
        info = get_player_info(p['id'])
        lineup.append(LineupPlayer(
            name=info['name'],
            mlb_id=info['id'],
            position=info['position'],
            batting_order=i + 1,
            bats=info.get('bats', 'R'),
        ))

    return lineup


def get_pitcher_info(pitcher_name: str, team_id: int) -> dict:
    """Get pitcher details from roster."""
    roster = get_team_roster(team_id)
    for p in roster:
        if p['type'] == 'Pitcher' and pitcher_name.lower() in p['name'].lower():
            info = get_player_info(p['id'])
            return info
    return {'name': pitcher_name, 'throws': 'R'}


def get_upcoming_games(days_ahead: int = 7) -> list[GameInfo]:
    """Get games for the next N days."""
    all_games = []
    for i in range(days_ahead):
        date = (datetime.now() + timedelta(days=i)).strftime('%m/%d/%Y')
        games = get_todays_games(date)
        # Only include scheduled/pre-game
        for g in games:
            if g.status in ('Scheduled', 'Pre-Game', 'Warmup', 'Final', 'In Progress'):
                all_games.append(g)
    return all_games
