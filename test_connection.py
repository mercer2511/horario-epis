# test_connection.py
from src.data_loader import load_data, load_config
import os

# REEMPLAZA ESTO CON EL NOMBRE EXACTO DE TU HOJA EN DRIVE
SPREADSHEET_NAME = "INFORMACION_HORARIOS" 

def test_google_sheets():
    print("1. Intentando conectar con Google Sheets...")
    
    # Verificamos credenciales
    if not os.path.exists('credentials.json'):
        print("ERROR: No se encuentra 'credentials.json' en la raíz.")
        return

    try:
        # Probamos cargar la configuración
        config = load_config(SPREADSHEET_NAME)
        print("\n✅ Configuración cargada con éxito:")
        print(f"   Population Size: {config.get('population_size')} (Tipo: {type(config.get('population_size'))})")
        print(f"   Break Slots: {config.get('break_slots')} (Tipo elemento: {type(config.get('break_slots')[0])})")

        # Probamos cargar los datos principales
        cursos, profesores, aulas, grupos, clases = load_data(SPREADSHEET_NAME)
        
        print("\n✅ Datos cargados con éxito:")
        print(f"   Cursos encontrados: {len(cursos)}")
        print(f"   Profesores encontrados: {len(profesores)}")
        print(f"   Ejemplo Profesor 1 Disponibilidad: {profesores[0].disponibilidad}")
        print(f"   Aulas encontradas: {len(aulas)}")
        print(f"   Grupos encontrados: {len(grupos)}")
        print(f"   Clases encontradas: {len(clases)}")

    except Exception as e:
        print(f"\n❌ OCURRIÓ UN ERROR: {e}")

if __name__ == "__main__":
    test_google_sheets()