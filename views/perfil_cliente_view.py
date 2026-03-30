"""Vista de perfil completo de cliente — KyoGym"""
from __future__ import annotations
from datetime import date, datetime
from calendar import monthrange

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFrame, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QSizePolicy, QTextEdit,
    QMessageBox, QCalendarWidget, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate, QRect, QSize
from PySide6.QtGui import (QFont, QColor, QPainter, QBrush,
                            QPen, QTextCharFormat, QPalette)

from services import perfil_cliente_service, asistencia_service
from services.membresia_service import calcular_estado_membresia
from utils.constants import ESTADO_ACTIVA, ESTADO_POR_VENCER, ESTADO_VENCIDA
from utils.table_styles import aplicar_estilo_tabla_moderna


# ─────────────────────── PALETA / HELPERS ────────────────────────
_COLOR_ACTIVA    = "#27ae60"
_COLOR_VENCER    = "#f39c12"
_COLOR_VENCIDA   = "#e74c3c"
_COLOR_SIN       = "#95a5a6"
_COLOR_AZUL      = "#2c6fad"
_COLOR_MORADO    = "#8e44ad"
_COLOR_FONDO     = "#f5f5f5"
_COLOR_CARD      = "#ffffff"
_COLOR_BORDE     = "#e0e0e0"
_COLOR_TEXT_PRI  = "#1a1a1a"
_COLOR_TEXT_SEC  = "#666666"
_ASIST_FILL      = QColor(39, 174, 96, 160)    # verde semitransparente
_PAGO_INDICATOR  = QColor(44, 111, 173, 200)   # azul para pagos
_TODAY_RING      = QColor(52, 73, 94)


def _color_estado(estado):
    return {
        ESTADO_ACTIVA:    _COLOR_ACTIVA,
        ESTADO_POR_VENCER: _COLOR_VENCER,
        ESTADO_VENCIDA:   _COLOR_VENCIDA,
    }.get(estado, _COLOR_SIN)


def _iniciales(nombre):
    partes = (nombre or "?").split()
    return "".join(p[0] for p in partes[:2]).upper()


def _fmt_fecha(f):
    if not f:
        return "—"
    try:
        d = date.fromisoformat(str(f))
        return d.strftime("%d/%m/%Y")
    except Exception:
        return str(f)


def _edad(fecha_nac_str):
    if not fecha_nac_str:
        return None
    try:
        nac = date.fromisoformat(fecha_nac_str)
        hoy = date.today()
        return hoy.year - nac.year - ((hoy.month, hoy.day) < (nac.month, nac.day))
    except Exception:
        return None


# ─────────────────────── CALENDARIO PERSONALIZADO ────────────────

class CalendarioAsistencia(QCalendarWidget):
    """QCalendarWidget que pinta en verde los días con asistencia
    y en azul los días con pago. Al hacer clic en un día con membresía
    activa marca/desmarca la asistencia."""

    def __init__(self, cliente_id, parent=None):
        super().__init__(parent)
        self.cliente_id = cliente_id
        self._dias_asistencia: set[int] = set()   # días del mes actual
        self._dias_pago: set[int] = set()
        self._anio = date.today().year
        self._mes = date.today().month
        self._tiene_membresia = False

        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        self.setNavigationBarVisible(True)
        self.setMinimumSize(380, 280)

        self._aplicar_estilo()
        self.currentPageChanged.connect(self._on_page_changed)
        self.clicked.connect(self._on_day_clicked)

    # ── estilos ───────────────────────────────────────────────────
    def _aplicar_estilo(self):
        self.setStyleSheet("""
            QCalendarWidget QAbstractItemView {
                background-color: #ffffff;
                selection-background-color: transparent;
                selection-color: #1a1a1a;
                color: #1a1a1a;
                font-size: 12px;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #2c3e50;
                padding: 4px;
            }
            QCalendarWidget QToolButton {
                color: #ffffff;
                background-color: transparent;
                font-size: 13px;
                font-weight: bold;
                border: none;
                padding: 4px 8px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #3d5166;
                border-radius: 4px;
            }
            QCalendarWidget QSpinBox {
                color: #ffffff;
                background-color: #2c3e50;
                font-size: 13px;
                border: none;
            }
            QCalendarWidget QMenu {
                color: #1a1a1a;
                background-color: #f5f5f5;
            }
            QCalendarWidget QAbstractItemView:enabled {
                color: #1a1a1a;
            }
            QCalendarWidget QAbstractItemView:disabled {
                color: #aaaaaa;
            }
        """)

    # ── datos ─────────────────────────────────────────────────────
    def cargar_mes(self, anio, mes, dias_asistencia: set[int],
                   dias_pago: set[int] = None, tiene_membresia=False):
        self._anio = anio
        self._mes = mes
        self._dias_asistencia = set(dias_asistencia)
        self._dias_pago = set(dias_pago or [])
        self._tiene_membresia = tiene_membresia
        self.updateCells()

    def _on_page_changed(self, anio, mes):
        """Señal emitida por el widget al navegar de mes."""
        self._anio = anio
        self._mes = mes
        if self.parent():
            perfil = self._find_perfil()
            if perfil:
                perfil._recargar_calendario(anio, mes)

    def _find_perfil(self):
        w = self.parent()
        while w:
            if isinstance(w, PerfilClienteDialog):
                return w
            w = w.parent() if hasattr(w, 'parent') else None
        return None

    def _on_day_clicked(self, qdate: QDate):
        """Marca o desmarca asistencia al hacer clic en un día."""
        if qdate.month() != self._mes or qdate.year() != self._anio:
            return
        dia = qdate.day()
        fecha = date(self._anio, self._mes, dia)
        # No permitir marcar en el futuro
        if fecha > date.today():
            return

        perfil = self._find_perfil()
        if not perfil:
            return

        if dia in self._dias_asistencia:
            # Desmarcar
            ok = asistencia_service.eliminar_asistencia(self.cliente_id, fecha)
            if ok:
                self._dias_asistencia.discard(dia)
        else:
            # Marcar — solo si tiene membresía o de todas formas si es manual
            ok, _ = asistencia_service.registrar_asistencia(
                self.cliente_id, fecha=fecha, origen="manual")
            if ok:
                self._dias_asistencia.add(dia)

        self.updateCells()
        if perfil:
            perfil._actualizar_stats_asistencia()
            perfil._recargar_tabla_asistencias()

    # ── paint ─────────────────────────────────────────────────────
    def paintCell(self, painter: QPainter, rect: QRect, qdate: QDate):
        painter.save()
        dia = qdate.day()
        es_mes_actual = (qdate.month() == self._mes and qdate.year() == self._anio)
        hoy = date.today()
        es_hoy = (qdate.toPython() == hoy)

        # Fondo base
        if not es_mes_actual:
            painter.fillRect(rect, QBrush(QColor("#f8f8f8")))
            painter.setPen(QColor("#cccccc"))
            painter.drawText(rect, Qt.AlignCenter, str(dia))
            painter.restore()
            return

        # Asistencia
        if dia in self._dias_asistencia:
            painter.fillRect(rect.adjusted(2, 2, -2, -2), QBrush(_ASIST_FILL))
        else:
            painter.fillRect(rect, QBrush(QColor("#ffffff")))

        # Indicador de pago (puntito azul arriba derecha)
        if dia in self._dias_pago:
            dot_r = 5
            painter.setBrush(QBrush(_PAGO_INDICATOR))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(rect.right() - dot_r * 2 - 1,
                                rect.top() + 2, dot_r * 2, dot_r * 2)

        # Borde de hoy
        if es_hoy:
            pen = QPen(_TODAY_RING, 2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 4, 4)

        # Texto del número
        color_num = QColor("#ffffff") if dia in self._dias_asistencia else QColor(_COLOR_TEXT_PRI)
        painter.setPen(color_num)
        font = painter.font()
        if es_hoy:
            font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, str(dia))

        painter.restore()


# ─────────────────────── TARJETA PEQUEÑA ────────────────────────

class MiniCard(QFrame):
    def __init__(self, titulo, valor="—", color=_COLOR_AZUL, icono=""):
        super().__init__()
        self.setFixedHeight(88)
        self.setStyleSheet(f"""
            QFrame {{
                background:{_COLOR_CARD}; border:1px solid {_COLOR_BORDE};
                border-radius:8px;
            }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)

        if icono:
            ic = QLabel(icono)
            ic.setFixedSize(38, 38)
            ic.setAlignment(Qt.AlignCenter)
            ic.setStyleSheet(f"background:{color}; border-radius:19px; font-size:18px;")
            lay.addWidget(ic)

        txt = QVBoxLayout()
        txt.setSpacing(2)
        self._lbl_titulo = QLabel(titulo)
        self._lbl_titulo.setStyleSheet(f"color:{_COLOR_TEXT_SEC}; font-size:11px;")
        self._lbl_valor = QLabel(str(valor))
        self._lbl_valor.setStyleSheet(
            f"color:{color}; font-size:20px; font-weight:bold; background:transparent;")
        self._lbl_valor.setWordWrap(True)
        txt.addWidget(self._lbl_titulo)
        txt.addWidget(self._lbl_valor)
        lay.addLayout(txt)
        lay.addStretch()

    def set_valor(self, v):
        self._lbl_valor.setText(str(v))

    def set_color(self, color):
        self._lbl_valor.setStyleSheet(
            f"color:{color}; font-size:20px; font-weight:bold; background:transparent;")


# ─────────────────────── DIALOG PRINCIPAL ────────────────────────

class PerfilClienteDialog(QDialog):
    """Diálogo de perfil completo de un cliente."""

    def __init__(self, cliente_id: int, parent=None):
        super().__init__(parent)
        self.cliente_id = cliente_id
        self._hoy = date.today()
        self._cal_anio = self._hoy.year
        self._cal_mes = self._hoy.month

        self.setWindowTitle("Perfil de Cliente")
        self.setMinimumSize(1100, 750)
        self.resize(1200, 820)
        self.setStyleSheet(f"QDialog {{ background:{_COLOR_FONDO}; }}")

        self._resumen = {}
        self._init_ui()
        self._cargar_todo()

    # ─────────────────────────────────────────────────────────────
    # UI BUILD
    # ─────────────────────────────────────────────────────────────

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Encabezado ─────────────────────────────────────────
        self._header = self._build_header()
        root.addWidget(self._header)

        # ── Cuerpo scrollable ──────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background:{_COLOR_FONDO}; border:none; }}")

        body_widget = QWidget()
        body_widget.setStyleSheet(f"background:{_COLOR_FONDO};")
        body_lay = QVBoxLayout(body_widget)
        body_lay.setContentsMargins(20, 16, 20, 20)
        body_lay.setSpacing(16)

        # Alertas
        self._alertas_frame = QFrame()
        self._alertas_frame.setVisible(False)
        body_lay.addWidget(self._alertas_frame)

        # Cards resumen
        body_lay.addWidget(self._build_cards_section())

        # Fila central: calendario + asistencias recientes
        centro = QHBoxLayout()
        centro.setSpacing(16)
        centro.addWidget(self._build_calendario_section(), 1)
        centro.addWidget(self._build_asistencias_section(), 1)
        body_lay.addLayout(centro)

        # Historial de pagos
        body_lay.addWidget(self._build_pagos_section())

        scroll.setWidget(body_widget)
        root.addWidget(scroll)

    # ── HEADER ───────────────────────────────────────────────────

    def _build_header(self):
        frame = QFrame()
        frame.setFixedHeight(130)
        frame.setStyleSheet("""
            QFrame { background: #2c3e50; }
        """)
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(20)

        # Avatar
        self._avatar_label = QLabel("?")
        self._avatar_label.setFixedSize(80, 80)
        self._avatar_label.setAlignment(Qt.AlignCenter)
        self._avatar_label.setStyleSheet("""
            QLabel {
                background-color: #3d5166;
                border-radius: 40px;
                color: #ffffff;
                font-size: 28px;
                font-weight: bold;
                border: 3px solid #c0c0c0;
            }
        """)
        lay.addWidget(self._avatar_label)

        # Info principal
        info_lay = QVBoxLayout()
        info_lay.setSpacing(4)
        self._lbl_nombre = QLabel("—")
        self._lbl_nombre.setStyleSheet(
            "color:#ffffff; font-size:22px; font-weight:bold;")
        self._lbl_sub = QLabel("—")
        self._lbl_sub.setStyleSheet("color:#aabbcc; font-size:13px;")
        self._lbl_reg = QLabel("—")
        self._lbl_reg.setStyleSheet("color:#aabbcc; font-size:12px;")
        info_lay.addWidget(self._lbl_nombre)
        info_lay.addWidget(self._lbl_sub)
        info_lay.addWidget(self._lbl_reg)
        lay.addLayout(info_lay)
        lay.addStretch()

        # Badge membresía
        badge_col = QVBoxLayout()
        badge_col.setSpacing(6)
        badge_col.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._lbl_membresia_estado = _badge_label("Sin membresía", _COLOR_SIN)
        self._lbl_membresia_plan   = QLabel("—")
        self._lbl_membresia_plan.setStyleSheet("color:#aabbcc; font-size:12px;")
        self._lbl_membresia_venc   = QLabel("—")
        self._lbl_membresia_venc.setStyleSheet("color:#aabbcc; font-size:12px;")

        badge_col.addWidget(self._lbl_membresia_estado, alignment=Qt.AlignRight)
        badge_col.addWidget(self._lbl_membresia_plan,   alignment=Qt.AlignRight)
        badge_col.addWidget(self._lbl_membresia_venc,   alignment=Qt.AlignRight)
        lay.addLayout(badge_col)

        # Botones acción
        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)

        self._btn_edit = _action_btn("✏️ Editar Cliente", "#555555")
        self._btn_cerrar = _action_btn("✖ Cerrar", "#7f8c8d")

        self._btn_edit.clicked.connect(self._on_editar_cliente)
        self._btn_cerrar.clicked.connect(self.close)

        for b in [self._btn_edit, self._btn_cerrar]:
            btn_col.addWidget(b)
        lay.addLayout(btn_col)

        return frame

    # ── ALERTAS ──────────────────────────────────────────────────

    def _rebuild_alertas(self, alertas):
        # Reemplazar el frame entero con uno nuevo para evitar problemas con shiboken
        parent_lay = self._alertas_frame.parentWidget().layout()
        if parent_lay is None:
            return
        idx = parent_lay.indexOf(self._alertas_frame)

        old = self._alertas_frame
        nuevo = QFrame()
        nuevo.setVisible(False)
        parent_lay.insertWidget(idx, nuevo)
        parent_lay.removeWidget(old)
        old.deleteLater()
        self._alertas_frame = nuevo

        if not alertas:
            return

        lay = QHBoxLayout(self._alertas_frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        for a in alertas:
            color_map = {"danger": "#fdeded", "warning": "#fff8e1", "info": "#e8f4fd"}
            border_map = {"danger": "#e74c3c", "warning": "#f39c12", "info": "#3498db"}
            bg    = color_map.get(a["tipo"], "#f5f5f5")
            borde = border_map.get(a["tipo"], "#cccccc")

            chip = QLabel(f"{a['icono']}  {a['mensaje']}")
            chip.setWordWrap(True)
            chip.setStyleSheet(f"""
                QLabel {{
                    background:{bg}; border:1px solid {borde}; border-radius:6px;
                    color:#333333; font-size:12px; padding:6px 10px;
                }}
            """)
            lay.addWidget(chip)

        lay.addStretch()
        self._alertas_frame.setVisible(True)

    # ── CARDS ─────────────────────────────────────────────────────

    def _build_cards_section(self):
        frame = QFrame()
        frame.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self._card_asist_mes   = MiniCard("Asistencias este mes", "—", _COLOR_ACTIVA, "📅")
        self._card_asist_ant   = MiniCard("Asistencias mes pasado", "—", _COLOR_TEXT_SEC, "📆")
        self._card_promedio    = MiniCard("Promedio mensual", "—", _COLOR_MORADO, "📊")
        self._card_dias_sin    = MiniCard("Días sin asistir", "—", _COLOR_VENCER, "⏳")
        self._card_ult_pago    = MiniCard("Último pago", "—", _COLOR_AZUL, "💳")
        self._card_total_pago  = MiniCard("Total pagado", "—", _COLOR_MORADO, "💰")
        self._card_total_asis  = MiniCard("Total asistencias", "—", _COLOR_ACTIVA, "🏋️")
        self._card_racha       = MiniCard("Racha actual", "—", _COLOR_ACTIVA, "🔥")

        for c in [self._card_asist_mes, self._card_asist_ant, self._card_promedio,
                  self._card_dias_sin, self._card_ult_pago, self._card_total_pago,
                  self._card_total_asis, self._card_racha]:
            lay.addWidget(c)

        return frame

    # ── CALENDARIO ───────────────────────────────────────────────

    def _build_calendario_section(self):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{ background:{_COLOR_CARD}; border:1px solid {_COLOR_BORDE};
                      border-radius:8px; }}
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        # Título + leyenda
        top = QHBoxLayout()
        lbl_t = QLabel("📅 Asistencias")
        lbl_t.setStyleSheet(f"color:{_COLOR_TEXT_PRI}; font-size:14px; font-weight:bold;")
        top.addWidget(lbl_t)
        top.addStretch()

        leyenda = QHBoxLayout()
        leyenda.setSpacing(6)
        for color, texto in [("#27ae60", "Asistió"), ("#2c6fad", "Pago")]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{color}; font-size:14px;")
            t = QLabel(texto)
            t.setStyleSheet(f"color:{_COLOR_TEXT_SEC}; font-size:11px;")
            leyenda.addWidget(dot)
            leyenda.addWidget(t)
        top.addLayout(leyenda)
        lay.addLayout(top)

        # Leyenda de instrucción
        lbl_ayuda = QLabel("Haz clic en un día para marcar/desmarcar asistencia")
        lbl_ayuda.setStyleSheet(f"color:{_COLOR_TEXT_SEC}; font-size:11px; font-style:italic;")
        lay.addWidget(lbl_ayuda)

        self._calendario = CalendarioAsistencia(self.cliente_id, parent=self)
        lay.addWidget(self._calendario)

        # Contador del mes
        self._lbl_cal_resumen = QLabel("")
        self._lbl_cal_resumen.setStyleSheet(
            f"color:{_COLOR_TEXT_SEC}; font-size:12px; padding-top:4px;")
        self._lbl_cal_resumen.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._lbl_cal_resumen)

        return frame

    # ── ASISTENCIAS RECIENTES ─────────────────────────────────────

    def _build_asistencias_section(self):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{ background:{_COLOR_CARD}; border:1px solid {_COLOR_BORDE};
                      border-radius:8px; }}
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        # Stats rápidas
        stats_row = QHBoxLayout()
        self._lbl_ultima_asist = _stat_label("Fecha", "—")
        self._lbl_total_asist  = _stat_label("Total asistencias", "—")
        self._lbl_mes_activo   = _stat_label("Mes más activo", "—")
        self._lbl_racha_label  = _stat_label("Racha actual", "—")
        for w in [self._lbl_ultima_asist, self._lbl_total_asist,
                  self._lbl_mes_activo, self._lbl_racha_label]:
            stats_row.addWidget(w)
        lay.addLayout(stats_row)

        lbl_t = QLabel("🗂 Asistencias recientes")
        lbl_t.setStyleSheet(
            f"color:{_COLOR_TEXT_PRI}; font-size:14px; font-weight:bold; padding-top:6px;")
        lay.addWidget(lbl_t)

        self._tabla_asist = QTableWidget()
        self._tabla_asist.setColumnCount(1)
        self._tabla_asist.setHorizontalHeaderLabels(["Fecha"])
        self._tabla_asist.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tabla_asist.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabla_asist.setSelectionMode(QAbstractItemView.NoSelection)
        self._tabla_asist.setAlternatingRowColors(False)
        self._tabla_asist.verticalHeader().setVisible(False)
        self._tabla_asist.setMaximumHeight(260)
        aplicar_estilo_tabla_moderna(self._tabla_asist)
        lay.addWidget(self._tabla_asist)

        return frame

    # ── PAGOS ─────────────────────────────────────────────────────

    def _build_pagos_section(self):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{ background:{_COLOR_CARD}; border:1px solid {_COLOR_BORDE};
                      border-radius:8px; }}
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        # Mini-resumen pagos
        top_row = QHBoxLayout()
        self._lbl_ult_pago_det  = _stat_label("Último pago", "—")
        self._lbl_total_pagado  = _stat_label("Total pagado", "—", _COLOR_ACTIVA)
        self._lbl_cant_pagos    = _stat_label("Cant. pagos", "—")
        self._lbl_prox_venc     = _stat_label("Próximo vencimiento", "—")
        for w in [self._lbl_ult_pago_det, self._lbl_total_pagado,
                  self._lbl_cant_pagos, self._lbl_prox_venc]:
            top_row.addWidget(w)
        top_row.addStretch()
        lay.addLayout(top_row)

        lbl_t = QLabel("💳 Historial de Pagos")
        lbl_t.setStyleSheet(
            f"color:{_COLOR_TEXT_PRI}; font-size:14px; font-weight:bold; padding-top:6px;")
        lay.addWidget(lbl_t)

        self._tabla_pagos = QTableWidget()
        self._tabla_pagos.setColumnCount(6)
        self._tabla_pagos.setHorizontalHeaderLabels(
            ["Fecha", "Concepto", "Monto", "Método", "Membresía", "Venc. Membresía"])
        self._tabla_pagos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tabla_pagos.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabla_pagos.setSelectionMode(QAbstractItemView.NoSelection)
        self._tabla_pagos.setAlternatingRowColors(False)
        self._tabla_pagos.verticalHeader().setVisible(False)
        self._tabla_pagos.setMaximumHeight(240)
        aplicar_estilo_tabla_moderna(self._tabla_pagos)
        lay.addWidget(self._tabla_pagos)

        return frame

    # ─────────────────────────────────────────────────────────────
    # CARGA DE DATOS
    # ─────────────────────────────────────────────────────────────

    def _cargar_todo(self):
        self._resumen = perfil_cliente_service.obtener_resumen_cliente(self.cliente_id)
        self._poblar_header()
        self._poblar_cards()
        self._recargar_calendario(self._cal_anio, self._cal_mes)
        self._recargar_tabla_asistencias()
        self._recargar_tabla_pagos()
        alertas = perfil_cliente_service.obtener_alertas_cliente(self.cliente_id)
        self._rebuild_alertas(alertas)

    # ── HEADER ───────────────────────────────────────────────────

    def _poblar_header(self):
        r = self._resumen
        nombre = r.get("nombre", "")
        self._avatar_label.setText(_iniciales(nombre))
        self._lbl_nombre.setText(nombre)

        partes_sub = []
        if r.get("telefono"):
            partes_sub.append(f"📞 {r['telefono']}")
        if r.get("email"):
            partes_sub.append(f"✉ {r['email']}")
        edad = _edad(r.get("fecha_nacimiento"))
        if edad:
            partes_sub.append(f"🎂 {edad} años")
        if r.get("sexo"):
            partes_sub.append(r["sexo"])
        self._lbl_sub.setText("   ".join(partes_sub) or "—")

        reg = r.get("fecha_registro")
        self._lbl_reg.setText(f"Registrado: {_fmt_fecha(reg)}")

        estado = r.get("estado_membresia", "Sin membresía")
        if estado == ESTADO_VENCIDA:
            display_estado = "Sin membresía"
            color = _COLOR_SIN
        else:
            display_estado = estado
            color = _color_estado(estado)
        self._lbl_membresia_estado.setText(f"  {display_estado}  ")
        self._lbl_membresia_estado.setStyleSheet(f"""
            QLabel {{
                background:{color}; color:#ffffff; padding:4px 10px;
                border-radius:10px; font-size:12px; font-weight:bold;
            }}
        """)
        self._lbl_membresia_plan.setText(f"Plan: {r.get('plan_actual', '—')}")
        venc = r.get("proximo_vencimiento")
        self._lbl_membresia_venc.setText(
            f"Vence: {_fmt_fecha(venc)}" if venc else "Sin vencimiento")

    # ── CARDS ─────────────────────────────────────────────────────

    def _poblar_cards(self):
        r = self._resumen
        self._card_asist_mes.set_valor(r.get("asist_este_mes", 0))
        self._card_asist_ant.set_valor(r.get("asist_mes_pasado", 0))
        self._card_promedio.set_valor(r.get("promedio_mensual", 0))

        dias_sin = r.get("dias_sin_asistir")
        self._card_dias_sin.set_valor("—" if dias_sin is None else dias_sin)
        if dias_sin is not None:
            col = _COLOR_VENCIDA if dias_sin >= 30 else (
                _COLOR_VENCER if dias_sin >= 14 else _COLOR_ACTIVA)
            self._card_dias_sin.set_color(col)

        self._card_ult_pago.set_valor(_fmt_fecha(r.get("ultimo_pago_fecha")))
        total = r.get("total_pagado", 0)
        self._card_total_pago.set_valor(f"${total:,.2f}")
        self._card_total_asis.set_valor(r.get("total_asistencias", 0))

        racha = r.get("racha_actual", 0)
        self._card_racha.set_valor(racha)

    def _actualizar_stats_asistencia(self):
        """Recalcula stats de asistencia tras marcar en el calendario."""
        self._resumen = perfil_cliente_service.obtener_resumen_cliente(self.cliente_id)
        r = self._resumen
        self._card_asist_mes.set_valor(r.get("asist_este_mes", 0))
        self._card_total_asis.set_valor(r.get("total_asistencias", 0))
        dias_sin = r.get("dias_sin_asistir")
        self._card_dias_sin.set_valor("—" if dias_sin is None else dias_sin)
        racha = r.get("racha_actual", 0)
        self._card_racha.set_valor(racha)
        # stats panel
        self._lbl_ultima_asist.findChild(QLabel).setText(
            _fmt_fecha(r.get("ultima_asistencia")))
        self._lbl_total_asist.findChild(QLabel).setText(str(r.get("total_asistencias", 0)))
        self._lbl_racha_label.findChild(QLabel).setText(
            f"{racha} día(s)")

    # ── CALENDARIO ───────────────────────────────────────────────

    def _recargar_calendario(self, anio, mes):
        self._cal_anio = anio
        self._cal_mes  = mes

        dias_asis = asistencia_service.dias_con_asistencia_mes(
            self.cliente_id, anio, mes)

        # Días con pago en ese mes
        from db import get_connection as _gconn
        from datetime import date as _date
        ult_dia = monthrange(anio, mes)[1]
        conn = _gconn()
        cur = conn.cursor()
        cur.execute("""
            SELECT fecha FROM pagos
            WHERE cliente_id=? AND fecha BETWEEN ? AND ?
        """, (self.cliente_id,
              _date(anio, mes, 1).isoformat(),
              _date(anio, mes, ult_dia).isoformat()))
        dias_pago = {_date.fromisoformat(r["fecha"]).day for r in cur.fetchall()}
        conn.close()

        tiene_membresia = bool(self._resumen.get("membresia_activa"))
        self._calendario.cargar_mes(anio, mes, dias_asis, dias_pago, tiene_membresia)

        # Navegar el widget al mes correcto si es diferente
        q_actual = self._calendario.yearShown() * 100 + self._calendario.monthShown()
        if q_actual != anio * 100 + mes:
            self._calendario.setCurrentPage(anio, mes)

        cnt = len(dias_asis)
        total_dias = ult_dia
        self._lbl_cal_resumen.setText(
            f"{cnt} asistencia(s) en {_nombre_mes(mes)} {anio}")

    # ── TABLA ASISTENCIAS ─────────────────────────────────────────

    def _recargar_tabla_asistencias(self):
        r = self._resumen
        # Stats rápidas
        _set_stat(self._lbl_ultima_asist, _fmt_fecha(r.get("ultima_asistencia")))
        _set_stat(self._lbl_total_asist, str(r.get("total_asistencias", 0)))
        _set_stat(self._lbl_mes_activo,  r.get("mes_mas_activo") or "—")
        racha = r.get("racha_actual", 0)
        _set_stat(self._lbl_racha_label, f"{racha} día(s)")

        asistencias = asistencia_service.listar_asistencias_recientes(
            self.cliente_id, limite=30)
        t = self._tabla_asist
        t.setRowCount(len(asistencias))
        for i, a in enumerate(asistencias):
            t.setRowHeight(i, 36)
            item = QTableWidgetItem(_fmt_fecha(a["fecha"]))
            item.setForeground(QColor(_COLOR_TEXT_PRI))
            t.setItem(i, 0, item)

    # ── TABLA PAGOS ───────────────────────────────────────────────

    def _recargar_tabla_pagos(self):
        r = self._resumen
        _set_stat(self._lbl_ult_pago_det,
                  f"{_fmt_fecha(r.get('ultimo_pago_fecha'))}  ${r.get('ultimo_pago_monto', 0):,.2f}")
        _set_stat(self._lbl_total_pagado,
                  f"${r.get('total_pagado', 0):,.2f}", _COLOR_ACTIVA)
        _set_stat(self._lbl_cant_pagos,
                  str(r.get("cantidad_pagos", 0)))
        _set_stat(self._lbl_prox_venc,
                  _fmt_fecha(r.get("proximo_vencimiento")))

        pagos = perfil_cliente_service.obtener_pagos_cliente(self.cliente_id)
        t = self._tabla_pagos
        t.setRowCount(len(pagos))
        for i, p in enumerate(pagos):
            t.setRowHeight(i, 36)
            vals = [
                _fmt_fecha(p.get("fecha")),
                p.get("concepto") or "—",
                f"${p.get('monto', 0):,.2f}",
                p.get("metodo") or "—",
                p.get("membresia_tipo") or "—",
                _fmt_fecha(p.get("membresia_vencimiento")),
            ]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                color = (_COLOR_ACTIVA if col == 2 else
                         _COLOR_TEXT_SEC if col in (4, 5) else _COLOR_TEXT_PRI)
                item.setForeground(QColor(color))
                t.setItem(i, col, item)

    # ─────────────────────────────────────────────────────────────
    # ACCIONES
    # ─────────────────────────────────────────────────────────────

    def _on_registrar_pago(self):
        """Abre el diálogo de pagos pre-cargado con este cliente."""
        try:
            from views.pagos_view import AgregarPagoDialog
            dlg = AgregarPagoDialog(self, cliente_preseleccionado=self._resumen)
            if dlg.exec():
                self._cargar_todo()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_registrar_membresia(self):
        """Abre el diálogo de membresía pre-cargado."""
        try:
            from views.membresias_view import AgregarMembresiaDialog
            dlg = AgregarMembresiaDialog(self, cliente_preseleccionado=self._resumen)
            if dlg.exec():
                self._cargar_todo()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_editar_cliente(self):
        """Abre el diálogo de edición del cliente."""
        try:
            from services import cliente_service
            from views.clientes_view import AgregarClienteDialog
            cliente = cliente_service.obtener_cliente(self.cliente_id)
            dlg = AgregarClienteDialog(self, cliente=cliente)
            if dlg.exec():
                datos = dlg.obtener_datos()
                cliente_service.actualizar_cliente(
                    self.cliente_id, datos["nombre"], datos["telefono"],
                    datos["sexo"], datos["fecha_nacimiento"], datos["email"])
                self._cargar_todo()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ─────────────────────── HELPERS PRIVADOS ────────────────────────

def _badge_label(texto, color):
    lbl = QLabel(texto)
    lbl.setStyleSheet(f"""
        QLabel {{
            background:{color}; color:#ffffff; padding:4px 10px;
            border-radius:10px; font-size:12px; font-weight:bold;
        }}
    """)
    return lbl


def _action_btn(texto, color):
    btn = QPushButton(texto)
    btn.setStyleSheet(f"""
        QPushButton {{
            background:{color}; color:#ffffff; padding:5px 12px;
            border:none; border-radius:4px; font-size:12px; font-weight:bold;
        }}
        QPushButton:hover {{ opacity:0.85; }}
    """)
    btn.setFixedWidth(170)
    return btn


def _stat_label(titulo, valor, color_val=None):
    """Crea un QFrame con título y valor. Devuelve el frame."""
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{ background:#f8f8f8; border:1px solid {_COLOR_BORDE};
                  border-radius:6px; }}
    """)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(10, 6, 10, 6)
    lay.setSpacing(1)
    lt = QLabel(titulo)
    lt.setStyleSheet(f"color:{_COLOR_TEXT_SEC}; font-size:10px;")
    lv = QLabel(valor)
    lv.setObjectName("valor")
    cv = color_val or _COLOR_TEXT_PRI
    lv.setStyleSheet(f"color:{cv}; font-size:13px; font-weight:bold; background:transparent;")
    lay.addWidget(lt)
    lay.addWidget(lv)
    return frame


def _set_stat(frame: QFrame, valor: str, color=None):
    lv = frame.findChild(QLabel, "valor")
    if lv:
        lv.setText(valor)
        if color:
            lv.setStyleSheet(
                f"color:{color}; font-size:13px; font-weight:bold; background:transparent;")


def _nombre_mes(mes: int) -> str:
    return ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
            "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"][mes - 1]
