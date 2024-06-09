from ajax_select import LookupChannel, register

from .models import Currencies, Listings, User


@register("users")
class UsersLookup(LookupChannel):
    model = User

    def get_query(self, q, request):

        if q == "ALL":
            return self.model.objects.all.order_by("username")[:50]

        return self.model.objects.filter(username__startswith=q).order_by("username")[
            :50
        ]

    def format_item_display(self, item):
        return "<span class='tag'>%s</span>" % item.username

    def check_auth(self, request):
        True


@register("currencies")
class Currencies(LookupChannel):
    model = Currencies

    def get_query(self, q, request):

        if q == "ALL":
            return self.model.objects.all[:50]

        return self.model.objects.filter(name__startswith=q, is_nft=False).order_by(
            "name"
        )[:50]

    def format_item_display(self, item):
        return "<span class='tag'>%s</span>" % item.name

    def check_auth(self, request):
        True


@register("nfts")
class NftsLookup(LookupChannel):
    model = Currencies

    def get_query(self, q, request):

        if q == "ALL":
            return self.model.objects.all[:50]

        return self.model.objects.filter(name__startswith=q, is_nft=True).order_by(
            "name"
        )[:50]

    def format_item_display(self, item):
        return "<span class='tag'>%s</span>" % item.name

    def check_auth(self, request):
        True


@register("currencies_with_listing")
class CurrenciesWithListingLookup(LookupChannel):
    model = Currencies

    def get_query(self, q, request):

        if q == "ALL":
            return self.model.objects.filter(is_nft=False)[:50]

        listings = Listings.objects.filter(
            currency__name__startswith=q, currency__is_nft=False
        )[:50]

        return self.model.objects.filter(id__in=listings.values("currency_id"))

    def format_item_display(self, item):
        return "<span class='tag'>%s</span>" % item.name

    def check_auth(self, request):
        True


@register("nfts_with_listing")
class NftsWithListingLookup(LookupChannel):
    model = Currencies

    def get_query(self, q, request):

        if q == "ALL":
            return self.model.objects.filter(is_nft=True)[:50]

        listings = Listings.objects.filter(
            currency__name__startswith=q, currency__is_nft=True
        )[:50]

        return self.model.objects.filter(id__in=listings.values("currency_id"))

    def format_item_display(self, item):
        return "<span class='tag'>%s</span>" % item.name

    def check_auth(self, request):
        True
