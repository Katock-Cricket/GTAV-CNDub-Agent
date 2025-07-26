import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


def process_file(src_path: Path, dst_path: Path):
    try:
        y, sr = librosa.load(src_path, sr=None, mono=False)

        # 多声道 → 单声道（能量平均）
        if y.ndim > 1:
            y = np.mean(y, axis=0)

        # 16-bit PCM WAV
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(dst_path, y, sr, subtype='PCM_16', format='WAV')
    except Exception as e:
        print(f"[WARN] Failed on {src_path}: {e}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert all audio files to mono 16-bit WAV.")
    parser.add_argument("--audio_dir", default="E:\\ai\GTA5_Chinese\\NPC语音[AI]\\中配文件",
                        help="Input directory (recursively searched).")
    parser.add_argument("--out_sfx_dir", default="E:\\ai\GTA5_Chinese\\NPC语音[AI]\\中配文件",
                        help="Output directory (mirrors structure).")
    parser.add_argument("--ncpu", type=int, default=16,
                        help="Thread count.")
    args = parser.parse_args()

    audio_dir = Path(args.audio_dir).expanduser()
    out_dir = Path(args.out_sfx_dir).expanduser()

    if not audio_dir.is_dir():
        print(f"{audio_dir} is not a directory.", file=sys.stderr)
        sys.exit(1)

    # 收集所有音频文件
    exts = {'.wav', '.flac', '.mp3', '.ogg', '.m4a', '.aac'}
    src_files = [p for p in audio_dir.rglob('*') if p.suffix.lower() in exts]

    if not src_files:
        print("No audio files found.")
        exit(0)

    print(f"Found {len(src_files)} files, converting to mono 16-bit WAV with {args.ncpu} threads...")

    tasks = []
    with ThreadPoolExecutor(max_workers=args.ncpu) as pool:
        for src_path in src_files:
            rel_path = src_path.relative_to(audio_dir)
            dst_path = (out_dir / rel_path).with_suffix('.wav')
            tasks.append(pool.submit(process_file, src_path, dst_path))

        for _ in as_completed(tasks):
            pass

    print("Done.")
