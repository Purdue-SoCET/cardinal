import os
import matplotlib.pyplot as plt

# Triangle shader capacity sweep data from SM26-SM30
capacity_kb = [4, 8, 16, 32, 64]
cycles = [255820, 252269, 247050, 237163, 216488]

out_dir = "gpu/tests/simulator/integration3/plots/plot_triangle_shader"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "capacity_sweep_cycles.png")

x_labels = [f"{kb} KB" for kb in capacity_kb]

fig, ax = plt.subplots(figsize=(15, 8.5))
ax.plot(range(len(capacity_kb)), cycles, marker='o', linewidth=2.0, markersize=7)

ax.set_title(
    "Triangle Shader Capacity Sweep: Cycles vs D$ Capacity",
    fontsize=18,
    fontweight='bold',
    pad=20
)
ax.set_xlabel(
    "D$ capacity",
    fontsize=14,
    fontweight='bold',
    labelpad=14
)
ax.set_ylabel(
    "Cycles",
    fontsize=14,
    fontweight='bold',
    labelpad=12
)

ax.set_xticks(range(len(x_labels)))
ax.set_xticklabels(x_labels, fontsize=12, fontweight='bold')

ax.tick_params(axis='y', labelsize=12)
for label in ax.get_yticklabels():
    label.set_fontweight('bold')

ax.set_ylim(min(cycles) - 10000, max(cycles) + 15000)
ax.margins(x=0.08)

for i, val in enumerate(cycles):
    ax.annotate(
        str(val),
        (i, val),
        textcoords="offset points",
        xytext=(0, 10),
        ha='center',
        fontsize=12,
        fontweight='bold'
    )

fig.tight_layout(pad=3.0)
fig.savefig(out_path, dpi=200, bbox_inches="tight")
plt.close(fig)

print(out_path)
