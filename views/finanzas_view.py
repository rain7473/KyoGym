"""Vista de Finanzas (solo admin) — 5 pestañas"""
from datetime import date, timedelta
import subprocess, sys, os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QFormLayout,
    QLineEdit, QDateEdit, QComboBox, QMessageBox, QSizePolicy, QGridLayout,
    QScrollArea, QSpacerItem, QToolTip, QSpinBox,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor, QPainter, QCursor
from PySide6.QtCharts import QChart, QChartView, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis

from services import finanzas_service
from utils.iconos_ui import crear_boton_icono, crear_widget_centrado
from utils.table_styles import aplicar_estilo_tabla_moderna
from utils.table_utils import limpiar_tabla
from utils.validators import crear_validador_numerico_decimal


# ─────────────────────────── helpers UI ──────────────────────────

_ESTILO_DATE = """
    QDateEdit {
        padding: 6px 10px; border: none; border-radius: 4px;
        background-color: #f5f5f5; font-size: 12px; color: #2c2c2c; min-width: 120px;
    }
    QDateEdit:focus { border: 2px solid #c0c0c0; }
    QDateEdit::drop-down { border: none; }
    QCalendarWidget QAbstractItemView { selection-background-color:#808080; color:#2c2c2c; background-color:#f5f5f5; }
    QCalendarWidget QWidget { color:#2c2c2c; background-color:#f5f5f5; }
    QCalendarWidget QToolButton { color:#2c2c2c; background-color:#f0f0f0; }
    QCalendarWidget QTableView::item:selected { background-color:#808080; color:white; }
    QCalendarWidget QTableView { color:#2c2c2c; }
"""

_ESTILO_BTN_FLT = """
    QPushButton {
        background-color:#3498db; color:white; padding:6px 16px;
        border:none; border-radius:4px; font-size:12px; font-weight:bold;
    }
    QPushButton:hover { background-color:#2980b9; }
"""

_ESTILO_BTN_LIMPIAR = """
    QPushButton {
        background-color:#95a5a6; color:white; padding:6px 16px;
        border:none; border-radius:4px; font-size:12px; font-weight:bold;
    }
    QPushButton:hover { background-color:#7f8c8d; }
"""

_ESTILO_BTN_ACCION = """
    QPushButton {
        background-color:#2c6fad; color:white; padding:10px 20px;
        border:none; border-radius:5px; font-weight:bold; font-size:13px;
    }
    QPushButton:hover { background-color:#255d91; }
"""

_ESTILO_COMBO = """
    QComboBox {
        padding:8px; border:2px solid #d0d0d0; border-radius:4px;
        background-color:#f5f5f5; color:#1a1a1a; font-size:13px;
    }
    QComboBox:focus { border:2px solid #c0c0c0; }
    QComboBox QAbstractItemView {
        color:#2c2c2c; background-color:#f5f5f5;
        selection-background-color:#808080; selection-color:white;
    }
"""


def _label_total(texto=""):
    lbl = QLabel(texto)
    lbl.setFont(QFont("Arial", 13, QFont.Bold))
    lbl.setStyleSheet("color:#27ae60; padding:6px 0;")
    return lbl


def _card(titulo, valor, color="#2c6fad"):
    """Crea una tarjeta de resumen."""
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background-color: #ffffff;
            border: none;
            border-radius: 8px;
        }}
    """)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(6)

    lbl_titulo = QLabel(titulo)
    lbl_titulo.setStyleSheet("color:#666666; font-size:12px;")
    layout.addWidget(lbl_titulo)

    lbl_valor = QLabel(valor)
    lbl_valor.setFont(QFont("Arial", 18, QFont.Bold))
    lbl_valor.setStyleSheet(f"color:{color}; background:transparent;")
    layout.addWidget(lbl_valor)

    return frame, lbl_valor


def _fila_rango_fechas(parent, desde_attr, hasta_attr, callback):
    """Utility: crea HBox con DateEdits de rango y botones Filtrar/Limpiar."""
    row = QHBoxLayout()
    row.setSpacing(8)

    lbl1 = QLabel("Desde:"); lbl1.setStyleSheet("color:#555; font-size:12px;")
    row.addWidget(lbl1)
    de = QDateEdit(); de.setCalendarPopup(True)
    de.setDate(QDate(date.today().year, date.today().month, 1))
    de.setDisplayFormat("dd/MM/yyyy"); de.setStyleSheet(_ESTILO_DATE)
    setattr(parent, desde_attr, de)
    row.addWidget(de)

    lbl2 = QLabel("Hasta:"); lbl2.setStyleSheet("color:#555; font-size:12px;")
    row.addWidget(lbl2)
    ha = QDateEdit(); ha.setCalendarPopup(True)
    ha.setDate(QDate.currentDate())
    ha.setDisplayFormat("dd/MM/yyyy"); ha.setStyleSheet(_ESTILO_DATE)
    setattr(parent, hasta_attr, ha)
    row.addWidget(ha)

    btn_f = QPushButton("Filtrar"); btn_f.setStyleSheet(_ESTILO_BTN_FLT)
    btn_f.clicked.connect(callback)
    row.addWidget(btn_f)

    btn_l = QPushButton("Limpiar"); btn_l.setStyleSheet(_ESTILO_BTN_LIMPIAR)
    btn_l.clicked.connect(lambda: _limpiar_rango(parent, desde_attr, hasta_attr, callback))
    row.addWidget(btn_l)

    row.addStretch()
    return row


def _limpiar_rango(parent, desde_attr, hasta_attr, callback):
    getattr(parent, desde_attr).setDate(QDate(date.today().year, date.today().month, 1))
    getattr(parent, hasta_attr).setDate(QDate.currentDate())
    callback()


def _qdate_to_date(qd):
    return date(qd.year(), qd.month(), qd.day())


# ─────────────────────────── VISTA PRINCIPAL ─────────────────────

class FinanzasView(QWidget):
    """Vista de Finanzas con 5 pestañas (solo admin)."""

    def __init__(self):
        super().__init__()
        self.init_ui()

    # ── init ──────────────────────────────────────────────────────

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        titulo = QLabel("Finanzas")
        titulo.setFont(QFont("Arial", 24, QFont.Bold))
        titulo.setStyleSheet("color:#1a1a1a;")
        layout.addWidget(titulo)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; border-radius:4px; background:#f8f8f8; }
            QTabBar::tab {
                padding: 10px 20px; font-size:13px; font-weight:bold;
                color:#555555; background:#eeeeee;
                border:none; border-bottom:none; border-radius:4px 4px 0 0;
            }
            QTabBar::tab:selected { background:#f8f8f8; color:#1a1a1a; border-bottom:1px solid #f8f8f8; }
            QTabBar::tab:hover { background:#e0e0e0; }
        """)

        self.tabs.addTab(self._crear_tab_resumen(), "📊 Resumen")
        self.tabs.addTab(self._crear_tab_ingresos(), "💵 Ingresos")
        self.tabs.addTab(self._crear_tab_egresos(), "💸 Egresos")
        self.tabs.addTab(self._crear_tab_reportes(), "📄 Reportes")

        layout.addWidget(self.tabs)

    # ── Pestaña 1: Resumen ────────────────────────────────────────

    def _crear_tab_resumen(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Tarjetas
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        frame_i, self.card_ingresos = _card("Ingresos del mes", "$0.00", "#27ae60")
        frame_e, self.card_egresos = _card("Egresos del mes", "$0.00", "#e74c3c")
        frame_u, self.card_utilidad = _card("Utilidad", "$0.00", "#2980b9")
        frame_a, self.card_activas = _card("Membresías activas", "0", "#8e44ad")

        for frame in [frame_i, frame_e, frame_u, frame_a]:
            cards_layout.addWidget(frame)

        layout.addLayout(cards_layout)

        # ── Gráfico Ingresos vs Egresos ──────────────────────────────
        chart_frame = QFrame()
        chart_frame.setStyleSheet(
            "QFrame { background:#ffffff; border:none; border-radius:8px; }"
        )
        chart_frame_layout = QVBoxLayout(chart_frame)
        chart_frame_layout.setContentsMargins(12, 10, 12, 10)
        chart_frame_layout.setSpacing(4)

        # ── Fila superior: título + controles ────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        lbl_chart = QLabel("Ingresos vs. Egresos")
        lbl_chart.setFont(QFont("Arial", 13, QFont.Bold))
        lbl_chart.setStyleSheet("color:#1a1a1a;")
        top_row.addWidget(lbl_chart)
        top_row.addStretch()

        # Botones de periodo
        _ESTILO_BTN_PER_ON = (
            "QPushButton { background:#2c6fad; color:white; padding:5px 14px;"
            " border:none; border-radius:4px; font-size:12px; font-weight:bold; }"
        )
        _ESTILO_BTN_PER_OFF = (
            "QPushButton { background:#e0e0e0; color:#333333; padding:5px 14px;"
            " border:none; border-radius:4px; font-size:12px; }"
            "QPushButton:hover { background:#cccccc; }"
        )

        self._btn_per_1m = QPushButton("1 Mes")
        self._btn_per_3m = QPushButton("3 Meses")
        self._btn_per_año = QPushButton("Año")
        self._btn_per_1m.setStyleSheet(_ESTILO_BTN_PER_OFF)
        self._btn_per_3m.setStyleSheet(_ESTILO_BTN_PER_OFF)
        self._btn_per_año.setStyleSheet(_ESTILO_BTN_PER_ON)  # activo por defecto
        self._chart_periodo = "año"

        self._btn_per_1m.clicked.connect(lambda: self._set_chart_periodo("1m"))
        self._btn_per_3m.clicked.connect(lambda: self._set_chart_periodo("3m"))
        self._btn_per_año.clicked.connect(lambda: self._set_chart_periodo("año"))

        top_row.addWidget(self._btn_per_1m)
        top_row.addWidget(self._btn_per_3m)
        top_row.addWidget(self._btn_per_año)

        # Selector de año
        lbl_año = QLabel("Año:")
        lbl_año.setStyleSheet("color:#555; font-size:12px;")
        top_row.addWidget(lbl_año)

        self._chart_spin_año = QSpinBox()
        self._chart_spin_año.setRange(2020, date.today().year)
        self._chart_spin_año.setValue(date.today().year)
        self._chart_spin_año.setStyleSheet(
            "QSpinBox { padding:4px 6px; border:none; border-radius:4px;"
            " background:#f5f5f5; color:#1a1a1a; font-size:12px; min-width:60px; }"
        )
        self._chart_spin_año.valueChanged.connect(lambda _: self._actualizar_grafico())
        top_row.addWidget(self._chart_spin_año)

        chart_frame_layout.addLayout(top_row)

        # ── Etiqueta de porcentaje ganancia/pérdida ──────────────────
        self._chart_pct_lbl = QLabel("")
        self._chart_pct_lbl.setStyleSheet("color:#27ae60; font-size:13px; font-weight:bold; padding:2px 0;")
        chart_frame_layout.addWidget(self._chart_pct_lbl)

        # ── Serie y ejes ─────────────────────────────────────────────
        self._bar_series = QBarSeries()
        self._bar_series.hovered.connect(self._on_bar_hovered)

        self._chart = QChart()
        self._chart.addSeries(self._bar_series)
        self._chart.setAnimationOptions(QChart.SeriesAnimations)
        self._chart.setBackgroundBrush(QColor("#ffffff"))
        self._chart.setBackgroundRoundness(0)
        self._chart.legend().setVisible(True)
        self._chart.legend().setAlignment(Qt.AlignBottom)

        self._chart_axis_x = QBarCategoryAxis()
        self._chart.addAxis(self._chart_axis_x, Qt.AlignBottom)

        self._chart_axis_y = QValueAxis()
        self._chart_axis_y.setLabelFormat("$%.0f")
        self._chart_axis_y.setMin(0)
        self._chart.addAxis(self._chart_axis_y, Qt.AlignLeft)

        # Adjuntar ejes a la serie una sola vez aquí
        self._bar_series.attachAxis(self._chart_axis_x)
        self._bar_series.attachAxis(self._chart_axis_y)

        chart_view = QChartView(self._chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setMinimumHeight(220)
        chart_view.setMaximumHeight(255)
        chart_frame_layout.addWidget(chart_view)

        layout.addWidget(chart_frame)

        # Tablas últimos registros
        tablas_layout = QHBoxLayout()
        tablas_layout.setSpacing(16)

        # Últimos ingresos
        grp_ing = QVBoxLayout()
        lbl_ing = QLabel("Últimos ingresos")
        lbl_ing.setFont(QFont("Arial", 13, QFont.Bold))
        lbl_ing.setStyleSheet("color:#1a1a1a;")
        grp_ing.addWidget(lbl_ing)
        self.tabla_ult_ingresos = QTableWidget()
        self.tabla_ult_ingresos.setColumnCount(4)
        self.tabla_ult_ingresos.setHorizontalHeaderLabels(["Fecha", "Cliente", "Concepto", "Monto"])
        self.tabla_ult_ingresos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_ult_ingresos.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_ult_ingresos.setSelectionMode(QTableWidget.NoSelection)
        self.tabla_ult_ingresos.setAlternatingRowColors(False)
        aplicar_estilo_tabla_moderna(self.tabla_ult_ingresos)
        grp_ing.addWidget(self.tabla_ult_ingresos)
        tablas_layout.addLayout(grp_ing)

        # Últimos egresos
        grp_eg = QVBoxLayout()
        lbl_eg = QLabel("Últimos egresos")
        lbl_eg.setFont(QFont("Arial", 13, QFont.Bold))
        lbl_eg.setStyleSheet("color:#1a1a1a;")
        grp_eg.addWidget(lbl_eg)
        self.tabla_ult_egresos = QTableWidget()
        self.tabla_ult_egresos.setColumnCount(4)
        self.tabla_ult_egresos.setHorizontalHeaderLabels(["Fecha", "Categoría", "Descripción", "Monto"])
        self.tabla_ult_egresos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_ult_egresos.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_ult_egresos.setSelectionMode(QTableWidget.NoSelection)
        self.tabla_ult_egresos.setAlternatingRowColors(False)
        aplicar_estilo_tabla_moderna(self.tabla_ult_egresos)
        grp_eg.addWidget(self.tabla_ult_egresos)
        tablas_layout.addLayout(grp_eg)

        layout.addLayout(tablas_layout)
        return w

    # ── Pestaña 2: Ingresos ───────────────────────────────────────

    def _crear_tab_ingresos(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Filtros
        filtros = QHBoxLayout()
        filtros.setSpacing(10)

        lbl = QLabel("📅 Rango:")
        lbl.setStyleSheet("color:#555; font-weight:bold; font-size:13px;")
        filtros.addWidget(lbl)

        filtros.addLayout(_fila_rango_fechas(self, "ing_desde", "ing_hasta",
                                            self._cargar_ingresos))

        lbl_b = QLabel("🔍 Cliente:")
        lbl_b.setStyleSheet("color:#555; font-size:13px;")
        filtros.addWidget(lbl_b)

        self.ing_buscar = QLineEdit()
        self.ing_buscar.setPlaceholderText("Buscar cliente...")
        self.ing_buscar.setClearButtonEnabled(True)
        self.ing_buscar.setStyleSheet("""
            QLineEdit { padding:8px 10px; border:none; border-radius:5px;
                        background:#f5f5f5; font-size:13px; color:#2c2c2c; }
            QLineEdit:focus { border:2px solid #c0c0c0; }
        """)
        self.ing_buscar.textChanged.connect(self._cargar_ingresos)
        filtros.addWidget(self.ing_buscar)

        layout.addLayout(filtros)

        # Tabla
        self.tabla_ingresos = QTableWidget()
        self.tabla_ingresos.setColumnCount(6)
        self.tabla_ingresos.setHorizontalHeaderLabels(["Fecha", "Cliente", "Concepto", "Método", "Monto", "Acciones"])
        self.tabla_ingresos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_ingresos.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_ingresos.setSelectionMode(QTableWidget.NoSelection)
        self.tabla_ingresos.setAlternatingRowColors(False)
        aplicar_estilo_tabla_moderna(self.tabla_ingresos)
        layout.addWidget(self.tabla_ingresos)

        self.ing_total_lbl = _label_total("Total: $0.00")
        layout.addWidget(self.ing_total_lbl)

        return w

    # ── Pestaña 3: Egresos ────────────────────────────────────────

    def _crear_tab_egresos(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Formulario de registro
        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame { background:#ffffff; border:none; border-radius:8px; }
            QLabel { border:none; background:transparent; color:#2c2c2c; font-size:13px; }
        """)
        form_layout = QFormLayout(form_frame)
        form_layout.setContentsMargins(16, 14, 16, 14)
        form_layout.setSpacing(10)

        lbl_form = QLabel("Registrar gasto")
        lbl_form.setFont(QFont("Arial", 13, QFont.Bold))
        lbl_form.setStyleSheet("color:#1a1a1a; background:transparent; border:none;")
        form_layout.addRow(lbl_form)

        self.eg_fecha = QDateEdit()
        self.eg_fecha.setCalendarPopup(True)
        self.eg_fecha.setDate(QDate.currentDate())
        self.eg_fecha.setDisplayFormat("dd/MM/yyyy")
        self.eg_fecha.setStyleSheet(_ESTILO_DATE)
        form_layout.addRow("Fecha:", self.eg_fecha)

        self.eg_categoria = QComboBox()
        self.eg_categoria.addItems(finanzas_service.CATEGORIAS_EGRESO)
        self.eg_categoria.setStyleSheet(_ESTILO_COMBO)
        form_layout.addRow("Categoría:", self.eg_categoria)

        self.eg_descripcion = QLineEdit()
        self.eg_descripcion.setPlaceholderText("Descripción del gasto")
        self.eg_descripcion.setStyleSheet("""
            QLineEdit { padding:8px; border:2px solid #d0d0d0; border-radius:4px;
                        background:#f5f5f5; color:#1a1a1a; font-size:13px; }
            QLineEdit:focus { border:2px solid #c0c0c0; }
        """)
        form_layout.addRow("Descripción:", self.eg_descripcion)

        self.eg_proveedor = QLineEdit()
        self.eg_proveedor.setPlaceholderText("Proveedor (opcional)")
        self.eg_proveedor.setStyleSheet(self.eg_descripcion.styleSheet())
        form_layout.addRow("Proveedor:", self.eg_proveedor)

        self.eg_metodo = QComboBox()
        self.eg_metodo.addItems(["Efectivo", "Tarjeta", "Transferencia", "Otro"])
        self.eg_metodo.setStyleSheet(_ESTILO_COMBO)
        form_layout.addRow("Método:", self.eg_metodo)

        self.eg_monto = QLineEdit()
        self.eg_monto.setPlaceholderText("0.00")
        self.eg_monto.setValidator(crear_validador_numerico_decimal())
        self.eg_monto.setStyleSheet(self.eg_descripcion.styleSheet())
        form_layout.addRow("Monto:", self.eg_monto)

        btn_registrar_eg = QPushButton("Registrar Gasto")
        btn_registrar_eg.setStyleSheet(_ESTILO_BTN_ACCION)
        btn_registrar_eg.clicked.connect(self._registrar_egreso)
        form_layout.addRow(btn_registrar_eg)

        layout.addWidget(form_frame)

        # Filtros tabla (fila manual para controlar exactamente los callbacks)
        flt_eg = QHBoxLayout()
        flt_eg.setSpacing(8)

        lbl_r = QLabel("📅 Rango:")
        lbl_r.setStyleSheet("color:#555; font-weight:bold; font-size:13px;")
        flt_eg.addWidget(lbl_r)

        lbl_desde_eg = QLabel("Desde:")
        lbl_desde_eg.setStyleSheet("color:#666; font-size:12px;")
        flt_eg.addWidget(lbl_desde_eg)

        self.eg_desde = QDateEdit()
        self.eg_desde.setCalendarPopup(True)
        self.eg_desde.setDate(QDate(date.today().year, date.today().month, 1))
        self.eg_desde.setDisplayFormat("dd/MM/yyyy")
        self.eg_desde.setStyleSheet(_ESTILO_DATE)
        flt_eg.addWidget(self.eg_desde)

        lbl_hasta_eg = QLabel("Hasta:")
        lbl_hasta_eg.setStyleSheet("color:#666; font-size:12px;")
        flt_eg.addWidget(lbl_hasta_eg)

        self.eg_hasta = QDateEdit()
        self.eg_hasta.setCalendarPopup(True)
        self.eg_hasta.setDate(QDate.currentDate())
        self.eg_hasta.setDisplayFormat("dd/MM/yyyy")
        self.eg_hasta.setStyleSheet(_ESTILO_DATE)
        flt_eg.addWidget(self.eg_hasta)

        btn_filtrar_eg = QPushButton("Filtrar")
        btn_filtrar_eg.setStyleSheet(_ESTILO_BTN_FLT)
        btn_filtrar_eg.clicked.connect(self._filtrar_egresos)
        flt_eg.addWidget(btn_filtrar_eg)

        btn_limpiar_eg = QPushButton("Limpiar")
        btn_limpiar_eg.setStyleSheet(_ESTILO_BTN_LIMPIAR)
        btn_limpiar_eg.clicked.connect(self._limpiar_filtro_egresos)
        flt_eg.addWidget(btn_limpiar_eg)

        flt_eg.addSpacing(16)

        lbl_cat = QLabel("Categoría:")
        lbl_cat.setStyleSheet("color:#555; font-size:13px;")
        flt_eg.addWidget(lbl_cat)

        self.eg_combo_filtro_cat = QComboBox()
        self.eg_combo_filtro_cat.addItem("Todas")
        self.eg_combo_filtro_cat.addItems(finanzas_service.CATEGORIAS_EGRESO)
        self.eg_combo_filtro_cat.setStyleSheet(_ESTILO_COMBO)
        # Usar lambda para evitar que el texto del signal se pase como argumento posicional
        self.eg_combo_filtro_cat.currentTextChanged.connect(lambda _: self._cargar_egresos())
        flt_eg.addWidget(self.eg_combo_filtro_cat)

        flt_eg.addStretch()
        layout.addLayout(flt_eg)

        # Tabla
        self.tabla_egresos = QTableWidget()
        self.tabla_egresos.setColumnCount(7)
        self.tabla_egresos.setHorizontalHeaderLabels(
            ["Fecha", "Categoría", "Descripción", "Proveedor", "Método", "Monto", "Acciones"])
        self.tabla_egresos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_egresos.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_egresos.setSelectionMode(QTableWidget.NoSelection)
        self.tabla_egresos.setAlternatingRowColors(False)
        aplicar_estilo_tabla_moderna(self.tabla_egresos)
        layout.addWidget(self.tabla_egresos)

        self.eg_total_lbl = _label_total("Total: $0.00")
        layout.addWidget(self.eg_total_lbl)

        return w

    # ── Pestaña 4: Morosidad ──────────────────────────────────────

    def _crear_tab_morosidad(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        btn_refresh = QPushButton("🔄 Actualizar")
        btn_refresh.setStyleSheet(_ESTILO_BTN_FLT)
        btn_refresh.clicked.connect(self._cargar_morosos)
        layout.addWidget(btn_refresh, alignment=Qt.AlignLeft)

        self.tabla_morosos = QTableWidget()
        self.tabla_morosos.setColumnCount(6)
        self.tabla_morosos.setHorizontalHeaderLabels(
            ["Cliente", "Teléfono", "Vencimiento", "Días de atraso", "Último monto", "Acción"])
        self.tabla_morosos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_morosos.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_morosos.setSelectionMode(QTableWidget.NoSelection)
        self.tabla_morosos.setAlternatingRowColors(False)
        aplicar_estilo_tabla_moderna(self.tabla_morosos)
        layout.addWidget(self.tabla_morosos)

        return w

    # ── Pestaña 5: Reportes ───────────────────────────────────────

    def _crear_tab_reportes(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # ── Sección: Reporte Diario (ARRIBA) ─────────────────────
        lbl_diario_top = QLabel("Reporte Diario")
        lbl_diario_top.setFont(QFont("Arial", 13, QFont.Bold))
        lbl_diario_top.setStyleSheet("color:#1a1a1a;")
        layout.addWidget(lbl_diario_top)

        ctrl_dia_top = QHBoxLayout()
        ctrl_dia_top.setSpacing(12)

        lbl_dia_top = QLabel("Día:")
        lbl_dia_top.setStyleSheet("color:#555; font-size:13px;")
        ctrl_dia_top.addWidget(lbl_dia_top)

        self.rpt_dia_top = QDateEdit()
        self.rpt_dia_top.setCalendarPopup(True)
        self.rpt_dia_top.setDate(QDate.currentDate())
        self.rpt_dia_top.setDisplayFormat("dd/MM/yyyy")
        self.rpt_dia_top.setStyleSheet(_ESTILO_DATE)
        ctrl_dia_top.addWidget(self.rpt_dia_top)

        btn_pdf_dia_top = QPushButton("\U0001f4c4 PDF del día")
        btn_pdf_dia_top.setStyleSheet("""
            QPushButton { background-color:#e74c3c; color:white; padding:8px 18px;
                          border:none; border-radius:4px; font-size:13px; font-weight:bold; }
            QPushButton:hover { background-color:#c0392b; }
        """)
        btn_pdf_dia_top.clicked.connect(lambda: self._exportar_pdf_diario(self.rpt_dia_top))
        ctrl_dia_top.addWidget(btn_pdf_dia_top)

        btn_excel_dia_top = QPushButton("\U0001f4ca Excel del día")
        btn_excel_dia_top.setStyleSheet("""
            QPushButton { background-color:#27ae60; color:white; padding:8px 18px;
                          border:none; border-radius:4px; font-size:13px; font-weight:bold; }
            QPushButton:hover { background-color:#219a52; }
        """)
        btn_excel_dia_top.clicked.connect(lambda: self._exportar_excel_diario(self.rpt_dia_top))
        ctrl_dia_top.addWidget(btn_excel_dia_top)

        ctrl_dia_top.addStretch()
        layout.addLayout(ctrl_dia_top)

        sep_top = QFrame()
        sep_top.setFrameShape(QFrame.HLine)
        sep_top.setStyleSheet("color:#d0d0d0; background:#d0d0d0; max-height:1px;")
        layout.addWidget(sep_top)

        # ── Sección: Reportes Mensuales/Anuales ──────────────────
        lbl_mensual = QLabel("Reportes Mensuales/Anuales")
        lbl_mensual.setFont(QFont("Arial", 13, QFont.Bold))
        lbl_mensual.setStyleSheet("color:#1a1a1a; padding-bottom:4px;")
        layout.addWidget(lbl_mensual)

        # Controles
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(12)

        lbl_año = QLabel("Año:")
        lbl_año.setStyleSheet("color:#555; font-size:13px;")
        ctrl_layout.addWidget(lbl_año)

        self.rpt_año = QComboBox()
        año_actual = date.today().year
        for a in range(año_actual - 3, año_actual + 2):
            self.rpt_año.addItem(str(a), a)
        self.rpt_año.setCurrentText(str(año_actual))
        self.rpt_año.setStyleSheet(_ESTILO_COMBO)
        ctrl_layout.addWidget(self.rpt_año)

        lbl_mes = QLabel("Mes:")
        lbl_mes.setStyleSheet("color:#555; font-size:13px;")
        ctrl_layout.addWidget(lbl_mes)

        self.rpt_mes = QComboBox()
        self.rpt_mes.addItem("Todo el año", 0)
        nombres_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        for i, nm in enumerate(nombres_meses, 1):
            self.rpt_mes.addItem(nm, i)
        self.rpt_mes.setCurrentIndex(date.today().month)
        self.rpt_mes.setStyleSheet(_ESTILO_COMBO)
        ctrl_layout.addWidget(self.rpt_mes)

        btn_generar = QPushButton("🔄 Generar")
        btn_generar.setStyleSheet(_ESTILO_BTN_FLT)
        btn_generar.clicked.connect(self._generar_reporte)
        ctrl_layout.addWidget(btn_generar)

        btn_pdf = QPushButton("📄 Exportar PDF")
        btn_pdf.setStyleSheet("""
            QPushButton { background-color:#e74c3c; color:white; padding:8px 18px;
                          border:none; border-radius:4px; font-size:13px; font-weight:bold; }
            QPushButton:hover { background-color:#c0392b; }
        """)
        btn_pdf.clicked.connect(self._exportar_pdf)
        ctrl_layout.addWidget(btn_pdf)

        btn_excel = QPushButton("📊 Exportar Excel")
        btn_excel.setStyleSheet("""
            QPushButton { background-color:#27ae60; color:white; padding:8px 18px;
                          border:none; border-radius:4px; font-size:13px; font-weight:bold; }
            QPushButton:hover { background-color:#219a52; }
        """)
        btn_excel.clicked.connect(self._exportar_excel)
        ctrl_layout.addWidget(btn_excel)

        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # Tabla ingresos del período
        lbl_i = QLabel("Ingresos del período")
        lbl_i.setFont(QFont("Arial", 13, QFont.Bold))
        lbl_i.setStyleSheet("color:#1a1a1a;")
        layout.addWidget(lbl_i)

        self.tabla_rpt_ingresos = QTableWidget()
        self.tabla_rpt_ingresos.setColumnCount(5)
        self.tabla_rpt_ingresos.setHorizontalHeaderLabels(["Fecha", "Cliente", "Concepto", "Método", "Monto"])
        self.tabla_rpt_ingresos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_rpt_ingresos.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_rpt_ingresos.setSelectionMode(QTableWidget.NoSelection)
        self.tabla_rpt_ingresos.setAlternatingRowColors(False)
        self.tabla_rpt_ingresos.setMaximumHeight(200)
        aplicar_estilo_tabla_moderna(self.tabla_rpt_ingresos)
        layout.addWidget(self.tabla_rpt_ingresos)

        self.rpt_total_ingresos = _label_total("Total ingresos período: $0.00")
        layout.addWidget(self.rpt_total_ingresos)

        # Tabla egresos del período
        lbl_e = QLabel("Egresos del período")
        lbl_e.setFont(QFont("Arial", 13, QFont.Bold))
        lbl_e.setStyleSheet("color:#1a1a1a;")
        layout.addWidget(lbl_e)

        self.tabla_rpt_egresos = QTableWidget()
        self.tabla_rpt_egresos.setColumnCount(6)
        self.tabla_rpt_egresos.setHorizontalHeaderLabels(
            ["Fecha", "Categoría", "Descripción", "Proveedor", "Método", "Monto"])
        self.tabla_rpt_egresos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_rpt_egresos.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_rpt_egresos.setSelectionMode(QTableWidget.NoSelection)
        self.tabla_rpt_egresos.setAlternatingRowColors(False)
        self.tabla_rpt_egresos.setMaximumHeight(200)
        aplicar_estilo_tabla_moderna(self.tabla_rpt_egresos)
        layout.addWidget(self.tabla_rpt_egresos)

        self.rpt_total_egresos = _label_total("Total egresos período: $0.00")
        self.rpt_total_egresos.setStyleSheet("color:#e74c3c; font-size:13px; font-weight:bold; padding:6px 0;")
        layout.addWidget(self.rpt_total_egresos)

        # Comparación mes a mes
        lbl_comp = QLabel("Comparación mes a mes")
        lbl_comp.setFont(QFont("Arial", 13, QFont.Bold))
        lbl_comp.setStyleSheet("color:#1a1a1a;")
        layout.addWidget(lbl_comp)

        self.tabla_comparacion = QTableWidget()
        self.tabla_comparacion.setColumnCount(5)
        self.tabla_comparacion.setHorizontalHeaderLabels(["Mes", "Ingresos", "Egresos", "Utilidad", "Variación %"])
        self.tabla_comparacion.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_comparacion.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_comparacion.setSelectionMode(QTableWidget.NoSelection)
        self.tabla_comparacion.setAlternatingRowColors(False)
        aplicar_estilo_tabla_moderna(self.tabla_comparacion)
        layout.addWidget(self.tabla_comparacion)

        return w

    # ── cargar_datos público ──────────────────────────────────────

    def cargar_datos(self):
        """Recarga todas las pestañas."""
        self._cargar_resumen()
        self._cargar_ingresos()
        self._cargar_egresos()
        self._generar_reporte()

    # ── Lógica pestaña Resumen ────────────────────────────────────

    def _cargar_resumen(self):
        resumen = finanzas_service.obtener_resumen_mes()

        self.card_ingresos.setText(f"${resumen['ingresos_mes']:,.2f}")
        self.card_egresos.setText(f"${resumen['egresos_mes']:,.2f}")

        utilidad = resumen["utilidad"]
        color_u = "#27ae60" if utilidad >= 0 else "#e74c3c"
        self.card_utilidad.setText(f"${utilidad:,.2f}")
        self.card_utilidad.setStyleSheet(f"color:{color_u}; background:transparent;")

        self.card_activas.setText(str(resumen["membresias_activas"]))

        # Últimos ingresos
        ult_ing = resumen["ultimos_ingresos"]
        self.tabla_ult_ingresos.setSortingEnabled(False)
        limpiar_tabla(self.tabla_ult_ingresos)
        self.tabla_ult_ingresos.setRowCount(len(ult_ing))
        for i, p in enumerate(ult_ing):
            self.tabla_ult_ingresos.setRowHeight(i, 40)
            for col, val in enumerate([p["fecha"], p["cliente_nombre"], p["concepto"],
                                        f"${p['monto']:,.2f}"]):
                item = QTableWidgetItem(str(val))
                item.setForeground(QColor("#27ae60" if col == 3 else "#1a1a1a"))
                self.tabla_ult_ingresos.setItem(i, col, item)

        # Últimos egresos
        ult_eg = resumen["ultimos_egresos"]
        self.tabla_ult_egresos.setSortingEnabled(False)
        limpiar_tabla(self.tabla_ult_egresos)
        self.tabla_ult_egresos.setRowCount(len(ult_eg))
        for i, e in enumerate(ult_eg):
            self.tabla_ult_egresos.setRowHeight(i, 40)
            for col, val in enumerate([e["fecha"], e["categoria"], e["descripcion"],
                                        f"${e['monto']:,.2f}"]):
                item = QTableWidgetItem(str(val))
                item.setForeground(QColor("#e74c3c" if col == 3 else "#1a1a1a"))
                self.tabla_ult_egresos.setItem(i, col, item)

        # Actualizar gráfico
        self._actualizar_grafico()

    # ── Helpers gráfico Resumen ───────────────────────────────────

    _MESES_CORTOS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                     "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    def _set_chart_periodo(self, periodo):
        self._chart_periodo = periodo
        _ON = (
            "QPushButton { background:#2c6fad; color:white; padding:5px 14px;"
            " border:none; border-radius:4px; font-size:12px; font-weight:bold; }"
        )
        _OFF = (
            "QPushButton { background:#e0e0e0; color:#333333; padding:5px 14px;"
            " border:none; border-radius:4px; font-size:12px; }"
            "QPushButton:hover { background:#cccccc; }"
        )
        self._btn_per_1m.setStyleSheet(_ON if periodo == "1m" else _OFF)
        self._btn_per_3m.setStyleSheet(_ON if periodo == "3m" else _OFF)
        self._btn_per_año.setStyleSheet(_ON if periodo == "año" else _OFF)
        self._actualizar_grafico()

    def _actualizar_grafico(self):
        año = self._chart_spin_año.value()
        periodo = self._chart_periodo
        hoy = date.today()

        comparacion = finanzas_service.obtener_comparacion_meses(año)

        if año == hoy.year:
            mes_hasta = hoy.month  # no mostrar meses futuros
        else:
            mes_hasta = 12

        if periodo == "1m":
            datos = [comparacion[mes_hasta - 1]]
            labels = [self._MESES_CORTOS[mes_hasta - 1]]
        elif periodo == "3m":
            inicio = max(0, mes_hasta - 3)
            datos = comparacion[inicio:mes_hasta]
            labels = self._MESES_CORTOS[inicio:mes_hasta]
        else:  # año
            datos = comparacion[:mes_hasta]
            labels = self._MESES_CORTOS[:mes_hasta]

        # Reconstruir serie
        self._bar_series.clear()
        bar_ing = QBarSet("Ingresos")
        bar_ing.setColor(QColor("#27ae60"))
        bar_eg = QBarSet("Egresos")
        bar_eg.setColor(QColor("#e74c3c"))
        for d in datos:
            bar_ing.append(d["ingresos"])
            bar_eg.append(d["egresos"])
        self._bar_series.append(bar_ing)
        self._bar_series.append(bar_eg)

        self._chart_axis_x.clear()
        self._chart_axis_x.append(labels)

        max_val = max((max(d["ingresos"], d["egresos"]) for d in datos), default=0)
        self._chart_axis_y.setRange(0, max_val * 1.2 if max_val > 0 else 100)

        # ── Porcentaje ganancia / pérdida ───────────────────────────
        total_ing = sum(d["ingresos"] for d in datos)
        total_eg = sum(d["egresos"] for d in datos)
        utilidad = total_ing - total_eg
        if total_ing > 0:
            pct = (utilidad / total_ing) * 100
            flecha = "▲" if pct >= 0 else "▼"
            tipo = "Margen de ganancia" if pct >= 0 else "Margen de pérdida"
            color = "#27ae60" if pct >= 0 else "#e74c3c"
            texto = f"{tipo}: {pct:+.1f}%  {flecha}  (${utilidad:,.2f})"
        else:
            texto = "Sin ingresos en el período seleccionado"
            color = "#888888"
        self._chart_pct_lbl.setText(texto)
        self._chart_pct_lbl.setStyleSheet(
            f"color:{color}; font-size:13px; font-weight:bold; padding:2px 0;"
        )

    def _on_bar_hovered(self, status, index, barset):
        if status:
            valor = barset.at(index)
            label = barset.label()
            QToolTip.showText(QCursor.pos(), f"{label}: ${valor:,.2f}")
        else:
            QToolTip.hideText()

    # ── Lógica pestaña Ingresos ───────────────────────────────────

    def _cargar_ingresos(self):
        fecha_desde = _qdate_to_date(self.ing_desde.date())
        fecha_hasta = _qdate_to_date(self.ing_hasta.date())
        cliente = self.ing_buscar.text().strip()

        pagos = finanzas_service.listar_ingresos(
            fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
            cliente=cliente if cliente else None)

        self.tabla_ingresos.setSortingEnabled(False)
        limpiar_tabla(self.tabla_ingresos)
        self.tabla_ingresos.setRowCount(len(pagos))

        total = 0.0
        for i, p in enumerate(pagos):
            self.tabla_ingresos.setRowHeight(i, 48)
            total += p["monto"]
            for col, val in enumerate([p["fecha"], p["cliente_nombre"],
                                        p["concepto"], p["metodo"]]):
                item = QTableWidgetItem(str(val))
                item.setForeground(QColor("#1a1a1a"))
                self.tabla_ingresos.setItem(i, col, item)

            monto_item = QTableWidgetItem(f"${p['monto']:,.2f}")
            monto_item.setForeground(QColor("#27ae60"))
            self.tabla_ingresos.setItem(i, 4, monto_item)

            btn_del = crear_boton_icono("delete.svg", "#e74c3c", "#c0392b", "Eliminar")
            btn_del.clicked.connect(lambda checked, pid=p["id"]: self._eliminar_ingreso(pid))
            self.tabla_ingresos.setCellWidget(i, 5, crear_widget_centrado(btn_del))

        self.tabla_ingresos.setSortingEnabled(True)
        self.ing_total_lbl.setText(f"Total: ${total:,.2f}")

    def _eliminar_ingreso(self, pago_id):
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirmar")
        msg.setText("¿Eliminar este ingreso?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        if msg.exec() == QMessageBox.Yes:
            try:
                from services import pago_service
                pago_service.eliminar_pago(pago_id)
                self._cargar_ingresos()
                self._cargar_resumen()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    # ── Lógica pestaña Egresos ────────────────────────────────────

    def _filtrar_egresos(self):
        """Aplica el filtro de rango de fechas seleccionado en la UI."""
        qd_desde = self.eg_desde.date()
        qd_hasta = self.eg_hasta.date()
        fd = _qdate_to_date(qd_desde)
        fh = _qdate_to_date(qd_hasta)
        if fd > fh:
            QMessageBox.warning(self, "Error", "La fecha 'Desde' no puede ser mayor que 'Hasta'.")
            return
        self._cargar_egresos(fecha_desde=fd, fecha_hasta=fh)

    def _limpiar_filtro_egresos(self):
        """Limpia el filtro de fecha y muestra todos los egresos."""
        self.eg_desde.setDate(QDate(date.today().year, date.today().month, 1))
        self.eg_hasta.setDate(QDate.currentDate())
        self._cargar_egresos()

    def _registrar_egreso(self):
        qd = self.eg_fecha.date()
        fecha = date(qd.year(), qd.month(), qd.day())
        categoria = self.eg_categoria.currentText()
        descripcion = self.eg_descripcion.text().strip()
        proveedor = self.eg_proveedor.text().strip()
        metodo = self.eg_metodo.currentText()
        monto_txt = self.eg_monto.text().strip()

        if not descripcion:
            QMessageBox.warning(self, "Error", "La descripción es obligatoria.")
            return
        try:
            monto = float(monto_txt.replace(",", "."))
            if monto <= 0:
                raise ValueError()
        except ValueError:
            QMessageBox.warning(self, "Error", "Ingrese un monto válido mayor a 0.")
            return

        finanzas_service.registrar_egreso(fecha, categoria, descripcion, proveedor, metodo, monto)

        # Limpiar formulario
        self.eg_descripcion.clear()
        self.eg_proveedor.clear()
        self.eg_monto.clear()
        self.eg_fecha.setDate(QDate.currentDate())

        self._cargar_egresos()
        self._cargar_resumen()

        msg = QMessageBox(self)
        msg.setWindowTitle("Éxito")
        msg.setText("Gasto registrado correctamente.")
        msg.exec()

    def _cargar_egresos(self, fecha_desde=None, fecha_hasta=None):
        """Carga egresos. Sin args muestra todos; con args aplica filtro de fecha."""
        categoria = self.eg_combo_filtro_cat.currentText()

        egresos = finanzas_service.listar_egresos(
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            categoria=categoria if categoria != "Todas" else None)

        self.tabla_egresos.setSortingEnabled(False)
        limpiar_tabla(self.tabla_egresos)
        self.tabla_egresos.setRowCount(len(egresos))

        total = 0.0
        for i, e in enumerate(egresos):
            self.tabla_egresos.setRowHeight(i, 48)
            total += e["monto"]
            for col, val in enumerate([e["fecha"], e["categoria"], e["descripcion"],
                                        e["proveedor"], e["metodo"]]):
                item = QTableWidgetItem(str(val))
                item.setForeground(QColor("#1a1a1a"))
                self.tabla_egresos.setItem(i, col, item)

            monto_item = QTableWidgetItem(f"${e['monto']:,.2f}")
            monto_item.setForeground(QColor("#e74c3c"))
            self.tabla_egresos.setItem(i, 5, monto_item)

            btn_del = crear_boton_icono("delete.svg", "#e74c3c", "#c0392b", "Eliminar")
            btn_del.clicked.connect(lambda checked, eid=e["id"]: self._eliminar_egreso(eid))
            self.tabla_egresos.setCellWidget(i, 6, crear_widget_centrado(btn_del))

        self.tabla_egresos.setSortingEnabled(True)
        self.eg_total_lbl.setText(f"Total: ${total:,.2f}")

    def _eliminar_egreso(self, egreso_id):
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirmar")
        msg.setText("¿Eliminar este gasto?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        if msg.exec() == QMessageBox.Yes:
            try:
                finanzas_service.eliminar_egreso(egreso_id)
                self._cargar_egresos()
                self._cargar_resumen()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    # ── Lógica pestaña Morosidad ──────────────────────────────────

    def _cargar_morosos(self):
        morosos = finanzas_service.listar_morosos()

        self.tabla_morosos.setSortingEnabled(False)
        limpiar_tabla(self.tabla_morosos)
        self.tabla_morosos.setRowCount(len(morosos))

        for i, m in enumerate(morosos):
            self.tabla_morosos.setRowHeight(i, 48)

            dias = m.get("dias_atraso", 0)
            for col, val in enumerate([
                m["cliente_nombre"],
                m.get("cliente_telefono", ""),
                m["fecha_vencimiento"],
                str(dias),
                f"${m['monto']:,.2f}",
            ]):
                item = QTableWidgetItem(str(val))
                if col == 3:
                    item.setForeground(QColor("#e74c3c"))
                else:
                    item.setForeground(QColor("#1a1a1a"))
                self.tabla_morosos.setItem(i, col, item)

            btn_renovar = QPushButton("Renovar")
            btn_renovar.setStyleSheet("""
                QPushButton { background-color:#2c6fad; color:white; padding:6px 14px;
                              border:none; border-radius:4px; font-size:12px; font-weight:bold; }
                QPushButton:hover { background-color:#255d91; }
            """)
            btn_renovar.clicked.connect(
                lambda checked, cliente_id=m["cliente_id"], cliente_nombre=m["cliente_nombre"]:
                    self._abrir_dialogo_renovar(cliente_id, cliente_nombre)
            )
            self.tabla_morosos.setCellWidget(i, 5, crear_widget_centrado(btn_renovar))

        self.tabla_morosos.setSortingEnabled(True)

    def _abrir_dialogo_renovar(self, cliente_id, cliente_nombre):
        """Abre el diálogo de nueva membresía pre-cargado con el cliente."""
        try:
            from views.membresias_view import AgregarMembresiaDialog
            from services import membresia_service, pago_service, cliente_service
            from utils.factura_generator import generar_factura_membresia, abrir_factura

            dialog = AgregarMembresiaDialog(self)
            # Pre-seleccionar el cliente
            for idx in range(dialog.combo_cliente.count()):
                if dialog.combo_cliente.itemData(idx) == cliente_id:
                    dialog.combo_cliente.setCurrentIndex(idx)
                    break

            if dialog.exec():
                datos = dialog.obtener_datos()
                from services import pago_service as ps
                from datetime import date as _date

                metodo = (datos.get("metodo_pago") or "Efectivo").strip() or "Efectivo"
                ok_pago, pago_id = ps.crear_pago(
                    cliente_id=datos["cliente_id"],
                    monto=datos["monto"],
                    metodo=metodo,
                    fecha_pago=datos["fecha_inicio"],
                    concepto="Pago de membresía",
                )
                if not ok_pago:
                    QMessageBox.warning(self, "Error", f"Error al registrar pago: {pago_id}")
                    return

                membresia_id = membresia_service.crear_membresia(
                    cliente_id=datos["cliente_id"],
                    tipo=datos.get("tipo", "Mensualidad"),
                    fecha_inicio=datos["fecha_inicio"],
                    monto=datos["monto"],
                    pago_id=pago_id,
                )

                self._cargar_morosos()
                self._cargar_resumen()

                msg = QMessageBox(self)
                msg.setWindowTitle("Membresía renovada")
                msg.setText(f"Membresía de {cliente_nombre} renovada exitosamente.")
                msg.exec()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al renovar: {str(e)}")

    # ── Lógica pestaña Reportes ───────────────────────────────────

    def _get_año_mes_rpt(self):
        año = self.rpt_año.currentData()
        mes = self.rpt_mes.currentData()
        return año, mes if mes != 0 else None

    def _generar_reporte(self):
        año, mes = self._get_año_mes_rpt()

        if mes:
            fecha_desde = date(año, mes, 1)
            if mes == 12:
                fecha_hasta = date(año, 12, 31)
            else:
                from datetime import timedelta
                fecha_hasta = date(año, mes + 1, 1) - timedelta(days=1)
        else:
            fecha_desde = date(año, 1, 1)
            fecha_hasta = date(año, 12, 31)

        # Ingresos
        ingresos = finanzas_service.listar_ingresos(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
        total_i = sum(p["monto"] for p in ingresos)
        self.tabla_rpt_ingresos.setSortingEnabled(False)
        limpiar_tabla(self.tabla_rpt_ingresos)
        self.tabla_rpt_ingresos.setRowCount(len(ingresos))
        for i, p in enumerate(ingresos):
            self.tabla_rpt_ingresos.setRowHeight(i, 40)
            for col, val in enumerate([p["fecha"], p["cliente_nombre"], p["concepto"],
                                        p["metodo"], f"${p['monto']:,.2f}"]):
                item = QTableWidgetItem(str(val))
                item.setForeground(QColor("#27ae60" if col == 4 else "#1a1a1a"))
                self.tabla_rpt_ingresos.setItem(i, col, item)
        self.rpt_total_ingresos.setText(f"Total ingresos período: ${total_i:,.2f}")

        # Egresos
        egresos = finanzas_service.listar_egresos(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
        total_e = sum(e["monto"] for e in egresos)
        self.tabla_rpt_egresos.setSortingEnabled(False)
        limpiar_tabla(self.tabla_rpt_egresos)
        self.tabla_rpt_egresos.setRowCount(len(egresos))
        for i, e in enumerate(egresos):
            self.tabla_rpt_egresos.setRowHeight(i, 40)
            for col, val in enumerate([e["fecha"], e["categoria"], e["descripcion"],
                                        e["proveedor"], e["metodo"], f"${e['monto']:,.2f}"]):
                item = QTableWidgetItem(str(val))
                item.setForeground(QColor("#e74c3c" if col == 5 else "#1a1a1a"))
                self.tabla_rpt_egresos.setItem(i, col, item)
        self.rpt_total_egresos.setText(f"Total egresos período: ${total_e:,.2f}")

        # Comparación
        comparacion = finanzas_service.obtener_comparacion_meses(año)
        self.tabla_comparacion.setSortingEnabled(False)
        limpiar_tabla(self.tabla_comparacion)
        self.tabla_comparacion.setRowCount(len(comparacion) + 1)

        tot_i2 = tot_e2 = 0.0
        for i, c in enumerate(comparacion):
            self.tabla_comparacion.setRowHeight(i, 40)
            tot_i2 += c["ingresos"]
            tot_e2 += c["egresos"]

            var_txt = "—"
            var_color = "#1a1a1a"
            if c["variacion_pct"] is not None:
                var_txt = f"{'↑' if c['variacion_pct'] >= 0 else '↓'} {abs(c['variacion_pct']):.1f}%"
                var_color = "#27ae60" if c["variacion_pct"] >= 0 else "#e74c3c"

            util = c["utilidad"]
            util_color = "#27ae60" if util >= 0 else "#e74c3c"

            vals = [c["nombre_mes"], f"${c['ingresos']:,.2f}",
                    f"${c['egresos']:,.2f}", f"${util:,.2f}", var_txt]
            colors_col = ["#1a1a1a", "#27ae60", "#e74c3c", util_color, var_color]
            for col, (val, clr) in enumerate(zip(vals, colors_col)):
                item = QTableWidgetItem(str(val))
                item.setForeground(QColor(clr))
                self.tabla_comparacion.setItem(i, col, item)

        # Fila total año
        row_total = len(comparacion)
        self.tabla_comparacion.setRowHeight(row_total, 44)
        tot_u = tot_i2 - tot_e2
        tot_color = "#27ae60" if tot_u >= 0 else "#e74c3c"
        totals = ["Total año", f"${tot_i2:,.2f}", f"${tot_e2:,.2f}", f"${tot_u:,.2f}", ""]
        tot_colors = ["#1a1a1a", "#27ae60", "#e74c3c", tot_color, "#1a1a1a"]
        for col, (val, clr) in enumerate(zip(totals, tot_colors)):
            item = QTableWidgetItem(val)
            item.setForeground(QColor(clr))
            f = item.font(); f.setBold(True); item.setFont(f)
            self.tabla_comparacion.setItem(row_total, col, item)

        self.tabla_comparacion.setSortingEnabled(True)

    def _exportar_pdf_diario(self, date_edit=None):
        qd = (date_edit or self.rpt_dia_top).date()
        fecha = date(qd.year(), qd.month(), qd.day())
        try:
            ruta = finanzas_service.exportar_pdf_reporte_diario(fecha=fecha)
            msg = QMessageBox(self)
            msg.setWindowTitle("PDF diario generado")
            msg.setText(f"Archivo guardado en:\n{ruta}")
            btn_abrir = msg.addButton("Abrir PDF", QMessageBox.ActionRole)
            msg.addButton("Cerrar", QMessageBox.RejectRole)
            msg.exec()
            if msg.clickedButton() == btn_abrir:
                _abrir_archivo(ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _exportar_excel_diario(self, date_edit=None):
        qd = (date_edit or self.rpt_dia_top).date()
        fecha = date(qd.year(), qd.month(), qd.day())
        try:
            ruta = finanzas_service.exportar_excel_reporte_diario(fecha=fecha)
            msg = QMessageBox(self)
            msg.setWindowTitle("Excel diario generado")
            msg.setText(f"Archivo guardado en:\n{ruta}")
            btn_abrir = msg.addButton("Abrir carpeta", QMessageBox.ActionRole)
            msg.addButton("Cerrar", QMessageBox.RejectRole)
            msg.exec()
            if msg.clickedButton() == btn_abrir:
                _abrir_carpeta(ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _exportar_excel(self):
        año, mes = self._get_año_mes_rpt()
        try:
            ruta = finanzas_service.exportar_excel_reporte(año=año, mes=mes or date.today().month)
            msg = QMessageBox(self)
            msg.setWindowTitle("Excel generado")
            msg.setText(f"Archivo guardado en:\n{ruta}")
            btn_abrir = msg.addButton("Abrir carpeta", QMessageBox.ActionRole)
            msg.addButton("Cerrar", QMessageBox.RejectRole)
            msg.exec()
            if msg.clickedButton() == btn_abrir:
                _abrir_carpeta(ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _exportar_pdf(self):
        año, mes = self._get_año_mes_rpt()
        try:
            ruta = finanzas_service.exportar_pdf_reporte(año=año, mes=mes or date.today().month)
            msg = QMessageBox(self)
            msg.setWindowTitle("PDF generado")
            msg.setText(f"Archivo guardado en:\n{ruta}")
            btn_abrir = msg.addButton("Abrir PDF", QMessageBox.ActionRole)
            msg.addButton("Cerrar", QMessageBox.RejectRole)
            msg.exec()
            if msg.clickedButton() == btn_abrir:
                _abrir_archivo(ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ─────────────────────────── helpers OS ──────────────────────────

def _abrir_carpeta(ruta):
    carpeta = os.path.dirname(ruta)
    if sys.platform == "win32":
        os.startfile(carpeta)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", carpeta])
    else:
        subprocess.Popen(["xdg-open", carpeta])


def _abrir_archivo(ruta):
    if sys.platform == "win32":
        os.startfile(ruta)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", ruta])
    else:
        subprocess.Popen(["xdg-open", ruta])
