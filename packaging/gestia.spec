# PyInstaller: empaqueta GestIA con Python, sus dependencias y el modelo (P3-24).
# Uso, desde la raíz del repositorio y con el modelo ya descargado en models/:
#   pyinstaller packaging/gestia.spec --noconfirm
# Resultado: dist/GestIA/GestIA.exe (carpeta que luego empaqueta packaging/installer.iss).

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path(SPECPATH).parent  # noqa: F821 - variable que define PyInstaller
MODEL = ROOT / "models" / "face_landmarker.task"
if not MODEL.exists():
    raise SystemExit("Falta models/face_landmarker.task: ejecute python tools/download_model.py")

datas = [
    (str(MODEL), "models"),
    (str(ROOT / "src" / "gestia" / "assets"), "gestia/assets"),
]
datas += collect_data_files("mediapipe")
binaries = collect_dynamic_libs("mediapipe")

analysis = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=["pynput.keyboard._win32", "pynput.mouse._win32"],
    excludes=["tkinter", "matplotlib", "pytest"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="GestIA",
    icon=str(ROOT / "packaging" / "gestia.ico"),
    console=False,
    upx=False,
)
COLLECT(  # noqa: F821
    exe,
    analysis.binaries,
    analysis.datas,
    name="GestIA",
    upx=False,
)
