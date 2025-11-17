import sys
import sqlite3
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFrame, QStackedWidget,
    QListWidget, QComboBox, QListWidgetItem, QMessageBox, QMainWindow
)
from PyQt6.QtGui import QFont, QCursor
from PyQt6.QtCore import Qt, QSize, pyqtSignal


class DatabaseManager:
    def __init__(self, db_name='office_system.db'):
        self.db_name = db_name
        self.init_database()
        self.seed_admin_user()

    def init_database(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL DEFAULT 'Сотрудник'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                equipment_type TEXT NOT NULL,
                inventory_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
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
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (equipment_id) REFERENCES equipment (id) ON DELETE CASCADE
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
                    'INSERT INTO users (username, password, full_name, email, role) VALUES (?, ?, ?, ?, ?)',
                    ('admin', 'admin', 'Главный Техник', 'admin@example.com', 'Техник')
                )
                conn.commit()
            except sqlite3.IntegrityError:
                pass
        conn.close()

    def create_user(self, username, password, full_name, email, role='Сотрудник'):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, password, full_name, email, role) VALUES (?, ?, ?, ?, ?)',
                (username, password, full_name, email, role)
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
            SELECT eq.id, eq.equipment_type, eq.inventory_id, 
                   (SELECT r.status FROM requests r 
                    WHERE r.equipment_id = eq.id 
                    ORDER BY r.id DESC LIMIT 1) as status
            FROM equipment eq
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
            "UPDATE requests SET status = 'Завершена', resolution_date = ? WHERE id = ?",
            (date, request_id)
        )
        conn.commit()
        conn.close()

    def get_all_technicians(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, full_name, email FROM users WHERE role = 'Техник' AND username != 'admin'")
        technicians = cursor.fetchall()
        conn.close()
        return technicians

    def delete_user(self, user_id):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Ошибка при удалении пользователя: {e}")
            return False

    def delete_equipment(self, equipment_id):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.execute("DELETE FROM requests WHERE equipment_id = ?", (equipment_id,))
            cursor.execute("DELETE FROM equipment WHERE id = ?", (equipment_id,))
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Ошибка при удалении оборудования: {e}")
            return False


class EquipmentItemWidget(QWidget):
    def __init__(self, equipment_data, employee_window):
        super().__init__()
        self.equipment_id, self.status, self.employee_window = equipment_data[0], equipment_data[3], employee_window
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.info_label = QLabel(f"{equipment_data[1]} - ID: {equipment_data[2]}")
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
        self.request_btn.setStyleSheet(
            "QPushButton { background-color: #34495e; color: white; padding: 5px; border-radius: 3px; } QPushButton:disabled { background-color: #95a5a6; color: #bdc3c7; }")
        self.request_btn.clicked.connect(self.create_request)

        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.delete_btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 5px; border-radius: 3px;")
        self.delete_btn.clicked.connect(self.delete_equipment)

        if self.status in ["В ожидании", "Принята"]:
            self.request_btn.setEnabled(False)

        layout.addWidget(self.info_label)
        layout.addStretch()
        layout.addWidget(self.status_label)
        layout.addWidget(self.request_btn)
        layout.addWidget(self.delete_btn)

    def create_request(self):
        self.employee_window.handle_add_request(self.equipment_id)

    def delete_equipment(self):
        if self.employee_window.db.delete_equipment(self.equipment_id):
            self.employee_window.load_content()
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось удалить оборудование.")


class RequestItemWidget(QWidget):
    def __init__(self, request_data, tech_window):
        super().__init__()
        self.request_id, self.status, self.tech_window = request_data[0], request_data[4], tech_window
        main_layout = QVBoxLayout(self);
        info_layout, action_layout = QHBoxLayout(), QHBoxLayout()
        info_label = QLabel(f"<b>{request_data[1]}</b>: {request_data[2]} (ID: {request_data[3]})")
        info_label.setStyleSheet("color: #000000; background-color: transparent; font-size: 11pt;")
        info_layout.addWidget(info_label)
        self.accept_btn = QPushButton("Принять");
        self.accept_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor));
        self.accept_btn.setStyleSheet("background-color: #27ae60; color: white; padding: 5px; border-radius: 3px;");
        self.accept_btn.clicked.connect(self.accept_request)
        self.reject_btn = QPushButton("Отклонить");
        self.reject_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor));
        self.reject_btn.setStyleSheet("background-color: #c0392b; color: white; padding: 5px; border-radius: 3px;");
        self.reject_btn.clicked.connect(self.reject_request)
        self.new_id_input = QLineEdit();
        self.new_id_input.setPlaceholderText("Введите новый ID");
        self.new_id_input.setStyleSheet("background-color: #ffffff; color: #000000; padding: 5px; border-radius: 3px;");
        self.new_id_input.hide()
        self.complete_btn = QPushButton("Завершить");
        self.complete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor));
        self.complete_btn.setStyleSheet("background-color: #2980b9; color: white; padding: 5px; border-radius: 3px;");
        self.complete_btn.hide();
        self.complete_btn.clicked.connect(self.complete_request)
        action_layout.addStretch();
        action_layout.addWidget(self.new_id_input);
        action_layout.addWidget(self.complete_btn);
        action_layout.addWidget(self.accept_btn);
        action_layout.addWidget(self.reject_btn)
        main_layout.addLayout(info_layout);
        main_layout.addLayout(action_layout)
        if self.status == 'Принята': self.show_completion_ui()

    def show_completion_ui(self):
        self.accept_btn.hide();
        self.reject_btn.hide();
        self.new_id_input.show();
        self.complete_btn.show()

    def accept_request(self):
        self.tech_window.db.update_request_status(self.request_id, "Принята")
        self.tech_window.load_content()

    def reject_request(self):
        self.tech_window.db.update_request_status(self.request_id, "Отклонена")
        self.tech_window.load_content()

    def complete_request(self):
        new_id_str = self.new_id_input.text().strip()
        if not new_id_str: QMessageBox.warning(self, "Ошибка", "Поле нового ID не может быть пустым."); return
        try:
            new_id = int(new_id_str)
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "ID оборудования должен быть числом.");
            return
        self.tech_window.db.resolve_request(self.request_id, new_id)
        self.tech_window.load_content()


class BaseWidget(QWidget):
    logout_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #2c3e50;")
        self.db = DatabaseManager()
        self.user_data = None

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(25, 25, 25, 25);
        self.main_layout.setSpacing(20)
        self.title_label = QLabel("Добро пожаловать!");
        self.title_label.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold));
        self.title_label.setStyleSheet("color: #ecf0f1;");
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_widget = QWidget()
        logout_btn = QPushButton("Выйти");
        logout_btn.setFixedHeight(45);
        logout_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor));
        logout_btn.setStyleSheet(
            "QPushButton { background-color: #e74c3c; color: white; font-weight: bold; border: none; border-radius: 8px; font-size: 14pt; } QPushButton:hover { background-color: #c0392b; }");
        logout_btn.clicked.connect(self.logout_requested.emit)

        self.main_layout.addWidget(self.title_label)
        self.main_layout.addWidget(self.content_widget, 1)
        self.main_layout.addWidget(logout_btn)

    def set_user_data(self, user_data):
        self.user_data = user_data
        self.title_label.setText(f"Добро пожаловать, {self.user_data['username']}!")
        if hasattr(self, 'load_content'): self.load_content()


class EmployeeWidget(BaseWidget):
    def __init__(self):
        super().__init__()
        self.setup_content_ui()

    def setup_content_ui(self):
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0);
        content_layout.setSpacing(15)
        add_frame = QFrame();
        add_frame.setStyleSheet("background-color: #34495e; border-radius: 8px; padding: 15px;")
        add_layout = QVBoxLayout(add_frame)
        add_label = QLabel("Добавить новое оборудование:");
        add_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold));
        add_label.setStyleSheet("color: #ecf0f1; background-color: transparent;")
        input_layout = QHBoxLayout()
        self.type_combo = QComboBox();
        self.type_combo.addItems(["Монитор", "ПК", "Ноутбук", "Принтер", "Телефон"]);
        self.type_combo.setStyleSheet(
            "font-size: 11pt; padding: 5px; color: #000000; background-color: #ffffff; border-radius: 3px;")
        self.id_input = QLineEdit();
        self.id_input.setPlaceholderText("Инвентарный ID");
        self.id_input.setStyleSheet(
            "font-size: 11pt; padding: 5px; color: #000000; background-color: #ffffff; border-radius: 3px;")
        add_btn = QPushButton("Добавить");
        add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor));
        add_btn.setStyleSheet("background-color: #2980b9; color: white; padding: 8px; border-radius: 5px;");
        add_btn.clicked.connect(self.handle_add_equipment)
        input_layout.addWidget(self.type_combo, 1);
        input_layout.addWidget(self.id_input, 2);
        input_layout.addWidget(add_btn, 1)
        self.message_label = QLabel("");
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter);
        self.message_label.setStyleSheet("color: #ecf0f1; background-color: transparent;");
        self.message_label.setFixedHeight(20)
        add_layout.addWidget(add_label);
        add_layout.addLayout(input_layout);
        add_layout.addWidget(self.message_label)
        list_label = QLabel("Мое оборудование и заявки:");
        list_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold));
        list_label.setStyleSheet("color: #ecf0f1;")
        self.equipment_list = QListWidget();
        self.equipment_list.setStyleSheet(
            "QListWidget { background-color: #ecf0f1; border-radius: 8px; padding: 10px; }")
        content_layout.addWidget(add_frame);
        content_layout.addWidget(list_label);
        content_layout.addWidget(self.equipment_list)

    def load_content(self):
        self.equipment_list.clear()
        if not self.user_data: return
        items = self.db.get_user_equipment(self.user_data['id'])
        if not items:
            self.equipment_list.addItem(QListWidgetItem("У вас пока нет добавленного оборудования"))
        else:
            for item_data in items:
                item_widget = EquipmentItemWidget(item_data, self)
                list_item = QListWidgetItem();
                list_item.setSizeHint(item_widget.sizeHint())
                self.equipment_list.addItem(list_item);
                self.equipment_list.setItemWidget(list_item, item_widget)

    def handle_add_equipment(self):
        inventory_id_str = self.id_input.text().strip()
        if not inventory_id_str: self.message_label.setStyleSheet("color: #f1c40f;"); self.message_label.setText(
            "Пожалуйста, введите инвентарный ID."); return
        try:
            inventory_id = int(inventory_id_str)
        except ValueError:
            self.message_label.setStyleSheet("color: #e74c3c;");
            self.message_label.setText(
                "ID оборудования должен быть числом.");
            return
        if self.db.add_equipment(self.user_data['id'], self.type_combo.currentText(), inventory_id):
            self.message_label.setStyleSheet("color: #2ecc71;");
            self.message_label.setText("Оборудование успешно добавлено!");
            self.id_input.clear();
            self.load_content()
        else:
            self.message_label.setStyleSheet("color: #e74c3c;");
            self.message_label.setText(
                "Ошибка: Оборудование с таким ID уже существует.")

    def handle_add_request(self, equipment_id):
        self.db.create_replacement_request(self.user_data['id'], equipment_id);
        self.load_content()


class TechSupportWidget(BaseWidget):
    def __init__(self):
        super().__init__()
        self.setup_content_ui()

    def setup_content_ui(self):
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0);
        content_layout.setSpacing(15)
        requests_label = QLabel("Активные заявки на замену:");
        requests_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold));
        requests_label.setStyleSheet("color: #ecf0f1;")
        self.requests_list = QListWidget();
        self.requests_list.setStyleSheet(
            "QListWidget { background-color: #ecf0f1; border-radius: 8px; padding: 10px; }")
        content_layout.addWidget(requests_label);
        content_layout.addWidget(self.requests_list)

    def load_content(self):
        self.requests_list.clear()
        requests = self.db.get_all_active_requests()
        if not requests:
            self.requests_list.addItem(QListWidgetItem("Нет активных заявок"))
        else:
            for req_data in requests:
                item_widget = RequestItemWidget(req_data, self)
                list_item = QListWidgetItem();
                list_item.setSizeHint(QSize(0, 70))
                self.requests_list.addItem(list_item);
                self.requests_list.setItemWidget(list_item, item_widget)


class TechUserItemWidget(QWidget):
    def __init__(self, tech_data, admin_window):
        super().__init__()
        self.tech_id, self.admin_window = tech_data[0], admin_window
        layout = QHBoxLayout(self)
        info_label = QLabel(f"<b>{tech_data[2]}</b> ({tech_data[1]}) - {tech_data[3]}");
        info_label.setStyleSheet("color: #000000; background-color: transparent; font-size: 11pt;")
        delete_btn = QPushButton("Удалить");
        delete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor));
        delete_btn.setStyleSheet("background-color: #c0392b; color: white; padding: 5px; border-radius: 3px;");
        delete_btn.clicked.connect(self.delete_user)
        layout.addWidget(info_label);
        layout.addStretch();
        layout.addWidget(delete_btn)

    def delete_user(self):
        reply = QMessageBox.question(self, 'Подтверждение', f"Вы уверены, что хотите удалить этого техника?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.admin_window.db.delete_user(self.tech_id):
                self.admin_window.load_content()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось удалить пользователя.")


class TechAdminManagementWidget(BaseWidget):
    def __init__(self):
        super().__init__()
        self.title_label.setText("Администрирование техников")
        self.setup_content_ui()

    def setup_content_ui(self):
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0);
        content_layout.setSpacing(15)
        creation_frame = QFrame();
        creation_frame.setStyleSheet("background-color: #34495e; border-radius: 8px; padding: 15px;")
        creation_layout = QVBoxLayout(creation_frame)
        title = QLabel("Создание учетной записи техника");
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold));
        title.setStyleSheet("color: #ecf0f1; background: transparent;");
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.username_edit = QLineEdit();
        self.username_edit.setPlaceholderText("Логин");
        self.username_edit.setStyleSheet(
            "font-size: 11pt; padding: 10px; border-radius: 5px; color: #000000; background-color: #ffffff;")
        self.password_edit = QLineEdit();
        self.password_edit.setPlaceholderText("Пароль");
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password);
        self.password_edit.setStyleSheet(
            "font-size: 11pt; padding: 10px; border-radius: 5px; color: #000000; background-color: #ffffff;")
        self.fullname_edit = QLineEdit();
        self.fullname_edit.setPlaceholderText("ФИО");
        self.fullname_edit.setStyleSheet(
            "font-size: 11pt; padding: 10px; border-radius: 5px; color: #000000; background-color: #ffffff;")
        self.email_edit = QLineEdit();
        self.email_edit.setPlaceholderText("Электронная почта");
        self.email_edit.setStyleSheet(
            "font-size: 11pt; padding: 10px; border-radius: 5px; color: #000000; background-color: #ffffff;")
        self.message_label = QLabel("");
        self.message_label.setStyleSheet("color: white; font-size: 10pt; background: transparent;");
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter);
        self.message_label.setFixedHeight(20)
        create_btn = QPushButton("Создать пользователя");
        create_btn.setFixedHeight(45);
        create_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor));
        create_btn.setStyleSheet(
            "QPushButton { background-color: #2ecc71; color: white; font-weight: bold; border-radius: 8px; font-size: 12pt; } QPushButton:hover { background-color: #27ae60; }");
        create_btn.clicked.connect(self.create_tech_user)
        creation_layout.addWidget(title);
        creation_layout.addWidget(self.fullname_edit);
        creation_layout.addWidget(self.email_edit);
        creation_layout.addWidget(self.username_edit);
        creation_layout.addWidget(self.password_edit);
        creation_layout.addWidget(create_btn);
        creation_layout.addWidget(self.message_label)
        list_label = QLabel("Существующие техники:");
        list_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold));
        list_label.setStyleSheet("color: #ecf0f1; margin-top: 10px;")
        self.tech_list = QListWidget();
        self.tech_list.setStyleSheet("background-color: #ecf0f1; border-radius: 8px; padding: 10px;")
        content_layout.addWidget(creation_frame);
        content_layout.addWidget(list_label);
        content_layout.addWidget(self.tech_list)

    def load_content(self):
        self.tech_list.clear()
        technicians = self.db.get_all_technicians()
        if not technicians:
            self.tech_list.addItem("Нет созданных техников")
        else:
            for tech in technicians:
                item_widget = TechUserItemWidget(tech, self)
                list_item = QListWidgetItem();
                list_item.setSizeHint(item_widget.sizeHint())
                self.tech_list.addItem(list_item);
                self.tech_list.setItemWidget(list_item, item_widget)

    def create_tech_user(self):
        username = self.username_edit.text().strip();
        password = self.password_edit.text();
        full_name = self.fullname_edit.text().strip();
        email = self.email_edit.text().strip()
        if not all([username, password, full_name, email]): self.message_label.setStyleSheet(
            "color: #f1c40f;"); self.message_label.setText("Пожалуйста, заполните все поля."); return
        if self.db.create_user(username, password, full_name, email, role='Техник'):
            self.message_label.setStyleSheet("color: #2ecc71;");
            self.message_label.setText(f"Пользователь '{username}' успешно создан!")
            self.username_edit.clear();
            self.password_edit.clear();
            self.fullname_edit.clear();
            self.email_edit.clear();
            self.load_content()
        else:
            self.message_label.setStyleSheet("color: #e74c3c;");
            self.message_label.setText(
                f"Имя пользователя или email уже заняты.")


class AuthWidget(QWidget):
    login_successful = pyqtSignal(dict);
    admin_login_successful = pyqtSignal();
    registration_successful = pyqtSignal(str)

    def __init__(self):
        super().__init__();
        self.db = DatabaseManager();
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("background-color: #f2f3f5;")
        self.stacked_widget = QStackedWidget(self)
        self.stacked_widget.addWidget(self.create_login_window())
        self.stacked_widget.addWidget(self.create_register_window())
        layout = QHBoxLayout(self);
        layout.addWidget(self.stacked_widget);
        layout.setContentsMargins(0, 0, 0, 0)

    def create_input_field(self, placeholder, is_password=False):
        field = QLineEdit();
        field.setPlaceholderText(placeholder);
        field.setFixedHeight(45)
        if is_password: field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setStyleSheet(
            "QLineEdit { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 10px 12px; font-size: 11pt; color: #000000; } QLineEdit:focus { border: 1px solid #4A90E2; }")
        return field

    def create_card(self, title, widgets, switch_text, switch_callback, height=450):
        card = QFrame();
        card.setStyleSheet("background: white; border-radius: 12px;");
        card.setFixedSize(380, height)
        layout = QVBoxLayout(card);
        layout.setContentsMargins(35, 30, 35, 30);
        layout.setSpacing(15);
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        title_label = QLabel(title);
        title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold));
        title_label.setStyleSheet("color: #333;");
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label);
        layout.addSpacing(20)
        for widget in widgets: layout.addWidget(widget)
        layout.addStretch()
        switch_label = QLabel(f'<a href="#" style="color: #555; text-decoration: none;">{switch_text}</a>');
        switch_label.setAlignment(Qt.AlignmentFlag.AlignCenter);
        switch_label.mousePressEvent = switch_callback
        layout.addWidget(switch_label)
        return card

    def create_login_window(self):
        window = QWidget();
        layout = QVBoxLayout(window);
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.login_info_label = QLabel("");
        self.login_info_label.setStyleSheet("color: #27ae60; font-size: 9pt;");
        self.login_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.login_username = self.create_input_field("Имя пользователя");
        self.login_password = self.create_input_field("Пароль", True)
        self.login_error_label = QLabel("");
        self.login_error_label.setStyleSheet("color: #e74c3c; font-size: 9pt;");
        self.login_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        login_btn = QPushButton("Войти");
        login_btn.setFixedHeight(45);
        login_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor));
        login_btn.setStyleSheet(
            "QPushButton { background-color: #4A90E2; color: white; font-weight: bold; border: none; border-radius: 8px; font-size: 12pt;} QPushButton:hover { background-color: #357ABD; }");
        login_btn.clicked.connect(self.handle_login)
        card = self.create_card("Вход в систему", [self.login_info_label, self.login_username, self.login_password,
                                                   self.login_error_label, login_btn],
                                "Нет аккаунта? <b>Зарегистрироваться</b>", self.show_register)
        layout.addWidget(card);
        return window

    def create_register_window(self):
        window = QWidget();
        layout = QVBoxLayout(window);
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reg_fullname = self.create_input_field("ФИО");
        self.reg_email = self.create_input_field("Электронная почта");
        self.reg_username = self.create_input_field("Имя пользователя");
        self.reg_password = self.create_input_field("Пароль", True);
        self.reg_confirm = self.create_input_field("Подтвердите пароль", True)
        self.register_error_label = QLabel("");
        self.register_error_label.setStyleSheet("color: #e74c3c; font-size: 9pt;");
        self.register_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        register_btn = QPushButton("Зарегистрироваться");
        register_btn.setFixedHeight(45);
        register_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor));
        register_btn.setStyleSheet(
            "QPushButton { background-color: #5cb85c; color: white; font-weight: bold; border: none; border-radius: 8px; font-size: 12pt; } QPushButton:hover { background-color: #4cae4c; }");
        register_btn.clicked.connect(self.handle_register)
        card = self.create_card("Регистрация", [self.reg_fullname, self.reg_email, self.reg_username, self.reg_password,
                                                self.reg_confirm, self.register_error_label, register_btn],
                                "Уже есть аккаунт? <b>Войти</b>", self.show_login, height=550)
        layout.addWidget(card);
        return window

    def clear_input_fields(self):
        self.login_username.clear();
        self.login_password.clear();
        self.login_info_label.clear();
        self.login_error_label.clear();
        self.reg_fullname.clear();
        self.reg_email.clear();
        self.reg_username.clear();
        self.reg_password.clear();
        self.reg_confirm.clear();
        self.register_error_label.clear()

    def show_login_with_message(self, message):
        self.clear_input_fields();
        self.login_info_label.setText(message);
        self.stacked_widget.setCurrentIndex(0)

    def show_login(self, event=None):
        self.clear_input_fields();
        self.stacked_widget.setCurrentIndex(0)

    def show_register(self, event=None):
        self.clear_input_fields();
        self.stacked_widget.setCurrentIndex(1)

    def handle_login(self):
        self.login_error_label.setText("");
        self.login_info_label.setText("")
        username = self.login_username.text().strip();
        password = self.login_password.text()
        if not username or not password: self.login_error_label.setText("Пожалуйста, заполните все поля."); return
        if username == 'admintx' and password == 'admintx': self.admin_login_successful.emit(); return
        user_data = self.db.authenticate_user(username, password)
        if user_data:
            self.login_successful.emit(dict(user_data))
        else:
            self.login_error_label.setText("Неверное имя пользователя или пароль.")

    def handle_register(self):
        self.register_error_label.setText("")
        full_name = self.reg_fullname.text().strip();
        email = self.reg_email.text().strip();
        username = self.reg_username.text().strip();
        password = self.reg_password.text();
        confirm_password = self.reg_confirm.text()
        if not all([full_name, email, username, password, confirm_password]): self.register_error_label.setText(
            "Пожалуйста, заполните все поля."); return
        if password != confirm_password: self.register_error_label.setText("Пароли не совпадают."); return
        if len(password) < 1: self.register_error_label.setText("Пароль должен быть не менее 4 символов."); return
        if '@' not in email or '.' not in email: self.register_error_label.setText("Введите корректный email."); return
        if self.db.create_user(username, password, full_name, email):
            self.registration_successful.emit("Регистрация успешна! Теперь вы можете войти.")
        else:
            self.register_error_label.setText("Это имя пользователя или email уже заняты.")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Система 'Учет'")
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        self.auth_widget = AuthWidget()
        self.employee_widget = EmployeeWidget()
        self.tech_support_widget = TechSupportWidget()
        self.tech_admin_widget = TechAdminManagementWidget()
        self.stacked_widget.addWidget(self.auth_widget)
        self.stacked_widget.addWidget(self.employee_widget)
        self.stacked_widget.addWidget(self.tech_support_widget)
        self.stacked_widget.addWidget(self.tech_admin_widget)
        self.auth_widget.login_successful.connect(self.handle_successful_login)
        self.auth_widget.admin_login_successful.connect(self.show_admin_panel)
        self.auth_widget.registration_successful.connect(self.handle_successful_registration)
        self.employee_widget.logout_requested.connect(self.handle_logout)
        self.tech_support_widget.logout_requested.connect(self.handle_logout)
        self.tech_admin_widget.logout_requested.connect(self.handle_logout)
        self.handle_logout()

    def handle_successful_login(self, user_data):
        self.auth_widget.clear_input_fields()
        if user_data['role'] == 'Техник':
            self.setFixedSize(700, 600);
            self.tech_support_widget.set_user_data(user_data);
            self.stacked_widget.setCurrentWidget(self.tech_support_widget)
        else:
            self.setFixedSize(700, 650);
            self.employee_widget.set_user_data(user_data);
            self.stacked_widget.setCurrentWidget(self.employee_widget)

    def show_admin_panel(self):
        self.auth_widget.clear_input_fields();
        self.setFixedSize(700, 750);
        self.tech_admin_widget.load_content();
        self.stacked_widget.setCurrentWidget(self.tech_admin_widget)

    def handle_successful_registration(self, message):
        self.auth_widget.show_login_with_message(message)

    def handle_logout(self):
        self.auth_widget.clear_input_fields();
        self.setFixedSize(450, 600);
        self.stacked_widget.setCurrentWidget(self.auth_widget)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
