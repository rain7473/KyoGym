"""Vista de gestión de pagos"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
                               QDialog, QFormLayout, QLineEdit, QDateEdit, QComboBox,
                               QMessageBox, QDialogButtonBox, QCompleter)
from PySide6.QtCore import Qt, QDate, QSortFilterProxyModel
from PySide6.QtGui import QFont, QColor
from datetime import date
from services import pago_service, cliente_service, membresia_service
from services import inventario_service
from utils.factura_generator import generar_factura_pago, abrir_factura
from utils.iconos_ui import crear_boton_icono, crear_widget_centrado
from utils.table_styles import aplicar_estilo_tabla_moderna
from utils.table_utils import limpiar_tabla
from utils.validators import crear_validador_numerico_decimal, crear_validador_entero
from pathlib import Path



class RegistrarPagoDialog(QDialog):
    """Diálogo para registrar o editar un pago"""
    def __init__(self, parent=None, pago=None):
        super().__init__(parent)
        self.pago = pago
        self.setWindowTitle("Editar Pago" if pago else "Registrar Pago")
        self.setMinimumWidth(400)
        self.init_ui()
        
        if pago:
            self.cargar_datos_pago()
    
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
        
        # Selector de cliente con búsqueda en tiempo real
        self.combo_cliente = QComboBox()
        self.combo_cliente.setEditable(True)
        self.combo_cliente.setInsertPolicy(QComboBox.NoInsert)
        self.combo_cliente.lineEdit().setPlaceholderText("Escribe para buscar...")
        self.combo_cliente.lineEdit().setClearButtonEnabled(True)
        self.cargar_clientes()
        layout.addRow("Cliente:", self.combo_cliente)
        
        # Fecha
        self.fecha = QDateEdit()
        self.fecha.setDate(QDate.currentDate())
        self.fecha.setCalendarPopup(True)
        self.fecha.setDisplayFormat("dd/MM/yyyy")
        layout.addRow("Fecha:", self.fecha)
        
        # Monto
        self.monto = QLineEdit()
        self.monto.setPlaceholderText("0.00")
        self.monto.setValidator(crear_validador_numerico_decimal())
        layout.addRow("Monto:", self.monto)
        
        # Método de pago
        self.metodo = QComboBox()
        self.metodo.addItems(["Efectivo", "Tarjeta", "Transferencia", "Otro"])
        layout.addRow("Método:", self.metodo)
        
        # Concepto (Tipo)
        self.concepto = QComboBox()
        self.concepto.addItems(["Pago de día", "Producto"])
        layout.addRow("Concepto:", self.concepto)

        # Selector de producto (oculto por defecto)
        self.combo_producto = QComboBox()
        self.combo_producto.setVisible(False)
        layout.addRow("Producto:", self.combo_producto)

        # Campo cantidad (oculto por defecto)
        self.input_cantidad = QLineEdit()
        self.input_cantidad.setPlaceholderText("Cantidad")
        self.input_cantidad.setValidator(crear_validador_entero())
        self.input_cantidad.setVisible(False)
        layout.addRow("Cantidad:", self.input_cantidad)

        # Cargar productos
        self.cargar_productos()

        # Detectar cambio de concepto
        self.concepto.currentTextChanged.connect(self.toggle_producto_fields)

        
        # Botones
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.aceptar)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)
        
        self.setLayout(layout)
    
    def cargar_clientes(self):
        """Carga la lista de clientes con búsqueda en tiempo real"""
        clientes = cliente_service.listar_clientes()
        self.combo_cliente.clear()
        self.combo_cliente.addItem("", None)  # opción vacía inicial

        nombres = []
        for cliente in clientes:
            self.combo_cliente.addItem(cliente['nombre'], cliente['id'])
            nombres.append(cliente['nombre'])

        # Autocompletar con búsqueda por contenido
        completer = QCompleter(nombres)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.combo_cliente.setCompleter(completer)

        # Sincronizar selección al elegir desde el completador
        def _on_activated(text):
            idx = self.combo_cliente.findText(text)
            if idx >= 0:
                self.combo_cliente.setCurrentIndex(idx)

        completer.activated.connect(_on_activated)

        # Dejar el campo vacío al abrir
        self.combo_cliente.setCurrentIndex(0)
        self.combo_cliente.lineEdit().clear()

    def cargar_productos(self):
        """Carga productos en el combo"""
        productos = inventario_service.listar_productos()
        self.combo_producto.clear()

        for producto in productos:
            self.combo_producto.addItem(producto['nombre'], producto['id'])

    def toggle_producto_fields(self, texto):
        """Muestra u oculta campos según concepto"""
        es_producto = texto == "Producto"
        self.combo_producto.setVisible(es_producto)
        self.input_cantidad.setVisible(es_producto)
    
    def cargar_datos_pago(self):
        """Carga los datos del pago a editar"""
        if not self.pago:
            return
        
        # Seleccionar cliente
        for i in range(self.combo_cliente.count()):
            if self.combo_cliente.itemData(i) == self.pago['cliente_id']:
                self.combo_cliente.setCurrentIndex(i)
                break
        
        # Fecha
        fecha_parts = self.pago['fecha'].split('-')
        self.fecha.setDate(QDate(int(fecha_parts[0]), int(fecha_parts[1]), int(fecha_parts[2])))
        
        # Monto
        self.monto.setText(str(self.pago['monto']))
        
        # Método
        metodo = self.pago.get('metodo_pago', 'Efectivo')
        index = self.metodo.findText(metodo)
        if index >= 0:
            self.metodo.setCurrentIndex(index)
        
        # Concepto
        concepto_guardado = self.pago.get('concepto', '')
        index = self.concepto.findText(concepto_guardado)
        if index >= 0:
            self.concepto.setCurrentIndex(index)
        else:
            # Es un nombre de producto directamente almacenado
            self.concepto.setCurrentText('Producto')
    
    def aceptar(self):
        """Valida y acepta el diálogo"""
        if self.combo_cliente.currentData() is None:
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText("Seleccione un cliente")
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
            msg.exec()
            return
        
        try:
            monto_texto = self.monto.text().strip()
            if not monto_texto:
                raise ValueError("Monto vacío")
            monto = float(monto_texto.replace(',', '.'))
            if monto <= 0:
                raise ValueError()
        except ValueError:
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText("Ingrese un monto válido mayor a 0 (puede usar decimales, ej: 0.50)")
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
            msg.exec()
            return
        
        self.accept()
    
    def obtener_datos(self):
        """Retorna los datos ingresados"""
        fecha = self.fecha.date()
        cliente_id = self.combo_cliente.currentData()
        concepto_texto = self.concepto.currentText()
        monto_texto = self.monto.text().strip()

        datos = {
            'cliente_id': cliente_id,
            'fecha': date(fecha.year(), fecha.month(), fecha.day()),
            'monto': float(monto_texto.replace(',', '.')) if monto_texto else 0.0,
            'metodo': self.metodo.currentText(),
            'concepto': concepto_texto
        }

        if concepto_texto == "Producto":
            producto_id = self.combo_producto.currentData()
            nombre_producto = self.combo_producto.currentText()
            try:
                cantidad = int(self.input_cantidad.text())
                if cantidad <= 0:
                    raise ValueError()
            except:
                QMessageBox.warning(self, "Error", "Cantidad inválida")
                return {}

            datos['producto_id'] = producto_id
            datos['cantidad'] = cantidad
            datos['concepto'] = nombre_producto  # Guardar nombre real del producto

        return datos


class PagosView(QWidget):
    """Vista de gestión de pagos"""
    def __init__(self):
        super().__init__()
        self.mostrar_membresias = False
        self.init_ui()
        self.cargar_datos()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Encabezado
        header_layout = QHBoxLayout()
        
        titulo = QLabel("Pagos")
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
        self.search_cliente.textChanged.connect(lambda: self.cargar_datos(limite=500))
        header_layout.addWidget(self.search_cliente)
        
        btn_registrar = QPushButton("Registrar Pago")
        btn_registrar.setStyleSheet("""
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
        btn_registrar.clicked.connect(self.registrar_pago)
        header_layout.addWidget(btn_registrar)
        
        layout.addLayout(header_layout)
        
        # Filtros rápidos
        filtros_layout = QHBoxLayout()
        label_filtro = QLabel("Ver:")
        label_filtro.setStyleSheet("color: #555555;")
        filtros_layout.addWidget(label_filtro)
        
        # Estilos para botones de filtro
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
        
        btn_todos = QPushButton("Todos")
        btn_mes = QPushButton("Este Mes")
        btn_mayor_10 = QPushButton("Mayor a $10")
        btn_ultimos = QPushButton("Últimos 50")
        
        btn_todos.clicked.connect(lambda: self.cargar_datos(limite=500))
        btn_mes.clicked.connect(self.cargar_pagos_mes)
        btn_mayor_10.clicked.connect(self.cargar_pagos_mayores_10)
        btn_ultimos.clicked.connect(lambda: self.cargar_datos(limite=50))
        
        for btn in [btn_todos, btn_mes, btn_mayor_10, btn_ultimos]:
            btn.setStyleSheet(estilo_botones)
            filtros_layout.addWidget(btn)

        # Botón toggle para mostrar/ocultar pagos de membresía
        self.btn_mostrar_membresias = QPushButton("Mostrar membresías")
        self.btn_mostrar_membresias.setCheckable(True)
        self.btn_mostrar_membresias.setChecked(False)
        self.btn_mostrar_membresias.setStyleSheet(estilo_botones)
        self.btn_mostrar_membresias.clicked.connect(self._toggle_membresias)
        filtros_layout.addWidget(self.btn_mostrar_membresias)

        filtros_layout.addStretch()
        
        # Total del mes
        self.label_total = QLabel("Total del mes: $0")
        self.label_total.setFont(QFont("Arial", 14, QFont.Bold))
        self.label_total.setStyleSheet("color: #27ae60;")
        filtros_layout.addWidget(self.label_total)
        
        layout.addLayout(filtros_layout)
        
        # ===== Filtro por rango de fechas =====
        filtros_fecha_layout = QHBoxLayout()
        
        label_fecha = QLabel("📅 Rango de fechas:")
        label_fecha.setStyleSheet("color: #555555; font-weight: bold; font-size: 13px;")
        filtros_fecha_layout.addWidget(label_fecha)
        
        estilo_date_pagos = """
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
            QCalendarWidget QTableView {
                color: #2c2c2c;
            }
        """
        
        label_desde_p = QLabel("Desde:")
        label_desde_p.setStyleSheet("color: #666666; font-size: 12px;")
        filtros_fecha_layout.addWidget(label_desde_p)
        
        self.date_desde = QDateEdit()
        self.date_desde.setCalendarPopup(True)
        self.date_desde.setDate(QDate(date.today().year, date.today().month, 1))
        self.date_desde.setDisplayFormat("dd/MM/yyyy")
        self.date_desde.setStyleSheet(estilo_date_pagos)
        filtros_fecha_layout.addWidget(self.date_desde)
        
        label_hasta_p = QLabel("Hasta:")
        label_hasta_p.setStyleSheet("color: #666666; font-size: 12px;")
        filtros_fecha_layout.addWidget(label_hasta_p)
        
        self.date_hasta = QDateEdit()
        self.date_hasta.setCalendarPopup(True)
        self.date_hasta.setDate(QDate.currentDate())
        self.date_hasta.setDisplayFormat("dd/MM/yyyy")
        self.date_hasta.setStyleSheet(estilo_date_pagos)
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
        self.tabla.setColumnCount(7)
        self.tabla.setHorizontalHeaderLabels(["Cliente", "Fecha", "Monto", "Método", "Concepto", "Factura", "Acciones"])
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
        self.actualizar_total_mes()
    
    def _filtrar_por_cliente(self, pagos):
        """Filtra la lista de pagos por el texto ingresado en el buscador de cliente"""
        texto = self.search_cliente.text().strip().lower()
        if texto:
            return [p for p in pagos if texto in p.get('cliente_nombre', '').lower()]
        return pagos

    def _filtrar_membresias(self, pagos):
        """Filtra pagos de membresía según el toggle activo"""
        if self.mostrar_membresias:
            return pagos
        return [p for p in pagos if p.get('concepto', '') != "Pago de membresía"]

    def _toggle_membresias(self):
        """Alterna la visibilidad de pagos de membresía"""
        self.mostrar_membresias = self.btn_mostrar_membresias.isChecked()
        self.cargar_datos()

    def cargar_datos(self, limite=100):
        """Carga los datos de pagos"""
        pagos = self._filtrar_membresias(self._filtrar_por_cliente(pago_service.listar_pagos(limite=limite)))
        sorting_enabled = self.tabla.isSortingEnabled()
        self.tabla.setSortingEnabled(False)

        limpiar_tabla(self.tabla)
        self.tabla.setRowCount(len(pagos))
        
        for i, pago in enumerate(pagos):
            self.tabla.setRowHeight(i, 52)
            # Cliente - negro
            item_cliente = QTableWidgetItem(pago['cliente_nombre'])
            item_cliente.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 0, item_cliente)
            
            # Fecha - negro
            item_fecha = QTableWidgetItem(pago['fecha'])
            item_fecha.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 1, item_fecha)
            
            # Monto - verde con widget (setForeground es pisado por el QSS de la tabla)
            monto_widget = QWidget()
            monto_widget.setStyleSheet("background: transparent; border: none;")
            monto_layout = QHBoxLayout(monto_widget)
            monto_layout.setContentsMargins(12, 0, 8, 0)
            monto_label = QLabel(f"${pago['monto']:,.2f}")
            monto_label.setStyleSheet("color: #27ae60; font-size: 13px; background: transparent; border: none;")
            monto_layout.addWidget(monto_label)
            monto_layout.addStretch()
            self.tabla.setCellWidget(i, 2, monto_widget)

            # Método - negro
            item_metodo = QTableWidgetItem(pago['metodo'])
            item_metodo.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 3, item_metodo)
            
            # Concepto - negro
            item_concepto = QTableWidgetItem(pago.get('concepto', ''))
            item_concepto.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 4, item_concepto)
            
            # Botón Ver Factura
            btn_ver_factura = crear_boton_icono("see.svg", "#9b59b6", "#8e44ad", "Ver Factura")
            btn_ver_factura.clicked.connect(lambda checked, p=pago: self.ver_factura_pago(p))
            self.tabla.setCellWidget(i, 5, crear_widget_centrado(btn_ver_factura))

            # Botones de acciones
            acciones_widget = QWidget()
            acciones_widget.setStyleSheet("background: transparent; border: none;")
            acciones_layout = QHBoxLayout(acciones_widget)
            acciones_layout.setContentsMargins(4, 4, 4, 4)
            acciones_layout.setSpacing(6)
            acciones_layout.setAlignment(Qt.AlignCenter)

            if pago.get('concepto', '') != "Pago de membresía":
                btn_editar = crear_boton_icono("edit.svg", "#7a8899", "#8a9aa9", "Editar")
                btn_editar.clicked.connect(lambda checked, p=pago: self.editar_pago(p))
                acciones_layout.addWidget(btn_editar)

            btn_eliminar = crear_boton_icono("delete.svg", "#e74c3c", "#c0392b", "Eliminar")
            btn_eliminar.clicked.connect(lambda checked, pid=pago['id']: self.eliminar_pago(pid))
            acciones_layout.addWidget(btn_eliminar)

            self.tabla.setCellWidget(i, 6, acciones_widget)

        self.tabla.setSortingEnabled(sorting_enabled)
    
    def cargar_pagos_mes(self):
        """Carga solo los pagos del mes actual"""
        pagos = self._filtrar_membresias(self._filtrar_por_cliente(pago_service.obtener_pagos_del_mes()))
        sorting_enabled = self.tabla.isSortingEnabled()
        self.tabla.setSortingEnabled(False)

        limpiar_tabla(self.tabla)
        self.tabla.setRowCount(len(pagos))
        
        for i, pago in enumerate(pagos):
            self.tabla.setRowHeight(i, 52)
            # Cliente - negro
            item_cliente = QTableWidgetItem(pago['cliente_nombre'])
            item_cliente.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 0, item_cliente)
            
            # Fecha - negro
            item_fecha = QTableWidgetItem(pago['fecha'])
            item_fecha.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 1, item_fecha)
            
            # Monto - verde con widget (setForeground es pisado por el QSS de la tabla)
            monto_widget = QWidget()
            monto_widget.setStyleSheet("background: transparent; border: none;")
            monto_layout = QHBoxLayout(monto_widget)
            monto_layout.setContentsMargins(12, 0, 8, 0)
            monto_label = QLabel(f"${pago['monto']:,.2f}")
            monto_label.setStyleSheet("color: #27ae60; font-size: 13px; background: transparent; border: none;")
            monto_layout.addWidget(monto_label)
            monto_layout.addStretch()
            self.tabla.setCellWidget(i, 2, monto_widget)

            # Método - negro
            item_metodo = QTableWidgetItem(pago['metodo'])
            item_metodo.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 3, item_metodo)
            
            # Concepto - negro
            item_concepto = QTableWidgetItem(pago.get('concepto', ''))
            item_concepto.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 4, item_concepto)
            
            # Botón Ver Factura
            btn_ver_factura = crear_boton_icono("see.svg", "#9b59b6", "#8e44ad", "Ver Factura")
            btn_ver_factura.clicked.connect(lambda checked, p=pago: self.ver_factura_pago(p))
            self.tabla.setCellWidget(i, 5, crear_widget_centrado(btn_ver_factura))

            # Botones de acciones
            acciones_widget = QWidget()
            acciones_widget.setStyleSheet("background: transparent; border: none;")
            acciones_layout = QHBoxLayout(acciones_widget)
            acciones_layout.setContentsMargins(4, 4, 4, 4)
            acciones_layout.setSpacing(6)
            acciones_layout.setAlignment(Qt.AlignCenter)

            if pago.get('concepto', '') != "Pago de membresía":
                btn_editar = crear_boton_icono("edit.svg", "#7a8899", "#8a9aa9", "Editar")
                btn_editar.clicked.connect(lambda checked, p=pago: self.editar_pago(p))
                acciones_layout.addWidget(btn_editar)

            btn_eliminar = crear_boton_icono("delete.svg", "#e74c3c", "#c0392b", "Eliminar")
            btn_eliminar.clicked.connect(lambda checked, pid=pago['id']: self.eliminar_pago(pid))
            acciones_layout.addWidget(btn_eliminar)

            self.tabla.setCellWidget(i, 6, acciones_widget)

        self.tabla.setSortingEnabled(sorting_enabled)

    def cargar_pagos_mayores_10(self):
        """Carga pagos cuyo monto sea mayor a 10 dólares"""
        pagos = pago_service.listar_pagos(limite=1000)
        pagos_filtrados = self._filtrar_por_cliente([p for p in pagos if p.get('monto', 0) > 10])

        self.label_total.setText(f"Total > $10: ${sum(p['monto'] for p in pagos_filtrados):,.2f}")
        self._poblar_tabla_pagos(pagos_filtrados)
    
    def actualizar_total_mes(self):
        """Actualiza el total de pagos del mes"""
        total = pago_service.calcular_total_mes()
        self.label_total.setText(f"Total del mes: ${total:,.2f}")
    
    def filtrar_por_fecha(self):
        """Filtra los pagos por el rango de fechas seleccionado"""
        qd_desde = self.date_desde.date()
        qd_hasta = self.date_hasta.date()
        fecha_desde = date(qd_desde.year(), qd_desde.month(), qd_desde.day())
        fecha_hasta = date(qd_hasta.year(), qd_hasta.month(), qd_hasta.day())
        
        if fecha_desde > fecha_hasta:
            QMessageBox.warning(self, "Error", "La fecha 'Desde' no puede ser mayor que 'Hasta'.")
            return
        
        pagos = self._filtrar_por_cliente(pago_service.listar_pagos(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, limite=1000))
        total_filtrado = sum(p['monto'] for p in pagos)
        self.label_total.setText(f"Total filtrado: ${total_filtrado:,.2f}")
        self._poblar_tabla_pagos(pagos)
    
    def limpiar_filtro_fecha(self):
        """Limpia el filtro de fecha y muestra todos"""
        self.date_desde.setDate(QDate(date.today().year, date.today().month, 1))
        self.date_hasta.setDate(QDate.currentDate())
        self.cargar_datos()
        self.actualizar_total_mes()
    
    def _poblar_tabla_pagos(self, pagos):
        """Llena la tabla con la lista de pagos proporcionada"""
        pagos = self._filtrar_membresias(pagos)
        sorting_enabled = self.tabla.isSortingEnabled()
        self.tabla.setSortingEnabled(False)
        limpiar_tabla(self.tabla)
        self.tabla.setRowCount(len(pagos))
        
        for i, pago in enumerate(pagos):
            self.tabla.setRowHeight(i, 52)
            item_cliente = QTableWidgetItem(pago['cliente_nombre'])
            item_cliente.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 0, item_cliente)
            
            item_fecha = QTableWidgetItem(pago['fecha'])
            item_fecha.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 1, item_fecha)
            
            monto_widget = QWidget()
            monto_widget.setStyleSheet("background: transparent; border: none;")
            monto_layout = QHBoxLayout(monto_widget)
            monto_layout.setContentsMargins(12, 0, 8, 0)
            monto_label = QLabel(f"${pago['monto']:,.2f}")
            monto_label.setStyleSheet("color: #27ae60; font-size: 13px; background: transparent; border: none;")
            monto_layout.addWidget(monto_label)
            monto_layout.addStretch()
            self.tabla.setCellWidget(i, 2, monto_widget)

            item_metodo = QTableWidgetItem(pago['metodo'])
            item_metodo.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 3, item_metodo)
            
            item_concepto = QTableWidgetItem(pago.get('concepto', ''))
            item_concepto.setForeground(QColor("#1a1a1a"))
            self.tabla.setItem(i, 4, item_concepto)
            
            btn_ver_factura = crear_boton_icono("see.svg", "#9b59b6", "#8e44ad", "Ver Factura")
            btn_ver_factura.clicked.connect(lambda checked, p=pago: self.ver_factura_pago(p))
            self.tabla.setCellWidget(i, 5, crear_widget_centrado(btn_ver_factura))

            acciones_widget = QWidget()
            acciones_widget.setStyleSheet("background: transparent; border: none;")
            acciones_layout = QHBoxLayout(acciones_widget)
            acciones_layout.setContentsMargins(4, 4, 4, 4)
            acciones_layout.setSpacing(6)
            acciones_layout.setAlignment(Qt.AlignCenter)

            if pago.get('concepto', '') != "Pago de membresía":
                btn_editar = crear_boton_icono("edit.svg", "#7a8899", "#8a9aa9", "Editar")
                btn_editar.clicked.connect(lambda checked, p=pago: self.editar_pago(p))
                acciones_layout.addWidget(btn_editar)

            btn_eliminar = crear_boton_icono("delete.svg", "#e74c3c", "#c0392b", "Eliminar")
            btn_eliminar.clicked.connect(lambda checked, pid=pago['id']: self.eliminar_pago(pid))
            acciones_layout.addWidget(btn_eliminar)

            self.tabla.setCellWidget(i, 6, acciones_widget)

        self.tabla.setSortingEnabled(sorting_enabled)
    
    def registrar_pago(self):
        """Abre diálogo para registrar pago"""
        dialog = RegistrarPagoDialog(self)
        if dialog.exec():
            datos = dialog.obtener_datos()
            
            if not datos:
                return
            
            ok, resultado = pago_service.crear_pago(
                cliente_id=datos['cliente_id'],
                fecha_pago=datos['fecha'],
                monto=datos['monto'],
                metodo=datos['metodo'],
                concepto=datos['concepto'],
                producto_id=datos.get('producto_id'),
                cantidad=datos.get('cantidad', 1)
            )

            if not ok:
                QMessageBox.warning(self, "Error", resultado)
                return

            pago_id = resultado

            
            # Generar factura
            pago = pago_service.obtener_pago(pago_id)
            cliente = cliente_service.obtener_cliente(datos['cliente_id'])
            ruta_factura = generar_factura_pago(pago, cliente)
            
            self.cargar_datos()
            self.actualizar_total_mes()
            
            # Mensaje con estilo y botón para ver factura
            msg = QMessageBox(self)
            msg.setWindowTitle("Éxito")
            msg.setText("Pago registrado correctamente")
            msg.setInformativeText("¿Desea ver la factura generada?")
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
            btn_ver = msg.addButton("Ver Factura", QMessageBox.ActionRole)
            msg.addButton("Cerrar", QMessageBox.RejectRole)
            msg.exec()
            
            if msg.clickedButton() == btn_ver:
                abrir_factura(ruta_factura)
    
    def editar_pago(self, pago):
        """Abre diálogo para editar un pago"""
        dialog = RegistrarPagoDialog(self, pago=pago)
        if dialog.exec():
            datos = dialog.obtener_datos()
            pago_service.actualizar_pago(
                pago_id=pago['id'],
                cliente_id=datos['cliente_id'],
                fecha_pago=datos['fecha'],
                monto=datos['monto'],
                metodo=datos['metodo'],
                concepto=datos['concepto']
            )
            # Regenerar factura con datos actualizados
            try:
                pago_actualizado = pago_service.obtener_pago(pago['id'])
                cliente = cliente_service.obtener_cliente(datos['cliente_id'])
                generar_factura_pago(pago_actualizado, cliente)
            except Exception:
                pass
            self.cargar_datos()
            self.actualizar_total_mes()
            # Actualizar dashboard si está disponible
            try:
                self.window().dashboard_view.cargar_datos()
            except Exception:
                pass
            # Mensaje con estilo
            msg = QMessageBox(self)
            msg.setWindowTitle("Éxito")
            msg.setText("Pago actualizado correctamente")
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
    
    def ver_factura_pago(self, pago):
        """Abre la factura de un pago"""
        try:
            # Obtener información completa del cliente
            cliente = cliente_service.obtener_cliente(pago['cliente_id'])
            
            # Generar o buscar la factura
            ruta_factura = Path.home() / "KyoGym" / "Facturas" / f"Factura_Pago_{pago['id']}.pdf"
            
            # Si la factura no existe, generarla
            if not ruta_factura.exists():
                ruta_factura = generar_factura_pago(pago, cliente)
            
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
    
    def eliminar_pago(self, pago_id):
        """Elimina un pago"""
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirmar eliminación")
        msg.setText("¿Está seguro de eliminar este pago?")
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
                pago_service.eliminar_pago(pago_id)
                self.cargar_datos()
                self.actualizar_total_mes()
                # Refrescar membresías si está disponible
                try:
                    self.window().membresias_view.cargar_datos()
                except Exception:
                    pass
                # Refrescar dashboard si está disponible
                try:
                    self.window().dashboard_view.cargar_datos()
                except Exception:
                    pass
                # Mensaje con estilo
                msg = QMessageBox(self)
                msg.setWindowTitle("Éxito")
                msg.setText("Pago eliminado correctamente")
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
                msg.setText(f"Error al eliminar pago: {str(e)}")
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
