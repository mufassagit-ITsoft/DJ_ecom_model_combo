from django.apps import AppConfig


class SyncConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sync'
    verbose_name = 'Backup DB Sync'

    def ready(self):
        import sync.signals  # noqa — registers all signal handlers on startup