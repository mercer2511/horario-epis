import json
import os
from collections import defaultdict

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def check_feasibility():
    base_path = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_path, 'data')
    
    clases = load_json(os.path.join(data_path, 'clases.json'))
    profesores = load_json(os.path.join(data_path, 'profesores.json'))
    cursos = load_json(os.path.join(data_path, 'cursos.json'))
    aulas = load_json(os.path.join(data_path, 'aulas.json'))
    config = load_json(os.path.join(base_path, 'config.json'))

    print("--- ANÁLISIS DE VIABILIDAD (Static Check) ---\n")
    
    # 1. ANALYSIS: Global Professor Hours
    total_slots_needed = sum(c['duracion_bloques'] for c in clases)
    total_slots_available = sum(p['max_horas_semana'] for p in profesores)
    
    print(f"1. HORAS PROFESORES (Global):")
    print(f"   - Demanda Total (Slots): {total_slots_needed}")
    print(f"   - Oferta Total (Slots):  {total_slots_available}")
    
    if total_slots_available < total_slots_needed:
        print(f"   [CRITICAL] FALTA OFERTA: Faltan {total_slots_needed - total_slots_available} slots de profesores para cubrir la demanda.")
        
        print("\n   --- DETALLE DE OFERTA (Profesores) ---")
        # Sort by max hours ascending to identifying low hanging fruit?
        for p in sorted(profesores, key=lambda x: x['max_horas_semana']):
            print(f"   - {p['nombre']} ({p['id']}): {p['max_horas_semana']} slots")
            
    else:
        print(f"   [OK] Hay suficientes horas globales ({total_slots_available - total_slots_needed} de sobra).")
    print()

    # 2. ANALYSIS: Course Specific Feasibility
    # For each course, calculate total slots needed (sum of all groups taking this course)
    # Compare with sum of max hours of ALL professors eligible for this course.
    print(f"2. COBERTURA POR CURSO (Análisis Botella de Cuello):")
    
    course_demand = defaultdict(int)
    for c in clases:
        course_demand[c['curso_id']] += c['duracion_bloques']
        
    p_map = {p['id']: p for p in profesores}
    
    issues_found = False
    
    # List highest demand courses
    print("\n   --- CURSOS CON MAYOR DEMANDA ---")
    sorted_courses = sorted(cursos, key=lambda x: course_demand[x['id']], reverse=True)
    for course in sorted_courses[:10]: # Top 10
        dem = course_demand[course['id']]
        print(f"   - {course['nombre']}: {dem} slots necesarios")
        
    print("\n   --- ANÁLISIS DE COBERTURA (Cuáles están más ajustados) ---")
    course_margins = []
    
    for course in cursos:
        c_id = course['id']
        demand = course_demand[c_id]
        
        # Sum capacity of eligible professors
        eligible_capacity = 0
        eligible_names = []
        for p_id in course['profesores_ids']:
            if p_id in p_map:
                eligible_capacity += p_map[p_id]['max_horas_semana']
                eligible_names.append(p_map[p_id]['nombre'])
        
        margin = eligible_capacity - demand
        course_margins.append({
            'name': course['nombre'],
            'demand': demand,
            'supply': eligible_capacity,
            'margin': margin,
            'profs': eligible_names
        })
        
        if eligible_capacity < demand:
            issues_found = True
            print(f"   [IMPOSIBLE] Curso: {course['nombre']} ({c_id})")
            print(f"      - Demanda: {demand} slots")
            print(f"      - Capacidad Máxima de Profesores Elegibles: {eligible_capacity} slots")
            print(f"      - DÉFICIT: {demand - eligible_capacity} slots. IMPOSIBLE CUBRIR.")

    # Show top 10 tightest courses
    course_margins.sort(key=lambda x: x['margin'])
    print("\n   --- TOP 10 CURSOS CON MENOR MARGEN DE OFERTA ---")
    print("   (Margin = Capacidad de Profes Eligibles - Demanda del Curso)")
    print("   * Nota: Un margen bajo significa que los profesores de este curso están saturados.")
    
    for cm in course_margins[:10]:
        print(f"   - {cm['name']}")
        print(f"       Demanda: {cm['demand']} | Oferta Combinada: {cm['supply']} | Margen: {cm['margin']}")
        print(f"       Profesores: {', '.join(cm['profs'])}")
        print(f"       ------------------------------------------------")

    
    if not issues_found:
        print("   [OK] Todos los cursos tienen teóricamente suficientes profesores asignados (individualmente).")
    print()

    # 3. ANALYSIS: Global Room Capacity
    # Total slots available = Num Rooms * Num Days * Num Slots per Day
    num_days = len(config['days'])
    num_time_slots = len(config['time_slots'])
    # Subtract break slots?
    # Usually break is common, so effective slots = total - break
    num_breaks = len(config.get('break_slots', []))
    effective_slots_per_day = num_time_slots # Assuming we might schedule in breaks if allowed, but let's be conservative?
    # Actually, config says "break_slots": [6]. If we enforce NO class in break, we subtract it.
    effective_slots_per_day = num_time_slots # Let's stick to raw capacity first
    
    total_room_capacity = len(aulas) * num_days * effective_slots_per_day
    
    print(f"3. CAPACIDAD AULAS (Global):")
    print(f"   - Demanda Total (Slots): {total_slots_needed}")
    print(f"   - Capacidad Total (Slots): {total_room_capacity}")
    
    if total_room_capacity < total_slots_needed:
        print(f"   [CRITICAL] FALTA AULAS: No hay suficientes espacios físicos.")
    else:
        rooms_usage = (total_slots_needed / total_room_capacity) * 100
        print(f"   [OK] Suficiente espacio. Ocupación estimada: {rooms_usage:.1f}%")
        
    print("\n--- FIN DEL ANÁLISIS ---")

if __name__ == "__main__":
    check_feasibility()
