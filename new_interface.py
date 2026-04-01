import sys
import json
import time
import subprocess
import pandas as pd
import os
import psutil
from pathlib import Path

from PyQt6.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout,
                             QLabel, QToolButton, QLineEdit, QComboBox, QCheckBox, QGroupBox, QTreeView,
                             QProgressBar, QMessageBox, QRadioButton, QButtonGroup, QTableWidget, QTableWidgetItem,
                             QHBoxLayout,  QTabWidget, QTextEdit,QAbstractItemView, QTableView, QFileDialog, QSizePolicy, QMainWindow)
from PyQt6.QtCore import QThread, pyqtSignal, QSettings, Qt, QModelIndex, QSortFilterProxyModel, QObject
from PyQt6.QtGui import QFont, QStandardItemModel, QStandardItem, QIntValidator

from main2 import setup_stealth_driver, YandexParser, GoogleParser, TwoGisParser, YandexService

from API_FNS import result_function

# Для exe путь к папке относительно exe
if getattr(sys, 'frozen', False):
    base_path = Path(sys.executable).parent
else:
    base_path = Path(__file__).parent

os.environ[r"C:\Users\EDWARD\Desktop\hz\prog\CoolParser\browsers"] = str(base_path / "browsers")

if "--install-playwright" in sys.argv:
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
    sys.exit(0)

def ensure_playwright():
    pw_dir = Path(os.getenv("LOCALAPPDATA", "")) / "ms-playwright"
    if pw_dir.exists():
        return

    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False
    )

ensure_playwright()

from playwright.sync_api import sync_playwright


if getattr(sys, "frozen", False):
    base_path = Path(sys._MEIPASS)  # временная распакованная папка
else:
    base_path = Path(__file__).parent

# === Указываем Playwright путь к браузерам ===
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(base_path / "browsers")

# === Пути к JSON файлам ===
normalize_file = base_path / "normalize_okved.json"
russia_number_file = base_path / "russia_number.json"

# Проверка файлов
assert normalize_file.exists(), f"{normalize_file} не найден"
assert russia_number_file.exists(), f"{russia_number_file} не найден"
def resource_path(filename):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.abspath("."), filename)


def is_chrome_running():
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] and 'chrome' in proc.info['name'].lower():
            return True
    return False


def add_node(parent_item, code, node_data, is_root=False):
    """
    parent_item: QStandardItem (родитель)
    code: '01.11.1'
    node_data: dict с name / children
    """
    OKVED = Qt.ItemDataRole.UserRole + 1

    text = f"{code} — {node_data['name']}"
    item = QStandardItem(text)

    item.setEditable(False)

    if is_root:
        # Корень: нельзя выбрать и нельзя отметить
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
    else:
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled |
            Qt.ItemFlag.ItemIsSelectable |
            Qt.ItemFlag.ItemIsUserCheckable
        )
        item.setCheckable(True)
        item.setCheckState(Qt.CheckState.Unchecked)


    role_code = item.setData(code, OKVED)
    parent_item.appendRow(item)

    children = node_data.get("children", {})
    for child_code, child_data in children.items():
        add_node(item, child_code, child_data)

    return role_code


def filter_tree(model, view, text):
    text = text.lower()

    root = model.invisibleRootItem()

    def filter_item(item):
        match = text in item.text().lower()
        child_match = False

        for row in range(item.rowCount()):
            child = item.child(row)
            if filter_item(child):
                child_match = True

        visible = match or child_match

        view.setRowHidden(item.row(), item.parent().index() if item.parent() else QModelIndex(), not visible)

        return visible

    for row in range(root.rowCount()):
        filter_item(root.child(row))


class NullableLineEdit(QLineEdit):
    def __init__(self, parent=None, validator=None):
        super().__init__(parent)

        if validator:
            self.setValidator(validator)

    def text(self):
        txt = super().text().strip()
        return txt if txt else None


class WorkerFNS(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(object)  # Изменено: передаем результаты
    error = pyqtSignal(str)

    def __init__(self, fns_data):
        super().__init__()
        self.fns_data = fns_data

    def run(self):
        try:
            self.progress.emit(10)
            time.sleep(0.1)
            self.progress.emit(20)
            time.sleep(0.1)
            self.progress.emit(30)
            time.sleep(0.1)
            result = result_function(self.fns_data)
            self.progress.emit(100)
            if result:
                self.finished.emit(result)  # Передаем результаты
            else:
                self.error.emit("Не найдено ни одного результата")
        except Exception as e:
            self.error.emit(str(e))


class WorkerParser(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)  # Изменено: передаем результаты
    error = pyqtSignal(str)

    def __init__(self, query, platform, parser_cls, selected_fields):
        super().__init__()
        self.query = query
        self.platform = platform
        self.parser_cls = parser_cls
        self.selected_fields = selected_fields
        self.results = []

    def run(self):
        driver = None
        try:
            if self.platform == '2ГИС':
                driver = setup_stealth_driver(platform='2ГИС')
            elif self.platform == 'Google':
                driver = setup_stealth_driver()

            if self.platform == 'Google' or self.platform == '2ГИС':
                parser = self.parser_cls(driver, self.platform, self.selected_fields)
                parser.progress.connect(self.progress.emit)

                self.results = parser.parse_businesses(self.query)
                print(self.results)
                if self.results:
                    self.finished.emit(self.results)
                else:
                    self.error.emit("Не найдено ни одного результата")

            elif self.platform == 'Яндекс Услуги':
                parser = YandexService(self.query)
                self.results = parser.run()

                if self.results:
                    self.finished.emit(self.results)
                else:
                    self.error.emit("Не найдено ни одного результата")
            elif self.platform == 'Яндекс':
                with sync_playwright() as playwright:
                    parser = YandexParser(self.query, playwright, self.selected_fields)
                    self.results = parser.execute()

                    if self.results:
                        self.finished.emit(self.results)
                    else:
                        self.error.emit("Не найдено ни одного результата")
        except Exception as e:
            self.error.emit(str(e))

        finally:
         if driver is not None:
                driver.quit()


class Interface(QWidget):
    def __init__(self, progress_bar, tabs, results_widget, logger):
        super().__init__()
        self.log = logger
        self.tabs = tabs
        self.results_widget = results_widget
        self.progress = progress_bar
        self.initUI()

    def initUI(self):
        self.layout = QHBoxLayout()

        control_group = QGroupBox("Настройки поиска")
        control_group.setMinimumHeight(260)

        control_group.setSizePolicy(
            control_group.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Expanding
        )

        control_layout = QVBoxLayout(control_group)

        # Выбор сервиса
        service_layout = QVBoxLayout()
        service_label = QLabel("Сервис:")
        service_label.setMinimumWidth(80)

        self.styleComboBox = QComboBox()
        self.styleComboBox.addItems(['Яндекс', '2ГИС', 'Google', 'Яндекс Услуги'])
        self.styleComboBox.setMinimumHeight(34)

        service_layout.addWidget(service_label)
        service_layout.addWidget(self.styleComboBox, stretch=1)
        control_layout.addLayout(service_layout)

        # Поля поиска
        checkbox_group = QGroupBox('Выберите поля для поиска')
        checkbox_layout = QVBoxLayout()

        self.checkboxes = []
        field_list = ['Название', 'Адрес', 'Номер', 'Почта', 'Вебсайт']

        for field in field_list:
            checkbox = QCheckBox(field)
            checkbox.setChecked(True)
            self.checkboxes.append(checkbox)
            checkbox_layout.addWidget(checkbox)

        checkbox_group.setLayout(checkbox_layout)
        control_layout.addWidget(checkbox_group)

        # Поля запроса
        query_box = QGroupBox('Параметры запроса')
        query_layout = QVBoxLayout(query_box)

        parser_box = QGroupBox('Данные для парсера')
        pars_layout = QHBoxLayout(parser_box)
        # ----------------
        self.company_input = QLineEdit()
        self.company_input.setPlaceholderText("Компании / услуги...")
        pars_layout.addWidget(self.company_input)

        self.region_input = QLineEdit()
        self.region_input.setPlaceholderText("Регион / город")
        pars_layout.addWidget(self.region_input)

        self.button = QPushButton()
        self.button.setText('Старт')

        self.button.clicked.connect(self.on_button_clicked)
        # ----------------

        query_layout.addWidget(parser_box)
        control_layout.addWidget(query_box)
        control_layout.addWidget(self.button)
        control_layout.addStretch(1)
        # ---------------------------------------------

        okved_choice = QGroupBox()
        okved_choice.setMinimumHeight(260)

        okved_choice.setSizePolicy(
            okved_choice.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Expanding
        )
        # ---------------------------------------------
        self.layout.addWidget(control_group, 1)
        self.layout.addWidget(okved_choice, 2)
        # ---------------------------------------------

        self.setLayout(self.layout)

    def collect_user_data(self):
        return {
            "service": self.styleComboBox.currentText(),
            "fields": {
                checkbox.text(): checkbox.isChecked()
                for checkbox in self.checkboxes
            },
            "query": {
                "company": self.company_input.text(),
                "region": self.region_input.text(),
            }
        }

    def validate_inputs(self):
        """Проверяет поля и подсвечивает пустые красным"""
        is_valid = True
        # Стиль для ошибки
        error_style = "border: 2px solid #ff4d4d; border-radius: 4px; background-color: #fff2f2;"
        # Стандартный стиль (пустая строка вернет стиль по умолчанию)
        default_style = ""

        # Проверяем компанию
        if not self.company_input.text().strip():
            self.company_input.setStyleSheet(error_style)
            is_valid = False
        else:
            self.company_input.setStyleSheet(default_style)

        # Проверяем регион
        if not self.region_input.text().strip():
            self.region_input.setStyleSheet(error_style)
            is_valid = False
        else:
            self.region_input.setStyleSheet(default_style)

        return is_valid

    def on_button_clicked(self):
        data = self.collect_user_data()

        company = data['query'].get('company', '').strip()
        region = data['query'].get('region', '').strip()

        if not company or not region:
            # Статический вызов через QMessageBox.Icon
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Ошибка")
            msg.setText("Заполните все поля поиска!")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()  # .exec() вместо старых методов часто работает стабильнее
            return
        # Подготовка данных
        text_input = f"{data['query']['company']} {data['query']['region']}"

        # Определение класса парсера
        service_map = {
            "Яндекс": YandexParser,
            "Google": GoogleParser,
            "2ГИС": TwoGisParser,
            "Яндекс Услуги": YandexService
        }
        parser_cls = service_map.get(data['service'])

        # 1. СОЗДАНИЕ ПОТОКА
        self.search_thread = QThread()
        self.search_worker = WorkerParser(text_input, data['service'], parser_cls, data['fields'])

        self.search_worker.moveToThread(self.search_thread)

        self.search_thread.started.connect(self.search_worker.run)
        self.search_worker.progress.connect(self.progress.setValue)
        self.search_worker.finished.connect(self.on_worker_finished)
        self.search_worker.error.connect(self.on_worker_error)

        self.search_worker.finished.connect(self.search_thread.quit)
        self.search_worker.finished.connect(self.search_worker.deleteLater)
        self.search_thread.finished.connect(self.search_thread.deleteLater)

        # Запуск
        self.button.setEnabled(False)
        self.search_thread.start()

    def on_worker_finished(self, results):
        self.button.setEnabled(True)
        self.button.setText("Старт")
        self.progress.setValue(100)

        # 1. Сначала сохраняем результаты ВНУТРИ виджета результатов
        # чтобы работали кнопки "Сохранить в Excel"
        self.results_widget.current_results = results

        # 2. Вызываем метод отрисовки таблицы
        self.results_widget.display_results(results)

        # 3. Переключаемся на вкладку "Результаты" (индекс 2)
        self.tabs.setCurrentIndex(2)

        QMessageBox.information(self, "Готово", f"Найдено объектов: {len(results)}")
        self.log(f"Успех! Получено строк: {len(results)}")

    def on_worker_error(self, error_message):
        self.button.setEnabled(True)
        self.button.setText("Старт")
        self.progress.setValue(0)
        self.log(f"ОШИБКА: {error_message}")

        QMessageBox.critical(self, "Ошибка", f"Произошла ошибка. Проверьте логи внизу окна.")


class Taxes(QWidget):
    def __init__(self, progress_bar, tabs, results_widget, logger): # Добавлены параметры
        super().__init__()
        self.tabs = tabs
        self.progress = progress_bar
        self.results_widget = results_widget # Сохраняем ссылку
        self.log = logger                    # Сохраняем ссылку
        self.selected_okved = set()
        self.settings = QSettings('FNS_APP', 'FNS_tool')

        self.initUI()


    def on_okved_changed(self, item: QStandardItem):
        code = item.data(Qt.ItemDataRole.UserRole + 1)

        if not code:
            return

        if item.checkState() == Qt.CheckState.Checked:
            self.selected_okved.add(code)
        else:
            self.selected_okved.discard(code)

    def initUI(self):
        self.layout = QHBoxLayout()

        control_group = QGroupBox("Настройки поиска")
        control_group.setMinimumHeight(260)

        control_group.setSizePolicy(
            control_group.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Expanding
        )

        control_layout = QVBoxLayout(control_group)

        FNS_box = QGroupBox('Данные для ФНС')
        FNS_layout = QVBoxLayout(FNS_box)

        FNS_query_people = QHBoxLayout()
        FNS_query_income = QHBoxLayout()

        # ---------------------------------------------

        validator = QIntValidator()

        saved_key = self.settings.value('api_token', '')

        self.api_label = QLineEdit()
        self.api_label.setPlaceholderText('Ключ API')
        self.api_label.setText(saved_key)

        control_layout.addWidget(self.api_label)
        self.min_people = NullableLineEdit(validator=validator)
        self.min_people.setPlaceholderText("Мин. сотрудников")
        FNS_query_people.addWidget(self.min_people)

        self.max_people = NullableLineEdit(validator=validator)
        self.max_people.setPlaceholderText("Макс. сотрудников")
        FNS_query_people.addWidget(self.max_people)
        # ----------------
        self.min_income = NullableLineEdit(validator=validator)
        self.min_income.setPlaceholderText("Мин. заработок(тыс.рублей)")
        FNS_query_income.addWidget(self.min_income)

        self.max_income = NullableLineEdit(validator=validator)
        self.max_income.setPlaceholderText("Макс. заработок(тыс.рублей)")
        FNS_query_income.addWidget(self.max_income)

        # ---------------------------------------------
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Код", "Регион"])

        with open(resource_path('russia_number.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)

        ROLE_CODE = Qt.ItemDataRole.UserRole + 2

        for code, name in data.items():
            code_item = QStandardItem(code)
            code_item.setData(code, ROLE_CODE)
            name_item = QStandardItem(name)

            code_item.setEditable(False)
            name_item.setEditable(False)

            model.appendRow([code_item, name_item])

        # -------------------------
        # Proxy для поиска
        proxy = QSortFilterProxyModel()
        proxy.setSourceModel(model)
        proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        proxy.setFilterKeyColumn(1)  # фильтр по названию региона

        # -------------------------
        # Таблица
        self.table = QTableView()
        self.table.setModel(proxy)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table.horizontalHeader().setStretchLastSection(True)

        # -------------------------
        # Поиск
        search_input = QLineEdit()
        search_input.setPlaceholderText("Поиск региона")
        search_input.textChanged.connect(proxy.setFilterFixedString)

        # -------------------------
        # Обработка выбора
        def on_region_selected(selected, deselected):
            indexes = self.table.selectionModel().selectedRows(0)  # 0 — колонка "Код"
            self.selected_region_codes = []

            for index in indexes:
                # index — это индекс в proxy-модели
                code = index.data(ROLE_CODE)
                if code:
                    self.selected_region_codes.append(code)


        self.table.selectionModel().selectionChanged.connect(on_region_selected)
        # ---------------------------------------------
        buttons = QGroupBox('Настройка выборки')
        button_layout = QHBoxLayout(buttons)

        self.rb_only_this = QRadioButton("Только этот ОКВЭД")
        self.rb_with_sub = QRadioButton("Этот ОКВЭД и все подкатегории")

        self.rb_only_this.setChecked(True)

        button_layout.addWidget(self.rb_only_this)
        button_layout.addWidget(self.rb_with_sub)

        self.group = QButtonGroup()
        self.group.setExclusive(True)
        self.group.addButton(self.rb_only_this)
        self.group.addButton(self.rb_with_sub)

        info = QToolButton()
        info.setText("ⓘ")
        info.setToolTip(
            """
            Первый пункт означает, что для поиска будут использоваться только выбранные категории ОКВЭД.
            Второй пункт означает, что будут использоваться выбранные категории и все его подразделы.
            """
        )
        info.setAutoRaise(True)
        button_layout.addWidget(info)
        # ---------------------------------------------

        self.button = QPushButton()
        self.button.setText('Старт')
        self.button.clicked.connect(self.on_button_clicked)
        # ---------------------------------------------

        FNS_layout.addLayout(FNS_query_people)
        FNS_layout.addLayout(FNS_query_income)
        FNS_layout.addWidget(search_input)
        FNS_layout.addWidget(self.table)
        FNS_layout.addWidget(buttons)
        FNS_layout.addWidget(self.button)

        # ---------------------------------------------

        okved_choice = QGroupBox("Выбор ОКВЭД")
        okved_choice.setMinimumHeight(260)

        okved_choice.setSizePolicy(
            okved_choice.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Expanding
        )

        # ---------------------------------------------
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(['ОКВЭД'])
        model.itemChanged.connect(self.on_okved_changed)
        root = model.invisibleRootItem()

        tree = QTreeView()
        tree.setModel(model)
        tree.setHeaderHidden(False)

        with open(resource_path('normalize_okved.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)

        for section_letter, section_data in data.items():  # A, B, C...
            for sub_code, sub_data in section_data.items():
                add_node(root, sub_code, sub_data, is_root=True)
        # ---------------------------------------------
        search_input = QLineEdit()
        search_input.setPlaceholderText('Поиск по ОКВЭД')

        search_input.textChanged.connect(
            lambda text: filter_tree(model, tree, text)
        )
        # ---------------------------------------------

        # ---------------------------------------------

        tree_layout = QVBoxLayout(okved_choice)
        tree_layout.addWidget(search_input)
        tree_layout.addWidget(tree)

        # ---------------------------------------------

        control_layout.addWidget(FNS_box)
        control_layout.addStretch(1)
        # ---------------------------------------------
        self.layout.addWidget(control_group, 1)
        self.layout.addWidget(okved_choice, 2)
        # ---------------------------------------------
        self.setLayout(self.layout)

    def collect_user_data(self):
        return {
            "fns": {
                "min_people": self.min_people.text(),
                "max_people": self.max_people.text(),
                "min_income": self.min_income.text(),
                "max_income": self.max_income.text(),
                "region_code": getattr(self, "selected_region_codes", None),
            },
            "okved": sorted(self.selected_okved),
            "okved_mode": (self.rb_only_this.isChecked(), self.rb_with_sub.isChecked()),
            "api_key": self.api_label.text(),
        }

    def on_button_clicked(self):
        current_key = self.api_label.text()

        self.settings.setValue('api_token', current_key)

        try:
            if hasattr(self, 'search_thread') and self.search_thread is not None:
                # Проверка sip.isdeleted предотвращает RuntimeError
                from PyQt6.sip import isdeleted
                if not isdeleted(self.search_thread) and self.search_thread.isRunning():
                    self.log("Поток уже запущен...")
                    return
        except RuntimeError:
            # Если объект всё же удалился в момент проверки
            self.search_thread = None

        data = self.collect_user_data()


        self.search_thread = QThread()
        self.search_worker = WorkerFNS(data)
        self.search_worker.moveToThread(self.search_thread)

        # Соединяем сигналы
        self.search_thread.started.connect(self.search_worker.run)
        self.search_worker.progress.connect(self.progress.setValue)
        self.search_worker.finished.connect(self.on_worker_finished)
        self.search_worker.error.connect(self.on_worker_error)

        # ГАРАНТИРОВАННОЕ ЗАВЕРШЕНИЕ:
        # Добавляем соединение для error, чтобы поток выключался в любом случае
        self.search_worker.finished.connect(self.search_thread.quit)
        self.search_worker.error.connect(self.search_thread.quit)  # Добавь эту строку!

        # Очистка ресурсов
        self.search_worker.finished.connect(self.search_worker.deleteLater)
        self.search_worker.error.connect(self.search_worker.deleteLater)  # И эту тоже!
        self.search_thread.finished.connect(self.search_thread.deleteLater)

        # Обнуление ссылки, чтобы hasattr в следующий раз работал корректно
        self.search_thread.finished.connect(lambda: setattr(self, 'search_thread', None))

        self.button.setEnabled(False)
        self.button.setText("Загрузка...")
        self.search_thread.start()

    # Добавьте это в класс окна, чтобы программа закрывалась чисто
    def closeEvent(self, event):
        if hasattr(self, 'search_thread') and self.search_thread.isRunning():
            self.search_thread.quit()
            self.search_thread.wait()  # Ждем завершения перед закрытием
        event.accept()

    def on_worker_finished(self, results):
        self.button.setEnabled(True)
        self.button.setText("Старт")
        self.progress.setValue(100)

        # 1. Сначала сохраняем результаты ВНУТРИ виджета результатов
        # чтобы работали кнопки "Сохранить в Excel"
        self.results_widget.current_results = results

        # 2. Вызываем метод отрисовки таблицы
        self.results_widget.display_results(results)

        # 3. Переключаемся на вкладку "Результаты" (индекс 2)
        self.tabs.setCurrentIndex(3)
        first_page = next(iter(results.values()))
        count = first_page.get("Count", 0)

        QMessageBox.information(self, "Готово", f"Найдено объектов: {count}")

    def on_worker_error(self, error_message):
        self.button.setEnabled(True)
        self.button.setText("Старт")
        self.progress.setValue(0)
        self.log(f"ОШИБКА: {error_message}")

        QMessageBox.critical(self, "Ошибка", f"Произошла ошибка. Проверьте логи внизу окна.")


class ResultWidget(QWidget):
    """Виджет для отображения результатов"""

    def __init__(self):
        super().__init__()
        self.current_results = []
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Таблица для отображения результатов
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #f0f0f0;
                gridline-color: #d0d0d0;
            }
            QHeaderView::section {
                background-color: #4CAF50;
                color: white;
                padding: 4px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.table)

        # Текстовое поле для JSON
        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setFont(QFont("Courier", 10))
        layout.addWidget(self.text_view)

        # Кнопки управления
        button_layout = QHBoxLayout()

        self.btn_save_excel = QPushButton("Сохранить в Excel")
        self.btn_save_excel.clicked.connect(self.save_excel)
        button_layout.addWidget(self.btn_save_excel)

        self.btn_save_json = QPushButton("Сохранить в JSON")
        self.btn_save_json.clicked.connect(self.save_json)
        button_layout.addWidget(self.btn_save_json)

        self.btn_copy = QPushButton("Копировать JSON")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        button_layout.addWidget(self.btn_copy)

        self.btn_clear = QPushButton("Очистить")
        self.btn_clear.clicked.connect(self.clear_results)
        button_layout.addWidget(self.btn_clear)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def display_results(self, results):
        """Отобразить результаты в таблице и текстовом поле"""
        if not results:
            self.text_view.setText("Нет результатов для отображения")
            return

        # Отображаем в таблице
        headers = list(results[0].keys())
        self.table.setColumnCount(len(headers))
        self.table.setRowCount(len(results))
        self.table.setHorizontalHeaderLabels(headers)

        for row_idx, result in enumerate(results):
            for col_idx, key in enumerate(headers):
                value = result.get(key, "")
                if isinstance(value, list):
                    value = ", ".join(map(str, value))
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, col_idx, item)

        # Автонастройка ширины столбцов
        self.table.resizeColumnsToContents()

        # Отображаем в текстовом поле как JSON
        json_text = json.dumps(results, ensure_ascii=False, indent=2)
        self.text_view.setText(json_text)

    def save_excel(self):
        """Сохранить результаты в Excel файл"""
        if not hasattr(self, 'current_results') or not self.current_results:
            QMessageBox.warning(self, "Ошибка", "Нет данных для сохранения")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Сохранить в Excel", "результаты.xlsx",
            "Excel Files (*.xlsx);;All Files (*)"
        )

        if filename:
            try:
                if not filename.endswith('.xlsx'):
                    filename += '.xlsx'

                df = pd.DataFrame(self.current_results)
                df.to_excel(filename, index=False)
                QMessageBox.information(self, "Успех", f"Данные сохранены в {filename}")

                # Предложение открыть файл
                reply = QMessageBox.question(
                    self,
                    "Открыть файл",
                    "Открыть сохраненный файл?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    os.startfile(filename)


            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл: {str(e)}")

    def save_json(self):
        """Сохранить результаты в JSON файл"""
        if not hasattr(self, 'current_results') or not self.current_results:
            QMessageBox.warning(self, "Ошибка", "Нет данных для сохранения")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Сохранить в JSON", "результаты.json",
            "JSON Files (*.json);;All Files (*)"
        )

        if filename:
            try:
                if not filename.endswith('.json'):
                    filename += '.json'

                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.current_results, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "Успех", f"Данные сохранены в {filename}")

            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл: {str(e)}")

    def copy_to_clipboard(self):
        """Скопировать JSON в буфер обмена"""
        if self.text_view.toPlainText():
            QApplication.clipboard().setText(self.text_view.toPlainText())
            QMessageBox.information(self, "Скопировано", "JSON скопирован в буфер обмена")

    def clear_results(self):
        """Очистить результаты"""
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self.text_view.clear()


class ResultWidgetFNS(QWidget):
    """Виджет для отображения результатов"""

    def __init__(self):
        super().__init__()
        self.current_results = []
        self.initUI()


    def initUI(self):
        layout = QVBoxLayout()

        # Таблица для отображения результатов
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #f0f0f0;
                gridline-color: #d0d0d0;
            }
            QHeaderView::section {
                background-color: #4CAF50;
                color: white;
                padding: 4px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.table)

        # Текстовое поле для JSON
        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setFont(QFont("Courier", 10))
        layout.addWidget(self.text_view)

        # Кнопки управления
        button_layout = QHBoxLayout()

        self.btn_save_excel = QPushButton("Сохранить в Excel")
        self.btn_save_excel.clicked.connect(self.save_excel)
        button_layout.addWidget(self.btn_save_excel)

        self.btn_save_json = QPushButton("Сохранить в JSON")
        self.btn_save_json.clicked.connect(self.save_json)
        button_layout.addWidget(self.btn_save_json)

        self.btn_copy = QPushButton("Копировать JSON")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        button_layout.addWidget(self.btn_copy)

        self.btn_clear = QPushButton("Очистить")
        self.btn_clear.clicked.connect(self.clear_results)
        button_layout.addWidget(self.btn_clear)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def normalize_fns_results(self, raw_data):
        """
        Собирает данные из всех страниц (page_1, page_2, ...),
        находит внутри них списки 'items' и извлекает объекты 'ЮЛ'.
        """
        all_items = []

        # 1. Если пришел словарь (ожидаем структуру со страницами)
        if isinstance(raw_data, dict):
            # Перебираем все ключи (page_1, page_2, page_3...)
            for key, page_content in raw_data.items():
                if isinstance(page_content, dict):
                    # Из каждой страницы забираем список 'items'
                    items = page_content.get('items', [])
                    if isinstance(items, list):
                        all_items.extend(items)

        # 2. Если вдруг пришел просто список (на всякий случай)
        elif isinstance(raw_data, list):
            all_items = raw_data

        # Теперь "вычищаем" ЮЛ из всех собранных элементов
        normalized = []
        for item in all_items:
            if isinstance(item, dict):
                ul = item.get("ЮЛ")
                if isinstance(ul, dict):
                    normalized.append(ul)
                else:
                    # Если ключа ЮЛ нет, но сам элемент - словарь, берем его целиком
                    normalized.append(item)

        return normalized
    def display_results(self, raw_results):
        """Отобразить результаты в таблице и текстовом поле"""
        if not raw_results:
            self.text_view.setText("Результаты пусты")
            return

        # Нормализуем данные ОДИН РАЗ здесь
        self.current_results = self.normalize_fns_results(raw_results)

        if not self.current_results:
            self.text_view.setText("Не удалось извлечь данные о компаниях (ЮЛ)")
            self.table.setRowCount(0)
            return

        # Подготовка таблицы
        headers = list(self.current_results[0].keys())
        self.table.setColumnCount(len(headers))
        self.table.setRowCount(len(self.current_results))
        self.table.setHorizontalHeaderLabels(headers)

        for row_idx, result in enumerate(self.current_results):
            for col_idx, key in enumerate(headers):
                value = result.get(key, "")
                item = QTableWidgetItem(str(value))
                # Используем правильный флаг для PyQt6
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, col_idx, item)

        self.table.resizeColumnsToContents()

        # Отображение JSON (уже нормализованного)
        json_text = json.dumps(self.current_results, ensure_ascii=False, indent=2)
        self.text_view.setText(json_text)

    def _extract_items(self):
        """
        Возвращает список items из current_results
        """
        if not hasattr(self, 'current_results'):
            return []

        data = self.current_results

        if isinstance(data, dict):
            first_page = next(iter(data.values()), {})
            return first_page.get('items', [])

        return data

    def save_excel(self):
        # Теперь берем данные напрямую из current_results, они уже чистые
        if not self.current_results:
            QMessageBox.warning(self, "Ошибка", "Нет данных для сохранения")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Сохранить в Excel", "fns_results.xlsx",
            "Excel Files (*.xlsx);;All Files (*)"
        )

        if filename:
            try:
                if not filename.endswith('.xlsx'):
                    filename += '.xlsx'

                df = pd.DataFrame(self.current_results)
                df.to_excel(filename, index=False)
                QMessageBox.information(self, "Успех", f"Файл сохранен: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка при сохранении: {e}")

    def save_json(self):
        if not self.current_results:
            QMessageBox.warning(self, "Ошибка", "Нет данных для сохранения")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Сохранить в JSON", "fns_results.json",
            "JSON Files (*.json);;All Files (*)"
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.current_results, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "Успех", "JSON сохранен")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка: {e}")
    def copy_to_clipboard(self):
        """Скопировать JSON в буфер обмена"""
        if self.text_view.toPlainText():
            QApplication.clipboard().setText(self.text_view.toPlainText())
            QMessageBox.information(self, "Скопировано", "JSON скопирован в буфер обмена")

    def clear_results(self):
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self.text_view.clear()
        self.current_results = None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Аггрегатор парсеров')
        self.setUpMainWindow()
        self.show()

    def setUpMainWindow(self):
        main_layout = QVBoxLayout()
        self.setMinimumSize(1100, 500)

        self.common_progress = QProgressBar()
        self.common_progress.setRange(0, 100)
        self.common_progress.setValue(0)

        # Вкладки
        self.tabs = QTabWidget()

        self.result_page = ResultWidget()
        self.result_fns = ResultWidgetFNS()

        self.interface = Interface(self.common_progress, self.tabs, self.result_page, self.log)
        self.fns_tab = Taxes(self.common_progress, self.tabs, self.result_fns, self.log)

        self.tabs.addTab(self.interface, 'Поиск')
        self.tabs.addTab(self.fns_tab, 'ФНС')
        self.tabs.addTab(self.result_page, 'Рез. парсер')
        self.tabs.addTab(self.result_fns, 'Рез. фнс')

        main = QWidget()
        main.setLayout(main_layout)

        self.setCentralWidget(main)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(100)
        self.log_console.setStyleSheet("""
                    background-color: #1e1e1e; 
                    color: #d4d4d4; 
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 10px;
                """)

        main_layout.addWidget(self.tabs)
        main_layout.addWidget(self.common_progress)
        main_layout.addWidget(self.log_console)

    def closeEvent(self, event):
        """Безопасно закрывает QThread при закрытии окна."""
        thread = getattr(self.interface, 'search_thread', None)

        if thread is not None:
            try:
                # Проверяем, жив ли поток
                if thread.isRunning():
                    thread.quit()  # корректно завершает run()
                    thread.wait()  # ждём окончания работы потока
            except RuntimeError:
                # Поток уже удалён — безопасно игнорируем
                pass

            # Сбрасываем ссылку на поток
            self.interface.search_thread = None

        # Можно вызвать стандартное закрытие окна
        event.accept()

        # Закрываем все Chrome драйверы, если они остались
        # (Здесь можно вызвать метод quit() у твоих парсеров)

        event.accept()
    def log(self, message):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_console.append(f"[{timestamp}] {message}")
        # Авто-скролл вниз
        self.log_console.ensureCursorVisible()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    import traceback
    def excepthook(exc_type, exc_value, exc_tb):
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

        print("CRITICAL ERROR:", tb)

    sys.excepthook = excepthook

    app.setStyle('Fusion')

    ex = MainWindow()

    app.exec()