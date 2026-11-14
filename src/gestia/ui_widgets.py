from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gestia.calibration import CORNER_ZONE, CORNERS
from gestia.feedback import STATUS_COLOR, STATUS_TEXT, StatusKind


class PauseIndicator(QWidget):
    """Aviso flotante de pausa (P3-19): se ve sobre cualquier aplicación y no roba el foco."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet(
            "QWidget { background: #fde68a; border: 2px solid #ca8a04; border-radius: 10px; }"
            "QLabel { border: none; color: #713f12; }"
        )
        self.title = QLabel("⏸  Control en pausa")
        font = self.title.font()
        font.setPixelSize(20)
        font.setBold(True)
        self.title.setFont(font)
        self.hint = QLabel()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint, alignment=Qt.AlignmentFlag.AlignCenter)

    def show_paused(self, hint: str) -> None:
        self.hint.setText(hint)
        self.adjustSize()
        screen = self.screen() or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(QPoint(area.x() + (area.width() - self.width()) // 2, area.y() + 12))
        self.show()


OVERLAY_FLAGS = (
    Qt.WindowType.Tool
    | Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.WindowDoesNotAcceptFocus
)


def _make_overlay(widget: QWidget) -> None:
    """Ventana que se ve sobre cualquier aplicación sin robar el foco ni los clics."""
    widget.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    # Sin esto una ventana de nivel superior ignora el borde de su hoja de estilo.
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)


class StatusIndicator(QWidget):
    """P3-44: estado siempre visible en una esquina y destello al reconocer un gesto."""

    FLASH_MS = 1200

    def __init__(self) -> None:
        super().__init__(None, OVERLAY_FLAGS)
        _make_overlay(self)
        self.status: StatusKind = StatusKind.STOPPED
        self.flashing = ""
        self.label = QLabel()
        font = self.label.font()
        font.setPixelSize(16)
        font.setBold(True)
        self.label.setFont(font)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.addWidget(self.label)
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._end_flash)
        self._render()

    def set_status(self, status: StatusKind) -> None:
        if status is not self.status:
            self.status = status
            self._render()

    def flash(self, text: str) -> None:
        """Señal visual de gesto reconocido; no depende de que el sonido esté activo."""
        self.flashing = text
        self._flash_timer.start(self.FLASH_MS)
        self._render()

    def _end_flash(self) -> None:
        self.flashing = ""
        self._render()

    def _render(self) -> None:
        color = STATUS_COLOR[self.status]
        if self.flashing:
            self.label.setText(f"✔  {self.flashing}")
            background, border, ink = color, color, "#ffffff"
        else:
            self.label.setText(f"●  {STATUS_TEXT[self.status]}")
            background, border, ink = "#ffffff", color, color
        self.setStyleSheet(
            f"QWidget {{ background: {background}; border: 2px solid {border}; "
            f"border-radius: 4px; }} QLabel {{ border: none; color: {ink}; }}"
        )
        self.adjustSize()
        self._place()

    def _place(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(QPoint(area.right() - self.width() - 16, area.bottom() - self.height() - 16))


class BreakReminder(QWidget):
    """P3-45: aviso de descanso que no interrumpe: no toma el foco y se cierra solo."""

    VISIBLE_MS = 20000

    def __init__(self) -> None:
        super().__init__(None, OVERLAY_FLAGS)
        _make_overlay(self)
        self.setStyleSheet(
            "QWidget { background: #e0f2fe; border: 2px solid #0284c7; border-radius: 4px; }"
            "QLabel { border: none; color: #0c4a6e; }"
        )
        self.title = QLabel("Hora de descansar")
        font = self.title.font()
        font.setPixelSize(18)
        font.setBold(True)
        self.title.setFont(font)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setFixedWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.addWidget(self.title)
        layout.addWidget(self.message)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_reminder(self, message: str) -> None:
        self.message.setText(message)
        self.adjustSize()
        screen = self.screen() or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(QPoint(area.right() - self.width() - 16, area.y() + 16))
        self.show()
        self._hide_timer.start(self.VISIBLE_MS)


class PointerPreview(QWidget):
    """Pantalla en miniatura con el puntero virtual; no mueve el cursor del sistema."""

    def __init__(self, show_corners: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.show_corners = show_corners
        self.pointer: tuple[float, float] | None = None
        self.reached: frozenset[str] = frozenset()
        self.setMinimumSize(160, 100)

    def set_pointer(
        self, pointer: tuple[float, float] | None, reached: frozenset[str] = frozenset()
    ) -> None:
        self.pointer, self.reached = pointer, reached
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        width = min(area.width(), area.height() * 16 / 9)
        height = width * 9 / 16
        screen = QRectF(
            area.center().x() - width / 2, area.center().y() - height / 2, width, height
        )
        painter.setPen(QPen(QColor("#475569"), 2))
        painter.setBrush(QColor("#0f172a"))
        painter.drawRoundedRect(screen, 6, 6)
        if self.show_corners:
            size_x = max(screen.width() * CORNER_ZONE * 2, 18)
            size_y = max(screen.height() * CORNER_ZONE * 2, 18)
            origins = {
                "top_left": (screen.left(), screen.top()),
                "top_right": (screen.right() - size_x, screen.top()),
                "bottom_left": (screen.left(), screen.bottom() - size_y),
                "bottom_right": (screen.right() - size_x, screen.bottom() - size_y),
            }
            for name in CORNERS:
                x, y = origins[name]
                done = name in self.reached
                painter.setPen(QPen(QColor("#22c55e" if done else "#f59e0b"), 2))
                painter.setBrush(QColor("#166534" if done else "#78350f"))
                painter.drawRect(QRectF(x, y, size_x, size_y))
        if self.pointer is not None:
            x, y = self.pointer
            center = QPointF(screen.left() + x * screen.width(), screen.top() + y * screen.height())
            radius = max(min(screen.width(), screen.height()) * 0.03, 5)
            painter.setPen(QPen(QColor("#e2e8f0"), 2))
            painter.setBrush(QColor("#38bdf8"))
            painter.drawEllipse(center, radius, radius)
        else:
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(screen, Qt.AlignmentFlag.AlignCenter, "Sin puntero")
        painter.end()
