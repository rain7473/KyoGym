"""Gestión de base de datos SQLite"""
import sqlite3
import hashlib
import os
import binascii
from utils.constants import DB_PATH


def get_connection():
    """Obtiene una conexión a la base de datos"""
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Habilitar WAL mode para mejor concurrencia
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def init_database():
    """Inicializa la base de datos y crea las tablas si no existen"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de clientes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT,
            sexo TEXT,
            fecha_nacimiento DATE,
            fecha_registro DATE NOT NULL,
            activo INTEGER DEFAULT 1
        )
    """)
    
    # Tabla de membresías
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS membresias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            fecha_inicio DATE NOT NULL,
            fecha_vencimiento DATE NOT NULL,
            monto REAL NOT NULL,
            pago_id INTEGER,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE,
            FOREIGN KEY (pago_id) REFERENCES pagos(id) ON DELETE SET NULL
        )
    """)
    
    # Tabla de pagos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            fecha DATE NOT NULL,
            monto REAL NOT NULL,
            metodo TEXT NOT NULL,
            concepto TEXT,
            producto_id INTEGER,
            cantidad INTEGER DEFAULT 1,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
        )
    """)

    # Tabla de usuarios (para login)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            full_name TEXT,
            role TEXT DEFAULT 'user',
            created_at DATE DEFAULT (DATE('now')),
            active INTEGER DEFAULT 1
        )
    """)
    
    # Crear índices para mejorar el rendimiento
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_membresias_cliente 
        ON membresias(cliente_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_membresias_vencimiento 
        ON membresias(fecha_vencimiento)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pagos_cliente 
        ON pagos(cliente_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pagos_fecha 
        ON pagos(fecha)
    """)
    
    # Tabla de inventario
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            categoria TEXT NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 0,
            precio REAL DEFAULT 0.0,
            fecha_registro DATE DEFAULT (DATE('now'))
        )
    """)
    
    # Índice para búsquedas rápidas por nombre
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_inventario_nombre 
        ON inventario(nombre)
    """)
    
    # Índice para búsquedas por categoría
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_inventario_categoria 
        ON inventario(categoria)
    """)
    
        # Tabla de historial de movimientos de inventario
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventario_movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            motivo TEXT,
            fecha DATE DEFAULT (DATE('now')),
            FOREIGN KEY (producto_id) REFERENCES inventario(id) ON DELETE CASCADE
        )
    """)

    # Tabla de egresos (gastos del gimnasio)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS egresos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATE NOT NULL,
            categoria TEXT NOT NULL,
            descripcion TEXT,
            proveedor TEXT,
            metodo TEXT NOT NULL,
            monto REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_egresos_fecha
        ON egresos(fecha)
    """)

    # Migraciones: agregar columnas nuevas si no existen
    try:
        cursor.execute("ALTER TABLE clientes ADD COLUMN email TEXT")
    except Exception:
        pass  # Ya existe

    try:
        cursor.execute("ALTER TABLE inventario ADD COLUMN stock_minimo INTEGER DEFAULT 0")
    except Exception:
        pass  # Ya existe

    # Pagos: soportar venta de productos (cantidad) sin romper DBs existentes
    try:
        cursor.execute("ALTER TABLE pagos ADD COLUMN producto_id INTEGER")
    except Exception:
        pass  # Ya existe

    try:
        cursor.execute("ALTER TABLE pagos ADD COLUMN cantidad INTEGER DEFAULT 1")
    except Exception:
        pass  # Ya existe

    conn.commit()
    conn.close()
    
    print(f"Base de datos inicializada en: {DB_PATH}")


def _hash_password(password: str, salt: bytes) -> str:
    """Devuelve el hash hex de sha256(salt + password)."""
    h = hashlib.sha256()
    h.update(salt)
    h.update(password.encode('utf-8'))
    return h.hexdigest()


def create_user(username: str, password: str, full_name: str = None, role: str = 'admin') -> bool:
    """Crea un usuario en la tabla usuarios. Retorna True si se inserta."""
    conn = get_connection()
    cur = conn.cursor()
    # Generar salt
    salt = os.urandom(16)
    salt_hex = binascii.hexlify(salt).decode('ascii')
    pwd_hash = _hash_password(password, salt)
    try:
        cur.execute("""
            INSERT INTO usuarios (username, password_hash, salt, full_name, role, created_at, active)
            VALUES (?, ?, ?, ?, ?, DATE('now'), 1)
        """, (username, pwd_hash, salt_hex, full_name or username, role))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creando usuario: {e}")
        return False
    finally:
        conn.close()


def verify_user(username: str, password: str) -> bool:
    """Verifica credenciales de usuario. Retorna True si coinciden."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT password_hash, salt, active FROM usuarios WHERE username = ?", (username,))
        row = cur.fetchone()
        if not row:
            return False
        if row['active'] == 0:
            return False
        salt_hex = row['salt']
        try:
            salt = binascii.unhexlify(salt_hex)
        except Exception:
            salt = salt_hex.encode('utf-8')
        expected = row['password_hash']
        return _hash_password(password, salt) == expected
    finally:
        conn.close()


def get_user_role(username: str) -> str:
    """Devuelve el rol del usuario ('admin', 'user', etc.) o 'user' si no existe."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT role FROM usuarios WHERE username = ? AND active = 1", (username,))
        row = cur.fetchone()
        return row['role'] if row else 'user'
    finally:
        conn.close()


def get_user_fullname(username: str) -> str:
    """Devuelve el nombre completo del usuario, o el username si no tiene."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT full_name FROM usuarios WHERE username = ? AND active = 1", (username,))
        row = cur.fetchone()
        if row and row['full_name']:
            return row['full_name']
        return username
    finally:
        conn.close()


def get_all_users() -> list:
    """Retorna lista de todos los usuarios activos: [{username, full_name, role}]."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT username, full_name, role FROM usuarios WHERE active = 1 ORDER BY username")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def delete_user(username: str) -> bool:
    """Desactiva (elimina lógicamente) un usuario por su username. Retorna True si tuvo efecto."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE usuarios SET active = 0 WHERE username = ?", (username,))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        print(f"Error eliminando usuario: {e}")
        return False
    finally:
        conn.close()


def ensure_default_user():
    """Crea un usuario por defecto si no existe ninguno."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(1) as cnt FROM sqlite_master WHERE type='table' AND name='usuarios'")
        # si tabla usuarios no existe, nada que hacer aquí (init_database la crea)
        cur.execute("SELECT COUNT(1) as cnt FROM usuarios")
        row = cur.fetchone()
        if row and row['cnt'] == 0:
            # Crear usuario por defecto
            create_user('zahir', 'kaiser2026', full_name='Zahir Lay', role='admin')
            print('Usuario por defecto creado: zahir / kaiser2026')
    except Exception:
        # si algo falla, intentar crear el usuario directamente
        try:
            create_user('zahir', 'kaiser2026', full_name='Zahir Lay', role='admin')
        except Exception:
            pass
    finally:
        conn.close()


if __name__ == "__main__":
    init_database()
