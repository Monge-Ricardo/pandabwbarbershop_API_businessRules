from datetime import date, time
from typing import Any

import httpx

from app.config import settings


BREVO_EMAIL_URL = "https://api.brevo.com/v3/smtp/email"


def format_date(value: date | str) -> str:
    if isinstance(value, date):
        parsed_date = value
    else:
        parsed_date = date.fromisoformat(
            str(value).split("T")[0]
        )

    return parsed_date.strftime("%d/%m/%Y")


def format_time(value: time | str) -> str:
    if isinstance(value, time):
        return value.strftime("%H:%M")

    return str(value).split(".")[0][:5]


async def send_appointment_created_email(
    customer_email: str,
    customer_name: str,
    appointment_id: str,
    appointment_date: date | str,
    start_time: time | str,
    service_name: str,
    barber_name: str,
) -> dict[str, Any]:

    if not settings.BREVO_API_KEY:
        raise RuntimeError(
            "BREVO_API_KEY no está configurada."
        )

    if not settings.BREVO_SENDER_EMAIL:
        raise RuntimeError(
            "BREVO_SENDER_EMAIL no está configurado."
        )

    if not customer_email:
        raise RuntimeError(
            "El customer no tiene un correo registrado."
        )

    appointment_date_formatted = format_date(
        appointment_date
    )
    appointment_time_formatted = format_time(
        start_time
    )

    html_content = f"""
    <html>
      <body style="
        font-family: Arial, sans-serif;
        background-color: #111111;
        color: #ffffff;
        padding: 25px;
      ">
        <div style="
          max-width: 600px;
          margin: auto;
          background-color: #1a1a1a;
          border: 1px solid #D4AF37;
          border-radius: 10px;
          padding: 30px;
        ">
          <h2 style="
            color: #D4AF37;
            text-align: center;
          ">
            Tu cita fue registrada
          </h2>

          <p>
            Hola, <strong>{customer_name}</strong>.
          </p>

          <p>
            Tu solicitud de cita fue creada correctamente.
          </p>

          <p>
            <strong>Servicio:</strong> {service_name}
          </p>

          <p>
            <strong>Barbero:</strong> {barber_name}
          </p>

          <p>
            <strong>Fecha:</strong>
            {appointment_date_formatted}
          </p>

          <p>
            <strong>Hora:</strong>
            {appointment_time_formatted}
          </p>

          <p>
            <strong>Estado:</strong>
            Pendiente de aceptación
          </p>

          <p>
            <strong>Código de cita:</strong>
            {appointment_id}
          </p>

          <p>
            Ahora solo debes esperar a que el barbero
            acepte tu solicitud.
          </p>

          <p style="
            color: #aaaaaa;
            font-size: 13px;
          ">
            Este correo confirma la creación de la cita,
            pero todavía no representa su aceptación.
          </p>
        </div>
      </body>
    </html>
    """

    payload = {
        "sender": {
            "name": settings.BREVO_SENDER_NAME,
            "email": settings.BREVO_SENDER_EMAIL,
        },
        "to": [
            {
                "email": customer_email,
                "name": customer_name,
            }
        ],
        "subject": (
            "Tu cita fue registrada y está "
            "pendiente de aceptación"
        ),
        "htmlContent": html_content,
        "textContent": (
            f"Hola, {customer_name}. "
            "Tu cita fue registrada correctamente. "
            f"Servicio: {service_name}. "
            f"Barbero: {barber_name}. "
            f"Fecha: {appointment_date_formatted}. "
            f"Hora: {appointment_time_formatted}. "
            "Estado: pendiente de aceptación."
        ),
        "tags": [
            "appointment-created"
        ],
    }

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": settings.BREVO_API_KEY,
    }

    async with httpx.AsyncClient(
        timeout=15.0
    ) as client:

        response = await client.post(
            BREVO_EMAIL_URL,
            headers=headers,
            json=payload,
        )

    if response.is_error:
        raise RuntimeError(
            f"Brevo respondió {response.status_code}: "
            f"{response.text}"
        )

    return response.json()


async def send_appointment_created_email_safely(
    **email_data: Any,
) -> None:

    appointment_id = email_data.get(
        "appointment_id",
        "desconocida",
    )

    try:
        result = await send_appointment_created_email(
            **email_data
        )

        print(
            "Correo de cita enviado correctamente. "
            f"appointment_id={appointment_id}, "
            f"message_id={result.get('messageId')}"
        )

    except Exception as error:
        print(
            "La cita fue guardada, pero el correo "
            "no pudo enviarse. "
            f"appointment_id={appointment_id}, "
            f"error={error}"
        )