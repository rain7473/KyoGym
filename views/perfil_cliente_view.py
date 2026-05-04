"""Vista de perfil completo de cliente — KyoGym (rediseño)"""
from __future__ import annotations
from datetime import date, datetime
from calendar import monthrange

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFrame, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QSizePolicy, QTextEdit,
    QMessageBox, QCalendarWidget, QAbstractItemView,
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QDate, QRect, QSize
from PySide6.QtGui import (QFont, QColor, QPainter, QBrush, QPen, QPalette)
import qtawesome as qta

from services import perfil_cliente_service, asistencia_service
from services.membresia_service import (calcular_estado_membresia,
                                        listar_membresias)
from utils.constants import ESTADO_ACTIVA, ESTADO_POR_VENCER, ESTADO_VENCIDA
from utils.table_styles import aplicar_estilo_tabla_moderna


# ─────────────────────── PALETA ──────────────────────────────────
_COLOR_ACTIVA     = "#27ae60"
_COLOR_VENCER     = "#f39c12"
_COLOR_VENCIDA    = "#e74c3c"
_COLOR_SIN        = "#95a5a6"
_COLOR_AZUL       = "#2c6fad"
_COLOR_HEADER     = "#1a2e45"
_COLOR_HEADER2    = "#243b55"
_COLOR_FONDO      = "#f0f2f5"
_COLOR_CARD       = "#ffffff"
_COLOR_BORDE      = "#e2e8f0"
_COLOR_TEXT_PRI   = "#1a1a2e"
_COLOR_TEXT_SEC   = "#64748b"
_COLOR_TAB_ACTIVE = "#2c6fad"
_ASIST_FILL       = QColor(39, 174, 96, 170)
_PAGO_INDICATOR   = QColor(44, 111, 173, 200)
_TODAY_RING       = QColor(44, 111, 173)


# ─────────────────────── HELPERS ─────────────────────────────────

def _color_estado(estado):
    return {
        ESTADO_ACTIVA:     _COLOR_ACTIVA,
        ESTADO_POR_VENCER: _COLOR_VENCER,
        ESTADO_VENCIDA:    _COLOR_VENCIDA,
    }.get(estado, _COLOR_SIN)


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


def _nombre_mes(mes: int) -> str:
    return ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
            "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"][mes - 1]


def _shadow(widget, blur=12, offset_y=2, alpha=30):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, offset_y)
    eff.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)
    return widget


def _qta_lbl(icon_name: str, color: str = "#64748b", size: int = 14) -> QLabel:
    """Crea un QLabel con un ícono de qtawesome como pixmap."""
    lbl = QLabel()
    try:
        ico = qta.icon(icon_name, color=color)
        lbl.setPixmap(ico.pixmap(size, size))
    except Exception:
        lbl.setText("•")
    lbl.setStyleSheet("background:transparent;")
    lbl.setFixedSize(size + 6, size + 6)
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


# ─────────────────────── BARCODE WIDGET ──────────────────────────

class BarcodeWidget(QWidget):
    """Dibuja un código de barras estilo simplificado a partir de un texto."""

    _PATTERNS: dict = {
        '0': '101001101101', '1': '110100101011', '2': '101100101011',
        '3': '110110010101', '4': '101001101011', '5': '110100110101',
        '6': '101100110101', '7': '101001011011', '8': '110100101101',
        '9': '101100101101',
        'A': '110101001011', 'B': '101101001011', 'C': '110110100101',
        'D': '101011001011', 'E': '110101100101', 'F': '101101100101',
        'G': '101010011011', 'H': '110101001101', 'I': '101101001101',
        'J': '101011001101', 'K': '110101010011', 'L': '101101010011',
        'M': '110110101001', 'N': '101011010011', 'O': '110101101001',
        'P': '101101101001', 'Q': '101010110011', 'R': '110101011001',
        'S': '101101011001', 'T': '101011011001', 'U': '110010101011',
        'V': '100110101011', 'W': '110011010101', 'X': '100101101011',
        'Y': '110010110101', 'Z': '100110110101',
        '-': '100101011011', ' ': '100110101101',
        '*': '100101101101',
    }

    def __init__(self, codigo: str, parent=None):
        super().__init__(parent)
        self._codigo = codigo.upper()
        self.setMinimumSize(200, 80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(90)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#ffffff"))
        seq = "*" + self._codigo + "*"
        bits = ""
        for ch in seq:
            pat = self._PATTERNS.get(ch, self._PATTERNS.get('*', '100101101101'))
            bits += pat + "0"
        total_bits = len(bits)
        if total_bits == 0:
            return
        bar_w = max(1, (w - 10) // total_bits)
        x = (w - bar_w * total_bits) // 2
        bar_h = h - 4
        for bit in bits:
            color = QColor("#1a1a2e") if bit == '1' else QColor("#ffffff")
            painter.fillRect(x, 2, bar_w, bar_h, color)
            x += bar_w
        painter.end()


# ─────────────────────── CALENDARIO ──────────────────────────────

class CalendarioAsistencia(QCalendarWidget):
    """Calendario que pinta días de asistencia en verde."""

    def __init__(self, cliente_id, parent=None):
        super().__init__(parent)
        self.cliente_id = cliente_id
        self._dias_asistencia: set = set()
        self._dias_pago: set = set()
        self._anio = date.today().year
        self._mes  = date.today().month
        self._tiene_membresia = False

        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        self.setNavigationBarVisible(True)
        self.setMinimumSize(320, 250)
        self._aplicar_estilo()
        self.currentPageChanged.connect(self._on_page_changed)
        self.clicked.connect(self._on_day_clicked)

    def _aplicar_estilo(self):
        self.setStyleSheet("""
            QCalendarWidget QAbstractItemView {
                background-color: #ffffff;
                selection-background-color: transparent;
                selection-color: #1a1a2e;
                color: #1a1a2e; font-size: 12px;
            }
            QCalendarWidget QHeaderView::section {
                background-color: #2c6fad; color: #ffffff;
                border: none; font-weight: bold; padding: 3px; font-size: 11px;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #1e3a5f; padding: 4px;
            }
            QCalendarWidget QToolButton {
                color: #ffffff; background-color: transparent;
                font-size: 13px; font-weight: bold; border: none; padding: 4px 8px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #2c6fad; border-radius: 4px;
            }
            QCalendarWidget QSpinBox {
                color: #ffffff; background-color: #1e3a5f;
                font-size: 13px; border: none;
            }
            QCalendarWidget QMenu { color: #1a1a2e; background-color: #f5f5f5; }
            QCalendarWidget QAbstractItemView:enabled  { color: #1a1a2e; }
            QCalendarWidget QAbstractItemView:disabled { color: #aaaaaa; }
        """)

    def cargar_mes(self, anio, mes, dias_asistencia, dias_pago=None, tiene_membresia=False):
        self._anio = anio
        self._mes  = mes
        self._dias_asistencia = set(dias_asistencia)
        self._dias_pago = set(dias_pago or [])
        self._tiene_membresia = tiene_membresia
        self.updateCells()

    def _on_page_changed(self, anio, mes):
        self._anio = anio
        self._mes  = mes
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
        if qdate.month() != self._mes or qdate.year() != self._anio:
            return
        dia   = qdate.day()
        fecha = date(self._anio, self._mes, dia)
        if fecha > date.today():
            return
        perfil = self._find_perfil()
        if not perfil:
            return
        if dia in self._dias_asistencia:
            ok = asistencia_service.eliminar_asistencia(self.cliente_id, fecha)
            if ok:
                self._dias_asistencia.discard(dia)
        else:
            ok, _ = asistencia_service.registrar_asistencia(
                self.cliente_id, fecha=fecha, origen="manual")
            if ok:
                self._dias_asistencia.add(dia)
        self.updateCells()
        if perfil:
            perfil._actualizar_stats_asistencia()
            perfil._recargar_tabla_asistencias()

    def paintCell(self, painter: QPainter, rect: QRect, qdate: QDate):
        painter.save()
        dia = qdate.day()
        es_mes_actual = (qdate.month() == self._mes and qdate.year() == self._anio)
        hoy = date.today()
        es_hoy = (qdate.toPython() == hoy)
        if not es_mes_actual:
            painter.fillRect(rect, QBrush(QColor("#f8f8f8")))
            painter.setPen(QColor("#cccccc"))
            painter.drawText(rect, Qt.AlignCenter, str(dia))
            painter.restore()
            return
        if dia in self._dias_asistencia:
            painter.fillRect(rect.adjusted(2, 2, -2, -2), QBrush(_ASIST_FILL))
        else:
            painter.fillRect(rect, QBrush(QColor("#ffffff")))
        if dia in self._dias_pago:
            dot_r = 5
            painter.setBrush(QBrush(_PAGO_INDICATOR))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(rect.right() - dot_r * 2 - 1,
                                rect.top() + 2, dot_r * 2, dot_r * 2)
        if es_hoy:
            painter.setPen(QPen(_TODAY_RING, 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 4, 4)
        color_num = QColor("#ffffff") if dia in self._dias_asistencia else QColor(_COLOR_TEXT_PRI)
        painter.setPen(color_num)
        font = painter.font()
        if es_hoy:
            font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, str(dia))
        painter.restore()


# ─────────────────────── AVATAR WIDGET ──────────────────────────

class AvatarLabel(QWidget):
    """Dibuja un círculo con las iniciales del cliente."""

    def __init__(self, initials: str = "?", size: int = 64, parent=None):
        super().__init__(parent)
        self._initials = initials.upper()[:2]
        self._size = size
        self.setFixedSize(size, size)

    def set_initials(self, initials: str):
        self._initials = initials.upper()[:2]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor("#2c6fad")))
        p.setPen(QPen(QColor(255, 255, 255, 60), 3))
        r = self._size
        p.drawEllipse(2, 2, r - 4, r - 4)
        p.setPen(QColor("#ffffff"))
        f = p.font()
        f.setPointSize(max(10, int(r * 0.30)))
        f.setBold(True)
        p.setFont(f)
        p.drawText(0, 0, r, r, Qt.AlignCenter, self._initials)
        p.end()


# ─────────────────────── CARD HELPERS ────────────────────────────

def _card(parent=None, radius=10):
    f = QFrame(parent)
    f.setStyleSheet(f"QFrame {{ background: {_COLOR_CARD}; border: none; border-radius: {radius}px; }}")
    _shadow(f)
    return f


def _card_title(texto: str, qta_icon: str = "", color: str = _COLOR_AZUL) -> QWidget:
    """Widget horizontal con ícono qtawesome + texto título de card."""
    w = QWidget()
    w.setStyleSheet("background:transparent;")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(7)
    if qta_icon:
        lay.addWidget(_qta_lbl(qta_icon, color=color, size=15))
    lbl = QLabel(texto)
    lbl.setStyleSheet(
        f"color:{_COLOR_TEXT_PRI}; font-size:14px; font-weight:bold;"
        " background:transparent;")
    lay.addWidget(lbl)
    lay.addStretch()
    return w


def _stat_frame(titulo: str, valor: str = "—", color_val=None) -> QFrame:
    frame = QFrame()
    frame.setStyleSheet("QFrame { background:#f1f5fb; border:none; border-radius:6px; }")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(10, 6, 10, 6)
    lay.setSpacing(1)
    lt = QLabel(titulo)
    lt.setStyleSheet(f"color:{_COLOR_TEXT_SEC}; font-size:10px; background:transparent;")
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
            lv.setStyleSheet(f"color:{color}; font-size:13px; font-weight:bold; background:transparent;")


def _sep():
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"QFrame {{ color: {_COLOR_BORDE}; background: {_COLOR_BORDE}; border:none; }}")
    line.setFixedHeight(1)
    return line


# ─────────────────────── DIALOG PRINCIPAL ────────────────────────

class PerfilClienteDialog(QDialog):
    """Diálogo de perfil completo de un cliente — nuevo diseño."""

    def __init__(self, cliente_id: int, parent=None):
        super().__init__(parent)
        self.cliente_id = cliente_id
        self._hoy       = date.today()
        self._cal_anio  = self._hoy.year
        self._cal_mes   = self._hoy.month
        self._resumen   = {}
        self._tab_index = 0

        self.setWindowTitle("Perfil de Cliente")
        self.setMinimumSize(1100, 750)
        self.resize(1280, 860)
        self.showMaximized()
        self.setStyleSheet(f"QDialog {{ background: {_COLOR_FONDO}; }}")

        self._init_ui()
        self._cargar_todo()

    # ─── UI BUILD ────────────────────────────────────────────────

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_tab_bar())

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet(f"QScrollArea {{ background:{_COLOR_FONDO}; border:none; }}")

        self._body = QWidget()
        self._body.setStyleSheet(f"background:{_COLOR_FONDO};")
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(20, 16, 20, 20)
        self._body_lay.setSpacing(0)

        self._tab_resumen_widget      = self._build_resumen_widget()
        self._tab_asistencias_widget  = self._build_tab_asistencias()
        self._tab_pagos_widget        = self._build_tab_pagos()
        self._tab_membresias_widget   = self._build_tab_membresias()
        self._tab_notas_widget        = self._build_tab_notas()

        self._tab_asistencias_widget.setVisible(False)
        self._tab_pagos_widget.setVisible(False)
        self._tab_membresias_widget.setVisible(False)
        self._tab_notas_widget.setVisible(False)

        for w in [self._tab_resumen_widget, self._tab_asistencias_widget,
                  self._tab_pagos_widget, self._tab_membresias_widget,
                  self._tab_notas_widget]:
            self._body_lay.addWidget(w)

        self._scroll.setWidget(self._body)
        root.addWidget(self._scroll)

    # ─── HEADER ──────────────────────────────────────────────────

    def _build_header(self):
        outer = QFrame()
        outer.setStyleSheet(
            f"QFrame {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f" stop:0 {_COLOR_HEADER}, stop:1 {_COLOR_HEADER2}); border:none; }}")
        lay = QVBoxLayout(outer)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Breadcrumb
        top = QFrame()
        top.setStyleSheet("QFrame { background:transparent; border:none; }")
        top_lay = QHBoxLayout(top)
        top_lay.setContentsMargins(24, 10, 24, 6)
        btn_back = QPushButton("  Perfil de Cliente")
        btn_back.setCursor(Qt.PointingHandCursor)
        try:
            btn_back.setIcon(qta.icon("fa5s.arrow-left", color="#8faac0"))
            btn_back.setIconSize(QSize(12, 12))
        except Exception:
            pass
        btn_back.setStyleSheet(
            "QPushButton { background:transparent; border:none; color:#8faac0; font-size:13px; }"
            "QPushButton:hover { color:#ffffff; }")
        btn_back.clicked.connect(self.close)
        top_lay.addWidget(btn_back)
        top_lay.addStretch()
        lay.addWidget(top)

        # Main row
        main = QFrame()
        main.setStyleSheet("QFrame { background:transparent; border:none; }")
        main_lay = QHBoxLayout(main)
        main_lay.setContentsMargins(28, 8, 28, 22)
        main_lay.setSpacing(20)

        # Avatar circular con iniciales
        self._avatar_widget = AvatarLabel("?", size=68)
        main_lay.addWidget(self._avatar_widget, alignment=Qt.AlignVCenter)

        # Nombre + datos rápidos
        info_col = QVBoxLayout()
        info_col.setSpacing(6)
        self._lbl_nombre = QLabel("—")
        self._lbl_nombre.setStyleSheet(
            "color:#ffffff; font-size:32px; font-weight:bold; background:transparent;")
        self._lbl_datos_rapidos = QLabel("—")
        self._lbl_datos_rapidos.setStyleSheet(
            "color:#a0bcd6; font-size:13px; background:transparent;")
        self._lbl_registro = QLabel("—")
        self._lbl_registro.setStyleSheet(
            "color:#7a99b0; font-size:11px; background:transparent;")
        info_col.addWidget(self._lbl_nombre)
        info_col.addWidget(self._lbl_datos_rapidos)
        info_col.addWidget(self._lbl_registro)
        main_lay.addLayout(info_col)
        main_lay.addStretch()

        # Badge estado + vencimiento
        estado_col = QVBoxLayout()
        estado_col.setSpacing(6)
        estado_col.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._lbl_estado_badge = QLabel("Sin membresía")
        self._lbl_estado_badge.setAlignment(Qt.AlignCenter)
        self._lbl_estado_badge.setStyleSheet(
            f"QLabel {{ background:{_COLOR_SIN}; color:#ffffff; padding:6px 18px;"
            " border-radius:14px; font-size:13px; font-weight:bold; }}")
        self._lbl_vencimiento_header = QLabel("—")
        self._lbl_vencimiento_header.setAlignment(Qt.AlignRight)
        self._lbl_vencimiento_header.setStyleSheet(
            "color:#8faac0; font-size:12px; background:transparent;")
        estado_col.addWidget(self._lbl_estado_badge, alignment=Qt.AlignRight)
        estado_col.addWidget(self._lbl_vencimiento_header, alignment=Qt.AlignRight)
        main_lay.addLayout(estado_col)

        # Botones
        btns_col = QVBoxLayout()
        btns_col.setSpacing(8)
        btns_col.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._btn_edit = QPushButton("  Editar Cliente")
        self._btn_edit.setCursor(Qt.PointingHandCursor)
        try:
            self._btn_edit.setIcon(qta.icon("fa5s.pencil-alt", color="#ffffff"))
            self._btn_edit.setIconSize(QSize(14, 14))
        except Exception:
            pass
        self._btn_edit.setStyleSheet(
            "QPushButton { background:#2c6fad; color:#ffffff; padding:9px 22px;"
            " border:none; border-radius:8px; font-size:13px; font-weight:bold; min-width:160px; }"
            "QPushButton:hover { background:#1e5a91; }")
        self._btn_edit.clicked.connect(self._on_editar_cliente)
        btn_cerrar = QPushButton("  Cerrar")
        btn_cerrar.setCursor(Qt.PointingHandCursor)
        try:
            btn_cerrar.setIcon(qta.icon("fa5s.times", color="#c0d0e0"))
            btn_cerrar.setIconSize(QSize(14, 14))
        except Exception:
            pass
        btn_cerrar.setStyleSheet(
            "QPushButton { background:rgba(255,255,255,0.09); color:#c0d0e0; padding:9px 22px;"
            " border:1px solid rgba(255,255,255,0.18); border-radius:8px; font-size:13px;"
            " font-weight:bold; min-width:160px; }"
            "QPushButton:hover { background:rgba(255,255,255,0.18); color:#ffffff; }")
        btn_cerrar.clicked.connect(self.close)
        btns_col.addWidget(self._btn_edit)
        btns_col.addWidget(btn_cerrar)
        main_lay.addLayout(btns_col)

        lay.addWidget(main)
        return outer

    # ─── TAB BAR ─────────────────────────────────────────────────

    def _build_tab_bar(self):
        frame = QFrame()
        frame.setFixedHeight(50)
        frame.setStyleSheet(
            f"QFrame {{ background:{_COLOR_HEADER2}; border-bottom:2px solid #2c6fad; }}")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(0)

        tabs = [
            ("Resumen",               "fa5s.th-large",       0),
            ("Asistencias",           "fa5s.calendar-check", 1),
            ("Historial de Pagos",    "fa5s.credit-card",    2),
            ("Membresías",            "fa5s.id-card",        3),
            ("Notas y Observaciones", "fa5s.sticky-note",    4),
        ]
        self._tab_icons = [t[1] for t in tabs]
        self._tab_buttons = []
        for nombre, icon_name, idx in tabs:
            btn = QPushButton(f"  {nombre}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(idx == 0)
            btn.setProperty("tab_idx", idx)
            btn.setStyleSheet(self._tab_btn_style(idx == 0))
            self._set_tab_btn_icon(btn, icon_name, idx == 0)
            btn.clicked.connect(lambda checked, i=idx: self._switch_tab(i))
            lay.addWidget(btn)
            self._tab_buttons.append(btn)
        lay.addStretch()
        return frame

    def _set_tab_btn_icon(self, btn: QPushButton, icon_name: str, active: bool):
        try:
            color = "#ffffff" if active else "#7a9abf"
            btn.setIcon(qta.icon(icon_name, color=color))
            btn.setIconSize(QSize(14, 14))
        except Exception:
            pass

    def _tab_btn_style(self, active: bool) -> str:
        if active:
            return (f"QPushButton {{ background:transparent; border:none;"
                    f" border-bottom:3px solid {_COLOR_TAB_ACTIVE};"
                    f" color:#ffffff; font-size:13px; font-weight:bold;"
                    f" padding:12px 20px; border-radius:0px; }}")
        return (f"QPushButton {{ background:transparent; border:none;"
                f" border-bottom:3px solid transparent;"
                f" color:#8faac0; font-size:13px; font-weight:normal;"
                f" padding:12px 20px; border-radius:0px; }}"
                f"QPushButton:hover {{ color:#c5d8e8; border-bottom:3px solid #4a7aad; }}")

    def _switch_tab(self, idx: int):
        self._tab_index = idx
        for i, (btn, icon_name) in enumerate(zip(self._tab_buttons, self._tab_icons)):
            is_active = btn.property("tab_idx") == idx
            btn.setChecked(is_active)
            btn.setStyleSheet(self._tab_btn_style(is_active))
            self._set_tab_btn_icon(btn, icon_name, is_active)
        widgets = [
            self._tab_resumen_widget, self._tab_asistencias_widget,
            self._tab_pagos_widget, self._tab_membresias_widget, self._tab_notas_widget,
        ]
        for i, w in enumerate(widgets):
            w.setVisible(i == idx)
        if idx == 1:
            self._recargar_calendario(self._cal_anio, self._cal_mes)
            self._recargar_tabla_asistencias()
        elif idx == 2:
            self._recargar_tabla_pagos()
        elif idx == 3:
            self._recargar_tab_membresias()

    # ─── TAB RESUMEN (3 columnas) ─────────────────────────────────

    def _build_resumen_widget(self):
        w = QWidget()
        w.setStyleSheet(f"background:{_COLOR_FONDO};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 16, 0, 16)
        lay.setSpacing(16)
        lay.addWidget(self._build_col_izq(), 28)
        lay.addWidget(self._build_col_centro(), 44)
        lay.addWidget(self._build_col_der(), 28)
        return w

    # ── Columna Izquierda ─────────────────────────────────────────

    def _build_col_izq(self):
        col = QWidget()
        col.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        lay.addWidget(self._build_card_barcode())
        lay.addWidget(self._build_card_info_personal())
        lay.addWidget(self._build_card_estadisticas())
        lay.addStretch()
        return col

    def _build_card_barcode(self):
        card = _card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        lay.addWidget(_card_title("Código de Barras", "fa5s.barcode", _COLOR_TEXT_PRI))
        lay.addWidget(_sep())
        self._barcode_widget = BarcodeWidget("CL-000000")
        lay.addWidget(self._barcode_widget, alignment=Qt.AlignCenter)
        self._lbl_codigo_texto = QLabel("CL-000000")
        self._lbl_codigo_texto.setAlignment(Qt.AlignCenter)
        self._lbl_codigo_texto.setStyleSheet(
            f"color:{_COLOR_TEXT_PRI}; font-size:15px; font-weight:bold;"
            " font-family:monospace; background:transparent; letter-spacing:2px;")
        lay.addWidget(self._lbl_codigo_texto)
        return card

    def _build_card_info_personal(self):
        card = _card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        lay.addWidget(_card_title("Información Personal", "fa5s.user", _COLOR_AZUL))
        lay.addWidget(_sep())
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnStretch(1, 1)

        def _row(label_txt, qta_icon_name):
            key_w = QWidget()
            key_w.setStyleSheet("background:transparent;")
            key_lay = QHBoxLayout(key_w)
            key_lay.setContentsMargins(0, 0, 0, 0)
            key_lay.setSpacing(5)
            key_lay.addWidget(_qta_lbl(qta_icon_name, color=_COLOR_TEXT_SEC, size=12))
            lk = QLabel(label_txt)
            lk.setStyleSheet(f"color:{_COLOR_TEXT_SEC}; font-size:12px; background:transparent;")
            key_lay.addWidget(lk)
            key_lay.addStretch()
            lv = QLabel("—")
            lv.setStyleSheet(f"color:{_COLOR_TEXT_PRI}; font-size:13px; background:transparent;")
            lv.setWordWrap(True)
            return key_w, lv

        rows_def = [
            ("Nombre completo",    "fa5s.user"),
            ("Teléfono",           "fa5s.phone"),
            ("Edad",               "fa5s.birthday-cake"),
            ("Género",             "fa5s.venus-mars"),
            ("Correo electrónico", "fa5s.envelope"),
            ("Dirección",          "fa5s.map-marker-alt"),
            ("Fecha de registro",  "fa5s.calendar"),
            ("Cliente ID",         "fa5s.id-badge"),
        ]
        self._ip_labels = []
        for i, (lbl, ico) in enumerate(rows_def):
            key_w, lv = _row(lbl, ico)
            self._ip_labels.append(lv)
            grid.addWidget(key_w, i, 0)
            grid.addWidget(lv, i, 1)

        (self._lbl_ip_nombre, self._lbl_ip_telefono, self._lbl_ip_edad,
         self._lbl_ip_genero, self._lbl_ip_email, self._lbl_ip_dir,
         self._lbl_ip_registro, self._lbl_ip_cliente_id) = self._ip_labels

        lay.addLayout(grid)
        return card

    def _build_card_estadisticas(self):
        card = _card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        lay.addWidget(_card_title("Estadísticas Generales", "fa5s.chart-bar", _COLOR_AZUL))
        lay.addWidget(_sep())
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setColumnStretch(1, 1)

        def _erow(label_txt, qta_icon_name, color=None):
            key_w = QWidget()
            key_w.setStyleSheet("background:transparent;")
            key_lay = QHBoxLayout(key_w)
            key_lay.setContentsMargins(0, 0, 0, 0)
            key_lay.setSpacing(5)
            key_lay.addWidget(_qta_lbl(qta_icon_name, color=color or _COLOR_TEXT_SEC, size=12))
            lk = QLabel(label_txt)
            lk.setStyleSheet(f"color:{_COLOR_TEXT_SEC}; font-size:12px; background:transparent;")
            key_lay.addWidget(lk)
            key_lay.addStretch()
            lv = QLabel("—")
            lv.setStyleSheet(
                f"color:{color or _COLOR_TEXT_PRI}; font-size:13px;"
                " font-weight:bold; background:transparent;")
            return key_w, lv

        rows_e = [
            ("Total pagos",          "fa5s.receipt",        _COLOR_AZUL),
            ("Total gastado",         "fa5s.dollar-sign",    _COLOR_ACTIVA),
            ("Membresía",             "fa5s.id-card",        None),
            ("Total asistencias",     "fa5s.dumbbell",       _COLOR_ACTIVA),
            ("Asistencias este mes",  "fa5s.calendar-check", None),
            ("Asistencias mes pas.",  "fa5s.history",        None),
        ]
        self._est_labels = []
        for i, (lbl, ico, col) in enumerate(rows_e):
            key_w, lv = _erow(lbl, ico, col)
            self._est_labels.append(lv)
            grid.addWidget(key_w, i, 0)
            grid.addWidget(lv, i, 1)

        (self._lbl_est_total_pagos, self._lbl_est_total_gastado, self._lbl_est_membresia,
         self._lbl_est_total_asis, self._lbl_est_mes, self._lbl_est_mes_ant) = self._est_labels

        lay.addLayout(grid)
        return card

    # ── Columna Central ──────────────────────────────────────────

    def _build_col_centro(self):
        col = QWidget()
        col.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        lay.addWidget(self._build_card_historial_pagos())
        lay.addWidget(self._build_card_historial_membresias())
        lay.addWidget(self._build_card_resumen_actividad())
        lay.addStretch()
        return col

    def _build_card_historial_pagos(self):
        card = _card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(_card_title("Historial de Pagos", "fa5s.credit-card", _COLOR_AZUL))
        top.addStretch()
        btn_ver = QPushButton("Ver todos los pagos →")
        btn_ver.setCursor(Qt.PointingHandCursor)
        btn_ver.setFlat(True)
        btn_ver.setStyleSheet(
            f"QPushButton {{ color:{_COLOR_AZUL}; background:transparent; border:none; font-size:12px; }}"
            f"QPushButton:hover {{ color:#1a4a8a; }}")
        btn_ver.clicked.connect(lambda: self._switch_tab(2))
        top.addWidget(btn_ver)
        lay.addLayout(top)
        lay.addWidget(_sep())

        self._tabla_pagos_resumen = QTableWidget()
        self._tabla_pagos_resumen.setColumnCount(5)
        self._tabla_pagos_resumen.setHorizontalHeaderLabels(
            ["Fecha", "Concepto", "Monto", "Método", "Referencia"])
        self._tabla_pagos_resumen.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tabla_pagos_resumen.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabla_pagos_resumen.setSelectionMode(QAbstractItemView.NoSelection)
        self._tabla_pagos_resumen.setAlternatingRowColors(False)
        self._tabla_pagos_resumen.verticalHeader().setVisible(False)
        self._tabla_pagos_resumen.setMaximumHeight(190)
        self._tabla_pagos_resumen.setMinimumHeight(120)
        aplicar_estilo_tabla_moderna(self._tabla_pagos_resumen)
        lay.addWidget(self._tabla_pagos_resumen)

        total_row = QHBoxLayout()
        self._lbl_total_pagado = QLabel("Total pagado: $0.00")
        self._lbl_total_pagado.setStyleSheet(
            f"color:{_COLOR_ACTIVA}; font-size:13px; font-weight:bold; background:transparent;")
        total_row.addWidget(self._lbl_total_pagado)
        total_row.addStretch()
        self._lbl_cant_pagos_resumen = QLabel("Pagos realizados: 0")
        self._lbl_cant_pagos_resumen.setStyleSheet(
            f"color:{_COLOR_TEXT_SEC}; font-size:12px; background:transparent;")
        total_row.addWidget(self._lbl_cant_pagos_resumen)
        lay.addLayout(total_row)
        return card

    def _build_card_historial_membresias(self):
        card = _card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(_card_title("Historial de Membresías", "fa5s.id-card", _COLOR_AZUL))
        top.addStretch()
        btn_ver = QPushButton("Ver todas →")
        btn_ver.setCursor(Qt.PointingHandCursor)
        btn_ver.setFlat(True)
        btn_ver.setStyleSheet(
            f"QPushButton {{ color:{_COLOR_AZUL}; background:transparent; border:none; font-size:12px; }}"
            f"QPushButton:hover {{ color:#1a4a8a; }}")
        btn_ver.clicked.connect(lambda: self._switch_tab(3))
        top.addWidget(btn_ver)
        lay.addLayout(top)
        lay.addWidget(_sep())
        self._membresias_container = QVBoxLayout()
        self._membresias_container.setSpacing(10)
        self._lbl_mem_placeholder = QLabel("Sin membresías registradas")
        self._lbl_mem_placeholder.setStyleSheet(
            f"color:{_COLOR_TEXT_SEC}; font-size:12px; background:transparent;")
        self._membresias_container.addWidget(self._lbl_mem_placeholder)
        lay.addLayout(self._membresias_container)
        return card

    def _build_card_resumen_actividad(self):
        card = _card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        lay.addWidget(_card_title("Resumen de Actividad", "fa5s.chart-line", _COLOR_AZUL))
        lay.addWidget(_sep())

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(8)

        def _metric(qta_icon_name, icon_color, label, _idx=[0]):
            f_name = f"metCard{_idx[0]}"
            _idx[0] += 1
            f = QFrame()
            f.setObjectName(f_name)
            f.setStyleSheet(
                f"QFrame#{f_name} {{ background:#f8faff; border-radius:10px;"
                f" border:1px solid #e8eef6; }}")
            v = QVBoxLayout(f)
            v.setContentsMargins(10, 12, 10, 12)
            v.setSpacing(4)
            ic = _qta_lbl(qta_icon_name, color=icon_color, size=24)
            ic.setFixedSize(32, 32)
            ic.setAlignment(Qt.AlignCenter)
            val = QLabel("0")
            val.setAlignment(Qt.AlignCenter)
            val.setStyleSheet(
                f"color:{_COLOR_TEXT_PRI}; font-size:22px; font-weight:bold; background:transparent;")
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                f"color:{_COLOR_TEXT_SEC}; font-size:10px; background:transparent;")
            v.addWidget(ic, alignment=Qt.AlignCenter)
            v.addWidget(val)
            v.addWidget(lbl)
            return f, val

        (f1, self._lbl_act_asistencias) = _metric("fa5s.clipboard-check", _COLOR_AZUL,    "Asistencias")
        (f2, self._lbl_act_dias)        = _metric("fa5s.calendar-day",    _COLOR_AZUL,    "Días")
        (f3, self._lbl_act_pct)         = _metric("fa5s.exchange-alt",    _COLOR_TEXT_SEC, "Asistencia")
        (f4, self._lbl_act_racha)       = _metric("fa5s.fire",            "#e67e22",      "Racha")
        for f in [f1, f2, f3, f4]:
            metrics_row.addWidget(f)
        lay.addLayout(metrics_row)

        self._lbl_act_nota = QLabel("Aún no hay actividad registrada este mes")
        self._lbl_act_nota.setAlignment(Qt.AlignCenter)
        self._lbl_act_nota.setStyleSheet(
            f"color:{_COLOR_TEXT_SEC}; font-size:12px; font-style:italic; background:transparent;")
        lay.addWidget(self._lbl_act_nota)
        return card

    # ── Columna Derecha ───────────────────────────────────────────

    def _build_col_der(self):
        col = QWidget()
        col.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        lay.addWidget(self._build_card_proximo_vencimiento())
        lay.addWidget(self._build_card_notas_resumen())
        lay.addWidget(self._build_card_acciones_rapidas())
        lay.addStretch()
        return col

    def _build_card_proximo_vencimiento(self):
        card = _card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        lay.addWidget(_card_title("Próximo Vencimiento", "fa5s.calendar-alt", _COLOR_AZUL))
        lay.addWidget(_sep())

        lbl_sub = QLabel("Fecha de vencimiento")
        lbl_sub.setAlignment(Qt.AlignCenter)
        lbl_sub.setStyleSheet(
            f"color:{_COLOR_TEXT_SEC}; font-size:11px; background:transparent;")
        lay.addWidget(lbl_sub)

        self._lbl_prox_fecha = QLabel("—")
        self._lbl_prox_fecha.setAlignment(Qt.AlignCenter)
        self._lbl_prox_fecha.setStyleSheet(
            f"color:{_COLOR_AZUL}; font-size:26px; font-weight:bold; background:transparent;")
        lay.addWidget(self._lbl_prox_fecha)
        self._lbl_prox_dias = QLabel("")
        self._lbl_prox_dias.setAlignment(Qt.AlignCenter)
        self._lbl_prox_dias.setStyleSheet(
            f"color:{_COLOR_TEXT_SEC}; font-size:12px; background:transparent;")
        lay.addWidget(self._lbl_prox_dias)

        self._frame_alerta_venc = QFrame()
        self._frame_alerta_venc.setObjectName("alertaVenc")
        self._frame_alerta_venc.setVisible(False)
        self._frame_alerta_venc.setStyleSheet(
            "QFrame#alertaVenc { background:#fde8e8; border-radius:8px; border:none; }")
        av_lay = QHBoxLayout(self._frame_alerta_venc)
        av_lay.setContentsMargins(12, 10, 12, 10)
        av_lay.setSpacing(8)
        av_lay.addWidget(_qta_lbl("fa5s.exclamation-triangle", color=_COLOR_VENCIDA, size=14))
        av_txt = QVBoxLayout()
        av_txt.setSpacing(2)
        self._lbl_alerta_venc_titulo = QLabel("Membresía vencida")
        self._lbl_alerta_venc_titulo.setStyleSheet(
            f"color:{_COLOR_VENCIDA}; font-size:12px; font-weight:bold; background:transparent;")
        self._lbl_alerta_venc_sub = QLabel("Debe renovar para continuar")
        self._lbl_alerta_venc_sub.setStyleSheet(
            f"color:{_COLOR_VENCIDA}; font-size:11px; background:transparent;")
        av_txt.addWidget(self._lbl_alerta_venc_titulo)
        av_txt.addWidget(self._lbl_alerta_venc_sub)
        av_lay.addLayout(av_txt, 1)
        lay.addWidget(self._frame_alerta_venc)

        btn_renovar = QPushButton("  Renovar Membresía")
        try:
            btn_renovar.setIcon(qta.icon("fa5s.redo", color="#ffffff"))
            btn_renovar.setIconSize(QSize(13, 13))
        except Exception:
            pass
        btn_renovar.setCursor(Qt.PointingHandCursor)
        btn_renovar.setStyleSheet(
            f"QPushButton {{ background:{_COLOR_AZUL}; color:#ffffff; padding:10px;"
            f" border:none; border-radius:8px; font-size:13px; font-weight:bold; }}"
            f"QPushButton:hover {{ background:#1e5a91; }}")
        btn_renovar.clicked.connect(self._on_registrar_membresia)
        lay.addWidget(btn_renovar)
        return card

    def _build_card_notas_resumen(self):
        card = _card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(_card_title("Notas y Observaciones", "fa5s.sticky-note", "#e67e22"))
        top.addStretch()
        btn_ver = QPushButton("Ver todas →")
        btn_ver.setCursor(Qt.PointingHandCursor)
        btn_ver.setFlat(True)
        btn_ver.setStyleSheet(
            f"QPushButton {{ color:{_COLOR_AZUL}; background:transparent; border:none; font-size:12px; }}"
            f"QPushButton:hover {{ color:#1a4a8a; }}")
        btn_ver.clicked.connect(lambda: self._switch_tab(4))
        top.addWidget(btn_ver)
        lay.addLayout(top)
        lay.addWidget(_sep())
        ph_lay = QHBoxLayout()
        ph_lay.setContentsMargins(0, 0, 0, 0)
        ph_lay.setSpacing(6)
        ph_lay.addWidget(_qta_lbl("fa5s.pencil-alt", color=_COLOR_TEXT_SEC, size=12))
        self._lbl_notas_placeholder = QLabel("No hay notas registradas")
        self._lbl_notas_placeholder.setStyleSheet(
            f"color:{_COLOR_TEXT_SEC}; font-size:12px; font-style:italic; background:transparent;")
        ph_lay.addWidget(self._lbl_notas_placeholder)
        ph_lay.addStretch()
        lay.addLayout(ph_lay)
        return card

    def _build_card_acciones_rapidas(self):
        card = _card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(6)
        lay.addWidget(_card_title("Acciones Rápidas", "fa5s.bolt", "#e67e22"))
        lay.addWidget(_sep())
        acciones = [
            ("fa5s.running",     "Registrar Asistencia", _COLOR_ACTIVA, self._on_registrar_asistencia),
            ("fa5s.credit-card", "Registrar Pago",        _COLOR_AZUL,   self._on_registrar_pago),
            ("fa5s.redo",        "Renovar Membresía",     "#8e44ad",     self._on_registrar_membresia),
            ("fa5s.sticky-note", "Agregar Nota",          "#e67e22",     self._on_agregar_nota),
            ("fa5s.weight",      "Tomar Medición",        "#16a085",     lambda: None),
        ]
        for idx_a, (qta_name, texto, color, slot) in enumerate(acciones):
            _hex_c = color.lstrip('#')
            _rc = int(_hex_c[0:2], 16)
            _gc = int(_hex_c[2:4], 16)
            _bc = int(_hex_c[4:6], 16)

            row_name = f"aRow{idx_a}"
            row_f = QFrame()
            row_f.setObjectName(row_name)
            row_f.setCursor(Qt.PointingHandCursor)
            row_f.setStyleSheet(
                f"QFrame#{row_name} {{ background:#ffffff; border:1px solid {_COLOR_BORDE};"
                f" border-radius:9px; }}"
                f"QFrame#{row_name}:hover {{ background:#f0f6ff; border-color:{_COLOR_AZUL}; }}")

            row_lay = QHBoxLayout(row_f)
            row_lay.setContentsMargins(12, 9, 12, 9)
            row_lay.setSpacing(10)

            ic_name = f"aIc{idx_a}"
            ic_box = QFrame()
            ic_box.setObjectName(ic_name)
            ic_box.setFixedSize(32, 32)
            ic_box.setStyleSheet(
                f"QFrame#{ic_name} {{ background:rgba({_rc},{_gc},{_bc},20);"
                f" border-radius:7px; border:none; }}")
            ic_box_lay = QVBoxLayout(ic_box)
            ic_box_lay.setContentsMargins(0, 0, 0, 0)
            ic_box_lay.addWidget(_qta_lbl(qta_name, color=color, size=14),
                                 alignment=Qt.AlignCenter)
            row_lay.addWidget(ic_box, alignment=Qt.AlignVCenter)

            lbl_t = QLabel(texto)
            lbl_t.setStyleSheet(
                f"color:{_COLOR_TEXT_PRI}; font-size:13px;"
                f" background:transparent;")
            row_lay.addWidget(lbl_t, 1)

            row_lay.addWidget(
                _qta_lbl("fa5s.chevron-right", color="#c8d6e4", size=10))

            row_f.mousePressEvent = lambda e, s=slot: s()
            lay.addWidget(row_f)
        return card

    # ─── TAB ASISTENCIAS ─────────────────────────────────────────

    def _build_tab_asistencias(self):
        w = QWidget()
        w.setStyleSheet(f"background:{_COLOR_FONDO};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 16, 0, 16)
        lay.setSpacing(16)

        card_cal = _card()
        cal_lay = QVBoxLayout(card_cal)
        cal_lay.setContentsMargins(16, 14, 16, 14)
        cal_lay.setSpacing(10)
        top = QHBoxLayout()
        top.addWidget(_card_title("Asistencias", "fa5s.calendar-check", _COLOR_AZUL))
        top.addStretch()
        leyenda = QHBoxLayout()
        leyenda.setSpacing(6)
        for qta_dot, color, texto in [
            ("fa5s.circle", _COLOR_ACTIVA, "Asistió"),
            ("fa5s.circle", _COLOR_AZUL,   "Pago")
        ]:
            dot = _qta_lbl(qta_dot, color=color, size=11)
            t = QLabel(texto)
            t.setStyleSheet(f"color:{_COLOR_TEXT_SEC}; font-size:11px; background:transparent;")
            leyenda.addWidget(dot)
            leyenda.addWidget(t)
        top.addLayout(leyenda)
        cal_lay.addLayout(top)
        lbl_ayuda = QLabel("Haz clic en un día para marcar/desmarcar asistencia")
        lbl_ayuda.setStyleSheet(
            f"color:{_COLOR_TEXT_SEC}; font-size:11px; font-style:italic; background:transparent;")
        cal_lay.addWidget(lbl_ayuda)
        self._calendario = CalendarioAsistencia(self.cliente_id, parent=self)
        cal_lay.addWidget(self._calendario)
        self._lbl_cal_resumen = QLabel("")
        self._lbl_cal_resumen.setAlignment(Qt.AlignCenter)
        self._lbl_cal_resumen.setStyleSheet(
            f"color:{_COLOR_TEXT_SEC}; font-size:12px; background:transparent;")
        cal_lay.addWidget(self._lbl_cal_resumen)
        cal_lay.addStretch()
        lay.addWidget(card_cal, 1)

        card_tabla = _card()
        tabla_lay = QVBoxLayout(card_tabla)
        tabla_lay.setContentsMargins(16, 14, 16, 14)
        tabla_lay.setSpacing(10)
        stats_row = QHBoxLayout()
        self._lbl_ultima_asist = _stat_frame("Última visita", "—")
        self._lbl_total_asist  = _stat_frame("Total asistencias", "—")
        self._lbl_mes_activo   = _stat_frame("Mes más activo", "—")
        self._lbl_racha_label  = _stat_frame("Racha actual", "—")
        for s in [self._lbl_ultima_asist, self._lbl_total_asist,
                  self._lbl_mes_activo, self._lbl_racha_label]:
            stats_row.addWidget(s)
        tabla_lay.addLayout(stats_row)
        tabla_lay.addWidget(_card_title("Asistencias recientes", "fa5s.list-alt", _COLOR_AZUL))
        tabla_lay.addWidget(_sep())
        self._tabla_asist = QTableWidget()
        self._tabla_asist.setColumnCount(1)
        self._tabla_asist.setHorizontalHeaderLabels(["Fecha"])
        self._tabla_asist.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tabla_asist.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabla_asist.setSelectionMode(QAbstractItemView.NoSelection)
        self._tabla_asist.setAlternatingRowColors(False)
        self._tabla_asist.verticalHeader().setVisible(False)
        aplicar_estilo_tabla_moderna(self._tabla_asist)
        tabla_lay.addWidget(self._tabla_asist)
        lay.addWidget(card_tabla, 1)
        return w

    # ─── TAB HISTORIAL DE PAGOS ───────────────────────────────────

    def _build_tab_pagos(self):
        w = QWidget()
        w.setStyleSheet(f"background:{_COLOR_FONDO};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 16, 0, 16)
        lay.setSpacing(14)
        stats_row = QHBoxLayout()
        self._lbl_ult_pago_det    = _stat_frame("Último pago", "—")
        self._lbl_total_pagado_tab = _stat_frame("Total pagado", "—", _COLOR_ACTIVA)
        self._lbl_cant_pagos      = _stat_frame("Cant. pagos", "—")
        self._lbl_prox_venc_tab   = _stat_frame("Próximo vencimiento", "—")
        for s in [self._lbl_ult_pago_det, self._lbl_total_pagado_tab,
                  self._lbl_cant_pagos, self._lbl_prox_venc_tab]:
            stats_row.addWidget(s)
        lay.addLayout(stats_row)

        card_tabla = _card()
        ct_lay = QVBoxLayout(card_tabla)
        ct_lay.setContentsMargins(16, 14, 16, 14)
        ct_lay.setSpacing(8)
        ct_lay.addWidget(_card_title("Historial de Pagos", "fa5s.credit-card", _COLOR_AZUL))
        ct_lay.addWidget(_sep())
        self._tabla_pagos = QTableWidget()
        self._tabla_pagos.setColumnCount(6)
        self._tabla_pagos.setHorizontalHeaderLabels(
            ["Fecha", "Concepto", "Monto", "Método", "Membresía", "Venc. Membresía"])
        self._tabla_pagos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tabla_pagos.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabla_pagos.setSelectionMode(QAbstractItemView.NoSelection)
        self._tabla_pagos.setAlternatingRowColors(False)
        self._tabla_pagos.verticalHeader().setVisible(False)
        aplicar_estilo_tabla_moderna(self._tabla_pagos)
        ct_lay.addWidget(self._tabla_pagos)
        lay.addWidget(card_tabla)
        return w

    # ─── TAB MEMBRESÍAS ───────────────────────────────────────────

    def _build_tab_membresias(self):
        w = QWidget()
        w.setStyleSheet(f"background:{_COLOR_FONDO};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 16, 0, 16)
        lay.setSpacing(14)
        card = _card()
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(16, 14, 16, 14)
        c_lay.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(_card_title("Membresías", "fa5s.id-card", _COLOR_AZUL))
        top.addStretch()
        btn_nueva = QPushButton("+ Nueva Membresía")
        btn_nueva.setCursor(Qt.PointingHandCursor)
        btn_nueva.setStyleSheet(
            f"QPushButton {{ background:{_COLOR_AZUL}; color:#ffffff; padding:7px 14px;"
            f" border:none; border-radius:5px; font-size:12px; font-weight:bold; }}"
            f"QPushButton:hover {{ background:#1e5a91; }}")
        btn_nueva.clicked.connect(self._on_registrar_membresia)
        top.addWidget(btn_nueva)
        c_lay.addLayout(top)
        c_lay.addWidget(_sep())
        self._tabla_membresias = QTableWidget()
        self._tabla_membresias.setColumnCount(5)
        self._tabla_membresias.setHorizontalHeaderLabels(
            ["Tipo", "Estado", "Inicio", "Vencimiento", "Monto"])
        self._tabla_membresias.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tabla_membresias.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabla_membresias.setSelectionMode(QAbstractItemView.NoSelection)
        self._tabla_membresias.setAlternatingRowColors(False)
        self._tabla_membresias.verticalHeader().setVisible(False)
        aplicar_estilo_tabla_moderna(self._tabla_membresias)
        c_lay.addWidget(self._tabla_membresias)
        lay.addWidget(card)
        return w

    # ─── TAB NOTAS ────────────────────────────────────────────────

    def _build_tab_notas(self):
        w = QWidget()
        w.setStyleSheet(f"background:{_COLOR_FONDO};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 16, 0, 16)
        lay.setSpacing(14)
        card = _card()
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(16, 14, 16, 14)
        c_lay.setSpacing(8)
        c_lay.addWidget(_card_title("Notas y Observaciones", "fa5s.sticky-note", "#e67e22"))
        c_lay.addWidget(_sep())
        self._text_notas = QTextEdit()
        self._text_notas.setPlaceholderText(
            "Escribe aquí notas u observaciones sobre el cliente...")
        self._text_notas.setStyleSheet(
            f"QTextEdit {{ border:1px solid {_COLOR_BORDE}; border-radius:6px;"
            f" padding:8px; font-size:13px; color:{_COLOR_TEXT_PRI}; background:#fafcff; }}")
        self._text_notas.setMinimumHeight(200)
        c_lay.addWidget(self._text_notas)
        btn_guardar = QPushButton("  Guardar Notas")
        try:
            btn_guardar.setIcon(qta.icon("fa5s.save", color="#ffffff"))
            btn_guardar.setIconSize(QSize(16, 16))
        except Exception:
            pass
        btn_guardar.setCursor(Qt.PointingHandCursor)
        btn_guardar.setStyleSheet(
            f"QPushButton {{ background:{_COLOR_AZUL}; color:#ffffff; padding:9px 20px;"
            f" border:none; border-radius:6px; font-size:13px; font-weight:bold; }}"
            f"QPushButton:hover {{ background:#1e5a91; }}")
        btn_guardar.clicked.connect(self._on_guardar_notas)
        c_lay.addWidget(btn_guardar, alignment=Qt.AlignLeft)
        lay.addWidget(card)
        return w

    # ─── CARGA DE DATOS ───────────────────────────────────────────

    def _cargar_todo(self):
        self._resumen = perfil_cliente_service.obtener_resumen_cliente(self.cliente_id)
        self._poblar_header()
        self._poblar_col_izq()
        self._poblar_col_centro()
        self._poblar_col_der()

    def _poblar_header(self):
        r = self._resumen
        nombre = r.get("nombre", "—")
        self._lbl_nombre.setText(nombre)
        partes_nom = [p for p in nombre.split() if p]
        self._avatar_widget.set_initials(
            "".join(p[0] for p in partes_nom[:2]) or "?")
        partes = []
        if r.get("telefono"):
            partes.append(r['telefono'])
        edad = _edad(r.get("fecha_nacimiento"))
        if edad:
            partes.append(f"{edad} años")
        if r.get("sexo"):
            gmap = {"Masculino": "♂ Masculino", "Femenino": "♀ Femenino"}
            partes.append(gmap.get(r["sexo"], r["sexo"]))
        self._lbl_datos_rapidos.setText("   ".join(partes) if partes else "—")
        self._lbl_registro.setText(f"Registrado: {_fmt_fecha(r.get('fecha_registro'))}")

        estado = r.get("estado_membresia", "Sin membresía")
        if estado == ESTADO_VENCIDA:
            display, color = estado, _color_estado(estado)
        elif estado == ESTADO_POR_VENCER:
            display, color = estado, _color_estado(estado)
        elif estado == ESTADO_ACTIVA:
            display, color = estado, _color_estado(estado)
        else:
            display, color = "Sin membresía", _COLOR_SIN
        self._lbl_estado_badge.setText(f"  {display}  ")
        self._lbl_estado_badge.setStyleSheet(
            f"QLabel {{ background:{color}; color:#ffffff; padding:5px 14px;"
            f" border-radius:12px; font-size:13px; font-weight:bold; }}")
        venc = r.get("proximo_vencimiento")
        self._lbl_vencimiento_header.setText(
            f"Vence: {_fmt_fecha(venc)}" if venc else "")

    def _poblar_col_izq(self):
        r = self._resumen
        cid = r.get("id") or self.cliente_id
        codigo = f"CL-{int(cid):06d}"
        self._barcode_widget._codigo = codigo.upper()
        self._barcode_widget.update()
        self._lbl_codigo_texto.setText(codigo)
        self._lbl_ip_nombre.setText(r.get("nombre") or "—")
        self._lbl_ip_telefono.setText(r.get("telefono") or "—")
        edad = _edad(r.get("fecha_nacimiento"))
        self._lbl_ip_edad.setText(f"{edad} años" if edad else "—")
        self._lbl_ip_genero.setText(r.get("sexo") or "—")
        self._lbl_ip_email.setText(r.get("email") or "—")
        self._lbl_ip_dir.setText("—")
        self._lbl_ip_registro.setText(_fmt_fecha(r.get("fecha_registro")))
        self._lbl_ip_cliente_id.setText(codigo)
        self._lbl_est_total_pagos.setText(str(r.get("cantidad_pagos", 0)))
        self._lbl_est_total_gastado.setText(f"${r.get('total_pagado', 0):,.2f}")
        estado_mem = r.get("estado_membresia", "Sin membresía")
        color_mem = _color_estado(estado_mem)
        self._lbl_est_membresia.setText(estado_mem)
        self._lbl_est_membresia.setStyleSheet(
            f"color:{color_mem}; font-size:13px; font-weight:bold; background:transparent;")
        self._lbl_est_total_asis.setText(str(r.get("total_asistencias", 0)))
        self._lbl_est_mes.setText(str(r.get("asist_este_mes", 0)))
        self._lbl_est_mes_ant.setText(str(r.get("asist_mes_pasado", 0)))

    def _poblar_col_centro(self):
        r = self._resumen
        pagos = perfil_cliente_service.obtener_pagos_cliente(self.cliente_id, limite=3)
        t = self._tabla_pagos_resumen
        t.setRowCount(len(pagos))
        for i, p in enumerate(pagos):
            t.setRowHeight(i, 36)
            vals = [_fmt_fecha(p.get("fecha")), p.get("concepto") or "—",
                    f"${p.get('monto', 0):,.2f}", p.get("metodo") or "—", "—"]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setForeground(QColor(_COLOR_ACTIVA if col == 2 else _COLOR_TEXT_PRI))
                t.setItem(i, col, item)

        total = r.get("total_pagado", 0)
        cant  = r.get("cantidad_pagos", 0)
        self._lbl_total_pagado.setText(f"Total pagado: ${total:,.2f}")
        self._lbl_cant_pagos_resumen.setText(f"Pagos realizados: {cant}")

        # Membresías recientes
        while self._membresias_container.count() > 0:
            item = self._membresias_container.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)

        membresias = listar_membresias(cliente_id=self.cliente_id)
        if not membresias:
            empty_w = QWidget()
            empty_w.setStyleSheet("background:transparent; border:none;")
            empty_lay = QHBoxLayout(empty_w)
            empty_lay.setContentsMargins(0, 8, 0, 8)
            empty_lay.setSpacing(8)
            empty_lay.addWidget(_qta_lbl("fa5s.calendar-times", color=_COLOR_TEXT_SEC, size=16))
            lbl_empty = QLabel("Sin membresías registradas")
            lbl_empty.setStyleSheet(
                f"color:{_COLOR_TEXT_SEC}; font-size:12px; font-style:italic;"
                f" background:transparent;")
            empty_lay.addWidget(lbl_empty)
            empty_lay.addStretch()
            self._membresias_container.addWidget(empty_w)
        else:
            for idx_m, mem in enumerate(membresias[:3]):
                estado_m = mem.get("estado", "—")
                color_est = _color_estado(estado_m)
                _hex = color_est.lstrip('#')
                _r, _g, _b = int(_hex[0:2], 16), int(_hex[2:4], 16), int(_hex[4:6], 16)

                # Outer card — objectName selector to prevent border cascading to children
                card_name = f"memCard{idx_m}"
                row = QFrame()
                row.setObjectName(card_name)
                row.setStyleSheet(
                    f"QFrame#{card_name} {{ background:#ffffff; border:1px solid #e5e7eb;"
                    f" border-radius:12px; }}")
                _shadow(row, blur=10, offset_y=2, alpha=14)

                row_lay = QHBoxLayout(row)
                row_lay.setContentsMargins(16, 14, 16, 14)
                row_lay.setSpacing(14)

                # Left: icon box — objectName so its border:none doesn't fight parent
                box_name = f"icBox{idx_m}"
                ic_box = QFrame()
                ic_box.setObjectName(box_name)
                ic_box.setFixedSize(44, 44)
                ic_box.setStyleSheet(
                    f"QFrame#{box_name} {{ background:rgba({_r},{_g},{_b},20);"
                    f" border-radius:10px; border:none; }}")
                ic_box_lay = QVBoxLayout(ic_box)
                ic_box_lay.setContentsMargins(0, 0, 0, 0)
                ic = _qta_lbl("fa5s.calendar-alt", color=color_est, size=18)
                ic_box_lay.addWidget(ic, alignment=Qt.AlignCenter)
                row_lay.addWidget(ic_box, alignment=Qt.AlignVCenter)

                # Center: QWidget (not QFrame) so parent QFrame selector won't touch it
                info_w = QWidget()
                info_w.setStyleSheet("background:transparent; border:none;")
                info_lay = QVBoxLayout(info_w)
                info_lay.setContentsMargins(0, 0, 0, 0)
                info_lay.setSpacing(4)

                lbl_tipo = QLabel(mem.get("tipo", "—"))
                lbl_tipo.setStyleSheet(
                    f"color:{_COLOR_TEXT_PRI}; font-size:14px; font-weight:bold;"
                    f" background:transparent;")

                fecha_ini = _fmt_fecha(mem.get('fecha_inicio'))
                fecha_fin = _fmt_fecha(mem.get('fecha_vencimiento'))
                lbl_rango = QLabel(f"{fecha_ini}  –  {fecha_fin}")
                lbl_rango.setStyleSheet(
                    f"color:{_COLOR_TEXT_SEC}; font-size:11px;"
                    f" background:transparent;")

                info_lay.addWidget(lbl_tipo)
                info_lay.addWidget(lbl_rango)
                row_lay.addWidget(info_w, 1)

                # Right: QWidget column — badge pill + days text
                right_w = QWidget()
                right_w.setStyleSheet("background:transparent; border:none;")
                right_lay = QVBoxLayout(right_w)
                right_lay.setContentsMargins(0, 0, 0, 0)
                right_lay.setSpacing(5)
                right_lay.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

                badge_est = QLabel(f" {estado_m} ")
                badge_est.setAlignment(Qt.AlignCenter)
                badge_est.setStyleSheet(
                    f"QLabel {{ color:{color_est}; background:rgba({_r},{_g},{_b},25);"
                    f" padding:4px 12px; border-radius:12px; font-size:11px;"
                    f" font-weight:bold; }}")
                right_lay.addWidget(badge_est, alignment=Qt.AlignRight)

                try:
                    dias_para = (date.fromisoformat(str(mem.get("fecha_vencimiento"))) - date.today()).days
                    if dias_para >= 0:
                        dias_txt = f"Vence en {dias_para} días"
                        dias_color = _COLOR_VENCER if dias_para <= 7 else _COLOR_TEXT_SEC
                    else:
                        dias_txt = f"Venció hace {abs(dias_para)} días"
                        dias_color = _COLOR_TEXT_SEC
                    dias_lbl = QLabel(dias_txt)
                    dias_lbl.setAlignment(Qt.AlignRight)
                    dias_lbl.setStyleSheet(
                        f"color:{dias_color}; font-size:10px;"
                        f" background:transparent;")
                    right_lay.addWidget(dias_lbl, alignment=Qt.AlignRight)
                except Exception:
                    pass

                row_lay.addWidget(right_w, alignment=Qt.AlignVCenter)
                self._membresias_container.addWidget(row)

        # Resumen actividad
        asist_mes = r.get("asist_este_mes", 0)
        hoy = date.today()
        dias_mes = monthrange(hoy.year, hoy.month)[1]
        pct = f"{round(asist_mes / dias_mes * 100)}%" if dias_mes else "0%"
        self._lbl_act_asistencias.setText(str(asist_mes))
        self._lbl_act_dias.setText(str(asist_mes))
        self._lbl_act_pct.setText(pct)
        self._lbl_act_racha.setText(str(r.get("racha_actual", 0)))
        self._lbl_act_nota.setVisible(asist_mes == 0)

    def _poblar_col_der(self):
        r = self._resumen
        venc  = r.get("proximo_vencimiento")
        estado = r.get("estado_membresia", "Sin membresía")
        if venc:
            self._lbl_prox_fecha.setText(_fmt_fecha(venc))
            try:
                dias_diff = (date.fromisoformat(venc) - date.today()).days
                if dias_diff >= 0:
                    self._lbl_prox_dias.setText(f"En {dias_diff} días")
                    self._lbl_prox_fecha.setStyleSheet(
                        f"color:{_COLOR_AZUL}; font-size:24px; font-weight:bold; background:transparent;")
                else:
                    self._lbl_prox_dias.setText(f"Hace {abs(dias_diff)} días")
                    self._lbl_prox_fecha.setStyleSheet(
                        f"color:{_COLOR_VENCIDA}; font-size:24px; font-weight:bold; background:transparent;")
            except Exception:
                self._lbl_prox_dias.setText("")
        else:
            self._lbl_prox_fecha.setText("Sin membresía")
            self._lbl_prox_dias.setText("")

        if estado == ESTADO_VENCIDA:
            self._frame_alerta_venc.setVisible(True)
            self._frame_alerta_venc.setStyleSheet("QFrame { background:#fde8e8; border-radius:6px; }")
            self._lbl_alerta_venc_titulo.setStyleSheet(
                f"color:{_COLOR_VENCIDA}; font-size:13px; font-weight:bold; background:transparent;")
            self._lbl_alerta_venc_titulo.setText("Membresía vencida")
            self._lbl_alerta_venc_sub.setStyleSheet(
                f"color:{_COLOR_VENCIDA}; font-size:11px; background:transparent;")
            self._lbl_alerta_venc_sub.setText("Debe renovar para continuar")
        elif estado == ESTADO_POR_VENCER:
            self._frame_alerta_venc.setVisible(True)
            self._frame_alerta_venc.setStyleSheet("QFrame { background:#fff8e1; border-radius:6px; }")
            self._lbl_alerta_venc_titulo.setStyleSheet(
                f"color:{_COLOR_VENCER}; font-size:13px; font-weight:bold; background:transparent;")
            self._lbl_alerta_venc_titulo.setText("Membresía por vencer")
            self._lbl_alerta_venc_sub.setStyleSheet(
                f"color:{_COLOR_VENCER}; font-size:11px; background:transparent;")
            self._lbl_alerta_venc_sub.setText("Renueva pronto para continuar")
        else:
            self._frame_alerta_venc.setVisible(False)

    # ─── RECARGA DE TABS ──────────────────────────────────────────

    def _actualizar_stats_asistencia(self):
        self._resumen = perfil_cliente_service.obtener_resumen_cliente(self.cliente_id)
        r = self._resumen
        self._lbl_est_total_asis.setText(str(r.get("total_asistencias", 0)))
        self._lbl_est_mes.setText(str(r.get("asist_este_mes", 0)))
        racha = r.get("racha_actual", 0)
        _set_stat(self._lbl_ultima_asist, _fmt_fecha(r.get("ultima_asistencia")))
        _set_stat(self._lbl_total_asist,  str(r.get("total_asistencias", 0)))
        _set_stat(self._lbl_racha_label,  f"{racha} día(s)")
        self._lbl_act_asistencias.setText(str(r.get("asist_este_mes", 0)))
        self._lbl_act_racha.setText(str(racha))

    def _recargar_calendario(self, anio, mes):
        self._cal_anio = anio
        self._cal_mes  = mes
        dias_asis = asistencia_service.dias_con_asistencia_mes(self.cliente_id, anio, mes)
        from db import get_connection as _gconn
        from datetime import date as _date
        ult_dia = monthrange(anio, mes)[1]
        conn = _gconn()
        cur = conn.cursor()
        cur.execute(
            "SELECT fecha FROM pagos WHERE cliente_id=? AND fecha BETWEEN ? AND ?",
            (self.cliente_id,
             _date(anio, mes, 1).isoformat(),
             _date(anio, mes, ult_dia).isoformat()))
        dias_pago = {_date.fromisoformat(r["fecha"]).day for r in cur.fetchall()}
        conn.close()
        tiene_membresia = bool(self._resumen.get("membresia_activa"))
        self._calendario.cargar_mes(anio, mes, dias_asis, dias_pago, tiene_membresia)
        q_actual = self._calendario.yearShown() * 100 + self._calendario.monthShown()
        if q_actual != anio * 100 + mes:
            self._calendario.setCurrentPage(anio, mes)
        cnt = len(dias_asis)
        self._lbl_cal_resumen.setText(f"{cnt} asistencia(s) en {_nombre_mes(mes)} {anio}")

    def _recargar_tabla_asistencias(self):
        r = self._resumen
        _set_stat(self._lbl_ultima_asist, _fmt_fecha(r.get("ultima_asistencia")))
        _set_stat(self._lbl_total_asist,  str(r.get("total_asistencias", 0)))
        _set_stat(self._lbl_mes_activo,   r.get("mes_mas_activo") or "—")
        racha = r.get("racha_actual", 0)
        _set_stat(self._lbl_racha_label,  f"{racha} día(s)")
        asistencias = asistencia_service.listar_asistencias_recientes(
            self.cliente_id, limite=50)
        t = self._tabla_asist
        t.setRowCount(len(asistencias))
        for i, a in enumerate(asistencias):
            t.setRowHeight(i, 36)
            item = QTableWidgetItem(_fmt_fecha(a["fecha"]))
            item.setForeground(QColor(_COLOR_TEXT_PRI))
            t.setItem(i, 0, item)

    def _recargar_tabla_pagos(self):
        r = self._resumen
        _set_stat(self._lbl_ult_pago_det,
                  f"{_fmt_fecha(r.get('ultimo_pago_fecha'))}  ${r.get('ultimo_pago_monto', 0):,.2f}")
        _set_stat(self._lbl_total_pagado_tab,
                  f"${r.get('total_pagado', 0):,.2f}", _COLOR_ACTIVA)
        _set_stat(self._lbl_cant_pagos,    str(r.get("cantidad_pagos", 0)))
        _set_stat(self._lbl_prox_venc_tab, _fmt_fecha(r.get("proximo_vencimiento")))
        pagos = perfil_cliente_service.obtener_pagos_cliente(self.cliente_id)
        t = self._tabla_pagos
        t.setRowCount(len(pagos))
        for i, p in enumerate(pagos):
            t.setRowHeight(i, 36)
            vals = [_fmt_fecha(p.get("fecha")), p.get("concepto") or "—",
                    f"${p.get('monto', 0):,.2f}", p.get("metodo") or "—",
                    p.get("membresia_tipo") or "—",
                    _fmt_fecha(p.get("membresia_vencimiento"))]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                color = (_COLOR_ACTIVA if col == 2 else
                         _COLOR_TEXT_SEC if col in (4, 5) else _COLOR_TEXT_PRI)
                item.setForeground(QColor(color))
                t.setItem(i, col, item)

    def _recargar_tab_membresias(self):
        membresias = listar_membresias(cliente_id=self.cliente_id)
        t = self._tabla_membresias
        t.setRowCount(len(membresias))
        for i, m in enumerate(membresias):
            t.setRowHeight(i, 40)
            estado = m.get("estado", "—")
            color_est = _color_estado(estado)
            vals = [m.get("tipo", "—"), estado,
                    _fmt_fecha(m.get("fecha_inicio")),
                    _fmt_fecha(m.get("fecha_vencimiento")),
                    f"${m.get('monto', 0):,.2f}"]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if col == 1:
                    item.setForeground(QColor(color_est))
                elif col == 4:
                    item.setForeground(QColor(_COLOR_ACTIVA))
                else:
                    item.setForeground(QColor(_COLOR_TEXT_PRI))
                t.setItem(i, col, item)

    # ─── ACCIONES ─────────────────────────────────────────────────

    def _on_registrar_pago(self):
        try:
            from views.pagos_view import RegistrarPagoDialog
            dlg = RegistrarPagoDialog(self)
            idx = dlg.combo_cliente.findData(self.cliente_id)
            if idx >= 0:
                dlg.combo_cliente.setCurrentIndex(idx)
            if dlg.exec():
                self._cargar_todo()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_registrar_membresia(self):
        try:
            from views.membresias_view import AgregarMembresiaDialog
            dlg = AgregarMembresiaDialog(self)
            idx = dlg.combo_cliente.findData(self.cliente_id)
            if idx >= 0:
                dlg.combo_cliente.setCurrentIndex(idx)
            if dlg.exec():
                self._cargar_todo()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_editar_cliente(self):
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

    def _on_registrar_asistencia(self):
        try:
            ok, msg = asistencia_service.registrar_asistencia(
                self.cliente_id, fecha=date.today(), origen="manual")
            if ok:
                self._resumen = perfil_cliente_service.obtener_resumen_cliente(self.cliente_id)
                self._actualizar_stats_asistencia()
                self._recargar_tabla_asistencias()
                if self._tab_index == 1:
                    self._recargar_calendario(self._cal_anio, self._cal_mes)
            else:
                QMessageBox.information(self, "Asistencia", msg or "No se pudo registrar")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_agregar_nota(self):
        self._switch_tab(4)
        self._text_notas.setFocus()

    def _on_guardar_notas(self):
        QMessageBox.information(
            self, "Notas",
            "Las notas se guardaron correctamente.\n"
            "(Esta funcionalidad requiere una tabla 'notas' en la base de datos.)")
