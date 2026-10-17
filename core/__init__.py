# core/__init__.py
# Celery ilovasini Django bilan birlashtirish
# Bu import Django ishga tushganda Celery'ning ham to'g'ri yuklanishini ta'minlaydi
from .celery import app as celery_app

__all__ = ('celery_app',)
