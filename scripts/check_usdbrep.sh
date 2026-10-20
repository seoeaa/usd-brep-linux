#!/bin/bash
# Проверка сборки NVIDIA usd-brep слоем за слоем.
# Использование: check_usdbrep.sh [путь_к_репозиторию]
# Возвращает 0, если все слои работают, и число провалов иначе.

B="${1:-/storage/usd-brep}"
U="$B/_build/target-deps/usd/release"
REL="$B/_build/linux-x86_64/release"
PY="$B/_build/target-deps/python/bin/python3"

export PYTHONPATH="$REL:$U/lib/python"
export LD_LIBRARY_PATH="$HOME/.local/lib/usdview-extra:$REL:$U/lib:$B/_build/target-deps/python/lib"
export PXR_PLUGINPATH_NAME="$B/_build/schema/omniSolid/resources:$REL/plugins/hdUsdBrep:$U/plugin/usd"
export OMNISOLID_PLUGIN_PATH="$B/_build/schema/omniSolid/resources"
export QT_QPA_PLATFORM=xcb
export PYOPENGL_PLATFORM=glx
export HDGP_INCLUDE_DEFAULT_RESOLVER=1

FAIL=0
ok()   { printf '  \033[32mOK\033[0m   %s\n' "$1"; }
bad()  { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAIL=$((FAIL+1)); }

echo "Репозиторий: $B"
[ -d "$B" ] || { echo "нет такого каталога"; exit 2; }

echo
echo "── Слой 1: артефакты сборки ──"
for f in libSMLib.so libSM_API.so libSM_API_USD.so libBREP_USD_DATA.so \
         libHYDRA_USD_BREP.so _omni_solid.cpython-312-x86_64-linux-gnu.so; do
    [ -f "$REL/$f" ] && ok "$f ($(du -h "$REL/$f" | cut -f1))" || bad "нет $f"
done
[ -f "$REL/plugins/hdUsdBrep/plugInfo.json" ] \
    && ok "plugInfo.json плагина Hydra" || bad "нет plugInfo.json плагина"
[ -f "$B/_build/schema/omniSolid/resources/plugInfo.json" ] \
    && ok "plugInfo.json схемы omniSolid" || bad "нет plugInfo.json схемы"

echo
echo "── Слой 2: геометрия и Python API ──"
$PY - "$B" <<'PYEOF' 2>/dev/null
import sys
try:
    import _omni_solid as sm
except Exception as e:
    print("  FAIL импорт _omni_solid:", e); sys.exit(1)
box = sm.create_box((0, 0, 0), 10, 10, 10)
f, e, v = box.face_count(), box.edge_count(), box.vertex_count()
vol = box.volume()
ok = (f, e, v) == (6, 12, 8) and abs(vol - 1000.0) < 1e-9
print(("  OK   " if ok else "  FAIL ") + f"create_box: {f} гран., {e} рёб., {v} верш., объём {vol:.1f}")
sys.exit(0 if ok else 1)
PYEOF
[ $? -eq 0 ] || FAIL=$((FAIL+1))

$PY - <<'PYEOF' 2>/dev/null
import sys
import _omni_solid as sm
cut = sm.boolean_difference(sm.create_box((0,0,0),10,10,10), sm.create_sphere((0,0,0),5))
vol = cut.volume()
ok = cut.is_manifold_solid() and abs(vol - 934.5394) < 0.01
print(("  OK   " if ok else "  FAIL ") + f"boolean_difference: {cut.face_count()} гран., объём {vol:.4f}, manifold={cut.is_manifold_solid()}")
sys.exit(0 if ok else 1)
PYEOF
[ $? -eq 0 ] || FAIL=$((FAIL+1))

$PY - <<'PYEOF' 2>/dev/null
import sys
import _omni_solid as sm
try:
    mesh = sm.tessellate(sm.create_sphere((0,0,0), 5))
    a = mesh.to_mesh_arrays()
    n = len(a["points"])
    ok = n > 100 and len(a["faces"]) > 0
    print(("  OK   " if ok else "  FAIL ") + f"tessellate сферы: {n} точек, {len(a['faces'])} индексов")
except Exception as ex:
    print("  FAIL tessellate:", ex); ok = False
sys.exit(0 if ok else 1)
PYEOF
[ $? -eq 0 ] || FAIL=$((FAIL+1))

echo
echo "── Слой 3: мост в USD (экспорт/импорт) ──"
$PY - <<'PYEOF' 2>/dev/null
import sys, tempfile, os
import _omni_solid as sm
cut = sm.boolean_difference(sm.create_box((0,0,0),10,10,10), sm.create_sphere((0,0,0),5))
path = os.path.join(tempfile.mkdtemp(), "rt.usda")
try:
    sm.usd.export_brep(cut, path)
    back = sm.usd.import_breps(path)
    ok = len(back) == 1 and back[0].face_count() == 7
    print(("  OK   " if ok else "  FAIL ") + f"USD-круговорот: {back[0].face_count()} граней, объём {back[0].volume():.4f}")
except Exception as ex:
    print("  FAIL USD-круговорот:", ex); ok = False
sys.exit(0 if ok else 1)
PYEOF
[ $? -eq 0 ] || FAIL=$((FAIL+1))

echo
echo "── Слой 4: регистрация плагина Hydra ──"
$PY - <<'PYEOF' 2>/dev/null
import sys
from pxr import Plug
reg = Plug.Registry()
p = reg.GetPluginWithName("hdUsdBrep")
if not p:
    print("  FAIL плагин hdUsdBrep не виден"); sys.exit(1)
types = list((p.metadata or {}).get("Types", {}).keys())
need = {"HdUsdBrepArrayAdapter", "HdUsdBrepArrayProceduralPlugin", "HdUsdBrepDisplaySceneIndexPlugin"}
ok = need.issubset(set(types))
print(("  OK   " if ok else "  FAIL ") + f"типы плагина: {len(types)} из 3 ожидаемых")
sys.exit(0 if ok else 1)
PYEOF
[ $? -eq 0 ] || FAIL=$((FAIL+1))

echo
echo "── Слой 5: приёмочные тесты плагина (без GPU) ──"
OUT=$("$PY" "$B/tests/HYDRA_USD_BREP_test/run_tests.py" 2>&1)
NPASS=$(printf '%s' "$OUT" | grep -c '^PASS:')
if [ "$NPASS" -ge 6 ]; then
    ok "тестов плагина пройдено: $NPASS"
else
    bad "тестов плагина пройдено только $NPASS, ожидалось 6"
    printf '%s\n' "$OUT" | grep -iE "fail|assert" | head -3
fi

echo
echo "── Слой 6: GPU-рендер BRep (нужен DISPLAY) ──"
if [ -z "$DISPLAY" ] || ! command -v xdotool >/dev/null; then
    echo "  SKIP нет DISPLAY — пропущено"
else
    IMG=/tmp/usdbrep_check_$$.png
    OUT=$(HDUSDBREP_GPU_IMAGE="$IMG" "$PY" "$B/tests/HYDRA_USD_BREP_test/run_tests.py" --gpu-image "$IMG" 2>&1)
    if printf '%s' "$OUT" | grep -q "PASS: native-GPU Storm rendering"; then
        ok "Storm отрендерил BRep на GPU, снимок $IMG"
    else
        bad "GPU-рендер не подтверждён"
        printf '%s\n' "$OUT" | grep -iE "assert|hgi|renderer" | head -3
    fi
fi

echo
if [ "$FAIL" -eq 0 ]; then
    printf '\033[32mИТОГ: все слои работают\033[0m\n'
else
    printf '\033[31mИТОГ: провалов %d\033[0m\n' "$FAIL"
fi
exit "$FAIL"
