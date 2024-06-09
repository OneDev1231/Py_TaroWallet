from django.core.management.base import BaseCommand
from walletapp.models import Balances, Transactions, User

from walletapp.utils import get_currency_btc


class Command(BaseCommand):
    help = "Fix balances below zero"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        sum_new_balance = 0
        sum_orig_balance = 0
        sum_orig_pending_balance = 0

        for user in User.objects.all():
            trans_received = Transactions.objects.filter(
                type="user",
                direction="inbound",
                status="inbound_invoice_paid",
                currency=get_currency_btc(),
                user=user,
            )

            trans_paid = Transactions.objects.filter(
                type="user",
                direction="outbound",
                status="outbound_invoice_paid",
                currency=get_currency_btc(),
                user=user,
            )

            trans_fees = Transactions.objects.filter(
                type="fee",
                direction="outbound",
                status="fee_paid",
                currency=get_currency_btc(),
                user=user,
            )

            amount_total = 0

            for trn in trans_received:
                amount_total = amount_total + trn.amount

            for trn in trans_paid:
                amount_total = amount_total - trn.amount

            for trn in trans_fees:
                amount_total = amount_total - trn.amount

            if Balances.objects.filter(user=user, currency=get_currency_btc()).exists():
                balance = Balances.objects.get(user=user, currency=get_currency_btc())

                print(user.username)
                print(balance.balance)
                print(balance.pending_balance)
                print(amount_total)

                new_balance = (
                    (
                        balance.balance
                        if balance.balance < 50000
                        else max(amount_total, 50000)
                    )
                    if amount_total > 0
                    else 50
                )

                print(new_balance)

                sum_orig_balance = sum_orig_balance + balance.balance
                sum_orig_pending_balance = (
                    sum_orig_pending_balance + balance.pending_balance
                )
                sum_new_balance = sum_new_balance + new_balance

                balance.balance = new_balance
                balance.save()

        print("sum_new_balance")
        print(sum_new_balance)

        print("sum_orig_balance")
        print(sum_orig_balance)

        print("sum_orig_pending_balance")
        print(sum_orig_pending_balance)
