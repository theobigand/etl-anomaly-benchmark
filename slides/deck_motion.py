"""Which motion family and which light each slide uses.

The deck is about what a low light reveals on a regular surface, so motion follows the content
of the slide and the light has a position. A slide gets one motion family from its role and
composition, and a light position: the shadows of every surface on the slide fall away from it.
Two consecutive slides never share both, so the sequence does not repeat itself. The assignment
is data: change a rule or an override here, not the CSS.

Families (see deck_motion.css):
  title      cinematic title and section reveal: the light arrives and sweeps across the headline
  rake       directional raking light across a surface (tables, matrices), shadows grow behind it
  flow       layered diagram and workflow: paths drawn in reading order, nodes lit in turn
  chart      data marks built from their baseline: bars grow, lines draw, dots appear in order
  compare    two quantities introduced one after the other, never tweened between values
  editorial  minimal line-by-line reveal for dense informational slides
  close      the closing treatment: the light slowly recedes
"""

from __future__ import annotations

# light name: (x, y) of the source in percent of the slide, shadow offset (dx, dy) in px, beam angle
LIGHTS = {
    "lower-left": (6, 104, 18, -7, 62),
    "raking-left": (-6, 46, 24, 2, 90),
    "upper-left": (8, -8, 14, 14, 135),
    "upper-right": (94, -8, -14, 13, 225),
    "lower-right": (104, 104, -18, -6, 298),
}
DARK_LIGHTS = ("lower-left", "raking-left", "upper-left", "lower-right")
BONE_LIGHTS = ("upper-left", "upper-right", "raking-left", "lower-left")

# first match wins; a family string is the `family` of the slide() call
RULES = [
    (("photograph", "image-led", "coded plate"), "title"),
    (("typographic statement", "typographic columns"), "title"),
    (("typographic contrast", "typographic pair", "table + two figures"), "compare"),
    (("threshold ladder", "segmented bar"), "chart"),
    (
        (
            "code + behaviour",
            "six distinct",
            "process diagram",
            "diagram-led",
            "flow diagram",
            "routing",
            "lanes",
            "log-axis",
        ),
        "flow",
    ),
    (("matrix", "matrices", "pictogram"), "rake"),
    (
        (
            "bar",
            "scatter",
            "slope",
            "interval",
            "strip",
            "curves",
            "multiples",
            "log bar",
            "column chart",
            "dumbbell",
        ),
        "chart",
    ),
    (("table", "equation", "formula", "example table"), "rake"),
    (
        (
            "ledger",
            "index",
            "specimen",
            "two lists",
            "evidence grid",
            "comparison",
            "four-column",
            "two-column",
            "numerals",
        ),
        "editorial",
    ),
]

# {1-based slide number: (family, light)} for the few slides the rules cannot place
OVERRIDES: dict[int, tuple[str, str]] = {}


def _family(slide: dict) -> str:
    text = f"{slide['family']} {slide['dominant']}".lower()
    for needles, motion in RULES:
        if any(needle in text for needle in needles):
            return motion
    return "editorial"


def assign(slides: list[dict]) -> None:
    """Set ``motion``, ``lightpos`` and ``variant`` on every slide, in order."""
    previous: tuple[str, str] | None = None
    cycle = {"dark": 0, "bone": 0}
    for number, slide in enumerate(slides, 1):
        motion = "close" if slide["role"] == "close" else _family(slide)
        choices = DARK_LIGHTS if slide["tone"] == "dark" else BONE_LIGHTS
        light = choices[cycle[slide["tone"]] % len(choices)]
        cycle[slide["tone"]] += 1
        if number in OVERRIDES:
            motion, light = OVERRIDES[number]
        if previous == (motion, light):
            light = next(name for name in choices if name != light)
        slide["motion"], slide["lightpos"] = motion, light
        slide["variant"] = number % 3
        previous = (motion, light)
