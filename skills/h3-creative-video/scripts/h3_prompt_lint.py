#!/usr/bin/env python3
"""Validate MiniMax-H3 base-mode and Ref2VA prompts."""

import argparse
import json
import re
import sys
from pathlib import Path


BASE_FIELDS = (
    "integrated_multimodal_description",
    "overall_soundscape",
    "non_diegetic_music",
)
REF_FIELDS = (
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
)
REF_TASK_TYPES = {
    "keyframe completion",
    "reference generation",
    "video editing",
    "video continuation",
    "audio reuse",
    "audio reference",
}
VISUAL_RETENTION = {
    "fully_preserved",
    "partially_preserved",
    "attribute_transfer",
    "weak_reference",
}
AUDIO_RETENTION = {
    "fully_copy",
    "partially_copy",
    "reference",
    "weak_reference",
}
REFERENCE_TYPES = ("Subject", "Picture", "Video", "Audio")
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
    if line == "subject_definitions:":
        return "ref2va"
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


def section_text(text, field_matches, fields, field):
    index = fields.index(field)
    start = field_matches[field][0].end()
    end = field_matches[fields[index + 1]][0].start() if index + 1 < len(fields) else len(text)
    return text[start:end]


def reference_numbers(text, reference_type):
    return sorted({
        int(value)
        for value in re.findall(rf"<{reference_type}\s+(\d+)>", text)
    })


def lint_shots(body, field_name, duration, require_shot_first, errors):
    shots = []
    shot_matches = list(re.finditer(r"\[Shot (\d+)\]", body))
    if not shot_matches:
        errors.append(f"{field_name} must contain [Shot 1]")
        return shots, []
    if require_shot_first and not body.lstrip().startswith("[Shot 1]"):
        errors.append(f"{field_name} must begin with [Shot 1]")

    shot_numbers = [int(match.group(1)) for match in shot_matches]
    expected = list(range(1, len(shot_numbers) + 1))
    if shot_numbers != expected:
        errors.append(f"shot numbers must appear once and sequentially: got {shot_numbers}")

    previous_time = 0.0
    for match in shot_matches:
        number = int(match.group(1))
        following = body[match.end():]
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
    return shots, shot_numbers


def lint_ref2va(text, field_matches, duration, inventory, errors, warnings):
    sections = {
        field: section_text(text, field_matches, REF_FIELDS, field)
        for field in REF_FIELDS
    }

    definitions = sections["subject_definitions"]
    definition_lines = [line.strip() for line in definitions.splitlines() if line.strip()]
    if not definition_lines:
        errors.append("subject_definitions must contain at least one reference definition")
    for line in definition_lines:
        if not re.match(r"<(?:Subject|Picture|Video|Audio)\s+\d+>", line):
            errors.append("each subject_definitions entry must begin with a reference label")

    all_numbers = {kind: reference_numbers(text, kind) for kind in REFERENCE_TYPES}
    definition_numbers = {kind: reference_numbers(definitions, kind) for kind in REFERENCE_TYPES}
    for kind in REFERENCE_TYPES:
        invalid = [number for number in all_numbers[kind] if number < 1]
        if invalid:
            errors.append(f"{kind} labels must use 1-based positive ordinals: {invalid}")
        unresolved = sorted(set(all_numbers[kind]) - set(definition_numbers[kind]))
        if unresolved:
            errors.append(
                f"{kind} labels used outside subject_definitions are undefined: {unresolved}"
            )
    subjects = all_numbers["Subject"]
    if subjects and subjects != list(range(1, max(subjects) + 1)):
        errors.append(f"Subject labels must be sequential from 1: got {subjects}")

    summary = sections["summary"].strip()
    summary_match = re.match(r"\[([^\]\n]+)\]\s+\S", summary)
    if not summary_match:
        errors.append("summary must begin with a square-bracketed Ref2VA task type")
    else:
        task_types = summary_match.group(1).split(" + ")
        unknown = [task for task in task_types if task not in REF_TASK_TYPES]
        if unknown:
            errors.append(f"unknown Ref2VA summary task types: {unknown}")
        if len(task_types) != len(set(task_types)):
            errors.append("Ref2VA summary task types must not repeat")

    retention_lines = [
        line.strip()
        for line in sections["retention_analysis"].splitlines()
        if line.strip()
    ]
    if not retention_lines:
        errors.append("retention_analysis must contain at least one relationship line")
    marker_pattern = "|".join(sorted(VISUAL_RETENTION | AUDIO_RETENTION, key=len, reverse=True))
    retained_labels = set()
    for line in retention_lines:
        label_match = re.match(r"<(Subject|Picture|Video|Audio)\s+(\d+)>", line)
        if not label_match:
            errors.append("each retention_analysis entry must begin with a reference label")
            continue
        retained_labels.add((label_match.group(1), int(label_match.group(2))))
        marker_match = re.search(rf":\s*({marker_pattern})\s+-\s+\S", line)
        if not marker_match:
            errors.append(f"retention_analysis entry has no valid marker/explanation: {line[:80]}")
            continue
        kind, marker = label_match.group(1), marker_match.group(1)
        allowed = AUDIO_RETENTION if kind == "Audio" else VISUAL_RETENTION
        if marker not in allowed:
            errors.append(f"{kind} retention marker {marker} is invalid for that label type")

    defined_labels = {
        (match.group(1), int(match.group(2)))
        for line in definition_lines
        if (match := re.match(r"<(Subject|Picture|Video|Audio)\s+(\d+)>", line))
    }
    definition_starts = [
        (match.group(1), int(match.group(2)))
        for line in definition_lines
        if (match := re.match(r"<(Subject|Picture|Video|Audio)\s+(\d+)>", line))
    ]
    duplicate_definitions = sorted({
        label for label in definition_starts if definition_starts.count(label) > 1
    })
    if duplicate_definitions:
        errors.append(f"reference labels have duplicate standalone definitions: {duplicate_definitions}")
    missing_retention = sorted(defined_labels - retained_labels)
    if missing_retention:
        errors.append(f"standalone definitions missing from retention_analysis: {missing_retention}")

    counts = {
        "Picture": inventory.get("pictures"),
        "Video": inventory.get("videos"),
        "Audio": inventory.get("audios"),
    }
    if all(value is not None for value in counts.values()) and not any(counts.values()):
        errors.append("Ref2VA requires at least one connected reference")
    if counts["Picture"] is not None and counts["Picture"] > 9:
        errors.append("Ref2VA supports at most 9 reference images")
    if counts["Video"] is not None and counts["Video"] > 3:
        errors.append("Ref2VA supports at most 3 reference videos")
    if counts["Audio"] is not None:
        max_audio_labels = (counts["Video"] if counts["Video"] is not None else 3) + 3
        if counts["Audio"] > max_audio_labels:
            errors.append(
                "Audio label count exceeds connected video soundtracks plus 3 standalone audios"
            )

    missing_inventory = [key for key, value in inventory.items() if value is None]
    if missing_inventory:
        warnings.append(
            "Ref2VA reference counts not supplied for " + ", ".join(missing_inventory)
        )
    for kind, count in counts.items():
        if count is None:
            continue
        used = all_numbers[kind]
        out_of_range = [number for number in used if number < 1 or number > count]
        if out_of_range:
            errors.append(f"{kind} labels exceed connected count {count}: {out_of_range}")
        unmentioned = sorted(set(range(1, count + 1)) - set(used))
        if unmentioned:
            warnings.append(f"connected {kind} labels never mentioned: {unmentioned}")

    shots, shot_numbers = lint_shots(
        sections["detailed_description"],
        "detailed_description",
        duration,
        False,
        errors,
    )
    return shots, shot_numbers, all_numbers


def lint(text, requested_mode="auto", duration=None, pictures=None, videos=None, audios=None):
    text = text.lstrip("\ufeff")
    errors, warnings = [], []
    first_line = first_nonblank_line(text)
    physical_lines = text.splitlines()
    detected_mode = detect_mode(first_line)
    mode = detected_mode if requested_mode == "auto" else requested_mode

    if not first_line:
        errors.append("prompt is empty")
        return {"ok": False, "mode": mode, "detected_mode": None,
                "duration_sec": duration, "shots": [], "references": {},
                "inventory": {"pictures": pictures, "videos": videos, "audios": audios},
                "errors": errors, "warnings": warnings}
    if physical_lines and physical_lines[0].strip() != first_line:
        errors.append("prompt must begin on physical line 1 with no blank line or preamble")
    if detected_mode is None:
        errors.append("first nonblank line does not match an official H3 mode opening")
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
    elif mode == "ref2va":
        if first_line != "subject_definitions:":
            errors.append("Ref2VA must begin directly with subject_definitions:")

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

    fields = REF_FIELDS if mode == "ref2va" else BASE_FIELDS
    field_matches = {}
    for field in fields:
        matches = list(re.finditer(rf"(?m)^{re.escape(field)}:\s*", text))
        field_matches[field] = matches
        if len(matches) != 1:
            errors.append(f"field {field} must appear exactly once at the start of a line")

    valid_fields = all(len(field_matches[field]) == 1 for field in fields)
    if valid_fields:
        ordered = [field_matches[field][0].start() for field in fields]
        if ordered != sorted(ordered):
            errors.append("core fields are not in official order")
        for index, field in enumerate(fields):
            match = field_matches[field][0]
            end = field_matches[fields[index + 1]][0].start() if index + 1 < len(fields) else len(text)
            if not text[match.end():end].strip():
                errors.append(f"field {field} is empty; use N/A only where officially allowed")

    shots = []
    references = {}
    if valid_fields and ordered == sorted(ordered):
        if mode == "ref2va":
            shots, shot_numbers, references = lint_ref2va(
                text,
                field_matches,
                duration,
                {"pictures": pictures, "videos": videos, "audios": audios},
                errors,
                warnings,
            )
        else:
            integrated = section_text(
                text,
                field_matches,
                BASE_FIELDS,
                "integrated_multimodal_description",
            )
            shots, shot_numbers = lint_shots(
                integrated,
                "integrated_multimodal_description",
                duration,
                True,
                errors,
            )
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
        "references": references,
        "inventory": {"pictures": pictures, "videos": videos, "audios": audios},
        "errors": errors,
        "warnings": warnings,
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="UTF-8 prompt file, or - for stdin")
    parser.add_argument(
        "--mode",
        choices=("auto", "t2va", "i2va", "fl2va", "l2va", "ref2va"),
        default="auto",
    )
    parser.add_argument("--duration", type=float, help="Effective video duration in seconds")
    parser.add_argument("--pictures", type=int, help="Connected Ref2VA <Picture N> label count")
    parser.add_argument("--videos", type=int, help="Connected Ref2VA <Video N> label count")
    parser.add_argument(
        "--audios",
        type=int,
        help="Emitted Ref2VA <Audio N> label count, including enabled video soundtracks",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    for name in ("pictures", "videos", "audios"):
        value = getattr(args, name)
        if value is not None and value < 0:
            parser.error(f"--{name} must be non-negative")
    return args


def main():
    args = parse_args()
    try:
        result = lint(
            read_prompt(args.prompt),
            args.mode,
            args.duration,
            args.pictures,
            args.videos,
            args.audios,
        )
    except Exception as exc:
        result = {"ok": False, "mode": args.mode, "detected_mode": None,
                  "duration_sec": args.duration, "shots": [], "references": {},
                  "inventory": {"pictures": args.pictures, "videos": args.videos,
                                "audios": args.audios},
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
