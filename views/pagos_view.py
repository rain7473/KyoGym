"""Vista de gestión de pagos"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
                               QDialog, QFormLayout, QLineEdit, QDateEdit, QComboBox,
                               QMessageBox, QDialogButtonBox, QCompleter, QSpinBox,
                               QApplication, QAbstractItemView)
from PySide6.QtCore import Qt, QDate, QSize, QSortFilterProxyModel, QObject, QEvent
from PySide6.QtGui import QFont, QColor
from datetime import date
from services import pago_service, cliente_service, membresia_service
from services import inventario_service
from utils.factura_generator import generar_factura_pago, abrir_factura
from utils.iconos_ui import crear_boton_icono, crear_widget_centrado, _svg_icon_color as _svg_ic
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
        self.setMinimumWidth(520)
        self.init_ui()
        
        if pago:
            self.cargar_datos_pago()
    
    def init_ui(self):
        main_layout = QVBoxLayout()
        layout = QFormLayout()
        main_layout.addLayout(layout)

        # Estilos para el diálogo
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #2c2c2c;
                font-size: 13px;
            }
            QLineEdit, QComboBox, QDateEdit, QSpinBox {
                padding: 8px;
                border: 2px solid #d0d0d0;
                border-radius: 4px;
                background-color: #f5f5f5;
                color: #1a1a1a;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus {
                border: 2px solid #c0c0c0;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 20px;
                border: none;
                background-color: #e0e0e0;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #c8c8c8;
            }
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                border-bottom: 1px solid #d0d0d0;
                border-top-right-radius: 2px;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                border-bottom-right-radius: 2px;
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
        
        # Fecha
        self.fecha = QDateEdit()
        self.fecha.setDate(QDate.currentDate())
        self.fecha.setCalendarPopup(True)
        self.fecha.setDisplayFormat("dd/MM/yyyy")
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
        self.fecha.calendarWidget().setStyleSheet(_cal_ss)
        layout.addRow("Fecha:", self.fecha)
        
        # Método de pago
        self.metodo = QComboBox()
        self.metodo.addItems(["Efectivo", "Tarjeta", "Transferencia", "Otro"])
        layout.addRow("Método:", self.metodo)

        # ─── Items del pago ──────────────────────────────────────
        lbl_items = QLabel("Items del pago:")
        lbl_items.setStyleSheet("color: #2c2c2c; font-weight: bold; font-size: 13px; margin-top: 6px;")
        main_layout.addWidget(lbl_items)

        self._items = []
        self.tabla_items = QTableWidget(0, 4)
        self.tabla_items.setHorizontalHeaderLabels(["Concepto", "Cant.", "Subtotal", "Elim."])
        self.tabla_items.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabla_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tabla_items.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tabla_items.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.tabla_items.horizontalHeader().resizeSection(3, 58)
        self.tabla_items.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.tabla_items.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla_items.setFixedHeight(150)
        self.tabla_items.verticalHeader().setDefaultSectionSize(32)
        self.tabla_items.setStyleSheet("""
            QTableWidget { background-color: #f5f5f5; border: 1px solid #d0d0d0; }
            QHeaderView::section { background-color: #e0e0e0; color: #2c2c2c; font-weight: bold; padding: 4px; }
            QTableWidget::item { color: #1a1a1a; padding: 4px; }
            QTableWidget QLineEdit { color: #1a1a1a; background-color: white; border: 1px solid #808080; padding: 2px; }
        """)
        main_layout.addWidget(self.tabla_items)
        self.tabla_items.cellChanged.connect(self._on_subtotal_editado)

        # Fila para agregar items
        add_row_widget = QWidget()
        add_row_layout = QHBoxLayout(add_row_widget)
        add_row_layout.setContentsMargins(0, 0, 0, 0)
        add_row_layout.setSpacing(6)

        self.combo_tipo_item = QComboBox()
        self.combo_tipo_item.addItems(["Pago de día", "Producto"])
        self.combo_tipo_item.currentTextChanged.connect(self._toggle_add_item_fields)
        add_row_layout.addWidget(self.combo_tipo_item)

        self.combo_cat_add = QComboBox()
        self.combo_cat_add.setVisible(False)
        self.combo_cat_add.setFixedWidth(110)
        add_row_layout.addWidget(self.combo_cat_add)

        self.combo_prod_add = QComboBox()
        self.combo_prod_add.setVisible(False)
        add_row_layout.addWidget(self.combo_prod_add, 1)

        self.spin_cant_add = QSpinBox()
        self.spin_cant_add.setMinimum(1)
        self.spin_cant_add.setMaximum(999)
        self.spin_cant_add.setValue(1)
        self.spin_cant_add.setFixedWidth(65)
        self.spin_cant_add.setVisible(False)
        add_row_layout.addWidget(self.spin_cant_add)

        self.btn_agregar_item = QPushButton("+ Agregar")
        self.btn_agregar_item.setFixedHeight(34)
        self.btn_agregar_item.clicked.connect(self._agregar_item)
        add_row_layout.addWidget(self.btn_agregar_item)

        main_layout.addWidget(add_row_widget)

        # Total
        total_widget = QWidget()
        total_layout = QHBoxLayout(total_widget)
        total_layout.setContentsMargins(0, 2, 0, 2)
        total_layout.addStretch()
        self.lbl_total = QLabel("Total: $0.00")
        total_font = QFont()
        total_font.setBold(True)
        total_font.setPointSize(12)
        self.lbl_total.setFont(total_font)
        self.lbl_total.setStyleSheet("color: #2c3e50;")
        total_layout.addWidget(self.lbl_total)
        main_layout.addWidget(total_widget)

        # Cargar productos y configurar campos
        self.cargar_productos()
        self._toggle_add_item_fields(self.combo_tipo_item.currentText())

        # Botones
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.aceptar)
        botones.rejected.connect(self.reject)
        main_layout.addWidget(botones)

        self.setLayout(main_layout)
    
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

    def cargar_productos(self):
        """Carga productos disponibles en el combo, filtrados por la categoría seleccionada"""
        todos = inventario_service.listar_productos()
        # Poblar categorías la primera vez
        if self.combo_cat_add.count() == 0:
            categorias = sorted({p['categoria'] for p in todos if p.get('categoria')})
            self.combo_cat_add.blockSignals(True)
            self.combo_cat_add.addItem("Todas")
            for cat in categorias:
                self.combo_cat_add.addItem(cat)
            self.combo_cat_add.blockSignals(False)
            self.combo_cat_add.currentTextChanged.connect(self.cargar_productos)

        cat_sel = self.combo_cat_add.currentText()
        if cat_sel and cat_sel != "Todas":
            productos = [p for p in todos if p.get('categoria') == cat_sel]
        else:
            productos = todos

        self.combo_prod_add.blockSignals(True)
        self.combo_prod_add.clear()
        for i, producto in enumerate(productos):
            self.combo_prod_add.addItem(producto['nombre'], producto['id'])
            self.combo_prod_add.setItemData(i, float(producto.get('precio', 0.0)), Qt.UserRole + 1)
        self.combo_prod_add.blockSignals(False)

    def _toggle_add_item_fields(self, tipo):
        """Muestra u oculta campos del panel agregar según el tipo seleccionado"""
        es_producto = tipo == "Producto"
        self.combo_cat_add.setVisible(es_producto)
        self.combo_prod_add.setVisible(es_producto)
        self.spin_cant_add.setVisible(es_producto)

    def _agregar_item(self):
        """Agrega un item al carrito de pago"""
        tipo = self.combo_tipo_item.currentText()
        if tipo == "Pago de día":
            nombre = "Pago de día"
            producto_id = None
            cantidad = 1
            precio_unit = 2.0
        else:
            idx = self.combo_prod_add.currentIndex()
            if idx < 0 or self.combo_prod_add.count() == 0:
                return
            nombre = self.combo_prod_add.currentText()
            producto_id = self.combo_prod_add.currentData()
            cantidad = self.spin_cant_add.value()
            try:
                precio_unit = float(self.combo_prod_add.itemData(idx, Qt.UserRole + 1) or 0.0)
            except (TypeError, ValueError):
                precio_unit = 0.0

        self._items.append({
            'nombre': nombre,
            'tipo': 'dia' if tipo == "Pago de día" else 'producto',
            'producto_id': producto_id,
            'cantidad': cantidad,
            'precio_unit': precio_unit,
            'subtotal': precio_unit * cantidad,
        })
        self._refrescar_tabla_items()
        self._actualizar_total()

    def _eliminar_item(self, idx):
        """Elimina un item del carrito por índice"""
        if 0 <= idx < len(self._items):
            self._items.pop(idx)
        self._refrescar_tabla_items()
        self._actualizar_total()

    def _refrescar_tabla_items(self):
        """Refresca la tabla visual con los items actuales del carrito"""
        self.tabla_items.blockSignals(True)
        self.tabla_items.setRowCount(0)
        for i, item in enumerate(self._items):
            row = self.tabla_items.rowCount()
            self.tabla_items.insertRow(row)
            label = item['nombre']
            if item['tipo'] == 'producto' and item['cantidad'] > 1:
                label += f" x{item['cantidad']}"

            # Concepto y Cant.: solo lectura
            item_concepto = QTableWidgetItem(label)
            item_concepto.setFlags(Qt.ItemIsEnabled)
            self.tabla_items.setItem(row, 0, item_concepto)

            item_cant = QTableWidgetItem(str(item['cantidad']))
            item_cant.setFlags(Qt.ItemIsEnabled)
            self.tabla_items.setItem(row, 1, item_cant)

            # Subtotal: editable (doble clic)
            item_sub = QTableWidgetItem(f"{item['subtotal']:.2f}")
            item_sub.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            item_sub.setToolTip("Doble clic para editar el subtotal")
            item_sub.setForeground(QColor("#1a6fa8"))
            self.tabla_items.setItem(row, 2, item_sub)

            btn_x = QPushButton()
            btn_x.setIcon(_svg_ic("delete.svg", QColor("white"), 15))
            btn_x.setIconSize(QSize(15, 15))
            btn_x.setFixedSize(28, 28)
            btn_x.setToolTip("Eliminar")
            btn_x.setCursor(Qt.PointingHandCursor)
            btn_x.setStyleSheet(
                "QPushButton { background-color: #e74c3c; border-radius: 4px; border: none; }"
                " QPushButton:hover { background-color: #c0392b; }"
            )
            btn_x.clicked.connect(lambda checked, idx_=i: self._eliminar_item(idx_))
            self.tabla_items.setCellWidget(row, 3, crear_widget_centrado(btn_x))
        self.tabla_items.blockSignals(False)

    def _on_subtotal_editado(self, row, col):
        """Actualiza el subtotal del item cuando el usuario lo edita directamente"""
        if col != 2:
            return
        if row < 0 or row >= len(self._items):
            return
        item_widget = self.tabla_items.item(row, col)
        if item_widget is None:
            return
        texto = item_widget.text().strip().replace(',', '.').replace('$', '')
        try:
            nuevo_subtotal = float(texto)
            if nuevo_subtotal < 0:
                raise ValueError
        except ValueError:
            # Revertir al valor anterior sin disparar el signal
            self.tabla_items.blockSignals(True)
            item_widget.setText(f"{self._items[row]['subtotal']:.2f}")
            self.tabla_items.blockSignals(False)
            return
        self._items[row]['subtotal'] = nuevo_subtotal
        # Actualizar precio_unit proporcional
        cant = self._items[row].get('cantidad', 1) or 1
        self._items[row]['precio_unit'] = nuevo_subtotal / cant
        self._actualizar_total()

    def _actualizar_total(self):
        """Actualiza la etiqueta con el total del carrito"""
        total = sum(item['subtotal'] for item in self._items)
        self.lbl_total.setText(f"Total: ${total:.2f}")

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

    def cargar_datos_pago(self):
        """Carga los datos del pago a editar reconstruyendo el carrito"""
        if not self.pago:
            return

        # Cliente
        for i in range(self.combo_cliente.count()):
            if self.combo_cliente.itemData(i) == self.pago['cliente_id']:
                self.combo_cliente.setCurrentIndex(i)
                break

        # Fecha
        fecha_parts = self.pago['fecha'].split('-')
        self.fecha.setDate(QDate(int(fecha_parts[0]), int(fecha_parts[1]), int(fecha_parts[2])))

        # Método
        metodo = self.pago.get('metodo', self.pago.get('metodo_pago', 'Efectivo'))
        index = self.metodo.findText(metodo)
        if index >= 0:
            self.metodo.setCurrentIndex(index)

        # Reconstruir items desde el pago guardado
        concepto = self.pago.get('concepto', '')
        producto_id = self.pago.get('producto_id')
        monto = float(self.pago.get('monto', 0))
        try:
            cantidad = int(self.pago.get('cantidad', 1) or 1)
        except (TypeError, ValueError):
            cantidad = 1

        if concepto == "Pago de día":
            self._items = [{
                'nombre': 'Pago de día', 'tipo': 'dia',
                'producto_id': None, 'cantidad': 1,
                'precio_unit': monto, 'subtotal': monto,
            }]
        elif producto_id is not None:
            precio_unit = monto / max(cantidad, 1)
            self._items = [{
                'nombre': concepto, 'tipo': 'producto',
                'producto_id': producto_id, 'cantidad': cantidad,
                'precio_unit': precio_unit, 'subtotal': monto,
            }]
        else:
            self._items = [{
                'nombre': concepto or 'Pago', 'tipo': 'otro',
                'producto_id': None, 'cantidad': 1,
                'precio_unit': monto, 'subtotal': monto,
            }]

        self._refrescar_tabla_items()
        self._actualizar_total()
    
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

        if not self._items:
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText("Agregue al menos un item al pago")
            msg.setStyleSheet(MSG_STYLE)
            msg.exec()
            return

        self.accept()
    
    def obtener_datos(self):
        """Retorna los datos del carrito de pago"""
        fecha = self.fecha.date()
        texto_campo = self.combo_cliente.lineEdit().text().strip()
        idx = self.combo_cliente.findText(texto_campo, Qt.MatchExactly)
        cliente_id = self.combo_cliente.itemData(idx) if idx >= 0 else None

        total = sum(item['subtotal'] for item in self._items)

        # Construir concepto como cadena de nombres
        partes = []
        for item in self._items:
            nombre = item['nombre']
            if item['tipo'] == 'producto' and item['cantidad'] > 1:
                nombre += f" x{item['cantidad']}"
            partes.append(nombre)
        concepto = " + ".join(partes) if partes else ""

        return {
            'cliente_id': cliente_id,
            'fecha': date(fecha.year(), fecha.month(), fecha.day()),
            'monto': total,
            'metodo': self.metodo.currentText(),
            'concepto': concepto,
            'items': list(self._items),
        }


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
        """
        
        label_desde_p = QLabel("Desde:")
        label_desde_p.setStyleSheet("color: #666666; font-size: 12px;")
        filtros_fecha_layout.addWidget(label_desde_p)
        
        self.date_desde = QDateEdit()
        self.date_desde.setCalendarPopup(True)
        self.date_desde.setDate(QDate(date.today().year, date.today().month, 1))
        self.date_desde.setDisplayFormat("dd/MM/yyyy")
        self.date_desde.setStyleSheet(estilo_date_pagos)
        self.date_desde.calendarWidget().setStyleSheet(_cal_ss)
        filtros_fecha_layout.addWidget(self.date_desde)
        
        label_hasta_p = QLabel("Hasta:")
        label_hasta_p.setStyleSheet("color: #666666; font-size: 12px;")
        filtros_fecha_layout.addWidget(label_hasta_p)
        
        self.date_hasta = QDateEdit()
        self.date_hasta.setCalendarPopup(True)
        self.date_hasta.setDate(QDate.currentDate())
        self.date_hasta.setDisplayFormat("dd/MM/yyyy")
        self.date_hasta.setStyleSheet(estilo_date_pagos)
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
            
            ok, resultado = pago_service.crear_pago_multiple(
                cliente_id=datos['cliente_id'],
                fecha_pago=datos['fecha'],
                monto=datos['monto'],
                metodo=datos['metodo'],
                concepto=datos['concepto'],
                items=datos.get('items', []),
            )

            if not ok:
                QMessageBox.warning(self, "Error", resultado)
                return

            pago_id = resultado

            
            # Generar factura
            pago = pago_service.obtener_pago(pago_id)
            cliente = cliente_service.obtener_cliente(datos['cliente_id'])
            ruta_factura = generar_factura_pago(pago, cliente, items=datos.get('items', []))
            
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
