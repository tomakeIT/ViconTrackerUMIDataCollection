import csv
from datetime import datetime
from pathlib import Path
import subprocess
import time

import pyvicon_datastream as pv

VICON_TRACKER_IP = "192.168.0.149"
BUFFER_SIZE = 512
FRAME_RETRY_COUNT = 20
NO_FRAME_SLEEP_SECONDS = 0.001
OUTPUT_DIR = Path("output")
FRAME_RATE_HZ = 120
COLLECTION_DURATION_SECONDS = 5
COLLECTION_FRAME_COUNT = COLLECTION_DURATION_SECONDS * FRAME_RATE_HZ
PRE_COLLECTION_DELAY_SECONDS = 2
START_SOUND_PATH = Path("/System/Library/Sounds/Ping.aiff")
DONE_SOUND_PATH = Path("/System/Library/Sounds/Hero.aiff")


def require_success(result, action):
    if result != pv.Result.Success:
        print(f"{action} failed: {result.name}")
        return False
    return True


def get_latest_frame(client, retries=FRAME_RETRY_COUNT):
    for _ in range(retries):
        if client.get_frame() == pv.Result.Success:
            return True
    return False


def connect_client():
    client = pv.PyViconDatastream()

    if not require_success(client.connect(VICON_TRACKER_IP), f"Connect to {VICON_TRACKER_IP}"):
        return None

    print(f"Connected to {VICON_TRACKER_IP}")

    if not require_success(
        client.set_stream_mode(pv.StreamMode.ClientPullPreFetch), "Set stream mode"
    ):
        return None

    client.set_buffer_size(BUFFER_SIZE)

    if not require_success(client.enable_segment_data(), "Enable segment data"):
        return None

    return client


def create_csv_path():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return OUTPUT_DIR / f"vicon_data_{timestamp}.csv"


def play_sound(sound_path):
    if not sound_path.exists():
        print("\a", end="", flush=True)
        return

    try:
        subprocess.Popen(
            ["afplay", str(sound_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        print("\a", end="", flush=True)


def get_subject_pose(client, index):
    subject_name = client.get_subject_name(index)
    root_segment_name = client.get_subject_root_segment_name(subject_name)
    translation = client.get_segment_global_translation(subject_name, root_segment_name)
    quaternion = client.get_segment_global_quaternion(subject_name, root_segment_name)

    x = y = z = None
    if translation is not None:
        x, y, z = translation.tolist()

    qw = qx = qy = qz = None
    if quaternion is not None:
        qw, qx, qy, qz = quaternion.tolist()

    return {
        "subject_name": subject_name,
        "x": x,
        "y": y,
        "z": z,
        "qw": qw,
        "qx": qx,
        "qy": qy,
        "qz": qz,
    }


def format_subject_pose(index, pose):
    if all(pose[key] is None for key in ("x", "y", "z", "qw", "qx", "qy", "qz")):
        return f"{index + 1}. {pose['subject_name']}: position and quaternion unavailable"

    position_text = "position unavailable"
    if pose["x"] is not None:
        position_text = f"x={pose['x']:.2f}, y={pose['y']:.2f}, z={pose['z']:.2f}"

    quaternion_text = "q=unavailable"
    if pose["qw"] is not None:
        quaternion_text = (
            f"q=(w={pose['qw']:.4f}, x={pose['qx']:.4f}, "
            f"y={pose['qy']:.4f}, z={pose['qz']:.4f})"
        )

    return f"{index + 1}. {pose['subject_name']}: {position_text}, {quaternion_text}"


def write_csv_header(csv_writer):
    csv_writer.writerow(
        [
            "timestamp",
            "frame_number",
            "subject_name",
            "x",
            "y",
            "z",
            "qw",
            "qx",
            "qy",
            "qz",
        ]
    )


def print_and_save_frame(client, csv_writer, csv_file, last_frame_number):
    frame_number = client.get_frame_number()
    subject_count = client.get_subject_count()
    timestamp = time.time()

    if last_frame_number is not None:
        skipped = frame_number - last_frame_number - 1
        if skipped > 0:
            print(f"\nWarning: detected skipped frames, lost {skipped} frame(s)")

    print(f"\nFrame {frame_number} | rigid body count: {subject_count}", flush=True)

    for index in range(subject_count):
        pose = get_subject_pose(client, index)
        print(format_subject_pose(index, pose), flush=True)
        csv_writer.writerow(
            [
                timestamp,
                frame_number,
                pose["subject_name"],
                pose["x"],
                pose["y"],
                pose["z"],
                pose["qw"],
                pose["qx"],
                pose["qy"],
                pose["qz"],
            ]
        )

    csv_file.flush()

    return frame_number


def main():
    vicon_client = connect_client()
    if vicon_client is None:
        return

    csv_file_path = create_csv_path()

    print(
        f"Streaming positions and quaternions for all rigid bodies for "
        f"{COLLECTION_DURATION_SECONDS} seconds "
        f"({COLLECTION_FRAME_COUNT} frames at {FRAME_RATE_HZ} Hz)."
    )
    print("ClientPullPreFetch is enabled with no artificial sampling delay.")
    print(f"Saving CSV to: {csv_file_path}")
    print(f"Collection will start in {PRE_COLLECTION_DELAY_SECONDS} seconds.")

    time.sleep(PRE_COLLECTION_DELAY_SECONDS)
    play_sound(START_SOUND_PATH)
    print("Collection started.")

    with open(csv_file_path, "w", newline="", encoding="utf-8") as csv_file:
        csv_writer = csv.writer(csv_file)
        write_csv_header(csv_writer)

        try:
            last_frame_number = None
            collected_frames = 0
            while True:
                if collected_frames >= COLLECTION_FRAME_COUNT:
                    print(f"\nCollection complete: {collected_frames} frames captured.")
                    play_sound(DONE_SOUND_PATH)
                    break

                if not get_latest_frame(vicon_client):
                    print("No new frame received")
                    time.sleep(NO_FRAME_SLEEP_SECONDS)
                    continue

                last_frame_number = print_and_save_frame(
                    vicon_client, csv_writer, csv_file, last_frame_number
                )
                collected_frames += 1
        except KeyboardInterrupt:
            print("\nStopped streaming.")
        finally:
            vicon_client.disconnect()


if __name__ == "__main__":
    main()