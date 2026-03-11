"""
KyoGym - Sistema de Gestión de Gimnasio
Aplicación de escritorio para Windows
"""
import sys
import os
import ctypes
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QStackedWidget, QLabel, QFrame,
                               QDialog, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QPixmap

# Inicializar base de datos
from db import init_database, ensure_default_user, verify_user, get_user_role, get_user_fullname
from usuario_activo import obtener_usuario_activo, guardar_usuario_activo
from views.login_view import LoginDialog

# Importar vistas
from views.dashboard_view import DashboardView
from views.membresias_view import MembresiasView
from views.clientes_view import ClientesView
from views.pagos_view import PagosView
from views.inventario_view import InventarioView
from views.finanzas_view import FinanzasView
from views.configuracion_view import ConfiguracionView


class SidebarButton(QPushButton):
    """Botón personalizado para el sidebar"""
    def __init__(self, texto, icono=None):
        super().__init__(texto)
        self.setCheckable(True)
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 15px 20px;
                border: none;
                background-color: transparent;
                color: #cccccc;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #1a1a1a;
                color: #ffffff;
                border-left: 4px solid #c0c0c0;
            }
        """)


class MainWindow(QMainWindow):
    """Ventana principal de la aplicación"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KyoGym - Sistema de Gestión")
        self.setMinimumSize(1200, 700)
        self.resize(1400, 800)  # Tamaño inicial más grande
        
        # Establecer icono de la ventana
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
        
        # Inicializar usuario activo y su rol
        self.usuario_activo = obtener_usuario_activo()
        self.rol_usuario = get_user_role(self.usuario_activo)
        self.nombre_completo = get_user_fullname(self.usuario_activo)

        # La base de datos ya debe inicializarse antes de instanciar MainWindow
        self.init_ui()
        self.aplicar_restricciones_rol()
        self.ir_a_inicio()
    
    def init_ui(self):
        """Inicializa la interfaz de usuario"""
        try:
            # Widget central
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            
            # Layout principal (horizontal)
            main_layout = QHBoxLayout(central_widget)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)
            
            # Sidebar (se crea primero para tener los botones disponibles)
            sidebar = self.crear_sidebar()
            main_layout.addWidget(sidebar)
            
            # Contenedor de vistas
            self.stack = QStackedWidget()
            self.stack.setStyleSheet("background-color: #f8f8f8;")
            
            # Agregar vistas
            print("Creando dashboard...")
            self.dashboard_view = DashboardView()
            print("Creando membresías...")
            self.membresias_view = MembresiasView()
            print("Creando clientes...")
            self.clientes_view = ClientesView()
            print("Creando pagos...")
            self.pagos_view = PagosView()
            print("Creando inventario...")
            self.inventario_view = InventarioView()
            print("Creando finanzas...")
            self.finanzas_view = FinanzasView()
            print("Creando configuración...")
            self.configuracion_view = ConfiguracionView()
            self.configuracion_view.logout_solicitado.connect(self.manejar_logout)
            self.stack.addWidget(self.dashboard_view)
            self.stack.addWidget(self.membresias_view)
            self.stack.addWidget(self.clientes_view)
            self.stack.addWidget(self.pagos_view)
            self.stack.addWidget(self.inventario_view)
            self.stack.addWidget(self.finanzas_view)
            self.stack.addWidget(self.configuracion_view)
            
            main_layout.addWidget(self.stack)
            
            # Establecer proporción (sidebar : contenido = 1 : 4)
            main_layout.setStretch(0, 1)
            main_layout.setStretch(1, 4)
            
            # Mostrar dashboard por defecto (ahora btn_inicio ya existe)
            self.btn_inicio.setChecked(True)
            self.stack.setCurrentWidget(self.dashboard_view)
            print("UI inicializada correctamente")
        except Exception as e:
            print(f"Error al inicializar UI: {e}")
            import traceback
            traceback.print_exc()
    
    def crear_sidebar(self):
        """Crea el sidebar de navegación"""
        sidebar = QFrame()
        sidebar.setStyleSheet("background-color: #111111;")
        sidebar.setMaximumWidth(250)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Logo/Título
        header_widget = QWidget()
        header_widget.setStyleSheet("background-color: #0a0a0a;")
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 24, 20, 24)
        header_layout.setSpacing(0)
        
        # Logo
        logo_label = QLabel()
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # Escalar el logo a 90x90 píxeles manteniendo la proporción
            scaled_pixmap = pixmap.scaled(115, 115, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignCenter)
            header_layout.addWidget(logo_label)
        
        layout.addWidget(header_widget)
        
        # Separador
        separador = QFrame()
        separador.setFrameShape(QFrame.HLine)
        separador.setStyleSheet("background-color: #2a2a2a;")
        layout.addWidget(separador)

        # Espaciado entre separador y botones
        spacer_top = QWidget()
        spacer_top.setFixedHeight(8)
        spacer_top.setStyleSheet("background: transparent;")
        layout.addWidget(spacer_top)
        
        # Botones de navegación
        self.btn_inicio = SidebarButton("🏠 Inicio")
        self.btn_membresias = SidebarButton("👥 Membresías")
        self.btn_clientes = SidebarButton("👤 Clientes")
        self.btn_pagos = SidebarButton("💰 Pagos")
        self.btn_inventario = SidebarButton("📦 Inventario")
        self.btn_finanzas = SidebarButton("💰 Finanzas")
        
        self.btn_inicio.clicked.connect(lambda: self.cambiar_vista(0, self.btn_inicio))
        self.btn_membresias.clicked.connect(lambda: self.cambiar_vista(1, self.btn_membresias))
        self.btn_clientes.clicked.connect(lambda: self.cambiar_vista(2, self.btn_clientes))
        self.btn_pagos.clicked.connect(lambda: self.cambiar_vista(3, self.btn_pagos))
        self.btn_inventario.clicked.connect(lambda: self.cambiar_vista(4, self.btn_inventario))
        self.btn_finanzas.clicked.connect(lambda: self.cambiar_vista(5, self.btn_finanzas))
        
        layout.addWidget(self.btn_inicio)
        layout.addWidget(self.btn_membresias)
        layout.addWidget(self.btn_clientes)
        layout.addWidget(self.btn_pagos)
        layout.addWidget(self.btn_inventario)
        layout.addWidget(self.btn_finanzas)
        
        # Espacio flexible
        layout.addStretch()
        
        # Separador antes del perfil
        separador_perfil = QFrame()
        separador_perfil.setFrameShape(QFrame.HLine)
        separador_perfil.setStyleSheet("background-color: #34495e;")
        layout.addWidget(separador_perfil)
        
        # Widget de perfil de usuario
        perfil_widget = self.crear_widget_perfil()
        layout.addWidget(perfil_widget)
        
        # Separador antes de configuración
        separador2 = QFrame()
        separador2.setFrameShape(QFrame.HLine)
        separador2.setStyleSheet("background-color: #2a2a2a;")
        layout.addWidget(separador2)
        
        # Botón de configuración al final
        self.btn_configuracion = SidebarButton("⚙️ Configuración")
        self.btn_configuracion.clicked.connect(lambda: self.cambiar_vista(6, self.btn_configuracion))
        layout.addWidget(self.btn_configuracion)
        
        return sidebar
    
    def crear_widget_perfil(self):
        """Crea el widget de perfil de usuario en el sidebar"""
        perfil_frame = QFrame()
        perfil_frame.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                padding: 10px;
            }
        """)

        perfil_layout = QHBoxLayout(perfil_frame)
        perfil_layout.setContentsMargins(10, 10, 10, 10)
        perfil_layout.setSpacing(10)

        # Icono de perfil
        icono_label = QLabel("👤")
        icono_label.setStyleSheet("font-size: 24px; background-color: transparent;")
        perfil_layout.addWidget(icono_label)

        # Nombre del usuario (nombre completo)
        self.nombre_usuario_label = QLabel(self.nombre_completo)
        self.nombre_usuario_label.setStyleSheet("""
            color: #c0c0c0;
            font-size: 13px;
            font-weight: bold;
            background-color: transparent;
        """)
        self.nombre_usuario_label.setWordWrap(True)
        perfil_layout.addWidget(self.nombre_usuario_label, 1)

        return perfil_frame
    
    def ir_a_inicio(self):
        """Navega a la vista inicial según el rol del usuario."""
        es_privilegiado = self.rol_usuario == 'admin' or self.usuario_activo == 'prueba'
        if es_privilegiado:
            self.cambiar_vista(0, self.btn_inicio)
        else:
            self.cambiar_vista(1, self.btn_membresias)

    def aplicar_restricciones_rol(self):
        """Muestra u oculta secciones según el rol del usuario activo."""
        es_privilegiado = self.rol_usuario == 'admin' or self.usuario_activo == 'prueba'
        self.btn_inicio.setVisible(es_privilegiado)
        self.btn_finanzas.setVisible(es_privilegiado)
        if hasattr(self, 'configuracion_view'):
            self.configuracion_view.set_usuario(self.usuario_activo, self.rol_usuario)

    def manejar_logout(self):
        """Oculta la ventana principal y muestra el login."""
        self.hide()
        login = LoginDialog()
        login.show()
        if login.exec() == QDialog.Accepted:
            nuevo = obtener_usuario_activo()
            self.usuario_activo = nuevo
            self.rol_usuario = get_user_role(nuevo)
            self.nombre_completo = get_user_fullname(nuevo)
            self.nombre_usuario_label.setText(self.nombre_completo)
            self.aplicar_restricciones_rol()
            self.showMaximized()
            self.ir_a_inicio()
        else:
            self.close()

    def cambiar_vista(self, indice, boton):
        """Cambia la vista actual"""
        # Desmarcar todos los botones
        self.btn_inicio.setChecked(False)
        self.btn_membresias.setChecked(False)
        self.btn_clientes.setChecked(False)
        self.btn_pagos.setChecked(False)
        self.btn_inventario.setChecked(False)
        self.btn_finanzas.setChecked(False)
        self.btn_configuracion.setChecked(False)
        
        # Marcar el botón actual
        boton.setChecked(True)
        
        # Cambiar vista
        self.stack.setCurrentIndex(indice)
        
        # Recargar datos al cambiar de módulo
        if indice == 0:
            self.dashboard_view.cargar_datos()
        elif indice == 1:
            self.membresias_view.cargar_datos()
        elif indice == 2:
            self.clientes_view.cargar_datos()
        elif indice == 3:
            self.pagos_view.cargar_datos()
            self.pagos_view.actualizar_total_mes()
        elif indice == 4:
            self.inventario_view.cargar_datos()
        elif indice == 5:
            self.finanzas_view.cargar_datos()


def main():
    """Función principal"""
    # Configurar AppUserModelID para Windows (hace que el icono aparezca en la barra de tareas)
    if sys.platform == 'win32':
        myappid = 'kyogym.gimnasio.app.1.0'  # ID único de tu aplicación
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
    app = QApplication(sys.argv)
    
    # Establecer icono de la aplicación
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
    if os.path.exists(logo_path):
        app.setWindowIcon(QIcon(logo_path))
    
    # Configurar estilo global
    app.setStyle("Fusion")

    # Forzar texto negro en todos los QMessageBox (evita texto blanco en tema oscuro)
    app.setStyleSheet("""
        QMessageBox {
            background-color: #ffffff;
        }
        QMessageBox QLabel {
            color: #000000;
            font-size: 13px;
        }
        QMessageBox QPushButton {
            color: #ffffff;
            background-color: #2c3e50;
            border: none;
            border-radius: 4px;
            padding: 8px 20px;
            font-size: 13px;
            font-weight: bold;
            min-width: 80px;
        }
        QMessageBox QPushButton:hover {
            background-color: #3d5166;
        }
    """)
    
    # Inicializar base de datos y crear usuario por defecto si es necesario
    init_database()
    ensure_default_user()

    # Mostrar diálogo de login en tamaño fijo
    login = LoginDialog()
    login.show()
    if login.exec() != QDialog.Accepted:
        sys.exit(0)

    window = MainWindow()
    window.showMaximized()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
