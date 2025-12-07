import os
import sys
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends # <--- FALTABA ESTO
from pydantic import BaseModel
import uvicorn

# Agregar el directorio raíz al path para importar módulos src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_loader import load_data, load_config
from src.genetic_algorithm import GeneticAlgorithm
from src.auth import get_current_user # <--- FALTABA ESTO

# Inicializar la aplicación FastAPI
app = FastAPI(
    title="API Generador de Horarios EPIS",
    description="Backend inteligente para generar horarios universitarios usando Algoritmos Genéticos.",
    version="1.0.0"
)

# Constantes
SPREADSHEET_NAME = "INFORMACION_HORARIOS"
CREDENTIALS_FILE = "credentials.json"

# --- Modelos de Datos ---
class ConflictDetail(BaseModel):
    message: str

class ScheduleResponse(BaseModel):
    status: str
    fitness: float
    generations_run: int
    conflicts: List[str]

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
def get_data_summary(): # Este endpoint puede ser público o protegido, tú decides
    try:
        cursos, profesores, aulas, grupos, clases = load_data(SPREADSHEET_NAME, CREDENTIALS_FILE)
        return {
            "total_cursos": len(cursos),
            "total_profesores": len(profesores),
            "total_grupos": len(grupos),
            "total_aulas": len(aulas)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cargando datos: {str(e)}")

# AQUI ESTA LA PROTECCION
@app.post("/generate", response_model=ScheduleResponse, tags=["Algoritmo"])
def run_genetic_algorithm(current_user: str = Depends(get_current_user)):
    """
    Ejecuta el Algoritmo Genético.
    REQUIERE AUTENTICACIÓN: Header 'Authorization: Bearer <firebase_token>'
    """
    print(f"🚀 Usuario autenticado {current_user} solicita horario...")
    try:
        config = load_config(SPREADSHEET_NAME, CREDENTIALS_FILE)
        cursos, profesores, aulas, grupos, clases = load_data(SPREADSHEET_NAME, CREDENTIALS_FILE)
        
        ga = GeneticAlgorithm(cursos, profesores, aulas, grupos, clases, config)
        best_schedule = ga.evolve()
        conflicts = ga.get_conflicts(best_schedule)
        
        status_msg = "Exito" if not conflicts else "Con Conflictos"
        
        return {
            "status": status_msg,
            "fitness": best_schedule.fitness,
            "generations_run": config['max_generations'],
            "conflicts": conflicts
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Fallo en el algoritmo: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("src.api:app", host="127.0.0.1", port=8000, reload=True)