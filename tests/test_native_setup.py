"""Native model and metadata regressions; set NBS_TEST_DESKTOP=1 to exercise Tk."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from multiplex_nbs.io import dataset_npz, describe, load_dataset, make_demo, run_dataset, validate_dataset

try:
    import tkinter as tk
    from tkinter import ttk
    from multiplex_nbs import native_setup as setup
except ImportError:
    setup = None


@unittest.skipIf(setup is None, "Tk unavailable")
class NativeFormInputs(unittest.TestCase):
    def test_table_input_preserves_rows_and_rejects_missing_cells(self):
        np.testing.assert_equal(setup._matrix("1, 2;3,4", "X"), [[1, 2], [3, 4]])
        np.testing.assert_equal(setup._matrix("1\t2\n3\t4", "X"), [[1, 2], [3, 4]])
        for text in ["1,,2;3,,4", "1,2;3", "nan,1", ""]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                setup._matrix(text, "X")

    def test_labels_preserve_punctuation_and_spaces(self):
        labels = ["Site; one", "Study, cohort", 'Unit "A"', "Control arm"]
        self.assertEqual(setup._label_vector(setup._labels_text(labels)), labels)
        self.assertEqual(setup._label_vector("a\nb\na\nb"), ["a", "b", "a", "b"])


@unittest.skipUnless(setup and os.environ.get("NBS_TEST_DESKTOP") == "1", "Requires desktop Tk")
class NativeModelInteraction(unittest.TestCase):
    def setUp(self):
        self.window = tk.Tk()
        self.window.withdraw()
        self.addCleanup(self.window.destroy)
        self.data = validate_dataset(make_demo())
        self.description = describe(self.data)
        self.name = "Test input"
        self.config = {"inference_mode": "multiplex", "design": "two-sample",
                       "threshold": 3, "n_perm": 3, "seed": 7}
        self.root = self.window
        self.parent = ttk.Frame(self.window)
        self.parent.pack(fill="both", expand=True)
        self.executed = None
        setup.model_page(self, self.parent)

    def start(self, config):
        self.executed = run_dataset(self.data, config)

    def load_data(self, data, name, mode=None):
        self.data, self.name, self.description = data, name, describe(data)
        self.config = {"inference_mode": mode, "design": self.description["suggested_design"],
                       "layer_adjacency": self.description["axis"]["adjacency"]}

    def descendants(self, widget):
        for child in widget.winfo_children():
            yield child
            yield from self.descendants(child)

    def find(self, predicate):
        return next(widget for widget in self.descendants(self.parent) if predicate(widget))

    def choose(self, label):
        combo = self.find(lambda w: isinstance(w, ttk.Combobox) and label in w["values"])
        combo.current(combo["values"].index(label))
        # Tk can omit virtual events for withdrawn windows. Model readiness must
        # follow the selected value just as it does when a visible menu closes.
        self.assertEqual(combo.get(), label)

    def run_button(self):
        return self.find(lambda w: isinstance(w, ttk.Button) and w["text"] == "Run permutations")

    def test_subtract_threshold_box_appears_under_mass_and_selects_intensity(self):
        box = self.find(lambda w: isinstance(w, ttk.Checkbutton) and w["text"] == setup.SUBTRACT_LABEL)
        self.assertFalse(box.winfo_ismapped() or box.grid_info())
        for method in ("Multiplex-NBS", "Layer-wise NBS", "Classic NBS"):
            with self.subTest(method=method):
                self.choose(method)
                if method == "Classic NBS":
                    self.choose(next(v for v in self.find(lambda w: isinstance(w, ttk.Combobox) and
                                                          any(" · " in str(x) and x[0].isdigit() for x in w["values"]))["values"]))
                self.choose("Mass · summed edge statistics")
                self.assertTrue(box.grid_info())
                self.assertEqual(self.remember_model()["metric"], "mass")
                box.invoke()
                self.assertEqual(self.remember_model()["metric"], "intensity")
                self.run_button().invoke()
                self.assertEqual(self.executed["config"]["metric"], "intensity")
                cluster = self.executed["clusters"][0]
                self.assertEqual(cluster["test_stat"], cluster["intensity"])
                box.invoke()
                extent = next(v for v in self.find(lambda w: isinstance(w, ttk.Combobox) and
                                                   "Mass · summed edge statistics" in w["values"])["values"]
                              if v.startswith("Extent"))
                self.choose(extent)
                self.assertFalse(box.grid_info())
                self.assertEqual(self.remember_model()["metric"], "extent")

    def test_classic_stack_and_one_sample_threshold(self):
        self.run_button().invoke()
        self.assertEqual(self.executed["config"]["inference_mode"], "multiplex")
        self.choose("Classic NBS")
        self.assertTrue(self.run_button().instate(["disabled"]))
        self.choose("3 · 8 Hz")
        self.choose("One sample")
        self.assertEqual(self.remember_model()["threshold"], "")
        self.assertTrue(self.run_button().instate(["disabled"]))
        threshold = self.find(lambda w: type(w) is ttk.Entry and w.get() == "")
        threshold.insert(0, "0.2")
        self.assertFalse(self.run_button().instate(["disabled"]))
        self.run_button().invoke()
        self.assertEqual(self.executed["config"]["stat_type"], "mean")
        self.assertEqual(self.executed["config"]["classic_layer"], 3)
        self.choose("Multiplex-NBS")
        self.assertEqual(self.remember_model()["threshold"], "")
        self.assertNotIn("classic_layer", self.remember_model())

    def test_glm_readiness_and_reference_draft(self):
        self.choose("GLM · F contrast")
        self.assertTrue(self.run_button().instate(["disabled"]))
        self.assertEqual(self.remember_model()["tail"], "right")
        self.assertEqual(self.remember_model()["threshold"], "")

    def test_one_layer_import_and_npz_round_trip_use_native_file_dialogs(self):
        single = validate_dataset({"W": self.data["W"][..., 0], "group": self.data["group"]})
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder, "study.npz")
            source.write_bytes(dataset_npz(single))
            with patch.object(setup.filedialog, "askopenfilename", return_value=str(source)):
                setup._import_dataset(self)
            self.assertEqual(self.config["inference_mode"], "classic")
            target = Path(folder, "reusable.npz")
            with patch.object(setup.filedialog, "asksaveasfilename", return_value=str(target)):
                setup._save_data(self)
            np.testing.assert_equal(load_dataset(target)["W"], single["W"])

    def test_metadata_edit_retains_the_original_model(self):
        self.choose("Classic NBS")
        self.choose("3 · 8 Hz")
        self.pages = {"model": self.parent}
        def rename_axis(app, title, help_text, rows, apply):
            apply(["Time", "ms", "0, 25, 50, 75, 100, 125, 150, 175", setup.ADJACENCY["independent"]])
        with patch.object(setup, "_dialog", side_effect=rename_axis):
            setup._edit_axis(self)
        self.assertEqual(self.config["classic_layer"], 3)
        self.assertEqual(self.config["n_perm"], "3")
        self.assertEqual(self.config["layer_adjacency"], "independent")
        self.assertEqual(self.description["axis"]["values"][2], 50)


if __name__ == "__main__":
    unittest.main()
