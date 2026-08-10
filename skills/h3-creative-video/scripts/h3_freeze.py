#!/usr/bin/env python3
"""Measure H3 tail activity and terminal full-frame freeze.

This does not prove that the intended subject keeps moving: hair, background, camera,
compression, or invented content can keep whole-frame differences above the floor.
"""

import argparse
import json
from pathlib import Path

import av
import numpy as np


def frame_diffs(path):
    container = av.open(path)
    try:
        stream = container.streams.video[0]
        fps = float(stream.average_rate)
        previous, values = None, []
        for frame in container.decode(video=0):
            image = np.asarray(
                frame.to_image().convert("L").resize((92, 164)), dtype=np.float32
            )
            if previous is not None:
                values.append(float(np.abs(image - previous).mean()))
            previous = image
    finally:
        container.close()
    if fps <= 0:
        raise ValueError("video stream has no usable frame rate")
    return np.asarray(values), fps


def analyze(path, args):
    result = {"path": str(path), "name": Path(path).name}
    try:
        diffs, fps = frame_diffs(path)
        if len(diffs) == 0:
            raise ValueError("video has fewer than two decoded frames")

        median = float(np.median(diffs))
        tail_frames = max(1, int(round(args.tail_sec * fps)))
        tail = diffs[-tail_frames:]
        tail_abs = float(tail.mean())
        ratio = tail_abs / median if median > 0 else 0.0

        index = len(diffs) - 1
        while index >= 0 and diffs[index] < args.freeze_abs:
            index -= 1
        frozen_frames = len(diffs) - (index + 1)
        freeze_sec = frozen_frames / fps

        failures = []
        if ratio < args.ratio_line:
            failures.append(f"tail ratio {ratio:.3f} < {args.ratio_line:.3f}")
        if tail_abs < args.abs_line:
            failures.append(f"tail absolute {tail_abs:.3f} < {args.abs_line:.3f}")
        if freeze_sec >= args.max_freeze_sec:
            failures.append(
                f"terminal full-frame freeze {freeze_sec:.3f}s >= {args.max_freeze_sec:.3f}s"
            )

        result.update(
            ok=not failures,
            fps=fps,
            diff_frames=len(diffs),
            median_diff=median,
            tail_sec=args.tail_sec,
            tail_abs=tail_abs,
            tail_ratio=ratio,
            ratio_line=args.ratio_line,
            abs_line=args.abs_line,
            freeze_abs=args.freeze_abs,
            terminal_freeze_frames=frozen_frames,
            terminal_freeze_sec=freeze_sec,
            freeze_from_sec=(index + 1) / fps if frozen_frames else None,
            max_freeze_sec=args.max_freeze_sec,
            failures=failures,
            blind_spot=(
                "whole-frame motion cannot prove intended-subject motion; inspect the tail "
                "or use a separately calibrated subject ROI metric"
            ),
        )
    except Exception as exc:
        result.update(ok=False, error=str(exc), failures=[str(exc)])
    return result


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("videos", nargs="+", help="MP4 files to analyze")
    parser.add_argument("--tail-sec", type=float, default=2.0)
    parser.add_argument("--ratio-line", type=float, default=0.40)
    parser.add_argument("--abs-line", type=float, default=1.00)
    parser.add_argument("--freeze-abs", type=float, default=0.30)
    parser.add_argument(
        "--max-freeze-sec",
        type=float,
        default=1.0,
        help="Fail when terminal full-frame freeze is greater than or equal to this value",
    )
    parser.add_argument("--json", action="store_true", help="Emit structured JSON")
    return parser.parse_args()


def main():
    args = parse_args()
    if min(args.tail_sec, args.ratio_line, args.abs_line, args.freeze_abs, args.max_freeze_sec) < 0:
        raise SystemExit("thresholds must be non-negative")
    results = [analyze(path, args) for path in args.videos]
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for row in results:
            print(f"{row['name']}: {'OK' if row['ok'] else 'FAIL'}")
            if "error" in row:
                print(f"   error={row['error']}")
                continue
            print(
                f"   fps={row['fps']:.3f} median={row['median_diff']:.2f} "
                f"tail_abs={row['tail_abs']:.2f}/{row['abs_line']:.2f} "
                f"ratio={row['tail_ratio']:.2f}/{row['ratio_line']:.2f}"
            )
            print(
                f"   terminal_full_frame_freeze={row['terminal_freeze_sec']:.2f}s "
                f"(fail >= {row['max_freeze_sec']:.2f}s)"
            )
            for failure in row["failures"]:
                print(f"   - {failure}")
    return 0 if all(row["ok"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
