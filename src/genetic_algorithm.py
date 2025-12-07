import random
import copy
from typing import List, Dict, Set
from .model import Curso, Profesor, Aula, Horario, Sesion, Grupo, Clase

class GeneticAlgorithm:
    def __init__(self, cursos: List[Curso], profesores: List[Profesor], aulas: List[Aula], grupos: List[Grupo], clases: List[Clase], config: dict):
        self.cursos = {c.id: c for c in cursos}
        self.profesores = {p.id: p for p in profesores}
        self.aulas = {a.id: a for a in aulas}
        self.grupos = {g.id: g for g in grupos}
        self.clases = clases
        self.config = config
        self.population: List[Horario] = []

        # Turn definitions (start_slot, end_slot) inclusive of the range available
        # Based on config: 0=08:00, 7=13:15(start)-14:00(end), 13=17:45, 18=21:30-22:15
        self.TURN_RANGES = {
            "MAÑANA": (0, 7),   # 08:00 - 14:00
            "TARDE": (7, 18),   # 13:15 - 22:15 (User specified "hasta el final")
            "NOCHE": (13, 18),  # 17:45 - 22:15
            "NOCHE_A": (13, 18),
            "NOCHE_B": (13, 18)
        }
        
        # Pre-process group hierarchy for fast lookup
        self.group_ancestry = self._build_group_ancestry()
        
        # Pre-process eligible professors per course for fast lookup
        self.course_professors = {c.id: c.profesores_ids for c in cursos}
        
        # Pre-process classrooms by type
        self.classrooms_by_type = {}
        for a in aulas:
            if a.tipo not in self.classrooms_by_type:
                self.classrooms_by_type[a.tipo] = []
            self.classrooms_by_type[a.tipo].append(a.id)

    def _build_group_ancestry(self) -> Dict[str, Set[str]]:
        """
        Returns a dict where key is group_id and value is a set of all related group_ids 
        (ancestors, descendants, and self) that would cause a conflict.
        """
        # 1. Map parent -> children
        children_map = {g_id: [] for g_id in self.grupos}
        for g in self.grupos.values():
            if g.parent_grupo_id:
                children_map[g.parent_grupo_id].append(g.id)

        # 2. Build related set for each group
        related = {g_id: set() for g_id in self.grupos}
        
        for g_id, group in self.grupos.items():
            related[g_id].add(g_id)
            
            # Add ancestors
            curr = group
            while curr.parent_grupo_id:
                related[g_id].add(curr.parent_grupo_id)
                curr = self.grupos[curr.parent_grupo_id]
            
            # Add descendants (BFS)
            queue = [g_id]
            while queue:
                curr_id = queue.pop(0)
                for child_id in children_map[curr_id]:
                    related[g_id].add(child_id)
                    queue.append(child_id)
                    
        return related

    def initialize_population(self):
        self.population = []
        for _ in range(self.config['population_size']):
            individual = self._create_random_individual()
            self.population.append(individual)

    def _create_random_individual(self) -> Horario:
        sesiones = []
        for clase in self.clases:
            # 1. Assign Professor
            eligible_profs = self.course_professors.get(clase.curso_id, [])
            if not eligible_profs:
                # Fallback if no professor assigned (should not happen with correct data)
                prof_id = list(self.profesores.keys())[0]
            else:
                prof_id = random.choice(eligible_profs)

            # 2. Assign Classroom
            eligible_rooms = self.classrooms_by_type.get(clase.tipo_aula, [])
            if not eligible_rooms:
                # Fallback
                aula_id = list(self.aulas.keys())[0]
            else:
                aula_id = random.choice(eligible_rooms)

            # 3. Assign Time Slot
            # Avoid break slot (index 6) and ensure it fits in the day
            num_slots = clase.duracion_bloques
            num_days = len(self.config['days'])
            total_slots = len(self.config['time_slots'])
            
            # Try to find a valid slot (simple retry mechanism)
            dia_idx = random.randint(0, num_days - 1)
            
            # Intelligent initialization: try to pick a slot in the group's turn
            grupo = self.grupos[clase.grupo_id]
            valid_range = self.TURN_RANGES.get(grupo.turno)
            
            if valid_range and random.random() < 0.8: # 80% chance to pick preferred turn
                start, end = valid_range
                # Ensure we have enough space for the class
                effective_end = end - num_slots + 1 
                if effective_end > start:
                    start_slot_idx = random.randint(start, effective_end)
                else:
                    start_slot_idx = random.randint(0, total_slots - num_slots)
            else:
                start_slot_idx = random.randint(0, total_slots - num_slots)
            
            # Simple heuristic: try to avoid break overlap if possible, but allow it for now 
            # (fitness will punish it if we define it as a constraint)
            
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
        score = 0.0
        HARD_PENALTY = 1000
        SOFT_PENALTY = 10
        
        # Data structures for conflict checking
        # (Day, Slot) -> Set of occupied resources
        prof_schedule = {} # (dia, slot) -> {prof_id}
        room_schedule = {} # (dia, slot) -> {aula_id}
        group_schedule = {} # (dia, slot) -> {group_id}
        
        break_slot = 6 # Index of break slot

        for sesion in individual.sesiones:
            # Check break overlap
            session_slots = range(sesion.start_slot_idx, sesion.start_slot_idx + sesion.num_slots)
            if break_slot in session_slots:
                score -= HARD_PENALTY # Class during break
            
            # Check slot bounds
            if sesion.start_slot_idx + sesion.num_slots > len(self.config['time_slots']):
                score -= HARD_PENALTY # Class goes out of bounds

            clase = next(c for c in self.clases if c.id == sesion.clase_id)
            group_id = clase.grupo_id
            
            for slot in session_slots:
                key = (sesion.dia_idx, slot)
                
                # 1. Professor Conflict
                if key not in prof_schedule: prof_schedule[key] = set()
                if sesion.profesor_id in prof_schedule[key]:
                    score -= HARD_PENALTY
                prof_schedule[key].add(sesion.profesor_id)
                
                # 2. Room Conflict
                if key not in room_schedule: room_schedule[key] = set()
                if sesion.aula_id in room_schedule[key]:
                    score -= HARD_PENALTY
                room_schedule[key].add(sesion.aula_id)
                
                # 3. Group Conflict (Hierarchy)
                if key not in group_schedule: group_schedule[key] = set()
                
                # Check if any related group is already scheduled
                related_groups = self.group_ancestry.get(group_id, {group_id})
                conflict = False
                for occupied_group in group_schedule[key]:
                    if occupied_group in related_groups:
                        conflict = True
                        break
                
                if conflict:
                    score -= HARD_PENALTY
                
                group_schedule[key].add(group_id)

            # 4. Room Capacity
            aula = self.aulas[sesion.aula_id]
            grupo = self.grupos[group_id]
            if aula.capacidad < grupo.num_estudiantes:
                 score -= HARD_PENALTY

            # 5. Turn Preference (Soft Constraint)
            # Check if all slots fall within the preferred turn range
            if grupo.turno in self.TURN_RANGES:
                turn_start, turn_end = self.TURN_RANGES[grupo.turno]
                # Slots are 0-indexed. 
                # Range is inclusive [start, end].
                # Session uses slots [start_slot_idx, start_slot_idx + num_slots - 1]
                
                s_start = sesion.start_slot_idx
                s_end = sesion.start_slot_idx + sesion.num_slots - 1
                
                # Check if the session is essentially OUTSIDE the range
                # We punish each slot that is outside the range
                out_of_turn_slots = 0
                for s_idx in range(s_start, s_end + 1):
                    if not (turn_start <= s_idx <= turn_end):
                        out_of_turn_slots += 1
                
                score -= (out_of_turn_slots * SOFT_PENALTY)

        # 6. Global Professor Max Hours Check (Hard Constraint)
        # We need to re-scan or track hours.
        # Let's count total slots per professor
        prof_hours = {}
        for sesion in individual.sesiones:
            if sesion.profesor_id not in prof_hours:
                prof_hours[sesion.profesor_id] = 0
            prof_hours[sesion.profesor_id] += sesion.num_slots
            
        for prof_id, total_slots in prof_hours.items():
            max_h = self.profesores[prof_id].max_horas_semana
            if total_slots > max_h:
                # Heavy penalty for every slot over the limit
                overage = total_slots - max_h
                score -= (overage * HARD_PENALTY)

        individual.fitness = score
        return score

    def get_conflicts(self, individual: Horario) -> List[str]:
        conflicts = []
        
        # Data structures for conflict checking
        prof_schedule = {} 
        room_schedule = {} 
        group_schedule = {} 
        
        break_slot = 6 

        for sesion in individual.sesiones:
            clase = next(c for c in self.clases if c.id == sesion.clase_id)
            curso = self.cursos[clase.curso_id]
            grupo = self.grupos[clase.grupo_id]
            profesor = self.profesores[sesion.profesor_id]
            aula = self.aulas[sesion.aula_id]
            
            session_slots = range(sesion.start_slot_idx, sesion.start_slot_idx + sesion.num_slots)
            
            # Check break overlap
            if break_slot in session_slots:
                conflicts.append(f"BREAK CONFLICT: {curso.nombre} (Group {grupo.id}) overlaps with break.")
            
            # Check slot bounds
            if sesion.start_slot_idx + sesion.num_slots > len(self.config['time_slots']):
                conflicts.append(f"BOUNDS CONFLICT: {curso.nombre} (Group {grupo.id}) goes out of time bounds.")

            for slot in session_slots:
                key = (sesion.dia_idx, slot)
                time_str = f"Day {sesion.dia_idx} Slot {slot}"
                
                # 1. Professor Conflict
                if key not in prof_schedule: prof_schedule[key] = []
                if sesion.profesor_id in [x[0] for x in prof_schedule[key]]:
                    other_class = [x[1] for x in prof_schedule[key] if x[0] == sesion.profesor_id][0]
                    conflicts.append(f"PROF CONFLICT: {profesor.nombre} has {curso.nombre} and {other_class} at {time_str}")
                prof_schedule[key].append((sesion.profesor_id, curso.nombre))
                
                # 2. Room Conflict
                if key not in room_schedule: room_schedule[key] = []
                if sesion.aula_id in [x[0] for x in room_schedule[key]]:
                    other_class = [x[1] for x in room_schedule[key] if x[0] == sesion.aula_id][0]
                    conflicts.append(f"ROOM CONFLICT: {aula.nombre} has {curso.nombre} and {other_class} at {time_str}")
                room_schedule[key].append((sesion.aula_id, curso.nombre))
                
                # 3. Group Conflict (Hierarchy)
                if key not in group_schedule: group_schedule[key] = []
                
                related_groups = self.group_ancestry.get(grupo.id, {grupo.id})
                for occupied_group_id, occupied_course_name in group_schedule[key]:
                    if occupied_group_id in related_groups:
                        conflicts.append(f"GROUP CONFLICT: Group {grupo.id} conflicts with {occupied_group_id} ({occupied_course_name}) at {time_str}")
                
                group_schedule[key].append((grupo.id, curso.nombre))

            # 4. Room Capacity
            if aula.capacidad < grupo.num_estudiantes:
                 conflicts.append(f"CAPACITY CONFLICT: {aula.nombre} ({aula.capacidad}) too small for {grupo.id} ({grupo.num_estudiantes})")

        # 5. Global Professor Max Hours Check
        prof_hours = {}
        for sesion in individual.sesiones:
            if sesion.profesor_id not in prof_hours:
                prof_hours[sesion.profesor_id] = 0
            prof_hours[sesion.profesor_id] += sesion.num_slots
            
        for prof_id, total_slots in prof_hours.items():
            max_h = self.profesores[prof_id].max_horas_semana
            if total_slots > max_h:
                conflicts.append(f"MAX HOURS CONFLICT: {self.profesores[prof_id].nombre} assigned {total_slots} slots, limit {max_h}")

        return list(set(conflicts)) # Remove duplicates

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
        for i in range(len(individual.sesiones)):
            if random.random() < self.config['mutation_rate']:
                # Mutate one attribute randomly
                attr = random.choice(['dia', 'slot', 'aula', 'profesor'])
                sesion = individual.sesiones[i]
                clase = next(c for c in self.clases if c.id == sesion.clase_id)
                
                if attr == 'dia':
                    sesion.dia_idx = random.randint(0, len(self.config['days']) - 1)
                elif attr == 'slot':
                    max_slot = len(self.config['time_slots']) - sesion.num_slots
                    grupo = self.grupos[clase.grupo_id]
                    valid_range = self.TURN_RANGES.get(grupo.turno)
                    
                    if valid_range and random.random() < 0.7: # Bias mutation towards preferred turn
                        start, end = valid_range
                        effective_end = end - sesion.num_slots + 1
                        if effective_end > start:
                            # Clamp within valid bounds
                            safe_start = max(0, start)
                            safe_end = min(max_slot, effective_end)
                            if safe_end >= safe_start:
                                sesion.start_slot_idx = random.randint(safe_start, safe_end)
                            else:
                                sesion.start_slot_idx = random.randint(0, max_slot)
                        else:
                            sesion.start_slot_idx = random.randint(0, max_slot)
                    else:
                        sesion.start_slot_idx = random.randint(0, max_slot)
                elif attr == 'aula':
                    eligible_rooms = self.classrooms_by_type.get(clase.tipo_aula, [])
                    if eligible_rooms:
                        sesion.aula_id = random.choice(eligible_rooms)
                elif attr == 'profesor':
                    eligible_profs = self.course_professors.get(clase.curso_id, [])
                    if eligible_profs:
                        sesion.profesor_id = random.choice(eligible_profs)

    def evolve(self):
        self.initialize_population()
        
        for generation in range(self.config['max_generations']):
            # Calculate fitness for all
            for ind in self.population:
                self.calculate_fitness(ind)
            
            # Sort to find best
            self.population.sort(key=lambda x: x.fitness, reverse=True)
            best_fitness = self.population[0].fitness
            
            if generation % 10 == 0:
                print(f"Generation {generation}: Best Fitness = {best_fitness}")
                
            if best_fitness == 0: # Perfect score (assuming 0 is max possible with current penalty logic)
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
            
        # Final evaluation
        for ind in self.population:
            self.calculate_fitness(ind)
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        
        return self.population[0]
