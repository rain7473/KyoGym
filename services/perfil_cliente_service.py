"""Servicio agregado para el perfil completo de un cliente"""
from datetime import date, timedelta
from calendar import monthrange
from db import get_connection
from services import asistencia_service
from services.membresia_service import (listar_membresias, obtener_membresia_activa,
                                        calcular_estado_membresia)
from utils.constants import ESTADO_ACTIVA, ESTADO_POR_VENCER, ESTADO_VENCIDA


# ─────────────────────────── RESUMEN PRINCIPAL ───────────────────

def obtener_resumen_cliente(cliente_id):
    """Devuelve un dict con todos los datos necesarios para el encabezado
    y las tarjetas resumen del perfil."""
    hoy = date.today()

    # ── Datos básicos del cliente ──────────────────────────────
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clientes WHERE id=?", (cliente_id,))
    cliente = dict(cur.fetchone() or {})
    conn.close()

    # ── Membresía actual ───────────────────────────────────────
    membresia_activa = obtener_membresia_activa(cliente_id)
    todas_membresias = listar_membresias(cliente_id=cliente_id)
    # La última aunque esté vencida
    ultima_membresia = todas_membresias[0] if todas_membresias else None
    if membresia_activa:
        estado_membresia = membresia_activa["estado"]
        plan_actual = membresia_activa["tipo"]
        proximo_vencimiento = membresia_activa["fecha_vencimiento"]
        dias_para_vencer = (date.fromisoformat(proximo_vencimiento) - hoy).days
    elif ultima_membresia:
        estado_membresia = calcular_estado_membresia(ultima_membresia["fecha_vencimiento"])
        plan_actual = ultima_membresia["tipo"]
        proximo_vencimiento = ultima_membresia["fecha_vencimiento"]
        dias_para_vencer = (date.fromisoformat(proximo_vencimiento) - hoy).days
    else:
        estado_membresia = "Sin membresía"
        plan_actual = "—"
        proximo_vencimiento = None
        dias_para_vencer = None

    # ── Pagos ──────────────────────────────────────────────────
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT fecha, monto, concepto, metodo FROM pagos
        WHERE cliente_id=? ORDER BY fecha DESC, id DESC
    """, (cliente_id,))
    pagos = [dict(r) for r in cur.fetchall()]
    conn.close()

    ultimo_pago_fecha = pagos[0]["fecha"] if pagos else None
    ultimo_pago_monto = pagos[0]["monto"] if pagos else 0
    total_pagado = sum(p["monto"] for p in pagos)
    cantidad_pagos = len(pagos)

    # ── Asistencias ────────────────────────────────────────────
    ult_asistencia = asistencia_service.ultima_asistencia(cliente_id)

    # Este mes
    primer_dia_mes = hoy.replace(day=1)
    ultimo_dia_mes = hoy.replace(day=monthrange(hoy.year, hoy.month)[1])
    asist_este_mes = asistencia_service.contar_asistencias_periodo(
        cliente_id, primer_dia_mes, ultimo_dia_mes)

    # Mes pasado
    primer_dia_mes_ant = (primer_dia_mes - timedelta(days=1)).replace(day=1)
    ultimo_dia_mes_ant = primer_dia_mes - timedelta(days=1)
    asist_mes_pasado = asistencia_service.contar_asistencias_periodo(
        cliente_id, primer_dia_mes_ant, ultimo_dia_mes_ant)

    # Promedio últimos 6 meses
    seis_meses_atras = hoy - timedelta(days=180)
    total_asis_6m = asistencia_service.contar_asistencias_periodo(
        cliente_id, seis_meses_atras, hoy)
    promedio_mensual = round(total_asis_6m / 6, 1)

    # Días sin asistir
    if ult_asistencia:
        dias_sin_asistir = (hoy - date.fromisoformat(ult_asistencia)).days
    else:
        dias_sin_asistir = None

    # Total asistencias históricas
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM asistencias WHERE cliente_id=?", (cliente_id,))
    total_asistencias = cur.fetchone()["cnt"]
    conn.close()

    # Racha actual (días consecutivos hasta hoy)
    racha = _calcular_racha(cliente_id, hoy)

    # Mes más activo
    mes_mas_activo = _mes_mas_activo(cliente_id)

    return {
        # cliente
        "id": cliente.get("id"),
        "nombre": cliente.get("nombre", ""),
        "telefono": cliente.get("telefono", ""),
        "sexo": cliente.get("sexo", ""),
        "email": cliente.get("email", ""),
        "fecha_nacimiento": cliente.get("fecha_nacimiento"),
        "fecha_registro": cliente.get("fecha_registro"),
        # membresía
        "estado_membresia": estado_membresia,
        "plan_actual": plan_actual,
        "proximo_vencimiento": proximo_vencimiento,
        "dias_para_vencer": dias_para_vencer,
        "membresia_activa": membresia_activa,
        # pagos
        "ultimo_pago_fecha": ultimo_pago_fecha,
        "ultimo_pago_monto": ultimo_pago_monto,
        "total_pagado": total_pagado,
        "cantidad_pagos": cantidad_pagos,
        # asistencias
        "ultima_asistencia": ult_asistencia,
        "asist_este_mes": asist_este_mes,
        "asist_mes_pasado": asist_mes_pasado,
        "promedio_mensual": promedio_mensual,
        "dias_sin_asistir": dias_sin_asistir,
        "total_asistencias": total_asistencias,
        "racha_actual": racha,
        "mes_mas_activo": mes_mas_activo,
    }


def _calcular_racha(cliente_id, hasta=None):
    """Días con asistencia en la racha actual.

    La racha solo se reinicia cuando hay 4 o más días seguidos sin asistir.
    Descansos de hasta 3 días consecutivos no cortan la racha.
    """
    if hasta is None:
        hasta = date.today()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT fecha FROM asistencias
        WHERE cliente_id=? AND fecha <= ?
        ORDER BY fecha DESC
    """, (cliente_id, hasta.isoformat()))
    fechas = sorted(
        [date.fromisoformat(r["fecha"]) for r in cur.fetchall()],
        reverse=True)
    conn.close()

    if not fechas:
        return 0

    # Si la última asistencia fue hace más de 3 días, la racha es 0
    if (hasta - fechas[0]).days > 3:
        return 0

    # Contar días de asistencia hasta encontrar un hueco de 4+ días
    racha = 1
    for i in range(1, len(fechas)):
        gap = (fechas[i - 1] - fechas[i]).days
        if gap > 3:
            break
        racha += 1

    return racha


def _mes_mas_activo(cliente_id):
    """Devuelve 'Mes YYYY' del mes con más asistencias."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT strftime('%Y-%m', fecha) as mes, COUNT(*) as cnt
        FROM asistencias WHERE cliente_id=?
        GROUP BY mes ORDER BY cnt DESC LIMIT 1
    """, (cliente_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    import locale
    try:
        y, m = row["mes"].split("-")
        meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                 "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        return f"{meses[int(m)-1]} {y}"
    except Exception:
        return row["mes"]


# ─────────────────────────── ASISTENCIAS ─────────────────────────

def obtener_asistencias_cliente(cliente_id, mes, anio):
    """Proxy a asistencia_service para uso desde la vista."""
    return asistencia_service.listar_asistencias_mes(cliente_id, anio, mes)


# ─────────────────────────── PAGOS ───────────────────────────────

def obtener_pagos_cliente(cliente_id, limite=200):
    """Devuelve historial de pagos del cliente con membresía asociada."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.fecha, p.monto, p.metodo, p.concepto,
               m.tipo as membresia_tipo, m.fecha_vencimiento as membresia_vencimiento
        FROM pagos p
        LEFT JOIN membresias m ON m.pago_id = p.id
        WHERE p.cliente_id=?
        ORDER BY p.fecha DESC, p.id DESC
        LIMIT ?
    """, (cliente_id, limite))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ─────────────────────────── ALERTAS ─────────────────────────────

def obtener_alertas_cliente(cliente_id):
    """Devuelve lista de alertas activas para el cliente.
    Cada alerta es dict con: tipo ('danger'|'warning'|'info'), mensaje.
    """
    hoy = date.today()
    resumen = obtener_resumen_cliente(cliente_id)
    alertas = []

    # Membresía vencida
    if resumen["estado_membresia"] == ESTADO_VENCIDA:
        venc = resumen["proximo_vencimiento"]
        dias = abs(resumen["dias_para_vencer"] or 0)
        alertas.append({
            "tipo": "danger",
            "icono": "🔴",
            "mensaje": f"Membresía vencida hace {dias} día(s) (venció {venc})"
        })
    elif resumen["estado_membresia"] == ESTADO_POR_VENCER:
        dias = resumen["dias_para_vencer"]
        alertas.append({
            "tipo": "warning",
            "icono": "🟡",
            "mensaje": f"Membresía vence en {dias} día(s) ({resumen['proximo_vencimiento']})"
        })
    elif resumen["estado_membresia"] == "Sin membresía":
        alertas.append({
            "tipo": "warning",
            "icono": "⚪",
            "mensaje": "Cliente sin membresía registrada"
        })

    # Días sin asistir
    dias_sin = resumen["dias_sin_asistir"]
    if dias_sin is None:
        alertas.append({"tipo": "info", "icono": "📅", "mensaje": "No tiene asistencias registradas"})
    elif dias_sin >= 30:
        alertas.append({"tipo": "danger", "icono": "🔴",
                        "mensaje": f"Sin asistir hace {dias_sin} días — riesgo de abandono"})
    elif dias_sin >= 14:
        alertas.append({"tipo": "warning", "icono": "🟡",
                        "mensaje": f"Sin asistir hace {dias_sin} días"})

    # Frecuencia bajó
    este_mes = resumen["asist_este_mes"]
    mes_pasado = resumen["asist_mes_pasado"]
    dia_del_mes = hoy.day
    if mes_pasado > 0 and dia_del_mes >= 15:
        # Comparación solo es justa a partir de la segunda quincena
        if este_mes < mes_pasado * 0.6:
            alertas.append({"tipo": "warning", "icono": "📉",
                             "mensaje": f"Frecuencia bajó: {este_mes} visitas este mes vs {mes_pasado} el mes pasado"})

    return alertas
