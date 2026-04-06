import matplotlib.pyplot as plt

def style_axes(ax, title, xlabel, ylabel, xtick_labels=None, rotation=0):
    ax.set_title(title, fontsize=18, fontweight='bold', pad=20)
    ax.set_xlabel(xlabel, fontsize=14, fontweight='bold', labelpad=14)
    ax.set_ylabel(ylabel, fontsize=14, fontweight='bold', labelpad=12)

    ax.tick_params(axis='both', labelsize=12)
    for label in ax.get_xticklabels():
        label.set_fontweight('bold')
        label.set_rotation(rotation)
        label.set_ha('right' if rotation else 'center')
    for label in ax.get_yticklabels():
        label.set_fontweight('bold')

    if xtick_labels is not None:
        ax.set_xticks(range(len(xtick_labels)))
        ax.set_xticklabels(xtick_labels)

def annotate_points(ax, xs, ys, labels, dy=10):
    for x, y, label in zip(xs, ys, labels):
        ax.annotate(
            str(label),
            (x, y),
            textcoords="offset points",
            xytext=(0, dy),
            ha='center',
            fontsize=12,
            fontweight='bold'
        )

# 1) Banking sweep
banks = [1, 2, 4, 8, 16]
ways_per_bank = [16, 8, 4, 2, 1]
banking_cycles = [79371, 78875, 78983, 78890, 78890]
banking_labels = [f"{b} bank, {w}-way" if b == 1 else f"{b} banks, {w}-way" for b, w in zip(banks, ways_per_bank)]

fig, ax = plt.subplots(figsize=(15, 8.5))
ax.plot(range(len(banks)), banking_cycles, marker='o', linewidth=2.0, markersize=7)
style_axes(
    ax,
    "Vertex Shader Banking Sweep: Cycles vs Banks and Associativity per Bank",
    "D$ banking / associativity per bank",
    "Cycles",
    banking_labels,
    rotation=18
)
ax.set_ylim(min(banking_cycles) - 30, max(banking_cycles) + 140)
ax.margins(x=0.08)
annotate_points(ax, range(len(banks)), banking_cycles, banking_cycles, dy=10)
fig.tight_layout(pad=3.0)
banking_path = "gpu/tests/simulator/integration3/plots/plot_dcache_pranav_vertex_shader/banking_sweep_cycles_bold.png"
fig.savefig(banking_path, dpi=200, bbox_inches="tight")
plt.show()

# 2) Set-count / associativity sweep
sets_per_bank = [4, 8, 16, 32, 64]
ways = [16, 8, 4, 2, 1]
set_cycles = [78983, 78983, 78983, 78983, 78983]
set_labels = [f"{s} sets, {w}-way" for s, w in zip(sets_per_bank, ways)]

fig, ax = plt.subplots(figsize=(15, 8.5))
ax.plot(range(len(sets_per_bank)), set_cycles, marker='o', linewidth=2.0, markersize=7)
style_axes(
    ax,
    "Vertex Shader Set-Count Sweep: Cycles vs Sets per Bank and Associativity",
    "D$ sets per bank / associativity",
    "Cycles",
    set_labels,
    rotation=16
)
ax.set_ylim(min(set_cycles) - 80, max(set_cycles) + 180)
ax.margins(x=0.08)
annotate_points(ax, range(len(sets_per_bank)), set_cycles, set_cycles, dy=10)
fig.tight_layout(pad=3.0)
setcount_path = "gpu/tests/simulator/integration3/plots/plot_dcache_pranav_vertex_shader/setcount_sweep_cycles_bold.png"
fig.savefig(setcount_path, dpi=200, bbox_inches="tight")
plt.show()

# 3) Capacity sweep
capacity_kb = [4, 8, 16, 32, 64]
capacity_cycles = [86065, 79446, 78875, 78875, 78875]
capacity_labels = [f"{kb} KB" for kb in capacity_kb]

fig, ax = plt.subplots(figsize=(15, 8.5))
ax.plot(range(len(capacity_kb)), capacity_cycles, marker='o', linewidth=2.0, markersize=7)
style_axes(
    ax,
    "Vertex Shader Capacity Sweep: Cycles vs D$ Capacity",
    "D$ capacity",
    "Cycles",
    capacity_labels,
    rotation=0
)
ax.set_ylim(min(capacity_cycles) - 120, max(capacity_cycles) + 800)
ax.margins(x=0.08)
annotate_points(ax, range(len(capacity_kb)), capacity_cycles, capacity_cycles, dy=10)
fig.tight_layout(pad=3.0)
capacity_path = "gpu/tests/simulator/integration3/plots/plot_dcache_pranav_vertex_shader/capacity_sweep_cycles_bold.png"
fig.savefig(capacity_path, dpi=200, bbox_inches="tight")
plt.show()

print(banking_path)
print(setcount_path)
print(capacity_path)
