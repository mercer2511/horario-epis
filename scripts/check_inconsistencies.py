import os
import sys
from collections import defaultdict

# Agregar src al path para importar los módulos
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.data_loader import load_data

# Configuración de conexión
SPREADSHEET_NAME = "INFORMACION_HORARIOS"
CREDENTIALS_FILE = "credentials.json"

def check_inconsistencies():
    print(f"⏳ Conectando a '{SPREADSHEET_NAME}' para verificar consistencia...")
    
    try:
        # Cargar solo Cursos y Clases (ignoramos el resto con _)
        cursos, _, _, _, clases = load_data(SPREADSHEET_NAME, CREDENTIALS_FILE)
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return

    # Mapa para búsqueda rápida de cursos: ID -> Objeto Curso
    cursos_map = {c.id: c for c in cursos}
    
    print("\n--- 🔍 ANÁLISIS DE DISCREPANCIAS (Plan de Estudios vs Programación) ---\n")
    
    # 1. AGRUPACIÓN INTELIGENTE
    # Un curso puede estar dividido en varias filas en la hoja 'Clases'
    # (Ej: 3 horas lunes + 3 horas miércoles = 6 horas totales)
    # Debemos sumar los bloques por (Curso + Grupo) antes de comparar.
    
    # Key: (curso_id, grupo_id) -> Value: Total Bloques
    actual_demand = defaultdict(int)
    
    for clase in clases:
        actual_demand[(clase.curso_id, clase.grupo_id)] += clase.duracion_bloques

    discrepancies = []
    
    # 2. COMPARACIÓN
    for (c_id, g_id), total_blocks in actual_demand.items():
        curso = cursos_map.get(c_id)
        
        # Validación de Integridad Referencial
        if not curso:
            print(f"❌ [ERROR GRAVE] El Grupo '{g_id}' tiene una clase del curso ID '{c_id}' que NO EXISTE en la tabla de Cursos.")
            continue
            
        nominal_hours = curso.horas_semanales
        
        # Comparamos lo que pide la malla (nominal) vs la suma de horas programadas (actual)
        if nominal_hours != total_blocks:
            discrepancies.append({
                'curso_id': c_id,
                'nombre': curso.nombre,
                'grupo_id': g_id,
                'nominal': nominal_hours,
                'actual': total_blocks
            })

    # 3. REPORTE
    if not discrepancies:
        print("✅ [OK] INTEGRIDAD PERFECTA.")
        print("   Todas las clases programadas coinciden exactamente con las horas exigidas en el plan de estudios.")
    else:
        print(f"⚠️  Se encontraron {len(discrepancies)} discrepancias de horas:\n")
        
        # Agrupar por nombre de curso para mostrar ordenado
        grouped = defaultdict(list)
        for d in discrepancies:
            grouped[d['nombre']].append(d)
            
        for curso_nombre, items in grouped.items():
            first = items[0]
            print(f"📚 CURSO: {curso_nombre} (ID: {first['curso_id']})")
            print(f"   Requisito Malla (Cursos): {first['nominal']} horas/bloques")
            
            # Verificar si todos los grupos tienen el mismo error o varía
            unique_actuals = set(i['actual'] for i in items)
            
            if len(unique_actuals) == 1:
                val = items[0]['actual']
                diff = val - first['nominal']
                sign = "+" if diff > 0 else ""
                print(f"   ⚠️  Programado en Clases: {val} bloques (Consistente en {len(items)} grupos)")
                print(f"      => DIFERENCIA: {sign}{diff} horas.")
            else:
                print(f"   ⚠️  Programado en Clases VARÍA entre grupos:")
                for i in items:
                    diff = i['actual'] - i['nominal']
                    sign = "+" if diff > 0 else ""
                    print(f"      - Grupo {i['grupo_id']}: Tiene {i['actual']} bloques (Dif: {sign}{diff})")
            
            print("-" * 50)

if __name__ == "__main__":
    check_inconsistencies()