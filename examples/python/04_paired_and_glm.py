"""Paired conditions and a general linear model (GLM) with a covariate."""
import numpy as np

from multiplex_nbs import components, load_demo, make_dataset, multiplex_nbs

# Paired: `group` holds pair IDs; each ID appears twice. The first observation of each
# pair is compared with the second (here condition 1 minus condition 2).
paired = load_demo("paired")
result = multiplex_nbs(paired, design="paired", n_perm=999)
print("Paired:", result["interpretation"]["headline"])

# GLM: give a design matrix X (one row per observation, with an intercept) and a
# contrast C. One contrast row gives a t test; several independent rows an F test.
glm = load_demo("glm")
print("Design columns: intercept, group, covariate. Contrast:", glm["C"])
result = multiplex_nbs(glm, design="glm-t", n_perm=999)   # Freedman–Lane permutation
print("GLM t:", result["interpretation"]["headline"])
for c in components(result, significant_only=True):
    print(f"  #{c['id']}: p = {c['p_fwe']:.3g}, {c['n_regions']} regions, {c['axis_values']} Hz")

# Your own GLM: age as a covariate
rng = np.random.default_rng(0)
W = glm["W"]
age = rng.uniform(20, 60, size=W.shape[0])
X = np.column_stack([np.ones(W.shape[0]), np.repeat([0, 1], W.shape[0] // 2), age - age.mean()])
# The contrast sets the direction: [0, -1, 0] tests group 0 > group 1 (how the demo was simulated).
data = make_dataset(W, X=X, C=[0, -1, 0], axis_values=glm["axis_values"], axis_name="Frequency", axis_unit="Hz")
print("Group effect adjusted for age:", multiplex_nbs(data, n_perm=199)["interpretation"]["headline"])
