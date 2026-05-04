"""Servicio CRUD para pagos"""
from datetime import date, datetime
from db import get_connection
from services.inventario_service import vender_producto
from services import auditoria_service
from usuario_activo import obtener_usuario_activo


def _auto_asistencia(cliente_id, fecha_pago):
    """Auto-registra asistencia en la fecha del pago si no existe ya.
    Se activa solo cuando el cliente tiene alguna membersía registrada."""
    try:
        from db import get_connection as _gc
        conn = _gc()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM membresias WHERE cliente_id=?", (cliente_id,))
        tiene = cur.fetchone()["cnt"] > 0
        conn.close()
        if tiene:
            from services.asistencia_service import registrar_asistencia_si_no_existe
            registrar_asistencia_si_no_existe(cliente_id, fecha=fecha_pago, origen="pago")
    except Exception:
        pass  # No bloquear el flujo principal


def crear_pago(cliente_id, monto, metodo, fecha_pago=None, concepto="", producto_id=None, cantidad=1):
    """Registra un nuevo pago y descuenta inventario si es producto"""

    # Normalizar cantidad
    try:
        cantidad = int(cantidad) if cantidad is not None else 1
    except Exception:
        cantidad = 1
    if cantidad <= 0:
        return False, "Cantidad inválida"

    # Si es venta de producto, descontar primero.
    # Nota: en la UI el 'concepto' se guarda como nombre del producto,
    # por eso no podemos depender de concepto == 'Producto'.
    if producto_id is not None:
        ok, mensaje = vender_producto(producto_id, cantidad)
        if not ok:
            return False, mensaje  # No registrar pago si falla stock

    conn = get_connection()
    cursor = conn.cursor()

    if fecha_pago is None:
        fecha_pago = date.today()
    elif isinstance(fecha_pago, str):
        fecha_pago = date.fromisoformat(fecha_pago)

    # Insert compatible con DBs antiguas (sin columnas de producto/cantidad)
    try:
        cursor.execute("""
            INSERT INTO pagos (cliente_id, fecha, monto, metodo, concepto, producto_id, cantidad)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cliente_id, fecha_pago.isoformat(), monto, metodo, concepto, producto_id, cantidad))
    except Exception:
        cursor.execute("""
            INSERT INTO pagos (cliente_id, fecha, monto, metodo, concepto)
            VALUES (?, ?, ?, ?, ?)
        """, (cliente_id, fecha_pago.isoformat(), monto, metodo, concepto))

    pago_id = cursor.lastrowid
    conn.commit()
    conn.close()
    _auto_asistencia(cliente_id, fecha_pago)
    try:
        from services import cliente_service as _cs
        _cli = _cs.obtener_cliente(cliente_id)
        _nombre_cli = _cli['nombre'] if _cli else f'ID {cliente_id}'
    except Exception:
        _nombre_cli = f'ID {cliente_id}'
    auditoria_service.registrar(
        modulo='Pagos',
        accion='PAGO',
        descripcion=f'Pago ${monto:.2f} ({metodo}) para "{_nombre_cli}"'
            + (f' — {concepto}' if concepto else ''),
        usuario=obtener_usuario_activo(),
        detalles=f'pago_id={pago_id}, fecha={fecha_pago.isoformat()}'
            + (f', producto_id={producto_id}, cantidad={cantidad}' if producto_id else ''),
    )
    return True, pago_id


def crear_pago_multiple(cliente_id, monto, metodo, items, concepto="", fecha_pago=None):
    """Registra un pago con múltiples ítems (días y/o productos).

    items: lista de dicts con las claves:
        tipo        ('dia' | 'producto' | 'otro')
        nombre      str
        producto_id int | None
        cantidad    int
        precio_unit float
        subtotal    float
    Descuenta inventario por cada producto antes de insertar el pago.
    Si cualquier descuento de stock falla, aborta sin registrar el pago.
    """
    # ── 1. Verificar y descontar stock de todos los productos ────
    for item in items:
        if item.get('tipo') == 'producto' and item.get('producto_id') is not None:
            ok, mensaje = vender_producto(item['producto_id'], item['cantidad'])
            if not ok:
                return False, f"Stock insuficiente para '{item['nombre']}': {mensaje}"

    # ── 2. Insertar el pago ──────────────────────────────────────
    conn = get_connection()
    cursor = conn.cursor()

    if fecha_pago is None:
        fecha_pago = date.today()
    elif isinstance(fecha_pago, str):
        fecha_pago = date.fromisoformat(fecha_pago)

    try:
        cursor.execute("""
            INSERT INTO pagos (cliente_id, fecha, monto, metodo, concepto)
            VALUES (?, ?, ?, ?, ?)
        """, (cliente_id, fecha_pago.isoformat(), monto, metodo, concepto))
    except Exception as e:
        conn.close()
        return False, str(e)

    pago_id = cursor.lastrowid
    conn.commit()
    conn.close()
    _auto_asistencia(cliente_id, fecha_pago)
    try:
        from services import cliente_service as _cs2
        _cli2 = _cs2.obtener_cliente(cliente_id)
        _nombre_cli2 = _cli2['nombre'] if _cli2 else f'ID {cliente_id}'
    except Exception:
        _nombre_cli2 = f'ID {cliente_id}'
    _items_desc = ', '.join(
        f"{it.get('nombre','?')} x{it.get('cantidad',1)}" for it in items
    ) if items else ''
    auditoria_service.registrar(
        modulo='Pagos',
        accion='PAGO',
        descripcion=f'Pago ${monto:.2f} ({metodo}) para "{_nombre_cli2}"'
            + (f' — {concepto}' if concepto else ''),
        usuario=obtener_usuario_activo(),
        detalles=f'pago_id={pago_id}, fecha={fecha_pago.isoformat()}, ítems: {_items_desc}',
    )
    return True, pago_id


def obtener_pago(pago_id: int):
    """Obtiene un pago por ID con información del cliente."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, c.nombre as cliente_nombre
        FROM pagos p
        JOIN clientes c ON p.cliente_id = c.id
        WHERE p.id = ?
    """, (pago_id,))
    pago = cursor.fetchone()
    conn.close()
    return dict(pago) if pago else None


def listar_pagos(cliente_id=None, fecha_desde=None, fecha_hasta=None, limite=100):
    """Lista pagos con filtros opcionales"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT p.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
        FROM pagos p
        JOIN clientes c ON p.cliente_id = c.id
        WHERE 1=1
    """
    params = []
    
    if cliente_id:
        query += " AND p.cliente_id = ?"
        params.append(cliente_id)
    
    if fecha_desde:
        query += " AND p.fecha >= ?"
        params.append(fecha_desde if isinstance(fecha_desde, str) else fecha_desde.isoformat())
    
    if fecha_hasta:
        query += " AND p.fecha <= ?"
        params.append(fecha_hasta if isinstance(fecha_hasta, str) else fecha_hasta.isoformat())
    
    query += " ORDER BY p.fecha DESC, p.id DESC LIMIT ?"
    params.append(limite)
    
    cursor.execute(query, params)
    pagos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return pagos


def obtener_pagos_del_mes(año=None, mes=None):
    """Obtiene todos los pagos del mes actual o del mes especificado"""
    if año is None or mes is None:
        hoy = date.today()
        año = hoy.year
        mes = hoy.month
    
    # Primer día del mes
    fecha_desde = date(año, mes, 1)
    
    # Último día del mes
    if mes == 12:
        fecha_hasta = date(año, 12, 31)
    else:
        fecha_hasta = date(año, mes + 1, 1)
        fecha_hasta = fecha_hasta.replace(day=1)
        from datetime import timedelta
        fecha_hasta = fecha_hasta - timedelta(days=1)
    
    return listar_pagos(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, limite=1000)


def calcular_total_mes(año=None, mes=None):
    """Calcula el total de pagos del mes"""
    pagos = obtener_pagos_del_mes(año, mes)
    return sum(pago['monto'] for pago in pagos)


def obtener_ultimos_pagos(limite=5):
    """Obtiene los últimos pagos registrados"""
    return listar_pagos(limite=limite)


def obtener_historial_pagos_cliente(cliente_id):
    """Obtiene todo el historial de pagos de un cliente"""
    return listar_pagos(cliente_id=cliente_id, limite=1000)


def actualizar_pago(pago_id, cliente_id, monto, metodo, fecha_pago, concepto=""):
    """Actualiza un pago existente"""
    conn = get_connection()
    cursor = conn.cursor()
    
    if isinstance(fecha_pago, date):
        fecha_pago = fecha_pago.isoformat()
    
    cursor.execute("""
        UPDATE pagos
        SET cliente_id = ?, fecha = ?, monto = ?, metodo = ?, concepto = ?
        WHERE id = ?
    """, (cliente_id, fecha_pago, monto, metodo, concepto, pago_id))
    
    conn.commit()
    conn.close()


def eliminar_pago(pago_id):
    """Elimina un pago y la membresía vinculada a él (si existe)"""
    conn = get_connection()
    cursor = conn.cursor()

    # Buscar si hay una membresía que referencia este pago
    cursor.execute("SELECT id FROM membresias WHERE pago_id = ?", (pago_id,))
    row = cursor.fetchone()
    membresia_id = row['id'] if row else None

    if membresia_id:
        cursor.execute("DELETE FROM membresias WHERE id = ?", (membresia_id,))

    cursor.execute("DELETE FROM pagos WHERE id = ?", (pago_id,))

    conn.commit()
    conn.close()

    # Eliminar factura PDF de la membresía si existía
    if membresia_id:
        try:
            from pathlib import Path
            ruta = Path.home() / "KyoGym" / "Facturas" / f"Factura_{membresia_id}.pdf"
            if ruta.exists():
                ruta.unlink()
        except Exception:
            pass

    return membresia_id  # Devuelve el id eliminado o None

