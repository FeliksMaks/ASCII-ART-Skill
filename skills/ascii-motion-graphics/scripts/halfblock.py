"""Shared by video.py: half-block cells, two coloured pixels a cell (the upper and lower half), twice the detail of
one character a cell.  render.py draws them as two exact rectangles."""
from PIL import Image


def pixels(im):
    return list(im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata())


def halfblock_cells(rgb_img, cols, rows, lift):
    """rgb_img -> per cell the upper and lower pixel's colours (rows of hex), after lift(rgb) -> rgb"""
    P = pixels(rgb_img.resize((cols, rows * 2), Image.BOX))
    fg, bg = [], []
    for r in range(rows):
        fg.append("".join("%02x%02x%02x" % lift(P[(2 * r) * cols + c]) for c in range(cols)))
        bg.append("".join("%02x%02x%02x" % lift(P[(2 * r + 1) * cols + c]) for c in range(cols)))
    return fg, bg
