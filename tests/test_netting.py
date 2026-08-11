"""
Netting layer: the data, the join, and the two opposite readings of it.

These tests are mostly about restraint. The interesting failure mode for this
layer is not "the netting is in the wrong place" — it is "the model claimed to
know something no source says", so most of what follows pins down where the
model must stay silent.
"""
import numpy as np
import pytest

from foulball import netting as N
from foulball.stadium import STADIUMS
from foulball.matchup_engine import predict_game_fouls
from foulball.batter_profiles import RED_SOX_2024_PROFILES, PITCHER_PROFILES


# Parks whose published extent joins onto their zone table. Locked as a list
# rather than a count so that a park moving in or out is a named diff.
MAPPED_PARKS = {
    'fenway_park', 'dodger_stadium', 'coors_field', 'truist_park',
    'camden_yards', 'citizens_bank', 'great_american', 'progressive_field',
    'minute_maid', 'angel_stadium', 'pnc_park', 'oracle_park', 'globe_life',
    'guaranteed_rate',
}

# Parks where SOURCED_DATA.md itself has no usable section-level extent.
SOURCE_GAP_PARKS = {
    'wrigley_field',        # published in words, no numbers
    'kauffman_stadium',     # club declines to publish sections
    'citi_field',           # nothing on the club's pages
    'loan_depot',           # netting published only as an image
    'oakland_coliseum',     # Sutter Health Park — no source at all
    'las_vegas_ballpark',   # no source at all
    'tropicana_field',      # club page contradicts itself
    'comerica_park',        # arc endpoints on a wrapping numbering
}

# Parks with a good club page whose section numbers cannot be reconciled with
# this model's printed labels. The netting data is not what is wrong here.
JOIN_GAP_PARKS = {
    'yankee_stadium', 'chase_field', 'petco_park', 'tmobile_park',
    'busch_stadium', 'rogers_centre', 'target_field', 'american_family',
    'nationals_park',
}


class TestTheDataItself:
    """Every entry is transcription, and every entry says where it came from."""

    def test_every_park_in_the_registry_has_an_entry(self):
        assert set(N.PARK_NETTING) == set(STADIUMS), (
            "PARK_NETTING and STADIUMS have drifted apart: "
            f"{set(N.PARK_NETTING) ^ set(STADIUMS)}"
        )

    @pytest.mark.parametrize('key', sorted(N.PARK_NETTING))
    def test_entry_carries_source_and_year(self, key):
        p = N.PARK_NETTING[key]
        assert p.published, f"{key}: no published extent recorded, not even a gap"
        assert p.source, f"{key}: no source"
        assert p.source_kind in ('primary', 'secondary_unverified', 'none')
        assert p.retrieved, f"{key}: no retrieval date"
        # A year may legitimately be absent — an undated page is a fact about
        # the source — but then the basis has to say so.
        assert p.year is not None or p.year_basis, (
            f"{key}: no year and no explanation of why there is no year"
        )

    @pytest.mark.parametrize('key', sorted(N.PARK_NETTING))
    def test_a_gap_park_publishes_no_ranges(self, key):
        """A park with a gap must not carry netted sections by the back door."""
        p = N.PARK_NETTING[key]
        if p.gap_kind is not None:
            assert not p.ranges, (
                f"{key} is recorded as a {p.gap_kind} gap but carries "
                f"{len(p.ranges)} netted range(s)"
            )

    @pytest.mark.parametrize('key', sorted(N.PARK_NETTING))
    def test_secondary_figures_are_never_applied(self, key):
        """Weak sources are recorded, never used.

        Kauffman, Citi Field and loanDepot all have a secondary figure. Each
        is unverified, and two of the three are six years old at parks where
        the netting elsewhere in the league has demonstrably moved since. They
        are held so the gap can be closed by re-checking one page, and they
        never reach a zone.
        """
        p = N.PARK_NETTING[key]
        if p.secondary:
            assert p.gap_kind is not None, (
                f"{key} carries a secondary figure but is not marked as a gap"
            )
            assert p.secondary_source, f"{key}: secondary figure with no source"

    def test_the_only_partial_flag_in_the_league_is_target_126(self):
        flagged = {k: p.partial_labels for k, p in N.PARK_NETTING.items()
                   if p.partial_labels}
        assert flagged == {'target_field': ('126',)}, (
            "SOURCED_DATA.md records exactly one club-published partial-"
            f"coverage flag; found {flagged}"
        )

    def test_every_interpretation_is_declared(self):
        """Turning wording into numbers is the only editorial act in the file.

        Each such call carries an `interpretation` string, and this is the
        list of them. It is asserted so that a new one cannot be added
        silently.
        """
        parks = sorted({k for k, _, _ in N.interpretations()})
        assert parks == ['camden_yards', 'dodger_stadium', 'fenway_park',
                         'pnc_park', 'rogers_centre', 'yankee_stadium']


class TestTheJoin:
    """Which parks map, which show a gap, and why."""

    @pytest.mark.parametrize('key', sorted(STADIUMS))
    def test_park_lands_in_its_expected_bucket(self, key):
        j = N.join_park(STADIUMS[key](), key)
        expected = ('mapped' if key in MAPPED_PARKS
                    else 'source_gap' if key in SOURCE_GAP_PARKS
                    else 'join_gap')
        assert j.status == expected, (
            f"{key}: expected {expected}, got {j.status} — {j.gap_detail}"
        )

    def test_the_buckets_cover_the_fleet_exactly_once(self):
        assert MAPPED_PARKS | SOURCE_GAP_PARKS | JOIN_GAP_PARKS == set(STADIUMS)
        assert not (MAPPED_PARKS & SOURCE_GAP_PARKS)
        assert not (MAPPED_PARKS & JOIN_GAP_PARKS)
        assert not (SOURCE_GAP_PARKS & JOIN_GAP_PARKS)

    @pytest.mark.parametrize('key', sorted(STADIUMS))
    def test_every_zone_gets_a_status(self, key):
        """No zone is ever missing from the map, whatever the outcome."""
        st = STADIUMS[key]()
        assert set(st.zone_netting) == {s.section_id for s in st.sections}

    @pytest.mark.parametrize('key', sorted(SOURCE_GAP_PARKS | JOIN_GAP_PARKS))
    def test_a_gap_park_marks_every_zone_unknown(self, key):
        """The headline rule: a gap shows as a gap, not as 'no netting'."""
        st = STADIUMS[key]()
        statuses = {z.status for z in st.zone_netting.values()}
        assert statuses == {'unknown'}, (
            f"{key} has no usable netting data but reports {statuses}"
        )
        assert not any(st.is_netted(s.section_id) for s in st.sections)

    @pytest.mark.parametrize('key', sorted(SOURCE_GAP_PARKS | JOIN_GAP_PARKS))
    def test_a_gap_park_says_why(self, key):
        j = N.join_park(STADIUMS[key](), key)
        assert j.gap_kind and j.gap_detail
        for z in j.zones.values():
            assert j.gap_detail.split(':')[0][:20] in z.reason or z.reason

    @pytest.mark.parametrize('key', sorted(MAPPED_PARKS))
    def test_a_mapped_park_nets_the_seats_behind_the_plate(self, key):
        """Every published extent in the file runs from behind the plate out.

        This is the guard that rejects nine parks, restated as a property of
        the ones that survive it.
        """
        st = STADIUMS[key]()
        home_field = [s for s in st.sections
                      if s.side == 'HOME' and s.level == 'field']
        for sec in home_field:
            z = st.zone_netting[sec.section_id]
            assert z.status in ('netted', 'unknown'), (
                f"{key}/{sec.section_id} is behind the plate at field level "
                f"and came out {z.status}"
            )

    def test_fenway_is_netted_field_boxes_and_open_loge(self):
        """The worked example: FB79 → FB9 across five field-box zones."""
        st = STADIUMS['fenway_park']()
        z = st.zone_netting
        assert z['HOME-F'].status == 'netted'
        assert z['1B-FB1'].status == 'netted'
        assert z['3B-FB1'].status == 'netted'
        assert z['1B-DUG'].status == 'netted'
        # FB71-FB79 netted, FB80-FB82 not.
        assert z['3B-DUG'].status == 'partially_netted'
        assert set(z['3B-DUG'].exposed_labels) == {'FB80', 'FB81', 'FB82'}
        # The Loge and Grandstand sit behind the field boxes; a net in front
        # of the boxes does not screen them, and the club lists neither.
        assert z['1B-LB1'].status == 'not_netted'
        assert z['HOME-U'].status == 'not_netted'

    def test_dodger_dugout_club_is_unknown_not_open(self):
        """An unlisted product at the front of the bowl is a gap.

        The Dugout Club is a DG-series product sitting in front of the field
        boxes behind the plate. The netting page never names it, so the model
        may not call it exposed.
        """
        st = STADIUMS['dodger_stadium']()
        assert st.zone_netting['HOME-DC'].status == 'unknown'
        assert st.zone_netting['HOME-F'].status == 'netted'

    def test_yankee_gap_names_the_numbering_clash(self):
        j = N.join_park(STADIUMS['yankee_stadium'](), 'yankee_stadium')
        assert j.gap_kind == 'labels_contradict_model'
        assert 'numbering' in j.gap_detail

    def test_rate_field_nets_the_whole_field_level(self):
        """Pole to pole since 2019, and the join reflects it."""
        st = STADIUMS['guaranteed_rate']()
        field = [s for s in st.sections if s.level == 'field']
        assert field
        for sec in field:
            assert st.zone_netting[sec.section_id].status == 'netted'


@pytest.fixture(scope='module')
def fenway_pred():
    """One half-game at the best-mapped park in the fleet."""
    np.random.seed(42)
    st = STADIUMS['fenway_park']()
    return predict_game_fouls(
        list(RED_SOX_2024_PROFILES.values()), 'Brayan Bello',
        PITCHER_PROFILES['Brayan Bello']['pitch_mix'], st, 200,
    )


class TestOppositeConclusions:
    """One status, two answers: no souvenir, and a safety highlight."""

    def test_netted_sections_are_absent_from_the_catch_ranking(self, fenway_pred):
        ranked = {p.section.section_id for p in fenway_pred.top_sections}
        netted = {p.section.section_id for p in fenway_pred.netted_sections}
        assert netted, "Fenway should have netted sections to exclude"
        assert not (ranked & netted)

    def test_netted_sections_have_no_catchable_fouls(self, fenway_pred):
        for p in fenway_pred.netted_sections:
            assert p.catchable_fouls == 0.0

    def test_netted_sections_keep_every_foul_they_drew(self, fenway_pred):
        """The safety half. Excluding a section from a ranking must not
        delete it from the model — the fouls still arrive, and behind-plate
        remains the busiest part of the park."""
        by_id = {p.section.section_id: p for p in fenway_pred.section_predictions}
        home = by_id['HOME-F']
        assert home.netting_status == 'netted'
        assert home.expected_fouls > 0
        assert home.danger_rating > 0
        # And it is still the busiest section in the park by expected fouls.
        busiest = max(fenway_pred.section_predictions,
                      key=lambda p: p.expected_fouls)
        assert busiest.section.section_id == 'HOME-F'

    def test_partially_netted_sections_stay_in_the_ranking(self, fenway_pred):
        """Part of the zone is open, so the fouls there are still catchable.
        The count is an upper bound and the status says so; dropping the zone
        would be as unsourced as ignoring the net."""
        ranked = {p.section.section_id: p for p in fenway_pred.top_sections}
        assert ranked['3B-DUG'].netting_status == 'partially_netted'
        assert ranked['3B-DUG'].catchable_fouls > 0

    def test_a_gap_park_excludes_nothing(self):
        np.random.seed(42)
        st = STADIUMS['yankee_stadium']()
        pred = predict_game_fouls(
            list(RED_SOX_2024_PROFILES.values()), 'Brayan Bello',
            PITCHER_PROFILES['Brayan Bello']['pitch_mix'], st, 200,
        )
        assert pred.netted_sections == []
        assert all(p.netting_status == 'unknown'
                   for p in pred.section_predictions)
        assert 'not mapped to sections' in pred.netting_note

    def test_the_note_says_which_park_the_source_is_for(self, fenway_pred):
        assert 'redsox' in fenway_pred.netting_note
        assert '2026' in fenway_pred.netting_note

    def test_events_record_netting_separately_from_catchability(self, fenway_pred):
        """A ball into the net and a ball too hot to catch are both
        uncatchable, and the model keeps them distinguishable."""
        netted = [e for e in fenway_pred.all_events if e.hit_netting]
        assert netted
        assert all(not e.is_catchable for e in netted)
        # Not every uncatchable ball is a netting strike.
        assert any(not e.is_catchable and not e.hit_netting
                   for e in fenway_pred.all_events)


class TestNettingMovesNoGeometry:
    """The layer must not disturb anything Step 9 established."""

    @pytest.mark.parametrize('key', sorted(STADIUMS))
    def test_zone_map_fingerprint_is_unaffected(self, key):
        """Netting is not part of the zone map, so logged observations keep
        their stamp and history is not silently re-read."""
        from foulball.seat_map import zone_map_fingerprint
        st = STADIUMS[key]()
        before = zone_map_fingerprint(st)
        st.zone_netting = {}
        assert zone_map_fingerprint(st) == before

    def test_a_hand_built_stadium_has_no_netting(self):
        """A Stadium built outside the factories claims nothing."""
        from foulball.stadium import Stadium
        st = Stadium(name='nowhere', city='nowhere', team='nobody')
        assert st.netting is None
        assert st.zone_netting == {}
        assert not st.is_netted('anything')
