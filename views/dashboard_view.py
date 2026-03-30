"""Vista del Dashboard con métricas, filtros por fecha, reloj y exportar PDF"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
                               QLineEdit, QPushButton, QDateEdit, QMessageBox,
                               QFileDialog)
from PySide6.QtCore import Qt, QTimer, QRect, QDate, QThread, Signal
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QPixmap
from services import membresia_service, pago_service, cliente_service
from utils.constants import ESTADO_ACTIVA, ESTADO_POR_VENCER, ESTADO_VENCIDA
from utils.table_styles import aplicar_estilo_tabla_moderna
from datetime import date, datetime
import math, tempfile, os
from services.inventario_service import obtener_stock_bajo


class SyncWorker(QThread):
    """Hilo que ejecuta la sincronización con Google Drive sin bloquear la UI"""
    terminado = Signal(bool, str)  # (exito, mensaje)

    def run(self):
        try:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from sync_onedrive_personal import OneDriveSyncPersonal
            syncer = OneDriveSyncPersonal()
            ok = syncer.sync()
            if ok:
                self.terminado.emit(True, "✅ Excel sincronizado con Google Drive correctamente.")
            else:
                self.terminado.emit(False, "❌ No se pudo sincronizar. Revisa la consola para más detalles.")
        except Exception as e:
            self.terminado.emit(False, f"❌ Error: {str(e)}")


# ---------- TARJETA ESTADÍSTICA MODERNA ----------
class StatCard(QFrame):
    """Tarjeta moderna para mostrar estadísticas"""
    def __init__(self, title, value, color, icon, extra_info=""):
        super().__init__()
        
        self.setFixedHeight(130)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #f5f5f5;
                border-radius: 8px;
                border: 1px solid #d8d8d8;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Icono en círculo a la izquierda
        icon_label = QLabel(icon)
        icon_label.setFixedSize(50, 50)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 25px;
                font-size: 24px;
                border: none;
            }}
        """)
        layout.addWidget(icon_label)
        
        # Contenedor de texto a la derecha
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        # Título
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666666; font-size: 14px; font-weight: normal; border: none; background-color: transparent;")
        
        # Valor
        value_label = QLabel(str(value))
        value_label.setStyleSheet(f"""
            color: #1a1a1a;
            font-size: 36px;
            font-weight: bold;
            border: none;
            background-color: transparent;
        """)
        
        # Información extra
        extra_label = QLabel(extra_info)
        extra_label.setStyleSheet("color: #666666; font-size: 12px; border: none; background-color: transparent;")
        extra_label.setWordWrap(True)
        
        text_layout.addWidget(title_label)
        text_layout.addWidget(value_label)
        if extra_info:
            text_layout.addWidget(extra_label)
        text_layout.addStretch()
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        self.label_valor = value_label
        self.label_extra = extra_label
        self.color = color
    
    def actualizar_valor(self, nuevo_valor, extra_info=""):
        """Actualiza el valor y la información extra"""
        self.label_valor.setText(str(nuevo_valor))
        self.label_extra.setText(extra_info)



class SimpleBarChart(QWidget):
    """Gráfico de barras simple"""
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(200)
        self.setMinimumWidth(300)
        self.datos = [15, 18, 22, 28, 20, 23, 25]
        self.labels = ["E", "F", "M", "A", "M", "J", "J"]
    
    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(500, 250)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Configuración
        width = self.width()
        height = self.height()
        margin = 40
        bar_width = (width - 2 * margin) / len(self.datos)
        max_value = max(self.datos)
        
        # Dibujar barras
        for i, value in enumerate(self.datos):
            x = margin + i * bar_width + bar_width * 0.2
            bar_height = (value / max_value) * (height - 2 * margin)
            y = height - margin - bar_height
            
            painter.fillRect(int(x), int(y), int(bar_width * 0.6), int(bar_height), QColor("#555555"))
            
            # Etiqueta del mes
            painter.setPen(QColor("#666666"))
            painter.drawText(int(x), height - margin + 20, int(bar_width * 0.6), 20,
                           Qt.AlignCenter, self.labels[i])


class SimplePieChart(QWidget):
    """Gráfico de torta simple"""
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(200)
        self.setMinimumWidth(200)
        self.setStyleSheet("background-color: #f5f5f5;")
        self.datos = [
            ("Activa", 0, QColor("#4CAF50")),
            ("Por Vencer", 0, QColor("#FF9800")),
            ("Vencida", 0, QColor("#F44336"))
        ]
        self.setMouseTracking(True)
        self.sector_bajo_cursor = None
        self.size_increment_actual = 0.0  # Tamaño actual de agrandamiento (animado)
        self.size_increment_objetivo = 0.0  # Tamaño objetivo
        
        # Timer para animación suave
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.animate_size)
        self.animation_timer.start(16)  # ~60 FPS
    
    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(300, 250)
    
    def actualizar_datos(self, activas, por_vencer, vencidas):
        """Actualiza los datos del gráfico"""
        self.datos = [
            ("Activa", activas, QColor("#4CAF50")),
            ("Por Vencer", por_vencer, QColor("#FF9800")),
            ("Vencida", vencidas, QColor("#F44336"))
        ]
        self.update()  # Repintar el widget
    
    def animate_size(self):
        """Anima suavemente el cambio de tamaño"""
        # Interpolación suave hacia el objetivo
        diferencia = self.size_increment_objetivo - self.size_increment_actual
        if abs(diferencia) > 0.1:
            self.size_increment_actual += diferencia * 0.2  # 20% de la diferencia cada frame
            self.update()
        elif abs(diferencia) > 0.01:
            self.size_increment_actual = self.size_increment_objetivo
            self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Configuración
        width = self.width()
        height = self.height()
        size = min(width, height) - 80
        x = (width - size) / 2
        y = 20
        
        # Calcular total
        total = sum(d[1] for d in self.datos)
        
        # Si no hay datos, mostrar círculo gris
        if total == 0:
            painter.setBrush(QBrush(QColor("#e0e0e0")))
            painter.setPen(QPen(QColor("#f0f0f0"), 2))
            painter.drawEllipse(int(x), int(y), int(size), int(size))
        else:
            # Dibujar sectores normales primero
            start_angle = 90 * 16  # Empezar desde arriba (12 en punto)
            for i, (label, value, color) in enumerate(self.datos):
                if value > 0:
                    span_angle = int((value / total) * 360 * 16)
                    
                    # Dibujar todos los sectores con tamaño normal
                    if i != self.sector_bajo_cursor:
                        painter.setBrush(QBrush(color))
                        painter.setPen(QPen(QColor("#f0f0f0"), 2))
                        painter.drawPie(int(x), int(y), int(size), int(size), start_angle, span_angle)
                    
                    start_angle += span_angle
            
            # Dibujar el sector seleccionado encima con mayor tamaño
            if self.sector_bajo_cursor is not None and self.size_increment_actual > 0.1:
                start_angle = 90 * 16
                for i, (label, value, color) in enumerate(self.datos):
                    if value > 0:
                        span_angle = int((value / total) * 360 * 16)
                        
                        if i == self.sector_bajo_cursor:
                            # Hacer el sector más grande con el tamaño actual de la animación
                            larger_size = size + self.size_increment_actual
                            larger_x = x - self.size_increment_actual / 2
                            larger_y = y - self.size_increment_actual / 2
                            
                            painter.setBrush(QBrush(color))
                            painter.setPen(QPen(QColor("#f0f0f0"), 3))  # Borde más grueso
                            painter.drawPie(int(larger_x), int(larger_y), int(larger_size), int(larger_size), start_angle, span_angle)
                            break
                        
                        start_angle += span_angle
        
        # Leyenda en horizontal
        legend_y = y + size + 20
        painter.setFont(QFont("Arial", 10))
        metrics = painter.fontMetrics()

        textos_leyenda = [f"{label}  {value}" for label, value, _ in self.datos]
        anchos_items = [15 + 6 + metrics.horizontalAdvance(texto) for texto in textos_leyenda]
        separacion = 20
        ancho_total = sum(anchos_items) + separacion * max(0, len(anchos_items) - 1)
        legend_x = max(20, int((width - ancho_total) / 2))

        for i, (label, value, color) in enumerate(self.datos):
            texto = f"{label}  {value}"

            # Cuadrado de color
            painter.fillRect(int(legend_x), int(legend_y), 15, 15, color)

            # Texto leyenda (claro sobre fondo oscuro)
            painter.setPen(QColor("#333333"))
            painter.drawText(int(legend_x + 21), int(legend_y + 12), texto)

            legend_x += anchos_items[i] + separacion
        
        # Tooltip sobre el sector
        if self.sector_bajo_cursor is not None and total > 0:
            label, value, color = self.datos[self.sector_bajo_cursor]
            porcentaje = (value / total * 100)
            
            # Fondo del tooltip
            tooltip_text = f"{label}: {porcentaje:.1f}%"
            font = QFont("Arial", 10, QFont.Bold)
            painter.setFont(font)
            
            # Calcular tamaño del texto
            from PySide6.QtGui import QFontMetrics
            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(tooltip_text)
            text_height = metrics.height()
            
            # Posición del tooltip (centro del gráfico)
            tooltip_x = int(width / 2 - text_width / 2 - 10)
            tooltip_y = int(y + size / 2 - text_height / 2 - 5)
            
            # Dibujar fondo del tooltip
            painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
            painter.setPen(QPen(Qt.NoPen))
            painter.drawRoundedRect(tooltip_x, tooltip_y, text_width + 20, text_height + 10, 5, 5)
            
            # Dibujar texto del tooltip
            painter.setPen(QColor("#ffffff"))
            painter.drawText(tooltip_x + 10, tooltip_y + text_height, tooltip_text)


    def mouseMoveEvent(self, event):
        """Detecta sobre qué sector está el mouse"""
        width = self.width()
        height = self.height()
        size = min(width, height) - 80
        center_x = width / 2
        center_y = 20 + size / 2
        
        # Posición del mouse
        mouse_x = event.pos().x()
        mouse_y = event.pos().y()
        
        # Calcular distancia del centro
        dx = mouse_x - center_x
        dy = mouse_y - center_y
        distance = math.sqrt(dx * dx + dy * dy)
        
        # Si está dentro del círculo
        if distance <= size / 2:
            # Calcular ángulo en grados
            # atan2 devuelve el ángulo desde el eje X positivo (3 en punto)
            # Convertimos para que 0° esté arriba (12 en punto) y vaya en sentido horario
            angle = math.atan2(dy, dx) * 180 / math.pi
            # Ajustar para que 0° esté arriba (12 en punto)
            angle = (angle - 90 + 360) % 360
            
            # Determinar en qué sector está
            total = sum(d[1] for d in self.datos)
            if total > 0:
                current_angle = 0
                for i, (label, value, color) in enumerate(self.datos):
                    if value > 0:
                        sector_angle = (value / total) * 360
                        if current_angle <= angle < current_angle + sector_angle:
                            if self.sector_bajo_cursor != i:
                                self.sector_bajo_cursor = i
                                self.size_increment_objetivo = 15.0  # Tamaño objetivo cuando hay hover
                                self.update()
                            return
                        current_angle += sector_angle
        
        # Si no está sobre ningún sector
        if self.sector_bajo_cursor is not None:
            self.sector_bajo_cursor = None
            self.size_increment_objetivo = 0.0  # Volver al tamaño normal
            self.update()
    
    def leaveEvent(self, event):
        """Limpia el tooltip cuando el mouse sale del widget"""
        if self.sector_bajo_cursor is not None:
            self.sector_bajo_cursor = None
            self.size_increment_objetivo = 0.0  # Volver al tamaño normal
            self.update()


class DashboardView(QWidget):
    """Vista principal del Dashboard"""
    def __init__(self):
        super().__init__()
        # Estado de filtros
        self.filtro_estado_membresia = None  # None = Todas
        self.filtro_fecha_desde = None
        self.filtro_fecha_hasta = None
        self._membresias_mostradas = []
        self._pagos_mostrados = []
        
        self.init_ui()
        self.cargar_datos()
        
        # Timer de datos cada 30 segundos
        self.timer = QTimer()
        self.timer.timeout.connect(self.cargar_datos)
        self.timer.start(30000)
        
        # Timer del reloj cada segundo
        self.timer_reloj = QTimer()
        self.timer_reloj.timeout.connect(self.actualizar_reloj)
        self.timer_reloj.start(1000)
    
    def init_ui(self):
        """Inicializa la interfaz de usuario"""
        # Estilos generales
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f8f8;
                font-family: Arial, sans-serif;
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
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header con título y búsqueda
        header_layout = QHBoxLayout()
        
        titulo = QLabel("Dashboard")
        titulo.setFont(QFont("Arial", 24, QFont.Bold))
        titulo.setStyleSheet("color: #1a1a1a; background-color: transparent;")
        header_layout.addWidget(titulo)
        
        header_layout.addStretch()
        
        # Reloj del sistema
        self.label_reloj = QLabel()
        self.label_reloj.setFont(QFont("Arial", 14))
        self.label_reloj.setStyleSheet("color: #555555; background-color: transparent;")
        self.actualizar_reloj()
        header_layout.addWidget(self.label_reloj)
        
        header_layout.addSpacing(15)
        
        # Botón exportar PDF
        btn_exportar_pdf = QPushButton("📄 Exportar PDF")
        btn_exportar_pdf.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad;
                color: white;
                padding: 8px 18px;
                border: none;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7d3c98;
                color: white;
            }
        """)
        btn_exportar_pdf.clicked.connect(self.exportar_dashboard_pdf)
        header_layout.addWidget(btn_exportar_pdf)

        header_layout.addSpacing(8)

        # Botón sincronizar Google Drive
        self.btn_sync = QPushButton("☁️ Sincronizar Drive")
        self.btn_sync.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 8px 18px;
                border: none;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #219a52;
                color: white;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: white;
            }
        """)
        self.btn_sync.clicked.connect(self.sincronizar_google_drive)
        header_layout.addWidget(self.btn_sync)
        
        layout.addLayout(header_layout)
        
        # ========== BARRA DE FILTROS POR FECHA ==========
        filtros_fecha_frame = QFrame()
        filtros_fecha_frame.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-radius: 8px;
                border: 1px solid #d8d8d8;
            }
        """)
        filtros_fecha_layout = QHBoxLayout(filtros_fecha_frame)
        filtros_fecha_layout.setContentsMargins(15, 10, 15, 10)
        filtros_fecha_layout.setSpacing(10)
        
        label_filtros = QLabel("📅 Filtrar por fecha:")
        label_filtros.setStyleSheet("color: #555555; font-weight: bold; font-size: 13px; border: none;")
        filtros_fecha_layout.addWidget(label_filtros)
        
        estilo_date = """
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
        
        label_desde = QLabel("Desde:")
        label_desde.setStyleSheet("color: #666666; font-size: 12px; border: none;")
        filtros_fecha_layout.addWidget(label_desde)
        
        self.date_desde = QDateEdit()
        self.date_desde.setCalendarPopup(True)
        self.date_desde.setDate(QDate(date.today().year, date.today().month, 1))
        self.date_desde.setDisplayFormat("dd/MM/yyyy")
        self.date_desde.setStyleSheet(estilo_date)
        filtros_fecha_layout.addWidget(self.date_desde)
        
        label_hasta = QLabel("Hasta:")
        label_hasta.setStyleSheet("color: #666666; font-size: 12px; border: none;")
        filtros_fecha_layout.addWidget(label_hasta)
        
        self.date_hasta = QDateEdit()
        self.date_hasta.setCalendarPopup(True)
        self.date_hasta.setDate(QDate.currentDate())
        self.date_hasta.setDisplayFormat("dd/MM/yyyy")
        self.date_hasta.setStyleSheet(estilo_date)
        filtros_fecha_layout.addWidget(self.date_hasta)
        
        btn_aplicar_fecha = QPushButton("Aplicar")
        btn_aplicar_fecha.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                padding: 6px 16px; border: none; border-radius: 4px;
                font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #2980b9; color: white; }
        """)
        btn_aplicar_fecha.clicked.connect(self.aplicar_filtro_fecha)
        filtros_fecha_layout.addWidget(btn_aplicar_fecha)
        
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
        
        # Etiqueta de filtros activos
        self.label_filtros_activos = QLabel("")
        self.label_filtros_activos.setStyleSheet("color: #555555; font-size: 11px; font-style: italic; border: none;")
        filtros_fecha_layout.addWidget(self.label_filtros_activos)
        
        filtros_fecha_layout.addStretch()
        
        layout.addWidget(filtros_fecha_frame)
        
        # Contenedor de métricas
        metricas_layout = QHBoxLayout()
        metricas_layout.setSpacing(15)
        
        self.card_activas = StatCard("Activas", "0", "#27ae60", "✅")
        self.card_por_vencer = StatCard("Por vencer", "0", "#f39c12", "⏰")
        self.card_vencidas = StatCard("Vencidas", "0", "#e74c3c", "❌")
        self.card_pagos_mes = StatCard("Ingresos", "$0", "#3498db", "💵")
        self.card_stock_bajo = StatCard("Stock bajo", "0", "#e67e22", "⚠️")

        
        metricas_layout.addWidget(self.card_activas)
        metricas_layout.addWidget(self.card_por_vencer)
        metricas_layout.addWidget(self.card_vencidas)
        metricas_layout.addWidget(self.card_pagos_mes)
        metricas_layout.addWidget(self.card_stock_bajo)

        
        layout.addLayout(metricas_layout)
        
        # Contenedor de gráficos
        graficos_layout = QHBoxLayout()
        graficos_layout.setSpacing(15)
        
        # Gráfico de torta (membresías por estado)
        frame_torta_membresias = QFrame()
        frame_torta_membresias.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-radius: 8px;
                border: 1px solid #d8d8d8;
            }
        """)
        layout_torta_membresias = QVBoxLayout(frame_torta_membresias)
        layout_torta_membresias.setContentsMargins(15, 15, 15, 15)
        
        # Título del gráfico
        titulo_torta_membresias = QLabel("Membresías")
        titulo_torta_membresias.setFont(QFont("Arial", 14, QFont.Bold))
        titulo_torta_membresias.setStyleSheet("color: #1a1a1a; padding: 5px;")
        layout_torta_membresias.addWidget(titulo_torta_membresias)
        
        self.chart_torta = SimplePieChart()
        layout_torta_membresias.addWidget(self.chart_torta)
        
        graficos_layout.addWidget(frame_torta_membresias, 1)
        
        # Gráfico de torta (clientes por sexo)
        frame_torta_sexo = QFrame()
        frame_torta_sexo.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-radius: 8px;
                border: 1px solid #d8d8d8;
            }
        """)
        layout_torta_sexo = QVBoxLayout(frame_torta_sexo)
        layout_torta_sexo.setContentsMargins(15, 15, 15, 15)
        
        # Título del gráfico
        titulo_torta_sexo = QLabel("Clientes por sexo")
        titulo_torta_sexo.setFont(QFont("Arial", 14, QFont.Bold))
        titulo_torta_sexo.setStyleSheet("color: #1a1a1a; padding: 5px;")
        layout_torta_sexo.addWidget(titulo_torta_sexo)
        
        self.chart_torta_sexo = SimplePieChart()
        layout_torta_sexo.addWidget(self.chart_torta_sexo)

        self.lbl_total_clientes_sexo = QLabel("Total clientes: 0")
        self.lbl_total_clientes_sexo.setFont(QFont("Arial", 13, QFont.Bold))
        self.lbl_total_clientes_sexo.setStyleSheet("color:#2c6fad; padding:4px 0; background:transparent;")
        self.lbl_total_clientes_sexo.setAlignment(Qt.AlignCenter)
        layout_torta_sexo.addWidget(self.lbl_total_clientes_sexo)

        graficos_layout.addWidget(frame_torta_sexo, 1)
        
        layout.addLayout(graficos_layout)
        
        # Contenedor de tablas
        tablas_layout = QHBoxLayout()
        tablas_layout.setSpacing(15)
        
        # Tabla de membresías
        frame_membresias = QFrame()
        frame_membresias.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-radius: 8px;
                border: 1px solid #d8d8d8;
            }
        """)
        layout_membresias = QVBoxLayout(frame_membresias)
        layout_membresias.setContentsMargins(15, 15, 15, 15)
        
        label_membresias = QLabel("Membresías")
        label_membresias.setFont(QFont("Arial", 14, QFont.Bold))
        label_membresias.setStyleSheet("color: #1a1a1a;")
        layout_membresias.addWidget(label_membresias)
        
        # Filtros de membresías
        filtros_layout = QHBoxLayout()
        
        # Estilos para botones de filtro
        estilo_botones = """
            QPushButton {
                background-color: transparent;
                color: #666666;
                padding: 6px 14px;
                border: none;
                border-bottom: 2px solid transparent;
                border-radius: 0px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #eeeeee;
                color: #555555;
            }
            QPushButton:checked {
                background-color: transparent;
                color: #555555;
                border-bottom: 2px solid #c0c0c0;
            }
        """
        
        self.btn_filtro_todas = QPushButton("Todas")
        self.btn_filtro_activas = QPushButton("Activas")
        self.btn_filtro_por_vencer = QPushButton("Por Vencer")
        self.btn_filtro_vencidas = QPushButton("Vencidas")
        
        self.btn_filtro_todas.setCheckable(True)
        self.btn_filtro_activas.setCheckable(True)
        self.btn_filtro_por_vencer.setCheckable(True)
        self.btn_filtro_vencidas.setCheckable(True)
        
        self.btn_filtro_todas.setChecked(True)
        
        self.btn_filtro_todas.clicked.connect(lambda: self.filtrar_membresias(None, self.btn_filtro_todas))
        self.btn_filtro_activas.clicked.connect(lambda: self.filtrar_membresias(ESTADO_ACTIVA, self.btn_filtro_activas))
        self.btn_filtro_por_vencer.clicked.connect(lambda: self.filtrar_membresias(ESTADO_POR_VENCER, self.btn_filtro_por_vencer))
        self.btn_filtro_vencidas.clicked.connect(lambda: self.filtrar_membresias(ESTADO_VENCIDA, self.btn_filtro_vencidas))
        
        for btn in [self.btn_filtro_todas, self.btn_filtro_activas, self.btn_filtro_por_vencer, self.btn_filtro_vencidas]:
            btn.setStyleSheet(estilo_botones)
            filtros_layout.addWidget(btn)
        
        filtros_layout.addStretch()
        layout_membresias.addLayout(filtros_layout)
        
        self.tabla_membresias = QTableWidget()
        self.tabla_membresias.setColumnCount(4)
        self.tabla_membresias.setHorizontalHeaderLabels(["Cliente", "Inicio", "Vencimiento", "Estado"])
        self.tabla_membresias.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_membresias.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_membresias.setSelectionMode(QTableWidget.NoSelection)
        self.tabla_membresias.verticalHeader().setVisible(False)
        self.tabla_membresias.setMinimumHeight(150)
        aplicar_estilo_tabla_moderna(self.tabla_membresias, compacta=True, embebida=True)
        layout_membresias.addWidget(self.tabla_membresias)
        
        tablas_layout.addWidget(frame_membresias, 3)
        
        # Tabla de últimos pagos
        frame_pagos = QFrame()
        frame_pagos.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-radius: 8px;
                border: 1px solid #d8d8d8;
            }
        """)
        layout_pagos = QVBoxLayout(frame_pagos)
        layout_pagos.setContentsMargins(15, 15, 15, 15)
        
        label_pagos = QLabel("Últimos Pagos")
        label_pagos.setFont(QFont("Arial", 14, QFont.Bold))
        label_pagos.setStyleSheet("color: #1a1a1a;")
        layout_pagos.addWidget(label_pagos)
        
        self.tabla_pagos = QTableWidget()
        self.tabla_pagos.setColumnCount(4)
        self.tabla_pagos.setHorizontalHeaderLabels(["Cliente", "Fecha", "Monto", "Método"])
        self.tabla_pagos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_pagos.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_pagos.setSelectionMode(QTableWidget.NoSelection)
        self.tabla_pagos.verticalHeader().setVisible(False)
        self.tabla_pagos.setMinimumHeight(150)
        aplicar_estilo_tabla_moderna(self.tabla_pagos, compacta=True, embebida=True)
        layout_pagos.addWidget(self.tabla_pagos)
        
        tablas_layout.addWidget(frame_pagos, 2)
        
        layout.addLayout(tablas_layout)
        
        self.setLayout(layout)
    
    def actualizar_reloj(self):
        """Actualiza el reloj del sistema cada segundo"""
        ahora = datetime.now()
        # Evitar pasar caracteres Unicode no-ASCII a strftime (puede fallar en algunas locales)
        time_str = ahora.strftime("%d/%m/%Y  %H:%M:%S")
        self.label_reloj.setText("🕐 " + time_str)

    def sincronizar_google_drive(self):
        """Lanza la sincronización en un hilo separado"""
        self.btn_sync.setEnabled(False)
        self.btn_sync.setText("⏳ Sincronizando...")

        self.sync_worker = SyncWorker()
        self.sync_worker.terminado.connect(self._on_sync_terminado)
        self.sync_worker.start()

    def _on_sync_terminado(self, exito, mensaje):
        """Se ejecuta cuando termina la sincronización"""
        self.btn_sync.setEnabled(True)
        self.btn_sync.setText("☁️ Sincronizar Drive")
        if exito:
            QMessageBox.information(self, "Sincronización", mensaje)
        else:
            QMessageBox.warning(self, "Error de sincronización", mensaje)
    
    def aplicar_filtro_fecha(self):
        """Aplica el filtro de fecha seleccionado"""
        qd_desde = self.date_desde.date()
        qd_hasta = self.date_hasta.date()
        self.filtro_fecha_desde = date(qd_desde.year(), qd_desde.month(), qd_desde.day())
        self.filtro_fecha_hasta = date(qd_hasta.year(), qd_hasta.month(), qd_hasta.day())
        
        if self.filtro_fecha_desde > self.filtro_fecha_hasta:
            QMessageBox.warning(self, "Error", "La fecha 'Desde' no puede ser mayor que 'Hasta'.")
            return
        
        self.actualizar_label_filtros()
        self.cargar_datos()
    
    def limpiar_filtro_fecha(self):
        """Limpia el filtro de fecha"""
        self.filtro_fecha_desde = None
        self.filtro_fecha_hasta = None
        self.date_desde.setDate(QDate(date.today().year, date.today().month, 1))
        self.date_hasta.setDate(QDate.currentDate())
        self.label_filtros_activos.setText("")
        self.cargar_datos()
    
    def actualizar_label_filtros(self):
        """Actualiza la etiqueta que muestra los filtros activos"""
        partes = []
        if self.filtro_fecha_desde and self.filtro_fecha_hasta:
            partes.append(f"Fecha: {self.filtro_fecha_desde.strftime('%d/%m/%Y')} - {self.filtro_fecha_hasta.strftime('%d/%m/%Y')}")
        if self.filtro_estado_membresia:
            partes.append(f"Estado: {self.filtro_estado_membresia}")
        if partes:
            self.label_filtros_activos.setText("Filtros: " + " | ".join(partes))
        else:
            self.label_filtros_activos.setText("")
    
    def obtener_texto_filtros_activos(self):
        """Devuelve texto descriptivo de los filtros activos para el PDF"""
        partes = []
        if self.filtro_fecha_desde and self.filtro_fecha_hasta:
            partes.append(f"Rango de fecha: {self.filtro_fecha_desde.strftime('%d/%m/%Y')} al {self.filtro_fecha_hasta.strftime('%d/%m/%Y')}")
        else:
            partes.append("Rango de fecha: Todos")
        if self.filtro_estado_membresia:
            partes.append(f"Estado membresía: {self.filtro_estado_membresia}")
        else:
            partes.append("Estado membresía: Todas")
        return partes
    
    def cargar_datos(self):
        """Carga los datos del dashboard respetando filtros"""
        # Si hay filtro de fecha, recalcular conteo de membresías filtrado
        if self.filtro_fecha_desde and self.filtro_fecha_hasta:
            todas = membresia_service.listar_membresias()
            filtradas = [
                m for m in todas
                if date.fromisoformat(m['fecha_inicio']) <= self.filtro_fecha_hasta
                and date.fromisoformat(m['fecha_vencimiento']) >= self.filtro_fecha_desde
            ]
            conteo = {ESTADO_ACTIVA: 0, ESTADO_POR_VENCER: 0, ESTADO_VENCIDA: 0}
            for m in filtradas:
                est = m['estado']
                if est in conteo:
                    conteo[est] += 1
        else:
            conteo = membresia_service.contar_membresias_por_estado()
        
        # Actualizar cards
        self.card_activas.actualizar_valor(conteo[ESTADO_ACTIVA])
        self.card_por_vencer.actualizar_valor(conteo[ESTADO_POR_VENCER])
        self.card_vencidas.actualizar_valor(conteo[ESTADO_VENCIDA])
        
        # Actualizar gráfico de torta con datos (filtrados o no)
        self.chart_torta.actualizar_datos(
            conteo[ESTADO_ACTIVA],
            conteo[ESTADO_POR_VENCER],
            conteo[ESTADO_VENCIDA]
        )
        
        # Actualizar gráfico de sexo
        conteo_sexo = cliente_service.contar_clientes_por_sexo()
        self.chart_torta_sexo.datos = [
            ("Masculino", conteo_sexo['Masculino'], QColor("#3498db")),
            ("Femenino", conteo_sexo['Femenino'], QColor("#e91e63")),
            ("Otro", conteo_sexo['Otro'], QColor("#9b59b6"))
        ]
        self.chart_torta_sexo.update()
        total_clientes = sum(conteo_sexo.values())
        self.lbl_total_clientes_sexo.setText(f"Total clientes: {total_clientes}")

        # Pagos: si hay filtro de fecha, calcular con ese rango
        if self.filtro_fecha_desde and self.filtro_fecha_hasta:
            pagos_filtrados = pago_service.listar_pagos(
                fecha_desde=self.filtro_fecha_desde,
                fecha_hasta=self.filtro_fecha_hasta,
                limite=1000
            )
            total_ingresos = sum(p['monto'] for p in pagos_filtrados)
            self.card_pagos_mes.actualizar_valor(
                f"${total_ingresos:,.0f}",
                f"📈 {self.filtro_fecha_desde.strftime('%d/%m')} - {self.filtro_fecha_hasta.strftime('%d/%m')}"
            )
        else:
            total_mes = pago_service.calcular_total_mes()
            self.card_pagos_mes.actualizar_valor(f"${total_mes:,.0f}", "📈 Este mes")

        # Stock bajo
        productos_bajo = obtener_stock_bajo()
        cantidad_bajo = len(productos_bajo)
        nombres_bajo = [p["nombre"] for p in productos_bajo]
        if nombres_bajo:
            resumen_nombres = ", ".join(nombres_bajo[:3])
            if len(nombres_bajo) > 3:
                resumen_nombres += "..."
            extra_stock = f"⚙️ {cantidad_bajo} productos: {resumen_nombres}"
        else:
            extra_stock = "⚙️ Sin productos con stock bajo"
        self.card_stock_bajo.actualizar_valor(cantidad_bajo, extra_stock)

        
        # Cargar tablas
        self.cargar_tabla_membresias(self.filtro_estado_membresia)
        self.cargar_tabla_pagos()
    
    def filtrar_membresias(self, estado, boton_activo):
        """Filtra las membresías por estado"""
        # Desmarcar todos los botones
        self.btn_filtro_todas.setChecked(False)
        self.btn_filtro_activas.setChecked(False)
        self.btn_filtro_por_vencer.setChecked(False)
        self.btn_filtro_vencidas.setChecked(False)
        
        # Marcar el botón activo
        boton_activo.setChecked(True)
        
        # Guardar estado del filtro
        self.filtro_estado_membresia = estado
        self.actualizar_label_filtros()
        
        # Cargar tabla con filtro
        self.cargar_tabla_membresias(estado)
    
    def cargar_tabla_membresias(self, filtro_estado=None):
        """Carga la tabla de membresías con filtros de estado y fecha"""
        if filtro_estado:
            membresias = [m for m in membresia_service.listar_membresias() if m['estado'] == filtro_estado]
        else:
            membresias = membresia_service.listar_membresias()
        
        # Filtrar por rango de fecha: membresia activa en algun momento del rango
        if self.filtro_fecha_desde and self.filtro_fecha_hasta:
            membresias = [
                m for m in membresias
                if date.fromisoformat(m['fecha_inicio']) <= self.filtro_fecha_hasta
                and date.fromisoformat(m['fecha_vencimiento']) >= self.filtro_fecha_desde
            ]
        
        # Guardar para export PDF
        self._membresias_mostradas = membresias[:10]
        
        membresias = membresias[:10]
        
        self.tabla_membresias.setRowCount(len(membresias))
        
        for i, membresia in enumerate(membresias):
            # Cliente - color oscuro
            cliente_item = QTableWidgetItem(membresia['cliente_nombre'])
            cliente_item.setForeground(QColor("#2c3e50"))
            self.tabla_membresias.setItem(i, 0, cliente_item)
            
            # Inicio - color oscuro
            inicio_item = QTableWidgetItem(membresia['fecha_inicio'])
            inicio_item.setForeground(QColor("#2c3e50"))
            self.tabla_membresias.setItem(i, 1, inicio_item)
            
            # Vencimiento - color oscuro
            vencimiento_item = QTableWidgetItem(membresia['fecha_vencimiento'])
            vencimiento_item.setForeground(QColor("#2c3e50"))
            self.tabla_membresias.setItem(i, 2, vencimiento_item)
            
            # Estado con color
            estado = membresia['estado']
            estado_item = QTableWidgetItem(estado)
            
            if estado == ESTADO_ACTIVA:
                estado_item.setForeground(QColor("#27ae60"))
            elif estado == ESTADO_POR_VENCER:
                estado_item.setForeground(QColor("#f39c12"))
            elif estado == ESTADO_VENCIDA:
                estado_item.setForeground(QColor("#e74c3c"))
            
            self.tabla_membresias.setItem(i, 3, estado_item)
    
    def cargar_tabla_pagos(self):
        """Carga la tabla de últimos pagos con filtro de fecha"""
        if self.filtro_fecha_desde and self.filtro_fecha_hasta:
            pagos = pago_service.listar_pagos(
                fecha_desde=self.filtro_fecha_desde,
                fecha_hasta=self.filtro_fecha_hasta,
                limite=10
            )
        else:
            pagos = pago_service.obtener_ultimos_pagos(limite=10)
        
        # Guardar para export PDF
        self._pagos_mostrados = pagos
        
        self.tabla_pagos.setRowCount(len(pagos))
        
        for i, pago in enumerate(pagos):
            # Cliente - color oscuro
            cliente_item = QTableWidgetItem(pago['cliente_nombre'])
            cliente_item.setForeground(QColor("#2c3e50"))
            self.tabla_pagos.setItem(i, 0, cliente_item)
            
            # Fecha - color oscuro
            fecha_item = QTableWidgetItem(pago['fecha'])
            fecha_item.setForeground(QColor("#2c3e50"))
            self.tabla_pagos.setItem(i, 1, fecha_item)
            
            # Monto - color oscuro
            monto_item = QTableWidgetItem(f"${pago['monto']:,.2f}")
            monto_item.setForeground(QColor("#2c3e50"))
            self.tabla_pagos.setItem(i, 2, monto_item)
            
            # Método - color oscuro
            metodo_item = QTableWidgetItem(pago['metodo'])
            metodo_item.setForeground(QColor("#2c3e50"))
            self.tabla_pagos.setItem(i, 3, metodo_item)
    
    # ==================== EXPORTAR PDF ====================
    def exportar_dashboard_pdf(self):
        """Exporta los datos visibles del dashboard a un PDF"""
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar Reporte PDF", 
            f"Dashboard_KyoGym_{date.today().isoformat()}.pdf",
            "PDF (*.pdf)"
        )
        if not ruta:
            return
        
        try:
            self._generar_pdf_dashboard(ruta)
            msg = QMessageBox(self)
            msg.setWindowTitle("Éxito")
            msg.setText("Reporte PDF exportado correctamente.")
            msg.setStyleSheet("""
                QMessageBox { background-color: white; }
                QLabel { color: black; font-size: 13px; min-width: 300px; }
                QPushButton { background-color: #27ae60; color: white; padding: 8px 20px; border: none; border-radius: 4px; font-weight: bold; font-size: 13px; min-width: 80px; }
                QPushButton:hover { background-color: #229954; }
            """)
            btn_abrir = msg.addButton("Abrir PDF", QMessageBox.ActionRole)
            msg.addButton("Cerrar", QMessageBox.RejectRole)
            msg.exec()
            if msg.clickedButton() == btn_abrir:
                from utils.factura_generator import abrir_factura
                abrir_factura(ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo generar el PDF:\n{str(e)}")
    
    def _capturar_widget_como_imagen(self, widget, ancho_px=400, alto_px=300):
        """Captura un widget como imagen PNG temporal sin alterar su geometría"""
        # Guardar tamaño original antes de redimensionar
        size_original = widget.size()
        
        # Redimensionar a la resolución deseada antes de capturar
        widget.resize(ancho_px, alto_px)
        widget.repaint()
        # grab() captura el widget pintado tal como está (API correcta de PySide6)
        pixmap = widget.grab()
        if pixmap.isNull():
            # Fallback: renderizar manualmente al QPixmap (QPaintDevice, no QPainter)
            pixmap = QPixmap(ancho_px, alto_px)
            pixmap.fill(QColor("white"))
            from PySide6.QtCore import QPoint, QRect as _QRect
            widget.render(pixmap, QPoint(0, 0))
        
        # Restaurar tamaño original para no alterar el layout de la UI
        widget.resize(size_original)
        widget.repaint()
        
        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        pixmap.save(tmp.name, 'PNG')
        tmp.close()
        return tmp.name
    
    def _generar_pdf_dashboard(self, ruta):
        """Genera el PDF del dashboard con datos, gráficos y filtros activos"""
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas as pdf_canvas
        
        # Capturar gráficos como imágenes antes de generar el PDF
        img_torta_membresias = self._capturar_widget_como_imagen(self.chart_torta, 350, 280)
        img_torta_sexo = self._capturar_widget_como_imagen(self.chart_torta_sexo, 350, 280)
        
        try:
            c = pdf_canvas.Canvas(ruta, pagesize=letter)
            ancho, alto = letter
            y = alto - 40
            
            # Título
            c.setFont("Helvetica-Bold", 20)
            c.drawString(40, y, "Reporte Dashboard - KyoGym")
            y -= 25
            
            # Fecha y hora de generación
            c.setFont("Helvetica", 10)
            c.drawString(40, y, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            y -= 20
            
            # Filtros activos
            filtros = self.obtener_texto_filtros_activos()
            c.setFont("Helvetica-Bold", 11)
            c.drawString(40, y, "Filtros aplicados:")
            y -= 15
            c.setFont("Helvetica", 10)
            for filtro in filtros:
                c.drawString(55, y, f"- {filtro}")
                y -= 14
            y -= 10
            
            # Línea separadora
            c.setStrokeColorRGB(0.8, 0.8, 0.8)
            c.line(40, y, ancho - 40, y)
            y -= 20
            
            # Métricas
            c.setFont("Helvetica-Bold", 14)
            c.drawString(40, y, "Resumen de Metricas")
            y -= 20
            c.setFont("Helvetica", 11)
            c.drawString(55, y, f"Membresias Activas: {self.card_activas.label_valor.text()}")
            y -= 16
            c.drawString(55, y, f"Membresias Por Vencer: {self.card_por_vencer.label_valor.text()}")
            y -= 16
            c.drawString(55, y, f"Membresias Vencidas: {self.card_vencidas.label_valor.text()}")
            y -= 16
            c.drawString(55, y, f"Ingresos: {self.card_pagos_mes.label_valor.text()}")
            y -= 16
            c.drawString(55, y, f"Stock Bajo: {self.card_stock_bajo.label_valor.text()}")
            y -= 25
            
            # Línea separadora
            c.line(40, y, ancho - 40, y)
            y -= 20
            
            # ===== Gráficos =====
            c.setFont("Helvetica-Bold", 14)
            c.drawString(40, y, "Graficos")
            y -= 10
            
            img_w = 240
            img_h = 190
            
            # Verificar si caben los gráficos, si no nueva página
            if y - img_h < 80:
                c.showPage()
                y = alto - 40
            
            # Gráfico de membresías a la izquierda
            c.setFont("Helvetica-Bold", 10)
            c.drawCentredString(40 + img_w / 2, y, "Membresias por estado")
            y -= 5
            c.drawImage(ImageReader(img_torta_membresias), 40, y - img_h, width=img_w, height=img_h, preserveAspectRatio=True, anchor='c', mask='auto')
            
            # Gráfico de sexo a la derecha
            c.drawCentredString(300 + img_w / 2, y + 5, "Clientes por sexo")
            c.drawImage(ImageReader(img_torta_sexo), 300, y - img_h, width=img_w, height=img_h, preserveAspectRatio=True, anchor='c', mask='auto')
            
            y -= img_h + 20
            
            # Línea separadora
            c.line(40, y, ancho - 40, y)
            y -= 20
            
            # ===== Tabla de membresías =====
            c.setFont("Helvetica-Bold", 14)
            c.drawString(40, y, "Membresias")
            y -= 18
            
            c.setFont("Helvetica-Bold", 9)
            cols_m = [40, 180, 290, 400]
            headers_m = ["Cliente", "Inicio", "Vencimiento", "Estado"]
            for col, header in zip(cols_m, headers_m):
                c.drawString(col, y, header)
            y -= 3
            c.line(40, y, ancho - 40, y)
            y -= 14
            
            c.setFont("Helvetica", 9)
            membresias = self._membresias_mostradas
            for m in membresias:
                if y < 80:
                    c.showPage()
                    y = alto - 40
                c.drawString(cols_m[0], y, str(m.get('cliente_nombre', ''))[:25])
                c.drawString(cols_m[1], y, str(m.get('fecha_inicio', '')))
                c.drawString(cols_m[2], y, str(m.get('fecha_vencimiento', '')))
                c.drawString(cols_m[3], y, str(m.get('estado', '')))
                y -= 14
            
            if not membresias:
                c.drawString(55, y, "Sin datos para mostrar")
                y -= 14
            
            y -= 15
            c.line(40, y, ancho - 40, y)
            y -= 20
            
            # ===== Tabla de pagos =====
            if y < 100:
                c.showPage()
                y = alto - 40
            
            c.setFont("Helvetica-Bold", 14)
            c.drawString(40, y, "Pagos")
            y -= 18
            
            c.setFont("Helvetica-Bold", 9)
            cols_p = [40, 180, 310, 420]
            headers_p = ["Cliente", "Fecha", "Monto", "Metodo"]
            for col, header in zip(cols_p, headers_p):
                c.drawString(col, y, header)
            y -= 3
            c.line(40, y, ancho - 40, y)
            y -= 14
            
            c.setFont("Helvetica", 9)
            pagos = self._pagos_mostrados
            for p in pagos:
                if y < 80:
                    c.showPage()
                    y = alto - 40
                c.drawString(cols_p[0], y, str(p.get('cliente_nombre', ''))[:25])
                c.drawString(cols_p[1], y, str(p.get('fecha', '')))
                c.drawString(cols_p[2], y, f"${p.get('monto', 0):,.2f}")
                c.drawString(cols_p[3], y, str(p.get('metodo', '')))
                y -= 14
            
            if not pagos:
                c.drawString(55, y, "Sin datos para mostrar")
                y -= 14
            
            # Pie de página
            c.setFont("Helvetica", 8)
            c.drawString(40, 30, f"KyoGym - Reporte generado automaticamente el {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            
            c.save()
        finally:
            # Limpiar archivos temporales de imágenes
            for img_path in [img_torta_membresias, img_torta_sexo]:
                try:
                    os.unlink(img_path)
                except OSError:
                    pass
