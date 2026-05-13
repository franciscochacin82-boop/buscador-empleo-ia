"""
Buscador de Empleo con IA — para profesionales de comunicaciones y marketing
"""
import streamlit as st
import os
from datetime import datetime

import re
import database as db
import cover_letter as cl
import document_generator as dg
import email_sender as es
import auto_pipeline
from scrapers import torre, remoteok, wwr, computrabajo

_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")

def _clean(text: str) -> str:
    """Strip any residual HTML tags from a string before display."""
    if not text:
        return ""
    text = _HTML_TAG.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Buscador de Empleo",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

db.init_db()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("💼 Buscador de Empleo")
    st.caption("Comunicaciones · Marketing · Venezuela")
    st.divider()

    page = st.radio(
        "nav",
        ["🚀 Auto-Aplicar", "🔍 Buscar empleos", "📋 Mis postulaciones", "✍️ Carta de presentación", "👤 Mi perfil"],
        label_visibility="collapsed",
    )

    st.divider()

    # ── API Key ──
    st.subheader("🔑 API Key (IA)")
    if "api_key" not in st.session_state:
        st.session_state["api_key"] = os.getenv("ANTHROPIC_API_KEY", "")
    api_key_input = st.text_input(
        "Anthropic API Key",
        type="password",
        help="Obtén una en console.anthropic.com — necesaria para generar cartas con IA.",
        key="api_key",
    )
    if api_key_input:
        os.environ["ANTHROPIC_API_KEY"] = api_key_input

    st.divider()

    # ── Email / SMTP ──
    with st.expander("📧 Configurar email (auto-aplicar)"):
        if "smtp_email" not in st.session_state:
            st.session_state["smtp_email"] = ""
        if "smtp_pass" not in st.session_state:
            st.session_state["smtp_pass"] = ""

        st.text_input("Tu email (remitente)", key="smtp_email",
                      placeholder="tucorreo@gmail.com")
        st.text_input("Contraseña de aplicación", key="smtp_pass",
                      type="password",
                      help="Gmail: myaccount.google.com → Seguridad → Contraseñas de aplicaciones")
        smtp_host = st.text_input("Servidor SMTP", value="smtp.gmail.com",
                                  key="smtp_host")
        smtp_port = st.number_input("Puerto", value=587, key="smtp_port")

        if st.session_state.get("smtp_email") and st.session_state.get("smtp_pass"):
            st.success("Email configurado ✓")
        else:
            st.caption("Completa estos campos para poder enviar solicitudes por email.")

    st.divider()

    # ── Stats ──
    summary = db.get_applications_summary()
    total = sum(summary.values())
    st.metric("Total postulaciones", total)
    c1, c2 = st.columns(2)
    c1.metric("Guardadas", summary.get("saved", 0))
    c2.metric("Aplicadas", summary.get("applied", 0))
    if summary.get("interview"):
        st.metric("🎯 Entrevistas", summary["interview"])
    if summary.get("offer"):
        st.metric("🎉 Ofertas", summary["offer"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def smtp_ready() -> bool:
    return bool(st.session_state.get("smtp_email") and st.session_state.get("smtp_pass"))


def _apply_email_form(job: dict, key_prefix: str):
    """Inline email-apply form for a single job."""
    profile = db.get_profile()
    if not profile:
        st.warning("Completa tu perfil primero.")
        return

    app_rec = db.get_application(job["id"])
    saved_letter = (app_rec or {}).get("cover_letter") or ""

    to_email = es.extract_email(job.get("description", "") or "") or ""
    to_input = st.text_input(
        "📩 Email de destino *",
        value=to_email,
        key=f"{key_prefix}_to",
        placeholder="rrhh@empresa.com",
    )

    subject = st.text_input(
        "Asunto",
        value=es.build_subject(profile, job),
        key=f"{key_prefix}_subj",
    )

    fmt = st.radio(
        "Formato del adjunto",
        ["PDF", "Word (.docx)"],
        horizontal=True,
        key=f"{key_prefix}_fmt",
    )

    if not saved_letter:
        st.caption("⚠️ No hay carta guardada para esta vacante. Ve a **Carta de presentación** y genera una primero, o se enviará un mensaje genérico.")

    if st.button("🚀 Enviar solicitud ahora", key=f"{key_prefix}_send", type="primary"):
        if not to_input:
            st.error("Ingresa el email de destino.")
            return
        if not smtp_ready():
            st.error("Configura tu email en la barra lateral primero.")
            return

        letter_to_use = saved_letter or cl.generate(profile, job) if api_key_input else ""
        body = es.build_body(profile, job)

        if fmt == "PDF":
            attachment = dg.to_pdf(profile, job, letter_to_use) if letter_to_use else dg.to_pdf(profile, job, body)
            att_name = f"carta_{profile.get('name','').replace(' ','_')}_{job.get('company','').replace(' ','_')}.pdf"
        else:
            attachment = dg.to_docx(profile, job, letter_to_use) if letter_to_use else dg.to_docx(profile, job, body)
            att_name = f"carta_{profile.get('name','').replace(' ','_')}_{job.get('company','').replace(' ','_')}.docx"

        with st.spinner("Enviando..."):
            ok, msg = es.send_application(
                smtp_email=st.session_state["smtp_email"],
                smtp_password=st.session_state["smtp_pass"],
                to_email=to_input,
                subject=subject,
                body=body,
                attachment=attachment,
                attachment_name=att_name,
                smtp_host=st.session_state.get("smtp_host", "smtp.gmail.com"),
                smtp_port=int(st.session_state.get("smtp_port", 587)),
            )

        if ok:
            db.save_application(job["id"], "applied",
                                (app_rec or {}).get("cover_letter", ""),
                                (app_rec or {}).get("notes", ""))
            st.success(msg)
            st.session_state.pop(f"{key_prefix}_open", None)
            st.rerun()
        else:
            st.error(msg)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Auto-Aplicar
# ─────────────────────────────────────────────────────────────────────────────
if page == "🚀 Auto-Aplicar":
    st.title("🚀 Auto-Aplicar")
    st.markdown(
        "Busca vacantes en **todos los portales** y aplica automáticamente — "
        "todo en un solo clic."
    )

    profile = db.get_profile()

    # ── How it works ──────────────────────────────────────────────────────
    with st.expander("ℹ️ ¿Cómo funciona?", expanded=False):
        st.markdown("""
**Paso 1 — Búsqueda**: consulta Torre.co, Remote OK, We Work Remotely y Computrabajo Venezuela.

**Paso 2 — Carta con IA**: genera una carta personalizada para cada vacante usando tu perfil.

**Paso 3 — Detecta el email**: rastrea la página de la vacante buscando el email de RRHH.

**Paso 4a — Aplica por email** ✅: si encuentra email → envía la carta en PDF automáticamente.

**Paso 4b — Aplica en la web** 🌐: si no hay email → usa el navegador automático para aplicar directamente en Torre.co o Computrabajo (requiere cuenta).

**Paso 5 — Resumen**: muestra qué empleos recibieron la solicitud y cuáles necesitan atención manual.
        """)

    st.divider()

    # ── Pre-flight checks ─────────────────────────────────────────────────
    checks = {
        "👤 Perfil completo": bool(profile and profile.get("name") and profile.get("summary")),
        "🔑 API Key de IA": bool(os.getenv("ANTHROPIC_API_KEY")),
        "📧 Email configurado": smtp_ready(),
    }
    all_ready = all(checks.values())

    col_chk, col_cfg = st.columns([1, 1])
    with col_chk:
        st.subheader("Estado")
        for label, ok in checks.items():
            st.markdown(f"{'✅' if ok else '❌'} {label}")
        if not checks["👤 Perfil completo"]:
            st.caption("→ Ve a **👤 Mi perfil** y completa tu información")
        if not checks["🔑 API Key de IA"]:
            st.caption("→ Pega tu Anthropic API Key en la barra lateral")
        if not checks["📧 Email configurado"]:
            st.caption("→ Abre **📧 Configurar email** en la barra lateral")

    with col_cfg:
        st.subheader("Configuración")
        kw = st.text_input("Palabras clave de búsqueda",
                           value="",
                           placeholder="ej: marketing, comunicaciones, finanzas, diseño...",
                           key="auto_kw")
        only_new = st.checkbox("Solo vacantes nuevas (omitir las ya aplicadas)", value=True)

    st.divider()

    # ── Platform accounts (web apply) ─────────────────────────────────────
    st.subheader("🌐 Cuentas en portales (para aplicar sin email)")
    st.caption("Opcional — solo necesario para empleos que no tienen email de contacto visible.")

    pcol1, pcol2 = st.columns(2)
    with pcol1:
        with st.container(border=True):
            st.markdown("**Torre.co**")
            if "torre_email" not in st.session_state:
                st.session_state["torre_email"] = ""
            if "torre_pass" not in st.session_state:
                st.session_state["torre_pass"] = ""
            st.text_input("Email", key="torre_email", placeholder="tu@email.com")
            st.text_input("Contraseña", key="torre_pass", type="password")
            st.caption("[Crear cuenta gratis →](https://torre.ai/register)")

    with pcol2:
        with st.container(border=True):
            st.markdown("**Computrabajo Venezuela**")
            if "ct_email" not in st.session_state:
                st.session_state["ct_email"] = ""
            if "ct_pass" not in st.session_state:
                st.session_state["ct_pass"] = ""
            st.text_input("Email", key="ct_email", placeholder="tu@email.com")
            st.text_input("Contraseña", key="ct_pass", type="password")
            st.caption("[Crear cuenta gratis →](https://www.computrabajo.com.ve/registrarse)")

    st.divider()

    # ── Launch button ──────────────────────────────────────────────────────
    if not profile:
        st.error("Completa tu **👤 Perfil** antes de iniciar.")
        st.stop()

    launch = st.button(
        "🚀 INICIAR AUTO-APLICACIÓN",
        type="primary",
        use_container_width=True,
        disabled=not all_ready,
    )

    if not all_ready and not launch:
        st.caption("Completa los 3 requisitos arriba para habilitar el botón.")

    if launch:
        st.divider()
        st.subheader("⚙️ Progreso en vivo")

        log_box = st.empty()
        progress_bar = st.progress(0)
        log_lines: list[str] = []

        def on_progress(msg: str):
            log_lines.append(msg)
            log_box.text_area("Log", value="\n".join(log_lines[-40:]),
                              height=260, label_visibility="collapsed")

        torre_creds = None
        if st.session_state.get("torre_email") and st.session_state.get("torre_pass"):
            torre_creds = {
                "email": st.session_state["torre_email"],
                "password": st.session_state["torre_pass"],
            }

        ct_creds = None
        if st.session_state.get("ct_email") and st.session_state.get("ct_pass"):
            ct_creds = {
                "email": st.session_state["ct_email"],
                "password": st.session_state["ct_pass"],
            }

        with st.spinner("Auto-aplicación en curso…"):
            results = auto_pipeline.run(
                profile=profile,
                smtp_email=st.session_state.get("smtp_email", ""),
                smtp_pass=st.session_state.get("smtp_pass", ""),
                smtp_host=st.session_state.get("smtp_host", "smtp.gmail.com"),
                smtp_port=int(st.session_state.get("smtp_port", 587)),
                keywords=kw,
                torre_creds=torre_creds,
                computrabajo_creds=ct_creds,
                on_progress=on_progress,
                only_new=only_new,
            )
        progress_bar.progress(100)

        # ── Results summary ────────────────────────────────────────────────
        st.divider()
        st.subheader("📊 Resultados")

        applied     = [r for r in results if r["success"]]
        with_email  = [r for r in results if r["contact_email"] and not r["success"]]
        manual      = [r for r in results if r["method"] == "manual_needed"]
        failed      = [r for r in results if not r["success"] and r["method"] not in ("manual_needed", "email_not_configured")]

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("✅ Enviadas", len(applied))
        m2.metric("📧 Emails encontrados", len([r for r in results if r["contact_email"]]))
        m3.metric("⚠️ Manual requerido", len(manual))
        m4.metric("❌ Fallidas", len(failed))

        # ── Applied table ──────────────────────────────────────────────────
        if applied:
            st.success(f"### ✅ {len(applied)} solicitudes enviadas")
            for r in applied:
                st.markdown(
                    f"- **{r['title']}** @ {r['company']}  "
                    f"| 📧 `{r['contact_email']}`  "
                    f"| {r['message']}"
                )

        # ── Emails found but not sent (SMTP issue) ─────────────────────────
        if with_email:
            st.warning(f"### 📧 {len(with_email)} emails encontrados — no enviados (verifica SMTP)")
            for r in with_email:
                st.markdown(f"- **{r['title']}** @ {r['company']} — `{r['contact_email']}`")

        # ── Manual needed ──────────────────────────────────────────────────
        if manual:
            st.info(f"### ℹ️ {len(manual)} vacantes requieren aplicación manual")
            st.caption("No se encontró email de contacto ni credenciales de portal para estas.")
            for r in manual:
                st.markdown(f"- [{r['title']} @ {r['company']}]({r['url']})")

        # ── Full details table ─────────────────────────────────────────────
        with st.expander("📋 Ver todos los resultados detallados"):
            import pandas as pd
            df = pd.DataFrame([{
                "Cargo": r["title"],
                "Empresa": r["company"],
                "Fuente": r["source"],
                "Email encontrado": r["contact_email"] or "—",
                "Método": r["method"],
                "Éxito": "✅" if r["success"] else "❌",
                "Mensaje": r["message"][:80],
            } for r in results])
            st.dataframe(df, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Buscar empleos
# ─────────────────────────────────────────────────────────────────────────────
elif page == "🔍 Buscar empleos":
    st.title("🔍 Buscar empleos")

    # ── Row 1: keywords + source + search button ──────────────────────────
    r1a, r1b, r1c = st.columns([3, 2, 1])
    with r1a:
        search_kw = st.text_input(
            "Palabras clave",
            value=st.session_state.get("last_kw", ""),
            placeholder="ej: marketing, diseñador, community manager...",
            key="search_kw_input",
        )
    with r1b:
        source_filter = st.selectbox(
            "Fuente",
            ["Todas", "Torre.co", "Remote OK", "We Work Remotely", "Computrabajo"],
        )
    with r1c:
        st.write("")
        st.write("")
        search_btn = st.button("🔎 Buscar", type="primary", use_container_width=True)

    # ── Row 2: scope toggle + negative keywords ────────────────────────────
    r2a, r2b = st.columns([1, 2])
    with r2a:
        scope = st.radio(
            "Buscar en",
            ["Solo título", "Todo el contenido"],
            horizontal=True,
            help="'Solo título' es más preciso. 'Todo el contenido' busca también en la descripción.",
        )
    with r2b:
        exclude_text = st.text_input(
            "🚫 Palabras negativas (excluir resultados que contengan estas palabras)",
            placeholder="ej: support, nurse, driver, sales",
            key="filter_exclude",
        )

    st.divider()

    if search_btn:
        if not search_kw.strip():
            st.warning("Escribe al menos una palabra clave antes de buscar.")
            st.stop()
        prog = st.progress(0, text="Torre.co...")
        db.upsert_jobs(torre.search(keywords=search_kw))
        prog.progress(25, text="Remote OK...")
        db.upsert_jobs(remoteok.search(keywords=search_kw))
        prog.progress(50, text="We Work Remotely...")
        db.upsert_jobs(wwr.search())
        prog.progress(75, text="Computrabajo Venezuela...")
        db.upsert_jobs(computrabajo.search())
        prog.progress(100, text="¡Listo!")
        st.session_state["last_kw"] = search_kw
        st.rerun()

    src = "" if source_filter == "Todas" else source_filter
    title_only = (scope == "Solo título")
    jobs = db.get_jobs(
        search=search_kw,
        exclude=exclude_text,
        source=src,
        title_only=title_only,
    )

    if not jobs:
        st.info("No hay empleos guardados aún. Haz clic en **Buscar** para comenzar.")
        st.stop()

    # ── Bulk-select toolbar ──
    st.caption(f"Mostrando **{len(jobs)}** vacante(s)")
    tb1, tb2, tb3, tb4 = st.columns([1, 1, 1, 4])

    select_all = tb1.checkbox("Seleccionar todo", key="sel_all")

    selected_ids = [
        j["id"] for j in jobs
        if st.session_state.get(f"sel_{j['id']}", False) or select_all
    ]

    if tb2.button(f"💾 Guardar {len(selected_ids)}", disabled=len(selected_ids) == 0):
        for jid in selected_ids:
            db.save_application(jid, "saved")
        st.success(f"✅ {len(selected_ids)} empleos guardados.")
        st.rerun()

    if tb3.button(f"🗑️ Borrar {len(selected_ids)}", disabled=len(selected_ids) == 0):
        for jid in selected_ids:
            db.delete_job(jid)
        st.rerun()

    st.divider()

    # ── Job cards ──
    STATUS_BADGE = {
        "saved": "🔖", "applied": "✅", "interview": "🎯",
        "rejected": "❌", "offer": "🎉",
    }

    for job in jobs:
        badge = STATUS_BADGE.get(job.get("status"), "")
        cb_col, card_col = st.columns([0.03, 0.97])

        with cb_col:
            st.checkbox("", key=f"sel_{job['id']}",
                        value=select_all,
                        label_visibility="collapsed")

        with card_col:
            label = (f"{badge} **{job['title']}** — {job['company']}  "
                     f"|  📍 {job['location']}  |  🌐 {job['source']}")
            with st.expander(label):
                left, right = st.columns([3, 1])

                with left:
                    if job.get("salary"):
                        st.markdown(f"💰 **Salario:** {job['salary']}")
                    tags = job.get("tags") or []
                    if isinstance(tags, list) and tags:
                        st.markdown("🏷️ " + "  ".join(f"`{t}`" for t in tags[:8]))
                    if job.get("description"):
                        desc = _clean(job["description"])
                        st.markdown(desc[:700] + ("…" if len(desc) > 700 else ""))

                with right:
                    st.markdown(f"[🔗 Ver vacante]({job['url']})")
                    st.divider()

                    opts = ["none", "saved", "applied", "interview", "rejected", "offer"]
                    cur = job.get("status") or "none"
                    new_status = st.selectbox(
                        "Estado", opts,
                        index=opts.index(cur) if cur in opts else 0,
                        key=f"status_{job['id']}",
                        format_func=lambda s: {
                            "none": "Sin estado", "saved": "🔖 Guardar",
                            "applied": "✅ Aplicado", "interview": "🎯 Entrevista",
                            "rejected": "❌ Rechazado", "offer": "🎉 Oferta",
                        }[s],
                    )
                    if st.button("Guardar estado", key=f"save_{job['id']}"):
                        if new_status != "none":
                            db.save_application(job["id"], new_status)
                        st.rerun()

                    if st.button("✍️ Generar carta", key=f"cl_{job['id']}", type="primary"):
                        st.session_state["cl_job_id"] = job["id"]
                        # switch nav
                        st.session_state["_nav"] = "✍️ Carta de presentación"
                        st.rerun()

                # ── Email apply toggle ──
                apply_key = f"apply_open_{job['id']}"
                if smtp_ready():
                    if st.button("📧 Aplicar por email", key=f"applyb_{job['id']}"):
                        st.session_state[apply_key] = not st.session_state.get(apply_key, False)

                    if st.session_state.get(apply_key):
                        with st.container(border=True):
                            st.markdown("**Enviar solicitud por email**")
                            _apply_email_form(job, key_prefix=f"jcard_{job['id']}")
                else:
                    st.caption("Configura tu email en la barra lateral para aplicar directamente.")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Mis postulaciones
# ─────────────────────────────────────────────────────────────────────────────
elif page == "📋 Mis postulaciones":
    st.title("📋 Mis postulaciones")

    STATUS_LABELS = {
        "saved": ("🔖", "Guardados"),
        "applied": ("✅", "Aplicados"),
        "interview": ("🎯", "Entrevistas"),
        "offer": ("🎉", "Ofertas"),
        "rejected": ("❌", "Rechazados"),
    }

    tabs = st.tabs([f"{v[0]} {v[1]}" for v in STATUS_LABELS.values()])

    for tab, (status, (icon, label)) in zip(tabs, STATUS_LABELS.items()):
        with tab:
            jobs = db.get_jobs()
            filtered = [j for j in jobs if j.get("status") == status]
            if not filtered:
                st.info(f"No hay empleos en '{label}' todavía.")
                continue

            for job in filtered:
                app_rec = db.get_application(job["id"])
                with st.expander(f"**{job['title']}** — {job['company']}  |  📍 {job['location']}"):
                    st.markdown(f"🌐 [{job['source']}]({job['url']})")
                    if app_rec and app_rec.get("applied_at"):
                        st.caption(f"Aplicado: {app_rec['applied_at'][:10]}")

                    notes = st.text_area("Notas", key=f"notes_{job['id']}",
                                         value=(app_rec or {}).get("notes") or "",
                                         height=80)
                    new_status = st.selectbox(
                        "Cambiar estado",
                        ["saved", "applied", "interview", "rejected", "offer"],
                        index=["saved", "applied", "interview", "rejected", "offer"].index(status),
                        key=f"pstatus_{job['id']}",
                        format_func=lambda s: {
                            "saved": "🔖 Guardado", "applied": "✅ Aplicado",
                            "interview": "🎯 Entrevista", "rejected": "❌ Rechazado",
                            "offer": "🎉 Oferta",
                        }[s],
                    )

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("💾 Guardar", key=f"psave_{job['id']}"):
                            cl_text = (app_rec or {}).get("cover_letter", "")
                            db.save_application(job["id"], new_status, cl_text, notes)
                            st.success("Guardado")
                            st.rerun()
                    with c2:
                        if st.button("✍️ Ver carta", key=f"pcl_{job['id']}"):
                            st.session_state["cl_job_id"] = job["id"]
                            st.rerun()
                    with c3:
                        if smtp_ready() and st.button("📧 Aplicar", key=f"papply_{job['id']}"):
                            st.session_state[f"papply_open_{job['id']}"] = True

                    if smtp_ready() and st.session_state.get(f"papply_open_{job['id']}"):
                        with st.container(border=True):
                            _apply_email_form(job, key_prefix=f"pcard_{job['id']}")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Carta de presentación
# ─────────────────────────────────────────────────────────────────────────────
elif page == "✍️ Carta de presentación":
    st.title("✍️ Carta de presentación con IA")

    profile = db.get_profile()
    if not profile:
        st.warning("Completa tu **👤 Perfil** primero — la IA lo necesita para personalizar la carta.")

    jobs = db.get_jobs()
    if not jobs:
        st.info("Primero busca y guarda algunas vacantes.")
        st.stop()

    job_options = {f"{j['title']} — {j['company']} ({j['source']})": j["id"] for j in jobs}

    default_label = None
    if "cl_job_id" in st.session_state:
        for lbl, jid in job_options.items():
            if jid == st.session_state["cl_job_id"]:
                default_label = lbl
                break

    selected_label = st.selectbox(
        "Selecciona la vacante",
        list(job_options.keys()),
        index=list(job_options.keys()).index(default_label) if default_label else 0,
    )
    selected_job_id = job_options[selected_label]
    job = db.get_job(selected_job_id)
    app_rec = db.get_application(selected_job_id)

    cl_key = f"cl_editor_{selected_job_id}"
    if cl_key not in st.session_state:
        saved = (app_rec or {}).get("cover_letter") or ""
        if saved:
            st.session_state[cl_key] = saved

    # ── Controls ──
    col1, col2 = st.columns([1, 1])
    with col1:
        language = st.radio("Idioma", ["Español", "Inglés"], horizontal=True)
        extra_notes = st.text_area("Notas para la IA (opcional)",
                                   placeholder="ej: énfasis en redes sociales, campañas digitales...",
                                   height=80)
        gen_btn = st.button("✨ Generar con IA", type="primary", use_container_width=True)

    with col2:
        st.markdown("**Vacante:**")
        st.markdown(f"- **{job['title']}** en {job['company']}")
        st.markdown(f"- 📍 {job['location']}")
        st.markdown(f"- [🔗 Ver vacante]({job['url']})")

    if gen_btn:
        if not profile:
            st.error("Completa tu perfil primero.")
        else:
            with st.spinner("Generando carta con Claude AI..."):
                lang_code = "es" if language == "Español" else "en"
                letter = cl.generate(profile, job, language=lang_code, extra_notes=extra_notes)
                st.session_state[cl_key] = letter

    st.divider()
    st.subheader("📝 Editar carta")

    letter_text = st.text_area(
        "Edita la carta aquí",
        height=420,
        key=cl_key,
        placeholder="La carta generada por IA aparecerá aquí. También puedes escribirla manualmente.",
    )

    if st.session_state.get(cl_key):
        improve_feedback = st.text_input(
            "Mejorar con IA",
            placeholder="ej: más concisa, más énfasis en liderazgo de equipos...",
        )
        if st.button("🔄 Mejorar"):
            with st.spinner("Mejorando..."):
                st.session_state[cl_key] = cl.improve(st.session_state[cl_key], improve_feedback)
            st.rerun()

    st.divider()
    st.subheader("💾 Guardar y descargar")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        if st.button("💾 Guardar", type="primary", use_container_width=True):
            status = (app_rec or {}).get("status") or "saved"
            notes = (app_rec or {}).get("notes") or ""
            db.save_application(selected_job_id, status, letter_text, notes)
            st.success("Carta guardada.")

    with c2:
        if letter_text and profile:
            docx_bytes = dg.to_docx(profile, job, letter_text)
            fname = f"carta_{job.get('company','').replace(' ','_')}.docx"
            st.download_button(
                "⬇️ Descargar Word",
                data=docx_bytes,
                file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        else:
            st.button("⬇️ Descargar Word", disabled=True, use_container_width=True)

    with c3:
        if letter_text and profile:
            pdf_bytes = dg.to_pdf(profile, job, letter_text)
            fname_pdf = f"carta_{job.get('company','').replace(' ','_')}.pdf"
            st.download_button(
                "⬇️ Descargar PDF",
                data=pdf_bytes,
                file_name=fname_pdf,
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.button("⬇️ Descargar PDF", disabled=True, use_container_width=True)

    with c4:
        if st.button("🗑️ Limpiar", use_container_width=True):
            st.session_state.pop(cl_key, None)
            st.rerun()

    # ── Email apply from cover letter page ──
    st.divider()
    st.subheader("📧 Aplicar directamente por email")

    if not smtp_ready():
        st.info("Configura tu email en la barra lateral (⬅️ sección **Configurar email**) para aplicar directamente.")
    elif not letter_text:
        st.info("Genera o escribe la carta primero.")
    else:
        with st.container(border=True):
            _apply_email_form(job, key_prefix=f"clpage_{selected_job_id}")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Mi perfil
# ─────────────────────────────────────────────────────────────────────────────
elif page == "👤 Mi perfil":
    st.title("👤 Mi perfil profesional")
    st.caption("Esta información personaliza las cartas de presentación generadas por IA.")

    profile = db.get_profile() or {}

    with st.form("profile_form"):
        st.subheader("Información personal")
        c1, c2 = st.columns(2)
        name = c1.text_input("Nombre completo *", value=profile.get("name", ""))
        email = c2.text_input("Email *", value=profile.get("email", ""))
        phone = c1.text_input("Teléfono / WhatsApp", value=profile.get("phone", ""))
        location = c2.text_input("Ubicación", value=profile.get("location", "Caracas, Venezuela"))
        linkedin = st.text_input("LinkedIn URL", value=profile.get("linkedin", ""))

        st.divider()
        st.subheader("Perfil profesional")
        summary = st.text_area("Resumen profesional *", value=profile.get("summary", ""),
                                height=110,
                                placeholder="Especialista en comunicaciones con X años de experiencia en marketing digital...")
        skills = st.text_area("Habilidades clave", value=profile.get("skills", ""),
                               height=75,
                               placeholder="Marketing digital, SEO, redes sociales, community management, copywriting...")
        languages = st.text_input("Idiomas", value=profile.get("languages", ""),
                                   placeholder="Español (nativo), Inglés (avanzado)")

        st.divider()
        st.subheader("Experiencia laboral")
        experience = st.text_area(
            "Experiencia (empresa, cargo, logros)",
            value=profile.get("experience", ""),
            height=160,
            placeholder=(
                "Empresa ABC — Coordinadora de Marketing Digital (2022–presente)\n"
                "- Crecí comunidad en Instagram de 5K a 50K seguidores\n"
                "- Gestioné campañas de email con 35% de tasa de apertura\n\n"
                "Empresa XYZ — Asistente de Comunicaciones (2019–2022)\n"
                "- Redacté comunicados de prensa para clientes corporativos"
            ),
        )

        st.divider()
        st.subheader("Educación")
        education = st.text_area("Formación académica", value=profile.get("education", ""),
                                  height=75,
                                  placeholder="Licenciatura en Comunicación Social — UCV (2018)")

        submitted = st.form_submit_button("💾 Guardar perfil", type="primary",
                                          use_container_width=True)
        if submitted:
            if not name or not email or not summary:
                st.error("Completa los campos obligatorios (*).")
            else:
                db.save_profile({
                    "name": name, "email": email, "phone": phone,
                    "location": location, "linkedin": linkedin,
                    "summary": summary, "skills": skills,
                    "experience": experience, "education": education,
                    "languages": languages,
                })
                st.success("✅ Perfil guardado.")
                st.balloons()
