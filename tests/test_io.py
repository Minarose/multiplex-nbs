"""Round-trip input formats and real local-HTTP job lifecycle checks."""
import io
import json
import unittest
from unittest.mock import patch

import numpy as np
from scipy.io import loadmat, savemat

from multiplex_nbs.io import describe, load_dataset, make_demo, result_csv, result_mat, result_text, run_dataset


def archive(data, suffix=".npz"):
    stream = io.BytesIO()
    if suffix == ".npz":
        np.savez_compressed(stream, **data)
    else:
        savemat(stream, data)
    stream.seek(0)
    return stream


class InputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo = make_demo()

    def test_npz_round_trip(self):
        loaded = load_dataset(archive(self.demo), ".npz")
        for key in self.demo:
            np.testing.assert_array_equal(loaded[key], self.demo[key])
        json.dumps(describe(loaded), allow_nan=False)

    def test_numeric_matlab_layout(self):
        data = dict(self.demo, W=np.moveaxis(self.demo["W"], 0, -1))
        loaded = load_dataset(archive(data, ".mat"), ".mat")
        np.testing.assert_array_equal(loaded["W"], self.demo["W"])
        np.testing.assert_array_equal(loaded["group"], self.demo["group"])

    def test_axis_metadata_round_trip_and_label_invariance(self):
        legacy = load_dataset(archive(self.demo), ".npz")
        self.assertEqual(describe(legacy)["axis"]["name"], "Frequency")
        timed = dict(self.demo, axis_name="Time", axis_unit="ms", axis_values=np.arange(8) * 50.)
        timed.pop("frequencies")
        timed["node_coordinates"] = np.zeros((12, 3))
        timed["coordinate_space"] = "Test coordinates"
        loaded = load_dataset(archive(timed), ".npz")
        self.assertEqual(describe(loaded)["axis"]["values"], list(range(0, 400, 50)))
        self.assertEqual(describe(loaded)["node_coordinates"], [[0., 0., 0.]] * 12)
        frequency_result = run_dataset(legacy, {"n_perm": 7})
        time_result = run_dataset(loaded, {"n_perm": 7})
        for field in ("statistic", "clusters", "null_max"):
            self.assertEqual(frequency_result[field], time_result[field])
        self.assertIn("Time, ms", time_result["methods"])
        self.assertIn(b"node", result_text(time_result))

    def test_invalid_axis_metadata_is_rejected(self):
        for fields in ({"axis_values": [1, 2]}, {"axis_name": ""}, {"axis_unit": "Hz\n" + "x" * 25},
                       {"layer_adjacency": "distance"}, {"node_coordinates": np.zeros((12, 2))},
                       {"axis_values": np.arange(8)}, {"demo_info_json": '{"value": NaN}'}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                load_dataset(archive(dict(self.demo, **fields)), ".npz")

    def test_matlab_cell_arrays_and_native_aliases(self):
        cells = np.empty((1, len(self.demo["W"])), dtype=object)
        for index, value in enumerate(self.demo["W"]):
            cells[0, index] = value[:, :, 0]  # One frequency is a 2D MATLAB matrix.
        labels = np.array(self.demo["node_labels"], dtype=object)
        groups = np.array(["A"] * 20 + ["B"] * 20, dtype=object)
        data = {"W": cells, "group": groups, "nodeLabels": labels,
                "exchangeBlocks": np.ones(40)}
        loaded = load_dataset(archive(data, ".mat"), ".mat")
        np.testing.assert_array_equal(loaded["W"], self.demo["W"][..., :1])
        np.testing.assert_array_equal(loaded["node_labels"], labels)
        np.testing.assert_array_equal(loaded["group"], groups)
        self.assertEqual(describe(loaded)["groups"], ["A", "B"])
        self.assertTrue(describe(loaded)["has_blocks"])

    def test_matlab_native_model(self):
        data = make_demo("glm")
        native = {"connectivity": data["W"], "model": {"X": data["X"], "C": data["C"][:, None], "statType": "F"}}
        loaded = load_dataset(archive(native, ".mat"), ".mat")
        self.assertEqual(describe(loaded)["stat_type"], "f")
        np.testing.assert_array_equal(loaded["X"], data["X"])
        result = run_dataset(loaded, {"design": "glm-f", "n_perm": 3})
        self.assertEqual(result["config"]["stat_type"], "f")

    def test_glm_demo_runs_without_group_conflict_or_mutating_settings(self):
        settings = {"design": "glm-t", "n_perm": 3}
        result = run_dataset(make_demo("glm"), settings)
        self.assertEqual(settings, {"design": "glm-t", "n_perm": 3})
        self.assertEqual(result["config"]["method"], "freedman-lane")
        self.assertEqual(result["config"]["group_values"], None)

    def test_design_readiness_distinguishes_connectivity_from_study_design(self):
        bare = {k: v for k, v in self.demo.items() if k != "group"}
        self.assertIsNone(describe(bare)["suggested_design"])
        self.assertFalse(describe(bare)["designs"]["two-sample"]["ready"])
        paired = describe(make_demo("paired"))
        self.assertEqual(paired["suggested_design"], "paired")
        self.assertEqual(len(paired["group_counts"]), 20)
        glm = make_demo("glm")
        glm["X"][:, 2] = glm["X"][:, 1]
        self.assertIn("independent columns", describe(glm)["designs"]["glm-t"]["issue"])

    def test_reporting_alpha_is_validated_and_recorded(self):
        for alpha in (0, 1, True, "0.05", float("nan")):
            with self.subTest(alpha=alpha), self.assertRaisesRegex(ValueError, "alpha"):
                run_dataset(self.demo, {"n_perm": 1, "alpha": alpha})
        self.assertEqual(run_dataset(self.demo, {"n_perm": 1, "alpha": .01})["reporting"], {"alpha": .01})

    def test_result_mat_preserves_full_json(self):
        result = run_dataset(self.demo, {"n_perm": 3})
        saved = loadmat(io.BytesIO(result_mat(result)))
        self.assertEqual(json.loads(saved["result_json"].item()), result)
        np.testing.assert_array_equal(saved["statistic"], result["statistic"])

    def test_csv_metadata_is_plain_spreadsheet_text(self):
        result = run_dataset(dict(self.demo, axis_name="=1+1", axis_unit="@example"), {"n_perm": 1})
        self.assertIn(b"'=1+1,'@example", result_csv(result))
        self.assertEqual(result["dataset"]["axis"]["name"], "=1+1")

    def test_malformed_or_unsafe_inputs(self):
        for suffix in (".npz", ".mat"):
            for body in (b"", b"not an array"):
                with self.subTest(suffix=suffix, body=body), self.assertRaises(ValueError):
                    load_dataset(io.BytesIO(body), suffix)
        for fields in (
            {}, {"W": np.zeros((0, 3, 3, 2))}, {"W": self.demo["W"].astype(complex)},
            dict(self.demo, W=np.full_like(self.demo["W"], np.nan)),
            dict(self.demo, group=np.array([1, 2])),
            dict(self.demo, node_labels=np.array(["one"])),
            dict(self.demo, frequencies=np.zeros(8)),
            dict(self.demo, X=np.ones((40, 1))),
            dict(self.demo, X=np.ones((40, 2)), C=np.ones((1, 3))),
            dict(self.demo, group=np.array([None] * 40)),
        ):
            with self.subTest(fields=list(fields)), self.assertRaises(ValueError):
                load_dataset(archive(fields), ".npz")

    def test_expanded_npz_size_is_bounded_before_loading(self):
        with self.assertRaisesRegex(ValueError, "Expanded NPZ"):
            load_dataset(archive(self.demo), ".npz", max_uncompressed_bytes=100)

if __name__ == "__main__":
    unittest.main()
