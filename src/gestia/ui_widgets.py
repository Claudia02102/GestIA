from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gestia.calibration import CORNER_ZONE, CORNERS


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
