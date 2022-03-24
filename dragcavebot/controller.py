import time
from datetime import datetime

from PyQt6.QtCore import (
    pyqtSignal,
    QMutex,
    QObject,
    QRunnable,
    QThread,
    QThreadPool,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QMainWindow,
    QMessageBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QWidget,
)

from dragcavebot.dragcave import DragCave
from dragcavebot.dragons import dragons


workers_mutex = QMutex()


class WorkerSignals(QObject):
    complete_signal = pyqtSignal(bool)


class LoginWidget(QWidget):
    def __init__(self, cave, login_callback):
        super().__init__()
        self.cave = cave
        self.login_callback = login_callback
        self.initUI()

    def initUI(self):
        username = QLineEdit()
        username.lbl = "Username"
        password = QLineEdit()
        password.setEchoMode(QLineEdit.EchoMode.Password)
        login_button = QPushButton("Login")
        login_button.clicked[bool].connect(self._login)

        self.username = username
        self.password = password

        vbox = QFormLayout(self)
        vbox.addRow("Username", username)
        vbox.addRow("Password", password)
        vbox.addWidget(login_button)

        self.login_layout = vbox
        self.setWindowTitle("Login")

    def _login(self, pressed):
        username = self.username.text()
        password = self.password.text()

        if not any((username, password)):
            error_message = QMessageBox()
            error_message.setWindowTitle("Error")
            error_message.setText("Please enter a username and/or password")
            error_message.exec()

        logged_in = self.cave.login(username, password)
        if logged_in:
            self.login_callback()


class MainWidget(QWidget):
    class ControlPanel(QWidget):
        def __init__(self, parent):
            super().__init__()
            self.parent = parent
            self.initUI()

        def initUI(self):
            grid = QGridLayout(self)
            log = QTextEdit()
            log.setReadOnly(True)
            log_label = QLabel("Log")

            start_button = QPushButton("Start")
            stop_button = QPushButton("Stop")
            timer = QLineEdit()
            timer.setReadOnly(True)
            stop_button.setEnabled(False)
            start_button.clicked[bool].connect(self.parent._start)
            stop_button.clicked[bool].connect(self.parent._stop)

            grid.addWidget(log_label, 0, 0)
            grid.addWidget(log, 1, 0)
            grid.addWidget(start_button, 1, 1)
            grid.addWidget(stop_button, 1, 2)
            grid.addWidget(timer, 1, 3)

            self.log = log
            self.start_button = start_button
            self.stop_button = stop_button
            self.timer = timer

    class WantedEggs(QWidget):
        def __init__(self, parent):
            super().__init__()
            self.parent = parent
            self.initUI()

        def initUI(self):
            grid = QGridLayout(self)
            positions = ((i, j) for i in range(1, 6) for j in range(4))

            select_all = QCheckBox("Select All")
            select_all.stateChanged.connect(self.parent._select_all_eggs)
            grid.addWidget(select_all)
            for position, dragon in zip(positions, dragons):
                name = dragon[0]
                checkbox = QCheckBox(name)
                checkbox.stateChanged.connect(self.parent._select_egg)
                self.parent.checkboxes.append(checkbox)
                grid.addWidget(checkbox, *position)

    class MainWorker(QObject):
        class Worker(QRunnable):
            def __init__(self, fn, *args, **kwargs):
                super().__init__()
                self.fn = fn
                self.args = args
                self.kwargs = kwargs
                self.signals = WorkerSignals()

            def run(self):
                self.fn(*self.args, **self.kwargs)
                self.signals.complete_signal.emit(True)

        can_press_start = pyqtSignal(bool)
        can_press_stop = pyqtSignal(bool)
        info = pyqtSignal(str)
        timer = pyqtSignal(str)

        def __init__(self, cave):
            super().__init__()
            self.cave = cave
            self.workers_complete = []
            self.thread_pool = QThreadPool(parent=self)

        def _set_worker_complete(self, res):
            workers_mutex.lock()
            self.workers_complete.append(res)
            workers_mutex.unlock()

        def get_egg(self, location):
            # Only real world time matters, so perf_counter is not needed
            start_time = time.time()

            while time.time() - start_time < 70:
                results = self.cave.get_available_eggs(location)
                for result in results:
                    egg_name, status = result
                    self.info.emit(f"{egg_name}: {status}")
                time.sleep(1) 

        def task(self):
            thread = QThread.currentThread()
            while not thread.isInterruptionRequested():
                now = datetime.now()
                current_minute = now.minute
                current_second = now.second
                if current_minute % 5 == 4 and current_second >= 55:
                    if self.thread_pool.activeThreadCount() < 1:
                        self.info.emit("Refreshing egg locations")
                        for location in self.cave.LOCATIONS:
                            worker = self.Worker(self.get_egg, location)
                            # worker.signals.complete_signal.connect(
                            #     self._set_worker_complete
                            # )
                            self.thread_pool.start(worker)

                self.timer.emit(datetime.now().strftime("%H:%M:%S"))

                if current_second % 10 == 0:
                    print(f"active threads: {self.thread_pool.activeThreadCount()}")

                time.sleep(0.5)
            else:
                self.timer.emit("Stopping")
                self.info.emit("Stopping - Please wait up to a minute.")
                self.thread_pool.waitForDone(-1)
                print(f"active threads: {self.thread_pool.activeThreadCount()}")
                self.can_press_start.emit(True)
                self.can_press_stop.emit(False)
                self.timer.emit("Ready")

    def __init__(self, cave, wanted_eggs):
        super().__init__()
        self.checkboxes = []
        self.cave = cave
        self.wanted_eggs = wanted_eggs
        self.control = self.ControlPanel(self)
        self.grid = self.WantedEggs(self)
        self.initUI()

    def initUI(self):
        tab_widget = QTabWidget(self)
        tab_widget.addTab(self.control, "Control Panel")
        tab_widget.addTab(self.grid, "Eggs")
        QGridLayout(self).addWidget(tab_widget)

    def _log_info(self, text):
        self.control.log.append(text)

    def _start(self):
        self.control.start_button.setEnabled(False)
        self.control.stop_button.setEnabled(True)

        self.thread = QThread(parent=self)
        self.worker = self.MainWorker(self.cave)
        self.worker.moveToThread(self.thread)
        self.worker.timer.connect(self.control.timer.setText)
        self.worker.can_press_start.connect(self.control.start_button.setEnabled)
        self.worker.can_press_stop.connect(self.control.stop_button.setEnabled)
        self.worker.info.connect(self._log_info)
        self.thread.start()
        self.thread.started.connect(self.worker.task)

    def _stop(self):
        self.control.stop_button.setEnabled(False)
        self.thread.requestInterruption()

    def _select_all_eggs(self, state):
        # This indirectly calls _select_egg because of the state change
        if state == 2:
            # Checked
            for checkbox in self.checkboxes:
                checkbox.setChecked(True)
        else:
            # Unchecked
            for checkbox in self.checkboxes:
                checkbox.setChecked(False)

    def _select_egg(self, state):
        name = self.sender().text()
        if state == 2:
            # Checked
            self.wanted_eggs[name] = True
            self._log_info(f"Adding {name} to wanted eggs")
        else:
            # Unchecked
            self.wanted_eggs[name] = False
            self._log_info(f"Removing {name} to wanted eggs")

        self.cave.set_wanted_eggs(self.wanted_eggs)


class Application(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cave = DragCave()
        self.wanted_eggs = {name: False for name, _ in dragons}
        self.initUI()

    def initUI(self):
        self.main_widget = MainWidget(self.cave, self.wanted_eggs)
        self.login_widget = LoginWidget(self.cave, self.login_callback)
        self.setCentralWidget(self.login_widget)

    def login_callback(self):
        self.setCentralWidget(self.main_widget)

    def closeEvent(self, event):
        try:
            if not isinstance(self.centralWidget(), LoginWidget):
                self.cave.logout()
        except Exception as e:
            print(e)
        finally:
            super().closeEvent(event)
