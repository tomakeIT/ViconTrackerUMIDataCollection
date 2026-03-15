import argparse
import csv
import importlib
from pathlib import Path

try:
    plt = importlib.import_module("matplotlib.pyplot")
except ImportError as exc:
    raise SystemExit(
        "matplotlib is required. Install it with: pip install matplotlib"
    ) from exc


OUTPUT_DIR = Path("output")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Visualize Vicon trajectories from a CSV file in 3D."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Path to a CSV file. Defaults to the newest CSV in output/.",
    )
    parser.add_argument(
        "--subject",
        default=None,
        help="Only visualize the specified rigid body name.",
    )
    return parser.parse_args()


def get_latest_csv_path():
    csv_files = sorted(OUTPUT_DIR.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError("No CSV files found in output/.")
    return csv_files[-1]


def load_trajectories(csv_path, subject_filter=None):
    trajectories = {}

    with open(csv_path, "r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            subject_name = row["subject_name"]
            if subject_filter and subject_name != subject_filter:
                continue

            if not row["x"] or not row["y"] or not row["z"]:
                continue

            trajectories.setdefault(subject_name, {"x": [], "y": [], "z": []})
            trajectories[subject_name]["x"].append(float(row["x"]))
            trajectories[subject_name]["y"].append(float(row["y"]))
            trajectories[subject_name]["z"].append(float(row["z"]))

    if not trajectories:
        if subject_filter:
            raise ValueError(f"No trajectory data found for subject '{subject_filter}'.")
        raise ValueError("No trajectory data found in the CSV file.")

    return trajectories


def set_equal_axes(ax, trajectories):
    all_x = []
    all_y = []
    all_z = []

    for values in trajectories.values():
        all_x.extend(values["x"])
        all_y.extend(values["y"])
        all_z.extend(values["z"])

    x_center = (min(all_x) + max(all_x)) / 2
    y_center = (min(all_y) + max(all_y)) / 2
    z_center = (min(all_z) + max(all_z)) / 2

    max_range = max(
        max(all_x) - min(all_x),
        max(all_y) - min(all_y),
        max(all_z) - min(all_z),
    ) / 2

    if max_range == 0:
        max_range = 1.0

    ax.set_xlim(x_center - max_range, x_center + max_range)
    ax.set_ylim(y_center - max_range, y_center + max_range)
    ax.set_zlim(z_center - max_range, z_center + max_range)


def plot_trajectories(csv_path, trajectories):
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    for subject_name, values in trajectories.items():
        ax.plot(values["x"], values["y"], values["z"], label=subject_name, linewidth=1.5)
        ax.scatter(values["x"][0], values["y"][0], values["z"][0], marker="o", s=50)
        ax.scatter(values["x"][-1], values["y"][-1], values["z"][-1], marker="^", s=60)

    set_equal_axes(ax, trajectories)
    ax.set_title(f"3D Trajectory Visualization\n{csv_path.name}")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.legend()
    plt.tight_layout()
    plt.show()


def main():
    args = parse_args()
    csv_path = args.file or get_latest_csv_path()
    trajectories = load_trajectories(csv_path, args.subject)
    plot_trajectories(csv_path, trajectories)


if __name__ == "__main__":
    main()
