import os
import json
import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def init_firebase():
    """
    Inicializa Firebase usando la misma credencial maestra que usamos para Sheets.
    Esto evita errores de permisos en Cloud Run.
    """
    try:
        # Evitar reinicializar si ya existe
        if not firebase_admin._apps:
            
            # 1. Intentamos leer la variable que configuraste en Secret Manager
            creds_json = os.environ.get('GCP_CREDENTIALS_JSON')
            
            if creds_json:
                # Parseamos el JSON string a un diccionario
                cred_dict = json.loads(creds_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                print("✅ Firebase inicializado correctamente con GCP_CREDENTIALS_JSON")
            else:
                # Fallback solo para desarrollo local si no hay variable
                print("⚠️ No se encontró GCP_CREDENTIALS_JSON. Intentando ApplicationDefault...")
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred)
                
    except Exception as e:
        # Imprimimos el error pero NO detenemos la app (evita el crash del contenedor)
        # Si falla, la API arrancará pero los endpoints protegidos darán error 500.
        print(f"❌ ERROR CRÍTICO al iniciar Firebase: {str(e)}")

# Ejecutamos la inicialización al importar el archivo
init_firebase()

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    """Valida el token JWT enviado por el Frontend."""
    token = creds.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        return uid
    except Exception as e:
        print(f"Error de auth: {e}") # Debug en logs
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )