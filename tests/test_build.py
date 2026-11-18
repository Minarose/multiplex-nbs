"""Building a dataset from one ZIP archive per group, and adding node coordinates."""
import io
import unittest
import zipfile

import numpy as np
from scipy.io import savemat

from multiplex_nbs.io import build_dataset, describe, load_dataset, read_coordinates, set_coordinates


def symmetric(rng, nodes=6, layers=3):
    m = rng.normal(size=(nodes, nodes, layers))
    return (m + m.transpose(1, 0, 2)) / 2


def mat_bytes(**arrays):
    stream = io.BytesIO()
    savemat(stream, arrays, do_compression=True)
    return stream.getvalue()


def npy_bytes(array):
    stream = io.BytesIO()
    np.save(stream, array)
    return stream.getvalue()


def zipped(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
    return stream.getvalue()


class BuildTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(3)
        self.a = {f"CTL{i}_plv.mat": symmetric(rng) for i in (10, 2, 1)}
        self.b = {f"PRM{i}_plv.mat": symmetric(rng) for i in (5, 7)}
        self.zip_a = zipped({f"controls/{k}": mat_bytes(plv=v) for k, v in self.a.items()}
                            | {"__MACOSX/controls/._CTL1_plv.mat": b"junk", "controls/.DS_Store": b"x", "controls/notes.docx": b"x"})
        self.zip_b = zipped({k: mat_bytes(plv=v) for k, v in self.b.items()})

    def test_groups_come_from_archives_in_natural_file_order(self):
        data = build_dataset([("Control", self.zip_a), ("Preterm", self.zip_b)],
                             axis={"name": "Frequency", "unit": "Hz", "start": 4, "step": 2})
        self.assertEqual(data["W"].shape, (5, 6, 6, 3))
        self.assertEqual(data["group"].tolist(), ["Control"] * 3 + ["Preterm"] * 2)
        self.assertEqual(data["observation_ids"].tolist(), [
            "Control/CTL1_plv.mat", "Control/CTL2_plv.mat", "Control/CTL10_plv.mat",
            "Preterm/PRM5_plv.mat", "Preterm/PRM7_plv.mat"])
        np.testing.assert_allclose(data["W"][2], self.a["CTL10_plv.mat"])
        np.testing.assert_allclose(data["W"][4], self.b["PRM7_plv.mat"])
        self.assertEqual(data["axis_values"].tolist(), [4, 6, 8])
        info = describe(data)
        self.assertEqual(info["suggested_design"], "two-sample")
        self.assertEqual(info["observation_ids"][0], "Control/CTL1_plv.mat")

    def test_npy_and_single_layer_text_files(self):
        rng = np.random.default_rng(4)
        m = [symmetric(rng, 4, 1)[..., 0] for _ in range(4)]
        text = lambda x, sep: "\n".join(sep.join(f"{v:.17g}" for v in row) for row in x).encode()
        data = build_dataset([("A", zipped({"s1.npy": npy_bytes(m[0]), "s2.csv": b"n1,n2,n3,n4\n" + text(m[1], ",")})),
                              ("B", zipped({"s3.txt": text(m[2], " "), "s4.tsv": text(m[3], "\t")}))])
        self.assertEqual(data["W"].shape, (4, 4, 4, 1))
        np.testing.assert_allclose(data["W"][1, ..., 0], m[1])
        np.testing.assert_allclose(data["W"][3, ..., 0], m[3])

    def test_mat_variable_choice_and_clear_errors(self):
        rng = np.random.default_rng(5)
        two = zipped({"s1.mat": mat_bytes(plv=symmetric(rng), coh=symmetric(rng)),
                      "s2.mat": mat_bytes(plv=symmetric(rng), coh=symmetric(rng))})
        with self.assertRaisesRegex(ValueError, r"2 numeric variables \(coh, plv\)"):
            build_dataset([("A", two), ("B", self.zip_b)])
        with self.assertRaisesRegex(ValueError, "no numeric variable named 'xyz'"):
            build_dataset([("A", two), ("B", self.zip_b)], variable="xyz")
        self.assertEqual(build_dataset([("A", two), ("B", self.zip_b)], variable="plv")["W"].shape[0], 4)
        odd = zipped({"s9.mat": mat_bytes(plv=symmetric(rng, nodes=5))})
        with self.assertRaisesRegex(ValueError, "B/s9.mat is 5 × 5 × 3, but Control/.*6 × 6 × 3"):
            build_dataset([("Control", self.zip_a), ("B", odd)])
        with self.assertRaisesRegex(ValueError, "No participant files"):
            build_dataset([("A", zipped({"readme.md": b"x"}))])
        with self.assertRaisesRegex(ValueError, "different name"):
            build_dataset([("A", self.zip_a), ("A", self.zip_b)])
        with self.assertRaisesRegex(ValueError, "not a readable ZIP"):
            build_dataset([("A", b"not a zip")])
        with self.assertRaisesRegex(ValueError, "symmetric"):
            build_dataset([("A", zipped({"s.npy": npy_bytes(rng.normal(size=(4, 4)))}))])

    def test_coordinates_formats_units_and_labels(self):
        xyz = np.array([[-40.5, 20, 10], [38, -22, 5], [0, -60, 30]])
        coords, labels = read_coordinates(b"x y z\n" + "\n".join(" ".join(map(str, r)) for r in xyz).encode(), "c.txt", 3)
        np.testing.assert_allclose(coords, xyz)
        self.assertIsNone(labels)
        text = "region,x,y,z\n" + "\n".join(f"R{i},{r[0] / 10},{r[1] / 10},{r[2] / 10}" for i, r in enumerate(xyz))
        coords, labels = read_coordinates(text.encode(), "c.csv", 3, "cm")
        np.testing.assert_allclose(coords, xyz)
        self.assertEqual(labels, ["R0", "R1", "R2"])
        np.testing.assert_allclose(read_coordinates(npy_bytes(xyz), "c.npy", 3)[0], xyz)
        np.testing.assert_allclose(read_coordinates(mat_bytes(coords=xyz), "c.mat", 3)[0], xyz)
        with self.assertRaisesRegex(ValueError, "needs 4 rows"):
            read_coordinates(npy_bytes(xyz), "c.npy", 4)
        with self.assertRaisesRegex(ValueError, "three columns"):
            read_coordinates(b"1,2,a\n3,4,5\n", "c.csv", 2)
        data = build_dataset([("Control", self.zip_a), ("Preterm", self.zip_b)])
        set_coordinates(data, npy_bytes(np.zeros((6, 3)) + 1), "c.npy", "cm", "MNI")
        self.assertEqual(data["coordinate_space"], "MNI (mm)")
        self.assertEqual(data["node_coordinates"][0].tolist(), [10, 10, 10])


class ExampleCoordinateTests(unittest.TestCase):
    def test_open_example_has_mni_centroids_in_node_order(self):
        from multiplex_nbs.demo import make_brain_demo
        data = make_brain_demo()
        coords = np.asarray(data["node_coordinates"])
        self.assertEqual(coords.shape, (32, 3))
        self.assertEqual(data["coordinate_space"], "MNI (mm)")
        left = np.array([label.startswith("L ") for label in data["node_labels"]])
        self.assertTrue((coords[left, 0] < 0).all() and (coords[~left, 0] > 0).all())
        self.assertTrue((np.abs(coords) < 100).all())
        self.assertEqual(len(describe(load_dataset(io.BytesIO(npy_free_npz(data)), ".npz"))["node_coordinates"]), 32)


def npy_free_npz(data):
    stream = io.BytesIO()
    np.savez_compressed(stream, **data)
    return stream.getvalue()

if __name__ == "__main__":
    unittest.main()
