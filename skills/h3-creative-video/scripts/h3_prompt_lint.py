#!/usr/bin/env python3
"""Validate MiniMax-H3 base prompts for T2VA, I2VA, FL2VA, or L2VA."""

import argparse
import json
import re
import sys
from pathlib import Path


FIELDS = (
    "integrated_multimodal_description",
    "overall_soundscape",
    "non_diegetic_music",
)
I2VA_LINE = (
    "For the target video, at 0.00 seconds into the target video, "
    "<Picture 1> (from [Shot 1]) is fully referenced."
)
FL2VA_RE = re.compile(
    r"How the reference pictures align with the target video — Picture 1 "
    r"\(from Shot 1\) aligns with the 0\.00-second mark of the target video; "
    r"Picture 2 \(from Shot (\d+)\) aligns with the (\d+\.\d{2})-second mark "
    r"of the target video\."
)
L2VA_RE = re.compile(
    r"How the reference pictures align with the target video — <Picture 1> "
    r"\(from \[Shot (\d+)\]\) aligns with the (\d+\.\d{2})-second mark "
    r"of the target video\."
)


def read_prompt(path):
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def first_nonblank_line(text):
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def detect_mode(line):
    if line.startswith("integrated_multimodal_description:"):
        return "t2va"
    if line == I2VA_LINE:
        return "i2va"
    if FL2VA_RE.fullmatch(line):
        return "fl2va"
    if L2VA_RE.fullmatch(line):
        return "l2va"
    return None


def seconds(value):
    minutes, secs = value.split(":")
    return int(minutes) * 60 + float(secs)


def lint(text, requested_mode="auto", duration=None):
    text = text.lstrip("\ufeff")
    errors, warnings = [], []
    first_line = first_nonblank_line(text)
    physical_lines = text.splitlines()
    detected_mode = detect_mode(first_line)
    mode = detected_mode if requested_mode == "auto" else requested_mode

    if not first_line:
        errors.append("prompt is empty")
        return {"ok": False, "mode": mode, "detected_mode": None,
                "duration_sec": duration, "shots": [], "errors": errors, "warnings": warnings}
    if physical_lines and physical_lines[0].strip() != first_line:
        errors.append("prompt must begin on physical line 1 with no blank line or preamble")
    if detected_mode is None:
        errors.append("first nonblank line does not match an official base-mode opening")
    elif requested_mode != "auto" and detected_mode != requested_mode:
        errors.append(f"opening detects {detected_mode}, but --mode requests {requested_mode}")

    aligned_duration = None
    aligned_final_shot = None
    if mode == "t2va":
        if not first_line.startswith("integrated_multimodal_description:"):
            errors.append("T2VA must begin directly with integrated_multimodal_description")
        if re.search(
            r"reference pictures align|<Picture\s+\d+>|Picture\s+\d+.*aligns with",
            text,
            re.IGNORECASE,
        ):
            errors.append("T2VA must not contain endpoint Picture-alignment instructions")
    elif mode == "i2va":
        if first_line != I2VA_LINE:
            errors.append("I2VA first-frame instruction does not match the official line")
    elif mode == "fl2va":
        match = FL2VA_RE.fullmatch(first_line)
        if not match:
            errors.append("FL2VA alignment instruction does not match the official line")
        else:
            aligned_final_shot = int(match.group(1))
            aligned_duration = float(match.group(2))
    elif mode == "l2va":
        match = L2VA_RE.fullmatch(first_line)
        if not match:
            errors.append("L2VA alignment instruction does not match the official line")
        else:
            aligned_final_shot = int(match.group(1))
            aligned_duration = float(match.group(2))

    if mode in ("i2va", "fl2va", "l2va"):
        if len(physical_lines) < 2 or physical_lines[1].strip():
            errors.append("image-mode alignment instruction must be followed by one blank line")

    if duration is None:
        duration = aligned_duration
    elif aligned_duration is not None and abs(duration - aligned_duration) > 0.011:
        errors.append(
            f"alignment duration {aligned_duration:.2f}s != requested duration {duration:.2f}s"
        )
    if duration is not None and duration <= 0:
        errors.append("duration must be greater than zero")

    field_matches = {}
    for field in FIELDS:
        matches = list(re.finditer(rf"(?m)^{re.escape(field)}:\s*", text))
        field_matches[field] = matches
        if len(matches) != 1:
            errors.append(f"field {field} must appear exactly once at the start of a line")

    if all(len(field_matches[field]) == 1 for field in FIELDS):
        ordered = [field_matches[field][0].start() for field in FIELDS]
        if ordered != sorted(ordered):
            errors.append("core fields are not in official order")
        for index, field in enumerate(FIELDS):
            match = field_matches[field][0]
            end = field_matches[FIELDS[index + 1]][0].start() if index + 1 < len(FIELDS) else len(text)
            if not text[match.end():end].strip():
                errors.append(f"field {field} is empty; use N/A only where officially allowed")

    shots = []
    integrated = ""
    if len(field_matches[FIELDS[0]]) == 1 and len(field_matches[FIELDS[1]]) == 1:
        start = field_matches[FIELDS[0]][0].end()
        end = field_matches[FIELDS[1]][0].start()
        integrated = text[start:end]
        shot_matches = list(re.finditer(r"\[Shot (\d+)\]", integrated))
        if not shot_matches:
            errors.append("integrated_multimodal_description must contain [Shot 1]")
        elif not integrated.lstrip().startswith("[Shot 1]"):
            errors.append("integrated_multimodal_description must begin with [Shot 1]")
        shot_numbers = [int(match.group(1)) for match in shot_matches]
        expected = list(range(1, len(shot_numbers) + 1))
        if shot_numbers != expected:
            errors.append(f"shot numbers must appear once and sequentially: got {shot_numbers}")

        previous_time = 0.0
        for index, match in enumerate(shot_matches):
            number = int(match.group(1))
            following = integrated[match.end():]
            if number == 1:
                if re.match(r"\s*At\s+\d{2}:[0-5]\d\.\d{3},", following):
                    errors.append("Shot 1 must not have a timestamp")
                shots.append({"shot": number, "cut_sec": None})
                continue
            timing = re.match(r"\s*At\s+(\d{2}:[0-5]\d\.\d{3}),", following)
            if not timing:
                errors.append(f"Shot {number} must begin with At 00:MM.SSS,")
                shots.append({"shot": number, "cut_sec": None})
                continue
            cut_sec = seconds(timing.group(1))
            if cut_sec <= previous_time:
                errors.append(f"Shot {number} cut time is not strictly increasing")
            if duration is not None and cut_sec >= duration:
                errors.append(f"Shot {number} cut {cut_sec:.3f}s is outside duration {duration:.3f}s")
            previous_time = cut_sec
            shots.append({"shot": number, "cut_sec": cut_sec})

        if shot_numbers and shot_numbers[0] != 1:
            errors.append("integrated_multimodal_description must begin with Shot 1")
        if aligned_final_shot is not None and shot_numbers:
            if aligned_final_shot != shot_numbers[-1]:
                errors.append(
                    f"alignment names Shot {aligned_final_shot} as final, "
                    f"but prompt ends with Shot {shot_numbers[-1]}"
                )

    if text.count("<d>") != text.count("</d>"):
        errors.append("dialogue tags <d> and </d> are unbalanced")
    for content in re.findall(r"<d>(.*?)</d>", text, flags=re.DOTALL):
        if not re.match(r"\s*\[[^\]\n]+\]\s+\S", content):
            errors.append("each <d> block must begin with [Language] followed by exact content")

    if duration is None:
        warnings.append("duration not supplied or encoded; cut times cannot be checked against the end")
    if mode == "t2va" and "Picture" in first_line:
        errors.append("T2VA opening must not refer to a Picture")

    return {
        "ok": not errors,
        "mode": mode,
        "detected_mode": detected_mode,
        "duration_sec": duration,
        "shots": shots,
        "errors": errors,
        "warnings": warnings,
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="UTF-8 prompt file, or - for stdin")
    parser.add_argument("--mode", choices=("auto", "t2va", "i2va", "fl2va", "l2va"), default="auto")
    parser.add_argument("--duration", type=float, help="Effective video duration in seconds")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        result = lint(read_prompt(args.prompt), args.mode, args.duration)
    except Exception as exc:
        result = {"ok": False, "mode": args.mode, "detected_mode": None,
                  "duration_sec": args.duration, "shots": [],
                  "errors": [str(exc)], "warnings": []}

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"mode={result['mode']} {'OK' if result['ok'] else 'FAIL'}")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for warning in result["warnings"]:
            print(f"WARN: {warning}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
