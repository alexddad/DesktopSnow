import ctypes
from ctypes import wintypes
import time
import math
import random
from typing import Dict, List, Tuple, Optional

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient, QCursor
)
from PyQt6.QtCore import Qt, QTimer, QPointF

from window_tracker import WindowTracker, WindowSurface
from garland import GarlandRenderer
from decor import DecorRenderer
from physics_snow import (
    SnowChunk, SnowDust, SnowFlakeParticle, PhysicalSnowball, PhysicalSnowman, SpriteCache
)

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080

HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

VK_LBUTTON = 0x01
VK_CONTROL = 0x11
DWMWA_EXTENDED_FRAME_BOUNDS = 9


class SnowOverlayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.screen_x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        self.screen_y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        self.screen_w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        self.screen_h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        self.floor_y = float(self.screen_y + self.screen_h - 10)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus |
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.setGeometry(self.screen_x, self.screen_y, self.screen_w, self.screen_h)

        self.bounds = (self.screen_x, self.screen_y, self.screen_w, self.screen_h)
        self.tracker = WindowTracker()
        self.surfaces: List[WindowSurface] = []
        self.active_window_rects: Dict[int, Tuple[float, float, float, float]] = {}

        # Localized snow heightmap per window
        self.snow_height = 10.0
        self.slice_step = 10.0
        self.window_profiles: Dict[int, List[float]] = {}
        self.target_profiles: Dict[int, List[float]] = {}

        self.paused = False
        self.anim_phase = 0.0

        # Новогодняя гирлянда на окнах
        self.garland = GarlandRenderer()
        self.decor = DecorRenderer(self.garland)  # ёлочка, подарки, блёстки

        # High-performance particle pools
        self.chunks: List[SnowChunk] = []
        self.dust: List[SnowDust] = []
        self.flakes: List[SnowFlakeParticle] = []

        # Snowballs & Snowmen with physics
        self.snowballs: List[PhysicalSnowball] = []
        self.snowmen: List[PhysicalSnowman] = []
        self.held_snowball: Optional[PhysicalSnowball] = None
        self.held_snowman: Optional[PhysicalSnowman] = None
        self.drag_offset = (0.0, 0.0)

        # Mouse velocity history
        self.prev_lbutton = False
        self.mouse_history: List[Tuple[float, float, float]] = []

        self.last_time = time.perf_counter()

        # Initialize sprite cache
        SpriteCache.init()

        # 60 FPS update timer
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self._on_frame)
        self.render_timer.start(16)

        # Window scan timer
        self.window_timer = QTimer(self)
        self.window_timer.timeout.connect(self._on_full_window_scan)
        self.window_timer.start(200)

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_win32_click_through()
        self.tracker.add_ignore_hwnd(int(self.winId()))

    def _apply_win32_click_through(self):
        hwnd = int(self.winId())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            hwnd,
            GWL_EXSTYLE,
            style | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        )
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
        )

    def _ensure_window_profile(self, hwnd: int, win_w: float) -> List[float]:
        num_slices = max(2, int(win_w / self.slice_step))
        if hwnd not in self.window_profiles or len(self.window_profiles[hwnd]) != num_slices:
            profile = []
            targets = []
            seed = (hwnd % 100) * 0.1
            for i in range(num_slices):
                wave = math.sin(i * 0.32 + seed) * (self.snow_height * 0.28)
                edge_factor = min(1.0, min(i, num_slices - 1 - i) / 2.0 + 0.3)
                h = max(3.0, (self.snow_height + wave) * edge_factor)
                profile.append(h)
                targets.append(h)
            self.window_profiles[hwnd] = profile
            self.target_profiles[hwnd] = targets
        return self.window_profiles[hwnd]

    def add_preset_snowman(self, x: Optional[float] = None, y: Optional[float] = None):
        if x is None or y is None:
            if self.surfaces:
                s = self.surfaces[0]
                x = s.left + s.width * 0.75
                y = s.top
            else:
                x = self.screen_w - 200
                y = self.screen_h - 60
        sm = PhysicalSnowman(x, y, r_base=34.0)
        sm.trigger_squash(0.60)
        self.snowmen.append(sm)
        self._spawn_dust_burst(x, y - 40, count=20)
        self.update()

    def clear_all_snowmen(self):
        self.snowmen.clear()
        self.snowballs.clear()
        self.held_snowball = None
        self.held_snowman = None
        self.update()

    def refill_all_snow(self):
        for s in self.surfaces:
            self._ensure_window_profile(s.hwnd, s.width)
            self.window_profiles[s.hwnd] = list(self.target_profiles[s.hwnd])
        self.update()

    def _spawn_dust_burst(self, x: float, y: float, count: int = 12, speed_mult: float = 1.0):
        if len(self.dust) > 70:
            return
        for _ in range(count):
            ang = random.uniform(0, math.pi * 2)
            spd = random.uniform(80, 220) * speed_mult
            self.dust.append(SnowDust(
                x, y,
                math.cos(ang) * spd,
                math.sin(ang) * spd,
                size=random.uniform(1.8, 2.8)
            ))

    def _spawn_movement_particles(self, s: WindowSurface, speed: float, dx: float, dy: float, is_hard_shake: bool = False):
        """Spawns visible, dynamic snow particles while dragging or shaking windows."""
        win_w = s.right - s.left
        profile = self.window_profiles.get(s.hwnd)

        # Count of particles
        if is_hard_shake:
            num_chunks = min(25, max(8, int(win_w / 35)))
            num_dust = min(35, max(12, int(win_w / 20)))
            num_flakes = min(18, max(6, int(win_w / 30)))
        else:
            num_chunks = min(8, max(2, int(speed * 0.4)))
            num_dust = min(16, max(4, int(speed * 0.8)))
            num_flakes = min(8, max(2, int(speed * 0.4)))

        # Cap total particles
        if len(self.chunks) > 55:
            num_chunks = 2
        if len(self.dust) > 65:
            num_dust = 4

        # Inertia opposite to window movement direction
        inv_vx = -dx * 12.0
        inv_vy = -dy * 12.0

        for _ in range(num_chunks):
            px = random.uniform(s.left, s.right)
            # Find height at this px
            idx = int((px - s.left) / self.slice_step)
            py = s.top
            if profile and 0 <= idx < len(profile):
                py -= profile[idx]

            self.chunks.append(SnowChunk(
                px, py + random.uniform(-2, 2),
                inv_vx * random.uniform(0.3, 0.7) + random.uniform(-70, 70),
                inv_vy * random.uniform(0.3, 0.7) + random.uniform(60, 200),
                size=random.uniform(4.5, 9.0)
            ))

        for _ in range(num_dust):
            px = random.uniform(s.left, s.right)
            self.dust.append(SnowDust(
                px, s.top + random.uniform(-4, 2),
                inv_vx * random.uniform(0.4, 0.9) + random.uniform(-120, 120),
                inv_vy * random.uniform(0.4, 0.9) + random.uniform(30, 160),
                size=random.uniform(1.6, 2.8)
            ))

        for _ in range(num_flakes):
            px = random.uniform(s.left, s.right)
            self.flakes.append(SnowFlakeParticle(
                px, s.top + random.uniform(-3, 2),
                inv_vx * 0.2 + random.uniform(-50, 50),
                random.uniform(90, 220),
                size=random.uniform(2.5, 4.5)
            ))

        # Reduce snow on window
        if profile:
            loss = random.uniform(2.5, 5.0) if is_hard_shake else speed * 0.05
            for i in range(len(profile)):
                profile[i] = max(0.0, profile[i] - loss)

    def _fast_track_active_window(self):
        """Tracks the foreground window every frame and triggers movement particles."""
        fg_hwnd = user32.GetForegroundWindow()
        if not fg_hwnd:
            return

        for s in self.surfaces:
            if s.hwnd == fg_hwnd:
                rect = wintypes.RECT()
                res = dwmapi.DwmGetWindowAttribute(fg_hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect))
                if res == 0 and rect.right - rect.left > 100:
                    new_left = rect.left
                    new_top = max(0, rect.top)
                    dx = new_left - s.left
                    dy = new_top - s.top
                    speed = math.hypot(dx, dy)

                    if speed > 2.0:
                        ax = dx - s.vx
                        ay = dy - s.vy
                        accel = math.hypot(ax, ay)

                        is_hard_shake = (accel > 8.0 or speed > 15.0)
                        self._spawn_movement_particles(s, speed, dx, dy, is_hard_shake=is_hard_shake)

                        s.vx = float(dx)
                        s.vy = float(dy)
                        s.ax = float(ax)
                        s.ay = float(ay)
                        s.left = new_left
                        s.top = new_top
                        s.right = rect.right
                        s.bottom = rect.bottom
                    else:
                        s.vx *= 0.5
                        s.vy *= 0.5
                        s.ax = 0.0
                        s.ay = 0.0
                break

    def _on_full_window_scan(self):
        """Scans for opened/closed windows periodically."""
        try:
            new_surfaces = self.tracker.get_visible_surfaces(self.bounds)
            cur_rects = {s.hwnd: (float(s.left), float(s.top), float(s.right), float(s.bottom)) for s in new_surfaces}

            for s in new_surfaces:
                self._ensure_window_profile(s.hwnd, s.width)

            # Check closed/minimized windows -> smooth cascade
            for hwnd, (prev_l, prev_t, prev_r, prev_b) in self.active_window_rects.items():
                if hwnd not in cur_rects:
                    win_w = prev_r - prev_l
                    num_chunks = min(20, max(5, int(win_w / 35)))
                    for _ in range(num_chunks):
                        px = random.uniform(prev_l, prev_r)
                        self.chunks.append(SnowChunk(px, prev_t, random.uniform(-40, 40), random.uniform(80, 200), size=random.uniform(5.0, 9.0)))
                    for _ in range(25):
                        px = random.uniform(prev_l, prev_r)
                        self.dust.append(SnowDust(px, prev_t, random.uniform(-80, 80), random.uniform(30, 150)))

                    if hwnd in self.window_profiles:
                        del self.window_profiles[hwnd]
                    if hwnd in self.target_profiles:
                        del self.target_profiles[hwnd]

            self.surfaces = new_surfaces
            self.active_window_rects = cur_rects
        except Exception:
            pass

    def _on_frame(self):
        now = time.perf_counter()
        dt = min(0.033, max(0.001, now - self.last_time))
        self.last_time = now

        if self.paused:
            return

        self.anim_phase += 0.05
        if self.anim_phase > math.pi * 2:
            self.anim_phase -= math.pi * 2

        # Ensure active foreground window is at index 0 (top-most in Z-order)
        fg_hwnd = user32.GetForegroundWindow()
        if fg_hwnd and self.surfaces:
            for i, s in enumerate(self.surfaces):
                if s.hwnd == fg_hwnd:
                    if i > 0:
                        self.surfaces.insert(0, self.surfaces.pop(i))
                    break

        # Fast tracking of moving active window
        self._fast_track_active_window()

        # 1. Update Chunks & check collision with lower windows
        for c in list(self.chunks):
            alive = c.update(dt)
            if not alive or c.y > self.floor_y:
                self.chunks.remove(c)
                continue

            for s in self.surfaces:
                if s.left <= c.x <= s.right and abs(c.y - s.top) <= 10.0 and c.vy > 0:
                    self._spawn_dust_burst(c.x, s.top, count=4, speed_mult=0.5)
                    profile = self.window_profiles.get(s.hwnd)
                    if profile:
                        idx = int((c.x - s.left) / self.slice_step)
                        if 0 <= idx < len(profile):
                            profile[idx] = min(self.snow_height + 3.0, profile[idx] + 1.6)
                    self.chunks.remove(c)
                    break

        # 2. Update Dust
        for d in list(self.dust):
            if not d.update(dt):
                self.dust.remove(d)

        # 3. Update Flakes
        for f in list(self.flakes):
            alive = f.update(dt)
            if not alive or f.y > self.floor_y:
                self.flakes.remove(f)
                continue

            for s in self.surfaces:
                if s.left <= f.x <= s.right and abs(f.y - s.top) <= 8.0 and f.vy > 0:
                    profile = self.window_profiles.get(s.hwnd)
                    if profile:
                        idx = int((f.x - s.left) / self.slice_step)
                        if 0 <= idx < len(profile):
                            profile[idx] = min(self.snow_height + 3.0, profile[idx] + 0.6)
                    self.flakes.remove(f)
                    break

        # 4. Slow natural regrowth (~50s)
        for s in self.surfaces:
            profile = self.window_profiles.get(s.hwnd)
            targets = self.target_profiles.get(s.hwnd)
            if profile and targets and len(profile) == len(targets):
                for i in range(len(profile)):
                    if profile[i] < targets[i]:
                        profile[i] = min(targets[i], profile[i] + 0.15 * dt)

        # 5. Update Snowballs
        debris_total = []
        for b in list(self.snowballs):
            debris = b.update(dt, self.floor_y, self.surfaces)
            debris_total.extend(debris)
            if b.is_broken:
                self._spawn_dust_burst(b.x, b.y, count=24, speed_mult=1.3)
                self.snowballs.remove(b)
        self.chunks.extend(debris_total[:8])

        # 6. Update Snowmen
        for sm in self.snowmen:
            sm.update(dt, self.floor_y, self.surfaces)

        # 7. Mouse interaction
        self._handle_mouse(dt, now)

        # 8. Garland animation
        self.garland.update(dt, self.surfaces)
        self.decor.update(dt)

        self.update()

    def _handle_mouse(self, dt: float, now: float):
        pos = QCursor.pos()
        mx, my = float(pos.x()), float(pos.y())
        lbutton = (user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000) != 0
        ctrl = (user32.GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0

        self.mouse_history.append((now, mx, my))
        self.mouse_history = [(t, x, y) for (t, x, y) in self.mouse_history if now - t <= 0.16]

        def get_mouse_velocity():
            if len(self.mouse_history) < 2:
                return (0.0, 0.0)
            t_old, x_old, y_old = self.mouse_history[0]
            t_new, x_new, y_new = self.mouse_history[-1]
            dt_m = max(0.01, t_new - t_old)
            return ((x_new - x_old) / dt_m, (y_new - y_old) / dt_m)

        def scoop_local_snow(target_s, px: float, scoop_radius: float, scoop_amount: float) -> float:
            profile = self.window_profiles.get(target_s.hwnd)
            if not profile:
                return 0.0

            rel_x = px - target_s.left
            center_idx = int(rel_x / self.slice_step)
            r_slices = max(2, int(scoop_radius / self.slice_step))

            total_scooped = 0.0
            num_slices = len(profile)

            for idx in range(max(0, center_idx - r_slices), min(num_slices, center_idx + r_slices + 1)):
                dist = abs((idx - center_idx) * self.slice_step)
                if dist <= scoop_radius:
                    falloff = math.cos((dist / max(1.0, scoop_radius)) * (math.pi / 2))
                    req = scoop_amount * falloff
                    actual = min(profile[idx], req)
                    profile[idx] -= actual
                    total_scooped += actual

                    if actual > 0.3 and random.random() < 0.25 and len(self.dust) < 50:
                        slice_x = target_s.left + idx * self.slice_step
                        self.dust.append(SnowDust(
                            slice_x, target_s.top - profile[idx],
                            random.uniform(-20, 20), random.uniform(-30, 10),
                            size=random.uniform(1.4, 2.2)
                        ))

            return total_scooped

        # Mouse Just Pressed
        if lbutton and not self.prev_lbutton:
            clicked_sm = None
            for sm in reversed(self.snowmen):
                if sm.contains(mx, my):
                    clicked_sm = sm
                    break

            if clicked_sm:
                self.held_snowman = clicked_sm
                clicked_sm.is_held = True
                self.drag_offset = (mx - clicked_sm.x, my - clicked_sm.y)
            else:
                clicked_ball = None
                for b in reversed(self.snowballs):
                    if math.hypot(mx - b.x, my - b.y) <= b.radius + 8:
                        clicked_ball = b
                        break

                if clicked_ball:
                    self.held_snowball = clicked_ball
                    clicked_ball.is_held = True
                    self.drag_offset = (mx - clicked_ball.x, my - clicked_ball.y)
                else:
                    target_s = None
                    for s in self.surfaces:
                        if s.left - 15 <= mx <= s.right + 15 and s.top - 22 <= my <= s.top + 8:
                            target_s = s
                            break

                    if target_s is None and ctrl:
                        for s in self.surfaces:
                            if s.left - 10 <= mx <= s.right + 10:
                                target_s = s
                                break

                    if target_s is not None:
                        scooped = scoop_local_snow(target_s, mx, scoop_radius=22.0, scoop_amount=4.5)
                        if scooped > 0.8:
                            new_ball = PhysicalSnowball(mx, my, radius=13.0)
                            new_ball.is_held = True
                            self.snowballs.append(new_ball)
                            self.held_snowball = new_ball
                            self.drag_offset = (0.0, 0.0)
                            self._spawn_dust_burst(mx, my, count=10)

        # Mouse Dragging
        elif lbutton and self.prev_lbutton:
            if self.held_snowman:
                self.held_snowman.x = mx - self.drag_offset[0]
                self.held_snowman.y = my - self.drag_offset[1]
                self.held_snowman.vx, self.held_snowman.vy = get_mouse_velocity()

            elif self.held_snowball:
                b = self.held_snowball
                dx = mx - b.x
                dy = my - b.y
                dist = math.hypot(dx, dy)
                b.x = mx - self.drag_offset[0]
                b.y = my - self.drag_offset[1]
                b.vx, b.vy = get_mouse_velocity()

                for s in self.surfaces:
                    if s.left - 20 <= mx <= s.right + 20 and abs(my - s.top) <= 28:
                        scoop_r = b.radius + 6.0
                        scooped = scoop_local_snow(s, mx, scoop_radius=scoop_r, scoop_amount=dist * 0.12)
                        if b.radius < 36.0:
                            b.radius = min(36.0, b.radius + scooped * 0.06)

        # Mouse Released -> THROW
        elif not lbutton and self.prev_lbutton:
            mvx, mvy = get_mouse_velocity()

            if self.held_snowman:
                sm = self.held_snowman
                sm.is_held = False
                sm.vx = mvx * 1.05
                sm.vy = mvy * 1.05
                self.held_snowman = None

            elif self.held_snowball:
                b = self.held_snowball
                b.is_held = False
                b.vx = mvx * 1.15
                b.vy = mvy * 1.15
                self.held_snowball = None

                for other in list(self.snowballs):
                    if other is b:
                        continue
                    dist = math.hypot(b.x - other.x, b.y - other.y)
                    if dist <= (b.radius + other.radius) * 1.35 and math.hypot(mvx, mvy) < 300.0:
                        larger = b if b.radius >= other.radius else other
                        smaller = other if b.radius >= other.radius else b

                        if b in self.snowballs:
                            self.snowballs.remove(b)
                        if other in self.snowballs:
                            self.snowballs.remove(other)

                        sm_x = larger.x
                        sm_y = max(larger.y + larger.radius, smaller.y + smaller.radius)
                        new_sm = PhysicalSnowman(sm_x, sm_y, r_base=max(30.0, larger.radius))
                        new_sm.trigger_squash(0.60)
                        self.snowmen.append(new_sm)
                        self._spawn_dust_burst(sm_x, sm_y - 40, count=25, speed_mult=1.2)
                        break

        self.prev_lbutton = lbutton

    def _get_visible_top_intervals(self, idx: int) -> List[Tuple[float, float]]:
        """Calculates visible (unoccluded) segments of window idx's top edge, clipped by windows in front."""
        s = self.surfaces[idx]
        intervals = [(float(s.left), float(s.right))]

        # All windows with j < idx are IN FRONT of window s in Z-order
        for j in range(idx):
            front = self.surfaces[j]
            # Check if front window covers s.top vertically
            if front.top - 2 <= s.top <= front.bottom + 2:
                cut_l = float(front.left)
                cut_r = float(front.right)
                new_intervals = []
                for l, r in intervals:
                    if cut_r <= l or cut_l >= r:
                        new_intervals.append((l, r))
                    else:
                        if cut_l > l:
                            new_intervals.append((l, cut_l))
                        if cut_r < r:
                            new_intervals.append((cut_r, r))
                intervals = new_intervals

        # Only keep intervals with width >= 25px
        return [it for it in intervals if it[1] - it[0] >= 25.0]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Draw snow ONLY on unoccluded, visible parts of active windows
        for idx, s in enumerate(self.surfaces):
            self._draw_window_snow(painter, s, idx)
            self._draw_window_decor(painter, s, idx)
            self._draw_window_garland(painter, s, idx)

        # 2. Draw Dust (fast flat rectangles)
        for d in self.dust:
            d.draw(painter)

        # 3. Draw Flakes (pre-rendered)
        for f in self.flakes:
            f.draw(painter)

        # 4. Draw Heavy Chunks (pre-rendered pixmaps!)
        for c in self.chunks:
            c.draw(painter)

        # 5. Draw Snowballs
        for b in self.snowballs:
            b.draw(painter)

        # 6. Draw Snowmen
        for sm in self.snowmen:
            sm.draw(painter)

        painter.end()

    def _draw_window_decor(self, painter: QPainter, s: WindowSurface, idx: int):
        if (self.decor.tree_fade < 0.02 and self.decor.sparkle_fade < 0.02) or s.width < 160:
            return
        intervals = self._get_visible_top_intervals(idx)
        if not intervals:
            return
        profile = self._ensure_window_profile(s.hwnd, s.width)
        slant_x = max(-10.0, min(10.0, -s.vx * 0.5))
        self.decor.draw(painter, s, profile, self.slice_step, intervals, slant_x)

    def _draw_window_garland(self, painter: QPainter, s: WindowSurface, idx: int):
        if self.garland.fade < 0.02 or s.width < 160:
            return
        intervals = self._get_visible_top_intervals(idx)
        if not intervals:
            return
        profile = self._ensure_window_profile(s.hwnd, s.width)
        slant_x = max(-10.0, min(10.0, -s.vx * 0.5))
        self.garland.draw(painter, s, profile, self.slice_step, intervals, slant_x)

    def _draw_window_snow(self, painter: QPainter, s: WindowSurface, idx: int):
        left = float(s.left)
        right = float(s.right)
        top = float(s.top)
        win_w = right - left

        if win_w < 80:
            return

        # CLIP OUT ANY PARTS OF THE TOP EDGE COVERED BY WINDOWS IN FRONT!
        visible_intervals = self._get_visible_top_intervals(idx)
        if not visible_intervals:
            return  # The entire top edge is covered by a window in front! Nothing to draw!

        profile = self._ensure_window_profile(s.hwnd, win_w)
        num_slices = len(profile)

        slant_x = max(-10.0, min(10.0, -s.vx * 0.5))

        for int_l, int_r in visible_intervals:
            # Find slices within this visible interval
            slice_start = max(0, int((int_l - left) / self.slice_step))
            slice_end = min(num_slices - 1, int((int_r - left) / self.slice_step))

            if slice_end <= slice_start:
                continue

            # Find contiguous segments where snow actually exists (h > 0.8)
            segments: List[Tuple[int, int]] = []
            cur_start = None
            for i in range(slice_start, slice_end + 1):
                if profile[i] > 0.8:
                    if cur_start is None:
                        cur_start = i
                else:
                    if cur_start is not None:
                        segments.append((cur_start, i - 1))
                        cur_start = None
            if cur_start is not None:
                segments.append((cur_start, slice_end))

            for seg_start, seg_end in segments:
                x_start = left + seg_start * self.slice_step + slant_x
                x_end = left + seg_end * self.slice_step + slant_x

                path = QPainterPath()
                path.moveTo(x_start, top)

                for i in range(seg_start, seg_end + 1):
                    px = left + i * self.slice_step + slant_x
                    py = top - profile[i]

                    if i == seg_start:
                        path.lineTo(px, py)
                    else:
                        prev_x = left + (i - 1) * self.slice_step + slant_x
                        prev_y = top - profile[i - 1]
                        cpx = (prev_x + px) / 2.0
                        path.quadTo(prev_x, prev_y, cpx, (prev_y + py) / 2.0)

                path.lineTo(x_end, top)

                for i in range(seg_end, seg_start - 1, -1):
                    px = left + i * self.slice_step
                    h = profile[i]
                    droop = (3.0 if ((i + s.hwnd) % 3 == 0) else 1.8) if h > 2.5 else 0.0
                    path.lineTo(px, top + droop)

                path.closeSubpath()

                max_seg_h = max(profile[seg_start:seg_end + 1])
                grad = QLinearGradient(x_start, top - max_seg_h - 4, x_start, top + 4)
                grad.setColorAt(0.0, QColor(255, 255, 255, 255))
                grad.setColorAt(0.65, QColor(248, 252, 255, 250))
                grad.setColorAt(0.88, QColor(230, 242, 255, 240))
                grad.setColorAt(1.0, QColor(210, 228, 248, 220))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(grad))
                painter.drawPath(path)

                # Top highlight stroke (only on top snow surface!)
                highlight_path = QPainterPath()
                highlight_path.moveTo(x_start, top)
                for i in range(seg_start, seg_end + 1):
                    px = left + i * self.slice_step + slant_x
                    py = top - profile[i]
                    if i == seg_start:
                        highlight_path.lineTo(px, py)
                    else:
                        prev_x = left + (i - 1) * self.slice_step + slant_x
                        prev_y = top - profile[i - 1]
                        cpx = (prev_x + px) / 2.0
                        highlight_path.quadTo(prev_x, prev_y, cpx, (prev_y + py) / 2.0)
                highlight_path.lineTo(x_end, top)

                painter.setPen(QPen(QColor(255, 255, 255, 230), 1.0))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(highlight_path)

                # Soft puffs on peaks
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 180))
                for i in range(seg_start + 1, seg_end, 3):
                    if profile[i] > 6.5:
                        puff_x = left + i * self.slice_step + slant_x * 0.6
                        puff_y = top - profile[i] + 1.5
                        painter.drawEllipse(QPointF(puff_x, puff_y), 4.5, 2.5)
