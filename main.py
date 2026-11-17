import sys
import os
import ctypes

# Attach to default desktop if launched from background / service runner
try:
    user32 = ctypes.windll.user32
    h_default = user32.OpenDesktopW("default", 0, False, 0x01FF)
    if h_default:
        user32.SetThreadDesktop(h_default)
except Exception:
    pass

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from overlay_widget import SnowOverlayWidget
from tray_manager import SnowTrayManager

def main():
    log_path = os.path.join(os.path.dirname(__file__), "debug.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("Starting main()...\n")
    try:
        # Set high DPI policy
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        app = QApplication(sys.argv)
        app.setApplicationName("DesktopSnowNewYear")
        app.setQuitOnLastWindowClosed(False)

        overlay = SnowOverlayWidget()
        overlay.show()

        def quit_app():
            overlay.close()
            app.quit()

        tray = SnowTrayManager(overlay, on_quit=quit_app)

        with open(log_path, "a", encoding="utf-8") as f:
            f.write("Entering exec()...\n")

        ret = app.exec()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"Exited exec() with code: {ret}\n")
        sys.exit(ret)
    except Exception as e:
        import traceback
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("Exception in main:\n")
            traceback.print_exc(file=f)
        raise

if __name__ == "__main__":
    main()
