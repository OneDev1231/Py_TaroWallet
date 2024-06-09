import json
import subprocess
import traceback
from zipfile import ZipFile

from django.core.management.base import BaseCommand
from django.db import transaction as djn_transaction
from django.db.models import Q
from walletapp.const_utils import (
    get_constant,
    get_fee_sat_per_vbyte,
    get_fee_sat_per_wu,
    set_constant,
)
from walletapp.models import (
    Balances,
    Collections,
    Currencies,
    ExternalInfoTable,
    Transactions,
    initiate_balances_from_files,
)
from walletapp.utils import (
    decode_invoice_lnd,
    decode_metadata,
    encode_metadata,
    get_currency_btc,
)

TARO_DIR = "/home/ec2-user/.taro"
REST_HOST = "localhost:8089"
MACAROON_PATH = "/home/ec2-user/.taro/data/testnet/admin.macaroon"
TLS_PATH = "/home/ec2-user/.taro/tls.cert"

import base64
import io
import json
import os
import time
from datetime import datetime, timedelta

from aws_xray_sdk.core import patch_all, xray_recorder
from django.core.files.base import ContentFile

xray_recorder.configure(
    plugins=("EC2Plugin", "ECSPlugin"),
    sampling=False,
    streaming_threshold=100,
    daemon_address="127.0.0.1:2000",
)
patch_all()

xray_recorder.configure(service="fallback_name", dynamic_naming="My application")

if os.getenv("DEV_ENV") == "PROD":
    network = "mainnet"
elif os.getenv("DEV_ENV") == "DEV":
    network = "testnet"
else:
    raise Exception(f"Unknown environment {os.getenv('DEV_ENV')}")

LNCLI_ARGS = [
    "--lnddir=/usr/share/efs/.lnd",
    "--tlscertpath=/usr/share/efs/.lnd/tls.cert",
]
TAPCLI_ARGS = [
    "--tapddir=/usr/share/efs/.tapd",
    "--tlscertpath=/usr/share/efs/.tapd/tls.cert",
]


def adjust_fee():
    if network == "testnet":
        comm = [
            "/bitcoin-22.0/bin/bitcoin-cli",
            "-testnet",
            "estimatesmartfee",
            "1",
            "economical",
        ]
    else:
        comm = ["/bitcoin-22.0/bin/bitcoin-cli", "estimatesmartfee", "1", "economical"]

    print(" ".join(comm))

    p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    out, err = p.communicate()

    if err:
        raise Exception("Got error: " + err)

    if "errors" in json.loads(out).keys():
        print("Got error: " + str(json.loads(out)["errors"]))
        print("Continuing...")

        print("Fee rate is " + str(get_constant("fee_sat_per_vbyte")) + " sats/vbyte")
    else:
        sats_per_byte = int(json.loads(out)["feerate"] * 100000000 / 1000)

        print("Adjusting fee to " + str(sats_per_byte) + " sats/vbyte")

        set_constant("fee_sat_per_vbyte", sats_per_byte)


def get_block_height():
    comm = (
        ["lncli"]
        + LNCLI_ARGS
        + [
            f"-n={network}",
            "getinfo",
        ]
    )

    print(" ".join(comm))

    p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    out, err = p.communicate()

    if err:
        raise Exception("Got error: " + err)

    block_height = int(json.loads(out)["block_height"])

    return block_height


def wait_new_block():
    block_height_1 = get_block_height()

    block_height_2 = block_height_1

    while block_height_2 <= block_height_1:
        print(f"Block height is {block_height_1}, waiting for a new block...")
        block_height_2 = get_block_height()
        time.sleep(30)

    print(f"Block height is {block_height_1}, done waiting.")


def balance_confirmed():
    try:
        currency_BTC = Currencies.objects.get(name="Bitcoin")
    except Exception as e:
        print("cant find BTC")

        Currencies.objects.create(name="Bitcoin", acronym="SAT", status="minted")

    currency_BTC = Currencies.objects.get(name="Bitcoin")

    balances_btc = Balances.objects.filter(currency=currency_BTC)

    balance_btc_total = 0
    balance_btc_pending_total = 0

    for balance_btc in balances_btc:
        balance_btc_total = balance_btc_total + balance_btc.balance
        balance_btc_pending_total = (
            balance_btc_pending_total + balance_btc.pending_balance
        )

    # trans_received = Transactions.objects.filter(
    #     type='user',
    #     direction='inbound' ,
    #     status='inbound_invoice_paid' ,
    #     currency = get_currency_btc(),
    #     )

    # trans_paid = Transactions.objects.filter(
    #     type='user',
    #     direction='outbound' ,
    #     status='outbound_invoice_paid' ,
    #     currency = get_currency_btc(),
    # )

    # trans_fees = Transactions.objects.filter(
    #     type='fee',
    #     direction='outbound' ,
    #     status='fee_paid' ,
    #     currency = get_currency_btc(),
    # )

    # amount_total = 0

    # for trn in trans_received:
    #     amount_total = amount_total + trn.amount

    # for trn in trans_paid:
    #     amount_total = amount_total - trn.amount

    # for trn in trans_fees:
    #     amount_total = amount_total - trn.amount

    # if balance_btc_total-315015!=amount_total:
    #     raise Exception(f"overall balance in the DB {balance_btc_total}-315015 SAT is larger than {amount_total} SAT.")

    confirmed_balance = 0
    unconfirmed_balance = 1

    comm = (
        ["lncli"]
        + LNCLI_ARGS
        + [
            f"-n={network}",
            "walletbalance",
        ]
    )

    print(" ".join(comm))

    p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    out, err = p.communicate()

    if err:
        print(f"Got output: {err}, continuing...")

        raise Exception("Got error: " + err.decode())

    unconfirmed_balance = int(json.loads(out)["unconfirmed_balance"])

    confirmed_balance = int(json.loads(out)["confirmed_balance"])

    if unconfirmed_balance > 10272:
        print(
            f"Found unconfirmed_balance={unconfirmed_balance}. Waiting for more"
            " confirmations..."
        )

    comm = (
        ["lncli"]
        + LNCLI_ARGS
        + [
            f"-n={network}",
            "listchannels",
        ]
    )

    print(" ".join(comm))

    p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    out, err = p.communicate()
    local_balance_channels_total = sum(
        [int(ch["local_balance"]) for ch in json.loads(out)["channels"]]
    )
    remote_balance_channels_total = sum(
        [int(ch["remote_balance"]) for ch in json.loads(out)["channels"]]
    )

    if unconfirmed_balance > 10272:
        return False
    if os.getenv("DEV_ENV") == "DEV":
        balance_adjustment = get_constant("cold_wallet_balance")
    else:
        balance_adjustment = 0.429642 * 100e6

    print("balance_btc_total")
    ExternalInfoTable.objects.create(
        variable_name="balance_btc_in_db_total", variable_value=balance_btc_total
    ).save()

    print("balance_btc_total_adjusted")
    print(balance_btc_total + balance_adjustment)

    print("confirmed_balance")
    print(confirmed_balance)
    ExternalInfoTable.objects.create(
        variable_name="confirmed_balance_onchain", variable_value=confirmed_balance
    ).save()

    print("local_balance_channels_total")
    print(local_balance_channels_total)
    ExternalInfoTable.objects.create(
        variable_name="local_balance_channels_total",
        variable_value=local_balance_channels_total,
    ).save()

    print("remote_balance_channels_total")
    print(remote_balance_channels_total)
    ExternalInfoTable.objects.create(
        variable_name="remote_balance_channels_total",
        variable_value=remote_balance_channels_total,
    ).save()

    if (
        confirmed_balance + local_balance_channels_total + balance_adjustment
    ) < balance_btc_total:
        raise Exception(
            "Accounting test failed. Node has less balance"
            f" { (confirmed_balance + local_balance_channels_total)} SAT than DB"
            f" {balance_btc_total + balance_adjustment} SAT. Difference ="
            f" {balance_btc_total - (confirmed_balance + local_balance_channels_total + balance_adjustment)}"
        )

    balances_below_zero = Balances.objects.filter(balance__lt=0)

    pending_balances_below_zero = Balances.objects.filter(balance__lt=0)

    if len(balances_below_zero) > 0:
        raise Exception("Found balance below zero")

    if len(pending_balances_below_zero) > 0:
        raise Exception("Found pending balance below zero")

    return True


#     restart_everything()


# def restart_everything():

#     print("Checking taro deanom status....")

#     comm = ["tapcli",f"-n={network}", "assets", "list"]

#     print(" ".join(comm))

#     p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

#     out, err = p.communicate()

#     if err:
#         print(f"got error {err}")
#         print(f"Resetting taro...")
#         command1 = subprocess.Popen(["pwd"])
#         out, err = command1.communicate()
#         print(out)
#         command1 = subprocess.Popen(["sh", "reset_script.sh"])

#         time.sleep(10)


class Command(BaseCommand):
    help = "Start main loop submitting Taro / BTC transactions"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        while True:
            print("Running another iteration...")
            update_loop()

            print("Waiting for 10 s...")
            time.sleep(30)


def update_loop():
    fcn_list_offchain = [
        process_transactions_internal,
        process_transactions_exchange,
        process_transactions_inbound_invoice_waiting_for_btc,
        process_transactions_inbound_invoice_generated_btc,
        process_transactions_lnd_inbound_invoice_waiting_for_btc,
        process_transactions_lnd_inbound_invoice_generated_btc,
        process_transactions_lnd_outbound_invoice_submitted_btc,
    ]

    fcn_list_onchain = [
        process_transactions_lnd_outbound_invoice_received_btc,
        process_transactions_outbound_invoice_received_btc,
        process_transactions_inbound_invoice_waiting_for,
        process_transactions_outbound_invoice_received,
        process_currencies_tx_created,
        process_currencies_minting,
        process_currencies_submitted_for_minting,
        process_transactions_inbound_invoice_generated,
        process_transactions_remove_old,
        process_get_currency_meta,
        process_collection_submitted_for_bulk_minting,
        adjust_fee,
    ]

    errors = 0

    # while True:

    while errors < 5:
        try:
            for fcn in fcn_list_onchain:
                segment = xray_recorder.begin_segment(fcn.__name__)
                if balance_confirmed():
                    try:
                        fcn()
                    except Exception as e:
                        segment.add_exception(e, traceback.extract_stack())
                        raise e
                    finally:
                        xray_recorder.end_segment()

            for fcn in fcn_list_offchain:
                segment = xray_recorder.begin_segment(fcn.__name__)
                try:
                    fcn()
                except Exception as e:
                    segment.add_exception(e, traceback.extract_stack())
                    raise e
                finally:
                    xray_recorder.end_segment()

            errors = 0
            print("Sleeping for 10s...")
            time.sleep(10)
        except Exception as e:
            print(e)

            errors = errors + 1

            time.sleep(60 * 10)

    if errors >= 5:
        raise Exception("Too many errors")


@djn_transaction.atomic
def process_transactions_outbound_invoice_received_btc():
    currency_BTC = get_currency_btc()

    transactions = Transactions.objects.filter(
        currency=currency_BTC, status="outbound_invoice_received"
    ).order_by("created_timestamp")
    # print(
    #     f"{len(transactions)} BTC transactions found with"
    #     " status=outbound_invoice_received"
    # )
    # for transaction in transactions:
    if transactions:

        with djn_transaction.atomic():
            transaction = transactions[0]

            print(f"Processing transaction {transaction.id}...")

            amt = transaction.amount

            lnd_addr = transaction.invoice_outbound

            comm = (
                ["lncli"]
                + LNCLI_ARGS
                + [
                    f"-n={network}",
                    "sendcoins",
                    f"--addr={lnd_addr}",
                    f"--amt={amt}",
                    f"--sat_per_vbyte={get_fee_sat_per_vbyte()}",
                ]
            )

            print(" ".join(comm))

            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()

            if err:
                print(f"Got output: {err}, continuing...")
                transaction.error_out(err.decode())

                # continue
                return
            try:
                txid = json.loads(out)["txid"]

            except Exception as e:
                print(f"Got output: {out}, continuing...")
                transaction.error_out(f"Got unprocessable output: \n {out[0:50]}")

                # continue
                return

            comm = (
                ["lncli"]
                + LNCLI_ARGS
                + [
                    f"-n={network}",
                    "listchaintxns",
                    f"--start_height={get_block_height()-(24*6*3)}",
                ]
            )
            print(" ".join(comm))
            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()

            if err:
                transaction.error_out(err.decode())

                # continue
                return

            transactions = json.loads(out)["transactions"]

            for trn in transactions:
                if trn["tx_hash"] == txid:
                    confirmations = int(trn["num_confirmations"])
                    total_fees = int(trn["total_fees"])

            transaction.status = "outbound_invoice_paid"
            transaction.tx_id = txid
            transaction.finalize()
            transaction.save()

            transaction.finalize_fee()

            # continue
            return


def process_transactions_outbound_invoice_received():
    currency_BTC = get_currency_btc()

    transactions = Transactions.objects.filter(
        ~Q(currency=currency_BTC), status="outbound_invoice_received"
    ).order_by("created_timestamp")
    # print(
    #     f"{len(transactions)} transactions found with status=outbound_invoice_received"
    # )
    # for transaction in transactions:
    if transactions:
        with djn_transaction.atomic():
            transaction = transactions[0]

            print(f"Processing transaction {transaction.id}...")

            balance = Balances.objects.filter(
                user=transaction.user, currency=transaction.currency
            ).first()

            amt = transaction.amount

            taro_addr = transaction.invoice_outbound

            comm = (
                ["tapcli"]
                + TAPCLI_ARGS
                + [
                    f"-n={network}",
                    "assets",
                    "send",
                    f"--addr={taro_addr}",
                    f"--sat_per_vbyte={get_fee_sat_per_wu()}",
                ]
            )

            print(" ".join(comm))
            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()

            if err:
                print(f"Got output: {err}, continuing...")

                transaction.error_out(err.decode())

                # continue
                return

            try:
                transfer_txid = None
                for output in json.loads(out)["transfer"]["outputs"]:
                    if not output["script_key_is_local"]:
                        transfer_txid = output["anchor"]["outpoint"].split(":")[0]

                total_fee_sats = int(
                    json.loads(out)["transfer"]["anchor_tx_chain_fees"]
                )

                if not transfer_txid:
                    raise Exception("Outpoint not found.")

            except Exception as e:
                print(f"Got unprocessable output. \n {out[:200]}")
                transaction.error_out(
                    f"Error: {e}. Got unprocessable output. \n {out[:200]}"
                )

                # continue
                return

            transaction.status = "outbound_invoice_paid"
            transaction.tx_id = transfer_txid
            transaction.finalize()
            transaction.save()

            transaction.finalize_fee()


def process_transactions_inbound_invoice_waiting_for_btc():
    currency_BTC = get_currency_btc()

    transactions = Transactions.objects.filter(
        currency=currency_BTC, status="inbound_invoice_waiting_for"
    ).order_by("created_timestamp")
    # print(
    #     f"{len(transactions)} BTC transactions found with"
    #     " status=inbound_invoice_waiting_for"
    # )
    for transaction in transactions:
        with djn_transaction.atomic():
            # transaction.error_out("New BTC deposits are disabled for now.")
            # continue

            # if transactions:
            #    transaction=transactions[0]

            print(f"Processing transaction {transaction.id}...")

            amt = transaction.amount

            comm = (
                ["lncli"]
                + LNCLI_ARGS
                + [
                    f"-n={network}",
                    "newaddress",
                    "p2wkh",
                ]
            )
            print(" ".join(comm))
            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()

            if err:
                print(f"Got output: {err}, continuing...")
                transaction.error_out(err.decode())

                continue
                # return

            try:
                btc_address = json.loads(out)["address"]

            except Exception as e:
                print(f"Got output: {out[0:50]}, continuing...")
                transaction.error_out(f"Got unprocessable output: \n {out[0:50]}")

                continue
                # return

            transaction.invoice_inbound = btc_address

            transaction.status = "inbound_invoice_generated"

            transaction.save()


def process_transactions_inbound_invoice_waiting_for():
    currency_BTC = get_currency_btc()

    transactions = Transactions.objects.filter(
        ~Q(currency=currency_BTC), status="inbound_invoice_waiting_for"
    ).order_by("created_timestamp")
    print(
        f"{len(transactions)} transactions found with"
        " status=inbound_invoice_waiting_for"
    )
    for transaction in transactions:
        with djn_transaction.atomic():
            # if transactions:
            #     transaction = transactions[0]

            print(f"Processing transaction {transaction.id}...")

            amt = transaction.amount
            asset_id = transaction.currency.asset_id

            comm = (
                ["tapcli"]
                + TAPCLI_ARGS
                + [
                    f"-n={network}",
                    "addrs",
                    "new",
                    f"--asset_id={asset_id}",
                    f"--amt={amt}",
                ]
            )
            print(" ".join(comm))
            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()

            if err:
                print(f"Got output: {err}, continuing...")
                transaction.error_out(err.decode())

                # continue
                continue

            try:
                taro_address = json.loads(out)["encoded"]

            except Exception as e:
                print(f"Got output: {out[0:50]}, continuing...")
                transaction.error_out(f"Got unprocessable output: \n {out[0:50]}")

                # continue
                continue

            transaction.invoice_inbound = taro_address

            transaction.status = "inbound_invoice_generated"

            transaction.save()


def process_transactions_inbound_invoice_generated_btc():
    currency_BTC = get_currency_btc()

    transactions = Transactions.objects.filter(
        currency=currency_BTC, status="inbound_invoice_generated"
    ).order_by("created_timestamp")
    print(f"Found {len(transactions)} transactions with inbound_invoice_generated")
    # print(
    #     f"{len(transactions)} BTC transactions found with"
    #     " status=inbound_invoice_generated"
    # )
    for transaction in transactions:
        with djn_transaction.atomic():
            # if transactions:
            #    transaction = transactions[0]

            print(f"Processing transaction {transaction.id}...")

            if not Balances.objects.filter(
                user=transaction.user, currency=transaction.currency
            ).exists():
                print(
                    f"Balance in {transaction.currency} not found for user"
                    f" {transaction.user}. Creating balance..."
                )
                balance_new = Balances.objects.create(
                    user=transaction.user,
                    currency=transaction.currency,
                    balance=0,
                )
                balance_new.save()

            balance = Balances.objects.filter(
                user=transaction.user, currency=transaction.currency
            ).first()

            amt = transaction.amount

            address = transaction.invoice_inbound

            comm = (
                ["lncli"]
                + LNCLI_ARGS
                + [
                    f"-n={network}",
                    "listchaintxns",
                    f"--start_height={get_block_height()-(24*6*3)}",
                ]
            )

            print(" ".join(comm))
            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()

            if err:
                print(f"Got output: {err}, continuing...")

                transaction.error_out(err.decode())

                # continue
                continue

            transactions = json.loads(out)["transactions"]

            if len(transactions) == 0:
                # continue
                continue

            confirmations = 0

            for trn in transactions:
                for output_detail in trn.get("output_details", []):
                    if address == output_detail["address"]:
                        amt_received = int(output_detail["amount"])
                        confirmations = int(trn["num_confirmations"])
                        tx_id = trn["tx_hash"]

            if confirmations < 1:
                # continue
                continue

            transaction.tx_id = tx_id
            transaction.amount = amt_received
            transaction.status = "inbound_invoice_paid"
            transaction.save()

            transaction.finalize()


def process_transactions_inbound_invoice_generated():
    currency_BTC = get_currency_btc()

    transactions = Transactions.objects.filter(
        ~Q(currency=currency_BTC), status="inbound_invoice_generated"
    ).order_by("created_timestamp")
    # print(
    #     f"{len(transactions)} transactions found with status=inbound_invoice_generated"
    # )
    for transaction in transactions:
        with djn_transaction.atomic():
            # if transactions:
            #    transaction=transactions[0]
            print(f"Processing transaction {transaction.id}...")

            if not Balances.objects.filter(
                user=transaction.user, currency=transaction.currency
            ).exists():
                print(
                    f"Balance in {transaction.currency} not found for user"
                    f" {transaction.user}. Creating balance..."
                )
                balance_new = Balances.objects.create(
                    user=transaction.user,
                    currency=transaction.currency,
                    balance=0,
                )
                balance_new.save()

            balance = Balances.objects.filter(
                user=transaction.user, currency=transaction.currency
            ).first()

            amt = transaction.amount

            taro_address = transaction.invoice_inbound

            comm = (
                ["tapcli"]
                + TAPCLI_ARGS
                + [
                    f"-n={network}",
                    "addrs",
                    "receives",
                    f"--addr={taro_address}",
                ]
            )
            print(" ".join(comm))
            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()

            if err:
                transaction.error_out(err.decode())

                continue
                # return

            try:
                events = json.loads(out)["events"]

            except Exception as e:
                print(f"Got output: {out[0:50]}, continuing...")

                transaction.error_out(f"Got unprocessable output: \n {out[0:50]}")

                # continue
                return

            if len(events) == 0:
                continue
                # return

            tx_hash = (json.loads(out)["events"][0]["outpoint"]).split(":")[0]

            if events[0]["status"] != "ADDR_EVENT_STATUS_TRANSACTION_CONFIRMED":
                continue
                # return

            transaction.status = "inbound_invoice_paid"
            transaction.tx_id = tx_hash
            transaction.finalize()
            transaction.save()


@djn_transaction.atomic
def process_currencies_submitted_for_minting():
    currencies = Currencies.objects.filter(status="submitted_for_minting")
    # print(f"{len(currencies)} currencies found with status=submitted_for_minting")
    # for currency in currencies:

    if currencies:
        if currencies[0].collection:
            currencies = Currencies.objects.filter(collection=currencies[0].collection)

        else:
            currencies = [currencies[0]]

    if len(currencies) > 0:
        internal_key_dict = {}

        for i, currency in enumerate(currencies):
            print(f"Processing currency {currency.id}...")

            if currency.is_nft:
                type = "collectible"
            else:
                type = "normal"

            meta = encode_metadata(currency)

            comm = (
                ["tapcli"]
                + TAPCLI_ARGS
                + [
                    f"-n={network}",
                    "assets",
                    "mint",
                    f"--type={type}",
                    f"--name={currency.name}",
                    f"--supply={currency.supply}",
                    f'--meta_bytes="{meta}"',
                ]
            )

            # if currency.is_nft:
            #     if i==0 and len(currencies)>0:
            #         comm.append(f"--new_grouped_asset")
            #     elif i>0 and len(currencies)>0:
            #         comm.append(f"--grouped_asset")
            #         comm.append(f"--group_anchor={currencies[0].name}")

            print(" ".join(comm))
            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()

            if err:
                print(f"Got error: {err}")
                currency.status = "error"
                currency.status_description = err.decode()

                currency.save()

                minting_transaction = currency.minting_transaction
                minting_transaction.error_out(err.decode())

                continue
                # return

            internal_key_dict[currency.id] = json.loads(out)["pending_batch"][
                "batch_key"
            ]

        comm = (
            ["tapcli"]
            + TAPCLI_ARGS
            + [
                f"-n={network}",
                "assets",
                "mint",
                "finalize",
                f"--sat_per_vbyte={get_fee_sat_per_wu()}",
            ]
        )
        print(" ".join(comm))
        p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        out, err = p.communicate()

        if err:
            print(f"Got error: {err}")
            for currency in currencies:
                if currency.status != "error":
                    currency.status = "error"
                    currency.status_description = err.decode()

                    currency.save()

                    minting_transaction = currency.minting_transaction
                    minting_transaction.error_out(err.decode())

                # continue

            return

        for currency in currencies:
            if currency.status != "error":
                currency.internal_key = internal_key_dict[currency.id]

                currency.status = "minting"
                currency.save()


@djn_transaction.atomic
def process_currencies_minting():
    currencies = Currencies.objects.filter(status="minting")
    # print(f"{len(currencies)} currencies found with status=minting")
    assets = None
    for currency in currencies:
        # if currencies:
        # currency=currencies[0]
        print(f"Processing currency {currency.id}...")
        if not assets:
            comm = ["tapcli"] + TAPCLI_ARGS + [f"-n={network}", "assets", "list"]
            print(" ".join(comm))
            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()

            if err:
                currency.status = "error"
                currency.status_description = err.decode()
                currency.save()

                minting_transaction = currency.minting_transaction
                minting_transaction.error_out(err.decode())

                continue
                # return

            assets = json.loads(out)["assets"]

        asset_id = None

        for asset_dict in assets:
            if (
                asset_dict["chain_anchor"]["internal_key"] == currency.internal_key
            ) and (currency.name == asset_dict["asset_genesis"]["name"]):
                print(asset_dict)

                asset_id = asset_dict["asset_genesis"]["asset_id"]

                anchor_txid = asset_dict["chain_anchor"]["anchor_outpoint"].split(":")[
                    0
                ]

        if not asset_id:
            print(f"no match for {currency.internal_key}")
            continue
            # return

        currency.status = "tx_created"
        currency.asset_id = asset_id
        currency.save()

        minting_transaction = currency.minting_transaction

        if minting_transaction:
            minting_transaction.tx_id = anchor_txid
            minting_transaction.status = "minting"
            minting_transaction.save()


@djn_transaction.atomic
def process_currencies_tx_created():
    currencies = Currencies.objects.filter(status="tx_created")

    # print(f"{len(currencies)} currencies found with status=tx_created")
    transactions = None
    for currency in currencies:
        # if currencies:
        # currency=currencies[0]
        print(f"Processing currency {currency.id}...")
        if not transactions:
            comm = (
                ["lncli"]
                + LNCLI_ARGS
                + [
                    f"-n={network}",
                    "listchaintxns",
                    f"--start_height={get_block_height()-(24*6*3)}",
                ]
            )
            print(" ".join(comm))
            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()

            if err:
                currency.status = "error"
                currency.status_description = err.decode()
                currency.save()

                minting_transaction = currency.minting_transaction
                minting_transaction.error_out(err.decode())

                continue
                # return

            transactions = json.loads(out)["transactions"]

        if currency.minting_transaction:
            tx_id = currency.minting_transaction.tx_id

        genesis_bootstrap_info = None

        confirmations = 0

        for trn in transactions:
            if trn["tx_hash"] == tx_id:
                confirmations = int(trn["num_confirmations"])
                total_fees = int(trn["total_fees"])

        if confirmations < 1:
            print(f"Only found {confirmations}. Continuing...")
            continue
            # return

        if currency.collection:
            adjusted_fee = (
                int(
                    total_fees
                    / len(
                        Currencies.objects.filter(
                            ~Q(status="error"), collection=currency.collection
                        )
                    )
                )
                + 1
            )
        else:
            adjusted_fee = total_fees

        currency.status = "minted"
        currency.save()

        transaction = currency.minting_transaction
        transaction.status = "minted"

        transaction.finalize()

        transaction.save()

        transaction.finalize_fee()


def process_transactions_remove_old():
    how_many_days = 1
    time_now = datetime.now()
    transactions = Transactions.objects.filter(
        status="inbound_invoice_generated",
        created_timestamp__lte=time_now - timedelta(days=how_many_days),
    ).order_by("created_timestamp")
    # print(
    #     f"{len(transactions)} transactions found with status=inbound_invoice_generated"
    #     f" and older than {how_many_days} days"
    # )
    for transaction in transactions:
        with djn_transaction.atomic():
            print(f"Processing transaction {transaction.id}...")
            transaction.error_out(
                f"The invoice was generated on {transaction.created_timestamp} for this"
                f" transaction was not paid for {how_many_days} days as of {time_now}."
                " We will no longer accept payment to this invoice."
            )


def process_transactions_internal():
    transactions = Transactions.objects.filter(status="internal_stated").order_by(
        "created_timestamp"
    )
    # print(
    #     f"{len(transactions)} transactions found with status=inbound_invoice_generated"
    # )
    for transaction in transactions:
        try:
            with djn_transaction.atomic():
                # if transactions:
                #     transaction=transactions[0]
                print(f"Processing transaction {transaction.id}...")

                transaction.status = "internal_finished"

                transaction.finalize()

                transaction.save()
        except Exception as e:
            with djn_transaction.atomic():
                print(e)
                transaction.error_out("Internal transaction failed")


def process_transactions_exchange():
    transactions = Transactions.objects.filter(status="exchange_started").order_by(
        "created_timestamp"
    )
    # print(
    #     f"{len(transactions)} transactions found with status=inbound_invoice_generated"
    # )
    for transaction in transactions:
        try:
            transaction.refresh_from_db()
            with djn_transaction.atomic():
                # if transactions:
                #     transaction=transactions[0]
                print(f"Processing transaction {transaction.id}...")

                associated_exchange_transaction = (
                    transaction.associated_exchange_transaction
                )

                if associated_exchange_transaction:
                    if not transaction.listing:
                        transaction.error_out(
                            "The order you tried to accept was taken by someone"
                            " else first."
                        )
                        associated_exchange_transaction.error_out(
                            "The order you tried to accept was taken by someone"
                            " else first."
                        )
                        continue

                    # if Balances.objects.filter(
                    #     user=transaction.destination_user, currency=transaction.currency
                    # ).exists():
                    #     destination_user_balance_coin = Balances.objects.get(
                    #         user=transaction.destination_user, currency=transaction.currency
                    #     ).balance
                    # else:
                    #     destination_user_balance_coin = 0

                    # if (
                    #     destination_user_balance_coin + transaction.amount * transaction.get_sgn()
                    # ) < 0:
                    #     transaction.error_out(
                    #         f"The user balances are not sufficient to complete this"
                    #         f" transaction."
                    #     )
                    #     associated_exchange_transaction.error_out(
                    #         f"The user balances are not sufficient to complete this"
                    #         f" transaction."
                    #     )
                    #     continue

                    # if Balances.objects.filter(
                    #     user=transaction.user, currency=transaction.currency
                    # ).exists():
                    #     balance = Balances.objects.get(
                    #         user=transaction.user, currency=transaction.currency
                    #     ).pending_balance
                    # else:
                    #     balance = 0

                    # if (balance - transaction.amount * transaction.get_sgn()) < 0:
                    #     transaction.error_out(
                    #         f"The user balances are not sufficient to complete this"
                    #         f" transaction."
                    #     )
                    #     associated_exchange_transaction.error_out(
                    #         f"The user balances are not sufficient to complete this"
                    #         f" transaction."
                    #     )
                    #     continue

                    # if Balances.objects.filter(
                    #     user=associated_exchange_transaction.destination_user,
                    #     currency=associated_exchange_transaction.currency,
                    # ).exists():
                    #     destination_user_balance = Balances.objects.get(
                    #         user=associated_exchange_transaction.destination_user,
                    #         currency=associated_exchange_transaction.currency,
                    #     ).balance
                    # else:
                    #     destination_user_balance = 0

                    # if (
                    #     destination_user_balance
                    #     + (associated_exchange_transaction.amount
                    #     * associated_exchange_transaction.get_sgn())
                    #     - (
                    #         associated_exchange_transaction.fee_transaction.amount
                    #         if associated_exchange_transaction.fee_transaction
                    #         else 0
                    #     )
                    # ) < 0:
                    #     transaction.error_out(
                    #         f"The user balances are not sufficient to complete this"
                    #         f" transaction."
                    #     )
                    #     associated_exchange_transaction.error_out(
                    #         f"The user balances are not sufficient to complete this"
                    #         f" transaction."
                    #     )
                    #     continue

                    # if Balances.objects.filter(
                    #     user=associated_exchange_transaction.user,
                    #     currency=associated_exchange_transaction.currency,
                    # ).exists():
                    #     balance = Balances.objects.get(
                    #         user=associated_exchange_transaction.user,
                    #         currency=associated_exchange_transaction.currency,
                    #     ).balance
                    # else:
                    #     balance = 0

                    # if (
                    #     balance
                    #     - associated_exchange_transaction.amount
                    #     * associated_exchange_transaction.get_sgn()
                    #     - (
                    #         associated_exchange_transaction.fee_transaction.amount
                    #         if associated_exchange_transaction.fee_transaction
                    #         else 0
                    #     )
                    # ) < 0:
                    #     transaction.error_out(
                    #         f"The user balances are not sufficient to complete this"
                    #         f" transaction."
                    #     )
                    #     associated_exchange_transaction.error_out(
                    #         f"The user balances are not sufficient to complete this"
                    #         f" transaction."
                    #     )
                    #     continue

                    transaction.status = "exchange_finished"
                    associated_exchange_transaction.status = "exchange_finished"

                    transaction.finalize()
                    associated_exchange_transaction.finalize()

                    transaction.save()
                    associated_exchange_transaction.save()

                    transaction.finalize_fee()

                    if transaction.listing:
                        if transaction.listing.type != "lp":
                            transaction.listing.delete()

        except Exception as e:
            print(traceback.format_exc())
            with djn_transaction.atomic():
                transaction.error_out("Could not process the transaction at this time.")
                associated_exchange_transaction.error_out(
                    "Could not process the transaction at this time."
                )

        #     continue
        #         # except BalanceException as e:
        #         #     transaction.error_out("Could not process the transaction at this time.")
        #         #     associated_exchange_transaction.error_out(
        #         #         "Could not process the transaction at this time."
        #         #     )
        #         #     continue


@djn_transaction.atomic
def process_get_currency_meta():
    currencies = Currencies.objects.filter(status="waiting_for_meta_data")
    # print(
    #     f"{len(transactions)} transactions found with status=inbound_invoice_generated"
    # )
    for currency in currencies:
        # if currencies:
        #     currency=currencies[0]

        print(f"Processing currency {currency.id}...")
        if (
            currency.universe_host
            and currency.universe_host != "universe.lightning.finance"
        ):

            universe_host = (
                currency.universe_host
                if currency.universe_host
                else "universe.lightning.finance"
            )

            comm = (
                ["tapcli"]
                + TAPCLI_ARGS
                + [
                    f"-n={network}",
                    "universe",
                    "sync",
                    f"--universe_host={universe_host}",
                    f"--asset_id={currency.asset_id}",
                ]
            )
            print(" ".join(comm))
            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()

            if err:
                currency.status = "error"
                currency.status_description = err.decode()
                currency.save()

                minting_transaction = currency.minting_transaction
                minting_transaction.error_out(currency.status_description)

                continue

        comm = (
            ["tapcli"]
            + TAPCLI_ARGS
            + [
                f"-n={network}",
                "universe",
                "leaves",
                f"--asset_id={currency.asset_id}",
            ]
        )
        print(" ".join(comm))
        p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        out, err = p.communicate()

        if err:
            currency.name = "error_" + currency.minting_transaction.id
            currency.status = "error"
            currency.status_description = err.decode()
            currency.save()

            minting_transaction = currency.minting_transaction
            minting_transaction.error_out(currency.status_description)

            continue
            # return

        if len(json.loads(out)["leaves"]) == 0:
            currency.status = "error"
            currency.status_description = (
                f"Cant find any leaves for asset_id={currency.asset_id}."
            )
            currency.save()

            minting_transaction = currency.minting_transaction
            minting_transaction.error_out(currency.status_description)

            continue
            # return

        supply = int(json.loads(out)["leaves"][0]["asset"]["amount"])
        name = json.loads(out)["leaves"][0]["asset"]["asset_genesis"]["name"]
        is_nft = (
            json.loads(out)["leaves"][0]["asset"]["asset_genesis"]["asset_type"]
        ) == "COLLECTIBLE"

        if Currencies.objects.filter(name=name).exists():
            currency.name = "error_" + currency.minting_transaction.id
            currency.status = "error"
            currency.status_description = "Currency with the same name already exists."
            currency.save()

            minting_transaction = currency.minting_transaction
            minting_transaction.error_out("Currency with the same name already exists.")

            continue

        currency.supply = supply
        currency.name = name
        currency.is_nft = is_nft

        comm = (
            ["tapcli"]
            + TAPCLI_ARGS
            + [
                f"-n={network}",
                "assets",
                "meta",
                f"--asset_id={currency.asset_id}",
            ]
        )
        print(" ".join(comm))
        p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        out, err = p.communicate()

        if err:
            currency.status = "error"
            currency.status_description = err.decode()
            currency.save()

            minting_transaction = currency.minting_transaction
            minting_transaction.error_out(err.decode())

            continue
            # return

        data = json.loads(out)["data"]
        metadata = decode_metadata(data)

        try:
            imgstring = metadata["image_data"]

            data_type = imgstring.split(",")[0].split(":")[1].split("/")[0]
            if data_type != "image":
                raise Exception(
                    f"The data type of image is '{data_type}'. It should be 'image'."
                )
            data_format = imgstring.split(",")[0].split(":")[1].split("/")[1]
            image_base64 = imgstring.split(",")[1]

            imgdata = base64.b64decode(image_base64)

            picture_orig_file = io.BytesIO()
            picture_orig_file.write(imgdata)

            picture_orig_file = io.BytesIO(picture_orig_file.getvalue())

            cf = ContentFile(picture_orig_file.read())

            if currency.is_nft:
                filename = currency.name
            else:
                filename = currency.acronym

            currency.picture_orig.save(name=filename + "." + data_format, content=cf)

        except Exception as e:
            # #currency.status = "error"
            # #currency.status_description = str(e)
            # currency.save()

            # minting_transaction = currency.minting_transaction
            # minting_transaction.error_out(str(e))

            # continue
            print("cant decode metadata image")

        if metadata["acronym"]:
            currency.acronym = metadata["acronym"]

        currency.description = metadata["description"]
        currency.status = "minted"

        minting_transaction = currency.minting_transaction
        minting_transaction.status = "currency_registration_finished"
        minting_transaction.save()

        currency.save()


def process_transactions_lnd_inbound_invoice_waiting_for_btc():
    transactions = Transactions.objects.filter(
        status="lnd_inbound_invoice_waiting_for"
    ).order_by("created_timestamp")

    for transaction in transactions:
        with djn_transaction.atomic():
            # transaction.error_out("New BTC deposits are disabled for now.")
            # continue

            # if transactions:
            #    transaction=transactions[0]

            print(f"Processing transaction {transaction.id}...")

            amt = transaction.amount

            comm = (
                ["lncli"]
                + LNCLI_ARGS
                + [
                    f"-n={network}",
                    "addinvoice",
                    f"--amt={amt}",
                    f"--memo='{transaction.description}'",
                    f"--expiry={60*60*24}",
                ]
            )
            print(" ".join(comm))
            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()

            if err:
                print(f"Got output: {err}, continuing...")
                transaction.error_out(err.decode())

                continue
                # return

            try:
                payment_request = json.loads(out)["payment_request"]

            except Exception as e:
                print(f"Got output: {out[0:50]}, continuing...")
                transaction.error_out(f"Got unprocessable output: \n {out[0:50]}")

                continue
                # return

            transaction.invoice_inbound = payment_request

            transaction.status = "lnd_inbound_invoice_generated"

            transaction.save()


def process_transactions_lnd_inbound_invoice_generated_btc():
    transactions = Transactions.objects.filter(
        status="lnd_inbound_invoice_generated"
    ).order_by("created_timestamp")

    for transaction in transactions:
        with djn_transaction.atomic():
            # transaction.error_out("New BTC deposits are disabled for now.")
            # continue

            # if transactions:
            #    transaction=transactions[0]

            print(f"Processing transaction {transaction.id}...")

            rhash = decode_invoice_lnd(transaction.invoice_inbound)["preimage"]

            comm = (
                ["lncli"]
                + LNCLI_ARGS
                + [f"-n={network}", "lookupinvoice", f"--rhash={rhash}"]
            )
            print(" ".join(comm))
            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()

            if err:
                print(f"Got output: {err}, continuing...")
                transaction.error_out(err.decode())

                continue
                # return

            try:
                settled = json.loads(out)["settled"]
                state = json.loads(out)["state"]

            except Exception as e:
                print(f"Got output: {out[0:50]}, continuing...")
                transaction.error_out(f"Got unprocessable output: \n {out[0:50]}")

                continue
                # return

            if state not in ["SETTLED", "OPEN"]:
                transaction.error_out(f"Invoice closed with state {state}")
                continue

            if not settled:
                continue

            transaction.status = "lnd_inbound_invoice_paid"
            transaction.finalize()

            transaction.save()


@djn_transaction.atomic
def process_transactions_lnd_outbound_invoice_received_btc():
    currency_BTC = get_currency_btc()

    transactions = Transactions.objects.filter(
        currency=currency_BTC, status="lnd_outbound_invoice_received"
    ).order_by("created_timestamp")
    # print(
    #     f"{len(transactions)} BTC transactions found with"
    #     " status=outbound_invoice_received"
    # )
    # for transaction in transactions:
    if transactions:
        with djn_transaction.atomic():
            transaction = transactions[0]

            print(f"Processing transaction {transaction.id}...")

            lnd_addr = transaction.invoice_outbound

            comm = (
                ["timeout", "5s", "lncli"]
                + LNCLI_ARGS
                + [
                    f"-n={network}",
                    "sendpayment",
                    "--force",
                    f"--pay_req={lnd_addr}",
                    f"--fee_limit={transaction.fee_transaction.amount}",
                    "--json",
                ]
            )

            print(" ".join(comm))

            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()
            exit_code = p.wait()

            if exit_code == 124:
                transaction.status = "lnd_outbound_invoice_paid"
                transaction.save()
                return

            if err:
                print(f"Got output: {err}, continuing...")
                transaction.error_out(err)

                return

            transaction.status = "lnd_outbound_invoice_paid"
            transaction.finalize()
            transaction.finalize_fee()
            transaction.save()


@djn_transaction.atomic
def process_transactions_lnd_outbound_invoice_received_btc():
    currency_BTC = get_currency_btc()

    transactions = Transactions.objects.filter(
        currency=currency_BTC, status="lnd_outbound_invoice_received"
    ).order_by("created_timestamp")
    # print(
    #     f"{len(transactions)} BTC transactions found with"
    #     " status=outbound_invoice_received"
    # )
    for transaction in transactions:
        # if transactions:
        with djn_transaction.atomic():
            # transaction = transactions[0]

            print(f"Processing transaction {transaction.id}...")

            lnd_addr = transaction.invoice_outbound

            comm = (
                ["timeout", "5s", "lncli"]
                + LNCLI_ARGS
                + [
                    f"-n={network}",
                    "sendpayment",
                    "--force",
                    f"--pay_req={lnd_addr}",
                    f"--fee_limit={transaction.fee_transaction.amount}",
                    "--json",
                ]
            )

            print(" ".join(comm))

            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()
            exit_code = p.wait()

            if exit_code == 124:
                print("Timeout..., continuing...")
                transaction.status = "lnd_outbound_invoice_submitted"
                transaction.save()
                continue

            if err:
                print(f"Got output: {err}, continuing...")
                transaction.error_out(err)

                continue

            transaction.status = "lnd_outbound_invoice_submitted"
            transaction.save()


@djn_transaction.atomic
def process_transactions_lnd_outbound_invoice_submitted_btc():
    currency_BTC = get_currency_btc()

    transactions = Transactions.objects.filter(
        currency=currency_BTC, status="lnd_outbound_invoice_submitted"
    ).order_by("created_timestamp")
    # print(
    #     f"{len(transactions)} BTC transactions found with"
    #     " status=outbound_invoice_received"
    # )
    for transaction in transactions:
        # if transactions:
        with djn_transaction.atomic():
            # transaction = transactions[0]

            print(f"Processing transaction {transaction.id}...")

            rhash = decode_invoice_lnd(transaction.invoice_outbound)["preimage"]

            comm = (
                ["timeout", "5s", "lncli"]
                + LNCLI_ARGS
                + [
                    f"-n={network}",
                    "trackpayment",
                    rhash,
                    "--json",
                ]
            )

            print(" ".join(comm))

            p = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            out, err = p.communicate()
            exit_code = p.wait()
            if exit_code == 124:
                print("Timeout..., continuing...")
                continue

            if err:
                print(f"Got output: {err}, continuing...")
                transaction.error_out(err)

                continue

            if json.loads(out)["status"] == "FAILED":
                transaction.error_out(
                    f"Payment failed with error {json.loads(out)['status']}:"
                    f" {json.loads(out)['failure_reason']}"
                )
                continue

            transaction.status = "lnd_outbound_invoice_paid"
            transaction.finalize()
            transaction.finalize_fee()
            transaction.save()


@djn_transaction.atomic
def process_collection_submitted_for_bulk_minting():

    collections = Collections.objects.filter(
        status="waiting_for_miting_transaction"
    ).order_by("created_timestamp")

    if collections:
        my_collection = collections[0]

        try:
            with djn_transaction.atomic():
                file_list = []
                info_list = None

                with ZipFile(my_collection.images_zip_file) as myzipfile:
                    for file_name in myzipfile.namelist():
                        if file_name.split(".")[0].isnumeric() and file_name.split(".")[
                            1
                        ] in ["jpeg", "jpg", "png"]:
                            picture_orig = myzipfile.open(file_name)
                            cf = ContentFile(
                                content=picture_orig.read(), name=file_name
                            )
                            file_list.append(cf)

                initiate_balances_from_files(
                    file_list, my_collection, my_collection.owner, info_list=info_list
                )
                my_collection.status = "minted"
                my_collection.save()

        except Exception as e:
            print(e)
            my_collection.status = "error"
            my_collection.save()
