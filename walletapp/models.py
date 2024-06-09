import os
import sys

from django.contrib.auth.models import User
from django.contrib.postgres.indexes import HashIndex
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, transaction
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.templatetags.static import static
from django.urls import reverse
from django.utils.timezone import now
from django_s3_storage.storage import S3Storage

from .const_utils import (
    get_fee_sat_estimate_exchange,
    get_fee_sat_estimate_lnd,
    get_fee_sat_estimate_onchain,
    get_final_fee,
    get_initial_free_btc_balance,
)
from .utils import (
    get_fee_user,
    get_free_amount_user,
    get_media_images_zip_file,
    get_media_path_large,
    get_media_path_orig,
    get_media_path_small,
    get_wash_users,
    resize_image_field,
)


class BalanceException(Exception):
    pass


if "test" in sys.argv:
    from tempfile import mkdtemp

    storage = FileSystemStorage(location=mkdtemp(), base_url="/")
else:
    DEV_ENV = os.getenv("DEV_ENV")
    if DEV_ENV == "DEV" or "test" in sys.argv:
        storage = S3Storage(aws_s3_bucket_name="django-images-testnet")
    elif DEV_ENV == "PROD":
        storage = S3Storage(aws_s3_bucket_name="django-images-prod")

alphanumeric = RegexValidator(
    r"^[0-9a-zA-Z]*$", "Only alphanumeric characters are allowed."
)


def get_btc_balance(self):
    return Balances.objects.get(
        user=self, currency=Currencies.objects.get(name="Bitcoin", acronym="SAT")
    ).balance


def get_btc_pending_balance(self):
    return Balances.objects.get(
        user=self, currency=Currencies.objects.get(name="Bitcoin")
    ).pending_balance


def get_currencies(self, currency=None):
    if currency:
        return [
            balance.currency
            for balance in Balances.objects.filter(user=self, currency=currency)
        ]
    else:
        return [balance.currency for balance in Balances.objects.filter(user=self)]


def get_currencies_dont_have(self):
    return Currencies.objects.filter(
        ~Q(id__in=[bal.currency.id for bal in Balances.objects.filter(user=self)])
    )


def get_currencies_str_list(self):
    return ",".join(
        [balance.currency.name for balance in Balances.objects.filter(user=self)]
    )


def get_balances(self, currency=None):
    if currency:
        return Balances.objects.get(user=self, currency=currency)
    else:
        return Balances.objects.filter(user=self, balance__gt=0)


def get_unread_notifications(self, max_notifications=10):

    return Notifications.objects.filter(destination_user=self).order_by(
        "read", "-created_timestamp"
    )[:max_notifications]


def get_unread_notifications_num(self):

    return len(Notifications.objects.filter(destination_user=self, read=False))


User.add_to_class("get_btc_balance", get_btc_balance)
User.add_to_class("get_btc_pending_balance", get_btc_pending_balance)
User.add_to_class("get_currencies", get_currencies)
User.add_to_class("get_currencies_str_list", get_currencies_str_list)
User.add_to_class("get_currencies_dont_have", get_currencies_dont_have)
User.add_to_class("get_balances", get_balances)
User.add_to_class("get_unread_notifications", get_unread_notifications)
User.add_to_class("get_unread_notifications_num", get_unread_notifications_num)


@transaction.atomic
def initiate_balances_from_files(file_list, collection, user, info_list=None):
    data = [
        Currencies(
            name=info_list[i]["name"]
            if info_list
            else collection.name + file.name.split(".")[0],
            description=info_list[i]["description"]
            if info_list
            else collection.description,
            owner=user,
            is_nft=True,
            collection=collection,
            status="waiting_for_miting_transaction",
            supply=1,
            picture_orig=file,
        )
        for i, file in enumerate(file_list)
    ]
    currs = Currencies.objects.bulk_create(data)
    for curr in currs:
        initiate_balances(created=True, instance=curr, sender=None)


@receiver(post_save, sender=User)
@transaction.atomic
def initiate_balances_for_user(sender, instance, created, **kwargs):
    if created:
        if not Currencies.objects.filter(name="Bitcoin").exists():
            currency_BTC = Currencies.objects.create(
                name="Bitcoin",
                acronym="SAT",
                description="Bitcoin currency",
                status="minted",
            )
            currency_BTC.save()

        currency_BTC = Currencies.objects.get(name="Bitcoin")

        balance_btc = Balances.objects.create(
            user=instance, currency=currency_BTC, balance=0
        )
        balance_btc.save()

        free_amount_user = get_free_amount_user()

        if free_amount_user.get_btc_balance() > get_initial_free_btc_balance():
            transaction = Transactions.objects.create(
                user=free_amount_user,
                direction="outbound",
                type="internal",
                status="internal_stated",
                destination_user=instance,
                currency=currency_BTC,
                amount=get_initial_free_btc_balance(),
            )
            transaction.save()


class Collections(models.Model):
    name = models.CharField(
        help_text="Collection name",
        max_length=30,
        validators=[alphanumeric],
        null=False,
        unique=True,
    )

    description = models.CharField(
        help_text=(
            "Short description of the collection, include founder contact"
            " information, explain purpose of this collection - what is its story?"
        ),
        max_length=200,
        default="",
    )

    COLLECTION_STATUS = (
        ("waiting_for_miting_transactions", "Waiting for minting transactions"),
        ("minted", "Minted"),
        ("error", "Error"),
    )

    status = models.CharField(
        max_length=50,
        choices=COLLECTION_STATUS,
        default="minted",
        help_text="Status of the minting transaction",
    )

    images_zip_file = models.FileField(
        help_text="Where to upload zip file containing collection",
        storage=storage,
        upload_to=get_media_images_zip_file,
        null=True,
        blank=True,
    )

    owner = models.ForeignKey(
        User,
        help_text="Owner of the collection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    volume = models.IntegerField(
        help_text="Volume of the collection traded in last 1 hour",
        default=0,
        null=True,
        blank=True,
    )

    transaction_num = models.IntegerField(
        help_text="Number of transactions done with the collection in last 1 hour",
        default=0,
        null=True,
        blank=True,
    )

    holders_num = models.IntegerField(
        help_text="Number of holders of the collection",
        default=0,
        null=True,
        blank=True,
    )

    orders_num = models.IntegerField(
        help_text="Number of orders on the collection",
        default=0,
        null=True,
        blank=True,
    )

    # created_timestamp = models.DateTimeField(auto_now_add=True)
    # updated_timestamp = models.DateTimeField(auto_now_add=True)
    created_timestamp = models.DateTimeField(default=now)
    updated_timestamp = models.DateTimeField(default=now)

    def get_assets(self, max_num=None):
        if max_num:
            return Currencies.objects.filter(collection=self)[:max_num]
        else:
            return Currencies.objects.filter(collection=self)

    def get_absolute_url(self):
        """Returns the URL to access a particular instance of MyModelName."""
        return reverse("currencies-nfts") + "?collection=" + self.name

    def get_absolute_public_url(self):
        """Returns the URL to access a particular instance of MyModelName."""
        return reverse("public-currencies") + "?asset_type=nft&collection=" + self.name

    def get_image_url_name(self):
        assets_in_collection = self.get_assets()
        if len(assets_in_collection) > 0:
            # return assets_in_collection[0].get_image_url_name()
            return reverse("collection-detail-preview-image", args=[str(self.id), 3])
        else:
            return None

    def get_preview_image_url(self):

        return reverse("collection-detail-preview-image", args=[str(self.id), 6])

    def get_preview_image_gif_url(self):

        return reverse("collection-detail-preview-gif-image", args=[str(self.id), 35])

    def get_color_id(self):
        """Returns the URL to access a particular instance of MyModelName."""
        return str(self.id % 7 + 1)

    class Meta:
        ordering = ["-holders_num"]

        constraints = [
            models.UniqueConstraint(fields=["name"], name="collection_name_unique"),
        ]


class Currencies(models.Model):
    name = models.CharField(
        help_text="Cryptocurrency name represented as word. e.g. Bitcoin, Ethereum",
        max_length=30,
        validators=[alphanumeric],
    )

    owner = models.ForeignKey(
        User,
        help_text="Owner of the asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    collection = models.ForeignKey(
        Collections,
        help_text="Collection the asset belongs to",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    picture_small = models.ImageField(
        help_text="Large icon representing the asset",
        storage=storage,
        upload_to=get_media_path_small,
        null=True,
        blank=True,
    )

    picture_large = models.ImageField(
        help_text="Small icon representing the asset",
        storage=storage,
        upload_to=get_media_path_large,
        null=True,
        blank=True,
    )
    picture_orig = models.ImageField(
        help_text=(
            "Image representing the asset. Please upload a square image about 800x800"
            " in size. Images will be rescaled."
        ),
        storage=storage,
        upload_to=get_media_path_orig,
        null=True,
        blank=True,
    )

    acronym = models.CharField(
        help_text="Asset acronym represented as 1 to 5 letters. e.g. ETH, BTC",
        max_length=5,
        unique=False,
        validators=[alphanumeric],
    )

    asset_id = models.CharField(
        help_text="Id of the asset. Required for creating an invoice.",
        max_length=50000,
        default="",
    )

    universe_host = models.CharField(
        help_text="Universe host associated with the currency.",
        max_length=50000,
        default="",
        null=True,
        blank=True,
    )

    minting_transaction = models.ForeignKey(
        "Transactions",
        help_text="Minting transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    description = models.CharField(
        help_text=(
            "Short description of the asset, include founder contact"
            " information, explain purpose of this currency - it is a stablecoin? a"
            " pegged coin ? "
        ),
        max_length=200,
        default="",
    )

    internal_key = models.CharField(
        help_text="Internal batch key of the asset if minted",
        default="",
        max_length=100,
        null=True,
        blank=True,
    )

    supply = models.BigIntegerField(
        help_text="Total supply of the asset once minted",
        default=1,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(2**32),
        ],
    )

    volume = models.IntegerField(
        help_text="Volume of the asset traded in last 1 day",
        default=0,
        null=True,
        blank=True,
    )

    transaction_num = models.IntegerField(
        help_text="Number of transactions done with the asset in last 1 day",
        default=0,
        null=True,
        blank=True,
    )

    holders_num = models.IntegerField(
        help_text="Number of holders of the assets",
        default=0,
        null=True,
        blank=True,
    )

    orders_num = models.IntegerField(
        help_text="Number of orders on the assets",
        default=0,
        null=True,
        blank=True,
    )

    price_change = models.IntegerField(
        help_text="Price change in the past 1 hour",
        default=0,
        null=True,
        blank=True,
    )

    is_nft = models.BooleanField(
        help_text="Indicates if the asset is a NFT or not",
        default=False,
        null=True,
        blank=True,
    )

    CURRENCY_STATUS = (
        ("waiting_for_miting_transaction", "Waiting for minting transaction"),
        ("submitted_for_minting", "Submitted for minting"),
        ("minting", "Minting"),
        ("minted", "Minted"),
        ("error", "Error"),
        ("waiting_for_meta_data", "Waiting for metadata"),
        ("waiting_for_create_transaction", "Waiting for create transaction"),
        ("minted", "Minted"),
    )

    status = models.CharField(
        max_length=50,
        choices=CURRENCY_STATUS,
        default="",
        help_text="Status of the minting transaction",
    )

    class Meta:

        indexes = (
            HashIndex(fields=("name",)),
            HashIndex(fields=("collection",)),
            HashIndex(fields=("asset_id",)),
            HashIndex(fields=("acronym",)),
            HashIndex(fields=("owner",)),
            HashIndex(fields=("is_nft",)),
            HashIndex(fields=("status",)),
            HashIndex(fields=("holders_num",)),
            models.Index(fields=["status", "is_nft", "holders_num"]),
        )

        constraints = [
            models.CheckConstraint(
                name="suppy_for_nft_assets_has_to_be_one",
                check=(
                    models.Q(is_nft=True, supply=1)
                    | models.Q(is_nft=False, supply__gt=0)
                ),
            ),
            models.UniqueConstraint(fields=["is_nft", "name"], name="name_unique"),
        ]
        ordering = ["-holders_num", "-orders_num"]

    created_timestamp = models.DateTimeField(auto_now_add=True)
    updated_timestamp = models.DateTimeField(auto_now_add=True)

    # Methods
    def get_absolute_url(self):
        """Returns the URL to access a particular instance of MyModelName."""
        return reverse("currency-detail", args=[str(self.id)])

    def get_absolute_public_url(self):
        """Returns the URL to access a particular instance of MyModelName."""
        return reverse("currency-detail-public", args=[str(self.id)])

    def get_minting_url(self):
        """Returns the URL to access a particular instance of MyModelName."""
        return reverse("transaction-detail", args=[str(self.id)])

    def get_preview_image_url(self):
        """Returns the URL to access a particular instance of MyModelName."""
        return reverse("currency-detail-preview-image", args=[str(self.id)])

    def __str__(self):
        """String for representing the MyModelName object (in Admin site etc.)."""
        return self.name

    def get_image_url_name(self):
        """Returns the URL to access a particular instance of MyModelName."""
        if self.name == "Bitcoin":
            return static("assets/images/btc.png")
        elif self.picture_small:
            return self.picture_small.url
        else:
            return static("assets/images/unknown_currency.png")

    def get_image_url_name_large(self):
        """Returns the URL to access a particular instance of MyModelName."""
        if self.name == "Bitcoin":
            return static("assets/images/btc.png")
        elif self.picture_large:
            return self.picture_large.url
        else:
            return static("assets/images/unknown_currency.png")

    def get_color_id(self):
        """Returns the URL to access a particular instance of MyModelName."""
        return str(self.id % 7 + 1)

    def get_market_cap(self):
        """Returns the URL to access a particular instance of MyModelName."""
        if Listings.objects.filter(currency=self.id, type="lp").exists():
            lp_listing = Listings.objects.get(currency=self.id, type="lp")
            return lp_listing.get_price_sat() * self.supply
        else:
            return None

    def get_lp_listing(self):
        """Returns the URL to access a particular instance of MyModelName."""
        if Listings.objects.filter(currency=self.id, type="lp").exists():
            return Listings.objects.get(currency=self.id, type="lp")
        else:
            return None

    def get_bid_orders(self):
        """Returns the URL to access a particular instance of MyModelName."""
        return Listings.objects.filter(currency=self.id, type="order_bid").order_by(
            "-price_sat"
        )[0:10]

    def get_ask_orders(self):
        """Returns the URL to access a particular instance of MyModelName."""
        return Listings.objects.filter(currency=self.id, type="order_ask").order_by(
            "price_sat"
        )[0:10]

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if not self.picture_orig:
            print("no image")
            self.picture_small = None
            self.picture_large = None
        else:
            picture_small = resize_image_field(
                self.picture_orig, 160, 160, apply_mask=not (self.is_nft)
            )
            picture_large = resize_image_field(
                self.picture_orig, 800, 800, apply_mask=not (self.is_nft)
            )

            if self.is_nft:
                filename = self.name
            else:
                filename = self.acronym

            cf = ContentFile(picture_large.getvalue())
            self.picture_large.save(name=filename + ".png", content=cf, save=False)

            cf = ContentFile(picture_small.getvalue())
            self.picture_small.save(name=filename + ".png", content=cf, save=False)

        state_adding = self._state.adding

        super(Currencies, self).save(force_insert, force_update, using, update_fields)


@receiver(post_save, sender=Currencies)
@transaction.atomic
def initiate_balances(sender, instance, created, **kwargs):
    if created:
        if (instance.name != "Bitcoin") and (
            instance.status == "waiting_for_miting_transaction"
        ):
            print("creating balance...")

            new_balance = Balances.objects.create(
                user=instance.owner, currency=instance, balance=0
            )
            new_balance.save()

            print("creating transaction...")

            minting_transaction = Transactions.objects.create(
                user=instance.owner,
                currency=instance,
                amount=instance.supply,
                description=f"Minting of currency {instance.name}",
                direction="inbound",
                status="minting_submitted",
                type="minting",
            )
            minting_transaction.save()

            instance.status = "submitted_for_minting"
            instance.minting_transaction = minting_transaction
            instance.save()

        if (instance.name != "Bitcoin") and (
            instance.status == "waiting_for_create_transaction"
        ):
            print("creating balance...")

            new_balance = Balances.objects.create(
                user=instance.owner, currency=instance, balance=0
            )
            new_balance.save()

            print("creating transaction...")

            minting_transaction = Transactions.objects.create(
                user=instance.owner,
                currency=instance,
                amount=0,
                description=f"Minting of currency {instance.name}",
                direction="inbound",
                status="waiting_for_meta_data",
                type="register_currency",
            )
            minting_transaction.save()

            instance.status = "waiting_for_meta_data"
            instance.minting_transaction = minting_transaction
            instance.save()


class Balances(models.Model):
    user = models.ForeignKey(
        User,
        help_text="Owner of the wallet",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    currency = models.ForeignKey(
        Currencies,
        help_text="Wallet currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    balance = models.IntegerField(
        help_text="Wallet balance", default=0, validators=[MinValueValidator(0)]
    )

    pending_balance = models.IntegerField(
        help_text="Pending wallet balance", default=0, validators=[MinValueValidator(0)]
    )

    created_timestamp = models.DateTimeField(auto_now_add=True)
    updated_timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (
            "user",
            "currency",
        )


class Transactions(models.Model):
    """A typical class defining a model, derived from the Model class."""

    user = models.ForeignKey(
        User,
        related_name="owner",
        help_text="User who executed the transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    invoice_inbound = models.CharField(
        help_text="Inbound Taproot Asset invoice",
        max_length=5000,
        null=True,
        blank=True,
    )

    invoice_outbound = models.CharField(
        help_text="Outbound Taproot Asset invoice",
        max_length=5000,
        null=True,
        blank=True,
    )

    tx_id = models.CharField(
        help_text="Transaction ID",
        max_length=5000,
        unique=False,
        null=True,
        blank=True,
    )

    description = models.CharField(
        help_text="Transaction description",
        max_length=150,
        default="",
        null=True,
        blank=True,
    )

    amount = models.IntegerField(
        help_text="Currency amount",
        default=0,
        validators=[MinValueValidator(1)],
        null=False,
    )

    balance = models.IntegerField(
        help_text="User balance",
        default=0,
        validators=[MinValueValidator(0)],
        null=False,
    )

    pending_balance = models.IntegerField(
        help_text="User pending balance",
        default=0,
        validators=[MinValueValidator(0)],
        null=False,
    )
    # balance = models.IntegerField(
    #     help_text="Balance at the time of purchase",
    #     default=0,
    #     validators=[MinValueValidator(0)],
    #     null=False,
    # )

    # pending_balance = models.IntegerField(
    #     help_text="Pending balance at the time of transaction",
    #     default=0,
    #     validators=[MinValueValidator(0)],
    #     null=False,
    # )

    currency = models.ForeignKey(
        Currencies,
        help_text="Transaction currency",
        on_delete=models.PROTECT,
        null=False,
        blank=True,
    )

    listing = models.ForeignKey(
        "Listings",
        help_text="Listing the transaction is executed from.",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    fee_transaction = models.ForeignKey(
        "Transactions",
        help_text="Fee transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    associated_exchange_transaction = models.ForeignKey(
        "Transactions",
        related_name="exchange_transaction",
        help_text="Associated exchange transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    TRANSACTION_TYPE = (
        ("user", "User Transaction"),
        ("internal", "Internal Transaction"),
        ("fee", "Fee"),
        ("minting", "Minting transaction"),
        ("exchange", "Exchange"),
        ("register_currency", "Register new asset"),
    )

    type = models.CharField(
        max_length=50,
        choices=TRANSACTION_TYPE,
        default="",
        help_text="Transaction type",
    )

    TRANSACTION_DIRECTION = (
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    )

    direction = models.CharField(
        max_length=50,
        choices=TRANSACTION_DIRECTION,
        default="",
        help_text="Transaction direction",
    )

    created_timestamp = models.DateTimeField(auto_now_add=True)
    updated_timestamp = models.DateTimeField(auto_now_add=True)

    TRANSACTION_STATUS = (
        (
            "lnd_inbound_invoice_waiting_for",
            "Waiting for inbound lighting invoice to be generated",
        ),
        (
            "lnd_inbound_invoice_generated",
            "Inbound lighting invoice was generated, waiting for it to be paid",
        ),
        ("lnd_inbound_invoice_paid", "Inbound lighting invoice was successfully paid"),
        (
            "lnd_outbound_invoice_received",
            "Outbound lighting invoice is waiting to be paid",
        ),
        (
            "lnd_outbound_invoice_submitted",
            "Outbound lighting invoice has been submitted and is now processing",
        ),
        ("lnd_outbound_invoice_paid", "Outbound lighting invoice paid"),
        (
            "inbound_invoice_waiting_for",
            "Waiting for inbound invoice to be generated",
        ),
        (
            "inbound_invoice_generated",
            "Inbound invoice was generated, waiting for it to be paid",
        ),
        ("inbound_invoice_paid", "Inbound invoice was successfully paid"),
        (
            "outbound_invoice_received",
            "Outbound invoice is waiting to be paid",
        ),
        ("outbound_invoice_paid", "Outbound invoice paid"),
        ("placeholder_fee", "Placeholder fee, real amount will be added"),
        ("fee_paid", "Fee paid"),
        ("minting_submitted", "Currency submitted for minting"),
        ("minting", "Currency is minting"),
        ("tx_created", "Minting transaction created"),
        ("minted", "Minting transaction was completed"),
        ("internal_stated", "Internal transaction submitted"),
        ("internal_finished", "Internal transaction finished"),
        ("exchange_started", "Exchange transaction submitted"),
        ("exchange_finished", "Exchange transaction finished"),
        (
            "replaced_with_internal_transaction",
            "This transaction was replaced with internal transaction to save fees",
        ),
        ("waiting_for_meta_data", "Waiting for currency metadata"),
        (
            "currency_registration_finished",
            "Registration of a new currency is finished.",
        ),
        ("error", "Error"),
    )

    status = models.CharField(
        help_text="Transaction status",
        max_length=50,
        choices=TRANSACTION_STATUS,
        default="",
    )

    status_description = models.CharField(
        help_text="Transaction status detail",
        max_length=500,
        default="",
        null=True,
        blank=True,
    )

    destination_user = models.ForeignKey(
        User,
        help_text="Internal user who has received the transaction",
        related_name="user2user",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # Metadata
    class Meta:
        ordering = ["-updated_timestamp"]

        indexes = (
            HashIndex(fields=("invoice_inbound",)),
            HashIndex(fields=("invoice_outbound",)),
        )

        constraints = [
            # Check status consistency
            models.CheckConstraint(
                check=(
                    models.Q(
                        type="user",
                        direction="inbound",
                        status="lnd_inbound_invoice_waiting_for",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="user",
                        direction="inbound",
                        status="lnd_inbound_invoice_generated",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=False,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="user",
                        direction="inbound",
                        status="lnd_inbound_invoice_paid",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=False,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="user",
                        direction="outbound",
                        status="lnd_outbound_invoice_submitted",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=False,
                    )
                    | models.Q(
                        type="user",
                        direction="outbound",
                        status="lnd_outbound_invoice_received",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=False,
                    )
                    | models.Q(
                        type="user",
                        direction="outbound",
                        status="lnd_outbound_invoice_paid",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=False,
                    )
                    | models.Q(
                        type="user",
                        direction="inbound",
                        status="inbound_invoice_waiting_for",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="user",
                        direction="inbound",
                        status="inbound_invoice_generated",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=False,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="user",
                        direction="inbound",
                        status="inbound_invoice_paid",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=False,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="user",
                        direction="outbound",
                        status="outbound_invoice_received",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=False,
                    )
                    | models.Q(
                        type="user",
                        direction="outbound",
                        status="outbound_invoice_paid",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=False,
                    )
                    | models.Q(
                        type="fee",
                        direction="outbound",
                        status="placeholder_fee",
                        destination_user__isnull=False,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="fee",
                        direction="outbound",
                        status="placeholder_fee",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="fee",
                        direction="outbound",
                        status="fee_paid",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="fee",
                        direction="outbound",
                        status="fee_paid",
                        destination_user__isnull=False,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="minting",
                        direction="inbound",
                        status="minting_submitted",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="minting",
                        direction="inbound",
                        status="minting",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="minting",
                        direction="inbound",
                        status="tx_created",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="minting",
                        direction="inbound",
                        status="minted",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="internal",
                        direction="outbound",
                        status="internal_stated",
                        destination_user__isnull=False,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="internal",
                        direction="outbound",
                        status="internal_finished",
                        destination_user__isnull=False,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="exchange",
                        direction="outbound",
                        status="exchange_started",
                        destination_user__isnull=False,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="exchange",
                        direction="outbound",
                        status="exchange_finished",
                        destination_user__isnull=False,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="exchange",
                        direction="inbound",
                        status="exchange_started",
                        destination_user__isnull=False,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="exchange",
                        direction="inbound",
                        status="exchange_finished",
                        destination_user__isnull=False,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="user",
                        direction="inbound",
                        status="replaced_with_internal_transaction",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=False,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="register_currency",
                        direction="inbound",
                        status="waiting_for_meta_data",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(
                        type="register_currency",
                        direction="inbound",
                        status="currency_registration_finished",
                        destination_user__isnull=True,
                        invoice_inbound__isnull=True,
                        invoice_outbound__isnull=True,
                    )
                    | models.Q(status="error")
                ),
                name="check_transaction_status_consistency",
            )
        ]

    # Methods
    def get_absolute_url(self):
        """Returns the URL to access a particular instance of MyModelName."""
        return reverse("transaction-detail", args=[str(self.id)])

    def __str__(self):
        """String for representing the MyModelName object (in Admin site etc.)."""
        return f"Transaction {self.id}"

    def get_sgn(self):
        if self.direction == "inbound":
            return -1
        elif self.direction == "outbound":
            return 1
        else:
            raise Exception(f"Unknown direction '{self.direction}'")

    @transaction.atomic
    def update_amt(self, amt_new):
        balance = Balances.objects.select_for_update().get(
            user=self.user, currency=self.currency
        )

        if self.direction == "outbound":
            balance.balance = balance.balance + self.amount * self.get_sgn()
            balance.pending_balance = (
                balance.pending_balance - self.amount * self.get_sgn()
            )

            balance.balance = balance.balance - amt_new * self.get_sgn()
            balance.pending_balance = balance.pending_balance + amt_new * self.get_sgn()

            balance.save()

        self.amount = amt_new
        self.save()

    @transaction.atomic
    def finalize_fee(self, amt_onchain_fee: int = None):
        fee_transaction = self.fee_transaction
        if fee_transaction:
            if amt_onchain_fee:
                currency_BTC = Currencies.objects.get(name="Bitcoin")
                if (
                    self.direction == "outbound"
                    and self.currency == currency_BTC
                    and self.type == "user"
                ):
                    amt_new = get_final_fee(amt_onchain_fee, self.amount)
                else:
                    amt_new = get_final_fee(amt_onchain_fee)

                fee_transaction.update_amt(amt_new)

            fee_transaction.status = "fee_paid"
            fee_transaction.save()

            self.fee_transaction.finalize()

    @transaction.atomic
    def initiate(self):

        self.log_transaction_status("Initialize started")

        if self.direction == "outbound":

            if not Balances.objects.filter(
                user=self.user, currency=self.currency
            ).exists():
                balance = Balances.objects.create(
                    user=self.user, currency=self.currency
                )
                balance.save()

            balance = Balances.objects.select_for_update().get(
                user=self.user, currency=self.currency
            )

            print(
                f"Initiate start: User {self.user.id} balance {balance.balance},"
                f" pending balance {balance.pending_balance},"
                f" {balance.currency.name} -> {self.amount}"
            )

            if (balance.balance - self.amount * self.get_sgn()) < 0:
                raise BalanceException(
                    f"The user {self.user.id} with original balance of"
                    f" {balance.currency.name} {balance.balance} has new balance of"
                    f" {(balance.balance - self.amount * self.get_sgn())} which is"
                    " smaller than zero."
                )

            if (balance.pending_balance + self.amount * self.get_sgn()) < 0:
                raise BalanceException(
                    f"The user {self.user.id} with original pending balance of"
                    f" {balance.currency.name} {balance.pending_balance} has new"
                    " pending balance of"
                    f" {(balance.pending_balance + self.amount * self.get_sgn())} which"
                    " is smaller than zero."
                )
            balance.pending_balance = (
                balance.pending_balance + self.amount * self.get_sgn()
            )

            balance.balance = balance.balance - self.amount * self.get_sgn()

            self.balance = balance.balance
            self.pending_balance = balance.pending_balance

            balance.save()

        elif self.direction == "inbound" and self.destination_user:

            if not Balances.objects.filter(
                user=self.destination_user, currency=self.currency
            ).exists():
                balance = Balances.objects.create(
                    user=self.destination_user, currency=self.currency
                )
                balance.save()

            balance = Balances.objects.select_for_update().get(
                user=self.destination_user, currency=self.currency
            )

            print(
                f"Initiate start: User {self.destination_user.id} balance"
                f" {balance.balance}, pending balance {balance.pending_balance},"
                f" {balance.currency.name} <- {self.amount}"
            )

            if (balance.balance + self.amount * self.get_sgn()) < 0:
                raise BalanceException(
                    f"The user {self.destination_user.id} with original balance"
                    f" {balance.currency.name} {balance.balance} has new balance of"
                    f" {(balance.balance + self.amount * self.get_sgn())} which is"
                    " smaller than zero."
                )

            if (balance.pending_balance - self.amount * self.get_sgn()) < 0:
                raise BalanceException(
                    f"The user {self.destination_user.id} with original pending balance"
                    f" {balance.currency.name} {balance.pending_balance} has new"
                    " pending balance of"
                    f" {(balance.pending_balance - self.amount * self.get_sgn())} which"
                    " is smaller than zero."
                )

            balance.pending_balance = (
                balance.pending_balance - self.amount * self.get_sgn()
            )

            balance.balance = balance.balance + self.amount * self.get_sgn()

            self.balance = balance.balance
            self.pending_balance = balance.pending_balance

            balance.save()

        self.add_fees_and_assoc_trans()

        self.log_transaction_status("Initialize finished")

    @transaction.atomic
    def finalize(self):

        self.log_transaction_status("Finalize started")

        if not Balances.objects.filter(user=self.user, currency=self.currency).exists():
            balance = Balances.objects.create(
                user=self.user, currency=self.currency, balance=0
            )
            balance.save()

        balance = Balances.objects.select_for_update().get(
            user=self.user, currency=self.currency
        )

        if self.type in ["internal", "exchange"] or (
            self.type == "fee" and self.destination_user
        ):
            if not Balances.objects.filter(
                user=self.destination_user, currency=self.currency
            ).exists():
                destination_user_balance = Balances.objects.create(
                    user=self.destination_user, currency=self.currency, balance=0
                )
                destination_user_balance.save()

            destination_user_balance = Balances.objects.select_for_update().get(
                user=self.destination_user, currency=self.currency
            )

            if self.direction == "inbound":

                if (
                    destination_user_balance.pending_balance
                    + self.amount * self.get_sgn()
                    < 0
                ):

                    raise BalanceException(
                        f"The user {self.destination_user.id} with original pending"
                        " balance"
                        f" {destination_user_balance.currency.name} {destination_user_balance.pending_balance} has"
                        " new pending balance of"
                        f" {destination_user_balance.pending_balance + self.amount * self.get_sgn()} which"
                        " is smaller than zero."
                    )

                destination_user_balance.pending_balance = (
                    destination_user_balance.pending_balance
                    + self.amount * self.get_sgn()
                )
            else:
                if (
                    destination_user_balance.balance + self.amount * self.get_sgn()
                ) < 0:
                    raise BalanceException(
                        f"The user {self.destination_user.id} with original pending"
                        " balance"
                        f" {destination_user_balance.currency.name} {destination_user_balance.pending_balance} has"
                        " new pending balance of"
                        f" {destination_user_balance.pending_balance + self.amount * self.get_sgn()} which"
                        " is smaller than zero."
                    )

                destination_user_balance.balance = (
                    destination_user_balance.balance + self.amount * self.get_sgn()
                )

            destination_user_balance.save()

        if self.direction == "outbound":
            if (balance.pending_balance - self.amount * self.get_sgn()) < 0:

                raise BalanceException(
                    f"The user {self.user.id} with original pending balance"
                    f" {balance.currency.name} {balance.pending_balance} has new"
                    " pending balance of"
                    f" {balance.pending_balance - self.amount * self.get_sgn()} which"
                    " is smaller than zero."
                )

            balance.pending_balance = (
                balance.pending_balance - self.amount * self.get_sgn()
            )

        if self.direction == "inbound":
            if (balance.balance - self.amount * self.get_sgn()) < 0:
                raise BalanceException(
                    f"The user {self.user.id} with original balance"
                    f" {balance.currency.name} {balance.balance} has new"
                    " balance of"
                    f" {balance.balance - self.amount * self.get_sgn()} which"
                    " is smaller than zero."
                )

            balance.balance = balance.balance - self.amount * self.get_sgn()

        if (
            self.currency.is_nft
            and Listings.objects.filter(currency=self.currency, type="lp").exists()
        ):
            print("deleting listing")
            Listings.objects.get(currency=self.currency, type="lp").delete()

        self.balance = balance.balance
        self.pending_balance = balance.pending_balance

        balance.save()

        self.log_transaction_status("Finalize finished")

    def log_transaction_status(self, title):

        if self.destination_user:
            if not Balances.objects.filter(
                user=self.destination_user, currency=self.currency
            ).exists():
                destination_user_balance = Balances.objects.create(
                    user=self.destination_user, currency=self.currency, balance=0
                )
                destination_user_balance.save()

            destination_user_balance = Balances.objects.select_for_update().get(
                user=self.destination_user, currency=self.currency
            )

        if not Balances.objects.filter(user=self.user, currency=self.currency).exists():
            balance = Balances.objects.create(
                user=self.user, currency=self.currency, balance=0
            )
            balance.save()

        balance = Balances.objects.select_for_update().get(
            user=self.user, currency=self.currency
        )

        str = f"""
            {title}
            
            Amount: {self.amount}
            Currency: {self.currency}
            Direction: {self.direction}
            Type: {self.type}
            
            User user:
                id: {self.user.id}
                balance: {balance.balance}
                pending_balance: {balance.pending_balance}

            """

        if self.destination_user:
            str = (
                str
                + f"""
                Destination user:
                    id: {self.destination_user.id}
                    balance: {destination_user_balance.balance}
                    pending_balance: {destination_user_balance.pending_balance}
                """
            )
        else:
            str = (
                str
                + f"""
                Destination user:
                    -
                """
            )
        print(str)

    @transaction.atomic
    def error_out(self, message):

        self.log_transaction_status("Error out start")

        if self.direction == "outbound":
            balance = Balances.objects.select_for_update().get(
                user=self.user, currency=self.currency
            )

            if (balance.pending_balance - self.amount * self.get_sgn()) < 0:
                raise BalanceException(
                    f"The user {self.user.id} with original pending balance"
                    f" {balance.currency.name} {balance.pending_balance} has new"
                    " pending balance of"
                    f" {balance.pending_balance - self.amount * self.get_sgn()} which"
                    " is smaller than zero."
                )

            balance.pending_balance = (
                balance.pending_balance - self.amount * self.get_sgn()
            )

            if (balance.balance + self.amount * self.get_sgn()) < 0:
                raise BalanceException(
                    f"The user {self.user.id} with original balance"
                    f" {balance.currency.name} {balance.balance} has new"
                    " balance of"
                    f" {balance.balance + self.amount * self.get_sgn()} which"
                    " is smaller than zero."
                )

            balance.balance = balance.balance + self.amount * self.get_sgn()

            balance.save()

        elif self.direction == "inbound" and self.destination_user:
            balance = Balances.objects.select_for_update().get(
                user=self.destination_user, currency=self.currency
            )

            if (balance.pending_balance + self.amount * self.get_sgn()) < 0:
                raise BalanceException(
                    f"The user {self.destination_user.id} with original pending balance"
                    f" {balance.currency.name} {balance.pending_balance} has new"
                    " pending balance of"
                    f" {balance.pending_balance + self.amount * self.get_sgn()} which"
                    " is smaller than zero."
                )

            balance.pending_balance = (
                balance.pending_balance + self.amount * self.get_sgn()
            )

            if (balance.balance - self.amount * self.get_sgn()) < 0:
                raise BalanceException(
                    f"The user {self.destination_user.id} with original balance"
                    f" {balance.currency.name} {balance.balance} has new"
                    " balance of"
                    f" {balance.balance - self.amount * self.get_sgn()} which"
                    " is smaller than zero."
                )

            balance.balance = balance.balance - self.amount * self.get_sgn()

            self.balance = balance.balance
            self.pending_balance = balance.pending_balance

            balance.save()

        self.status_description = message
        self.status = "error"

        if self.fee_transaction:
            if self.fee_transaction.status == "placeholder_fee":
                self.fee_transaction.error_out("parent transaction ended in error")

        self.save()

        self.log_transaction_status("Error out finished")

    @transaction.atomic
    def send_to_app_user(self, user):
        balance = Balances.objects.select_for_update().get(
            user=self.user, currency=self.currency
        )

        balance.balance = balance.balance + self.amount * self.get_sgn()

        balance.save()

    def get_big_status_image_class(self, viewer=None):
        if self.status == "error":
            return "fa fa-heart-broken"

        if self.status in [
            "inbound_invoice_waiting_for",
            "lnd_inbound_invoice_waiting_for",
            "outbound_invoice_received",
            "lnd_outbound_invoice_submitted",
            "lnd_outbound_invoice_received",
            "minting_submitted",
            "minting",
            "tx_created",
            "placeholder_fee",
            "exchange_started",
            "waiting_for_meta_data",
            "internal_stated",
        ]:
            return "fa fa-spinner fa-spin"
        elif self.status in [
            "inbound_invoice_generated",
            "lnd_inbound_invoice_generated",
        ]:
            return "fa fa-file-invoice-dollar"
        elif self.status in [
            "inbound_invoice_paid",
            "outbound_invoice_paid",
            "lnd_inbound_invoice_paid",
            "lnd_outbound_invoice_paid",
            "fee_paid",
            "internal_finished",
            "exchange_finished",
        ]:
            return "fa fa-check-circle"
        elif self.status in ["minted", "currency_registration_finished"]:
            return "fa fa-coins"
        elif self.status == "replaced_with_internal_transaction":
            return "fa fa-clone"

    def get_small_status_image_class(self, viewer=None):
        if self.is_error():
            return "fa fa-heart-broken"
        elif self.is_pending():
            return "fas fa-hourglass-half"
        elif self.type in ["minting", "currency_registration_finished"]:
            return "fas fa-coins"
        elif self.status == "replaced_with_internal_transaction":
            return "fas fa-clone"
        elif self.type == "fee":
            return "fas fa-money-check-alt"
        elif self.type == "exchange":
            return "fas fa-exchange-alt"
        elif self.direction == "inbound":
            return "fas fa-arrow-right"
        elif self.direction == "outbound":
            return "fas fa-arrow-left"

    def get_small_status_image_class_dest_user(self):
        if self.is_error():
            return "fa fa-heart-broken"
        elif self.is_pending():
            return "fas fa-hourglass-half"
        elif self.type == "exchange":
            return "fas fa-exchange-alt"
        if self.direction == "outbound":
            return "fas fa-arrow-right"

    def is_pending(self):
        return self.status in [
            "waiting_for_meta_data",
            "inbound_invoice_waiting_for",
            "inbound_invoice_generated",
            "outbound_invoice_received",
            "lnd_inbound_invoice_waiting_for",
            "lnd_inbound_invoice_generated",
            "lnd_outbound_invoice_received",
            "tx_created",
            "minting_submitted",
            "minting",
            "placeholder_fee",
            "internal_stated",
            "exchange_started",
        ]

    def is_error(self):
        return self.status in ["error"]

    def get_description(self):
        desc = ""
        if self.type == "minting":
            desc = desc + "New currency minting"
        elif self.type == "fee":
            desc = desc + "Transaction fee"
        elif self.type == "exchange":
            if self.currency.name == "Bitcoin":
                desc = desc + "Exchange - BTC"
            else:
                desc = desc + "Exchange - Taproot Asset Protocol currency"

        elif self.type == "register_currency":
            desc = desc + "New currency registration"

        else:
            if self.direction == "inbound":
                desc = desc + "Deposit"
            elif self.direction == "outbound":
                if self.type == "internal":
                    desc = desc + f"Payment to {self.destination_user.username}"
                else:
                    desc = desc + "Withdrawal"

        if self.status == "replaced_with_internal_transaction":
            desc = "[Replaced with internal transaction] " + desc

        elif self.status == "error":
            desc = "[Error] " + desc

        elif self.is_pending():
            desc = "[Pending] " + desc

        return desc

    def get_description_dest_user(self):
        desc = ""

        if self.type == "exchange":
            if self.currency.name == "Bitcoin":
                desc = desc + "Exchange - BTC"
            else:
                desc = desc + "Exchange - Taproot Asset Protocol currency"

        elif self.direction == "outbound":
            desc = desc + f"Payment from {self.user.username}"

        if self.status == "error":
            desc = "[Error] " + desc

        elif self.is_pending():
            desc = "[Pending] " + desc

        return desc

    @transaction.atomic
    def add_fees_and_assoc_trans(self):
        currency_BTC = Currencies.objects.get(name="Bitcoin")

        if (self.type in ["user"] and self.direction == "outbound") or (
            self.type == "minting"
        ):
            if self.status == "lnd_outbound_invoice_received":
                amount = get_fee_sat_estimate_lnd(self.amount)
            else:
                if self.type == "minting" and self.currency.collection:
                    num_curr = len(
                        Currencies.objects.filter(collection=self.currency.collection)
                    )
                    amount = int(get_fee_sat_estimate_onchain() / num_curr) + 1
                else:
                    amount = get_fee_sat_estimate_onchain()

                # amount = get_fee_sat_estimate_onchain()

            fee_transaction = Transactions.objects.create(
                user=self.user,
                currency=currency_BTC,
                amount=amount,
                description=f"Onchain fee",
                direction="outbound",
                status="placeholder_fee",
                type="fee",
            )
            fee_transaction.save()

            self.fee_transaction = fee_transaction

        if (self.type in ["exchange"]) and (self.currency != currency_BTC):
            listing = self.listing

            amount_sat = int(
                listing.get_price_sat(-self.amount * self.get_sgn()) * self.amount
            )

            sat_transaction = Transactions.objects.create(
                user=self.destination_user,
                listing=listing,
                destination_user=self.user,
                currency=currency_BTC,
                amount=amount_sat,
                description=(
                    f"Payment of {amount_sat} SAT for"
                    f" {self.amount} {self.currency.name}."
                ),
                direction=self.direction,
                status="exchange_started",
                type="exchange",
            )

            if (
                self.destination_user.id in [u.id for u in get_wash_users()]
            ) or self.direction == "inbound":
                amount_sat = 0
            else:
                amount_sat = get_fee_sat_estimate_exchange(amount_sat)

            fee_transaction = Transactions.objects.create(
                user=self.destination_user,
                destination_user=get_fee_user(),
                currency=currency_BTC,
                amount=amount_sat,
                description=f"Fee for exchange",
                direction="outbound",
                status="placeholder_fee",
                type="fee",
            )
            fee_transaction.save()

            self.fee_transaction = fee_transaction

            sat_transaction.save()
            self.associated_exchange_transaction = sat_transaction

            # amount_fee = min(int(sat_transaction.amount*0.01),5)

            # fee_transaction = Transactions.objects.create(
            #     user=self.destination_user,
            #     destination_user=self.user,
            #     currency=currency_BTC,
            #     amount=amount_fee,
            #     description=(
            #         f"Transaction fee."
            #     ),
            #     direction="outbound",
            #     status="placeholder_fee",
            #     type="fee",
            # )

    # balance = Balances.objects.get(currency=self.currency, user=self.user)
    # self.balance = balance.balance
    # self.pending_balance = balance.pending_balance

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        # check is new object
        if self._state.adding:
            self.initiate()

        super(Transactions, self).save(force_insert, force_update, using, update_fields)


class Listings(models.Model):
    user = models.ForeignKey(
        User,
        help_text="Internal user who has received the transaction",
        on_delete=models.CASCADE,
        null=False,
        blank=True,
    )

    LISTING_TYPE = (
        ("order_bid", "Bid - Offering SATs in exchange for Taproot Assets"),
        ("order_ask", "Ask - Asking for SATs in exchange for Taproot Assets"),
        ("lp", "Listing of currency with liquidity pool"),
    )

    type = models.CharField(
        max_length=50,
        choices=LISTING_TYPE,
        default="lp",
        help_text="Type of listing - Bid or Ask",
    )

    amount = models.IntegerField(
        help_text="Amount of currency to be exchanged",
        default=0,
        validators=[MinValueValidator(1)],
        null=True,
        blank=True,
    )

    currency = models.ForeignKey(
        Currencies,
        help_text="Taproot Asset to be exchanged",
        on_delete=models.CASCADE,
        null=False,
        blank=True,
    )

    price_sat = models.DecimalField(
        help_text="Price in SATs that the asset should be exchanged for.",
        decimal_places=5,
        max_digits=15,
        default=0,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )

    def is_ask(self):
        if self.type == "order_bid":
            return False
        elif self.type == "order_ask":
            return True
        else:
            raise Exception("This listing is an LP.")

    def user_can_execute(self, user):
        if self.user == user:
            return False

        if Balances.objects.filter(
            user, currency=self.currency, balance__gt=0
        ).exists():
            return True
        else:
            return False

    def get_lp_btc(self):
        currency_BTC = Currencies.objects.get(name="Bitcoin")
        balance_btc = Balances.objects.get(
            user=self.user, currency=currency_BTC
        ).balance

        return balance_btc

    def get_lp_curr(self):
        balance_currency = Balances.objects.get(
            user=self.user, currency=self.currency
        ).balance

        return balance_currency

    def get_price_sat_total(self):
        if self.currency.is_nft == True or self.type in ["order_bid", "order_ask"]:
            return int(self.get_price_sat() * self.amount)

        raise Exception("Can't obtain total price for this type of listing.")

    def get_price_sat(self, amount=0):
        if self.currency.is_nft == True or self.type in ["order_bid", "order_ask"]:
            return self.price_sat
        else:
            currency_BTC = Currencies.objects.get(name="Bitcoin")

            # buy
            # trans_outgoing_currency = Transactions.objects.filter(user=self.user, currency=self.currency, type='exchange', status="exchange_started", direction="outbound")
            trans_incomming_btc = Transactions.objects.filter(
                destination_user=self.user,
                currency=currency_BTC,
                type="exchange",
                status="exchange_started",
                direction="outbound",
            )

            # sell
            trans_incomming_currency = Transactions.objects.filter(
                user=self.user,
                currency=self.currency,
                type="exchange",
                status="exchange_started",
                direction="inbound",
            )
            # trans_outgoing_btc = Transactions.objects.filter(
            #     destination_user=self.user,
            #     currency=currency_BTC,
            #     type="exchange",
            #     status="exchange_started",
            #     direction="inbound",
            # )

            balance_currency = Balances.objects.get(
                user=self.user, currency=self.currency
            ).balance

            balance_btc = Balances.objects.get(
                user=self.user, currency__name="Bitcoin"
            ).balance

            for trn in trans_incomming_btc:
                balance_btc = balance_btc + trn.amount

            # for trn in trans_outgoing_btc:
            #     balance_btc = balance_btc - trn.amount

            for trn in trans_incomming_currency:
                balance_currency = balance_currency + trn.amount

            # for trn in trans_outgoing_currency:
            #     balance_currency = balance_currency - trn.amount
            if balance_currency < 0:
                raise Exception("Currency balance is invalid")

            if balance_btc < 0:
                raise Exception("BTC balance is invalid")

            if (balance_currency + amount) <= 0:
                raise Exception("New currency balance is invalid")

            return (balance_btc) / (balance_currency + amount)

    # Methods
    def get_absolute_url(self):
        """Returns the URL to access a particular instance of MyModelName."""
        return reverse("currency-detail", args=[str(self.currency.id)])

    def __str__(self):
        """String for representing the MyModelName object (in Admin site etc.)."""
        return f"Listing {self.id}"

    class Meta:
        constraints = [
            # Check status consistency
            models.UniqueConstraint(
                fields=["currency"], condition=Q(type="lp"), name="one_lp_per_currency"
            ),
            models.UniqueConstraint(
                fields=["user", "currency"],
                condition=Q(type="order_ask"),
                name="one_order_ask_per_user_currency",
            ),
            models.UniqueConstraint(
                fields=["user", "currency"],
                condition=Q(type="order_bid"),
                name="one_order_bid_per_user_currency",
            ),
        ]


class PriceHistory(models.Model):
    currency = models.ForeignKey(
        Currencies,
        help_text="Currency for sale",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    price_sat = models.FloatField(
        help_text="Currency price",
        default=0,
        validators=[MinValueValidator(0)],
        blank=True,
    )

    volume = models.FloatField(
        help_text="Currency volume",
        default=0,
        validators=[MinValueValidator(0)],
        blank=True,
    )

    orders = models.CharField(
        help_text="JSON list of all orders closed in this time period",
        max_length=5000,
        default="",
    )

    created_timestamp = models.DateTimeField(auto_now=True)

    PERIODS = (
        ("1m", "1 minute"),
        ("1h", "1 hour"),
        ("1d", "1 day"),
    )

    period = models.CharField(
        help_text="Time period",
        max_length=50,
        choices=PERIODS,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_timestamp"]

        indexes = (
            HashIndex(fields=("currency",)),
            HashIndex(fields=("period",)),
            HashIndex(fields=("created_timestamp",)),
            models.Index(fields=["currency", "period", "created_timestamp"]),
            models.Index(fields=["currency", "period"]),
        )


class ControlTable(models.Model):
    parameter_name = models.CharField(
        max_length=50,
        default="",
        help_text="Name of the control parameter",
        null=False,
        blank=False,
    )

    parameter_value = models.IntegerField(
        help_text="Value of the control parameter",
        default=0,
        null=False,
        blank=False,
    )

    created_timestamp = models.DateTimeField(auto_now=True)


class ExternalInfoTable(models.Model):
    variable_name = models.CharField(
        max_length=50,
        default="",
        help_text="Name of the variable",
        null=False,
        blank=False,
    )

    variable_value = models.IntegerField(
        help_text="Value of the variable",
        default=0,
        null=False,
        blank=False,
    )

    created_timestamp = models.DateTimeField(auto_now=True)


class Notifications(models.Model):

    destination_user = models.ForeignKey(
        User,
        related_name="target_user",
        help_text="User targeted by the notification",
        on_delete=models.CASCADE,
        null=False,
        blank=True,
    )

    read = models.BooleanField(
        help_text="Indicates if the notification was read",
        default=False,
        null=True,
        blank=True,
    )

    message = models.CharField(
        max_length=200,
        default="",
        help_text="Message to display",
        null=False,
        blank=False,
    )

    OBJECT_NAME_LIST = (
        ("t", "Transactions"),
        ("w", "Listings"),
        ("c", "Currencies"),
    )

    object_name = models.CharField(
        max_length=100,
        default="",
        choices=OBJECT_NAME_LIST,
        help_text="Object related to the message",
        null=False,
        blank=False,
    )

    transaction = models.ForeignKey(
        Transactions,
        help_text="Transaction associated with the notification",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    listing = models.ForeignKey(
        Listings,
        help_text="Listing associated with the notification",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    TYPES = (
        ("e", "error"),
        ("w", "warning"),
        ("s", "success"),
    )

    type = models.CharField(
        help_text="Notifications type",
        max_length=50,
        choices=TYPES,
        null=True,
        blank=True,
    )

    created_timestamp = models.DateTimeField(auto_now_add=True)
    updated_timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "transaction",
                    "listing",
                    "object_name",
                    "destination_user",
                    "type",
                ],
                name="one_notification_per_object_per_user",
            ),
        ]

        indexes = (
            HashIndex(fields=("destination_user",)),
            HashIndex(fields=("read",)),
            HashIndex(fields=("created_timestamp",)),
            models.Index(fields=["destination_user", "read", "created_timestamp"]),
        )

        ordering = ["read", "-created_timestamp"]

    def get_notification_class(self):
        translate_dict = {
            "success": "notification-success",
            "warning": "notification-pending",
            "error": "notification-cancel",
        }
        if self.read:
            return translate_dict[self.type] + " read-notification"
        else:
            return translate_dict[self.type]

    def get_notification_icon(self):

        translate_dict = {
            "success": "fas fa-check-circle",
            "warning": "fas fa-exclamation-circle",
            "error": "fas fa-times-circle",
        }

        return translate_dict[self.type]

    def get_link_to_object(self):

        if self.object_name == "Transactions":
            if self.transaction:
                return self.transaction.get_absolute_url()
            else:
                return "#"

        elif self.object_name == "Listings":
            if self.listing:
                return self.listing.currency.get_absolute_url() + (
                    "#bids" if self.listing.type == "order_bid" else "#asks"
                )
            else:
                return "#"


@receiver(post_save, sender=Transactions)
@transaction.atomic
def generate_transaction_notification(sender, instance, created, **kwargs):
    if created:
        if instance.type == "internal" and instance.status == "internal_stated":
            notification = Notifications.objects.create(
                destination_user=instance.destination_user,
                message=(
                    f"You have received {instance.currency.name} NFT from"
                    f" {instance.user.username}"
                )
                if instance.currency.is_nft
                else (
                    "You have received"
                    f" {instance.amount} {instance.currency.acronym} from"
                    f" {instance.user.username}"
                ),
                read=False,
                type="success",
                object_name="Transactions",
                transaction=instance,
            )
            notification.save()

        if (
            instance.type == "exchange"
            and instance.status == "exchange_started"
            and instance.listing
            and instance.associated_exchange_transaction is None
        ):
            if instance.listing.type in ["order_bid", "order_ask"]:

                notification = Notifications.objects.create(
                    destination_user=instance.listing.user,
                    message=(
                        "Your"
                        f" {'bid' if instance.listing.type == 'order_bid' else 'ask'} order"
                        " was"
                        f" {'bought' if instance.listing.type == 'order_bid' else 'sold'}."
                    ),
                    read=False,
                    type="success",
                    object_name="Transactions",
                    transaction=instance,
                )
                notification.save()


@receiver(post_save, sender=Listings)
@transaction.atomic
def generate_listing_notification(sender, instance, created, **kwargs):
    if created:
        if instance.currency.is_nft:
            balance = Balances.objects.get(currency=instance.currency, balance__gt=0)
            if instance.type in ["order_bid", "order_ask"]:
                notification = Notifications.objects.create(
                    destination_user=balance.user,
                    message=(
                        "There is a new"
                        f" {'bid' if instance.type=='order_bid' else 'ask'} order on"
                        f" your NFT {instance.currency.name} {instance.user.username}"
                    ),
                    read=False,
                    type="success",
                    object_name="Listings",
                    listing=instance,
                )
                notification.save()


def mark_notifications_as_read(object_name, object_instance, user):

    if object_name == "Transactions":

        if Notifications.objects.filter(
            destination_user=user,
            transaction=object_instance,
            object_name="Transactions",
        ).exists():
            notification = Notifications.objects.get(
                transaction=object_instance, object_name="Transactions"
            )
            notification.read = True
            notification.save()

    elif object_name == "Currencies":

        if Notifications.objects.filter(
            destination_user=user,
            listing__currency=object_instance,
            object_name="Listings",
        ).exists():
            notification_list = Notifications.objects.filter(
                listing__currency=object_instance, object_name="Listings"
            )
            for notification in notification_list:
                notification.read = True
                notification.save()

        else:
            return "#"

    else:
        raise Exception(f"Unknown object name '{object_name}'")


class ConstantsNumeric(models.Model):

    name = models.CharField(
        max_length=200,
        default="",
        help_text="Constant name",
        null=False,
        blank=False,
    )

    value = models.IntegerField(
        help_text="Constant value",
        default=0,
        null=False,
        blank=False,
    )

    class Meta:

        indexes = (models.Index(fields=["name"]),)
