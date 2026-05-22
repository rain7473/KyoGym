"""
KyoGym - Sistema de Gestión de Gimnasio
Aplicación de escritorio para Windows
"""
import sys
import os
import ctypes
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QStackedWidget, QLabel, QFrame,
                               QDialog, QMessageBox, QGraphicsDropShadowEffect,
                               QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView)
from PySide6.QtCore import Qt, QTimer, QPoint, QObject, QEvent, Signal
from PySide6.QtGui import QFont, QIcon, QPixmap, QColor

# Inicializar base de datos
from db import init_database, ensure_default_user, verify_user, get_user_role, get_user_fullname, has_any_user
from usuario_activo import obtener_usuario_activo, guardar_usuario_activo
from views.login_view import LoginDialog, PrimeraVezDialog

# Importar vistas
from views.dashboard_view import DashboardView
from views.membresias_view import MembresiasView
from views.clientes_view import ClientesView
from views.pagos_view import PagosView
from views.inventario_view import InventarioView
from views.finanzas_view import FinanzasView
from views.configuracion_view import ConfiguracionView
from services import cliente_service


# ─────────────────────── BARCODE EVENT FILTER ────────────────────

class BarcodeEventFilter(QObject):
    """Filtro global que captura input de pistola lectora de códigos de barras.

    Las pistolas lectoras envían caracteres muy rápido (< 50 ms entre teclas)
    y terminan con Enter. Este filtro acumula esos caracteres y, al recibir
    Enter, emite la señal `codigo_detectado` si el buffer tiene al menos 3
    caracteres y llegaron todos en menos de 100 ms/carácter en promedio.
    """
    codigo_detectado = Signal(str)

    # Tiempo máximo (ms) entre pulsaciones para considerar input del escáner
    _MAX_GAP_MS = 80

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buffer = ""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._reset_buffer)

    def _reset_buffer(self):
        self._buffer = ""

    def eventFilter(self, obj, event):
        if event.type() != QEvent.KeyPress:
            return False

        key = event.key()
        text = event.text()

        if key in (Qt.Key_Return, Qt.Key_Enter):
            code = self._buffer.strip()
            self._buffer = ""
            self._timer.stop()
            if len(code) >= 3:
                self.codigo_detectado.emit(code)
            return False  # no consumir Enter

        if text and text.isprintable():
            self._buffer += text
            # Reiniciar timer: si no llega otro carácter pronto, limpiar buffer
            self._timer.start(self._MAX_GAP_MS * 5)

        return False


# ─────────────────────── ASIGNAR CÓDIGO DIALOG ───────────────────

class AsignarCodigoDialog(QDialog):
    """Muestra la lista de clientes sin código de barras asignado
    para que el usuario elija a quién asignarle el código escaneado."""

    def __init__(self, codigo_escaneado: str, parent=None):
        super().__init__(parent)
        self.codigo_escaneado = codigo_escaneado
        self.cliente_seleccionado = None
        self.setWindowTitle("Asignar código de barras")
        self.setMinimumSize(520, 400)
        self._build_ui()
        self._cargar_clientes()

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog { background:#f5f7fa; }
            QLabel  { color:#1a2e45; font-size:13px; }
            QTableWidget { background:#ffffff; border:1px solid #d0d8e4;
                           border-radius:6px; gridline-color:#e8edf2; }
            QHeaderView::section { background:#1a2e45; color:#ffffff;
                                   padding:6px; border:none; font-weight:bold; }
            QPushButton { padding:9px 22px; border-radius:6px; font-size:13px;
                          font-weight:bold; border:none; }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)

        info = QLabel(
            f"Código escaneado: <b style='font-family:monospace'>{self.codigo_escaneado}</b><br>"
            "El código no está asignado a ningún cliente.<br>"
            "Selecciona el cliente al que deseas asignárselo:")
        info.setWordWrap(True)
        info.setStyleSheet(
            "background:#e8f0fa; border-radius:6px; padding:10px 14px;"
            " color:#1a3a5c; font-size:12px;")
        lay.addWidget(info)

        self._tabla = QTableWidget()
        self._tabla.setColumnCount(3)
        self._tabla.setHorizontalHeaderLabels(["ID", "Nombre", "Teléfono"])
        self._tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self._tabla.setColumnWidth(0, 55)
        self._tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self._tabla.setColumnWidth(2, 120)
        self._tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.doubleClicked.connect(self._on_aceptar)
        lay.addWidget(self._tabla)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet(
            "QPushButton { background:#e2e8f0; color:#334155; }"
            "QPushButton:hover { background:#cbd5e1; }")
        btn_cancel.clicked.connect(self.reject)
        btn_asignar = QPushButton("Asignar código")
        btn_asignar.setCursor(Qt.PointingHandCursor)
        btn_asignar.setDefault(True)
        btn_asignar.setStyleSheet(
            "QPushButton { background:#2c6fad; color:#ffffff; }"
            "QPushButton:hover { background:#1e5a91; }")
        btn_asignar.clicked.connect(self._on_aceptar)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_asignar)
        lay.addLayout(btns)

    def _cargar_clientes(self):
        from services import cliente_service
        from db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, nombre, telefono FROM clientes
            WHERE activo=1 AND (codigo_barras IS NULL OR codigo_barras='')
            ORDER BY nombre COLLATE NOCASE
        """)
        rows = cur.fetchall()
        conn.close()
        self._tabla.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self._tabla.setRowHeight(i, 32)
            for j, val in enumerate([str(row[0]), row[1] or "—", row[2] or "—"]):
                item = QTableWidgetItem(val)
                self._tabla.setItem(i, j, item)

    def _on_aceptar(self):
        sel = self._tabla.selectedItems()
        if not sel:
            QMessageBox.warning(self, "Selección requerida",
                                "Por favor selecciona un cliente de la lista.")
            return
        fila = self._tabla.currentRow()
        cliente_id = int(self._tabla.item(fila, 0).text())
        nombre = self._tabla.item(fila, 1).text()
        self.cliente_seleccionado = {"id": cliente_id, "nombre": nombre}
        self.accept()


class BirthdayToast(QFrame):
    """Toast flotante de cumpleaños — widget hijo del central widget (sin ventana layered)."""

    def __init__(self, nombre, parent, offset_y=0):
        # Hijo directo del parent: evita ventanas layered transparentes de Windows
        super().__init__(parent)
        self._offset_y = offset_y
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._build_ui(nombre)
        self._apply_shadow()
        # Auto-cerrar a los 30 segundos
        QTimer.singleShot(30000, self.close)

    def _build_ui(self, nombre):
        self.setFixedWidth(340)
        self.setStyleSheet("""
            BirthdayToast {
                background-color: rgba(254, 252, 232, 210);
                border-radius: 14px;
                border: 1px solid #FDE68A;
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 18)
        outer.setSpacing(6)

        # ── Fila superior: pastel + título + cerrar ──────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        lbl_cake = QLabel("🎂")
        lbl_cake.setStyleSheet("font-size: 26px; background: transparent; border: none;")
        top_row.addWidget(lbl_cake, alignment=Qt.AlignVCenter)

        lbl_title = QLabel("¡Feliz cumpleaños!")
        lbl_title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #78350F;
            background: transparent;
            border: none;
        """)
        top_row.addWidget(lbl_title, 1, Qt.AlignVCenter)

        btn_close = QPushButton("×")
        btn_close.setFixedSize(22, 22)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #92400E;
                font-size: 16px;
                font-weight: bold;
                border: none;
                padding: 0;
            }
            QPushButton:hover { color: #78350F; }
        """)
        btn_close.clicked.connect(self.close)
        top_row.addWidget(btn_close, alignment=Qt.AlignTop)

        outer.addLayout(top_row)

        # ── Fila inferior: texto + confeti ────────────────────────
        bot_row = QHBoxLayout()
        bot_row.setSpacing(10)

        lbl_body = QLabel(f"Hoy es el cumpleaños de <b>{nombre}</b>.")
        lbl_body.setStyleSheet("""
            font-size: 13px;
            color: #4B3510;
            background: transparent;
            border: none;
        """)
        lbl_body.setWordWrap(True)
        bot_row.addWidget(lbl_body, 1, Qt.AlignVCenter)

        lbl_confetti = QLabel("🎉")
        lbl_confetti.setStyleSheet("font-size: 28px; background: transparent; border: none;")
        bot_row.addWidget(lbl_confetti, alignment=Qt.AlignBottom)

        outer.addLayout(bot_row)
        self.adjustSize()

    def _apply_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

    def place(self, parent_widget):
        """Posiciona el toast en la esquina inferior derecha del widget padre."""
        self.adjustSize()
        margin = 24
        pw = parent_widget.width()
        ph = parent_widget.height()
        x = pw - self.width() - margin
        y = ph - self.height() - margin - self._offset_y
        self.move(x, y)
        self.raise_()
        self.show()


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
        self._toasts_activos = []
        QTimer.singleShot(700, self.mostrar_notificacion_cumpleanos)

        # Instalar filtro global de escáner de códigos de barras
        self._barcode_filter = BarcodeEventFilter(self)
        QApplication.instance().installEventFilter(self._barcode_filter)
        self._barcode_filter.codigo_detectado.connect(self._procesar_codigo_barras)
    
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
            # Conectar navegación desde las cards del dashboard
            self.dashboard_view.navegacion_solicitada.connect(self._navegar_desde_dashboard)
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
    
    def mostrar_notificacion_cumpleanos(self):
        """Muestra un toast por cada cliente que cumple años hoy."""
        try:
            cumpleaneros = cliente_service.obtener_cumpleaneros_hoy()
            if not cumpleaneros:
                return
            # El toast es hijo del centralWidget para evitar ventanas layered en Windows
            parent_widget = self.centralWidget()
            toast_h = 120   # altura estimada por toast
            gap    = 12     # separación entre toasts
            for idx, cliente in enumerate(cumpleaneros):
                offset_y = idx * (toast_h + gap)
                toast = BirthdayToast(cliente['nombre'], parent=parent_widget, offset_y=offset_y)
                toast.place(parent_widget)
                self._toasts_activos.append(toast)
                toast.destroyed.connect(
                    lambda _, t=toast: self._toasts_activos.remove(t)
                    if t in self._toasts_activos else None
                )
        except Exception:
            pass

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

    def _navegar_desde_dashboard(self, destino, parametro):
        """Navega desde una card del dashboard a la vista correspondiente con filtro."""
        if destino == "membresias":
            self.cambiar_vista(1, self.btn_membresias)
            self.membresias_view.cambiar_filtro(parametro)
        elif destino == "finanzas":
            self.cambiar_vista(5, self.btn_finanzas)
            if parametro == "ingresos":
                self.finanzas_view.tabs.setCurrentIndex(1)
        elif destino == "inventario":
            self.cambiar_vista(4, self.btn_inventario)
            if parametro == "bajo_stock":
                self.inventario_view.filtro_bajo_stock = True
                self.inventario_view.btn_bajo_stock.setChecked(True)
                self.inventario_view.cargar_datos()

    def _procesar_codigo_barras(self, codigo: str):
        """Procesa un código detectado por el escáner global."""
        from datetime import date as _date
        from services import cliente_service as _cs, asistencia_service as _as
        from services.membresia_service import obtener_membresia_activa
        from utils.constants import ESTADO_ACTIVA, ESTADO_POR_VENCER

        cliente = _cs.buscar_por_codigo_barras(codigo)

        if not cliente:
            # ── Código no asignado: ofrecer asignarlo ─────────────
            dlg_asignar = AsignarCodigoDialog(codigo, self)
            if dlg_asignar.exec() == QDialog.Accepted and dlg_asignar.cliente_seleccionado:
                sel = dlg_asignar.cliente_seleccionado
                ok, err = _cs.actualizar_codigo_barras(sel["id"], codigo)
                if ok:
                    QMessageBox.information(
                        self, "Código asignado",
                        f"Código <b>{codigo}</b> asignado a <b>{sel['nombre']}</b> correctamente.")
                else:
                    QMessageBox.warning(self, "Error al asignar", err)
            return

        cliente_id = cliente["id"]
        nombre = cliente["nombre"]

        # ── Verificar membresía ────────────────────────────────────
        membresia = obtener_membresia_activa(cliente_id)
        tiene_membresia_activa = (
            membresia is not None and
            membresia.get("estado") in (ESTADO_ACTIVA, ESTADO_POR_VENCER)
        )

        abrir_perfil = True
        if tiene_membresia_activa:
            hoy = _date.today()
            if _as.tiene_asistencia(cliente_id, hoy):
                msg = QMessageBox(self)
                msg.setWindowTitle("Asistencia ya registrada")
                msg.setIcon(QMessageBox.Information)
                msg.setText(
                    f"<b>{nombre}</b><br>"
                    f"La asistencia de hoy ya fue registrada.")
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec()
            else:
                ok, _ = _as.registrar_asistencia(cliente_id, fecha=hoy, origen="escaner")
                if ok:
                    msg = QMessageBox(self)
                    msg.setWindowTitle("Asistencia registrada")
                    msg.setIcon(QMessageBox.NoIcon)
                    msg.setText(
                        f"✅  <b>{nombre}</b><br>"
                        f"Asistencia registrada correctamente.")
                    msg.setStyleSheet(
                        "QMessageBox { background:#f0faf5; }"
                        "QLabel { color:#155724; font-size:13px; }")
                    msg.setStandardButtons(QMessageBox.Ok)
                    msg.exec()
        else:
            estado = membresia.get("estado", "Vencida") if membresia else "Sin membresía"
            msg = QMessageBox(self)
            msg.setWindowTitle("Membresía inactiva")
            msg.setIcon(QMessageBox.Warning)
            msg.setText(
                f"<b>{nombre}</b><br>"
                f"Estado de membresía: <b>{estado}</b><br><br>"
                f"No se registra asistencia. ¿Desea abrir el perfil del cliente?")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)
            abrir_perfil = (msg.exec() == QMessageBox.Yes)

        if abrir_perfil:
            try:
                from views.perfil_cliente_view import PerfilClienteDialog
                dlg = PerfilClienteDialog(cliente_id, self)
                dlg.exec()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo abrir el perfil: {e}")


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
    """)
    
    # Inicializar base de datos y crear usuario por defecto si es necesario
    init_database()

    # Primera ejecución: no hay usuarios → pedir crear admin
    if not has_any_user():
        setup = PrimeraVezDialog()
        setup.show()
        if setup.exec() != QDialog.Accepted:
            sys.exit(0)

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
