"""
IMDC Dashboard - Wrapper con autenticación
Configuración: Repo PÚBLICO + Contraseña + Secrets en Streamlit Cloud
Seguridad: ⭐⭐⭐⭐ (uso personal/empresarial)
"""

import streamlit as st
import os
from pathlib import Path
import hashlib
import time

st.set_page_config(
    page_title="IMDC Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# AUTENTICACIÓN
# ============================================================

def hash_password(password: str) -> str:
    """Hash SHA-256 de la contraseña"""
    return hashlib.sha256(password.encode()).hexdigest()

def check_password():
    """Sistema de autenticación con protección anti fuerza bruta"""
    
    # IMPORTANTE: El hash debe estar en Streamlit Secrets, no aquí
    if "password_hash" not in st.secrets:
        st.error("❌ Configuración incompleta. Configura 'password_hash' en Streamlit Secrets.")
        st.info("💡 Ve a Settings > Secrets y agrega: password_hash = \"TU_HASH_AQUI\"")
        st.stop()
    
    VALID_HASH = st.secrets["password_hash"]
    SESSION_TIMEOUT = 3600  # 60 minutos
    MAX_ATTEMPTS = 3
    LOCKOUT_TIME = 300  # 5 minutos
    
    # Inicializar estado
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.last_activity = None
        st.session_state.failed_attempts = 0
        st.session_state.lockout_until = None
    
    # Verificar timeout de sesión
    if st.session_state.authenticated and st.session_state.last_activity:
        if time.time() - st.session_state.last_activity > SESSION_TIMEOUT:
            st.session_state.authenticated = False
            st.warning("⏱️ Sesión expirada por inactividad.")
    
    # Si autenticado, actualizar actividad
    if st.session_state.authenticated:
        st.session_state.last_activity = time.time()
        return True
    
    # Verificar lockout
    if st.session_state.lockout_until:
        if time.time() < st.session_state.lockout_until:
            remaining = int(st.session_state.lockout_until - time.time())
            st.error(f"🔒 Bloqueado por seguridad. Espera {remaining} segundos.")
            return False
        else:
            st.session_state.lockout_until = None
            st.session_state.failed_attempts = 0
    
    # Pantalla de login
    st.markdown("""
    <div style='text-align:center; padding:40px 0 20px 0;'>
        <h1 style='color:#2563EB; margin-bottom:8px;'>📊 IMDC Dashboard</h1>
        <p style='color:#64748B; font-size:14px;'>Sistema de Análisis de Ventas</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("login_form"):
            password = st.text_input("🔐 Contraseña", type="password", 
                                     placeholder="Ingresa tu contraseña")
            submit = st.form_submit_button("Iniciar Sesión", use_container_width=True)
            
            if submit:
                if hash_password(password) == VALID_HASH:
                    st.session_state.authenticated = True
                    st.session_state.last_activity = time.time()
                    st.session_state.failed_attempts = 0
                    st.rerun()
                else:
                    st.session_state.failed_attempts += 1
                    
                    if st.session_state.failed_attempts >= MAX_ATTEMPTS:
                        st.session_state.lockout_until = time.time() + LOCKOUT_TIME
                        st.error(f"🔒 Demasiados intentos fallidos. Bloqueado por 5 minutos.")
                    else:
                        remaining = MAX_ATTEMPTS - st.session_state.failed_attempts
                        st.error(f"❌ Contraseña incorrecta. Te quedan {remaining} intento(s).")
    
    return False


# ============================================================
# DESCARGA DE DATOS DESDE GOOGLE DRIVE
# ============================================================

def download_from_drive():
    """Descarga parquets desde Google Drive usando Service Account"""
    
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
        import io
        
        # Verificar secrets
        if "gcp_service_account" not in st.secrets:
            st.error("❌ Credenciales de Google no configuradas.")
            st.info("💡 Configura 'gcp_service_account' en Streamlit Secrets")
            st.stop()
        
        if "gdrive_folder_id" not in st.secrets:
            st.error("❌ ID de carpeta de Google Drive no configurado.")
            st.info("💡 Configura 'gdrive_folder_id' en Streamlit Secrets")
            st.stop()
        
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        
        service = build('drive', 'v3', credentials=credentials)
        folder_id = st.secrets["gdrive_folder_id"]
        
        # Crear directorio temporal
        data_dir = Path("/tmp/imdc_data")
        data_dir.mkdir(exist_ok=True)
        
        # Listar archivos .parquet
        query = f"'{folder_id}' in parents and name contains '.parquet' and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        
        if not files:
            st.error("❌ No se encontraron archivos .parquet en Google Drive")
            st.info("💡 Verifica que compartiste la carpeta con el Service Account")
            st.stop()
        
        # Descargar archivos
        with st.spinner(f"📥 Descargando {len(files)} archivo(s)..."):
            for file in files:
                file_path = data_dir / file['name']
                
                # Cachear por 1 hora
                if file_path.exists():
                    age = time.time() - file_path.stat().st_mtime
                    if age < 3600:
                        continue
                
                request = service.files().get_media(fileId=file['id'])
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                
                with open(file_path, 'wb') as f:
                    f.write(fh.getvalue())
        
        # Comunicar ruta al dashboard
        os.environ["IMDC_DATA_DIR"] = str(data_dir)
        return True
        
    except Exception as e:
        st.error(f"❌ Error al descargar datos: {str(e)}")
        with st.expander("Ver detalles del error"):
            st.exception(e)
        st.stop()


# ============================================================
# MAIN
# ============================================================

def main():
    if not check_password():
        st.stop()
    
    download_from_drive()
    
    try:
        import imdc_web_FINAL_COMPLETO
    except Exception as e:
        st.error(f"❌ Error al cargar el dashboard: {str(e)}")
        st.exception(e)


if __name__ == "__main__":
    main()
