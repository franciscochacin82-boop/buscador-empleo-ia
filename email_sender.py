"""
Sends job application emails with the cover letter attached as PDF.
Works with Gmail (App Password) and any standard SMTP server.
"""
import re
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")


def extract_email(text: str) -> str | None:
    """Pull the first email address found in a block of text."""
    m = EMAIL_RE.search(text or "")
    return m.group(0) if m else None


def build_subject(profile: dict, job: dict) -> str:
    name = profile.get("name", "Candidata")
    title = job.get("title", "Vacante")
    return f"Postulación – {title} – {name}"


def build_body(profile: dict, job: dict) -> str:
    name = profile.get("name", "")
    title = job.get("title", "la vacante")
    company = job.get("company", "su empresa")
    email = profile.get("email", "")
    phone = profile.get("phone", "")

    lines = [
        f"Estimado equipo de {company},",
        "",
        f"Me dirijo a ustedes para expresar mi interés en el cargo de {title}. "
        "Adjunto mi carta de presentación con el detalle de mi perfil y experiencia profesional.",
        "",
        "Quedo a su disposición para cualquier consulta o entrevista.",
        "",
        "Atentamente,",
        name,
    ]
    if email:
        lines.append(email)
    if phone:
        lines.append(phone)
    return "\n".join(lines)


def send_application(
    smtp_email: str,
    smtp_password: str,
    to_email: str,
    subject: str,
    body: str,
    attachment: bytes,
    attachment_name: str,
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
) -> tuple[bool, str]:
    """
    Send the application email. Returns (success, message).
    attachment_name should end in .pdf or .docx.
    """
    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_email
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain", "utf-8"))

        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{attachment_name}"',
        )
        msg.attach(part)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, to_email, msg.as_bytes())

        return True, "✅ Correo enviado correctamente."
    except smtplib.SMTPAuthenticationError:
        return False, (
            "❌ Error de autenticación. Para Gmail usa una Contraseña de Aplicación "
            "(myaccount.google.com → Seguridad → Contraseñas de aplicaciones)."
        )
    except smtplib.SMTPException as e:
        return False, f"❌ Error SMTP: {e}"
    except Exception as e:
        return False, f"❌ Error: {e}"
