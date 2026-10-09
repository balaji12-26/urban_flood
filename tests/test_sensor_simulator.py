from backend.services.sensor_simulator import get_water_level, BUCKET_SECONDS, describe


def test_deterministic_same_bucket():
    a = get_water_level("velachery", 1_700_000_000.0, 10.0, baseline_cm=45.0)
    b = get_water_level("velachery", 1_700_000_000.0 + 5, 10.0, baseline_cm=45.0)  # same 30s bucket
    assert a == b


def test_changes_across_buckets():
    vals = {get_water_level("velachery", 1_700_000_000.0 + i * BUCKET_SECONDS, 10.0, baseline_cm=45.0)
            for i in range(10)}
    assert len(vals) > 1, "live mode should vary across buckets"


def test_zone_isolation_of_noise():
    a = get_water_level("velachery", 1_700_000_000.0, 10.0, baseline_cm=45.0)
    b = get_water_level("guindy", 1_700_000_000.0, 10.0, baseline_cm=45.0)
    assert a != b, "different zones must draw different noise"


def test_frozen_is_baseline():
    assert get_water_level("velachery", 123.0, 50.0, mode="frozen", baseline_cm=45.0) == 45.0


def test_replay_exact():
    assert get_water_level("velachery", 123.0, 50.0, mode="replay", replay_value=88.4) == 88.4


def test_rain_lifts_level():
    dry = get_water_level("adyar", 1_700_000_000.0, 0.0, baseline_cm=40.0)
    wet = get_water_level("adyar", 1_700_000_000.0, 30.0, baseline_cm=40.0)
    assert wet > dry


def test_seed_changes_noise():
    a = get_water_level("adyar", 1_700_000_000.0, 0.0, seed=42, baseline_cm=40.0)
    b = get_water_level("adyar", 1_700_000_000.0, 0.0, seed=7, baseline_cm=40.0)
    assert a != b


def test_never_negative_and_bad_inputs_safe():
    assert get_water_level("tnagar", "bad", None, baseline_cm=0.0) >= 0.0
    assert get_water_level("unknown-zone", 0, 0) >= 0.0


def test_describe_is_labelled_simulated():
    assert describe()["label"] == "SIMULATED"
