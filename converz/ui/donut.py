"""The donut of formats that pops up at the cursor.

Two ways to use it:
  * drag mode  – appears (invisible) under the cursor while you hold the key and
                 drag; it only draws itself once real files are dragged over it.
                 You drop the file on a slice.
  * click mode – opened with files already known (Send to, drop zone, file
                 picker); you click a slice.
Dropping/clicking in the middle, or anywhere outside, cancels.
"""
from __future__ import annotations

import math

from PySide6.QtCore import (QEasingCurve, QPoint, QPointF, QRectF, Qt, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QCursor, QGuiApplication, QPainter, QPainterPath,
                           QRadialGradient, QFont)
from PySide6.QtWidgets import QWidget

from ..formats import KIND_NAMES_TH, Action, Selection, actions_for, display_label, make_selection
from . import theme

R_OUT = 150      # outer radius of the ring
R_IN = 58        # inner radius (the "cancel" hole)
PAD = 26         # room for the shadow
SIZE = 2 * (R_OUT + PAD)


class Donut(QWidget):
    chosen = Signal(str, list)     # action id, files
    closed = Signal()

    def __init__(self, usage_provider=lambda: {}):
        super().__init__(None)
        self._usage = usage_provider
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setFixedSize(SIZE, SIZE)
        self.mode = "drag"
        self.sel: Selection | None = None
        self.actions: list[Action] = []
        self.hover = -1
        self._shown_content = False
        self._t = 1.0
        self._anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

    # ------------------------------------------------------------------ show / hide

    def _place(self, global_pos: QPoint):
        screen = QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        x = min(max(global_pos.x() - SIZE // 2, g.left()), g.right() - SIZE)
        y = min(max(global_pos.y() - SIZE // 2, g.top()), g.bottom() - SIZE)
        self.move(x, y)

    def _set_flags(self, popup: bool):
        base = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.NoDropShadowWindowHint
        if popup:
            self.setWindowFlags(base | Qt.WindowType.Popup)
        else:
            self.setWindowFlags(base | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)

    def show_catcher(self, global_pos: QPoint):
        """Drag mode: sit invisibly under the cursor and wait for files."""
        if self.isVisible() and self.mode == "click":
            return
        self.mode = "drag"
        self.sel, self.actions, self.hover = None, [], -1
        self._shown_content = False
        self._set_flags(popup=False)
        self._place(global_pos)
        self.show()
        self.raise_()
        self.update()

    def show_menu(self, files: list[str], global_pos: QPoint | None = None):
        """Click mode: files are known, show the donut right away."""
        sel = make_selection(files)
        self.mode = "click"
        self._set_flags(popup=True)
        self._set_selection(sel)
        self._place(global_pos or QCursor.pos())
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def dismiss(self):
        if self.isVisible():
            self.hide()
            self.closed.emit()

    def hideEvent(self, e):
        self._anim.stop()
        self.sel, self.actions, self.hover = None, [], -1
        self._shown_content = False
        super().hideEvent(e)

    def _set_selection(self, sel: Selection):
        self.sel = sel
        self.actions = actions_for(sel, self._usage())
        self.hover = -1
        if not self._shown_content:
            self._shown_content = True
            self._anim.stop()
            self._anim.start()
        self.update()

    def _on_anim(self, v):
        self._t = float(v)
        self.update()

    # ------------------------------------------------------------------ geometry

    def _center(self) -> QPointF:
        return QPointF(SIZE / 2, SIZE / 2)

    def index_at(self, pos: QPointF) -> int:
        n = len(self.actions)
        if not n:
            return -1
        c = self._center()
        dx, dy = pos.x() - c.x(), pos.y() - c.y()
        r = math.hypot(dx, dy)
        if r < R_IN or r > R_OUT + 14:
            return -1
        span = 360.0 / n
        ang = (math.degrees(math.atan2(dx, -dy)) + 360.0) % 360.0  # clockwise from 12 o'clock
        return int(((ang + span / 2) % 360.0) // span)

    def _slice_path(self, i: int, r_in: float, r_out: float, gap_deg: float = 0) -> QPainterPath:
        n = len(self.actions)
        span = 360.0 / n
        # Qt angles: counter-clockwise from 3 o'clock.
        start = 90.0 - i * span + span / 2 - gap_deg
        sweep = -(span - 2 * gap_deg)
        c = self._center()
        outer = QRectF(c.x() - r_out, c.y() - r_out, 2 * r_out, 2 * r_out)
        inner = QRectF(c.x() - r_in, c.y() - r_in, 2 * r_in, 2 * r_in)
        p = QPainterPath()
        p.arcMoveTo(outer, start)
        p.arcTo(outer, start, sweep)
        p.arcTo(inner, start + sweep, -sweep)
        p.closeSubpath()
        return p

    # ------------------------------------------------------------------ painting

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        c = self._center()

        if not self._shown_content:
            # Invisible but still "there", so Windows sends the drag to us.
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 1))
            p.drawEllipse(c, R_OUT, R_OUT)
            return

        t = self._t
        p.setOpacity(t)
        p.translate(c)
        p.scale(0.88 + 0.12 * t, 0.88 + 0.12 * t)
        p.translate(-c)

        # soft shadow
        g = QRadialGradient(c + QPointF(0, 6), R_OUT + PAD)
        g.setColorAt((R_OUT - 20) / (R_OUT + PAD), QColor(30, 20, 80, 46))
        g.setColorAt(1.0, QColor(30, 20, 80, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(c + QPointF(0, 6), R_OUT + PAD, R_OUT + PAD)

        # ring
        ring = QPainterPath()
        ring.addEllipse(c, R_OUT, R_OUT)
        p.setBrush(QColor(255, 255, 255, 250))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(ring)

        n = len(self.actions)
        if n:
            span = 360.0 / n
            # thin separators
            p.setPen(theme.LINE)
            for i in range(n):
                a = math.radians(90 - i * span + span / 2)
                p.drawLine(QPointF(c.x() + R_IN * math.cos(a), c.y() - R_IN * math.sin(a)),
                           QPointF(c.x() + (R_OUT - 2) * math.cos(a), c.y() - (R_OUT - 2) * math.sin(a)))
            # hovered slice
            if 0 <= self.hover < n:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(theme.ACCENT)
                p.drawPath(self._slice_path(self.hover, R_IN + 4, R_OUT - 4, gap_deg=1.2))
            # labels
            r_mid = (R_IN + R_OUT) / 2 + 4
            big = theme.font(15 if n <= 7 else 14, QFont.Weight.Bold)
            small = theme.font(10.5)
            for i, act in enumerate(self.actions):
                a = math.radians(90 - i * span)
                x, y = c.x() + r_mid * math.cos(a), c.y() - r_mid * math.sin(a)
                label, sub = display_label(act, self.sel)
                on = i == self.hover
                p.setPen(QColor("white") if on else theme.TEXT)
                p.setFont(big)
                box = QRectF(x - 44, y - (16 if sub else 10), 88, 20)
                p.drawText(box, Qt.AlignmentFlag.AlignCenter, label)
                if sub:
                    p.setFont(small)
                    p.setPen(QColor(255, 255, 255, 215) if on else theme.TEXT_SOFT)
                    p.drawText(QRectF(x - 46, y + 3, 92, 16), Qt.AlignmentFlag.AlignCenter, sub)

        # center
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.ACCENT_SOFT if self.hover < 0 else QColor("#F4F3FA"))
        p.drawEllipse(c, R_IN - 6, R_IN - 6)
        self._paint_center(p, c)

    def _paint_center(self, p: QPainter, c: QPointF):
        sel = self.sel
        box = QRectF(c.x() - 50, c.y() - 30, 100, 60)
        if not sel or not sel.kind:
            p.setPen(theme.TEXT)
            p.setFont(theme.font(12, QFont.Weight.Bold))
            p.drawText(QRectF(c.x() - 50, c.y() - 22, 100, 22), Qt.AlignmentFlag.AlignCenter, "ยังไม่รองรับ")
            p.setPen(theme.TEXT_SOFT)
            p.setFont(theme.font(10))
            p.drawText(QRectF(c.x() - 50, c.y() + 1, 100, 18), Qt.AlignmentFlag.AlignCenter, "ไฟล์ชนิดนี้")
            return
        if 0 <= self.hover < len(self.actions):
            label, _ = display_label(self.actions[self.hover], sel)
            top = f"{sel.count} {KIND_NAMES_TH[sel.kind]}"
            bottom = f"→ {label}"
        else:
            top = f"{sel.count} {KIND_NAMES_TH[sel.kind]}"
            bottom = "ปล่อยตรงนี้ = ยกเลิก" if self.mode == "drag" else "กดตรงนี้ = ยกเลิก"
        p.setPen(theme.TEXT)
        p.setFont(theme.font(14, QFont.Weight.Bold))
        p.drawText(QRectF(box.x(), c.y() - 21, box.width(), 22), Qt.AlignmentFlag.AlignCenter, top)
        is_hint = self.hover < 0
        p.setPen(theme.TEXT_SOFT if is_hint else theme.ACCENT)
        p.setFont(theme.font(9.5 if is_hint else 13, QFont.Weight.Normal if is_hint else QFont.Weight.Bold))
        p.drawText(QRectF(box.x() - 4, c.y() + 2, box.width() + 8, 20), Qt.AlignmentFlag.AlignCenter, bottom)

    # ------------------------------------------------------------------ drag mode

    @staticmethod
    def _local_files(mime) -> list[str]:
        if not mime.hasUrls():
            return []
        return [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]

    def dragEnterEvent(self, e):
        files = self._local_files(e.mimeData())
        if not files:
            e.ignore()
            return
        if self.sel is None or self.sel.files + self.sel.skipped != files:
            self._set_selection(make_selection(files))
        e.setDropAction(Qt.DropAction.CopyAction)
        e.accept()

    def dragMoveEvent(self, e):
        idx = self.index_at(e.position())
        if idx != self.hover:
            self.hover = idx
            self.update()
        if idx >= 0 and self.sel and self.sel.kind:
            # Always COPY: the source file must never be moved or deleted.
            e.setDropAction(Qt.DropAction.CopyAction)
            e.accept()
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self.hover = -1
        self.update()

    def dropEvent(self, e):
        idx = self.index_at(e.position())
        if idx < 0 or not self.sel or not self.sel.kind:
            e.ignore()
            return
        e.setDropAction(Qt.DropAction.CopyAction)
        e.accept()
        action_id, files = self.actions[idx].id, list(self.sel.files)
        # Finish the Windows drop first, then close and start converting.
        QTimer.singleShot(0, lambda: (self.hide(), self.chosen.emit(action_id, files)))

    def _choose(self, idx: int):
        if not self.sel or not (0 <= idx < len(self.actions)):
            return
        action, files = self.actions[idx], list(self.sel.files)
        self.hide()
        self.chosen.emit(action.id, files)

    # ------------------------------------------------------------------ click mode

    def mouseMoveEvent(self, e):
        if self.mode != "click":
            return
        idx = self.index_at(e.position())
        if idx != self.hover:
            self.hover = idx
            self.setCursor(Qt.CursorShape.PointingHandCursor if idx >= 0 else Qt.CursorShape.ArrowCursor)
            self.update()

    def mouseReleaseEvent(self, e):
        if self.mode != "click":
            return
        idx = self.index_at(e.position())
        if idx >= 0 and self.sel and self.sel.kind:
            self._choose(idx)
        else:
            self.dismiss()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.dismiss()
        else:
            super().keyPressEvent(e)
