"""The settings window (opened from the tray icon or Start menu)."""
from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QRectF, QSize, Qt, Signal, Property, QEasingCurve
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from .. import APP_NAME, VERSION
from ..settings import Settings
from . import theme

KEY_INFO = {
    "ctrl": ("ok", "Ctrl + ลาก ปกติ Windows ใช้ “คัดลอกไฟล์” — ถ้าเผลอไปปล่อยในโฟลเดอร์อื่น "
                   "จะได้สำเนาเพิ่มมา 1 ไฟล์ ไม่มีอะไรเสียหาย  (แนะนำ)"),
    "shift": ("warn", "Shift + ลาก ปกติ Windows ใช้ “ย้ายไฟล์” — ถ้าเผลอไปปล่อยในโฟลเดอร์อื่น "
                      "ไฟล์จะถูกย้ายไปอยู่ที่นั่นแทน  (ต้องระวังกว่า)"),
    "alt": ("ok", "Alt + ลาก ปกติ Windows ใช้ “สร้างทางลัด (shortcut)” — ถ้าเผลอไปปล่อยที่อื่น "
                  "จะได้ไฟล์ทางลัดเพิ่มมา 1 ไฟล์ ไม่มีอะไรเสียหาย"),
}


class Switch(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self, duration=140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def sizeHint(self):
        return QSize(44, 26)

    def _animate(self, on):
        self._anim.stop()
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def setChecked(self, on):
        super().setChecked(on)
        self._anim.stop()
        self._pos = 1.0 if on else 0.0
        self.update()

    def get_knob(self):
        return self._pos

    def set_knob(self, v):
        self._pos = v
        self.update()

    knob = Property(float, get_knob, set_knob)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, 44, 26)
        off, on = QColor("#D9D8E3"), theme.ACCENT
        t = self._pos
        col = QColor(int(off.red() + (on.red() - off.red()) * t), int(off.green() + (on.green() - off.green()) * t),
                     int(off.blue() + (on.blue() - off.blue()) * t))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(r, 13, 13)
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(3 + 18 * t, 3, 20, 20))


class DropZone(QFrame):
    files_dropped = Signal(list)
    pick_clicked = Signal()

    def __init__(self, key_name: str):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumHeight(170)
        self._hover = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 26, 20, 22)
        lay.setSpacing(6)
        self.big = QLabel("ลากไฟล์มาวางตรงนี้")
        self.big.setFont(theme.font(19, QFont.Weight.Bold))
        self.big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.small = QLabel()
        self.small.setObjectName("Soft")
        self.small.setFont(theme.font(13))
        self.small.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.small.setWordWrap(True)
        self.set_key(key_name)
        btn = QPushButton("เลือกไฟล์…")
        btn.setObjectName("Primary")
        btn.setFont(theme.font(13, QFont.Weight.DemiBold))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self.pick_clicked)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn)
        row.addStretch()
        lay.addStretch()
        lay.addWidget(self.big)
        lay.addWidget(self.small)
        lay.addSpacing(10)
        lay.addLayout(row)
        lay.addStretch()

    def set_key(self, key_name: str):
        self.small.setText(f"หรือกด {key_name} ค้างไว้ แล้วลากไฟล์จากที่ไหนก็ได้ในเครื่อง")

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setBrush(theme.ACCENT_SOFT if self._hover else QColor("white"))
        pen = QPen(theme.ACCENT if self._hover else QColor("#D5D3E3"), 1.6, Qt.PenStyle.DashLine)
        pen.setDashPattern([5, 4])
        p.setPen(pen)
        p.drawRoundedRect(r, 16, 16)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            self._hover = True
            self.update()
            e.setDropAction(Qt.DropAction.CopyAction)
            e.accept()

    def dragMoveEvent(self, e):
        e.setDropAction(Qt.DropAction.CopyAction)
        e.accept()

    def dragLeaveEvent(self, e):
        self._hover = False
        self.update()

    def dropEvent(self, e):
        self._hover = False
        self.update()
        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        e.setDropAction(Qt.DropAction.CopyAction)
        e.accept()
        if files:
            self.files_dropped.emit(files)


def _card() -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("Card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(10)
    return f, lay


def _title(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("Title")
    l.setFont(theme.font(14, QFont.Weight.Bold))
    return l


def _segmented(options: list[tuple[str, str]], current: str, on_change) -> tuple[QWidget, QButtonGroup]:
    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    group = QButtonGroup(w)
    group.setExclusive(True)
    for key, label in options:
        b = QPushButton(label)
        b.setObjectName("Seg")
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFont(theme.font(13, QFont.Weight.DemiBold))
        b.setProperty("key", key)
        b.setChecked(key == current)
        group.addButton(b)
        row.addWidget(b, 1)
    group.buttonClicked.connect(lambda b: on_change(b.property("key")))
    return w, group


def _toggle_row(text: str, sub: str, on: bool, changed) -> tuple[QWidget, Switch]:
    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 2, 0, 2)
    col = QVBoxLayout()
    col.setSpacing(1)
    t = QLabel(text)
    t.setFont(theme.font(13, QFont.Weight.DemiBold))
    s = QLabel(sub)
    s.setObjectName("Soft")
    s.setFont(theme.font(12))
    s.setWordWrap(True)
    col.addWidget(t)
    col.addWidget(s)
    sw = Switch()
    sw.setChecked(on)
    sw.toggled.connect(changed)
    row.addLayout(col, 1)
    row.addWidget(sw, 0, Qt.AlignmentFlag.AlignVCenter)
    return w, sw


class MainWindow(QWidget):
    files_dropped = Signal(list)
    settings_changed = Signal(str)   # name of the setting
    quit_clicked = Signal()
    hidden_to_tray = Signal()

    KEY_LABEL = {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt"}

    def __init__(self, settings: Settings):
        super().__init__()
        self.s = settings
        self.setObjectName("Main")
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(theme.app_icon())
        self.setStyleSheet(theme.STYLE)
        self.setFont(theme.font(13))
        self.resize(500, 760)
        self.setMinimumWidth(440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("Main")
        scroll.setWidget(body)
        outer.addWidget(scroll)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(14)

        # header
        head = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(theme.app_icon().pixmap(36, 36))
        name = QLabel(APP_NAME)
        name.setFont(theme.font(22, QFont.Weight.Bold))
        head.addWidget(icon)
        head.addSpacing(6)
        head.addWidget(name)
        head.addStretch()
        self.status = QLabel()
        self.status.setFont(theme.font(12, QFont.Weight.DemiBold))
        self.enable_sw = Switch()
        self.enable_sw.setChecked(self.s.enabled)
        self.enable_sw.toggled.connect(self._set_enabled)
        head.addWidget(self.status)
        head.addSpacing(6)
        head.addWidget(self.enable_sw)
        lay.addLayout(head)
        self._refresh_status()

        # drop zone
        self.drop = DropZone(self.KEY_LABEL[self.s.trigger_key])
        self.drop.files_dropped.connect(self.files_dropped)
        self.drop.pick_clicked.connect(self._pick)
        lay.addWidget(self.drop)

        # trigger key
        card, c = _card()
        c.addWidget(_title("ปุ่มที่ต้องกดค้างตอนลากไฟล์"))
        seg, _ = _segmented([("ctrl", "Ctrl"), ("shift", "Shift"), ("alt", "Alt")],
                            self.s.trigger_key, self._set_key)
        c.addWidget(seg)
        self.key_info = QLabel()
        self.key_info.setWordWrap(True)
        self.key_info.setFont(theme.font(12))
        c.addWidget(self.key_info)
        self._refresh_key_info()
        lay.addWidget(card)

        # quality
        card, c = _card()
        c.addWidget(_title("คุณภาพไฟล์ใหม่"))
        seg, _ = _segmented([("small", "ไฟล์เล็ก"), ("balanced", "สมดุล"), ("best", "ชัดที่สุด")],
                            self.s.quality, self._set_quality)
        c.addWidget(seg)
        q = QLabel("“สมดุล” เหมาะกับงานส่วนใหญ่ · “ชัดที่สุด” ไฟล์ใหญ่และแปลงวิดีโอช้ากว่า")
        q.setObjectName("Soft")
        q.setWordWrap(True)
        q.setFont(theme.font(12))
        c.addWidget(q)
        lay.addWidget(card)

        # output
        card, c = _card()
        c.addWidget(_title("เก็บไฟล์ใหม่ไว้ที่"))
        seg, self.out_group = _segmented([("same", "ข้างไฟล์เดิม"), ("folder", "โฟลเดอร์ที่เลือก")],
                                         self.s.output_mode, self._set_out_mode)
        c.addWidget(seg)
        self.folder_btn = QPushButton()
        self.folder_btn.setObjectName("Ghost")
        self.folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_btn.setFont(theme.font(12))
        self.folder_btn.clicked.connect(self._choose_folder)
        c.addWidget(self.folder_btn)
        n = QLabel("ไฟล์ต้นฉบับจะไม่ถูกแก้หรือลบเด็ดขาด ถ้าชื่อซ้ำจะเติม (1), (2) ให้เอง")
        n.setObjectName("Soft")
        n.setWordWrap(True)
        n.setFont(theme.font(12))
        c.addWidget(n)
        self._refresh_folder()
        lay.addWidget(card)

        # toggles
        card, c = _card()
        w, _ = _toggle_row("เปิดพร้อม Windows", "พร้อมใช้ทันทีทุกครั้งที่เปิดเครื่อง",
                           self.s.start_with_windows, lambda v: self._set("start_with_windows", v))
        c.addWidget(w)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{theme.LINE.name()};")
        c.addWidget(line)
        w, _ = _toggle_row("เมนูคลิกขวา", "คลิกขวาที่ไฟล์ → ส่งไปยัง (Send to) → Converz",
                           self.s.send_to_menu, lambda v: self._set("send_to_menu", v))
        c.addWidget(w)
        lay.addWidget(card)

        # footer
        foot = QHBoxLayout()
        v = QLabel(f"เวอร์ชัน {VERSION} · ปิดหน้าต่างนี้ได้ โปรแกรมยังทำงานอยู่ที่มุมขวาล่าง")
        v.setObjectName("Soft")
        v.setFont(theme.font(11))
        v.setWordWrap(True)
        quit_btn = QPushButton("ออกจากโปรแกรม")
        quit_btn.setObjectName("Link")
        quit_btn.setFont(theme.font(11))
        quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quit_btn.clicked.connect(self.quit_clicked)
        foot.addWidget(v, 1)
        foot.addWidget(quit_btn)
        lay.addLayout(foot)

    # ---------------------------------------------------------------- handlers

    def _set(self, name, value):
        setattr(self.s, name, value)
        self.s.save()
        self.settings_changed.emit(name)

    def _set_enabled(self, v):
        self._set("enabled", v)
        self._refresh_status()

    def set_enabled_external(self, v):
        self.enable_sw.blockSignals(True)
        self.enable_sw.setChecked(v)
        self.enable_sw.blockSignals(False)
        self._refresh_status()

    def _refresh_status(self):
        if self.s.enabled:
            self.status.setText("พร้อมใช้งาน")
            self.status.setStyleSheet(f"color:{theme.GREEN.name()};")
        else:
            self.status.setText("หยุดชั่วคราว")
            self.status.setStyleSheet(f"color:{theme.TEXT_SOFT.name()};")

    def _set_key(self, key):
        self._set("trigger_key", key)
        self._refresh_key_info()
        self.drop.set_key(self.KEY_LABEL[key])

    def _refresh_key_info(self):
        level, text = KEY_INFO[self.s.trigger_key]
        self.key_info.setObjectName("Warn" if level == "warn" else "Hint")
        self.key_info.setText(text)
        self.key_info.style().unpolish(self.key_info)
        self.key_info.style().polish(self.key_info)

    def _set_quality(self, q):
        self._set("quality", q)

    def _set_out_mode(self, mode):
        if mode == "folder" and not self.s.output_folder:
            if not self._choose_folder():
                for b in self.out_group.buttons():
                    b.setChecked(b.property("key") == "same")
                return
        self._set("output_mode", mode)
        self._refresh_folder()

    def _choose_folder(self) -> bool:
        d = QFileDialog.getExistingDirectory(self, "เลือกโฟลเดอร์สำหรับเก็บไฟล์ใหม่", self.s.output_folder)
        if not d:
            return False
        self.s.output_folder = d
        self._set("output_mode", "folder")
        for b in self.out_group.buttons():
            b.setChecked(b.property("key") == "folder")
        self._refresh_folder()
        return True

    def _refresh_folder(self):
        show = self.s.output_mode == "folder" and bool(self.s.output_folder)
        self.folder_btn.setVisible(show)
        if show:
            self.folder_btn.setText(f"📁  {self.s.output_folder}   (กดเพื่อเปลี่ยน)")

    def _pick(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "เลือกไฟล์ที่จะแปลง", "",
            "รูป วิดีโอ และเสียง (*.jpg *.jpeg *.png *.webp *.heic *.heif *.avif *.bmp *.tif *.tiff *.gif *.ico "
            "*.mp4 *.mov *.mkv *.avi *.webm *.wmv *.flv *.m4v *.3gp *.mts *.ts *.mpg *.mpeg "
            "*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.opus *.wma *.aiff *.amr);;ทุกไฟล์ (*.*)")
        if files:
            self.files_dropped.emit(files)

    def closeEvent(self, e):
        e.ignore()
        self.hide()
        self.hidden_to_tray.emit()
