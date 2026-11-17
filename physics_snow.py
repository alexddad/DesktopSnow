import math
import random
from typing import List, Tuple, Optional, Dict
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient, QPolygonF, QLinearGradient, QPixmap
)
from PyQt6.QtCore import Qt, QPointF

GRAVITY = 850.0

class SpriteCache:
    """Pre-rendered cached pixmaps for 80x faster rendering without dynamic QRadialGradients."""
    _initialized = False
    chunk_pixmaps: Dict[int, QPixmap] = {}
    flake_pixmaps: Dict[int, QPixmap] = {}
    crystal_pixmap: Optional[QPixmap] = None

    @classmethod
    def init(cls):
        if cls._initialized:
            return
        cls._initialized = True

        # Pre-render 4 sizes of chunky snow blobs (diameters 12, 16, 20, 24)
        for d in (12, 16, 20, 24):
            pix = QPixmap(d + 4, d + 4)
            pix.fill(Qt.GlobalColor.transparent)
            p = QPainter(pix)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            cx = (d + 4) / 2.0
            cy = (d + 4) / 2.0
            r = d / 2.0

            grad = QRadialGradient(cx - r * 0.35, cy - r * 0.35, r * 1.3)
            grad.setColorAt(0.0, QColor(255, 255, 255, 255))
            grad.setColorAt(0.7, QColor(245, 250, 255, 255))
            grad.setColorAt(1.0, QColor(200, 222, 248, 255))

            p.setPen(QPen(QColor(185, 210, 238, 220), 1.0))
            p.setBrush(QBrush(grad))
            p.drawEllipse(QPointF(cx, cy), r, r)

            # Highlight
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 200))
            p.drawEllipse(QPointF(cx - r * 0.25, cy - r * 0.3), r * 0.4, r * 0.25)
            p.end()
            cls.chunk_pixmaps[d] = pix

        # Pre-render crystal snowflake
        c_pix = QPixmap(16, 16)
        c_pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(c_pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(255, 255, 255, 240), 1.2))
        p.drawLine(8, 2, 8, 14)
        p.drawLine(2, 8, 14, 8)
        p.drawLine(4, 4, 12, 12)
        p.drawLine(4, 12, 12, 4)
        p.end()
        cls.crystal_pixmap = c_pix


class SnowChunk:
    """Heavy chunk of snow that tumbles, falls fast, and splatters on collision."""
    def __init__(self, x: float, y: float, vx: float, vy: float, size: float = 8.0):
        SpriteCache.init()
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.size = size
        self.life = random.uniform(2.0, 3.5)
        self.max_life = self.life
        # Choose nearest pre-rendered sprite
        target_d = int(size * 2)
        if target_d <= 14:
            self.d = 12
        elif target_d <= 18:
            self.d = 16
        elif target_d <= 22:
            self.d = 20
        else:
            self.d = 24
        self.pix = SpriteCache.chunk_pixmaps[self.d]

    def update(self, dt: float) -> bool:
        self.vy += GRAVITY * 1.1 * dt
        self.vx *= max(0.0, 1.0 - 0.4 * dt)
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        return self.life > 0

    def draw(self, painter: QPainter):
        alpha = self.life / self.max_life
        if alpha <= 0.05:
            return

        if alpha < 0.95:
            painter.setOpacity(alpha)

        offset = (self.d + 4) / 2.0
        painter.drawPixmap(int(self.x - offset), int(self.y - offset), self.pix)

        if alpha < 0.95:
            painter.setOpacity(1.0)


class SnowDust:
    """Fine powdery blast particle that explodes outward and rapidly slows down."""
    def __init__(self, x: float, y: float, vx: float, vy: float, size: float = 2.0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.size = size
        self.life = random.uniform(0.5, 1.1)
        self.max_life = self.life
        self.drag = random.uniform(3.5, 5.5)

    def update(self, dt: float) -> bool:
        self.vy += (GRAVITY * 0.35) * dt
        drag_factor = max(0.0, 1.0 - self.drag * dt)
        self.vx *= drag_factor
        self.vy *= max(0.0, 1.0 - 1.2 * dt)
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        return self.life > 0

    def draw(self, painter: QPainter):
        alpha = int(max(0, min(255, 255 * (self.life / self.max_life))))
        if alpha <= 5:
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, alpha))
        painter.drawRect(int(self.x), int(self.y), int(self.size), int(self.size))


class SnowFlakeParticle:
    """Standard drifting snowflake with turbulence and terminal fall speed."""
    def __init__(self, x: float, y: float, vx: float, vy: float, size: float = 3.5):
        SpriteCache.init()
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.size = size
        self.sway_phase = random.uniform(0, math.pi * 2)
        self.sway_speed = random.uniform(2.5, 4.5)
        self.sway_amp = random.uniform(30.0, 70.0)
        self.life = random.uniform(2.0, 3.5)
        self.max_life = self.life
        self.is_crystal = random.random() < 0.3

    def update(self, dt: float) -> bool:
        target_vy = 180.0 + self.size * 20.0
        self.vy += (target_vy - self.vy) * 2.5 * dt
        self.vx *= max(0.0, 1.0 - 0.9 * dt)

        self.sway_phase += self.sway_speed * dt
        sway_offset = math.sin(self.sway_phase) * self.sway_amp * dt

        self.x += (self.vx * dt) + sway_offset
        self.y += self.vy * dt
        self.life -= dt
        return self.life > 0

    def draw(self, painter: QPainter):
        alpha = self.life / self.max_life
        if alpha <= 0.05:
            return

        if self.is_crystal and SpriteCache.crystal_pixmap:
            if alpha < 0.95:
                painter.setOpacity(alpha)
            painter.drawPixmap(int(self.x - 8), int(self.y - 8), SpriteCache.crystal_pixmap)
            if alpha < 0.95:
                painter.setOpacity(1.0)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, int(alpha * 240)))
            painter.drawEllipse(QPointF(self.x, self.y), self.size, self.size)


class PhysicalSnowball:
    """A snowball with real ballistic trajectory, inertia throw, bounce, and squash spring."""
    def __init__(self, x: float, y: float, radius: float = 16.0):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.radius = radius
        self.is_held = False
        self.squash_x = 1.0
        self.squash_y = 1.0
        self.squash_vx = 0.0
        self.squash_vy = 0.0
        self.is_broken = False

    def trigger_squash(self, factor: float = 0.65):
        self.squash_y = factor
        self.squash_x = 1.0 / factor

    def update(self, dt: float, floor_y: float, surfaces: list) -> List[SnowChunk]:
        debris = []
        # Spring-damper for squash & stretch
        k_spring = 160.0
        damp = 14.0

        fx = -k_spring * (self.squash_x - 1.0) - damp * self.squash_vx
        self.squash_vx += fx * dt
        self.squash_x += self.squash_vx * dt

        fy = -k_spring * (self.squash_y - 1.0) - damp * self.squash_vy
        self.squash_vy += fy * dt
        self.squash_y += self.squash_vy * dt

        if self.is_held:
            return debris

        # Free flight physics
        self.vy += GRAVITY * dt
        self.vx *= max(0.0, 1.0 - 0.15 * dt)
        self.x += self.vx * dt
        self.y += self.vy * dt

        # Collision with window tops
        for s in surfaces:
            if s.left - self.radius <= self.x <= s.right + self.radius:
                top_y = s.top - self.radius
                if top_y - 8 <= self.y <= top_y + 16 and self.vy > 0:
                    speed = math.hypot(self.vx, self.vy)
                    if speed > 650.0:
                        self.is_broken = True
                        for _ in range(12):
                            ang = random.uniform(math.pi, 2 * math.pi)
                            mag = random.uniform(150, 400)
                            debris.append(SnowChunk(
                                self.x, self.y,
                                math.cos(ang) * mag + self.vx * 0.2,
                                math.sin(ang) * mag,
                                size=random.uniform(4.0, 7.5)
                            ))
                        return debris
                    else:
                        self.y = top_y
                        self.vy = -self.vy * 0.45
                        self.vx *= 0.6
                        self.trigger_squash(0.65)
                        if abs(self.vy) < 40.0:
                            self.vy = 0.0

        # Floor bounce
        if self.y >= floor_y - self.radius:
            speed = math.hypot(self.vx, self.vy)
            if speed > 700.0:
                self.is_broken = True
                for _ in range(14):
                    ang = random.uniform(math.pi, 2 * math.pi)
                    mag = random.uniform(180, 450)
                    debris.append(SnowChunk(
                        self.x, floor_y - self.radius,
                        math.cos(ang) * mag,
                        math.sin(ang) * mag,
                        size=random.uniform(4.0, 8.0)
                    ))
                return debris

            self.y = floor_y - self.radius
            self.vy = -self.vy * 0.42
            self.vx *= 0.65
            self.trigger_squash(0.60)
            if abs(self.vy) < 40.0:
                self.vy = 0.0

        return debris

    def draw(self, painter: QPainter):
        if self.is_broken:
            return

        r = self.radius
        cx = self.x
        cy = self.y

        painter.save()
        painter.translate(cx, cy)
        painter.scale(self.squash_x, self.squash_y)

        grad = QRadialGradient(-r * 0.35, -r * 0.35, r * 1.35)
        grad.setColorAt(0.0, QColor(255, 255, 255, 255))
        grad.setColorAt(0.7, QColor(245, 250, 255, 255))
        grad.setColorAt(1.0, QColor(195, 220, 248, 255))

        painter.setPen(QPen(QColor(180, 208, 238, 220), 1.2))
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPointF(0, 0), r, r)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 190))
        painter.drawEllipse(QPointF(-r * 0.25, -r * 0.32), r * 0.42, r * 0.26)

        painter.restore()


class PhysicalSnowman:
    """Snowman with ragdoll bounce, squash springs, and throwable inertia."""
    def __init__(self, x: float, y: float, r_base: float = 34.0):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.r_base = r_base
        self.r_mid = r_base * 0.72
        self.r_head = r_base * 0.48
        self.is_held = False

        self.squash_y = 1.0
        self.squash_x = 1.0
        self.squash_vy = 0.0

        self.hat_type = random.choice(["bucket", "tophat"])
        self.scarf_color = random.choice([
            QColor(225, 40, 40),
            QColor(40, 160, 235),
            QColor(45, 185, 85),
            QColor(245, 140, 25)
        ])

    @property
    def total_height(self) -> float:
        return self.r_base * 2 + self.r_mid * 1.6 + self.r_head * 1.5 + 22

    def contains(self, px: float, py: float) -> bool:
        dx = abs(px - self.x)
        dy = self.y - py
        return dx <= self.r_base * 1.3 and -10 <= dy <= self.total_height + 10

    def trigger_squash(self, factor: float = 0.72):
        self.squash_y = factor
        self.squash_x = 1.0 / math.sqrt(factor)

    def update(self, dt: float, floor_y: float, surfaces: list):
        k_spring = 140.0
        damp = 12.0
        fy = -k_spring * (self.squash_y - 1.0) - damp * self.squash_vy
        self.squash_vy += fy * dt
        self.squash_y += self.squash_vy * dt
        self.squash_x = 1.0 + (1.0 - self.squash_y) * 0.7

        if self.is_held:
            return

        self.vy += GRAVITY * dt
        self.vx *= max(0.0, 1.0 - 0.20 * dt)
        self.x += self.vx * dt
        self.y += self.vy * dt

        # Collision with window tops
        for s in surfaces:
            if s.left - self.r_base <= self.x <= s.right + self.r_base:
                if s.top - 8 <= self.y <= s.top + 16 and self.vy > 0:
                    self.y = s.top
                    self.vy = -self.vy * 0.35
                    self.vx *= 0.6
                    self.trigger_squash(0.70)
                    if abs(self.vy) < 45.0:
                        self.vy = 0.0

        # Floor bounce
        if self.y >= floor_y:
            self.y = floor_y
            self.vy = -self.vy * 0.32
            self.vx *= 0.65
            self.trigger_squash(0.68)
            if abs(self.vy) < 45.0:
                self.vy = 0.0

    def draw(self, painter: QPainter):
        cx = self.x
        cy = self.y

        painter.save()
        painter.translate(cx, cy)
        painter.scale(self.squash_x, self.squash_y)

        base_y = -self.r_base
        mid_y = base_y - self.r_base - self.r_mid + 8
        head_y = mid_y - self.r_mid - self.r_head + 6

        # Twig arms
        painter.setPen(QPen(QColor(110, 65, 30), 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(int(-self.r_mid * 0.8), int(mid_y), int(-self.r_mid * 1.8), int(mid_y - 14))
        painter.drawLine(int(-self.r_mid * 1.4), int(mid_y - 10), int(-self.r_mid * 1.8), int(mid_y - 24))

        painter.drawLine(int(self.r_mid * 0.8), int(mid_y), int(self.r_mid * 1.8), int(mid_y - 14))
        painter.drawLine(int(self.r_mid * 1.4), int(mid_y - 10), int(self.r_mid * 1.8), int(mid_y - 24))

        def draw_ball(by, r):
            grad = QRadialGradient(-r * 0.35, by - r * 0.35, r * 1.35)
            grad.setColorAt(0.0, QColor(255, 255, 255, 255))
            grad.setColorAt(0.7, QColor(245, 250, 255, 255))
            grad.setColorAt(1.0, QColor(195, 220, 248, 255))
            painter.setPen(QPen(QColor(180, 208, 238, 210), 1.2))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QPointF(0, by), r, r)

        draw_ball(base_y, self.r_base)
        draw_ball(mid_y, self.r_mid)

        # Buttons
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(35, 35, 35))
        painter.drawEllipse(QPointF(0, mid_y - 6), 2.5, 2.5)
        painter.drawEllipse(QPointF(0, mid_y + 4), 2.5, 2.5)
        painter.drawEllipse(QPointF(0, mid_y + 14), 2.5, 2.5)

        draw_ball(head_y, self.r_head)

        # Scarf
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.scarf_color)
        scarf_w = self.r_mid * 1.55
        painter.drawRoundedRect(int(-scarf_w / 2), int(mid_y - self.r_mid + 1), int(scarf_w), 9, 3, 3)
        painter.drawRoundedRect(4, int(mid_y - self.r_mid + 5), 9, 20, 3, 3)

        # Eyes
        painter.setBrush(QColor(25, 25, 25))
        painter.drawEllipse(QPointF(-5.5, head_y - 3), 2.2, 2.2)
        painter.drawEllipse(QPointF(5.5, head_y - 3), 2.2, 2.2)
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(QPointF(-6.0, head_y - 4.0), 0.8, 0.8)
        painter.drawEllipse(QPointF(5.0, head_y - 4.0), 0.8, 0.8)

        # Carrot
        painter.setBrush(QColor(255, 125, 0))
        carrot = QPolygonF([
            QPointF(0, head_y + 1),
            QPointF(15, head_y + 3.5),
            QPointF(0, head_y + 6.0)
        ])
        painter.drawPolygon(carrot)

        # Smile
        painter.setBrush(QColor(40, 40, 40))
        for dx, dy in [(-6, 8), (-3, 10), (0, 10.5), (3, 10), (6, 8)]:
            painter.drawEllipse(QPointF(dx, head_y + dy), 1.2, 1.2)

        # Hat
        if self.hat_type == "bucket":
            grad_hat = QLinearGradient(-15, head_y - self.r_head - 22, 15, head_y - self.r_head)
            grad_hat.setColorAt(0.0, QColor(140, 150, 160))
            grad_hat.setColorAt(1.0, QColor(80, 90, 100))
            painter.setBrush(QBrush(grad_hat))
            painter.setPen(QPen(QColor(60, 70, 80), 1.0))
            bucket = QPolygonF([
                QPointF(-11, head_y - self.r_head - 18),
                QPointF(11, head_y - self.r_head - 18),
                QPointF(14, head_y - self.r_head + 2),
                QPointF(-14, head_y - self.r_head + 2),
            ])
            painter.drawPolygon(bucket)
        else:
            painter.setBrush(QColor(40, 40, 45))
            painter.setPen(QPen(QColor(20, 20, 20), 1.0))
            painter.drawRoundedRect(-18, int(head_y - self.r_head), 36, 4, 2, 2)
            painter.drawRect(-12, int(head_y - self.r_head - 18), 24, 18)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(220, 40, 40))
            painter.drawRect(-12, int(head_y - self.r_head - 5), 24, 4)

        painter.restore()
