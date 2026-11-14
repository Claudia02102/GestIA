from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QAbstractButton, QLabel, QVBoxLayout, QWidget

from gestia import theme
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
        p = theme.current()
        self.setStyleSheet(
            f"QWidget {{ background: {p.surface}; border: 2px solid {p.accent}; "
            f"border-radius: 4px; }} QLabel {{ border: none; color: {p.text}; }}"
        )
        self.title.setStyleSheet(f"color: {p.accent_text};")
        self.message.setText(message)
        self.adjustSize()
        screen = self.screen() or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(QPoint(area.right() - self.width() - 16, area.y() + 16))
        self.show()
        self._hide_timer.start(self.VISIBLE_MS)


class ToggleSwitch(QAbstractButton):
    """Interruptor tipo píldora (modo oscuro); se usa con clic, Espacio o un gesto de clic."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(text)
        self.setText(text)
        self.setFixedSize(46, 26)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(46, 26)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        on = self.isChecked()
        painter.setPen(QPen(QColor(p.accent if on else p.border), 1))
        painter.setBrush(QColor(p.accent if on else p.surface_alt))
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        diameter = track.height() - 6
        x = track.right() - diameter - 3 if on else track.left() + 3
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.WHITE if on else p.text_muted))
        painter.drawEllipse(QRectF(x, track.top() + 3, diameter, diameter))
        if self.hasFocus():
            painter.setPen(QPen(QColor(p.accent), 1, Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        painter.end()


class LogoMark(QWidget):
    """Ícono de GestIA como en la landing: cuadrado naranja redondeado con una cara."""

    def __init__(self, size: int = 34, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = float(self.width())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.ORANGE))
        painter.drawRoundedRect(QRectF(0, 0, side, side), side * 0.3, side * 0.3)
        pen = QPen(QColor(theme.WHITE), side * 0.07)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        inset, arm = side * 0.24, side * 0.14
        for x, y, dx, dy in (
            (inset, inset, 1, 1), (side - inset, inset, -1, 1),
            (inset, side - inset, 1, -1), (side - inset, side - inset, -1, -1),
        ):  # esquinas del encuadre de la cámara
            painter.drawLine(QPointF(x, y), QPointF(x + dx * arm, y))
            painter.drawLine(QPointF(x, y), QPointF(x, y + dy * arm))
        eye = side * 0.05
        painter.setBrush(QColor(theme.WHITE))
        painter.drawEllipse(QPointF(side * 0.41, side * 0.44), eye, eye)
        painter.drawEllipse(QPointF(side * 0.59, side * 0.44), eye, eye)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(side * 0.38, side * 0.46, side * 0.24, side * 0.16), 200 * 16,
                        140 * 16)
        painter.end()


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
        p = theme.current()
        painter.setPen(QPen(QColor(p.border), 2))
        painter.setBrush(QColor(p.preview))
        painter.drawRoundedRect(screen, 10, 10)
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
            painter.setPen(QPen(QColor(theme.WHITE), 2))
            painter.setBrush(QColor(p.accent))
            painter.drawEllipse(center, radius, radius)
        else:
            painter.setPen(QColor("#9aa1a9"))
            painter.drawText(screen, Qt.AlignmentFlag.AlignCenter, "Sin puntero")
        painter.end()
