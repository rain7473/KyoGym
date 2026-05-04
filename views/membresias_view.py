"""Vista de gestión de membresías"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
                               QDialog, QFormLayout, QLineEdit, QDateEdit, QComboBox,
                               QMessageBox, QDialogButtonBox, QCompleter, QApplication)
from PySide6.QtCore import Qt, QDate, QObject, QEvent
from PySide6.QtGui import QFont, QColor
from datetime import date
from pathlib import Path
from services import membresia_service, cliente_service
from utils.constants import ESTADO_ACTIVA, ESTADO_POR_VENCER, ESTADO_VENCIDA
from utils.factura_generator import generar_factura_membresia, abrir_factura
from utils.iconos_ui import crear_boton_icono, crear_widget_centrado
from utils.table_styles import aplicar_estilo_tabla_moderna
from utils.table_utils import limpiar_tabla
from utils.validators import crear_validador_numerico_decimal


class AgregarMembresiaDialog(QDialog):
    """Diálogo para agregar o editar membresía"""
    def __init__(self, parent=None, membresia=None):
        super().__init__(parent)
        self.membresia = membresia
        self.setWindowTitle("Editar Membresía" if membresia else "Nueva Membresía")
        self.setMinimumWidth(400)
        self.init_ui()
        
        if membresia:
            self.cargar_datos_membresia()
    
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
            QComboBox QAbstractItemView {
                color: #2c2c2c;
                background-color: #f5f5f5;
                selection-background-color: #808080;
                selection-color: white;
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
        
        # Selector de cliente con búsqueda en tiempo real
        self.combo_cliente = QComboBox()
        self.combo_cliente.setEditable(True)
        self.combo_cliente.setInsertPolicy(QComboBox.NoInsert)
        self.combo_cliente.lineEdit().setPlaceholderText("Escribe para buscar...")
        self.combo_cliente.lineEdit().setClearButtonEnabled(True)
        self.cargar_clientes()

        # Fila de cliente con botón agregar y check de estado
        _cliente_row = QWidget()
        _cliente_hbox = QHBoxLayout(_cliente_row)
        _cliente_hbox.setContentsMargins(0, 0, 0, 0)
        _cliente_hbox.setSpacing(4)
        _cliente_hbox.addWidget(self.combo_cliente, 1)

        self.btn_agregar_cliente = QPushButton("+")
        self.btn_agregar_cliente.setFixedSize(32, 32)
        self.btn_agregar_cliente.setToolTip("Agregar nuevo cliente")
        self.btn_agregar_cliente.setVisible(False)
        self.btn_agregar_cliente.setCursor(Qt.PointingHandCursor)
        self.btn_agregar_cliente.setStyleSheet("""
            QPushButton {
                background-color: #2c6fad;
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
                min-width: 0px;
            }
            QPushButton:hover { background-color: #255d91; }
        """)
        self.btn_agregar_cliente.clicked.connect(self._agregar_cliente_rapido)
        _cliente_hbox.addWidget(self.btn_agregar_cliente)

        self.lbl_cliente_ok = QLabel("✔")
        self.lbl_cliente_ok.setFixedSize(32, 32)
        self.lbl_cliente_ok.setAlignment(Qt.AlignCenter)
        self.lbl_cliente_ok.setStyleSheet("color: #27ae60; font-size: 18px; font-weight: bold;")
        self.lbl_cliente_ok.setVisible(False)
        _cliente_hbox.addWidget(self.lbl_cliente_ok)

        layout.addRow("Cliente:", _cliente_row)
        self.combo_cliente.lineEdit().textChanged.connect(self._verificar_cliente_estado)
        
        # Fecha de inicio
        _cal_ss = """
            QCalendarWidget QAbstractItemView {
                selection-background-color: #5e88b4;
                selection-color: white;
                color: #2c2c2c;
                background-color: #eaf0f9;
            }
            QCalendarWidget QWidget {
                color: #2c2c2c;
                background-color: #eaf0f9;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #dce7f3;
            }
            QCalendarWidget QToolButton {
                color: #2c2c2c;
                background-color: #dce7f3;
            }
            QCalendarWidget QMenu {
                color: #2c2c2c;
                background-color: #f5f5f5;
            }
            QCalendarWidget QSpinBox {
                color: #2c2c2c;
                background-color: #f0f0f0;
            }
            QCalendarWidget QTableView {
                color: #2c2c2c;
            }
        """
        self.fecha_inicio = QDateEdit()
        self.fecha_inicio.setDate(QDate.currentDate())
        self.fecha_inicio.setCalendarPopup(True)
        self.fecha_inicio.setDisplayFormat("dd/MM/yyyy")
        self.fecha_inicio.calendarWidget().setStyleSheet(_cal_ss)
        layout.addRow("Fecha Inicio:", self.fecha_inicio)
        
        # Tipo de membresía
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItem("Mensualidad", 25.00)
        self.combo_tipo.addItem("Mensualidad + Entrenador", 50.00)
        self.combo_tipo.addItem("Quincenal", 15.00)
        layout.addRow("Tipo:", self.combo_tipo)

        # Método de pago (solo aplica al crear, ya que la edición no modifica el pago asociado)
        self.combo_metodo_pago = QComboBox()
        self.combo_metodo_pago.addItems(["Efectivo", "Tarjeta", "Transferencia", "Otro"])
        if self.membresia:
            self.combo_metodo_pago.setEnabled(False)
        layout.addRow("Método de pago:", self.combo_metodo_pago)
        
        # Monto
        self.monto = QLineEdit()
        self.monto.setPlaceholderText("0.00")
        self.monto.setValidator(crear_validador_numerico_decimal())
        layout.addRow("Monto:", self.monto)
        
        # Rellenar monto según tipo seleccionado
        self._actualizar_monto_por_tipo(0)
        self.combo_tipo.currentIndexChanged.connect(self._actualizar_monto_por_tipo)
        
        # Botones
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.aceptar)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)
        
        self.setLayout(layout)
    
    def _actualizar_monto_por_tipo(self, index):
        """Rellena el monto según el tipo de membresía seleccionado"""
        precio = self.combo_tipo.itemData(index)
        if precio is not None:
            self.monto.setText(f"{precio:.2f}")
    
    def cargar_clientes(self):
        """Carga la lista de clientes con búsqueda en tiempo real"""
        clientes = cliente_service.listar_clientes()
        self.combo_cliente.clear()
        self.combo_cliente.addItem("", None)

        nombres = []
        for cliente in clientes:
            self.combo_cliente.addItem(cliente['nombre'], cliente['id'])
            nombres.append(cliente['nombre'])

        # Popup que filtra por contenido (MatchContains)
        completer = QCompleter(nombres)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.combo_cliente.setCompleter(completer)

        combo = self.combo_cliente
        line_edit = combo.lineEdit()

        # Sincronizar selección al elegir desde el popup (clic o Enter)
        def _on_activated(text):
            idx = combo.findText(text)
            if idx >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(idx)
                combo.blockSignals(False)
            line_edit.deselect()
            line_edit.setCursorPosition(len(line_edit.text()))

        completer.activated.connect(_on_activated)

        # Tab: acepta el primer item del popup (o el resaltado con ↑↓)
        # Se instala a nivel de app para que Qt no intercepte Tab antes.
        class _TabFilter(QObject):
            def eventFilter(self_, obj, event):
                if (
                    event.type() == QEvent.Type.KeyPress
                    and event.key() == Qt.Key_Tab
                    and obj is line_edit
                ):
                    popup = completer.popup()
                    if popup and popup.isVisible():
                        model = popup.model()
                        cur = popup.currentIndex()
                        if not cur.isValid() and model.rowCount() > 0:
                            cur = model.index(0, 0)
                        if cur.isValid():
                            text = model.data(cur)
                            _on_activated(text)
                            popup.hide()
                            return True
                return False

        self._tab_filter_clientes = _TabFilter(self)
        QApplication.instance().installEventFilter(self._tab_filter_clientes)
        self.finished.connect(
            lambda: QApplication.instance().removeEventFilter(self._tab_filter_clientes)
        )

        # Strip espacios al salir del campo
        line_edit.editingFinished.connect(
            lambda: line_edit.setText(line_edit.text().strip())
        )

        self.combo_cliente.setCurrentIndex(0)
        line_edit.clear()
    
    def _verificar_cliente_estado(self, text):
        """Muestra botón + o check verde según si el cliente existe en la lista"""
        text = text.strip()
        if not text:
            self.btn_agregar_cliente.setVisible(False)
            self.lbl_cliente_ok.setVisible(False)
            return
        idx = self.combo_cliente.findText(text, Qt.MatchExactly)
        cliente_id = self.combo_cliente.itemData(idx) if idx >= 0 else None
        if cliente_id:
            self.btn_agregar_cliente.setVisible(False)
            self.lbl_cliente_ok.setVisible(True)
        else:
            self.btn_agregar_cliente.setVisible(True)
            self.lbl_cliente_ok.setVisible(False)

    def _agregar_cliente_rapido(self):
        """Abre el diálogo de nuevo cliente con el nombre prellenado"""
        from views.clientes_view import AgregarClienteDialog
        nombre_sugerido = self.combo_cliente.lineEdit().text().strip()
        dialog = AgregarClienteDialog(self)
        if nombre_sugerido:
            dialog.nombre.setText(nombre_sugerido)
        if dialog.exec() == QDialog.Accepted:
            datos = dialog.obtener_datos()
            nuevo_id = cliente_service.crear_cliente(
                datos['nombre'], datos.get('telefono', ''),
                datos.get('sexo', ''), datos.get('fecha_nacimiento'),
                datos.get('email', '')
            )
            self.cargar_clientes()
            idx = self.combo_cliente.findData(nuevo_id)
            if idx >= 0:
                self.combo_cliente.setCurrentIndex(idx)

    def cargar_datos_membresia(self):
        """Carga los datos de la membresía a editar"""
        if not self.membresia:
            return
        
        # Seleccionar cliente
        for i in range(self.combo_cliente.count()):
            if self.combo_cliente.itemData(i) == self.membresia['cliente_id']:
                self.combo_cliente.setCurrentIndex(i)
                break
        
        # Fecha inicio
        fecha_parts = self.membresia['fecha_inicio'].split('-')
        self.fecha_inicio.setDate(QDate(int(fecha_parts[0]), int(fecha_parts[1]), int(fecha_parts[2])))
        
        # Monto
        self.monto.setText(str(self.membresia['monto']))
        
        # Tipo (si existe en los datos guardados)
        tipo_guardado = self.membresia.get('tipo', '')
        if tipo_guardado:
            idx_tipo = self.combo_tipo.findText(tipo_guardado)
            if idx_tipo >= 0:
                self.combo_tipo.blockSignals(True)
                self.combo_tipo.setCurrentIndex(idx_tipo)
                self.combo_tipo.blockSignals(False)

        # Método de pago (informativo: se intenta cargar desde el pago asociado)
        try:
            pago_id = self.membresia.get('pago_id')
            if pago_id:
                from services import pago_service

                pago = pago_service.obtener_pago(pago_id)
                metodo = (pago or {}).get('metodo')
                if metodo:
                    idx_metodo = self.combo_metodo_pago.findText(metodo)
                    if idx_metodo >= 0:
                        self.combo_metodo_pago.setCurrentIndex(idx_metodo)
        except Exception:
            # Si falla, mantener el valor por defecto
            pass
    
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

        # Validar que se haya seleccionado un cliente del dropdown (no sólo escrito)
        texto_campo = self.combo_cliente.lineEdit().text().strip()
        idx = self.combo_cliente.findText(texto_campo, Qt.MatchExactly)
        cliente_id = self.combo_cliente.itemData(idx) if idx >= 0 else None
        if not cliente_id:
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText("Seleccione un cliente de la lista")
            msg.setStyleSheet(MSG_STYLE)
            msg.exec()
            return
        
        monto_texto = self.monto.text().strip()
        if not monto_texto:
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText("Ingrese un monto mayor a 0")
            msg.setStyleSheet(MSG_STYLE)
            msg.exec()
            return
        
        try:
            monto_valor = float(monto_texto)
            if monto_valor <= 0:
                raise ValueError("Monto debe ser mayor a 0")
        except ValueError:
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText("El monto debe ser mayor a 0")
            msg.setStyleSheet(MSG_STYLE)
            msg.exec()
            return
        
        self.accept()
    
    def obtener_datos(self):
        """Retorna los datos ingresados"""
        fecha = self.fecha_inicio.date()
        monto_texto = self.monto.text().strip()
        texto_campo = self.combo_cliente.lineEdit().text().strip()
        idx = self.combo_cliente.findText(texto_campo, Qt.MatchExactly)
        cliente_id = self.combo_cliente.itemData(idx) if idx >= 0 else None
        return {
            'cliente_id': cliente_id,
            'fecha_inicio': date(fecha.year(), fecha.month(), fecha.day()),
            'tipo': self.combo_tipo.currentText(),
            'monto': float(monto_texto) if monto_texto else 0.0,
            'metodo_pago': self.combo_metodo_pago.currentText() or "Efectivo",
        }


class MembresiasView(QWidget):
    """Vista de gestión de membresías"""
    def __init__(self):
        super().__init__()
        self.filtro_actual = "Todos"
        self.filtro_fecha_desde = None
        self.filtro_fecha_hasta = None
        self.init_ui()
        self.cargar_datos()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Encabezado
        header_layout = QHBoxLayout()
        
        titulo = QLabel("Membresías")
        titulo.setFont(QFont("Arial", 24, QFont.Bold))
        titulo.setStyleSheet("color: #1a1a1a;")
        header_layout.addWidget(titulo)
        
        header_layout.addStretch()
        
        self.search_cliente = QLineEdit()
        self.search_cliente.setPlaceholderText("🔍 Buscar cliente...")
        self.search_cliente.setClearButtonEnabled(True)
        self.search_cliente.setFixedWidth(220)
        self.search_cliente.setStyleSheet("""
            QLineEdit {
                padding: 8px 10px; border: 1px solid #d0d0d0; border-radius: 5px;
                background-color: #f5f5f5; font-size: 13px; color: #2c2c2c;
            }
            QLineEdit:focus { border: 2px solid #c0c0c0; }
        """)
        self.search_cliente.textChanged.connect(self.cargar_datos)
        header_layout.addWidget(self.search_cliente)
        
        btn_agregar = QPushButton("Agregar Membresía")
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
        btn_agregar.clicked.connect(self.agregar_membresia)
        header_layout.addWidget(btn_agregar)
        
        layout.addLayout(header_layout)
        
        # Filtros
        filtros_layout = QHBoxLayout()
        label_filtro = QLabel("Filtro:")
        label_filtro.setStyleSheet("color: #555555;")
        filtros_layout.addWidget(label_filtro)
        
        self.btn_todos = QPushButton("Todos")
        self.btn_activas = QPushButton("Activas")
        self.btn_por_vencer = QPushButton("Por Vencer")
        self.btn_vencidas = QPushButton("Vencidas")
        
        # Estilos para los botones de filtro
        estilo_botones = """
            QPushButton {
                color: #555555;
                background-color: #eeeeee;
                border: 1px solid #d0d0d0;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:checked {
                background-color: #d8d8d8;
                color: #555555;
                border: 1px solid #c0c0c0;
            }
            QPushButton:hover {
                background-color: #d8d8d8;
            }
            QPushButton:checked:hover {
                background-color: #333333;
            }
        """
        
        for btn, filtro in [(self.btn_todos, "Todos"), (self.btn_activas, ESTADO_ACTIVA),
                            (self.btn_por_vencer, ESTADO_POR_VENCER), (self.btn_vencidas, ESTADO_VENCIDA)]:
            btn.setCheckable(True)
            btn.setStyleSheet(estilo_botones)
            btn.clicked.connect(lambda checked, f=filtro: self.cambiar_filtro(f))
            filtros_layout.addWidget(btn)
        
        self.btn_todos.setChecked(True)
        filtros_layout.addStretch()
        
        layout.addLayout(filtros_layout)
        
        # ===== Filtro por rango de fechas =====
        filtros_fecha_layout = QHBoxLayout()
        
        label_fecha = QLabel("📅 Rango de fechas:")
        label_fecha.setStyleSheet("color: #555555; font-weight: bold; font-size: 13px;")
        filtros_fecha_layout.addWidget(label_fecha)
        
        _cal_ss = """
            QCalendarWidget QAbstractItemView {
                selection-background-color: #5e88b4;
                selection-color: white;
                color: #2c2c2c;
                background-color: #eaf0f9;
            }
            QCalendarWidget QWidget {
                color: #2c2c2c;
                background-color: #eaf0f9;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #dce7f3;
            }
            QCalendarWidget QToolButton {
                color: #2c2c2c;
                background-color: #dce7f3;
            }
            QCalendarWidget QMenu {
                color: #2c2c2c;
                background-color: #f5f5f5;
            }
            QCalendarWidget QSpinBox {
                color: #2c2c2c;
                background-color: #f0f0f0;
            }
            QCalendarWidget QTableView {
                color: #2c2c2c;
            }
        """
        estilo_date_m = """
            QDateEdit {
                padding: 6px 10px;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background-color: #f5f5f5;
                font-size: 12px;
                color: #2c2c2c;
                min-width: 120px;
            }
            QDateEdit:focus { border: 2px solid #c0c0c0; }
            QDateEdit::drop-down { border: none; }
        """
        
        label_desde_m = QLabel("Desde:")
        label_desde_m.setStyleSheet("color: #666666; font-size: 12px;")
        filtros_fecha_layout.addWidget(label_desde_m)
        
        self.date_desde = QDateEdit()
        self.date_desde.setCalendarPopup(True)
        self.date_desde.setDate(QDate(date.today().year, date.today().month, 1))
        self.date_desde.setDisplayFormat("dd/MM/yyyy")
        self.date_desde.setStyleSheet(estilo_date_m)
        self.date_desde.calendarWidget().setStyleSheet(_cal_ss)
        filtros_fecha_layout.addWidget(self.date_desde)
        
        label_hasta_m = QLabel("Hasta:")
        label_hasta_m.setStyleSheet("color: #666666; font-size: 12px;")
        filtros_fecha_layout.addWidget(label_hasta_m)
        
        self.date_hasta = QDateEdit()
        self.date_hasta.setCalendarPopup(True)
        self.date_hasta.setDate(QDate.currentDate())
        self.date_hasta.setDisplayFormat("dd/MM/yyyy")
        self.date_hasta.setStyleSheet(estilo_date_m)
        self.date_hasta.calendarWidget().setStyleSheet(_cal_ss)
        filtros_fecha_layout.addWidget(self.date_hasta)
        
        btn_filtrar_fecha = QPushButton("Filtrar")
        btn_filtrar_fecha.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                padding: 6px 16px; border: none; border-radius: 4px;
                font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #2980b9; color: white; }
        """)
        btn_filtrar_fecha.clicked.connect(self.filtrar_por_fecha)
        filtros_fecha_layout.addWidget(btn_filtrar_fecha)
        
        btn_limpiar_fecha = QPushButton("Limpiar")
        btn_limpiar_fecha.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6; color: white;
                padding: 6px 16px; border: none; border-radius: 4px;
                font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #7f8c8d; color: white; }
        """)
        btn_limpiar_fecha.clicked.connect(self.limpiar_filtro_fecha)
        filtros_fecha_layout.addWidget(btn_limpiar_fecha)
        
        filtros_fecha_layout.addStretch()
        layout.addLayout(filtros_fecha_layout)
        
        # Tabla
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(8)
        self.tabla.setHorizontalHeaderLabels(["Cliente", "Teléfono", "Inicio", "Vencimiento", "Monto", "Estado", "Factura", "Acciones"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.horizontalHeader().setSectionsClickable(True)
        self.tabla.horizontalHeader().setSortIndicatorShown(True)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setSelectionMode(QTableWidget.NoSelection)
        self.tabla.setSortingEnabled(True)
        self.tabla.setAlternatingRowColors(False)
        aplicar_estilo_tabla_moderna(self.tabla)
        
        layout.addWidget(self.tabla)
        
        self.setLayout(layout)
    
    def cambiar_filtro(self, filtro):
        """Cambia el filtro aplicado"""
        self.filtro_actual = filtro
        
        # Actualizar botones
        self.btn_todos.setChecked(filtro == "Todos")
        self.btn_activas.setChecked(filtro == ESTADO_ACTIVA)
        self.btn_por_vencer.setChecked(filtro == ESTADO_POR_VENCER)
        self.btn_vencidas.setChecked(filtro == ESTADO_VENCIDA)
        
        self.cargar_datos()
    
    def filtrar_por_fecha(self):
        """Filtra las membresías por el rango de fechas seleccionado"""
        qd_desde = self.date_desde.date()
        qd_hasta = self.date_hasta.date()
        self.filtro_fecha_desde = date(qd_desde.year(), qd_desde.month(), qd_desde.day())
        self.filtro_fecha_hasta = date(qd_hasta.year(), qd_hasta.month(), qd_hasta.day())
        
        if self.filtro_fecha_desde > self.filtro_fecha_hasta:
            QMessageBox.warning(self, "Error", "La fecha 'Desde' no puede ser mayor que 'Hasta'.")
            return
        
        self.cargar_datos()
    
    def limpiar_filtro_fecha(self):
        """Limpia el filtro de fecha"""
        self.filtro_fecha_desde = None
        self.filtro_fecha_hasta = None
        self.date_desde.setDate(QDate(date.today().year, date.today().month, 1))
        self.date_hasta.setDate(QDate.currentDate())
        self.cargar_datos()
    
    def cargar_datos(self):
        """Carga los datos de membresías con filtros de estado y fecha"""
        if self.filtro_actual == "Todos":
            membresias = membresia_service.listar_membresias()
        else:
            membresias = membresia_service.listar_membresias(estado=self.filtro_actual)
        
        # Aplicar filtro de fecha (por fecha de vencimiento)
        if self.filtro_fecha_desde and self.filtro_fecha_hasta:
            membresias = [
                m for m in membresias
                if self.filtro_fecha_desde <= date.fromisoformat(m['fecha_vencimiento']) <= self.filtro_fecha_hasta
            ]
        
        # Aplicar filtro por nombre de cliente
        texto_busqueda = self.search_cliente.text().strip().lower()
        if texto_busqueda:
            membresias = [m for m in membresias if texto_busqueda in m['cliente_nombre'].lower()]

        sorting_enabled = self.tabla.isSortingEnabled()
        self.tabla.setSortingEnabled(False)

        limpiar_tabla(self.tabla)
        self.tabla.setRowCount(len(membresias))

        for i, membresia in enumerate(membresias):
            self.tabla.setRowHeight(i, 52)
            # Cliente - color negro
            cliente_item = QTableWidgetItem(membresia['cliente_nombre'])
            cliente_item.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 0, cliente_item)
            
            # Teléfono - color negro
            telefono_item = QTableWidgetItem(membresia.get('cliente_telefono', ''))
            telefono_item.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 1, telefono_item)
            
            # Inicio - color negro
            inicio_item = QTableWidgetItem(membresia['fecha_inicio'])
            inicio_item.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 2, inicio_item)
            
            # Vencimiento - color negro
            vencimiento_item = QTableWidgetItem(membresia['fecha_vencimiento'])
            vencimiento_item.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 3, vencimiento_item)
            
            # Monto - color verde
            monto_item = QTableWidgetItem(f"${membresia['monto']:,.2f}")
            monto_item.setForeground(QColor("#27ae60"))
            self.tabla.setItem(i, 4, monto_item)
            
            # Colorear estado con widget propio (el QSS de la tabla override setForeground)
            if membresia['estado'] == ESTADO_ACTIVA:
                estado_color = "#27ae60"
            elif membresia['estado'] == ESTADO_POR_VENCER:
                estado_color = "#e67e22"
            elif membresia['estado'] == ESTADO_VENCIDA:
                estado_color = "#e74c3c"
            else:
                estado_color = "#1a1a1a"

            estado_widget = QWidget()
            estado_widget.setStyleSheet("background: transparent; border: none;")
            estado_layout = QHBoxLayout(estado_widget)
            estado_layout.setContentsMargins(12, 0, 8, 0)
            estado_label = QLabel(membresia['estado'])
            estado_label.setStyleSheet(
                f"color: {estado_color}; font-size: 13px; background: transparent; border: none;"
            )
            estado_layout.addWidget(estado_label)
            estado_layout.addStretch()
            self.tabla.setCellWidget(i, 5, estado_widget)
            
            # Botón Ver Factura
            btn_ver_factura = crear_boton_icono("see.svg", "#9b59b6", "#8e44ad", "Ver Factura")
            btn_ver_factura.clicked.connect(lambda checked, m=membresia: self.ver_factura_membresia(m))
            self.tabla.setCellWidget(i, 6, crear_widget_centrado(btn_ver_factura))

            # Botones de acciones
            acciones_widget = QWidget()
            acciones_widget.setStyleSheet("background: transparent; border: none;")
            acciones_layout = QHBoxLayout(acciones_widget)
            acciones_layout.setContentsMargins(4, 4, 4, 4)
            acciones_layout.setSpacing(6)
            acciones_layout.setAlignment(Qt.AlignCenter)

            btn_eliminar = crear_boton_icono("delete.svg", "#e74c3c", "#c0392b", "Eliminar")
            btn_eliminar.clicked.connect(lambda checked, mid=membresia['id']: self.eliminar_membresia(mid))
            acciones_layout.addWidget(btn_eliminar)

            self.tabla.setCellWidget(i, 7, acciones_widget)

        self.tabla.setSortingEnabled(sorting_enabled)
    
    def agregar_membresia(self):
        """Abre diálogo para agregar membresía"""
        dialog = AgregarMembresiaDialog(self)
        if dialog.exec():
            datos = dialog.obtener_datos()
            try:
                # Verificar si el cliente ya tiene una membresía activa
                membresia_activa = membresia_service.obtener_membresia_activa(datos['cliente_id'])
                nueva_inicio = datos['fecha_inicio']
                if isinstance(nueva_inicio, str):
                    nueva_inicio = date.fromisoformat(nueva_inicio)
                if membresia_activa and nueva_inicio <= date.fromisoformat(membresia_activa['fecha_vencimiento']):
                    cliente = cliente_service.obtener_cliente(datos['cliente_id'])
                    msg = QMessageBox(self)
                    msg.setWindowTitle("Membresía Activa")
                    msg.setText(f"El cliente {cliente['nombre']} ya tiene una membresía activa.")
                    msg.setInformativeText(f"Estado: {membresia_activa['estado']}\nVencimiento: {membresia_activa['fecha_vencimiento']}")
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
                
                # Importar pago_service aquí para evitar imports circulares
                from services import pago_service

                metodo_pago = (datos.get('metodo_pago') or "Efectivo").strip() or "Efectivo"
                
                # Crear el pago primero
                ok_pago, pago_id = pago_service.crear_pago(
                    cliente_id=datos['cliente_id'],
                    monto=datos['monto'],
                    metodo=metodo_pago,
                    fecha_pago=datos['fecha_inicio'],
                    concepto="Pago de membresía"
                )
                if not ok_pago:
                    raise Exception(f"Error al registrar el pago: {pago_id}")
                
                # Crear membresía con el pago_id
                membresia_id = membresia_service.crear_membresia(
                    cliente_id=datos['cliente_id'],
                    tipo=datos.get('tipo', 'Mensualidad'),
                    fecha_inicio=datos['fecha_inicio'],
                    monto=datos['monto'],
                    pago_id=pago_id
                )
                
                # Obtener datos completos de la membresía
                membresia = membresia_service.obtener_membresia(membresia_id)
                cliente = cliente_service.obtener_cliente(datos['cliente_id'])
                
                # Generar factura
                ruta_factura = generar_factura_membresia(membresia, cliente)
                
                # Recargar datos
                self.cargar_datos()
                
                # Preguntar si desea ver la factura
                respuesta_msg = QMessageBox(self)
                respuesta_msg.setWindowTitle("Membresía Creada")
                respuesta_msg.setText(f"Membresía creada exitosamente.\nFactura #{membresia_id} generada.\n\n¿Desea abrir la factura?")
                respuesta_msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                respuesta_msg.setDefaultButton(QMessageBox.Yes)
                respuesta_msg.setStyleSheet("""
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
                respuesta = respuesta_msg.exec()
                
                if respuesta == QMessageBox.Yes:
                    abrir_factura(ruta_factura)
                    
            except Exception as e:
                msg = QMessageBox(self)
                msg.setWindowTitle("Error")
                msg.setText(f"Error al crear membresía: {str(e)}")
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
    
    def editar_membresia(self, membresia):
        """Abre diálogo para editar una membresía"""
        dialog = AgregarMembresiaDialog(self, membresia=membresia)
        if dialog.exec():
            datos = dialog.obtener_datos()
            try:
                membresia_service.actualizar_membresia(
                    membresia_id=membresia['id'],
                    cliente_id=datos['cliente_id'],
                    tipo=datos.get('tipo', 'Mensualidad'),
                    fecha_inicio=datos['fecha_inicio'],
                    monto=datos['monto']
                )
                self.cargar_datos()
                
                # Mensaje con estilo
                msg = QMessageBox(self)
                msg.setWindowTitle("Éxito")
                msg.setText("Membresía actualizada exitosamente")
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
                    
            except Exception as e:
                msg = QMessageBox(self)
                msg.setWindowTitle("Error")
                msg.setText(f"Error al actualizar membresía: {str(e)}")
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
    
    def ver_factura_membresia(self, membresia):
        """Abre la factura de una membresía"""
        try:
            # Obtener información completa del cliente
            cliente = cliente_service.obtener_cliente(membresia['cliente_id'])
            
            # Generar o buscar la factura
            ruta_factura = Path.home() / "KyoGym" / "Facturas" / f"Factura_{membresia['id']}.pdf"
            
            # Si la factura no existe, generarla
            if not ruta_factura.exists():
                ruta_factura = generar_factura_membresia(membresia, cliente)
            
            # Abrir la factura
            abrir_factura(str(ruta_factura))
            
        except Exception as e:
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText(f"No se pudo abrir la factura: {str(e)}")
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
    
    def eliminar_membresia(self, membresia_id):
        """Elimina una membresía"""
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirmar eliminación")
        msg.setText("¿Está seguro de eliminar esta membresía?")
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
                membresia_service.eliminar_membresia(membresia_id)
                self.cargar_datos()
                # Refrescar tabla de pagos si está disponible
                try:
                    self.window().pagos_view.cargar_datos()
                    self.window().pagos_view.actualizar_total_mes()
                except Exception:
                    pass
                # Refrescar dashboard si está disponible
                try:
                    self.window().dashboard_view.cargar_datos()
                except Exception:
                    pass
                # Eliminar factura PDF de la membresía si existe
                try:
                    from pathlib import Path
                    ruta_factura = Path.home() / "KyoGym" / "Facturas" / f"Factura_{membresia_id}.pdf"
                    if ruta_factura.exists():
                        ruta_factura.unlink()
                except Exception:
                    pass
                # Mensaje con estilo
                msg = QMessageBox(self)
                msg.setWindowTitle("Éxito")
                msg.setText("Membresía eliminada correctamente")
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
            except Exception as e:
                msg = QMessageBox(self)
                msg.setWindowTitle("Error")
                msg.setText(f"Error al eliminar membresía: {str(e)}")
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

