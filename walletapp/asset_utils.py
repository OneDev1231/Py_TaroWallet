


import requests
from binascii import hexlify, unhexlify
import mimetypes
from enum import Enum
import base58
import bitstring
import json

from io import BytesIO

CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
BECH32M_CONST = 0x2BC830A3

def u5_to_bitarray(arr):
    ret = bitstring.BitArray()
    for a in arr:
        ret += bitstring.pack("uint:5", a)
    return ret

class Encoding(Enum):
    """Enumeration type to list the various supported encodings."""

    BECH32 = 1
    BECH32M = 2

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

def bech32_verify_checksum(hrp, data):
    """Verify a checksum given HRP and converted data characters."""
    const = bech32_polymod(bech32_hrp_expand(hrp) + data)
    if const == 1:
        return Encoding.BECH32
    if const == BECH32M_CONST:
        return Encoding.BECH32M
    return None

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

def get_assets():
    
    pass

def get_asset_by_id(asset_id: str):
    
    res = requests.get(f"https://universe.lightning.finance/v1/taproot-assets/universe/leaves/asset-id/{asset_id}?proof_type=PROOF_TYPE_ISSUANCE")
    
    res_json = res.json()

    name = res_json['leaves'][0]["asset"]["asset_genesis"]["name"]
    supply = res_json['leaves'][0]["asset"]["amount"]
    asset_type = res_json['leaves'][0]["asset"]["asset_genesis"]["asset_type"]
    minting_tx = res_json['leaves'][0]["asset"]["asset_genesis"]["genesis_point"].split(":")[0]
    print("minting_tx")
    print(minting_tx)
    proof = res_json['leaves'][0]["proof"]
    
    data = unhexlify(bytes(proof,'utf-8'))[4:]
    
    data = bitstring.ConstBitStream(data)

    print(data)
    
        #amt, tagdata = read_bigsize(tagdata)
        #print(amt)
        #fdsasfad
    # print((unhexlify(bytes(proof,'utf-8'))))
    
    # mime = mimetypes.guess_type(unhexlify(bytes(proof,'utf-8')))
    # print(mime)
    
    proof_details = {}

    while data.len - data.pos > 0:

        tag, tagdata, data = pull_tagged(data)

        # print(tag)
        # print(tagdata.bytes)

        if tag == 0:
            proof_details["taproot_asset_version"] = tagdata.uint32
        elif tag == 1:
            proof_details["prev_out"] = hexlify(tagdata.bytes).decode() 
        elif tag == 2:
            proof_details["block_header"] = hexlify(tagdata.bytes).decode()
        elif tag == 3:
            proof_details["anchor_tx"] = hexlify(tagdata.bytes).decode()
        elif tag == 4:
            proof_details["anchor_tx_merkle_proof"] = hexlify(tagdata.bytes).decode()
        elif tag == 5:
            proof_details["taproot_asset_asset_leaf"] = hexlify(tagdata.bytes).decode()
        elif tag == 6:
            proof_details["taproot_asset_inclusion_proofs"] = hexlify(tagdata.bytes).decode()
        elif tag == 7:
            proof_details["taproot_exclusion_proofs"] = hexlify(tagdata.bytes).decode()
        elif tag == 8:
            proof_details["split_root_proof"] = hexlify(tagdata.bytes).decode()
        elif tag == 9:
            proof_details["meta_reveal"] = hexlify(tagdata.bytes).decode()
        elif tag == 10:
            proof_details["taproot_asset_input_splits"] = hexlify(tagdata.bytes).decode()
        elif tag == 11:
            proof_details["challenge_witness"] = hexlify(tagdata.bytes).decode()
        elif tag == 12:
            proof_details["asset_genesis"] = hexlify(tagdata.bytes).decode()
        elif tag == 13:
            proof_details["asset_group_key_reveal"] = hexlify(tagdata.bytes).decode()
        elif tag == 17:
            proof_details["meta"] = {}
            data1 = bitstring.ConstBitStream(tagdata)
            
            while data1.len - data1.pos > 0:
                if data1.len - data1.pos < 8:
                    (data1.read(data1.len - data.pos))
                else:
                    tag1, tagdata1, data1 = pull_tagged(data1)
                
                print(tag1)
                print(tagdata1.bytes)
                
                if tag1 == 0:
                    proof_details["meta"]["meta_type"] = tagdata1.uint8
                elif tag1 == 1:
                    proof_details["meta"]["1"] = tagdata1.bytes
                elif tag1 == 2:
                    proof_details["meta"]["meta_data"] = tagdata1.bytes
                    
            #invoice_details["meta"] = hexlify(tagdata.bytes).decode()
            
        # print(invoice_details)
    
    #magic.from_buffer(bytesio(invoice_details["meta"]["meta_data"]))
    
    # with open("test.png",'wb') as f:
    #     f.write(invoice_details["meta"]["meta_data"])
    
    meta_data = proof_details["meta"]["meta_data"]
    
    # JSON
    
    print(meta_data.decode().strip("\"").strip("'"))
    
    json_format = json.loads(meta_data.decode().strip("\"").strip("'"))
    
    # URL

    print(meta_data.decode().strip("\"").strip("'"))
    
    json_format = json.loads(meta_data.decode().strip("\"").strip("'"))

    # PNG
    
    
    
    # STRING 
    
# type: 1 (prev_out)
# value:
# [36*byte:txid || output_index]
# type: 2 (block_header)
# value:
# [80*byte:bitcoin_header]
# type: 3 (anchor_tx)
# value:
# [...*byte:serialized_bitcoin_tx]
# type: 4 (anchor_tx_merkle_proof)
# value:
# [...*byte:merkle_inclusion_proof]
# type: 5 (taproot_asset_asset_leaf)
# value:
# [tlv_blob:serialized_tlv_leaf]
# type: 6 (taproot_asset_inclusion_proofs)
# value:
# [...*byte:taproot_asset_taproot_proof]
# type: 0 (output_index
# value: [int32:index]
# type: 1 (internal_key
# value: [33*byte:y_parity_byte || schnorr_x_only_key]
# type: 2 (taproot_asset_proof)
# value: [...*byte:asset_proof]
# type: 0 (taproot_asset_proof)
# value: [...*byte:asset_inclusion_proof]
# type: 0
# value: [uint32:proof_version]
# type: 1
# value: [32*byte:asset_id]
# type: 2
# value: [...*byte:ms_smt_inclusion_proof]
# type: 1 (taproot_asset_inclusion_proof)
# value: [...*byte:taproot_asset_inclusion_proof]
# type: 0
# value: [uint32:proof_version]
# type: 1
# value: [...*byte:ms_smt_inclusion_proof]
# type: 2 (taproot_sibling_preimage)
# value: [byte:sibling_type][varint:num_bytes][...*byte:tapscript_preimage]
# type: 3 (taproot_asset_commitment_exclusion_proof
# value: [...*byte:taproot_exclusion_proof]
# type: 0 (tap_image_1)
# value: [...*byte:tapscript_preimage]
# type: 1 (tap_image_2)
# value: [...*byte:tapscript_preimage]
# type: 2 (bip_86)
# value: [byte 0x00/0x01:bip_86]
# type: 7 (taproot_exclusion_proofs)
# value:
# [uint16:num_proofs][...*byte:taproot_asset_taproot_proof]
# type: 8 (split_root_proof)
# value:
# [...*byte:taproot_asset_taproot_proof]
# type: 9 (meta_reveal)
# value:
# [...*byte:asset_meta_reveal]
# type: 0 (meta_type
# value: [uint8:type]
# type: 1 (meta_data
# value: [*byte:meta_data_bytes]
# type: 10 (taproot_asset_input_splits)
# value:
# [...*byte:nested_proof_map]
# type: 11 (challenge_witness)
# value:
# [...*byte:challenge_witness]
# type: 12 (block_height)
# value:
# [uint32:block_height]
# type: 12 (asset_genesis)
# value:
# [32*byte:first_prev_out_hash]
# [u32:first_prev_out_index]
# [BigSize:tag_len]
# [tag_len*byte:tag]
# [BigSize:metadata_len]
# [metadata_len*byte:metadata]
# [u32:output_index]
# [u8:type]
# type: 13 (asset_group_key_reveal)
# value:
# [64*byte:pub_key || asset_group_script_root]

#get_asset_by_id("3b7693c532a59186a56c25b39328bb1801b052ca960a7effd25724f3074eeda9")

get_asset_by_id("3b7693c532a59186a56c25b39328bb1801b052ca960a7effd25724f3074eeda9")

