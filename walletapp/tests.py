import json
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image, ImageDraw
from walletapp.management.commands.handle_transactions import (
    process_currencies_minting,
    process_currencies_submitted_for_minting,
    process_currencies_tx_created,
    process_transactions_exchange,
    process_transactions_inbound_invoice_generated,
    process_transactions_inbound_invoice_waiting_for,
    process_transactions_internal,
    process_transactions_outbound_invoice_received,
)
from walletapp.preview_utils import currency_card

from .const_utils import (
    get_fee_sat_estimate_exchange,
    get_fee_sat_estimate_onchain,
    get_initial_free_btc_balance,
)
from .models import (
    BalanceException,
    Balances,
    Collections,
    Currencies,
    Listings,
    Transactions,
    initiate_balances_from_files,
)
from .utils import encode_metadata, get_currency_btc, get_fee_user, get_free_amount_user

common_settings = override_settings(
    DEFAULT_FILE_STORAGE="django.core.files.storage.FileSystemStorage",
    PASSWORD_HASHERS=("django.contrib.auth.hashers.UnsaltedMD5PasswordHasher",),
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
)


def set_up_free_amount_user():
    free_amount_user = get_free_amount_user()

    balance = Balances.objects.get(user=free_amount_user, currency=get_currency_btc())
    balance.balance = 1000000
    balance.save()


def create_mock_image(
    filename="test_image.png", size=(800, 700), image_mode="RGB", image_format="PNG"
):
    """
    Generate a test image, returning the filename that it was saved as.

    If ``storage`` is ``None``, the BytesIO containing the image data
    will be passed instead.
    """
    data = BytesIO()
    img = Image.new(image_mode, size)
    img1 = ImageDraw.Draw(img)
    shape = [(300, 330), (600, 600)]
    img1.rectangle(shape, fill="black", outline="red")

    img.save(data, image_format)

    return SimpleUploadedFile(
        "test_image.png", (data.getvalue()), content_type="image/png"
    )


class MockProcess:
    def __init__(self, stdout, stderr=""):
        self.stdout = stdout
        self.stderr = stderr

    def communicate(self):
        return self.stdout, bytes(self.stderr, "utf-8")


class MockPoopenCurrencyMint:
    def __init__(self, fail_on=None) -> None:
        self.fail_on = fail_on
        self.block_height = 10

    def mock_poopen_tarocli(self, command_list, stdout, stderr):
        cmd = " ".join(command_list)

        print("Mock submitted:'" + cmd + "'")

        if self.fail_on:
            if cmd.startswith(self.fail_on):
                print("mocking minting...")
                return MockProcess(stdout="", stderr="mock_error")

        if cmd.startswith("tapcli -n=testnet assets mint"):
            print("mocking minting...")
            return MockProcess(
                """
                {
                    "pending_batch":
                        {
                            "batch_key": "test_batch_key"
                        }
                }
                """
            )

        if cmd.startswith("tapcli -n=testnet assets mint finalize"):
            print("mocking minting...")
            return MockProcess(
                """
                {
                    "pending_batch":
                        {
                            "batch_key": "test_batch_key"
                        }
                }
                """
            )

        if cmd.startswith("tapcli -n=testnet assets list"):
            print("mocking list assets...")
            return MockProcess(
                """
            {
                "assets":
                [
                    {
                        "chain_anchor":
                        {
                            "internal_key": "test_batch_key",
                            "anchor_outpoint": "mock_txid:0"
                        },
                        "asset_genesis": 
                        {
                            "asset_id": "mock_asset_id",
                            "name": "mock_name"
                        }
                    }
                ]
            }
            """
            )
        if cmd.startswith("lncli -n=testnet listchaintxns"):
            print("mocking list txn...")
            return MockProcess(
                """
            {
                "transactions":
                [
                    {
                        "tx_hash": "mock_txid",
                        "total_fees": 321,
                        "num_confirmations": 100
                    }
                ]
            }
            """
            )

        if cmd.startswith("lncli") and cmd.endswith("getinfo"):
            print("mocking list getinfo...")
            self.block_height = self.block_height + 1
            return MockProcess(json.dumps({"block_height": self.block_height}))

        raise Exception(f"Cant identify what to return for '{cmd}'")


class MockPoopenCurrencyCreate:
    def __init__(self, fail_on=None) -> None:
        self.fail_on = fail_on
        self.block_height = 10

    def mock_poopen_tarocli(self, command_list, stdout, stderr):
        cmd = " ".join(command_list)

        print("Mock submitted: " + cmd)

        if self.fail_on:
            if cmd.startswith(self.fail_on):
                print("mocking minting...")
                return MockProcess(stdout="", stderr="mock_error")

        if cmd.startswith("tapcli assets meta"):
            print("mocking get metadata...")
            return MockProcess(
                """
                {
                    "data":  "227b226465736372697074696f6e223a2022576169667520436f696e20697320612063727970746f63757272656e637920666f6375736564206f6e206272696e67696e672070656f706c6520636c6f73657220746f2066696374696f6e616c2063686172616374657273207468726f75676820646563656e7472616c697a656420726577617264732e222c20226e616d65223a20225761696675436f696e516a796f222c20226163726f6e796d223a202257414946222c202275736572223a20226661756365745f757365725f31222c20226d696e7465645f7573696e67223a202268747470733a2f2f746573746e65742e7461726f77616c6c65742e6e65742f222c2022696d6167655f64617461223a2022646174613a696d6167652f6a70673b6261736536342c2f396a2f34414151536b5a4a5267414241514141415141424141442f32774244414956635a48566b55345631624857576a6f576579502f5a794c653379502f2f2f2f4c2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f32774244415936576c73697679502f5a32662f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f7741415243414367414b41444153494141684542417845422f38514148774141415155424151454241514541414141414141414141414543417751464267634943516f4c2f3851417452414141674544417749454177554642415141414146394151494441415152425249684d5545474531466842794a7846444b426b61454949304b78775256533066416b4d324a7967676b4b4668635947526f6c4a69636f4b536f304e5459334f446b3651305246526b644953557054564656575631685a576d4e6b5a575a6e61476c7163335231646e643465587144684957476834694a69704b546c4a57576c35695a6d714b6a704b576d7036697071724b7a744c57327437693575734c44784d584778386a4a79744c54314e585731396a5a32754869342b546c3575666f3665727838765030396662332b506e362f38514148774541417745424151454241514542415141414141414141414543417751464267634943516f4c2f385141745245414167454342415144424163464241514141514a3341414543417845454253457842684a425551646863524d694d6f454946454b526f62484243534d7a55764156596e4c524368596b4e4f456c3852635947526f6d4a7967704b6a55324e7a67354f6b4e4552555a4853456c4b55315256566c64595756706a5a47566d5a326870616e4e3064585a3365486c36676f4f456859614869496d4b6b704f556c5a61586d4a6d616f714f6b7061616e714b6d7173724f3074626133754c6d367773504578636248794d6e4b3074505531646258324e6e613475506b3565626e364f6e7138765030396662332b506e362f396f4144414d42414149524178454150774378525252514155555555414646464a6d6742614b546e3655684948553072674c526b65744d336f4b547a466f754f784a5331467655303445646a53356773506f7075543961584e4f3468614b4b4b59425355744641435555744641425252525141556c48536b397a514164665955316e56616a6b6c37436f53784e4c635a4930784e526c7961644845583536443171645931586f4b4c415677726e7361504c66304e57614d30415669726a71445342694b74436b614a5737595072514243737046544c4947344e5635497968353665744e42496f7342642b6e4970516331586a6c39616e427a794b535944714b51484e4c5643436969696741704b576b504a7851416e7561686c6b37436e545067597173546b314f34774a7a54346f3937633942317067354e573058616f556669616f51385948416f4e494f6c4a6e4a4870514170464a6967484c5575614268696c70724835654b4e3354336f41566c444b51617075685273566350714b6a6d54636d52326f4556716c696b78554e4b44696b316343373135464b4f6168686673616c364836304959366969696d49536b4a777554536e734b696d6241785359794352736d6d5570704b596953455a665070566a7342363961696848796e334e532f786668514d553838554d4d596f475354696b4966484f43506267306745422b59306f504e4a336f37476741484f425372796151635a2b6c4b6f627467653941436a67346f48424937554545594a4f615476544172534c7463696d565063444f472f436f4b42446b4f445674547557716457494737556d4d6d48536c704f394c54454a3371744f6561736574565a6676476c314752305555557846694837672b74502f4149716a68507948324e536e7361426a444c734f414354546674445a2b364b6b4147375051396a55573335696359494e43416b5631632b6837696c3971574e666c4259664e5373766355414d5968567966576d6661443255594654415a516a363158326b4b43527a51674a504f7a77796b5a702f705345416f7059636755646851416b6f796a4438617131624a2b596539566d473169505367427453776e44436f71664839366b39675262505930366d6e37744c5168436574565a66765661396171796a356a52314752305555557845734a777846574635424656497a6878566748422b6c417835486364525367356f79434d3030484463394b5144364b4b626b353755784471445254576248316f4159353755443774494f54532f7855696766376d52324f61696d48495964366c586e4b6e747855654d6f79487176536d496870386633715a54342f76556d4a46762b476c70503461576c45413731586e484e57443631484d7552545930564b4b553961536d49636e33783961734837777147455a663656502f41425544515a326d676d6a37783971516a4270414b48414f44543869717a487365522f4b70496e2b513550536d496537685236557748504e516b354f5365616c584742696761484c316f492b5930754f4d30486b6730686a474f31672f7743426f6c47434a422b4e4f635a36394454596a775932375578454c444463644f315068487a55316c494f30397635564e437647616d57774576705471614f744f70705751684b516a4977616453486a6d6867564a4677616a71334b6d526d71324147353655495a4e4375314d6e765373366a71667771463543337350536d55774a6a4e2f64483531477a7333553046534143652f5368564c746764614243555a2f57676a4278533744733339733041495156366a464b6f5a6a686574444d57497a54787841534f35356f474c756c516854336f383342777778394b62764f467831427a544353535365744146705744727761696348715076436f675370794467314c356d34656a55414b66336d316831715a5274576d524a6a6d704f702b6c5475416f34464c52525643436b70614b4147394f4f31517978397855394a37476b304d704559704b7453525a3546563255696934456a4174416841365557792f4d543655784a47546f65505370325a56694c4c7875706751796f524963633535707a4462416f506331496a4b79686a3157713775584f5361414a4a31414b34474d696e68554d5241626a504a706b334b6f6661694c2f5675506167427168664f4142794b5355596b59436b6a4f48552b39506d475a546967434d444e54525235354e4c4846334e54446a67564f344237436c6f4178533030684252525254414b4b4b4b41436b70614b414536653470705657703949526d6c5943426f66536f796a4372665031704f4f346f3147553845556d44567a436e306f324c3755585946544270516a6471746256487053386468526467514c43653953716972542b667052696977436466595576536c6f70694369696967424b4b576b6f412f396b3d227d22",
                    "type":  "META_TYPE_OPAQUE",
                    "meta_hash":  "d3e38832df8edddf079865f82723adc98b509204e8fff0b75210be13b4e3387b"
                }
                """
            )

        if cmd.startswith("tapcli universe leaves"):
            print("mocking get leaves...")
            return MockProcess(
                """
            {
                "leaves":  [
                    {
                        "asset":  {
                            "version":  0,
                            "asset_genesis":  {
                                "name":  "WaifuCoinQjyo"
                            },
                            "asset_type":  "NORMAL",
                            "amount":  "1000"
                        }
                    }
                ]
            }
            """
            )


@common_settings
class MintCurrenciesTestCase(TestCase):
    def setUp(self):
        set_up_free_amount_user()

        self.user1 = User.objects.create_user(
            username="john", email="jlennon@beatles.com", password="glass onion"
        )

        self.user1.save()

        self.user1_bal_btc = Balances.objects.get(
            user=self.user1, currency=get_currency_btc()
        )
        self.user1_bal_btc.balance = get_fee_sat_estimate_onchain() * 2
        self.user1_bal_btc.save()

        self.currency1 = Currencies.objects.create(
            name="TestCaseCoin",
            owner=self.user1,
            picture_orig=None,
            acronym="ACC",
            asset_id="xxx",
            description="This is my test coin",
            supply=10,
            status="waiting_for_miting_transaction",
        )

        self.currency1.save()
        process_transactions_internal()

    @patch("walletapp.management.commands.handle_transactions.time.sleep")
    @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
    def test_simulate_minting_sucess(self, mock_poopen, mock_sleep):
        mock_storage = Storage

        self.user1.refresh_from_db()
        btc_bal_init = self.user1.get_btc_balance()

        mock_poopen.side_effect = MockPoopenCurrencyMint().mock_poopen_tarocli
        self.currency1.refresh_from_db()
        self.assertEqual(self.currency1.minting_transaction.status, "minting_submitted")

        fee_transaction = (Transactions.objects.filter(user=self.user1, type="fee"))[0]
        self.assertEqual(fee_transaction.amount, get_fee_sat_estimate_onchain())

        minting_transaction = (
            Transactions.objects.filter(user=self.user1, type="minting")
        )[0]
        self.assertEqual(minting_transaction.amount, 10)

        self.assertEqual(
            self.user1.get_btc_pending_balance(), get_fee_sat_estimate_onchain()
        )

        process_currencies_submitted_for_minting()
        self.currency1.refresh_from_db()
        self.assertEqual(self.currency1.status, "minting")

        self.assertEqual(
            self.user1.get_btc_pending_balance(), get_fee_sat_estimate_onchain()
        )
        fee_transaction.refresh_from_db()
        self.assertEqual(fee_transaction.status, "placeholder_fee")

        process_currencies_minting()
        self.currency1.refresh_from_db()
        self.assertEqual(self.currency1.status, "tx_created")
        self.assertEqual(self.currency1.minting_transaction.status, "minting")

        self.assertEqual(
            self.user1.get_btc_pending_balance(), get_fee_sat_estimate_onchain()
        )

        process_currencies_tx_created()
        self.user1.refresh_from_db()
        self.currency1.refresh_from_db()
        fee_transaction.refresh_from_db()

        self.assertEqual(self.currency1.status, "minted")
        self.assertEqual(self.currency1.minting_transaction.status, "minted")

        self.assertEqual(self.user1.get_btc_pending_balance(), 0)
        self.assertEqual(self.user1.get_balances(currency=self.currency1).balance, 10)
        self.assertEqual(
            self.user1.get_balances(currency=self.currency1).pending_balance, 0
        )

        self.assertEqual(fee_transaction.status, "fee_paid")
        self.assertEqual(fee_transaction.amount, get_final_fee(321))

        self.assertEqual(
            (get_fee_sat_estimate_onchain() * 2 + get_initial_free_btc_balance())
            - self.user1.get_btc_balance(),
            get_final_fee(321),
            msg="fee correctly subtracted from BTC balance",
        )

        fee_transaction.refresh_from_db()

        self.assertEqual(fee_transaction.status, "fee_paid")

        print(self.currency1.minting_transaction)

    @patch("walletapp.management.commands.handle_transactions.time.sleep")
    @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
    def test_simulate_minting_fail_1(self, mock_poopen, mock_sleep):
        mock_poopen.side_effect = MockPoopenCurrencyMint(
            fail_on="tapcli -n=testnet assets mint"
        ).mock_poopen_tarocli

        fee_transaction = (Transactions.objects.filter(user=self.user1, type="fee"))[0]

        process_currencies_submitted_for_minting()
        self.currency1.refresh_from_db()
        self.assertEqual(self.currency1.status, "error")

        fee_transaction.refresh_from_db()

        self.assertEqual(self.user1.get_btc_pending_balance(), 0)
        self.assertEqual(
            self.user1.get_btc_balance(),
            (get_fee_sat_estimate_onchain() * 2 + get_initial_free_btc_balance()),
        )
        self.assertEqual(fee_transaction.status, "error")
        self.assertEqual(self.currency1.minting_transaction.status, "error")

    @patch("walletapp.management.commands.handle_transactions.time.sleep")
    @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
    def test_simulate_minting_fail_2(self, mock_poopen, mock_sleep):
        mock_poopen.side_effect = MockPoopenCurrencyMint(
            fail_on="tapcli -n=testnet assets list"
        ).mock_poopen_tarocli

        fee_transaction = (Transactions.objects.filter(user=self.user1, type="fee"))[0]

        process_currencies_submitted_for_minting()
        process_currencies_minting()

        self.currency1.refresh_from_db()
        self.assertEqual(self.currency1.status, "error")

        fee_transaction.refresh_from_db()

        self.assertEqual(self.user1.get_btc_pending_balance(), 0)
        self.assertEqual(
            self.user1.get_btc_balance(),
            (get_fee_sat_estimate_onchain() * 2 + get_initial_free_btc_balance()),
        )
        self.assertEqual(fee_transaction.status, "error")
        self.assertEqual(self.currency1.minting_transaction.status, "error")

    @patch("walletapp.management.commands.handle_transactions.time.sleep")
    @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
    def test_simulate_minting_fail_3(self, mock_poopen, mock_sleep):
        mock_poopen.side_effect = MockPoopenCurrencyMint(
            fail_on="lncli -n=testnet listchaintxns"
        ).mock_poopen_tarocli

        fee_transaction = (Transactions.objects.filter(user=self.user1, type="fee"))[0]

        process_currencies_submitted_for_minting()
        process_currencies_minting()
        process_currencies_tx_created()

        self.currency1.refresh_from_db()
        self.assertEqual(self.currency1.status, "error")

        fee_transaction.refresh_from_db()

        self.assertEqual(self.user1.get_btc_pending_balance(), 0)
        self.assertEqual(
            self.user1.get_btc_balance(),
            (get_fee_sat_estimate_onchain() * 2 + get_initial_free_btc_balance()),
        )
        self.assertEqual(fee_transaction.status, "error")
        self.assertEqual(self.currency1.minting_transaction.status, "error")


@common_settings
class MintCurrenciesBulkTestCase(TestCase):
    def setUp(self):
        set_up_free_amount_user()

        self.user1 = User.objects.create_user(
            username="john", email="jlennon@beatles.com", password="glass onion"
        )

        self.user1.save()

        self.user1_bal_btc = Balances.objects.get(
            user=self.user1, currency=get_currency_btc()
        )
        self.user1_bal_btc.balance = get_fee_sat_estimate_onchain() * 2
        self.user1_bal_btc.save()

        self.collection = Collections(
            name="TestCollection", description="My test collection"
        )
        self.collection.save()

        self.file_list = []
        self.num_batch = 5
        for i in range(0, self.num_batch):
            with open(
                "walletapp/static/assets/images/unknown_currency.png", "rb"
            ) as picture_orig:
                cf = ContentFile(content=picture_orig.read(), name=str(i + 1) + ".jpg")
                self.file_list.append(cf)

        initiate_balances_from_files(self.file_list, self.collection, self.user1)

        process_transactions_internal()

    @patch("walletapp.management.commands.handle_transactions.time.sleep")
    @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
    def test_simulate_minting_sucess(self, mock_poopen, mock_sleep):
        mock_storage = Storage

        mock_poopen.side_effect = MockPoopenCurrencyMint().mock_poopen_tarocli

        self.assertEqual(
            self.collection.get_assets()[0].minting_transaction.status,
            "minting_submitted",
        )

        fee_transactions = Transactions.objects.filter(user=self.user1, type="fee")
        self.assertEqual(len(fee_transactions), self.num_batch)
        self.assertEqual(
            fee_transactions[0].amount,
            int(get_fee_sat_estimate_onchain() / self.num_batch) + 1,
        )

        minting_transactions = Transactions.objects.filter(
            user=self.user1, type="minting"
        )
        self.assertEqual(len(minting_transactions), self.num_batch)
        self.assertEqual(minting_transactions[0].amount, 1)

        self.assertEqual(
            self.user1.get_btc_pending_balance(),
            (int(get_fee_sat_estimate_onchain() / self.num_batch) + 1) * self.num_batch,
        )

        process_currencies_submitted_for_minting()

        for curr in self.collection.get_assets():
            self.assertEqual(curr.status, "minting")

        self.assertEqual(
            self.user1.get_btc_pending_balance(),
            (int(get_fee_sat_estimate_onchain() / self.num_batch) + 1) * self.num_batch,
        )
        for fee_transaction in fee_transactions:
            fee_transaction.refresh_from_db()
            self.assertEqual(fee_transaction.status, "placeholder_fee")

        process_currencies_minting()
        for curr in self.collection.get_assets():
            curr.refresh_from_db()
            self.assertEqual(curr.status, "tx_created")
            self.assertEqual(curr.minting_transaction.status, "minting")

        self.assertEqual(
            self.user1.get_btc_pending_balance(),
            (int(get_fee_sat_estimate_onchain() / self.num_batch) + 1) * self.num_batch,
        )

        process_currencies_tx_created()
        self.user1.refresh_from_db()
        for curr in self.collection.get_assets():
            self.assertEqual(curr.status, "minted")
            self.assertEqual(curr.minting_transaction.status, "minted")
            self.assertEqual(self.user1.get_balances(currency=curr).balance, 1)
            self.assertEqual(self.user1.get_balances(currency=curr).pending_balance, 0)

        self.assertEqual(self.user1.get_btc_pending_balance(), 0)

        for fee_transaction in fee_transactions:
            fee_transaction.refresh_from_db()
            self.assertEqual(fee_transaction.status, "fee_paid")
            self.assertEqual(
                fee_transaction.amount, get_final_fee(int(321 / self.num_batch) + 1)
            )

        self.assertEqual(
            (get_fee_sat_estimate_onchain() * 2 + get_initial_free_btc_balance())
            - self.user1.get_btc_balance(),
            get_final_fee((int(321 / self.num_batch) + 1) * self.num_batch),
            msg="fee correctly subtracted from BTC balance",
        )


class MockPoopenReceiveCurrencies:
    def __init__(
        self, fail_on=None, test_invoice_to_return="test_taro_invoice"
    ) -> None:
        self.fail_on = fail_on
        self.test_invoice_to_return = test_invoice_to_return

    def mock_poopen_tarocli(self, command_list, stdout, stderr):
        cmd = " ".join(command_list)

        print("Mock submitted: " + cmd)

        if self.fail_on:
            if cmd.startswith(self.fail_on):
                print("mocking minting...")
                return MockProcess(stdout="", stderr="mock_error")

        if cmd.startswith("tapcli -n=testnet addrs new"):
            print("mocking minting...")
            return MockProcess(
                f"""
            {{
                "encoded": "{self.test_invoice_to_return}"
            }}
            """
            )

        if cmd.startswith("tapcli -n=testnet addrs receives"):
            print("mocking get receives...")
            return MockProcess(
                """
            {
                "events":
                [
                    {
                        "status": "ADDR_EVENT_STATUS_TRANSACTION_CONFIRMED",
                        "outpoint" : "mock_tx_id:0"
                    }
                ]
            }
            """
            )


@common_settings
class ReceiveCurrenciesTestCase(TestCase):
    def setUp(self):
        set_up_free_amount_user()

        self.user1 = User.objects.create_user(
            username="john", email="jlennon@beatles.com", password="glass onion"
        )

        self.user1.save()

        self.currency1 = Currencies.objects.create(
            name="TestCaseCoin",
            owner=self.user1,
            picture_orig=None,
            acronym="ACC",
            asset_id="mock_asset_id",
            description="This is my test coin",
            supply=10,
            status="minted",
        )

        self.currency1.save()

        balance = Balances.objects.create(
            user=self.user1, currency=self.currency1, balance=10
        )
        balance.save()

        process_transactions_internal()

    @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
    def test_deposit_success(self, mock_poopen):
        mock_poopen.side_effect = MockPoopenReceiveCurrencies().mock_poopen_tarocli

        transaction1 = Transactions.objects.create(
            user=self.user1,
            description="My test money deposit",
            amount=5,
            currency=self.currency1,
            type="user",
            direction="inbound",
            status="inbound_invoice_waiting_for",
        )
        transaction1.save()

        process_transactions_inbound_invoice_waiting_for()

        transaction1.refresh_from_db()
        self.assertEqual(transaction1.invoice_inbound, "test_taro_invoice")
        self.assertEqual(transaction1.status, "inbound_invoice_generated")

        self.assertEqual(self.user1.get_btc_pending_balance(), 0)
        self.assertEqual(self.user1.get_btc_balance(), get_initial_free_btc_balance())
        self.assertEqual(self.user1.get_balances(currency=self.currency1).balance, 10)

        process_transactions_inbound_invoice_generated()

        transaction1.refresh_from_db()
        self.assertEqual(transaction1.invoice_inbound, "test_taro_invoice")
        self.assertEqual(transaction1.status, "inbound_invoice_paid")
        self.assertEqual(transaction1.tx_id, "mock_tx_id")
        self.assertEqual(self.user1.get_balances(currency=self.currency1).balance, 15)

    @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
    def test_deposit_fail_1(self, mock_poopen):
        mock_poopen.side_effect = MockPoopenReceiveCurrencies(
            fail_on="tapcli -n=testnet addrs new"
        ).mock_poopen_tarocli

        transaction1 = Transactions.objects.create(
            user=self.user1,
            description="My test money deposit",
            amount=5,
            currency=self.currency1,
            type="user",
            direction="inbound",
            status="inbound_invoice_waiting_for",
        )
        transaction1.save()

        process_transactions_inbound_invoice_waiting_for()

        transaction1.refresh_from_db()
        self.assertEqual(transaction1.invoice_inbound, None)
        self.assertEqual(transaction1.status, "error")

        self.assertEqual(self.user1.get_btc_pending_balance(), 0)
        self.assertEqual(self.user1.get_btc_balance(), get_initial_free_btc_balance())
        self.assertEqual(self.user1.get_balances(currency=self.currency1).balance, 10)

    @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
    def test_deposit_fail_2(self, mock_poopen):
        mock_poopen.side_effect = MockPoopenReceiveCurrencies(
            fail_on="tapcli -n=testnet addrs receives"
        ).mock_poopen_tarocli

        transaction1 = Transactions.objects.create(
            user=self.user1,
            description="My test money deposit",
            amount=5,
            currency=self.currency1,
            type="user",
            direction="inbound",
            status="inbound_invoice_waiting_for",
        )
        transaction1.save()

        process_transactions_inbound_invoice_waiting_for()

        transaction1.refresh_from_db()
        self.assertEqual(transaction1.invoice_inbound, "test_taro_invoice")
        self.assertEqual(transaction1.status, "inbound_invoice_generated")

        self.assertEqual(self.user1.get_btc_pending_balance(), 0)
        self.assertEqual(self.user1.get_btc_balance(), get_initial_free_btc_balance())
        self.assertEqual(self.user1.get_balances(currency=self.currency1).balance, 10)

        process_transactions_inbound_invoice_generated()

        transaction1.refresh_from_db()
        self.assertEqual(transaction1.invoice_inbound, "test_taro_invoice")
        self.assertEqual(transaction1.status, "error")
        self.assertEqual(transaction1.tx_id, None)
        self.assertEqual(self.user1.get_balances(currency=self.currency1).balance, 10)


class MockPoopenSendCurrencies:
    def __init__(self, fail_on=None) -> None:
        self.fail_on = fail_on

    def mock_poopen_tarocli(self, command_list, stdout, stderr):
        cmd = " ".join(command_list)

        print("Mock submitted: " + cmd)

        if self.fail_on:
            if cmd.startswith(self.fail_on):
                print("mocking sending...")
                return MockProcess(stdout="", stderr="mock_error")

        if cmd.startswith("tapcli -n=testnet assets send"):
            print("mocking sending...")
            return MockProcess(
                """
                {
                    "transfer":  {
                        "anchor_tx_chain_fees":  "321",
                        "inputs":  [
                            {
                                "anchor_point":  "8bc4b17043b8d9165743accad55b8c8df6627b5d86341109f7f39a86eec07918:0",
                                "asset_id":  "6ab81f9b6b72138bc77189ea4afeabcfdb8722d1d5485ddbefc7a344bd9884e6",
                                "script_key":  "0282f621af104d54bf98482f7ca8a1fce4c79aeb7100d4d28c348fe3b39f1e8982",
                                "amount":  "100"
                            }
                        ],
                        "outputs":  [
                            {
                                "anchor":  {
                                    "outpoint":  "test_outpoint:0"
                                },
                                "script_key":  "test_script_key",
                                "script_key_is_local":  true
                            },
                            {
                                "anchor":  {
                                    "outpoint":  "mock_txid:0"
                                },
                                "script_key":  "test_script_key_2",
                                "script_key_is_local":  false
                            }
                        ]
                    }
                }
                """
            )


@common_settings
class SendCurrenciesTestCase(TestCase):
    def setUp(self):
        set_up_free_amount_user()

        self.user1 = User.objects.create_user(
            username="john", email="jlennon@beatles.com", password="glass onion"
        )

        self.user1.save()

        self.currency1 = Currencies.objects.create(
            name="TestCaseCoin",
            owner=self.user1,
            picture_orig=None,
            acronym="ACC",
            asset_id="mock_asset_id",
            description="This is my test coin",
            supply=10,
            status="minted",
        )

        self.currency1.save()

        balance = Balances.objects.create(
            user=self.user1, currency=self.currency1, balance=10
        )
        balance.save()

        process_transactions_internal()

        balance = Balances.objects.get(user=self.user1, currency=get_currency_btc())
        balance.balance = get_fee_sat_estimate_onchain() * 3
        balance.save()

    @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
    def test_send_success(self, mock_poopen):
        mock_poopen.side_effect = MockPoopenSendCurrencies().mock_poopen_tarocli

        transactions_list = Transactions.objects.all()

        for trn in transactions_list:
            print(trn)

        self.assertEqual(self.user1.get_btc_pending_balance(), 0)
        self.assertEqual(
            self.user1.get_btc_balance(), get_fee_sat_estimate_onchain() * 3
        )
        self.assertEqual(self.user1.get_balances(currency=self.currency1).balance, 10)

        transaction1 = Transactions.objects.create(
            user=self.user1,
            description="My test money withdrawal",
            invoice_outbound="mock_outbound_invoice",
            amount=5,
            currency=self.currency1,
            type="user",
            direction="outbound",
            status="outbound_invoice_received",
        )
        transaction1.save()

        process_transactions_outbound_invoice_received()

        transaction1.refresh_from_db()

        print(transaction1.status)

        self.assertNotEqual(
            transaction1.status, "error", transaction1.status_description
        )

        self.assertEqual(self.user1.get_btc_pending_balance(), 0)
        self.assertEqual(
            self.user1.get_btc_balance(),
            get_fee_sat_estimate_onchain() * 3 - get_final_fee(321),
        )
        self.assertEqual(self.user1.get_balances(currency=self.currency1).balance, 5)

    @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
    def test_send_fail_1(self, mock_poopen):
        mock_poopen.side_effect = MockPoopenSendCurrencies(
            fail_on="tarocli assets send"
        ).mock_poopen_tarocli

        self.assertEqual(self.user1.get_btc_pending_balance(), 0)
        self.assertEqual(
            self.user1.get_btc_balance(), get_fee_sat_estimate_onchain() * 3
        )
        self.assertEqual(self.user1.get_balances(currency=self.currency1).balance, 10)

        with self.assertRaises(Exception) as context:
            transaction1 = Transactions.objects.create(
                user=self.user1,
                description="My test money withdrawal",
                invoice_outbound="mock_outbound_invoice",
                amount=11,
                currency=self.currency1,
                type="user",
                direction="outbound",
                status="outbound_invoice_received",
            )
            transaction1.save()

        self.assertTrue("New balance is smaller than zero." in str(context.exception))

        process_transactions_outbound_invoice_received()

        self.assertEqual(self.user1.get_btc_pending_balance(), 0)
        self.assertEqual(
            self.user1.get_btc_balance(), get_fee_sat_estimate_onchain() * 3
        )
        self.assertEqual(self.user1.get_balances(currency=self.currency1).balance, 10)


@common_settings
class MintCurrenciesEncodeDecodeImage(TestCase):
    def setUp(self):
        set_up_free_amount_user()
        self.user1 = User.objects.create_user(
            username="john", email="jlennon@beatles.com", password="glass onion"
        )

        self.user1.save()

        self.currency1 = Currencies.objects.create(
            name="TestCaseCoin",
            owner=self.user1,
            picture_orig=None,
            acronym="ACC",
            asset_id="xxx",
            description="This is my test coin",
            supply=10,
            status="submitted_for_minting",
        )

        with open(
            "walletapp/static/assets/images/unknown_currency.png", "rb"
        ) as picture_orig:
            cf = ContentFile(picture_orig.read())

        if self.currency1.is_nft:
            filename = self.currency1.name
        else:
            filename = self.currency1.acronym

        self.currency1.picture_orig.save(name=filename + ".png", content=cf, save=False)

        self.currency1.save()

    def test_simulate_image(self):
        metadata = encode_metadata(self.currency1)

        print(metadata)


# @common_settings
# class RequestTestRegAsset(TestCase):
#     def setUp(self):
#         set_up_free_amount_user()
#         self.user1 = User.objects.create_user(username="john", password="glass onion")

#         self.user1.save()

#     def test_free_balance(self):

#         self.client.login(username="john", password="glass onion")

#         response = self.client.get(reverse("balances"))

#         self.assertEqual(response.status_code, 200)

#         bitcoin_balance = response.context["balances_list"][0]
#         self.assertEqual(bitcoin_balance.currency.name, "Bitcoin")
#         self.assertEqual(bitcoin_balance.balance, get_initial_free_btc_balance())

#     def test_register_currency_no_image_success(self):

#         self.client.login(username="john", password="glass onion")

#         data = {
#             "acronym": "TC",
#             "asset_id": (
#                 "7de54d782bb102607cc752a2a2f9be6eaefdcf1c0cdfec90bc85e21b72101a09"
#             ),
#             "universe_host": "",
#             "picture_orig": "",
#         }

#         response = self.client.post(reverse("currency-create"), data=data, follow=True)

#         self.assertEqual(response.status_code, 200)

#         form = response.context.get("form", [])
#         errors = {field.name: field.errors[0] for field in form if field.errors}
#         self.assertEqual([], list(errors.keys()))

#         transactions = response.context["transactions"]

#         self.assertEqual(transactions.currency.name, "7de54d782b")
#         self.assertEqual(transactions.currency.acronym, "TC")

#     def test_register_currency_image_success(self):

#         self.client.login(username="john", password="glass onion")

#         data = {
#             "acronym": "TC",
#             "asset_id": (
#                 "7de54d782bb102607cc752a2a2f9be6eaefdcf1c0cdfec90bc85e21b72101a09"
#             ),
#             "picture_orig": create_mock_image(),
#         }

#         response = self.client.post(reverse("currency-create"), data=data, follow=True)

#         self.assertEqual(response.status_code, 200)

#         form = response.context.get("form", [])
#         errors = {field.name: field.errors[0] for field in form if field.errors}
#         self.assertEqual([], list(errors.keys()))

#         transactions = response.context["transactions"]

#         self.assertEqual(transactions.currency.acronym, "TC")

#     def test_register_currency_repeat_fail(self):

#         self.client.login(username="john", password="glass onion")

#         data = {
#             "acronym": "TC1",
#             "asset_id": "3c0473c2631d8e38ada77934a139d3ad15a536a16de21b8d4e073c22f51070ce00000002085465737443757272076d7920746573740000000000",
#             "picture_orig": create_mock_image(),
#         }

#         response = self.client.post(
#             reverse("currency-create"), data=data, follow=True, format="multipart"
#         )

#         self.assertEqual(response.status_code, 200)

#         data = {
#             "acronym": "TC2",
#             "asset_id": "3c0473c2631d8e38ada77934a139d3ad15a536a16de21b8d4e073c22f51070ce00000002085465737443757272076d7920746573740000000000",
#             "universe_host": "",
#             "picture_orig": create_mock_image(),
#         }

#         response = self.client.post(
#             reverse("currency-create"), data=data, follow=True, format="multipart"
#         )

#         self.assertEqual(response.status_code, 200)
#         print(response.context)
#         form = response.context["form"]
#         errors = {field.name: field.errors[0] for field in form if field.errors}

#         self.assertIn("asset_id", errors.keys())


# @common_settings
# class RequestTestMintAsset(TestCase):
#     def setUp(self):
#         set_up_free_amount_user()
#         self.user1 = User.objects.create_user(username="john", password="glass onion")

#         self.user1.save()

#     def test_mint_currency_no_image(self):

#         self.client.login(username="john", password="glass onion")

#         data = {
#             "acronym": "TC",
#             "name": "TestCurrency",
#             "description": "This is my test description",
#             "supply": 100,
#             "picture_orig": "",
#         }

#         response = self.client.post(reverse("currency-mint"), data=data, follow=True)

#         self.assertEqual(response.status_code, 200)

#         form = response.context.get("form", [])
#         errors = {field.name: field.errors[0] for field in form if field.errors}
#         self.assertEqual([], list(errors.keys()))

#         transaction = response.context["transactions"]

#         self.assertEqual(transaction.currency.acronym, "TC")
#         self.assertEqual(transaction.amount, 100)

#         self.assertEqual(
#             transaction.currency.get_image_url_name(),
#             "/static/assets/images/unknown_currency.png",
#         )

#     def test_mint_currency_image(self):

#         self.client.login(username="john", password="glass onion")

#         data = {
#             "acronym": "TC",
#             "name": "TestCurrency",
#             "description": "This is my test description",
#             "supply": 100,
#             "picture_orig": create_mock_image(),
#         }

#         response = self.client.post(reverse("currency-mint"), data=data, follow=True)

#         self.assertEqual(response.status_code, 200)

#         form = response.context.get("form", [])
#         errors = {field.name: field.errors[0] for field in form if field.errors}
#         self.assertEqual([], list(errors.keys()))

#         transaction = response.context["transactions"]

#         self.assertEqual(transaction.currency.acronym, "TC")
#         self.assertEqual(transaction.amount, 100)
#         self.assertTrue(
#             transaction.currency.get_image_url_name().startswith("/uploads/small/TC_")
#         )

#     def test_mint_nft_image(self):

#         self.client.login(username="john", password="glass onion")

#         data = {
#             "name": "TestCurrency",
#             "description": "This is my test description",
#             "picture_orig": create_mock_image(),
#         }

#         response = self.client.post(
#             reverse("currency-mint-nft"), data=data, follow=True
#         )

#         self.assertEqual(response.status_code, 200)

#         form = response.context.get("form", [])
#         errors = {field.name: field.errors[0] for field in form if field.errors}
#         self.assertEqual([], list(errors.keys()))

#         transaction = response.context["transactions"]

#         self.assertEqual(transaction.currency.name, "TestCurrency")
#         self.assertEqual(transaction.amount, 1)
#         self.assertTrue(
#             transaction.currency.get_image_url_name().startswith(
#                 "/uploads/small/TestCurrency_"
#             )
#         )


# @common_settings
# class RequestTestDepositAsset(TestCase):
#     def setUp(self):
#         set_up_free_amount_user()
#         self.user1 = User.objects.create_user(
#             username="john", email="jlennon@beatles.com", password="glass onion"
#         )

#         self.user1.save()

#         self.client.login(username="john", password="glass onion")

#         data = {
#             "acronym": "TC",
#             "asset_id": (
#                 "ece2f8e5dadf386790bafd16b12598e3258cf6c7e9b1e979b46503aea668ee79"
#             ),
#             "universe_host": "",
#             "picture_orig": "",
#         }

#         response = self.client.post(reverse("currency-create"), data=data, follow=True)

#         self.currency = Currencies.objects.get(acronym="TC")

#         data = {"currency": self.currency.id}

#         response = self.client.post(reverse("balance-create"), data=data, follow=True)

#         balance = Balances.objects.get(currency=self.currency, user=self.user1)
#         balance.balance = 100
#         balance.save()

#     @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
#     def test_deposit_currency(self, mock_poopen):

#         mock_poopen.side_effect = MockPoopenReceiveCurrencies().mock_poopen_tarocli

#         data = {
#             "amount": 10,
#             "currency": self.currency.id,
#             "description": "Test receive transaction",
#         }

#         response = self.client.post(
#             reverse("transaction-receive-taro"), data=data, follow=True
#         )

#         process_transactions_inbound_invoice_waiting_for()

#         transaction1 = response.context["transactions"]
#         transaction1 = Transactions.objects.get(id=transaction1.id)
#         self.assertEqual(transaction1.invoice_inbound, "test_taro_invoice")
#         self.assertEqual(transaction1.status, "inbound_invoice_generated")

#         self.assertEqual(self.user1.get_btc_pending_balance(), 0)
#         self.assertEqual(self.user1.get_btc_balance(), get_initial_free_btc_balance())
#         self.assertEqual(self.user1.get_balances(currency=self.currency).balance, 100)

#         process_transactions_inbound_invoice_generated()

#         transaction1.refresh_from_db()
#         self.assertEqual(transaction1.invoice_inbound, "test_taro_invoice")
#         self.assertEqual(transaction1.status, "inbound_invoice_paid")
#         self.assertEqual(transaction1.tx_id, "mock_tx_id")
#         self.assertEqual(self.user1.get_balances(currency=self.currency).balance, 110)


# @common_settings
# class RequestTestWithdrawAsset(TestCase):
#     def setUp(self):
#         set_up_free_amount_user()
#         self.user1 = User.objects.create_user(
#             username="john", email="jlennon@beatles.com", password="glass onion"
#         )

#         self.user1.save()

#         self.user2 = User.objects.create_user(
#             username="john2", email="jlennon@beatles.com", password="glass onion"
#         )

#         self.user2.save()

#         self.client.login(username="john", password="glass onion")

#         data = {
#             "acronym": "TC",
#             "asset_id": (
#                 "ece2f8e5dadf386790bafd16b12598e3258cf6c7e9b1e979b46503aea668ee79"
#             ),
#             "universe_host": "",
#             "picture_orig": "",
#         }

#         response = self.client.post(reverse("currency-create"), data=data, follow=True)

#         self.currency = Currencies.objects.get(acronym="TC")

#         data = {"currency": self.currency.id}

#         response = self.client.post(reverse("balance-create"), data=data, follow=True)

#         self.client.login(username="john2", password="glass onion")

#         self.currency = Currencies.objects.get(acronym="TC")

#         data = {"currency": self.currency.id}

#         response = self.client.post(reverse("balance-create"), data=data, follow=True)

#         balance = Balances.objects.get(currency=self.currency, user=self.user1)
#         balance.balance = 100
#         balance.save()

#         balance2 = Balances.objects.get(currency=self.currency, user=self.user2)
#         balance2.balance = 100
#         balance2.save()

#     def test_withdraw_currency(self):

#         self.client.login(username="john", password="glass onion")

#         data = {
#             "invoice_outbound": "taptb1qqqsqq3qan303ew6muux0y96l5ttzfvcuvjceak8axc7j7d5v5p6afngaeusgggz6angh6xxuntaprtls6syrdx5emgcts35gfr6h8y2knzdmqfghyusvggzn0zg9933snsunku3utvpc0djewfnjmldmzjwu9kuaw7ellu6g0dssqg237vngx",
#         }

#         response = self.client.post(
#             reverse("transaction-send-taro"), data=data, follow=True
#         )

#         form = response.context.get("form", [])
#         errors = {field.name: field.errors[0] for field in form if field.errors}
#         print(errors)
#         self.assertEqual({}, errors)

#         transaction = response.context["transactions"]

#         print(transaction)

#         balance = Balances.objects.get(currency=self.currency, user=self.user1)

#         self.assertEqual(balance.balance, 90)

#     @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
#     def test_withdraw_existing_invoice_fail(self, mock_poopen):

#         self.client.login(username="john", password="glass onion")

#         mock_poopen.side_effect = MockPoopenReceiveCurrencies(
#             test_invoice_to_return="taptb1qqqsqq3qan303ew6muux0y96l5ttzfvcuvjceak8axc7j7d5v5p6afngaeusgggz6angh6xxuntaprtls6syrdx5emgcts35gfr6h8y2knzdmqfghyusvggzn0zg9933snsunku3utvpc0djewfnjmldmzjwu9kuaw7ellu6g0dssqg237vngx"
#         ).mock_poopen_tarocli

#         data = {
#             "amount": 10,
#             "currency": self.currency.id,
#             "description": "Test receive transaction",
#         }

#         response = self.client.post(
#             reverse("transaction-receive-taro"), data=data, follow=True
#         )

#         print(response.context)

#         process_transactions_inbound_invoice_waiting_for()

#         self.client.logout()

#         self.client.login(username="john2", password="glass onion")

#         data = {
#             "invoice_outbound": "taptb1qqqsqq3qan303ew6muux0y96l5ttzfvcuvjceak8axc7j7d5v5p6afngaeusgggz6angh6xxuntaprtls6syrdx5emgcts35gfr6h8y2knzdmqfghyusvggzn0zg9933snsunku3utvpc0djewfnjmldmzjwu9kuaw7ellu6g0dssqg237vngx",
#         }

#         response = self.client.post(
#             reverse("transaction-send-taro"), data=data, follow=True
#         )

#         form = response.context.get("form", [])
#         errors = {field.name: field.errors[0] for field in form if field.errors}
#         self.assertEqual({}, dict(errors))

#         transaction = response.context["transactions"]

#         self.assertEqual(transaction.type, "internal")
#         self.assertEqual(transaction.amount, 10)
#         self.assertEqual(transaction.currency.id, self.currency.id)

#         process_transactions_internal()

#         balance = Balances.objects.get(currency=self.currency, user=self.user1)

#         balance2 = Balances.objects.get(currency=self.currency, user=self.user2)

#         self.assertEqual(balance.balance, 110)
#         self.assertEqual(balance2.balance, 90)


# def http_auth(username, password):
#     """
#     Encode Basic Auth username:password.
#     :param username:
#     :param password:
#     :return String:
#     """
#     data = f"{username}:{password}"
#     credentials = base64.b64encode(data.encode("utf-8")).strip()
#     auth_string = f'Basic {credentials.decode("utf-8")}'
#     return auth_string


# @common_settings
# class RequestTestApiAssetCreate(TestCase):
#     def setUp(self):
#         set_up_free_amount_user()
#         self.user1 = User.objects.create_user(
#             username="john", email="jlennon@beatles.com", password="glass onion"
#         )

#         self.user1.save()

#         self.client.login(username="john", password="glass onion")

#     @patch("walletapp.management.commands.handle_transactions.time.sleep")
#     @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
#     def test_create_currency(self, mock_poopen, mock_sleep):

#         data = {
#             "acronym": "ApiTC",
#             "asset_id": (
#                 "ece2f8e5dadf386790bafd16b12598e3258cf6c7e9b1e979b46503aea668ee79"
#             ),
#         }

#         response = self.client.post(
#             reverse("api-currency-create"),
#             json.dumps(data),
#             content_type="application/json",
#             follow=True,
#             **{"HTTP_AUTHORIZATION": http_auth("john", "glass onion")},
#         )

#         print(response.data)

#         currency = Currencies.objects.get(acronym="ApiTC")
#         self.assertEqual(
#             "ece2f8e5dadf386790bafd16b12598e3258cf6c7e9b1e979b46503aea668ee79",
#             currency.asset_id,
#         )

#         mock_poopen.side_effect = MockPoopenCurrencyCreate().mock_poopen_tarocli

#         process_get_currency_meta()

#         currency.refresh_from_db()

#         self.assertEqual(
#             currency.minting_transaction.status, "currency_registration_finished"
#         )

#         self.assertEqual(currency.acronym, "WAIF")
#         self.assertEqual(currency.name, "WaifuCoinQjyo")
#         self.assertEqual(
#             currency.description,
#             "Waifu Coin is a cryptocurrency focused on bringing people closer to"
#             " fictional characters through decentralized rewards.",
#         )


# @common_settings
# class RequestTestAssetBuy(TestCase):
#     def setUp(self):
#         set_up_free_amount_user()
#         self.user1 = User.objects.create_user(
#             username="john", email="jlennon@beatles.com", password="glass onion"
#         )

#         self.user1.save()

#         self.user2 = User.objects.create_user(
#             username="john2", email="jlennon@beatles.com", password="glass onion"
#         )

#         self.user2.save()

#         self.currency1 = Currencies.objects.create(
#             name="TestCaseCoin",
#             owner=self.user1,
#             picture_orig=None,
#             acronym="ACC",
#             asset_id="mock_asset_id",
#             description="This is my test coin",
#             supply=1000,
#             status="minted",
#         )

#         self.currency1.save()

#         balance = Balances.objects.create(
#             user=self.user1, currency=self.currency1, balance=1000
#         )
#         balance.save()

#         self.listing1 = Listings.objects.create(
#             user=self.user1, currency=self.currency1
#         )

#         balance = Balances.objects.get(
#             currency=Currencies.objects.get(name="Bitcoin"), user=self.user2
#         )
#         balance.balance = 20000000
#         balance.save()

#         self.listing1.save()

#         self.client.login(username="john2", password="glass onion")

#     @patch("walletapp.management.commands.handle_transactions.time.sleep")
#     @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
#     def test_buy_currency_success(self, mock_poopen, mock_sleep):

#         data = {"currency": self.currency1.id, "amount": 300}

#         response = self.client.post(
#             reverse("buy-currency-asset"), data=data, follow=True
#         )

#         print(response.context)

#         form = response.context.get("form", [])
#         errors = {field.name: field.errors[0] for field in form if field.errors}
#         print(errors)
#         self.assertEqual({}, errors)

#         process_transactions_exchange()

#         balance = Balances.objects.get(user=self.user2, currency=self.currency1)
#         self.assertEqual(balance.balance, 300)

#         balance = Balances.objects.get(user=self.user1, currency=self.currency1)
#         self.assertEqual(balance.balance, 700)

#     @patch("walletapp.management.commands.handle_transactions.time.sleep")
#     @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
#     def test_buy_currency_fail1(self, mock_poopen, mock_sleep):

#         data = {"currency": self.currency1.id, "amount": 501}

#         response = self.client.post(
#             reverse("buy-currency-asset"), data=data, follow=True
#         )

#         print(response.context)

#         form = response.context.get("form", [])
#         errors = {field.name: field.errors[0] for field in form if field.errors}
#         print(errors)
#         self.assertEqual(
#             {
#                 "amount": (
#                     "Please enter an amount smaller than 501 ACC as that is close to"
#                     " the maximum available in liquidity pool"
#                 )
#             },
#             errors,
#         )

#     @patch("walletapp.management.commands.handle_transactions.time.sleep")
#     @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
#     def test_buy_currency_fail2(self, mock_poopen, mock_sleep):

#         for i in range(0, 14):

#             amt_to_buy = int(500 / (2 ** (i)))

#             if amt_to_buy == 0:
#                 amt_to_buy = 1

#             data = {"currency": self.currency1.id, "amount": amt_to_buy}

#             response = self.client.post(
#                 reverse("buy-currency-asset"), data=data, follow=True
#             )

#             form = response.context.get("form", [])
#             errors = {field.name: field.errors[0] for field in form if field.errors}
#             print(errors)

#             self.assertEqual({}, errors)
#             process_transactions_exchange()

#         amt_to_buy = 1

#         data = {"currency": self.currency1.id, "amount": amt_to_buy}

#         response = self.client.post(
#             reverse("buy-currency-asset"), data=data, follow=True
#         )

#         form = response.context.get("form", [])
#         errors = {field.name: field.errors[0] for field in form if field.errors}
#         print(errors)

#         self.assertEqual(
#             {
#                 "amount": (
#                     "Please enter an amount smaller than 1 ACC as that is close to the "
#                     "maximum available in liquidity pool"
#                 )
#             },
#             errors,
#         )
#         process_transactions_exchange()


# @common_settings
# class RequestTestAssetSell(TestCase):
#     def setUp(self):
#         set_up_free_amount_user()
#         self.user1 = User.objects.create_user(
#             username="john", email="jlennon@beatles.com", password="glass onion"
#         )

#         self.user1.save()

#         self.user2 = User.objects.create_user(
#             username="john2", email="jlennon@beatles.com", password="glass onion"
#         )

#         self.user2.save()

#         self.currency1 = Currencies.objects.create(
#             name="TestCaseCoin",
#             owner=self.user1,
#             picture_orig=None,
#             acronym="ACC",
#             asset_id="mock_asset_id",
#             description="This is my test coin",
#             supply=1000,
#             status="minted",
#         )

#         self.currency1.save()

#         balance = Balances.objects.create(
#             user=self.user1, currency=self.currency1, balance=1000
#         )
#         balance.save()

#         self.listing1 = Listings.objects.create(
#             user=self.user1, currency=self.currency1
#         )

#         balance = Balances.objects.create(
#             currency=self.currency1, user=self.user2, balance=1000000
#         )
#         balance.save()

#         self.listing1.save()

#         self.client.login(username="john2", password="glass onion")

#     @patch("walletapp.management.commands.handle_transactions.time.sleep")
#     @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
#     def test_sell_currency_success(self, mock_poopen, mock_sleep):

#         data = {"currency": self.currency1.id, "amount": 300}

#         response = self.client.post(reverse("sell-taro-asset"), data=data, follow=True)

#         print(response.context)

#         form = response.context.get("form", [])
#         errors = {field.name: field.errors[0] for field in form if field.errors}
#         print(errors)
#         self.assertEqual({}, errors)

#         process_transactions_exchange()

#         balance = Balances.objects.get(user=self.user2, currency=self.currency1)
#         self.assertEqual(balance.balance, 1000000 - 300)

#         balance = Balances.objects.get(user=self.user1, currency=self.currency1)
#         self.assertEqual(balance.balance, 1300)

#     @patch("walletapp.management.commands.handle_transactions.time.sleep")
#     @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
#     def test_sell_currency_fail1(self, mock_poopen, mock_sleep):

#         data = {
#             "currency": self.currency1.id,
#             "amount": int(2000 / self.listing1.get_price_sat()) + 1,
#         }

#         response = self.client.post(reverse("sell-taro-asset"), data=data, follow=True)

#         print(response.context)

#         form = response.context.get("form", [])
#         errors = {field.name: field.errors[0] for field in form if field.errors}

#         self.assertEqual(
#             {
#                 "amount": (
#                     "Please enter an amount larger than 0 ACC and smaller than 501 ACC."
#                     " This is due to liquidity pool restrictions."
#                 )
#             },
#             errors,
#         )


@common_settings
class PendingFundsInExchange(TestCase):
    def setUp(self):
        set_up_free_amount_user()
        self.user1 = User.objects.create_user(
            username="john", email="jlennon@beatles.com", password="glass onion"
        )

        self.user1.save()

        self.user2 = User.objects.create_user(
            username="jane", email="jane@beatles.com", password="glass onion"
        )

        self.user2.save()

        # self.currency_btc = Currencies.objects.create(
        #     name="Bitcoin",
        #     picture_orig=None,
        #     acronym="SAT",
        #     asset_id="",
        #     description="This is my test coin",
        #     supply=1000,
        #     status="waiting_for_miting_transaction",
        # )
        # self.currency_btc.save()

        self.currency = Currencies.objects.create(
            name="TestCaseCoin",
            owner=self.user1,
            picture_orig=None,
            acronym="ACC",
            asset_id="xxx",
            description="This is my test coin",
            supply=100,
            status="waiting_for_create_transaction",
        )
        self.currency.save()

        self.user1_bal_btc = Balances.objects.get(
            user=self.user1, currency=get_currency_btc()
        )
        self.user1_bal_btc.balance = 1000
        self.user1_bal_btc.save()

        self.user1_bal = Balances.objects.get(user=self.user1, currency=self.currency)
        self.user1_bal.balance = 100
        self.user1_bal.save()

        self.user2_bal_btc = Balances.objects.get(
            user=self.user2, currency=get_currency_btc()
        )
        self.user2_bal_btc.balance = 100000
        self.user2_bal_btc.save()

        self.user2_bal = Balances.objects.create(
            user=self.user2, currency=self.currency, balance=100
        )
        self.user2_bal.save()

        self.user_fee_bal_btc = Balances.objects.get(
            user=get_fee_user(), currency=get_currency_btc()
        )

        self.listing = Listings.objects.create(
            user=self.user1, currency=self.currency, type="lp"
        )
        self.listing.save()

        process_transactions_internal()

        self.user1_bal_btc.refresh_from_db()
        self.user2_bal_btc.refresh_from_db()
        self.user_fee_bal_btc.refresh_from_db()

        self.btc_sum = (
            self.user2_bal_btc.balance
            + self.user1_bal_btc.balance
            + self.user_fee_bal_btc.balance
        )

    #     @patch("walletapp.management.commands.handle_transactions.time.sleep")
    #     @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
    #     def test_transactions_buy(self, mock_poopen, mock_sleep):

    #         print("price before")
    #         print(self.listing.get_price_sat())
    #         print("price before with -10 SATs")
    #         print(self.listing.get_price_sat(-10))

    #         trn1 = Transactions.objects.create(
    #             user=self.listing.user,
    #             destination_user=self.user2,
    #             direction="outbound",
    #             type="exchange",
    #             status="exchange_started",
    #             currency=self.listing.currency,
    #             amount=10,
    #         )
    #         trn1.save()
    #         price_after_save = self.listing.get_price_sat()
    #         process_transactions_exchange()
    #         price_after_process = self.listing.get_price_sat()
    #         self.assertEqual(price_after_save, price_after_process)
    #         # self.user1_bal.refresh_from_db()
    #         # self.user2_bal.refresh_from_db()

    #         # self.user1_bal_btc.refresh_from_db()
    #         # self.user2_bal_btc.refresh_from_db()

    #         # print(self.user2_bal.balance)
    #         # print(self.user2_bal.pending_balance)

    #         # print(self.user2_bal_btc.balance)
    #         # print(self.user2_bal_btc.pending_balance)

    #         # print(self.user1_bal.balance)
    #         # print(self.user1_bal.pending_balance)
    #         # print(self.user1_bal_btc.balance)
    #         # print(self.user1_bal_btc.pending_balance)

    #         # print(1000/(100-25))
    #         self.listing.refresh_from_db()
    #         print(self.listing.get_price_sat())
    #         print("price before 3")
    #         print(self.listing.get_price_sat())
    #         trn2 = Transactions.objects.create(
    #             user=self.listing.user,
    #             destination_user=self.user2,
    #             direction="outbound",
    #             type="exchange",
    #             status="exchange_started",
    #             currency=self.listing.currency,
    #             amount=10,
    #         )
    #         trn2.save()
    #         trn3 = Transactions.objects.create(
    #             user=self.listing.user,
    #             destination_user=self.user2,
    #             direction="outbound",
    #             type="exchange",
    #             status="exchange_started",
    #             currency=self.listing.currency,
    #             amount=10,
    #         )
    #         trn3.save()
    #         print("price after 3")
    #         print(self.listing.get_price_sat())
    #         price_after_save = self.listing.get_price_sat()
    #         process_transactions_exchange()
    #         price_after_process = self.listing.get_price_sat()
    #         self.assertEqual(price_after_save, price_after_process)

    #     @patch("walletapp.management.commands.handle_transactions.time.sleep")
    #     @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
    #     def test_transactions_sell(self, mock_poopen, mock_sleep):

    #         print("price before")
    #         print(self.listing.get_price_sat())
    #         print("price before with 10 SATs")
    #         print(self.listing.get_price_sat(10))

    #         trn1 = Transactions.objects.create(
    #             user=self.listing.user,
    #             destination_user=self.user2,
    #             direction="inbound",
    #             type="exchange",
    #             status="exchange_started",
    #             currency=self.listing.currency,
    #             amount=10,
    #         )
    #         trn1.save()
    #         print("price after")
    #         print(self.listing.get_price_sat())

    #         price_after_save = self.listing.get_price_sat()
    #         process_transactions_exchange()
    #         price_after_process = self.listing.get_price_sat()
    #         self.assertEqual(price_after_save, price_after_process)

    #         print("price before 3")
    #         print(self.listing.get_price_sat())

    #         trn2 = Transactions.objects.create(
    #             user=self.listing.user,
    #             destination_user=self.user2,
    #             direction="inbound",
    #             type="exchange",
    #             status="exchange_started",
    #             currency=self.listing.currency,
    #             amount=10,
    #         )
    #         trn2.save()
    #         trn3 = Transactions.objects.create(
    #             user=self.listing.user,
    #             destination_user=self.user2,
    #             direction="inbound",
    #             type="exchange",
    #             status="exchange_started",
    #             currency=self.listing.currency,
    #             amount=10,
    #         )
    #         trn3.save()
    #         self.listing.refresh_from_db()
    #         print("price after 3")
    #         print(self.listing.get_price_sat())
    #         price_after_save = self.listing.get_price_sat()
    #         process_transactions_exchange()
    #         price_after_process = self.listing.get_price_sat()
    #         self.assertEqual(price_after_save, price_after_process)

    @patch("walletapp.management.commands.handle_transactions.time.sleep")
    @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
    def test_transactions_sell(self, mock_poopen, mock_sleep):
        print("price before")
        print(self.listing.get_price_sat())

        product_initial = self.user2_bal.balance * self.user1_bal_btc.balance

        for i in range(0, 10):
            print(i)
            trn1 = Transactions.objects.create(
                user=self.listing.user,
                destination_user=self.user2,
                direction="inbound",
                type="exchange",
                status="exchange_started",
                currency=self.listing.currency,
                amount=20,
                listing=self.listing,
            )
            trn1.save()

            print("price after sale")
            self.listing.refresh_from_db()
            print(self.listing.get_price_sat())

            process_transactions_exchange()
            process_transactions_internal()
            print(self.listing.get_price_sat())

            trn2 = Transactions.objects.create(
                user=self.listing.user,
                destination_user=self.user2,
                direction="outbound",
                type="exchange",
                status="exchange_started",
                currency=self.listing.currency,
                amount=20,
                listing=self.listing,
            )
            trn2.save()
            process_transactions_exchange()
            process_transactions_internal()

            self.user1_bal_btc.refresh_from_db()
            self.user2_bal_btc.refresh_from_db()
            self.user1_bal.refresh_from_db()
            self.user2_bal.refresh_from_db()
            self.user_fee_bal_btc.refresh_from_db()

            # print("user 1 BTC")
            # print(self.user1_bal_btc.balance)
            # print("user 1 curr")
            # print(self.user1_bal.balance)

            print("BTC sum")
            print(self.user1_bal_btc.balance * self.user1_bal.balance)

            print("product")
            print(self.user2_bal.balance * self.user1_bal_btc.balance)

            self.assertEqual(
                0,
                self.user2_bal_btc.pending_balance
                + self.user1_bal_btc.pending_balance
                + self.user_fee_bal_btc.pending_balance,
            )
            self.assertEqual(
                self.btc_sum,
                self.user2_bal_btc.balance
                + self.user1_bal_btc.balance
                + self.user_fee_bal_btc.balance,
            )
            print("price after purchase")
            self.listing.refresh_from_db()
            print(self.listing.get_price_sat())

        product_final = self.user2_bal.balance * self.user1_bal_btc.balance
        self.assertGreaterEqual(product_final, product_initial)

        print("LP btc")
        print(self.user1_bal_btc.balance)
        print("LP curr")
        print(self.user1_bal.balance)

        print("price after")
        print(self.listing.get_price_sat())


# @common_settings
# class FeesInExchange(TestCase):
#     def setUp(self):
#         set_up_free_amount_user()
#         self.user1 = User.objects.create_user(
#             username="john", email="jlennon@beatles.com", password="glass onion"
#         )

#         self.user1.save()

#         self.user2 = User.objects.create_user(
#             username="jane", email="jane@beatles.com", password="glass onion"
#         )

#         self.user2.save()

#         # self.currency_btc = Currencies.objects.create(
#         #     name="Bitcoin",
#         #     picture_orig=None,
#         #     acronym="SAT",
#         #     asset_id="",
#         #     description="This is my test coin",
#         #     supply=1000,
#         #     status="waiting_for_miting_transaction",
#         # )
#         # self.currency_btc.save()

#         self.currency = Currencies.objects.create(
#             name="TestCaseCoin",
#             owner=self.user1,
#             picture_orig=None,
#             acronym="ACC",
#             asset_id="xxx",
#             description="This is my test coin",
#             supply=100,
#             status="waiting_for_create_transaction",
#         )
#         self.currency.save()

#         self.user1_bal_btc = Balances.objects.get(
#             user=self.user1, currency=get_currency_btc()
#         )
#         self.user1_bal_btc.balance = 1000
#         self.user1_bal_btc.save()

#         self.user1_bal = Balances.objects.get(user=self.user1, currency=self.currency)
#         self.user1_bal.balance = 100
#         self.user1_bal.save()

#         self.user2_bal_btc = Balances.objects.get(
#             user=self.user2, currency=get_currency_btc()
#         )
#         self.user2_bal_btc.balance = 100
#         self.user2_bal_btc.save()

#         self.user2_bal = Balances.objects.create(
#             user=self.user2, currency=self.currency, balance=100
#         )
#         self.user2_bal.save()

#         self.listing = Listings.objects.create(user=self.user1, currency=self.currency)
#         self.listing.save()

#         self.btc_sum = self.user2_bal_btc.balance + self.user1_bal_btc.balance

#         self.fee_user = get_fee_user()
#         self.fee_user_balance_btc = Balances.objects.get(
#             user=self.fee_user, currency=get_currency_btc()
#         )
#         self.fee_user_balance_btc.balance = 0
#         self.fee_user_balance_btc.save()
#         process_transactions_internal()

#     @patch("walletapp.management.commands.handle_transactions.time.sleep")
#     @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
#     def test_transactions_buy(self, mock_poopen, mock_sleep):

#         amount = 2
#         price = self.listing.get_price_sat()

#         self.user2_bal_btc.refresh_from_db()
#         balance_orig = self.user2_bal_btc.balance

#         trn1 = Transactions.objects.create(
#             user=self.listing.user,
#             listing=self.listing,
#             destination_user=self.user2,
#             direction="outbound",
#             type="exchange",
#             status="exchange_started",
#             currency=self.listing.currency,
#             amount=amount,
#         )
#         trn1.save()
#         self.user2_bal_btc.refresh_from_db()

#         self.assertEqual(
#             self.user2_bal_btc.balance,
#             balance_orig - int(price * amount) - int(max(price * amount * 0.003, 3)),
#         )
#         self.assertEqual(self.user2_bal.balance, 100)
#         self.assertEqual(
#             self.user2_bal_btc.pending_balance,
#             price * amount + max(price * amount * 0.005, 3),
#         )
#         self.assertEqual(self.user2_bal.pending_balance, 0)

#         self.assertEqual(
#             self.user2_bal_btc.pending_balance,
#             price * amount + max(price * amount * 0.005, 3),
#         )

#         transactions = Transactions.objects.filter(user=self.user2)

#         self.assertEqual(len(transactions), 2)

#         for trn in transactions:
#             if trn.type == "fee":
#                 self.assertEqual(trn.direction, "outbound")
#                 self.assertEqual(trn.amount, max(price * amount * 0.005, 3))
#                 self.assertEqual(trn.status, "placeholder_fee")
#             if trn.type == "exchange":
#                 self.assertEqual(trn.direction, "outbound")
#                 self.assertEqual(trn.amount, price * amount)
#                 self.assertEqual(trn.status, "exchange_started")

#         process_transactions_exchange()

#         self.user2_bal_btc.refresh_from_db()
#         self.user2_bal.refresh_from_db()

#         self.assertEqual(
#             self.user2_bal_btc.balance,
#             balance_orig - price * amount - max(price * amount * 0.005, 3),
#         )
#         self.assertEqual(self.user2_bal.balance, 100 + amount)
#         self.assertEqual(self.user2_bal_btc.pending_balance, 0)
#         self.assertEqual(self.user2_bal.pending_balance, 0)

#         transactions = Transactions.objects.filter(user=self.user2)

#         self.assertEqual(len(transactions), 2)

#         for trn in transactions:
#             if trn.type == "fee":
#                 self.assertEqual(trn.direction, "outbound")
#                 self.assertEqual(trn.amount, max(price * amount * 0.005, 3))
#                 self.assertEqual(trn.status, "fee_paid")
#             if trn.type == "exchange":
#                 self.assertEqual(trn.direction, "outbound")
#                 self.assertEqual(trn.amount, price * amount)
#                 self.assertEqual(trn.status, "exchange_finished")

#     @patch("walletapp.management.commands.handle_transactions.time.sleep")
#     @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
#     def test_transactions_sell(self, mock_poopen, mock_sleep):

#         amount = 2
#         price = self.listing.get_price_sat(amount)

#         self.user2_bal_btc.refresh_from_db()
#         balance_orig = self.user2_bal_btc.balance

#         trn1 = Transactions.objects.create(
#             user=self.listing.user,
#             listing=self.listing,
#             destination_user=self.user2,
#             direction="inbound",
#             type="exchange",
#             status="exchange_started",
#             currency=self.listing.currency,
#             amount=2,
#         )
#         trn1.save()
#         self.user2_bal_btc.refresh_from_db()
#         self.user2_bal.refresh_from_db()

#         self.assertEqual(
#             self.user2_bal_btc.balance, balance_orig - max(price * amount * 0.003, 3)
#         )
#         self.assertEqual(self.user2_bal.balance, balance_orig - price * amount)
#         self.assertEqual(
#             self.user2_bal_btc.pending_balance, max(price * amount * 0.003, 3)
#         )
#         self.assertEqual(self.user2_bal.pending_balance, 0)

#         transactions = Transactions.objects.filter(user=self.user2)

#         self.assertEqual(len(transactions), 2)

#         for trn in transactions:
#             if trn.type == "fee":
#                 self.assertEqual(trn.direction, "outbound")
#                 self.assertEqual(trn.amount, max(price * amount * 0.005, 3))
#                 self.assertEqual(trn.status, "placeholder_fee")
#             if trn.type == "exchange":
#                 self.assertEqual(trn.direction, "inbound")
#                 self.assertEqual(trn.amount, int(price * amount))
#                 self.assertEqual(trn.status, "exchange_started")

#         process_transactions_exchange()

#         self.user2_bal_btc.refresh_from_db()
#         self.user2_bal.refresh_from_db()
#         self.fee_user_balance_btc.refresh_from_db()

#         self.assertEqual(
#             self.user2_bal_btc.balance,
#             balance_orig + int(price * amount) - max(price * amount * 0.005, 3),
#         )
#         self.assertEqual(self.user2_bal.balance, 100 - amount)
#         self.assertEqual(self.user2_bal_btc.pending_balance, 0)
#         self.assertEqual(self.user2_bal.pending_balance, 0)
#         self.assertEqual(
#             self.fee_user_balance_btc.balance, max(price * amount * 0.005, 3)
#         )

#         transactions = Transactions.objects.filter(user=self.user2)

#         self.assertEqual(len(transactions), 2)

#         for trn in transactions:
#             if trn.type == "fee":
#                 self.assertEqual(trn.direction, "outbound")
#                 self.assertEqual(trn.amount, max(price * amount * 0.005, 3))
#                 self.assertEqual(trn.status, "fee_paid")
#             if trn.type == "exchange":
#                 self.assertEqual(trn.direction, "inbound")
#                 self.assertEqual(trn.amount, int(price * amount))
#                 self.assertEqual(trn.status, "exchange_finished")

#     @patch("walletapp.management.commands.handle_transactions.time.sleep")
#     @patch("walletapp.management.commands.handle_transactions.subprocess.Popen")
#     def test_transactions_sell_fail(self, mock_poopen, mock_sleep):

#         amount = 2
#         price = self.listing.get_price_sat(amount)

#         self.user2_bal_btc.balance = 0
#         self.user2_bal_btc.save()

#         self.user2_bal_btc.refresh_from_db()
#         balance_orig = self.user2_bal_btc.balance
#         with self.assertRaises(Exception):
#             trn1 = Transactions.objects.create(
#                 user=self.listing.user,
#                 listing=self.listing,
#                 destination_user=self.user2,
#                 direction="inbound",
#                 type="exchange",
#                 status="exchange_started",
#                 currency=self.listing.currency,
#                 amount=2,
#             )
#             trn1.save()


@common_settings
class RandomExchange(TestCase):
    def setUp(self):
        set_up_free_amount_user()
        self.users = []

        for i in range(0, 100):
            self.users[i] = User.objects.create_user(
                username="john", email="jlennon@beatles.com", password="glass onion"
            )

            self.user1.save()

        self.currency_btc = Currencies.objects.create(
            name="Bitcoin",
            picture_orig=None,
            acronym="SAT",
            asset_id="",
            description="This is my test coin",
            supply=1000,
            status="waiting_for_miting_transaction",
        )
        self.currency_btc.save()

        self.currency = Currencies.objects.create(
            name="TestCaseCoin",
            owner=self.user1,
            picture_orig=None,
            acronym="ACC",
            asset_id="xxx",
            description="This is my test coin",
            supply=100,
            status="waiting_for_create_transaction",
        )
        self.currency.save()

        self.user1_bal_btc = Balances.objects.get(
            user=self.user1, currency=get_currency_btc()
        )
        self.user1_bal_btc.balance = 1000
        self.user1_bal_btc.save()

        self.user1_bal = Balances.objects.get(user=self.user1, currency=self.currency)
        self.user1_bal.balance = 100
        self.user1_bal.save()

        self.user2_bal_btc = Balances.objects.get(
            user=self.user2, currency=get_currency_btc()
        )
        self.user2_bal_btc.balance = 100000
        self.user2_bal_btc.save()

        self.user2_bal = Balances.objects.create(
            user=self.user2, currency=self.currency, balance=100
        )
        self.user2_bal.save()

        self.listing = Listings.objects.create(user=self.user1, currency=self.currency)
        self.listing.save()

        self.btc_sum = self.user2_bal_btc.balance + self.user1_bal_btc.balance

        process_transactions_internal()


@common_settings
class DoubleListingExchange(TestCase):
    def setUp(self):
        set_up_free_amount_user()
        self.user1 = User.objects.create_user(
            username="john", email="jlennon@beatles.com", password="glass onion"
        )

        self.user1.save()

        self.user2 = User.objects.create_user(
            username="jane", email="jane@beatles.com", password="glass onion"
        )

        self.user2.save()

        self.currency = Currencies.objects.create(
            name="TestCaseCoin",
            owner=self.user1,
            picture_orig=None,
            acronym="ACC",
            asset_id="xxx",
            description="This is my test coin",
            supply=100,
            status="waiting_for_create_transaction",
        )
        self.currency.save()

        self.user1_bal_btc = Balances.objects.get(
            user=self.user1, currency=get_currency_btc()
        )
        self.user1_bal_btc.balance = 5000
        self.user1_bal_btc.save()

        self.user1_bal = Balances.objects.get(user=self.user1, currency=self.currency)
        self.user1_bal.balance = 100
        self.user1_bal.save()

        self.user2_bal_btc = Balances.objects.get(
            user=self.user2, currency=get_currency_btc()
        )
        self.user2_bal_btc.balance = 100000
        self.user2_bal_btc.save()

        self.user2_bal = Balances.objects.create(
            user=self.user2, currency=self.currency, balance=100
        )
        self.user2_bal.save()

        self.listing_1 = Listings.objects.create(
            user=self.user1,
            currency=self.currency,
            type="order_bid",
            amount=33,
            price_sat=123,
        )
        self.listing_1.save()

        self.listing_2 = Listings.objects.create(
            user=self.user1,
            currency=self.currency,
            type="order_ask",
            amount=33,
            price_sat=123,
        )
        self.listing_2.save()

        self.btc_sum = self.user2_bal_btc.balance + self.user1_bal_btc.balance

        process_transactions_internal()

    def test_success_bid(self):
        self.user1_bal.refresh_from_db()
        self.user1_bal_btc.refresh_from_db()
        self.user2_bal.refresh_from_db()
        self.user2_bal_btc.refresh_from_db()

        user1_bal_orig = self.user1_bal.balance
        user1_bal_btc_orig = self.user1_bal_btc.balance
        user2_bal_orig = self.user2_bal.balance
        user2_bal_btc_orig = self.user2_bal_btc.balance

        trn1 = Transactions.objects.create(
            user=self.listing_1.user,
            listing=self.listing_1,
            currency=self.listing_1.currency,
            destination_user=self.user2,
            amount=self.listing_1.amount,
            direction="inbound",
            type="exchange",
            status="exchange_started",
        )

        trn1.save()
        # trn2 = Transactions.objects.create(
        #     user=self.listing_1.user,
        #     listing=self.listing_1,
        #     currency=self.listing_1.currency,
        #     destination_user=self.user2,
        #     amount=self.listing_1.amount,
        #     direction="inbound",
        #     type="exchange",
        #     status="exchange_started",
        # )
        # trn2.save()

        self.user1_bal.refresh_from_db()
        self.user1_bal_btc.refresh_from_db()
        self.user2_bal.refresh_from_db()
        self.user2_bal_btc.refresh_from_db()
        trn1.refresh_from_db()

        user1_bal_new = self.user1_bal.balance
        user1_bal_btc_new = self.user1_bal_btc.balance
        user2_bal_new = self.user2_bal.balance
        user2_bal_btc_new = self.user2_bal_btc.balance

        self.assertEqual(trn1.status, "exchange_started")
        self.assertEqual(
            trn1.associated_exchange_transaction.status, "exchange_started"
        )
        self.assertEqual(trn1.fee_transaction.status, "placeholder_fee")

        self.assertEqual(user1_bal_new - user1_bal_orig, 0)
        self.assertEqual(user2_bal_new - user2_bal_orig, -33)

        self.assertEqual(user1_bal_btc_new - user1_bal_btc_orig, -123 * 33)
        self.assertEqual(
            user2_bal_btc_new - user2_bal_btc_orig,
            -get_fee_sat_estimate_exchange(123 * 33),
        )

        self.assertEqual(self.user1_bal.pending_balance, 0)
        self.assertEqual(self.user2_bal.pending_balance, 33)
        self.assertEqual(self.user1_bal_btc.pending_balance, 123 * 33)
        self.assertEqual(
            self.user2_bal_btc.pending_balance, get_fee_sat_estimate_exchange(123 * 33)
        )

        process_transactions_exchange()

        self.user1_bal.refresh_from_db()
        self.user1_bal_btc.refresh_from_db()
        self.user2_bal.refresh_from_db()
        self.user2_bal_btc.refresh_from_db()
        trn1.refresh_from_db()
        # trn2.refresh_from_db()

        user1_bal_new = self.user1_bal.balance
        user1_bal_btc_new = self.user1_bal_btc.balance
        user2_bal_new = self.user2_bal.balance
        user2_bal_btc_new = self.user2_bal_btc.balance

        print(user2_bal_btc_orig)
        print(user2_bal_btc_new)

        print(trn1.status)
        print(trn1.status_description)
        # print(trn2.status)
        # print(trn2.status_description)

        self.assertEqual(trn1.status, "exchange_finished")
        self.assertEqual(
            trn1.associated_exchange_transaction.status, "exchange_finished"
        )
        self.assertEqual(trn1.fee_transaction.status, "fee_paid")

        self.assertEqual(user1_bal_new - user1_bal_orig, 33)
        self.assertEqual(user2_bal_new - user2_bal_orig, -33)

        self.assertEqual(user1_bal_btc_new - user1_bal_btc_orig, -123 * 33)
        self.assertEqual(
            user2_bal_btc_new - user2_bal_btc_orig,
            123 * 33 - get_fee_sat_estimate_exchange(123 * 33),
        )

        self.assertEqual(self.user1_bal.pending_balance, 0)
        self.assertEqual(self.user2_bal.pending_balance, 0)
        self.assertEqual(self.user1_bal_btc.pending_balance, 0)
        self.assertEqual(self.user2_bal_btc.pending_balance, 0)

    def test_success_ask(self):
        self.user1_bal.refresh_from_db()
        self.user1_bal_btc.refresh_from_db()
        self.user2_bal.refresh_from_db()
        self.user2_bal_btc.refresh_from_db()

        user1_bal_orig = self.user1_bal.balance
        user1_bal_btc_orig = self.user1_bal_btc.balance
        user2_bal_orig = self.user2_bal.balance
        user2_bal_btc_orig = self.user2_bal_btc.balance

        trn1 = Transactions.objects.create(
            user=self.listing_2.user,
            listing=self.listing_2,
            currency=self.listing_2.currency,
            destination_user=self.user2,
            amount=self.listing_2.amount,
            direction="outbound",
            type="exchange",
            status="exchange_started",
        )

        trn1.save()
        # trn2 = Transactions.objects.create(
        #     user=self.listing_1.user,
        #     listing=self.listing_1,
        #     currency=self.listing_1.currency,
        #     destination_user=self.user2,
        #     amount=self.listing_1.amount,
        #     direction="inbound",
        #     type="exchange",
        #     status="exchange_started",
        # )
        # trn2.save()

        self.user1_bal.refresh_from_db()
        self.user1_bal_btc.refresh_from_db()
        self.user2_bal.refresh_from_db()
        self.user2_bal_btc.refresh_from_db()
        trn1.refresh_from_db()

        user1_bal_new = self.user1_bal.balance
        user1_bal_btc_new = self.user1_bal_btc.balance
        user2_bal_new = self.user2_bal.balance
        user2_bal_btc_new = self.user2_bal_btc.balance

        self.assertEqual(trn1.status, "exchange_started")
        self.assertEqual(
            trn1.associated_exchange_transaction.status, "exchange_started"
        )
        self.assertEqual(trn1.fee_transaction.status, "placeholder_fee")

        self.assertEqual(user1_bal_new - user1_bal_orig, -33)
        self.assertEqual(user2_bal_new - user2_bal_orig, 0)

        self.assertEqual(user1_bal_btc_new - user1_bal_btc_orig, 0)
        self.assertEqual(
            user2_bal_btc_new - user2_bal_btc_orig,
            -123 * 33 - get_fee_sat_estimate_exchange(123 * 33),
        )

        self.assertEqual(self.user1_bal.pending_balance, 33)
        self.assertEqual(self.user2_bal.pending_balance, 0)
        self.assertEqual(self.user1_bal_btc.pending_balance, 0)
        self.assertEqual(
            self.user2_bal_btc.pending_balance,
            123 * 33 + get_fee_sat_estimate_exchange(123 * 33),
        )

        process_transactions_exchange()

        self.user1_bal.refresh_from_db()
        self.user1_bal_btc.refresh_from_db()
        self.user2_bal.refresh_from_db()
        self.user2_bal_btc.refresh_from_db()
        trn1.refresh_from_db()
        # trn2.refresh_from_db()

        user1_bal_new = self.user1_bal.balance
        user1_bal_btc_new = self.user1_bal_btc.balance
        user2_bal_new = self.user2_bal.balance
        user2_bal_btc_new = self.user2_bal_btc.balance

        print(user2_bal_btc_orig)
        print(user2_bal_btc_new)

        print(trn1.status)
        print(trn1.status_description)
        # print(trn2.status)
        # print(trn2.status_description)

        self.assertEqual(trn1.status, "exchange_finished")
        self.assertEqual(
            trn1.associated_exchange_transaction.status, "exchange_finished"
        )
        self.assertEqual(trn1.fee_transaction.status, "fee_paid")

        self.assertEqual(user1_bal_new - user1_bal_orig, -33)
        self.assertEqual(user2_bal_new - user2_bal_orig, 33)

        self.assertEqual(user1_bal_btc_new - user1_bal_btc_orig, 123 * 33)
        self.assertEqual(
            user2_bal_btc_new - user2_bal_btc_orig,
            -123 * 33 - get_fee_sat_estimate_exchange(123 * 33),
        )

        self.assertEqual(self.user1_bal.pending_balance, 0)
        self.assertEqual(self.user2_bal.pending_balance, 0)
        self.assertEqual(self.user1_bal_btc.pending_balance, 0)
        self.assertEqual(self.user2_bal_btc.pending_balance, 0)

    def test_fail_no_balance_curr_left(self):
        self.user1_bal.refresh_from_db()
        self.user1_bal_btc.refresh_from_db()
        self.user2_bal.refresh_from_db()
        self.user2_bal_btc.refresh_from_db()

        self.user2_bal.balance = 32
        self.user2_bal.save()

        user1_bal_orig = self.user1_bal.balance
        user1_bal_btc_orig = self.user1_bal_btc.balance
        user2_bal_orig = self.user2_bal.balance
        user2_bal_btc_orig = self.user2_bal_btc.balance

        with self.assertRaises(BalanceException):
            trn1 = Transactions.objects.create(
                user=self.listing_1.user,
                listing=self.listing_1,
                currency=self.listing_1.currency,
                destination_user=self.user2,
                amount=self.listing_1.amount,
                direction="inbound",
                type="exchange",
                status="exchange_started",
            )

            trn1.save()
        # trn2 = Transactions.objects.create(
        #     user=self.listing_1.user,
        #     listing=self.listing_1,
        #     currency=self.listing_1.currency,
        #     destination_user=self.user2,
        #     amount=self.listing_1.amount,
        #     direction="inbound",
        #     type="exchange",
        #     status="exchange_started",
        # )
        # trn2.save()

        self.user1_bal.refresh_from_db()
        self.user1_bal_btc.refresh_from_db()
        self.user2_bal.refresh_from_db()
        self.user2_bal_btc.refresh_from_db()

        user1_bal_new = self.user1_bal.balance
        user1_bal_btc_new = self.user1_bal_btc.balance
        user2_bal_new = self.user2_bal.balance
        user2_bal_btc_new = self.user2_bal_btc.balance

        self.assertEqual(user1_bal_new - user1_bal_orig, 0)
        self.assertEqual(user2_bal_new - user2_bal_orig, 0)

        self.assertEqual(user1_bal_btc_new - user1_bal_btc_orig, 0)
        self.assertEqual(user2_bal_btc_new - user2_bal_btc_orig, 0)

        self.assertEqual(self.user1_bal.pending_balance, 0)
        self.assertEqual(self.user2_bal.pending_balance, 0)
        self.assertEqual(self.user1_bal_btc.pending_balance, 0)
        self.assertEqual(self.user2_bal_btc.pending_balance, 0)

        process_transactions_exchange()

        self.user1_bal.refresh_from_db()
        self.user1_bal_btc.refresh_from_db()
        self.user2_bal.refresh_from_db()
        self.user2_bal_btc.refresh_from_db()

        user1_bal_new = self.user1_bal.balance
        user1_bal_btc_new = self.user1_bal_btc.balance
        user2_bal_new = self.user2_bal.balance
        user2_bal_btc_new = self.user2_bal_btc.balance

        print(user2_bal_btc_orig)
        print(user2_bal_btc_new)

        self.assertEqual(user1_bal_new - user1_bal_orig, 0)
        self.assertEqual(user2_bal_new - user2_bal_orig, 0)

        self.assertEqual(user1_bal_btc_new - user1_bal_btc_orig, 0)
        self.assertEqual(user2_bal_btc_new - user2_bal_btc_orig, 0)

        self.assertEqual(self.user1_bal.pending_balance, 0)
        self.assertEqual(self.user2_bal.pending_balance, 0)
        self.assertEqual(self.user1_bal_btc.pending_balance, 0)
        self.assertEqual(self.user2_bal_btc.pending_balance, 0)

    def test_fail_no_balance_btc_left(self):
        self.user1_bal.refresh_from_db()
        self.user1_bal_btc.refresh_from_db()
        self.user2_bal.refresh_from_db()
        self.user2_bal_btc.refresh_from_db()

        self.user1_bal.balance = 0
        self.user1_bal.save()

        self.user1_bal_btc.balance = 321
        self.user1_bal_btc.save()

        user1_bal_orig = self.user1_bal.balance
        user1_bal_btc_orig = self.user1_bal_btc.balance
        user2_bal_orig = self.user2_bal.balance
        user2_bal_btc_orig = self.user2_bal_btc.balance

        with self.assertRaises(BalanceException):
            trn1 = Transactions.objects.create(
                user=self.listing_1.user,
                listing=self.listing_1,
                currency=self.listing_1.currency,
                destination_user=self.user2,
                amount=self.listing_1.amount,
                direction="inbound",
                type="exchange",
                status="exchange_started",
            )

            trn1.save()
        # trn2 = Transactions.objects.create(
        #     user=self.listing_1.user,
        #     listing=self.listing_1,
        #     currency=self.listing_1.currency,
        #     destination_user=self.user2,
        #     amount=self.listing_1.amount,
        #     direction="inbound",
        #     type="exchange",
        #     status="exchange_started",
        # )
        # trn2.save()

        self.user1_bal.refresh_from_db()
        self.user1_bal_btc.refresh_from_db()
        self.user2_bal.refresh_from_db()
        self.user2_bal_btc.refresh_from_db()

        user1_bal_new = self.user1_bal.balance
        user1_bal_btc_new = self.user1_bal_btc.balance
        user2_bal_new = self.user2_bal.balance
        user2_bal_btc_new = self.user2_bal_btc.balance

        self.assertEqual(user1_bal_new - user1_bal_orig, 0)
        self.assertEqual(user2_bal_new - user2_bal_orig, 0)

        self.assertEqual(user1_bal_btc_new - user1_bal_btc_orig, 0)
        self.assertEqual(user2_bal_btc_new - user2_bal_btc_orig, 0)

        self.assertEqual(self.user1_bal.pending_balance, 0)
        self.assertEqual(self.user2_bal.pending_balance, 0)
        self.assertEqual(self.user1_bal_btc.pending_balance, 0)
        self.assertEqual(self.user2_bal_btc.pending_balance, 0)

        process_transactions_exchange()

        self.user1_bal.refresh_from_db()
        self.user1_bal_btc.refresh_from_db()
        self.user2_bal.refresh_from_db()
        self.user2_bal_btc.refresh_from_db()

        user1_bal_new = self.user1_bal.balance
        user1_bal_btc_new = self.user1_bal_btc.balance
        user2_bal_new = self.user2_bal.balance
        user2_bal_btc_new = self.user2_bal_btc.balance

        print(user2_bal_btc_orig)
        print(user2_bal_btc_new)

        self.assertEqual(user1_bal_new - user1_bal_orig, 0)
        self.assertEqual(user2_bal_new - user2_bal_orig, 0)

        self.assertEqual(user1_bal_btc_new - user1_bal_btc_orig, 0)
        self.assertEqual(user2_bal_btc_new - user2_bal_btc_orig, 0)

        self.assertEqual(self.user1_bal.pending_balance, 0)
        self.assertEqual(self.user2_bal.pending_balance, 0)
        self.assertEqual(self.user1_bal_btc.pending_balance, 0)
        self.assertEqual(self.user2_bal_btc.pending_balance, 0)

    # def test_fail_double_trans(self):

    #     self.user1_bal.refresh_from_db()
    #     self.user1_bal_btc.refresh_from_db()
    #     self.user2_bal.refresh_from_db()
    #     self.user2_bal_btc.refresh_from_db()

    #     self.user1_bal.balance = 0
    #     self.user1_bal.save()

    #     self.user1_bal_btc.balance = 10000
    #     self.user1_bal_btc.save()

    #     user1_bal_orig = self.user1_bal.balance
    #     user1_bal_btc_orig = self.user1_bal_btc.balance
    #     user2_bal_orig = self.user2_bal.balance
    #     user2_bal_btc_orig = self.user2_bal_btc.balance

    #     trn1 = Transactions.objects.create(
    #         user=self.listing_1.user,
    #         listing=self.listing_1,
    #         currency=self.listing_1.currency,
    #         destination_user=self.user2,
    #         amount=self.listing_1.amount,
    #         direction="inbound",
    #         type="exchange",
    #         status="exchange_started",
    #     )

    #     trn1.save()
    #     trn2 = Transactions.objects.create(
    #         user=self.listing_1.user,
    #         listing=self.listing_1,
    #         currency=self.listing_1.currency,
    #         destination_user=self.user2,
    #         amount=self.listing_1.amount,
    #         direction="inbound",
    #         type="exchange",
    #         status="exchange_started",
    #     )
    #     trn2.save()

    #     self.user1_bal.refresh_from_db()
    #     self.user1_bal_btc.refresh_from_db()
    #     self.user2_bal.refresh_from_db()
    #     self.user2_bal_btc.refresh_from_db()
    #     trn1.refresh_from_db()

    #     user1_bal_new = self.user1_bal.balance
    #     user1_bal_btc_new = self.user1_bal_btc.balance
    #     user2_bal_new = self.user2_bal.balance
    #     user2_bal_btc_new = self.user2_bal_btc.balance

    #     self.assertEqual(trn1.status, "exchange_started")
    #     self.assertEqual(
    #         trn1.associated_exchange_transaction.status, "exchange_started"
    #     )
    #     self.assertEqual(trn1.fee_transaction.status, "placeholder_fee")

    #     self.assertEqual(user1_bal_new - user1_bal_orig, 0)
    #     self.assertEqual(user2_bal_new - user2_bal_orig, -33 * 2)

    #     self.assertEqual(user1_bal_btc_new - user1_bal_btc_orig, -123 * 33 * 2)
    #     self.assertEqual(
    #         user2_bal_btc_new - user2_bal_btc_orig,
    #         -get_fee_sat_estimate_exchange(123 * 33) * 2,
    #     )

    #     self.assertEqual(self.user1_bal.pending_balance, 0)
    #     self.assertEqual(self.user2_bal.pending_balance, 33 * 2)
    #     self.assertEqual(self.user1_bal_btc.pending_balance, 123 * 33 * 2)
    #     self.assertEqual(
    #         self.user2_bal_btc.pending_balance,
    #         get_fee_sat_estimate_exchange(123 * 33) * 2,
    #     )

    #     process_transactions_exchange()

    #     self.user1_bal.refresh_from_db()
    #     self.user1_bal_btc.refresh_from_db()
    #     self.user2_bal.refresh_from_db()
    #     self.user2_bal_btc.refresh_from_db()
    #     trn1.refresh_from_db()
    #     trn2.refresh_from_db()

    #     user1_bal_new = self.user1_bal.balance
    #     user1_bal_btc_new = self.user1_bal_btc.balance
    #     user2_bal_new = self.user2_bal.balance
    #     user2_bal_btc_new = self.user2_bal_btc.balance

    #     print(user2_bal_btc_orig)
    #     print(user2_bal_btc_new)

    #     print(trn1.status)
    #     print(trn1.status_description)
    #     # print(trn2.status)
    #     # print(trn2.status_description)

    #     self.assertEqual(trn1.status, "exchange_finished")
    #     self.assertEqual(
    #         trn1.associated_exchange_transaction.status, "exchange_finished"
    #     )
    #     self.assertEqual(trn1.fee_transaction.status, "fee_paid")

    #     self.assertEqual(trn2.status, "error")
    #     self.assertEqual(trn2.associated_exchange_transaction.status, "error")
    #     self.assertEqual(trn2.fee_transaction.status, "error")

    #     self.assertEqual(user1_bal_new - user1_bal_orig, 33)
    #     self.assertEqual(user2_bal_new - user2_bal_orig, -33)

    #     self.assertEqual(user1_bal_btc_new - user1_bal_btc_orig, -123 * 33)
    #     self.assertEqual(
    #         user2_bal_btc_new - user2_bal_btc_orig,
    #         123 * 33 - get_fee_sat_estimate_exchange(123 * 33),
    #     )

    #     self.assertEqual(self.user1_bal.pending_balance, 0)
    #     self.assertEqual(self.user2_bal.pending_balance, 0)
    #     self.assertEqual(self.user1_bal_btc.pending_balance, 0)
    #     self.assertEqual(self.user2_bal_btc.pending_balance, 0)


@common_settings
class PreviewImageCurrency(TestCase):
    def setUp(self):
        set_up_free_amount_user()
        self.user1 = User.objects.create_user(
            username="john", email="jlennon@beatles.com", password="glass onion"
        )

        self.user1.save()

        self.user2 = User.objects.create_user(
            username="jane", email="jane@beatles.com", password="glass onion"
        )

        self.user2.save()

        self.currency = Currencies.objects.create(
            name="TestCaseCoin",
            owner=self.user1,
            picture_orig=create_mock_image(),
            acronym="ACC",
            asset_id="xxx",
            description="This is my test coin",
            supply=100,
            status="waiting_for_create_transaction",
        )
        self.currency.save()

    def test_get_curr_card(self):
        picture_bytes = currency_card(self.currency.id)

        with open("test.jpg", "wb") as f:
            f.write(picture_bytes)
