"""Constantes de la aplicación"""
import sys
import os
from pathlib import Path

# Nombre de la aplicación
APP_NAME = "Kyo-Gym"

# Ruta de datos de aplicación
# Cuando corre como exe empaquetado (PyInstaller), __file__ apunta a una carpeta
# temporal que se borra al cerrar. En ese caso usar la carpeta donde está el exe.
if getattr(sys, 'frozen', False):
    APP_DATA_DIR = Path(sys.executable).parent
else:
    APP_DATA_DIR = Path(__file__).parent.parent

APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Ruta de la base de datos - estará junto al exe en producción
DB_PATH = APP_DATA_DIR / "gimnasio.db"

# Estados de membresía
ESTADO_ACTIVA = "Activa"
ESTADO_POR_VENCER = "Por Vencer"
ESTADO_VENCIDA = "Vencida"

# Días para considerar "por vencer"
DIAS_ALERTA_VENCIMIENTO = 7
