#!/usr/bin/env python3
import argparse
import csv
import json
import math
import statistics
import time
import uuid
from pathlib import Path
from urllib import error, parse, request


def now_ms():
    return time.perf_counter() * 1000.0


def percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct / 100.0
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return ordered[int(pos)]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (pos - lower)


def summarize(values):
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return {}
    return {
        "count": len(clean),
        "mean": statistics.fmean(clean),
        "min": min(clean),
        "p50": percentile(clean, 50),
        "p90": percentile(clean, 90),
        "p95": percentile(clean, 95),
        "p99": percentile(clean, 99),
        "max": max(clean),
        "stddev": statistics.pstdev(clean) if len(clean) > 1 else 0.0,
    }


def root_url(base_url):
    parsed = parse.urlparse(base_url)
    return parse.urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def timed_get(url, timeout):
    start = now_ms()
    req = request.Request(url, method="GET")
    with request.urlopen(req, timeout=timeout) as resp:
        resp.read()
    return now_ms() - start


def extract_delta_text(payload):
    choices = payload.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    for key in ("content", "reasoning_content"):
        value = delta.get(key)
        if value:
            return value
    return ""


def stream_once(base_url, model, prompt, max_tokens, temperature, timeout):
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    start = now_ms()
    first_token_ms = None
    first_token_text = ""
    non_empty_chunks = 0
    response_bytes = 0

    with request.urlopen(req, timeout=timeout) as resp:
        headers_ms = now_ms() - start
        while True:
            line = resp.readline()
            if not line:
                break
            response_bytes += len(line)
            text = line.decode("utf-8", errors="replace").strip()
            if not text or not text.startswith("data:"):
                continue
            chunk = text[5:].strip()
            if chunk == "[DONE]":
                break
            try:
                payload = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            delta_text = extract_delta_text(payload)
            if delta_text:
                non_empty_chunks += 1
                if first_token_ms is None:
                    first_token_ms = now_ms() - start
                    first_token_text = delta_text

    return {
        "headers_ms": headers_ms,
        "ttft_ms": first_token_ms,
        "total_ms": now_ms() - start,
        "first_token_text": first_token_text,
        "completion_tokens_observed": non_empty_chunks,
        "response_bytes": response_bytes,
    }


def write_csv(path, rows):
    fields = [
        "phase",
        "run_index",
        "ok",
        "health_rtt_ms",
        "headers_ms",
        "ttft_ms",
        "vllm_est_ms",
        "total_ms",
        "completion_tokens_observed",
        "first_token_text",
        "error",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18000/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--output", default="./vllm_ttft_results.json")
    parser.add_argument("--csv-output", default="./vllm_ttft_results.csv")
    args = parser.parse_args()

    health_url = root_url(args.base_url).rstrip("/") + "/health"
    rows = []

    for phase, count in (("warmup", args.warmup), ("measure", args.runs)):
        for idx in range(count):
            salt = uuid.uuid4().hex[:12]
            prompt = (
                f"salt={salt}. Explain first-token latency in two concise sentences."
            )
            row = {"phase": phase, "run_index": idx + 1, "ok": False}
            try:
                health_rtt_ms = timed_get(health_url, args.timeout)
                result = stream_once(
                    args.base_url,
                    args.model,
                    prompt,
                    args.max_tokens,
                    args.temperature,
                    args.timeout,
                )
                row.update(result)
                row["health_rtt_ms"] = health_rtt_ms
                row["vllm_est_ms"] = (
                    max(0.0, result["ttft_ms"] - health_rtt_ms)
                    if result["ttft_ms"] is not None
                    else None
                )
                row["ok"] = row["ttft_ms"] is not None
            except Exception as exc:
                row["error"] = repr(exc)
                if isinstance(exc, error.HTTPError):
                    try:
                        row["error_body"] = exc.read().decode("utf-8", errors="replace")
                    except Exception:
                        pass
            rows.append(row)
            label = "W" if phase == "warmup" else "M"
            if row["ok"]:
                print(
                    f"{label}{idx + 1:02d} health={row['health_rtt_ms']:.2f}ms "
                    f"headers={row['headers_ms']:.2f}ms ttft={row['ttft_ms']:.2f}ms "
                    f"vllm_est={row['vllm_est_ms']:.2f}ms"
                )
            else:
                print(f"{label}{idx + 1:02d} ERROR {row.get('error', 'unknown')}")

    measured = [row for row in rows if row["phase"] == "measure" and row.get("ok")]
    summary = {
        "base_url": args.base_url,
        "model": args.model,
        "runs_requested": args.runs,
        "warmup_requested": args.warmup,
        "runs_ok": len(measured),
        "metrics": {
            "health_rtt_ms": summarize(row.get("health_rtt_ms") for row in measured),
            "headers_ms": summarize(row.get("headers_ms") for row in measured),
            "ttft_ms": summarize(row.get("ttft_ms") for row in measured),
            "vllm_est_ms": summarize(row.get("vllm_est_ms") for row in measured),
            "total_ms": summarize(row.get("total_ms") for row in measured),
        },
        "rows": rows,
    }

    output = Path(args.output)
    csv_output = Path(args.csv_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    csv_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_output, rows)

    print("\nSUMMARY")
    for name, stats in summary["metrics"].items():
        if not stats:
            continue
        print(
            f"{name}: mean={stats['mean']:.2f}ms p50={stats['p50']:.2f}ms "
            f"p90={stats['p90']:.2f}ms p95={stats['p95']:.2f}ms "
            f"p99={stats['p99']:.2f}ms min={stats['min']:.2f}ms max={stats['max']:.2f}ms"
        )
    print(f"\nJSON: {output}")
    print(f"CSV: {csv_output}")


if __name__ == "__main__":
    main()
