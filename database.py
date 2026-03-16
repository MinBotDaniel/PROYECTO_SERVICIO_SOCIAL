import sqlite3

NOMBRE_DB = "tienda.db"

def inicializar_tablas():
    conn = sqlite3.connect(NOMBRE_DB)
    cursor = conn.cursor()

    # ==========================================
    # 1. TABLAS CATÁLOGO (Configuración base)
    # ==========================================
    cursor.execute('CREATE TABLE IF NOT EXISTS categorias (id_categoria INTEGER PRIMARY KEY AUTOINCREMENT, categoria TEXT NOT NULL)')
    
    cursor.execute('CREATE TABLE IF NOT EXISTS proveedores (id_proveedor INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, telefono TEXT, email TEXT)')
    
    cursor.execute('CREATE TABLE IF NOT EXISTS empleados (id_empleado INTEGER PRIMARY KEY AUTOINCREMENT, rfc TEXT UNIQUE, nombre TEXT NOT NULL, apaterno TEXT, amaterno TEXT, telefono TEXT, email TEXT)')
    
    cursor.execute('CREATE TABLE IF NOT EXISTS formas_pago (id_forma_pago INTEGER PRIMARY KEY AUTOINCREMENT, forma_pago TEXT NOT NULL)')

    # NUEVA: Tabla de Distribuidoras
    cursor.execute('''CREATE TABLE IF NOT EXISTS distribuidoras (
        id_distribuidora INTEGER PRIMARY KEY AUTOINCREMENT, 
        nombre TEXT NOT NULL, 
        telefono TEXT,
        comision REAL DEFAULT 0
    )''')

    # ==========================================
    # 2. TABLAS PRINCIPALES (Productos y Compras)
    # ==========================================
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos (
        id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
        id_categoria INTEGER,
        descripcion TEXT,
        precio REAL,
        stock INTEGER DEFAULT 0,
        FOREIGN KEY (id_categoria) REFERENCES categorias (id_categoria)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS compras (
        folio_compra INTEGER PRIMARY KEY AUTOINCREMENT,
        id_proveedor INTEGER,
        fecha TEXT,
        sub_total REAL,
        FOREIGN KEY (id_proveedor) REFERENCES proveedores (id_proveedor)
    )''')

    # ==========================================
    # 3. ACTUALIZACIÓN DE TABLA VENTAS (Estructura POS)
    # ==========================================
    # Ejecutamos ALTER TABLE uno por uno para evitar errores de sintaxis
    columnas_nuevas = [
        "ALTER TABLE ventas ADD COLUMN id_empleado INTEGER REFERENCES empleados(id_empleado)",
        "ALTER TABLE ventas ADD COLUMN id_forma_pago INTEGER REFERENCES formas_pago(id_forma_pago)",
        "ALTER TABLE ventas ADD COLUMN tipo_venta TEXT DEFAULT 'CRÉDITO'",
        "ALTER TABLE ventas ADD COLUMN estatus_pago TEXT DEFAULT 'PAGADO'",
        "ALTER TABLE ventas ADD COLUMN id_distribuidora INTEGER REFERENCES distribuidoras(id_distribuidora)",
        "ALTER TABLE ventas ADD COLUMN comision_monto REAL DEFAULT 0"
    ]

    for query in columnas_nuevas:
        try:
            cursor.execute(query)
        except sqlite3.OperationalError:
            pass # Ignora si la columna ya existe

    # Sincronización de datos históricos de los Excel
    # Todo lo migrado es CRÉDITO. El estatus depende del adeudo.
    cursor.execute("UPDATE ventas SET tipo_venta = 'CRÉDITO' WHERE tipo_venta IS NULL")
    cursor.execute("UPDATE ventas SET estatus_pago = 'PENDIENTE' WHERE adeudo > 0")
    cursor.execute("UPDATE ventas SET estatus_pago = 'PAGADO' WHERE adeudo <= 0 OR adeudo IS NULL")

    # ==========================================
    # 4. DETALLES (Movimientos)
    # ==========================================
    cursor.execute('''CREATE TABLE IF NOT EXISTS detalle_compras (
        id_detalle INTEGER PRIMARY KEY AUTOINCREMENT, 
        folio_compra INTEGER, 
        id_producto INTEGER, 
        cantidad INTEGER, 
        precio_compra REAL, 
        FOREIGN KEY (folio_compra) REFERENCES compras (folio_compra), 
        FOREIGN KEY (id_producto) REFERENCES productos (id_producto))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS detalle_ventas (
        id_detalle INTEGER PRIMARY KEY AUTOINCREMENT, 
        id_venta INTEGER, 
        id_producto INTEGER, 
        cantidad INTEGER, 
        precio_venta REAL, 
        FOREIGN KEY (id_venta) REFERENCES ventas (id), 
        FOREIGN KEY (id_producto) REFERENCES productos (id_producto))''')

    # ==========================================
    # 5. RECURSOS HUMANOS
    # ==========================================
    cursor.execute('CREATE TABLE IF NOT EXISTS tipos_empleado (id_tipo INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT)')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS contratos (
        id_contrato INTEGER PRIMARY KEY AUTOINCREMENT, 
        id_empleado INTEGER, 
        id_tipo INTEGER, 
        fecha_inicio TEXT, 
        fecha_fin TEXT, 
        sueldo REAL, 
        FOREIGN KEY (id_empleado) REFERENCES empleados (id_empleado), 
        FOREIGN KEY (id_tipo) REFERENCES tipos_empleado (id_tipo))''')

    # ==========================================
    # 6. VISTAS DE INTELIGENCIA (Reportes automáticos)
    # ==========================================
    
    # Vista 1: Semáforo de Clientes (con JOIN de Pagos)
    cursor.execute("DROP VIEW IF EXISTS clasificacion_clientes")
    cursor.execute('''
    CREATE VIEW clasificacion_clientes AS
    SELECT 
        id, nombre, telefono, (total_comprado - total_pagado) AS adeudo_actual,
        CASE WHEN ultima_venta > ultimo_pago THEN ultima_venta ELSE ultimo_pago END AS ultima_actividad,
        CASE 
            WHEN (total_comprado - total_pagado) > 0 AND ultimo_pago <= date('now', '-6 months') THEN 'ROJO'
            WHEN (total_comprado - total_pagado) > 0 AND ultimo_pago > date('now', '-6 months') THEN 'VERDE'
            WHEN (total_comprado - total_pagado) <= 0 AND ultima_venta >= date('now', '-1 year') THEN 'VERDE'
            WHEN (total_comprado - total_pagado) <= 0 AND ultima_venta < date('now', '-1 year') THEN 'AMARILLO'
            ELSE 'SIN CLASIFICAR'
        END AS tipo_cliente
    FROM (
        SELECT 
            c.id, c.nombre, c.telefono,
            IFNULL((SELECT SUM(total) FROM ventas WHERE cliente_id = c.id), 0) AS total_comprado,
            IFNULL((SELECT MAX(fecha) FROM ventas WHERE cliente_id = c.id), '2000-01-01') AS ultima_venta,
            IFNULL((SELECT SUM(p.monto) FROM pagos p JOIN ventas v ON p.venta_id = v.id WHERE v.cliente_id = c.id), 0) AS total_pagado,
            IFNULL((SELECT MAX(p.fecha) FROM pagos p JOIN ventas v ON p.venta_id = v.id WHERE v.cliente_id = c.id), '2000-01-01') AS ultimo_pago
        FROM clientes c
    )
    ''')

    # Vista 2: Reporte de Comisiones para Distribuidoras
    cursor.execute("DROP VIEW IF EXISTS reporte_comisiones")
    cursor.execute('''
    CREATE VIEW reporte_comisiones AS
    SELECT 
        v.id AS folio_venta,
        v.fecha,
        d.nombre AS distribuidora,
        v.total AS monto_venta,
        v.comision_monto AS comision_a_pagar,
        (v.total - v.comision_monto) AS ingreso_neto_tienda
    FROM ventas v
    JOIN distribuidoras d ON v.id_distribuidora = d.id_distribuidora
    ''')

    # ==========================================
    # 7. TRIGGERS (Automatización de stock)
    # ==========================================
    cursor.execute('''CREATE TRIGGER IF NOT EXISTS restar_inventario_por_venta 
                      AFTER INSERT ON detalle_ventas 
                      BEGIN UPDATE productos SET stock = stock - NEW.cantidad WHERE id_producto = NEW.id_producto; END''')
    
    cursor.execute('''CREATE TRIGGER IF NOT EXISTS sumar_inventario_por_compra 
                      AFTER INSERT ON detalle_compras 
                      BEGIN UPDATE productos SET stock = stock + NEW.cantidad WHERE id_producto = NEW.id_producto; END''')

    conn.commit()
    conn.close()
    print("--- ESTRUCTURA COMPLETADA CON ÉXITO ---")
    print("1. Tablas catálogo y RRHH listas.")
    print("2. Soporte para Distribuidoras y Comisiones activo.")
    print("3. Vistas de clasificación y comisiones creadas.")
    print("4. Triggers de inventario funcionando.")

if __name__ == "__main__":
    inicializar_tablas()