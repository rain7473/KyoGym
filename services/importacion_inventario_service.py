"""Servicio de importación masiva de productos al inventario desde Excel y PDF"""


def _mapear_columna(header):
    """Mapea un nombre de columna del archivo al campo interno del sistema."""
    h = str(header).strip().lower()
    mapping = {
        "nombre":       ["nombre", "name", "producto", "product", "descripcion", "descripción"],
        "categoria":    ["categoria", "categoría", "category", "tipo", "type"],
        "cantidad":     ["cantidad", "quantity", "stock", "qty", "inventario"],
        "precio":       ["precio", "price", "costo", "cost", "valor", "value"],
        "stock_minimo": ["stock_minimo", "stock minimo", "stock mínimo", "min_stock",
                         "minimo", "mínimo", "stock_min"],
    }
    for campo, aliases in mapping.items():
        if h in aliases:
            return campo
    return None


def leer_excel(filepath):
    """
    Lee un archivo Excel (.xlsx) y devuelve una lista de dicts crudos
    con los campos encontrados en las columnas.
    """
    try:
        import openpyxl
    except ImportError:
        raise ImportError(
            "openpyxl no está instalado. Instálalo con: pip install openpyxl"
        )

    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return []

    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    col_map = {}
    for i, h in enumerate(headers):
        campo = _mapear_columna(h)
        if campo:
            col_map[campo] = i

    productos = []
    for row in rows[1:]:
        if all(v is None or str(v).strip() == "" for v in row):
            continue
        producto = {}
        for campo, idx in col_map.items():
            val = row[idx] if idx < len(row) else None
            producto[campo] = val
        if producto:
            productos.append(producto)

    return productos


def leer_pdf(filepath):
    """
    Lee un archivo PDF y extrae datos de tablas usando pdfplumber.
    Devuelve una lista de dicts crudos.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError(
            "pdfplumber no está instalado. Instálalo con: pip install pdfplumber"
        )

    productos = []
    col_map = None

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue

                headers = [str(h).strip() if h is not None else "" for h in table[0]]

                if col_map is None:
                    col_map = {}
                    for i, h in enumerate(headers):
                        campo = _mapear_columna(h)
                        if campo:
                            col_map[campo] = i

                start = 1 if col_map else 0
                for row in table[start:]:
                    if not row or all(v is None or str(v).strip() == "" for v in row):
                        continue
                    producto = {}
                    if col_map:
                        for campo, idx in col_map.items():
                            val = row[idx] if idx < len(row) else None
                            producto[campo] = val
                    else:
                        # Sin encabezados reconocidos: mapear por posición
                        if len(row) >= 1:
                            producto["nombre"] = row[0]
                        if len(row) >= 2:
                            producto["categoria"] = row[1]
                        if len(row) >= 3:
                            try:
                                producto["cantidad"] = int(row[2])
                            except (ValueError, TypeError):
                                pass
                        if len(row) >= 4:
                            try:
                                producto["precio"] = float(
                                    str(row[3]).replace("$", "").replace(",", ".").strip()
                                )
                            except (ValueError, TypeError):
                                pass
                    if producto:
                        productos.append(producto)

    return productos


def validar_productos(productos_raw):
    """
    Valida y normaliza una lista de productos crudos.
    Devuelve una lista de dicts con los campos normalizados
    y una clave 'errores' (lista de strings, vacía si es válido).
    """
    CATEGORIAS_VALIDAS = ["Suplementos", "Equipamiento", "Accesorios", "Bebidas", "Otros"]
    resultado = []

    for raw in productos_raw:
        errores = []
        producto = {
            "nombre": "",
            "categoria": "Otros",
            "cantidad": 0,
            "precio": 0.0,
            "stock_minimo": 0,
            "errores": [],
        }

        # Nombre
        nombre = str(raw.get("nombre", "") or "").strip()
        if not nombre:
            errores.append("Nombre requerido")
        elif len(nombre) > 100:
            errores.append("Nombre demasiado largo (máx. 100 caracteres)")
        else:
            producto["nombre"] = nombre

        # Categoría
        cat_raw = str(raw.get("categoria", "") or "").strip()
        if not cat_raw:
            producto["categoria"] = "Otros"
        else:
            cat_match = next(
                (c for c in CATEGORIAS_VALIDAS if c.lower() == cat_raw.lower()), None
            )
            producto["categoria"] = cat_match if cat_match else cat_raw

        # Cantidad
        try:
            cantidad = int(float(str(raw.get("cantidad", 0) or 0)))
            if cantidad < 0:
                errores.append("La cantidad no puede ser negativa")
            else:
                producto["cantidad"] = cantidad
        except (ValueError, TypeError):
            errores.append(f"Cantidad inválida: '{raw.get('cantidad')}'")

        # Precio
        try:
            precio_str = (
                str(raw.get("precio", 0) or 0)
                .replace("$", "")
                .replace(",", ".")
                .strip()
            )
            precio = float(precio_str)
            if precio < 0:
                errores.append("El precio no puede ser negativo")
            else:
                producto["precio"] = precio
        except (ValueError, TypeError):
            errores.append(f"Precio inválido: '{raw.get('precio')}'")

        # Stock mínimo (opcional, sin error si falla)
        try:
            sm = int(float(str(raw.get("stock_minimo", 0) or 0)))
            producto["stock_minimo"] = max(0, sm)
        except (ValueError, TypeError):
            producto["stock_minimo"] = 0

        producto["errores"] = errores
        resultado.append(producto)

    return resultado
