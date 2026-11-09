#!/usr/bin/env python3
"""Transcribe one audio/video file with faster-whisper large-v3; JSONL to stdout or --out.

Run in the movieDB env:  source /nfs/envs/moviedb-env.sh
Each line: {start, end, text, lang, suspect}. suspect=true marks known Whisper hallucination
phrases; they are kept so the caller decides (see references/asr_ocr.md).
The last stderr line reports speed. ASR_DONE (exit 0) means the transcript passed the hallucination
gate; ASR_SUSPECT (exit 3) means over 10% of the characters are known hallucination text.
"""
import argparse
import json
import os
import re
import sys
import time

MODEL = os.environ.get("ASR_MODEL", "/home/share/models/faster-whisper-large-v3")
SENT_END = tuple("。！？!?.…")
HALLU = re.compile(r"点赞|订阅|转发|打赏|明镜|字幕由|字幕组|Amara|请不吝|Thanks for watching|Subscribe", re.I)


def split_lines(words):
    """Cut word timestamps into lines: sentence end, pause > 1 s, or line > 12 s."""
    lines, cur = [], []

    def flush():
        text = "".join(w.word for w in cur).strip()
        if text:
            lines.append((cur[0].start, cur[-1].end, text))
        cur.clear()

    for w in words:
        if cur and (w.start - cur[-1].end > 1.0 or w.end - cur[0].start > 12):
            flush()
        cur.append(w)
        if w.word.strip().endswith(SENT_END):
            flush()
    flush()
    return lines


def transcribe(a):
    from faster_whisper import WhisperModel

    # Sequential, no initial_prompt, on both devices. Do not change either without re-measuring:
    # sequential + prompt turned a 10 min clip with a music intro into pure hallucination, and
    # BatchedInferencePipeline silently lost a 25 s passage of a 32 min talk at any batch size.
    if a.device == "cpu":
        m = WhisperModel(MODEL, device="cpu", compute_type="int8", cpu_threads=a.threads)
    else:
        m = WhisperModel(MODEL, device="cuda", device_index=0, compute_type="float16")
    return m.transcribe(a.input, language=a.lang, vad_filter=not a.no_vad, beam_size=5, word_timestamps=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    ap.add_argument("--lang", default="zh", help="zh/en/ko/ja; 'auto' detects the language")
    ap.add_argument("--no-vad", action="store_true", help="keep whispers VAD would drop; expect silence hallucinations")
    ap.add_argument("--threads", type=int, default=16, help="CPU threads; never leave this to the host core count")
    ap.add_argument("--out")
    a = ap.parse_args()
    a.lang = None if a.lang == "auto" else a.lang

    t0 = time.time()
    segs, info = transcribe(a)
    n = chars = bad_chars = wordless = 0
    out = open(a.out, "w", encoding="utf-8") if a.out else sys.stdout
    for s in segs:
        if s.words:
            lines = split_lines(s.words)
        else:  # a segment can come back with text but no word timestamps; keep the text
            wordless += 1
            lines = [(s.start, s.end, s.text.strip())] if s.text.strip() else []
        suspect = bool(HALLU.search(s.text))  # whole segment: lines can split a phrase (Am / ara. / org)
        for start, end, text in lines:
            n += 1
            chars += len(text)
            bad_chars += len(text) if suspect else 0
            out.write(json.dumps({"start": round(start, 2), "end": round(end, 2), "text": text,
                                  "lang": info.language, "suspect": suspect}, ensure_ascii=False) + "\n")
            out.flush()
    dt = time.time() - t0
    ratio = bad_chars / chars if chars else 0.0
    status = "ASR_SUSPECT" if ratio > 0.1 else "ASR_DONE"
    print(f"{status} device={a.device} lines={n} chars={chars} suspect_ratio={ratio:.2f} wordless_segments={wordless} "
          f"audio_s={info.duration:.1f} "
          f"elapsed_s={dt:.1f} x_realtime={info.duration / dt:.1f} (includes model load)", file=sys.stderr, flush=True)
    if status == "ASR_SUSPECT":
        sys.exit(3)


if __name__ == "__main__":
    main()
