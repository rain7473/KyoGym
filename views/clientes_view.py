"""Vista de gestión de clientes"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
                               QDialog, QFormLayout, QLineEdit, QDateEdit, QComboBox,
                               QMessageBox, QDialogButtonBox, QFrame, QTabWidget)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor
from datetime import date
from services import cliente_service
from services import finanzas_service
from utils.iconos_ui import crear_boton_icono, crear_widget_centrado
from utils.table_styles import aplicar_estilo_tabla_moderna
from utils.table_utils import limpiar_tabla
from utils.validators import crear_validador_nombre, TelefonoFormateadoLineEdit, crear_validador_email


class NumericTableWidgetItem(QTableWidgetItem):
    """Ítem de tabla que ordena valores numéricos correctamente"""
    def __init__(self, valor_numerico, texto_display):
        super().__init__(texto_display)
        self.setData(Qt.UserRole, valor_numerico)

    def __lt__(self, other):
        my_val = self.data(Qt.UserRole)
        other_val = other.data(Qt.UserRole) if isinstance(other, QTableWidgetItem) else None
        if my_val is not None and other_val is not None:
            return my_val < other_val
        return super().__lt__(other)


class FechaTableWidgetItem(QTableWidgetItem):
    """Ítem de tabla que ordena fechas en formato dd/MM/yyyy correctamente"""
    def __init__(self, texto):
        super().__init__(texto)
        # Guardar ordinal como dato de ordenamiento (UserRole) para soporte fiable en PySide6
        ordinal = self._calcular_ordinal(texto)
        self.setData(Qt.UserRole, ordinal)

    @staticmethod
    def _calcular_ordinal(texto):
        texto = texto.strip()
        if not texto or texto == "-":
            return 0
        try:
            d = date.fromisoformat("-".join(reversed(texto.split("/"))))
            return d.toordinal()
        except (ValueError, IndexError):
            return 0

    def __lt__(self, other):
        my_ord = self.data(Qt.UserRole)
        other_ord = other.data(Qt.UserRole) if isinstance(other, QTableWidgetItem) else None
        if my_ord is not None and other_ord is not None:
            return my_ord < other_ord
        return super().__lt__(other)


class AgregarClienteDialog(QDialog):
    """Diálogo para agregar/editar cliente"""
    def __init__(self, parent=None, cliente=None):
        super().__init__(parent)
        self.cliente = cliente
        self.setWindowTitle("Editar Cliente" if cliente else "Nuevo Cliente")
        self.setMinimumWidth(400)
        self.init_ui()
        
        if cliente:
            self.cargar_datos_cliente()
    
    def init_ui(self):
        layout = QFormLayout()
        
        # Estilos para el diálogo
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #2c2c2c;
                font-size: 13px;
            }
            QLineEdit, QComboBox, QDateEdit {
                padding: 8px;
                border: 2px solid #d0d0d0;
                border-radius: 4px;
                background-color: #f5f5f5;
                color: #1a1a1a;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
                border: 2px solid #c0c0c0;
            }
            QCalendarWidget QAbstractItemView {
                selection-background-color: #808080;
                selection-color: white;
                color: #2c2c2c;
                background-color: #f5f5f5;
            }
            QCalendarWidget QWidget {
                color: #2c2c2c;
                background-color: #f5f5f5;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #f0f0f0;
            }
            QCalendarWidget QToolButton {
                color: #2c2c2c;
                background-color: #f0f0f0;
            }
            QCalendarWidget QMenu {
                color: #2c2c2c;
                background-color: #f5f5f5;
            }
            QCalendarWidget QSpinBox {
                color: #2c2c2c;
                background-color: #f0f0f0;
            }
            QCalendarWidget QAbstractItemView:enabled {
                color: #2c2c2c;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar QToolButton#qt_calendar_prevmonth,
            QCalendarWidget QWidget#qt_calendar_navigationbar QToolButton#qt_calendar_nextmonth {
                qproperty-icon: none;
            }
            QCalendarWidget QAbstractItemView::item:disabled {
                color: #555555;
            }
            QCalendarWidget QTableView::item:selected {
                background-color: #808080;
                color: white;
            }
            QCalendarWidget QWidget {
                alternate-background-color: #f5f5f5;
            }
            QCalendarWidget QAbstractItemView:enabled[isHeaderRow="true"] {
                color: #555555;
                font-weight: bold;
                background-color: #f0f0f0;
            }
            QCalendarWidget QTableView {
                color: #2c2c2c;
            }
            QPushButton {
                background-color: #2c3e50;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3d5166;
            }
        """)
        
        # Nombre
        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText("Ingrese el nombre completo")
        self.nombre.setValidator(crear_validador_nombre())
        layout.addRow("Nombre:", self.nombre)
        
        # Teléfono
        self.telefono = TelefonoFormateadoLineEdit()
        layout.addRow("Teléfono:", self.telefono)
        
        # Sexo
        self.sexo = QComboBox()
        self.sexo.addItems(["Masculino", "Femenino", "Otro"])
        layout.addRow("Sexo:", self.sexo)
        
        # Fecha de nacimiento (opcional)
        self.fecha_nacimiento = QDateEdit()
        self.fecha_nacimiento.setCalendarPopup(True)
        self.fecha_nacimiento.setDisplayFormat("dd/MM/yyyy")
        self.fecha_nacimiento.setMinimumDate(QDate(1900, 1, 1))
        self.fecha_nacimiento.setSpecialValueText("No especificada")
        self.fecha_nacimiento.setDate(QDate(1900, 1, 1))  # vacío por defecto
        layout.addRow("Fecha de Nacimiento:", self.fecha_nacimiento)
        
        # Email
        self.email = QLineEdit()
        self.email.setPlaceholderText("correo@ejemplo.com (opcional)")
        self.email.setValidator(crear_validador_email())
        layout.addRow("Email:", self.email)
        
        # Botones
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.aceptar)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)
        
        self.setLayout(layout)
    
    def cargar_datos_cliente(self):
        """Carga los datos del cliente para editar"""
        self.nombre.setText(self.cliente['nombre'])
        self.telefono.setText(self.cliente['telefono'] or "")
        
        if self.cliente.get('sexo'):
            index = self.sexo.findText(self.cliente['sexo'])
            if index >= 0:
                self.sexo.setCurrentIndex(index)
        
        if self.cliente.get('fecha_nacimiento'):
            fecha = date.fromisoformat(self.cliente['fecha_nacimiento'])
            self.fecha_nacimiento.setDate(QDate(fecha.year, fecha.month, fecha.day))
        else:
            self.fecha_nacimiento.setDate(QDate(1900, 1, 1))
        
        self.email.setText(self.cliente.get('email') or "")
    
    def aceptar(self):
        """Valida y acepta el diálogo"""
        MSG_STYLE = """
            QMessageBox { background-color: #ffffff; }
            QLabel { color: #2c2c2c; font-size: 13px; min-width: 300px; }
            QPushButton {
                background-color: #2c3e50; color: white;
                padding: 8px 20px; border: none; border-radius: 4px;
                font-weight: bold; font-size: 13px; min-width: 80px;
            }
            QPushButton:hover { background-color: #3d5166; }
        """

        if not self.nombre.text().strip():
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText("El nombre es requerido")
            msg.setStyleSheet(MSG_STYLE)
            msg.exec()
            return

        email_texto = self.email.text().strip()
        if email_texto and ("@" not in email_texto or "." not in email_texto):
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText("El email debe contener '@' y '.'")
            msg.setStyleSheet(MSG_STYLE)
            msg.exec()
            return

        fecha_nacimiento = self.fecha_nacimiento.date()
        if fecha_nacimiento != QDate(1900, 1, 1) and fecha_nacimiento > QDate.currentDate():
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText("La fecha de nacimiento no puede ser futura")
            msg.setStyleSheet(MSG_STYLE)
            msg.exec()
            return

        self.accept()
    
    def obtener_datos(self):
        """Retorna los datos ingresados"""
        fecha = self.fecha_nacimiento.date()
        fecha_nac = None if fecha == QDate(1900, 1, 1) else date(fecha.year(), fecha.month(), fecha.day()).isoformat()
        return {
            'nombre': self.nombre.text().strip(),
            'telefono': self.telefono.text().strip(),
            'sexo': self.sexo.currentText(),
            'fecha_nacimiento': fecha_nac,
            'email': self.email.text().strip()
        }


class ClientesView(QWidget):
    """Vista de gestión de clientes"""
    def __init__(self):
        super().__init__()
        self.filtro_genero = None
        self.filtro_edad = None
        self.edad_minima = None
        self.edad_maxima = None
        self.init_ui()
        self.cargar_datos()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Encabezado
        header_layout = QHBoxLayout()
        
        titulo = QLabel("Clientes")
        titulo.setFont(QFont("Arial", 24, QFont.Bold))
        titulo.setStyleSheet("color: #1a1a1a;")
        header_layout.addWidget(titulo)
        
        header_layout.addStretch()
        
        # Búsqueda
        self.buscar_input = QLineEdit()
        self.buscar_input.setPlaceholderText("🔍 Buscar cliente...")
        self.buscar_input.setClearButtonEnabled(True)
        self.buscar_input.setFixedWidth(220)
        self.buscar_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 10px;
                border: none;
                border-radius: 5px;
                font-size: 13px;
                color: #2c2c2c;
                background-color: #f5f5f5;
            }
            QLineEdit:focus {
                border: 1px solid #c0c0c0;
            }
        """)
        self.buscar_input.textChanged.connect(self.cargar_datos)
        header_layout.addWidget(self.buscar_input)
        
        btn_agregar = QPushButton("Agregar Cliente")
        btn_agregar.setStyleSheet("""
            QPushButton {
                background-color: #2c6fad;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #255d91;
                color: white;
            }
        """)
        btn_agregar.clicked.connect(self.agregar_cliente)
        header_layout.addWidget(btn_agregar)
        
        layout.addLayout(header_layout)

        # ── Tabs ─────────────────────────────────────
        self.tabs_clientes = QTabWidget()
        self.tabs_clientes.setStyleSheet("""
            QTabWidget::pane { border: none; border-radius:4px; background:#f8f8f8; }
            QTabBar::tab {
                padding:8px 18px; font-size:13px; font-weight:bold;
                color:#555555; background:#eeeeee;
                border: none; border-bottom:none; border-radius:4px 4px 0 0;
            }
            QTabBar::tab:selected { background:#f8f8f8; color:#1a1a1a; border-bottom:1px solid #f8f8f8; }
            QTabBar::tab:hover { background:#e0e0e0; }
        """)
        self.tabs_clientes.addTab(self._crear_tab_lista(), "📋 Lista")
        self.tabs_clientes.addTab(self._crear_tab_estadisticas(), "📊 Estadísticas")
        self.tabs_clientes.addTab(self._crear_tab_top_clientes(), "🏆 Top Clientes")
        self.tabs_clientes.addTab(self._crear_tab_frecuentes(), "🔁 Frecuentes")
        self.tabs_clientes.addTab(self._crear_tab_inactivos(), "💤 Inactivos")
        self.tabs_clientes.currentChanged.connect(self._on_tab_clientes_changed)
        layout.addWidget(self.tabs_clientes)

        self.setLayout(layout)

    def _crear_tab_lista(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)

        # Filtros
        filtros_layout = QHBoxLayout()

        # Filtros por género
        label_genero = QLabel("Género:")
        label_genero.setStyleSheet("color: #555555; font-weight: bold;")
        filtros_layout.addWidget(label_genero)

        estilo_botones = """
            QPushButton {
                background-color: #eeeeee;
                color: #555555;
                padding: 8px 16px;
                border: 2px solid #d0d0d0;
                border-radius: 5px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #d8d8d8;
                border: 2px solid #555555;
                color: #1a1a1a;
            }
            QPushButton:checked {
                background-color: #d8d8d8;
                color: #555555;
                border: 2px solid #c0c0c0;
            }
        """

        self.btn_todos_genero = QPushButton("Todos")
        self.btn_masculino = QPushButton("Masculino")
        self.btn_femenino = QPushButton("Femenino")
        self.btn_otro = QPushButton("Otro")

        self.btn_todos_genero.setCheckable(True)
        self.btn_masculino.setCheckable(True)
        self.btn_femenino.setCheckable(True)
        self.btn_otro.setCheckable(True)
        self.btn_todos_genero.setChecked(True)

        self.btn_todos_genero.clicked.connect(lambda: self.cambiar_filtro_genero(None, self.btn_todos_genero))
        self.btn_masculino.clicked.connect(lambda: self.cambiar_filtro_genero("Masculino", self.btn_masculino))
        self.btn_femenino.clicked.connect(lambda: self.cambiar_filtro_genero("Femenino", self.btn_femenino))
        self.btn_otro.clicked.connect(lambda: self.cambiar_filtro_genero("Otro", self.btn_otro))

        for btn in [self.btn_todos_genero, self.btn_masculino, self.btn_femenino, self.btn_otro]:
            btn.setStyleSheet(estilo_botones)
            filtros_layout.addWidget(btn)

        separador = QLabel("|")
        separador.setStyleSheet("color: #333333; font-size: 18px; padding: 0 10px;")
        filtros_layout.addWidget(separador)

        label_edad = QLabel("Edad:")
        label_edad.setStyleSheet("color: #555555; font-weight: bold;")
        filtros_layout.addWidget(label_edad)

        self.btn_todas_edades = QPushButton("Todas")
        self.btn_todas_edades.setCheckable(True)
        self.btn_todas_edades.setChecked(True)
        self.btn_todas_edades.clicked.connect(lambda: self.cambiar_filtro_edad(None, self.btn_todas_edades))
        self.btn_todas_edades.setStyleSheet(estilo_botones)
        filtros_layout.addWidget(self.btn_todas_edades)

        label_menor = QLabel("Menor que:")
        label_menor.setStyleSheet("color: #666666;")
        filtros_layout.addWidget(label_menor)

        self.input_menor_que = QLineEdit()
        self.input_menor_que.setPlaceholderText("Edad")
        self.input_menor_que.setMaximumWidth(60)
        self.input_menor_que.setStyleSheet("""
            QLineEdit {
                padding: 8px; border: 2px solid #d0d0d0; border-radius: 5px;
                font-size: 13px; color: #1a1a1a; background-color: #f5f5f5;
            }
        """)
        self.input_menor_que.textChanged.connect(self.aplicar_filtro_menor_que)
        filtros_layout.addWidget(self.input_menor_que)

        label_mayor = QLabel("Mayor que:")
        label_mayor.setStyleSheet("color: #666666;")
        filtros_layout.addWidget(label_mayor)

        self.input_mayor_que = QLineEdit()
        self.input_mayor_que.setPlaceholderText("Edad")
        self.input_mayor_que.setMaximumWidth(60)
        self.input_mayor_que.setStyleSheet("""
            QLineEdit {
                padding: 8px; border: 2px solid #d0d0d0; border-radius: 5px;
                font-size: 13px; color: #1a1a1a; background-color: #f5f5f5;
            }
        """)
        self.input_mayor_que.textChanged.connect(self.aplicar_filtro_mayor_que)
        filtros_layout.addWidget(self.input_mayor_que)

        filtros_layout.addStretch()
        layout.addLayout(filtros_layout)

        # Tabla de clientes
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(["Nombre", "Teléfono", "Edad", "Sexo", "Fecha Nacimiento", "Acciones"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.horizontalHeader().setSectionsClickable(True)
        self.tabla.horizontalHeader().setSortIndicatorShown(True)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setSelectionMode(QTableWidget.NoSelection)
        self.tabla.setSortingEnabled(True)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.verticalHeader().setVisible(False)
        aplicar_estilo_tabla_moderna(self.tabla)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tabla)

        return w

    def _crear_tab_estadisticas(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        btn_refresh = QPushButton("🔄 Actualizar")
        btn_refresh.setStyleSheet("""
            QPushButton { background-color:#3498db; color:white; padding:6px 16px;
                          border:none; border-radius:4px; font-size:12px; font-weight:bold; }
            QPushButton:hover { background-color:#2980b9; }
        """)
        btn_refresh.clicked.connect(self._cargar_tab_estadisticas)
        layout.addWidget(btn_refresh, alignment=Qt.AlignLeft)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        def _card_stat(titulo, color="#2c6fad"):
            frame = QFrame()
            frame.setStyleSheet("QFrame { background:#ffffff; border: none; border-radius:8px; }")
            fl = QVBoxLayout(frame)
            fl.setContentsMargins(16, 14, 16, 14)
            fl.setSpacing(4)
            lbl_t = QLabel(titulo)
            lbl_t.setStyleSheet("color:#666666; font-size:12px;")
            fl.addWidget(lbl_t)
            lbl_v = QLabel("—")
            lbl_v.setStyleSheet(f"color:{color}; font-size:22px; font-weight:bold; background:transparent;")
            fl.addWidget(lbl_v)
            return frame, lbl_v

        f1, self.stat_total = _card_stat("Total clientes", "#2c6fad")
        f2, self.stat_activos = _card_stat("Con membresía activa", "#27ae60")
        f3, self.stat_sin = _card_stat("Sin membresía", "#95a5a6")
        f4, self.stat_promedio = _card_stat("Promedio gasto/cliente", "#8e44ad")

        for f in [f1, f2, f3, f4]:
            cards_layout.addWidget(f)
        layout.addLayout(cards_layout)

        # Tabla detallada de gasto por cliente (ordenable por columnas)
        lbl_det = QLabel("Detalle de gasto por cliente (haz clic en el encabezado para ordenar):")
        lbl_det.setStyleSheet("color:#555; font-size:12px; padding-top:6px;")
        layout.addWidget(lbl_det)

        self.tabla_gasto_clientes = QTableWidget()
        self.tabla_gasto_clientes.setColumnCount(5)
        self.tabla_gasto_clientes.setHorizontalHeaderLabels(
            ["#", "Cliente", "Género", "Total Pagado", "Cant. Pagos"])
        self.tabla_gasto_clientes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_gasto_clientes.horizontalHeader().setSectionsClickable(True)
        self.tabla_gasto_clientes.horizontalHeader().setSortIndicatorShown(True)
        self.tabla_gasto_clientes.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_gasto_clientes.setSelectionMode(QTableWidget.NoSelection)
        self.tabla_gasto_clientes.setAlternatingRowColors(False)
        self.tabla_gasto_clientes.verticalHeader().setVisible(False)
        self.tabla_gasto_clientes.setSortingEnabled(True)
        aplicar_estilo_tabla_moderna(self.tabla_gasto_clientes)
        layout.addWidget(self.tabla_gasto_clientes)

        return w

    def _crear_tab_top_clientes(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # ── Fila de controles ───────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)

        btn_refresh = QPushButton("🔄 Actualizar")
        btn_refresh.setStyleSheet("""
            QPushButton { background-color:#3498db; color:white; padding:6px 16px;
                          border:none; border-radius:4px; font-size:12px; font-weight:bold; }
            QPushButton:hover { background-color:#2980b9; }
        """)
        btn_refresh.clicked.connect(self._cargar_tab_top_clientes)
        ctrl.addWidget(btn_refresh)

        lbl_filtro = QLabel("Período:")
        lbl_filtro.setStyleSheet("color:#555; font-size:12px; font-weight:bold;")
        ctrl.addWidget(lbl_filtro)

        self.combo_top_periodo = QComboBox()
        self.combo_top_periodo.addItems([
            "Todo el tiempo", "Hoy", "Esta semana", "Este mes", "Este año", "Período personalizado"
        ])
        self.combo_top_periodo.setStyleSheet("""
            QComboBox { padding:6px 10px; border: none; border-radius:4px;
                        font-size:12px; color:#1a1a1a; background:#f5f5f5; min-width:150px; }
            QComboBox::drop-down { border:none; }
        """)
        self.combo_top_periodo.currentIndexChanged.connect(self._on_top_periodo_changed)
        ctrl.addWidget(self.combo_top_periodo)

        lbl_desde = QLabel("Desde:")
        lbl_desde.setStyleSheet("color:#555; font-size:12px;")
        self.lbl_top_desde = lbl_desde
        ctrl.addWidget(lbl_desde)

        self.date_top_desde = QDateEdit()
        self.date_top_desde.setCalendarPopup(True)
        self.date_top_desde.setDisplayFormat("dd/MM/yyyy")
        self.date_top_desde.setDate(QDate.currentDate().addMonths(-1))
        self.date_top_desde.setStyleSheet("""
            QDateEdit { padding:6px; border: none; border-radius:4px;
                        font-size:12px; color:#1a1a1a; background:#f5f5f5; }
        """)
        ctrl.addWidget(self.date_top_desde)

        lbl_hasta = QLabel("Hasta:")
        lbl_hasta.setStyleSheet("color:#555; font-size:12px;")
        self.lbl_top_hasta = lbl_hasta
        ctrl.addWidget(lbl_hasta)

        self.date_top_hasta = QDateEdit()
        self.date_top_hasta.setCalendarPopup(True)
        self.date_top_hasta.setDisplayFormat("dd/MM/yyyy")
        self.date_top_hasta.setDate(QDate.currentDate())
        self.date_top_hasta.setStyleSheet("""
            QDateEdit { padding:6px; border: none; border-radius:4px;
                        font-size:12px; color:#1a1a1a; background:#f5f5f5; }
        """)
        ctrl.addWidget(self.date_top_hasta)

        # Ocultar pickers de período personalizado por defecto
        for w2 in [lbl_desde, self.date_top_desde, lbl_hasta, self.date_top_hasta]:
            w2.setVisible(False)

        ctrl.addStretch()
        layout.addLayout(ctrl)

        lbl = QLabel("Clientes que más han pagado (por monto total)")
        lbl.setStyleSheet("color:#555; font-size:12px; padding-bottom:4px;")
        layout.addWidget(lbl)

        self.tabla_top = QTableWidget()
        self.tabla_top.setColumnCount(5)
        self.tabla_top.setHorizontalHeaderLabels(["#", "Cliente", "Género", "Cant. Pagos", "Total Pagado"])
        self.tabla_top.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_top.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_top.setSelectionMode(QTableWidget.NoSelection)
        self.tabla_top.setAlternatingRowColors(False)
        self.tabla_top.verticalHeader().setVisible(False)
        aplicar_estilo_tabla_moderna(self.tabla_top)
        layout.addWidget(self.tabla_top)

        return w

    def _on_top_periodo_changed(self, index):
        """Muestra/oculta los DateEdits según el período seleccionado"""
        es_personalizado = (self.combo_top_periodo.currentText() == "Período personalizado")
        for w2 in [self.lbl_top_desde, self.date_top_desde, self.lbl_top_hasta, self.date_top_hasta]:
            w2.setVisible(es_personalizado)

    def _calcular_rango_top(self):
        """Devuelve (fecha_desde_str, fecha_hasta_str) según el filtro seleccionado"""
        from datetime import date, timedelta
        hoy = date.today()
        texto = self.combo_top_periodo.currentText()
        if texto == "Hoy":
            return hoy.isoformat(), hoy.isoformat()
        elif texto == "Esta semana":
            lunes = hoy - timedelta(days=hoy.weekday())
            return lunes.isoformat(), hoy.isoformat()
        elif texto == "Este mes":
            return hoy.replace(day=1).isoformat(), hoy.isoformat()
        elif texto == "Este año":
            return hoy.replace(month=1, day=1).isoformat(), hoy.isoformat()
        elif texto == "Período personalizado":
            d = self.date_top_desde.date()
            h = self.date_top_hasta.date()
            return date(d.year(), d.month(), d.day()).isoformat(), date(h.year(), h.month(), h.day()).isoformat()
        else:  # Todo el tiempo
            return None, None

    def _crear_tab_frecuentes(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        btn_refresh = QPushButton("🔄 Actualizar")
        btn_refresh.setStyleSheet("""
            QPushButton { background-color:#3498db; color:white; padding:6px 16px;
                          border:none; border-radius:4px; font-size:12px; font-weight:bold; }
            QPushButton:hover { background-color:#2980b9; }
        """)
        btn_refresh.clicked.connect(self._cargar_tab_frecuentes)
        layout.addWidget(btn_refresh, alignment=Qt.AlignLeft)

        lbl = QLabel("Clientes con más pagos registrados (frecuencia de visita)")
        lbl.setStyleSheet("color:#555; font-size:12px; padding-bottom:4px;")
        layout.addWidget(lbl)

        self.tabla_frecuentes = QTableWidget()
        self.tabla_frecuentes.setColumnCount(6)
        self.tabla_frecuentes.setHorizontalHeaderLabels(
            ["#", "Cliente", "Género", "Cant. Pagos", "Total Pagado", "Último Pago"])
        self.tabla_frecuentes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_frecuentes.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_frecuentes.setSelectionMode(QTableWidget.NoSelection)
        self.tabla_frecuentes.setAlternatingRowColors(False)
        self.tabla_frecuentes.verticalHeader().setVisible(False)
        aplicar_estilo_tabla_moderna(self.tabla_frecuentes)
        layout.addWidget(self.tabla_frecuentes)

        return w

    def _crear_tab_inactivos(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)

        btn_refresh = QPushButton("🔄 Actualizar")
        btn_refresh.setStyleSheet("""
            QPushButton { background-color:#3498db; color:white; padding:6px 16px;
                          border:none; border-radius:4px; font-size:12px; font-weight:bold; }
            QPushButton:hover { background-color:#2980b9; }
        """)
        btn_refresh.clicked.connect(self._cargar_tab_inactivos)
        ctrl.addWidget(btn_refresh)

        lbl_dias = QLabel("Sin pago hace más de:")
        lbl_dias.setStyleSheet("color:#555; font-size:12px;")
        ctrl.addWidget(lbl_dias)

        self.input_dias_inactivo = QLineEdit("60")
        self.input_dias_inactivo.setMaximumWidth(55)
        self.input_dias_inactivo.setStyleSheet("""
            QLineEdit { padding:6px; border: none; border-radius:4px;
                        font-size:12px; color:#1a1a1a; background:#f5f5f5; }
        """)
        ctrl.addWidget(self.input_dias_inactivo)

        lbl_dias2 = QLabel("días")
        lbl_dias2.setStyleSheet("color:#555; font-size:12px;")
        ctrl.addWidget(lbl_dias2)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        lbl = QLabel("Clientes que no han realizado ningún pago en el período indicado.")
        lbl.setStyleSheet("color:#555; font-size:12px; padding-bottom:4px;")
        layout.addWidget(lbl)

        self.tabla_inactivos = QTableWidget()
        self.tabla_inactivos.setColumnCount(4)
        self.tabla_inactivos.setHorizontalHeaderLabels(
            ["Cliente", "Género", "Último Pago", "Estado"])
        self.tabla_inactivos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_inactivos.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_inactivos.setSelectionMode(QTableWidget.NoSelection)
        self.tabla_inactivos.setAlternatingRowColors(False)
        self.tabla_inactivos.verticalHeader().setVisible(False)
        aplicar_estilo_tabla_moderna(self.tabla_inactivos)
        layout.addWidget(self.tabla_inactivos)

        return w

    def _on_tab_clientes_changed(self, index):
        if index == 1:
            self._cargar_tab_estadisticas()
        elif index == 2:
            self._cargar_tab_top_clientes()
        elif index == 3:
            self._cargar_tab_frecuentes()
        elif index == 4:
            self._cargar_tab_inactivos()

    def _cargar_tab_estadisticas(self):
        try:
            stats = finanzas_service.obtener_estadisticas_clientes()
            self.stat_total.setText(str(stats["total_clientes"]))
            self.stat_activos.setText(str(stats["con_membresia_activa"]))
            self.stat_sin.setText(str(stats["sin_membresia"]))
            self.stat_promedio.setText(f"${stats['promedio_gasto_cliente']:,.2f}")

            # Tabla detallada
            clientes_gasto = finanzas_service.obtener_gasto_por_cliente()
            self.tabla_gasto_clientes.setSortingEnabled(False)
            limpiar_tabla(self.tabla_gasto_clientes)
            self.tabla_gasto_clientes.setRowCount(len(clientes_gasto))
            for i, c in enumerate(clientes_gasto):
                self.tabla_gasto_clientes.setRowHeight(i, 40)
                item_num = NumericTableWidgetItem(i + 1, str(i + 1))
                item_num.setForeground(QColor("#888888"))
                self.tabla_gasto_clientes.setItem(i, 0, item_num)

                item_nombre = QTableWidgetItem(c["nombre"])
                item_nombre.setForeground(QColor("#1a1a1a"))
                self.tabla_gasto_clientes.setItem(i, 1, item_nombre)

                item_sexo = QTableWidgetItem(c["sexo"] or "-")
                item_sexo.setForeground(QColor("#555555"))
                self.tabla_gasto_clientes.setItem(i, 2, item_sexo)

                item_total = NumericTableWidgetItem(c["total_pagado"], f"${c['total_pagado']:,.2f}")
                item_total.setForeground(QColor("#27ae60" if c["total_pagado"] > 0 else "#aaaaaa"))
                self.tabla_gasto_clientes.setItem(i, 3, item_total)

                item_pagos = NumericTableWidgetItem(c["cantidad_pagos"], str(c["cantidad_pagos"]))
                item_pagos.setForeground(QColor("#2c6fad" if c["cantidad_pagos"] > 0 else "#aaaaaa"))
                self.tabla_gasto_clientes.setItem(i, 4, item_pagos)

            self.tabla_gasto_clientes.setSortingEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _cargar_tab_top_clientes(self):
        try:
            fecha_desde, fecha_hasta = self._calcular_rango_top()
            top = finanzas_service.obtener_top_clientes_por_monto(
                limite=50, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
            limpiar_tabla(self.tabla_top)
            self.tabla_top.setRowCount(len(top))
            for i, c in enumerate(top):
                self.tabla_top.setRowHeight(i, 44)
                self.tabla_top.setItem(i, 0, QTableWidgetItem(str(i + 1)))
                self.tabla_top.setItem(i, 1, QTableWidgetItem(c["nombre"]))
                self.tabla_top.setItem(i, 2, QTableWidgetItem(c["sexo"] or "-"))
                self.tabla_top.setItem(i, 3, QTableWidgetItem(str(c["cantidad_pagos"])))
                item_total = QTableWidgetItem(f"${c['total_pagado']:,.2f}")
                item_total.setForeground(QColor("#27ae60"))
                self.tabla_top.setItem(i, 4, item_total)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _cargar_tab_frecuentes(self):
        try:
            frec = finanzas_service.obtener_clientes_frecuentes(limite=20)
            limpiar_tabla(self.tabla_frecuentes)
            self.tabla_frecuentes.setRowCount(len(frec))
            for i, c in enumerate(frec):
                self.tabla_frecuentes.setRowHeight(i, 44)
                vals = [str(i + 1), c["nombre"], c["sexo"] or "-",
                        str(c["cantidad_pagos"]), f"${c['total_pagado']:,.2f}",
                        c["ultimo_pago"] or "—"]
                for col, val in enumerate(vals):
                    item = QTableWidgetItem(val)
                    item.setForeground(QColor("#2c6fad" if col == 3 else
                                             "#27ae60" if col == 4 else "#1a1a1a"))
                    self.tabla_frecuentes.setItem(i, col, item)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _cargar_tab_inactivos(self):
        try:
            dias_txt = self.input_dias_inactivo.text().strip()
            dias = int(dias_txt) if dias_txt.isdigit() else 60
            inactivos = finanzas_service.obtener_clientes_inactivos(dias=dias)
            limpiar_tabla(self.tabla_inactivos)
            self.tabla_inactivos.setRowCount(len(inactivos))
            for i, c in enumerate(inactivos):
                self.tabla_inactivos.setRowHeight(i, 44)
                ultimo = c["ultimo_pago"] or "Nunca"
                estado = "Sin pagos" if not c["ultimo_pago"] else f"Inactivo +{dias}d"
                vals = [c["nombre"], c["sexo"] or "-", ultimo, estado]
                for col, val in enumerate(vals):
                    item = QTableWidgetItem(val)
                    item.setForeground(QColor("#e74c3c" if col == 3 else "#1a1a1a"))
                    self.tabla_inactivos.setItem(i, col, item)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
    
    def cargar_datos(self):
        """Carga los clientes en la tabla"""
        buscar = self.buscar_input.text() if hasattr(self, 'buscar_input') else ""
        clientes = cliente_service.listar_clientes(buscar=buscar)

        sorting_enabled = self.tabla.isSortingEnabled()
        self.tabla.setSortingEnabled(False)

        limpiar_tabla(self.tabla)
        
        self.tabla.setRowCount(len(clientes))
        
        for i, cliente in enumerate(clientes):
            self.tabla.setRowHeight(i, 52)
            # Nombre
            self.tabla.setItem(i, 0, QTableWidgetItem(cliente['nombre']))
            
            # Teléfono
            self.tabla.setItem(i, 1, QTableWidgetItem(cliente['telefono'] or "-"))
            
            # Edad
            fecha_nac = cliente.get('fecha_nacimiento', '')
            if fecha_nac:
                fecha = date.fromisoformat(fecha_nac)
                hoy = date.today()
                edad = hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))
                self.tabla.setItem(i, 2, QTableWidgetItem(str(edad)))
            else:
                self.tabla.setItem(i, 2, QTableWidgetItem("-"))
            
            # Sexo
            self.tabla.setItem(i, 3, QTableWidgetItem(cliente.get('sexo', "-")))
            
            # Fecha de nacimiento
            if fecha_nac:
                fecha_texto = fecha.strftime("%d/%m/%Y")
            else:
                fecha_texto = "-"
            self.tabla.setItem(i, 4, FechaTableWidgetItem(fecha_texto))

            # Botones de acciones
            acciones_widget = QWidget()
            acciones_widget.setStyleSheet("background: transparent; border: none;")
            acciones_layout = QHBoxLayout(acciones_widget)
            acciones_layout.setContentsMargins(4, 4, 4, 4)
            acciones_layout.setSpacing(6)
            acciones_layout.setAlignment(Qt.AlignCenter)

            btn_editar = crear_boton_icono("edit.svg", "#7a8899", "#8a9aa9", "Editar")
            btn_editar.clicked.connect(lambda checked, c=cliente: self.editar_cliente(c))
            acciones_layout.addWidget(btn_editar)

            btn_perfil = crear_boton_icono("see.svg", "#2c6fad", "#255d91", "Ver Perfil")
            btn_perfil.clicked.connect(lambda checked, cid=cliente['id']: self.ver_perfil_cliente(cid))
            acciones_layout.addWidget(btn_perfil)

            btn_eliminar = crear_boton_icono("delete.svg", "#e74c3c", "#c0392b", "Eliminar")
            btn_eliminar.clicked.connect(lambda checked, cid=cliente['id']: self.eliminar_cliente(cid))
            acciones_layout.addWidget(btn_eliminar)

            self.tabla.setCellWidget(i, 5, acciones_widget)

        self.tabla.setSortingEnabled(sorting_enabled)

    def ver_perfil_cliente(self, cliente_id):
        """Abre el diálogo de perfil del cliente."""
        from views.perfil_cliente_view import PerfilClienteDialog
        dlg = PerfilClienteDialog(cliente_id, parent=self)
        dlg.exec()
        self.cargar_datos()

    def agregar_cliente(self):
        """Muestra diálogo para agregar cliente"""
        dialog = AgregarClienteDialog(self)
        if dialog.exec() == QDialog.Accepted:
            datos = dialog.obtener_datos()
            try:
                # Verificar si el teléfono ya está registrado
                if datos['telefono']:
                    cliente_existente = cliente_service.verificar_telefono_existente(datos['telefono'])
                    if cliente_existente:
                        msg = QMessageBox(self)
                        msg.setWindowTitle("Teléfono en uso")
                        msg.setText(f"El número {datos['telefono']} ya está vinculado al cliente: {cliente_existente['nombre']}")
                        msg.setStyleSheet("""
                            QMessageBox {
                                background-color: #f5f5f5;
                            }
                            QLabel {
                                color: #2c2c2c;
                                font-size: 13px;
                                min-width: 300px;
                            }
                            QPushButton {
                                background-color: #e74c3c;
                                color: white;
                                padding: 8px 20px;
                                border: none;
                                border-radius: 4px;
                                font-weight: bold;
                                font-size: 13px;
                                min-width: 80px;
                            }
                            QPushButton:hover {
                                background-color: #c0392b;
                            }
                        """)
                        msg.exec()
                        return
                
                cliente_service.crear_cliente(
                    nombre=datos['nombre'],
                    telefono=datos['telefono'],
                    sexo=datos['sexo'],
                    fecha_nacimiento=datos['fecha_nacimiento'],
                    email=datos.get('email', '')
                )
                # Mensaje con estilo
                msg = QMessageBox(self)
                msg.setWindowTitle("Éxito")
                msg.setText("Cliente agregado exitosamente")
                msg.setStyleSheet("""
                    QMessageBox {
                        background-color: #f5f5f5;
                    }
                    QLabel {
                        color: #2c2c2c;
                        font-size: 13px;
                        min-width: 300px;
                    }
                    QPushButton {
                        background-color: #27ae60;
                        color: white;
                        padding: 8px 20px;
                        border: none;
                        border-radius: 4px;
                        font-weight: bold;
                        font-size: 13px;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #229954;
                    }
                """)
                msg.exec()
                self.cargar_datos()
            except Exception as e:
                msg = QMessageBox(self)
                msg.setWindowTitle("Error")
                msg.setText(f"Error al agregar cliente: {str(e)}")
                msg.setStyleSheet("""
                    QMessageBox {
                        background-color: #f5f5f5;
                    }
                    QLabel {
                        color: #2c2c2c;
                        font-size: 13px;
                        min-width: 300px;
                    }
                    QPushButton {
                        background-color: #e74c3c;
                        color: white;
                        padding: 8px 20px;
                        border: none;
                        border-radius: 4px;
                        font-weight: bold;
                        font-size: 13px;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #c0392b;
                    }
                """)
                msg.exec()
    
    def editar_cliente(self, cliente):
        """Muestra diálogo para editar cliente"""
        dialog = AgregarClienteDialog(self, cliente)
        if dialog.exec() == QDialog.Accepted:
            datos = dialog.obtener_datos()
            try:
                # Verificar si el teléfono ya está registrado para otro cliente
                if datos['telefono']:
                    cliente_existente = cliente_service.verificar_telefono_existente(datos['telefono'], excluir_id=cliente['id'])
                    if cliente_existente:
                        msg = QMessageBox(self)
                        msg.setWindowTitle("Teléfono en uso")
                        msg.setText(f"El número {datos['telefono']} ya está vinculado al cliente: {cliente_existente['nombre']}")
                        msg.setStyleSheet("""
                            QMessageBox {
                                background-color: #f5f5f5;
                            }
                            QLabel {
                                color: #2c2c2c;
                                font-size: 13px;
                                min-width: 300px;
                            }
                            QPushButton {
                                background-color: #e74c3c;
                                color: white;
                                padding: 8px 20px;
                                border: none;
                                border-radius: 4px;
                                font-weight: bold;
                                font-size: 13px;
                                min-width: 80px;
                            }
                            QPushButton:hover {
                                background-color: #c0392b;
                            }
                        """)
                        msg.exec()
                        return
                
                cliente_service.actualizar_cliente(
                    cliente_id=cliente['id'],
                    nombre=datos['nombre'],
                    telefono=datos['telefono'],
                    sexo=datos['sexo'],
                    fecha_nacimiento=datos['fecha_nacimiento'],
                    email=datos.get('email', '')
                )
                # Mensaje con estilo
                msg = QMessageBox(self)
                msg.setWindowTitle("Éxito")
                msg.setText("Cliente actualizado exitosamente")
                msg.setStyleSheet("""
                    QMessageBox {
                        background-color: #f5f5f5;
                    }
                    QLabel {
                        color: #2c2c2c;
                        font-size: 13px;
                        min-width: 300px;
                    }
                    QPushButton {
                        background-color: #27ae60;
                        color: white;
                        padding: 8px 20px;
                        border: none;
                        border-radius: 4px;
                        font-weight: bold;
                        font-size: 13px;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #229954;
                    }
                """)
                msg.exec()
                self.cargar_datos()
            except Exception as e:
                msg = QMessageBox(self)
                msg.setWindowTitle("Error")
                msg.setText(f"Error al actualizar cliente: {str(e)}")
                msg.setStyleSheet("""
                    QMessageBox {
                        background-color: #f5f5f5;
                    }
                    QLabel {
                        color: #2c2c2c;
                        font-size: 13px;
                        min-width: 300px;
                    }
                    QPushButton {
                        background-color: #e74c3c;
                        color: white;
                        padding: 8px 20px;
                        border: none;
                        border-radius: 4px;
                        font-weight: bold;
                        font-size: 13px;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #c0392b;
                    }
                """)
                msg.exec()
    
    def eliminar_cliente(self, cliente_id):
        """Elimina un cliente"""
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirmar eliminación")
        msg.setText("¿Está seguro de eliminar este cliente?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #ffffff;
            }
            QLabel {
                color: #2c2c2c;
                font-size: 13px;
                min-width: 300px;
            }
            QPushButton {
                background-color: #2c3e50;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3d5166;
            }
        """)
        respuesta = msg.exec()
        
        if respuesta == QMessageBox.Yes:
            try:
                cliente_service.eliminar_cliente(cliente_id)
                # Mensaje con estilo
                msg = QMessageBox(self)
                msg.setWindowTitle("Éxito")
                msg.setText("Cliente eliminado exitosamente")
                msg.setStyleSheet("""
                    QMessageBox {
                        background-color: #f5f5f5;
                    }
                    QLabel {
                        color: #2c2c2c;
                        font-size: 13px;
                        min-width: 300px;
                    }
                    QPushButton {
                        background-color: #27ae60;
                        color: white;
                        padding: 8px 20px;
                        border: none;
                        border-radius: 4px;
                        font-weight: bold;
                        font-size: 13px;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #229954;
                    }
                """)
                msg.exec()
                self.cargar_datos()
            except Exception as e:
                msg = QMessageBox(self)
                msg.setWindowTitle("Error")
                msg.setText(f"Error al eliminar cliente: {str(e)}")
                msg.setStyleSheet("""
                    QMessageBox {
                        background-color: #f5f5f5;
                    }
                    QLabel {
                        color: #2c2c2c;
                        font-size: 13px;
                        min-width: 300px;
                    }
                    QPushButton {
                        background-color: #e74c3c;
                        color: white;
                        padding: 8px 20px;
                        border: none;
                        border-radius: 4px;
                        font-weight: bold;
                        font-size: 13px;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #c0392b;
                    }
                """)
                msg.exec()
    
    def cambiar_filtro_genero(self, genero, boton_activo):
        """Cambia el filtro de género"""
        # Desmarcar todos los botones de género
        for btn in [self.btn_todos_genero, self.btn_masculino, self.btn_femenino, self.btn_otro]:
            btn.setChecked(False)
        
        # Marcar el botón activo
        boton_activo.setChecked(True)
        
        # Actualizar filtro
        self.filtro_genero = genero
        self.aplicar_filtros()
    
    def cambiar_filtro_edad(self, rango_edad, boton_activo):
        """Cambia el filtro de edad"""
        # Desmarcar el botón "Todas"
        self.btn_todas_edades.setChecked(False)
        
        # Marcar el botón activo
        boton_activo.setChecked(True)
        
        # Limpiar los campos de entrada personalizados
        self.input_menor_que.clear()
        self.input_mayor_que.clear()
        self.edad_minima = None
        self.edad_maxima = None
        
        # Actualizar filtro
        self.filtro_edad = rango_edad
        self.aplicar_filtros()
    
    def aplicar_filtro_menor_que(self):
        """Aplica el filtro de edad menor que el valor ingresado"""
        # Desmarcar el botón "Todas"
        self.btn_todas_edades.setChecked(False)
        
        texto = self.input_menor_que.text().strip()
        
        if texto and texto.isdigit():
            self.edad_maxima = int(texto)
        else:
            self.edad_maxima = None
        
        # Si ambos campos están vacíos, marcar "Todas"
        if not self.input_menor_que.text().strip() and not self.input_mayor_que.text().strip():
            self.btn_todas_edades.setChecked(True)
        
        self.filtro_edad = "personalizado"
        self.aplicar_filtros()
    
    def aplicar_filtro_mayor_que(self):
        """Aplica el filtro de edad mayor que el valor ingresado"""
        # Desmarcar el botón "Todas"
        self.btn_todas_edades.setChecked(False)
        
        texto = self.input_mayor_que.text().strip()
        
        if texto and texto.isdigit():
            self.edad_minima = int(texto)
        else:
            self.edad_minima = None
        
        # Si ambos campos están vacíos, marcar "Todas"
        if not self.input_menor_que.text().strip() and not self.input_mayor_que.text().strip():
            self.btn_todas_edades.setChecked(True)
        
        self.filtro_edad = "personalizado"
        self.aplicar_filtros()
    
    def aplicar_filtros(self):
        """Aplica los filtros de género y edad a la tabla"""
        buscar = self.buscar_input.text() if hasattr(self, 'buscar_input') else ""
        clientes = cliente_service.listar_clientes(buscar=buscar)
        
        # Filtrar por género
        if self.filtro_genero:
            clientes = [c for c in clientes if c.get('sexo') == self.filtro_genero]
        
        # Filtrar por edad
        if self.filtro_edad == "personalizado" and (self.edad_minima is not None or self.edad_maxima is not None):
            hoy = date.today()
            clientes_filtrados = []
            
            for cliente in clientes:
                if cliente.get('fecha_nacimiento'):
                    fecha_nac = date.fromisoformat(cliente['fecha_nacimiento'])
                    edad = (hoy - fecha_nac).days // 365
                    
                    # Aplicar ambos filtros si están definidos
                    cumple_minimo = True if self.edad_minima is None else edad > self.edad_minima
                    cumple_maximo = True if self.edad_maxima is None else edad < self.edad_maxima
                    
                    if cumple_minimo and cumple_maximo:
                        clientes_filtrados.append(cliente)
            
            clientes = clientes_filtrados
        
        # Actualizar tabla con clientes filtrados
        limpiar_tabla(self.tabla)
        self.tabla.setRowCount(len(clientes))
        
        for i, cliente in enumerate(clientes):
            self.tabla.setRowHeight(i, 52)
            # Nombre
            self.tabla.setItem(i, 0, QTableWidgetItem(cliente['nombre']))
            
            # Teléfono
            self.tabla.setItem(i, 1, QTableWidgetItem(cliente['telefono'] or "-"))
            
            # Edad
            fecha_nac = cliente.get('fecha_nacimiento', '')
            if fecha_nac:
                fecha = date.fromisoformat(fecha_nac)
                hoy = date.today()
                edad = hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))
                self.tabla.setItem(i, 2, QTableWidgetItem(str(edad)))
            else:
                self.tabla.setItem(i, 2, QTableWidgetItem("-"))
            
            # Sexo
            self.tabla.setItem(i, 3, QTableWidgetItem(cliente.get('sexo', "-")))
            
            # Fecha de nacimiento
            if fecha_nac:
                fecha_texto = fecha.strftime("%d/%m/%Y")
            else:
                fecha_texto = "-"
            self.tabla.setItem(i, 4, QTableWidgetItem(fecha_texto))

            # Botones de acciones
            acciones_widget = QWidget()
            acciones_widget.setStyleSheet("background: transparent; border: none;")
            acciones_layout = QHBoxLayout(acciones_widget)
            acciones_layout.setContentsMargins(4, 0, 4, 0)
            acciones_layout.setSpacing(6)

            btn_editar = crear_boton_icono("edit.svg", "#7a8899", "#8a9aa9", "Editar")
            btn_editar.clicked.connect(lambda checked, c=cliente: self.editar_cliente(c))
            acciones_layout.addWidget(btn_editar)

            btn_eliminar = crear_boton_icono("delete.svg", "#e74c3c", "#c0392b", "Eliminar")
            btn_eliminar.clicked.connect(lambda checked, cid=cliente['id']: self.eliminar_cliente(cid))
            acciones_layout.addWidget(btn_eliminar)

            self.tabla.setCellWidget(i, 5, acciones_widget)
