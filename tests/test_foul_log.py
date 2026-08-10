"""
Foul observation log tests (Step 8).

The log is the only first-party spatial data in the project and cannot be
re-collected after 2026-09-27, so these tests concentrate on the failure modes
that would corrupt it silently rather than loudly:

  - a retried submission counting a foul twice
  - a contradictory row (netting + catchable) reaching storage
  - a printed section resolving to the wrong zone, or to a zone at all when
    the mapping is ambiguous
  - calibration scoring an unobservable zone as zero, which manufactures a
    false "model over-predicts here"
"""
import json
import math
import threading

import pytest

import calibrate_log
from foulball import foul_log
from foulball.seat_map import (
    build_printed_index, normalize_label, parse_printed_ranges,
    zone_catalog, zone_for_printed_section, zone_map_fingerprint, zone_map_version,
)
from foulball.stadium import STADIUMS

ALL_STADIUM_KEYS = list(STADIUMS.keys())


@pytest.fixture
def db(tmp_path):
    """A throwaway log database."""
    conn = foul_log.connect(str(tmp_path / "test_log.db"))
    yield conn
    conn.close()


def _entry(uid="e1", **kw):
    base = {
        "entry_uid": uid,
        "game_pk": 700001,
        "park_key": "yankee_stadium",
        "inning": 3,
        "half": "top",
        "side": "3B",
        "landing_type": "seats",
        "catchable": 1,
        "caught": 0,
        "location_confidence": "exact",
    }
    base.update(kw)
    return base


# ============================================================
# Printed section <-> zone mapping
# ============================================================

class TestSeatMap:
    """The printed label is the log's anchor to the physical building."""

    @pytest.mark.parametrize("key", ALL_STADIUM_KEYS)
    def test_every_section_declares_a_printed_range(self, key):
        stadium = STADIUMS[key]()
        for sec in stadium.sections:
            assert parse_printed_ranges(sec.name), (
                f"{key} section {sec.section_id} has no parseable printed range "
                f"in its name: {sec.name!r}. Without one, a fan reading the sign "
                f"cannot be mapped into this zone."
            )

    @pytest.mark.parametrize("key", ALL_STADIUM_KEYS)
    def test_printed_index_is_non_empty(self, key):
        assert build_printed_index(STADIUMS[key]())

    @pytest.mark.parametrize("key", ALL_STADIUM_KEYS)
    def test_ambiguous_labels_resolve_by_side_or_return_none(self, key):
        """Ambiguity must never be resolved by guessing.

        Dodger Stadium numbers its field decks symmetrically (FD12 exists on
        both sides), so a bare label is genuinely ambiguous there. The form
        always captures a side, which resolves it; without one the lookup must
        return None rather than pick the first match.
        """
        stadium = STADIUMS[key]()
        index = build_printed_index(stadium)
        for label, zones in index.items():
            if len(zones) == 1:
                continue
            assert zone_for_printed_section(stadium, label) is None, (
                f"{key}: {label} maps to {zones} but resolved without a side hint"
            )
            sides = {s.side for s in stadium.sections if s.section_id in zones}
            for side in sides:
                got = zone_for_printed_section(stadium, label, side=side)
                assert got is None or got in zones

    def test_known_mappings(self):
        yankee = STADIUMS["yankee_stadium"]()
        # "3B Main Level (Sec 223-228)"
        assert zone_for_printed_section(yankee, "226") == "3B-LB1"
        # "1B Main Level (Sec 211-217)"
        assert zone_for_printed_section(yankee, "214") == "1B-LB1"
        # Fenway's alpha-prefixed numbering
        fenway = STADIUMS["fenway_park"]()
        assert zone_for_printed_section(fenway, "FB20") == "1B-FB1"

    def test_unknown_section_returns_none_not_a_guess(self):
        """An unmapped printed section is a finding, not a bad row."""
        assert zone_for_printed_section(STADIUMS["yankee_stadium"](), "999") is None

    def test_normalize_label_handles_what_fans_type(self):
        for raw in ["214", " 214 ", "Sec 214", "section 214", "SECTION214"]:
            assert normalize_label(raw) == "214"
        assert normalize_label("fb20") == "FB20"
        assert normalize_label(None) == ""

    def test_fingerprint_tracks_geometry_changes(self):
        """A stadium.py edit must invalidate stamps on rows logged before it."""
        stadium = STADIUMS["yankee_stadium"]()
        before = zone_map_fingerprint(stadium)
        stadium.sections[0].angle_max += 1
        assert zone_map_fingerprint(stadium) != before

    def test_zone_catalog_shape(self):
        cat = zone_catalog(STADIUMS["fenway_park"]())
        assert cat and all(
            {"zone_id", "name", "side", "level", "printed"} <= set(z) for z in cat)


# ============================================================
# Storage
# ============================================================

class TestStorage:

    def test_record_and_read_back(self, db):
        uid, created = foul_log.record_foul(db, _entry())
        assert created is True
        rows = foul_log.list_fouls(db)
        assert len(rows) == 1 and rows[0]["entry_uid"] == uid
        assert rows[0]["logged_at"], "server timestamp must always be set"

    def test_retry_is_idempotent(self, db):
        """The phone's offline queue retries. A retry is not a second foul."""
        payload = _entry()
        foul_log.record_foul(db, payload)
        uid, created = foul_log.record_foul(db, payload)
        assert created is False
        assert len(foul_log.list_fouls(db)) == 1

    def test_void_hides_but_keeps(self, db):
        foul_log.record_foul(db, _entry())
        assert foul_log.void_foul(db, "e1", "mis-tap") is True
        assert foul_log.list_fouls(db) == []
        kept = foul_log.list_fouls(db, include_voided=True)
        assert len(kept) == 1 and kept[0]["void_reason"] == "mis-tap"
        # Voiding twice is a no-op, not an error.
        assert foul_log.void_foul(db, "e1") is False

    def test_session_upsert_preserves_unsupplied_fields(self, db):
        """A heartbeat carrying only last_inning must not blank the vantage."""
        foul_log.upsert_session(db, {
            "session_uid": "s1", "game_pk": 1, "scope": "3b_side",
            "vantage": "in_park", "observer": "JA", "first_inning": 1,
        })
        foul_log.upsert_session(db, {"session_uid": "s1", "last_inning": 7})
        s = foul_log.list_sessions(db)[0]
        assert s["scope"] == "3b_side"
        assert s["vantage"] == "in_park"
        assert s["last_inning"] == 7

    def test_counts_and_logged_games(self, db):
        foul_log.record_foul(db, _entry("a"))
        foul_log.record_foul(db, _entry("b", game_pk=700002))
        foul_log.void_foul(db, "b")
        c = foul_log.counts(db)
        assert c["total"] == 2 and c["live"] == 1
        assert [g["game_pk"] for g in foul_log.logged_games(db)] == [700001]

    def test_export_includes_voided(self, db):
        foul_log.record_foul(db, _entry())
        foul_log.void_foul(db, "e1")
        assert len(foul_log.export_rows(db)) == 1

    def test_foul_stores_without_a_matching_session(self, db):
        """Regression: a phone that started the game offline has fouls whose
        session row never reached the server. A foreign key made those inserts
        fail forever, stranding a whole game's observations on the handset."""
        uid, created = foul_log.record_foul(db, _entry(session_uid="never-sent"))
        assert created is True
        assert foul_log.list_fouls(db)[0]["session_uid"] == "never-sent"

        # And the session filling in later still links up.
        foul_log.upsert_session(db, {"session_uid": "never-sent", "game_pk": 700001,
                                     "scope": "full_bowl"})
        assert foul_log.list_sessions(db)[0]["session_uid"] == "never-sent"

    def test_concurrent_writers_on_a_fresh_database(self, tmp_path):
        """Regression: the first foul of a game must not hit 'database is locked'.

        The form fires a session update, a foul write and an entry fetch within
        a few hundred milliseconds, each on its own connection. Re-issuing
        `PRAGMA journal_mode=WAL` per connection made that combination fail —
        SQLite returns SQLITE_BUSY for a journal-mode change without consulting
        the busy handler, so the retry timeout never applied.
        """
        path = str(tmp_path / "concurrent.db")
        errors, wrote = [], []

        def writer(n):
            try:
                conn = foul_log.connect(path)
                try:
                    foul_log.upsert_session(conn, {"session_uid": f"s{n}"})
                    foul_log.record_foul(conn, _entry(f"c{n}"))
                    foul_log.list_fouls(conn)
                    wrote.append(n)
                finally:
                    conn.close()
            except Exception as e:  # noqa: BLE001 - the point is to catch any
                errors.append(f"{type(e).__name__}: {e}")

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, errors
        assert len(wrote) == 8

        conn = foul_log.connect(path)
        try:
            assert len(foul_log.list_fouls(conn)) == 8
        finally:
            conn.close()


class TestValidation:

    def test_accepts_a_minimal_entry(self):
        """Side and outcome are the only required observations.

        A fan gets a few seconds. Inning, batter and section are all optional
        so that a hurried row is still a row.
        """
        assert foul_log.validate_foul({
            "entry_uid": "x", "side": "1B", "landing_type": "seats"}) == []

    @pytest.mark.parametrize("bad,field", [
        ({"side": "left"}, "side"),
        ({"landing_type": "bleachers"}, "landing_type"),
        ({"location_confidence": "certain"}, "location_confidence"),
        ({"half": "middle"}, "half"),
        ({"inning": 0}, "inning"),
        ({"inning": "seventh"}, "inning"),
    ])
    def test_rejects_out_of_vocabulary_values(self, bad, field):
        payload = {"entry_uid": "x", "side": "1B", "landing_type": "seats"}
        payload.update(bad)
        violations = foul_log.validate_foul(payload)
        assert any(field in v for v in violations), violations

    def test_requires_entry_uid(self):
        v = foul_log.validate_foul({"side": "1B", "landing_type": "seats"})
        assert any("entry_uid" in x for x in v)

    def test_rejects_contradictions(self):
        """A ball that hit the netting was not catchable."""
        v = foul_log.validate_foul({
            "entry_uid": "x", "side": "1B", "landing_type": "netting",
            "catchable": 1})
        assert v
        v = foul_log.validate_foul({
            "entry_uid": "x", "side": "1B", "landing_type": "seats",
            "catchable": 0, "caught": 1})
        assert v

    def test_storage_refuses_invalid_rows(self, db):
        with pytest.raises(ValueError):
            foul_log.record_foul(db, _entry(side="left"))
        assert foul_log.list_fouls(db) == []


class TestCoverage:
    """Coverage bookkeeping — the difference between under-prediction and
    an observer who was not looking."""

    def test_session_innings_prefers_explicit_list(self):
        assert foul_log.session_innings(
            {"innings_watched": json.dumps([1, 2, 9])}) == {1, 2, 9}

    def test_session_innings_falls_back_to_span(self):
        assert foul_log.session_innings(
            {"first_inning": 3, "last_inning": 5}) == {3, 4, 5}

    def test_unknown_coverage_is_empty_not_nine(self):
        """Assuming nine innings would credit an observer with fouls they
        never had the chance to see."""
        assert foul_log.session_innings({}) == set()

    def test_observable_zones_by_scope(self):
        stadium = STADIUMS["yankee_stadium"]()
        by_id = {s.section_id: s for s in stadium.sections}

        full = foul_log.observable_zones(stadium, "full_bowl")
        assert len(full) == len(stadium.sections)

        third = foul_log.observable_zones(stadium, "3b_side")
        assert third and all(by_id[z].side in ("3B", "HOME") for z in third)
        assert not any(by_id[z].side == "1B" for z in third)

        home = foul_log.observable_zones(stadium, "home_plate")
        assert all(by_id[z].side == "HOME" for z in home)

    def test_broadcast_excludes_upper_decks(self):
        """A centre-field camera does not reliably show the upper deck."""
        stadium = STADIUMS["yankee_stadium"]()
        by_id = {s.section_id: s for s in stadium.sections}
        zones = foul_log.observable_zones(stadium, "broadcast_frame")
        assert zones
        assert all(by_id[z].level in ("field", "lower") for z in zones)

    def test_unknown_scope_observes_nothing(self):
        assert foul_log.observable_zones(STADIUMS["yankee_stadium"](), None) == set()


# ============================================================
# Calibration
# ============================================================

class TestPoisson:

    def test_cdf_endpoints(self):
        assert calibrate_log.poisson_cdf(0, 1.0) == pytest.approx(math.exp(-1.0))
        assert calibrate_log.poisson_cdf(60, 5.0) == pytest.approx(1.0, abs=1e-9)

    def test_p_value_is_one_at_the_mean(self):
        assert calibrate_log.poisson_two_sided_p(10, 10.0) > 0.9

    def test_p_value_small_in_both_tails(self):
        assert calibrate_log.poisson_two_sided_p(40, 10.0) < 0.001
        assert calibrate_log.poisson_two_sided_p(0, 10.0) < 0.001

    def test_p_value_bounded(self):
        for o in range(0, 25):
            p = calibrate_log.poisson_two_sided_p(o, 8.0)
            assert 0.0 <= p <= 1.0


class TestCompareGame:

    @staticmethod
    def _prediction(stadium, overrides=None):
        expected = {s.section_id: 1.0 for s in stadium.sections}
        expected.update(overrides or {})
        return {
            "game_pk": 1, "park_key": "yankee_stadium",
            "zone_map_version": zone_map_version(stadium),
            "expected": expected, "catchable": expected,
        }

    def test_unobservable_zones_are_dropped_not_zeroed(self):
        """The core guard. A 3B-side observer says nothing about 1B zones."""
        stadium = STADIUMS["yankee_stadium"]()
        sessions = [{"scope": "3b_side"}]
        fouls = [_entry(f"e{i}", model_zone_id="3B-LB1") for i in range(10)]

        result = calibrate_log.compare_game(
            1, fouls, sessions, self._prediction(stadium), stadium)

        zones = {r["zone_id"] for r in result["rows"]}
        assert "3B-LB1" in zones
        assert not any(z.startswith("1B") for z in zones), (
            "a 1B zone appeared in a 3B-side observer's comparison; it would be "
            "scored as zero observed and reported as over-prediction")

    def test_expected_counts_renormalize_to_what_was_logged(self):
        stadium = STADIUMS["yankee_stadium"]()
        fouls = [_entry(f"e{i}", model_zone_id="3B-LB1") for i in range(12)]
        result = calibrate_log.compare_game(
            1, fouls, [{"scope": "full_bowl"}], self._prediction(stadium), stadium)
        total_expected = sum(r["expected"] for r in result["rows"])
        assert total_expected == pytest.approx(result["n_compared"])
        assert result["n_compared"] == 12

    def test_no_session_scope_skips_the_game(self):
        """Comparing without knowing coverage silently assumes full coverage."""
        stadium = STADIUMS["yankee_stadium"]()
        fouls = [_entry("e1", model_zone_id="3B-LB1")]
        result = calibrate_log.compare_game(
            1, fouls, [], self._prediction(stadium), stadium)
        assert result.get("skipped")

    def test_counts_unmapped_and_off_scope_separately(self):
        stadium = STADIUMS["yankee_stadium"]()
        fouls = [
            _entry("a", model_zone_id="3B-LB1"),
            _entry("b", model_zone_id=None),          # printed section no zone claims
            _entry("c", model_zone_id="1B-LB1"),      # outside a 3B observer's view
        ]
        result = calibrate_log.compare_game(
            1, fouls, [{"scope": "3b_side"}], self._prediction(stadium), stadium)
        assert result["n_compared"] == 1
        assert result["unassigned"] == 1
        assert result["outside_scope"] == 1

    def test_scope_union_across_two_observers(self):
        stadium = STADIUMS["yankee_stadium"]()
        fouls = [_entry("a", model_zone_id="3B-LB1"),
                 _entry("b", model_zone_id="1B-LB1")]
        result = calibrate_log.compare_game(
            1, fouls, [{"scope": "3b_side"}, {"scope": "1b_side"}],
            self._prediction(stadium), stadium)
        assert result["outside_scope"] == 0
        assert result["n_compared"] == 2


class TestAggregate:

    @staticmethod
    def _comparison(rows):
        return {"game_pk": 1, "park_key": "yankee_stadium", "rows": rows,
                "observable": [r["zone_id"] for r in rows]}

    def test_verdicts(self):
        rows = [
            {"zone_id": "3B-LB1", "zone_name": "n", "side": "3B", "level": "lower",
             "observed": 40, "expected": 10.0, "model_share": .1},
            {"zone_id": "1B-LB1", "zone_name": "n", "side": "1B", "level": "lower",
             "observed": 0, "expected": 20.0, "model_share": .2},
            {"zone_id": "HOME-F", "zone_name": "n", "side": "HOME", "level": "field",
             "observed": 10, "expected": 10.0, "model_share": .1},
            {"zone_id": "3B-UB", "zone_name": "n", "side": "3B", "level": "upper",
             "observed": 1, "expected": 1.0, "model_share": .01},
        ]
        out = {r["zone_id"]: r for r in calibrate_log.aggregate([self._comparison(rows)])}
        assert out["3B-LB1"]["verdict"] == "UNDER-predicted"
        assert out["1B-LB1"]["verdict"] == "OVER-predicted"
        assert out["HOME-F"]["verdict"] == "consistent"
        assert out["3B-UB"]["verdict"] == "insufficient data", (
            "a zone with an expected count of 1 cannot support a verdict")

    def test_small_samples_get_no_verdict(self):
        rows = [{"zone_id": "Z", "zone_name": "n", "side": "3B", "level": "lower",
                 "observed": 2, "expected": 0.5, "model_share": .05}]
        out = calibrate_log.aggregate([self._comparison(rows)])
        assert out[0]["verdict"] == "insufficient data"

    def test_counts_add_across_games(self):
        rows = [{"zone_id": "Z", "zone_name": "n", "side": "3B", "level": "lower",
                 "observed": 5, "expected": 6.0, "model_share": .1}]
        out = calibrate_log.aggregate([self._comparison(rows), self._comparison(rows)])
        assert out[0]["observed"] == 10
        assert out[0]["expected"] == pytest.approx(12.0)
        assert out[0]["games"] == 2

    def test_zones_are_not_pooled_across_parks(self):
        """Two parks' 3B-LB1 are different seats."""
        a = {"game_pk": 1, "park_key": "yankee_stadium", "observable": ["3B-LB1"],
             "rows": [{"zone_id": "3B-LB1", "zone_name": "n", "side": "3B",
                       "level": "lower", "observed": 5, "expected": 5.0,
                       "model_share": .1}]}
        b = dict(a, park_key="fenway_park")
        out = calibrate_log.aggregate([a, b])
        assert len(out) == 2

    def test_threshold_is_corrected_for_multiple_zones(self):
        rows = [{"zone_id": f"Z{i}", "zone_name": "n", "side": "3B",
                 "level": "lower", "observed": 10, "expected": 10.0,
                 "model_share": .1} for i in range(10)]
        out = calibrate_log.aggregate([self._comparison(rows)])
        assert out[0]["adjusted_threshold"] == pytest.approx(calibrate_log.ALPHA / 10)


class TestReadiness:

    def test_tracks_printed_sections_and_unmapped_seats(self):
        fouls = [
            _entry("a", printed_section="226", model_zone_id="3B-LB1"),
            _entry("b", printed_section="226", model_zone_id="3B-LB1"),
            _entry("c", printed_section="999", model_zone_id=None),
            _entry("d", printed_section=None, model_zone_id="3B-LB1"),
        ]
        out = calibrate_log.boundary_readiness(fouls)
        park = out["parks"]["yankee_stadium"]
        assert park["observations"] == 3
        assert park["sections_seen"] == 2
        assert out["entries_without_printed_section"] == 1
        assert dict(park["unmapped_sections"])["999"] == 1
        assert park["target_observations"] > park["observations"], (
            "the readiness target must not be reachable with four rows")

    def test_confidence_mix_is_reported(self):
        fouls = [_entry("a", location_confidence="exact"),
                 _entry("b", location_confidence="guess")]
        out = calibrate_log.boundary_readiness(fouls)
        assert out["confidence_mix"] == {"exact": 1, "guess": 1}


class TestZoneResolution:
    """Server-side derivation of the zone from what the fan tapped and typed."""

    @staticmethod
    def _resolve(**kw):
        import webapp_v2
        payload = {"entry_uid": "x", "park_key": "yankee_stadium",
                   "side": "3B", "landing_type": "seats"}
        payload.update(kw)
        return webapp_v2._resolve_zone(payload)

    def test_printed_section_wins_over_a_tapped_zone(self):
        entry, warning = self._resolve(printed_section="226", model_zone_id="3B-UB")
        assert entry["model_zone_id"] == "3B-LB1"
        assert entry["zone_source"] == "printed_section"
        assert warning is None

    def test_tapped_zone_used_when_no_section_typed(self):
        entry, _ = self._resolve(model_zone_id="3B-UB")
        assert entry["model_zone_id"] == "3B-UB"
        assert entry["zone_source"] == "tapped_zone"

    def test_unmapped_section_keeps_the_tapped_zone(self):
        entry, _ = self._resolve(printed_section="999", model_zone_id="3B-UB")
        assert entry["model_zone_id"] == "3B-UB"
        assert entry["zone_source"] == "tapped_zone"

    def test_unmapped_section_with_nothing_tapped_stores_no_zone(self):
        entry, _ = self._resolve(printed_section="999")
        assert entry["model_zone_id"] is None
        assert entry["zone_source"] == "none"
        assert entry["printed_section"] == "999", "the printed section is kept"

    def test_side_conflict_stores_no_zone(self):
        """Section 214 is a 1B zone. Tapped as 3B, one of the two taps is
        wrong and there is no way to tell which — so neither is trusted."""
        entry, warning = self._resolve(side="3B", printed_section="214")
        assert entry["model_zone_id"] is None
        assert entry["zone_source"] == "conflict"
        assert entry["printed_section"] == "214"
        assert warning and "1B" in warning

    def test_stamps_the_zone_map_version(self):
        entry, _ = self._resolve(printed_section="226")
        assert entry["zone_map_version"].startswith("1:")


class TestLoadLog:

    def test_guesses_are_excluded_by_default(self, tmp_path):
        path = str(tmp_path / "log.db")
        conn = foul_log.connect(path)
        foul_log.record_foul(conn, _entry("a", location_confidence="exact"))
        foul_log.record_foul(conn, _entry("b", location_confidence="guess"))
        conn.close()

        default = calibrate_log.load_log(path)
        assert len(default["fouls"]) == 1
        assert default["dropped_low_confidence"] == 1

        everything = calibrate_log.load_log(path, min_confidence="guess")
        assert len(everything["fouls"]) == 2

    def test_voided_entries_never_reach_calibration(self, tmp_path):
        path = str(tmp_path / "log.db")
        conn = foul_log.connect(path)
        foul_log.record_foul(conn, _entry("a"))
        foul_log.void_foul(conn, "a")
        conn.close()
        assert calibrate_log.load_log(path)["fouls"] == []
