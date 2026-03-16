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
    # 2. TABLAS PRINCIPALES
    # ==========================================
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos (
        id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
        id_categoria INTEGER,
        descripcion TEXT,
        precio REAL,
        stock INTEGER DEFAULT 0,
        FOREIGN KEY (id_categoria) REFERENCES categorias (id_categoria)
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
    cursor.execute('''CREATE TABLE IF NOT EXISTS detalle_ventas (id_detalle INTEGER PRIMARY KEY AUTOINCREMENT, id_venta INTEGER, id_producto INTEGER, cantidad INTEGER, precio_venta REAL, FOREIGN KEY (id_venta) REFERENCES ventas (id), FOREIGN KEY (id_producto) REFERENCES productos (id_producto))''')
    cursor.execute('CREATE TABLE IF NOT EXISTS tipos_empleado (id_tipo INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT)')
    cursor.execute('''CREATE TABLE IF NOT EXISTS contratos (id_contrato INTEGER PRIMARY KEY AUTOINCREMENT, id_empleado INTEGER, id_tipo INTEGER, fecha_inicio TEXT, fecha_fin TEXT, sueldo REAL, FOREIGN KEY (id_empleado) REFERENCES empleados (id_empleado), FOREIGN KEY (id_tipo) REFERENCES tipos_empleado (id_tipo))''')

    # ==========================================
    # 6. REPORTES (VISTAS) - AQUÍ REINTEGRAMOS TU REPORTE
    # ==========================================
    
    # REPORTE DE COMISIONES (La que pediste)
    cursor.execute("DROP VIEW IF EXISTS reporte_comisiones")
    cursor.execute('''
    CREATE VIEW reporte_comisiones AS
    SELECT 
        rc.id_venta AS folio_venta,
        rc.fecha_registro AS fecha,
        d.nombre AS distribuidora,
        rc.monto_venta_total AS total_venta,
        rc.monto_comision AS comision_generada,
        rc.adeudo_comision AS saldo_pendiente,
        rc.estatus_pago_distribuidora AS estatus
    FROM registro_comisiones rc
    JOIN distribuidoras d ON rc.id_distribuidora = d.id_distribuidora;
    ''')

    # SALDO GLOBAL POR DISTRIBUIDORA
    cursor.execute("DROP VIEW IF EXISTS saldo_distribuidoras")
    cursor.execute('''
    CREATE VIEW saldo_distribuidoras AS
    SELECT d.nombre, SUM(rc.adeudo_comision) AS total_por_pagar
    FROM registro_comisiones rc
    JOIN distribuidoras d ON rc.id_distribuidora = d.id_distribuidora
    WHERE rc.estatus_pago_distribuidora = 'PENDIENTE'
    GROUP BY d.nombre;
    ''')

    # ==========================================
    # 7. TRIGGERS
    # ==========================================
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
    END;
    ''')

    conn.commit()
    conn.close()
    print("¡Base de datos sincronizada! 'reporte_comisiones' reintegrado y funcional.")

if __name__ == "__main__":
    inicializar_tablas()