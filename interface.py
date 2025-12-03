import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout,
                             QLabel, QLineEdit, QComboBox, QCheckBox, QGroupBox)

from main2 import main

field_list_eng = ['name', 'address', 'number', 'mail', 'website']


class MyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('PyQt5')
        self.setGeometry(300, 300, 300, 400)

        self.layout = QVBoxLayout()

        self.styleComboBox = QComboBox()
        self.styleComboBox.addItems(['Яндекс', '2ГИС', 'Google', 'Яндекс Услуги'])
        self.layout.addWidget(self.styleComboBox)

        self.checkbox_group = QGroupBox("Выберите поля для поиска:")
        checkbox_layout = QVBoxLayout()

        self.checkboxes = []

        field_list = ['Название', 'Адрес', 'Номер', 'Почта', 'Вебсайт']

        for field in field_list:
            checkbox = QCheckBox(field)
            checkbox.setChecked(True)
            self.checkboxes.append(checkbox)
            checkbox_layout.addWidget(checkbox)

        self.checkbox_group.setLayout(checkbox_layout)
        self.layout.addWidget(self.checkbox_group)

        # Поле ввода и кнопка
        self.label = QLabel('Введите запрос для поиска:', self)
        self.layout.addWidget(self.label)

        self.text_input = QLineEdit(self)
        self.layout.addWidget(self.text_input)

        self.button = QPushButton('Найти', self)
        self.layout.addWidget(self.button)

        self.setLayout(self.layout)
        self.button.clicked.connect(self.on_button_clicked)  # type: ignore

    def on_button_clicked(self):
        input_text = self.text_input.text()

        # Получаем выбранные чекбоксы
        selected_fields = {}
        for i, checkbox in enumerate(self.checkboxes):
            if checkbox.isChecked():
                selected_fields.update({f'{field_list_eng[i]}': True})
            else:
                selected_fields.update({f'{field_list_eng[i]}': False})

        # Формируем результат
        service = self.styleComboBox.currentText()

        # result = {'platform': service,
        #     'query': input_text,
        #     'check_data': selected_fields}
        main(input_text, service, selected_fields)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MyApp()
    ex.show()
    sys.exit(app.exec_())

