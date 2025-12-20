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
    # ============================================
    # CONFIGURAÇÕES DE PERFORMANCE E RATE LIMITING
    # ============================================
    # Limitar prefetch para evitar acúmulo de tasks
    worker_prefetch_multiplier=1,
    # Ack late para garantir reprocessamento em caso de crash
    task_acks_late=True,
    # Rejeitar task se worker morrer
    task_reject_on_worker_lost=True,
    # Rate limit global para tasks de cotação (3 por segundo)
    # Valor otimizado para 6 workers - ver docs/ANALISE_PERFORMANCE_CELERY.md
    task_annotations={
        'process_quote_request': {'rate_limit': '3/s'},
        'process_batch_quote': {'rate_limit': '3/s'},
    },
    # Timeout para tasks longas (10 minutos)
    task_time_limit=600,
    task_soft_time_limit=540,
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
    'fix-stuck-batches': {
        'task': 'fix_stuck_batches',
        'schedule': crontab(minute='*/10'),  # A cada 10 minutos
        'options': {'queue': 'default'}
    },
    'cleanup-old-processing-daily': {
        'task': 'cleanup_old_processing',
        'schedule': crontab(hour=4, minute=0),  # Diariamente às 04:00
        'options': {'queue': 'default'}
    },
    # ===== Tarefas de Inventário =====
    'sync-inventory-master-data-daily': {
        'task': 'sync_inventory_master_data',
        'schedule': crontab(hour=2, minute=0),  # Diariamente às 02:00 (horário de baixo uso)
        'options': {'queue': 'default'}
    },
    'check-inventory-sessions-hourly': {
        'task': 'check_inventory_sessions_status',
        'schedule': crontab(minute=30),  # A cada hora (minuto 30)
        'options': {'queue': 'default'}
    },
}

