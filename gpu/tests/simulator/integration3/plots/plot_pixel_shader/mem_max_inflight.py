import os
import matplotlib.pyplot as plt

# Pixel shader capacity sweep data from SM11-SM15
mem_max_inflight = [1, 2, 4, 6, 8]
cycles = [373290, 348818, 348818, 348818, 350028]

out_dir = "gpu/tests/simulator/integration3/plots/plot_pixel_shader"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "mem_max_inflight_sweep_cycles.png")

x_labels = [f"{entries} Entries" for entries in mem_max_inflight]

fig, ax = plt.subplots(figsize=(15, 8.5))
ax.plot(range(len(mem_max_inflight)), cycles, marker='o', linewidth=2.0, markersize=7)

ax.set_title(
    "Pixel Shader Mem Max Inflight Sweep: Cycles vs Memory Controller Inflight Requests Capacity",
    fontsize=18,
    fontweight='bold',
    pad=20
)
ax.set_xlabel(
    "Max InfligHT Requests",
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
plt.show()

print(out_path)