from django.core.management.base import BaseCommand
from walletapp.models import Balances, Currencies, User


class Command(BaseCommand):
    help = "Fix balances below zero"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        user = User.objects.get(id=5191)

        print(str(user.username) + " " + str(user.id))
        # currency = Currencies.objects.get(acronym="AC")
        currency_btc = Currencies.objects.get(acronym="USDA")

        balance = Balances.objects.get(user=user, currency=currency_btc)

        # for balance in balances:
        print(balance.balance)
        print(balance.pending_balance)

        balance.pending_balance = 1
        balance.save()

        # print(balance.balance)
        # print(balance.pending_balance)

        # print(balance_btc.balance)
        # print(balance_btc.pending_balance)
