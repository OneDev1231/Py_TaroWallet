import random
import string
import time

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Q
from walletapp.models import Balances, Currencies, Listings, Transactions
from walletapp.utils import get_currency_btc, get_pwd


def get_random_string(length):
    # choose from all lowercase letter
    letters = string.ascii_lowercase
    result_str = "".join(random.choice(letters) for i in range(length))
    print("Random string of length", length, "is:", result_str)
    return result_str


class Command(BaseCommand):
    help = "Initiate faucet accounts and other accounts"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        create_btc_currency()
        create_faucet_account()
        add_btc_to_all_users()


def create_btc_currency():
    if not Currencies.objects.filter(name="Bitcoin").exists():
        currency_btc = Currencies.objects.create(
            name="Bitcoin",
            owner=get_faucet_user(),
            picture_orig=None,
            acronym="SAT",
            description="Base currency",
            supply=21000000,
            status="minted",
        )

        currency_btc.save()


def get_faucet_user():
    if not User.objects.filter(username="faucet_user_1").exists():
        user1 = User.objects.create_user(
            username="faucet_user_1",
            password=get_pwd(),
        )

        user1.save()
    else:
        user1 = User.objects.get(username="faucet_user_1")

    return user1


def add_btc_to_all_users():
    user_list = User.objects.all()

    for user1 in user_list:
        if not Balances.objects.filter(
            user=user1, currency=get_currency_btc()
        ).exists():
            balance_btc = Balances.objects.create(
                user=user1, currency=get_currency_btc(), balance=5000
            )
            balance_btc.save()


def create_faucet_account():
    rand_str = get_random_string(4)
    # rand_str = "_b1"

    user1 = get_faucet_user()

    if not Balances.objects.filter(user=user1, currency=get_currency_btc()).exists():
        Balances.objects.create(user=user1, currency=get_currency_btc(), balance=50000)

    # name_list = [
    #     # "shitcoin",
    #     # "frogcoin",
    #     # "shiba inu on steroids",
    #     # "buttcoin",
    #     # "girlcoin",
    #     # "memecoin",
    #     # "jaba the hutt coin",
    #     # "pikachu coin",
    #     # "pokemon coin",
    #     # "anime coin",
    #     "waifu coin",
    #     # "MemeCoin",
    #     # "FedCoin",
    #     # "Bitcoinized dollar",
    #     # "Dollarized Bitcoin",
    #     # "Barbiecoin",
    #     # "Lambocoin",
    #     # "AdamCoin",
    #     # "Beckycoin",
    #     # "Bitcoin Trash",
    #     # "drone coin",
    #     # "Plus size coin",
    #     # "Karen coin",
    #     # "McDonalds coin",
    #     # "Burger King coin",
    #     "Clown coin",
    #     #  "Autism coin",
    #     #  "Minecraft coin",
    #     # "Tim Hortons coin",
    #     # "White trash coin",
    #     # "Jesus coin",
    #     # "Gandhi coin",
    #     # "Fun on a bun coin",
    #     # "Communism coin",
    #     # "Ecological coin",
    #     # "Fast food coin",
    #     # "Fart coin",
    #     "Roman Empire coin",
    # ]

    # for name in name_list:

    #     print(name)

    #     description = get_description(name)
    #     picture_orig_file = get_image(name)

    #     name_with_rand = (name + " " + rand_str).title().replace(" ", "")

    #     acronym = name[:4].upper()

    #     if not Currencies.objects.filter(name=name_with_rand).exists():
    #         my_coin = Currencies.objects.create(
    #             name=name_with_rand,
    #             owner=user1,
    #             picture_orig=None,
    #             acronym=acronym,
    #             description=description,
    #             supply=1000000,
    #             status="waiting_for_miting_transaction",
    #             is_nft=False,
    #         )

    #         cf = ContentFile(picture_orig_file.read())

    #         # cf = ContentFile(picture_orig.read())

    #         if my_coin.is_nft:
    #             filename = my_coin.name
    #         else:
    #             filename = my_coin.acronym

    #         my_coin.picture_orig.save(name=filename + ".png", content=cf)

    #         my_coin.save()

    # name_list = [
    #     # "a girl holding bitcoin",
    #     # "a girl cherishing a meme frog",
    #     # "a girl holding a shiba inu dog",
    #     # "decision to hold of sell crypto",
    #     # "a boy with diamond hands",
    #     # "a bitcoin whale",
    #     # "investor going to the moon",
    #     # "a rugpull",
    #     # "a girl investing in crypto",
    #     # "a hacker stealing bitcoin",
    #     # "a boy using lightning network",
    #     # "a meme coin",
    #     # "a shitcoin",
    #     # "a bitcoiner",
    #     # "a nocoiner",
    #     # "an etherhead",
    #     # "a long term hodler",
    #     # "a NFT",
    #     # "a crypto shill",
    #     # "buying lamborghini",
    #     # "a girl buying the dip",
    #     # "investing in dogecoin",
    #     # "investing in shiba inu",
    #     # "loosing money on NFTs",
    #     # "paper hands",
    #     # "normie",
    #     # "a stablecoin investor",
    #     # "a cyberpunk",
    #     # "a pudgy penguin",
    #     "Overly attached girlfriend",
    #     # "Karen from HR",
    #     # "good boi",
    #     # "Raptor Jesus",
    #     # "Fat Jesus",
    #     # "Nyan Cat",
    #     # "Bitcoin shrimp",
    #     # "Unicorn startup",
    #     # "Soy software developer",
    #     # "Alyx from Half life",
    #     # "Rei Ayanami",
    #     "Captain Sweden",
    #     # "Captain Canada",
    #     # "Elon Tusk",
    #     # "Negative Nancy",
    #     # "TempleOS",
    #     # "Gamer girl",
    #     # "Hamburglar",
    #     # "McDonald Szechuan sauce",
    #     # "Eurotrash",
    #     # "Rust programming language",
    #     # "Pythonista",
    #     # "Aggressive Karen",
    #     "Final boss",
    #     # "Earth-chan",
    #     # "Soyboy",
    #     # "Rare Pepe",
    #     # "Greta Thunberg",
    #     # "Positive Peter",
    #     # "Fart in a jar",
    #     # "Reptilian conspiracy",
    #     # "A Pigdog",
    #     # "Thinking about Roman empire",
    #     # "Eating tide pods",
    #     # "Farting in the wind",
    #     # "Sam Bankman Fraud",
    #     # "Quesadillasaur",
    # ]

    # for name in name_list:

    #     print(name)

    #     description = get_description(name)
    #     picture_orig_file = get_image(name)

    #     name_with_rand = (name + " " + rand_str).title().replace(" ", "")

    #     if not Currencies.objects.filter(name=name_with_rand).exists():
    #         my_nft = Currencies.objects.create(
    #             name=name_with_rand,
    #             owner=user1,
    #             picture_orig=None,
    #             description=description,
    #             supply=1,
    #             status="waiting_for_miting_transaction",
    #             is_nft=True,
    #         )

    #     # with open(
    #     #     f"walletapp/static/assets/images/gcp-file.jpg", "wb"
    #     # ) as picture_orig:
    #     #     picture_orig.write(picture_orig_file.getvalue())

    #     # with open(
    #     #     f"walletapp/static/assets/images/gcp-file.jpg", "rb"
    #     # ) as picture_orig:

    #     cf = ContentFile(picture_orig_file.read())

    #     # cf = ContentFile(picture_orig.read())

    #     if my_nft.is_nft:
    #         filename = my_nft.name
    #     else:
    #         filename = my_nft.acronym

    #     my_nft.picture_orig.save(name=filename + ".png", content=cf)

    #     my_nft.save()

    # for listing in Listings.objects.all():
    #     listing.delete()

    currencies = Currencies.objects.filter(~Q(name="Bitcoin"), owner=get_faucet_user())

    for currency in currencies:
        if currency.status != "minted":
            continue

        if Listings.objects.filter(currency=currency).exists():
            print("Currency is already listed...")
            continue

        username = "user_" + currency.name.replace(" ", "_").lower()
        print(username)
        if not User.objects.filter(username=username).exists():
            user1 = User.objects.create_user(
                username=username,
                email="adam.ivansky@gmail.com",
                password=get_pwd(),
            )
            user1.save()
        else:
            user1 = User.objects.get(username=username)

        # if Listings.objects.filter(currency=currency, user=user1).exists():
        #     listing = Listings.objects.get(currency=currency, user=user1)
        #     listing.delete()

        if currency.is_nft:
            price_sat = int(random.random() * 1000)

            listing = Listings.objects.create(
                currency=currency, user=get_faucet_user(), price_sat=price_sat
            )
            listing.save()

        else:
            if (
                Balances.objects.get(user=get_faucet_user(), currency=currency).balance
                < 3
            ):
                continue

            amount_to_send = Balances.objects.get(
                user=get_faucet_user(), currency=currency
            ).balance
            amount_to_send = amount_to_send / 2

            transaction = Transactions.objects.create(
                user=get_faucet_user(),
                direction="outbound",
                type="internal",
                status="internal_stated",
                destination_user=user1,
                currency=currency,
                amount=amount_to_send,
            )
            transaction.save()

            transaction = Transactions.objects.create(
                user=get_faucet_user(),
                direction="outbound",
                type="internal",
                status="internal_stated",
                destination_user=user1,
                currency=get_currency_btc(),
                amount=3000,
            )
            transaction.save()

            while transaction.status == "internal_stated":
                transaction.refresh_from_db()
                print(f"Transaction status = {transaction.status}, waiting...")
                time.sleep(1)

            print(transaction.user)
            print(transaction.direction)
            print(transaction.type)
            print(transaction.amount)
            print(transaction.destination_user)
            print(transaction.status)

            print(Balances.objects.get(user=user1, currency=currency).balance)

            listing = Listings.objects.create(currency=currency, user=user1)
            print(listing.get_price_sat())
            listing.save()
