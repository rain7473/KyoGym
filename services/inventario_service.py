"""Servicio CRUD para inventario con auditoría de cambios"""
from datetime import date
from db import get_connection


# ---------------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------------

def obtener_categorias():
    """Devuelve la lista de categorías distintas en el inventario."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT categoria FROM inventario ORDER BY categoria")
    cats = [row[0] for row in cursor.fetchall()]
    conn.close()
    return cats


# ---------------------------------------------------------------------------
# Auditoría (helper interno)
# ---------------------------------------------------------------------------

def _registrar_auditoria(conn, producto_id, producto_nombre, accion, usuario,
                          campo=None, valor_anterior=None, valor_nuevo=None):
    """Inserta un registro en inventario_auditoria dentro de una conexión abierta."""
    conn.execute(
        """
        INSERT INTO inventario_auditoria
            (producto_id, producto_nombre, accion, campo,
             valor_anterior, valor_nuevo, usuario)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            producto_id,
            producto_nombre,
            accion,
            campo,
            str(valor_anterior) if valor_anterior is not None else None,
            str(valor_nuevo)    if valor_nuevo    is not None else None,
            usuario,
        ),
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def crear_producto(nombre, categoria, cantidad=0, precio=0.0, stock_minimo=0,
                   usuario="admin"):
    """Crea un nuevo producto en el inventario y registra la acción en auditoría."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO inventario (nombre, categoria, cantidad, precio, fecha_registro, stock_minimo)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (nombre, categoria, cantidad, precio, date.today().isoformat(), stock_minimo),
    )
    producto_id = cursor.lastrowid

    _registrar_auditoria(
        conn, producto_id, nombre, "CREAR", usuario,
        valor_nuevo=(
            f"categoría={categoria}, cantidad={cantidad}, "
            f"precio={precio:.2f}, stock_min={stock_minimo}"
        ),
    )

    conn.commit()
    conn.close()
    return producto_id


def obtener_producto(producto_id):
    """Obtiene un producto por ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventario WHERE id = ?", (producto_id,))
    producto = cursor.fetchone()
    conn.close()
    return dict(producto) if producto else None


def listar_productos(buscar="", categoria=None):
    """Lista productos con búsqueda opcional y filtro por categoría."""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM inventario WHERE 1=1"
    params = []

    if buscar:
        query += " AND nombre LIKE ?"
        params.append(f"%{buscar}%")

    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)

    query += " ORDER BY nombre ASC"
    cursor.execute(query, params)
    productos = cursor.fetchall()
    conn.close()
    return [dict(p) for p in productos]


def actualizar_producto(producto_id, nombre, categoria, cantidad, precio,
                        stock_minimo=0, usuario="admin"):
    """Actualiza un producto y registra en auditoría cada campo modificado."""
    conn = get_connection()
    cursor = conn.cursor()

    # Capturar valores actuales para comparar
    cursor.execute("SELECT * FROM inventario WHERE id = ?", (producto_id,))
    anterior = cursor.fetchone()

    cursor.execute(
        """
        UPDATE inventario
        SET nombre = ?, categoria = ?, cantidad = ?, precio = ?, stock_minimo = ?
        WHERE id = ?
        """,
        (nombre, categoria, cantidad, precio, stock_minimo, producto_id),
    )

    if anterior:
        campos = [
            ("nombre",       anterior["nombre"],            nombre),
            ("categoria",    anterior["categoria"],         categoria),
            ("cantidad",     anterior["cantidad"],          cantidad),
            ("precio",       float(anterior["precio"]),     float(precio)),
            ("stock_minimo", anterior["stock_minimo"] or 0, stock_minimo),
        ]
        for campo, val_ant, val_nuevo in campos:
            if str(val_ant) != str(val_nuevo):
                _registrar_auditoria(
                    conn, producto_id, nombre, "MODIFICAR", usuario,
                    campo=campo, valor_anterior=val_ant, valor_nuevo=val_nuevo,
                )

    conn.commit()
    conn.close()


def eliminar_producto(producto_id, usuario="admin"):
    """Elimina un producto y registra la acción en auditoría."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT nombre FROM inventario WHERE id = ?", (producto_id,))
    row = cursor.fetchone()
    nombre = row["nombre"] if row else "Desconocido"

    # Auditoría antes de eliminar (FK en auditoria es SET NULL implícito)
    _registrar_auditoria(conn, producto_id, nombre, "ELIMINAR", usuario)

    cursor.execute("DELETE FROM inventario WHERE id = ?", (producto_id,))
    conn.commit()
    conn.close()


def actualizar_cantidad(producto_id, cantidad):
    """Actualiza solo la cantidad de un producto (operación interna de ventas)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE inventario SET cantidad = ? WHERE id = ?",
        (cantidad, producto_id),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Historial / Auditoría
# ---------------------------------------------------------------------------

def obtener_historial_producto(producto_id):
    """Devuelve el historial de auditoría de un producto, ordenado del más reciente al más antiguo."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, producto_nombre, accion, campo,
               valor_anterior, valor_nuevo, usuario, fecha_hora
        FROM inventario_auditoria
        WHERE producto_id = ?
        ORDER BY id DESC
        """,
        (producto_id,),
    )
    historial = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return historial


# ---------------------------------------------------------------------------
# Importación masiva
# ---------------------------------------------------------------------------

def importar_productos_masivo(productos, usuario="admin"):
    """
    Inserta en lote una lista de productos previamente validados.
    Omite duplicados por nombre (case-insensitive).
    Devuelve (insertados, duplicados).
    """
    conn = get_connection()
    cursor = conn.cursor()
    insertados = 0
    duplicados = 0

    for p in productos:
        cursor.execute(
            "SELECT id FROM inventario WHERE LOWER(nombre) = LOWER(?)",
            (p["nombre"],),
        )
        if cursor.fetchone():
            duplicados += 1
            continue

        cursor.execute(
            """
            INSERT INTO inventario
                (nombre, categoria, cantidad, precio, fecha_registro, stock_minimo)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                p["nombre"], p["categoria"], p["cantidad"], p["precio"],
                date.today().isoformat(), p.get("stock_minimo", 0),
            ),
        )
        producto_id = cursor.lastrowid
        _registrar_auditoria(
            conn, producto_id, p["nombre"], "IMPORTAR", usuario,
            valor_nuevo=(
                f"categoría={p['categoria']}, cantidad={p['cantidad']}, "
                f"precio={p['precio']:.2f}"
            ),
        )
        insertados += 1

    conn.commit()
    conn.close()
    return insertados, duplicados


def obtener_categorias():
    """Obtiene todas las categorías únicas del inventario"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT categoria FROM inventario
        ORDER BY categoria ASC
    """)
    
    categorias = cursor.fetchall()
    conn.close()
    
    return [cat['categoria'] for cat in categorias]


def contar_productos():
    """Cuenta el total de productos en inventario"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as total FROM inventario")
    resultado = cursor.fetchone()
    conn.close()
    
    return resultado['total'] if resultado else 0


def calcular_valor_total():
    """Calcula el valor total del inventario (cantidad * precio)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT SUM(cantidad * precio) as valor_total 
        FROM inventario
    """)
    
    resultado = cursor.fetchone()
    conn.close()
    
    return resultado['valor_total'] if resultado and resultado['valor_total'] else 0.0


def productos_bajo_stock(minimo=5):
    """Lista productos con stock bajo el mínimo especificado"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM inventario 
        WHERE cantidad < ?
        ORDER BY cantidad ASC
    """, (minimo,))
    
    productos = cursor.fetchall()
    conn.close()
    
    return [dict(producto) for producto in productos]

def vender_producto(producto_id, cantidad, motivo="Venta de producto"):
    """Descuenta inventario y registra movimiento automáticamente"""
    conn = get_connection()
    cursor = conn.cursor()

    # Obtener stock actual
    cursor.execute("SELECT cantidad FROM inventario WHERE id = ?", (producto_id,))
    producto = cursor.fetchone()

    if not producto:
        conn.close()
        return False, "Producto no existe"

    stock_actual = producto["cantidad"]

    if stock_actual < cantidad:
        conn.close()
        return False, "Stock insuficiente"

    # Descontar inventario
    nuevo_stock = stock_actual - cantidad
    cursor.execute("""
        UPDATE inventario
        SET cantidad = ?
        WHERE id = ?
    """, (nuevo_stock, producto_id))

    # Registrar movimiento en historial
    cursor.execute("""
        INSERT INTO inventario_movimientos (producto_id, tipo, cantidad, motivo)
        VALUES (?, 'SALIDA', ?, ?)
    """, (producto_id, cantidad, motivo))

    conn.commit()
    conn.close()

    return True, "Venta registrada correctamente"

def agregar_stock(producto_id, cantidad, motivo="Ingreso de stock"):
    """Aumenta inventario y registra movimiento"""
    conn = get_connection()
    cursor = conn.cursor()

    # Aumentar inventario
    cursor.execute("""
        UPDATE inventario
        SET cantidad = cantidad + ?
        WHERE id = ?
    """, (cantidad, producto_id))

    # Registrar movimiento
    cursor.execute("""
        INSERT INTO inventario_movimientos (producto_id, tipo, cantidad, motivo)
        VALUES (?, 'ENTRADA', ?, ?)
    """, (producto_id, cantidad, motivo))

    conn.commit()
    conn.close()

def obtener_stock_bajo():
    from db import get_connection
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nombre, cantidad, stock_minimo
        FROM inventario
        WHERE cantidad <= stock_minimo
    """)

    productos = cursor.fetchall()
    conn.close()
    return productos

