"""Часы-дайс: корпус со скруглёнными рёбрами, точный тор-безель и 60 меток.

Демонстрация конвейера usd-brep по плейбуку репозитория:
аналитические примитивы + булевы + скругления + тесселяция -> USD-меши.

Запуск из корня репозитория (`<repo>/_myvals/` лежит на два уровня ниже):
    uv run --locked --group gui python _myvals/clock_dice.py
"""

import math
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get(
    "SOLIDMODELING_REPO",
    os.path.abspath(os.path.join(_SCRIPT_DIR, "..")),
)
sys.path.insert(0, os.path.join(REPO, "tools", "scripts"))

import view_usd  # noqa: E402

view_usd._ensure_usd_runtime_env()

# Каталог сборки в sys.path — так делает и штатный шаблон.
_BUILD_BIN = os.path.join(REPO, "_build", view_usd._pick_platform(),
                          view_usd._pick_config(REPO))
if os.path.isdir(_BUILD_BIN) and _BUILD_BIN not in sys.path:
    sys.path.insert(0, _BUILD_BIN)

import _omni_solid as sm  # noqa: E402

OUT_DIR = os.path.join(REPO, "_myvals", "out")

# ── размеры, мм ────────────────────────────────────────────────────────────
SIDE = 40.0          # сторона кубика
BEVEL_R = 1.6        # фаска по всем рёбрам
BEZEL_OUT = 15.0     # внешний радиус циферблата
BEZEL_IN = 13.2      # внутренний радиус
RIM_Z = 1.2          # толщина бортика
FACE_Z = SIDE / 2.0  # верхняя грань кубика

MARK_Z = 0.9         # высота метки над гранью
MARK_W = 0.42        # полуширина минутного деления
HOUR_W = 0.95        # полуширина часового деления
TICK_LEN = (12.2, 4.2)   # (внешний, внутренний) радиус минутного деления
HOUR_LEN = (12.0, 5.0)   # то же для часового

HAND_Z = 1.1         # высота стрелки
HAND_T = 0.28        # полуширина стрелки


def beveled_cube():
    """Куб с фасками по всем рёбрам.

    Скругление (fillet_edges) ломает тело, если брать все 12 рёбер, а четыре
    вертикальных дают полосы на верхней грани при триангуляции ребра с
    отверстием. Фаска (chamfer_fillet) делает все рёбра сразу и остаётся
    манифолдной, поэтому берём её.
    """
    box = sm.create_box((-SIDE / 2, -SIDE / 2, -SIDE / 2), SIDE, SIDE, SIDE)
    out = sm.chamfer_fillet(box, radius=BEVEL_R)
    if not out.is_manifold_solid():
        raise RuntimeError("после фаски тело не манифолдно")
    return out


def bar(angle_deg, r_out, r_in, half_w, z0, height):
    """Прямоугольное деление из центра по направлению angle_deg."""
    length = r_out - r_in
    curves = sm.create_rectangle((0.0, 0.0, z0), length, half_w * 2.0)
    prism = sm.linear_sweep(curves, (0.0, 0.0, 1.0), height)
    prism = sm.translate(prism, (r_in, 0.0, 0.0))
    # поворот вокруг центра кубика: (0,0,1) — ось, угол в градусах
    return sm.rotate(prism, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), angle_deg)


def build():
    parts = []

    def add(name, brep, color):
        parts.append(dict(name=name, brep=brep, color=color))

    # 1. Корпус
    add("Corpus", beveled_cube(), (0.80, 0.82, 0.86))

    # 2. Безель — точный (не тесселированный) тор
    tube_r = (BEZEL_OUT - BEZEL_IN) / 2.0
    mid_r = (BEZEL_OUT + BEZEL_IN) / 2.0
    ring = sm.create_torus((0.0, 0.0, FACE_Z), mid_r, tube_r)
    ring = sm.translate(ring, (0.0, 0.0, RIM_Z / 2.0))
    add("Bezel", ring, (0.98, 0.80, 0.28))

    # 3. Метки. Угол 90° — «12 часов», дальше по часовой.
    hours, minutes = [], []
    for i in range(60):
        ang = 90.0 - i * 6.0
        if i % 5 == 0:
            hours.append(bar(ang, HOUR_LEN[0], HOUR_LEN[1], HOUR_W,
                             FACE_Z, MARK_Z))
        else:
            minutes.append(bar(ang, TICK_LEN[0], TICK_LEN[1], MARK_W,
                               FACE_Z, MARK_Z))

    if len(hours) != 12 or len(minutes) != 48:
        raise RuntimeError(f"метки: {len(hours)} часовых, {len(minutes)} минутных")

    add("HourMarks", sm.merge_breps(hours, operation=sm.BooleanOp.UNION),
        (0.10, 0.12, 0.16))
    add("MinuteMarks", sm.merge_breps(minutes, operation=sm.BooleanOp.UNION),
        (0.32, 0.35, 0.40))

    # 4. Стрелки: часовая на 10 (угол -60), минутная на 2 (угол 30)
    add("HourHand", bar(-60.0 - 90.0, 9.5, -1.8, HAND_T * 2.4,
                        FACE_Z, HAND_Z), (0.10, 0.12, 0.16))
    add("MinuteHand", bar(30.0 - 90.0, 12.8, -2.2, HAND_T,
                          FACE_Z, HAND_Z), (0.10, 0.12, 0.16))

    # 5. Ось
    add("Cap", sm.create_cylinder((0.0, 0.0, FACE_Z), 1.6, HAND_Z + 0.6),
        (0.85, 0.18, 0.18))

    return parts


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("[1/3] строим части")
    parts = build()
    for p in parts:
        b = p["brep"]
        print("      %-12s %3d гран., %3d рёбер, манифолд=%s"
              % (p["name"], b.face_count(), b.edge_count(),
                 b.is_manifold_solid()))

    print("[2/3] тесселяция")
    total_v = total_i = 0
    for p in parts:
        mesh = sm.tessellate(p["brep"], chord_height_tolerance=0.01)
        arr = mesh.to_mesh_arrays(face_varying_normals=True)
        p["mesh"] = arr
        total_v += len(arr["points"])
        total_i += len(arr["faces"])
    print("      %d объектов, %d вершин, %d индексов"
          % (len(parts), total_v, total_i))

    print("[3/3] экспорт USD")
    out = os.path.join(OUT_DIR, "ClockDice.usda")
    view_usd_example_write(parts, out)
    print("      ->", out)


def view_usd_example_write(parts, out_path):
    """Тот же формат, что в tools/scripts/example_generate_asset.py."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "example_generate_asset",
        os.path.join(REPO, "tools", "scripts", "example_generate_asset.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.write_usda(parts, out_path, root_name="ClockDice")


if __name__ == "__main__":
    main()
