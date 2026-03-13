import os
import openpyxl

# --- PON TU RUTA REAL AQUÍ ---
CARPETA_EXCEL = "C:/PROYECTO_SERVICIO_SOCIAL/ArchivosExcel" 

def escanear_excel():
    archivos = [f for f in os.listdir(CARPETA_EXCEL) if f.endswith('.xlsx') and not f.startswith('~')]
    
    if not archivos:
        print("No se encontraron archivos.")
        return

    archivo_prueba = archivos[0] # Agarramos solo el primero
    ruta = os.path.join(CARPETA_EXCEL, archivo_prueba)
    
    print(f"--- ESCANEANDO CON RAYOS X: {archivo_prueba} ---\n")
    
    wb = openpyxl.load_workbook(ruta, data_only=True)
    hoja = wb.active
    
    for fila in range(1, 10):
        for col in range(1, 15):
            val = hoja.cell(row=fila, column=col).value
            
            # Si la celda no está vacía, imprimimos qué hay adentro
            if val is not None and str(val).strip() != "":
                tipo = type(val).__name__
                print(f"Fila {fila}, Columna {col} | Tipo: {tipo} | Valor: {val}")

if __name__ == "__main__":
    escanear_excel()