from django.core.management.base import BaseCommand
from walletapp.models import Balances, Transactions, User, Notifications

from walletapp.utils import get_currency_btc


class Command(BaseCommand):
    help = "Fix transactions with no associated_exchange_transaction_id"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        
        notification_list = Notifications.objects.all()

        for notification in notification_list:
            print(notification)
            notification.delete()