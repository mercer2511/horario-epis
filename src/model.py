from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class Curso:
    id: str
    nombre: str
    ciclo: str
    horas_semanales: int
    tipo: str  # 'Teoria' o 'Laboratorio'
    profesores_ids: List[str]

@dataclass
class Profesor:
    id: str
    nombre: str
    max_horas_semana: int
    disponibilidad: Dict[str, List[str]] # Dia -> Lista de rangos horarios "HH:MM-HH:MM"

@dataclass
class Aula:
    id: str
    nombre: str
    capacidad: int
    tipo: str # 'Teoria' o 'Laboratorio'

@dataclass
class Grupo:
    id: str
    nombre: str
    ciclo: int
    turno: str
    seccion: str
    num_estudiantes: int
    parent_grupo_id: Optional[str] = None

@dataclass
class Clase:
    id: str
    curso_id: str
    grupo_id: str
    duracion_bloques: int
    tipo_aula: str

@dataclass
class Sesion:
    clase_id: str # Referencia a la clase que se está programando
    profesor_id: str
    aula_id: str
    dia_idx: int # 0=Lunes, 1=Martes, ...
    start_slot_idx: int # Índice del slot de inicio (0-18)
    num_slots: int # Duración en slots (debe coincidir con Clase.duracion_bloques)

@dataclass
class Horario:
    sesiones: List[Sesion]
    fitness: float = 0.0
