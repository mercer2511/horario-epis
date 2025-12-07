import os
import sys
import csv

# Add src to path so we can import modules if running from root
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.data_loader import load_data, load_config
from src.genetic_algorithm import GeneticAlgorithm

# CONFIGURACIÓN GLOBAL
SPREADSHEET_NAME = "INFORMACION_HORARIOS"
CREDENTIALS_FILE = "credentials.json"

def main():
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    print(f"🚀 Iniciando sistema. Conectando a Google Sheets: '{SPREADSHEET_NAME}'...")
    
    try:
        # 1. Cargar Datos y Configuración desde la Nube
        # Nota: load_data ahora solo pide el nombre de la hoja y las credenciales
        cursos, profesores, aulas, grupos, clases = load_data(SPREADSHEET_NAME, CREDENTIALS_FILE)
        config = load_config(SPREADSHEET_NAME, CREDENTIALS_FILE)
        
        print("✅ Datos descargados exitosamente:")
        print(f"   - Cursos: {len(cursos)}")
        print(f"   - Profesores: {len(profesores)}")
        print(f"   - Aulas: {len(aulas)}")
        print(f"   - Grupos: {len(grupos)}")
        print(f"   - Clases (demandas): {len(clases)}")
        print(f"   - Configuración: Población {config.get('population_size')}, Gens {config.get('max_generations')}")

        # 2. Inicializar Algoritmo Genético
        print("\n🧬 Inicializando Algoritmo Genético...")
        ga = GeneticAlgorithm(cursos, profesores, aulas, grupos, clases, config)
        
        # 3. Evolución
        print("⚡ Iniciando evolución...")
        best_schedule = ga.evolve()
        
        print(f"\n🏆 Mejor horario encontrado con fitness: {best_schedule.fitness}")
        
        # 4. Reporte de Conflictos
        if best_schedule.fitness < 0:
            print("\n--- ⚠️ CONFLICTOS DETECTADOS ---")
            conflicts = ga.get_conflicts(best_schedule)
            for c in conflicts[:20]: # Show first 20
                print(f"  [x] {c}")
            if len(conflicts) > 20:
                print(f"      ... y {len(conflicts) - 20} más.")
        else:
            print("\n✨ ¡Horario Perfecto! Sin conflictos duros detectados.")
                
        # 5. Exportar a CSV
        output_file = os.path.join(base_path, 'horario_generado.csv')
        print(f"\n💾 Exportando horario a {output_file}...")
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Dia', 'Hora Inicio', 'Hora Fin', 'Curso', 'Grupo', 'Aula', 'Profesor', 'Tipo Aula'])
            
            days = config['days']
            slots = config['time_slots']
            
            # Helper to get group id from session for sorting
            def get_group_id(session):
                clase = next(c for c in clases if c.id == session.clase_id)
                return clase.grupo_id

            # Ordenar para que el CSV sea legible (Día -> Hora -> Grupo)
            sorted_sessions = sorted(best_schedule.sesiones, key=lambda s: (s.dia_idx, s.start_slot_idx, get_group_id(s)))
            
            for s in sorted_sessions:
                clase = next(c for c in clases if c.id == s.clase_id)
                curso = next(c for c in cursos if c.id == clase.curso_id)
                prof = next(p for p in profesores if p.id == s.profesor_id)
                aula = next(a for a in aulas if a.id == s.aula_id)
                grupo = next(g for g in grupos if g.id == clase.grupo_id)
                
                day_name = days[s.dia_idx]
                
                # Manejo seguro de slots
                if s.start_slot_idx < len(slots):
                    start_time = slots[s.start_slot_idx].split('-')[0]
                    end_slot_idx = s.start_slot_idx + s.num_slots - 1
                    if end_slot_idx < len(slots):
                        end_time = slots[end_slot_idx].split('-')[1]
                    else:
                        end_time = "OUT_OF_BOUNDS"
                else:
                    start_time = "ERROR"
                    end_time = "ERROR"
                
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
                
        print("✅ Exportación completada.")

    except Exception as e:
        print(f"\n❌ Error Crítico: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()