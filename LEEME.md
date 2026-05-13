# 💼 Buscador de Empleo con IA

Aplicación web personal para automatizar la búsqueda de empleo y el proceso de postulación, diseñada para profesionales de **comunicaciones y marketing** en Venezuela y para trabajo remoto.

---

## ¿Qué hace esta app?

| Función | Descripción |
|--------|-------------|
| 🔍 **Buscar empleos** | Busca en Torre.co, Remote OK, We Work Remotely y Computrabajo Venezuela |
| 📋 **Rastrear postulaciones** | Organiza vacantes por estado: Guardado → Aplicado → Entrevista → Oferta |
| ✍️ **Carta de presentación con IA** | Genera cartas personalizadas usando Claude AI para cada vacante |
| 👤 **Tu perfil** | Guarda tu información una vez y se reutiliza en todas las cartas |

---

## Instalación

### Requisitos
- Python 3.10 o superior → [python.org](https://python.org)

### Pasos

1. **Abre una terminal** (símbolo del sistema / PowerShell) en esta carpeta

2. **Instala las dependencias:**
   ```
   pip install -r requirements.txt
   ```

3. **Inicia la aplicación:**
   ```
   streamlit run app.py
   ```
   O simplemente haz doble clic en **`inicio.bat`**

4. Se abrirá automáticamente en tu navegador: `http://localhost:8501`

---

## Configurar la IA (Opcional pero recomendado)

Para generar cartas de presentación con inteligencia artificial:

1. Crea una cuenta en [console.anthropic.com](https://console.anthropic.com)
2. Ve a "API Keys" y crea una nueva key
3. Cópiala y pégala en la barra lateral de la app (campo "Anthropic API Key")

> **Costo:** muy bajo, cada carta cuesta aproximadamente $0.001 USD.

---

## Primeros pasos recomendados

1. Ve a **👤 Mi perfil** y completa toda tu información
2. Ve a **🔍 Buscar empleos**, escribe tus palabras clave y presiona Buscar
3. Guarda las vacantes que te interesen
4. Ve a **✍️ Carta de presentación** y genera una carta personalizada para cada una
5. Rastrea tu progreso en **📋 Mis postulaciones**

---

## Fuentes de empleo incluidas

- **Torre.co** — Mejor plataforma para trabajo en Latinoamérica y remoto
- **Remote OK** — Empleos 100% remotos con buenos salarios en USD
- **We Work Remotely** — Empleos remotos de marketing y comunicaciones
- **Computrabajo Venezuela** — Empleos locales en Venezuela

---

*Creado con Python, Streamlit y Claude AI*
