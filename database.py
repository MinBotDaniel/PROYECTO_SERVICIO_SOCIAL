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

    cursor.execute('''CREATE TABLE IF NOT EXISTS distribuidoras (
        id_distribuidora INTEGER PRIMARY KEY AUTOINCREMENT, 
        nombre TEXT NOT NULL, 
        telefono TEXT,
        comision_porcentaje REAL DEFAULT 0
    )''')

    # ==========================================
    # 2. TABLAS PRINCIPALES (Clientes, Productos y Compras)
    # ==========================================
    # Nota: Asumo que la tabla 'clientes' ya existe por tu migración previa.
    # Si no, puedes descomentar la siguiente línea:
    # cursor.execute('CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, domicilio TEXT, telefono TEXT)')

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
    # 3. ACTUALIZACIÓN DE TABLA VENTAS
    # ==========================================
    columnas_nuevas = [
        "ALTER TABLE ventas ADD COLUMN id_empleado INTEGER REFERENCES empleados(id_empleado)",
        "ALTER TABLE ventas ADD COLUMN id_forma_pago INTEGER REFERENCES formas_pago(id_forma_pago)",
        "ALTER TABLE ventas ADD COLUMN tipo_venta TEXT DEFAULT 'CRÉDITO'",
        "ALTER TABLE ventas ADD COLUMN estatus_pago TEXT DEFAULT 'PAGADO'",
        "ALTER TABLE ventas ADD COLUMN id_distribuidora INTEGER REFERENCES distribuidoras(id_distribuidora)"
    ]

    for query in columnas_nuevas:
        try:
            cursor.execute(query)
        except sqlite3.OperationalError:
            pass 

    # Limpieza de estatus para datos migrados
    cursor.execute("UPDATE ventas SET tipo_venta = 'CRÉDITO' WHERE tipo_venta IS NULL")
    cursor.execute("UPDATE ventas SET estatus_pago = 'PENDIENTE' WHERE adeudo > 0")
    cursor.execute("UPDATE ventas SET estatus_pago = 'PAGADO' WHERE adeudo <= 0 OR adeudo IS NULL")

    # ==========================================
    # 4. SISTEMA DE COMISIONES Y PAGOS (DISTRIBUIDORAS)
    # ==========================================
    
    # Registro de la comisión generada por venta
    cursor.execute('''CREATE TABLE IF NOT EXISTS registro_comisiones (
        id_comision INTEGER PRIMARY KEY AUTOINCREMENT,
        id_venta INTEGER UNIQUE, 
        id_distribuidora INTEGER,
        monto_venta_total REAL,
        monto_comision REAL,          -- Comisión total calculada
        adeudo_comision REAL,         -- Lo que falta por pagar a la distribuidora
        fecha_registro TEXT,
        estatus_pago_distribuidora TEXT DEFAULT 'PENDIENTE', 
        FOREIGN KEY (id_venta) REFERENCES ventas (id),
        FOREIGN KEY (id_distribuidora) REFERENCES distribuidoras (id_distribuidora)
    )''')

    # Registro de pagos realizados a las distribuidoras
    cursor.execute('''CREATE TABLE IF NOT EXISTS pagos_distribuidoras (
        id_pago_dist INTEGER PRIMARY KEY AUTOINCREMENT,
        id_comision INTEGER,
        monto_pagado REAL,
        fecha_pago TEXT,
        metodo_pago TEXT, 
        FOREIGN KEY (id_comision) REFERENCES registro_comisiones (id_comision)
    )''')

    # ==========================================
    # 5. DETALLES Y RECURSOS HUMANOS
    # ==========================================
    cursor.execute('''CREATE TABLE IF NOT EXISTS detalle_compras (id_detalle INTEGER PRIMARY KEY AUTOINCREMENT, folio_compra INTEGER, id_producto INTEGER, cantidad INTEGER, precio_compra REAL, FOREIGN KEY (folio_compra) REFERENCES compras (folio_compra), FOREIGN KEY (id_producto) REFERENCES productos (id_producto))''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS detalle_ventas (id_detalle INTEGER PRIMARY KEY AUTOINCREMENT, id_venta INTEGER, id_producto INTEGER, cantidad INTEGER, precio_venta REAL, FOREIGN KEY (id_venta) REFERENCES ventas (id), FOREIGN KEY (id_producto) REFERENCES productos (id_producto))''')
    
    cursor.execute('CREATE TABLE IF NOT EXISTS tipos_empleado (id_tipo INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT)')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS contratos (id_contrato INTEGER PRIMARY KEY AUTOINCREMENT, id_empleado INTEGER, id_tipo INTEGER, fecha_inicio TEXT, fecha_fin TEXT, sueldo REAL, FOREIGN KEY (id_empleado) REFERENCES empleados (id_empleado), FOREIGN KEY (id_tipo) REFERENCES tipos_empleado (id_tipo))''')

    # ==========================================
    # 6. VISTAS DE INTELIGENCIA (REPORTES)
    # ==========================================
    
    # Vista: Semáforo de Clientes
    cursor.execute("DROP VIEW IF EXISTS clasificacion_clientes")
    cursor.execute('''
    CREATE VIEW clasificacion_clientes AS
    SELECT id, nombre, telefono, (total_comprado - total_pagado) AS adeudo_actual,
    CASE WHEN ultima_venta > ultimo_pago THEN ultima_venta ELSE ultimo_pago END AS ultima_actividad,
    CASE WHEN (total_comprado - total_pagado) > 0 AND ultimo_pago <= date('now', '-6 months') THEN 'ROJO'
         WHEN (total_comprado - total_pagado) > 0 AND ultimo_pago > date('now', '-6 months') THEN 'VERDE'
         WHEN (total_comprado - total_pagado) <= 0 AND ultima_venta >= date('now', '-1 year') THEN 'VERDE'
         WHEN (total_comprado - total_pagado) <= 0 AND ultima_venta < date('now', '-1 year') THEN 'AMARILLO'
         ELSE 'SIN CLASIFICAR' END AS tipo_cliente
    FROM (SELECT c.id, c.nombre, c.telefono,
          IFNULL((SELECT SUM(total) FROM ventas WHERE cliente_id = c.id), 0) AS total_comprado,
          IFNULL((SELECT MAX(fecha) FROM ventas WHERE cliente_id = c.id), '2000-01-01') AS ultima_venta,
          IFNULL((SELECT SUM(p.monto) FROM pagos p JOIN ventas v ON p.venta_id = v.id WHERE v.cliente_id = c.id), 0) AS total_pagado,
          IFNULL((SELECT MAX(p.fecha) FROM pagos p JOIN ventas v ON p.venta_id = v.id WHERE v.cliente_id = c.id), '2000-01-01') AS ultimo_pago
          FROM clientes c)
    ''')

    # Vista: Reporte de Saldos con Distribuidoras
    cursor.execute("DROP VIEW IF EXISTS saldo_distribuidoras")
    cursor.execute('''
    CREATE VIEW saldo_distribuidoras AS
    SELECT 
        d.nombre AS distribuidora,
        COUNT(rc.id_comision) AS ventas_pendientes,
        SUM(rc.adeudo_comision) AS total_por_pagar
    FROM registro_comisiones rc
    JOIN distribuidoras d ON rc.id_distribuidora = d.id_distribuidora
    WHERE rc.estatus_pago_distribuidora = 'PENDIENTE'
    GROUP BY d.id_distribuidora
    ''')

    # ==========================================
    # 7. TRIGGERS (AUTOMATIZACIÓN)
    # ==========================================
    
    # Robot 1: Restar stock por venta
    cursor.execute('CREATE TRIGGER IF NOT EXISTS restar_inv AFTER INSERT ON detalle_ventas BEGIN UPDATE productos SET stock = stock - NEW.cantidad WHERE id_producto = NEW.id_producto; END')
    
    # Robot 2: Sumar stock por compra
    cursor.execute('CREATE TRIGGER IF NOT EXISTS sumar_inv AFTER INSERT ON detalle_compras BEGIN UPDATE productos SET stock = stock + NEW.cantidad WHERE id_producto = NEW.id_producto; END')

    # Robot 3: Actualizar adeudo de comisión cuando le pagas a la distribuidora
    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS actualizar_adeudo_distribuidora
    AFTER INSERT ON pagos_distribuidoras
    BEGIN
        UPDATE registro_comisiones 
        SET adeudo_comision = adeudo_comision - NEW.monto_pagado,
            estatus_pago_distribuidora = CASE 
                WHEN (adeudo_comision - NEW.monto_pagado) <= 0 THEN 'PAGADO' 
                ELSE 'PENDIENTE' 
            END
        WHERE id_comision = NEW.id_comision;
    END
    ''')

    conn.commit()
    conn.close()
    print("¡SISTEMA COMPLETO SINCRONIZADO!")
    print("- Gestión de Inventario, Empleados, Clientes y Distribuidoras lista.")

if __name__ == "__main__":
    inicializar_tablas()