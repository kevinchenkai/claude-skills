#!/usr/bin/env python3
"""Build a contact sheet for the human story and timing review."""

import argparse

import av
from PIL import Image, ImageDraw


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video")
    parser.add_argument("output")
    parser.add_argument("cells", type=int, nargs="?", default=7)
    parser.add_argument("--cell-width", type=int, default=200)
    parser.add_argument("--label-height", type=int, default=24)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.cells < 2 or args.cell_width < 16 or args.label_height < 0:
        raise SystemExit("cells >= 2, cell-width >= 16, and label-height >= 0 are required")

    container = av.open(args.video)
    try:
        fps = float(container.streams.video[0].average_rate)
        frames = [frame.to_image().convert("RGB") for frame in container.decode(video=0)]
    finally:
        container.close()
    if not frames or fps <= 0:
        raise SystemExit("video has no decodable frames or usable frame rate")

    count = len(frames)
    indices = [round((count - 1) * index / (args.cells - 1)) for index in range(args.cells)]
    source_width, source_height = frames[0].size
    cell_height = round(args.cell_width * source_height / source_width)
    sheet = Image.new(
        "RGB", (args.cell_width * len(indices), cell_height + args.label_height), "white"
    )
    draw = ImageDraw.Draw(sheet)
    for column, frame_index in enumerate(indices):
        x = column * args.cell_width
        sheet.paste(frames[frame_index].resize((args.cell_width, cell_height)), (x, 0))
        if args.label_height:
            draw.text((x + 4, cell_height + 4), f"{frame_index / fps:.2f}s", fill="black")
    sheet.save(args.output, quality=92)

    times = ", ".join(f"{index / fps:.2f}s" for index in indices)
    print(
        f"wrote {args.output} frames={count} fps={fps:.3f} "
        f"source={source_width}x{source_height} samples={times}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
