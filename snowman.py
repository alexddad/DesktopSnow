import math
import random
from typing import List, Optional, Tuple
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPolygonF, QRadialGradient, QLinearGradient
)
from PyQt6.QtCore import Qt, QPointF

class Snowball:
    def __init__(self, x: float, y: float, radius: float = 14.0):
        self.x = x
        self.y = y
        self.radius = radius
        self.is_dragged = False

    def draw(self, painter: QPainter):
        r = self.radius
        cx = self.x
        cy = self.y
        grad = QRadialGradient(cx - r * 0.35, cy - r * 0.35, r * 1.3)
        grad.setColorAt(0.0, QColor(255, 255, 255, 255))
        grad.setColorAt(0.7, QColor(245, 250, 255, 255))
        grad.setColorAt(1.0, QColor(200, 222, 248, 255))

        painter.setPen(QPen(QColor(185, 210, 238, 220), 1.2))
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPointF(cx, cy), r, r)

        # Highlight on top
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 180))
        painter.drawEllipse(QPointF(cx - r * 0.25, cy - r * 0.3), r * 0.4, r * 0.25)


class Snowman:
    def __init__(self, x: float, y: float, r_base: float = 34.0):
        self.x = x
        self.y = y  # y of the bottom of base
        self.r_base = r_base
        self.r_mid = r_base * 0.72
        self.r_head = r_base * 0.48
        self.is_dragged = False
        self.hat_type = random.choice(["bucket", "tophat"])
        self.scarf_color = random.choice([
            QColor(220, 35, 35),
            QColor(40, 160, 230),
            QColor(45, 180, 80)
        ])

    @property
    def total_height(self) -> float:
        return self.r_base * 2 + self.r_mid * 1.6 + self.r_head * 1.5 + 20

    def contains(self, px: float, py: float) -> bool:
        # Check if point is inside snowman bounds
        dx = abs(px - self.x)
        dy = self.y - py
        return dx <= self.r_base * 1.2 and 0 <= dy <= self.total_height

    def draw(self, painter: QPainter):
        cx = self.x
        base_y = self.y - self.r_base
        mid_y = base_y - self.r_base - self.r_mid + 8
        head_y = mid_y - self.r_mid - self.r_head + 6

        # Twig arms (behind body)
        painter.setPen(QPen(QColor(110, 65, 30), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        # Left arm
        painter.drawLine(int(cx - self.r_mid * 0.8), int(mid_y), int(cx - self.r_mid * 1.7), int(mid_y - 12))
        painter.drawLine(int(cx - self.r_mid * 1.4), int(mid_y - 8), int(cx - self.r_mid * 1.7), int(mid_y - 20))
        # Right arm
        painter.drawLine(int(cx + self.r_mid * 0.8), int(mid_y), int(cx + self.r_mid * 1.7), int(mid_y - 12))
        painter.drawLine(int(cx + self.r_mid * 1.4), int(mid_y - 8), int(cx + self.r_mid * 1.7), int(mid_y - 20))

        def draw_ball(bx, by, r):
            grad = QRadialGradient(bx - r * 0.35, by - r * 0.35, r * 1.35)
            grad.setColorAt(0.0, QColor(255, 255, 255, 255))
            grad.setColorAt(0.7, QColor(245, 250, 255, 255))
            grad.setColorAt(1.0, QColor(200, 222, 248, 255))
            painter.setPen(QPen(QColor(185, 210, 238, 210), 1.2))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QPointF(bx, by), r, r)

        # 1. Base snowball
        draw_ball(cx, base_y, self.r_base)

        # 2. Middle snowball
        draw_ball(cx, mid_y, self.r_mid)

        # Coal buttons on body
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(35, 35, 35))
        painter.drawEllipse(QPointF(cx, mid_y - 6), 2.5, 2.5)
        painter.drawEllipse(QPointF(cx, mid_y + 4), 2.5, 2.5)
        painter.drawEllipse(QPointF(cx, mid_y + 14), 2.5, 2.5)

        # 3. Head snowball
        draw_ball(cx, head_y, self.r_head)

        # Scarf around neck
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.scarf_color)
        scarf_w = self.r_mid * 1.5
        painter.drawRoundedRect(int(cx - scarf_w / 2), int(mid_y - self.r_mid + 1), int(scarf_w), 8, 3, 3)
        # Scarf hanging tail
        painter.drawRoundedRect(int(cx + 4), int(mid_y - self.r_mid + 5), 8, 18, 3, 3)

        # Face details
        # Eyes
        painter.setBrush(QColor(25, 25, 25))
        painter.drawEllipse(QPointF(cx - 5.5, head_y - 3), 2.2, 2.2)
        painter.drawEllipse(QPointF(cx + 5.5, head_y - 3), 2.2, 2.2)
        # Eye glints
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(QPointF(cx - 6.0, head_y - 4.0), 0.8, 0.8)
        painter.drawEllipse(QPointF(cx + 5.0, head_y - 4.0), 0.8, 0.8)

        # Carrot nose (pointing right)
        painter.setBrush(QColor(255, 125, 0))
        carrot = QPolygonF([
            QPointF(cx, head_y + 1),
            QPointF(cx + 14, head_y + 3.5),
            QPointF(cx, head_y + 5.5)
        ])
        painter.drawPolygon(carrot)

        # Pebble smile
        painter.setBrush(QColor(40, 40, 40))
        for dx, dy in [(-6, 8), (-3, 10), (0, 10.5), (3, 10), (6, 8)]:
            painter.drawEllipse(QPointF(cx + dx, head_y + dy), 1.2, 1.2)

        # Hat
        if self.hat_type == "bucket":
            # Metallic bucket (trapezoid, inverted)
            grad_hat = QLinearGradient(cx - 15, head_y - self.r_head - 20, cx + 15, head_y - self.r_head)
            grad_hat.setColorAt(0.0, QColor(140, 150, 160))
            grad_hat.setColorAt(1.0, QColor(80, 90, 100))
            painter.setBrush(QBrush(grad_hat))
            painter.setPen(QPen(QColor(60, 70, 80), 1.0))
            bucket = QPolygonF([
                QPointF(cx - 11, head_y - self.r_head - 16),
                QPointF(cx + 11, head_y - self.r_head - 16),
                QPointF(cx + 14, head_y - self.r_head + 2),
                QPointF(cx - 14, head_y - self.r_head + 2),
            ])
            painter.drawPolygon(bucket)
        else:
            # Classic black top hat
            painter.setBrush(QColor(40, 40, 45))
            painter.setPen(QPen(QColor(20, 20, 20), 1.0))
            # Brim
            painter.drawRoundedRect(int(cx - 18), int(head_y - self.r_head), 36, 4, 2, 2)
            # Cylinder
            painter.drawRect(int(cx - 12), int(head_y - self.r_head - 18), 24, 18)
            # Red ribbon on hat
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(220, 40, 40))
            painter.drawRect(int(cx - 12), int(head_y - self.r_head - 5), 24, 4)
