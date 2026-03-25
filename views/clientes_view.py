"""Vista de gestión de clientes"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
                               QDialog, QFormLayout, QLineEdit, QDateEdit, QComboBox,
                               QMessageBox, QDialogButtonBox, QFrame)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor
from datetime import date
from services import cliente_service
from utils.iconos_ui import crear_boton_icono, crear_widget_centrado
from utils.table_styles import aplicar_estilo_tabla_moderna
from utils.table_utils import limpiar_tabla
from utils.validators import crear_validador_nombre, TelefonoFormateadoLineEdit, crear_validador_email


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
                border: 1px solid #d0d0d0;
                border-radius: 5px;
                font-size: 13px;
                color: #2c2c2c;
                background-color: #f5f5f5;
            }
            QLineEdit:focus {
                border: 2px solid #c0c0c0;
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
        
        # Separador
        separador = QLabel("|")
        separador.setStyleSheet("color: #333333; font-size: 18px; padding: 0 10px;")
        filtros_layout.addWidget(separador)
        
        # Filtros por edad
        label_edad = QLabel("Edad:")
        label_edad.setStyleSheet("color: #555555; font-weight: bold;")
        filtros_layout.addWidget(label_edad)
        
        self.btn_todas_edades = QPushButton("Todas")
        self.btn_todas_edades.setCheckable(True)
        self.btn_todas_edades.setChecked(True)
        self.btn_todas_edades.clicked.connect(lambda: self.cambiar_filtro_edad(None, self.btn_todas_edades))
        self.btn_todas_edades.setStyleSheet(estilo_botones)
        filtros_layout.addWidget(self.btn_todas_edades)
        
        # Filtro menor que
        label_menor = QLabel("Menor que:")
        label_menor.setStyleSheet("color: #666666;")
        filtros_layout.addWidget(label_menor)
        
        self.input_menor_que = QLineEdit()
        self.input_menor_que.setPlaceholderText("Edad")
        self.input_menor_que.setMaximumWidth(60)
        self.input_menor_que.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #d0d0d0;
                border-radius: 5px;
                font-size: 13px;
                color: #1a1a1a;
                background-color: #f5f5f5;
            }
        """)
        self.input_menor_que.textChanged.connect(self.aplicar_filtro_menor_que)
        filtros_layout.addWidget(self.input_menor_que)
        
        # Filtro mayor que
        label_mayor = QLabel("Mayor que:")
        label_mayor.setStyleSheet("color: #666666;")
        filtros_layout.addWidget(label_mayor)
        
        self.input_mayor_que = QLineEdit()
        self.input_mayor_que.setPlaceholderText("Edad")
        self.input_mayor_que.setMaximumWidth(60)
        self.input_mayor_que.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #d0d0d0;
                border-radius: 5px;
                font-size: 13px;
                color: #1a1a1a;
                background-color: #f5f5f5;
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
        
        # Ajustar columnas para que ocupen todo el espacio
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(self.tabla)
        
        self.setLayout(layout)
    
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

            btn_eliminar = crear_boton_icono("delete.svg", "#e74c3c", "#c0392b", "Eliminar")
            btn_eliminar.clicked.connect(lambda checked, cid=cliente['id']: self.eliminar_cliente(cid))
            acciones_layout.addWidget(btn_eliminar)

            self.tabla.setCellWidget(i, 5, acciones_widget)

        self.tabla.setSortingEnabled(sorting_enabled)
    
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
