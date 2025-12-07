import json
import os
from collections import defaultdict

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def check_inconsistencies():
    base_path = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_path, 'data')
    
    clases = load_json(os.path.join(data_path, 'clases.json'))
    cursos = load_json(os.path.join(data_path, 'cursos.json'))
    
    cursos_map = {c['id']: c for c in cursos}
    
    print("--- ANÁLISIS DE DISCREPANCIAS (Cursos vs Clases) ---\n")
    
    discrepancies = []
    
    # Check each class
    for clase in clases:
        c_id = clase['curso_id']
        curso = cursos_map.get(c_id)
        
        if not curso:
            print(f"[ERROR] Clase {clase['id']} referencia curso {c_id} que no existe.")
            continue
            
        nominal_hours = curso['horas_semanales']
        actual_blocks = clase['duracion_bloques']
        
        if nominal_hours != actual_blocks:
            discrepancies.append({
                'curso_id': c_id,
                'nombre': curso['nombre'],
                'grupo_id': clase['grupo_id'],
                'nominal': nominal_hours,
                'actual': actual_blocks
            })

    if not discrepancies:
        print("[OK] No se encontraron discrepancias entre horas semanales y bloques de clase.")
    else:
        print(f"Se encontraron {len(discrepancies)} discrepancias:\n")
        
        # Group by course to avoid spam
        grouped = defaultdict(list)
        for d in discrepancies:
            grouped[d['nombre']].append(d)
            
        for curso_nombre, items in grouped.items():
            first = items[0]
            print(f"CURSO: {curso_nombre} (ID: {first['curso_id']})")
            print(f"   - Horas en cursos.json: {first['nominal']}")
            
            # Check if all classes for this course have the same discrepancy
            unique_actuals = set(i['actual'] for i in items)
            
            if len(unique_actuals) == 1:
                val = items[0]['actual']
                print(f"   - Bloques en clases.json: {val} (Consistente en {len(items)} grupos)")
                print(f"   => DISCREPANCIA: {val - first['nominal']} horas/bloques de diferencia.")
            else:
                print(f"   - Bloques en clases.json VARÍAN: {unique_actuals}")
                for i in items:
                    print(f"      - Grupo {i['grupo_id']}: {i['actual']} bloques")
            print("-" * 40)

if __name__ == "__main__":
    check_inconsistencies()
