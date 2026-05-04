"""Servicio CRUD para clientes"""
from datetime import date
from db import get_connection
from services import auditoria_service
from usuario_activo import obtener_usuario_activo


def verificar_telefono_existente(telefono, excluir_id=None):
    """Verifica si un teléfono ya está registrado para otro cliente"""
    if not telefono or telefono.strip() == "":
        return False
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if excluir_id:
        cursor.execute("""
            SELECT id, nombre FROM clientes WHERE telefono = ? AND id != ?
        """, (telefono, excluir_id))
    else:
        cursor.execute("""
            SELECT id, nombre FROM clientes WHERE telefono = ?
        """, (telefono,))
    
    cliente = cursor.fetchone()
    conn.close()
    return dict(cliente) if cliente else None


def crear_cliente(nombre, telefono="", sexo="", fecha_nacimiento=None, email=""):
    """Crea un nuevo cliente"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO clientes (nombre, telefono, sexo, fecha_nacimiento, fecha_registro, email)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (nombre, telefono, sexo, fecha_nacimiento, date.today().isoformat(), email))
    
    cliente_id = cursor.lastrowid
    conn.commit()
    conn.close()
    auditoria_service.registrar(
        modulo='Clientes',
        accion='CREAR',
        descripcion=f'Cliente "{nombre}" registrado'
            + (f' — Tel: {telefono}' if telefono else ''),
        usuario=obtener_usuario_activo(),
    )
    return cliente_id


def obtener_cliente(cliente_id):
    """Obtiene un cliente por ID"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM clientes WHERE id = ?
    """, (cliente_id,))
    
    cliente = cursor.fetchone()
    conn.close()
    return dict(cliente) if cliente else None


def listar_clientes(buscar="", solo_activos=True):
    """Lista todos los clientes con opción de búsqueda"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM clientes WHERE 1=1"
    params = []
    
    if solo_activos:
        query += " AND activo = 1"
    
    if buscar:
        query += " AND (nombre LIKE ? COLLATE NOCASE OR telefono LIKE ? COLLATE NOCASE)"
        buscar_param = f"%{buscar}%"
        params.extend([buscar_param, buscar_param])
    
    query += " ORDER BY nombre"
    
    cursor.execute(query, params)
    clientes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return clientes


def actualizar_cliente(cliente_id, nombre, telefono="", sexo="", fecha_nacimiento=None, email=""):
    """Actualiza los datos de un cliente"""
    conn = get_connection()
    cursor = conn.cursor()
    # Capturar nombre anterior para log
    cursor.execute("SELECT nombre FROM clientes WHERE id = ?", (cliente_id,))
    row = cursor.fetchone()
    nombre_anterior = row['nombre'] if row else nombre

    cursor.execute("""
        UPDATE clientes 
        SET nombre = ?, telefono = ?, sexo = ?, fecha_nacimiento = ?, email = ?
        WHERE id = ?
    """, (nombre, telefono, sexo, fecha_nacimiento, email, cliente_id))

    conn.commit()
    conn.close()
    auditoria_service.registrar(
        modulo='Clientes',
        accion='MODIFICAR',
        descripcion=f'Cliente "{nombre_anterior}" actualizado'
            + (f' (nuevo nombre: "{nombre}")' if nombre != nombre_anterior else ''),
        usuario=obtener_usuario_activo(),
    )


def eliminar_cliente(cliente_id):
    """Desactiva un cliente (soft delete)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nombre FROM clientes WHERE id = ?", (cliente_id,))
    row = cursor.fetchone()
    nombre = row['nombre'] if row else f'ID {cliente_id}'

    cursor.execute("""
        UPDATE clientes SET activo = 0 WHERE id = ?
    """, (cliente_id,))

    conn.commit()
    conn.close()
    auditoria_service.registrar(
        modulo='Clientes',
        accion='ELIMINAR',
        descripcion=f'Cliente "{nombre}" eliminado (desactivado)',
        usuario=obtener_usuario_activo(),
    )


def buscar_clientes_por_nombre(nombre):
    """Busca clientes por nombre (para autocompletado)"""
    return listar_clientes(buscar=nombre)


def contar_clientes_por_sexo():
    """Cuenta clientes por sexo"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT sexo, COUNT(*) as cantidad
        FROM clientes
        WHERE activo = 1 AND sexo IS NOT NULL AND sexo != ''
        GROUP BY sexo
    """)
    
    resultado = {'Masculino': 0, 'Femenino': 0, 'Otro': 0}
    for row in cursor.fetchall():
        sexo = row['sexo']
        cantidad = row['cantidad']
        if sexo in resultado:
            resultado[sexo] = cantidad
    
    conn.close()
    return resultado


def obtener_cumpleaneros_hoy():
    """Retorna clientes activos que cumplen años hoy (mismo mes y día)"""
    hoy = date.today()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM clientes
        WHERE activo = 1
          AND fecha_nacimiento IS NOT NULL
          AND strftime('%m', fecha_nacimiento) = ?
          AND strftime('%d', fecha_nacimiento) = ?
    """, (f"{hoy.month:02d}", f"{hoy.day:02d}"))
    clientes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return clientes
