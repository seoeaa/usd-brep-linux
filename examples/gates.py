"""Откатные ворота 5500 мм по чертежу zabortver.ru (лист 2026-09-15).

Размеры из «СПЕЦИФИКАЦИЯ МАТЕРИАЛОВ (ДЕТАЛИРОВКА)»:
    5500 проём / 1800 высота проёма / 1530 высота створки
    8115 полная длина / 5640 полотно / 2475 непроезжая часть
    33° раскосы и наклонная / шаг стоек 927
Профили: стойки и обвязка 60x40, направляющая 80x40, диагонали 40x20.
"""

import math
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("SOLIDMODELING_REPO",
                      os.path.abspath(os.path.join(_SCRIPT_DIR, "..")))
sys.path.insert(0, os.path.join(REPO, "tools", "scripts"))

import view_usd  # noqa: E402

view_usd._ensure_usd_runtime_env()

_BUILD_BIN = os.path.join(REPO, "_build", view_usd._pick_platform(),
                          view_usd._pick_config(REPO))
if os.path.isdir(_BUILD_BIN) and _BUILD_BIN not in sys.path:
    sys.path.insert(0, _BUILD_BIN)

import _omni_solid as sm  # noqa: E402

OUT_DIR = os.path.join(REPO, "_myvals", "out")

S, HP, HV = 5500.0, 1800.0, 1530.0
L, L1, XN = 8115.0, 5640.0, 2475.0
ANG = 33.0
FRAME, FRAME_T = 60.0, 40.0
GUIDE, GUIDE_T = 80.0, 40.0
DIAG, DIAG_T = 40.0, 20.0
STEP = 927.0

STEEL = (0.44, 0.48, 0.54)
RAIL_C = (0.62, 0.64, 0.68)
POST_C = (0.28, 0.30, 0.34)
DIAG_C = (0.55, 0.58, 0.63)


def bar(length, depth, thickness, x0, z0, angle_deg=0.0, y0=0.0):
    """Брус: length по X, depth по Z, thickness по Y, начало в (x0,z0)."""
    c = sm.create_rectangle((length / 2.0, depth / 2.0, 0.0), length, depth)
    body = sm.linear_sweep(c, (0.0, 1.0, 0.0), thickness)
    if abs(angle_deg) > 1e-9:
        body = sm.rotate(body, (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), angle_deg)
    return sm.translate(body, (x0, y0, z0))


def build():
    parts = []

    def add(name, brep, color):
        parts.append(dict(name=name, brep=brep, color=color))

    pw = pt = 60.0
    for i, x in enumerate((-pw, S)):
        add("Post%d" % (i + 1),
            sm.create_box((x, -pt / 2, -120.0), pw, pt, HP + 120.0), POST_C)

    rail_start = L1 - XN
    add("Rail", sm.create_box((rail_start, -GUIDE_T / 2, 0.0), L - rail_start,
                              GUIDE_T, GUIDE), RAIL_C)

    z_low = GUIDE
    add("BottomRail", bar(L1, FRAME, FRAME_T, 0.0, z_low, y0=-FRAME_T / 2), STEEL)
    z_top = z_low + HV - FRAME
    add("TopRail", bar(L1, FRAME, FRAME_T, 0.0, z_top, y0=-FRAME_T / 2), STEEL)

    xs, x = [], 0.0
    while x <= L1 - FRAME + 0.5:
        xs.append(x)
        x += STEP
    if abs(xs[-1] - (L1 - FRAME)) > 1.0:
        xs.append(L1 - FRAME)
    for i, px in enumerate(xs):
        add("Stud%02d" % (i + 1),
            sm.create_box((px, -FRAME_T / 2, z_low), FRAME, FRAME_T, HV), STEEL)
    print("      стоек: %d, панелей: %d" % (len(xs), len(xs) - 1))

    t33 = math.radians(ANG)
    n = 0
    for i in range(len(xs) - 1):
        xa = xs[i] + FRAME
        span = xs[i + 1] - xa
        if span < 2 * DIAG:
            continue
        ln = (span / 2.0) / math.cos(t33)
        n += 1
        add("Diag%02d" % n, bar(ln, DIAG, DIAG_T, xa, z_low, -ANG, y0=-DIAG_T / 2), DIAG_C)
        n += 1
        add("Diag%02d" % n, bar(ln, DIAG, DIAG_T, xs[i + 1], z_low, -(180.0 - ANG),
                                y0=-DIAG_T / 2), DIAG_C)

    t12 = math.radians(12.0)
    m = 0
    for i in range(len(xs) - 1):
        xa = xs[i] + FRAME
        span = xs[i + 1] - xa
        if span < 2 * DIAG:
            continue
        ln = (span / 2.0) / math.cos(t12)
        z0 = z_low + (HV - FRAME) * 0.55
        m += 1
        add("Flat%02d" % m, bar(ln, DIAG, DIAG_T, xa, z0, -12.0, y0=DIAG_T / 2), DIAG_C)
        m += 1
        add("Flat%02d" % m, bar(ln, DIAG, DIAG_T, xs[i + 1], z0, -(180.0 - 12.0),
                                y0=DIAG_T / 2), DIAG_C)

    tail_ln = (L - L1) / math.cos(t33)
    add("TailTop", bar(tail_ln, FRAME, FRAME_T, L1, z_top + FRAME, ANG,
                       y0=-FRAME_T / 2), STEEL)
    add("TailBottom", bar(tail_ln, FRAME, FRAME_T, L, z_low, -(180.0 - ANG),
                          y0=-FRAME_T / 2), STEEL)

    return parts


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("[1/3] строим части")
    parts = build()
    for p in parts:
        if p["name"].startswith(("Diag01", "Diag02", "Tail", "Rail", "Post")):
            bb = p["brep"].bounding_box()
            print("      %-11s x=[%7.1f..%7.1f] z=[%6.0f..%6.0f]"
                  % (p["name"], bb[0][0], bb[1][0], bb[0][2], bb[1][2]))

    print("[2/3] тесселяция")
    tv = ti = 0
    for p in parts:
        arr = sm.tessellate(p["brep"], chord_height_tolerance=0.5) \
            .to_mesh_arrays(face_varying_normals=True)
        p["mesh"] = arr
        tv += len(arr["points"])
        ti += len(arr["faces"])
    print("      %d объектов, %d вершин, %d индексов" % (len(parts), tv, ti))

    print("[3/3] экспорт USD")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ega", os.path.join(REPO, "tools", "scripts", "example_generate_asset.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = os.path.join(OUT_DIR, "Gates_5500.usda")
    mod.write_usda(parts, out, root_name="SlideGate")
    print("      ->", out)


if __name__ == "__main__":
    main()
