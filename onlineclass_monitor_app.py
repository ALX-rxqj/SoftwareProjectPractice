import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from PyQt5.QtWidgets import QApplication
from src.interface import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("OnlineClassMonitor")
    app.setApplicationName("NetClassFocusAnalyzer")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
