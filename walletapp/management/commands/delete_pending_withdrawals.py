from django.core.management.base import BaseCommand
from walletapp.models import Balances, Transactions, User

from walletapp.utils import get_currency_btc


class Command(BaseCommand):
    help = "Delete pending transactions"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        trans_received = Transactions.objects.filter(
            type="user",
            direction="outbound",
            status="outbound_invoice_received",
            currency=get_currency_btc(),
        )

        for trn in trans_received:
            print(trn)
            trn.error_out("Transactions failed because of maintenance.")
