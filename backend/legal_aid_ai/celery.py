import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "legal_aid_ai.settings")

app = Celery("legal_aid_ai")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

