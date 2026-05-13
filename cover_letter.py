"""
AI-powered cover letter generator using Claude.
"""
import os
import anthropic


def generate(profile: dict, job: dict, language: str = "es", extra_notes: str = "") -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "(Ingresa tu API key de Anthropic en la barra lateral para generar cartas de presentación con IA)"

    client = anthropic.Anthropic(api_key=api_key)

    lang_instruction = (
        "Escribe la carta en español (Venezuela)." if language == "es"
        else "Write the letter in English."
    )

    profile_text = f"""
Nombre: {profile.get('name', '')}
Email: {profile.get('email', '')}
Teléfono: {profile.get('phone', '')}
LinkedIn: {profile.get('linkedin', '')}
Resumen profesional: {profile.get('summary', '')}
Habilidades: {profile.get('skills', '')}
Experiencia: {profile.get('experience', '')}
Educación: {profile.get('education', '')}
Idiomas: {profile.get('languages', '')}
""".strip()

    job_text = f"""
Cargo: {job.get('title', '')}
Empresa: {job.get('company', '')}
Ubicación: {job.get('location', '')}
Descripción: {job.get('description', '')[:1500]}
""".strip()

    extra = f"\nNotas adicionales del candidato: {extra_notes}" if extra_notes else ""

    prompt = f"""Eres un experto en redacción de cartas de presentación para profesionales de comunicaciones y marketing en América Latina.

Perfil del candidato:
{profile_text}

Vacante:
{job_text}
{extra}

{lang_instruction}

Escribe una carta de presentación profesional, personalizada y convincente de 3-4 párrafos.
- Párrafo 1: Presentación e interés específico en la empresa/cargo.
- Párrafo 2: Experiencia y logros más relevantes para este puesto.
- Párrafo 3: Habilidades clave y por qué es la candidata ideal.
- Párrafo 4: Cierre con llamada a la acción y disponibilidad.

Tono: profesional, cálido, seguro. Evita frases genéricas. Sé específica con la empresa y el cargo.
Solo devuelve el texto de la carta, sin títulos ni encabezados adicionales."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def improve(cover_letter: str, feedback: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return cover_letter

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Mejora esta carta de presentación según las instrucciones del usuario.

Carta actual:
{cover_letter}

Instrucciones de mejora:
{feedback}

Devuelve solo la carta mejorada, sin explicaciones adicionales."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text
