import flet as ft
import sqlite3

NOMBRE_DB = "tienda.db"

def main(page: ft.Page):
    page.title = "Sistema POS Integral Maestro"
    page.theme_mode = "light"
    page.padding = 20
    
    def get_db_connection():
        return sqlite3.connect(NOMBRE_DB)
        
    # ==========================================
    # AUTO-REPARACIÓN DE LA BASE DE DATOS (MIGRACIÓN SEGURA)
    # ==========================================
    conn = get_db_connection()
    # Tablas Base
    conn.execute('''CREATE TABLE IF NOT EXISTS pagos (
        id_pago INTEGER PRIMARY KEY AUTOINCREMENT, 
        venta_id INTEGER, 
        monto REAL, 
        fecha TEXT
    )''')
    # AQUI CORREGIMOS EL NOMBRE A comision
    conn.execute('''CREATE TABLE IF NOT EXISTS distribuidoras (
        id_distribuidora INTEGER PRIMARY KEY AUTOINCREMENT, 
        nombre TEXT NOT NULL, 
        telefono TEXT, 
        comision REAL DEFAULT 0
    )''')
    
    # Tabla Comisiones
    conn.execute('''CREATE TABLE IF NOT EXISTS registro_comisiones (
        id_comision INTEGER PRIMARY KEY AUTOINCREMENT, 
        id_venta INTEGER UNIQUE, 
        id_distribuidora INTEGER, 
        monto_venta_total REAL, 
        monto_comision REAL, 
        adeudo_comision REAL, 
        fecha_registro TEXT, 
        estatus_pago_distribuidora TEXT DEFAULT 'PENDIENTE'
    )''')
    
    # Intentar agregar columnas si venimos de versiones anteriores
    try: 
        conn.execute("ALTER TABLE ventas ADD COLUMN id_distribuidora INTEGER")
    except: 
        pass
    
    try: 
        conn.execute("ALTER TABLE registro_comisiones ADD COLUMN adeudo_comision REAL")
        # Si se acaba de crear, igualamos el adeudo a la comisión inicial
        conn.execute("UPDATE registro_comisiones SET adeudo_comision = monto_comision WHERE adeudo_comision IS NULL")
    except: 
        pass

    # Pagos a distribuidoras
    conn.execute('''CREATE TABLE IF NOT EXISTS pagos_distribuidoras (
        id_pago_dist INTEGER PRIMARY KEY AUTOINCREMENT, 
        id_comision INTEGER, 
        monto_pagado REAL, 
        fecha_pago TEXT, 
        metodo_pago TEXT
    )''')
    
    # Vistas y Triggers actualizados
    conn.execute("DROP VIEW IF EXISTS reporte_comisiones")
    conn.execute('''
    CREATE VIEW reporte_comisiones AS
    SELECT rc.id_comision, rc.id_venta AS folio_venta, rc.fecha_registro AS fecha, d.nombre AS distribuidora,
           rc.monto_venta_total AS total_venta, rc.monto_comision AS comision_generada, rc.adeudo_comision AS saldo_pendiente, rc.estatus_pago_distribuidora AS estatus
    FROM registro_comisiones rc 
    JOIN distribuidoras d ON rc.id_distribuidora = d.id_distribuidora;
    ''')
    
    conn.execute('''
    CREATE TRIGGER IF NOT EXISTS actualizar_adeudo_distribuidora
    AFTER INSERT ON pagos_distribuidoras
    BEGIN
        UPDATE registro_comisiones 
        SET adeudo_comision = adeudo_comision - NEW.monto_pagado,
            estatus_pago_distribuidora = CASE WHEN (adeudo_comision - NEW.monto_pagado) <= 0 THEN 'PAGADO' ELSE 'PENDIENTE' END
        WHERE id_comision = NEW.id_comision;
    END;
    ''')
    
    conn.commit()
    conn.close()

    # --- ESTADO GLOBAL ---
    estado_app = {
        "cliente_pos_id": None, 
        "empleado_pos_id": None, 
        "distribuidora_pos_id": None, 
        "producto_pos_id": None, 
        "producto_pos_nombre": "", 
        "producto_pos_precio": 0.0, 
        "cliente_cobro_id": None
    }

    # ==========================================
    # MÓDULO 1: CLIENTES (Gris)
    # ==========================================
    def agregar_cliente_click(e):
        if not txt_nombre.value or not txt_telefono.value:
            page.snack_bar = ft.SnackBar(ft.Text("Campos obligatorios vacíos"))
            page.snack_bar.open = True
            page.update()
            return
            
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO clientes (nombre, domicilio, telefono) VALUES (?, ?, ?)", 
                (txt_nombre.value, txt_domicilio.value, txt_telefono.value)
            )
            conn.commit()
            
            txt_nombre.value = ""
            txt_domicilio.value = ""
            txt_telefono.value = ""
            
            page.snack_bar = ft.SnackBar(ft.Text("¡Cliente guardado con éxito!"))
            page.snack_bar.open = True
            cargar_clasificacion() 
        except Exception as ex:
            print(f"Error: {ex}")
        finally:
            conn.close()
            page.update()

    def cargar_clasificacion(filtro=""):
        tabla_clientes.rows.clear()
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            query = """
                SELECT c.id, c.nombre, IFNULL(SUM(v.adeudo), 0) AS adeudo_total
                FROM clientes c
                LEFT JOIN ventas v ON c.id = v.cliente_id
            """
            if filtro == "":
                query += " GROUP BY c.id ORDER BY c.nombre"
                cursor.execute(query)
            else:
                query += " WHERE c.nombre LIKE ? GROUP BY c.id ORDER BY c.nombre"
                cursor.execute(query, ('%'+filtro+'%',))
                
            for r in cursor.fetchall():
                nombre_cliente = r[1]
                adeudo_val = r[2]
                
                # Clasificación Automática de Colores
                if adeudo_val <= 0:
                    tipo_cliente = "VERDE"
                    color_v = "green"
                elif adeudo_val > 0 and adeudo_val <= 1500:
                    tipo_cliente = "AMARILLO"
                    color_v = "orange"
                else:
                    tipo_cliente = "ROJO"
                    color_v = "red"
                
                # Texto de Estado de Cuenta
                if adeudo_val > 0: 
                    txt_adeudo = f"Debe: ${adeudo_val:.2f}"
                    color_adeudo = "red"
                elif adeudo_val < 0: 
                    txt_adeudo = f"A favor: ${abs(adeudo_val):.2f}"
                    color_adeudo = "green"
                else: 
                    txt_adeudo = "$0.00"
                    color_adeudo = "black"

                tabla_clientes.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(nombre_cliente))), 
                        ft.DataCell(ft.Text(txt_adeudo, color=color_adeudo, weight="bold")),
                        ft.DataCell(ft.Text("●", color=color_v, size=20)), 
                        ft.DataCell(ft.Text(tipo_cliente)),
                    ])
                )
        except Exception as ex:
            print(f"Error cargando clientes: {ex}")
        finally:
            conn.close()
            page.update()

    txt_nombre = ft.TextField(label="Nombre", expand=True)
    txt_domicilio = ft.TextField(label="Domicilio", expand=True)
    txt_telefono = ft.TextField(label="Teléfono", expand=True)
    
    btn_guardar_cliente = ft.Button(content=ft.Text("Guardar Cliente"), on_click=agregar_cliente_click)
    txt_buscar_cliente = ft.TextField(label="🔍 Buscar cliente...", on_change=lambda e: cargar_clasificacion(e.control.value))

    tabla_clientes = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Nombre")), 
            ft.DataColumn(ft.Text("Estado de Cuenta")), 
            ft.DataColumn(ft.Text("Status")), 
            ft.DataColumn(ft.Text("Clasificación"))
        ], 
        rows=[]
    )
    
    vista_clientes = ft.Column([
        ft.Text("Inteligencia de Clientes", size=25, weight="bold"),
        ft.Container(
            content=ft.Column([
                ft.Text("Nuevo Registro"), 
                ft.Row([txt_nombre, txt_telefono]), 
                ft.Row([txt_domicilio, btn_guardar_cliente])
            ]), 
            padding=15, 
            bgcolor="#eeeeee", 
            border_radius=10
        ),
        txt_buscar_cliente, 
        ft.Column([tabla_clientes], scroll="always", height=300)
    ])

    # ==========================================
    # MÓDULO 2: INVENTARIO (Azul)
    # ==========================================
    def agregar_producto_click(e):
        if not txt_desc_prod.value or not txt_precio_prod.value: 
            page.snack_bar = ft.SnackBar(ft.Text("Descripción y Precio son obligatorios"))
            page.snack_bar.open = True
            page.update()
            return
            
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO productos (id_categoria, descripcion, precio, stock) VALUES (1, ?, ?, ?)", 
                (txt_desc_prod.value, float(txt_precio_prod.value), int(txt_stock_prod.value or 0))
            )
            conn.commit()
            
            txt_desc_prod.value = ""
            txt_precio_prod.value = ""
            txt_stock_prod.value = ""
            
            page.snack_bar = ft.SnackBar(ft.Text("¡Producto agregado al inventario!"))
            page.snack_bar.open = True
            cargar_inventario()
        except Exception as ex:
            print(f"Error: {ex}")
        finally:
            conn.close()
            page.update()

    def cargar_inventario(filtro=""):
        tabla_productos.rows.clear()
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if filtro == "": 
                cursor.execute("SELECT descripcion, precio, stock FROM productos ORDER BY descripcion")
            else: 
                cursor.execute("SELECT descripcion, precio, stock FROM productos WHERE descripcion LIKE ? ORDER BY descripcion", ('%'+filtro+'%',))
                
            for r in cursor.fetchall():
                color_stock = "red" if r[2] < 5 else "black"
                tabla_productos.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(r[0]))), 
                        ft.DataCell(ft.Text(f"${r[1]:.2f}")), 
                        ft.DataCell(ft.Text(str(r[2]), color=color_stock, weight="bold"))
                    ])
                )
        except Exception as ex:
            print(f"Error: {ex}")
        finally:
            conn.close()
            page.update()

    txt_desc_prod = ft.TextField(label="Descripción", expand=True)
    txt_precio_prod = ft.TextField(label="Precio Venta", expand=True)
    txt_stock_prod = ft.TextField(label="Stock", expand=True)
    
    btn_guardar_prod = ft.Button(content=ft.Text("Guardar Producto"), on_click=agregar_producto_click)
    txt_buscar_prod = ft.TextField(label="🔍 Buscar producto...", on_change=lambda e: cargar_inventario(e.control.value))

    tabla_productos = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Producto")), 
            ft.DataColumn(ft.Text("Precio")), 
            ft.DataColumn(ft.Text("Existencias"))
        ], 
        rows=[]
    )
    
    vista_inventario = ft.Column([
        ft.Text("Gestión de Inventario", size=25, weight="bold"),
        ft.Container(
            content=ft.Column([
                ft.Text("Registrar Nuevo Producto"), 
                ft.Row([txt_desc_prod, txt_precio_prod, txt_stock_prod]), 
                ft.Row([btn_guardar_prod])
            ]), 
            padding=15, 
            bgcolor="#e3f2fd", 
            border_radius=10
        ), 
        txt_buscar_prod, 
        ft.Column([tabla_productos], scroll="always", height=300)
    ])

    # ==========================================
    # MÓDULO 3: EMPLEADOS (Verde Claro)
    # ==========================================
    def agregar_empleado_click(e):
        if not txt_nombre_emp.value: 
            page.snack_bar = ft.SnackBar(ft.Text("El nombre es obligatorio"))
            page.snack_bar.open = True
            page.update()
            return
            
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO empleados (nombre, apaterno, amaterno, rfc, telefono, email) VALUES (?, ?, ?, ?, ?, ?)", 
                (txt_nombre_emp.value, txt_apaterno_emp.value, txt_amaterno_emp.value, txt_rfc_emp.value, txt_tel_emp.value, txt_email_emp.value)
            )
            conn.commit()
            
            txt_nombre_emp.value = ""
            txt_apaterno_emp.value = ""
            txt_amaterno_emp.value = ""
            txt_rfc_emp.value = ""
            txt_tel_emp.value = ""
            txt_email_emp.value = ""
            
            page.snack_bar = ft.SnackBar(ft.Text("¡Empleado registrado con éxito!"))
            page.snack_bar.open = True
            cargar_empleados()
        except sqlite3.IntegrityError:
            page.snack_bar = ft.SnackBar(ft.Text("Error: El RFC ingresado ya existe."))
            page.snack_bar.open = True
        except Exception as ex:
            print(f"Error: {ex}")
        finally:
            conn.close()
            page.update()

    def cargar_empleados(filtro=""):
        tabla_empleados.rows.clear()
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if filtro == "": 
                cursor.execute("SELECT nombre || ' ' || IFNULL(apaterno,'') AS nombre_completo, rfc, telefono FROM empleados ORDER BY nombre")
            else: 
                cursor.execute("SELECT nombre || ' ' || IFNULL(apaterno,'') AS nombre_completo, rfc, telefono FROM empleados WHERE nombre LIKE ? ORDER BY nombre", ('%'+filtro+'%',))
                
            for r in cursor.fetchall(): 
                tabla_empleados.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(r[0]).strip())), 
                        ft.DataCell(ft.Text(str(r[1] or 'S/N'))), 
                        ft.DataCell(ft.Text(str(r[2] or 'S/N')))
                    ])
                )
        except Exception as ex: 
            print(f"Error: {ex}")
        finally: 
            conn.close()
            page.update()

    txt_nombre_emp = ft.TextField(label="Nombre(s)", expand=True)
    txt_apaterno_emp = ft.TextField(label="Ap. Paterno", expand=True)
    txt_amaterno_emp = ft.TextField(label="Ap. Materno", expand=True)
    txt_rfc_emp = ft.TextField(label="RFC", expand=True)
    txt_tel_emp = ft.TextField(label="Teléfono", expand=True)
    txt_email_emp = ft.TextField(label="Correo", expand=True)
    
    btn_guardar_emp = ft.Button(content=ft.Text("Guardar"), on_click=agregar_empleado_click)
    txt_buscar_emp = ft.TextField(label="🔍 Buscar empleado...", on_change=lambda e: cargar_empleados(e.control.value))

    tabla_empleados = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Nombre")), 
            ft.DataColumn(ft.Text("RFC")), 
            ft.DataColumn(ft.Text("Teléfono"))
        ], 
        rows=[]
    )
    
    vista_empleados = ft.Column([
        ft.Text("Empleados", size=25, weight="bold"), 
        ft.Container(
            content=ft.Column([
                ft.Row([txt_nombre_emp, txt_apaterno_emp, txt_amaterno_emp]), 
                ft.Row([txt_rfc_emp, txt_tel_emp, txt_email_emp]), 
                ft.Row([btn_guardar_emp])
            ]), 
            padding=15, 
            bgcolor="#e8f5e9", 
            border_radius=10
        ), 
        txt_buscar_emp, 
        ft.Column([tabla_empleados], scroll="always", height=250)
    ])

    # ==========================================
    # MÓDULO 4: PROVEEDORES (Naranja)
    # ==========================================
    def agregar_proveedor_click(e):
        if not txt_nombre_prov.value: 
            page.snack_bar = ft.SnackBar(ft.Text("El nombre es obligatorio"))
            page.snack_bar.open = True
            page.update()
            return
            
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO proveedores (nombre, telefono, email) VALUES (?, ?, ?)", 
                (txt_nombre_prov.value, txt_tel_prov.value, txt_email_prov.value)
            )
            conn.commit()
            
            txt_nombre_prov.value = ""
            txt_tel_prov.value = ""
            txt_email_prov.value = ""
            
            page.snack_bar = ft.SnackBar(ft.Text("¡Proveedor guardado!"))
            page.snack_bar.open = True
            cargar_proveedores()
        except Exception as ex: 
            print(f"Error: {ex}")
        finally: 
            conn.close()
            page.update()

    def cargar_proveedores(filtro=""):
        tabla_proveedores.rows.clear()
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if filtro == "": 
                cursor.execute("SELECT nombre, telefono, email FROM proveedores ORDER BY nombre")
            else: 
                cursor.execute("SELECT nombre, telefono, email FROM proveedores WHERE nombre LIKE ? ORDER BY nombre", ('%'+filtro+'%',))
                
            for r in cursor.fetchall(): 
                tabla_proveedores.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(r[0]))), 
                        ft.DataCell(ft.Text(str(r[1] or 'S/N'))), 
                        ft.DataCell(ft.Text(str(r[2] or 'S/N')))
                    ])
                )
        except Exception as ex: 
            print(f"Error: {ex}")
        finally: 
            conn.close()
            page.update()

    txt_nombre_prov = ft.TextField(label="Proveedor", expand=True)
    txt_tel_prov = ft.TextField(label="Teléfono", expand=True)
    txt_email_prov = ft.TextField(label="Correo", expand=True)
    
    btn_guardar_prov = ft.Button(content=ft.Text("Guardar"), on_click=agregar_proveedor_click)
    txt_buscar_prov = ft.TextField(label="🔍 Buscar proveedor...", on_change=lambda e: cargar_proveedores(e.control.value))

    tabla_proveedores = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Proveedor")), 
            ft.DataColumn(ft.Text("Teléfono")), 
            ft.DataColumn(ft.Text("Email"))
        ], 
        rows=[]
    )
    
    vista_proveedores = ft.Column([
        ft.Text("Proveedores", size=25, weight="bold"), 
        ft.Container(
            content=ft.Column([
                ft.Row([txt_nombre_prov, txt_tel_prov]), 
                ft.Row([txt_email_prov, btn_guardar_prov])
            ]), 
            padding=15, 
            bgcolor="#fff3e0", 
            border_radius=10
        ), 
        txt_buscar_prov, 
        ft.Column([tabla_proveedores], scroll="always", height=250)
    ])

    # ==========================================
    # MÓDULO 5: DISTRIBUIDORAS (Amarillo)
    # ==========================================
    def agregar_distribuidora_click(e):
        if not txt_nombre_dist.value or not txt_comision_dist.value: 
            page.snack_bar = ft.SnackBar(ft.Text("Nombre y Porcentaje son obligatorios"))
            page.snack_bar.open = True
            page.update()
            return
            
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # CORRECCIÓN: usamos comision en lugar de comision_porcentaje
            cursor.execute(
                "INSERT INTO distribuidoras (nombre, telefono, comision) VALUES (?, ?, ?)", 
                (txt_nombre_dist.value, txt_tel_dist.value, float(txt_comision_dist.value))
            )
            conn.commit()
            
            txt_nombre_dist.value = ""
            txt_tel_dist.value = ""
            txt_comision_dist.value = ""
            
            page.snack_bar = ft.SnackBar(ft.Text("¡Distribuidora guardada!"))
            page.snack_bar.open = True
            cargar_distribuidoras()
        except Exception as ex: 
            print(f"Error: {ex}")
        finally: 
            conn.close()
            page.update()

    def cargar_distribuidoras():
        tabla_distribuidoras.rows.clear()
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # CORRECCIÓN: usamos comision en lugar de comision_porcentaje
            cursor.execute("SELECT nombre, telefono, comision FROM distribuidoras ORDER BY nombre")
            for r in cursor.fetchall(): 
                tabla_distribuidoras.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(r[0]))), 
                        ft.DataCell(ft.Text(str(r[1] or 'S/N'))), 
                        ft.DataCell(ft.Text(f"{r[2]}%"))
                    ])
                )
        except Exception as ex:
            print(f"Error: {ex}")
        finally:
            conn.close()
            page.update()

    txt_nombre_dist = ft.TextField(label="Nombre", expand=True)
    txt_tel_dist = ft.TextField(label="Teléfono", expand=True)
    txt_comision_dist = ft.TextField(label="% de Comisión", expand=True)
    
    btn_guardar_dist = ft.Button(content=ft.Text("Guardar"), on_click=agregar_distribuidora_click)

    tabla_distribuidoras = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Nombre")), 
            ft.DataColumn(ft.Text("Teléfono")), 
            ft.DataColumn(ft.Text("Comisión"))
        ], 
        rows=[]
    )
    
    vista_distribuidoras = ft.Column([
        ft.Text("Distribuidoras", size=25, weight="bold"), 
        ft.Container(
            content=ft.Column([
                ft.Row([txt_nombre_dist, txt_tel_dist, txt_comision_dist]), 
                ft.Row([btn_guardar_dist])
            ]), 
            padding=15, 
            bgcolor="#fff9c4", 
            border_radius=10
        ), 
        ft.Column([tabla_distribuidoras], scroll="always", height=250)
    ])

    # ==========================================
    # MÓDULO 6: REPORTE DE COMISIONES Y PAGOS
    # ==========================================
    def cargar_reporte_comisiones():
        tabla_comisiones.rows.clear()
        dd_comision_pagar.options.clear()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id_comision, fecha, distribuidora, folio_venta, total_venta, comision_generada, saldo_pendiente, estatus FROM reporte_comisiones ORDER BY id_comision DESC")
            for r in cursor.fetchall():
                id_com, fecha, dist, folio, total, comision, saldo, estado = r
                color_estado = "green" if estado == "PAGADO" else "red"
                
                tabla_comisiones.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(fecha))), 
                        ft.DataCell(ft.Text(str(dist))), 
                        ft.DataCell(ft.Text(f"#{folio}")),
                        ft.DataCell(ft.Text(f"${total:.2f}")), 
                        ft.DataCell(ft.Text(f"${saldo:.2f}", weight="bold")), 
                        ft.DataCell(ft.Text(estado, color=color_estado)),
                    ])
                )
                
                if estado != "PAGADO":
                    dd_comision_pagar.options.append(ft.dropdown.Option(key=str(id_com), text=f"Nota #{folio} - {dist} (Deuda: ${saldo:.2f})"))
        except Exception as ex: 
            print(f"Error: {ex}")
        finally: 
            conn.close()
            page.update()

    def liquidar_comision_click(e):
        if not dd_comision_pagar.value or not txt_monto_comision.value: 
            return
            
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO pagos_distribuidoras (id_comision, monto_pagado, fecha_pago, metodo_pago) VALUES (?, ?, date('now', 'localtime'), 'EFECTIVO')", 
                (int(dd_comision_pagar.value), float(txt_monto_comision.value))
            )
            conn.commit()
            
            txt_monto_comision.value = ""
            page.snack_bar = ft.SnackBar(ft.Text("¡Abono a comisión registrado!"))
            page.snack_bar.open = True
            cargar_reporte_comisiones()
        except Exception as ex: 
            print(f"Error: {ex}")
        finally: 
            conn.close()
            page.update()

    tabla_comisiones = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Fecha")), 
            ft.DataColumn(ft.Text("Distribuidora")), 
            ft.DataColumn(ft.Text("Folio Venta")), 
            ft.DataColumn(ft.Text("Total Venta")), 
            ft.DataColumn(ft.Text("Saldo Pagar")), 
            ft.DataColumn(ft.Text("Estatus"))
        ], 
        rows=[]
    )
    
    dd_comision_pagar = ft.Dropdown(label="Seleccionar Nota Pendiente", expand=True)
    txt_monto_comision = ft.TextField(label="Monto a Pagar ($)", width=150)
    btn_pagar_comision = ft.Button(content=ft.Text("Liquidar Comisión"), on_click=liquidar_comision_click, bgcolor="green", color="white")
    
    vista_comisiones = ft.Column([
        ft.Text("Gestión y Pago de Comisiones", size=25, weight="bold"),
        ft.Container(
            content=ft.Row([dd_comision_pagar, txt_monto_comision, btn_pagar_comision]), 
            padding=15, 
            bgcolor="#fff9c4", 
            border_radius=10
        ),
        ft.Column([tabla_comisiones], scroll="always", height=300)
    ])

    # ==========================================
    # MÓDULO 7: HISTORIAL DE VENTAS
    # ==========================================
    def cargar_historial_ventas(filtro=""):
        tabla_historial.rows.clear()
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            query = "SELECT v.id, v.fecha, c.nombre, v.total, IFNULL(v.tipo_venta, 'MIGRADO'), v.adeudo FROM ventas v JOIN clientes c ON v.cliente_id = c.id"
            if filtro:
                query += " WHERE c.nombre LIKE ? OR v.fecha LIKE ? ORDER BY v.id DESC"
                cursor.execute(query, ('%'+filtro+'%', '%'+filtro+'%'))
            else:
                query += " ORDER BY v.id DESC LIMIT 50"
                cursor.execute(query)
                
            for r in cursor.fetchall():
                adeudo_venta = r[5]
                estado = "PAGADO" if adeudo_venta <= 0 else "PENDIENTE"
                color_est = "green" if estado == "PAGADO" else "red"
                
                tabla_historial.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(f"#{r[0]}")), 
                        ft.DataCell(ft.Text(str(r[1]))), 
                        ft.DataCell(ft.Text(str(r[2]))),
                        ft.DataCell(ft.Text(f"${r[3]:.2f}")), 
                        ft.DataCell(ft.Text(str(r[4]))), 
                        ft.DataCell(ft.Text(estado, color=color_est, weight="bold")),
                    ])
                )
        except Exception as ex: 
            print(f"Error: {ex}")
        finally: 
            conn.close()
            page.update()

    txt_buscar_historial = ft.TextField(label="🔍 Buscar Cliente o Fecha...", on_change=lambda e: cargar_historial_ventas(e.control.value))
    
    tabla_historial = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Folio")), 
            ft.DataColumn(ft.Text("Fecha")), 
            ft.DataColumn(ft.Text("Cliente")), 
            ft.DataColumn(ft.Text("Total")), 
            ft.DataColumn(ft.Text("Tipo")), 
            ft.DataColumn(ft.Text("Estatus"))
        ], 
        rows=[]
    )
    
    vista_historial = ft.Column([
        ft.Text("Historial de Ventas", size=25, weight="bold"), 
        txt_buscar_historial, 
        ft.Column([tabla_historial], scroll="always", height=400)
    ])

    # ==========================================
    # MÓDULO 8: COBRANZA Y VALES
    # ==========================================
    def seleccionar_cliente_cobro(id_c, nombre_c):
        estado_app["cliente_cobro_id"] = id_c
        txt_cliente_cobro.value = nombre_c
        lista_cliente_cobro.visible = False
        page.update()

    def buscar_cliente_cobro(e):
        lista_cliente_cobro.content.controls.clear()
        filtro = e.control.value
        
        if not filtro:
            lista_cliente_cobro.visible = False
            estado_app["cliente_cobro_id"] = None
            page.update()
            return
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.nombre, IFNULL(SUM(v.adeudo), 0) 
            FROM clientes c 
            LEFT JOIN ventas v ON c.id = v.cliente_id 
            WHERE c.nombre LIKE ? 
            GROUP BY c.id 
            ORDER BY c.nombre LIMIT 10
        """, ('%'+filtro+'%',))
        
        for r in cursor.fetchall():
            deuda = r[2]
            info = f"(Debe: ${deuda:.2f})" if deuda > 0 else (f"(A favor: ${abs(deuda):.2f})" if deuda < 0 else "(Al corriente)")
            texto = f"{r[1]} {info}"
            
            lista_cliente_cobro.content.controls.append(
                ft.ListTile(title=ft.Text(texto), on_click=lambda ev, id_c=r[0], nom=texto: seleccionar_cliente_cobro(id_c, nom))
            )
            
        conn.close()
        lista_cliente_cobro.visible = len(lista_cliente_cobro.content.controls) > 0
        page.update()

    txt_cliente_cobro = ft.TextField(label="🔍 Buscar Cliente...", on_change=buscar_cliente_cobro, expand=True)
    lista_cliente_cobro = ft.Container(content=ft.ListView(height=120), visible=False, bgcolor="#eeeeee", border_radius=5)
    
    def registrar_abono_click(e):
        if not estado_app["cliente_cobro_id"] or not txt_monto_abono.value: 
            return
            
        monto_pago = float(txt_monto_abono.value)
        cliente_id = estado_app["cliente_cobro_id"]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, adeudo FROM ventas WHERE cliente_id = ? AND adeudo > 0 ORDER BY fecha ASC", (cliente_id,))
            ventas_pendientes = cursor.fetchall()
            
            if not ventas_pendientes:
                cursor.execute("SELECT id FROM ventas WHERE cliente_id = ? ORDER BY fecha DESC LIMIT 1", (cliente_id,))
                ultima_v = cursor.fetchone()
                if ultima_v:
                    cursor.execute("INSERT INTO pagos (venta_id, monto, fecha) VALUES (?, ?, date('now', 'localtime'))", (ultima_v[0], monto_pago))
                    cursor.execute("UPDATE ventas SET adeudo = adeudo - ? WHERE id = ?", (monto_pago, ultima_v[0]))
            else:
                monto_restante = monto_pago
                for v in ventas_pendientes:
                    v_id, adeudo_venta = v[0], v[1]
                    if monto_restante <= 0: 
                        break
                    
                    if monto_restante >= adeudo_venta:
                        cursor.execute("INSERT INTO pagos (venta_id, monto, fecha) VALUES (?, ?, date('now', 'localtime'))", (v_id, adeudo_venta))
                        cursor.execute("UPDATE ventas SET adeudo = 0, estatus_pago = 'PAGADO' WHERE id = ?", (v_id,))
                        monto_restante -= adeudo_venta
                    else:
                        cursor.execute("INSERT INTO pagos (venta_id, monto, fecha) VALUES (?, ?, date('now', 'localtime'))", (v_id, monto_restante))
                        cursor.execute("UPDATE ventas SET adeudo = adeudo - ? WHERE id = ?", (monto_restante, v_id))
                        monto_restante = 0
                        
                if monto_restante > 0:
                    last_v_id = ventas_pendientes[-1][0]
                    cursor.execute("INSERT INTO pagos (venta_id, monto, fecha) VALUES (?, ?, date('now', 'localtime'))", (last_v_id, monto_restante))
                    cursor.execute("UPDATE ventas SET adeudo = adeudo - ? WHERE id = ?", (monto_restante, last_v_id))
                    
            conn.commit()
            
            txt_monto_abono.value = ""
            txt_cliente_cobro.value = ""
            estado_app["cliente_cobro_id"] = None
            
            page.snack_bar = ft.SnackBar(ft.Text("¡Abono registrado!"))
            page.snack_bar.open = True
            
            cargar_clasificacion()
            cargar_historial_ventas()
        except Exception as ex: 
            print(ex)
            conn.rollback()
        finally: 
            conn.close()
            page.update()

    txt_monto_abono = ft.TextField(label="Monto del Abono/Vale ($)", width=200)
    btn_abonar = ft.Button(content=ft.Text("Registrar Abono"), on_click=registrar_abono_click)
    
    vista_cobranza = ft.Column([
        ft.Text("Cobranza y Vales", size=25, weight="bold"),
        ft.Container(
            content=ft.Column([
                ft.Column([txt_cliente_cobro, lista_cliente_cobro]), 
                ft.Row([txt_monto_abono, btn_abonar])
            ]), 
            padding=20, 
            bgcolor="#e8f5e9", 
            border_radius=10
        )
    ])

    # ==========================================
    # MÓDULO 9: CAJA REGISTRADORA POS
    # ==========================================
    carrito_compras = [] 

    # --- AUTOCOMPLETES POS ---
    def seleccionar_cliente_pos(id_c, nombre_c):
        estado_app["cliente_pos_id"] = id_c
        txt_cliente_pos.value = nombre_c
        lista_cliente_pos.visible = False
        page.update()

    def buscar_cliente_pos(e):
        lista_cliente_pos.content.controls.clear()
        if not e.control.value:
            lista_cliente_pos.visible = False
            estado_app["cliente_pos_id"] = None
            page.update()
            return
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre FROM clientes WHERE nombre LIKE ? ORDER BY nombre LIMIT 10", ('%'+e.control.value+'%',))
        
        for r in cursor.fetchall(): 
            lista_cliente_pos.content.controls.append(
                ft.ListTile(title=ft.Text(r[1]), on_click=lambda ev, id_c=r[0], nom=r[1]: seleccionar_cliente_pos(id_c, nom))
            )
            
        conn.close()
        lista_cliente_pos.visible = len(lista_cliente_pos.content.controls) > 0
        page.update()

    txt_cliente_pos = ft.TextField(label="1. 🔍 Buscar Cliente...", on_change=buscar_cliente_pos)
    lista_cliente_pos = ft.Container(content=ft.ListView(height=120), visible=False, bgcolor="#eeeeee", border_radius=5)

    def seleccionar_empleado_pos(id_e, nombre_e):
        estado_app["empleado_pos_id"] = id_e
        txt_empleado_pos.value = nombre_e
        lista_empleado_pos.visible = False
        page.update()

    def buscar_empleado_pos(e):
        lista_empleado_pos.content.controls.clear()
        if not e.control.value:
            lista_empleado_pos.visible = False
            estado_app["empleado_pos_id"] = None
            page.update()
            return
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id_empleado, nombre FROM empleados WHERE nombre LIKE ? ORDER BY nombre LIMIT 10", ('%'+e.control.value+'%',))
        
        for r in cursor.fetchall(): 
            lista_empleado_pos.content.controls.append(
                ft.ListTile(title=ft.Text(r[1]), on_click=lambda ev, id_e=r[0], nom=r[1]: seleccionar_empleado_pos(id_e, nom))
            )
            
        conn.close()
        lista_empleado_pos.visible = len(lista_empleado_pos.content.controls) > 0
        page.update()

    txt_empleado_pos = ft.TextField(label="2. 🔍 Buscar Empleado...", on_change=buscar_empleado_pos)
    lista_empleado_pos = ft.Container(content=ft.ListView(height=120), visible=False, bgcolor="#eeeeee", border_radius=5)

    def seleccionar_distribuidora_pos(id_d, nombre_d):
        estado_app["distribuidora_pos_id"] = id_d
        txt_distribuidora_pos.value = nombre_d
        lista_distribuidora_pos.visible = False
        page.update()

    def buscar_distribuidora_pos(e):
        lista_distribuidora_pos.content.controls.clear()
        if not e.control.value:
            lista_distribuidora_pos.visible = False
            estado_app["distribuidora_pos_id"] = None
            page.update()
            return
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        lista_distribuidora_pos.content.controls.append(
            ft.ListTile(title=ft.Text("-- Venta Directa --", color="red"), on_click=lambda ev: seleccionar_distribuidora_pos(None, ""))
        )
        
        # CORRECCIÓN: usamos comision en lugar de comision_porcentaje
        cursor.execute("SELECT id_distribuidora, nombre, comision FROM distribuidoras WHERE nombre LIKE ? ORDER BY nombre LIMIT 10", ('%'+e.control.value+'%',))
        for r in cursor.fetchall():
            texto = f"{r[1]} ({r[2]}%)"
            lista_distribuidora_pos.content.controls.append(
                ft.ListTile(title=ft.Text(texto), on_click=lambda ev, id_d=r[0], nom=texto: seleccionar_distribuidora_pos(id_d, nom))
            )
            
        conn.close()
        lista_distribuidora_pos.visible = True
        page.update()

    txt_distribuidora_pos = ft.TextField(label="3. 🔍 Distribuidora (Opcional)...", on_change=buscar_distribuidora_pos)
    lista_distribuidora_pos = ft.Container(content=ft.ListView(height=120), visible=False, bgcolor="#eeeeee", border_radius=5)

    def seleccionar_producto_pos(id_p, desc_p, precio_p):
        estado_app["producto_pos_id"] = id_p
        estado_app["producto_pos_nombre"] = desc_p
        estado_app["producto_pos_precio"] = precio_p
        
        txt_producto_pos.value = f"{desc_p} (${precio_p:.2f})"
        lista_producto_pos.visible = False
        page.update()

    def buscar_producto_pos(e):
        lista_producto_pos.content.controls.clear()
        if not e.control.value:
            lista_producto_pos.visible = False
            estado_app["producto_pos_id"] = None
            page.update()
            return
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id_producto, descripcion, precio FROM productos WHERE stock > 0 AND descripcion LIKE ? ORDER BY descripcion LIMIT 10", ('%'+e.control.value+'%',))
        
        for r in cursor.fetchall(): 
            lista_producto_pos.content.controls.append(
                ft.ListTile(title=ft.Text(f"{r[1]} (${r[2]:.2f})"), on_click=lambda ev, id_p=r[0], desc=r[1], p=r[2]: seleccionar_producto_pos(id_p, desc, p))
            )
            
        conn.close()
        lista_producto_pos.visible = len(lista_producto_pos.content.controls) > 0
        page.update()

    txt_producto_pos = ft.TextField(label="🔍 Buscar Producto...", on_change=buscar_producto_pos, expand=True)
    lista_producto_pos = ft.Container(content=ft.ListView(height=120), visible=False, bgcolor="#eeeeee", border_radius=5)

    # --- EDICIÓN DEL CARRITO ---
    def eliminar_item_carrito(e):
        idx = e.control.data
        carrito_compras.pop(idx)
        actualizar_tabla_carrito()

    def actualizar_tabla_carrito():
        tabla_carrito.rows.clear()
        total = 0

        for idx, item in enumerate(carrito_compras):
            total += item['subtotal']

            btn_eliminar = ft.IconButton(
                icon=ft.Icons.DELETE,
                icon_color="red",
                data=idx,
                on_click=eliminar_item_carrito
            )

            tabla_carrito.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(item['cant']))),
                    ft.DataCell(ft.Text(item['desc'])),
                    ft.DataCell(ft.Text(f"${item['precio']:.2f}")),
                    ft.DataCell(ft.Text(f"${item['subtotal']:.2f}")),
                    ft.DataCell(btn_eliminar)
                ])
            )

        txt_total_venta.value = f"TOTAL: ${total:.2f}"
        page.update()

    def agregar_al_carrito_click(e):
        if not estado_app["producto_pos_id"] or not txt_cantidad_pos.value: 
            return
            
        cant = int(txt_cantidad_pos.value)
        id_prod = estado_app["producto_pos_id"]
        precio = estado_app["producto_pos_precio"]
        nombre_prod = estado_app["producto_pos_nombre"]
        
        carrito_compras.append({
            "id": id_prod, 
            "desc": nombre_prod, 
            "cant": cant, 
            "precio": precio, 
            "subtotal": cant * precio
        })
        
        actualizar_tabla_carrito()
        txt_producto_pos.value = ""
        estado_app["producto_pos_id"] = None
        page.update()

    def cobrar_venta_click(e):
        if len(carrito_compras) == 0 or not estado_app["cliente_pos_id"] or not estado_app["empleado_pos_id"]:
            page.snack_bar = ft.SnackBar(ft.Text("Faltan datos: Agrega productos, cliente y empleado"))
            page.snack_bar.open = True
            page.update()
            return

        total_venta = sum(item['subtotal'] for item in carrito_compras)
        tipo = dd_tipo_venta.value
        adeudo = total_venta if tipo == "CRÉDITO" else 0
        estatus = "PENDIENTE" if tipo == "CRÉDITO" else "PAGADO"
        id_dist = estado_app["distribuidora_pos_id"]
            
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO ventas (cliente_id, id_empleado, id_distribuidora, fecha, total, adeudo, tipo_venta, estatus_pago) 
                VALUES (?, ?, ?, date('now', 'localtime'), ?, ?, ?, ?)
            """, (estado_app["cliente_pos_id"], estado_app["empleado_pos_id"], id_dist, total_venta, adeudo, tipo, estatus))
            
            id_nueva_venta = cursor.lastrowid 
            
            for item in carrito_compras: 
                cursor.execute(
                    "INSERT INTO detalle_ventas (id_venta, id_producto, cantidad, precio_venta) VALUES (?, ?, ?, ?)", 
                    (id_nueva_venta, item["id"], item["cant"], item["precio"])
                )
                
            if id_dist:
                # CORRECCIÓN: usamos comision en lugar de comision_porcentaje
                cursor.execute("SELECT comision FROM distribuidoras WHERE id_distribuidora = ?", (id_dist,))
                porcentaje = cursor.fetchone()[0]
                monto_comision = total_venta * (porcentaje / 100.0)
                
                cursor.execute("""
                    INSERT INTO registro_comisiones (id_venta, id_distribuidora, monto_venta_total, monto_comision, adeudo_comision, fecha_registro) 
                    VALUES (?, ?, ?, ?, ?, date('now', 'localtime'))
                """, (id_nueva_venta, id_dist, total_venta, monto_comision, monto_comision))
                
            conn.commit()
            
            carrito_compras.clear()
            txt_cantidad_pos.value = "1"
            txt_cliente_pos.value = ""
            txt_empleado_pos.value = ""
            txt_distribuidora_pos.value = ""
            estado_app["cliente_pos_id"] = None
            estado_app["empleado_pos_id"] = None
            estado_app["distribuidora_pos_id"] = None
            
            actualizar_tabla_carrito()
            cargar_inventario()
            cargar_reporte_comisiones()
            cargar_historial_ventas()
            cargar_clasificacion()
            
            page.snack_bar = ft.SnackBar(ft.Text(f"¡Venta Registrada! Folio: {id_nueva_venta}"))
            page.snack_bar.open = True
        except Exception as ex: 
            print(ex)
            conn.rollback() 
        finally: 
            conn.close()
            page.update()

    txt_cantidad_pos = ft.TextField(label="Cant.", value="1", width=80)
    btn_agregar_carrito = ft.Button(content=ft.Text("Agregar"), on_click=agregar_al_carrito_click)
    
    tabla_carrito = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Cant.")), 
            ft.DataColumn(ft.Text("Descripción")), 
            ft.DataColumn(ft.Text("P. Unitario")), 
            ft.DataColumn(ft.Text("Subtotal")), 
            ft.DataColumn(ft.Text("Acción"))
        ], 
        rows=[]
    )
    
    txt_total_venta = ft.Text("TOTAL: $0.00", size=30, weight="bold", color="blue", text_align="right")
    
    dd_tipo_venta = ft.Dropdown(
        label="Tipo de Venta", 
        options=[
            ft.dropdown.Option(key="CONTADO", text="Pago de Contado"), 
            ft.dropdown.Option(key="CRÉDITO", text="A Crédito (Aumenta Adeudo)")
        ], 
        value="CONTADO", 
        width=250
    )
    
    btn_cobrar = ft.Button(content=ft.Text("Completar Venta"), on_click=cobrar_venta_click, bgcolor="green", color="white")

    vista_pos = ft.Column([
        ft.Text("Caja Registradora", size=25, weight="bold"),
        ft.Container(
            content=ft.Column([
                ft.Text("1. Datos de la Venta"), 
                ft.Row([
                    ft.Column([txt_cliente_pos, lista_cliente_pos], expand=True), 
                    ft.Column([txt_empleado_pos, lista_empleado_pos], expand=True)
                ], vertical_alignment=ft.CrossAxisAlignment.START), 
                ft.Row([
                    ft.Column([txt_distribuidora_pos, lista_distribuidora_pos], expand=True)
                ], vertical_alignment=ft.CrossAxisAlignment.START)
            ]), 
            padding=10, 
            bgcolor="#f5f5f5", 
            border_radius=10
        ),
        ft.Container(
            content=ft.Column([
                ft.Text("2. Agregar / Editar Productos"), 
                ft.Row([
                    ft.Column([txt_producto_pos, lista_producto_pos], expand=True), 
                    txt_cantidad_pos, 
                    btn_agregar_carrito
                ], vertical_alignment=ft.CrossAxisAlignment.START), 
                ft.Column([tabla_carrito], scroll="always", height=150)
            ]), 
            padding=10, 
            bgcolor="#f3e5f5", 
            border_radius=10
        ),
        ft.Row([dd_tipo_venta, ft.Container(content=txt_total_venta, expand=True)], alignment="spaceBetween"),
        ft.Row([btn_cobrar], alignment="end")
    ])

    # ==========================================
    # SISTEMA DE NAVEGACIÓN
    # ==========================================
    contenedor_clientes = ft.Container(content=vista_clientes, visible=True)
    contenedor_inventario = ft.Container(content=vista_inventario, visible=False)
    contenedor_empleados = ft.Container(content=vista_empleados, visible=False)
    contenedor_proveedores = ft.Container(content=vista_proveedores, visible=False)
    contenedor_distribuidoras = ft.Container(content=vista_distribuidoras, visible=False)
    contenedor_comisiones = ft.Container(content=vista_comisiones, visible=False)
    contenedor_cobranza = ft.Container(content=vista_cobranza, visible=False)
    contenedor_historial = ft.Container(content=vista_historial, visible=False)
    contenedor_pos = ft.Container(content=vista_pos, visible=False)

    def cambiar_pestana(e):
        contenedor_clientes.visible = False
        contenedor_inventario.visible = False
        contenedor_empleados.visible = False
        contenedor_proveedores.visible = False
        contenedor_distribuidoras.visible = False
        contenedor_comisiones.visible = False
        contenedor_cobranza.visible = False
        contenedor_historial.visible = False
        contenedor_pos.visible = False
        
        tab_sel = e.control.data
        if tab_sel == "clientes": 
            cargar_clasificacion()
            contenedor_clientes.visible = True
        elif tab_sel == "inventario": 
            cargar_inventario()
            contenedor_inventario.visible = True
        elif tab_sel == "empleados": 
            cargar_empleados()
            contenedor_empleados.visible = True
        elif tab_sel == "proveedores": 
            cargar_proveedores()
            contenedor_proveedores.visible = True
        elif tab_sel == "distribuidoras": 
            cargar_distribuidoras()
            contenedor_distribuidoras.visible = True
        elif tab_sel == "comisiones": 
            cargar_reporte_comisiones()
            contenedor_comisiones.visible = True
        elif tab_sel == "cobranza": 
            contenedor_cobranza.visible = True
        elif tab_sel == "historial": 
            cargar_historial_ventas()
            contenedor_historial.visible = True
        elif tab_sel == "pos": 
            contenedor_pos.visible = True
            
        page.update()

    menu_superior = ft.Row([
        ft.Button(content=ft.Text("Clientes"), data="clientes", on_click=cambiar_pestana), 
        ft.Button(content=ft.Text("Inventario"), data="inventario", on_click=cambiar_pestana),
        ft.Button(content=ft.Text("Empleados"), data="empleados", on_click=cambiar_pestana), 
        ft.Button(content=ft.Text("Proveedores"), data="proveedores", on_click=cambiar_pestana),
        ft.Button(content=ft.Text("Distribuidoras"), data="distribuidoras", on_click=cambiar_pestana), 
        ft.Button(content=ft.Text("Comisiones"), data="comisiones", on_click=cambiar_pestana),
        ft.Button(content=ft.Text("Cobranza"), data="cobranza", on_click=cambiar_pestana), 
        ft.Button(content=ft.Text("Historial"), data="historial", on_click=cambiar_pestana),
        ft.Button(content=ft.Text("Caja (POS)"), data="pos", on_click=cambiar_pestana, bgcolor="blue", color="white"),
    ], alignment="center", wrap=True) 

    page.add(
        menu_superior, 
        ft.Divider(height=2, color="black"),
        contenedor_clientes, 
        contenedor_inventario, 
        contenedor_empleados, 
        contenedor_proveedores,
        contenedor_distribuidoras, 
        contenedor_comisiones, 
        contenedor_cobranza, 
        contenedor_historial, 
        contenedor_pos
    )
    
    # Cargas Iniciales de todos los módulos
    cargar_clasificacion()
    cargar_inventario()
    cargar_empleados()
    cargar_proveedores()
    cargar_distribuidoras()
    cargar_reporte_comisiones()
    cargar_historial_ventas()

if __name__ == "__main__":
    ft.run(main)