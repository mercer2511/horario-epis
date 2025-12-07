import os
import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Esquema de seguridad: Espera un header "Authorization: Bearer <token>"
security = HTTPBearer()

def init_firebase():
    """Inicializa la app de Firebase si no existe ya."""
    try:
        if not firebase_admin._apps:
            # En Cloud Run, esto usa las credenciales por defecto del servicio automáticamente
            # En local, busca la variable GOOGLE_APPLICATION_CREDENTIALS
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"⚠️ Advertencia Firebase: {e}")

# Inicializamos al importar el módulo
init_firebase()

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    """
    Valida el token JWT de Firebase.
    Retorna el UID del usuario si es válido.
    """
    token = creds.credentials
    try:
        # En modo desarrollo local, si no quieres validar tokens reales cada vez,
        # podrías poner un "bypass" aquí, pero por seguridad lo dejamos estricto.
        
        # Verifica la firma del token con los servidores de Google
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        return uid
        
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token ha expirado. Por favor inicia sesión nuevamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )