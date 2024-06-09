from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from walletapp.models import Balances, Currencies
from walletapp.utils import get_currency_btc, get_pwd


class Command(BaseCommand):
    help = "Pay all unpaid invoices"

    def handle(self, *args, **options):
        # Create BTC currency

        if not Currencies.objects.filter(name="Bitcoin").exists():
            currency_BTC = Currencies.objects.create(
                name="Bitcoin",
                acronym="SAT",
                description="Bitcoin currency",
                status="minted",
            )
            currency_BTC.save()

        # Faucet user

        user = User.objects.create_user(username="faucet_user_1", password=get_pwd())
        user.save()

        balance_btc = Balances.objects.get(user=user, currency=get_currency_btc())
        balance_btc.balance = 0
        balance_btc.save()
