# ruff: noqa: E501
"""Helpers for the raking-light deck: layout boxes, tables, native SVG charts, pad glyphs.

Colour semantics (see slides/README.md):
  amber  = an anomaly found, an open item, a failed or unsupported result (always with a word or symbol)
  steel  = held under test, best of its column, verified (always with a word or symbol)
  paper / ink = neutral numbers and editorial emphasis (class .em)
  cividis scale = measured recall or rates in matrices (perceptually uniform, colour-blind safe)
"""

import json
import pathlib

HERE = pathlib.Path(__file__).parent
SLIDES: list[dict] = []

DARK = {
    "ink": "#ece6da",
    "soft": "#a9a498",
    "line": "#ffffff2e",
    "amber": "#eaa24f",
    "steel": "#93aab4",
    "bg": "#141516",
}
BONE = {
    "ink": "#151617",
    "soft": "#55534d",
    "line": "#15161738",
    "amber": "#94490a",
    "steel": "#35505b",
    "bg": "#e9e8e2",
}

MATRIX = json.loads((HERE / "art/recall_matrix.json").read_text())
TYPES = ["missing", "duplicate", "univariate", "multivariate", "drift", "invalid"]


def D(x, y, w=None, h=None, cls="", inner="", style=""):
    pos = f"left:{x}px;top:{y}px;"
    if w is not None:
        pos += f"width:{w}px;"
    if h is not None:
        pos += f"height:{h}px;"
    return f'<div class="{cls}" style="{pos}{style}">{inner}</div>'


def slide(
    sec,
    body,
    tone="dark",
    role="",
    family="",
    dominant="",
    density="",
    image="none",
    light="none",
    colour="neutral",
):
    SLIDES.append(
        {
            "sec": sec,
            "tone": tone,
            "body": body,
            "role": role,
            "family": family,
            "dominant": dominant,
            "density": density,
            "image": image,
            "light": light,
            "colour": colour,
        }
    )


def svg(x, y, w, h, inner, label=""):
    return f"<svg style='position:absolute;left:{x}px;top:{y}px' width='{w}' height='{h}' viewBox='0 0 {w} {h}' role='img' aria-label='{label}'>{inner}</svg>"


def txt(
    x,
    y,
    s,
    size=15,
    fill="#fff",
    anchor="start",
    weight=400,
    family="Avenir Next, Helvetica, sans-serif",
    extra="",
):
    return f"<text x='{x}' y='{y}' fill='{fill}' font-size='{size}' text-anchor='{anchor}' font-weight='{weight}' font-family='{family}' {extra}>{s}</text>"


def mono(x, y, s, size=14, fill="#fff", anchor="start", weight=500):
    return txt(x, y, s, size, fill, anchor, weight, "SF Mono, Menlo, monospace")


def cividis(v):
    stops = [
        (0, (0, 32, 77)),
        (0.25, (49, 68, 107)),
        (0.5, (124, 123, 120)),
        (0.75, (188, 175, 111)),
        (1, (255, 233, 69)),
    ]
    v = max(0.0, min(1.0, v))
    for (a, ca), (b, cb) in zip(stops, stops[1:], strict=False):
        if v <= b:
            t = (v - a) / (b - a)
            r, g, bl = (round(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))
            return f"#{r:02x}{g:02x}{bl:02x}"
    return "#ffe945"


def tbl(head, rows, best=(), anom=(), text_cols=(), compact=0):
    fs = {0: "", 1: ' style="font-size:16px"', 2: ' style="font-size:15px"'}[compact]
    pad = {0: "", 1: ' style="padding:4px 12px"', 2: ' style="padding:1px 12px"'}[compact]
    h = "".join(f'<th class="{"t" if i in text_cols else ""}">{c}</th>' for i, c in enumerate(head))
    out = [f"<table{fs}><tr>{h}</tr>"]
    for r, row in enumerate(rows):
        if isinstance(row, str):
            out.append(f'<tr class="grp"><td colspan="{len(head)}">{row}</td></tr>')
            continue
        cells = []
        for c, v in enumerate(row):
            k = "cool" if (r, c) in best else ("hot" if (r, c) in anom else "")
            if c in text_cols:
                k += " t"
            mark = "&#9679; " if (r, c) in best else ""
            cells.append(f'<td class="{k.strip()}"{pad}>{mark}{v}</td>')
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</table>")
    return "".join(out)


def photo(x, y, w, h, pos="50% 50%", size="cover", img="cover-plate", dim=0):
    shade = f"linear-gradient(rgba(10,10,10,{dim}),rgba(10,10,10,{dim})),"
    return D(
        x,
        y,
        w,
        h,
        "ph",
        "",
        f"background-image:{shade if dim else ''}url(art/assets/web/{img}.jpg);background-position:{pos};background-size:{size}",
    )


def padfield(cols, rows, kinds=None, w=1280, h=720, seed=3, mark=None):
    """A lit plate of pads. Light from the lower left; shadows fall right, length set by pad height.
    kinds: {(c, r): 'raised'|'missing'|'crack'|'double'|'slope'|'shift'|'lit'}; mark: set of (c, r) lit amber."""
    kinds = kinds or {}
    mark = mark or set()
    cw, ch = w / cols, h / rows
    pw, ph = cw * 0.66, ch * 0.62
    out = [
        f"<defs><filter id='soft{seed}'><feGaussianBlur stdDeviation='1.4'/></filter>"
        f"<linearGradient id='fall{seed}' x1='0' y1='1' x2='1' y2='0'><stop offset='0' stop-color='#f0b872' stop-opacity='.32'/>"
        f"<stop offset='.55' stop-color='#f0b872' stop-opacity='0'/><stop offset='1' stop-color='#000' stop-opacity='.3'/></linearGradient></defs>",
        f"<rect width='{w}' height='{h}' fill='#25272a'/>",
    ]
    for r in range(rows):
        for c in range(cols):
            x, y = c * cw + cw * 0.17, r * ch + ch * 0.2
            k = kinds.get((c, r))
            if k == "missing":
                out.append(
                    f"<rect x='{x}' y='{y}' width='{pw}' height='{ph}' fill='#0a0a0b'/><rect x='{x}' y='{y}' width='{pw * 0.14}' height='{ph}' fill='#000'/>"
                    f"<rect x='{x + pw}' y='{y}' width='2' height='{ph}' fill='#f0b872' opacity='.55'/>"
                )
                continue
            ht = {"raised": 5.2, "double": 1.0, "slope": 1.0}.get(k, 1.0)
            sx, sy = pw * 0.2 * ht, -ph * 0.03 * ht
            if k == "shift":
                x += pw * 0.28
            out.append(
                f"<polygon points='{x},{y + ph} {x + pw},{y + ph} {x + pw + sx},{y + ph + sy} {x + sx},{y + ph + sy}' fill='#000' opacity='.5' filter='url(#soft{seed})'/>"
            )
            out.append(
                f"<polygon points='{x + pw},{y} {x + pw + sx},{y + sy} {x + pw + sx},{y + ph + sy} {x + pw},{y + ph}' fill='#000' opacity='.55' filter='url(#soft{seed})'/>"
            )
            lift = ph * 0.1 * (ht - 1)
            face = "#6a6150" if k == "raised" else "#3b3d42"
            out.append(f"<rect x='{x}' y='{y - lift}' width='{pw}' height='{ph}' fill='{face}'/>")
            if k == "slope":
                out.append(
                    f"<polygon points='{x},{y + ph} {x + pw},{y + ph} {x + pw},{y + ph * 0.25}' fill='#3b3d41'/>"
                )
            if k == "crack":
                out.append(
                    f"<path d='M{x + pw * 0.1} {y + ph * 0.1} L{x + pw * 0.9} {y + ph * 0.9}' stroke='#f0b872' stroke-width='1.4' opacity='.9'/>"
                )
            if k == "double":
                out.append(
                    f"<rect x='{x + pw * 0.12}' y='{y + ph * 0.14}' width='{pw * 0.76}' height='{ph * 0.76}' fill='none' stroke='#f0b872' stroke-width='1.4' opacity='.85'/>"
                )
            lit = "#f0b872"
            op = 0.95 if (k == "raised" or (c, r) in mark) else 0.6
            out.append(
                f"<rect x='{x}' y='{y - lift}' width='2' height='{ph}' fill='{lit}' opacity='{op}'/><rect x='{x}' y='{y - lift}' width='{pw}' height='1.6' fill='{lit}' opacity='{op * 0.6}'/>"
            )
    out.append(f"<rect width='{w}' height='{h}' fill='url(#fall{seed})'/>")
    return svg(0, 0, w, h, "".join(out), "illustration: a plate of regular pads under low light")


def glyph(kind, x, y, s=120):
    """3x3 plate with one defective pad, lit from the lower left."""
    return svg(x, y, s, s, _glyph_inner(kind, s, s / 3), kind)


def _glyph_inner(kind, s, cell):
    pw, ph = cell * 0.66, cell * 0.62
    o = []
    for r in range(3):
        for c in range(3):
            x, y = c * cell + cell * 0.17, r * cell + cell * 0.2
            k = kind if (c, r) == (1, 1) else None
            if k == "missing":
                o.append(
                    f"<rect x='{x}' y='{y}' width='{pw}' height='{ph}' fill='#050506'/><rect x='{x}' y='{y}' width='{pw * 0.18}' height='{ph}' fill='#000'/>"
                )
                continue
            if k == "shift":
                x += pw * 0.3
            ht = 4.5 if k == "raised" else 1
            o.append(
                f"<rect x='{x + pw * 0.2 * ht}' y='{y + ph * 0.08}' width='{pw}' height='{ph}' fill='#000' opacity='.55'/>"
            )
            lift = ph * 0.12 * (ht - 1)
            o.append(
                f"<rect x='{x}' y='{y - lift}' width='{pw}' height='{ph}' fill='{'#4a453b' if k == 'raised' else '#2c2e31'}'/>"
            )
            if k == "crack":
                o.append(
                    f"<path d='M{x + 2} {y + 2} L{x + pw - 2} {y + ph - 2}' stroke='#f0b872' stroke-width='2'/>"
                )
            if k == "duplicate":
                o.append(
                    f"<rect x='{x + pw * 0.14}' y='{y + ph * 0.16}' width='{pw * 0.72}' height='{ph * 0.7}' fill='none' stroke='#f0b872' stroke-width='2'/>"
                )
            if k == "slope":
                o.append(
                    f"<polygon points='{x},{y + ph} {x + pw},{y + ph} {x + pw},{y + ph * 0.2}' fill='#3d3f44'/>"
                )
            o.append(
                f"<rect x='{x}' y='{y - lift}' width='2' height='{ph}' fill='#f0b872' opacity='{0.95 if k else 0.5}'/><rect x='{x}' y='{y - lift}' width='{pw}' height='1.6' fill='#f0b872' opacity='{0.6 if k else 0.3}'/>"
            )
    return "".join(o)


def matrix(
    x,
    y,
    rows,
    cols,
    data,
    cell_w,
    cell_h,
    tone,
    best=None,
    font=14,
    label_w=120,
    header=True,
    legend=True,
):
    """Native heat matrix on the cividis scale; values printed in every cell; best-of-column marked with a dot."""
    t = DARK if tone == "dark" else BONE
    o = []
    for j, c in enumerate(cols):
        o.append(txt(label_w + j * cell_w + cell_w / 2, 16, c, 14, t["soft"], "middle"))
    for i, r in enumerate(rows):
        yy = 26 + i * cell_h
        o.append(txt(label_w - 10, yy + cell_h / 2 + 5, r, 15, t["ink"], "end"))
        for j, c in enumerate(cols):
            v = data[i][j]
            if v is None:
                continue
            col = cividis(v)
            tc = "#0d0d0e" if v > 0.5 else "#f3efe6"
            o.append(
                f"<rect x='{label_w + j * cell_w + 1.5}' y='{yy + 1.5}' width='{cell_w - 3}' height='{cell_h - 3}' fill='{col}'><title>{r}, {c}: {v:.2f}</title></rect>"
            )
            o.append(
                mono(
                    label_w + j * cell_w + cell_w / 2,
                    yy + cell_h / 2 + 5,
                    f"{v:.2f}",
                    font,
                    tc,
                    "middle",
                    600,
                )
            )
            if best and (i, j) in best:
                o.append(
                    f"<circle cx='{label_w + j * cell_w + 10}' cy='{yy + 10}' r='4' fill='none' stroke='{tc}' stroke-width='1.6'/>"
                )
    w = label_w + len(cols) * cell_w + 4
    h = 30 + len(rows) * cell_h
    if legend:
        gy = h + 6
        for k in range(50):
            o.append(
                f"<rect x='{label_w + k * (len(cols) * cell_w) / 50}' y='{gy}' width='{(len(cols) * cell_w) / 50 + 0.5}' height='10' fill='{cividis(k / 49)}'/>"
            )
        o.append(txt(label_w, gy + 28, "0", 13, t["soft"]))
        o.append(txt(label_w + len(cols) * cell_w, gy + 28, "1 (recall)", 13, t["soft"], "end"))
        h += 40
    return svg(x, y, w, h, "".join(o), "heat matrix"), h


def hbars(
    x, y, w, rows, vmax, tone, label_w=170, row_h=38, ref=None, ref_label="", unit="", digits=3
):
    """Horizontal bars from 0. rows: (label, value, kind) with kind 'best', 'neutral' or 'anom'."""
    t = DARK if tone == "dark" else BONE
    bw = w - label_w - 90
    o = []
    for i, (lab, v, kind) in enumerate(rows):
        yy = i * row_h + 6
        col = {"best": t["steel"], "anom": t["amber"]}.get(kind, t["soft"])
        o.append(txt(label_w - 12, yy + 22, lab, 17, t["ink"], "end", 600))
        o.append(
            f"<rect x='{label_w}' y='{yy + 6}' width='{max(2, bw * v / vmax)}' height='20' fill='{col}'/>"
        )
        o.append(
            mono(
                label_w + bw * v / vmax + 8,
                yy + 22,
                f"{v:.{digits}f}{unit}" + (" &#9679;" if kind == "best" else ""),
                15,
                t["ink"],
            )
        )
    h = len(rows) * row_h + 14
    if ref is not None:
        rx = label_w + bw * ref / vmax
        o.append(
            f"<line x1='{rx}' x2='{rx}' y1='0' y2='{h - 6}' stroke='{t['ink']}' stroke-dasharray='4 4' opacity='.7'/>"
        )
        o.append(txt(rx + 6, h + 14, ref_label, 14, t["soft"]))
        h += 22
    return svg(x, y, w, h, "".join(o), "bar chart"), h


def pr_scatter(x, y, pts, tone, w=560, h=470):
    """Precision against recall with iso-F1 curves. pts: (label, precision, recall, kind)."""
    t = DARK if tone == "dark" else BONE
    px0, py0, pw, ph = 56, 10, w - 76, h - 56
    X = lambda r: px0 + pw * r  # noqa: E731
    Y = lambda p: py0 + ph * (1 - p)  # noqa: E731
    o = [f"<rect x='{px0}' y='{py0}' width='{pw}' height='{ph}' fill='none' stroke='{t['line']}'/>"]
    for f in (0.2, 0.4, 0.6, 0.8):
        path = []
        for k in range(1, 100):
            r = k / 100
            p = f * r / (2 * r - f) if 2 * r - f > 0 else None
            if p is not None and 0 <= p <= 1:
                path.append(f"{X(r):.1f},{Y(p):.1f}")
        if path:
            o.append(
                f"<polyline points='{' '.join(path)}' fill='none' stroke='{t['soft']}' stroke-dasharray='3 5' opacity='.6'/>"
            )
            o.append(
                txt(
                    float(path[-1].split(",")[0]) - 4,
                    float(path[-1].split(",")[1]) - 6,
                    f"F1 {f}",
                    12,
                    t["soft"],
                    "end",
                )
            )
    for g in (0, 0.25, 0.5, 0.75, 1):
        o.append(txt(px0 - 8, Y(g) + 5, f"{g:g}", 13, t["soft"], "end"))
        o.append(txt(X(g), py0 + ph + 20, f"{g:g}", 13, t["soft"], "middle"))
    o.append(txt(px0 + pw / 2, h - 4, "recall", 14, t["soft"], "middle"))
    o.append(
        txt(
            14,
            py0 + ph / 2,
            "precision",
            14,
            t["soft"],
            "middle",
            extra=f"transform='rotate(-90 14 {py0 + ph / 2})'",
        )
    )
    for pt in pts:
        lab, p, r, kind = pt[:4]
        off = pt[4] if len(pt) > 4 else None
        col = {"best": t["steel"], "anom": t["amber"]}.get(kind, t["ink"])
        o.append(
            f"<circle cx='{X(r)}' cy='{Y(p)}' r='6.5' fill='{col}'><title>{lab}: precision {p}, recall {r}</title></circle>"
        )
        dx, dy, anchor = off if off else ((10, 5, "start") if r < 0.62 else (-10, 5, "end"))
        o.append(txt(X(r) + dx, Y(p) + dy, lab, 14, t["ink"], anchor, 600))
    return svg(x, y, w, h, "".join(o), "precision recall scatter")


def interval_dots(
    x,
    y,
    w,
    rows,
    tone,
    vmin=0.08,
    vmax=0.34,
    row_h=27,
    label_w=170,
    hl=(),
    ticks=(0.1, 0.15, 0.2, 0.25, 0.3),
    fmt="{:.2f}",
):
    """Median with 95% interval. rows: (label, median, lo, hi)."""
    t = DARK if tone == "dark" else BONE
    bw = w - label_w - 30
    X = lambda v: label_w + bw * (v - vmin) / (vmax - vmin)  # noqa: E731
    o = []
    for g in ticks:
        o.append(
            f"<line x1='{X(g)}' x2='{X(g)}' y1='0' y2='{len(rows) * row_h}' stroke='{t['line']}'/>"
        )
        o.append(txt(X(g), len(rows) * row_h + 20, fmt.format(g), 13, t["soft"], "middle"))
    for i, (lab, m, lo, hi) in enumerate(rows):
        yy = i * row_h + row_h / 2
        col = t["amber"] if lab in hl else t["ink"]
        o.append(txt(label_w - 10, yy + 5, lab, 15, col, "end", 600 if lab in hl else 500))
        o.append(
            f"<line x1='{X(lo)}' x2='{X(hi)}' y1='{yy}' y2='{yy}' stroke='{col}' stroke-width='2' opacity='.8'/>"
        )
        o.append(
            f"<circle cx='{X(m)}' cy='{yy}' r='5' fill='{col}'><title>{lab}: {m} [{lo}, {hi}]</title></circle>"
        )
    o.append(
        txt(
            label_w + bw / 2,
            len(rows) * row_h + 40,
            "value, with 95% interval",
            13,
            t["soft"],
            "middle",
        )
    )
    return svg(x, y, w, len(rows) * row_h + 46, "".join(o), "median with 95 percent intervals")


def foot(src):
    return D(64, 678, 1152, None, "src", src)
