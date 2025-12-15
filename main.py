#
# Gemini ImageGen v0.1
#
# GUI for Gemini Image Generation using PySide6
# (C) Copyright 2025 Mika Jussila
#

from gui import MainWindow
from PySide6.QtWidgets import QApplication
import sys


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
