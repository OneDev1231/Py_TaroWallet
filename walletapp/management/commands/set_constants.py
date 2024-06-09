from django.core.management.base import BaseCommand
from walletapp.const_utils import set_constant


class Command(BaseCommand):
    help = "Update price history"

    def handle(self, *args, **options):

        set_constant("min_exchange_sats", 10)
        # return 10

        set_constant("initial_free_btc_balance", 500)
        # return

        set_constant("max_withdrawal_onchain", 10000000)
        # return 10000000

        set_constant("max_withdrawal_lnd", 5000000)
        # return 5000000

        set_constant("fee_sat_per_vbyte", 110)
        # return 110

        set_constant("transactions_enabled", 1)

        set_constant(
            "cold_wallet_balance",
            -7972540
            + 50
            + 97
            + 18087647
            + 170
            + 1098539
            + 1098539
            + 238603
            + 100000
            + 1056809
            + 1056809,
        )
