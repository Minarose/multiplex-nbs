"""The documented public API: every function a researcher is told to call."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

import multiplex_nbs as m


class PublicApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo = m.load_demo()
        cls.result = m.multiplex_nbs(cls.demo, n_perm=99, seed=1)

    def test_three_methods_share_one_engine(self):
        layerwise = m.layerwise_nbs(self.demo, n_perm=19)
        classic = m.classic_nbs(self.demo, layer=3, metric="intensity", n_perm=19)
        self.assertEqual(self.result["config"]["layer_adjacency"], "consecutive")
        self.assertEqual(layerwise["config"]["layer_adjacency"], "independent")
        self.assertEqual(classic["config"]["inference_mode"], "classic")
        self.assertEqual(classic["config"]["classic_layer"], 3)

    def test_planted_effect_is_recovered_by_multiplex(self):
        best = m.components(self.result, significant_only=True)[0]
        self.assertIn(100.0, best["axis_values"])
        self.assertTrue(best["significant"])
        self.assertEqual(best["direction"], "positive")
        self.assertEqual(len(best["regions"]), best["n_regions"])

    def test_arrays_in_give_the_same_answer_as_a_dataset(self):
        data = self.demo
        from_arrays = m.nbs(data["W"], data["group"], axis_values=data["axis_values"], n_perm=99, seed=1)
        self.assertEqual([c["p_fwe"] for c in from_arrays["clusters"]], [c["p_fwe"] for c in self.result["clusters"]])

    def test_designs(self):
        for name, test in (("paired", "paired"), ("glm", "glm"), ("two-sample", "two-sample")):
            with self.subTest(name=name):
                self.assertEqual(m.multiplex_nbs(m.load_demo(name), n_perm=9)["config"]["test"], test)

    def test_classic_on_a_stack_requires_a_prespecified_layer(self):
        with self.assertRaises(ValueError):
            m.classic_nbs(self.demo, n_perm=9)

    def test_results_save_and_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            for suffix in (".json", ".csv", ".mat", ".txt"):
                path = m.save_results(self.result, Path(folder, "result" + suffix))
                self.assertGreater(path.stat().st_size, 100)
            back = m.load_results(Path(folder, "result.json"))
            self.assertEqual(back["clusters"], json.loads(json.dumps(self.result["clusters"])))
            with self.assertRaises(ValueError):
                m.save_results(self.result, Path(folder, "result.xlsx"))

    def test_alpha_changes_reporting_only(self):
        result = json.loads(json.dumps(self.result))
        before = [c["p_fwe"] for c in result["clusters"]]
        m.set_alpha(result, .001)
        self.assertEqual([c["p_fwe"] for c in result["clusters"]], before)
        self.assertFalse(m.components(result, significant_only=True))

    def test_dataset_round_trip_and_zip_builder(self):
        w = self.demo["W"]
        with tempfile.TemporaryDirectory() as folder:
            saved = m.save_dataset(self.demo, Path(folder, "demo"))
            self.assertEqual(saved.suffix, ".npz")
            np.testing.assert_allclose(m.load_dataset(saved)["W"], w)
            archives = []
            for label, rows in (("A", range(0, 20)), ("B", range(20, 40))):
                path = Path(folder, f"{label}.zip")
                with zipfile.ZipFile(path, "w") as archive:
                    for k in rows:
                        buffer = io.BytesIO()
                        np.save(buffer, w[k])
                        archive.writestr(f"sub-{k:02d}.npy", buffer.getvalue())
                archives.append((label, path))
            built = m.build_dataset(archives, axis_name="Time", axis_unit="ms", first_value=0, step=50)
            np.testing.assert_allclose(built["W"], w)
            self.assertEqual(list(built["axis_values"][:2]), [0, 50])

    def test_make_dataset_validates(self):
        with self.assertRaises(ValueError):
            m.make_dataset(np.ones((4, 3, 2)))  # not square
        data = m.make_dataset(self.demo["W"], X=np.column_stack([np.ones(40), np.repeat([0, 1], 20)]), C=[0, 1])
        self.assertEqual(data["stat_type"], "t")
        self.assertEqual(m.describe(data)["suggested_design"], "glm-t")

    def test_report_and_methods_text(self):
        text = m.report(self.result)
        self.assertIn("METHODS DRAFT", text)
        self.assertIn("Multiplex-NBS 0.1.0", self.result["methods"])

    def test_figures(self):
        try:
            import matplotlib
        except ImportError:
            self.skipTest("matplotlib is optional")
        matplotlib.use("Agg")
        for plot in (m.plot_layer_profile, m.plot_membership, m.plot_null_distribution):
            with self.subTest(plot=plot.__name__):
                self.assertTrue(plot(self.result).has_data() or plot.__name__ == "plot_membership")

    def test_command_line(self):
        from multiplex_nbs.__main__ import main
        with tempfile.TemporaryDirectory() as folder:
            main(["demo", str(Path(folder, "demo.npz")), "--name", "two-sample"])
            main(["run", str(Path(folder, "demo.npz")), "--output", str(Path(folder, "out.csv")), "--n-perm", "9"])
            self.assertTrue(Path(folder, "out.csv").read_text().startswith("cluster"))


if __name__ == "__main__":
    unittest.main()
