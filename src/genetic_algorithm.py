import random
import copy
from typing import List, Dict, Set
from collections import defaultdict
from .model import Curso, Profesor, Aula, Horario, Sesion, Grupo, Clase
from .fitness import FitnessEvaluator

# --- Parallel Execution Helpers ---
_worker_evaluator = None

def _init_worker(evaluator):
    """Inicializa el worker con el evaluador (una sola vez por proceso)."""
    global _worker_evaluator
    _worker_evaluator = evaluator

def _evaluate_wrapper(individual):
    """Función top-level para evaluar individuo usando el evaluador global del worker."""
    if _worker_evaluator:
         # El método evaluate devuelve un float
        return _worker_evaluator.evaluate(individual)
    return -999999.0

class GeneticAlgorithm:
    def __init__(self, cursos: List[Curso], profesores: List[Profesor], aulas: List[Aula], grupos: List[Grupo], clases: List[Clase], config: dict):
        self.cursos = {c.id: c for c in cursos}
        self.profesores = {p.id: p for p in profesores}
        self.aulas = {a.id: a for a in aulas}
        self.grupos = {g.id: g for g in grupos}
        self.clases = clases
        self.config = config
        self.population: List[Horario] = []
        
        # Initialize Evaluator
        self.evaluator = FitnessEvaluator(cursos, profesores, aulas, grupos, clases, config)

        # Access constants from evaluator or define locally if needed for mutations
        # We need TURN_RANGES for mutation/init
        self.TURN_RANGES = self.evaluator.TURN_RANGES
        
        # Pre-process eligible professors per course for fast lookup (Optimized for Init/Mutation)
        self.course_professors = {c.id: c.profesores_ids for c in cursos}
        
        # Pre-process classrooms by type
        self.classrooms_by_type = {}
        for a in aulas:
            if a.tipo not in self.classrooms_by_type:
                self.classrooms_by_type[a.tipo] = []
            self.classrooms_by_type[a.tipo].append(a.id)

    def initialize_population(self):
        self.population = []
        for _ in range(self.config['population_size']):
            individual = self._create_random_individual()
            self.population.append(individual)

    def _create_random_individual(self) -> Horario:
        sesiones = []
        total_slots = len(self.config['time_slots'])
        break_slots = self.config.get('break_slots', [6])
        first_break_idx = break_slots[0] if break_slots else -1

        for clase in self.clases:
            # 1. Assign Professor
            eligible_profs = self.course_professors.get(clase.curso_id, [])
            if not eligible_profs:
                # Fallback
                prof_id = list(self.profesores.keys())[0] if self.profesores else "UNKNOWN"
            else:
                prof_id = random.choice(eligible_profs)

            # 2. Assign Classroom
            eligible_rooms = self.classrooms_by_type.get(clase.tipo_aula, [])
            if not eligible_rooms:
                # Fallback
                aula_id = list(self.aulas.keys())[0] if self.aulas else "UNKNOWN"
            else:
                aula_id = random.choice(eligible_rooms)

            # 3. Assign Time Slot
            num_slots = clase.duracion_bloques
            num_days = len(self.config['days'])
            
            dia_idx = random.randint(0, num_days - 1)
            
            grupo = self.grupos[clase.grupo_id]
            valid_range = self.TURN_RANGES.get(grupo.turno)
            
            # --- INTELLIGENT INITIALIZATION FOR LONG CLASSES ---
            is_long_morning = (grupo.turno == "MAÑANA" and num_slots >= 5)
            
            if is_long_morning and first_break_idx >= 0:
                if num_slots <= first_break_idx:
                     start_slot_idx = 0
                else:
                    start_slot_idx = 0
            
            elif valid_range and random.random() < 0.9: 
                start, end = valid_range
                effective_end = end - num_slots + 1 
                if effective_end > start:
                    if random.random() < 0.5:
                        start_slot_idx = start
                    else:
                        start_slot_idx = random.randint(start, effective_end)
                else:
                    start_slot_idx = random.randint(0, max(0, total_slots - num_slots))
            else:
                start_slot_idx = random.randint(0, max(0, total_slots - num_slots))
            
            sesion = Sesion(
                clase_id=clase.id,
                profesor_id=prof_id,
                aula_id=aula_id,
                dia_idx=dia_idx,
                start_slot_idx=start_slot_idx,
                num_slots=num_slots
            )
            sesiones.append(sesion)
            
        return Horario(sesiones=sesiones)

    def calculate_fitness(self, individual: Horario) -> float:
        # Delegate to FitnessEvaluator (used for serialfallback or init)
        individual.fitness = self.evaluator.evaluate(individual)
        return individual.fitness

    def get_conflicts(self, individual: Horario) -> List[str]:
        # Delegate to FitnessEvaluator
        return self.evaluator.get_conflicts(individual)

    def selection(self) -> Horario:
        # Tournament Selection
        tournament_size = 5
        tournament = random.sample(self.population, tournament_size)
        return max(tournament, key=lambda x: x.fitness)

    def crossover(self, parent1: Horario, parent2: Horario) -> Horario:
        # Uniform Crossover
        if random.random() > self.config['crossover_rate']:
            return copy.deepcopy(parent1)
            
        child_sesiones = []
        for i in range(len(parent1.sesiones)):
            if random.random() < 0.5:
                child_sesiones.append(copy.deepcopy(parent1.sesiones[i]))
            else:
                child_sesiones.append(copy.deepcopy(parent2.sesiones[i]))
        
        return Horario(sesiones=child_sesiones)

    def mutation(self, individual: Horario):
        break_slots = self.config.get('break_slots', [6])
        first_break_idx = break_slots[0] if break_slots else -1

        for i in range(len(individual.sesiones)):
            if random.random() < self.config['mutation_rate']:
                attr = random.choice(['dia', 'slot', 'aula', 'profesor'])
                sesion = individual.sesiones[i]
                clase = next(c for c in self.clases if c.id == sesion.clase_id)
                
                if attr == 'dia':
                    sesion.dia_idx = random.randint(0, len(self.config['days']) - 1)
                elif attr == 'slot':
                    max_slot = len(self.config['time_slots']) - sesion.num_slots
                    grupo = self.grupos[clase.grupo_id]
                    valid_range = self.TURN_RANGES.get(grupo.turno)
                    
                    is_long_morning = (grupo.turno == "MAÑANA" and sesion.num_slots >= 5)

                    if is_long_morning and first_break_idx >= 0 and random.random() < 0.8:
                        sesion.start_slot_idx = 0
                    
                    elif valid_range and random.random() < 0.8: 
                        start, end = valid_range
                        effective_end = end - sesion.num_slots + 1
                        if effective_end > start:
                            safe_start = max(0, start)
                            safe_end = min(max_slot, effective_end)
                            if safe_end >= safe_start:
                                if random.random() < 0.5:
                                    sesion.start_slot_idx = safe_start
                                else:
                                    sesion.start_slot_idx = random.randint(safe_start, safe_end)
                            else:
                                sesion.start_slot_idx = random.randint(0, max(0, max_slot))
                        else:
                            sesion.start_slot_idx = random.randint(0, max(0, max_slot))
                    else:
                        sesion.start_slot_idx = random.randint(0, max(0, max_slot))
                elif attr == 'aula':
                    eligible_rooms = self.classrooms_by_type.get(clase.tipo_aula, [])
                    if eligible_rooms:
                        sesion.aula_id = random.choice(eligible_rooms)
                elif attr == 'profesor':
                    eligible_profs = self.course_professors.get(clase.curso_id, [])
                    if eligible_profs:
                        sesion.profesor_id = random.choice(eligible_profs)

    def evolve(self, on_progress: callable = None, should_cancel: callable = None):
        self.initialize_population()
        
        max_gens = self.config['max_generations']

        # Import local to avoid top-level overhead if not used
        print(f"🚀 Iniciando evolución paralela con 4 workers...")
        
        with ProcessPoolExecutor(max_workers=4, initializer=_init_worker, initargs=(self.evaluator,)) as executor:
            
            for generation in range(max_gens):
                # Check Cancellation
                if should_cancel and should_cancel():
                    print("🛑 Genetic Algorithm cancelled by user.")
                    return None

                # PARALLEL FITNESS EVALUATION
                # Map returns results in order
                results = list(executor.map(_evaluate_wrapper, self.population))
                
                # Assign fitness back to individuals
                for ind, fit in zip(self.population, results):
                    ind.fitness = fit
                
                # Sort to find best
                self.population.sort(key=lambda x: x.fitness, reverse=True)
                best_fitness = self.population[0].fitness
                
                # Update Progress every 5 generations or first/last
                if on_progress and (generation % 5 == 0 or generation == max_gens - 1):
                    on_progress(generation, best_fitness)
                
                if generation % 10 == 0:
                    print(f"Generation {generation}: Best Fitness = {best_fitness}")
                    
                if best_fitness == 0: 
                    print("Solution found!")
                    break

                new_population = []
                
                # Elitism
                new_population.extend(copy.deepcopy(self.population[:self.config['elitism_count']]))
                
                # Generate rest
                while len(new_population) < self.config['population_size']:
                    parent1 = self.selection()
                    parent2 = self.selection()
                    child = self.crossover(parent1, parent2)
                    self.mutation(child)
                    new_population.append(child)
                
                self.population = new_population
            
        # Final evaluation (Serial or Parallel, reusing pool is cleaner but we exited context)
        # For simplicity and given population size is small, serial final pass or reuse logic.
        # Since we are out of context, let's do serial or minimal overhead.
        for ind in self.population:
            self.calculate_fitness(ind)
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        
        return self.population[0]
