# pytune_helpers/celery_client.py
import os
from celery import Celery
from pytune_configuration.sync_config_singleton import config, SimpleConfig
from simple_logger.logger import SimpleLogger, get_logger

if config is None:
    config = SimpleConfig()

logger: SimpleLogger = get_logger("pytune_worker")


class CeleryInitializationError(Exception):
    """Raised when Celery client initialization fails."""
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class CeleryClient:
    """
    Lightweight Celery client:
    - reads broker/backend from env
    - exposes task signatures (email + piano)
    - runs a quick health check on the email worker at init
    """

    def __init__(self):
        broker_url = os.getenv("RABBIT_BROKER_URL")
        backend_url = os.getenv("RABBIT_BACKEND")
        logger.info(f"Celery Client, broker_url={broker_url}, backend_url={backend_url}")

        self.celery_client = Celery(
            "pytune",
            broker=broker_url,
            backend=backend_url,
        )

        self.celery_client.conf.update(
            worker_pool=config.RABBIT_WORKER_POOL,
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            broker_transport_options={"visibility_timeout": config.RABBIT_VISIBILITY_TIMEOUT},
            timezone="UTC",
            enable_utc=True,
        )

        # ---- Exported task signatures (match worker task names) ----
        # Email worker
        self.health_check = self.celery_client.signature("email_tasks.health_check")
        self.send_mail = self.celery_client.signature("email_tasks.send_mail")
        # Piano worker
        self.piano_health_check = self.celery_client.signature("piano_tasks.health_check")
        self.piano_beautify = self.celery_client.signature("piano_tasks.beautify_piano")

        # ---- Baseline health check (email worker) ----
        try:
            self.health_status = self.check_health()
            if self.health_status.get("status") != "OK":
                raise CeleryInitializationError(
                    f"Initialization failed: {self.health_status.get('message')}"
                )
        except CeleryInitializationError as e:
            logger.error(f"Error during Celery initialization: {e}")
            raise

    # Optional: a separate piano check if you want to test it explicitly
    def check_piano_health(self):
        try:
            result = self.piano_health_check.delay()
            return result.get(timeout=10)
        except Exception as e:
            return {"status": "ERROR", "message": f"Piano health failed: {e}"}

    def check_health(self):
        """Ping the email worker (kept as baseline)."""
        try:
            result = self.health_check.delay()
            logger.info(f"Health check task submitted id=[{result.id}]")
            res = result.get(timeout=10)
            logger.info(f"Health check result: {res}")
            return res
        except Exception as e:
            msg = {"status": "ERROR", "message": f"Health check task failed: {e}"}
            logger.error(msg)
            return msg
