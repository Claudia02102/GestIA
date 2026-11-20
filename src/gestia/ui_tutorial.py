"""Ventana del tutorial y del modo de práctica (P3-26), a pantalla completa como la calibración.

La lógica está en ``tutorial.py``. Esta ventana solo dibuja el tablero con el puntero virtual y
muestra los mensajes; los botones son para quien asiste, la persona usuaria avanza con gestos.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gestia import theme
from gestia.gestures import GestureEvent
from gestia.tutorial import (
    EXIT_TARGET,
    TARGET_RADIUS,
    Lesson,
    LessonKind,
    TutorialSession,
    TutorialUpdate,
)

CLOSE_AFTER_DONE_MS = 6000


class PracticeBoard(QWidget):
    """Tablero donde se mueve el puntero virtual; no toca el cursor del sistema."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.lesson: Lesson | None = None
        self.pointer: tuple[float, float] | None = None
        self.hovered: str | None = None
        self.done: frozenset[str] = frozenset()
        self.setMinimumSize(560, 320)

    def show_update(self, update: TutorialUpdate) -> None:
        self.lesson, self.pointer = update.lesson, update.pointer
        self.hovered, self.done = update.hovered, update.done
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = theme.DARK
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        painter.setPen(QPen(QColor(p.border), 2))
        painter.setBrush(QColor(p.preview))
        painter.drawRoundedRect(area, 16, 16)
        scale = min(area.width(), area.height())
        radius = TARGET_RADIUS * scale
        font = QFont(painter.font())
        font.setPointSize(13)
        font.setBold(True)
        painter.setFont(font)
        for target in () if self.lesson is None else self.lesson.targets:
            center = QPointF(
                area.left() + target.x * area.width(), area.top() + target.y * area.height()
            )
            done = target.id in self.done
            if done:
                pen, brush, text = p.success, "#14532d", "✔"
            elif target.id == self.hovered:
                pen, brush, text = p.accent, "#7c2d12", target.label
            else:
                pen, brush, text = "#9aa1a9", p.surface, target.label
            if target.id == EXIT_TARGET and not done:
                pen = p.danger
            painter.setPen(QPen(QColor(pen), 3))
            painter.setBrush(QColor(brush))
            painter.drawEllipse(center, radius, radius)
            painter.setPen(QColor(p.text))
            box = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
        if self.pointer is not None:
            x, y = self.pointer
            center = QPointF(area.left() + x * area.width(), area.top() + y * area.height())
            size = max(scale * 0.025, 8)
            painter.setPen(QPen(QColor(theme.WHITE), 3))
            painter.setBrush(QColor(p.accent))
            painter.drawEllipse(center, size, size)
        elif self.lesson is not None and self.lesson.kind is not LessonKind.DONE:
            painter.setPen(QColor("#9aa1a9"))
            painter.drawText(area, Qt.AlignmentFlag.AlignCenter, "Sin rostro: puntero detenido")
        painter.end()


class TutorialDialog(QDialog):
    """Tutorial (``practice=False``) o modo de práctica (``practice=True``)."""

    completed = Signal(bool)  # True si la persona terminó todas las lecciones

    def __init__(
        self,
        session: TutorialSession,
        on_success: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.on_success = on_success
        self._closing = False
        practice = session.practice
        self.setWindowTitle("GestIA — " + ("modo de práctica" if practice else "tutorial"))
        p = theme.DARK
        self.setStyleSheet(
            f"QDialog {{ background: {p.background}; }} QLabel {{ color: {p.text}; }}"
            f"QPushButton {{ background: {p.surface_alt}; color: {p.text}; "
            f"border: 1px solid {p.border}; border-radius: 16px; padding: 8px 16px; }}"
        )
        layout = QHBoxLayout(self)

        self.lessons_list = QListWidget()
        self.lessons_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lessons_list.setMinimumWidth(240)
        self.lessons_list.setMaximumWidth(320)
        self.lessons_list.setWordWrap(True)
        self.lessons_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lessons_list.setStyleSheet(
            f"QListWidget {{ background: {p.surface}; color: {p.text}; font-size: 15px; "
            f"border: 1px solid {p.border}; border-radius: 12px; }}"
            f"QListWidget::item:selected {{ background: {p.accent_soft}; color: {p.accent}; }}"
        )
        for lesson in session.lessons:
            self.lessons_list.addItem(QListWidgetItem(lesson.title))
        self.lessons_list.setVisible(not practice)
        layout.addWidget(self.lessons_list)

        center = QVBoxLayout()
        self.counter = QLabel()
        self.counter.setStyleSheet(f"font-size: 16px; color: {p.accent}; font-weight: 700;")
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-size: 30px; font-weight: 700;")
        self.instruction = QLabel()
        self.instruction.setWordWrap(True)
        self.instruction.setStyleSheet(f"font-size: 18px; color: {p.text_muted};")
        self.message = QLabel(" ")
        self.message.setWordWrap(True)
        self.message.setStyleSheet(f"font-size: 22px; font-weight: 600; color: {p.warning};")
        self.board = PracticeBoard()
        note = QLabel(
            "Aquí los gestos no actúan sobre el equipo: el cursor real no se mueve ni hace clic."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"font-size: 14px; color: {p.text_muted};")
        for widget in (self.counter, self.title, self.instruction, self.message):
            center.addWidget(widget)
        center.addWidget(self.board, 1)
        center.addWidget(note)
        layout.addLayout(center, 1)

        side = QVBoxLayout()
        side.addStretch()
        self.skip_button = QPushButton("Saltar lección")
        self.skip_button.clicked.connect(self.skip)
        self.restart_button = QPushButton("Reiniciar")
        self.restart_button.clicked.connect(self.restart)
        close = QPushButton("Salir (asistente)")
        close.clicked.connect(self.reject)
        for button in (self.skip_button, self.restart_button):
            button.setVisible(not practice)
            side.addWidget(button)
        side.addWidget(close)
        layout.addLayout(side)
        self._shown_index = -1
        self.feed(None, (), 0)

    def feed(
        self, pointer: tuple[float, float] | None, events: Iterable[GestureEvent], now_ms: int
    ) -> None:
        if self._closing:
            return
        update = self.session.feed(pointer, events, now_ms)
        if update.success and self.on_success is not None:
            self.on_success()
        self._render(update)
        if update.finished:
            self._closing = True
            delay = 1500 if self.session.practice else CLOSE_AFTER_DONE_MS
            QTimer.singleShot(delay, self._finish)

    def skip(self) -> None:
        self.session.skip()
        self.feed(None, (), 0)

    def restart(self) -> None:
        self._closing = False
        self.session.restart()
        self.feed(None, (), 0)

    def _render(self, update: TutorialUpdate) -> None:
        session = self.session
        if self._shown_index != update.index:
            self._shown_index = update.index
            for row in range(self.lessons_list.count()):
                prefix = "✔ " if row < update.index else ("➜ " if row == update.index else "   ")
                self.lessons_list.item(row).setText(prefix + session.lessons[row].title)
            self.lessons_list.setCurrentRow(update.index)
        lesson = update.lesson
        if session.practice:
            self.counter.setText("Práctica libre")
        else:
            total = len(session.lessons)
            self.counter.setText(f"Lección {update.index + 1} de {total}")
        self.title.setText(lesson.title)
        self.instruction.setText(lesson.instruction)
        p = theme.DARK
        color = p.success if update.success or "¡" in update.message else p.warning
        self.message.setStyleSheet(f"font-size: 22px; font-weight: 600; color: {color};")
        self.message.setText(update.message if update.message != lesson.instruction else " ")
        self.skip_button.setEnabled(lesson.kind is not LessonKind.DONE)
        self.board.setVisible(lesson.kind is not LessonKind.DONE)
        self.board.show_update(update)

    def _finish(self) -> None:
        if not self._closing:
            return
        self.completed.emit(self.session.lesson.kind is LessonKind.DONE)
        self.accept()
