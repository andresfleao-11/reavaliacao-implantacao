from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "quote_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=['app.tasks.quote_tasks', 'app.tasks.batch_tasks', 'app.tasks.scheduled_tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Sao_Paulo',
    enable_utc=True,
)

# Configuração do Celery Beat - Tarefas agendadas
celery_app.conf.beat_schedule = {
    'update-exchange-rate-daily': {
        'task': 'update_exchange_rate',
        'schedule': crontab(hour=23, minute=0),  # Todos os dias às 23:00 (horário de Brasília)
        'options': {'queue': 'default'}
    },
    'recover-stuck-quotes': {
        'task': 'recover_stuck_quotes',
        'schedule': crontab(minute='*/5'),  # A cada 5 minutos
        'options': {'queue': 'default'}
    },
    'cleanup-old-processing-daily': {
        'task': 'cleanup_old_processing',
        'schedule': crontab(hour=4, minute=0),  # Diariamente às 04:00
        'options': {'queue': 'default'}
    },
}

