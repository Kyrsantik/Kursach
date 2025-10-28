import sys
import sqlite3
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFrame, QStackedWidget,
    QListWidget, QComboBox, QListWidgetItem, QMessageBox
)
from PyQt6.QtGui import QFont, QCursor
from PyQt6.QtCore import Qt, QSize


class DatabaseManager:
    def __init__(self, db_name='office_system.db'):
        self.db_name = db_name
        self.init_database()
        self.seed_admin_user()

    def init_database(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                                                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                 username TEXT UNIQUE NOT NULL,
                                                 password TEXT NOT NULL,
                                                 role TEXT NOT NULL DEFAULT 'Сотрудник'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                equipment_type TEXT NOT NULL,
                inventory_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE (user_id, inventory_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS requests (
                                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                    user_id INTEGER NOT NULL,
                                                    equipment_id INTEGER NOT NULL,
                                                    status TEXT NOT NULL,
                                                    request_date TEXT NOT NULL,
                                                    resolution_date TEXT,
                                                    FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (equipment_id) REFERENCES equipment (id)
            )
        ''')
        conn.commit()
        conn.close()

    def seed_admin_user(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        if cursor.fetchone() is None:
            try:
                cursor.execute(
                    'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                    ('admin', 'admin', 'Техник')
                )
                conn.commit()
            except sqlite3.IntegrityError:
                pass
        conn.close()

    def create_user(self, username, password, role='Сотрудник'):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                (username, password, role)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    def authenticate_user(self, username, password):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
        conn.close()
        return user

    def add_equipment(self, user_id, equipment_type, inventory_id):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO equipment (user_id, equipment_type, inventory_id) VALUES (?, ?, ?)",
                (user_id, equipment_type, inventory_id)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_user_equipment(self, user_id):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT eq.id, eq.equipment_type, eq.inventory_id, r.status
            FROM equipment eq
            LEFT JOIN requests r ON eq.id = r.equipment_id AND r.status IN ('В ожидании', 'Принята')
            WHERE eq.user_id = ?
            ORDER BY eq.equipment_type
        """, (user_id,))
        items = cursor.fetchall()
        conn.close()
        return items

    def create_replacement_request(self, user_id, equipment_id):
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO requests (user_id, equipment_id, status, request_date) VALUES (?, ?, ?, ?)",
            (user_id, equipment_id, 'В ожидании', date)
        )
        conn.commit()
        conn.close()

    def get_all_active_requests(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.id, u.username, eq.equipment_type, eq.inventory_id, r.status
            FROM requests r
            JOIN users u ON r.user_id = u.id
            JOIN equipment eq ON r.equipment_id = eq.id
            WHERE r.status IN ('В ожидании', 'Принята')
            ORDER BY r.request_date
        """)
        requests = cursor.fetchall()
        conn.close()
        return requests

    def update_request_status(self, request_id, new_status):
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE requests SET status = ?, resolution_date = ? WHERE id = ?",
            (new_status, date, request_id)
        )
        conn.commit()
        conn.close()

    def resolve_request(self, request_id, new_inventory_id):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT equipment_id FROM requests WHERE id = ?", (request_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return

        equipment_id = result[0]
        cursor.execute("UPDATE equipment SET inventory_id = ? WHERE id = ?", (new_inventory_id, equipment_id))
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE requests SET status = ?, resolution_date = ? WHERE id = ?",
            ('Завершена', date, request_id)
        )
        conn.commit()
        conn.close()


class EquipmentItemWidget(QWidget):
    def __init__(self, equipment_data, employee_window):
        super().__init__()
        self.equipment_id = equipment_data[0]
        self.status = equipment_data[3]
        self.employee_window = employee_window

        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        info_text = f"{equipment_data[1]} - ID: {equipment_data[2]}"
        self.info_label = QLabel(info_text)
        self.info_label.setStyleSheet("color: #000000; background-color: transparent; font-size: 11pt;")

        self.status_label = QLabel(self.status if self.status else "")
        font = self.status_label.font()
        font.setBold(True)
        self.status_label.setFont(font)

        if self.status == "В ожидании":
            self.status_label.setStyleSheet("color: #e67e22;")
        elif self.status == "Принята":
            self.status_label.setStyleSheet("color: #27ae60;")
        elif self.status == "Отклонена":
            self.status_label.setStyleSheet("color: #c0392b;")

        self.request_btn = QPushButton("Запросить замену")
        self.request_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.request_btn.setStyleSheet("""
            QPushButton { 
                background-color: #34495e; color: white; 
            }
            QPushButton:disabled {
                background-color: #95a5a6; color: #bdc3c7;
            }
        """)
        self.request_btn.clicked.connect(self.create_request)

        if self.status in ["В ожидании", "Принята"]:
            self.request_btn.setEnabled(False)

        layout.addWidget(self.info_label)
        layout.addStretch()
        layout.addWidget(self.status_label)
        layout.addWidget(self.request_btn)
        self.setLayout(layout)

    def create_request(self):
        self.employee_window.handle_add_request(self.equipment_id)


class RequestItemWidget(QWidget):
    def __init__(self, request_data, tech_window):
        super().__init__()
        self.request_id = request_data[0]
        self.status = request_data[4]
        self.tech_window = tech_window

        main_layout = QVBoxLayout()
        info_layout = QHBoxLayout()
        action_layout = QHBoxLayout()

        info_label_text = f"<b>{request_data[1]}</b>: {request_data[2]} (ID: {request_data[3]})"
        info_label = QLabel(info_label_text)
        # ИСПРАВЛЕНО: Добавлен прозрачный фон, чтобы избежать появления темных прямоугольников, особенно с тегом <b>
        info_label.setStyleSheet("color: #000000; background-color: transparent; font-size: 11pt;")
        info_layout.addWidget(info_label)

        self.accept_btn = QPushButton("Принять")
        self.accept_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.accept_btn.setStyleSheet("background-color: #27ae60; color: white; padding: 5px; border-radius: 3px;")
        self.accept_btn.clicked.connect(self.accept_request)

        self.reject_btn = QPushButton("Отклонить")
        self.reject_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.reject_btn.setStyleSheet("background-color: #c0392b; color: white; padding: 5px; border-radius: 3px;")
        self.reject_btn.clicked.connect(self.reject_request)

        self.new_id_input = QLineEdit()
        self.new_id_input.setPlaceholderText("Введите новый ID")
        self.new_id_input.setStyleSheet("background-color: #ffffff; color: #000000; padding: 5px; border-radius: 3px;")
        self.new_id_input.hide()

        self.complete_btn = QPushButton("Завершить")
        self.complete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.complete_btn.setStyleSheet("background-color: #2980b9; color: white; padding: 5px; border-radius: 3px;")
        self.complete_btn.hide()
        self.complete_btn.clicked.connect(self.complete_request)

        action_layout.addStretch()
        action_layout.addWidget(self.new_id_input)
        action_layout.addWidget(self.complete_btn)
        action_layout.addWidget(self.accept_btn)
        action_layout.addWidget(self.reject_btn)

        main_layout.addLayout(info_layout)
        main_layout.addLayout(action_layout)
        self.setLayout(main_layout)

        if self.status == 'Принята':
            self.show_completion_ui()

    def show_completion_ui(self):
        self.accept_btn.hide()
        self.reject_btn.hide()
        self.new_id_input.show()
        self.complete_btn.show()

    def accept_request(self):
        self.tech_window.db.update_request_status(self.request_id, "Принята")
        self.show_completion_ui()

    def reject_request(self):
        self.tech_window.db.update_request_status(self.request_id, "Отклонена")
        self.tech_window.load_requests()

    def complete_request(self):
        new_id_str = self.new_id_input.text().strip()
        if not new_id_str:
            QMessageBox.warning(self, "Ошибка", "Поле нового ID не может быть пустым.")
            return

        try:
            new_id = int(new_id_str)
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "ID оборудования должен быть числом.")
            return

        self.tech_window.db.resolve_request(self.request_id, new_id)
        self.tech_window.load_requests()


class BaseWindow(QWidget):
    def __init__(self, title, username, auth_window):
        super().__init__()
        self.setWindowTitle(title)
        self.setFixedSize(700, 550)
        self.setStyleSheet("background-color: #2c3e50;")
        self.auth_window = auth_window
        self.db = DatabaseManager()

        layout = QVBoxLayout()
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)

        self.title_label = QLabel(f"Добро пожаловать, {username}!")
        self.title_label.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #ecf0f1;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.content_widget = QWidget()
        layout.addWidget(self.content_widget)
        layout.addStretch()

        logout_btn = QPushButton("Выйти")
        logout_btn.setFixedHeight(45)
        logout_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        logout_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                font-size: 14pt;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        logout_btn.clicked.connect(self.handle_logout)
        layout.addWidget(logout_btn)
        self.setLayout(layout)

    def handle_logout(self):
        self.close()
        if self.auth_window:
            self.auth_window.clear_input_fields()
            self.auth_window.show()


class EmployeeWindow(BaseWindow):
    def __init__(self, user_data, auth_window):
        super().__init__("Панель сотрудника", user_data['username'], auth_window)
        self.user_id = user_data['id']
        self.setup_content_ui()
        self.load_equipment()

    def setup_content_ui(self):
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 10, 0, 10)
        content_layout.setSpacing(15)

        add_frame = QFrame()
        add_frame.setStyleSheet("background-color: #34495e; border-radius: 8px;")
        add_layout = QVBoxLayout(add_frame)

        add_label = QLabel("Добавить новое оборудование:")
        add_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        add_label.setStyleSheet("color: #ecf0f1; background-color: transparent;")

        input_layout = QHBoxLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Монитор", "ПК", "Ноутбук", "Принтер", "Телефон"])
        self.type_combo.setStyleSheet("font-size: 11pt; padding: 5px; color: #000000; background-color: #ffffff;")
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("Инвентарный ID оборудования")
        self.id_input.setStyleSheet("font-size: 11pt; padding: 5px; color: #000000; background-color: #ffffff;")
        add_btn = QPushButton("Добавить")
        add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_btn.setStyleSheet("background-color: #2980b9; color: white; padding: 8px; border-radius: 5px;")
        add_btn.clicked.connect(self.handle_add_equipment)
        input_layout.addWidget(self.type_combo, 1)
        input_layout.addWidget(self.id_input, 2)
        input_layout.addWidget(add_btn, 1)

        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setStyleSheet("color: #ecf0f1; background-color: transparent;")

        add_layout.addWidget(add_label)
        add_layout.addLayout(input_layout)
        add_layout.addWidget(self.message_label)

        list_label = QLabel("Мое оборудование и заявки:")
        list_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        list_label.setStyleSheet("color: #ecf0f1;")

        self.equipment_list = QListWidget()
        self.equipment_list.setStyleSheet(
            "QListWidget { background-color: #ecf0f1; border-radius: 8px; padding: 10px; }"
        )

        content_layout.addWidget(add_frame)
        content_layout.addWidget(list_label)
        content_layout.addWidget(self.equipment_list)

    def load_equipment(self):
        self.equipment_list.clear()
        items = self.db.get_user_equipment(self.user_id)
        if not items:
            placeholder_item = QListWidgetItem("У вас пока нет добавленного оборудования")
            placeholder_item.setForeground(Qt.GlobalColor.darkGray)
            self.equipment_list.addItem(placeholder_item)
        else:
            for item_data in items:
                item_widget = EquipmentItemWidget(item_data, self)
                list_item = QListWidgetItem(self.equipment_list)
                list_item.setSizeHint(item_widget.sizeHint())
                self.equipment_list.addItem(list_item)
                self.equipment_list.setItemWidget(list_item, item_widget)

    def handle_add_equipment(self):
        equipment_type = self.type_combo.currentText()
        inventory_id_str = self.id_input.text().strip()

        if not inventory_id_str:
            self.message_label.setStyleSheet("color: #f1c40f;")
            self.message_label.setText("Пожалуйста, введите инвентарный ID.")
            return

        try:
            inventory_id = int(inventory_id_str)
        except ValueError:
            self.message_label.setStyleSheet("color: #e74c3c;")
            self.message_label.setText("ID оборудования должен быть числом.")
            return

        success = self.db.add_equipment(self.user_id, equipment_type, inventory_id)
        if success:
            self.message_label.setStyleSheet("color: #2ecc71;")
            self.message_label.setText(f"Оборудование '{inventory_id}' успешно добавлено!")
            self.id_input.clear()
            self.load_equipment()
        else:
            self.message_label.setStyleSheet("color: #e74c3c;")
            self.message_label.setText("Ошибка: Оборудование с таким ID уже существует.")

    def handle_add_request(self, equipment_id):
        self.db.create_replacement_request(self.user_id, equipment_id)
        self.load_equipment()


class TechSupportWindow(BaseWindow):
    def __init__(self, user_data, auth_window):
        super().__init__("Панель техподдержки", user_data['username'], auth_window)
        self.setup_content_ui()
        self.load_requests()

    def setup_content_ui(self):
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 10, 0, 10)

        requests_label = QLabel("Активные заявки на замену:")
        requests_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        requests_label.setStyleSheet("color: #ecf0f1;")

        self.requests_list = QListWidget()
        self.requests_list.setStyleSheet(
            "QListWidget { background-color: #ecf0f1; border-radius: 8px; padding: 10px; }"
        )

        content_layout.addWidget(requests_label)
        content_layout.addWidget(self.requests_list)

    def load_requests(self):
        self.requests_list.clear()
        requests = self.db.get_all_active_requests()
        if not requests:
            placeholder_item = QListWidgetItem("Нет активных заявок")
            placeholder_item.setForeground(Qt.GlobalColor.darkGray)
            self.requests_list.addItem(placeholder_item)
        else:
            for req_data in requests:
                item_widget = RequestItemWidget(req_data, self)
                list_item = QListWidgetItem(self.requests_list)
                list_item.setSizeHint(QSize(0, 70))
                self.requests_list.addItem(list_item)
                self.requests_list.setItemWidget(list_item, item_widget)


class TechAdminCreationWindow(QWidget):
    def __init__(self, auth_window):
        super().__init__()
        self.auth_window = auth_window
        self.db = DatabaseManager()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Администрирование техников")
        self.setFixedSize(500, 400)
        self.setStyleSheet("background-color: #34495e;")

        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        title = QLabel("Создание учетной записи техника")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #ecf0f1;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Логин нового техника")
        self.username_edit.setFixedHeight(40)
        self.username_edit.setStyleSheet("font-size: 11pt; padding: 10px; border-radius: 5px; color: #000000; background-color: #ffffff;")

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Пароль нового техника")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setFixedHeight(40)
        self.password_edit.setStyleSheet("font-size: 11pt; padding: 10px; border-radius: 5px; color: #000000; background-color: #ffffff;")

        self.message_label = QLabel("")
        self.message_label.setStyleSheet("color: white; font-size: 10pt;")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        create_btn = QPushButton("Создать пользователя")
        create_btn.setFixedHeight(45)
        create_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                font-size: 12pt;
            }
            QPushButton:hover { background-color: #27ae60; }
        """)
        create_btn.clicked.connect(self.create_tech_user)

        back_btn = QPushButton("Назад к авторизации")
        back_btn.setFixedHeight(45)
        back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                font-size: 12pt;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        back_btn.clicked.connect(self.handle_back_to_login)

        layout.addWidget(self.username_edit)
        layout.addWidget(self.password_edit)
        layout.addWidget(create_btn)
        layout.addWidget(self.message_label)
        layout.addStretch()
        layout.addWidget(back_btn)
        self.setLayout(layout)

    def create_tech_user(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        if not username or not password:
            self.message_label.setStyleSheet("color: #f1c40f;")
            self.message_label.setText("Пожалуйста, заполните все поля.")
            return

        if self.db.create_user(username, password, role='Техник'):
            self.message_label.setStyleSheet("color: #2ecc71;")
            self.message_label.setText(f"Пользователь '{username}' успешно создан!")
            self.username_edit.clear()
            self.password_edit.clear()
        else:
            self.message_label.setStyleSheet("color: #e74c3c;")
            self.message_label.setText(f"Имя пользователя '{username}' уже занято.")

    def handle_back_to_login(self):
        self.close()
        if self.auth_window:
            self.auth_window.clear_input_fields()
            self.auth_window.show()


class AuthWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.main_app_window = None
        self.tech_admin_window = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Система 'Учет': Авторизация")
        self.setFixedSize(400, 500)
        self.setStyleSheet("background-color: #f2f3f5;")

        self.stacked_widget = QStackedWidget()
        self.login_window = self.create_login_window()
        self.register_window = self.create_register_window()

        self.stacked_widget.addWidget(self.login_window)
        self.stacked_widget.addWidget(self.register_window)

        layout = QVBoxLayout(self)
        layout.addWidget(self.stacked_widget)

    def create_input_field(self, placeholder, is_password=False):
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setFixedHeight(40)
        if is_password:
            field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setStyleSheet("""
            QLineEdit {
                background: #fff;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 11pt;
                color: #000000;
            }
            QLineEdit:focus { border: 1px solid #4A90E2; }
        """)
        return field

    def create_card(self, title, widgets, switch_text, switch_callback):
        card = QFrame()
        card.setStyleSheet("background: white; border-radius: 12px; border: 1px solid #e1e1e1;")
        card.setFixedSize(350, 420)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #333;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        layout.addSpacing(10)

        for widget in widgets:
            layout.addWidget(widget)

        layout.addStretch()
        switch_label = QLabel(f'<a href="#" style="color: #555;">{switch_text}</a>')
        switch_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        switch_label.mousePressEvent = switch_callback
        layout.addWidget(switch_label)
        return card

    def create_login_window(self):
        window = QWidget()
        layout = QVBoxLayout(window)

        self.login_info_label = QLabel("")
        self.login_info_label.setStyleSheet("color: #27ae60; font-size: 9pt;")
        self.login_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.login_username = self.create_input_field("Имя пользователя")
        self.login_password = self.create_input_field("Пароль", True)

        self.login_error_label = QLabel("")
        self.login_error_label.setStyleSheet("color: #e74c3c; font-size: 9pt;")
        self.login_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        login_btn = QPushButton("Войти")
        login_btn.setFixedHeight(45)
        login_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        login_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #357ABD; }
        """)
        login_btn.clicked.connect(self.handle_login)

        widgets = [self.login_info_label, self.login_username, self.login_password, self.login_error_label, login_btn]
        card = self.create_card("Вход в систему", widgets, "Нет аккаунта? Зарегистрироваться", self.show_register)
        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        return window

    def create_register_window(self):
        window = QWidget()
        layout = QVBoxLayout(window)

        self.reg_username = self.create_input_field("Имя пользователя")
        self.reg_password = self.create_input_field("Пароль", True)
        self.reg_confirm = self.create_input_field("Подтвердите пароль", True)

        self.register_error_label = QLabel("")
        self.register_error_label.setStyleSheet("color: #e74c3c; font-size: 9pt;")
        self.register_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        register_btn = QPushButton("Зарегистрироваться")
        register_btn.setFixedHeight(45)
        register_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        register_btn.setStyleSheet("""
            QPushButton {
                background-color: #5cb85c;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #4cae4c; }
        """)
        register_btn.clicked.connect(self.handle_register)

        widgets = [self.reg_username, self.reg_password, self.reg_confirm, self.register_error_label, register_btn]
        card = self.create_card("Регистрация", widgets, "Уже есть аккаунт? Войти", self.show_login)
        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        return window

    def clear_input_fields(self):
        self.login_username.clear()
        self.login_password.clear()
        self.login_info_label.clear()
        self.login_error_label.clear()
        self.reg_username.clear()
        self.reg_password.clear()
        self.reg_confirm.clear()
        self.register_error_label.clear()

    def show_login(self, event=None):
        self.clear_input_fields()
        self.stacked_widget.setCurrentIndex(0)

    def show_register(self, event=None):
        self.clear_input_fields()
        self.stacked_widget.setCurrentIndex(1)

    def handle_login(self):
        self.login_error_label.setText("")
        self.login_info_label.setText("")
        username = self.login_username.text().strip()
        password = self.login_password.text()

        if not username or not password:
            self.login_error_label.setText("Пожалуйста, заполните все поля.")
            return

        if username == 'admintx' and password == 'admintx':
            self.hide()
            self.tech_admin_window = TechAdminCreationWindow(self)
            self.tech_admin_window.show()
            return

        user_data = self.db.authenticate_user(username, password)
        if user_data:
            self.hide()
            if user_data['role'] == 'Техник':
                self.main_app_window = TechSupportWindow(user_data, self)
            else:
                self.main_app_window = EmployeeWindow(user_data, self)
            self.main_app_window.show()
        else:
            self.login_error_label.setText("Неверное имя пользователя или пароль.")

    def handle_register(self):
        self.register_error_label.setText("")
        username = self.reg_username.text().strip()
        password = self.reg_password.text()
        confirm_password = self.reg_confirm.text()

        if not username or not password or not confirm_password:
            self.register_error_label.setText("Пожалуйста, заполните все поля.")
            return
        if password != confirm_password:
            self.register_error_label.setText("Пароли не совпадают.")
            return
        if len(password) < 4:
            self.register_error_label.setText("Пароль должен быть не менее 4 символов.")
            return

        if self.db.create_user(username, password):
            self.show_login()
            self.login_info_label.setText("Регистрация успешна! Теперь вы можете войти.")
        else:
            self.register_error_label.setText("Это имя пользователя уже занято.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AuthWindow()
    window.show()
    sys.exit(app.exec())