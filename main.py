import sys
import os
import random
from PyQt6 import QtWidgets, QtCore, QtGui
from PIL import Image, ExifTags
from geopy.geocoders import Nominatim  # for reverse geocoding metadata

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


def extract_metadata(image_path, geolocator, cache):
    """
    Extracts date and location (city, country) from image EXIF metadata.
    Caches results to speed up repeated calls.
    Returns tuple (date_str or '', location_str or '').
    """
    if image_path in cache:
        return cache[image_path]

    date_str = ''
    location_str = ''

    try:
        img = Image.open(image_path)
        exif_data = img._getexif() or {}
        # Map tag IDs to names
        exif = {ExifTags.TAGS.get(k, k): v for k, v in exif_data.items()}

        # Date
        if 'DateTimeOriginal' in exif:
            date_str = exif['DateTimeOriginal'].split(' ')[0].replace(':', '-')

        # GPS
        if 'GPSInfo' in exif:
            gps = exif['GPSInfo']
            # Helper to convert coords
            def _convert(coord, ref):
                d, m, s = coord
                dec = d[0]/d[1] + m[0]/m[1]/60 + s[0]/s[1]/3600
                return -dec if ref in ['S', 'W'] else dec

            lat = _convert(gps[2], gps[1]) if 1 in gps and 2 in gps else None
            lon = _convert(gps[4], gps[3]) if 3 in gps and 4 in gps else None

            if lat and lon:
                # Reverse geocode
                loc = geolocator.reverse((lat, lon), exactly_one=True, language='en')
                if loc and 'address' in loc.raw:
                    addr = loc.raw['address']
                    city = addr.get('city') or addr.get('town') or addr.get('village') or ''
                    country = addr.get('country', '')
                    location_str = ', '.join(filter(None, [city, country]))
    except Exception:
        pass

    cache[image_path] = (date_str, location_str)
    return cache[image_path]


class SlideshowWindow(QtWidgets.QWidget):
    def __init__(self, images, interval, parent=None):
        super().__init__(parent)
        self.images = images
        self.interval_ms = int(interval * 1000)
        self.current_index = 0

        # Black background
        self.setStyleSheet("background-color: black;")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        self.showFullScreen()

        # Prepare geolocator and cache
        self.geolocator = Nominatim(user_agent="digital_photo_frame")
        self.metadata_cache = {}

        # Image label
        self.label = QtWidgets.QLabel(self)
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("background-color: black;")

        # Info label (date & location)
        self.info_label = QtWidgets.QLabel(self)
        self.info_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet(
            "color: white; background-color: rgba(0, 0, 0, 128); padding: 5px;"
        )

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label, stretch=1)
        layout.addWidget(self.info_label)

        # Timer
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.show_next_image)
        self.timer.start(self.interval_ms)

        self.show_image()

    def show_image(self):
        if not self.images:
            return
        path = self.images[self.current_index]
        pixmap = QtGui.QPixmap(path)
        if pixmap.isNull():
            return

        # Scale to screen size
        screen_rect = QtWidgets.QApplication.primaryScreen().geometry()
        pixmap = pixmap.scaled(
            screen_rect.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation
        )
        self.label.setPixmap(pixmap)

        # Metadata
        date_str, location_str = extract_metadata(path, self.geolocator, self.metadata_cache)
        info = ' | '.join(filter(None, [date_str, location_str]))
        self.info_label.setText(info)

    def show_next_image(self):
        self.current_index = (self.current_index + 1) % len(self.images)
        self.show_image()

    def show_prev_image(self):
        self.current_index = (self.current_index - 1) % len(self.images)
        self.show_image()

    def keyPressEvent(self, event):
        key = event.key()
        if key == QtCore.Qt.Key.Key_Right:
            self.show_next_image()
        elif key == QtCore.Qt.Key.Key_Left:
            self.show_prev_image()
        else:
            self.close()

    def mousePressEvent(self, event):
        self.close()

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()
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
            random.shuffle(self.image_list)
            self.count_label.setText(f"{len(self.image_list)} Images found.")

    def start_slideshow(self):
        if not self.image_list:
            QtWidgets.QMessageBox.warning(self, "No images", "Please select a folder with images first.")
            return
        interval = self.interval_spin.value()
        self.hide()
        self.slideshow = SlideshowWindow(self.image_list, interval)
        self.slideshow.destroyed.connect(self.show)
        self.slideshow.show()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
