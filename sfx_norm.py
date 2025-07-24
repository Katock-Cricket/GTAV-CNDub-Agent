import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


def rms_db(y: np.ndarray) -> float:
    """Compute RMS of a signal in dBFS."""
    rms = np.sqrt(np.mean(y**2))
    if rms == 0:
        return -np.inf
    return 20 * np.log10(rms)


def normalize_rms(y: np.ndarray, target_db: float) -> np.ndarray:
    """Scale signal so its RMS equals `target_db` dBFS."""
    current_db = rms_db(y)
    if np.isinf(current_db):
        return y  # silent, nothing to do
    gain = 10 ** ((target_db - current_db) / 20)
    return y * gain


def process_file(src_path: Path, dst_path: Path, target_rms_db: float):
    """Load, normalize, save one file."""
    try:
        y, sr = librosa.load(src_path, sr=None, mono=False)
        if y.ndim > 1:
            # stereo or more, normalize each channel separately
            y = np.stack([normalize_rms(ch, target_rms_db) for ch in y])
        else:
            y = normalize_rms(y, target_rms_db)

        # Ensure target directory exists
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(dst_path, y.T if y.ndim > 1 else y, sr)
    except Exception as e:
        # Very relaxed error handling
        print(f"[WARN] Failed to process {src_path}: {e}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch loudness normalization based on total RMS.")
    parser.add_argument(
        "--audio_dir",
        default="./out_sfx/男_白_警察_1_已剪辑",
        help="Directory containing audio files (recursively searched).",
    )
    parser.add_argument(
        "--out_sfx_dir",
        default="./out_sfx_norm/男_白_警察_1_已剪辑",
        help="Directory where normalized files will be saved.",
    )
    parser.add_argument(
        "--ncpu",
        type=int,
        default=12,
        help="Number of threads (ThreadPoolExecutor).",
    )
    parser.add_argument(
        "--rms",
        type=float,
        default=-14.0,
        help="Target RMS in dBFS.",
    )
    args = parser.parse_args()

    audio_dir = Path(args.audio_dir).expanduser()
    out_dir = Path(args.out_sfx_dir).expanduser()
    target_rms_db = float(args.rms)

    if not audio_dir.is_dir():
        print(f"audio_dir '{audio_dir}' is not a directory or does not exist.", file=sys.stderr)
        sys.exit(1)

    # Collect all audio files (librosa supports many formats, but let's be simple)
    supported_ext = {".wav", ".flac", ".mp3", ".ogg", ".m4a"}
    src_files = [p for p in audio_dir.rglob("*") if p.suffix.lower() in supported_ext]

    if not src_files:
        print("No audio files found.")
        exit(0)

    print(f"Found {len(src_files)} files, normalizing to {target_rms_db} dBFS using {args.ncpu} threads...")

    tasks = []
    with ThreadPoolExecutor(max_workers=args.ncpu) as pool:
        for src_path in src_files:
            rel_path = src_path.relative_to(audio_dir)
            dst_path = out_dir / rel_path
            tasks.append(pool.submit(process_file, src_path, dst_path, target_rms_db))

        for _ in as_completed(tasks):
            pass  # ignore results/raise

    print("Done.")
