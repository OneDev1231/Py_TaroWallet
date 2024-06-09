

from django.core.management.base import BaseCommand
from walletapp.models import Balances, Transactions, User

from walletapp.utils import get_currency_btc

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

from walletapp.models import (
    BalanceException,
    Balances,
    Collections,
    Currencies,
    Listings,
    Transactions,
    initiate_balances_from_files,
)
from walletapp.utils import (
    encode_metadata,
    get_currency_btc,
    get_fee_sat_estimate_exchange,
    get_fee_sat_estimate_onchain,
    get_fee_user,
    get_final_fee,
    get_free_amount_user,
    get_initial_free_btc_balance,
)

class Command(BaseCommand):
    help = "Fix balances below zero"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        
        user1 = User.objects.get(username="pokemon_collection_user")

        collection = Collections(
            name="TaprootAdam", description="A collection dedicated to AdamCoin. The collection shows Adams wife Eve and their evil enemy the snake.", 
        )
        collection.save()
        
        file_list = []
        info_list = []
        
        for i in range(0, 1500):
            print(i)
            try:
                with open(
                    f'/Users/adamivansky/Documents/Python/nft-assembler/generated_nfts/adam_{i+1}.png', "rb"
                ) as picture_orig:
                    cf = ContentFile(content=picture_orig.read(), name=str(i + 1) + ".png")
                    
                with open(
                    f'/Users/adamivansky/Documents/Python/nft-assembler/generated_nfts/adam_{i+1}.json'
                    , "rb"
                ) as info_file:
                    json_data = (json.loads(info_file.read()))
                
                if len(json_data['description'])>199:
                    json_data['description']=json_data['description'][:195] + "..."
                
                json_data['name'] = "Adam" + f"{i}" + (''.join(ch for ch in json_data['name'] if ch.isalnum()))

                if len(json_data['name'])>25:
                    json_data['name']=json_data['name'][:25]

                found = True 
                for info in info_list:
                    if info["name"]==json_data['name']:
                        found = False
                
                if Currencies.objects.filter(name=json_data['name'], status='minted').exists():
                    found = False
                
                print(json_data['name'])
                
                if found:
                    info_list.append(json_data)
                    file_list.append(cf)
                else:
                    print(info["name"] + " is duplicate.")
                
                
                
            except Exception as e:
                print(e)



        initiate_balances_from_files(file_list, collection, user1, info_list=info_list)