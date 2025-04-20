import sys
import os
import random
from PyQt6 import QtWidgets, QtCore, QtGui

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')

def scan_images(folder_path):
    """
    Recursively scan the given folder for image files.
    Returns a list of absolute file paths.
    """
    image_paths = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(IMAGE_EXTENSIONS):
                image_paths.append(os.path.join(root, file))
    return image_paths

class SlideshowWindow(QtWidgets.QWidget):
    def __init__(self, images, interval, parent=None):
        super().__init__(parent)
        self.images = images
        self.interval_ms = int(interval * 1000)

        # Fullscreen & borderless
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        self.showFullScreen()

        self.label = QtWidgets.QLabel(self)
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

        # Timer for image changes
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.show_random_image)
        self.timer.start(self.interval_ms)
        self.show_random_image()

    def show_random_image(self):
        if not self.images:
            return
        img_path = random.choice(self.images)
        pixmap = QtGui.QPixmap(img_path)
        if pixmap.isNull():
            return
        screen_rect = QtWidgets.QApplication.primaryScreen().geometry()
        pixmap = pixmap.scaled(
            screen_rect.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation
        )
        self.label.setPixmap(pixmap)

    def keyPressEvent(self, event):
        self.close()

    def mousePressEvent(self, event):
        self.close()

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()
        # Emit destroyed to signal MainWindow
        super().closeEvent(event)

class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Digital Photo Frame Setup")

        # Widgets
        self.folder_label = QtWidgets.QLabel("No folder selected.")
        self.browse_btn = QtWidgets.QPushButton("Browse Folder...")
        self.count_label = QtWidgets.QLabel("")
        self.interval_spin = QtWidgets.QDoubleSpinBox()
        self.interval_spin.setSuffix(" seconds")
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(5)
        self.start_btn = QtWidgets.QPushButton("Start Slideshow")

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.browse_btn)
        layout.addWidget(self.folder_label)
        layout.addWidget(self.count_label)
        layout.addWidget(QtWidgets.QLabel("Display time per image:"))
        layout.addWidget(self.interval_spin)
        layout.addWidget(self.start_btn)
        self.setLayout(layout)

        # Signals
        self.browse_btn.clicked.connect(self.choose_folder)
        self.start_btn.clicked.connect(self.start_slideshow)

        # Data
        self.image_list = []
        self.slideshow = None

    def choose_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if folder:
            self.folder_label.setText(folder)
            self.image_list = scan_images(folder)
            self.count_label.setText(f"{len(self.image_list)} Images found.")

    def start_slideshow(self):
        if not self.image_list:
            QtWidgets.QMessageBox.warning(self, "No images", "Please select a folder with images first.")
            return
        interval = self.interval_spin.value()
        self.hide()
        # Keep a reference to prevent GC
        self.slideshow = SlideshowWindow(self.image_list, interval)
        self.slideshow.destroyed.connect(self.show)
        self.slideshow.show()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
