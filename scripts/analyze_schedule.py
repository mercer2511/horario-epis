import csv
import os
import sys
from collections import defaultdict

# Agregar src al path para importar los módulos
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.data_loader import load_data, load_config

# Configuración de conexión
SPREADSHEET_NAME = "INFORMACION_HORARIOS"
CREDENTIALS_FILE = "credentials.json"

def build_ancestry(grupos):
    """
    Construye un mapa de parentesco entre grupos usando Objetos.
    """
    # Map group_id -> object
    g_map = {g.id: g for g in grupos}
    
    # Map group_id -> set of related ids (self + ancestors + descendants)
    related = defaultdict(set)
    
    for g in grupos:
        current = g
        # Recorrer hacia arriba (ancestros)
        while current:
            related[g.id].add(current.id)
            related[current.id].add(g.id) # Agregar self a la lista del ancestro
            
            parent_id = current.parent_grupo_id
            if parent_id and parent_id in g_map:
                current = g_map[parent_id]
            else:
                current = None
            
    return related

def parse_time(time_str):
    try:
        h, m = map(int, time_str.split(':'))
        return h * 60 + m
    except ValueError:
        return 0 # Manejo seguro si viene vacío o error

def check_overlap(start1, end1, start2, end2):
    return max(start1, start2) < min(end1, end2)

def analyze():
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"🔍 Analizando horario. Cargando datos maestros de '{SPREADSHEET_NAME}'...")
    
    try:
        # 1. Cargar Datos Maestros (Objetos)
        cursos, profesores, aulas, grupos, clases = load_data(SPREADSHEET_NAME, CREDENTIALS_FILE)
        config = load_config(SPREADSHEET_NAME, CREDENTIALS_FILE)
    except Exception as e:
        print(f"❌ Error al conectar con Google Sheets: {e}")
        return

    # 2. Construir Índices de Búsqueda (Lookups)
    # Necesitamos buscar objetos por su NOMBRE, ya que el CSV tiene nombres, no IDs.
    
    g_map_name = {g.id: g for g in grupos} # ID -> Obj (para ancestry)
    
    # Nombre -> Objeto
    c_name_map = {c.nombre: c for c in cursos}
    p_name_map = {p.nombre: p for p in profesores}
    a_name_map = {a.nombre: a for a in aulas}
    g_id_map = {g.id: g for g in grupos} # El CSV usa ID de grupo, no nombre, en la columna 'Grupo'
    
    related_map = build_ancestry(grupos)
    
    # 3. Cargar Horario Generado (CSV)
    schedule = []
    csv_path = os.path.join(base_path, 'horario_generado.csv')
    
    if not os.path.exists(csv_path):
        print(f"❌ No se encontró el archivo: {csv_path}")
        return

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            schedule.append(row)
            
    conflicts = []
    print(f"📊 Verificando {len(schedule)} sesiones programadas...")

    # Group by Day for time conflict checks
    by_day = defaultdict(list)
    
    # Definir horario de break basado en strings (o calcularlo de config si fuera necesario)
    # Asumimos que el break slot 6 corresponde aprox a 12:30-13:15
    # Para ser exactos, deberíamos leer config['time_slots'] y config['break_slots']
    break_intervals = []
    if 'break_slots' in config and 'time_slots' in config:
        for slot_idx in config['break_slots']:
             if slot_idx < len(config['time_slots']):
                 t_str = config['time_slots'][slot_idx] # "12:30-13:15"
                 s, e = t_str.split('-')
                 break_intervals.append((parse_time(s), parse_time(e)))

    for row in schedule:
        by_day[row['Dia']].append(row)
        
        # --- Validaciones Individuales ---
        
        start_min = parse_time(row['Hora Inicio'])
        end_min = parse_time(row['Hora Fin'])
        
        # 1. Break Time Check (Dinámico basado en config)
        for b_start, b_end in break_intervals:
             if check_overlap(start_min, end_min, b_start, b_end):
                 conflicts.append(f"BREAK VIOLATION: {row['Curso']} ({row['Grupo']}) solapa con refrigerio. Hora: {row['Hora Inicio']}-{row['Hora Fin']}")

        # 2. Room Capacity Check
        aula = a_name_map.get(row['Aula'])
        grupo = g_id_map.get(row['Grupo']) # CSV guarda ID del grupo (ej: C1-M)
        
        if aula and grupo:
            # Nota: Usamos acceso por punto .capacidad
            if aula.capacidad < grupo.num_estudiantes:
                conflicts.append(f"CAPACITY VIOLATION: {row['Aula']} (Cap: {aula.capacidad}) muy pequeña para {row['Grupo']} ({grupo.num_estudiantes} est).")
        
        # 3. Professor Eligibility Check
        curso = c_name_map.get(row['Curso'])
        prof = p_name_map.get(row['Profesor'])
        
        if curso and prof:
            # curso.profesores_ids es lista de IDs
            # prof.id es el ID del profesor actual
            if prof.id not in curso.profesores_ids:
                 conflicts.append(f"ELIGIBILITY VIOLATION: {row['Profesor']} no está autorizado para enseñar {row['Curso']}.")

        # 4. Room Type Check
        if aula:
            required_type = row['Tipo Aula']
            if aula.tipo != required_type:
                 conflicts.append(f"ROOM TYPE VIOLATION: {row['Aula']} es {aula.tipo}, la clase requiere {required_type}.")

    # --- Validaciones de Pares (Conflictos de Tiempo) ---
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
                    # 5. Group Conflict (Ancestry)
                    g1 = s1['Grupo']
                    g2 = s2['Grupo']
                    
                    # Verificamos si g2 está relacionado con g1
                    if g2 in related_map.get(g1, set()):
                        conflicts.append(f"GROUP CONFLICT: {day} - {g1} vs {g2} se solapan.")
                    
                    # 6. Professor Conflict
                    p1 = s1['Profesor']
                    p2 = s2['Profesor']
                    if p1 == p2:
                        conflicts.append(f"PROFESSOR CONFLICT: {day} - {p1} tiene choque: {s1['Curso']} y {s2['Curso']}")
                        
                    # 7. Room Conflict
                    r1 = s1['Aula']
                    r2 = s2['Aula']
                    if r1 == r2:
                        conflicts.append(f"ROOM CONFLICT: {day} - {r1} tiene choque: {s1['Curso']} y {s2['Curso']}")

    # 8. Max Hours Per Week Check
    prof_hours = defaultdict(float) 
    
    for row in schedule:
        prof_name = row['Profesor']
        start_min = parse_time(row['Hora Inicio'])
        end_min = parse_time(row['Hora Fin'])
        duration_minutes = end_min - start_min
        
        # Asumimos bloques de 45 min para contar "horas académicas"
        slots = round(duration_minutes / 45)
        prof_hours[prof_name] += slots

    for prof_name, total_slots in prof_hours.items():
        prof_obj = p_name_map.get(prof_name)
        if prof_obj:
            max_h = prof_obj.max_horas_semana
            if total_slots > max_h:
                 conflicts.append(f"MAX HOURS VIOLATION: {prof_name} asignado {total_slots} hrs, maximo es {max_h}.")

    # Reporte Final
    if not conflicts:
        print("\n✅ VERIFICACIÓN EXITOSA: El horario generado es válido y respeta todas las reglas.")
    else:
        print(f"\n⚠️ SE ENCONTRARON {len(conflicts)} PROBLEMAS:")
        for c in conflicts[:50]: 
            print(f"  [x] {c}")
        if len(conflicts) > 50:
            print(f"  ... y {len(conflicts) - 50} más.")

if __name__ == "__main__":
    analyze()