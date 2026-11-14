"""Estilo visual de GestIA: paleta de la landing, modo claro y modo oscuro.

Colores de marca: naranja ``#ff6a2b``, crema ``#f3efe6``, blanco ``#ffffff`` y tinta
``#13171c``. Todo color de la interfaz sale de una ``Palette``; nada fija colores por su cuenta,
así el modo oscuro cambia la aplicación entera de una vez.

Contraste (WCAG 2.1 AA, 4,5:1 para texto): el naranja de marca da 2,9:1 con el blanco, así que
se usa como relleno y el texto sobre él es tinta (6,3:1). En modo claro, el texto naranja usa
``accent_text``, un tono más oscuro de la misma familia (≥ 4,8:1 sobre blanco y crema).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ORANGE, CREAM, WHITE, INK = "#ff6a2b", "#f3efe6", "#ffffff", "#13171c"
# Qt solo admite rutas con «/» en las hojas de estilo, también en Windows.
CHECK_ICON = (Path(__file__).parent / "assets" / "check.svg").as_posix()
FONT_FAMILY = '"Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", sans-serif'


@dataclass(frozen=True, slots=True)
class Palette:
    name: str
    background: str  # fondo de la ventana
    surface: str  # tarjetas
    surface_alt: str  # campos, botones secundarios
    text: str
    text_muted: str
    border: str
    accent: str
    accent_hover: str
    accent_soft: str  # fondo de chips y selección
    accent_text: str  # texto naranja legible sobre el fondo de esta paleta
    on_accent: str  # texto sobre el naranja
    preview: str  # fondo de la cámara y del puntero
    success: str
    warning: str
    danger: str
    info: str
    special: str


LIGHT = Palette(
    name="claro",
    background=CREAM,
    surface=WHITE,
    surface_alt="#faf8f3",
    text=INK,
    text_muted="#5f646b",
    border="#e4ddd0",
    accent=ORANGE,
    accent_hover="#e85a1d",
    accent_soft="#ffe8dd",
    accent_text="#b93c0d",
    on_accent=INK,
    preview=INK,
    success="#15803d",
    warning="#b45309",
    danger="#c2410c",
    info="#1d4ed8",
    special="#7c3aed",
)

DARK = Palette(
    name="oscuro",
    background=INK,
    surface="#1c2128",
    surface_alt="#242a32",
    text=CREAM,
    text_muted="#a3a8ae",
    border="#323943",
    accent=ORANGE,
    accent_hover="#ff8550",
    accent_soft="#3d2418",
    accent_text=ORANGE,
    on_accent=INK,
    preview="#0c0f12",
    success="#4ade80",
    warning="#fbbf24",
    danger="#fb923c",
    info="#93c5fd",
    special="#c4b5fd",
)

_current = LIGHT


def current() -> Palette:
    """Paleta en uso; los widgets que se dibujan a mano la consultan al pintarse."""
    return _current


def palette_for(dark: bool) -> Palette:
    return DARK if dark else LIGHT


@dataclass(slots=True)
class AppearanceSettings:
    dark_mode: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AppearanceSettings:
        if not isinstance(raw, dict):
            raise ValueError("Ajustes de apariencia no válidos")
        settings = cls(**raw)
        if not isinstance(settings.dark_mode, bool):
            raise ValueError("El modo oscuro debe ser verdadero o falso")
        return settings


def stylesheet(p: Palette) -> str:
    """Hoja de estilo Qt con el lenguaje de la landing: tarjetas, píldoras y naranja."""
    return f"""
* {{ font-family: {FONT_FAMILY}; font-size: 13px; }}
QWidget {{ color: {p.text}; }}
QMainWindow, QDialog, QMessageBox, QInputDialog {{ background: {p.background}; }}
QToolTip {{ background: {p.surface}; color: {p.text}; border: 1px solid {p.border};
           padding: 6px 8px; border-radius: 8px; }}

QFrame#card {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 18px; }}
QFrame#header {{ background: {p.background}; border: none;
                 border-bottom: 1px solid {p.border}; }}
QLabel#brand {{ font-size: 20px; font-weight: 700; }}
QLabel#eyebrow {{ color: {p.accent_text}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QLabel#muted, QLabel#guidance {{ color: {p.text_muted}; }}
QLabel#preview {{ background: {p.preview}; color: #cbd2d9; border-radius: 14px; }}
QLabel#pill {{ background: {p.accent_soft}; color: {p.accent_text}; border-radius: 11px;
               padding: 3px 10px; font-weight: 600; }}

QPushButton {{ background: {p.surface_alt}; color: {p.text}; border: 1px solid {p.border};
               border-radius: 16px; padding: 7px 16px; font-weight: 600; }}
QPushButton:hover {{ border-color: {p.accent}; color: {p.accent_text}; }}
QPushButton:pressed, QPushButton:checked {{ background: {p.accent_soft}; color: {p.accent_text};
                                            border-color: {p.accent}; }}
QPushButton:disabled {{ color: {p.text_muted}; background: {p.surface_alt};
                        border-color: {p.border}; }}
QPushButton[primary="true"] {{ background: {p.accent}; color: {p.on_accent};
                               border-color: {p.accent}; }}
QPushButton[primary="true"]:hover {{ background: {p.accent_hover};
                                     border-color: {p.accent_hover}; color: {p.on_accent}; }}
QPushButton[primary="true"]:disabled {{ background: {p.accent_soft}; color: {p.text_muted};
                                        border-color: {p.accent_soft}; }}

QComboBox, QSpinBox, QLineEdit {{ background: {p.surface_alt}; color: {p.text};
    border: 1px solid {p.border}; border-radius: 12px; padding: 5px 10px; min-height: 20px; }}
QComboBox:hover, QSpinBox:hover, QLineEdit:focus {{ border-color: {p.accent}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {p.surface}; color: {p.text};
    border: 1px solid {p.border}; selection-background-color: {p.accent_soft};
    selection-color: {p.text}; outline: none; }}
QSpinBox::up-button, QSpinBox::down-button {{ border: none; width: 16px; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px;
                        border: 2px solid {p.border}; background: {p.surface_alt}; }}
QCheckBox::indicator:hover {{ border-color: {p.accent}; }}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent};
                                image: url({CHECK_ICON}); }}

QTabWidget::pane {{ border: none; top: 6px; }}
QTabBar::tab {{ background: {p.surface_alt}; color: {p.text_muted};
                border: 1px solid {p.border}; border-radius: 14px;
                padding: 6px 14px; margin-right: 6px; font-weight: 600; }}
QTabBar::tab:hover {{ color: {p.accent_text}; border-color: {p.accent}; }}
QTabBar::tab:selected {{ background: {p.accent}; color: {p.on_accent};
                         border-color: {p.accent}; }}

QListWidget {{ background: {p.surface_alt}; border: 1px solid {p.border};
               border-radius: 12px; padding: 4px; }}
QListWidget::item:selected {{ background: {p.accent_soft}; color: {p.text}; }}

QSlider::groove:horizontal {{ height: 6px; border-radius: 3px; background: {p.border}; }}
QSlider::sub-page:horizontal {{ background: {p.accent}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {p.surface}; border: 2px solid {p.accent};
                              width: 14px; height: 14px; margin: -6px 0; border-radius: 9px; }}
QSlider::handle:horizontal:disabled {{ border-color: {p.border}; }}
QSlider::sub-page:horizontal:disabled {{ background: {p.border}; }}

QProgressBar {{ background: {p.border}; border: none; border-radius: 4px; }}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 4px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""


def keyboard_stylesheet(p: Palette) -> str:
    """Teclas del teclado virtual y del menú rápido con la misma paleta."""
    return f"""
QWidget {{ background: {p.background}; color: {p.text}; font-family: {FONT_FAMILY}; }}
QPushButton {{ background: {p.surface}; color: {p.text}; border: 1px solid {p.border};
               border-radius: 10px; font-weight: 600; padding: 2px; }}
QPushButton:hover {{ border-color: {p.accent}; color: {p.accent_text}; }}
QPushButton:pressed {{ background: {p.accent}; color: {p.on_accent}; }}
QPushButton[role="special"] {{ background: {p.surface_alt}; color: {p.text_muted}; }}
QPushButton[role="suggestion"] {{ background: {p.accent_soft}; color: {p.accent_text}; }}
QPushButton[role="active"] {{ background: {p.accent}; color: {p.on_accent};
                              border-color: {p.accent}; }}
QPushButton:disabled {{ color: {p.text_muted}; background: {p.surface_alt}; }}
"""


def apply(dark: bool) -> Palette:
    """Aplica el tema a toda la aplicación y lo deja como paleta actual."""
    global _current
    from PySide6.QtWidgets import QApplication

    _current = palette_for(dark)
    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(stylesheet(_current))
    return _current
