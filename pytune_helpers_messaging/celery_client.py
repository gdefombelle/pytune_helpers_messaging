# pytune_helpers_messaging/celery_client.py
import os
from celery import Celery
from pytune_configuration.sync_config_singleton import config, SimpleConfig
from simple_logger.logger import SimpleLogger, get_logger

if config is None:
    config = SimpleConfig()

logger: SimpleLogger = get_logger("email_worker")


class CeleryInitializationError(Exception):
    """Raised when Celery client initialization fails."""
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class CeleryClient:
    """
    Celery client STRICTEMENT limité au email_worker.
    - Ne déclare QUE email_tasks.*
    - Ne fait un health check QUE sur email worker.
    """

    def __init__(self):
        broker_url = os.getenv("RABBIT_BROKER_URL")
        backend_url = os.getenv("RABBIT_BACKEND")
        logger.info(f"[CeleryClient] broker={broker_url}, backend={backend_url}")

        self.celery_client = Celery(
            "pytune_email_client",
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

        # ---- Email worker only ----
        self.health_check = self.celery_client.signature("email_tasks.health_check")
        self.send_mail = self.celery_client.signature("email_tasks.send_mail")

        # ---- Baseline health check ----
        # try:
        #     self.health_status = self.check_health()
        #     if self.health_status.get("status") != "OK":
        #         raise CeleryInitializationError(
        #             f"Initialization failed: {self.health_status.get('message')}"
        #         )
        # except CeleryInitializationError as e:
        #     logger.error(f"[CeleryClient] {e}")
        #     raise

    def check_health(self):
        """Check ONLY the email worker."""
        try:
            result = self.health_check.delay()
            logger.info(f"[CeleryClient] Email health_check id={result.id}")
            res = result.get(timeout=10)
            logger.info(f"[CeleryClient] Email health_check result={res}")
            return res
        except Exception as e:
            msg = {"status": "ERROR", "message": f"Email health check failed: {e}"}
            logger.error(msg)
            return msg