"""Vista de gestión de inventario"""
import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
                               QDialog, QFormLayout, QLineEdit, QComboBox,
                               QMessageBox, QDialogButtonBox, QSpinBox, QDoubleSpinBox,
                               QFileDialog)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from services import inventario_service
from usuario_activo import obtener_usuario_activo
from utils.iconos_ui import crear_boton_icono, crear_widget_centrado
from utils.table_styles import aplicar_estilo_tabla_moderna
from utils.table_utils import limpiar_tabla
from utils.validators import crear_validador_nombre, crear_validador_entero, crear_validador_numerico_decimal


# ===========================================================================
# Diálogo de importación masiva
# ===========================================================================

class ImportarArchivoDialog(QDialog):
    """Diálogo para importar productos masivamente desde Excel (.xlsx) o PDF."""

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
            min-width: 100px;
        }
        QPushButton:hover    { background-color: #3d5166; }
        QPushButton:disabled { background-color: #aaaaaa; color: #ffffff; }
        QPushButton#btn_importar       { background-color: #27ae60; }
        QPushButton#btn_importar:hover { background-color: #229954; }
        QLineEdit {
            padding: 8px;
            border: 2px solid #d0d0d0;
            border-radius: 4px;
            background-color: #f0f0f0;
            color: #1a1a1a;
            font-size: 13px;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importar Productos")
        self.setMinimumSize(860, 580)
        self.productos_validos = []
        self.filepath = None
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(self._STYLE)
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        titulo = QLabel("Importar Productos desde Archivo")
        titulo.setFont(QFont("Arial", 16, QFont.Bold))
        titulo.setStyleSheet("color: #1a1a1a; margin-bottom: 4px;")
        layout.addWidget(titulo)

        nota = QLabel(
            "Formatos soportados: Excel (.xlsx) y PDF con tablas.\n"
            "Columnas esperadas: nombre, categoria, cantidad, precio, stock_minimo"
        )
        nota.setStyleSheet("color: #666666; font-size: 12px;")
        layout.addWidget(nota)

        file_row = QHBoxLayout()
        self.lbl_archivo = QLineEdit()
        self.lbl_archivo.setPlaceholderText("Ningún archivo seleccionado...")
        self.lbl_archivo.setReadOnly(True)
        file_row.addWidget(self.lbl_archivo)

        btn_sel = QPushButton("Seleccionar archivo")
        btn_sel.setMinimumWidth(160)
        btn_sel.clicked.connect(self._seleccionar_archivo)
        file_row.addWidget(btn_sel)

        btn_proc = QPushButton("Procesar")
        btn_proc.setMinimumWidth(100)
        btn_proc.clicked.connect(self._procesar_archivo)
        file_row.addWidget(btn_proc)
        layout.addLayout(file_row)

        self.lbl_resumen = QLabel("")
        self.lbl_resumen.setStyleSheet("font-size: 12px; color: #555555;")
        layout.addWidget(self.lbl_resumen)

        self.tabla_preview = QTableWidget()
        self.tabla_preview.setColumnCount(7)
        self.tabla_preview.setHorizontalHeaderLabels([
            "Nombre", "Categoría", "Cantidad", "Precio", "Stock Mín.", "Estado", "Detalle"
        ])
        self.tabla_preview.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_preview.setSelectionMode(QTableWidget.NoSelection)
        self.tabla_preview.verticalHeader().setVisible(False)
        layout.addWidget(self.tabla_preview)

        bottom = QHBoxLayout()
        bottom.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        bottom.addWidget(btn_cancelar)

        self.btn_importar = QPushButton("Importar productos válidos")
        self.btn_importar.setObjectName("btn_importar")
        self.btn_importar.setEnabled(False)
        self.btn_importar.clicked.connect(self.accept)
        bottom.addWidget(self.btn_importar)
        layout.addLayout(bottom)

        self.setLayout(layout)

    def _seleccionar_archivo(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo", "",
            "Archivos soportados (*.xlsx *.pdf);;Excel (*.xlsx);;PDF (*.pdf)"
        )
        if filepath:
            self.filepath = filepath
            self.lbl_archivo.setText(filepath)
            self.tabla_preview.setRowCount(0)
            self.lbl_resumen.setText("")
            self.btn_importar.setEnabled(False)
            self.productos_validos = []

    def _procesar_archivo(self):
        if not self.filepath:
            QMessageBox.warning(self, "Aviso", "Seleccione un archivo primero.")
            return
        try:
            from services import importacion_inventario_service as imp_svc
            ext = os.path.splitext(self.filepath)[1].lower()
            if ext == ".xlsx":
                raw = imp_svc.leer_excel(self.filepath)
            elif ext == ".pdf":
                raw = imp_svc.leer_pdf(self.filepath)
            else:
                QMessageBox.warning(
                    self, "Formato no soportado",
                    "Solo se aceptan archivos .xlsx y .pdf"
                )
                return
            if not raw:
                QMessageBox.information(
                    self, "Sin datos",
                    "No se encontraron datos en el archivo."
                )
                return
            productos = imp_svc.validar_productos(raw)
            self._mostrar_preview(productos)
        except ImportError as e:
            QMessageBox.critical(self, "Dependencia faltante", str(e))
        except Exception as e:
            QMessageBox.critical(
                self, "Error al procesar",
                f"No se pudo procesar el archivo:\n{str(e)}"
            )

    def _mostrar_preview(self, productos):
        self.productos_validos = [p for p in productos if not p["errores"]]
        total    = len(productos)
        validos  = len(self.productos_validos)
        invalidos = total - validos

        self.lbl_resumen.setText(
            f"Total: {total} filas  |  ✓ Válidos: {validos}  |  ✗ Con errores: {invalidos}"
        )

        color_ok  = QColor("#e8fdf0")
        color_err = QColor("#fde8e8")
        self.tabla_preview.setSortingEnabled(False)
        self.tabla_preview.setRowCount(total)

        for i, p in enumerate(productos):
            es_valido = not p["errores"]
            color = color_ok if es_valido else color_err
            celdas = [
                p.get("nombre", ""),
                p.get("categoria", ""),
                str(p.get("cantidad", 0)),
                f"${p.get('precio', 0):.2f}",
                str(p.get("stock_minimo", 0)),
                "✓ Válido" if es_valido else "✗ Error",
                ", ".join(p["errores"]) if p["errores"] else "",
            ]
            for j, texto in enumerate(celdas):
                item = QTableWidgetItem(str(texto))
                item.setBackground(color)
                if j == 5:
                    item.setForeground(
                        QColor("#27ae60") if es_valido else QColor("#e74c3c")
                    )
                self.tabla_preview.setItem(i, j, item)

        self.btn_importar.setEnabled(validos > 0)
        self.btn_importar.setText(f"Importar {validos} producto(s) válido(s)")

    def obtener_productos_validos(self):
        return self.productos_validos


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

        btn_importar_archivo = QPushButton("Importar archivo")
        btn_importar_archivo.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #229954;
                color: white;
            }
        """)
        btn_importar_archivo.clicked.connect(self.importar_archivo)
        header_layout.addWidget(btn_importar_archivo)

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
        productos = inventario_service.listar_productos(buscar=buscar, categoria=self.filtro_categoria)

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
    # Importación masiva
    # -----------------------------------------------------------------------

    def importar_archivo(self):
        """Abre el diálogo de importación masiva y procesa los productos válidos."""
        dialog = ImportarArchivoDialog(self)
        if not dialog.exec():
            return
        productos = dialog.obtener_productos_validos()
        if not productos:
            return
        try:
            insertados, duplicados = inventario_service.importar_productos_masivo(
                productos, usuario=obtener_usuario_activo()
            )
            detalle = f"Productos importados correctamente: {insertados}"
            if duplicados:
                detalle += f"\nOmitidos por nombre duplicado: {duplicados}"
            msg = QMessageBox(self)
            msg.setWindowTitle("Importación completada")
            msg.setText(detalle)
            msg.setStyleSheet("""
                QMessageBox { background-color: #f5f5f5; }
                QLabel { color: #2c2c2c; font-size: 13px; min-width: 300px; }
                QPushButton {
                    background-color: #27ae60; color: white;
                    padding: 8px 20px; border: none; border-radius: 4px;
                    font-weight: bold; font-size: 13px; min-width: 80px;
                }
                QPushButton:hover { background-color: #229954; }
            """)
            msg.exec()
            self.cargar_datos()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al importar productos:\n{str(e)}")

    # -----------------------------------------------------------------------
    # Historial de auditoría
    # -----------------------------------------------------------------------

    def mostrar_historial(self, producto):
        """Abre el diálogo de historial de auditoría para el producto seleccionado."""
        dialog = HistorialProductoDialog(producto['id'], producto['nombre'], self)
        dialog.exec()


