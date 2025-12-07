import os
import sys
from collections import defaultdict

# Agregar src al path para importar los módulos
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.data_loader import load_data, load_config

# Configuración de conexión
SPREADSHEET_NAME = "INFORMACION_HORARIOS"
CREDENTIALS_FILE = "credentials.json"

def check_feasibility():
    print("⏳ Conectando a Google Sheets para descargar datos...")
    
    try:
        # 1. Cargar Datos (Objetos) y Configuración (Diccionario)
        cursos, profesores, aulas, grupos, clases = load_data(SPREADSHEET_NAME, CREDENTIALS_FILE)
        config = load_config(SPREADSHEET_NAME, CREDENTIALS_FILE)
    except Exception as e:
        print(f"❌ Error al cargar datos: {e}")
        return

    print("\n--- 📊 ANÁLISIS DE VIABILIDAD (Static Check) ---\n")
    
    # ---------------------------------------------------------
    # 1. ANÁLISIS: Horas Globales de Profesores (Oferta vs Demanda)
    # ---------------------------------------------------------
    # Accedemos con punto (.) porque 'clases' y 'profesores' son listas de objetos
    total_slots_needed = sum(c.duracion_bloques for c in clases)
    total_slots_available = sum(p.max_horas_semana for p in profesores)
    
    print(f"1. HORAS PROFESORES (Global):")
    print(f"   - Demanda Total (Slots): {total_slots_needed}")
    print(f"   - Oferta Total (Slots):  {total_slots_available}")
    
    if total_slots_available < total_slots_needed:
        deficit = total_slots_needed - total_slots_available
        print(f"   ❌ [CRÍTICO] FALTA OFERTA: Faltan {deficit} slots de profesores para cubrir la demanda.")
        
        print("\n   --- DETALLE DE OFERTA (Profesores) ---")
        # Ordenar por horas disponibles
        for p in sorted(profesores, key=lambda x: x.max_horas_semana):
            print(f"   - {p.nombre} ({p.id}): {p.max_horas_semana} slots")
    else:
        superavit = total_slots_available - total_slots_needed
        print(f"   ✅ [OK] Hay suficientes horas globales ({superavit} de sobra).")
    print()

    # ---------------------------------------------------------
    # 2. ANÁLISIS: Viabilidad por Curso (Cuellos de Botella)
    # ---------------------------------------------------------
    print(f"2. COBERTURA POR CURSO (Análisis de Cuellos de Botella):")
    
    # Mapa de demanda: curso_id -> total slots requeridos
    course_demand = defaultdict(int)
    for c in clases:
        course_demand[c.curso_id] += c.duracion_bloques
        
    # Mapa de búsqueda rápida de profesores por ID
    p_map = {p.id: p for p in profesores}
    
    issues_found = False
    
    # Listar cursos con mayor demanda
    print("\n   --- CURSOS CON MAYOR DEMANDA ---")
    # Ordenamos cursos (objetos) usando el diccionario de demanda externa
    sorted_courses = sorted(cursos, key=lambda x: course_demand[x.id], reverse=True)
    
    for course in sorted_courses[:10]: # Top 10
        dem = course_demand[course.id]
        if dem > 0:
            print(f"   - {course.nombre}: {dem} slots necesarios")
        
    print("\n   --- ANÁLISIS DE COBERTURA (Márgenes ajustados) ---")
    course_margins = []
    
    for course in cursos:
        c_id = course.id
        demand = course_demand[c_id]
        
        # Si el curso no tiene demanda (no hay clases programadas), lo saltamos
        if demand == 0:
            continue
        
        # Sumar capacidad de profesores elegibles para este curso
        eligible_capacity = 0
        eligible_names = []
        
        # course.profesores_ids es una lista de strings ['DOC1', 'DOC2']
        for p_id in course.profesores_ids:
            if p_id in p_map:
                prof = p_map[p_id]
                eligible_capacity += prof.max_horas_semana
                eligible_names.append(prof.nombre)
        
        margin = eligible_capacity - demand
        
        course_margins.append({
            'name': course.nombre,
            'demand': demand,
            'supply': eligible_capacity,
            'margin': margin,
            'profs': eligible_names
        })
        
        if eligible_capacity < demand:
            issues_found = True
            print(f"   ❌ [IMPOSIBLE] Curso: {course.nombre} ({c_id})")
            print(f"      - Demanda: {demand} slots")
            print(f"      - Capacidad Máxima de Profesores Elegibles: {eligible_capacity} slots")
            print(f"      - DÉFICIT: {demand - eligible_capacity} slots. IMPOSIBLE CUBRIR.")

    # Mostrar Top 10 cursos más ajustados
    course_margins.sort(key=lambda x: x['margin'])
    
    print("\n   --- TOP 10 CURSOS CON MENOR MARGEN DE OFERTA ---")
    print("   (Margen = Capacidad de Profes Elegibles - Demanda del Curso)")
    print("   * Nota: Un margen bajo o negativo significa problemas.")
    
    for cm in course_margins[:10]:
        status_icon = "⚠️" if cm['margin'] < 5 else "✅"
        if cm['margin'] < 0: status_icon = "❌"
        
        print(f"   {status_icon} {cm['name']}")
        print(f"       Demanda: {cm['demand']} | Oferta Combinada: {cm['supply']} | Margen: {cm['margin']}")
        print(f"       Profesores: {', '.join(cm['profs'])}")
        print(f"       ------------------------------------------------")

    if not issues_found:
        print("   ✅ [OK] Todos los cursos tienen teóricamente suficientes profesores asignados.")
    print()

    # ---------------------------------------------------------
    # 3. ANÁLISIS: Capacidad Global de Aulas
    # ---------------------------------------------------------
    # Aquí usamos 'config' que sigue siendo un diccionario
    num_days = len(config['days'])
    num_time_slots = len(config['time_slots'])
    
    # Cálculo de slots efectivos (Total slots - Slots de break)
    # config['break_slots'] es una lista de enteros ahora
    num_breaks = len(config.get('break_slots', []))
    
    # Asumimos que durante el break NO se pueden dictar clases
    effective_slots_per_day = num_time_slots - num_breaks
    
    # Capacidad Total = Num Aulas * Num Dias * Slots Efectivos
    total_room_capacity = len(aulas) * num_days * effective_slots_per_day
    
    print(f"3. CAPACIDAD AULAS (Global):")
    print(f"   - Demanda Total (Slots): {total_slots_needed}")
    print(f"   - Capacidad Total (Slots): {total_room_capacity}")
    print(f"     ({len(aulas)} aulas x {num_days} días x {effective_slots_per_day} slots útiles)")
    
    if total_room_capacity < total_slots_needed:
        print(f"   ❌ [CRÍTICO] FALTA AULAS: No hay suficientes espacios físicos para meter todas las clases.")
    else:
        rooms_usage = (total_slots_needed / total_room_capacity) * 100
        print(f"   ✅ [OK] Suficiente espacio físico. Ocupación estimada global: {rooms_usage:.1f}%")
        
    print("\n--- FIN DEL ANÁLISIS ---")

if __name__ == "__main__":
    check_feasibility()