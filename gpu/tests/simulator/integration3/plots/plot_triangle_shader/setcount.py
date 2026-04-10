import os
import matplotlib.pyplot as plt

# Triangle shader set-count / associativity sweep data from SM21-SM25
sets_per_bank = [4, 8, 16, 32, 64]
ways = [16, 8, 4, 2, 1]
cycles = [244680, 246454, 241289, 242270, 241805]

x_labels = [f"{s} sets, {w}-way" for s, w in zip(sets_per_bank, ways)]

out_dir = "gpu/tests/simulator/integration3/plots/plot_triangle_shader"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "setcount_sweep_cycles.png")

fig, ax = plt.subplots(figsize=(15, 8.5))
ax.plot(range(len(sets_per_bank)), cycles, marker='o', linewidth=2.0, markersize=7)

ax.set_title(
    "Triangle Shader Set-Count Sweep: Cycles vs Sets per Bank and Associativity",
    fontsize=18,
    fontweight='bold',
    pad=20
)
ax.set_xlabel(
    "D$ sets per bank / associativity",
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
ax.set_xticklabels(x_labels, fontsize=12, fontweight='bold', rotation=16, ha='right')
ax.tick_params(axis='y', labelsize=12)
for label in ax.get_yticklabels():
    label.set_fontweight('bold')

ax.set_ylim(min(cycles) - 4000, max(cycles) + 5000)
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
