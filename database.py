import sqlite3

NOMBRE_DB = "tienda.db"

def inicializar_tablas():
    conn = sqlite3.connect(NOMBRE_DB)
    cursor = conn.cursor()

    # [1. Tablas Catálogo, 2. Productos y 3. Ventas se mantienen igual...]
    # (Omitidas en este bloque para brevedad, pero mantenlas en tu archivo)

    # ==========================================
    # 4. TABLA DE REGISTRO DE COMISIONES (ACTUALIZADA)
    # ==========================================
    cursor.execute('''CREATE TABLE IF NOT EXISTS registro_comisiones (
        id_comision INTEGER PRIMARY KEY AUTOINCREMENT,
        id_venta INTEGER UNIQUE, 
        id_distribuidora INTEGER,
        monto_venta_total REAL,
        monto_comision REAL,          -- Lo que se ganó en total esa venta
        adeudo_comision REAL,         -- Lo que aún le debes de esa comisión
        fecha_registro TEXT,
        estatus_pago_distribuidora TEXT DEFAULT 'PENDIENTE', 
        FOREIGN KEY (id_venta) REFERENCES ventas (id),
        FOREIGN KEY (id_distribuidora) REFERENCES distribuidoras (id_distribuidora)
    )''')

    # ==========================================
    # 5. NUEVA: TABLA DE PAGOS A DISTRIBUIDORAS
    # ==========================================
    # Aquí es donde registras cuando SACAS dinero de la caja para pagarles
    cursor.execute('''CREATE TABLE IF NOT EXISTS pagos_distribuidoras (
        id_pago_dist INTEGER PRIMARY KEY AUTOINCREMENT,
        id_comision INTEGER,
        monto_pagado REAL,
        fecha_pago TEXT,
        metodo_pago TEXT, -- Efectivo, transferencia, etc.
        FOREIGN KEY (id_comision) REFERENCES registro_comisiones (id_comision)
    )''')

    # ==========================================
    # 6. TRIGGER PARA ACTUALIZAR ADEUDO DE COMISIÓN
    # ==========================================
    # Este "Robot" resta automáticamente del adeudo de la distribuidora cuando le pagas
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

    # ==========================================
    # 7. VISTA DE SALDOS CON DISTRIBUIDORAS
    # ==========================================
    cursor.execute("DROP VIEW IF EXISTS saldo_distribuidoras;")
    cursor.execute('''
    CREATE VIEW saldo_distribuidoras AS
    SELECT 
        d.nombre AS distribuidora,
        COUNT(rc.id_comision) AS ventas_pendientes,
        SUM(rc.adeudo_comision) AS total_por_pagar
    FROM registro_comisiones rc
    JOIN distribuidoras d ON rc.id_distribuidora = d.id_distribuidora
    WHERE rc.estatus_pago_distribuidora = 'PENDIENTE'
    GROUP BY d.id_distribuidora;
    ''')

    conn.commit()
    conn.close()
    print("¡Sistema de pagos a distribuidoras integrado!")

if __name__ == "__main__":
    inicializar_tablas()