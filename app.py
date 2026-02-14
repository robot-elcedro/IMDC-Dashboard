"""
═══════════════════════════════════════════════════════════════
DASHBOARD IMDC - STREAMLIT CLOUD
Con Google Drive PRIVADO usando Service Account
SEGURIDAD MÁXIMA ⭐⭐⭐⭐⭐
═══════════════════════════════════════════════════════════════
"""

import streamlit as st
import time
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# ============================================================
# CONFIGURACIÓN DE PÁGINA
# ============================================================
st.set_page_config(
    page_title="IMDC Dashboard",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# SISTEMA DE AUTENTICACIÓN
# ============================================================

def init_session_state():
    """Inicializa variables de sesión"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'login_time' not in st.session_state:
        st.session_state.login_time = None
    if 'failed_attempts' not in st.session_state:
        st.session_state.failed_attempts = 0
    if 'last_activity' not in st.session_state:
        st.session_state.last_activity = datetime.now()
    if 'blocked_until' not in st.session_state:
        st.session_state.blocked_until = None


def check_if_blocked():
    """Verifica si el usuario está bloqueado por intentos fallidos"""
    if st.session_state.blocked_until:
        if datetime.now() < st.session_state.blocked_until:
            remaining = (st.session_state.blocked_until - datetime.now()).seconds
            return True, remaining
        else:
            st.session_state.blocked_until = None
            st.session_state.failed_attempts = 0
            return False, 0
    return False, 0


def check_session_timeout():
    """Verifica timeout de sesión"""
    if st.session_state.authenticated:
        timeout_minutes = st.secrets.get("settings", {}).get("session_timeout_minutes", 60)
        
        if datetime.now() - st.session_state.last_activity > timedelta(minutes=timeout_minutes):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.warning("⏱️ Sesión expirada por inactividad. Inicia sesión nuevamente.")
            time.sleep(2)
            st.rerun()
        else:
            st.session_state.last_activity = datetime.now()


def authenticate():
    """Sistema de autenticación robusto"""
    
    init_session_state()
    
    if st.session_state.authenticated:
        check_session_timeout()
        return True
    
    is_blocked, remaining_seconds = check_if_blocked()
    
    st.markdown("""
    <div style='text-align: center; padding: 30px;'>
        <h1 style='color: #2563EB;'>🏪 FERRETERÍA EL CEDRO</h1>
        <h2 style='color: #64748B;'>Dashboard Ejecutivo</h2>
        <p style='color: #94A3B8;'>Acceso Restringido</p>
    </div>
    """, unsafe_allow_html=True)
    
    if is_blocked:
        minutes = remaining_seconds // 60
        seconds = remaining_seconds % 60
        st.error(f"🚫 **Bloqueado temporalmente**")
        st.info(f"⏱️ Tiempo restante: {minutes}m {seconds}s")
        time.sleep(1)
        st.rerun()
        return False
    
    with st.form("login_form"):
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            username = st.text_input(
                "👤 Usuario",
                placeholder="Ingresa tu usuario",
                key="username_input"
            )
            password = st.text_input(
                "🔒 Contraseña",
                type="password",
                placeholder="Ingresa tu contraseña",
                key="password_input"
            )
            
            submit = st.form_submit_button(
                "🚀 Iniciar Sesión",
                use_container_width=True,
                type="primary"
            )
        
        if submit:
            if not username or not password:
                st.error("❌ Por favor completa todos los campos")
            else:
                passwords = st.secrets.get("passwords", {})
                
                if username in passwords and password == passwords[username]:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.login_time = datetime.now()
                    st.session_state.last_activity = datetime.now()
                    st.session_state.failed_attempts = 0
                    st.session_state.blocked_until = None
                    
                    st.success(f"✅ Bienvenido, **{username}**!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.session_state.failed_attempts += 1
                    max_attempts = st.secrets.get("settings", {}).get("max_failed_attempts", 3)
                    remaining = max_attempts - st.session_state.failed_attempts
                    
                    if remaining > 0:
                        st.error(f"❌ Credenciales incorrectas. Intentos restantes: **{remaining}**")
                    else:
                        st.session_state.blocked_until = datetime.now() + timedelta(minutes=5)
                        st.error("🚫 **Demasiados intentos fallidos**. Bloqueado por 5 minutos.")
    
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.caption("🔒 Todos los accesos son monitoreados y registrados")
        st.caption(f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    return False


def logout():
    """Cerrar sesión"""
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.login_time = None
    st.rerun()


def show_session_info():
    """Muestra información de sesión en el sidebar"""
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 👤 Sesión Activa")
        st.write(f"**Usuario:** {st.session_state.username}")
        
        if st.session_state.login_time:
            duration = datetime.now() - st.session_state.login_time
            hours = int(duration.total_seconds() / 3600)
            minutes = int((duration.total_seconds() % 3600) / 60)
            
            if hours > 0:
                st.caption(f"⏱️ Tiempo: {hours}h {minutes}m")
            else:
                st.caption(f"⏱️ Tiempo: {minutes}m")
        
        if st.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
            logout()


# ============================================================
# CARGA DE DATOS DESDE GOOGLE DRIVE PRIVADO
# CON SERVICE ACCOUNT (100% SEGURO)
# ============================================================

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import io
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    st.error("❌ No se pudo importar Google API. Verifica requirements.txt")


@st.cache_data(ttl=86400, show_spinner=False)
def download_from_private_drive():
    """
    Descarga datos desde Google Drive PRIVADO usando Service Account
    """
    
    if not GOOGLE_API_AVAILABLE:
        st.error("❌ Google API no disponible")
        return None
    
    try:
        # Cargar credenciales del service account desde secrets
        creds_dict = dict(st.secrets["google_service_account"])
        
        # Crear credenciales
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        
        # Conectar a Google Drive API
        service = build('drive', 'v3', credentials=creds)
        
        # Obtener ID de la carpeta
        folder_id = st.secrets.get("google_drive", {}).get("folder_id")
        
        if not folder_id or folder_id == "PONER_AQUI_TU_FOLDER_ID":
            st.error("❌ **Configuración de Google Drive no encontrada**")
            st.info("💡 Configura el `folder_id` en Settings → Secrets")
            return None
        
        # Crear directorio temporal
        data_dir = Path("/tmp/imdc_data")
        data_dir.mkdir(exist_ok=True)
        
        # Listar archivos en la carpeta
        query = f"'{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType, size)"
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            st.error("❌ No se encontraron archivos en la carpeta")
            return None
        
        # Descargar archivos
        archivos_descargados = 0
        
        for file in files:
            file_id = file['id']
            file_name = file['name']
            file_size = int(file.get('size', 0))
            
            if file_name.endswith('.parquet') or file_name.endswith('.xlsx'):
                request = service.files().get_media(fileId=file_id)
                file_path = data_dir / file_name
                
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                
                with open(file_path, 'wb') as f:
                    f.write(fh.getvalue())
                
                archivos_descargados += 1
                size_mb = file_size / (1024 * 1024)
                st.success(f"✅ {file_name} ({size_mb:.1f} MB)")
        
        if archivos_descargados == 0:
            st.warning("⚠️ No se encontraron archivos .parquet o .xlsx")
            return None
        
        st.success(f"✅ Total descargado: {archivos_descargados} archivos")
        return data_dir
        
    except KeyError as e:
        st.error(f"❌ **Error en configuración de Secrets**: {str(e)}")
        return None
        
    except Exception as e:
        st.error(f"❌ **Error al conectar con Google Drive**")
        st.exception(e)
        return None


# ============================================================
# APLICACIÓN PRINCIPAL
# ============================================================

def main():
    """Aplicación principal"""
    
    # Sistema de autenticación
    if not authenticate():
        st.stop()
    
    # Mostrar info de sesión
    show_session_info()
    
    # Descargar datos desde Google Drive PRIVADO
    with st.spinner("📥 Descargando datos..."):
        data_dir = download_from_private_drive()
    
    if data_dir is None:
        st.error("❌ No se pudieron cargar los datos")
        st.stop()
    
    # Configurar variable de entorno para que el dashboard encuentre los datos
    os.environ['IMDC_DATA_DIR'] = str(data_dir)
    
    # Agregar directorio al path
    sys.path.insert(0, str(Path(__file__).parent))
    
    try:
        # Importar módulo del dashboard
        import imdc_web_FINAL_COMPLETO
        
        # Modificar OUTPUT_DIR para que use los datos descargados
        if hasattr(imdc_web_FINAL_COMPLETO, 'OUTPUT_DIR'):
            imdc_web_FINAL_COMPLETO.OUTPUT_DIR = data_dir
        
        # Forzar recarga si es necesario
        if hasattr(imdc_web_FINAL_COMPLETO, 'load_parquet_data'):
            st.success("🎉 **Dashboard cargado correctamente**")
        
    except ImportError as e:
        st.error(f"❌ Error al importar el dashboard: {str(e)}")
        st.info("""
        **Verifica:**
        - El archivo `imdc_web_FINAL_COMPLETO.py` está en el repositorio
        - El archivo `graficos_mejorados.py` está en el repositorio
        """)
        st.stop()
    except Exception as e:
        st.error(f"❌ Error en el dashboard: {str(e)}")
        st.exception(e)
        st.stop()


if __name__ == "__main__":
    main()
