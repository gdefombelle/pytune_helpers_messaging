import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from .celery_client import CeleryClient, CeleryInitializationError
from simple_logger.logger import SimpleLogger, get_logger
from pytune_configuration.sync_config_singleton import config, SimpleConfig

if config is None:
    config = SimpleConfig()

logger : SimpleLogger = get_logger("email_worker")

class EmailService:
    _instance = None

    def __new__(cls, smtp_server=config.SMTP_SERVER, 
                smtp_port=config.SMTP_SERVER_PORT, 
                smtp_user=config.SMTP_USER, 
                smtp_password=config.SMTP_PASSWORD, 
                from_email=config.FROM_EMAIL):
        if cls._instance is None:
            cls._instance = super(EmailService, cls).__new__(cls)
            cls._instance._initialize(
                smtp_server=smtp_server,
                smtp_port=smtp_port,
                smtp_user=smtp_user,
                smtp_password=smtp_password,
                from_email=from_email,
            )
        return cls._instance

    def _initialize(self, smtp_server, smtp_port, smtp_user, smtp_password, from_email):
        """Initialise ou réinitialise les paramètres SMTP"""

        self.smtp_server = smtp_server or config.SMTP_SERVER
        self.smtp_port = smtp_port or config.SMTP_SERVER_PORT
        self.smtp_user = smtp_user or config.SMTP_USER
        self.smtp_password = smtp_password or config.SMTP_PASSWORD
        self.from_email = from_email or config.FROM_EMAIL
        self.logger : SimpleLogger = get_logger()

        if not all([self.smtp_server, self.smtp_port, self.smtp_user, self.smtp_password, self.from_email]):
            self.logger.critical("SMTP configuration is incomplete")
            raise ValueError("SMTP configuration is incomplete")
        # Prépare Celery (pour l'intégration avec RabbitMQ)
        try:
            self.celery_client = CeleryClient()
            self.logger.info(f"Health check during initialization: {self.celery_client.health_status}")
            if self.celery_client.health_status["status"] != "OK":
                self.logger.critical("Celery client health check error failed")
                raise CeleryInitializationError(f"Celery health check failed: {self.celery_client.health_status['message']}")
        except Exception as e:
            self.celery_client = None  # Désactive Celery en cas d'erreur
            self.logger.error(f"Failed to initialize Celery client: {str(e)}")


    def get_smtp_config(self):
        return {
            "smtp_server": self.smtp_server,
            "smtp_port": self.smtp_port,
            "smtp_user": self.smtp_user,
            "smtp_password": self.smtp_password,
            "from_email": self.from_email,
        }
        
    async def send_email(self, to_email: str, subject: str, body: str, is_html=False, send_background=False, from_email=None):
        """Méthode asynchrone pour envoyer un email."""
        if not from_email:
            from_email = self.from_email
        if not from_email:
            await self.logger.aerror(f"SMTP 'from_email' not configured - Sending {subject} to: {to_email}")
            raise ValueError("SMTP 'from_email' not configured")

        if send_background:
            # Planifie la tâche via RabbitMQ (Celery)
            self.celery_client.send_mail.delay(
                to_email = to_email,
                subject = subject,
                body = body,
                is_html = is_html,
                from_email = formataddr(("Pytune Support", from_email))
            )
            await self.logger.ainfo(f"Email to {to_email} scheduled to be sent in background")
            return {"message": "Email scheduled to be sent in background"}
        
        # Construire le message
        message = self._build_email(to_email, subject, body, is_html, from_email)

        # Envoi immédiat
        await self._send_email_task(message)
        await self.logger.ainfo(f"Email {subject} to: {to_email} sent successfully")
        return {"message": "Email sent successfully"}

    def _build_email(self, to_email: str, subject: str, body: str, is_html: bool, from_email: str):
        """Construit le message email."""
        message = MIMEMultipart()
        message["From"] = formataddr(("Pytune Support", from_email))
        message["To"] = to_email
        message["Subject"] = subject

        if is_html:
            message.attach(MIMEText(body, "html"))
        else:
            message.attach(MIMEText(body, "plain"))

        return message

    async def _send_email_task(self, message):
        """Méthode interne pour envoyer un email en mode asynchrone."""
        try:
            await aiosmtplib.send(
                message,
                hostname=self.smtp_server,
                port=self.smtp_port,
                start_tls=True,
                username=self.smtp_user,
                password=self.smtp_password,
            )
            await self.logger.ainfo(f"Email sent to {message['To']}")
        except Exception as e:
            await self.logger.aerror(f"Failed to send email to {message['To']}: {e}")

   
