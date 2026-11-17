import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

try:
    h_default = user32.OpenDesktopW("default", 0, False, 0x01FF)
    if h_default:
        user32.SetThreadDesktop(h_default)
except Exception:
    pass

DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14

@dataclass
class WindowSurface:
    hwnd: int
    title: str
    left: int
    top: int
    right: int
    bottom: int
    vx: float = 0.0
    vy: float = 0.0
    ax: float = 0.0
    ay: float = 0.0
    
    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


class WindowTracker:
    def __init__(self, ignore_hwnds: Optional[List[int]] = None):
        self.ignore_hwnds = set(ignore_hwnds or [])
        self.prev_positions: Dict[int, Tuple[int, int]] = {}
        self.prev_velocities: Dict[int, Tuple[float, float]] = {}

    def add_ignore_hwnd(self, hwnd: int):
        self.ignore_hwnds.add(hwnd)

    def get_visible_surfaces(self, screen_bounds: Tuple[int, int, int, int]) -> List[WindowSurface]:
        surfaces: List[WindowSurface] = []
        sx, sy, sw, sh = screen_bounds
        screen_right = sx + sw
        screen_bottom = sy + sh

        def enum_window_callback(hwnd, lparam):
            if hwnd in self.ignore_hwnds:
                return True
            if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                return True

            # Check if cloaked (hidden virtual desktop or suspended UWP app)
            cloaked = ctypes.c_int(0)
            res_cloaked = dwmapi.DwmGetWindowAttribute(
                hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
            )
            if res_cloaked == 0 and cloaked.value != 0:
                return True

            # Check class name
            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            class_name = class_buf.value

            # Strictly ignore system UI, docks, dynamic islands, taskbars, wallpaper
            ignored_substrings = (
                "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                "DynamicIsland", "Atoll", "Windows.UI.Core.CoreWindow",
                "ApplicationFrameWindow_Child"
            )
            for ign in ignored_substrings:
                if ign.lower() in class_name.lower():
                    return True

            # Get title
            length = user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value

            # Ignore our own overlay or empty titles
            if not title.strip() or "DesktopSnow" in title or "SnowOverlay" in title:
                return True
            if "Atoll" in title:
                return True

            # Get bounds
            rect = wintypes.RECT()
            res = dwmapi.DwmGetWindowAttribute(
                hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)
            )
            if res != 0 or rect.right - rect.left <= 0:
                user32.GetWindowRect(hwnd, ctypes.byref(rect))

            left = rect.left
            top = rect.top
            right = rect.right
            bottom = rect.bottom
            width = right - left
            height = bottom - top

            # Filter out small utilities
            if width < 300 or height < 200:
                return True

            # Filter out top docks (e.g. top=0 and height < 400)
            if top <= 0 and height < 400:
                return True

            # Filter out full desktop backgrounds
            if left <= sx and top <= sy and right >= screen_right and bottom >= screen_bottom:
                if not title.strip() or title == "Program Manager":
                    return True

            # Filter out off-screen windows
            if right <= sx or left >= screen_right or bottom <= sy or top >= screen_bottom:
                return True

            effective_top = max(0, top)

            surfaces.append(WindowSurface(
                hwnd=hwnd,
                title=title,
                left=left,
                top=effective_top,
                right=right,
                bottom=bottom
            ))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_window_callback), 0)

        # Calculate accurate velocity and acceleration
        cur_positions = {}
        cur_velocities = {}
        for s in surfaces:
            cur_positions[s.hwnd] = (s.left, s.top)
            if s.hwnd in self.prev_positions:
                prev_x, prev_y = self.prev_positions[s.hwnd]
                vx = float(s.left - prev_x)
                vy = float(s.top - prev_y)
                s.vx = vx
                s.vy = vy

                if s.hwnd in self.prev_velocities:
                    pvx, pvy = self.prev_velocities[s.hwnd]
                    s.ax = vx - pvx
                    s.ay = vy - pvy
                cur_velocities[s.hwnd] = (vx, vy)
            else:
                cur_velocities[s.hwnd] = (0.0, 0.0)

        self.prev_positions = cur_positions
        self.prev_velocities = cur_velocities
        return surfaces
