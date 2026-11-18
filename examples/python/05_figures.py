"""Figures for a component (needs matplotlib: pip install "multiplex-nbs[plot]").

For brain views and animations, open the result's dataset in the desktop app.
"""
import matplotlib.pyplot as plt

from multiplex_nbs import load_demo, multiplex_nbs, plot_layer_profile, plot_membership, plot_null_distribution

result = multiplex_nbs(load_demo(), n_perm=999)

fig, axes = plt.subplots(3, 1, figsize=(8, 11))
plot_layer_profile(result, ax=axes[0])      # regions per time window: component vs all above threshold
plot_membership(result, ax=axes[1])         # region × time grid of the component
plot_null_distribution(result, ax=axes[2])  # observed size against the permutation maxima
fig.tight_layout()
fig.savefig("component_figures.png", dpi=150)
print("Saved component_figures.png")
