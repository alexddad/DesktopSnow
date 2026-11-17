import math
import random
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

@dataclass
class Snowflake:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    alpha: float
    flake_type: int        # 0: dot, 1: soft circle, 2: crystal
    angle: float = 0.0
    rot_speed: float = 0.0
    sway_phase: float = 0.0
    sway_speed: float = 0.0
    sway_amp: float = 0.0
    state: str = "falling" # "falling", "settled", "dislodged"
    target_hwnd: int = 0
    rel_x: float = 0.0
    rel_y: float = 0.0
    life: float = 0.0
    max_life: float = 0.0

class SnowEngine:
    def __init__(self, screen_bounds: Tuple[int, int, int, int], max_flakes: int = 220):
        self.bounds = screen_bounds  # x, y, w, h
        self.max_flakes = max_flakes
        self.flakes: List[Snowflake] = []
        
        # Settings
        self.falling_snow_enabled = True
        self.snow_on_windows = True
        self.mouse_interaction = True
        self.cap_height_setting = 12.0  # Default fluffy height
        
        self.wind = 0.0
        self.target_wind = 0.0
        self.wind_timer = 0.0
        
        self.cursor_pos = (-1000, -1000)
        self.prev_cursor_pos = (-1000, -1000)
        self.cursor_speed = 0.0
        
        # Accumulation maps for window surfaces: hwnd -> list of heights
        # Each slice is 10px wide
        self.slice_width = 10
        self.window_snow_caps: Dict[int, List[float]] = {}
        self.window_target_caps: Dict[int, List[float]] = {}
        
        # Initialize flakes
        for _ in range(self.max_flakes):
            self.flakes.append(self._create_flake(random_y=True))

    def _create_flake(self, random_y: bool = False) -> Snowflake:
        sx, sy, sw, sh = self.bounds
        x = random.uniform(sx - 50, sx + sw + 50)
        y = random.uniform(sy, sy + sh) if random_y else random.uniform(sy - 60, sy - 5)
        
        # 3 types: 55% soft dot, 30% fluffy circle, 15% crystal
        r = random.random()
        if r < 0.55:
            flake_type = 0
            size = random.uniform(1.8, 3.0)
            vy = random.uniform(1.2, 2.0)
            alpha = random.uniform(130, 200)
        elif r < 0.85:
            flake_type = 1
            size = random.uniform(3.0, 4.8)
            vy = random.uniform(1.5, 2.6)
            alpha = random.uniform(170, 230)
        else:
            flake_type = 2
            size = random.uniform(5.5, 8.5)
            vy = random.uniform(1.7, 3.0)
            alpha = random.uniform(190, 255)

        return Snowflake(
            x=x,
            y=y,
            vx=random.uniform(-0.25, 0.25),
            vy=vy,
            size=size,
            alpha=alpha,
            flake_type=flake_type,
            angle=random.uniform(0, 360),
            rot_speed=random.uniform(-1.8, 1.8),
            sway_phase=random.uniform(0, math.pi * 2),
            sway_speed=random.uniform(0.02, 0.05),
            sway_amp=random.uniform(0.5, 1.6),
            state="falling"
        )

    def set_max_flakes(self, count: int):
        self.max_flakes = count
        if len(self.flakes) < count:
            for _ in range(count - len(self.flakes)):
                self.flakes.append(self._create_flake(random_y=True))
        elif len(self.flakes) > count:
            self.flakes = self.flakes[:count]

    def set_cap_height(self, height: float):
        self.cap_height_setting = height
        for hwnd in self.window_target_caps:
            self._generate_window_cap(hwnd, len(self.window_target_caps[hwnd]))

    def _generate_window_cap(self, hwnd: int, num_slices: int):
        """Generates natural undulating snow drift targets for a window."""
        targets = []
        caps = []
        freq = random.uniform(0.2, 0.4)
        offset = random.uniform(0, math.pi * 2)
        base = self.cap_height_setting
        for i in range(num_slices):
            wave = math.sin(i * freq + offset) * (base * 0.3)
            # Edge tapers slightly
            edge_factor = min(1.0, min(i, num_slices - 1 - i) / 3.0)
            h = max(3.0, (base + wave + random.uniform(-1.0, 1.0)) * edge_factor)
            targets.append(h)
            caps.append(h)
        self.window_target_caps[hwnd] = targets
        self.window_snow_caps[hwnd] = caps

    def clear_snow_caps(self):
        """Dislodges all snow caps into falling flakes."""
        for hwnd, caps in self.window_snow_caps.items():
            for i in range(len(caps)):
                caps[i] = 0.0
        for f in self.flakes:
            if f.state == "settled":
                f.state = "dislodged"
                f.vy = random.uniform(1.5, 3.5)
                f.vx = random.uniform(-1.0, 1.0)

    def update_cursor(self, mx: int, my: int):
        dx = mx - self.cursor_pos[0]
        dy = my - self.cursor_pos[1]
        self.cursor_speed = math.hypot(dx, dy)
        self.prev_cursor_pos = self.cursor_pos
        self.cursor_pos = (mx, my)

    def update(self, dt: float, surfaces: list, wind_mode: str = "light"):
        sx, sy, sw, sh = self.bounds
        screen_bottom = sy + sh
        screen_right = sx + sw

        # 1. Update wind
        self.wind_timer += dt
        if wind_mode == "none":
            self.wind = 0.0
        elif wind_mode == "light":
            if self.wind_timer > 3.0:
                self.wind_timer = 0.0
                self.target_wind = random.uniform(-0.7, 0.7)
            self.wind += (self.target_wind - self.wind) * (dt * 1.0)
        elif wind_mode == "gusty":
            if self.wind_timer > 2.0:
                self.wind_timer = 0.0
                self.target_wind = random.uniform(-2.5, 2.5)
            self.wind += (self.target_wind - self.wind) * (dt * 2.2)

        # Build surface lookup for collision
        surface_dict = {s.hwnd: s for s in surfaces}

        # Remove closed/hidden windows
        for hwnd in list(self.window_snow_caps.keys()):
            if hwnd not in surface_dict:
                del self.window_snow_caps[hwnd]
                if hwnd in self.window_target_caps:
                    del self.window_target_caps[hwnd]

        # Ensure all current windows have snow caps initialized!
        if self.snow_on_windows:
            for s in surfaces:
                num_slices = max(1, int(s.width // self.slice_width) + 1)
                if s.hwnd not in self.window_snow_caps or len(self.window_snow_caps[s.hwnd]) != num_slices:
                    self._generate_window_cap(s.hwnd, num_slices)

        # Slow snow regrowth / recovery towards natural target height
        for hwnd, caps in self.window_snow_caps.items():
            targets = self.window_target_caps.get(hwnd)
            if targets:
                for i in range(len(caps)):
                    if caps[i] < targets[i]:
                        caps[i] = min(targets[i], caps[i] + 0.4 * dt)

        # Dislodge snow if window is moved quickly
        for s in surfaces:
            win_speed = math.hypot(s.vx, s.vy)
            if win_speed > 14.0 and s.hwnd in self.window_snow_caps:
                caps = self.window_snow_caps[s.hwnd]
                for idx in range(len(caps)):
                    if caps[idx] > 1.0 and random.random() < 0.22:
                        caps[idx] = max(0.0, caps[idx] - 2.0)
                        if random.random() < 0.35 and len(self.flakes) < self.max_flakes + 40:
                            spawn_x = s.left + idx * self.slice_width + random.uniform(0, self.slice_width)
                            spawn_y = s.top - caps[idx]
                            fl = self._create_flake(random_y=False)
                            fl.x = spawn_x
                            fl.y = spawn_y
                            fl.vx = -s.vx * 0.12 + random.uniform(-1.0, 1.0)
                            fl.vy = random.uniform(1.5, 4.0)
                            fl.state = "dislodged"
                            self.flakes.append(fl)

        # Mouse brush interaction with snow caps
        mx, my = self.cursor_pos
        if self.mouse_interaction and mx > -500:
            for s in surfaces:
                if s.hwnd in self.window_snow_caps:
                    # If cursor is near top edge of window
                    if abs(my - s.top) < 28 and (s.left - 15 <= mx <= s.right + 15):
                        caps = self.window_snow_caps[s.hwnd]
                        rel_m = mx - s.left
                        center_idx = int(rel_m // self.slice_width)
                        brush_rad = 4
                        for idx in range(max(0, center_idx - brush_rad), min(len(caps), center_idx + brush_rad + 1)):
                            if caps[idx] > 0.5:
                                # Brush creates falling flakes!
                                if random.random() < 0.25 and len(self.flakes) < self.max_flakes + 40:
                                    spawn_x = s.left + idx * self.slice_width + random.uniform(0, self.slice_width)
                                    spawn_y = s.top - caps[idx]
                                    f = self._create_flake(random_y=False)
                                    f.x = spawn_x
                                    f.y = spawn_y
                                    f.vx = random.uniform(-1.5, 1.5)
                                    f.vy = random.uniform(1.5, 3.8)
                                    f.state = "dislodged"
                                    self.flakes.append(f)
                                caps[idx] = max(0.0, caps[idx] - 1.5)

        # 2. Update flakes (only if falling snow is enabled or flakes are dislodged)
        for f in self.flakes:
            if f.state == "settled":
                s = surface_dict.get(f.target_hwnd)
                if s is None:
                    # Window closed or minimized -> dislodge!
                    f.state = "dislodged"
                    f.vy = random.uniform(1.2, 3.0)
                    f.vx = random.uniform(-0.8, 0.8)
                    continue

                # Dislodge if window moved fast
                win_speed = math.hypot(s.vx, s.vy)
                if win_speed > 16.0 and random.random() < 0.35:
                    f.state = "dislodged"
                    f.vx = -s.vx * 0.15 + random.uniform(-1.0, 1.0)
                    f.vy = random.uniform(1.5, 4.0)
                    continue

                # Lock to surface position
                f.x = s.left + f.rel_x
                f.y = s.top + f.rel_y

                # Countdown life
                f.life -= dt
                if f.life <= 0:
                    self._reset_flake(f)
                    continue
                elif f.life < 3.0:
                    f.alpha = max(0.0, (f.life / 3.0) * 200.0)

                # Mouse brush interaction with settled flakes
                if self.mouse_interaction and mx > -500:
                    dist = math.hypot(f.x - mx, f.y - my)
                    if dist < 32:
                        f.state = "dislodged"
                        kick = (32 - dist) / 32.0
                        f.vx = (f.x - mx) * 0.1 * kick + random.uniform(-1, 1)
                        f.vy = random.uniform(1.0, 3.5)

            elif f.state in ("falling", "dislodged"):
                # Movement physics
                f.sway_phase += f.sway_speed
                sway = math.sin(f.sway_phase) * f.sway_amp
                f.x += f.vx + self.wind + sway
                f.y += f.vy
                f.angle += f.rot_speed

                # Mouse repulsion
                if self.mouse_interaction and mx > -500:
                    dist = math.hypot(f.x - mx, f.y - my)
                    if dist < 60 and dist > 0.1:
                        force = (60 - dist) / 60.0
                        nx = (f.x - mx) / dist
                        ny = (f.y - my) / dist
                        f.x += nx * force * 3.5
                        f.y += ny * force * 1.8

                # Collision check ONLY with window tops
                landed = False
                if self.snow_on_windows:
                    for s in surfaces:
                        if s.left <= f.x <= s.right:
                            cap_height = 0.0
                            slice_idx = int((f.x - s.left) // self.slice_width)
                            if s.hwnd in self.window_snow_caps:
                                caps = self.window_snow_caps[s.hwnd]
                                if 0 <= slice_idx < len(caps):
                                    cap_height = caps[slice_idx]

                            landing_y = s.top - cap_height

                            # Did flake hit the top edge or snow cap?
                            if landing_y - 3 <= f.y <= landing_y + 5 and f.vy > 0:
                                if random.random() < 0.65:
                                    f.state = "settled"
                                    f.target_hwnd = s.hwnd
                                    f.rel_x = f.x - s.left
                                    f.rel_y = -cap_height + random.uniform(-1, 1)
                                    f.max_life = random.uniform(15.0, 35.0)
                                    f.life = f.max_life

                                    if s.hwnd in self.window_snow_caps:
                                        caps = self.window_snow_caps[s.hwnd]
                                        if 0 <= slice_idx < len(caps):
                                            if caps[slice_idx] < self.cap_height_setting + 4.0:
                                                caps[slice_idx] += random.uniform(0.4, 0.8)

                                    landed = True
                                    break

                # Wrap around screen
                if not landed:
                    if f.y > screen_bottom + 20:
                        self._reset_flake(f)
                    elif f.x < sx - 100:
                        f.x = screen_right + 30
                    elif f.x > screen_right + 100:
                        f.x = sx - 30

    def _reset_flake(self, f: Snowflake):
        sx, sy, sw, sh = self.bounds
        f.x = random.uniform(sx - 50, sx + sw + 50)
        f.y = random.uniform(sy - 40, sy - 5)
        f.state = "falling"
        r = random.random()
        if r < 0.55:
            f.flake_type = 0
            f.size = random.uniform(1.8, 3.0)
            f.vy = random.uniform(1.2, 2.0)
            f.alpha = random.uniform(130, 200)
        elif r < 0.85:
            f.flake_type = 1
            f.size = random.uniform(3.0, 4.8)
            f.vy = random.uniform(1.5, 2.6)
            f.alpha = random.uniform(170, 230)
        else:
            f.flake_type = 2
            f.size = random.uniform(5.5, 8.5)
            f.vy = random.uniform(1.7, 3.0)
            f.alpha = random.uniform(190, 255)
        f.life = 0.0
