# ============================================================
# EduSelf Teacher — core/celery.py
# Celery 5.4 ilovasi va Beat sozlamalari
# TECH_STACK.md §6, Backend.md §6 asosida
# ============================================================
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.local')

# 'eduself_teacher' — Celery ilova nomi (broker'da va loglarda ko'rinadi)
app = Celery('eduself_teacher')

# Django settings'dan CELERY_ prefiksli sozlamalarni yuklash
app.config_from_object('django.conf:settings', namespace='CELERY')

# Barcha apps/* va core/* ichidagi tasks.py fayllarini avtomatik topish
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Test uchun debug vazifa — 'celery call core.celery.debug_task' bilan tekshiring"""
    print(f'Request: {self.request!r}')
