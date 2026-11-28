"""Design-only simulations of the cluster-level analysis and the batch alert budget."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis_design_simulation as ads  # noqa: E402


def _empirical_alert_probability(n, level, reps, seed):
    rng = np.random.default_rng(seed)
    scores = rng.random((reps, n))
    threshold = np.quantile(scores, level, axis=1, method="linear")
    return 1.0 - threshold  # uniform scores: P(new > T) = 1 - T


def test_the_alert_probability_after_an_interpolated_quantile_is_not_beta_1_n():
    moments = ads.false_alert_moments(20, 0.95)
    simulated = _empirical_alert_probability(20, 0.95, 200_000, 1)
    assert moments["mean"] == pytest.approx(simulated.mean(), abs=0.0007)
    assert moments["sd"] == pytest.approx(simulated.std(), abs=0.0007)
    assert moments["mean"] == pytest.approx(1 - 19.05 / 21)
    assert moments["mean"] > 1 / 20  # Beta(1, n) would give about 1 / (n + 1)


def test_the_sample_maximum_is_the_case_where_beta_1_n_holds():
    moments = ads.false_alert_moments(20, 1.0)
    assert moments["mean"] == pytest.approx(1 / 21)
    assert moments["sd"] == pytest.approx(np.sqrt(20 / (21**2 * 22)))


def test_the_budget_is_met_in_expectation_only_with_many_validation_batches():
    assert ads.false_alert_moments(100, 0.95)["mean"] < 0.06
    assert ads.false_alert_moments(16, 0.95)["mean"] > 0.10


def test_observed_test_rate_adds_binomial_noise_to_the_threshold_uncertainty():
    base = ads.false_alert_moments(20, 0.95)
    with_test = ads.observed_rate_sd(20, 0.95, 40)
    assert with_test > base["sd"]
    assert with_test == pytest.approx(
        np.sqrt(base["sd"] ** 2 + (base["mean"] * (1 - base["mean"]) - base["sd"] ** 2) / 40)
    )


def test_ties_make_a_strict_threshold_alert_less_often_than_continuous_scores():
    rng = np.random.default_rng(2)
    plain_valid, plain_new = rng.random((20000, 20)), rng.random((20000, 1))
    tied_valid, tied_new = np.round(plain_valid, 1), np.round(plain_new, 1)
    assert ads.alert_rate(tied_valid, 0.95, tied_new) < ads.alert_rate(plain_valid, 0.95, plain_new)


def test_the_t_test_holds_its_level_for_normal_independent_clusters():
    res = ads.simulate(n=40, sigma=0.10, delta=0.0, reps=600, boot=199, seed=3)
    assert res["t"]["reject"] == pytest.approx(0.05, abs=0.03)
    assert res["boot"]["reject"] == pytest.approx(0.05, abs=0.035)
    assert res["perm"]["reject"] == pytest.approx(0.05, abs=0.03)


def test_coverage_is_reported_against_the_true_difference():
    res = ads.simulate(n=40, sigma=0.10, delta=0.05, reps=600, boot=199, seed=4)
    assert res["t"]["coverage"] == pytest.approx(0.95, abs=0.035)


def test_power_is_higher_for_more_clusters():
    small = ads.simulate(n=20, sigma=0.10, delta=0.05, reps=400, boot=99, seed=5)
    large = ads.simulate(n=80, sigma=0.10, delta=0.05, reps=400, boot=99, seed=5)
    assert large["t"]["reject"] > small["t"]["reject"]


def test_curator_dependence_inflates_type_one_error_and_the_curator_bootstrap_repairs_it():
    res = ads.simulate(
        n=60, sigma=0.10, delta=0.0, curator_size=6, icc=0.5, reps=600, boot=199, seed=6
    )
    assert res["t"]["reject"] > 0.10
    assert res["boot_curator"]["reject"] < res["t"]["reject"]


def test_the_bounded_skewed_shape_keeps_the_mean_and_scale():
    z = ads.standardised_shape("bounded", np.random.default_rng(1), (200_000,))
    assert z.mean() == pytest.approx(0, abs=0.01) and z.std() == pytest.approx(1, abs=0.01)
    assert abs(((z - z.mean()) ** 3).mean()) > 0.5  # visibly skewed


def test_an_unknown_shape_is_rejected():
    with pytest.raises(ValueError, match="^unknown shape 'x'$"):
        ads.standardised_shape("x", np.random.default_rng(1), (3,))


def test_a_fixed_seed_reproduces_the_result():
    a = ads.simulate(n=10, sigma=0.1, delta=0.05, reps=50, boot=49, seed=9)
    assert a == ads.simulate(n=10, sigma=0.1, delta=0.05, reps=50, boot=49, seed=9)


def test_the_evidence_covers_every_scenario_and_the_batch_budget_table(tmp_path):
    import json

    target = tmp_path / "e.json"
    assert ads.main(["--reps", "20", "--boot", "19", "--output", str(target)]) == 0
    out = json.loads(target.read_text())
    assert [r["scenario"] for r in out["scenarios"]] == [s["name"] for s in ads.SCENARIOS]
    assert {"null@0.05", "effect_0.05@0.0167"} <= set(out["scenarios"][0])
    assert out["batch_alert_budget"][0]["validation_batches"] == 16


@pytest.mark.parametrize(
    ("n", "level", "mean", "sd"),
    [
        (21, 0.95, 0.09090909090909094, 0.059943679399617),  # an exact order statistic
        (16, 1.0, 1 / 17, np.sqrt(16 / (17**2 * 18))),  # Beta(1, 16)
        (30, 0.9, 0.12580645161290316, 0.05784568980783642),
    ],
)
def test_the_alert_probability_moments_are_exact(n, level, mean, sd):
    moments = ads.false_alert_moments(n, level)
    assert moments["mean"] == pytest.approx(mean, rel=1e-9)
    assert moments["sd"] == pytest.approx(sd, rel=1e-9)


def test_the_median_threshold_of_ten_scores_has_the_hand_computed_sd():
    variance = 0.25 * (30 / (121 * 12) + 30 / (121 * 12) + 2 * 25 / (121 * 12))
    assert ads.false_alert_moments(10, 0.5)["sd"] == pytest.approx(np.sqrt(variance), rel=1e-9)


def test_the_alert_rate_is_strict_and_uses_each_validation_row():
    validation = np.array([[1.0, 2.0, 3.0, 4.0, 5.0], [10.0, 20.0, 30.0, 40.0, 50.0]])
    new = np.array([[2.0, 3.0, 4.0], [20.0, 30.0, 31.0]])
    assert ads.alert_rate(validation, 0.5, new) == pytest.approx(2 / 6)


def test_the_standardised_shape_streams_are_fixed_by_the_seed():
    normal = ads.standardised_shape("normal", np.random.default_rng(3), (2,))
    assert normal == pytest.approx(np.random.default_rng(3).standard_normal(2))
    bounded = ads.standardised_shape("bounded", np.random.default_rng(3), (2,))
    lower = -(0.5 / 3.5) / np.sqrt(0.5 * 3 / (3.5**2 * 4.5))
    assert bounded.shape == (2,) and (bounded > lower).all()


SNAPSHOTS = [
    (
        dict(n=12, sigma=0.1, delta=0.05, reps=40, boot=29, seed=1),
        {"t": (0.375, 0.925), "boot": (0.6, 0.825), "boot_curator": (0.55, 0.825), "perm": 0.375},
    ),
    (
        dict(
            n=12,
            sigma=0.1,
            delta=0.0,
            shape="bounded",
            heterogeneity=1.0,
            size_noise=0.5,
            reps=40,
            boot=29,
            seed=2,
        ),
        {"t": (0.025, 0.975), "boot": (0.1, 0.9), "boot_curator": (0.1, 0.9), "perm": 0.025},
    ),
    (
        dict(
            n=12,
            sigma=0.1,
            delta=0.0,
            curator_size=4,
            icc=0.5,
            reps=40,
            boot=29,
            seed=3,
            alpha=0.0167,
        ),
        {"t": (0.125, 0.875), "boot": (0.3, 0.7), "boot_curator": (0.275, 0.725), "perm": 0.0},
    ),
]


@pytest.mark.parametrize(("params", "expected"), SNAPSHOTS)
def test_seeded_simulations_reproduce_the_recorded_rates(params, expected):
    res = ads.simulate(**params)
    for method in ("t", "boot", "boot_curator"):
        assert (res[method]["reject"], res[method]["coverage"]) == pytest.approx(expected[method])
    assert res["perm"] == {"reject": pytest.approx(expected["perm"])}


def test_a_clearly_positive_effect_is_always_rejected_and_covered_by_every_method():
    data = np.full((5, 30), 1.0) + np.random.default_rng(0).normal(0, 0.01, (5, 30))
    rng = np.random.default_rng(1)
    assert ads._t_reject(data, 0.05) == 1.0
    assert ads._signflip(data, 99, 0.05, rng) == 1.0
    boot = ads._boot(data, 1.0, 99, 0.05, rng, None)
    assert boot == {"reject": 1.0, "coverage": 1.0}
    assert ads._boot(data, 1.0, 99, 0.05, rng, 5) == {"reject": 1.0, "coverage": 1.0}


def test_a_centred_effect_is_not_rejected_at_the_stated_level_by_the_permutation_test():
    data = np.tile(np.array([-1.0, 1.0] * 10), (3, 1))
    assert ads._signflip(data, 199, 0.05, np.random.default_rng(1)) == 0.0
    assert ads._t_reject(data, 0.05) == 0.0


def test_the_curator_bootstrap_resamples_whole_curators():
    # two curators with opposite constant effects: resampling curators moves the mean a lot
    data = np.array([[1.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0, -1.0]])
    by_cluster = ads._boot(data, 0.0, 499, 0.05, np.random.default_rng(1), None)
    by_curator = ads._boot(data, 0.0, 499, 0.05, np.random.default_rng(1), 4)
    assert by_cluster["reject"] == 0.0
    assert by_curator["reject"] == 0.0 and by_curator["coverage"] == 1.0


def test_the_evidence_runs_every_scenario_with_its_own_seed_offset():
    out = ads.evidence(reps=20, boot=19, seed=7)
    assert (out["reps"], out["boot"], out["sigma"]) == (20, 19, 0.10)
    assert out["note"].startswith("design-only synthetic")
    first = {k: v for k, v in ads.SCENARIOS[0].items() if k != "name"}
    assert out["scenarios"][0]["null@0.05"] == ads.simulate(
        sigma=0.10, delta=0.0, reps=20, boot=19, alpha=0.05, seed=7, **first
    )
    second = {k: v for k, v in ads.SCENARIOS[1].items() if k != "name"}
    assert out["scenarios"][1]["effect_0.05@0.0167"] == ads.simulate(
        sigma=0.10, delta=0.05, reps=20, boot=19, alpha=0.05 / 3, seed=8, **second
    )
    row = out["scenarios"][1]
    assert row["scenario"] == ads.SCENARIOS[1]["name"] and row["shape"] == "bounded"
    assert out["batch_alert_budget"][1] == {
        "validation_batches": 20,
        "beta_1_n_mean_if_max": 1 / 21,
        **ads.false_alert_moments(20, 0.95),
    }
    assert [b["validation_batches"] for b in out["batch_alert_budget"]] == [
        16,
        20,
        21,
        30,
        40,
        60,
        100,
    ]


def test_the_command_line_passes_its_arguments_and_writes_sorted_indented_json(
    tmp_path, monkeypatch
):
    import json

    seen = {}

    def fake(reps, boot, seed):
        seen.update(reps=reps, boot=boot, seed=seed)
        return {"b": 1, "a": 2}

    monkeypatch.setattr(ads, "evidence", fake)
    target = tmp_path / "e.json"
    assert ads.main(["--output", str(target)]) == 0
    assert seen == {"reps": 2000, "boot": 999, "seed": 2026}
    assert target.read_text() == json.dumps({"a": 2, "b": 1}, indent=1) + "\n"
    ads.main(["--reps", "3", "--boot", "4", "--seed", "5", "--output", str(target)])
    assert seen == {"reps": 3, "boot": 4, "seed": 5}
