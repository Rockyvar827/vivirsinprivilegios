"""Envia un email con los borradores nuevos. Configuracion por variables de entorno."""
import json
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path


def titulo(ruta):
    p = Path(ruta)
    for linea in p.read_text(encoding="utf-8").splitlines():
        if linea.startswith("title:"):
            try:
                return json.loads(linea.split(":", 1)[1].strip())
            except ValueError:
                break
    return p.name


def main():
    try:
        host = os.environ["SMTP_HOST"]
        puerto = int(os.environ.get("SMTP_PORT") or 587)
        usuario = os.environ["SMTP_USER"]
        clave = os.environ["SMTP_PASS"]
        destino = os.environ["EMAIL_TO"]
        lista = Path(os.environ["LISTA"])
        pr_url = os.environ.get("PR_URL", "")
    except KeyError as e:
        sys.exit(f"Falta la variable {e}. Revisa los secretos del repositorio.")

    ficheros = [l for l in lista.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not ficheros:
        print("No hay borradores nuevos; no se envía email.")
        return

    lineas = [f"Se han detectado {len(ficheros)} posibles novedades:", ""]
    lineas += [f"- {titulo(f)}" for f in ficheros]
    lineas += ["", f"Revisa el Pull Request: {pr_url}", "",
               "Recuerda: fusionar no publica nada. Redacta el resumen y cambia draft a false."]

    msg = EmailMessage()
    msg["Subject"] = f"Novedades de extranjería: {len(ficheros)} por revisar"
    msg["From"] = usuario
    msg["To"] = destino
    msg.set_content("\n".join(lineas))

    with smtplib.SMTP(host, puerto, timeout=30) as s:
        s.starttls()
        s.login(usuario, clave)
        s.send_message(msg)
    print("Email enviado.")


if __name__ == "__main__":
    main()