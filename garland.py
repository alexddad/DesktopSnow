"""Новогодняя гирлянда: лампочки лежат на сугробах по верхнему краю окон,
мерцают, светятся и качаются, когда окно двигают."""
import math
from typing import Dict, List, Tuple

from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QPixmap, QRadialGradient
from PyQt6.QtCore import Qt, QPointF, QRectF

CLASSIC_HUES = [0, 42, 125, 205, 300]  # красный, золото, зелёный, синий, малиновый


class GarlandRenderer:
    MODES = {
        "classic": "✨ Классика (мягкое мерцание)",
        "chase": "💫 Бегущие огни",
        "rainbow": "🌈 Радуга",
    }

    def __init__(self):
        self.enabled = True
        self.mode = "classic"
        self.t = 0.0
        self.fade = 0.0  # плавное включение / выключение
        self.sway: Dict[int, List[float]] = {}  # hwnd -> [смещение, скорость]
        self._glow_cache: Dict[int, QPixmap] = {}

    # ---------- управление ----------
    def set_enabled(self, value: bool):
        self.enabled = bool(value)

    def set_mode(self, mode: str):
        if mode in self.MODES:
            self.mode = mode

    # ---------- анимация ----------
    def update(self, dt: float, surfaces: list):
        self.t += dt
        target = 1.0 if self.enabled else 0.0
        self.fade += (target - self.fade) * min(1.0, dt * 2.5)

        alive = set()
        for s in surfaces:
            alive.add(s.hwnd)
            st = self.sway.setdefault(s.hwnd, [0.0, 0.0])
            goal = max(-14.0, min(14.0, -s.vx * 1.2))
            acc = (goal - st[0]) * 60.0 - st[1] * 7.0  # пружина с затуханием
            st[1] += acc * dt
            st[0] += st[1] * dt
        for hwnd in list(self.sway):
            if hwnd not in alive:
                del self.sway[hwnd]

    # ---------- рисование ----------
    def _glow(self, hue: float) -> QPixmap:
        key = int(hue) // 8
        pm = self._glow_cache.get(key)
        if pm is None:
            size = 44
            pm = QPixmap(size, size)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            base = QColor.fromHsv((key * 8 + 4) % 360, 210, 255)
            g = QRadialGradient(size / 2, size / 2, size / 2)
            for pos, alpha in ((0.0, 175), (0.45, 60), (1.0, 0)):
                c = QColor(base)
                c.setAlpha(alpha)
                g.setColorAt(pos, c)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(0, 0, size, size)
            p.end()
            self._glow_cache[key] = pm
        return pm

    @staticmethod
    def _snow_h(profile: List[float], rel_x: float, step: float) -> float:
        if not profile:
            return 0.0
        idx = int(rel_x / step)
        return profile[max(0, min(len(profile) - 1, idx))]

    def _bulb_look(self, gi: int) -> Tuple[float, float]:
        """Возвращает (оттенок, яркость 0..1) для лампочки gi."""
        if self.mode == "rainbow":
            return (gi * 14 + self.t * 70) % 360, 0.9 + 0.1 * math.sin(self.t * 3 + gi)
        hue = CLASSIC_HUES[gi % len(CLASSIC_HUES)]
        if self.mode == "chase":
            wave = max(0.0, math.sin(self.t * 3.5 - gi * 0.8))
            return hue, 0.25 + 0.75 * wave
        return hue, 0.85 + 0.15 * math.sin(self.t * 2.2 + gi * 1.9)

    def draw(self, painter: QPainter, s, profile: List[float], step: float,
             intervals: List[Tuple[float, float]], slant: float):
        if self.fade < 0.02:
            return
        left, right, top = float(s.left), float(s.right), float(s.top)
        width = right - left
        if width < 160:
            return

        n_anchor = max(2, int(width // 110) + 1)
        margin = 18.0
        span = width - margin * 2
        anchors = []
        for i in range(n_anchor):
            ax = left + margin + span * i / (n_anchor - 1)
            ay = top - self._snow_h(profile, ax - left, step) - 3.0
            anchors.append((ax + slant, ay))

        sway = self.sway.get(s.hwnd, [0.0, 0.0])[0]
        seed = (s.hwnd % 97) * 0.1

        painter.save()
        clip = QPainterPath()
        for l, r in intervals:
            clip.addRect(QRectF(l - 6, top - 60, r - l + 12, 110))
        painter.setClipPath(clip)

        bulbs = []  # (x, y, bx, by) — точка на проводе и центр лампочки
        wire = QPainterPath()
        for i in range(len(anchors) - 1):
            x0, y0 = anchors[i]
            x1, y1 = anchors[i + 1]
            sag = 10.0 + 4.0 * math.sin(seed + i * 1.7)
            cx = (x0 + x1) / 2 + sway * 0.4
            cy = (y0 + y1) / 2 + sag * 2
            wire.moveTo(x0, y0)
            wire.quadTo(cx, cy, x1, y1)

            nb = max(3, int(math.hypot(x1 - x0, y1 - y0) / 22))
            for k in range(nb):
                t = (k + 0.5) / nb
                u = 1 - t
                wx = u * u * x0 + 2 * u * t * cx + t * t * x1
                wy = u * u * y0 + 2 * u * t * cy + t * t * y1
                off = sway * math.sin(math.pi * t) * 0.35
                bulbs.append((wx, wy, wx + off * 0.6, wy + 7.0))

        # провод
        painter.setOpacity(self.fade)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(18, 32, 24, 235), 1.5))
        painter.drawPath(wire)

        # крепления
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(30, 30, 34, 240))
        for ax, ay in anchors:
            painter.drawEllipse(QPointF(ax, ay), 2.2, 2.2)

        # свечение (под лампочками)
        looks = [self._bulb_look(gi) for gi in range(len(bulbs))]
        for (wx, wy, bx, by), (hue, br) in zip(bulbs, looks):
            painter.setOpacity(self.fade * min(1.0, br) * 0.95)
            painter.drawPixmap(QPointF(bx - 22, by - 22), self._glow(hue))

        # сами лампочки
        painter.setOpacity(self.fade)
        for (wx, wy, bx, by), (hue, br) in zip(bulbs, looks):
            painter.setPen(QPen(QColor(18, 32, 24, 220), 1.0))
            painter.drawLine(QPointF(wx, wy), QPointF(bx, by - 3.5))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor.fromHsv(int(hue) % 360, 220, int(90 + 165 * max(0.0, min(1.0, br)))))
            painter.drawEllipse(QPointF(bx, by), 3.2, 4.2)
            painter.setBrush(QColor(255, 255, 255, int(200 * max(0.0, min(1.0, br)))))
            painter.drawEllipse(QPointF(bx - 0.8, by - 1.0), 1.1, 1.4)
            painter.setBrush(QColor(30, 30, 34, 240))
            painter.drawRect(QRectF(bx - 1.6, by - 6.0, 3.2, 2.6))

        painter.restore()
