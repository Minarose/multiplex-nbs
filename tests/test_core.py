"""Small regression suite for mathematical behavior and inference boundaries."""

import json
import unittest

import numpy as np
from scipy import stats

from multiplex_nbs import analyze, build_clusters


def networks(y, n_nodes=3, n_freq=2):
    """Place S × E × F data in the MATLAB-order upper triangle."""
    y = np.asarray(y)
    w = np.zeros((len(y), n_nodes, n_nodes, n_freq))
    j, i = np.tril_indices(n_nodes, -1)
    w[:, i, j, :] = y.reshape(len(y), len(i), n_freq)
    w[:, j, i, :] = w[:, i, j, :]
    return w


class ClusterTests(unittest.TestCase):
    def test_classic_extent_and_intensity(self):
        # A triangle with a pendant edge, a disjoint edge, and a threshold tie.
        edges = [[0, 1], [0, 2], [1, 2], [2, 3], [3, 4], [4, 5]]
        statistic = [[4], [5], [3.25], [4], [3], [8]]
        for sign, tail in [(1, "right"), (-1, "left")]:
            classic = build_clusters(np.array(statistic) * sign, edges, 6, threshold=3,
                                     tail=tail, metric="intensity", inference_mode="classic")
            self.assertEqual([c["extent"] for c in classic], [4, 1])
            self.assertEqual([c["intensity"] for c in classic], [4.25, 5])
            self.assertEqual([c["test_stat"] for c in classic], [4.25, 5])
            self.assertEqual([c["mass"] for c in classic], [16.25, 8])
            self.assertEqual([c["n_nodes"] for c in classic], [4, 2])
            mass = build_clusters(np.array(statistic) * sign, edges, 6, threshold=3,
                                  tail=tail, metric="mass", inference_mode="classic")
            self.assertEqual([c["test_stat"] for c in mass], [16.25, 8])

    def test_node_frequency_links_and_mass(self):
        edges = [[0, 1], [0, 2], [1, 2], [2, 3]]
        t = np.array([[4, 0, 0], [0, 5, 0], [0, 0, 0], [0, 0, 6]])
        clusters = build_clusters(t, edges, 4, threshold=3, metric="mass")
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["extent"], 6)
        self.assertEqual(clusters[0]["mass"], 15)
        self.assertEqual(clusters[0]["sites"], [[1, 1], [2, 1], [1, 2], [3, 2], [3, 3], [4, 3]])
        self.assertEqual(clusters[0]["test_stat"], 15)
        # Intensity subtracts the threshold once per retained edge: 15 - 3 edges x 3.
        self.assertEqual(clusters[0]["intensity"], 6)
        intensity = build_clusters(t, edges, 4, threshold=3, metric="intensity")
        self.assertEqual(intensity[0]["test_stat"], 6)
        layerwise = build_clusters(t, edges, 4, threshold=3, metric="intensity", layer_adjacency="independent")
        self.assertEqual(sorted(c["intensity"] for c in layerwise), [1, 2, 3])

    def test_missing_middle_bin_breaks_connection(self):
        clusters = build_clusters([[4, 0, 4]], [[0, 1]], 2)
        self.assertEqual(len(clusters), 2)
        self.assertEqual([c["extent"] for c in clusters], [2, 2])

    def test_independent_layers_do_not_connect(self):
        clusters = build_clusters([[4, 5]], [[0, 1]], 2, layer_adjacency="independent")
        self.assertEqual([c["layer_bins"] for c in clusters], [[1], [2]])
        self.assertEqual([c["extent"] for c in clusters], [2, 2])
        self.assertEqual([c["mass"] for c in clusters], [4, 5])
        self.assertEqual(len(build_clusters([[4, 5]], [[0, 1]], 2)), 1)

    def test_two_tails_do_not_merge(self):
        clusters = build_clusters([[4, -5]], [[0, 1]], 2, tail="both")
        self.assertEqual([c["tail"] for c in clusters], ["right", "left"])
        self.assertEqual([c["extent"] for c in clusters], [2, 2])

    def test_strict_threshold_and_empty_map(self):
        self.assertEqual(build_clusters([[3, -3]], [[0, 1]], 2, tail="both"), [])

    def test_invalid_edges(self):
        for edges in ([[1, 0]], [[0, 0]], [[0, 2]], [[0, 0.5]]):
            with self.subTest(edges=edges), self.assertRaises(ValueError):
                build_clusters([[4]], edges, 2)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(41)
        self.y = self.rng.normal(size=(24, 6))
        self.w = networks(self.y)
        self.group = np.repeat([0, 1], 12)

    def run_analysis(self, **kwargs):
        options = {"group": self.group, "n_perm": 11, "seed": 7}
        options.update(kwargs)
        return analyze(self.w, **options)

    def test_welch_statistic_matches_scipy(self):
        result = self.run_analysis()
        expected = stats.ttest_ind(self.y[:12], self.y[12:], equal_var=False).statistic
        np.testing.assert_allclose(np.array(result["statistic"]).ravel(), expected, rtol=1e-12)
        self.assertEqual(result["edges"], [[1, 2], [1, 3], [2, 3]])
        json.dumps(result, allow_nan=False)

    def test_classic_permutation_maxima_and_layer_selection(self):
        # Any subset of the three possible edges on three nodes is connected.
        layer = self.w[..., 1]
        vals = self.y.reshape(24, 3, 2)[..., 1]
        for metric in ["extent", "mass", "intensity"]:
            settings = dict(group=self.group, inference_mode="classic", metric=metric,
                            threshold=.65, tail="both", n_perm=15, seed=119)
            run = analyze(self.w, classic_layer=2, **settings)
            direct = analyze(layer, **settings)
            self.assertEqual(run["config"]["classic_layer"], 2)
            self.assertEqual(run["clusters"], direct["clusters"])
            self.assertEqual(run["null_max"], direct["null_max"])
            rng = np.random.default_rng(119)
            maxima = []
            for _ in range(15):
                group = rng.permutation(self.group)
                t = stats.ttest_ind(vals[group == 0], vals[group == 1], equal_var=False).statistic
                if metric == "extent":
                    scores = [(sign * t > .65).sum() for sign in (1, -1)]
                elif metric == "mass":
                    scores = [np.where(sign * t > .65, sign * t, 0).sum() for sign in (1, -1)]
                else:
                    scores = [np.maximum(sign * t - .65, 0).sum() for sign in (1, -1)]
                maxima.append(max(scores))
            np.testing.assert_allclose(run["null_max"], maxima)
            for component in run["clusters"]:
                self.assertEqual(component["p_fwe"], (1 + sum(n >= component["test_stat"] for n in run["null_max"])) / 16)

        for options in [{}, {"classic_layer": 3}, {"classic_layer": 1, "metric": "size"}]:
            with self.assertRaises(ValueError):
                self.run_analysis(inference_mode="classic", **options)

    def test_classic_io_reports_original_axis_and_extent_units(self):
        from multiplex_nbs.io import load_dataset, result_csv, result_text, run_dataset, validate_dataset
        from scipy.io import savemat
        from io import BytesIO
        data = validate_dataset({"W": self.w, "group": self.group, "axis_values": [10, 12],
                                 "axis_name": "Frequency", "axis_unit": "Hz"})
        run = run_dataset(data, {"inference_mode": "classic", "classic_layer": 2, "threshold": .1, "n_perm": 3})
        self.assertEqual(run["dataset"]["axis"]["values"], [12.0])
        self.assertEqual(data["axis_values"].tolist(), [10, 12])
        self.assertEqual(run["dataset"]["layer_count"], 1)
        self.assertIn("input layer 2 (Frequency = 12 Hz)", run["methods"])
        self.assertIn("retained edges", run["methods"])
        self.assertIn(b"extent (edges) | mass", result_text(run))
        self.assertIn(b"classic,extent,edges", result_csv(run))
        for kind in ("mat", "npz"):
            f = BytesIO()
            if kind == "mat":
                savemat(f, {"W": np.moveaxis(self.w[..., 1], 0, -1), "group": self.group})
            else:
                np.savez(f, W=self.w[..., 1], group=self.group)
            f.seek(0)
            loaded = load_dataset(f, "."+kind)
            np.testing.assert_array_equal(loaded["W"], self.w[..., 1:2])

    def test_one_sample_mean_and_t_use_whole_observation_sign_flips(self):
        from multiplex_nbs.io import describe, run_dataset, validate_dataset
        # One network edge per layer, so its weighted score is independently calculable.
        values = self.rng.normal(loc=.2, scale=.7, size=11)
        w = networks(values, n_nodes=2, n_freq=1)
        data = validate_dataset({"W": w})
        self.assertTrue(describe(data)["designs"]["one-sample"]["ready"])
        for mode, metric in [("classic", "intensity"), ("multiplex", "mass")]:
            opts = dict(inference_mode=mode, metric=metric, design="one-sample", tail="both",
                        n_perm=19, seed=18, threshold=.1)
            r = run_dataset(data, opts)
            def reference_stat(sample):
                if mode == "classic":
                    return np.mean(sample)
                return stats.ttest_1samp(sample, 0).statistic
            self.assertEqual(r["config"]["stat_type"], "mean" if mode == "classic" else "t")
            self.assertAlmostEqual(r["statistic"][0][0], reference_stat(values))
            rng = np.random.default_rng(18)
            expected = []
            for _ in range(19):
                score = abs(reference_stat(values * rng.choice([-1, 1], size=11)))
                expected.append((score - .1 if mode == "classic" else score) if score > .1 else 0)
            np.testing.assert_allclose(r["null_max"], expected)
        for invalid in [{"use_abs": True}, {"group": [1]*11}, {"exchange_blocks": [1]*11},
                        {"X": np.ones((11,1)), "C": [1]}, {"method": "rowshuffle"}]:
            with self.assertRaises(ValueError):
                analyze(w, test="one-sample", n_perm=1, **invalid)

    def test_paired_sign_flips_and_statistic(self):
        ids = np.tile(np.arange(12), 2)
        result = self.run_analysis(group=ids, test="paired")
        expected = stats.ttest_rel(self.y[:12], self.y[12:]).statistic
        np.testing.assert_allclose(np.array(result["statistic"]).ravel(), expected, rtol=1e-12)
        self.assertEqual(result["config"]["pair_indices"][0], [1, 13])
        self.assertEqual(result["config"]["method"], "sign-flip")

    def test_glm_t_matches_independent_ols(self):
        nuisance = self.rng.normal(size=24)
        x = np.column_stack((np.ones(24), self.group, nuisance))
        result = self.run_analysis(group=None, X=x, C=[0, 1, 0])
        beta = np.linalg.lstsq(x, self.y, rcond=None)[0]
        sigma2 = np.sum((self.y - x @ beta) ** 2, axis=0) / 21
        expected = beta[1] / np.sqrt(sigma2 * np.linalg.inv(x.T @ x)[1, 1])
        np.testing.assert_allclose(np.array(result["statistic"]).ravel(), expected, rtol=1e-12)
        self.assertEqual(result["config"]["method"], "freedman-lane")

    def test_glm_f_is_t_squared_for_single_contrast(self):
        x = np.column_stack((np.ones(24), self.group, self.rng.normal(size=24)))
        t = self.run_analysis(group=None, X=x, C=[0, 1, 0])
        f = self.run_analysis(group=None, X=x, C=[0, 1, 0], stat_type="F")
        np.testing.assert_allclose(f["statistic"], np.array(t["statistic"]) ** 2, rtol=1e-12)

    def test_glm_multirow_f_matches_nested_model(self):
        x = np.column_stack((np.ones(24), self.group, self.rng.normal(size=24)))
        c = [[0, 1, 0], [0, 0, 1]]
        result = self.run_analysis(group=None, X=x, C=c, stat_type="F")
        full = x @ np.linalg.lstsq(x, self.y, rcond=None)[0]
        ss_full = np.sum((self.y - full) ** 2, axis=0)
        ss_reduced = np.sum((self.y - self.y.mean(axis=0)) ** 2, axis=0)
        expected = ((ss_reduced - ss_full) / 2) / (ss_full / 21)
        np.testing.assert_allclose(np.array(result["statistic"]).ravel(), expected, rtol=1e-12)

    def test_freedman_lane_first_draw_matches_manual(self):
        x = np.column_stack((np.ones(24), self.group, self.rng.normal(size=24)))
        threshold = 0.3
        result = self.run_analysis(group=None, X=x, C=[0, 1, 0], n_perm=1,
                                   threshold=threshold, metric="mass", tail="both")
        reduced = x[:, [0, 2]]
        fitted = reduced @ np.linalg.lstsq(reduced, self.y, rcond=None)[0]
        indices = np.random.default_rng(7).permutation(24)
        perm_y = fitted + (self.y - fitted)[indices]
        beta = np.linalg.lstsq(x, perm_y, rcond=None)[0]
        s2 = np.sum((perm_y - x @ beta) ** 2, axis=0) / 21
        t = beta[1] / np.sqrt(s2 * np.linalg.inv(x.T @ x)[1, 1])
        clusters = build_clusters(t.reshape(3, 2), [[0, 1], [0, 2], [1, 2]], 3,
                                  threshold, "both", "mass")
        self.assertAlmostEqual(result["null_max"][0], max(c["mass"] for c in clusters))

    def test_rowshuffle_matches_design_row_permutation(self):
        x = np.column_stack((np.ones(24), self.group, self.rng.normal(size=24)))
        blocks = np.tile(np.arange(12), 2)
        result = self.run_analysis(group=None, X=x, C=[0, 1, 0], n_perm=1,
                                   threshold=0.2, metric="mass", method="rowshuffle", exchange_blocks=blocks)
        rng = np.random.default_rng(7)
        indices = np.arange(24)
        for block in np.unique(blocks):
            idx = np.flatnonzero(blocks == block)
            indices[idx] = rng.permutation(idx)
        xp = x[indices]
        beta = np.linalg.lstsq(xp, self.y, rcond=None)[0]
        s2 = np.sum((self.y - xp @ beta) ** 2, axis=0) / 21
        t = beta[1] / np.sqrt(s2 * np.linalg.inv(xp.T @ xp)[1, 1])
        clusters = build_clusters(t.reshape(3, 2), [[0, 1], [0, 2], [1, 2]], 3, 0.2, "right", "mass")
        self.assertAlmostEqual(result["null_max"][0], max(c["mass"] for c in clusters))

    def test_two_tails_share_null_maximum_and_plus_one(self):
        settings = {"threshold": 0.5, "metric": "mass"}
        right = self.run_analysis(tail="right", **settings)
        left = self.run_analysis(tail="left", **settings)
        both = self.run_analysis(tail="both", **settings)
        np.testing.assert_allclose(both["null_max"], np.maximum(right["null_max"], left["null_max"]))
        null = np.array(both["null_max"])
        for cluster in both["clusters"]:
            self.assertEqual(cluster["p_fwe"], (1 + np.sum(null >= cluster["test_stat"])) / 12)
            self.assertGreaterEqual(cluster["p_fwe"], 1 / 12)

    def test_independent_layers_share_one_correction_family(self):
        settings = dict(group=self.group, threshold=.5, tail="both", metric="mass",
                        n_perm=7, seed=19, layer_adjacency="independent")
        combined = analyze(self.w, **settings)
        separate = [analyze(self.w[..., i:i+1], **settings) for i in range(2)]
        np.testing.assert_allclose(combined["null_max"], np.maximum(*[r["null_max"] for r in separate]))
        self.assertTrue(all(c["n_layers"] == 1 for c in combined["clusters"]))
        self.assertEqual(combined["dimensions"]["n_layers"], 2)

    def test_reproducibility_and_progress(self):
        calls = []
        first = self.run_analysis(progress=lambda done, total: calls.append((done, total)))
        self.assertEqual(first, self.run_analysis())
        self.assertEqual(calls, [(i, 11) for i in range(12)])

    def test_constant_null_features_are_zero(self):
        result = analyze(np.zeros_like(self.w), group=self.group, n_perm=2)
        self.assertEqual(result["clusters"], [])
        self.assertEqual(result["null_max"], [0, 0])
        x = np.column_stack((np.ones(24), self.group))
        glm = analyze(np.zeros_like(self.w), X=x, C=[0, 1], n_perm=2)
        self.assertEqual(glm["clusters"], [])

    def test_invalid_inputs_are_rejected(self):
        invalid = [
            {"n_perm": 0}, {"n_perm": 2.5}, {"n_perm": True}, {"seed": -1},
            {"threshold": 0}, {"threshold": float("nan")}, {"threshold": "3"},
            {"threshold": True}, {"tail": "invalid"},
            {"metric": "size"}, {"layer_adjacency": "circular"}, {"test": "invalid"}, {"group": np.ones(24)},
            {"group": np.full(24, np.nan)}, {"exchange_blocks": self.group},
            {"test": "paired"}, {"stat_type": "F"}, {"method": "freedman-lane"},
            {"group": None, "X": np.ones((24, 1)), "C": [1]},
            {"group": None, "X": np.ones((24, 2)), "C": [0, 1]},
        ]
        for options in invalid:
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.run_analysis(**options)
        for w in (self.w[..., 0], self.w.astype(complex), np.full_like(self.w, np.nan)):
            with self.subTest(shape=w.shape), self.assertRaises(ValueError):
                analyze(w, group=self.group, n_perm=2)
        asymmetric = self.w.copy()
        asymmetric[0, 0, 1, 0] += 1
        with self.assertRaisesRegex(ValueError, "symmetric"):
            analyze(asymmetric, group=self.group, n_perm=2)

    def test_nonzero_constant_effect_rejected(self):
        y = np.repeat(self.group[:, None], 6, axis=1)
        with self.assertRaisesRegex(ValueError, "zero error variance"):
            analyze(networks(y), group=self.group, n_perm=2)
        x = np.column_stack((np.ones(24), self.group))
        with self.assertRaisesRegex(ValueError, "zero residual variance"):
            analyze(networks(y), X=x, C=[0, 1], n_perm=2)


if __name__ == "__main__":
    unittest.main()
