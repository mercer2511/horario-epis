import os
import json
import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def init_firebase():
    """
    Inicializa la app de Firebase usando explícitamente la variable de entorno
    GCP_CREDENTIALS_JSON para evitar conflictos de proyectos en Cloud Run.
    """
    try:
        if not firebase_admin._apps:
            # 1. Buscamos la variable que ya configuraste en Cloud Run
            creds_json = os.environ.get('GCP_CREDENTIALS_JSON')
            
            if creds_json:
                # Si existe, parseamos el JSON y creamos credenciales explícitas
                cred_dict = json.loads(creds_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                print("✅ Firebase inicializado con GCP_CREDENTIALS_JSON")
            else:
                # Fallback para local si tienes el archivo físico
                print("⚠️ No se detectó GCP_CREDENTIALS_JSON, buscando ApplicationDefault...")
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred)
                
    except Exception as e:
        # Imprimimos el error real para verlo en los logs de Cloud Run si falla
        print(f"❌ CRITICAL ERROR inicializando Firebase: {str(e)}")
        # No hacemos raise aquí para no matar el import, pero fallará al usarlo.

# Inicializamos al importar
init_firebase()

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    """Valida el token JWT."""
    token = creds.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        return uid
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o expiradas",
            headers={"WWW-Authenticate": "Bearer"},
        )