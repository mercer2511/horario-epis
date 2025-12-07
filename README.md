# Sistema de Horarios Académicos EPIS - Algoritmo Genético

Este proyecto implementa un **Algoritmo Genético (AG)** para generar horarios académicos óptimos y libres de conflictos para la Escuela Profesional de Ingeniería de Sistemas (EPIS).

## 🚀 Guía de Inicio Rápido

### 1. Requisitos Previos
- Python 3.8 o superior.
- Librerías estándar (no requiere dependencias externas pesadas, solo `json`, `csv`, `random`, `collections`).

### 2. Flujo de Trabajo Recomendado

El proceso de generación de horarios consta de 4 pasos principales:

#### Paso 1: Verificación de Viabilidad (Pre-Check)
Antes de ejecutar el algoritmo, verifica si tienes suficientes profesores y aulas para cubrir la demanda.
```powershell
python check_feasibility.py
```
*Si este paso muestra errores críticos (Déficit de oferta), el algoritmo no encontrará una solución perfecta.*

#### Paso 2: Generación del Horario (Ejecución del AG)
Ejecuta el algoritmo genético. Este script leerá los datos, evolucionará poblaciones y exportará el mejor horario encontrado a `horario_generado.csv`.
```powershell
python src/main.py
```

#### Paso 3: Validación de Resultados
Verifica que el horario generado cumpla con todas las reglas (duplicados, horas máximas, cruces).
```powershell
python analyze_schedule.py
```

#### Paso 4: Visualización
Genera archivos HTML interactivos para ver el horario por ciclo con colores.
```powershell
python src/visualizer.py
```
*Los archivos se guardarán como `horario_ciclo_X.html` en la carpeta raíz.*

---

## 📁 Estructura de Datos (`data/`)

*   **`cursos.json`**: Definición de asignaturas (ID, nombre, ciclo, horas).
*   **`profesores.json`**: Docentes disponibles y sus horas máximas semanales (`max_horas_semana`).
*   **`aulas.json`**: Aulas disponibles y su capacidad.
*   **`grupos.json`**: Secciones por curso (ej. C1-A, C5-B) y su turno preferido (MAÑANA, TARDE, NOCHE).
*   **`clases.json`**: La demanda real. Define qué profesor dicta qué grupo y cuántos bloques dura la sesión.

---

## 🧬 Documentación Técnica del Algoritmo Genético

El núcleo del sistema se encuentra en `src/genetic_algorithm.py`. A continuación se detallan sus componentes:

### 1. Representación (Cromosoma)
Un **Individuo** (`Horario`) es una lista completa de **Sesiones**.
*   **Gen**: Una `Sesion` única que contiene:
    *   `clase_id`: ID de la demanda.
    *   `profesor_id`: Docente asignado.
    *   `aula_id`: Aula asignada.
    *   `dia_idx`: Día de la semana (0=Lunes, 4=Viernes).
    *   `start_slot_idx`: Bloque de inicio (0=08:00, 1=08:45, ...).

### 2. Función de Aptitud (Fitness)
El `score` inicia en 0 y se restan puntos por cada infracción. Se busca maximizar el puntaje (cercano a 0 es mejor).

#### Restricciones Duras (Hard Constraints) - Penalización Alta
Si se violan, el horario es inválido.
1.  **Conflictos de Profesor**: Un docente no puede estar en dos aulas al mismo tiempo.
2.  **Conflictos de Aula**: Un aula no puede tener dos clases al mismo tiempo.
3.  **Conflictos de Grupo**: Un grupo de alumnos no puede tener dos cursos a la vez (incluye jerarquía de grupos padre/hijo).
4.  **Capacidad de Aula**: El aula debe soportar el número de estudiantes del grupo.
5.  **Refrigerio de Almuerzo**: Ninguna clase puede solaparse con el bloque de break (12:30 - 13:15).
6.  **Horas Máximas**: El profesor no puede exceder su límite de `max_horas_semana`.

#### Restricciones Suaves (Soft Constraints) - Penalización Baja
Son deseables pero no obligatorias.
1.  **Preferencia de Turno**: Si un grupo es "MAÑANA", se penaliza si sus clases caen fuera del rango 08:00-14:00.
2.  **Inicio Temprano (Early Start)**: Se penaliza si, dentro de su turno, el grupo tiene "huecos" al inicio (ej. empezar a la 3ra hora si la 1ra estaba libre). Esto promueve horarios compactos que inician a las 08:00 am.

### 3. Operadores Genéticos

#### Selección
*   **Torneo**: Se escogen aleatoriamente 5 individuos y se selecciona el mejor para ser padre.

#### Cruce (Crossover)
*   **Uniforme**: Cada sesión del hijo se toma aleatoriamente del Padre 1 o del Padre 2 (50/50). Esto preserva asignaciones válidas individuales.

#### Mutación
*   Se modifica aleatoriamente un atributo de una sesión (Día, Slot, Aula, Profesor) con una probabilidad baja (`mutation_rate`).
*   **Heurística Inteligente**:
    *   Al mutar el `slot`, el algoritmo tiene un **90% de probabilidad** de escoger un bloque dentro del turno preferido del grupo.
    *   Adicionalmente, hay un sesgo del **50%** para escoger específicamente el **bloque de inicio** del turno, acelerando la convergencia hacia horarios de "Inicio Temprano".

### 4. Configuración (`config.json`)
*   `population_size`: Número de horarios simultáneos (ej. 100).
*   `max_generations`: Cuántas iteraciones correrá el algoritmo.
*   `mutation_rate`: Probabilidad de cambio aleatorio.
*   `elitism_count`: Cuántos mejores individuos pasan intactos a la siguiente generación.

---

## 🛠 Scripts de Utilidad

*   **`update_mappings.py`**: Script para actualizar rápidamente qué profesores dictan qué curso en `cursos.json`. Útil para corregir asignaciones erróneas.
*   **`check_inconsistencies.py`**: Valida que las horas definidas en `cursos.json` coincidan con los bloques en `clases.json`.

---
*Escuela Profesional de Ingeniería de Sistemas - 2024*
