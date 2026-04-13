import os
import sys
import time
import atexit
import threading
import subprocess
import keyboard

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLineEdit,
    QFrame,
    QGraphicsDropShadowEffect,
)

from PIL import Image, ImageQt, ImageDraw


class GlowButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.active = False
        self.hovered = False

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(42)

        self.glow = QGraphicsDropShadowEffect(self)
        self.glow.setBlurRadius(0)
        self.glow.setOffset(0, 0)
        self.glow.setColor(QColor(255, 255, 255, 0))
        self.setGraphicsEffect(self.glow)

        self.update_style()

    def enterEvent(self, event):
        self.hovered = True
        self.update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update_style()
        super().leaveEvent(event)

    def set_active(self, state: bool):
        self.active = state
        if state:
            self.glow.setBlurRadius(22)
            self.glow.setColor(QColor(255, 255, 255, 180))
        else:
            self.glow.setBlurRadius(0)
            self.glow.setColor(QColor(255, 255, 255, 0))
        self.update_style()

    def update_style(self):
        bg = "#303030"
        border = "#505050" if self.hovered else "#3a3a3a"

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: #f2f2f2;
                border: 1px solid {border};
                border-radius: 12px;
                font-weight: 600;
                font-size: 14px;
                padding: 8px 14px;
            }}
        """)


class StyledInput(QLineEdit):
    def __init__(self, text="0"):
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedWidth(60)
        self.setFixedHeight(38)
        self.setFont(QFont("Consolas", 11))
        self.setMaxLength(3)
        self.textChanged.connect(self.sanitize)
        self.update_style()

    def sanitize(self):
        value = self.text()
        filtered = "".join(ch for ch in value if ch.isdigit())
        if value != filtered:
            cursor = self.cursorPosition()
            self.setText(filtered)
            self.setCursorPosition(min(cursor - 1, len(filtered)))

    def update_style(self):
        self.setStyleSheet("""
            QLineEdit {
                background-color: #303030;
                color: #f2f2f2;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                padding: 6px;
            }
            QLineEdit:focus {
                border: 1px solid #8a8a8a;
            }
        """)


class AbilityCard(QFrame):
    def __init__(self, name, image_path, cooldown):
        super().__init__()
        self.name = name
        self.image_path = image_path
        self.cooldown = cooldown
        self.next_fire_time = None

        self.setObjectName("abilityCard")
        self.setStyleSheet("""
            QFrame#abilityCard {
                background-color: #262626;
                border: 1px solid #363636;
                border-radius: 14px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.image_label = QLabel()
        self.image_label.setFixedSize(56, 56)
        self.image_label.setPixmap(self.load_image(self.image_path, self.name, (56, 56)))
        self.image_label.setScaledContents(True)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        self.name_label = QLabel(self.name)
        self.name_label.setStyleSheet("""
            color: #f2f2f2;
            font-size: 14px;
            font-weight: 700;
        """)

        self.cooldown_label = QLabel(f"Cooldown: {self.cooldown:.1f}")
        self.cooldown_label.setStyleSheet("""
            color: #bdbdbd;
            font-size: 12px;
        """)

        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.cooldown_label)

        self.key_input = StyledInput("0")

        layout.addWidget(self.image_label)
        layout.addLayout(text_layout, 1)
        layout.addWidget(self.key_input)

    def load_image(self, path, label, size):
        if os.path.exists(path):
            img = Image.open(path).convert("RGBA")
            img.thumbnail(size)
        else:
            img = Image.new("RGBA", size, (80, 80, 80, 255))
            draw = ImageDraw.Draw(img)
            draw.text((6, 18), label[:6], fill=(255, 255, 255, 255))

        qimage = ImageQt.ImageQt(img)
        pixmap = QPixmap.fromImage(qimage)
        return pixmap

    def get_key(self):
        return self.key_input.text().strip()

    def set_countdown(self, text):
        self.cooldown_label.setText(text)


class HotkeyApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("mondaydevv's HiveHub")
        self.setFixedSize(360, 620)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setStyleSheet("background-color: #202020;")

        self.running = False
        self.paused = False
        self.threads = []
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.ahk_process = None
        self.registered_hotkeys = []

        script_dir = os.path.dirname(os.path.abspath(__file__))
        images_dir = os.path.join(script_dir, "imageAssets")

        self.abilities = [
            {"name": "Red Extract", "image": os.path.join(images_dir, "red.png"), "cooldown": 600.0},
            {"name": "Blue Extract", "image": os.path.join(images_dir, "blue.png"), "cooldown": 600.0},
            {"name": "Glitter", "image": os.path.join(images_dir, "glitter.png"), "cooldown": 911.0},
            {"name": "Glue", "image": os.path.join(images_dir, "glue.png"), "cooldown": 600.0},
            {"name": "Tropical", "image": os.path.join(images_dir, "tropical.png"), "cooldown": 600.0},
        ]

        self.cards = []
        self.build_ui()
        self.register_global_hotkeys()
        self.start_ahk()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdowns)
        self.timer.start(100)

        atexit.register(self.cleanup)

    def build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        title = QLabel("HiveHub")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            color: #f2f2f2;
            font-size: 22px;
            font-weight: 700;
            margin-bottom: 4px;
        """)
        outer.addWidget(title)

        #
        #outer.addWidget(subtitle)

        for ability in self.abilities:
            card = AbilityCard(ability["name"], ability["image"], ability["cooldown"])
            self.cards.append(card)
            outer.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.start_btn = GlowButton("Start")
        self.pause_btn = GlowButton("Pause")
        self.stop_btn = GlowButton("Stop")

        self.start_btn.clicked.connect(self.start)
        self.pause_btn.clicked.connect(self.pause)
        self.stop_btn.clicked.connect(self.stop)

        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.pause_btn)
        btn_row.addWidget(self.stop_btn)

        outer.addLayout(btn_row)

        self.status_label = QLabel("Stopped")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            color: #f2f2f2;
            background-color: #303030;
            border: 1px solid #3a3a3a;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 600;
            padding: 10px;
        """)
        outer.addWidget(self.status_label)

    def register_global_hotkeys(self):
        self.registered_hotkeys.append(keyboard.add_hotkey("f1", self.start))
        self.registered_hotkeys.append(keyboard.add_hotkey("f2", self.pause))
        self.registered_hotkeys.append(keyboard.add_hotkey("f3", self.stop))

    def send_signal_key(self, key):
        keyboard.send(key)

    def press_assigned_key(self, key):
        keyboard.send(key)

    def press_key_loop(self, index, key, cooldown):
        while not self.stop_event.is_set():
            if self.pause_event.is_set():
                time.sleep(0.1)
                continue

            self.press_assigned_key(key)
            self.cards[index].next_fire_time = time.time() + cooldown
            time.sleep(cooldown)

    def update_countdowns(self):
        now = time.time()

        for i, ability in enumerate(self.abilities):
            next_time = self.cards[i].next_fire_time
            if next_time is None:
                self.cards[i].set_countdown(f"Cooldown: {ability['cooldown']:.1f}")
            else:
                remaining = max(0, int(next_time - now))
                self.cards[i].set_countdown(f"Cooldown: {remaining}")

    def start(self):
        if self.running:
            return

        self.running = True
        self.stop_event.clear()
        self.pause_event.clear()

        self.start_btn.set_active(True)
        self.pause_btn.set_active(False)
        self.stop_btn.set_active(False)

        self.send_signal_key("f13")

        self.threads.clear()

        for i, card in enumerate(self.cards):
            if card.get_key() == "0" or card.get_key() == "":
                continue

            key = card.get_key()
            cooldown = self.abilities[i]["cooldown"]

            t = threading.Thread(target=self.press_key_loop, args=(i, key, cooldown), daemon=True)
            t.start()
            self.threads.append(t)

        self.status_label.setText("Running")

    def pause(self):
        if not self.running:
            return

        self.pause_event.set()
        self.start_btn.set_active(False)
        self.pause_btn.set_active(True)
        self.stop_btn.set_active(False)

        self.send_signal_key("f14")
        self.status_label.setText("Paused")

    def stop(self):
        self.running = False
        self.stop_event.set()
        self.pause_event.clear()

        self.start_btn.set_active(False)
        self.pause_btn.set_active(False)
        self.stop_btn.set_active(True)

        self.send_signal_key("f15")
        self.status_label.setText("Stopped")

        for card in self.cards:
            card.next_fire_time = None

    def start_ahk(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ahk_path = os.path.join(script_dir, "main.ahk")
        ahk_exe = r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe"

        if os.path.exists(ahk_path) and os.path.exists(ahk_exe):
            self.ahk_process = subprocess.Popen([ahk_exe, ahk_path])

    def stop_ahk(self):
        if self.ahk_process:
            self.ahk_process.terminate()
            self.ahk_process = None

    def cleanup(self):
        self.stop()
        self.stop_ahk()
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass

    def closeEvent(self, event):
        self.cleanup()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = HotkeyApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()