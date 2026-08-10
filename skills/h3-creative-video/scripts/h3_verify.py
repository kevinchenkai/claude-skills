#!/usr/bin/env python3
"""Gate H3 video pixels, dimensions, frame count, and declared audio policy."""

import argparse
import json
from pathlib import Path

import av
import numpy as np


def laplacian_variance(gray):
    out = (
        gray[:-2, 1:-1]
        + gray[1:-1, :-2]
        - 4 * gray[1:-1, 1:-1]
        + gray[1:-1, 2:]
        + gray[2:, 1:-1]
    )
    return float(out.var())


def analyze(path, args):
    result = {"path": str(path), "name": Path(path).name}
    failures = []
    try:
        container = av.open(path)
        try:
            if not container.streams.video:
                raise ValueError("no video stream")
            stream = container.streams.video[0]
            fps = float(stream.average_rate)
            width = stream.codec_context.width
            height = stream.codec_context.height

            frames = blank = video_nan_frames = 0
            means, sharpness, motion = [], [], []
            previous = None
            for index, frame in enumerate(container.decode(video=0)):
                image = frame.to_ndarray(format="rgb24").astype(np.float32)
                if not np.isfinite(image).all():
                    video_nan_frames += 1
                means.append(float(np.nanmean(image)))
                if float(np.nanstd(image)) < args.blank_std:
                    blank += 1
                if index % 8 == 0:
                    gray = np.nanmean(image, axis=2)[::2, ::2]
                    sharpness.append(laplacian_variance(gray))
                    if previous is not None:
                        motion.append(float(np.nanmean(np.abs(gray - previous))))
                    previous = gray
                frames += 1
        finally:
            container.close()

        if frames == 0:
            failures.append("no decoded video frames")
        if blank:
            failures.append(f"blank frames: {blank}")
        if video_nan_frames:
            failures.append(f"video NaN frames: {video_nan_frames}")
        if args.expected_frames is not None and frames != args.expected_frames:
            failures.append(f"frames {frames} != expected {args.expected_frames}")
        if args.expected_width is not None and width != args.expected_width:
            failures.append(f"width {width} != expected {args.expected_width}")
        if args.expected_height is not None and height != args.expected_height:
            failures.append(f"height {height} != expected {args.expected_height}")

        video_duration = frames / fps if fps > 0 else 0.0
        result.update(
            frames=frames,
            blank_frames=blank,
            video_nan_frames=video_nan_frames,
            width=width,
            height=height,
            fps=fps,
            video_duration_sec=video_duration,
            mean_min=min(means) if means else None,
            mean_max=max(means) if means else None,
            sharpness=float(np.mean(sharpness)) if sharpness else None,
            sampled_motion=float(np.mean(motion)) if motion else None,
        )

        audio_container = av.open(path)
        try:
            has_audio = bool(audio_container.streams.audio)
            result["has_audio"] = has_audio
            if args.audio == "required" and not has_audio:
                failures.append("required audio stream is missing")
            if args.audio == "forbidden" and has_audio:
                failures.append("audio stream present but policy is forbidden")

            if has_audio:
                audio_stream = audio_container.streams.audio[0]
                channels = audio_stream.codec_context.channels
                sample_rate = audio_stream.codec_context.sample_rate
                buffers = [
                    frame.to_ndarray().astype(np.float32).ravel()
                    for frame in audio_container.decode(audio=0)
                ]
                if not buffers or sum(len(buffer) for buffer in buffers) == 0:
                    failures.append("audio stream decoded zero samples")
                else:
                    samples = np.concatenate(buffers)
                    audio_nan = bool(np.isnan(samples).any())
                    rms = float(np.sqrt(np.nanmean(samples ** 2)))
                    audio_duration = len(samples) / sample_rate / channels
                    av_drift = abs(audio_duration - video_duration)
                    result.update(
                        audio_channels=channels,
                        audio_sample_rate=sample_rate,
                        audio_nan=audio_nan,
                        audio_rms=rms,
                        audio_duration_sec=audio_duration,
                        av_duration_drift_sec=av_drift,
                    )
                    if audio_nan:
                        failures.append("audio contains NaN")
                    if args.audio != "forbidden" and rms < args.min_audio_rms:
                        failures.append(
                            f"audio RMS {rms:.8f} < silence floor {args.min_audio_rms:.8f}"
                        )
                    if args.audio != "forbidden" and av_drift > args.max_av_drift:
                        failures.append(
                            f"A/V duration drift {av_drift:.3f}s > {args.max_av_drift:.3f}s"
                        )
        finally:
            audio_container.close()

        result.update(ok=not failures, failures=failures)
    except Exception as exc:
        result.update(ok=False, error=str(exc), failures=[str(exc)])
    return result


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("videos", nargs="+", help="MP4 files to verify")
    parser.add_argument("--expected-frames", type=int)
    parser.add_argument("--expected-width", type=int)
    parser.add_argument("--expected-height", type=int)
    parser.add_argument("--blank-std", type=float, default=1.0)
    parser.add_argument("--audio", choices=("required", "optional", "forbidden"), default="required")
    parser.add_argument("--min-audio-rms", type=float, default=0.000001)
    parser.add_argument("--max-av-drift", type=float, default=0.25)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    results = [analyze(path, args) for path in args.videos]
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for row in results:
            print(f"{row['name']}: {'OK' if row['ok'] else 'FAIL'}")
            if "error" not in row:
                print(
                    f"   {row['frames']} frames {row['width']}x{row['height']} "
                    f"fps={row['fps']:.3f} blank={row['blank_frames']} "
                    f"video_nan={row['video_nan_frames']} audio={row['has_audio']}"
                )
            for failure in row["failures"]:
                print(f"   - {failure}")
    return 0 if all(row["ok"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
