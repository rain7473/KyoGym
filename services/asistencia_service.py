"""Servicio CRUD para asistencias de clientes"""
from datetime import date, datetime, timedelta
from db import get_connection


def registrar_asistencia(cliente_id, fecha=None, hora_entrada=None, hora_salida=None,
                         observacion=None, origen="manual"):
    """Registra o actualiza la asistencia de un cliente en una fecha.
    Si ya existe un registro para ese día, lo actualiza (UPSERT).
    Devuelve (True, id) o (False, mensaje_error).
    """
    if fecha is None:
        fecha = date.today()
    if isinstance(fecha, str):
        fecha = date.fromisoformat(fecha)
    if hora_entrada is None:
        hora_entrada = datetime.now().strftime("%H:%M")

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO asistencias (cliente_id, fecha, hora_entrada, hora_salida, observacion, origen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(cliente_id, fecha) DO UPDATE SET
                hora_entrada = COALESCE(excluded.hora_entrada, hora_entrada),
                hora_salida  = COALESCE(excluded.hora_salida,  hora_salida),
                observacion  = COALESCE(excluded.observacion,  observacion),
                origen       = excluded.origen
        """, (cliente_id, fecha.isoformat(), hora_entrada, hora_salida, observacion, origen))
        conn.commit()
        return True, cur.lastrowid or _id_para(cur, cliente_id, fecha)
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def _id_para(cur, cliente_id, fecha):
    cur.execute("SELECT id FROM asistencias WHERE cliente_id=? AND fecha=?",
                (cliente_id, fecha.isoformat()))
    row = cur.fetchone()
    return row["id"] if row else None


def eliminar_asistencia(cliente_id, fecha):
    """Elimina la asistencia de un cliente en una fecha concreta."""
    if isinstance(fecha, str):
        fecha = date.fromisoformat(fecha)
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM asistencias WHERE cliente_id=? AND fecha=?",
                    (cliente_id, fecha.isoformat()))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def tiene_asistencia(cliente_id, fecha):
    """Devuelve True si el cliente tiene asistencia registrada en esa fecha."""
    if isinstance(fecha, str):
        fecha = date.fromisoformat(fecha)
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM asistencias WHERE cliente_id=? AND fecha=?",
                    (cliente_id, fecha.isoformat()))
        return cur.fetchone() is not None
    finally:
        conn.close()


def obtener_asistencia(cliente_id, fecha):
    """Devuelve el dict de asistencia para esa fecha o None."""
    if isinstance(fecha, str):
        fecha = date.fromisoformat(fecha)
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM asistencias WHERE cliente_id=? AND fecha=?",
                    (cliente_id, fecha.isoformat()))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def listar_asistencias_mes(cliente_id, anio, mes):
    """Devuelve lista de asistencias del cliente en el mes/año dado."""
    from calendar import monthrange
    ultimo_dia = monthrange(anio, mes)[1]
    fecha_ini = date(anio, mes, 1).isoformat()
    fecha_fin = date(anio, mes, ultimo_dia).isoformat()

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT * FROM asistencias
            WHERE cliente_id=? AND fecha BETWEEN ? AND ?
            ORDER BY fecha
        """, (cliente_id, fecha_ini, fecha_fin))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def dias_con_asistencia_mes(cliente_id, anio, mes):
    """Devuelve un set de días (int) en que el cliente asistió en ese mes."""
    asistencias = listar_asistencias_mes(cliente_id, anio, mes)
    return {date.fromisoformat(a["fecha"]).day for a in asistencias}


def listar_asistencias_recientes(cliente_id, limite=20):
    """Devuelve las últimas N asistencias del cliente."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT * FROM asistencias
            WHERE cliente_id=?
            ORDER BY fecha DESC, hora_entrada DESC
            LIMIT ?
        """, (cliente_id, limite))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def contar_asistencias_periodo(cliente_id, fecha_desde, fecha_hasta):
    """Cuenta asistencias del cliente en un período."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT COUNT(*) as cnt FROM asistencias
            WHERE cliente_id=? AND fecha BETWEEN ? AND ?
        """, (cliente_id,
              fecha_desde.isoformat() if isinstance(fecha_desde, date) else fecha_desde,
              fecha_hasta.isoformat() if isinstance(fecha_hasta, date) else fecha_hasta))
        return cur.fetchone()["cnt"]
    finally:
        conn.close()


def ultima_asistencia(cliente_id):
    """Devuelve la fecha de la última asistencia o None."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT fecha FROM asistencias
            WHERE cliente_id=? ORDER BY fecha DESC LIMIT 1
        """, (cliente_id,))
        row = cur.fetchone()
        return row["fecha"] if row else None
    finally:
        conn.close()


def registrar_asistencia_si_no_existe(cliente_id, fecha=None, origen="pago"):
    """Registra asistencia solo si no hay una para ese día (para auto-marcado)."""
    if fecha is None:
        fecha = date.today()
    if isinstance(fecha, str):
        fecha = date.fromisoformat(fecha)
    if not tiene_asistencia(cliente_id, fecha):
        return registrar_asistencia(cliente_id, fecha=fecha, origen=origen)
    return True, None
