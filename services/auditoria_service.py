"""Servicio de auditoría global del sistema"""
from db import get_connection


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

def registrar(modulo: str, accion: str, descripcion: str, usuario: str,
              detalles: str = None):
    """
    Inserta un registro en auditoria_global.

    modulo:      'Clientes' | 'Pagos' | 'Membresías' | 'Inventario'
    accion:      'CREAR' | 'MODIFICAR' | 'ELIMINAR' | 'PAGO' | 'RENOVAR' | ...
    descripcion: Texto legible, ej "Pago $500 registrado para Juan Pérez"
    usuario:     username del operador
    detalles:    texto libre adicional (opcional)
    """
    try:
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO auditoria_global (modulo, accion, descripcion, detalles, usuario)
            VALUES (?, ?, ?, ?, ?)
            """,
            (modulo, accion, descripcion, detalles, usuario),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # La auditoría nunca debe interrumpir el flujo principal


# ---------------------------------------------------------------------------
# Lectura (combina auditoria_global + inventario_auditoria)
# ---------------------------------------------------------------------------

def obtener_historial(modulo: str = None, buscar: str = None, limite: int = 500):
    """
    Devuelve el historial global combinando auditoria_global e inventario_auditoria,
    ordenado del más reciente al más antiguo.

    modulo : filtrar por módulo ('Clientes','Pagos','Membresías','Inventario') o None para todos.
    buscar : texto libre que se busca en descripción, acción y usuario.
    limite : nro. máximo de filas a devolver.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # ── Condición de módulo ──────────────────────────────────────────────
    filtro_modulo_global  = "1=1"
    filtro_modulo_inv     = "1=1"
    params_global = []
    params_inv    = []

    if modulo and modulo != "Todos":
        if modulo == "Inventario":
            filtro_modulo_global = "0=1"    # excluir auditoria_global para Inventario
        else:
            filtro_modulo_inv    = "0=1"    # excluir inventario_auditoria para otros módulos
            filtro_modulo_global = "modulo = ?"
            params_global.append(modulo)

    # ── Condición de búsqueda ────────────────────────────────────────────
    filtro_buscar_global = "1=1"
    filtro_buscar_inv    = "1=1"
    if buscar and buscar.strip():
        b = f"%{buscar.strip()}%"
        filtro_buscar_global = "(descripcion LIKE ? OR accion LIKE ? OR usuario LIKE ?)"
        params_global += [b, b, b]
        filtro_buscar_inv = "(producto_nombre LIKE ? OR accion LIKE ? OR usuario LIKE ?)"
        params_inv += [b, b, b]

    query = f"""
        SELECT modulo, accion, descripcion, usuario, fecha_hora
        FROM auditoria_global
        WHERE ({filtro_modulo_global}) AND ({filtro_buscar_global})

        UNION ALL

        SELECT
            'Inventario' AS modulo,
            accion,
            CASE
                WHEN campo IS NOT NULL
                THEN producto_nombre || ' — ' || campo
                     || ': ' || COALESCE(valor_anterior,'?')
                     || ' → ' || COALESCE(valor_nuevo,'?')
                ELSE producto_nombre
            END AS descripcion,
            usuario,
            fecha_hora
        FROM inventario_auditoria
        WHERE ({filtro_modulo_inv}) AND ({filtro_buscar_inv})

        ORDER BY fecha_hora DESC
        LIMIT ?
    """

    cursor.execute(query, params_global + params_inv + [limite])
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Limpieza (solo admin) – solo borra auditoria_global; inventario se conserva
# ---------------------------------------------------------------------------

def limpiar_historial_global():
    """Elimina todos los registros de auditoria_global."""
    conn = get_connection()
    conn.execute("DELETE FROM auditoria_global")
    conn.commit()
    conn.close()
