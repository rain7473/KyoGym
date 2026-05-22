"""Vista de gestión de inventario"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
                               QDialog, QFormLayout, QLineEdit, QComboBox,
                               QMessageBox, QDialogButtonBox, QSpinBox, QDoubleSpinBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from services import inventario_service
from usuario_activo import obtener_usuario_activo
from utils.iconos_ui import crear_boton_icono, crear_widget_centrado
from utils.table_styles import aplicar_estilo_tabla_moderna
from utils.table_utils import limpiar_tabla
from utils.validators import crear_validador_nombre, crear_validador_entero, crear_validador_numerico_decimal


# ===========================================================================
# Diálogo de historial de auditoría
# ===========================================================================

class HistorialProductoDialog(QDialog):
    """Muestra el historial de auditoría de un producto."""

    _STYLE = """
        QDialog { background-color: #f5f5f5; }
        QLabel  { color: #2c2c2c; font-size: 13px; }
        QTableWidget {
            background-color: #ffffff;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            gridline-color: #e0e0e0;
            color: #1a1a1a;
            font-size: 12px;
        }
        QTableWidget::item { padding: 4px 8px; }
        QHeaderView::section {
            background-color: #2c3e50;
            color: white;
            font-weight: bold;
            padding: 6px;
            border: none;
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
        QPushButton:hover { background-color: #3d5166; }
    """

    def __init__(self, producto_id, producto_nombre, parent=None):
        super().__init__(parent)
        self.producto_id = producto_id
        self.setWindowTitle(f"Historial – {producto_nombre}")
        self.setMinimumSize(900, 480)
        self._init_ui(producto_nombre)

    def _init_ui(self, nombre):
        self.setStyleSheet(self._STYLE)
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        titulo = QLabel(f"Historial de cambios: {nombre}")
        titulo.setFont(QFont("Arial", 15, QFont.Bold))
        titulo.setStyleSheet("color: #1a1a1a;")
        layout.addWidget(titulo)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels([
            "Fecha y Hora", "Acción", "Campo", "Valor Anterior", "Valor Nuevo", "Usuario"
        ])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setSelectionMode(QTableWidget.NoSelection)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(False)
        layout.addWidget(self.tabla)

        self.lbl_vacio = QLabel("No hay registros de auditoría para este producto.")
        self.lbl_vacio.setStyleSheet("color: #888888; font-size: 12px;")
        self.lbl_vacio.setAlignment(Qt.AlignCenter)
        self.lbl_vacio.setVisible(False)
        layout.addWidget(self.lbl_vacio)

        bottom = QHBoxLayout()
        bottom.addStretch()
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.accept)
        bottom.addWidget(btn_cerrar)
        layout.addLayout(bottom)

        self.setLayout(layout)
        self._cargar_historial()

    def _cargar_historial(self):
        historial = inventario_service.obtener_historial_producto(self.producto_id)
        if not historial:
            self.tabla.setVisible(False)
            self.lbl_vacio.setVisible(True)
            return

        colores_fondo = {
            "CREAR":     QColor("#e8fdf0"),
            "MODIFICAR": QColor("#fff8e1"),
            "ELIMINAR":  QColor("#fde8e8"),
            "IMPORTAR":  QColor("#e8f4fd"),
        }
        colores_accion = {
            "CREAR":     QColor("#27ae60"),
            "MODIFICAR": QColor("#d68910"),
            "ELIMINAR":  QColor("#e74c3c"),
            "IMPORTAR":  QColor("#2980b9"),
        }

        self.tabla.setRowCount(len(historial))
        for i, reg in enumerate(historial):
            accion = reg.get("accion", "")
            color_fondo = colores_fondo.get(accion, QColor("#ffffff"))
            celdas = [
                reg.get("fecha_hora", ""),
                accion,
                reg.get("campo")          or "—",
                reg.get("valor_anterior") or "—",
                reg.get("valor_nuevo")    or "—",
                reg.get("usuario", ""),
            ]
            for j, texto in enumerate(celdas):
                item = QTableWidgetItem(str(texto))
                item.setBackground(color_fondo)
                if j == 1:
                    item.setForeground(colores_accion.get(accion, QColor("#2c2c2c")))
                self.tabla.setItem(i, j, item)
        self.tabla.resizeRowsToContents()


# ===========================================================================
class AgregarProductoDialog(QDialog):
    """Diálogo para agregar/editar producto"""
    def __init__(self, parent=None, producto=None):
        super().__init__(parent)
        self.producto = producto
        self.setWindowTitle("Editar Producto" if producto else "Nuevo Producto")
        self.setMinimumWidth(400)
        self.init_ui()
        
        if producto:
            self.cargar_datos_producto()
    
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
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                padding: 8px;
                border: 2px solid #d0d0d0;
                border-radius: 4px;
                background-color: #f5f5f5;
                color: #1a1a1a;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 2px solid #c0c0c0;
            }
            /* Forzar color en el popup de los QComboBox */
            QComboBox QAbstractItemView {
                background-color: #f5f5f5;
                color: #2c2c2c;
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
        
        # Nombre
        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText("Ingrese el nombre del producto")
        self.nombre.setValidator(crear_validador_nombre())
        layout.addRow("Nombre:", self.nombre)
        
        # Categoría
        self.categoria = QComboBox()
        self.categoria.setEditable(False)
        categorias_existentes = inventario_service.obtener_categorias()
        self.categoria.addItems(["Suplementos", "Equipamiento", "Accesorios", "Bebidas", "Otros"])
        if categorias_existentes:
            for cat in categorias_existentes:
                if cat not in ["Suplementos", "Equipamiento", "Accesorios", "Bebidas", "Otros"]:
                    self.categoria.addItem(cat)
        layout.addRow("Categoría:", self.categoria)
        
        # Cantidad
        self.cantidad = QSpinBox()
        self.cantidad.setMinimum(0)
        self.cantidad.setMaximum(999999)
        self.cantidad.setValue(0)
        layout.addRow("Cantidad:", self.cantidad)
        
        # Precio
        self.precio = QDoubleSpinBox()
        self.precio.setMinimum(0.0)
        self.precio.setMaximum(999999.99)
        self.precio.setDecimals(2)
        self.precio.setPrefix("$")
        self.precio.setValue(0.0)
        layout.addRow("Precio:", self.precio)

        # Stock mínimo
        self.stock_minimo = QSpinBox()
        self.stock_minimo.setMinimum(0)
        self.stock_minimo.setMaximum(999999)
        self.stock_minimo.setValue(0)
        layout.addRow("Stock Mínimo:", self.stock_minimo)
        
        # Botones
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.aceptar)
        botones.rejected.connect(self.reject)
        btn_cancel = botones.button(QDialogButtonBox.Cancel)
        if btn_cancel:
            btn_cancel.setStyleSheet("""
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
        layout.addRow(botones)
        
        self.setLayout(layout)
    
    def cargar_datos_producto(self):
        """Carga los datos del producto para editar"""
        self.nombre.setText(self.producto['nombre'])
        self.categoria.setCurrentText(self.producto['categoria'])
        self.cantidad.setValue(self.producto['cantidad'])
        self.precio.setValue(self.producto['precio'])
        self.stock_minimo.setValue(self.producto.get('stock_minimo') or 0)
    
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

        if not self.categoria.currentText().strip():
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText("La categoría es requerida")
            msg.setStyleSheet(MSG_STYLE)
            msg.exec()
            return

        if self.precio.value() <= 0:
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText("El precio debe ser mayor a 0")
            msg.setStyleSheet(MSG_STYLE)
            msg.exec()
            return

        self.accept()
    
    def obtener_datos(self):
        """Retorna los datos ingresados"""
        return {
            'nombre': self.nombre.text().strip(),
            'categoria': self.categoria.currentText().strip(),
            'cantidad': self.cantidad.value(),
            'precio': self.precio.value(),
            'stock_minimo': self.stock_minimo.value()
        }


class InventarioView(QWidget):
    """Vista de gestión de inventario"""
    def __init__(self):
        super().__init__()
        self.filtro_categoria = None
        self.filtro_bajo_stock = False
        self.init_ui()
        self.cargar_datos()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Encabezado
        header_layout = QHBoxLayout()
        
        titulo = QLabel("Inventario")
        titulo.setFont(QFont("Arial", 24, QFont.Bold))
        titulo.setStyleSheet("color: #1a1a1a;")
        header_layout.addWidget(titulo)
        
        header_layout.addStretch()
        
        # Búsqueda
        self.buscar_input = QLineEdit()
        self.buscar_input.setPlaceholderText("Buscar producto...")
        self.buscar_input.setMinimumWidth(250)
        self.buscar_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #d0d0d0;
                border-radius: 5px;
                font-size: 13px;
                color: #1a1a1a;
                background-color: #f5f5f5;
            }
            QLineEdit:focus {
                border: 2px solid #c0c0c0;
            }
        """)
        self.buscar_input.textChanged.connect(self.cargar_datos)
        header_layout.addWidget(self.buscar_input)
        
        btn_agregar = QPushButton("Agregar Producto")
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
        btn_agregar.clicked.connect(self.agregar_producto)
        header_layout.addWidget(btn_agregar)

        layout.addLayout(header_layout)
        
        # Filtros por categoría
        filtros_layout = QHBoxLayout()
        
        label_categoria = QLabel("Categoría:")
        label_categoria.setStyleSheet("color: #555555; font-weight: bold;")
        filtros_layout.addWidget(label_categoria)
        
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
        
        self.btn_todas_categorias = QPushButton("Todas")
        self.btn_todas_categorias.setCheckable(True)
        self.btn_todas_categorias.setChecked(True)
        self.btn_todas_categorias.clicked.connect(lambda: self.cambiar_filtro_categoria(None, self.btn_todas_categorias))
        self.btn_todas_categorias.setStyleSheet(estilo_botones)
        filtros_layout.addWidget(self.btn_todas_categorias)
        
        # Botones de categorías comunes
        self.botones_categoria = {}
        categorias_comunes = ["Suplementos", "Equipamiento", "Accesorios", "Bebidas"]
        
        for cat in categorias_comunes:
            btn = QPushButton(cat)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, c=cat, b=btn: self.cambiar_filtro_categoria(c, b))
            btn.setStyleSheet(estilo_botones)
            filtros_layout.addWidget(btn)
            self.botones_categoria[cat] = btn
        
        filtros_layout.addStretch()

        # Botón Bajo Stock
        self.btn_bajo_stock = QPushButton("⚠ Bajo Stock")
        self.btn_bajo_stock.setCheckable(True)
        self.btn_bajo_stock.setChecked(False)
        self.btn_bajo_stock.clicked.connect(self._toggle_bajo_stock)
        self.btn_bajo_stock.setStyleSheet("""
            QPushButton {
                background-color: #eeeeee;
                color: #555555;
                padding: 8px 16px;
                border: 2px solid #d0d0d0;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #fde8cc;
                border: 2px solid #f39c12;
                color: #c87f0a;
            }
            QPushButton:checked {
                background-color: #fde8cc;
                border: 2px solid #f39c12;
                color: #c87f0a;
            }
        """)
        filtros_layout.addWidget(self.btn_bajo_stock)
        
        layout.addLayout(filtros_layout)
        
        # Tabla de inventario
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(["Nombre", "Categoría", "Cantidad", "Precio", "Acciones"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.horizontalHeader().setSectionsClickable(True)
        self.tabla.horizontalHeader().setSortIndicatorShown(True)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setSelectionMode(QTableWidget.NoSelection)
        self.tabla.setSortingEnabled(True)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.verticalHeader().setVisible(False)

        aplicar_estilo_tabla_moderna(self.tabla)
        
        layout.addWidget(self.tabla)
        
        self.setLayout(layout)
    
    def cargar_datos(self):
        """Carga los productos en la tabla"""
        buscar = self.buscar_input.text() if hasattr(self, 'buscar_input') else ""
        productos = inventario_service.listar_productos(
            buscar=buscar,
            categoria=self.filtro_categoria,
            bajo_stock=self.filtro_bajo_stock
        )

        sorting_enabled = self.tabla.isSortingEnabled()
        self.tabla.setSortingEnabled(False)

        limpiar_tabla(self.tabla)
        
        self.tabla.setRowCount(len(productos))

        for i, producto in enumerate(productos):
            self.tabla.setRowHeight(i, 52)
            # Nombre
            self.tabla.setItem(i, 0, QTableWidgetItem(producto['nombre']))
            
            # Categoría
            self.tabla.setItem(i, 1, QTableWidgetItem(producto['categoria']))
            
            # Cantidad
            cantidad_item = QTableWidgetItem(str(producto['cantidad']))
            # Colorear según stock
            if producto['cantidad'] == 0:
                cantidad_item.setForeground(QColor("#e74c3c"))  # Rojo
            elif producto['cantidad'] < 5:
                cantidad_item.setForeground(QColor("#f39c12"))  # Naranja
            else:
                cantidad_item.setForeground(QColor("#27ae60"))  # Verde
            self.tabla.setItem(i, 2, cantidad_item)
            
            # Precio
            precio_item = QTableWidgetItem(f"${producto['precio']:.2f}")
            self.tabla.setItem(i, 3, precio_item)

            # Botones de acciones
            acciones_widget = QWidget()
            acciones_widget.setStyleSheet("background: transparent; border: none;")
            acciones_layout = QHBoxLayout(acciones_widget)
            acciones_layout.setContentsMargins(4, 4, 4, 4)
            acciones_layout.setSpacing(6)
            acciones_layout.setAlignment(Qt.AlignCenter)

            btn_editar = crear_boton_icono("edit.svg", "#7a8899", "#8a9aa9", "Editar")
            btn_editar.clicked.connect(lambda checked, p=producto: self.editar_producto(p))
            acciones_layout.addWidget(btn_editar)

            btn_eliminar = crear_boton_icono("delete.svg", "#e74c3c", "#c0392b", "Eliminar")
            btn_eliminar.clicked.connect(lambda checked, pid=producto['id']: self.eliminar_producto(pid))
            acciones_layout.addWidget(btn_eliminar)

            btn_hist = crear_boton_icono("history.svg", "#7a6fa0", "#6a5f90", "Ver historial")
            btn_hist.clicked.connect(lambda checked, p=producto: self.mostrar_historial(p))
            acciones_layout.addWidget(btn_hist)

            self.tabla.setCellWidget(i, 4, acciones_widget)

        self.tabla.setSortingEnabled(sorting_enabled)
    
    def _toggle_bajo_stock(self):
        """Activa/desactiva el filtro de bajo stock"""
        self.filtro_bajo_stock = self.btn_bajo_stock.isChecked()
        self.cargar_datos()

    def cambiar_filtro_categoria(self, categoria, boton_activo):
        """Cambia el filtro de categoría"""
        # Desmarcar todos los botones
        self.btn_todas_categorias.setChecked(False)
        for btn in self.botones_categoria.values():
            btn.setChecked(False)
        
        # Marcar el botón activo
        boton_activo.setChecked(True)
        
        # Actualizar filtro
        self.filtro_categoria = categoria
        self.cargar_datos()
    
    def agregar_producto(self):
        """Muestra diálogo para agregar producto"""
        dialog = AgregarProductoDialog(self)
        if dialog.exec():
            datos = dialog.obtener_datos()
            try:
                inventario_service.crear_producto(
                    nombre=datos['nombre'],
                    categoria=datos['categoria'],
                    cantidad=datos['cantidad'],
                    precio=datos['precio'],
                    stock_minimo=datos.get('stock_minimo', 0),
                    usuario=obtener_usuario_activo()
                )
                
                msg = QMessageBox(self)
                msg.setWindowTitle("Éxito")
                msg.setText("Producto agregado exitosamente")
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
                msg.setText(f"Error al agregar producto: {str(e)}")
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
    
    def editar_producto(self, producto):
        """Muestra diálogo para editar producto"""
        dialog = AgregarProductoDialog(self, producto)
        if dialog.exec():
            datos = dialog.obtener_datos()
            try:
                inventario_service.actualizar_producto(
                    producto_id=producto['id'],
                    nombre=datos['nombre'],
                    categoria=datos['categoria'],
                    cantidad=datos['cantidad'],
                    precio=datos['precio'],
                    stock_minimo=datos.get('stock_minimo', 0),
                    usuario=obtener_usuario_activo()
                )
                
                msg = QMessageBox(self)
                msg.setWindowTitle("Éxito")
                msg.setText("Producto actualizado exitosamente")
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
                msg.setText(f"Error al actualizar producto: {str(e)}")
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
    
    def eliminar_producto(self, producto_id):
        """Elimina un producto"""
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirmar eliminación")
        msg.setText("¿Está seguro de eliminar este producto?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        msg.setStyleSheet("""
            QMessageBox { background-color: #ffffff; }
            QLabel { color: #2c2c2c; font-size: 13px; min-width: 300px; }
        """)
        btn_si = msg.button(QMessageBox.Yes)
        btn_si.setText("Sí")
        btn_si.setStyleSheet("background:#e74c3c; color:white; padding:8px 20px; border:none; border-radius:4px; font-weight:bold; font-size:13px; min-width:80px;")
        btn_no = msg.button(QMessageBox.No)
        btn_no.setStyleSheet("background:#7f8c8d; color:white; padding:8px 20px; border:none; border-radius:4px; font-weight:bold; font-size:13px; min-width:80px;")
        respuesta = msg.exec()
        
        if respuesta == QMessageBox.Yes:
            try:
                inventario_service.eliminar_producto(producto_id, usuario=obtener_usuario_activo())
                
                msg = QMessageBox(self)
                msg.setWindowTitle("Éxito")
                msg.setText("Producto eliminado exitosamente")
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
                msg.setText(f"Error al eliminar producto: {str(e)}")
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

    # -----------------------------------------------------------------------
    # Historial de auditoría
    # -----------------------------------------------------------------------

    def mostrar_historial(self, producto):
        """Abre el diálogo de historial de auditoría para el producto seleccionado."""
        dialog = HistorialProductoDialog(producto['id'], producto['nombre'], self)
        dialog.exec()


