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


def flow(x, y, w, blocks, maxh=None, gap=18, style=""):
    """Vertical stack positioned once; blocks keep their natural height. maxh shrinks the stack with
    CSS zoom when fonts are wider than expected (the stack, not each block, is fitted)."""
    mh = f" data-maxh='{maxh}'" if maxh else ""
    return f"<div class='flow'{mh} style='left:{x}px;top:{y}px;width:{w}px;gap:{gap}px;{style}'>{''.join(blocks)}</div>"


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


def _lum(hexcol):
    rgb = [int(hexcol[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    """WCAG contrast ratio between two #rrggbb colours."""
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def text_on(fill, light="#ffffff", dark="#000000"):
    """Whichever of two text colours reads better on `fill`."""
    return light if contrast(fill, light) >= contrast(fill, dark) else dark


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


def padfield(cols, rows, kinds=None, w=1280, h=720, seed=3, mark=None, dim_unmarked=False):
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
            op = 0.95 if (k == "raised" or (c, r) in mark) else (0.12 if dim_unmarked else 0.6)
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
    unit="recall",
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
            tc = text_on(col)
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
        o.append(txt(label_w + len(cols) * cell_w, gy + 28, f"1 ({unit})", 14, t["soft"], "end"))
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
                    13,
                    t["soft"],
                    "end",
                    extra=f"style='paint-order:stroke;stroke:{t['bg']};stroke-width:5px;stroke-linejoin:round'",
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
        if abs(dx) > 14 or abs(dy) > 14:
            o.append(
                f"<line x1='{X(r)}' y1='{Y(p)}' x2='{X(r) + dx + (-4 if anchor == 'end' else 4)}' y2='{Y(p) + dy - 5}' stroke='{t['soft']}' stroke-width='1'/>"
            )
        o.append(
            txt(
                X(r) + dx,
                Y(p) + dy,
                lab,
                14,
                t["ink"],
                anchor,
                600,
                extra=f"stroke='{t['bg']}' stroke-width='4' paint-order='stroke'",
            )
        )
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
    axis_label="value, with 95% interval",
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
            axis_label,
            14,
            t["soft"],
            "middle",
        )
    )
    return svg(x, y, w, len(rows) * row_h + 46, "".join(o), "median with 95 percent intervals")


def foot(src):
    return D(64, 678, 1152, None, "src", src)


INK, SOFT, AMB = "#ece6da", "#8d897f", "#eaa24f"


def _cell(
    x, y, w, h, s, fill="none", stroke="#ffffff30", color=INK, size=15, dash="", anchor="middle"
):
    tx = x + w / 2 if anchor == "middle" else x + 8
    return (
        f"<rect x='{x}' y='{y}' width='{w}' height='{h}' fill='{fill}' stroke='{stroke}' stroke-dasharray='{dash}'/>"
        + (mono(tx, y + h / 2 + 5, s, size, color, anchor, 500) if s else "")
    )


def type_icon(kind, x, y, w=360, h=170):
    """Small data diagram for one anomaly type. Each uses a different form: a table with an empty cell,
    two identical rows, a number line, a 2-D scatter, distributions over time, a form with rule violations.
    The defect is marked by amber plus a word, never by colour alone."""
    o = [
        f"<rect x='0.5' y='0.5' width='{w - 1}' height='{h - 1}' fill='#1b1d1f' stroke='#ffffff1f'/>"
    ]
    if kind == "missing":
        cols = ["id", "income", "balance"]
        rows = [("101", "48,900", "2,140"), ("102", "52,300", None), ("103", "61,400", "3,310")]
        cw = 104
        for j, c in enumerate(cols):
            o.append(txt(24 + j * cw + cw / 2, 28, c, 14, SOFT, "middle"))
        for i, r in enumerate(rows):
            for j, v in enumerate(r):
                yy = 40 + i * 36
                if v is None:
                    o.append(
                        _cell(24 + j * cw, yy, cw - 6, 30, "null", "#eaa24f22", AMB, AMB, 15, "4 3")
                    )
                else:
                    o.append(_cell(24 + j * cw, yy, cw - 6, 30, v))
        o.append(txt(24, 160, "a cell with no value", 14, AMB, "start", 600))
    elif kind == "duplicate":
        rows = [
            ("105", "38,700", "960", False),
            ("104", "52,300", "1,820", False),
            ("104", "52,300", "1,820", True),
        ]
        cw = 96
        for i, r in enumerate(rows):
            yy = 20 + i * 38
            for j, v in enumerate(r[:3]):
                o.append(
                    _cell(
                        24 + j * cw,
                        yy,
                        cw - 6,
                        30,
                        v,
                        "#eaa24f1a" if r[3] else "none",
                        AMB if r[3] else "#ffffff30",
                        AMB if r[3] else INK,
                    )
                )
        o.append(
            f"<path d='M{24 + 3 * cw + 6} {58} L{24 + 3 * cw + 18} {58} L{24 + 3 * cw + 18} {96} L{24 + 3 * cw + 6} {96}' fill='none' stroke='{AMB}' stroke-width='2'/>"
        )
        o.append(txt(24 + 3 * cw + 26, 82, "=", 26, AMB, "start", 700))
        o.append(txt(24, 154, "the same record again, id included", 14, AMB, "start", 600))
    elif kind == "univariate":
        o.append(f"<line x1='24' x2='{w - 24}' y1='96' y2='96' stroke='{INK}' stroke-width='1.5'/>")
        for k, xx in enumerate(
            [84, 98, 110, 118, 126, 134, 146, 154, 166, 176, 188, 130, 120, 140, 158]
        ):
            o.append(
                f"<circle cx='{xx + 10}' cy='{96 - 8 - (k % 4) * 8}' r='4.5' fill='{INK}' opacity='.85'/>"
            )
        o.append(
            f"<path d='M84 108 L84 114 L206 114 L206 108' fill='none' stroke='{SOFT}'/>"
            + txt(145, 132, "expected range", 14, SOFT, "middle")
        )
        o.append(
            f"<circle cx='{w - 40}' cy='88' r='7' fill='{AMB}'/><circle cx='{w - 40}' cy='88' r='13' fill='none' stroke='{AMB}' stroke-width='2'/>"
        )
        o.append(
            txt(w - 40, 62, "outlier", 14, AMB, "middle", 700)
            + txt(24, 28, "income, one column", 14, SOFT, "start")
        )
        o.append(txt(w - 24, 154, "value x 15 to 45", 14, AMB, "end", 600))
    elif kind == "multivariate":
        o.append(
            f"<line x1='48' x2='48' y1='18' y2='138' stroke='{INK}'/><line x1='48' x2='{w - 24}' y1='138' y2='138' stroke='{INK}'/>"
        )
        pts = [
            (80, 120),
            (100, 108),
            (118, 100),
            (136, 88),
            (152, 82),
            (170, 70),
            (188, 62),
            (206, 54),
            (124, 112),
            (160, 94),
            (182, 76),
            (214, 66),
            (96, 122),
            (144, 98),
        ]
        o += [f"<circle cx='{px}' cy='{py}' r='4.5' fill='{INK}' opacity='.85'/>" for px, py in pts]
        o.append(
            f"<rect x='48' y='46' width='4' height='88' fill='{SOFT}' opacity='.6'/><rect x='70' y='134' width='156' height='4' fill='{SOFT}' opacity='.6'/>"
        )
        ax, ay = 92, 52
        o.append(
            f"<line x1='{ax}' x2='{ax}' y1='{ay}' y2='134' stroke='{AMB}' stroke-dasharray='3 3'/><line x1='52' x2='{ax}' y1='{ay}' y2='{ay}' stroke='{AMB}' stroke-dasharray='3 3'/>"
        )
        o.append(
            f"<circle cx='{ax}' cy='{ay}' r='7' fill='{AMB}'/><circle cx='{ax}' cy='{ay}' r='13' fill='none' stroke='{AMB}' stroke-width='2'/>"
        )
        o.append(
            txt(ax + 20, ay + 4, "unusual pair", 14, AMB, "start", 700)
            + txt(w - 24, 156, "age", 14, SOFT, "end")
            + txt(60, 22, "balance", 14, SOFT, "start")
        )
        o.append(
            txt(w - 14, 112, "each value is in range,", 14, SOFT, "end")
            + txt(w - 14, 130, "the pair is not", 14, SOFT, "end")
        )
    elif kind == "drift":
        o.append(
            f"<line x1='24' x2='{w - 24}' y1='132' y2='132' stroke='{INK}'/>"
            + txt(w - 24, 154, "time", 14, SOFT, "end")
            + txt(24, 154, "earlier", 14, SOFT, "start")
        )
        for k, (cx, op) in enumerate([(90, 0.35), (170, 0.6), (250, 1)]):
            pts = " ".join(
                f"{cx - 56 + i * 4:.0f},{132 - 70 * 2.718 ** (-((i * 4 - 56) ** 2) / (2 * 20**2)):.1f}"
                for i in range(29)
            )
            o.append(
                f"<polyline points='{pts}' fill='none' stroke='{AMB if k == 2 else INK}' stroke-width='2.2' opacity='{op}'/>"
            )
        o.append(f"<line x1='90' x2='90' y1='30' y2='132' stroke='{SOFT}' stroke-dasharray='3 4'/>")
        o.append(
            f"<path d='M96 52 L246 52' stroke='{AMB}' stroke-width='2'/><path d='M246 52 l-9 -5 l0 10 z' fill='{AMB}'/>"
        )
        o.append(
            txt(w / 2, 30, "the whole distribution moves", 14, AMB, "middle", 700)
            + txt(24, 20, "income", 14, SOFT, "start")
        )
    else:
        rows = [
            ("email", "marie.dupont@", "no domain"),
            ("age", "217", "impossible"),
            ("country", "ZZ", "not a country"),
        ]
        for i, (f, v, why) in enumerate(rows):
            yy = 22 + i * 46
            o.append(txt(24, yy + 22, f, 14, SOFT, "start"))
            o.append(_cell(88, yy, 132, 32, v, "#eaa24f1a", AMB, AMB, 15))
            o.append(txt(230, yy + 22, "&#10007; " + why, 14, AMB, "start", 700))
    return svg(x, y, w, h, "".join(o), f"diagram of {kind}")


# ---- native line panels (precision-recall curves and severity sweeps) -------------------------------------

PR_DATA = json.loads((HERE / "art/data/pr_curves.json").read_text())
SEVERITY_CSV = HERE.parent / "verification/evidence/severity.csv"

LINE_STYLES = {
    "A": ("ink", "", 2.8),
    "B": ("soft", "7 4", 2.6),
    "E": ("ink", "12 3 2 3", 2.6),
    "C": ("ink", "2 4", 2.6),
    "D": ("amber", "", 2.8),
}
SHORT = {
    "isolation_forest": "Isolation Forest",
    "great_expectations": "Great Expectations",
    "ocsvm": "One-Class SVM",
    "zscore": "Z-score",
    "iqr": "IQR",
    "lof": "LOF",
    "ecod": "ECOD",
    "copod": "COPOD",
    "hbos": "HBOS",
    "knn": "KNN",
    "pca": "PCA",
    "drift": "Drift detector",
}


def _line_style(tone, key):
    t = DARK if tone == "dark" else BONE
    col, dash, width = LINE_STYLES[key]
    colour = {
        "ink": t["ink"],
        "steel": "#4f7a8c" if tone == "bone" else t["steel"],
        "amber": t["amber"],
        "soft": "#6b685f" if tone == "bone" else "#c9c4b8",
    }[col]
    return colour, dash, width


def line_panel(
    x,
    y,
    w,
    h,
    title,
    series,
    tone,
    xticks,
    xlim,
    xlabel="",
    ylabel="",
    base=None,
    labels=True,
    right_pad=8,
    vline=None,
    sub=None,
    key_rows=None,
):
    """One panel. series: list of (label, [(x, y), ...], style) where style is 'grey' or a LINE_STYLES key.

    Grey series are drawn first and thin. Styled series are labelled at their right end (labels are spread
    so they cannot collide) when labels=True; otherwise the caller supplies a key.
    """
    t = DARK if tone == "dark" else BONE
    key_need = sum(30 + 7.6 * len(lab) + 14 for lab, _ in sub) if sub else 0
    if key_rows is None:
        key_rows = 2 if sub and key_need > w - 46 else 1
    px0, py0 = 46, 34 + (18 * key_rows if sub else 0)
    pw, ph = w - px0 - right_pad, h - py0 - 40
    x0, x1 = xlim
    X = lambda v: px0 + pw * (v - x0) / (x1 - x0)  # noqa: E731
    Y = lambda v: py0 + ph * (1 - v)  # noqa: E731
    o = [txt(px0, 18, title, 17, t["ink"], "start", 600)]
    if sub:
        cx, ky = px0, 36
        for lab, style in sub:
            colour, dash, width = _line_style(tone, style)
            da = f" stroke-dasharray='{dash}'" if dash else ""
            o.append(
                f"<line x1='{cx}' x2='{cx + 24}' y1='{ky}' y2='{ky}' stroke='{colour}' stroke-width='{width}'{da}/>"
            )
            o.append(txt(cx + 30, ky + 5, lab, 14, t["ink"], "start", 500))
            if key_rows > 1:
                ky += 19
            else:
                cx += 30 + 7.6 * len(lab) + 14
    o.append(
        f"<rect x='{px0}' y='{py0}' width='{pw}' height='{ph}' fill='none' stroke='{t['line']}'/>"
    )
    for g in (0, 0.25, 0.5, 0.75, 1):
        o.append(txt(px0 - 7, Y(g) + 5, f"{g:g}", 13, t["soft"], "end"))
        if 0 < g < 1:
            o.append(
                f"<line x1='{px0}' x2='{px0 + pw}' y1='{Y(g)}' y2='{Y(g)}' stroke='{t['line']}' stroke-dasharray='1 5'/>"
            )
    for g in xticks:
        o.append(txt(X(g), py0 + ph + 19, f"{g:g}", 13, t["soft"], "middle"))
    if xlabel:
        o.append(txt(px0 + pw / 2, h - 4, xlabel, 14, t["soft"], "middle"))
    if ylabel:
        o.append(
            txt(
                14,
                py0 + ph / 2,
                ylabel,
                14,
                t["soft"],
                "middle",
                extra=f"transform='rotate(-90 14 {py0 + ph / 2})'",
            )
        )
    if vline is not None:
        o.append(
            f"<line x1='{X(vline)}' x2='{X(vline)}' y1='{py0}' y2='{py0 + ph}' stroke='{t['soft']}' stroke-dasharray='4 4' opacity='.7'/>"
        )
    if base is not None:
        o.append(
            f"<line x1='{px0}' x2='{px0 + pw}' y1='{Y(base)}' y2='{Y(base)}' stroke='{t['soft']}' stroke-dasharray='5 4'/>"
        )
    ordered = [s for s in series if s[2] == "grey"] + [s for s in series if s[2] != "grey"]
    ends = []
    for lab, pts, style in ordered:
        path = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in pts)
        if style == "grey":
            o.append(
                f"<polyline points='{path}' fill='none' stroke='{t['soft']}' stroke-width='1.2' opacity='.5' stroke-linejoin='round'><title>{lab}</title></polyline>"
            )
            continue
        colour, dash, width = _line_style(tone, style)
        da = f" stroke-dasharray='{dash}'" if dash else ""
        o.append(
            f"<polyline points='{path}' fill='none' stroke='{colour}' stroke-width='{width}'{da} stroke-linejoin='round'><title>{lab}</title></polyline>"
        )
        if len(pts) <= 8:
            for a, b in pts:
                o.append(f"<circle cx='{X(a):.1f}' cy='{Y(b):.1f}' r='3.4' fill='{colour}'/>")
        ends.append((Y(pts[-1][1]), lab, colour))
    if labels:
        ends.sort()
        placed = []
        for yy, lab, colour in ends:
            if placed and yy < placed[-1] + 16:
                yy = placed[-1] + 16
            placed.append(yy)
            o.append(txt(px0 + pw + 8, yy + 5, lab, 14, colour, "start", 600))
    return f"<g transform='translate({x},{y})'>{''.join(o)}</g>"


def pr_panels(x, y, tone, w=700, h=520):
    """2x2 native precision-recall panels from slides/art/data/pr_curves.json (see export_pr_curves.py).

    Per panel: the highest-AP method in dark solid, the lowest-AP method in blue dashed, the rest in grey.
    The choice is by AP, not by hand, so no method is picked to suit the argument.
    """
    names = [
        ("credit_card", "Credit Card Fraud"),
        ("water_quality", "Water Quality"),
        ("cardio", "Cardio"),
        ("synthetic", "Synthetic"),
    ]
    pw, ph = w // 2, h // 2
    parts = []
    for k, (key, label) in enumerate(names):
        d = PR_DATA["datasets"][key]
        ms = d["methods"]
        best = max(ms, key=lambda m: ms[m]["ap"])
        worst = min(ms, key=lambda m: ms[m]["ap"])
        series = []
        for m, v in ms.items():
            lab = f"{SHORT.get(m, m)}, AP {v['ap']:.2f}"
            style = "A" if m == best else "B" if m == worst else "grey"
            series.append((lab, v["points"], style))
        br = d["base_rate"]
        base_txt = f"{br * 100:.2f}%" if br < 0.01 else f"{br:.2f}"
        parts.append(
            line_panel(
                (k % 2) * pw,
                (k // 2) * ph,
                pw,
                ph,
                f"{label} (base rate {base_txt})",
                series,
                tone,
                (0, 0.5, 1),
                (0, 1),
                xlabel="recall" if k >= 2 else "",
                ylabel="precision" if k % 2 == 0 else "",
                base=br,
                labels=False,
                key_rows=2,
                sub=[
                    (f"{SHORT.get(best, best)} {ms[best]['ap']:.2f}", "A"),
                    (f"{SHORT.get(worst, worst)} {ms[worst]['ap']:.2f}", "B"),
                ],
            )
        )
    return svg(x, y, w, h, "".join(parts), "precision-recall curves by dataset"), names


def pr_best_worst():
    out = {}
    for key, d in PR_DATA["datasets"].items():
        ms = d["methods"]
        best = max(ms, key=lambda m: ms[m]["ap"])
        worst = min(ms, key=lambda m: ms[m]["ap"])
        out[key] = (best, ms[best]["ap"], worst, ms[worst]["ap"])
    return out


def severity_panels(x, y, w, h, tone, picks):
    """Three native severity panels from verification/evidence/severity.csv.

    picks: {anomaly_type: [(method, style), ...]}; every other method is drawn grey.
    """
    import csv

    rows = list(csv.DictReader(SEVERITY_CSV.open()))
    data: dict = {}
    for r in rows:
        data.setdefault(r["anomaly_type"], {}).setdefault(r["method"], []).append(
            (float(r["severity"]), float(r["recall"]))
        )
    for tdict in data.values():
        for m in tdict:
            tdict[m].sort()
    parts = []
    pw = w // 3
    for k, (atype, label) in enumerate(
        [
            ("univariate_outlier", "Univariate outlier"),
            ("multivariate_outlier", "Multivariate outlier"),
            ("temporal_drift", "Temporal drift"),
        ]
    ):
        chosen = dict(picks.get(atype, []))
        series = []
        for m, pts in data[atype].items():
            if m == "transform_dedup":
                continue
            series.append((SHORT.get(m, m), pts, chosen.get(m, "grey")))
        parts.append(
            line_panel(
                k * pw,
                0,
                pw,
                h,
                label,
                series,
                tone,
                (0.5, 1, 2, 3, 5),
                (0.4, 5.1),
                xlabel="injection severity (1 = reference)",
                ylabel="recall" if k == 0 else "",
                labels=True,
                right_pad=150 if k < 2 else 150,
                vline=1,
            )
        )
    return svg(x, y, w, h, "".join(parts), "recall against injection severity")
