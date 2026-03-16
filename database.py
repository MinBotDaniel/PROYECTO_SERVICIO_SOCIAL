import sqlite3

NOMBRE_DB = "tienda.db"

def inicializar_tablas():
    conn = sqlite3.connect(NOMBRE_DB)
    cursor = conn.cursor()

    # ==========================================
    # 1. TABLAS CATÁLOGO (Las que no dependen de otras)
    # ==========================================
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS categorias (
        id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
        categoria TEXT NOT NULL
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS proveedores (
        id_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        telefono TEXT,
        email TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS empleados (
        id_empleado INTEGER PRIMARY KEY AUTOINCREMENT,
        rfc TEXT UNIQUE, -- Se guarda como información, pero ya no es la llave
        nombre TEXT NOT NULL,
        apaterno TEXT,
        amaterno TEXT,
        telefono TEXT,
        email TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS formas_pago (
        id_forma_pago INTEGER PRIMARY KEY AUTOINCREMENT,
        forma_pago TEXT NOT NULL
    )''')

    # ==========================================
    # 2. TABLAS PRINCIPALES (Productos, Compras, etc.)
    # ==========================================

    cursor.execute('''CREATE TABLE IF NOT EXISTS productos (
        id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
        id_categoria INTEGER,
        descripcion TEXT,
        precio REAL,
        stock INTEGER DEFAULT 0, -- Agregamos el stock para el inventario
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
    # 3. ACTUALIZACIÓN DE LA TABLA VENTAS EXISTENTE
    # ==========================================
    
    columnas_nuevas = [
        "ALTER TABLE ventas ADD COLUMN id_empleado INTEGER REFERENCES empleados(id_empleado);", # ¡Aquí está el cambio!
        "ALTER TABLE ventas ADD COLUMN id_forma_pago INTEGER REFERENCES formas_pago(id_forma_pago);",
        "ALTER TABLE ventas ADD COLUMN tipo_venta TEXT DEFAULT 'CONTADO';",
        "ALTER TABLE ventas ADD COLUMN estatus_pago TEXT DEFAULT 'PAGADO';"
    ]

    for query in columnas_nuevas:
        try:
            cursor.execute(query)
        except sqlite3.OperationalError:
            pass

    # ==========================================
    # 4. DETALLES (Relaciones muchos a muchos)
    # ==========================================
    
    # Detalle de qué productos llegaron en cada compra
    cursor.execute('''CREATE TABLE IF NOT EXISTS detalle_compras (
        id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
        folio_compra INTEGER,
        id_producto INTEGER,
        cantidad INTEGER,
        precio_compra REAL,
        FOREIGN KEY (folio_compra) REFERENCES compras (folio_compra),
        FOREIGN KEY (id_producto) REFERENCES productos (id_producto)
    )''')

    # Detalle de qué productos se llevan en cada venta (El puente entre Ventas y Productos)
    cursor.execute('''CREATE TABLE IF NOT EXISTS detalle_ventas (
        id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
        id_venta INTEGER,
        id_producto INTEGER,
        cantidad INTEGER,
        precio_venta REAL,
        FOREIGN KEY (id_venta) REFERENCES ventas (id),
        FOREIGN KEY (id_producto) REFERENCES productos (id_producto)
    )''')

    # ==========================================
    # 5. TABLAS DE RECURSOS HUMANOS 
    # ==========================================
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS tipos_empleado (
        id_tipo INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS contratos (
        id_contrato INTEGER PRIMARY KEY AUTOINCREMENT,
        id_empleado INTEGER,
        id_tipo INTEGER,
        fecha_inicio TEXT,
        fecha_fin TEXT,
        sueldo REAL,
        FOREIGN KEY (id_empleado) REFERENCES empleados (id_empleado),
        FOREIGN KEY (id_tipo) REFERENCES tipos_empleado (id_tipo)
    )''')

    # ==========================================
    # 6. INTELIGENCIA DE CLIENTES (Semaforización Automática)
    # ==========================================
    
    # Borramos la vista si ya existía para poder actualizar las reglas
    cursor.execute("DROP VIEW IF EXISTS clasificacion_clientes;")

    cursor.execute('''
    CREATE VIEW clasificacion_clientes AS
    WITH Resumen AS (
        SELECT 
            c.id,
            c.nombre,
            c.telefono,
            -- Sumamos todo lo que ha comprado
            COALESCE((SELECT SUM(total) FROM ventas WHERE cliente_id = c.id), 0) AS total_comprado,
            -- Sumamos todo lo que ha pagado
            COALESCE((SELECT SUM(monto) FROM pagos WHERE cliente_id = c.id), 0) AS total_pagado,
            -- Buscamos la fecha de su última compra
            COALESCE((SELECT MAX(fecha) FROM ventas WHERE cliente_id = c.id), '2000-01-01') AS ultima_venta,
            -- Buscamos la fecha de su último abono
            COALESCE((SELECT MAX(fecha) FROM pagos WHERE cliente_id = c.id), '2000-01-01') AS ultimo_pago
        FROM clientes c
    )
    SELECT 
        id,
        nombre,
        telefono,
        (total_comprado - total_pagado) AS adeudo_actual,
        -- Comparamos para ver qué hizo al último: ¿comprar o pagar?
        MAX(ultima_venta, ultimo_pago) AS ultima_actividad,
        
        -- AQUI ESTÁN TUS REGLAS DE NEGOCIO EXACTAS:
        CASE 
            -- 🔴 ROJO: Quedó a deber y su último movimiento fue hace más de 2 años
            WHEN (total_comprado - total_pagado) > 0 
                 AND MAX(ultima_venta, ultimo_pago) <= date('now', '-2 years') 
            THEN 'ROJO'
            
            -- 🟢 VERDE (Crédito Vigente): Tiene deuda, pero ha abonado o comprado en los últimos 2 años
            WHEN (total_comprado - total_pagado) > 0 
                 AND MAX(ultima_venta, ultimo_pago) > date('now', '-2 years') 
            THEN 'VERDE'
            
            -- 🟢 VERDE (Regular): No debe nada y compró hace menos de 1 año
            WHEN (total_comprado - total_pagado) <= 0 
                 AND ultima_venta >= date('now', '-1 year') 
            THEN 'VERDE'
            
            -- 🟡 AMARILLO: No debe nada, pero lleva más de 1 año sin comprar
            WHEN (total_comprado - total_pagado) <= 0 
                 AND ultima_venta < date('now', '-1 year') 
            THEN 'AMARILLO'
            
            ELSE 'SIN CLASIFICAR'
        END AS tipo_cliente
    FROM Resumen;
    ''')

    conn.commit()
    conn.close()
    print("¡Base de datos estructurada y tabla de ventas actualizada para el POS!")

if __name__ == "__main__":
    inicializar_tablas()