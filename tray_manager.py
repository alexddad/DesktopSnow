from typing import Callable
from PyQt6.QtWidgets import (
    QSystemTrayIcon, QMenu, QApplication
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QPen, QColor, QAction, QActionGroup
)
from PyQt6.QtCore import Qt

from overlay_widget import SnowOverlayWidget
from garland import GarlandRenderer

class SnowTrayManager:
    def __init__(self, overlay: SnowOverlayWidget, on_quit: Callable):
        self.overlay = overlay
        self.on_quit = on_quit

        self.icon = self._create_snowflake_icon()
        self.tray = QSystemTrayIcon(self.icon, self.overlay)
        self.tray.setToolTip("❄️ Новогодний снег на окнах")

        self.menu = QMenu()
        self._build_menu()
        self.tray.setContextMenu(self.menu)

        self.tray.show()

    def _create_snowflake_icon(self) -> QIcon:
        pix = QPixmap(32, 32)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Blue badge
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(30, 144, 255, 235))
        p.drawRoundedRect(2, 2, 28, 28, 7, 7)

        # White snowflake
        p.translate(16, 16)
        pen = QPen(QColor(255, 255, 255, 250), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        size = 9
        for _ in range(6):
            p.drawLine(0, 0, 0, -size)
            spur_y = int(-size * 0.5)
            p.drawLine(0, spur_y, 3, spur_y - 2)
            p.drawLine(0, spur_y, -3, spur_y - 2)
            p.rotate(60)
        p.end()
        return QIcon(pix)

    def _build_menu(self):
        header = self.menu.addAction("❄️ Снег на окнах")
        header.setEnabled(False)
        self.menu.addSeparator()

        # Snowman submenu
        sm_menu = self.menu.addMenu("⛄ Лепка снеговика")
        
        act_add_sm = sm_menu.addAction("🎁 Поставить снеговика")
        act_add_sm.triggered.connect(lambda: self.overlay.add_preset_snowman())

        act_clear_sm = sm_menu.addAction("🧹 Убрать всех снеговиков")
        act_clear_sm.triggered.connect(self.overlay.clear_all_snowmen)

        sm_menu.addSeparator()
        info_act = sm_menu.addAction("💡 Зажмите Ctrl+ЛКМ на снегу, чтобы слепить ком!")
        info_act.setEnabled(False)

        # Garland submenu
        garland_menu = self.menu.addMenu("🎄 Гирлянда")
        self.act_garland = QAction("Включить гирлянду", garland_menu, checkable=True)
        self.act_garland.setChecked(True)
        self.act_garland.triggered.connect(self.overlay.garland.set_enabled)
        garland_menu.addAction(self.act_garland)
        garland_menu.addSeparator()

        mode_group = QActionGroup(garland_menu)
        mode_group.setExclusive(True)
        for key, label in GarlandRenderer.MODES.items():
            act = QAction(label, garland_menu, checkable=True)
            act.setChecked(key == self.overlay.garland.mode)
            mode_group.addAction(act)
            garland_menu.addAction(act)
            act.triggered.connect(lambda _, k=key: self.overlay.garland.set_mode(k))

        # Decor submenu
        decor_menu = self.menu.addMenu("🎁 Украшения")
        act_tree = QAction("Ёлочка с подарками на окнах", decor_menu, checkable=True)
        act_tree.setChecked(True)
        act_tree.triggered.connect(self.overlay.decor.set_tree)
        decor_menu.addAction(act_tree)
        act_sparkles = QAction("Блёстки на снегу", decor_menu, checkable=True)
        act_sparkles.setChecked(True)
        act_sparkles.triggered.connect(self.overlay.decor.set_sparkles)
        decor_menu.addAction(act_sparkles)

        # Thickness Submenu
        thickness_menu = self.menu.addMenu("📏 Высота сугробов")
        thickness_group = QActionGroup(self.menu)
        thickness_group.setExclusive(True)

        heights = [
            ("Тонкий аккуратный слой (6 px)", 6.0, False),
            ("Классические сугробики (10 px)", 10.0, True),
            ("Пышные зимние шапки (15 px)", 15.0, False),
        ]

        for label, h, checked in heights:
            action = QAction(label, thickness_menu, checkable=True)
            action.setChecked(checked)
            thickness_group.addAction(action)
            thickness_menu.addAction(action)
            action.triggered.connect(lambda _, val=h: setattr(self.overlay, "snow_height", val))

        act_refill = self.menu.addAction("❄️ Насыпать свежего снега на все окна")
        act_refill.triggered.connect(self.overlay.refill_all_snow)

        act_shake_all = self.menu.addAction("🧹 Стряхнуть весь снег с окон")
        act_shake_all.triggered.connect(self._shake_all_snow)

        self.menu.addSeparator()

        # Pause / Resume Action
        self.act_pause = self.menu.addAction("⏸️ Поставить на паузу")
        self.act_pause.triggered.connect(self._toggle_pause)

        self.menu.addSeparator()

        # Quit Action
        act_quit = self.menu.addAction("❌ Закрыть приложение")
        act_quit.triggered.connect(self.on_quit)

    def _shake_all_snow(self):
        ov = self.overlay
        for s in ov.surfaces:
            ov._spawn_movement_particles(s, 20.0, 0.0, 5.0, is_hard_shake=True)
            profile = ov.window_profiles.get(s.hwnd)
            if profile:
                for i in range(len(profile)):
                    profile[i] = 0.0
        ov.update()

    def _toggle_pause(self):
        self.overlay.paused = not self.overlay.paused
        if self.overlay.paused:
            self.act_pause.setText("▶️ Возобновить")
        else:
            self.act_pause.setText("⏸️ Поставить на паузу")
