import argparse
import csv
import os

import matplotlib.pyplot as plt


DEFAULT_TRACE = (
    "gpu/tests/simulator/integration3/sweep_dumps/"
    "ldst_q_trace_pixel1024_dump/sm_00/ldst_q_trace.csv"
)
DEFAULT_OUT_DIR = "gpu/tests/simulator/integration3/plots/plot_pixel_shader"


def load_trace(path: str):
    cycles = []
    occupancy = []
    capacity = []
    full = []
    outstanding = []
    wb_buffer = []

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cycles.append(int(row["cycle"]))
            occupancy.append(int(row["ldst_q_occupancy"]))
            capacity.append(int(row["ldst_q_capacity"]))
            full.append(int(row["ldst_q_full"]))
            outstanding.append(int(row["ldst_outstanding"]))
            wb_buffer.append(int(row["ldst_wb_buffer_occupancy"]))

    return cycles, occupancy, capacity, full, outstanding, wb_buffer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", default=DEFAULT_TRACE)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    cycles, occupancy, capacity, full, outstanding, wb_buffer = load_trace(args.trace)

    os.makedirs(DEFAULT_OUT_DIR, exist_ok=True)
    out_path = args.out or os.path.join(DEFAULT_OUT_DIR, "ldst_q_trace.png")

    cap_value = capacity[0] if capacity else 0
    full_scaled = [x * cap_value for x in full]
    outstanding_scaled = [x * cap_value for x in outstanding]

    fig, ax = plt.subplots(figsize=(15, 8.5))
    ax.plot(cycles, occupancy, linewidth=2.0, color="tab:blue", label="LD/ST queue occupancy")
    ax.plot(cycles, capacity, linewidth=2.0, linestyle="--", color="tab:red", label="LD/ST queue capacity")
    ax.plot(cycles, wb_buffer, linewidth=1.8, color="tab:green", label="LD/ST WB buffer occupancy")
    ax.fill_between(cycles, 0, full_scaled, color="tab:orange", alpha=0.18, label="Queue full")
    ax.fill_between(cycles, 0, outstanding_scaled, color="tab:purple", alpha=0.12, label="Outstanding dcache req")

    ax.set_title(
        "Pixel Shader LD/ST Queue Trace: Occupancy vs Cycle",
        fontsize=18,
        fontweight="bold",
        pad=20,
    )
    ax.set_xlabel(
        "Cycle",
        fontsize=14,
        fontweight="bold",
        labelpad=14,
    )
    ax.set_ylabel(
        "Entries",
        fontsize=14,
        fontweight="bold",
        labelpad=12,
    )

    ax.tick_params(axis="both", labelsize=12)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontweight("bold")

    ax.set_ylim(0, max(capacity + occupancy + wb_buffer + [1]) + 0.75)
    ax.margins(x=0.01)
    ax.legend(prop={"weight": "bold", "size": 11}, loc="upper right")

    fig.tight_layout(pad=3.0)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.show()

    print(out_path)


if __name__ == "__main__":
    main()
