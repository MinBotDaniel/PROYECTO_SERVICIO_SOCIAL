import sqlite3

NOMBRE_DB = "tienda.db"

def inicializar_tablas():
    conn = sqlite3.connect(NOMBRE_DB)
    cursor = conn.cursor()

    # ==========================================
    # 1. TABLAS CATÁLOGO
    # ==========================================
    cursor.execute('CREATE TABLE IF NOT EXISTS categorias (id_categoria INTEGER PRIMARY KEY AUTOINCREMENT, categoria TEXT NOT NULL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS proveedores (id_proveedor INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, telefono TEXT, email TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS empleados (id_empleado INTEGER PRIMARY KEY AUTOINCREMENT, rfc TEXT UNIQUE, nombre TEXT NOT NULL, apaterno TEXT, amaterno TEXT, telefono TEXT, email TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS formas_pago (id_forma_pago INTEGER PRIMARY KEY AUTOINCREMENT, forma_pago TEXT NOT NULL)')
    
    # Nombre original: comision
    cursor.execute('''CREATE TABLE IF NOT EXISTS distribuidoras (
        id_distribuidora INTEGER PRIMARY KEY AUTOINCREMENT, 
        nombre TEXT NOT NULL, 
        telefono TEXT,
        comision REAL DEFAULT 0
    )''')

    # ==========================================
    # 2. TABLAS PRINCIPALES
    # ==========================================
    # MODIFICACIÓN: Se agrega fecha_registro por defecto a la fecha y hora actual del sistema local
    cursor.execute('CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, domicilio TEXT, telefono TEXT, fecha_registro TEXT DEFAULT (datetime(\'now\', \'localtime\')))')

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
    # 3. ACTUALIZACIÓN DE TABLAS
    # ==========================================
    columnas_nuevas = [
        "ALTER TABLE ventas ADD COLUMN id_empleado INTEGER REFERENCES empleados(id_empleado)",
        "ALTER TABLE ventas ADD COLUMN id_forma_pago INTEGER REFERENCES formas_pago(id_forma_pago)",
        "ALTER TABLE ventas ADD COLUMN tipo_venta TEXT DEFAULT 'CRÉDITO'",
        "ALTER TABLE ventas ADD COLUMN estatus_pago TEXT DEFAULT 'PAGADO'",
        "ALTER TABLE ventas ADD COLUMN id_distribuidora INTEGER REFERENCES distribuidoras(id_distribuidora)",
        "ALTER TABLE clientes ADD COLUMN fecha_registro TEXT DEFAULT (datetime('now', 'localtime'))" # MODIFICACIÓN: Alter table para clientes existentes
    ]

    for query in columnas_nuevas:
        try:
            cursor.execute(query)
        except sqlite3.OperationalError:
            pass 

    # ==========================================
    # 4. SISTEMA DE COMISIONES Y PAGOS
    # ==========================================
    cursor.execute('''CREATE TABLE IF NOT EXISTS registro_comisiones (
        id_comision INTEGER PRIMARY KEY AUTOINCREMENT,
        id_venta INTEGER UNIQUE, 
        id_distribuidora INTEGER,
        monto_venta_total REAL,
        monto_comision REAL,
        adeudo_comision REAL, 
        fecha_registro TEXT,
        estatus_pago_distribuidora TEXT DEFAULT 'PENDIENTE', 
        FOREIGN KEY (id_venta) REFERENCES ventas (id),
        FOREIGN KEY (id_distribuidora) REFERENCES distribuidoras (id_distribuidora)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS pagos_distribuidoras (
        id_pago_dist INTEGER PRIMARY KEY AUTOINCREMENT,
        id_comision INTEGER,
        monto_pagado REAL,
        fecha_pago TEXT,
        metodo_pago TEXT,
        FOREIGN KEY (id_comision) REFERENCES registro_comisiones (id_comision)
    )''')

    # ==========================================
    # 5. DETALLES Y RRHH
    # ==========================================
    cursor.execute('''CREATE TABLE IF NOT EXISTS detalle_compras (id_detalle INTEGER PRIMARY KEY AUTOINCREMENT, folio_compra INTEGER, id_producto INTEGER, cantidad INTEGER, precio_compra REAL, FOREIGN KEY (folio_compra) REFERENCES compras (folio_compra), FOREIGN KEY (id_producto) REFERENCES productos (id_producto))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS detalle_ventas (id_detalle INTEGER PRIMARY KEY AUTOINCREMENT, id_venta INTEGER, id_producto INTEGER, cantidad INTEGER, precio_venta REAL, FOREIGN KEY (id_venta) REFERENCES ventas (id), FOREIGN KEY (id_producto) REFERENCES productos (id_producto))''')
    cursor.execute('CREATE TABLE IF NOT EXISTS tipos_empleado (id_tipo INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT)')
    cursor.execute('''CREATE TABLE IF NOT EXISTS contratos (id_contrato INTEGER PRIMARY KEY AUTOINCREMENT, id_empleado INTEGER, id_tipo INTEGER, fecha_inicio TEXT, fecha_fin TEXT, sueldo REAL, FOREIGN KEY (id_empleado) REFERENCES empleados (id_empleado), FOREIGN KEY (id_tipo) REFERENCES tipos_empleado (id_tipo))''')

    # ==========================================
    # 6. REPORTES (VISTAS)
    # ==========================================
    
    # MODIFICACIÓN: Lógica de la vista centralizada, incluyendo fecha_registro y arreglando el bug de ROJO
    cursor.execute("DROP VIEW IF EXISTS clasificacion_clientes")
    cursor.execute('''
    CREATE VIEW clasificacion_clientes AS
    SELECT id, nombre, domicilio, telefono, fecha_registro, adeudo_actual, ultima_actividad,
    CASE WHEN adeudo_actual > 0 AND ultima_actividad <= date('now', '-2 year') THEN 'ROJO'
         WHEN adeudo_actual > 0 AND ultima_actividad >= date('now', '-6 months') THEN 'VERDE'
         WHEN adeudo_actual <= 0 AND ultima_venta >= date('now', '-1 year') THEN 'VERDE'
         WHEN adeudo_actual > 0 AND ultima_actividad < date('now', '-6 months') THEN 'AMARILLO'
         WHEN adeudo_actual <= 0 AND ultima_venta <= date('now', '-2 year') THEN 'AMARILLO'
         ELSE 'SIN CLASIFICAR' END AS tipo_cliente
    FROM (
        SELECT id, nombre, domicilio, telefono, fecha_registro, (total_comprado - total_pagado) AS adeudo_actual,
               CASE WHEN ultima_venta > ultimo_pago THEN ultima_venta ELSE ultimo_pago END AS ultima_actividad,
               ultima_venta
        FROM (SELECT c.id, c.nombre, c.domicilio, c.telefono, c.fecha_registro,
              IFNULL((SELECT SUM(total) FROM ventas WHERE cliente_id = c.id), 0) AS total_comprado,
              IFNULL((SELECT MAX(fecha) FROM ventas WHERE cliente_id = c.id), '2000-01-01') AS ultima_venta,
              IFNULL((SELECT SUM(p.monto) FROM pagos p JOIN ventas v ON p.venta_id = v.id WHERE v.cliente_id = c.id), 0) AS total_pagado,
              IFNULL((SELECT MAX(p.fecha) FROM pagos p JOIN ventas v ON p.venta_id = v.id WHERE v.cliente_id = c.id), '2000-01-01') AS ultimo_pago
              FROM clientes c)
    )
    ''')

    # Nombre original restaurado: reporte_comisiones_limpio
    cursor.execute("DROP VIEW IF EXISTS reporte_comisiones_limpio")
    cursor.execute('''
    CREATE VIEW reporte_comisiones_limpio AS
    SELECT 
        rc.id_comision,
        rc.fecha_registro, 
        d.nombre AS distribuidora, 
        rc.id_venta AS folio_nota,
        rc.monto_venta_total, 
        rc.monto_comision, 
        rc.adeudo_comision AS saldo_pendiente,
        rc.estatus_pago_distribuidora
    FROM registro_comisiones rc
    JOIN distribuidoras d ON rc.id_distribuidora = d.id_distribuidora
    ''')

    # ==========================================
    # 7. TRIGGERS
    # ==========================================
    cursor.execute('CREATE TRIGGER IF NOT EXISTS restar_inv AFTER INSERT ON detalle_ventas BEGIN UPDATE productos SET stock = stock - NEW.cantidad WHERE id_producto = NEW.id_producto; END')
    cursor.execute('CREATE TRIGGER IF NOT EXISTS sumar_inv AFTER INSERT ON detalle_compras BEGIN UPDATE productos SET stock = stock + NEW.cantidad WHERE id_producto = NEW.id_producto; END')
    
    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS liquidar_comision
    AFTER INSERT ON pagos_distribuidoras
    BEGIN
        UPDATE registro_comisiones 
        SET adeudo_comision = adeudo_comision - NEW.monto_pagado,
            estatus_pago_distribuidora = CASE WHEN (adeudo_comision - NEW.monto_pagado) <= 0 THEN 'PAGADO' ELSE 'PENDIENTE' END
        WHERE id_comision = NEW.id_comision;
    END
    ''')

    conn.commit()
    conn.close()
    print("¡Base de datos sincronizada con tus nombres originales y nueva vista de clientes!")

if __name__ == "__main__":
    inicializar_tablas()