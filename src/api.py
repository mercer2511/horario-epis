import os
import sys
import uuid
from typing import List, Optional, Dict
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks # <--- BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware # <--- 1. IMPORTAR ESTO
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

# Configuración de CORS
origins = [
    "http://localhost:5173", # Vite por defecto
    "http://localhost:5174", # Tu puerto actual
    "http://localhost:3000", # React clásico
    "*"                      # Permitir todo (Útil para desarrollo y evitar dolores de cabeza)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # En producción puedes poner solo tu dominio real
    allow_credentials=True,
    allow_methods=["*"],      # Permitir GET, POST, OPTIONS, etc.
    allow_headers=["*"],      # Permitir el header Authorization (¡CRUCIAL PARA FIREBASE!)
)
# ------------------------------------------------

# Constantes
SPREADSHEET_NAME = "INFORMACION_HORARIOS"
CREDENTIALS_FILE = "credentials.json"

# --- Sistema de Jobs (En memoria para Demo/Cloud Run Instance Single) ---
jobs: Dict[str, Dict] = {} 
active_job_id: Optional[str] = None # Semáforo Singleton 

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

# Cambiamos @app.get por @app.api_route para aceptar GET y HEAD
@app.api_route("/", methods=["GET", "HEAD"], tags=["General"])
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

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Fallo en algoritmo: {str(e)}")

# --- Async GA Task Wrapper ---
def run_ga_bg_task(job_id: str):
    """
    Ejecuta el GA en segundo plano y actualiza el diccionario global 'jobs'.
    """
    global active_job_id
    try:
        print(f"🔄 [Job {job_id}] Iniciando tarea en segundo plano...")
        
        # 1. Cargar datos
        config = load_config(SPREADSHEET_NAME, CREDENTIALS_FILE)
        cursos, profesores, aulas, grupos, clases = load_data(SPREADSHEET_NAME, CREDENTIALS_FILE)
        
        # Definir callback para reportar progreso
        max_gens = config['max_generations']
        
        def on_progress_update(generation, fitness):
            percent = int((generation / max_gens) * 100)
            jobs[job_id]["progress"] = percent
            jobs[job_id]["fitness"] = fitness
            # print(f"Job {job_id}: {percent}% (Fit: {fitness})")

        def check_cancellation():
            return jobs[job_id]["status"] == "cancelled"

        # 2. Ejecutar GA
        ga = GeneticAlgorithm(cursos, profesores, aulas, grupos, clases, config)
        
        # Llamamos a evolve pasando el callback
        best_schedule = ga.evolve(on_progress=on_progress_update, should_cancel=check_cancellation)
        
        if best_schedule is None:
             print(f"🛑 [Job {job_id}] Detenido por solicitud del usuario.")
             return # Salimos de la función background
             
        conflicts = ga.get_conflicts(best_schedule)
        
        # 3. Procesar resultado
        json_output = []
        days = config['days']
        slots = config['time_slots']
        
        def get_sort_key(s):
            c_obj = next((c for c in clases if c.id == s.clase_id), None)
            return (s.dia_idx, s.start_slot_idx, c_obj.grupo_id if c_obj else "")

        sorted_sessions = sorted(best_schedule.sesiones, key=get_sort_key)

        for s in sorted_sessions:
            clase = next(c for c in clases if c.id == s.clase_id)
            curso = next(c for c in cursos if c.id == clase.curso_id)
            prof = next(p for p in profesores if p.id == s.profesor_id)
            aula = next(a for a in aulas if a.id == s.aula_id)
            grupo = next(g for g in grupos if g.id == clase.grupo_id)
            
            start_time = "ERROR"
            end_time = "ERROR"
            
            if s.start_slot_idx < len(slots):
                start_time = slots[s.start_slot_idx].split('-')[0]
                end_slot_idx = s.start_slot_idx + s.num_slots - 1
                if end_slot_idx < len(slots):
                    end_time = slots[end_slot_idx].split('-')[1]
                else:
                    end_time = "OUT_OF_BOUNDS"
            
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
            
        status_msg = "Exito" if not conflicts else "Con Conflictos"
        
        # 4. Guardar resultado final en el estado del job
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["result"] = {
            "status": status_msg,
            "fitness": best_schedule.fitness,
            "conflicts": conflicts,
            "schedule": [item.model_dump() for item in json_output]
        }
        print(f"✅ [Job {job_id}] Completado exitosamente.")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        print(f"❌ [Job {job_id}] Falló: {e}")
    finally:
        # Liberar el semáforo SIEMPRE, pase lo que pase
        if active_job_id == job_id:
            print(f"🔓 Liberando semáforo del job {job_id}")
            active_job_id = None

class JobResponse(BaseModel):
    job_id: str
    status: str

@app.post("/generate", response_model=JobResponse, tags=["Algoritmo"])
def start_genetic_algorithm(background_tasks: BackgroundTasks, current_user: str = Depends(get_current_user)):
    """
    Inicia la generación en segundo plano y devuelve un Job ID.
    Usa GET /progress/{job_id} para ver el estado.
    """
    global active_job_id
    
    # 1. Check Semáforo
    if active_job_id is not None:
        # Verificar si el job activo realmente existe y está corriendo
        current_job = jobs.get(active_job_id)
        if current_job and current_job["status"] == "running":
            raise HTTPException(
                status_code=503, 
                detail="El servidor está ocupado procesando otro horario. Por favor intente en unos minutos."
            )
        else:
            # Auto-reparación: Si estaba seteado pero el status no es running, liberamos
            print("⚠️ Semáforo inconsistente detectado. Reseteando.")
            active_job_id = None

    job_id = str(uuid.uuid4())
    
    # Toma el semáforo
    active_job_id = job_id
    
    # Inicializar estado del job
    jobs[job_id] = {
        "status": "running",
        "progress": 0,
        "fitness": 0.0,
        "result": None,
        "user": current_user
    }
    
    # Encolar tarea en segundo plano
    background_tasks.add_task(run_ga_bg_task, job_id)
    
    return {"job_id": job_id, "status": "started"}

@app.get("/progress/{job_id}", tags=["Algoritmo"])
def get_job_progress(job_id: str, current_user: str = Depends(get_current_user)):
    """
    Devuelve el progreso del algoritmo.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job no encontrado")
        
    job = jobs[job_id]
    
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job.get("progress", 0),
        "fitness": job.get("fitness", 0),
        "result": job.get("result"), # Será null mientras corre, y tendrá el horario al final
        "error": job.get("error")
    }

@app.post("/cancel/{job_id}", tags=["Algoritmo"])
def cancel_job(job_id: str, current_user: str = Depends(get_current_user)):
    """
    Cancela un trabajo en ejecución.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    if jobs[job_id]["status"] in ["completed", "failed"]:
        return {"status": "job_already_finished"}
        
    jobs[job_id]["status"] = "cancelled"
    return {"status": "cancelled"}

class SaveRequest(BaseModel):
    schedule: List[SessionData]

@app.post("/save", tags=["Persistencia"])
def save_schedule(payload: SaveRequest, current_user: str = Depends(get_current_user)):
    """
    Guarda el horario validado en Google Sheets (Hoja 'Resultados').
    """
    print(f"💾 Usuario {current_user} guardando resultados...")
    
    # Convertir modelos Pydantic a lista de dicts
    data_to_save = [item.model_dump() for item in payload.schedule]
    
    try:
        # Import lazy para evitar dependencia circular si estuviera arriba (aunque aquí no hay)
        from src.data_loader import save_schedule_to_sheet
        
        save_schedule_to_sheet(data_to_save, SPREADSHEET_NAME, CREDENTIALS_FILE)
        
        return {"status": "Guardado exitosamente", "records": len(data_to_save)}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al guardar: {str(e)}")

class ScheduleStateResponse(BaseModel):
    exists: bool
    count: int
    schedule: List[SessionData]

@app.get("/schedule/latest", response_model=ScheduleStateResponse, tags=["Persistencia"])
def get_latest_schedule(current_user: str = Depends(get_current_user)):
    """
    Consulta si existe un horario previamente guardado en Sheets.
    Útil para recuperar el estado al recargar la página.
    """
    try:
        from src.data_loader import get_saved_schedule
        
        saved_data = get_saved_schedule(SPREADSHEET_NAME, CREDENTIALS_FILE)
        
        return {
            "exists": len(saved_data) > 0,
            "count": len(saved_data),
            "schedule": saved_data
        }
    except Exception as e:
        # No queremos que falle toda la app si Sheets falla en esta consulta no crítica
        print(f"⚠️ Error recuperando horario guardado: {e}")
        return {
            "exists": False,
            "count": 0,
            "schedule": []
        }

if __name__ == "__main__":
    uvicorn.run("src.api:app", host="127.0.0.1", port=8000, reload=True)