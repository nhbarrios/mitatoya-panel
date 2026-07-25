import streamlit as st
from supabase import create_client
from datetime import date, datetime
import pandas as pd

st.set_page_config(page_title="MitaToya · Panel de administración", page_icon="🏝️", layout="wide")

# ============================================================
# CONEXIÓN A SUPABASE
# Estos valores se leen desde Streamlit Secrets, nunca los escribas aquí directamente.
# ============================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = st.secrets["SUPABASE_SERVICE_KEY"]  # clave privada, solo vive aquí
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ============================================================
# ACCESO CON CLAVE (para que no cualquiera entre a tu panel)
# ============================================================
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "cambia-esta-clave")

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🏝️ MitaToya — Panel de administración")
    clave = st.text_input("Clave de acceso", type="password")
    if st.button("Entrar"):
        if clave == ADMIN_PASSWORD:
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Clave incorrecta")
    st.stop()

st.title("🏝️ MitaToya — Panel de administración")
tab_reservas, tab_disponibilidad, tab_fotos = st.tabs(
    ["📋 Reservas", "📅 Disponibilidad", "🖼️ Fotos"]
)

# ============================================================
# TAB 1: RESERVAS
# ============================================================
with tab_reservas:
    st.subheader("Solicitudes de reserva recibidas desde el sitio")
    data = supabase.table("reservas").select("*").order("created_at", desc=True).execute()
    df = pd.DataFrame(data.data)

    if df.empty:
        st.info("Todavía no ha llegado ninguna reserva.")
    else:
        st.dataframe(df, use_container_width=True)
        st.markdown("### Cambiar el estado de una reserva")
        col1, col2, col3 = st.columns(3)
        reserva_id = col1.selectbox("Reserva (id)", df["id"].tolist())
        nuevo_estado = col2.selectbox("Nuevo estado", ["pendiente", "confirmada", "cancelada"])
        if col3.button("Actualizar estado", use_container_width=True):
            supabase.table("reservas").update({"estado": nuevo_estado}).eq("id", reserva_id).execute()
            st.success("Reserva actualizada.")
            st.rerun()

        st.caption(
            "Tip: cuando confirmes una reserva de renta de carro u hospedaje, "
            "recuerda ir a la pestaña **Disponibilidad** y bloquear esas fechas "
            "para que no se dupliquen."
        )

# ============================================================
# TAB 2: DISPONIBILIDAD (calendario de bloqueos)
# ============================================================
with tab_disponibilidad:
    st.subheader("Bloquear fechas no disponibles")
    st.caption("Esto es lo que tu sitio web consulta para saber qué fechas mostrar como ocupadas.")

    servicio = st.selectbox("Servicio", ["renta", "hospedaje"], key="servicio_bloqueo")
    habitacion = None
    if servicio == "hospedaje":
        habitacion = st.selectbox("Habitación", ["triple", "doble"], key="habitacion_bloqueo")

    col1, col2 = st.columns(2)
    fecha_inicio = col1.date_input("Desde", value=date.today())
    fecha_fin = col2.date_input("Hasta", value=date.today())
    motivo = st.text_input("Motivo (opcional)", value="Ocupado")

    if st.button("Bloquear estas fechas"):
        if fecha_fin < fecha_inicio:
            st.error("La fecha 'Hasta' no puede ser anterior a 'Desde'.")
        else:
            supabase.table("bloqueos").insert({
                "servicio": servicio,
                "habitacion": habitacion,
                "fecha_inicio": str(fecha_inicio),
                "fecha_fin": str(fecha_fin),
                "motivo": motivo
            }).execute()
            st.success("Fechas bloqueadas correctamente.")
            st.rerun()

    st.markdown("### Bloqueos actuales")
    bloqueos = supabase.table("bloqueos").select("*").order("fecha_inicio").execute()
    dfb = pd.DataFrame(bloqueos.data)

    if dfb.empty:
        st.info("No hay fechas bloqueadas todavía.")
    else:
        st.dataframe(dfb, use_container_width=True)
        eliminar_id = st.selectbox("Eliminar bloqueo (por id)", dfb["id"].tolist())
        if st.button("Eliminar bloqueo seleccionado"):
            supabase.table("bloqueos").delete().eq("id", eliminar_id).execute()
            st.success("Bloqueo eliminado.")
            st.rerun()

# ============================================================
# TAB 3: FOTOS
# ============================================================
with tab_fotos:
    st.subheader("Subir fotos")
    st.caption(
        "Requiere un bucket de Storage llamado 'fotos' en tu proyecto de Supabase, "
        "marcado como público (ver README)."
    )

    categoria = st.selectbox("¿Para qué sección es esta foto?", [
        "galeria", "habitacion_triple", "habitacion_doble"
    ])
    archivo = st.file_uploader("Selecciona una imagen", type=["jpg", "jpeg", "png"])

    if archivo and st.button("Subir foto"):
        nombre_archivo = f"{categoria}/{datetime.now().strftime('%Y%m%d%H%M%S')}_{archivo.name}"
        try:
            supabase.storage.from_("fotos").upload(nombre_archivo, archivo.getvalue())
            url = supabase.storage.from_("fotos").get_public_url(nombre_archivo)
            st.success("Foto subida correctamente.")
            st.image(url, width=320)
            st.code(url, language="text")
            st.caption("Copia este link si quieres usarlo directo en el index.html.")
        except Exception as e:
            st.error(f"No se pudo subir la foto: {e}")

    st.markdown("### Fotos ya subidas")
    try:
        archivos = supabase.storage.from_("fotos").list(categoria)
        if not archivos:
            st.info("Todavía no hay fotos en esta categoría.")
        else:
            cols = st.columns(4)
            for i, f in enumerate(archivos):
                ruta = f"{categoria}/{f['name']}"
                url = supabase.storage.from_("fotos").get_public_url(ruta)
                with cols[i % 4]:
                    st.image(url, use_container_width=True)
                    if st.button("🗑️ Eliminar", key=ruta):
                        supabase.storage.from_("fotos").remove([ruta])
                        st.rerun()
    except Exception as e:
        st.warning(f"No se pudo listar las fotos: {e}")
