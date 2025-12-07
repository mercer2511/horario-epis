import json
import os
from typing import List, Tuple, Dict, Any
import gspread
from google.oauth2.service_account import Credentials
from .model import Curso, Profesor, Aula, Grupo, Clase

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def _get_gspread_client(credentials_path: str = 'credentials.json') -> gspread.Client:
    """
    Obtiene el cliente de gspread usando autenticación híbrida:
    1. Intenta leer la variable de entorno GCP_CREDENTIALS_JSON (Cloud Run).
    2. Si no existe, intenta leer el archivo credentials_path (Local).
    """
    creds_json_str = os.environ.get('GCP_CREDENTIALS_JSON')

    if creds_json_str:
        try:
            creds_dict = json.loads(creds_json_str)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        except json.JSONDecodeError as e:
             raise ValueError("Error al decodificar GCP_CREDENTIALS_JSON") from e
    else:
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"No se encontró el archivo de credenciales: {credentials_path} y GCP_CREDENTIALS_JSON no está definida.")
        creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)

    return gspread.authorize(creds)

def load_data(spreadsheet_name: str, credentials_path: str = 'credentials.json') -> Tuple[List[Curso], List[Profesor], List[Aula], List[Grupo], List[Clase]]:
    """
    Carga los datos desde una Google Sheet.
    """
    client = _get_gspread_client(credentials_path)
    
    try:
        sh = client.open(spreadsheet_name)
    except gspread.SpreadsheetNotFound:
        raise ValueError(f"No se encontró la hoja de cálculo: {spreadsheet_name}")

    # --- Cursos ---
    ws_cursos = sh.worksheet("Cursos")
    cursos_records = ws_cursos.get_all_records()
    cursos = []
    for r in cursos_records:
        # Parse profesores_ids: "DOC1, DOC2" -> ["DOC1", "DOC2"]
        prof_ids_str = str(r.get('profesores_ids', ''))
        prof_ids = [pid.strip() for pid in prof_ids_str.split(',') if pid.strip()]
        
        cursos.append(Curso(
            id=str(r['id']),
            nombre=str(r['nombre']),
            ciclo=str(r['ciclo']),
            horas_semanales=int(r['horas_semanales']),
            tipo=str(r['tipo']),
            profesores_ids=prof_ids
        ))

    # --- Profesores ---
    ws_profesores = sh.worksheet("Profesores")
    profesores_records = ws_profesores.get_all_records()
    profesores = []
    for r in profesores_records:
        # Parse disponibilidad: String JSON -> Dict
        disp_str = str(r.get('disponibilidad', '{}'))
        try:
            disponibilidad = json.loads(disp_str)
        except json.JSONDecodeError:
            disponibilidad = {}
            print(f"Advertencia: Error al parsear disponibilidad para profesor {r.get('id')}, usando {{}}")

        profesores.append(Profesor(
            id=str(r['id']),
            nombre=str(r['nombre']),
            max_horas_semana=int(r['max_horas_semana']),
            disponibilidad=disponibilidad
        ))

    # --- Aulas ---
    ws_aulas = sh.worksheet("Aulas")
    aulas_records = ws_aulas.get_all_records()
    aulas = [Aula(
        id=str(r['id']),
        nombre=str(r['nombre']),
        capacidad=int(r['capacidad']),
        tipo=str(r['tipo'])
    ) for r in aulas_records]

    # --- Grupos ---
    ws_grupos = sh.worksheet("Grupos")
    grupos_records = ws_grupos.get_all_records()
    grupos = []
    for r in grupos_records:
        try:
           parent_id = str(r.get('parent_grupo_id', '')).strip()
           if not parent_id:
               parent_id = None
        except ValueError:
            parent_id = None

        grupos.append(Grupo(
            id=str(r['id']),
            nombre=str(r['nombre']),
            ciclo=int(r['ciclo']),
            turno=str(r['turno']),
            seccion=str(r['seccion']),
            num_estudiantes=int(r['num_estudiantes']),
            parent_grupo_id=parent_id
        ))

    # --- Clases ---
    ws_clases = sh.worksheet("Clases")
    clases_records = ws_clases.get_all_records()
    clases = [Clase(
        id=str(r['id']),
        curso_id=str(r['curso_id']),
        grupo_id=str(r['grupo_id']),
        duracion_bloques=int(r['duracion_bloques']),
        tipo_aula=str(r['tipo_aula'])
    ) for r in clases_records]

    return cursos, profesores, aulas, grupos, clases

def load_config(spreadsheet_name: str, credentials_path: str = 'credentials.json') -> dict:
    """
    Carga la configuración desde la hoja 'Configuracion'.
    Maneja tipos de datos específicos (enteros, listas, floats).
    """
    client = _get_gspread_client(credentials_path)
    try:
        sh = client.open(spreadsheet_name)
    except gspread.SpreadsheetNotFound:
        raise ValueError(f"No se encontró la hoja de cálculo: {spreadsheet_name}")
        
    ws_config = sh.worksheet("Configuracion")
    records = ws_config.get_all_records()
    
    # Crear diccionario base
    raw_config = {r['parametro']: r['valor'] for r in records}
    config = {}

    # 1. Enteros simples
    for key in ['population_size', 'max_generations', 'elitism_count']:
        if key in raw_config:
            config[key] = int(raw_config[key])
    
    # 2. Floats
    for key in ['mutation_rate', 'crossover_rate']:
        if key in raw_config:
            # Reemplazar coma por punto si viene formato español (0,01 -> 0.01)
            val = str(raw_config[key]).replace(',', '.')
            config[key] = float(val)
            
    # 3. Listas de ENTEROS (Caso especial para break_slots)
    # IMPORTANTE: El algoritmo genético espera [6], no ["6"]
    if 'break_slots' in raw_config:
        val = raw_config['break_slots']
        if isinstance(val, str):
             # "6, 12" -> [6, 12]
             config['break_slots'] = [int(x.strip()) for x in val.split(',') if x.strip().isdigit()]
        elif isinstance(val, (int, float)):
             config['break_slots'] = [int(val)]
        else:
             config['break_slots'] = [] # Default seguro

    # 4. Listas de STRINGS (time_slots, days)
    for key in ['time_slots', 'days']:
        if key in raw_config:
            val = raw_config[key]
            if isinstance(val, str):
                config[key] = [x.strip() for x in val.split(',') if x.strip()]
            else:
                config[key] = [str(val)]

    # Copiar cualquier otro valor que no requiera conversión especial
    for k, v in raw_config.items():
        if k not in config:
            config[k] = v

    return config