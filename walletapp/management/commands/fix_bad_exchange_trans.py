from django.core.management.base import BaseCommand
from walletapp.models import Balances, Transactions, User

from walletapp.utils import get_currency_btc


class Command(BaseCommand):
    help = "Fix transactions with no associated_exchange_transaction_id"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        trans_bad = Transactions.objects.filter(
            type="exchange",
            status="exchange_started",
            associated_exchange_transaction__isnull=True,
        )

        for trn in trans_bad:
            print(trn)
            trn.error_out("Transactions failed because of maintenance.")
