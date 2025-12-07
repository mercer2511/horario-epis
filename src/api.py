import os
import sys
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import uvicorn

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_loader import load_data, load_config
from src.genetic_algorithm import GeneticAlgorithm
from src.auth import get_current_user

app = FastAPI(
    title="API Generador de Horarios EPIS",
    version="1.1.0"
)

# Constantes
SPREADSHEET_NAME = "INFORMACION_HORARIOS"
CREDENTIALS_FILE = "credentials.json"

# --- Modelos de Datos (JSON Response) ---

class SessionData(BaseModel):
    dia: str
    hora_inicio: str
    hora_fin: str
    curso: str
    grupo: str
    aula: str
    profesor: str
    tipo_aula: str

class ScheduleResponse(BaseModel):
    status: str
    fitness: float
    conflicts: List[str]
    # ESTO ES NUEVO: La lista real de clases para el frontend
    schedule: List[SessionData] 

class DataSummary(BaseModel):
    total_cursos: int
    total_profesores: int
    total_grupos: int
    total_aulas: int

# --- Endpoints ---

@app.get("/", tags=["General"])
def read_root():
    return {"status": "online", "system": "HorarioEPIS AI"}

@app.get("/data/summary", response_model=DataSummary, tags=["Datos"])
def get_data_summary():
    try:
        cursos, profesores, aulas, grupos, clases = load_data(SPREADSHEET_NAME, CREDENTIALS_FILE)
        return {
            "total_cursos": len(cursos),
            "total_profesores": len(profesores),
            "total_grupos": len(grupos),
            "total_aulas": len(aulas)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/generate", response_model=ScheduleResponse, tags=["Algoritmo"])
def run_genetic_algorithm(current_user: str = Depends(get_current_user)):
    """
    Ejecuta el algoritmo y devuelve el horario estructurado en JSON.
    """
    print(f"🚀 Usuario {current_user} solicitando generación...")
    
    try:
        # 1. Cargar datos
        config = load_config(SPREADSHEET_NAME, CREDENTIALS_FILE)
        cursos, profesores, aulas, grupos, clases = load_data(SPREADSHEET_NAME, CREDENTIALS_FILE)
        
        # 2. Ejecutar GA
        ga = GeneticAlgorithm(cursos, profesores, aulas, grupos, clases, config)
        best_schedule = ga.evolve()
        conflicts = ga.get_conflicts(best_schedule)
        
        # 3. Procesar el resultado para el Frontend (Transformar IDs a Nombres)
        json_output = []
        days = config['days']
        slots = config['time_slots']
        
        # Ordenar sesiones para que salgan ordenadas en el JSON
        def get_sort_key(s):
            # Necesitamos buscar la clase para saber el grupo
            c_obj = next((c for c in clases if c.id == s.clase_id), None)
            return (s.dia_idx, s.start_slot_idx, c_obj.grupo_id if c_obj else "")

        sorted_sessions = sorted(best_schedule.sesiones, key=get_sort_key)

        for s in sorted_sessions:
            # Buscar objetos relacionales
            clase = next(c for c in clases if c.id == s.clase_id)
            curso = next(c for c in cursos if c.id == clase.curso_id)
            prof = next(p for p in profesores if p.id == s.profesor_id)
            aula = next(a for a in aulas if a.id == s.aula_id)
            grupo = next(g for g in grupos if g.id == clase.grupo_id)
            
            # Calcular horas legibles
            start_time = "ERROR"
            end_time = "ERROR"
            
            if s.start_slot_idx < len(slots):
                start_time = slots[s.start_slot_idx].split('-')[0]
                end_slot_idx = s.start_slot_idx + s.num_slots - 1
                if end_slot_idx < len(slots):
                    end_time = slots[end_slot_idx].split('-')[1]
                else:
                    end_time = "OUT_OF_BOUNDS"
            
            # Crear objeto de sesión para la respuesta
            session_data = SessionData(
                dia=days[s.dia_idx],
                hora_inicio=start_time,
                hora_fin=end_time,
                curso=curso.nombre,
                grupo=grupo.id,
                aula=aula.nombre,
                profesor=prof.nombre,
                tipo_aula=aula.tipo
            )
            json_output.append(session_data)

        # 4. Retornar respuesta completa
        status_msg = "Exito" if not conflicts else "Con Conflictos"
        
        return {
            "status": status_msg,
            "fitness": best_schedule.fitness,
            "conflicts": conflicts,
            "schedule": json_output # <--- Aquí van los datos reales
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Fallo en algoritmo: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("src.api:app", host="127.0.0.1", port=8000, reload=True)