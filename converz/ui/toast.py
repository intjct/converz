"""Small card in the bottom-right corner: progress while converting, then the result."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from . import theme

W, H, M = 360, 92, 14   # card size and shadow margin


class Toast(QWidget):
    clicked = Signal()
    cancel_clicked = Signal()

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus
                         | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(W + 2 * M, H + 2 * M)
        self.setMouseTracking(True)
        self.state = "work"       # work / done / error / info
        self.title = ""
        self.detail = ""
        self.frac: float | None = 0.0
        self.can_cancel = False
        self._hover_cancel = False
        self._hide_timer = QTimer(self, singleShot=True, timeout=self.hide)

    # ---------------------------------------------------------------- api

    def _place(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 6, screen.bottom() - self.height() - 6)

    def _show(self):
        self._place()
        self.show()
        self.raise_()
        self.update()

    def working(self, title: str, detail: str, frac: float | None):
        self._hide_timer.stop()
        self.state, self.title, self.detail, self.frac = "work", title, detail, frac
        self.can_cancel = True
        self._show()

    def finished(self, title: str, detail: str, ok: bool = True, seconds: int = 7):
        self.state = "done" if ok else "error"
        self.title, self.detail, self.frac, self.can_cancel = title, detail, None, False
        self._show()
        self._hide_timer.start(seconds * 1000)

    def info(self, title: str, detail: str, seconds: int = 6):
        self.state = "info"
        self.title, self.detail, self.frac, self.can_cancel = title, detail, None, False
        self._show()
        self._hide_timer.start(seconds * 1000)

    # ---------------------------------------------------------------- input

    def _cancel_rect(self) -> QRectF:
        return QRectF(M + W - 76, M + 14, 62, 26)

    def enterEvent(self, e):
        if self.state != "work":
            self._hide_timer.stop()

    def leaveEvent(self, e):
        self._hover_cancel = False
        self.update()
        if self.state != "work" and self.isVisible():
            self._hide_timer.start(2500)

    def mouseMoveEvent(self, e):
        h = self.can_cancel and self._cancel_rect().contains(e.position())
        if h != self._hover_cancel:
            self._hover_cancel = h
            self.update()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, e):
        if self.can_cancel and self._cancel_rect().contains(e.position()):
            self.cancel_clicked.emit()
            return
        if self.state == "work":
            return
        self.clicked.emit()
        self.hide()

    # ---------------------------------------------------------------- paint

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = QRectF(M, M, W, H)
        # shadow
        for i in range(M, 0, -2):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(30, 20, 80, int(5 * (1 - i / M) ** 1.5 * 4)))
            p.drawRoundedRect(card.adjusted(-i, -i + 3, i, i + 3), 16 + i, 16 + i)
        path = QPainterPath()
        path.addRoundedRect(card, 16, 16)
        p.fillPath(path, QColor("white"))
        p.setPen(QPen(theme.LINE, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        # status dot / icon
        ic = QPointF(M + 30, M + 32)
        color = {"work": theme.ACCENT, "done": theme.GREEN, "error": theme.RED,
                 "info": theme.ACCENT}[self.state]
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 30))
        p.drawEllipse(ic, 16, 16)
        pen = QPen(color, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self.state == "done":
            p.drawPolyline([ic + QPointF(-6, 0), ic + QPointF(-1.5, 4.5), ic + QPointF(6.5, -4.5)])
        elif self.state == "error":
            p.drawLine(ic + QPointF(0, -6), ic + QPointF(0, 1.5))
            p.drawPoint(ic + QPointF(0, 6))
        elif self.state == "work":
            p.drawArc(QRectF(ic.x() - 7, ic.y() - 7, 14, 14), 90 * 16, -270 * 16)
        else:
            p.drawPoint(ic)

        # text
        tx = M + 58
        tw = W - 58 - (84 if self.can_cancel else 18)
        p.setPen(theme.TEXT)
        f = theme.font(14, QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(QRectF(tx, M + 14, tw, 22), Qt.AlignmentFlag.AlignVCenter,
                   QFontMetrics(f).elidedText(self.title, Qt.TextElideMode.ElideRight, int(tw)))
        f2 = theme.font(12)
        p.setFont(f2)
        p.setPen(theme.TEXT_SOFT)
        p.drawText(QRectF(tx, M + 38, W - 58 - 18, 20), Qt.AlignmentFlag.AlignVCenter,
                   QFontMetrics(f2).elidedText(self.detail, Qt.TextElideMode.ElideMiddle, W - 58 - 18))

        # progress bar
        if self.state == "work" and self.frac is not None:
            bar = QRectF(tx, M + H - 22, W - 58 - 18, 5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.ACCENT_SOFT)
            p.drawRoundedRect(bar, 2.5, 2.5)
            p.setBrush(theme.ACCENT)
            p.drawRoundedRect(QRectF(bar.x(), bar.y(), max(5.0, bar.width() * self.frac), bar.height()), 2.5, 2.5)

        if self.can_cancel:
            r = self._cancel_rect()
            p.setPen(QPen(theme.RED if self._hover_cancel else theme.LINE, 1))
            p.setBrush(QColor("#FFF5F5") if self._hover_cancel else QColor("white"))
            p.drawRoundedRect(r, 8, 8)
            p.setPen(theme.RED if self._hover_cancel else theme.TEXT_SOFT)
            p.setFont(theme.font(12))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "ยกเลิก")
