import sys

from PyQt6.QtWidgets import QApplication

from dragcavebot.controller import Application


def main():
    app = QApplication(sys.argv)
    ex = Application()
    ex.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
