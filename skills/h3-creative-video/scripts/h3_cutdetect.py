#!/usr/bin/env python3
"""Locate isolated hard cuts and optionally gate them against expected times."""

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


def match_expected(cuts, expected, tolerance):
    available = set(range(len(cuts)))
    matches, failures = [], []
    for target in expected:
        if not available:
            failures.append(f"expected cut {target:.3f}s was not detected")
            continue
        selected = min(available, key=lambda index: abs(cuts[index]["time_sec"] - target))
        error = cuts[selected]["time_sec"] - target
        available.remove(selected)
        if abs(error) > tolerance:
            failures.append(
                f"nearest cut to {target:.3f}s is {cuts[selected]['time_sec']:.3f}s "
                f"(error {error:+.3f}s > {tolerance:.3f}s)"
            )
            continue
        matches.append(
            {"expected_sec": target, "detected_sec": cuts[selected]["time_sec"], "error_sec": error}
        )
    for index in sorted(available):
        failures.append(f"unexpected hard cut at {cuts[index]['time_sec']:.3f}s")
    return matches, failures


def analyze(path, args):
    result = {"path": str(path), "name": Path(path).name}
    try:
        diffs, fps = frame_diffs(path)
        if len(diffs) < 2 * args.wing + 1:
            raise ValueError("video is too short for the configured detection wing")
        median = float(np.median(diffs))
        high, low = median * args.spike, median * args.quiet

        raw = []
        for index in range(args.wing, len(diffs) - args.wing):
            if diffs[index] < high:
                continue
            left = diffs[index - args.wing:index]
            right = diffs[index + 1:index + 1 + args.wing]
            if (left < low).sum() >= args.wing - 1 and (right < low).sum() >= args.wing - 1:
                if raw and index - raw[-1][0] <= 2:
                    if diffs[index] > raw[-1][1]:
                        raw[-1] = (index, float(diffs[index]))
                else:
                    raw.append((index, float(diffs[index])))

        cuts = [
            {
                "frame": index,
                "time_sec": index / fps,
                "magnitude": magnitude,
                "multiple_of_median": magnitude / median if median > 0 else None,
            }
            for index, magnitude in raw
        ]
        matches, failures = match_expected(cuts, args.expected_cut, args.tolerance) if args.expected_cut else ([], [])
        result.update(
            ok=not failures,
            fps=fps,
            median_diff=median,
            spike_multiplier=args.spike,
            quiet_multiplier=args.quiet,
            frames_over_threshold=int((diffs > high).sum()),
            cuts=cuts,
            expected_cuts=args.expected_cut,
            tolerance_sec=args.tolerance,
            matches=matches,
            failures=failures,
            blind_spot="dissolves and gradual transitions require human filmstrip review",
        )
    except Exception as exc:
        result.update(ok=False, error=str(exc), failures=[str(exc)])
    return result


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("videos", nargs="+", help="MP4 files to analyze")
    parser.add_argument("--spike", type=float, default=5.0)
    parser.add_argument("--quiet", type=float, default=1.5)
    parser.add_argument("--wing", type=int, default=3)
    parser.add_argument("--expected-cut", type=float, action="append", default=[])
    parser.add_argument("--tolerance", type=float, default=0.25)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.wing < 1 or min(args.spike, args.quiet, args.tolerance) < 0:
        raise SystemExit("wing must be positive and thresholds must be non-negative")
    results = [analyze(path, args) for path in args.videos]
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for row in results:
            print(f"{row['name']}: {'OK' if row['ok'] else 'FAIL'}")
            if "error" not in row:
                print(
                    f"   median={row['median_diff']:.2f} "
                    f"over_threshold={row['frames_over_threshold']} cuts={len(row['cuts'])}"
                )
                for cut in row["cuts"]:
                    print(f"   cut @ {cut['time_sec']:.3f}s magnitude={cut['magnitude']:.1f}")
                print("   NOTE: dissolves remain a filmstrip-only check")
            for failure in row["failures"]:
                print(f"   - {failure}")
    return 0 if all(row["ok"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
