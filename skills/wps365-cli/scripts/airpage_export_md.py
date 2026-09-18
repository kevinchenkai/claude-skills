#!/usr/bin/env python3
"""把智能文档（AirPage/.otl）导出为 Markdown。

为什么不用 `drive file-content get --format markdown`：
它会整表丢失。实测一篇 .otl，源文档 7 表（44 单元格）导出后剩 0 表、
25 标题剩 13，而 `is_partly_exported` 仍返回 false——该字段不能当完整性依据。
本脚本改从 `airpage block get` 的块树重建，并做一次可自证的完整性校验。

用法：
    python3 airpage_export_md.py <file_id> -o out.md
    python3 airpage_export_md.py <file_id> -o out.md --front-matter
    python3 airpage_export_md.py <file_id> --stdout

完整性校验总是执行：把源块树里每个 attributes.content 片段与产物比对，
命中率不足即以非 0 退出，并列出缺失片段。--allow-loss 可降级为警告。
"""
import argparse
import json
import os
import re
import subprocess
import sys

WPS = os.path.expanduser(os.environ.get("WPS365_CLI", "~/.local/bin/wps365-cli"))

# 已在真实文档中验证过的块类型；其余一律告警，不静默丢弃
KNOWN = {"paragraph", "heading", "table", "blockquote", "code_block", "title", "doc",
         "horizontal_rule"}


def run(args, timeout=120):
    p = subprocess.run([WPS] + args, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        sys.exit(f"命令失败: wps365-cli {' '.join(args)}\n{p.stderr or p.stdout}")
    return p.stdout


def fetch(file_id):
    raw = run(["airpage", "block", "get", file_id, "-o", "json"])
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(f"返回不是 JSON，前 200 字符：\n{raw[:200]}")
    if d.get("code") != 0:
        sys.exit(f"接口返回 code={d.get('code')} msg={d.get('msg')}")
    return d["data"]["block"]


def inline(elements):
    """elements[] -> 带行内格式的文本。样式叠加顺序固定，保证可复现。"""
    out = []
    for e in elements or []:
        t = e.get("text")
        if not t:
            continue
        a = t.get("attributes") or {}
        s = a.get("content", "")
        if not s:
            continue
        st = a.get("style") or {}
        if st.get("code"):
            s = f"`{s}`"
        if st.get("bold"):
            s = f"**{s}**"
        if st.get("italic"):
            s = f"*{s}*"
        if st.get("strikethrough"):
            s = f"~~{s}~~"
        link = a.get("link")
        if isinstance(link, dict) and link.get("url"):
            s = f"[{s}]({link['url']})"
        out.append(s)
    return "".join(out).strip()


def children_of(node):
    """AirPage v2 的子块可能在 children，也可能在 doc_children。"""
    return node.get("children") or node.get("doc_children") or []


def cell_md(cell):
    """单元格可含多个段落；表格语法不允许换行，压成一行并转义竖线。"""
    parts = [inline(n.get("elements")) for ch in children_of(cell) for n in ch.values()]
    return " ".join(p for p in parts if p).replace("|", "\\|")


def render(nodes, unknown):
    lines = []
    for node in nodes or []:
        for kind, body in node.items():
            if kind in ("block_id", "range_marks", "attributes"):
                continue
            if not isinstance(body, dict):
                continue
            attrs = body.get("attributes") or {}

            if kind == "heading":
                lvl = max(1, min(6, int(attrs.get("level") or 1)))
                txt = inline(body.get("elements"))
                if txt:
                    lines += [f"{'#' * lvl} {txt}", ""]

            elif kind == "paragraph":
                txt = inline(body.get("elements"))
                if not txt:
                    continue
                if attrs.get("ordered"):
                    lines.append(f"1. {txt}")
                elif attrs.get("bullet"):
                    lines.append(f"- {txt}")
                else:
                    lines += [txt, ""]

            elif kind == "blockquote":
                txt = inline(body.get("elements"))
                if txt:
                    lines += [f"> {txt}", ""]

            elif kind == "code_block":
                lang = attrs.get("language") or ""
                if lang == "plaintext":
                    lang = ""
                lines += [f"```{lang}", inline(body.get("elements")), "```", ""]

            elif kind == "table":
                rows = body.get("rows") or []
                if not rows:
                    continue
                head = [cell_md(c) for c in (rows[0].get("cells") or [])]
                if not head:
                    continue
                lines.append("| " + " | ".join(head) + " |")
                lines.append("|" + "---|" * len(head))
                for r in rows[1:]:
                    cs = [cell_md(c) for c in (r.get("cells") or [])]
                    cs += [""] * (len(head) - len(cs))
                    lines.append("| " + " | ".join(cs[: len(head)]) + " |")
                lines.append("")

            elif kind == "horizontal_rule":
                lines += ["---", ""]

            elif kind in ("image", "picture"):
                # 图片二进制不随块树返回；留可见占位，不假装导出成功
                name = attrs.get("name") or attrs.get("sourceKey") or "image"
                lines += [f"<!-- 图片未导出: {name} -->", ""]
                unknown.append(f"{kind}({name})")

            else:
                if kind not in KNOWN:
                    unknown.append(kind)
                txt = inline(body.get("elements"))
                if txt:
                    lines += [txt, ""]
                sub = children_of(body)
                if sub:
                    lines += render(sub, unknown)
    return lines


def source_fragments(block):
    """源块树里全部正文片段，用于完整性比对。"""
    out = []

    def walk(x):
        if isinstance(x, dict):
            a = x.get("attributes")
            if isinstance(a, dict) and isinstance(a.get("content"), str):
                s = a["content"].strip()
                if s:
                    out.append(s)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(block)
    return out


def check(block, md, probe_len=24):
    """完整性校验，并自证：故意抽走一段必须能被报出，否则校验本身无效。"""
    frags = [f for f in source_fragments(block) if len(f) >= 10]
    missing = [f for f in frags if f[:probe_len] not in md]

    valid = False
    if frags:
        probe = max(frags, key=len)
        valid = probe[:probe_len] not in md.replace(probe, "", 1)
    return frags, missing, valid


def main():
    ap = argparse.ArgumentParser(description="把智能文档导出为 Markdown（从块树重建）")
    ap.add_argument("file_id")
    ap.add_argument("-o", "--out", help="输出 .md 路径")
    ap.add_argument("--stdout", action="store_true", help="打印到标准输出")
    ap.add_argument("--front-matter", action="store_true", help="写入 file_id / 导出时间")
    ap.add_argument("--allow-loss", action="store_true", help="完整性不足时仅告警")
    a = ap.parse_args()

    if not a.out and not a.stdout:
        ap.error("需要 -o 或 --stdout")

    block = fetch(a.file_id)
    doc = block.get("doc") or block

    title = ""
    t = doc.get("title")
    if isinstance(t, dict):
        title = inline(t.get("elements"))

    unknown = []
    body = render(children_of(doc), unknown)

    head = []
    if a.front_matter:
        import datetime

        head = [
            "---",
            f'source: "wps365:{a.file_id}"',
            f"exported_at: {datetime.date.today().isoformat()}",
            "exported_by: airpage_export_md.py",
            "---",
            "",
        ]
    if title:
        head += [f"# {title}", ""]

    md = re.sub(r"\n{3,}", "\n\n", "\n".join(head + body)).strip() + "\n"

    frags, missing, valid = check(block, md)
    hit = len(frags) - len(missing)
    print(f"块统计: 表格 {md.count(chr(10) + '|---')} / 标题 {len(re.findall(r'^#{1,6} ', md, re.M))}", file=sys.stderr)
    print(f"完整性: {hit}/{len(frags)} 片段命中", file=sys.stderr)
    print(f"校验自证: {'通过（能检出人为删除）' if valid else '⚠️ 无效——校验器可能只会报 0'}", file=sys.stderr)

    if unknown:
        print(f"⚠️ 未覆盖/未导出的块: {', '.join(sorted(set(unknown)))}", file=sys.stderr)
    if missing:
        print(f"⚠️ 缺失 {len(missing)} 段，前 5 条：", file=sys.stderr)
        for m in missing[:5]:
            print(f"    {m[:70]}", file=sys.stderr)
        if not a.allow_loss:
            sys.exit("完整性不足，未写出文件（要强制写出加 --allow-loss）")
    if not valid and not a.allow_loss:
        sys.exit("完整性校验自证失败，拒绝把结果当成完整导出")

    if a.stdout:
        sys.stdout.write(md)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"✅ {a.out}  ({len(md.encode())} 字节 / {md.count(chr(10)) + 1} 行)", file=sys.stderr)


if __name__ == "__main__":
    main()
