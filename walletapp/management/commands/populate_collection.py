from django.core.management.base import BaseCommand
from walletapp.models import Collections, Currencies
from walletapp.utils import get_faucet_user


def get_collection(name):
    if not Collections.objects.filter(name=name):
        collection = Collections.objects.create(
            name=name,
            description=(
                "A taproot NFT collection focusing on animals wearing VR headsets"
            ),
            owner=get_faucet_user(),
        )
        collection.save()
    else:
        collection = Collections.objects.get(name=name)

    return collection


class Command(BaseCommand):
    help = "Populate collections"

    def handle(self, *args, **options):
        coll_dict = {}

        for name in [
            "VRA",
            "TaprootRocks",
            "TaprootCans",
            "TaprootApes",
            "Punks",
            "PlanetaryRoots",
        ]:
            coll_dict[name] = get_collection(name)

        # collection_roots = Collections.objects.create(name="Roots", description='A taproot NFT collection focusing on animals wearing VR headsets', owner=get_faucet_user() )
        # collection_roots.save()

        curr_list = Currencies.objects.filter(is_nft=True)

        for curr in curr_list:
            for name, coll in coll_dict.items():
                if curr.name.lower().startswith(name.lower()[:-1]):
                    print(
                        f"Assigning collection {coll.name} to currency {curr.name} -"
                        f" starts with {name.lower()[:-1]}"
                    )
                    curr.collection = coll
                    curr.save()
