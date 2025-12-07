import csv
import json
import os
from collections import defaultdict

def load_json(base_path, subdir, filename):
    with open(os.path.join(base_path, subdir, filename), 'r', encoding='utf-8') as f:
        return json.load(f)

def build_ancestry(grupos):
    # Map group_id -> object
    g_map = {g['id']: g for g in grupos}
    
    # Map group_id -> set of related ids (self + ancestors + descendants)
    related = defaultdict(set)
    
    # 1. Parent/Child (Ancestors)
    for g in grupos:
        current = g
        while current:
            related[g['id']].add(current['id'])
            related[current['id']].add(g['id']) # Add self to ancestor's related list too
            parent_id = current.get('parent_grupo_id')
            current = g_map.get(parent_id) if parent_id else None
            
    return related

def parse_time(time_str):
    h, m = map(int, time_str.split(':'))
    return h * 60 + m

def check_overlap(start1, end1, start2, end2):
    return max(start1, start2) < min(end1, end2)

def analyze():
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    # Load all data
    grupos = load_json(base_path, 'data', 'grupos.json')
    cursos = load_json(base_path, 'data', 'cursos.json')
    profesores = load_json(base_path, 'data', 'profesores.json')
    aulas = load_json(base_path, 'data', 'aulas.json')
    clases = load_json(base_path, 'data', 'clases.json')
    
    # Config is in root, not data
    with open(os.path.join(base_path, 'config.json'), 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Build lookups
    g_map = {g['id']: g for g in grupos}
    c_map = {c['id']: c for c in cursos}
    p_map = {p['id']: p for p in profesores}
    a_map = {a['id']: a for a in aulas}
    cl_map = {cl['id']: cl for cl in clases} # Not strictly needed if we rely on CSV names, but good for validation
    
    # Map names back to IDs for validation (since CSV has names)
    c_name_map = {c['nombre']: c for c in cursos}
    p_name_map = {p['nombre']: p for p in profesores}
    a_name_map = {a['nombre']: a for a in aulas}
    
    related_map = build_ancestry(grupos)
    
    schedule = []
    with open(os.path.join(base_path, 'horario_generado.csv'), 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            schedule.append(row)
            
    conflicts = []
    
    # Group by Day for time conflict checks
    by_day = defaultdict(list)
    for row in schedule:
        by_day[row['Dia']].append(row)
        
        # --- Single Row Checks ---
        
        # 1. Break Time Check
        # Break is 12:30 - 13:15. 
        # If a class starts before 13:15 AND ends after 12:30, it overlaps.
        start_min = parse_time(row['Hora Inicio'])
        end_min = parse_time(row['Hora Fin'])
        break_start = parse_time("12:30")
        break_end = parse_time("13:15")
        
        if check_overlap(start_min, end_min, break_start, break_end):
             conflicts.append(f"BREAK VIOLATION: {row['Curso']} ({row['Grupo']}) overlaps with break time (12:30-13:15). Time: {row['Hora Inicio']}-{row['Hora Fin']}")

        # 2. Room Capacity Check
        aula = a_name_map.get(row['Aula'])
        grupo = g_map.get(row['Grupo'])
        if aula and grupo:
            if aula['capacidad'] < grupo['num_estudiantes']:
                conflicts.append(f"CAPACITY VIOLATION: {row['Aula']} (Cap: {aula['capacidad']}) is too small for {row['Grupo']} ({grupo['num_estudiantes']} students).")
        
        # 3. Professor Eligibility Check
        curso = c_name_map.get(row['Curso'])
        prof = p_name_map.get(row['Profesor'])
        if curso and prof:
            if prof['id'] not in curso['profesores_ids']:
                 conflicts.append(f"ELIGIBILITY VIOLATION: {row['Profesor']} is not assigned to teach {row['Curso']}.")

        # 4. Room Type Check
        # We need to find the specific class requirement to know the required room type
        # We can try to match by Course + Group
        # Or just check if the assigned room type matches the 'Tipo Aula' column which presumably comes from the requirement
        if aula:
            required_type = row['Tipo Aula'] # From CSV, which came from Class requirement
            if aula['tipo'] != required_type:
                 conflicts.append(f"ROOM TYPE VIOLATION: {row['Aula']} is {aula['tipo']}, but class requires {required_type}.")

    # --- Pairwise Checks (Time Conflicts) ---
    for day, sessions in by_day.items():
        for i in range(len(sessions)):
            for j in range(i + 1, len(sessions)):
                s1 = sessions[i]
                s2 = sessions[j]
                
                start1 = parse_time(s1['Hora Inicio'])
                end1 = parse_time(s1['Hora Fin'])
                start2 = parse_time(s2['Hora Inicio'])
                end2 = parse_time(s2['Hora Fin'])
                
                if check_overlap(start1, end1, start2, end2):
                    # 5. Group Conflict
                    g1 = s1['Grupo']
                    g2 = s2['Grupo']
                    if g2 in related_map[g1]:
                        conflicts.append(f"GROUP CONFLICT: {day} - {g1} vs {g2}")
                    
                    # 6. Professor Conflict
                    p1 = s1['Profesor']
                    p2 = s2['Profesor']
                    if p1 == p2:
                        conflicts.append(f"PROFESSOR CONFLICT: {day} - {p1} has overlapping classes: {s1['Curso']} and {s2['Curso']}")
                        
                    # 7. Room Conflict
                    r1 = s1['Aula']
                    r2 = s2['Aula']
                    if r1 == r2:
                        conflicts.append(f"ROOM CONFLICT: {day} - {r1} has overlapping classes: {s1['Curso']} and {s2['Curso']}")

    # 8. Max Hours Per Week Check
    prof_hours = defaultdict(float) # Hours (or slots) per professor
    
    for row in schedule:
        prof_name = row['Profesor']
        start_min = parse_time(row['Hora Inicio'])
        end_min = parse_time(row['Hora Fin'])
        duration_minutes = end_min - start_min
        # Convert to hours. 
        # CAUTION: Academic hours vs Clock hours.
        # Data says `max_horas_semana`. Usually this means academic hours (45 min) or clock hours?
        # Let's assume the limit is in academic hours count or simply count slots.
        # The `Curso` has `horas_semanales`. The `Profesor` has `max_horas_semana`.
        # `horas_semanales` is likely count of academic hours.
        # So we should count slots (45 min blocks).
        
        # Duration in academic hours (approx)
        # 45 min = 1 unit.
        slots = round(duration_minutes / 45)
        prof_hours[prof_name] += slots

    for prof_name, total_slots in prof_hours.items():
        prof_data = p_name_map.get(prof_name)
        if prof_data:
            max_h = prof_data['max_horas_semana']
            if total_slots > max_h:
                 conflicts.append(f"MAX HOURS VIOLATION: {prof_name} is assigned {total_slots} academic hours, max is {max_h}.")

    if not conflicts:
        print("VERIFICACIÓN EXITOSA: No se encontraron violaciones a las restricciones.")
    else:
        print(f"Se encontraron {len(conflicts)} problemas:")
        for c in conflicts[:50]: # Limit output
            print(f"- {c}")
        if len(conflicts) > 50:
            print(f"... y {len(conflicts) - 50} más.")

if __name__ == "__main__":
    analyze()
