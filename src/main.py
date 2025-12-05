import os
import sys

# Add src to path so we can import modules if running from root
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.data_loader import load_data, load_config
from src.genetic_algorithm import GeneticAlgorithm

def main():
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_path, 'data')
    
    cursos_path = os.path.join(data_path, 'cursos.json')
    profesores_path = os.path.join(data_path, 'profesores.json')
    aulas_path = os.path.join(data_path, 'aulas.json')
    grupos_path = os.path.join(data_path, 'grupos.json')
    clases_path = os.path.join(data_path, 'clases.json')
    config_path = os.path.join(base_path, 'config.json')

    print("Cargando datos...")
    cursos, profesores, aulas, grupos, clases = load_data(cursos_path, profesores_path, aulas_path, grupos_path, clases_path)
    config = load_config(config_path)
    
    print(f"Cursos cargados: {len(cursos)}")
    print(f"Profesores cargados: {len(profesores)}")
    print(f"Aulas cargadas: {len(aulas)}")
    print(f"Grupos cargados: {len(grupos)}")
    print(f"Clases (demandas) cargadas: {len(clases)}")

    print("Inicializando Algoritmo Genético...")
    ga = GeneticAlgorithm(cursos, profesores, aulas, grupos, clases, config)
    
    print("Iniciando evolución...")
    best_schedule = ga.evolve()
    
    print(f"Mejor horario encontrado con fitness: {best_schedule.fitness}")
    
    if best_schedule.fitness < 0:
        print("\n--- CONFLICTOS DETECTADOS ---")
        conflicts = ga.get_conflicts(best_schedule)
        for c in conflicts[:20]: # Show first 20
            print(c)
        if len(conflicts) > 20:
            print(f"... y {len(conflicts) - 20} más.")
            
    # Exportar a CSV
    import csv
    output_file = os.path.join(base_path, 'horario_generado.csv')
    print(f"\nExportando horario a {output_file}...")
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Dia', 'Hora Inicio', 'Hora Fin', 'Curso', 'Grupo', 'Aula', 'Profesor', 'Tipo Aula'])
        
        days = config['days']
        slots = config['time_slots']
        
        # Sort by Day, then Time, then Group (need to lookup group via class)
        # Helper to get group id from session
        def get_group_id(session):
            clase = next(c for c in clases if c.id == session.clase_id)
            return clase.grupo_id

        sorted_sessions = sorted(best_schedule.sesiones, key=lambda s: (s.dia_idx, s.start_slot_idx, get_group_id(s)))
        
        for s in sorted_sessions:
            clase = next(c for c in clases if c.id == s.clase_id)
            curso = next(c for c in cursos if c.id == clase.curso_id)
            prof = next(p for p in profesores if p.id == s.profesor_id)
            aula = next(a for a in aulas if a.id == s.aula_id)
            grupo = next(g for g in grupos if g.id == clase.grupo_id)
            
            day_name = days[s.dia_idx]
            start_time = slots[s.start_slot_idx].split('-')[0]
            end_slot_idx = s.start_slot_idx + s.num_slots - 1
            end_time = slots[end_slot_idx].split('-')[1]
            
            writer.writerow([
                day_name,
                start_time,
                end_time,
                curso.nombre,
                grupo.id,
                aula.nombre,
                prof.nombre,
                aula.tipo
            ])
            
    print("Exportación completada.")

if __name__ == "__main__":
    main()
