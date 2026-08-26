#!/usr/bin/env python3
"""Publish a Markdown report with native local images to WPS AirPage.

Usage:
    python3 airpage_publish.py <parent-folder-id> <title> <report.md>
        [--drive 6lABZaR] [--asset-root DIR]
        [--on-name-conflict fail|rename] [--result result.json]

Requires Pillow (pip install Pillow) — the only third-party dependency.

The script converts long Markdown in H2-sized chunks, uploads each unique local
image as an AirPage attachment, binds picture.attrs.sourceKey, inserts blocks,
and validates the resulting structure. A partial document created by this run is
deleted if publishing fails.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    from PIL import Image
except ImportError:  # 唯一的第三方依赖：读图片原始宽高用
    sys.exit("需要 Pillow：pip install Pillow（仅本脚本用到，用于读取图片宽高）")


CHUNK_LIMIT = 17_500


def cli(*args):
    proc = subprocess.run(["wps365-cli", *args], capture_output=True, text=True)
    if not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip() or "wps365-cli returned no JSON")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"wps365-cli returned non-JSON output for {' '.join(args)}: "
            f"{proc.stdout[:300]} {proc.stderr[:300]}"
        ) from exc
    if data.get("code") not in (0, None):
        raise RuntimeError(json.dumps(data, ensure_ascii=False))
    return data


def b64(value):
    return base64.b64encode(
        json.dumps(value, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")


def unb64(value):
    return json.loads(base64.b64decode(value))


def split_markdown(content, limit=CHUNK_LIMIT):
    sections = re.split(r"(?=^## )", content, flags=re.M)
    chunks = []
    current = ""
    for section in sections:
        candidate = current + section
        if current and len(candidate.encode("utf-8")) > limit:
            chunks.append(current)
            current = section
        else:
            current = candidate
    if current:
        chunks.append(current)
    oversized = [len(chunk.encode("utf-8")) for chunk in chunks if len(chunk.encode("utf-8")) > limit]
    if oversized:
        raise RuntimeError(
            f"one H2 section exceeds the {limit}-byte conversion limit: {oversized}; "
            "split the source Markdown at a safe heading boundary"
        )
    return chunks


def response_header(headers, *names):
    for name in names:
        match = re.search(rf"^{re.escape(name)}:\s*(.+?)\r?$", headers, re.I | re.M)
        if match:
            return match.group(1).strip()
    raise RuntimeError(f"missing storage response header: {names}")


def resolve_local_asset(uri, root):
    parsed = urlparse(uri)
    if parsed.scheme in {"http", "https"}:
        raise RuntimeError(f"remote image is not accepted; download it first: {uri}")
    if parsed.scheme and parsed.scheme != "file":
        raise RuntimeError(f"unsupported image URI: {uri}")
    raw_path = unquote(parsed.path if parsed.scheme == "file" else uri)
    path = Path(raw_path)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"image referenced by Markdown does not exist: {uri} -> {path}")
    return path


def upload_attachment(file_id, upload_name, path):
    raw = path.read_bytes()
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    request = cli(
        "api", "post", f"/v7/coop/files/{file_id}/attachments/upload/address",
        "--token-type", "delegated",
        "--data", json.dumps({
            "name": upload_name,
            "size": len(raw),
            "content_type": content_type,
            "md5": hashlib.md5(raw).hexdigest(),
            "internal": False,
        }),
        "-o", "json",
    )["data"]

    store = request["request"]
    command = [
        "curl", "-sS", "-D", "-", "-o", "/dev/null",
        "-X", store.get("method") or "PUT",
    ]
    for name, value in (store.get("headers") or {}).items():
        command.extend(["-H", f"{name}: {value}"])
    command.extend(["--data-binary", "@-", store["url"]])
    proc = subprocess.run(command, input=raw, capture_output=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace"))
    headers = proc.stdout.decode("latin1")
    statuses = re.findall(r"HTTP/\S+\s+(\d+)", headers)
    if not statuses or statuses[-1] not in {"200", "201", "204"}:
        raise RuntimeError(f"attachment store failed: {headers[:600]}")

    complete = cli(
        "api", "post", f"/v7/coop/files/{file_id}/attachments/upload/complete",
        "--token-type", "delegated",
        "--data", json.dumps({
            "upload_id": request["upload_id"],
            "params": {
                "etag": response_header(headers, "etag"),
                "key": response_header(headers, "newfilename", "x-asimov-request-id2"),
            },
        }),
        "-o", "json",
    )["data"]
    return complete["attachment_id"]


def walk(value, visitor):
    if isinstance(value, dict):
        visitor(value)
        for child in value.values():
            walk(child, visitor)
    elif isinstance(value, list):
        for child in value:
            walk(child, visitor)


def count_types(value):
    counts = {}

    def visitor(item):
        kind = item.get("type")
        if kind:
            counts[kind] = counts.get(kind, 0) + 1

    walk(value, visitor)
    return counts


def patch_picture_blocks(blocks, converted_attachments, uploaded, dimensions):
    block_to_uri = {}
    for old_id, refs in converted_attachments.items():
        if len(refs) != 1 or not refs[0].get("uri"):
            raise RuntimeError(f"unexpected converted attachment binding: {old_id} -> {refs}")
        uri = refs[0]["uri"]
        if uri not in uploaded:
            raise RuntimeError(f"no uploaded attachment for picture URI: {uri}")
        block_to_uri[old_id] = uri

    patched = 0

    def visitor(item):
        nonlocal patched
        if item.get("type") != "picture" or item.get("id") not in block_to_uri:
            return
        uri = block_to_uri[item["id"]]
        width, height = dimensions[uri]
        scale = min(740 / width, 740 / height, 1.0)
        item.setdefault("attrs", {}).update({
            "sourceKey": uploaded[uri],
            "width": width,
            "height": height,
            "renderWidth": round(width * scale),
            "renderHeight": round(height * scale),
            "version": 3,
        })
        patched += 1

    walk(blocks, visitor)
    if patched != len(block_to_uri):
        raise RuntimeError(f"patched {patched} pictures but convert declared {len(block_to_uri)}")
    return patched


def source_keys(value):
    found = set()

    def visitor(item):
        if item.get("type") == "picture":
            key = item.get("attrs", {}).get("sourceKey")
            if key:
                found.add(key)

    walk(value, visitor)
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("parent")
    parser.add_argument("title")
    parser.add_argument("markdown")
    parser.add_argument("--drive", default="6lABZaR")
    parser.add_argument("--asset-root")
    parser.add_argument("--on-name-conflict", choices=["fail", "rename"], default="fail")
    parser.add_argument("--result")
    args = parser.parse_args()

    report = Path(args.markdown).resolve()
    if not report.is_file():
        raise FileNotFoundError(report)
    asset_root = Path(args.asset_root).resolve() if args.asset_root else report.parent
    name = args.title if args.title.endswith(".otl") else args.title + ".otl"
    chunks = split_markdown(report.read_text(encoding="utf-8"))

    file_id = None
    try:
        created = cli(
            "api", "post", "/v7/airpage/files",
            "--data", json.dumps({
                "drive_id": args.drive,
                "parent_id": args.parent,
                "name": name,
                "template_id": "",
                "on_name_conflict": args.on_name_conflict,
            }, ensure_ascii=False),
            "-o", "json",
        )["data"]
        file_id = created["id"]
        if created["name"] != name:
            print(f"warning: WPS renamed the file to {created['name']}", file=sys.stderr)

        converted_chunks = []
        uri_paths = {}
        expected = {}
        for chunk in chunks:
            converted = unb64(cli(
                "api", "post", f"/v7/airpage/{file_id}/blocks/convert",
                "--data", json.dumps({"arg": b64({"format": "markdown", "content": chunk})}),
                "-o", "json",
            )["data"]["result"])
            converted_chunks.append(converted)
            counts = count_types(converted["blocks"])
            for kind, count in counts.items():
                expected[kind] = expected.get(kind, 0) + count
            for refs in converted.get("attachments", {}).values():
                if len(refs) != 1 or not refs[0].get("uri"):
                    raise RuntimeError(f"unexpected converted attachment refs: {refs}")
                uri = refs[0]["uri"]
                uri_paths.setdefault(uri, resolve_local_asset(uri, asset_root))

        uploaded = {}
        dimensions = {}
        for index, (uri, path) in enumerate(uri_paths.items(), 1):
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                dimensions[uri] = image.size
            digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
            uploaded[uri] = upload_attachment(file_id, f"{digest}-{path.name}", path)
            print(f"uploaded image {index}/{len(uri_paths)}: {uri}", flush=True)

        patched_pictures = 0
        for index, converted in enumerate(converted_chunks, 1):
            blocks = converted["blocks"]
            patched_pictures += patch_picture_blocks(
                blocks, converted.get("attachments", {}), uploaded, dimensions
            )
            unb64(cli(
                "api", "post", f"/v7/airpage/{file_id}/blocks/create",
                "--data", json.dumps({"arg": b64({
                    "blockId": "doc", "index": 1_000_000_000, "content": blocks,
                })}),
                "-o", "json",
            )["data"]["result"])
            print(f"inserted chunk {index}/{len(converted_chunks)}", flush=True)

        got = unb64(cli(
            "api", "post", f"/v7/airpage/{file_id}/blocks",
            "--data", json.dumps({"arg": b64({"blockId": "doc"})}),
            "-o", "json",
        )["data"]["result"])
        top = got["blocks"][0]["content"]
        actual = count_types(top)

        exported = cli(
            "api", "post", f"/v7/airpage/{file_id}/export_to_json",
            "--data", "{}", "-o", "json",
        )["data"]
        exported_ids = {item.get("id") for item in exported.get("attachment_list", [])}
        exported_ids.discard(None)
        keys = source_keys(top)

        for kind in ("picture", "table", "codeBlock"):
            if actual.get(kind, 0) != expected.get(kind, 0):
                raise RuntimeError(
                    f"{kind} count mismatch: expected {expected.get(kind, 0)}, "
                    f"got {actual.get(kind, 0)}"
                )
        if patched_pictures != expected.get("picture", 0):
            raise RuntimeError(
                f"picture binding mismatch: patched {patched_pictures}, "
                f"expected {expected.get('picture', 0)}"
            )
        if keys != exported_ids or keys != set(uploaded.values()):
            raise RuntimeError(
                "picture sourceKey, uploaded attachment IDs, and export attachment IDs do not match"
            )

        path_result = cli("drive", "file-path", "get", args.drive, file_id, "-o", "json")
        cloud_path = " / ".join(item["name"] for item in path_result["data"]["paths"])
        result = {
            "name": created["name"],
            "drive_id": args.drive,
            "file_id": file_id,
            "link_url": created["link_url"],
            "cloud_path": cloud_path,
            "markdown": str(report),
            "chunks": len(chunks),
            "block_types": actual,
            "pictures": actual.get("picture", 0),
            "unique_attachments": len(exported_ids),
            "tables": actual.get("table", 0),
            "code_blocks": actual.get("codeBlock", 0),
        }
        if args.result:
            result_path = Path(args.result).resolve()
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception:
        if file_id:
            try:
                cli("drive", "file", "delete", args.drive, file_id, "-o", "json")
                print(f"deleted partial document {file_id}", file=sys.stderr)
            except Exception as cleanup_error:
                print(f"failed to delete partial document {file_id}: {cleanup_error}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()

