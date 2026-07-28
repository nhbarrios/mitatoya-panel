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

def buscar_choques(servicio, habitacion, fecha_inicio, fecha_fin, excluir_reserva_id=None):
    """Devuelve una lista de conflictos (reservas confirmadas y bloqueos) que se
    cruzan con el rango de fechas dado, para el mismo servicio/habitación."""
    choques = []

    q_res = supabase.table("reservas").select("*").eq("servicio", servicio).in_("estado", ["confirmada", "completada"]) \
        .lte("fecha_inicio", str(fecha_fin)).gte("fecha_fin", str(fecha_inicio))
    if habitacion:
        q_res = q_res.eq("habitacion", habitacion)
    for r in q_res.execute().data:
        if excluir_reserva_id and r["id"] == excluir_reserva_id:
            continue
        choques.append(f"Reserva confirmada de {r['nombre']} ({r['fecha_inicio']} al {r['fecha_fin']})")

    q_bloq = supabase.table("bloqueos").select("*").eq("servicio", servicio) \
        .lte("fecha_inicio", str(fecha_fin)).gte("fecha_fin", str(fecha_inicio))
    if habitacion:
        q_bloq = q_bloq.eq("habitacion", habitacion)
    for b in q_bloq.execute().data:
        choques.append(f"Bloqueo manual: {b.get('motivo') or 'Ocupado'} ({b['fecha_inicio']} al {b['fecha_fin']})")

    return choques

tab_reservas, tab_facturacion, tab_disponibilidad, tab_fotos, tab_tarifas, tab_destinos = st.tabs(
    ["📋 Reservas", "🧾 Facturación", "📅 Disponibilidad", "🖼️ Fotos", "💲 Tarifas", "📍 Rincones"]
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
        nuevo_estado = col2.selectbox("Nuevo estado", ["pendiente", "confirmada", "cancelada", "completada"])
        if col3.button("Actualizar estado", use_container_width=True):
            fila = df[df["id"] == reserva_id].iloc[0]
            if nuevo_estado == "confirmada" and fila["servicio"] in ("renta", "hospedaje"):
                choques = buscar_choques(
                    fila["servicio"], fila.get("habitacion"),
                    fila["fecha_inicio"], fila["fecha_fin"], excluir_reserva_id=reserva_id
                )
                if choques:
                    st.session_state["choque_confirmacion_pendiente"] = {"id": reserva_id, "estado": nuevo_estado}
                    st.warning(
                        "⚠️ Esas fechas ya tienen algo registrado para este servicio:\n\n"
                        + "\n".join(f"- {c}" for c in choques)
                    )
                else:
                    supabase.table("reservas").update({"estado": nuevo_estado}).eq("id", reserva_id).execute()
                    st.success("Reserva actualizada.")
                    st.rerun()
            else:
                supabase.table("reservas").update({"estado": nuevo_estado}).eq("id", reserva_id).execute()
                st.success("Reserva actualizada.")
                st.rerun()

        if st.session_state.get("choque_confirmacion_pendiente"):
            if st.button("Confirmar de todos modos (ya lo revisé)"):
                p = st.session_state["choque_confirmacion_pendiente"]
                supabase.table("reservas").update({"estado": p["estado"]}).eq("id", p["id"]).execute()
                del st.session_state["choque_confirmacion_pendiente"]
                st.success("Reserva actualizada.")
                st.rerun()

        st.caption(
            "Tip: cuando confirmes una reserva de renta de carro u hospedaje, "
            "recuerda ir a la pestaña **Disponibilidad** y bloquear esas fechas "
            "para que no se dupliquen."
        )

        st.divider()
        st.markdown("### Agregar un cargo extra (daño, servicio fuera de lo pactado, etc.)")
        st.caption(
            "Esto es para ajustes que surgen DESPUÉS de la reserva — por ejemplo, un daño al "
            "vehículo o una parada extra que el cliente pidió. No afecta el total original, "
            "queda registrado aparte."
        )
        col_e1, col_e2, col_e3 = st.columns([1, 1, 2])
        reserva_id_extra = col_e1.selectbox("Reserva (id)", df["id"].tolist(), key="reserva_extra")
        monto_extra = col_e2.number_input("Monto extra (USD)", min_value=0.0, step=1.0, key="monto_extra")
        motivo_extra = col_e3.text_input("Motivo", placeholder="Ej: daño en la puerta trasera", key="motivo_extra")
        if st.button("➕ Aplicar cargo extra"):
            supabase.table("reservas").update({
                "cargos_extra": monto_extra, "motivo_cargos_extra": motivo_extra
            }).eq("id", reserva_id_extra).execute()
            st.success("Cargo extra aplicado — ya aparece en la tabla de reservas de arriba.")
            st.rerun()

# ============================================================
# TAB: FACTURACIÓN (cerrar un servicio ya confirmado)
# ============================================================
with tab_facturacion:
    st.subheader("🧾 Facturar y cerrar un servicio")
    st.caption(
        "Elige una reserva ya CONFIRMADA, agrega cargos extra si los hubo, y genera el "
        "comprobante final (PDF o texto para WhatsApp). Al cerrarla, la reserva pasa a "
        "'completada' y deja de aparecer en esta lista."
    )

    data_conf = supabase.table("reservas").select("*").eq("estado", "confirmada") \
        .order("fecha_inicio").execute()
    df_conf = pd.DataFrame(data_conf.data)

    if df_conf.empty:
        st.info("No hay reservas confirmadas pendientes de facturar en este momento.")
    else:
        etiquetas_reserva = {
            r["id"]: f'#{r["id"]} · {r["nombre"]} · {r["servicio"]}'
                      f'{" (" + r["habitacion"] + ")" if r.get("habitacion") else ""}'
                      f' · {r["fecha_inicio"]} → {r["fecha_fin"]}'
            for r in df_conf.to_dict("records")
        }
        reserva_id_fact = st.selectbox(
            "Reserva confirmada a facturar",
            list(etiquetas_reserva.keys()),
            format_func=lambda i: etiquetas_reserva[i],
            key="reserva_facturar"
        )
        r = df_conf[df_conf["id"] == reserva_id_fact].iloc[0]

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**Cliente:** {r['nombre']}")
            st.markdown(f"**Cédula/Pasaporte:** {r.get('documento') or '—'}")
            st.markdown(f"**WhatsApp:** {r.get('telefono') or '—'}")
            servicio_txt = r['servicio'] + (f" — {r['habitacion']}" if r.get('habitacion') else "")
            st.markdown(f"**Servicio:** {servicio_txt}")
        with col_b:
            st.markdown(f"**Fechas:** {r['fecha_inicio']} → {r['fecha_fin']}")
            st.markdown(
                f"**Personas:** {r.get('cantidad', 1)} · "
                f"Niños: {r.get('ninos', 0)} · Mascotas: {r.get('mascotas', 0)}"
            )
            st.markdown(f"**Total original:** ${float(r.get('total') or 0):.2f}")
            st.markdown(f"**Depósito ya registrado:** ${float(r.get('deposito') or 0):.2f}")

        st.divider()
        st.markdown("### Cargos extra (daños, servicios fuera de lo pactado, etc.)")
        cargo_extra_actual = float(r.get("cargos_extra") or 0)
        motivo_extra_actual = r.get("motivo_cargos_extra") or ""

        col_c1, col_c2 = st.columns([1, 2])
        nuevo_cargo_extra = col_c1.number_input(
            "Monto total de cargos extra (USD)", min_value=0.0, step=1.0,
            value=cargo_extra_actual, key="fact_cargo_extra"
        )
        nuevo_motivo_extra = col_c2.text_input(
            "Motivo", value=motivo_extra_actual, placeholder="Ej: daño en la puerta trasera",
            key="fact_motivo_extra"
        )

        total_original = float(r.get("total") or 0)
        deposito_pagado = float(r.get("deposito") or 0)
        total_final = total_original + nuevo_cargo_extra
        saldo_final = total_final - deposito_pagado

        st.divider()
        st.markdown("### Resumen del comprobante")
        col_r1, col_r2, col_r3 = st.columns(3)
        col_r1.metric("Total del servicio", f"${total_final:.2f}")
        col_r2.metric("Depósito ya pagado", f"${deposito_pagado:.2f}")
        col_r3.metric("Saldo a cobrar", f"${saldo_final:.2f}")

        fecha_comprobante = datetime.now().strftime("%d/%m/%Y %H:%M")
        extra_linea = "Cargos extra"
        if nuevo_motivo_extra:
            extra_linea += f" ({nuevo_motivo_extra})"
        texto_comprobante = f"""COMPROBANTE DE SERVICIO — MitaToya Tours & Taxi Ometepe
Fecha de emisión: {fecha_comprobante}
Reserva #{int(r['id'])}

Cliente: {r['nombre']}
Cédula/Pasaporte: {r.get('documento') or '—'}
WhatsApp: {r.get('telefono') or '—'}

Servicio: {servicio_txt}
Fechas: {r['fecha_inicio']} al {r['fecha_fin']}
Personas: {r.get('cantidad', 1)}   Niños: {r.get('ninos', 0)}   Mascotas: {r.get('mascotas', 0)}

Total del servicio:       ${total_original:.2f}
{extra_linea}: ${nuevo_cargo_extra:.2f}
--------------------------------------------
TOTAL FINAL:               ${total_final:.2f}
Depósito ya pagado:       -${deposito_pagado:.2f}
--------------------------------------------
SALDO A COBRAR:            ${saldo_final:.2f}

¡Gracias por viajar con nosotros!
"""
        st.text_area(
            "Texto del comprobante (para copiar y enviar por WhatsApp)",
            texto_comprobante, height=320, key="fact_texto"
        )

        # --- PDF ---
        pdf_bytes = None
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, "MitaToya Tours & Taxi Ometepe", ln=True)
            pdf.set_font("Helvetica", "", 11)
            pdf.cell(0, 8, "Comprobante de servicio", ln=True)
            pdf.cell(0, 8, f"Emitido: {fecha_comprobante}    Reserva #{int(r['id'])}", ln=True)
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Datos del cliente", ln=True)
            pdf.set_font("Helvetica", "", 11)
            pdf.cell(0, 7, f"Nombre: {r['nombre']}", ln=True)
            pdf.cell(0, 7, f"Cedula/Pasaporte: {r.get('documento') or '-'}", ln=True)
            pdf.cell(0, 7, f"WhatsApp: {r.get('telefono') or '-'}", ln=True)
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Servicio", ln=True)
            pdf.set_font("Helvetica", "", 11)
            pdf.cell(0, 7, f"Tipo: {servicio_txt}", ln=True)
            pdf.cell(0, 7, f"Fechas: {r['fecha_inicio']} al {r['fecha_fin']}", ln=True)
            pdf.cell(
                0, 7,
                f"Personas: {r.get('cantidad', 1)}   Ninos: {r.get('ninos', 0)}   "
                f"Mascotas: {r.get('mascotas', 0)}", ln=True
            )
            pdf.ln(6)
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Totales", ln=True)
            pdf.set_font("Helvetica", "", 11)
            pdf.cell(0, 7, f"Total del servicio: ${total_original:.2f}", ln=True)
            pdf.cell(0, 7, f"{extra_linea}: ${nuevo_cargo_extra:.2f}", ln=True)
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, f"TOTAL FINAL: ${total_final:.2f}", ln=True)
            pdf.set_font("Helvetica", "", 11)
            pdf.cell(0, 7, f"Deposito ya pagado: -${deposito_pagado:.2f}", ln=True)
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, f"SALDO A COBRAR: ${saldo_final:.2f}", ln=True)
            pdf_bytes = bytes(pdf.output())
        except ImportError:
            st.warning(
                "Para descargar el comprobante en PDF, agrega `fpdf2` a tu requirements.txt "
                "(`pip install fpdf2`) y reinicia la app. Mientras tanto, usa el texto de arriba "
                "para enviarlo por WhatsApp."
            )

        col_d1, col_d2 = st.columns(2)
        if pdf_bytes:
            col_d1.download_button(
                "⬇️ Descargar comprobante (PDF)", data=pdf_bytes,
                file_name=f"comprobante_reserva_{int(r['id'])}.pdf", mime="application/pdf",
                use_container_width=True
            )
        tel_limpio = "".join(ch for ch in str(r.get("telefono") or "") if ch.isdigit())
        if tel_limpio:
            from urllib.parse import quote
            wa_link = f"https://wa.me/{tel_limpio}?text={quote(texto_comprobante)}"
            col_d2.link_button("💬 Enviar por WhatsApp", wa_link, use_container_width=True)

        st.divider()
        st.markdown("### Cerrar este servicio")
        st.caption(
            "Al cerrar, se guardan los cargos extra de arriba y la reserva pasa a 'completada' "
            "— ya no aparecerá como pendiente de facturar."
        )
        if st.button("✅ Guardar cargos y marcar servicio como completado", use_container_width=True):
            supabase.table("reservas").update({
                "cargos_extra": nuevo_cargo_extra,
                "motivo_cargos_extra": nuevo_motivo_extra,
                "estado": "completada"
            }).eq("id", reserva_id_fact).execute()
            st.success("Servicio cerrado y comprobante listo. La reserva ahora aparece como 'completada'.")
            st.rerun()

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
    reservas_cal = supabase.table("reservas").select("*").in_("estado", ["confirmada", "completada"]) \
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
            choques = buscar_choques(servicio, habitacion, fecha_inicio, fecha_fin)
            if choques:
                st.session_state["choques_bloqueo_pendiente"] = {
                    "servicio": servicio, "habitacion": habitacion,
                    "fecha_inicio": str(fecha_inicio), "fecha_fin": str(fecha_fin), "motivo": motivo
                }
                st.warning(
                    "⚠️ Estas fechas ya tienen algo registrado para este servicio:\n\n"
                    + "\n".join(f"- {c}" for c in choques)
                )
            else:
                supabase.table("bloqueos").insert({
                    "servicio": servicio, "habitacion": habitacion,
                    "fecha_inicio": str(fecha_inicio), "fecha_fin": str(fecha_fin), "motivo": motivo
                }).execute()
                st.success("Fechas bloqueadas correctamente.")
                st.rerun()

    if st.session_state.get("choques_bloqueo_pendiente"):
        if st.button("Bloquear de todos modos (ya lo revisé)"):
            p = st.session_state["choques_bloqueo_pendiente"]
            supabase.table("bloqueos").insert(p).execute()
            del st.session_state["choques_bloqueo_pendiente"]
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
        "tarifa_nino": "Cargo extra por niño (USD)",
        "tarifa_mascota": "Cargo extra por mascota (USD)",
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
