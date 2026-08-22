#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

from douyin_hd_core.media import (
    MediaError,
    download_variant,
    ffprobe_summary,
    is_watermarked,
    run_ffprobe,
    select_variant,
)
from douyin_hd_core.models import Inspection, VideoVariant, safe_url_parts
from douyin_hd_core.pipeline import inspect_public_aweme, make_client
from douyin_hd_core.providers import ProviderError
from douyin_hd_core.resolver import ResolveError


VERSION = "0.2.0"
DEFAULT_OUTPUT_DIR = "~/Downloads/douyin"


def _size(value: int | None) -> str:
    if not value:
        return "-"
    units = ("B", "KiB", "MiB", "GiB")
    number = float(value)
    for unit in units:
        if number < 1024 or unit == units[-1]:
            return f"{number:.1f} {unit}" if unit != "B" else f"{int(number)} B"
        number /= 1024
    return str(value)


def _bitrate(value: int | None) -> str:
    return f"{value / 1_000_000:.3f} Mbps" if value else "-"


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _print_candidates(variants: list[VideoVariant]) -> None:
    headers = ("IDX", "SOURCE", "RESOLUTION", "CODEC", "BITRATE", "SIZE", "PROBE", "GEAR")
    rows = []
    for index, variant in enumerate(variants):
        rows.append(
            (
                str(index),
                variant.source_type,
                variant.resolution,
                variant.codec or "-",
                _bitrate(variant.bitrate),
                _size(variant.file_size_hint),
                str(variant.probe.status_code) if variant.probe.ok else f"FAIL:{variant.probe.error or '-'}",
                variant.gear_name or "-",
            )
        )
    widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]
    print("  ".join(headers[i].ljust(widths[i]) for i in range(len(headers))))
    print("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))))


def print_inspection(inspection: Inspection, *, debug: bool) -> None:
    aweme = inspection.aweme
    print(f"aweme_id: {aweme.aweme_id}")
    print(f"author: {aweme.author_name or '-'}")
    print(f"title: {aweme.desc or '-'}")
    print(f"duration_ms: {aweme.duration_ms or '-'}")
    print(f"provider: {aweme.provider}")
    print(f"cookie_required: {'provided' if aweme.cookie_used else 'no'}")
    print(f"browser_fallback_used: {'yes' if aweme.browser_fallback_used else 'no'}")
    print(f"bit_rate_count: {sum(v.source_type == 'bitrate' for v in aweme.variants)}")
    print("\navailable variants:")
    _print_candidates(aweme.variants)

    if debug:
        print("\n=== Debug (URLs redacted) ===")
        for failure in inspection.provider_failures:
            print(f"provider_failure: {failure}")
        for index, variant in enumerate(aweme.variants):
            source = safe_url_parts(variant.urls[0] if variant.urls else None)
            resolved = safe_url_parts(variant.probe.resolved_url)
            print(
                f"[{index}] source={variant.source_type} host={source['host']} path={source['path']} "
                f"resolved_host={resolved['host']} content_type={variant.probe.content_type or '-'} "
                f"content_length={variant.probe.content_length or '-'}"
            )


async def _inspect_from_args(args: argparse.Namespace) -> Inspection:
    cookie = os.environ.get(args.cookie_env) if args.cookie_env else None
    return await inspect_public_aweme(
        args.input,
        browser_fallback=args.browser_fallback,
        cookie_header=cookie,
        timeout_seconds=args.timeout,
    )


async def command_inspect(args: argparse.Namespace) -> int:
    inspection = await _inspect_from_args(args)
    print_inspection(inspection, debug=args.debug)
    if args.save_json:
        path = Path(args.save_json).expanduser().resolve()
        _atomic_json(path, inspection.public_dict())
        print(f"\nJSON: {path}")
    return 0


async def _download_selected(
    inspection: Inspection,
    *,
    quality: str,
    codec: str | None,
    output_path: Path,
    timeout: float,
    cookie: str | None,
) -> dict[str, Any]:
    selected, reason = select_variant(inspection.aweme.variants, quality, codec)
    async with make_client(timeout_seconds=max(timeout, 120), cookie_header=cookie) as client:
        total, sha256 = await download_variant(client, selected, output_path)
    ffprobe = run_ffprobe(output_path)
    summary = ffprobe_summary(ffprobe)
    return {
        "quality_mode": quality,
        "selection_reason": reason,
        "watermarked": is_watermarked(selected),
        "selected_candidate": selected.public_dict(),
        "file": str(output_path),
        "bytes": total,
        "sha256": sha256,
        "ffprobe": ffprobe,
        "summary": summary,
    }


async def command_download(args: argparse.Namespace) -> int:
    inspection = await _inspect_from_args(args)
    print_inspection(inspection, debug=args.debug)
    cookie = os.environ.get(args.cookie_env) if args.cookie_env else None
    item_dir = Path(args.output).expanduser().resolve() / inspection.aweme.aweme_id
    media_path = item_dir / f"{inspection.aweme.aweme_id}.mp4"
    result = await _download_selected(
        inspection,
        quality=args.quality,
        codec=args.codec,
        output_path=media_path,
        timeout=args.timeout,
        cookie=cookie,
    )
    _atomic_json(item_dir / "candidates.json", inspection.public_dict())
    _atomic_json(item_dir / "ffprobe.json", result["ffprobe"])
    metadata = {
        **inspection.aweme.public_dict(),
        "input_url": inspection.extracted_url,
        "selected_quality": args.quality,
        "selected_source": result["selected_candidate"]["source_type"],
        "selection_reason": result["selection_reason"],
        "watermarked": result["watermarked"],
        "file": result["file"],
        "file_size": result["bytes"],
        "sha256": result["sha256"],
        **result["summary"],
    }
    _atomic_json(item_dir / "metadata.json", metadata)

    print("\n=== Selected ===")
    print(f"quality_mode: {args.quality}")
    print(f"source: {result['selected_candidate']['source_type']}")
    print(f"reason: {result['selection_reason']}")
    if result["watermarked"]:
        print("warning: 选中的是带水印的 playwm 源，不是无水印原片。")
    print("\n=== Download ===")
    print(f"file: {media_path}")
    print(f"bytes: {result['bytes']}")
    print(f"sha256: {result['sha256']}")
    print("\n=== ffprobe ===")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


async def command_compare(args: argparse.Namespace) -> int:
    inspection = await _inspect_from_args(args)
    print_inspection(inspection, debug=args.debug)
    cookie = os.environ.get(args.cookie_env) if args.cookie_env else None
    item_dir = Path(args.output).expanduser().resolve() / inspection.aweme.aweme_id
    modes = ["original", "highest"]
    if args.include_play_addr:
        modes.append("play_addr")
    results: dict[str, Any] = {}
    selected_urls: dict[str, str] = {}

    for mode in modes:
        selected, _ = select_variant(inspection.aweme.variants, mode, args.codec)
        identity = selected.best_download_url
        if identity in selected_urls:
            results[mode] = {
                "same_as": selected_urls[identity],
                "quality_mode": mode,
                "selected_candidate": selected.public_dict(),
            }
            continue
        selected_urls[identity] = mode
        result = await _download_selected(
            inspection,
            quality=mode,
            codec=args.codec,
            output_path=item_dir / f"{mode}.mp4",
            timeout=args.timeout,
            cookie=cookie,
        )
        results[mode] = result
        _atomic_json(item_dir / f"{mode}.ffprobe.json", result["ffprobe"])

    comparison = {
        **inspection.aweme.public_dict(),
        "input_url": inspection.extracted_url,
        "results": {
            mode: {key: value for key, value in result.items() if key != "ffprobe"}
            for mode, result in results.items()
        },
    }
    _atomic_json(item_dir / "candidates.json", inspection.public_dict())
    _atomic_json(item_dir / "comparison.json", comparison)

    print("\n=== Comparison ===")
    print("MODE       SOURCE      RESOLUTION  CODEC  BITRATE       SIZE")
    print("---------  ----------  ----------  -----  ------------  ---------")
    for mode in modes:
        result = results[mode]
        if result.get("same_as"):
            print(f"{mode:<9}  same as {result['same_as']}")
            continue
        candidate = result["selected_candidate"]
        summary = result["summary"]
        print(
            f"{mode:<9}  {candidate['source_type']:<10}  "
            f"{str(summary.get('resolution') or '-'):<10}  "
            f"{str(summary.get('video_codec') or '-'):<5}  "
            f"{_bitrate(summary.get('container_bitrate')):<12}  {_size(result['bytes'])}"
        )
    print(f"\ncomparison.json: {item_dir / 'comparison.json'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="douyin-hd",
        description="Inspect public Douyin sources and download without transcoding.",
    )
    parser.add_argument("--version", action="version", version=VERSION)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("input", help="Douyin URL or full share text")
        subparser.add_argument(
            "--browser-fallback",
            action="store_true",
            help="launch Chrome only if lightweight SSR metadata is incomplete",
        )
        subparser.add_argument(
            "--cookie-env",
            default="DOUYIN_COOKIE",
            help="environment variable containing an optional Cookie header",
        )
        subparser.add_argument("--timeout", type=float, default=35.0)
        subparser.add_argument("--debug", action="store_true")

    inspect_parser = subparsers.add_parser("inspect", help="enumerate and probe candidates")
    common(inspect_parser)
    inspect_parser.add_argument("--save-json", help="write a redacted inspection JSON")
    inspect_parser.set_defaults(handler=command_inspect)

    download_parser = subparsers.add_parser("download", help="download one selected source")
    common(download_parser)
    download_parser.add_argument(
        "--quality",
        default="original",
        choices=("original", "highest", "compatible", "1080p", "720p", "540p"),
    )
    download_parser.add_argument("--codec", choices=("h264", "h265"))
    download_parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_DIR,
        help=f"output directory; files land in <output>/<aweme_id>/ (default: {DEFAULT_OUTPUT_DIR})",
    )
    download_parser.set_defaults(handler=command_download)

    compare_parser = subparsers.add_parser("compare", help="download and ffprobe quality modes")
    common(compare_parser)
    compare_parser.add_argument("--codec", choices=("h264", "h265"))
    compare_parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_DIR,
        help=f"output directory; files land in <output>/<aweme_id>/ (default: {DEFAULT_OUTPUT_DIR})",
    )
    compare_parser.add_argument("--include-play-addr", action="store_true")
    compare_parser.set_defaults(handler=command_compare)
    return parser


async def async_main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return await args.handler(args)


def main() -> int:
    try:
        return asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n已取消；未完成的 .part 文件已清理。", file=sys.stderr)
        return 130
    except (ResolveError, ProviderError, MediaError, httpx.HTTPError, RuntimeError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
