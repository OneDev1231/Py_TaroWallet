#! /usr/bin/env python3
import base64
import hashlib
import io
import json
import os
import re

# import secp256k1
import time

#! /usr/bin/env python3
# from bech32 import bech32_encode, bech32_decode, CHARSET
from binascii import hexlify
from datetime import datetime
from decimal import Decimal

import base58
import bitstring
import coinaddrvalidator

# import coinaddrvalidator
import numpy as np
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from PIL import Image, ImageDraw

# from django.contrib.auth.models import User


"""Reference implementation for Bech32 and segwit addresses."""

from enum import Enum


class Encoding(Enum):
    """Enumeration type to list the various supported encodings."""

    BECH32 = 1
    BECH32M = 2


CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
BECH32M_CONST = 0x2BC830A3


def get_pwd():
    return os.getenv("SERVICE_ACCOUNT_PWD")


def check_alphanumeric(text):
    if text:
        for c in text:
            if (
                c
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890 .:"
            ):
                raise ValidationError(
                    "This field can only contain alphanumeric characters, space, '.'"
                    " and ':'."
                )


def get_media_path_small(instance, filename):
    return get_media_path(instance, filename, "small")


def get_media_path_large(instance, filename):
    return get_media_path(instance, filename, "large")


def get_media_path_orig(instance, filename):
    return get_media_path(instance, filename, "orig")


def get_media_images_zip_file(instance, filename):
    return get_media_path(instance, filename, "collections_zip_path")


def get_media_path(instance, filename, size_name):

    if size_name == "collections_zip_path":
        filename = instance.name
    else:
        if instance.is_nft:
            filename = instance.name
        else:
            filename = instance.acronym

    code = str(filename)
    # here you can change the name
    # filename = filename  # or another thing
    return os.path.join("uploads", size_name, code + ".png")


def get_free_amount_user():
    if not User.objects.filter(username="free_amount_user").exists():
        user1 = User.objects.create_user(
            username="free_amount_user",
            password=get_pwd(),
        )

        user1.save()
    else:
        user1 = User.objects.get(username="free_amount_user")

    return user1


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


def get_fee_user():
    if not User.objects.filter(username="fee_user_1").exists():
        user1 = User.objects.create_user(
            username="fee_user_1",
            password=get_pwd(),
        )

        user1.save()
    else:
        user1 = User.objects.get(username="fee_user_1")

    return user1


def get_wash_users():

    wash_userlist = []

    for i in range(0, 10):
        if not User.objects.filter(username=f"bot_{i}").exists():
            user1 = User.objects.create_user(
                username=f"bot_{i}",
                password=get_pwd(),
            )
            user1.save()
        else:
            user1 = User.objects.get(username=f"bot_{i}")

        wash_userlist.append(user1)

    return wash_userlist


def resize_image_field(image_data, size_x, size_y, apply_mask=True):
    image = Image.open(image_data)

    # ImageOps compatible mode
    if image.mode not in ("L", "RGB"):
        image = image.convert("RGB")

    image = image.resize((size_x, size_y), Image.ANTIALIAS)

    if apply_mask:
        img = image.convert("RGB")
        npImage = np.array(img)
        h, w = img.size

        # Create same size alpha layer with circle
        alpha = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(alpha)
        draw.pieslice([0, 0, h, w], 0, 360, fill=255)

        # Convert alpha Image to numpy array
        npAlpha = np.array(alpha)

        # Add alpha layer to RGB
        npImage = np.dstack((npImage, npAlpha))

        # Save with alpha
        image = Image.fromarray(npImage)

    image_file = io.BytesIO()
    image.save(image_file, format="png", optimize=True)
    image.close()

    return io.BytesIO(image_file.getvalue())


def get_currency_btc():
    from .models import Currencies

    try:
        currency_BTC = Currencies.objects.get(name="Bitcoin")
    except Exception as e:
        print("cant find BTC")

        Currencies.objects.create(name="Bitcoin", acronym="SAT")

    currency_BTC = Currencies.objects.get(name="Bitcoin")

    return currency_BTC


def decode_btc_address(bitcoinAddress):

    res = coinaddrvalidator.validate("btc", bytes(bitcoinAddress, "utf8"))

    if not res.valid:
        raise Exception(f"The address '{bitcoinAddress}' is an invalid address.")

    if os.getenv("DEV_ENV") == "PROD" and res.network == "test":
        raise Exception(
            f"The address '{bitcoinAddress}' is a testnet address. Please provide a"
            " mainnet address."
        )
    elif os.getenv("DEV_ENV") == "DEV" and res.network == "main":
        raise Exception(
            f"The address '{bitcoinAddress}' is a mainnet address. Please provide a"
            " testnet address."
        )

    # hrp, data, spec = bech32_decode(bitcoinAddress)

    # if spec not in [Encoding.BECH32, Encoding.BECH32M]:
    #     raise Exception("Cant validate the address as p2wkh bech32 encoded segwit.")

    # return True


"""Reference implementation for Bech32/Bech32m and segwit addresses."""


def bech32_polymod(values):
    """Internal function that computes the Bech32 checksum."""
    generator = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            chk ^= generator[i] if ((top >> i) & 1) else 0
    return chk


def bech32_hrp_expand(hrp):
    """Expand the HRP into values for checksum computation."""
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def bech32_verify_checksum(hrp, data):
    """Verify a checksum given HRP and converted data characters."""
    const = bech32_polymod(bech32_hrp_expand(hrp) + data)
    if const == 1:
        return Encoding.BECH32
    if const == BECH32M_CONST:
        return Encoding.BECH32M
    return None


def bech32_create_checksum(hrp, data, spec):
    """Compute the checksum values given HRP and data."""
    values = bech32_hrp_expand(hrp) + data
    const = BECH32M_CONST if spec == Encoding.BECH32M else 1
    polymod = bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ const
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def bech32_encode(hrp, data, spec):
    """Compute a Bech32 string given HRP and data values."""
    combined = data + bech32_create_checksum(hrp, data, spec)
    return hrp + "1" + "".join([CHARSET[d] for d in combined])


def bech32_decode(bech):
    """Validate a Bech32/Bech32m string, and determine HRP and data."""
    if (any(ord(x) < 33 or ord(x) > 126 for x in bech)) or (
        bech.lower() != bech and bech.upper() != bech
    ):
        return (None, None, None)
    bech = bech.lower()
    pos = bech.rfind("1")
    if pos < 1 or pos + 7 > len(bech):  # or len(bech) > 90:
        return (None, None, None)
    if not all(x in CHARSET for x in bech[pos + 1 :]):
        return (None, None, None)
    hrp = bech[:pos]
    data = [CHARSET.find(x) for x in bech[pos + 1 :]]
    spec = bech32_verify_checksum(hrp, data)
    if spec is None:
        return (None, None, None)
    return (hrp, data[:-6], spec)


def bech32_decode_tapd(bech):
    """Validate a Bech32 string, and determine HRP and data."""
    # if (any(ord(x) < 33 or ord(x) > 126 for x in bech)) or (
    #     bech.lower() != bech and bech.upper() != bech
    # ):
    #     return (None, None)
    bech = bech.lower()
    pos = bech.rfind("1")
    # if pos < 1 or pos + 7 > len(bech):  # or len(bech) > 90:
    #     return (None, None)
    # if not all(x in CHARSET for x in bech[pos + 1 :]):
    #     return (None, None)
    hrp = bech[:pos]
    data = [CHARSET.find(x) for x in bech[pos + 1 :]]
    # if not bech32_verify_checksum(hrp, data):
    #     return (None, None)
    return (hrp, data[:-6])


def convertbits(data, frombits, tobits, pad=True):
    """General power-of-2 base conversion."""
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            return None
        acc = ((acc << frombits) | value) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        return None
    return ret


def decode(hrp, addr):
    """Decode a segwit address."""
    hrpgot, data, spec = bech32_decode(addr)
    if hrpgot != hrp:
        return (None, None)
    decoded = convertbits(data[1:], 5, 8, False)
    if decoded is None or len(decoded) < 2 or len(decoded) > 40:
        return (None, None)
    if data[0] > 16:
        return (None, None)
    if data[0] == 0 and len(decoded) != 20 and len(decoded) != 32:
        return (None, None)
    if (
        data[0] == 0
        and spec != Encoding.BECH32
        or data[0] != 0
        and spec != Encoding.BECH32M
    ):
        return (None, None)
    return (data[0], decoded)


def encode(hrp, witver, witprog):
    """Encode a segwit address."""
    spec = Encoding.BECH32 if witver == 0 else Encoding.BECH32M
    ret = bech32_encode(hrp, [witver] + convertbits(witprog, 8, 5), spec)
    if decode(hrp, ret) == (None, None):
        return None
    return ret


# def encode(hrp, witver, witprog):
#     """Encode a segwit address."""
#     ret = bech32_encode(hrp, [witver] + convertbits(witprog, 8, 5))
#     assert decode(hrp, ret) is not (None, None)
#     return ret


# BOLT #11:
#
# A writer MUST encode `amount` as a positive decimal integer with no
# leading zeroes, SHOULD use the shortest representation possible.
def shorten_amount(amount):
    """Given an amount in bitcoin, shorten it"""
    # Convert to pico initially
    amount = int(amount * 10**12)
    units = ["p", "n", "u", "m", ""]
    for unit in units:
        if amount % 1000 == 0:
            amount //= 1000
        else:
            break
    return str(amount) + unit


def unshorten_amount(amount):
    """Given a shortened amount, convert it into a decimal"""
    # BOLT #11:
    # The following `multiplier` letters are defined:
    #
    # * `m` (milli): multiply by 0.001
    # * `u` (micro): multiply by 0.000001
    # * `n` (nano): multiply by 0.000000001
    # * `p` (pico): multiply by 0.000000000001
    units = {
        "p": 10**12,
        "n": 10**9,
        "u": 10**6,
        "m": 10**3,
    }
    unit = str(amount)[-1]
    # BOLT #11:
    # A reader SHOULD fail if `amount` contains a non-digit, or is followed by
    # anything except a `multiplier` in the table above.
    if not re.fullmatch("\d+[pnum]?", str(amount)):
        raise ValueError("Invalid amount '{}'".format(amount))

    if unit in units.keys():
        return Decimal(amount[:-1]) / units[unit]
    else:
        return Decimal(amount)


# Bech32 spits out array of 5-bit values.  Shim here.
def u5_to_bitarray(arr):
    ret = bitstring.BitArray()
    for a in arr:
        ret += bitstring.pack("uint:5", a)
    return ret


def bitarray_to_u5(barr):
    assert barr.len % 5 == 0
    ret = []
    s = bitstring.ConstBitStream(barr)
    while s.pos != s.len:
        ret.append(s.read(5).uint)
    return ret


def encode_fallback(fallback, currency):
    """Encode all supported fallback addresses."""
    if currency == "bc" or currency == "tb":
        fbhrp, witness = bech32_decode(fallback)
        if fbhrp:
            if fbhrp != currency:
                raise ValueError("Not a bech32 address for this currency")
            wver = witness[0]
            if wver > 16:
                raise ValueError("Invalid witness version {}".format(witness[0]))
            wprog = u5_to_bitarray(witness[1:])
        else:
            addr = base58.b58decode_check(fallback)
            if is_p2pkh(currency, addr[0]):
                wver = 17
            elif is_p2sh(currency, addr[0]):
                wver = 18
            else:
                raise ValueError("Unknown address type for {}".format(currency))
            wprog = addr[1:]
        return tagged("f", bitstring.pack("uint:5", wver) + wprog)
    else:
        raise NotImplementedError(
            "Support for currency {} not implemented".format(currency)
        )


def parse_fallback(fallback, currency):
    if currency == "bc" or currency == "tb":
        wver = fallback[0:5].uint
        if wver == 17:
            addr = base58.b58encode_check(
                bytes([base58_prefix_map[currency][0]]) + fallback[5:].tobytes()
            )
        elif wver == 18:
            addr = base58.b58encode_check(
                bytes([base58_prefix_map[currency][1]]) + fallback[5:].tobytes()
            )
        elif wver <= 16:
            addr = bech32_encode(currency, bitarray_to_u5(fallback))
        else:
            return None
    else:
        addr = fallback.tobytes()
    return addr


# Map of classical and witness address prefixes
base58_prefix_map = {"bc": (0, 5), "tb": (111, 196)}


def is_p2pkh(currency, prefix):
    return prefix == base58_prefix_map[currency][0]


def is_p2sh(currency, prefix):
    return prefix == base58_prefix_map[currency][1]


# Tagged field containing BitArray
def tagged(char, l):
    # Tagged fields need to be zero-padded to 5 bits.
    while l.len % 5 != 0:
        l.append("0b0")
    return (
        bitstring.pack(
            "uint:5, uint:5, uint:5",
            CHARSET.find(char),
            (l.len / 5) / 32,
            (l.len / 5) % 32,
        )
        + l
    )


# Tagged field containing bytes
def tagged_bytes(char, l):
    return tagged(char, bitstring.BitArray(l))


# Discard trailing bits, convert to bytes.
def trim_to_bytes(barr):
    # Adds a byte if necessary.
    b = barr.tobytes()
    if barr.len % 8 != 0:
        return b[:-1]
    return b


def read_bigsize(stream):
    x = stream.read(8)

    if x.uint8 == 253:
        x = stream.read(16)
        return x.uint16, stream
    elif x.uint8 == 254:
        x = stream.read(32)
        return x.uint32, stream
    elif x.uint8 == 254:
        x = stream.read(64)
        return x.uint64, stream
    else:
        return x.uint8, stream


def pull_tagged(stream):
    tag, stream = read_bigsize(stream)
    length, stream = read_bigsize(stream)
    return (tag, stream.read(length * 8), stream)


# Try to pull out tagged data: returns tag, tagged data and remainder.
def pull_tagged_lnd(stream):
    tag = stream.read(5).uint
    length = stream.read(5).uint * 32 + stream.read(5).uint
    return (CHARSET[tag], stream.read(length * 5), stream)


# def lnencode(addr, privkey):
#     if addr.amount:
#         amount = Decimal(str(addr.amount))
#         # We can only send down to millisatoshi.
#         if amount * 10 ** 12 % 10:
#             raise ValueError(
#                 "Cannot encode {}: too many decimal places".format(addr.amount)
#             )

#         amount = addr.currency + shorten_amount(amount)
#     else:
#         amount = addr.currency if addr.currency else ""

#     hrp = "ln" + amount

#     # Start with the timestamp
#     data = bitstring.pack("uint:35", addr.date)

#     # Payment hash
#     data += tagged_bytes("p", addr.paymenthash)
#     tags_set = set()

#     for k, v in addr.tags:

#         # BOLT #11:
#         #
#         # A writer MUST NOT include more than one `d`, `h`, `n` or `x` fields,
#         if k in ("d", "h", "n", "x"):
#             if k in tags_set:
#                 raise ValueError("Duplicate '{}' tag".format(k))

#         if k == "r":
#             route = bitstring.BitArray()
#             for step in v:
#                 pubkey, channel, feebase, feerate, cltv = step
#                 route.append(
#                     bitstring.BitArray(pubkey)
#                     + bitstring.BitArray(channel)
#                     + bitstring.pack("intbe:32", feebase)
#                     + bitstring.pack("intbe:32", feerate)
#                     + bitstring.pack("intbe:16", cltv)
#                 )
#             data += tagged("r", route)
#         elif k == "f":
#             data += encode_fallback(v, addr.currency)
#         elif k == "d":
#             data += tagged_bytes("d", v.encode())
#         elif k == "x":
#             # Get minimal length by trimming leading 5 bits at a time.
#             expirybits = bitstring.pack("intbe:64", v)[4:64]
#             while expirybits.startswith("0b00000"):
#                 expirybits = expirybits[5:]
#             data += tagged("x", expirybits)
#         elif k == "h":
#             data += tagged_bytes(
#                 "h", hashlib.sha256(v.encode("utf-8")).digest()
#             )
#         elif k == "n":
#             data += tagged_bytes("n", v)
#         else:
#             # FIXME: Support unknown tags?
#             raise ValueError("Unknown tag {}".format(k))

#         tags_set.add(k)

#     # BOLT #11:
#     #
#     # A writer MUST include either a `d` or `h` field, and MUST NOT include
#     # both.
#     if "d" in tags_set and "h" in tags_set:
#         raise ValueError("Cannot include both 'd' and 'h'")
#     if not "d" in tags_set and not "h" in tags_set:
#         raise ValueError("Must include either 'd' or 'h'")

#     # We actually sign the hrp, then data (padded to 8 bits with zeroes).
#     privkey = secp256k1.PrivateKey(bytes(unhexlify(privkey)))
#     sig = privkey.ecdsa_sign_recoverable(
#         bytearray([ord(c) for c in hrp]) + data.tobytes()
#     )
#     # This doesn't actually serialize, but returns a pair of values :(
#     sig, recid = privkey.ecdsa_recoverable_serialize(sig)
#     data += bytes(sig) + bytes([recid])

#     return bech32_encode(hrp, bitarray_to_u5(data))


class LnAddr(object):
    def __init__(
        self,
        paymenthash=None,
        amount=None,
        currency="bc",
        tags=None,
        date=None,
    ):
        self.date = int(time.time()) if not date else int(date)
        self.tags = [] if not tags else tags
        self.unknown_tags = []
        self.paymenthash = paymenthash
        self.signature = None
        self.pubkey = None
        self.currency = currency
        self.amount = amount


def decode_genesis_bootstrap_info(a, verbose=True):
    # hrp, data = bech32_decode(a)

    data = bytes.fromhex(a)
    # data = u5_to_bitarray(data)

    stream = bitstring.ConstBitStream(data)

    genesis_bootstrap_info_dict = {}

    first_prev_out_hash = stream.read(32 * 8)
    genesis_bootstrap_info_dict["first_prev_out_hash"] = first_prev_out_hash

    first_prev_out_index = stream.read(32)
    genesis_bootstrap_info_dict["first_prev_out_index"] = first_prev_out_index.uint32

    tag_len, stream = read_bigsize(stream)

    tag = stream.read(tag_len * 8)
    genesis_bootstrap_info_dict["tag"] = tag.bytes.decode()

    metadata_len, stream = read_bigsize(stream)

    metadata = stream.read(metadata_len * 8)
    genesis_bootstrap_info_dict["metadata"] = metadata.bytes.decode()

    output_index = stream.read(32)
    genesis_bootstrap_info_dict["output_index"] = output_index

    my_type = stream.read(8)
    genesis_bootstrap_info_dict["type"] = my_type.uint

    return genesis_bootstrap_info_dict


def decode_invoice(a, verbose=True):
    hrp, data = bech32_decode_tapd(a)

    if not hrp.startswith("tap"):
        raise ValueError("Does not start with tap")

    data = u5_to_bitarray(data)

    data = bitstring.ConstBitStream(data)

    invoice_details = {}

    while data.len - data.pos > 0:
        if data.len - data.pos < 8:
            (data.read(data.len - data.pos))
        else:
            tag, tagdata, data = pull_tagged(data)

        if tag == 0:
            invoice_details["taro_version"] = tagdata.uint8
        elif tag == 2:
            invoice_details["taproot_asset_version"] = hexlify(tagdata.bytes).decode()
        elif tag == 4:
            invoice_details["asset_id"] = hexlify(tagdata.bytes).decode()
        elif tag == 5:
            invoice_details["asset_group_key"] = hexlify(tagdata.bytes).decode()
        elif tag == 6:
            invoice_details["script_key"] = hexlify(tagdata.bytes).decode()
        elif tag == 8:
            invoice_details["internal_key"] = hexlify(tagdata.bytes).decode()
        elif tag == 9:
            invoice_details["taproot_sibling_preimage"] = tagdata.uint
        elif tag == 10:
            amt, tagdata = read_bigsize(tagdata)
            invoice_details["amt"] = amt
        elif tag == 12:
            proof_courier_addr = hexlify(tagdata.bytes).decode()
            invoice_details["proof_courier_addr"] = tagdata.bytes.decode()
        else:
            invoice_details[f"tag_{tag}"] = hexlify(tagdata.bytes).decode()

    return invoice_details


def encode_metadata(currency):
    if currency.picture_small:
        max_image_size = 100000

        im_size = 2 * max_image_size
        quality = 100

        while im_size > max_image_size and quality >= 5:
            quality = quality - 2

            image = Image.open(currency.picture_small)

            image_file = io.BytesIO()
            rgb_image = image.convert("RGB")
            rgb_image.save(image_file, format="jpeg", quality=quality)

            image_data = image_file.getvalue()

            im_size = len(image_data)

        image.close()

        if im_size > max_image_size:
            image_data = None

    else:
        image_data = None

    metadata = {
        "description": currency.description,
        "name": currency.name,
        "acronym": currency.acronym,
        "user": currency.owner.username,
        "email": currency.owner.email,
        "minted_using": "https://mainnet.tiramisuwallet.com/",
        "image": "https://mainnet.tiramisuwallet.com"
        + currency.get_preview_image_url(),
    }

    if image_data:
        metadata["image_data"] = "data:image/jpg;base64," + base64.b64encode(
            image_data
        ).decode("utf-8")

    metadata_raw = json.dumps(metadata)

    return metadata_raw


def decode_metadata(metadata_raw):
    res = bytearray.fromhex(metadata_raw)

    try:
        metadata = json.loads(res.decode().strip('"'))
    except Exception as e:
        metadata = ""
        print(e)

    if isinstance(metadata, str):
        metadata = {
            "description": metadata_raw[:200],
            "name": None,
            "acronym": None,
            "image_data": None,
        }

    return metadata


def decode_invoice_lnd(invoice_str_in):
    addr = lndecode(invoice_str_in)

    currency_str = "Bitcoin mainnet" if addr.currency == "bc" else "Bitcoin testnet"

    timestamp = datetime.utcfromtimestamp(addr.date).strftime("%Y-%m-%d %H:%M:%S")
    expiration = dict(addr.tags).get("x", 0)
    expiration_time = datetime.utcfromtimestamp(addr.date + expiration).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    current_time = datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

    route_raw_list = dict(addr.tags).get("r")
    route_list = []
    if route_raw_list:
        for route_raw in route_raw_list:
            route = {}
            route["pubkey"] = hexlify(route_raw[0])
            route["short_channel_id"] = hexlify(route_raw[1])
            route["fee_base_msat"] = route_raw[2]
            route["fee_proportional_millionths"] = route_raw[3]
            route["cltv_expiry_delta"] = route_raw[4]
            route_list.append(route)

    fallback_bitcoin_address = dict(addr.tags).get("f")

    description = dict(addr.tags).get("d")

    if description is None:
        description = dict(addr.tags).get("h")

    preimage = (hexlify(addr.paymenthash)).decode("utf-8")

    public_key_target_node = (
        (hexlify(addr.pubkey)).decode("utf-8") if addr.pubkey else ""
    )

    return {
        "currency": currency_str,
        "amount_sat": int(addr.amount * 100000000) if addr.amount else int(0),
        "timestamp": timestamp,
        "expiration": expiration,
        "expiration_time": expiration_time,
        "current_time": current_time,
        "route_list": route_list,
        "fallback_bitcoin_address": fallback_bitcoin_address,
        "description": description,
        "preimage": preimage,
        "public_key_target_node": public_key_target_node,
    }


def lndecode(a, verbose=True):
    hrp, data, _ = bech32_decode(a)

    if not hrp:
        raise ValueError("Bad bech32 checksum")

    # BOLT #11:
    #
    # A reader MUST fail if it does not understand the `prefix`.
    if not hrp.startswith("ln"):
        raise ValueError("Does not start with ln")

    data = u5_to_bitarray(data)

    # Final signature 65 bytes, split it off.
    if len(data) < 65 * 8:
        raise ValueError("Too short to contain signature")
    sigdecoded = data[-65 * 8 :].tobytes()
    data = bitstring.ConstBitStream(data[: -65 * 8])

    addr = LnAddr()
    addr.pubkey = None

    m = re.search("[^\d]+", hrp[2:])
    if m:
        addr.currency = m.group(0)
        amountstr = hrp[2 + m.end() :]
        # BOLT #11:
        #
        # A reader SHOULD indicate if amount is unspecified, otherwise it MUST
        # multiply `amount` by the `multiplier` value (if any) to derive the
        # amount required for payment.
        if amountstr != "":
            addr.amount = unshorten_amount(amountstr)

    addr.date = data.read(35).uint

    while data.pos != data.len:
        tag, tagdata, data = pull_tagged_lnd(data)

        # BOLT #11:
        #
        # A reader MUST skip over unknown fields, an `f` field with unknown
        # `version`, or a `p`, `h`, or `n` field which does not have
        # `data_length` 52, 52, or 53 respectively.
        data_length = len(tagdata) / 5

        if tag == "r":
            # BOLT #11:
            #
            # * `r` (3): `data_length` variable.  One or more entries
            # containing extra routing information for a private route;
            # there may be more than one `r` field, too.
            #    * `pubkey` (264 bits)
            #    * `short_channel_id` (64 bits)
            #    * `feebase` (32 bits, big-endian)
            #    * `feerate` (32 bits, big-endian)
            #    * `cltv_expiry_delta` (16 bits, big-endian)
            route = []
            s = bitstring.ConstBitStream(tagdata)
            while s.pos + 264 + 64 + 32 + 32 + 16 < s.len:
                route.append(
                    (
                        s.read(264).tobytes(),
                        s.read(64).tobytes(),
                        s.read(32).intbe,
                        s.read(32).intbe,
                        s.read(16).intbe,
                    )
                )
            addr.tags.append(("r", route))
        elif tag == "f":
            fallback = parse_fallback(tagdata, addr.currency)
            if fallback:
                addr.tags.append(("f", fallback))
            else:
                # Incorrect version.
                addr.unknown_tags.append((tag, tagdata))
                continue

        elif tag == "d":
            addr.tags.append(("d", trim_to_bytes(tagdata).decode("utf-8")))

        elif tag == "h":
            if data_length != 52:
                addr.unknown_tags.append((tag, tagdata))
                continue
            addr.tags.append(("h", trim_to_bytes(tagdata)))

        elif tag == "x":
            addr.tags.append(("x", tagdata.uint))

        elif tag == "p":
            if data_length != 52:
                addr.unknown_tags.append((tag, tagdata))
                continue
            addr.paymenthash = trim_to_bytes(tagdata)

        elif tag == "n":
            if data_length != 53:
                addr.unknown_tags.append((tag, tagdata))
                continue
            # addr.pubkey = secp256k1.PublicKey(flags=secp256k1.ALL_FLAGS)
            # addr.pubkey.deserialize(trim_to_bytes(tagdata))
        else:
            addr.unknown_tags.append((tag, tagdata))

    if verbose:
        print(
            "hex of signature data (32 byte r, 32 byte s): {}".format(
                hexlify(sigdecoded[0:64])
            )
        )
        print("recovery flag: {}".format(sigdecoded[64]))
        print(
            "hex of data for signing: {}".format(
                hexlify(bytearray([ord(c) for c in hrp]) + data.tobytes())
            )
        )
        print(
            "SHA256 of above: {}".format(
                hashlib.sha256(
                    bytearray([ord(c) for c in hrp]) + data.tobytes()
                ).hexdigest()
            )
        )

    # BOLT #11:
    #
    # A reader MUST check that the `signature` is valid (see the `n` tagged
    # field specified below).
    if addr.pubkey:  # Specified by `n`
        # BOLT #11:
        #
        # A reader MUST use the `n` field to validate the signature instead of
        # performing signature recovery if a valid `n` field is provided.
        addr.signature = addr.pubkey.ecdsa_deserialize_compact(sigdecoded[0:64])
        if not addr.pubkey.ecdsa_verify(
            bytearray([ord(c) for c in hrp]) + data.tobytes(), addr.signature
        ):
            raise ValueError("Invalid signature")
    else:  # Recover pubkey from signature.
        # addr.pubkey = secp256k1.PublicKey(flags=secp256k1.ALL_FLAGS)
        # addr.signature = addr.pubkey.ecdsa_recoverable_deserialize(
        #    sigdecoded[0:64], sigdecoded[64])
        # addr.pubkey.public_key = addr.pubkey.ecdsa_recover(
        #    bytearray([ord(c) for c in hrp]) + data.tobytes(), addr.signature)
        pass
    return addr


def check_invoice_lnd(invoice_str_in, check_exp_amt=True):
    try:
        addr = lndecode(invoice_str_in)
    except Exception as e:
        raise Exception(
            f"Error decoding the invoice. Got error {e} for the invoice"
            f" {invoice_str_in}"
        )

    # print(addr.date)

    # print(dict(addr.tags)['x'])
    # print(dict(addr.tags))
    # print(dict(addr.unknown_tags))
    # print(addr.paymenthash)
    # print(addr.signature)
    # print(addr.pubkey)
    # print(addr.currency)
    # print(addr.amount)

    if os.getenv("DEV_ENV") == "PROD":
        prefix = "bc"
    elif os.getenv("DEV_ENV") == "DEV":
        prefix = "tb"

    if addr.currency != prefix:
        raise Exception(
            f"The currency '{addr.currency}' is not supported please provide a Bitcoin"
            " Mainnet Lightning invoice."
        )

    if check_exp_amt:
        # if addr.amount is None:
        #     raise Exception(
        #         f"The invoice amount is not provided. Please specify the invoice amount to be at least 1 sat."
        #     )

        # if addr.amount < 1e-8:
        #     raise Exception(
        #         f"The amount {addr.amount} is too low. Please enter an invoice for at least at least 1 sat."
        #     )

        if (addr.date + dict(addr.tags).get("x", 0) + 60 * 1) < time.time():
            raise Exception(
                "Please provide an invoice that expires at least 1 minute in the"
                " future. The invoice you have supplied expires on"
                f" {datetime.utcfromtimestamp(addr.date+dict(addr.tags)['x']).strftime('%Y-%m-%d %H:%M:%S')}"
            )

        if (addr.date + dict(addr.tags).get("x", 0) - 60 * 60 * 24) > time.time():
            raise Exception(
                "Please provide an invoice that expires in less than 24 hours. The"
                " invoice you have supplied expires on"
                f" {datetime.utcfromtimestamp(addr.date+dict(addr.tags)['x']).strftime('%Y-%m-%d %H:%M:%S')}"
            )


# print(decode_invoice_lnd("lnbc90n1pj4vpd2pp5g7sxdpv2a5ywzur669wkn6p345u0x566rwldkxcfmsmkmkfe7mhqdqqcqzzgxqyz5vqrzjqwnvuc0u4txn35cafc7w94gxvq5p3cu9dd95f7hlrh0fvs46wpvhdetgkz0mg8g62gqqqqryqqqqthqqpyrzjqw8c7yfutqqy3kz8662fxutjvef7q2ujsxtt45csu0k688lkzu3ldetgkz0mg8g62gqqqqryqqqqthqqpysp58340uk6d2ecaphcl7s0nl687dy88wuqvqeumhfahhmual878ngmq9qypqsqk496zjw9x9yl72c0wgq7tshtt66k70dw2gcejutft5atmhxujwapc9avrn6f47hetd6rjnh9gd98mzj84jm8v00xj36qeeghaczwu6sqvcxwsm"))
# print(check_invoice_lnd("lnbc1ps7gmgepp56454p9ncylhhk7aetr9s9f5wg983q3wj2j0dqkwdsmunhqg0d63qdqqcqzzgxqyz5vqrzjqw8c7yfutqqy3kz8662fxutjvef7q2ujsxtt45csu0k688lkzu3ld03k30egsfqdryqqqqryqqqqthqqpysp57sw64su4j9ul3prt30r5fkmeaqcmxp9hus0kmmyhhw7d24ahhqdq9qypqsqmxuc3sgg7p0ze0ntyfelvnt3hna2802qjjlane6mx5naacfuvfkxz0lt6pejhh7myc2y0q0aplxp0udkakep75tljjzprdtes8hz22cq3et7y3"))


# print(
#     decode_invoice(
#         "taptb1qqqsqqspqqzzqzkm5ed0c3daevpme0x92hz6u8usynwm8cf4g67qw4xtt509x9muqcssy9hfa5qc7qgpfqkul8lxkvwcxlwppy0hkpcrm4khw0882kpd8wrdpqssyzyst39ctqx9jd6v8fyun49u23p9acz6wksllp2wp8zfr0x5272tpgqsxrpkw4hxjan9wfek2unsvvaz7tm5v4ehgmn9wsh82mnfwejhyum99ekxjemgw3hxjmn89enxjmnpde3k2w33xqcrywgdxk4en"
#     )
# )
# print(check_invoice("lnbc1ps7gmgepp56454p9ncylhhk7aetr9s9f5wg983q3wj2j0dqkwdsmunhqg0d63qdqqcqzzgxqyz5vqrzjqw8c7yfutqqy3kz8662fxutjvef7q2ujsxtt45csu0k688lkzu3ld03k30egsfqdryqqqqryqqqqthqqpysp57sw64su4j9ul3prt30r5fkmeaqcmxp9hus0kmmyhhw7d24ahhqdq9qypqsqmxuc3sgg7p0ze0ntyfelvnt3hna2802qjjlane6mx5naacfuvfkxz0lt6pejhh7myc2y0q0aplxp0udkakep75tljjzprdtes8hz22cq3et7y3"))

# print(decode_invoice("tarotb1qqqsqqjfdlwdeayx2ut98uyj4rjq52lggjfhalyanfl97fgp803rw3vqf0rqqqqqqg8jysmgv9exc6t9ypp82cmtwv3q7gj5v4ehggrrw4e8yetwvdujyqqqqqqqqpppqt3arfc4zu027z0mg436z3arhrg7p0wal0duxaetegjj3u85y25dyp3pq09nnnpx7tcfthqfmec3qjv7wf03cfpzp9lrwtlu4dcstf4wucl9uzqpqyr4wl73"))
# print(decode_genesis_bootstrap_info("953ccf6651b6bbddd69b556a12c79ec69ab69349cb81f227a082bfc1641748a7"))

# print(decode_genesis_bootstrap_info("43e2278fe0917fca71b85d4f80e75053edfb321197452c3b18a20d849ae23dc80000000111224164616d20436f6f6c206275636b7322332254686973206973206d7920746573742063757272656e63792e204d7920686f6262792063757272656e6379203a29203a29220000000000", verbose=True))
# print(decode_genesis_bootstrap_info("21d720c4d766ac2ced9ad5188bb1dff8ab100be0b779b44838b21cb8dda47c570000000208746573746e667434132274657374206e6674206e756d6265722034220000000001", verbose=True))

# check_invoice("lnbc110u1psc6kzvpp5em3ssn8uf7guguyyvhfm3erve9gxw5n5uad0uhn2jnt8dsmfrnsqdq6f4ujqenfwfehggrfdemx76trv5cqpjsp5mmnumlgvhxu7a5y7r7cf2x28qlcjaepclgp9t7en7y3csqw5wxeq9qtzqqqqqqysgqxqyjw5qrzjqwryaup9lh50kkranzgcdnn2fgvx390wgj5jd07rwr3vxeje0glcllmzjpmg5x5y8qqqqqlgqqqqqeqqjq0y6cq046dxnert7yk8a9cx8vzm93xf5pch6azyz9vgm24k0kxusz4drwpnjy7r46dqdld4w95dejpe4r5gdratq3sj2r6qxj2897legqhpe3ed")
# print(check_invoice("lnbc1pslnjgvpp5cwn0znqgj2mrrwusp8h303s4uhng8geyrmyf4vvfglmc5sfcy0eqdqqcqzzgxqyz5vqrzjqw8c7yfutqqy3kz8662fxutjvef7q2ujsxtt45csu0k688lkzu3ldqwkgu6kxlrszcqqqqryqqqqthqqpysp5er3nghny0tet4dyyydnngrgtarhl24d26wcyccz6a0wcqgta554q9qypqsq63me7wd0md3pxgsz9hn5k63jenk2uk6ppkarpyrca4522dqn9e8qhwv3zg3svuttgd04wtjuhfrykfypun2fjmfdyzwn5e8wmrahkngqxqyt0l"))
# print(decode_invoice("lnbc1pslnjgvpp5cwn0znqgj2mrrwusp8h303s4uhng8geyrmyf4vvfglmc5sfcy0eqdqqcqzzgxqyz5vqrzjqw8c7yfutqqy3kz8662fxutjvef7q2ujsxtt45csu0k688lkzu3ldqwkgu6kxlrszcqqqqryqqqqthqqpysp5er3nghny0tet4dyyydnngrgtarhl24d26wcyccz6a0wcqgta554q9qypqsq63me7wd0md3pxgsz9hn5k63jenk2uk6ppkarpyrca4522dqn9e8qhwv3zg3svuttgd04wtjuhfrykfypun2fjmfdyzwn5e8wmrahkngqxqyt0l"))
# print(
#     hexlify(b'\xebAe[\xa8\\Y\xd9\xfb\x14H\x86\x90P\xba_\xd3x\xb2]\xf2\x9c\x01\x8c\xd5\xfb\x9fc\xf6\x96\xfe\xc9').decode()
# )

# print(str(hexlify(b'\x05\x00\x13g\x15\xc2\x81\x8d\x91v\xc3\xe0"\x0bR\xc9\xf1BQ\xf4\xa6\xedZF\x9d\xf9\xfa\xac\xe7([\xf5')))
# print((unhexlify(bytes("0500136715c2818d9176c3e0220b52c9f14251f4a6ed5a469df9faace7285bf5",'utf-8'))).decode('utf-8'))

# print(decode_genesis_bootstrap_info("4164616d732074657374206d6f6e657973"))

# print(bytearray(data).decode('utf-8'))

# decode_btc_address("bc1qr9y2n26ajz3zrzj8kkdj308qadm5dsce0hjz4q")
