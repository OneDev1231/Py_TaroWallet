from django.core.management.base import BaseCommand
from walletapp.models import Balances, Currencies, User


class Command(BaseCommand):
    help = "Fix balances below zero"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        # piaoran1573  19128 done
        # Norpeo  264 done
        # jianggaoyi  20465 done
        # rex 1312 done
        # yudian 5595 done
        # youzi2023 4917 done
        # pengkaijia 2348 done
        # a545120 25164 done
        # jianyang127614280
        # ivanlien 5273
        # lixinxin428@gmail.com 5262
        # huolea 892 done
        # dfinitysz@gmail.com 5250 done
        # shaocui7684fnht@gmail.com 5217 done 800
        # es5554424@gmail.com 5221 done
        # genius88 89 done
        # es5554424@gmail.com 5221 done 1600

        user_id_list = [14280, 5273, 5262, 892, 5250, 5217, 5217, 5221, 89, 5221, 5221]

        for user_id in user_id_list:
            user = User.objects.get(id=user_id)
            print(str(user.username) + str(user.id))
            currency = Currencies.objects.get(acronym="AC")
            currency_btc = Currencies.objects.get(acronym="SAT")

            balance_ac = Balances.objects.get(user=user, currency=currency)
            balance_btc = Balances.objects.get(user=user, currency=currency_btc)

            balance_ac.balance = balance_ac.balance + 800
            balance_ac.save()

            # print(balance_ac.balance)
            # print(balance_ac.pending_balance)

            # print(balance_btc.balance)
            # print(balance_btc.pending_balance)
