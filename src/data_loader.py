import json
from typing import List, Tuple
from .model import Curso, Profesor, Aula, Grupo, Clase

def load_data(cursos_path: str, profesores_path: str, aulas_path: str, grupos_path: str, clases_path: str) -> Tuple[List[Curso], List[Profesor], List[Aula], List[Grupo], List[Clase]]:
    with open(cursos_path, 'r', encoding='utf-8') as f:
        cursos_data = json.load(f)
        cursos = [Curso(**c) for c in cursos_data]

    with open(profesores_path, 'r', encoding='utf-8') as f:
        profesores_data = json.load(f)
        profesores = [Profesor(**p) for p in profesores_data]

    with open(aulas_path, 'r', encoding='utf-8') as f:
        aulas_data = json.load(f)
        aulas = [Aula(**a) for a in aulas_data]

    with open(grupos_path, 'r', encoding='utf-8') as f:
        grupos_data = json.load(f)
        grupos = [Grupo(**g) for g in grupos_data]

    with open(clases_path, 'r', encoding='utf-8') as f:
        clases_data = json.load(f)
        clases = [Clase(**c) for c in clases_data]

    return cursos, profesores, aulas, grupos, clases

def load_config(config_path: str) -> dict:
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)
