import logging
from django.db.models.signals import post_save, post_delete
from django.contrib.auth.models import User
from django.dispatch import receiver

from store.models import Topic, Category, Product
from payment.models import ShippingAddress, Order, OrderItem, RefundRequest, RefundItem
from account.models import RewardAccount, RewardTransaction

logger = logging.getLogger(__name__)

BACKUP_DB = ['backup', 'separate']

_syncing = set()

def mirror_save(instance):
    """
    Save an instance to the backup database.
    - Guards against infinite recursion via _syncing set
    - Errors are logged but never crash the primary write
    - CloudinaryField on Product is stored as its public_id string
    """
    key = (instance.__class__.__name__, instance.pk)
    if key in _syncing:
        return
    _syncing.add(key)
    try:
        for db in BACKUP_DB:
            try:
                instance.save(using=db)
            except Exception as e:
                logger.error(
                    '[Backup Sync] Save failed for %s (pk=%s) on db=%s: %s',
                    instance.__class__.__name__, instance.pk, db, e
                )
    finally:
        _syncing.discard(key)


def mirror_delete(instance):
    """
    Delete an instance from the backup database by pk.
    Errors are logged but never crash the primary delete.
    """
    for db in BACKUP_DB:
        try:
            type(instance).objects.using(db).filter(pk=instance.pk).delete()
        except Exception as e:
            logger.error(
                '[Backup Sync] Delete failed for %s (pk=%s) on db=%s: %s',
                instance.__class__.__name__, instance.pk, db, e
            )

@receiver(post_save, sender=User)
def sync_user_save(sender, instance, **kwargs):
    mirror_save(instance)

@receiver(post_delete, sender=User)
def sync_user_delete(sender, instance, **kwargs):
    mirror_delete(instance)

@receiver(post_save, sender=Topic)
def sync_topic_save(sender, instance, **kwargs):
    mirror_save(instance)

@receiver(post_delete, sender=Topic)
def sync_topic_delete(sender, instance, **kwargs):
    mirror_delete(instance)


@receiver(post_save, sender=Category)
def sync_category_save(sender, instance, **kwargs):
    mirror_save(instance)

@receiver(post_delete, sender=Category)
def sync_category_delete(sender, instance, **kwargs):
    mirror_delete(instance)


@receiver(post_save, sender=Product)
def sync_product_save(sender, instance, **kwargs):
    mirror_save(instance)

@receiver(post_delete, sender=Product)
def sync_product_delete(sender, instance, **kwargs):
    mirror_delete(instance)

@receiver(post_save, sender=ShippingAddress)
def sync_shipping_address_save(sender, instance, **kwargs):
    mirror_save(instance)

@receiver(post_delete, sender=ShippingAddress)
def sync_shipping_address_delete(sender, instance, **kwargs):
    mirror_delete(instance)


@receiver(post_save, sender=Order)
def sync_order_save(sender, instance, **kwargs):
    mirror_save(instance)

@receiver(post_delete, sender=Order)
def sync_order_delete(sender, instance, **kwargs):
    mirror_delete(instance)


@receiver(post_save, sender=OrderItem)
def sync_order_item_save(sender, instance, **kwargs):
    mirror_save(instance)

@receiver(post_delete, sender=OrderItem)
def sync_order_item_delete(sender, instance, **kwargs):
    mirror_delete(instance)


@receiver(post_save, sender=RefundRequest)
def sync_refund_request_save(sender, instance, **kwargs):
    mirror_save(instance)

@receiver(post_delete, sender=RefundRequest)
def sync_refund_request_delete(sender, instance, **kwargs):
    mirror_delete(instance)


@receiver(post_save, sender=RefundItem)
def sync_refund_item_save(sender, instance, **kwargs):
    mirror_save(instance)

@receiver(post_delete, sender=RefundItem)
def sync_refund_item_delete(sender, instance, **kwargs):
    mirror_delete(instance)

@receiver(post_save, sender=RewardAccount)
def sync_reward_account_save(sender, instance, **kwargs):
    mirror_save(instance)

@receiver(post_delete, sender=RewardAccount)
def sync_reward_account_delete(sender, instance, **kwargs):
    mirror_delete(instance)


@receiver(post_save, sender=RewardTransaction)
def sync_reward_transaction_save(sender, instance, **kwargs):
    mirror_save(instance)

@receiver(post_delete, sender=RewardTransaction)
def sync_reward_transaction_delete(sender, instance, **kwargs):
    mirror_delete(instance)