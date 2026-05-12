from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QWidget,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QFont, QPainter, QPainterPath
import os
from db import verify_user
from usuario_activo import guardar_usuario_activo


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KyoGym - Iniciar sesión")
        self.setMinimumSize(980, 620)
        # Permitir que el diálogo se muestre como ventana principal para poder maximizar
        self.setWindowFlag(Qt.Window)
        self.init_ui()

    def init_ui(self):
        root = os.path.dirname(os.path.dirname(__file__))
        assets_path = os.path.join(root, "assets")
        logo_path = os.path.join(assets_path, "logo.png")

        self.setStyleSheet("""
            QDialog {
                background-color: #0a0a0a;
            }
            QMessageBox {
                background-color: #ffffff;
            }
            QMessageBox QLabel {
                color: #000000;
                font-size: 13px;
            }
            QMessageBox QPushButton {
                color: #ffffff;
                background-color: #3498db;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #2980b9;
            }
            QFrame#LoginCard {
                background-color: #111111;
                border: 1px solid #4d4d4d;
                border-radius: 18px;
            }
            QLabel#BrandLabel {
                color: #cfcfcf;
                font-size: 13px;
                font-weight: 600;
                letter-spacing: 0.4px;
            }
            QLabel#TitleLabel {
                color: #ffffff;
                font-size: 30px;
                font-weight: 700;
                letter-spacing: 1px;
            }
            QLabel#SubTitleLabel {
                color: #dddddd;
                font-size: 15px;
            }
            QLabel#FieldLabel {
                color: #efefef;
                font-size: 13px;
                font-weight: 600;
            }
            QLineEdit {
                background-color: transparent;
                color: #ffffff;
                border: 2px solid #8f8f8f;
                border-radius: 16px;
                padding: 10px 14px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 2px solid #ffffff;
            }
            QLineEdit::placeholder {
                color: #b5b5b5;
            }
            QPushButton#LoginButton {
                background-color: #c0c0c0;
                color: #000000;
                border: 2px solid #ffffff;
                border-radius: 17px;
                font-size: 16px;
                font-weight: 700;
                padding: 10px;
            }
            QPushButton#LoginButton:hover {
                background-color: #d8d8d8;
            }
            QLabel#CircleBorder {
                border: 4px solid #c0c0c0;
                border-radius: 160px;
                background-color: #181818;
            }
            QLabel#AccentText {
                color: #d0d0d0;
                font-size: 13px;
                font-weight: 600;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(48, 48, 48, 48)

        login_card = QFrame()
        login_card.setObjectName("LoginCard")
        card_layout = QHBoxLayout(login_card)
        card_layout.setContentsMargins(34, 30, 34, 30)
        card_layout.setSpacing(22)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 6, 20, 6)
        left_layout.setSpacing(14)

        brand = QLabel("KyoGym")
        brand.setObjectName("BrandLabel")
        left_layout.addWidget(brand)

        title = QLabel("¡BIENVENIDO DE NUEVO!")
        title.setObjectName("TitleLabel")
        left_layout.addWidget(title)

        subtitle = QLabel("Accede a tu panel")
        subtitle.setObjectName("SubTitleLabel")
        left_layout.addWidget(subtitle)

        lbl_user = QLabel("Usuario")
        lbl_user.setObjectName("FieldLabel")
        left_layout.addWidget(lbl_user)

        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("Ingresa tu usuario")
        self.input_user.setMinimumHeight(44)
        left_layout.addWidget(self.input_user)

        lbl_pass = QLabel("Contraseña")
        lbl_pass.setObjectName("FieldLabel")
        left_layout.addWidget(lbl_pass)

        self.input_pass = QLineEdit()
        self.input_pass.setPlaceholderText("••••••••")
        self.input_pass.setEchoMode(QLineEdit.Password)
        self.input_pass.setMinimumHeight(44)
        left_layout.addWidget(self.input_pass)

        self.btn_login = QPushButton("Iniciar sesión")
        self.btn_login.setObjectName("LoginButton")
        self.btn_login.setMinimumHeight(46)
        self.btn_login.clicked.connect(self.attempt_login)
        left_layout.addWidget(self.btn_login)
        left_layout.addStretch()

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(14)
        right_layout.addStretch()

        circle = QLabel()
        circle.setObjectName("CircleBorder")
        circle.setFixedSize(320, 320)
        circle.setAlignment(Qt.AlignCenter)

        if os.path.exists(logo_path):
            pix = QPixmap(logo_path)
            if not pix.isNull():
                circle_pix = self._create_round_pixmap(pix, 292)
                circle.setPixmap(circle_pix)
        else:
            circle.setText("KyoGym")
            circle.setStyleSheet("color: #ffffff; font-size: 28px; font-weight: bold;")

        right_layout.addWidget(circle, alignment=Qt.AlignCenter)

        right_layout.addStretch()

        card_layout.addWidget(left_panel, 5)
        card_layout.addWidget(right_panel, 5)
        main_layout.addWidget(login_card)

    def _create_round_pixmap(self, source: QPixmap, diameter: int) -> QPixmap:
        side = min(source.width(), source.height())
        x = (source.width() - side) // 2
        y = (source.height() - side) // 2
        square = source.copy(x, y, side, side)
        square = square.scaled(diameter, diameter, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

        output = QPixmap(diameter, diameter)
        output.fill(Qt.transparent)

        painter = QPainter(output)
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addEllipse(0, 0, diameter, diameter)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, square)
        painter.end()

        return output

    def attempt_login(self):
        username = self.input_user.text().strip()
        password = self.input_pass.text()
        if not username or not password:
            QMessageBox.warning(self, "Error", "Debe ingresar usuario y contraseña.")
            return

        try:
            if verify_user(username, password):
                guardar_usuario_activo(username)
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Usuario o contraseña incorrectos.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al verificar credenciales: {e}")


class PrimeraVezDialog(QDialog):
    """Diálogo que se muestra la primera vez que se inicia KyoGym
    para crear el usuario administrador inicial."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KyoGym - Configuración inicial")
        self.setMinimumSize(480, 440)
        self.setWindowFlag(Qt.Window)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #0a0a0a; }
            QFrame#SetupCard {
                background-color: #111111;
                border: 1px solid #4d4d4d;
                border-radius: 18px;
            }
            QLabel { color: #efefef; font-size: 13px; }
            QLabel#Title { color: #ffffff; font-size: 22px; font-weight: 700; }
            QLabel#Sub   { color: #aaaaaa; font-size: 13px; }
            QLineEdit {
                background-color: transparent;
                color: #ffffff;
                border: 2px solid #8f8f8f;
                border-radius: 16px;
                padding: 10px 14px;
                font-size: 13px;
            }
            QLineEdit:focus { border: 2px solid #ffffff; }
            QPushButton#CreateBtn {
                background-color: #c0c0c0;
                color: #000000;
                border: 2px solid #ffffff;
                border-radius: 17px;
                font-size: 15px;
                font-weight: 700;
                padding: 10px;
            }
            QPushButton#CreateBtn:hover { background-color: #d8d8d8; }
            QMessageBox QLabel { color: #000000; }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 32, 32, 32)

        card = QFrame()
        card.setObjectName("SetupCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(14)

        title = QLabel("Bienvenido a KyoGym")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        sub = QLabel("Es la primera vez que se inicia la aplicación.\nCrea el usuario administrador para continuar.")
        sub.setObjectName("Sub")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        lay.addWidget(sub)

        lay.addSpacing(8)

        lay.addWidget(QLabel("Nombre completo"))
        self.input_nombre = QLineEdit()
        self.input_nombre.setPlaceholderText("Ej. Juan Pérez")
        self.input_nombre.setMinimumHeight(42)
        lay.addWidget(self.input_nombre)

        lay.addWidget(QLabel("Usuario"))
        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("Ej. admin")
        self.input_user.setMinimumHeight(42)
        lay.addWidget(self.input_user)

        lay.addWidget(QLabel("Contraseña"))
        self.input_pass = QLineEdit()
        self.input_pass.setEchoMode(QLineEdit.Password)
        self.input_pass.setPlaceholderText("••••••••")
        self.input_pass.setMinimumHeight(42)
        lay.addWidget(self.input_pass)

        lay.addWidget(QLabel("Confirmar contraseña"))
        self.input_pass2 = QLineEdit()
        self.input_pass2.setEchoMode(QLineEdit.Password)
        self.input_pass2.setPlaceholderText("••••••••")
        self.input_pass2.setMinimumHeight(42)
        lay.addWidget(self.input_pass2)

        lay.addSpacing(6)

        self.btn_crear = QPushButton("Crear administrador")
        self.btn_crear.setObjectName("CreateBtn")
        self.btn_crear.setMinimumHeight(46)
        self.btn_crear.clicked.connect(self._on_crear)
        lay.addWidget(self.btn_crear)

        main_layout.addWidget(card)

    def _on_crear(self):
        from db import create_user
        nombre = self.input_nombre.text().strip()
        username = self.input_user.text().strip()
        password = self.input_pass.text()
        password2 = self.input_pass2.text()

        if not nombre or not username or not password:
            QMessageBox.warning(self, "Campos requeridos", "Todos los campos son obligatorios.")
            return
        if len(username) < 3:
            QMessageBox.warning(self, "Usuario inválido", "El usuario debe tener al menos 3 caracteres.")
            return
        if len(password) < 6:
            QMessageBox.warning(self, "Contraseña débil", "La contraseña debe tener al menos 6 caracteres.")
            return
        if password != password2:
            QMessageBox.warning(self, "Contraseñas no coinciden", "Las contraseñas no coinciden.")
            return

        ok = create_user(username, password, full_name=nombre, role='admin')
        if ok:
            QMessageBox.information(
                self, "Listo",
                f"Usuario <b>{username}</b> creado correctamente.\nYa puedes iniciar sesión."
            )
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "No se pudo crear el usuario. Intenta con otro nombre de usuario.")

