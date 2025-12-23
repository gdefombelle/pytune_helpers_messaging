from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import aiosmtplib

from simple_logger.logger import get_logger
from pytune_configuration.sync_config_singleton import config, SimpleConfig
from pytune_helpers_messaging.email_celery import email_celery

if config is None:
    config = SimpleConfig()

logger = get_logger("email_worker")


class EmailService:
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        is_html: bool = False,
        send_background: bool = False,
        from_email: str | None = None,
        reply_to: str | None = None,
    ):
        from_email = from_email or config.FROM_EMAIL
        if not from_email:
            raise ValueError("SMTP from_email not configured")

        # 🔥 MODE CELERY (comme piano_worker)
        if send_background:
            async_result = email_celery.send_task(
                "email_tasks.send_mail",
                kwargs={
                    "to_email": to_email,
                    "subject": subject,
                    "body": body,
                    "is_html": is_html,
                    "from_email": from_email,
                    "reply_to": reply_to,
                },
                queue="email_tasks_queue",
            )

            logger.info(
                f"[EmailService] queued email {async_result.id} → {to_email}"
            )

            return {
                "job_id": async_result.id,
                "queue": "email_tasks_queue",
                "task": "email_tasks.send_mail",
                "state": "PENDING",
            }

        # 🧪 MODE DIRECT SMTP
        msg = self._build_email(to_email, subject, body, is_html, from_email, reply_to)
        await self._send_direct(msg)
        return {"message": "Email sent directly"}

    def _build_email(self, to_email, subject, body, is_html, from_email, reply_to):
        msg = MIMEMultipart()
        msg["From"] = formataddr(("PyTune Support", from_email))
        msg["To"] = to_email
        msg["Subject"] = subject
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.attach(MIMEText(body, "html" if is_html else "plain"))
        return msg

    async def _send_direct(self, msg):
        await aiosmtplib.send(
            msg,
            hostname=config.SMTP_SERVER,
            port=config.SMTP_SERVER_PORT,
            username=config.SMTP_USER,
            password=config.SMTP_PASSWORD,
            start_tls=True,
        )