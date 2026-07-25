# MitaToya — Panel de administración (backend)

Este proyecto te da un panel privado (hecho con Streamlit) para:
- Ver las reservas que llegan desde tu sitio web
- Bloquear/desbloquear fechas de renta de carro y de las habitaciones
- Subir y borrar fotos de la galería

Tu `index.html` (el sitio público) va a consultar directamente la base de
datos de Supabase para saber qué fechas mostrar como no disponibles — no
necesita pasar por Streamlit.

## Paso 1 — Crear el proyecto en Supabase (gratis)

1. Entra a https://supabase.com y crea una cuenta.
2. Crea un **New project**. Elige una contraseña de base de datos y guárdala.
3. Ve a **SQL Editor > New query**, pega todo el contenido de `supabase_schema.sql`
   de esta carpeta, y dale **Run**. Esto crea las tablas `reservas` y `bloqueos`.
4. Ve a **Storage** y crea un bucket llamado `fotos`, márcalo como **Public bucket**.
5. Ve a **Project Settings > API**. Ahí vas a ver dos claves:
   - **`anon` `public`** → esta es la que va a ir *dentro de tu `index.html`* (es segura de exponer, solo permite insertar reservas y leer bloqueos, según las reglas del SQL).
   - **`service_role`** → esta es **secreta**, solo va en el panel de Streamlit. Nunca la pongas en el sitio web público.
   - También copia la **Project URL** (algo como `https://xxxx.supabase.co`).

## Paso 2 — Subir este proyecto a GitHub

1. Crea un repositorio nuevo en GitHub (puede ser privado).
2. Sube estos archivos: `streamlit_app.py`, `requirements.txt`, `supabase_schema.sql`, este `README.md`.
3. **No subas** `.streamlit/secrets.toml` con tus claves reales — solo el `.example` que te dejé de referencia.

## Paso 3 — Desplegar el panel en Streamlit Community Cloud (gratis)

1. Entra a https://streamlit.io/cloud y conéctalo con tu cuenta de GitHub.
2. Elige **New app**, selecciona tu repositorio y el archivo `streamlit_app.py`.
3. Antes de darle Deploy, ve a **Advanced settings > Secrets** y pega:
   ```
   SUPABASE_URL = "https://xxxx.supabase.co"
   SUPABASE_SERVICE_KEY = "tu-clave-service_role"
   ADMIN_PASSWORD = "elige-una-clave-segura"
   ```
4. Dale **Deploy**. En un par de minutos tienes tu panel en una URL tipo
   `https://tu-app.streamlit.app`, protegido con la clave que elegiste.

## Paso 4 — Conectar tu `index.html` a Supabase

En tu sitio web, busca (o pide que se agregue) el bloque con:
```javascript
const SUPABASE_URL = "PON-AQUI-TU-URL";
const SUPABASE_ANON_KEY = "PON-AQUI-TU-CLAVE-ANON-PUBLICA";
```
Reemplaza esos dos valores por los que copiaste en el Paso 1 (la clave **anon**,
no la service_role). Con eso, tu sitio ya puede:
- Consultar qué fechas están bloqueadas antes de dejar reservar
- Guardar cada solicitud de reserva directo en la tabla `reservas`

## Cómo se usa día a día

- Cuando llega una reserva por el sitio, la ves en la pestaña **Reservas** del panel.
- Cuando la confirmas con el cliente (por WhatsApp, como ya haces), cambias su
  estado a "confirmada" y vas a la pestaña **Disponibilidad** para bloquear esas
  fechas — así el sitio deja de ofrecerlas a otros clientes.
- Subes fotos nuevas desde la pestaña **Fotos**, sin tocar código.
