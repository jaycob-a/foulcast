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
    'fenway_park', 'dodger_stadium', 'truist_park',
    'citizens_bank', 'great_american',
    'minute_maid', 'guaranteed_rate',
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
    # Rejected by the structural checks (G4) rather than by the extent:
    'angel_stadium', 'pnc_park',    # one foul line's labels wrap
    'globe_life',                   # sides not establishable
    # Rejected by the side-anchor check (G5): the seating map puts the lower
    # bowl ascending toward third base and the zone table has it ascending
    # toward first. Passed every other guard, because they are all symmetric.
    'camden_yards',
    # Step 12, the second map read. Coors and Progressive are clean
    # mirrors. Oracle is mirrored *and* has its plate zone several
    # sections down the first-base line, so three of its anchored
    # sections happen to agree; the check reports that as inconsistent
    # rather than flipped, and G5 passes it on as labels_contradict_model.
    'coors_field', 'progressive_field', 'oracle_park',
}

# What each G4 park fails on, locked so a change of guard is a named diff.
# Angel Stadium and PNC Park moved from 'labels_wrap_unpublished' to
# 'labels_contradict_model' in Step 14: both already failed on the wrap, and
# the map read added a side anchor each one's zone table contradicts, which is
# the earlier and stronger reason. Angel Stadium carries 133-141 as "3B Field"
# and the map has 133 134 135 at the end of the right-field arm; PNC carries
# 101-107 as "3B Infield" and the map has that arm running to the Right Field
# Gate. See MAP_FINDINGS.md.
STRUCTURAL_GAP_KINDS = {
    'angel_stadium': 'labels_contradict_model',
    'pnc_park': 'labels_contradict_model',
    'globe_life': 'sides_unverifiable',
    'camden_yards': 'sides_flipped',
    'coors_field': 'sides_flipped',
    'progressive_field': 'sides_flipped',
    'oracle_park': 'labels_contradict_model',
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


class TestTheZoneTableMustDescribeABowl:
    """G4: structural checks on the labels, before any netting is applied.

    These are the only checks in the layer that fire on evidence from outside
    the netting data. They exist because the alternative is a park whose
    netting looks mapped and whose sides may be swapped — worse than a gap,
    because it is a wrong answer wearing a citation.
    """

    @pytest.mark.parametrize('key,kind', sorted(STRUCTURAL_GAP_KINDS.items()))
    def test_structural_gap_park_fails_for_the_recorded_reason(self, key, kind):
        j = N.join_park(STADIUMS[key](), key)
        assert j.gap_kind == kind, f"{key}: {j.gap_kind} — {j.gap_detail}"

    @pytest.mark.parametrize('key', ['angel_stadium', 'pnc_park'])
    def test_a_wrapped_foul_line_is_detected(self, key):
        """One 3B zone sits on the far side of the plate's numbers from the
        other. Angel's 3B runs 103-109 and then 133-141 with the plate at
        110-113; PNC's runs 101-107 and then 130-139 with the plate at
        108-111. Either the numbering wraps at a point no source gives, or a
        zone is on the wrong side. Both make an interval unreadable as an arc.
        """
        s = N._field_label_structure(STADIUMS[key]())
        assert s['straddle'], f"{key}: expected a straddling side"
        assert s['straddle'][0][0] == '3B'

    @pytest.mark.parametrize('key', sorted(MAPPED_PARKS))
    def test_no_mapped_park_has_a_wrapped_foul_line(self, key):
        assert not N._field_label_structure(STADIUMS[key]())['straddle']

    def test_globe_life_sides_are_not_establishable(self):
        """Both foul lines numbered above the plate zone, with a five-section
        hole between them, and an extent that covers only part of the series.
        Which block is 1B and which is 3B decides the answer, and nothing
        establishes it."""
        s = N._field_label_structure(STADIUMS['globe_life']())
        assert s['plate_at_end']
        assert not N._extent_covers_field_span(
            N.PARK_NETTING['globe_life'], s['field_span'])

    def test_rate_field_survives_the_same_shape(self):
        """Same unverifiable shape, and it does not matter: the White Sox net
        pole to pole, so every field-level label is inside the extent and no
        zone's status depends on which side it is on."""
        s = N._field_label_structure(STADIUMS['guaranteed_rate']())
        assert s['plate_at_end']
        assert N._extent_covers_field_span(
            N.PARK_NETTING['guaranteed_rate'], s['field_span'])

    def test_dodger_survives_the_same_shape_by_corroboration(self):
        """Dodger's field boxes really are numbered outward from the plate,
        and the club says so: 40 on 1B, 41 on 3B, matching the zone table's
        parity. That evidence is recorded on the entry and is what keeps the
        park mapped where Globe Life is not."""
        s = N._field_label_structure(STADIUMS['dodger_stadium']())
        assert s['plate_at_end']
        assert not N._extent_covers_field_span(
            N.PARK_NETTING['dodger_stadium'], s['field_span'])
        assert N.PARK_NETTING['dodger_stadium'].series_corroborated
        assert N.join_park(STADIUMS['dodger_stadium'](),
                           'dodger_stadium').status == 'mapped'

    def test_a_mirrored_table_is_invisible_to_every_symmetric_guard(self):
        """The reason G5 had to exist.

        Swap Camden's 1B and 3B field-level labels and G1-G4 report exactly
        what they reported before: the geometry is mirror-symmetric, so none
        of them can see the difference. Only the side anchors can.
        """
        import copy
        from foulball import seat_map as SM

        park = N.PARK_NETTING['camden_yards']
        as_is = STADIUMS['camden_yards']()
        mirrored = copy.deepcopy(as_is)
        for sec in mirrored.sections:
            if sec.side in ('1B', '3B'):
                sec.side = '3B' if sec.side == '1B' else '1B'

        def verdict(st):
            return N._check_join(
                st,
                {s.section_id: N._classify_zone(s, park) for s in st.sections},
                park)

        # With the anchors removed, G1-G4 are all that is left — and they pass
        # the park both ways round. That is the state this layer was in before
        # G5 existed, and it is why Camden was `mapped` with its sides swapped.
        kept = SM.SIDE_ANCHORS.pop('camden_yards')
        try:
            assert verdict(as_is) == ('', '')
            assert verdict(mirrored) == ('', '')
        finally:
            SM.SIDE_ANCHORS['camden_yards'] = kept

        # With the anchors back, the two tables stop looking alike: the one
        # the file ships is rejected, and its mirror image passes.
        assert verdict(as_is)[0] == 'sides_flipped'
        assert verdict(mirrored) == ('', '')

    def test_unverified_anchors_can_flag_but_never_reject(self):
        """Fenway's dugout anchor is a compilation SOURCED_DATA.md could not
        confirm. It agrees with the map read, but if it ever disagreed it must
        not turn a park into a gap on its own."""
        from foulball import seat_map as SM
        secondary = [a for a in SM.SIDE_ANCHORS['fenway_park']
                     if a.source_kind == 'secondary_unverified']
        assert secondary, 'expected the unverified dugout anchors'
        assert all(a.source_kind not in SM.DECIDING_ANCHOR_KINDS
                   for a in secondary)

    def test_an_anchor_check_says_nothing_about_boundaries(self):
        """Truist passes every anchor and its plate zone is still four
        sections up the third-base line (MAP_FINDINGS.md). Passing means
        'not mirrored', not 'correct'."""
        from foulball import seat_map as SM
        c = SM.check_side_anchors(STADIUMS['truist_park'](), 'truist_park')
        assert c.status == 'ok'
        home = [s for s in STADIUMS['truist_park']().sections
                if s.side == 'HOME' and s.level == 'field'][0]
        assert '129-133' in home.name   # the offset the check cannot see

    def test_overlapping_side_claims_make_a_park_untestable(self):
        """Petco's page names 111-115 as 1B and 112-116 as 3B. A section is on
        one foul line or the other, so the wording is not describing sides in
        a testable way, and the check must decline rather than pick."""
        from foulball import seat_map as SM
        c = SM.check_side_anchors(STADIUMS['petco_park'](), 'petco_park')
        assert c.status == 'untestable'
        assert 'same printed numbers' in c.detail

    def test_mapped_parks_record_whether_their_sides_were_tested(self):
        """A mapped park either passed the anchor check or had no anchor to
        run, and the two must not look alike to a reader."""
        from foulball import seat_map as SM
        for key in sorted(MAPPED_PARKS):
            j = N.join_park(STADIUMS[key](), key)
            c = SM.check_side_anchors(STADIUMS[key](), key)
            assert c.status in ('ok', 'untestable'), f'{key}: {c.status}'
            marker = 'sides confirmed' if c.status == 'ok' else 'sides untested'
            assert any(f.startswith(marker) for f in j.flags), (
                f'{key}: no flag recording that sides were '
                f'{"confirmed" if c.status == "ok" else "untested"}')

    def test_corroboration_is_claimed_at_exactly_one_park(self):
        """It is an escape hatch from a structural check, so it stays rare and
        stays visible."""
        claimed = {k for k, p in N.PARK_NETTING.items()
                   if p.series_corroborated}
        assert claimed == {'dodger_stadium'}

    @pytest.mark.parametrize('key', sorted(MAPPED_PARKS))
    def test_asymmetry_at_a_mapped_park_is_the_source_s(self, key):
        """A mapped park's asymmetry, where it has any, comes from the extent
        and not from a wrapped or reversed table — the structural checks have
        already excluded those. The flag says so and carries the numbers."""
        j = N.join_park(STADIUMS[key](), key)
        for f in j.flags:
            if 'asymmetric' in f:
                assert 'structural checks' in f
                assert 'below the behind-plate zone' in f


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
