"""Glue: tray icon, hold-key watcher, conversion queue, single instance."""
from __future__ import annotations

import getpass
import json
import math
import os
import queue
import sys
import threading

from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCursor
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import APP_NAME, converter, winutil
from .formats import ACTIONS_BY_ID, KIND_NAMES_TH, make_selection
from .settings import Settings
from .ui import theme
from .ui.donut import Donut
from .ui.mainwindow import MainWindow
from .ui.toast import Toast

SERVER_NAME = f"converz-{getpass.getuser()}"


# --------------------------------------------------------------------------- watcher

class HoldDragWatcher(QObject):
    """Polls the mouse and the trigger key ~40 times a second.

    When the left button is held, the mouse has moved a little, and the trigger
    key is down, we put the (invisible) donut under the cursor. Windows then
    hands the dragged files to it. Polling is used instead of a global hook:
    it can't slow down the mouse and Windows can't silently remove it."""
    triggered = Signal(QPoint)
    released = Signal()

    MOVE_PX = 10

    def __init__(self, settings: Settings, busy=lambda: False):
        super().__init__()
        self.s = settings
        self._busy = busy
        self._state = "idle"
        self._start = QPoint()
        self._timer = QTimer(self, interval=25, timeout=self._tick)
        if winutil.IS_WIN:
            self._timer.start()

    def _tick(self):
        down = winutil.left_button_down()
        if self._state == "idle":
            if down:
                self._state = "pressed"
                self._start = QCursor.pos()
            return
        if not down:
            if self._state == "armed":
                self.released.emit()
            self._state = "idle"
            return
        if self._state == "pressed" and self.s.enabled and not self._busy():
            pos = QCursor.pos()
            moved = math.hypot(pos.x() - self._start.x(), pos.y() - self._start.y())
            if moved >= self.MOVE_PX and winutil.key_down(winutil.VK[self.s.trigger_key]):
                self._state = "armed"
                self.triggered.emit(pos)


# --------------------------------------------------------------------------- worker

class Bridge(QObject):
    progress = Signal(float, str, int, int)   # frac, file, job index, jobs waiting
    finished = Signal(object, str, int)       # Result, action id, jobs waiting


class Worker:
    """Runs conversion jobs one after another on a background thread."""

    def __init__(self, settings: Settings):
        self.s = settings
        self.bridge = Bridge()
        self.q: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    def submit(self, action_id: str, files: list[str]):
        self.q.put((action_id, files))

    def cancel_current(self):
        self.cancel.set()

    def _loop(self):
        while True:
            action_id, files = self.q.get()
            self.cancel.clear()
            waiting = self.q.qsize()
            res = converter.run(
                action_id, files, self.s.quality, self.s.out_dir,
                progress=lambda f, n: self.bridge.progress.emit(f, n, len(files), self.q.qsize()),
                cancel=self.cancel)
            self.bridge.finished.emit(res, action_id, self.q.qsize())


# --------------------------------------------------------------------------- app

class ConverzApp(QObject):
    def __init__(self, qapp: QApplication, background: bool, initial_files: list[str]):
        super().__init__()
        self.qapp = qapp
        self.s = Settings.load()
        self.donut = Donut(usage_provider=lambda: self.s.usage)
        self.donut.chosen.connect(self.start_job)
        self.toast = Toast()
        self.toast.clicked.connect(self._open_last)
        self.toast.cancel_clicked.connect(self._cancel)
        self.worker = Worker(self.s)
        self.worker.bridge.progress.connect(self._on_progress)
        self.worker.bridge.finished.connect(self._on_finished)
        self._last_output: str | None = None
        self._job_label = ""

        self.win = MainWindow(self.s)
        self.win.files_dropped.connect(lambda files: self.show_menu(files))
        self.win.settings_changed.connect(self._on_setting)
        self.win.quit_clicked.connect(self.quit)
        self.win.hidden_to_tray.connect(self._on_window_hidden)
        self._told_tray = False

        self.watcher = HoldDragWatcher(
            self.s, busy=lambda: self.donut.isVisible() and self.donut.mode == "click")
        self.watcher.triggered.connect(self.donut.show_catcher)
        self.watcher.released.connect(self._on_release)

        self._make_tray()
        self._start_server()

        if not self.s.first_run_done:
            self.s.first_run_done = True
            self.s.save()
            self._apply_system_settings()
            background = False
        else:
            # keep shortcuts pointing at the current .exe location
            self._apply_system_settings()

        if initial_files:
            QTimer.singleShot(150, lambda: self.show_menu(initial_files))
        elif not background:
            self.open_window()

    # ---------------------------------------------------------------- tray

    def _make_tray(self):
        self.tray = QSystemTrayIcon(theme.app_icon(), self)
        self.tray.setToolTip(f"{APP_NAME} — กด {self._key()} ค้างแล้วลากไฟล์เพื่อแปลง")
        menu = QMenu()
        menu.setFont(theme.font(13))
        open_act = QAction("เปิด Converz", menu, triggered=self.open_window)
        self.pause_act = QAction("", menu, triggered=self._toggle_enabled)
        quit_act = QAction("ออกจากโปรแกรม", menu, triggered=self.quit)
        menu.addAction(open_act)
        menu.addAction(self.pause_act)
        menu.addSeparator()
        menu.addAction(quit_act)
        self._menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self.open_window() if r in (QSystemTrayIcon.ActivationReason.Trigger,
                                                  QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        self._refresh_pause()
        self.tray.show()

    def _key(self):
        return {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt"}[self.s.trigger_key]

    def _refresh_pause(self):
        self.pause_act.setText("หยุดชั่วคราว" if self.s.enabled else "เปิดใช้งานต่อ")
        self.tray.setToolTip(f"{APP_NAME} — กด {self._key()} ค้างแล้วลากไฟล์เพื่อแปลง"
                             if self.s.enabled else f"{APP_NAME} — หยุดชั่วคราว")

    def _toggle_enabled(self):
        self.s.enabled = not self.s.enabled
        self.s.save()
        self.win.set_enabled_external(self.s.enabled)
        self._refresh_pause()

    def open_window(self):
        self.win.show()
        self.win.setWindowState(self.win.windowState() & ~Qt.WindowState.WindowMinimized)
        self.win.raise_()
        self.win.activateWindow()

    def _on_window_hidden(self):
        if not self._told_tray:
            self._told_tray = True
            self.toast.info("Converz ยังทำงานอยู่", f"กด {self._key()} ค้างแล้วลากไฟล์ได้เลย · ไอคอนอยู่มุมขวาล่าง")

    def quit(self):
        self.tray.hide()
        self.qapp.quit()

    # ---------------------------------------------------------------- settings

    def _on_setting(self, name):
        if name in ("enabled", "trigger_key"):
            self._refresh_pause()
        if name in ("start_with_windows", "send_to_menu"):
            self._apply_system_settings()

    def _apply_system_settings(self):
        start, send_to = self.s.start_with_windows, self.s.send_to_menu

        def work():  # PowerShell can take a second; keep the UI responsive
            try:
                winutil.set_start_with_windows(start)
            except Exception:
                pass
            try:
                winutil.set_send_to(send_to)
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------------- donut

    def _on_release(self):
        # Mouse let go somewhere: if it wasn't on a slice, just close.
        QTimer.singleShot(250, lambda: self.donut.hide() if self.donut.mode == "drag" else None)

    def show_menu(self, files: list[str]):
        sel = make_selection(files)
        if not sel.kind:
            self.toast.info("ยังไม่รองรับไฟล์ชนิดนี้", "Converz แปลงได้เฉพาะรูป วิดีโอ และไฟล์เสียง")
            return
        self.donut.show_menu(files, QCursor.pos())

    # ---------------------------------------------------------------- jobs

    def start_job(self, action_id: str, files: list[str]):
        action = ACTIONS_BY_ID[action_id]
        self.s.count_use(action_id)
        self.s.save()
        if action_id == "img_pdf" and len(files) > 1:
            self._job_label = f"รวม {len(files)} รูปเป็น PDF"
        elif not action.label.isascii():
            self._job_label = f"{action.label} {len(files)} {KIND_NAMES_TH[action.kind]}"
        else:
            self._job_label = f"แปลง {len(files)} ไฟล์เป็น {action.label}"
        self.toast.working(self._job_label, "กำลังเริ่ม…", 0.0)
        self.worker.submit(action_id, files)

    def _on_progress(self, frac, name, n, waiting):
        detail = name or "เกือบเสร็จแล้ว…"
        if waiting:
            detail += f"  ·  รออีก {waiting} งาน"
        self.toast.working(self._job_label, detail, frac)

    def _cancel(self):
        self.worker.cancel_current()

    def _on_finished(self, res, action_id, waiting):
        if res.cancelled:
            self.toast.finished("ยกเลิกแล้ว", "ไฟล์ที่แปลงเสร็จก่อนหน้ายังอยู่ครบ", ok=False, seconds=4)
            return
        if res.outputs:
            self._last_output = res.outputs[-1]
        if waiting:
            return  # next job's progress will take over the toast
        n_ok, n_err = len(res.outputs), len(res.errors)
        if n_ok and not n_err:
            if n_ok == 1:
                self.toast.finished("เสร็จแล้ว", f"{os.path.basename(res.outputs[0])}  ·  กดเพื่อดูไฟล์")
            else:
                self.toast.finished(f"เสร็จแล้ว {n_ok} ไฟล์", "กดเพื่อเปิดโฟลเดอร์")
        elif n_ok:
            self.toast.finished(f"เสร็จ {n_ok} ไฟล์ · ไม่สำเร็จ {n_err} ไฟล์",
                                f"{os.path.basename(res.errors[0][0])}: {res.errors[0][1]}", ok=False, seconds=12)
        else:
            src, msg = res.errors[0] if res.errors else ("", "ไม่ทราบสาเหตุ")
            name = os.path.basename(src)
            self.toast.finished("แปลงไม่สำเร็จ", f"{name}: {msg}" if name else msg, ok=False, seconds=12)

    def _open_last(self):
        if self._last_output and os.path.exists(self._last_output):
            winutil.show_in_folder(self._last_output)

    # ---------------------------------------------------------------- single instance

    def _start_server(self):
        QLocalServer.removeServer(SERVER_NAME)
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._on_conn)
        self.server.listen(SERVER_NAME)

    def _on_conn(self):
        sock = self.server.nextPendingConnection()
        buf = bytearray()

        def read():
            buf.extend(bytes(sock.readAll()))
            if buf.endswith(b"\n"):
                try:
                    msg = json.loads(buf.decode("utf-8"))
                except Exception:
                    msg = {}
                files = msg.get("files") or []
                if files:
                    self.show_menu(files)
                else:
                    self.open_window()
                sock.disconnectFromServer()
        sock.readyRead.connect(read)


def send_to_running(files: list[str], background: bool = False) -> bool:
    """If Converz is already running, hand it the files (or ask it to show itself)."""
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if not sock.waitForConnected(400):
        return False
    if background and not files:
        return True  # started with Windows but already running: nothing to do
    if winutil.IS_WIN:
        try:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(-1)  # let it pop up in front
        except Exception:
            pass
    sock.write((json.dumps({"files": files}, ensure_ascii=False) + "\n").encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(1000)
    sock.waitForDisconnected(1500)
    return True


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in argv:
        from .selftest import selftest
        return selftest()
    background = "--background" in argv
    files = [os.path.abspath(a) for a in argv if not a.startswith("--") and os.path.exists(a)]

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    qapp = QApplication(sys.argv[:1])
    qapp.setApplicationName(APP_NAME)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setWindowIcon(theme.app_icon())
    qapp.setFont(theme.font(13))

    if send_to_running(files, background):
        return 0
    if winutil.IS_WIN:
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Converz.App")
        except Exception:
            pass
    app = ConverzApp(qapp, background, files)  # noqa: F841 (keep a reference)
    return qapp.exec()
