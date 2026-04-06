import os
import matplotlib.pyplot as plt

# Pixel shader set-count / associativity sweep data from SM06-SM10
sets_per_bank = [4, 8, 16, 32, 64]
ways = [16, 8, 4, 2, 1]
cycles = [399280, 397321, 386248, 390071, 400722]

x_labels = [f"{s} sets, {w}-way" for s, w in zip(sets_per_bank, ways)]

out_dir = "gpu/tests/simulator/integration3/plots/plot_pixel_shader"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "setcount_sweep_cycles.png")

fig, ax = plt.subplots(figsize=(15, 8.5))
ax.plot(range(len(sets_per_bank)), cycles, marker='o', linewidth=2.0, markersize=7)

ax.set_title(
    "Pixel Shader Set-Count Sweep: Cycles vs Sets per Bank and Associativity",
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

ax.set_ylim(min(cycles) - 8000, max(cycles) + 12000)
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
plt.show()

print(out_path)