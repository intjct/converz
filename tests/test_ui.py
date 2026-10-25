import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QApplication

from converz.ui.donut import Donut, R_IN, R_OUT, SIZE


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _mime(paths):
    m = QMimeData()
    m.setUrls([QUrl.fromLocalFile(p) for p in paths])
    return m


def _slice_point(n, i):
    span = 360 / n
    a = math.radians(i * span)  # clockwise from 12 o'clock
    r = (R_IN + R_OUT) / 2
    return QPointF(SIZE / 2 + r * math.sin(a), SIZE / 2 - r * math.cos(a))


def test_drag_drop_flow(app, tmp_path):
    files = []
    for i in range(3):
        p = tmp_path / f"p{i}.jpg"
        Image.new("RGB", (4, 4)).save(p)
        files.append(str(p))
    d = Donut()
    got = []
    d.chosen.connect(lambda aid, f: got.append((aid, f)))
    d.show_catcher(QPoint(500, 500))
    assert d.sel is None  # invisible until files arrive

    mime = _mime(files)
    # Shift-drag proposes MOVE; we must answer COPY so the original stays put.
    actions = Qt.DropAction.CopyAction | Qt.DropAction.MoveAction | Qt.DropAction.LinkAction
    enter = QDragEnterEvent(QPoint(SIZE // 2, SIZE // 2), actions, mime,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier)
    d.dragEnterEvent(enter)
    assert enter.isAccepted() and d.sel.count == 3

    n = len(d.actions)
    pdf_i = [a.id for a in d.actions].index("img_pdf")
    pt = _slice_point(n, pdf_i)
    assert d.index_at(pt) == pdf_i
    move = QDragMoveEvent(pt.toPoint(), actions, mime, Qt.MouseButton.LeftButton,
                          Qt.KeyboardModifier.ShiftModifier)
    d.dragMoveEvent(move)
    assert move.isAccepted() and move.dropAction() == Qt.DropAction.CopyAction

    # Center = cancel: drop is refused.
    center = QDropEvent(QPointF(SIZE / 2, SIZE / 2), actions, mime, Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier)
    d.dropEvent(center)
    assert not center.isAccepted()

    drop = QDropEvent(pt, actions, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier)
    d.dropEvent(drop)
    assert drop.isAccepted() and drop.dropAction() == Qt.DropAction.CopyAction
    for _ in range(5):
        app.processEvents()
    assert got and got[0][0] == "img_pdf" and len(got[0][1]) == 3


def test_every_slice_reachable(app, tmp_path):
    p = tmp_path / "v.mov"
    p.write_bytes(b"x")
    d = Donut()
    d.show_menu([str(p)])
    n = len(d.actions)
    assert [d.index_at(_slice_point(n, i)) for i in range(n)] == list(range(n))
    assert d.index_at(QPointF(SIZE / 2, SIZE / 2)) == -1
    d.hide()
