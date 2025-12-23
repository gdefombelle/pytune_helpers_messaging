
from celery import Celery
from os import getenv

email_celery = Celery(
    "email_api_client",
    broker=getenv("RABBIT_BROKER_URL", "pyamqp://admin:MyStr0ngP@ss2024!@localhost//"),
    backend=getenv("RABBIT_BACKEND", "redis://:UltraSecurePass2024!@pytune-redis:6379/0"),
)