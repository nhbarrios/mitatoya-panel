import streamlit as st
from supabase import create_client
from datetime import date, datetime, timedelta
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
tab_reservas, tab_disponibilidad, tab_fotos, tab_tarifas, tab_destinos = st.tabs(
    ["📋 Reservas", "📅 Disponibilidad", "🖼️ Fotos", "💲 Tarifas", "📍 Rincones"]
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
    st.subheader("📅 Vista de calendario")
    st.caption("De un vistazo: qué está libre, reservado o bloqueado por cada servicio.")

    RECURSOS = [
        {"etiqueta": "🚗 Renta de carro", "servicio": "renta", "habitacion": None},
        {"etiqueta": "🛏️ Habitación Triple", "servicio": "hospedaje", "habitacion": "triple"},
        {"etiqueta": "🛏️ Habitación Doble", "servicio": "hospedaje", "habitacion": "doble"},
    ]

    col_cal1, col_cal2 = st.columns(2)
    cal_desde = col_cal1.date_input("Ver desde", value=date.today(), key="cal_desde")
    cal_dias = col_cal2.slider("Cuántos días mostrar", min_value=7, max_value=30, value=14, key="cal_dias")
    cal_hasta = cal_desde + timedelta(days=cal_dias - 1)

    rango_fechas = [cal_desde + timedelta(days=i) for i in range(cal_dias)]
    columnas_fecha = [f.strftime("%a %d/%m") for f in rango_fechas]
    mapa_columna_fecha = dict(zip(columnas_fecha, rango_fechas))

    df_cal = pd.DataFrame("🟢 Libre", index=[r["etiqueta"] for r in RECURSOS], columns=columnas_fecha)

    # Bloqueos manuales
    bloqueos_cal = supabase.table("bloqueos").select("*") \
        .lte("fecha_inicio", str(cal_hasta)).gte("fecha_fin", str(cal_desde)).execute().data
    for b in bloqueos_cal:
        for r in RECURSOS:
            if b["servicio"] == r["servicio"] and (b.get("habitacion") == r["habitacion"]):
                for col, f in mapa_columna_fecha.items():
                    if str(b["fecha_inicio"]) <= str(f) <= str(b["fecha_fin"]):
                        df_cal.at[r["etiqueta"], col] = f"🔒 {b.get('motivo') or 'Bloqueado'}"

    # Reservas confirmadas
    reservas_cal = supabase.table("reservas").select("*").eq("estado", "confirmada") \
        .lte("fecha_inicio", str(cal_hasta)).gte("fecha_fin", str(cal_desde)).execute().data
    for res in reservas_cal:
        for r in RECURSOS:
            if res["servicio"] == r["servicio"] and (res.get("habitacion") == r["habitacion"]):
                nombre_corto = (res.get("nombre") or "Reserva").split()[0]
                for col, f in mapa_columna_fecha.items():
                    f_str = str(f)
                    if f_str == str(res["fecha_inicio"]):
                        df_cal.at[r["etiqueta"], col] = f"🛬 {nombre_corto}"
                    elif f_str == str(res["fecha_fin"]):
                        actual = df_cal.at[r["etiqueta"], col]
                        df_cal.at[r["etiqueta"], col] = f"🔄 {nombre_corto}" if "🛬" in actual else f"🛫 {nombre_corto}"
                    elif str(res["fecha_inicio"]) < f_str < str(res["fecha_fin"]):
                        df_cal.at[r["etiqueta"], col] = f"🔴 {nombre_corto}"

    def _color_celda(val):
        if "🟢" in val: return "background-color:#e8f5e9;color:#2e7d32;"
        if "🔴" in val: return "background-color:#fff9c4;color:#b71c1c;"
        if "🛬" in val: return "background-color:#e3f2fd;color:#0d47a1;font-weight:bold;"
        if "🛫" in val: return "background-color:#fce4ec;color:#880e4f;font-weight:bold;"
        if "🔄" in val: return "background-color:#f3e5f5;color:#4a148c;"
        if "🔒" in val: return "background-color:#eeeeee;color:#424242;"
        return ""

    st.dataframe(df_cal.style.map(_color_celda), use_container_width=True)
    st.caption("🟢 Libre · 🛬 Entra · 🛫 Sale · 🔄 Sale y entra el mismo día · 🔴 Ocupado · 🔒 Bloqueado manualmente")

    st.divider()
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
        "marcado como público, y la tabla 'fotos_galeria' (ver README)."
    )

    RINCONES_BASE = {
        "destino-ojo-de-agua": "Rincón: Ojo de Agua",
        "destino-charco-verde": "Rincón: Charco Verde",
        "destino-cascada-san-ramon": "Rincón: Cascada San Ramón",
        "destino-volcan-concepcion": "Rincón: Volcán Concepción",
        "destino-volcan-maderas": "Rincón: Volcán Maderas",
        "destino-rio-istian": "Rincón: Río Istián",
        "destino-el-pital": "Rincón: El Pital",
        "destino-punta-jesus-maria": "Rincón: Punta Jesús María",
        "destino-santo-domingo": "Rincón: Santo Domingo",
        "destino-santa-cruz": "Rincón: Santa Cruz",
        "destino-balgue": "Rincón: Balgüe",
    }
    try:
        destinos_custom = supabase.table("destinos").select("categoria_fotos, titulo").execute().data
        for d in destinos_custom:
            RINCONES_BASE[d["categoria_fotos"]] = f"Rincón: {d['titulo']}"
    except Exception:
        pass

    opciones_categoria = ["galeria", "habitacion_triple", "habitacion_doble"] + list(RINCONES_BASE.keys())
    etiquetas_categoria = {**{"galeria": "Galería general", "habitacion_triple": "Habitación Triple", "habitacion_doble": "Habitación Doble"}, **RINCONES_BASE}

    categoria = st.selectbox(
        "¿Para qué sección es esta foto?",
        opciones_categoria,
        format_func=lambda c: etiquetas_categoria.get(c, c)
    )
    archivo = st.file_uploader("Selecciona una imagen", type=["jpg", "jpeg", "png"])

    if archivo and st.button("Subir foto"):
        nombre_archivo = f"{categoria}/{datetime.now().strftime('%Y%m%d%H%M%S')}_{archivo.name}"
        try:
            supabase.storage.from_("fotos").upload(nombre_archivo, archivo.getvalue())
            url = supabase.storage.from_("fotos").get_public_url(nombre_archivo)
            supabase.table("fotos_galeria").insert({
                "categoria": categoria, "url": url, "ruta_storage": nombre_archivo
            }).execute()
            st.success("Foto subida — ya debería aparecer en tu sitio web.")
            st.image(url, width=320)
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
                        supabase.table("fotos_galeria").delete().eq("ruta_storage", ruta).execute()
                        st.rerun()
    except Exception as e:
        st.warning(f"No se pudo listar las fotos: {e}")

    st.divider()
    st.caption(
        "¿Subiste fotos ANTES de tener esta pestaña actualizada y no te aparecen "
        "en el sitio? Dale clic aquí para ponerlas al día."
    )
    if st.button("🔄 Sincronizar fotos existentes con el sitio web"):
        try:
            archivos_sync = supabase.storage.from_("fotos").list(categoria)
            total = 0
            for f in archivos_sync:
                ruta = f"{categoria}/{f['name']}"
                url = supabase.storage.from_("fotos").get_public_url(ruta)
                supabase.table("fotos_galeria").upsert(
                    {"categoria": categoria, "url": url, "ruta_storage": ruta},
                    on_conflict="ruta_storage"
                ).execute()
                total += 1
            st.success(f"Listo — {total} foto(s) de '{categoria}' sincronizadas.")
        except Exception as e:
            st.error(f"No se pudo sincronizar: {e}")

# ============================================================
# TAB 4: TARIFAS
# ============================================================
with tab_tarifas:
    st.subheader("Precios y condiciones de reserva")
    st.caption(
        "Estos son los valores que tu sitio web usa para calcular el total y el "
        "depósito. Cambia lo que necesites y dale 'Guardar cambios' — se actualiza "
        "en tu sitio al instante, sin tocar código."
    )

    ETIQUETAS = {
        "traslado": "Traslado privado (USD, precio fijo por viaje)",
        "tour": "Tour guiado (USD, por persona)",
        "grupo": "Transporte para grupos (USD, tarifa base)",
        "renta": "Renta de carro (USD, por día)",
        "hospedaje_triple": "Habitación Triple (USD, por noche)",
        "hospedaje_doble": "Habitación Doble (USD, por noche)",
        "deposito_porcentaje": "Porcentaje de depósito (%)",
        "tipo_cambio": "Tipo de cambio (córdobas por 1 USD)",
    }

    precios_data = supabase.table("precios").select("*").execute()
    precios_actuales = {p["clave"]: p["valor"] for p in precios_data.data}

    if not precios_actuales:
        st.warning(
            "No encontré la tabla de precios. Corre el archivo "
            "`supabase_schema_precios.sql` en el SQL Editor de Supabase primero."
        )
    else:
        nuevos_valores = {}
        for clave, etiqueta in ETIQUETAS.items():
            valor_actual = precios_actuales.get(clave, 0)
            nuevos_valores[clave] = st.number_input(
                etiqueta, min_value=0.0, value=float(valor_actual), step=0.5, key=f"precio_{clave}"
            )

        if st.button("💾 Guardar cambios", use_container_width=True):
            for clave, valor in nuevos_valores.items():
                supabase.table("precios").upsert({"clave": clave, "valor": valor}).execute()
            st.success("Tarifas actualizadas. Tu sitio ya las va a usar la próxima vez que alguien lo cargue.")
            st.rerun()

# ============================================================
# TAB 5: RINCONES (destinos nuevos)
# ============================================================
with tab_destinos:
    st.subheader("Agregar un rincón nuevo")
    st.caption(
        "Los 11 rincones que ya tenías (Ojo de Agua, Charco Verde, etc.) siguen tal cual en la "
        "página. Aquí agregas rincones ADICIONALES — se muestran después de esos 11."
    )

    import re as _re

    def _slug(texto):
        s = texto.strip().lower()
        s = (s.replace("á", "a").replace("é", "e").replace("í", "i")
               .replace("ó", "o").replace("ú", "u").replace("ñ", "n").replace("ü", "u"))
        s = _re.sub(r"[^a-z0-9\s-]", "", s)
        s = _re.sub(r"\s+", "-", s).strip("-")
        return f"destino-{s}"

    titulo_nuevo = st.text_input("Nombre del rincón", placeholder="Ej: Mirador La Vigía")
    descripcion_nueva = st.text_area("Descripción corta", placeholder="Una o dos frases sobre este lugar")
    fotos_nuevas = st.file_uploader(
        "Fotos de este rincón (puedes subir 1 o 2)", type=["jpg", "jpeg", "png"], accept_multiple_files=True
    )

    if st.button("➕ Agregar rincón"):
        if not titulo_nuevo:
            st.error("Ponle un nombre al rincón primero.")
        else:
            categoria_nueva = _slug(titulo_nuevo)
            try:
                orden_actual = supabase.table("destinos").select("orden").order("orden", desc=True).limit(1).execute()
                siguiente_orden = (orden_actual.data[0]["orden"] + 1) if orden_actual.data else 1

                supabase.table("destinos").insert({
                    "titulo": titulo_nuevo, "descripcion": descripcion_nueva,
                    "categoria_fotos": categoria_nueva, "orden": siguiente_orden
                }).execute()

                for foto in (fotos_nuevas or []):
                    nombre_archivo = f"{categoria_nueva}/{datetime.now().strftime('%Y%m%d%H%M%S')}_{foto.name}"
                    supabase.storage.from_("fotos").upload(nombre_archivo, foto.getvalue())
                    url = supabase.storage.from_("fotos").get_public_url(nombre_archivo)
                    supabase.table("fotos_galeria").insert({
                        "categoria": categoria_nueva, "url": url, "ruta_storage": nombre_archivo
                    }).execute()

                st.success(f"'{titulo_nuevo}' agregado — ya debería aparecer en tu sitio.")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo agregar el rincón: {e}")

    st.divider()
    st.markdown("### Rincones agregados desde aquí")
    try:
        destinos_data = supabase.table("destinos").select("*").order("orden").execute()
        if not destinos_data.data:
            st.info("Todavía no has agregado ningún rincón adicional.")
        else:
            for d in destinos_data.data:
                col1, col2 = st.columns([5, 1])
                col1.write(f"**{d['titulo']}** — {d.get('descripcion', '')}")
                if col2.button("🗑️ Borrar", key=f"del-destino-{d['id']}"):
                    supabase.table("destinos").delete().eq("id", d["id"]).execute()
                    st.rerun()
    except Exception as e:
        st.warning(f"No se pudo cargar la lista: {e}")
