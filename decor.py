"""Новогодние украшения окон: ёлочка с подарками и блёстки на сугробах."""
import math
from typing import List, Tuple

from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QPolygonF, QLinearGradient
from PyQt6.QtCore import Qt, QPointF, QRectF

from garland import GarlandRenderer

# (ярус, смещение по ширине -1..1, положение по высоте яруса 0..1) — где висят огоньки
TREE_LIGHTS = [
    (0, -0.70, 0.80), (0, 0.05, 0.86), (0, 0.65, 0.74), (0, -0.30, 0.45), (0, 0.35, 0.42),
    (1, -0.55, 0.75), (1, 0.45, 0.70), (1, 0.0, 0.38),
    (2, -0.45, 0.70), (2, 0.45, 0.65), (2, 0.0, 0.32),
]

GIFT_COLORS = [
    (QColor(220, 40, 50), QColor(255, 215, 90)),
    (QColor(40, 130, 230), QColor(255, 255, 255)),
    (QColor(50, 170, 90), QColor(255, 90, 110)),
    (QColor(150, 70, 210), QColor(255, 220, 120)),
]


class DecorRenderer:
    def __init__(self, garland: GarlandRenderer):
        self.garland = garland  # берём у гирлянды цвета/мерцание и свечение
        self.tree_on = True
        self.sparkles_on = True
        self.t = 0.0
        self.tree_fade = 0.0
        self.sparkle_fade = 0.0

    def set_tree(self, value: bool):
        self.tree_on = bool(value)

    def set_sparkles(self, value: bool):
        self.sparkles_on = bool(value)

    def update(self, dt: float):
        self.t += dt
        k = min(1.0, dt * 2.5)
        self.tree_fade += ((1.0 if self.tree_on else 0.0) - self.tree_fade) * k
        self.sparkle_fade += ((1.0 if self.sparkles_on else 0.0) - self.sparkle_fade) * k

    @staticmethod
    def _snow_h(profile: List[float], rel_x: float, step: float) -> float:
        if not profile:
            return 0.0
        idx = int(rel_x / step)
        return profile[max(0, min(len(profile) - 1, idx))]

    # ---------- общий вход ----------
    def draw(self, painter: QPainter, s, profile: List[float], step: float,
             intervals: List[Tuple[float, float]], slant: float):
        want_tree = self.tree_fade > 0.02 and s.width >= 420
        want_sparkles = self.sparkle_fade > 0.02
        if not (want_tree or want_sparkles):
            return
        top = float(s.top)

        painter.save()
        clip = QPainterPath()
        for l, r in intervals:
            clip.addRect(QRectF(l - 6, top - 120, r - l + 12, 170))
        painter.setClipPath(clip)

        if want_sparkles:
            self._draw_sparkles(painter, s, profile, step, slant)
        if want_tree:
            self._draw_tree_and_gifts(painter, s, profile, step, intervals, slant)
        painter.restore()

    # ---------- блёстки ----------
    def _draw_sparkles(self, painter, s, profile, step, slant):
        left, top, width = float(s.left), float(s.top), float(s.width)
        seed = (s.hwnd % 89) * 0.071
        n = max(2, int(width / 70))
        painter.setPen(Qt.PenStyle.NoPen)
        for j in range(n):
            rel = ((j * 0.6180339 + seed) % 1.0) * width
            h = self._snow_h(profile, rel, step)
            if h < 3.0:
                continue
            frac = 0.35 + 0.5 * ((j * 0.37 + seed) % 1.0)
            k = max(0.0, math.sin(self.t * 1.6 + j * 2.1 + seed * 9)) ** 4
            if k < 0.05:
                continue
            x = left + rel + slant * 0.6
            y = top - h * frac
            size = 2.0 + 4.5 * k
            painter.setOpacity(self.sparkle_fade * 0.35 * k)
            painter.setBrush(QColor(150, 205, 255))
            painter.drawEllipse(QPointF(x, y), size * 1.7, size * 1.7)
            painter.setOpacity(self.sparkle_fade * min(1.0, k * 1.2))
            painter.setBrush(QColor(255, 255, 255))
            q = size * 0.22
            painter.drawPolygon(QPolygonF([
                QPointF(x, y - size), QPointF(x + q, y - q), QPointF(x + size, y), QPointF(x + q, y + q),
                QPointF(x, y + size), QPointF(x - q, y + q), QPointF(x - size, y), QPointF(x - q, y - q),
            ]))

    # ---------- ёлочка ----------
    def _tree_spot(self, s, intervals) -> float:
        """Где стоит ёлочка: детерминированно по окну, внутри видимого участка края."""
        seed = ((s.hwnd * 7919) % 1000) / 1000.0
        cx = s.left + s.width * (0.12 + 0.76 * seed)
        for l, r in intervals:
            if l + 60 <= cx <= r - 60:
                return cx
        return -1.0

    def _draw_tree_and_gifts(self, painter, s, profile, step, intervals, slant):
        cx = self._tree_spot(s, intervals)
        if cx < 0:
            return
        left, top = float(s.left), float(s.top)
        base_y = top - self._snow_h(profile, cx - left, step) + 3.0
        fade = self.tree_fade
        seed = s.hwnd % 4

        def shear(y: float) -> float:  # ёлка чуть кренится вместе с окном
            return slant * 0.4 * max(0.0, (base_y - y) / 60.0)

        # подарки (под ёлкой, по бокам)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setOpacity(fade)
        gifts = [(-34, 15, 13), (30, 12, 11), (44, 9, 9)]
        for gi, (dx, w, h) in enumerate(gifts):
            gx = cx + dx
            gy = top - self._snow_h(profile, gx - left, step) + 3.0
            body, ribbon = GIFT_COLORS[(seed + gi) % len(GIFT_COLORS)]
            painter.setBrush(body)
            painter.drawRoundedRect(QRectF(gx - w / 2, gy - h, w, h), 1.5, 1.5)
            painter.setBrush(ribbon)
            painter.drawRect(QRectF(gx - 1.2, gy - h, 2.4, h))
            painter.drawRect(QRectF(gx - w / 2, gy - h / 2 - 1.1, w, 2.2))
            painter.drawEllipse(QPointF(gx - 2.6, gy - h - 1.6), 2.6, 1.8)
            painter.drawEllipse(QPointF(gx + 2.6, gy - h - 1.6), 2.6, 1.8)

        # ствол
        painter.setBrush(QColor(95, 58, 30))
        painter.drawRect(QRectF(cx - 3 + shear(base_y - 3), base_y - 6, 6, 6))

        # три яруса: (низ, полуширина, высота)
        tiers = [(base_y - 5, 21.0, 26.0), (base_y - 22, 16.0, 24.0), (base_y - 39, 11.0, 22.0)]
        apex_y = []
        for bottom, hw, h in tiers:
            ay = bottom - h
            apex_y.append(ay)
            grad = QLinearGradient(cx, ay, cx, bottom)
            grad.setColorAt(0.0, QColor(46, 160, 82))
            grad.setColorAt(1.0, QColor(14, 86, 46))
            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(QColor(8, 56, 30, 220), 1.0))
            painter.drawPolygon(QPolygonF([
                QPointF(cx + shear(ay), ay),
                QPointF(cx + hw + shear(bottom), bottom),
                QPointF(cx - hw + shear(bottom), bottom),
            ]))
            # снежок на кончиках ярусов
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 235))
            for fx in (-0.85, -0.45, 0.0, 0.45, 0.85):
                painter.drawEllipse(QPointF(cx + hw * fx + shear(bottom), bottom - 0.5), 3.2, 1.7)

        # огоньки (цвета и мерцание берём у гирлянды)
        painter.setPen(Qt.PenStyle.NoPen)
        pts = []
        for gi, (tier, dx, tt) in enumerate(TREE_LIGHTS):
            bottom, hw, h = tiers[tier]
            y = (bottom - h) + tt * h
            x = cx + dx * hw * tt * 0.9 + shear(y)
            pts.append((x, y, self.garland._bulb_look(gi + 3)))
        for x, y, (hue, br) in pts:
            painter.setOpacity(fade * min(1.0, br) * 0.9)
            painter.drawPixmap(QPointF(x - 22, y - 22), self.garland._glow(hue))
        painter.setOpacity(fade)
        for x, y, (hue, br) in pts:
            painter.setBrush(QColor.fromHsv(int(hue) % 360, 220, int(100 + 155 * max(0.0, min(1.0, br)))))
            painter.drawEllipse(QPointF(x, y), 2.2, 2.2)
            painter.setBrush(QColor(255, 255, 255, int(190 * max(0.0, min(1.0, br)))))
            painter.drawEllipse(QPointF(x - 0.6, y - 0.6), 0.8, 0.8)

        # звезда на макушке
        sx, sy = cx + shear(apex_y[2]), apex_y[2] - 3.0
        pulse = 0.75 + 0.25 * math.sin(self.t * 3.0)
        painter.setOpacity(fade * pulse)
        painter.drawPixmap(QPointF(sx - 22, sy - 22), self.garland._glow(48))
        painter.setOpacity(fade)
        star = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            r = 6.0 if i % 2 == 0 else 2.6
            star.append(QPointF(sx + math.cos(ang) * r, sy + math.sin(ang) * r))
        painter.setBrush(QColor(255, 214, 70))
        painter.setPen(QPen(QColor(210, 150, 20, 230), 0.8))
        painter.drawPolygon(QPolygonF(star))
