#!/usr/bin/env python3
"""Read burned-in Chinese subtitles from a video clip with RapidOCR (PP-OCRv6), CPU only; JSONL to stdout or --out.

Run in the movieDB env:  source /nfs/envs/moviedb-env.sh
Each line: {start, end, text, score}. Picture text is dropped by requiring a centred line that contains CJK;
a line seen in one frame only is dropped as a transition ghost.
CPU only on purpose: onnxruntime-gpu next to another large GPU process has preceded driver hangs (see references/asr_ocr.md).
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "4")

from concurrent.futures import ProcessPoolExecutor  # noqa: E402

import numpy as np  # noqa: E402

CJK = re.compile(r"[一-鿿]")
MIN_SCORE = 0.6
_ENG = None


def ocr_frame(img):
    global _ENG
    if _ENG is None:
        from rapidocr import RapidOCR
        _ENG = RapidOCR(params={"Global.log_level": "error",
                                "EngineConfig.onnxruntime.intra_op_num_threads": 4,
                                "EngineConfig.onnxruntime.inter_op_num_threads": 1})
    r = _ENG(np.repeat(img[:, :, None], 3, axis=2))
    if r is None or r.txts is None:
        return []
    out = []
    for box, text, score in zip(r.boxes, r.txts, r.scores):
        b = np.asarray(box)
        out.append((float(b[:, 0].min()), float(b[:, 0].max()), text.strip(), float(score)))
    return out


def subtitle_of(boxes, w):
    """Join the boxes of a frame whose combined line is centred and contains CJK; '' if none.

    Each box must sit near the centre on its own: corner watermarks share the subtitle row and, if joined,
    get pasted into every line and make different subtitles look alike.
    """
    boxes = sorted((b for b in boxes if b[2] and b[3] >= MIN_SCORE and CJK.search(b[2])
                    and abs((b[0] + b[1]) / 2 - w / 2) <= 0.3 * w), key=lambda b: b[0])
    if not boxes or abs((boxes[0][0] + boxes[-1][1]) / 2 - w / 2) > 0.2 * w:
        return "", 0.0
    return " ".join(b[2] for b in boxes), min(b[3] for b in boxes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--dur", type=float, help="seconds; omit for the whole file")
    ap.add_argument("--fps", type=float, default=3)
    ap.add_argument("--top", type=float, default=0.78, help="scan from this fraction of the frame height to the bottom")
    ap.add_argument("--workers", type=int, default=8, help="each worker uses 4 threads")
    ap.add_argument("--out")
    a = ap.parse_args()

    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", a.input], capture_output=True, text=True, check=True)
    W, H = map(int, p.stdout.strip().split(",")[:2])
    y0 = int(H * a.top) // 2 * 2
    h = (H - y0) // 2 * 2
    w = W
    # scale to the nominal size first: some sources change resolution mid-file and crop would fail
    vf = f"fps={a.fps},scale={W}:{H},crop={W}:{h}:0:{y0}"
    if W > 1920:
        w, h = 1920, int(round(h * 1920 / W / 2)) * 2
        vf += f",scale={w}:{h}"
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-ss", str(a.start)]
    cmd += ["-t", str(a.dur)] if a.dur else []
    cmd += ["-i", a.input, "-map", "0:v:0", "-vf", vf + ",format=gray", "-f", "rawvideo", "-"]
    band = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.uint8).reshape(-1, h, w)

    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex:
        results = list(ex.map(ocr_frame, list(band), chunksize=8))
    seq = [subtitle_of(r, w) for r in results]

    rows, i = [], 0
    while i < len(seq):
        if not seq[i][0]:
            i += 1
            continue
        j = i
        while j + 1 < len(seq) and seq[j + 1][0] and \
                difflib.SequenceMatcher(None, seq[i][0], seq[j + 1][0]).ratio() >= 0.8:
            j += 1
        if j > i:
            texts = [seq[k][0] for k in range(i, j + 1)]
            best = max(set(texts), key=texts.count)
            rows.append({"start": round(a.start + i / a.fps, 2), "end": round(a.start + (j + 1) / a.fps, 2),
                         "text": best, "score": round(max(s for t, s in seq[i:j + 1] if t == best), 3)})
        i = j + 1

    out = open(a.out, "w", encoding="utf-8") if a.out else sys.stdout
    for r in rows:
        out.write(json.dumps(r, ensure_ascii=False) + "\n")
    out.flush()
    dt = time.time() - t0
    print(f"OCR_DONE lines={len(rows)} frames={len(band)} ocr_s={dt:.1f} ocr_fps={len(band) / dt:.1f} "
          f"workers={a.workers}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
