from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from store.models import Topic, Category, Product
from payment.models import ShippingAddress, Order, OrderItem, RefundRequest, RefundItem
from account.models import RewardAccount, RewardTransaction

BACKUP_DB = ['backup', 'separate']

# Sync order matters — FK parents must come before their children
SYNC_MODELS = [
    ('Users',               User),
    ('Topics',              Topic),
    ('Categories',          Category),
    ('Products',            Product),
    ('Shipping Addresses',  ShippingAddress),
    ('Orders',              Order),
    ('Order Items',         OrderItem),
    ('Refund Requests',     RefundRequest),
    ('Refund Items',        RefundItem),
    ('Reward Accounts',     RewardAccount),
    ('Reward Transactions', RewardTransaction),
]


class Command(BaseCommand):
    help = 'One-time full sync of all production Gamestore data into the backup database.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\nStarting full sync to backup database...\n'
        ))

        total_synced = 0
        total_errors = 0

        for label, Model in SYNC_MODELS:
            queryset = Model.objects.using('default').all()
            count = queryset.count()
            synced = 0
            errors = 0

            self.stdout.write(f'  Syncing {label} ({count} records)...')

            for instance in queryset.iterator():
                instance_errors = 0
                for db in BACKUP_DB:
                    try:
                        instance.save(using=db)
                    except Exception as e:
                        instance_errors += 1
                        errors += 1
                        self.stderr.write(
                            f'    ERROR syncing {label} pk={instance.pk} on db={db}: {e}'
                        )
                if instance_errors == 0:
                    synced += 1

            total_synced += synced
            total_errors += errors

            status = self.style.SUCCESS(f'✓ {synced}/{count}')
            if errors:
                status += self.style.ERROR(f'  ({errors} errors)')
            self.stdout.write(f'    {status}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Sync complete. {total_synced} records synced.'
        ))
        if total_errors:
            self.stdout.write(self.style.ERROR(
                f'{total_errors} errors encountered — check output above.'
            ))