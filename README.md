# Api Generador de Horarios EPIS (Cloud Run Backend)

Este repositorio aloja el **Servicio Backend** para la generación inteligente de horarios de la Escuela Profesional de Ingeniería de Sistemas.

Funciona como una **API REST** construida con **FastAPI** y desplegada en **Google Cloud Run**, que ejecuta un Algoritmo Genético avanzado para crear horarios libres de conflictos.

---

## 🚀 Arquitectura

*   **Backend**: Python 3.13 + FastAPI.
*   **Algoritmo**: Genético (Evolutivo) implementado en Python puro.
*   **Base de Datos**: Google Sheets (Lectura de configuración y Plan de Estudios).
*   **Autenticación**: Firebase Auth (JWT).
*   **Infraestructura**: Docker + Cloud Run.

---

## 📡 Documentación de la API

La API expone los siguientes endpoints para ser consumidos por el Frontend (React/Next.js/etc).

### 1. Estado del Servicio
Verifica si el backend está online.

*   **Endpoint:** `GET /`
*   **Auth:** Pública.
*   **Respuesta:**
    ```json
    {
      "status": "online",
      "system": "HorarioEPIS AI"
    }
    ```

### 2. Resumen de Datos
Obtiene métricas rápidas sobre los datos cargados desde Google Sheets.

*   **Endpoint:** `GET /data/summary`
*   **Auth:** Pública.
*   **Respuesta:**
    ```json
    {
      "total_cursos": 36,
      "total_profesores": 36,
      "total_grupos": 29,
      "total_aulas": 14
    }
    ```

### 3. Generar Horario (Core)
Ejecuta el Algoritmo Genético bajo demanda. Este proceso puede tardar unos segundos (o minutos dependiendo de la complejidad).

*   **Endpoint:** `POST /generate`
*   **Auth:** Requiere Token Bearer de Firebase.
*   **Header:** `Authorization: Bearer <FIREBASE_ID_TOKEN>`
*   **Respuesta Exitosa (200 OK):**
    Retorna el horario generado y una lista de conflictos (si los hubiera, aunque el objetivo es 0 conflictos).
    ```json
    {
      "status": "Exito",
      "fitness": -50.0,
      "conflicts": [],
      "schedule": [
        {
          "dia": "Lunes",
          "hora_inicio": "08:00",
          "hora_fin": "10:15",
          "curso": "INTELIGENCIA ARTIFICIAL",
          "grupo": "C8-M",
          "aula": "LAB-01",
          "profesor": "Juan Perez",
          "tipo_aula": "Laboratorio"
        },
        ...
      ]
    }
    ```
*   **Errores Posibles:**
    *   `401 Unauthorized`: Token inválido o expirado.
    *   `500 Internal Server Error`: Fallo en el algoritmo o conexión a Sheets.

---

## 🔐 Autenticación

Este servicio está protegido. Para consumir el endpoint `/generate`, el cliente debe:

1.  Iniciar sesión en el Frontend usando **Firebase Authentication**.
2.  Obtener el `idToken` del usuario logueado.
3.  Enviar este token en el header `Authorization` de la petición HTTP.

---

## 🧬 Detalles del Algoritmo

El backend utiliza una estrategia evolutiva para resolver el problema de horarios (CSP).

### Restricciones Manejadas (Hard Constraints)
El sistema garantiza evitar:
1.  **Cruces de Docente**: Un profe en dos sitios a la vez.
2.  **Cruces de Aula**: Un aula con dos clases a la vez.
3.  **Cruces de Grupo**: Estudiantes con dos clases a la vez (incluyendo lógica de subgrupos A/B).
4.  **Aforo**: Cantidad de alumnos > Capacidad del aula.
5.  **Refrigerio**: Clases chocando con el break (12:30-13:15).
6.  **Carga Acuémica**: Profesores excediendo sus horas contratadas.

---

## 🛠 Desarrollo Local

Para correr el servidor en tu máquina:

1.  **Instalar dependencias:**
    ```powershell
    pip install -r requirements.txt
    ```
2.  **Configurar Credenciales:**
    *   Coloca `credentials.json` (Service Account de Google) en la raíz.
    *   O configura la variable de entorno `GOOGLE_APPLICATION_CREDENTIALS`.
3.  **Ejecutar Servidor:**
    ```powershell
    uvicorn src.api:app --reload
    ```
    El API estará disponible en `http://127.0.0.1:8000`.

4.  **Swagger UI:**
    Visita `http://127.0.0.1:8000/docs` para probar los endpoints interactivamente.

---

## ☁️ Despliegue en Cloud Run

El proyecto incluye un `Dockerfile` optimizado.

1.  **Construir imagen:**
    ```bash
    gcloud builds submit --tag gcr.io/TU_PROYECTO/horario-backend
    ```
2.  **Desplegar:**
    ```bash
    gcloud run deploy horario-api --image gcr.io/TU_PROYECTO/horario-backend --platform managed
    ```
