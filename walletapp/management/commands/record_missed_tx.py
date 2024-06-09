from django.core.management.base import BaseCommand
from walletapp.models import Balances, Currencies, User, Transactions

from walletapp.utils import get_currency_btc


class Command(BaseCommand):
    help = "Add missed transaction"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        user = User.objects.get(username="soldyuyuyu")

        # currency_btc = Currencies.objects.get(acronym="SAT")
        # balance_btc = Balances.objects.get(user=user,currency=currency_btc)
        # print("before")
        # print(balance_btc.balance)
        # print(balance_btc.pending_balance)

        # trn = Transactions.objects.create(
        #     user=user,
        #     invoice_inbound="bc1qvmnq7hp92d4r8ak79kvgpvrl43efpjr23pyrav",
        #     tx_id = "f31dc9b16b5a1ad11024df2c9b8956ad452428879dffea964038d8a936fdd31a",
        #     amount = 2000000,
        #     status = "inbound_invoice_paid",
        #     direction = "inbound",
        #     currency = get_currency_btc(),
        #     type = "user",
        # )
        # trn.finalize()
        # trn.save()

        # balance_btc.refresh_from_db()
        # print("after")
        # print(balance_btc.balance)
        # print(balance_btc.pending_balance)

        # balance_btc.refresh_from_db()
        # print("tx_id")
        # print(trn.id)

        trn = Transactions.objects.get(
            user=user,
            invoice_inbound="bc1qvmnq7hp92d4r8ak79kvgpvrl43efpjr23pyrav",
            tx_id="f31dc9b16b5a1ad11024df2c9b8956ad452428879dffea964038d8a936fdd31a",
            amount=20000000,
            status="inbound_invoice_paid",
            direction="inbound",
            currency=get_currency_btc(),
            type="user",
        )

        trn.amount = 2000000
        trn.save()
