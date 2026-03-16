import sqlite3

def diagnosticar_datos():
    conn = sqlite3.connect("tienda.db")
    cursor = conn.cursor()

    print("--- RADIOGRAFÍA DE LA BASE DE DATOS ---")

    # 1. Revisar si la tabla pagos existe
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pagos';")
        existe_pagos = cursor.fetchone()
        print(f"1. ¿Existe la tabla 'pagos'?: {'SÍ' if existe_pagos else 'NO'}")
    except Exception as e:
        print(f"1. Error al buscar tabla pagos: {e}")

    # 2. Contar cuántos clientes hay
    try:
        cursor.execute("SELECT COUNT(*) FROM clientes;")
        print(f"2. Total de clientes registrados: {cursor.fetchone()[0]}")
    except Exception as e:
        print(f"2. Error al contar clientes: {e}")

    # 3. Contar ventas y ver si están conectadas a un cliente
    try:
        cursor.execute("SELECT COUNT(*) FROM ventas;")
        total_ventas = cursor.fetchone()[0]
        print(f"3. Total de ventas registradas: {total_ventas}")

        cursor.execute("SELECT COUNT(*) FROM ventas WHERE cliente_id IS NOT NULL;")
        ventas_conectadas = cursor.fetchone()[0]
        print(f"4. Ventas que SÍ tienen un cliente_id asignado: {ventas_conectadas}")
    except Exception as e:
        print(f"3 y 4. Error al consultar ventas: {e}")

    # 5. Intentar leer la vista para ver el error exacto
    print("\n--- RESULTADO DE LA VISTA ---")
    try:
        # Cambiamos total_comprado por adeudo_actual que es la columna que sí devuelve tu vista
        cursor.execute("SELECT id, nombre, adeudo_actual, tipo_cliente FROM clasificacion_clientes LIMIT 5;")
        resultados = cursor.fetchall()
        if not resultados:
            print("La vista existe y funciona, pero no arrojó ningún dato.")
        else:
            print("Datos encontrados en la vista:")
            for fila in resultados:
                print(fila)
    except Exception as e:
        print(f"¡ERROR al intentar leer la vista!: {e}")

    conn.close()

if __name__ == "__main__":
    diagnosticar_datos()