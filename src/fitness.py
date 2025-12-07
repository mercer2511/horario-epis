from typing import List, Dict, Set, Tuple
from collections import defaultdict
from .model import Curso, Profesor, Aula, Horario, Sesion, Grupo, Clase

class FitnessEvaluator:
    def __init__(self, cursos: List[Curso], profesores: List[Profesor], aulas: List[Aula], grupos: List[Grupo], clases: List[Clase], config: dict):
        self.cursos = {c.id: c for c in cursos}
        self.profesores = {p.id: p for p in profesores}
        self.aulas = {a.id: a for a in aulas}
        self.grupos = {g.id: g for g in grupos}
        self.clases = clases
        self.config = config
        
        # Ranges definition
        self.TURN_RANGES = {
            "MAÑANA": (0, 7),
            "TARDE": (7, 18),
            "NOCHE": (13, 18),
            "NOCHE_A": (13, 18),
            "NOCHE_B": (13, 18)
        }
        
        self.group_ancestry = self._build_group_ancestry()

    def _build_group_ancestry(self) -> Dict[str, Set[str]]:
        children_map = {g_id: [] for g_id in self.grupos}
        for g in self.grupos.values():
            if g.parent_grupo_id:
                children_map[g.parent_grupo_id].append(g.id)

        related = {g_id: set() for g_id in self.grupos}
        for g_id, group in self.grupos.items():
            related[g_id].add(g_id)
            curr = group
            while curr.parent_grupo_id:
                related[g_id].add(curr.parent_grupo_id)
                curr = self.grupos[curr.parent_grupo_id]
            
            queue = [g_id]
            while queue:
                curr_id = queue.pop(0)
                for child_id in children_map[curr_id]:
                    related[g_id].add(child_id)
                    queue.append(child_id)
        return related

    def evaluate(self, individual: Horario) -> float:
        score = 0.0
        
        # Build maps once
        prof_schedule = defaultdict(set)
        room_schedule = defaultdict(set)
        group_schedule = defaultdict(set)
        prof_hours = defaultdict(float)
        group_day_starts = defaultdict(lambda: defaultdict(list))
        
        # Penalties
        HARD_PENALTY = 5000
        BREAK_PENALTY = 10000
        SOFT_PENALTY = 10
        EARLY_START_PENALTY = 5
        
        break_slots = set(self.config.get('break_slots', [6]))
        total_slots = len(self.config.get('time_slots', []))

        # 1. Single Pass Loop for Per-Session Checks
        for sesion in individual.sesiones:
            # Metadata
            clase = next((c for c in self.clases if c.id == sesion.clase_id), None)
            if not clase: continue # Should not happen
            
            group_id = clase.grupo_id
            grupo = self.grupos[group_id]
            aula = self.aulas[sesion.aula_id]
            
            session_slots = range(sesion.start_slot_idx, sesion.start_slot_idx + sesion.num_slots)
            
            # Update aggregates
            prof_hours[sesion.profesor_id] += sesion.num_slots
            group_day_starts[sesion.clase_id][sesion.dia_idx].append(sesion.start_slot_idx)

            # --- HARD CONSTRAINTS (Immediate Check) ---
            
            # Break Overlap
            for s in session_slots:
                if s in break_slots:
                    score -= BREAK_PENALTY
            
            # Bounds
            if sesion.start_slot_idx + sesion.num_slots > total_slots:
                score -= HARD_PENALTY

            # Room Capacity
            if aula.capacidad < grupo.num_estudiantes:
                score -= HARD_PENALTY

            # --- RESOURCE CONFLICTS (Map Building) ---
            related_groups = self.group_ancestry.get(group_id, {group_id})
            
            for slot in session_slots:
                key = (sesion.dia_idx, slot)
                
                # Professor Conflict
                if sesion.profesor_id in prof_schedule[key]:
                    score -= HARD_PENALTY
                prof_schedule[key].add(sesion.profesor_id)
                
                # Room Conflict
                if sesion.aula_id in room_schedule[key]:
                    score -= HARD_PENALTY
                room_schedule[key].add(sesion.aula_id)
                
                # Group Hierarchical Conflict
                conflict = False
                # Efficient check: intersection of scheduled groups at this slot vs related groups
                # Since related_groups is small, we can iterate or set overlap
                # optimization: group_schedule[key] is a bucket of group_ids
                for occupied_group in group_schedule[key]:
                    if occupied_group in related_groups:
                        conflict = True
                        break
                if conflict:
                    score -= HARD_PENALTY
                group_schedule[key].add(group_id)

            # --- SOFT CONSTRAINTS (Turn Preference) ---
            if grupo.turno in self.TURN_RANGES:
                turn_start, turn_end = self.TURN_RANGES[grupo.turno]
                s_start = sesion.start_slot_idx
                s_end = sesion.start_slot_idx + sesion.num_slots - 1
                
                # Count slots outside range
                # Valid slots: [turn_start, turn_end]
                # Session: [s_start, s_end]
                # Intersection: [max(turn_start, s_start), min(turn_end, s_end)]
                # If intersection invalid (start > end), then 0 valid slots.
                # Total slots = num_slots
                # Out = Total - Valid
                
                v_start = max(turn_start, s_start)
                v_end = min(turn_end, s_end)
                
                valid_count = max(0, v_end - v_start + 1)
                out_of_turn = sesion.num_slots - valid_count
                
                if out_of_turn > 0:
                    score -= (out_of_turn * SOFT_PENALTY)

        # 2. Post-Loop Checks
        
        # Max Hours Per Professor
        for prof_id, total in prof_hours.items():
            max_h = self.profesores[prof_id].max_horas_semana
            if total > max_h:
                score -= (total - max_h) * HARD_PENALTY
                
        # Early Start Preference
        class_group_map = {c.id: self.grupos[c.grupo_id] for c in self.clases}
        for clase_id, days_data in group_day_starts.items():
            group = class_group_map[clase_id]
            turn_start = 0
            if group.turno == 'TARDE': turn_start = 7
            elif 'NOCHE' in group.turno: turn_start = 13
            
            for day, starts in days_data.items():
                if not starts: continue
                first_class = min(starts)
                if first_class > turn_start:
                    gap = first_class - turn_start
                    score -= gap * EARLY_START_PENALTY
                    
        return score

    def get_conflicts(self, individual: Horario) -> List[str]:
        conflicts = []
        break_slots = set(self.config.get('break_slots', [6]))
        total_slots = len(self.config.get('time_slots', []))
        
        prof_schedule = defaultdict(set) # (dia, slot) -> Set[(prof_id, curso_nombre)]
        room_schedule = defaultdict(set) # (dia, slot) -> Set[(aula_id, curso_nombre)]
        group_schedule = defaultdict(set) # (dia, slot) -> Set[(group_id, curso_nombre)]
        prof_hours = defaultdict(float)

        # Iterate
        for sesion in individual.sesiones:
            clase = next(c for c in self.clases if c.id == sesion.clase_id)
            curso = self.cursos[clase.curso_id]
            grupo = self.grupos[clase.grupo_id]
            profesor = self.profesores[sesion.profesor_id]
            aula = self.aulas[sesion.aula_id]
            
            session_slots = range(sesion.start_slot_idx, sesion.start_slot_idx + sesion.num_slots)
            
            prof_hours[sesion.profesor_id] += sesion.num_slots
            
            # Break
            for s in session_slots:
                if s in break_slots:
                    conflicts.append(f"BREAK CONFLICT: {curso.nombre} (Group {grupo.id}) overlaps with break at slot {s}.")
                    break
            
            # Bounds
            if sesion.start_slot_idx + sesion.num_slots > total_slots:
                conflicts.append(f"BOUNDS CONFLICT: {curso.nombre} (Group {grupo.id}) goes out of time bounds.")

            # Capacity
            if aula.capacidad < grupo.num_estudiantes:
                conflicts.append(f"CAPACITY CONFLICT: {aula.nombre} ({aula.capacidad}) too small for {grupo.id} ({grupo.num_estudiantes})")
            
            related_groups = self.group_ancestry.get(grupo.id, {grupo.id})

            for slot in session_slots:
                key = (sesion.dia_idx, slot)
                time_str = f"Day {sesion.dia_idx} Slot {slot}"
                
                # Check Maps
                # Prof
                # To provide detailed error, we check who is there
                # prof_schedule[key] contains tuples (prof_id, curso_nome)
                for p_id, c_name in prof_schedule[key]:
                    if p_id == sesion.profesor_id:
                        conflicts.append(f"PROF CONFLICT: {profesor.nombre} has {curso.nombre} and {c_name} at {time_str}")
                prof_schedule[key].add((sesion.profesor_id, curso.nombre))
                
                # Room
                for r_id, c_name in room_schedule[key]:
                    if r_id == sesion.aula_id:
                        conflicts.append(f"ROOM CONFLICT: {aula.nombre} has {curso.nombre} and {c_name} at {time_str}")
                room_schedule[key].add((sesion.aula_id, curso.nombre))
                
                # Group
                for g_id, c_name in group_schedule[key]:
                    if g_id in related_groups:
                        conflicts.append(f"GROUP CONFLICT: Group {grupo.id} conflicts with {g_id} ({c_name}) at {time_str}")
                group_schedule[key].add((grupo.id, curso.nombre))

        # Max Hours
        for prof_id, total in prof_hours.items():
            max_h = self.profesores[prof_id].max_horas_semana
            if total > max_h:
                conflicts.append(f"MAX HOURS CONFLICT: {self.profesores[prof_id].nombre} assigned {total} slots, limit {max_h}")

        return list(set(conflicts))
