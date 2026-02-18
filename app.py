"""
IMDC Dashboard - Wrapper con autenticación
"""

import streamlit as st
import sys
import traceback

# Configuración de página PRIMERO (antes de cualquier otra cosa)
st.set_page_config(
    page_title="IMDC Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Manejo de errores global
try:
    import os
    from pathlib import Path
    import hashlib
    import time

    # ============================================================
    # AUTENTICACIÓN
    # ============================================================

    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def check_password():
        if "password_hash" not in st.secrets:
            st.error("❌ Falta password_hash en Secrets")
            st.stop()
        
        VALID_HASH = st.secrets["password_hash"]
        SESSION_TIMEOUT = 3600
        MAX_ATTEMPTS = 3
        LOCKOUT_TIME = 300
        
        if "authenticated" not in st.session_state:
            st.session_state.authenticated = False
            st.session_state.last_activity = None
            st.session_state.failed_attempts = 0
            st.session_state.lockout_until = None
        
        if st.session_state.authenticated and st.session_state.last_activity:
            if time.time() - st.session_state.last_activity > SESSION_TIMEOUT:
                st.session_state.authenticated = False
                st.warning("⏱️ Sesión expirada")
        
        if st.session_state.authenticated:
            st.session_state.last_activity = time.time()
            return True
        
        if st.session_state.lockout_until:
            if time.time() < st.session_state.lockout_until:
                remaining = int(st.session_state.lockout_until - time.time())
                st.error(f"🔒 Bloqueado. Espera {remaining}s")
                return False
            else:
                st.session_state.lockout_until = None
                st.session_state.failed_attempts = 0
        
        st.markdown("""
        <div style='text-align:center; padding:40px 0 20px 0;'>
            <h1 style='color:#2563EB;'>📊 IMDC Dashboard</h1>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            with st.form("login_form"):
                password = st.text_input("🔐 Contraseña", type="password")
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
                            st.error(f"🔒 Bloqueado por 5 minutos")
                        else:
                            remaining = MAX_ATTEMPTS - st.session_state.failed_attempts
                            st.error(f"❌ Incorrecta. {remaining} intento(s)")
        
        return False

    # ============================================================
    # DESCARGA DE DATOS
    # ============================================================

    def download_from_drive():
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaIoBaseDownload
            import io
            
            if "gcp_service_account" not in st.secrets:
                st.error("❌ Falta gcp_service_account en Secrets")
                st.stop()
            
            if "gdrive_folder_id" not in st.secrets:
                st.error("❌ Falta gdrive_folder_id en Secrets")
                st.stop()
            
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=["https://www.googleapis.com/auth/drive.readonly"]
            )
            
            service = build('drive', 'v3', credentials=credentials)
            folder_id = st.secrets["gdrive_folder_id"]
            
            data_dir = Path("/tmp/imdc_data")
            data_dir.mkdir(exist_ok=True)
            
            query = f"'{folder_id}' in parents and name contains '.parquet' and trashed=false"
            results = service.files().list(q=query, fields="files(id, name)").execute()
            files = results.get('files', [])
            
            if not files:
                st.error("❌ No hay archivos .parquet en Drive")
                st.stop()
            
            with st.spinner(f"📥 Descargando {len(files)} archivo(s)..."):
                for file in files:
                    file_path = data_dir / file['name']
                    
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
            
            os.environ["IMDC_DATA_DIR"] = str(data_dir)
            return True
            
        except Exception as e:
            st.error(f"❌ Error en Drive: {str(e)}")
            st.code(traceback.format_exc())
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
            st.error(f"❌ Error al cargar dashboard: {str(e)}")
            st.code(traceback.format_exc())

    if __name__ == "__main__":
        main()

except Exception as e:
    st.error(f"❌ ERROR CRÍTICO: {str(e)}")
    st.code(traceback.format_exc())
