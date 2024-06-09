import io
import textwrap
from datetime import timedelta

import pandas as pd

# import matplotlib.pyplot as plt
from django.utils import timezone
from matplotlib.figure import Figure
from numerize import numerize
from PIL import Image, ImageDraw, ImageFont

from .models import Collections, Currencies, PriceHistory


def draw_week_chart(currency_id):

    x_start = 40
    x_end = 40

    y_start = 40
    y_end = 40

    now = timezone.now()

    period_mins = 60 * 24 * 7

    earlier = now - timedelta(minutes=period_mins)

    currency = Currencies.objects.get(id=currency_id)

    price_hist_item_list = PriceHistory.objects.filter(
        currency=currency,
        period="1h",
        created_timestamp__range=(earlier, now),
    ).order_by("created_timestamp")

    prices = pd.DataFrame(
        list(price_hist_item_list.values("created_timestamp", "price_sat"))
    )
    prices["price_sat_diff"] = prices.price_sat.diff()

    # # plot up prices
    # plt.bar(up.created_timestamp, up.price_sat_diff, width, bottom=up.price_sat, color=col1)

    # # plot down prices
    # plt.bar(down.created_timestamp, down.price_sat, width, bottom=down.price_sat, color=col2)
    fig = Figure(dpi=72, figsize=[55 / 72, 35 / 72])
    ax = fig.subplots()
    ax.plot(prices.created_timestamp, prices.price_sat, "-", color="#87CEEB")
    ax.fill_between(
        prices.created_timestamp, prices.price_sat, "-", color="#87CEEB", alpha=0.5
    )
    ax.axis("off")

    file = io.BytesIO()
    fig.savefig(file, format="png", transparent=True)

    return file.getvalue()


def currency_card(currency_id):
    currency = Currencies.objects.get(id=currency_id)

    # if currency.get_lp_listing():
    #     img_currency = Image.new(mode="RGBA", size=(1600, 400), color=(0, 0, 0))
    #     img_chart = draw_week_chart(currency_id)
    #     img_currency.paste(img_chart, (800, 0))
    # else:
    img_currency = Image.new(mode="RGBA", size=(800, 400), color=(0, 0, 0))

    draw = ImageDraw.Draw(img_currency)

    # font = ImageFont.truetype(<font-file>, <font-size>)
    font_symbols = ImageFont.truetype(
        "walletapp/static/assets/fontawesome/webfonts/fa-solid-900.ttf", 32
    )
    font_title = ImageFont.truetype(
        "walletapp/static/assets/fonts/Poppins-Bold.ttf", 32
    )

    font_symbols_stats = ImageFont.truetype(
        "walletapp/static/assets/fontawesome/webfonts/fa-solid-900.ttf", 24
    )
    font_stats = ImageFont.truetype(
        "walletapp/static/assets/fonts/Poppins-Bold.ttf", 24
    )

    font_desc = ImageFont.truetype("walletapp/static/assets/fonts/Poppins-Bold.ttf", 16)
    # draw.text((x, y),"Sample Text",(r,g,b))

    img_curr_symbol = Image.open(currency.picture_large)

    # ImageOps compatible mode
    if img_curr_symbol.mode not in ("L", "RGB"):
        img_curr_symbol = img_curr_symbol.convert("RGBA")

    img_curr_symbol = img_curr_symbol.resize((360, 360), Image.Resampling.LANCZOS)

    if currency.is_nft:
        img_currency.paste(img_curr_symbol, (20, 20))
    else:
        img_currency.paste(img_curr_symbol, (20, 20), img_curr_symbol)

    # Title
    draw.text(
        (400 + 32 + 16, 20),
        (currency.name if len(currency.name) <= 12 else (currency.name[:12] + "..."))
        + ("" if currency.is_nft else f" ({currency.acronym})"),
        (255, 255, 255),
        align="left",
        font=font_title,
    )

    symbol_coins = "\uf51e"
    symbol_jewel = "\uf3a5"

    symbol_arrow = "\uf201"
    symbol_user = "\uf007"
    symbol_bolt = "\uf0e7"
    symbol_file_invoice = "\uf570"

    if currency.is_nft:
        draw.text(
            (400, 20), symbol_jewel, (255, 255, 255), align="left", font=font_symbols
        )

    else:
        draw.text(
            (400, 20), symbol_coins, (255, 255, 255), align="left", font=font_symbols
        )

    draw.text(
        (400, 20 + 32 + 16),
        symbol_arrow,
        (255, 255, 255),
        align="left",
        font=font_symbols_stats,
    )
    draw.text(
        (400 + 32, 20 + 32 + 12),
        str(currency.price_change) + "%",
        (255, 255, 255),
        align="left",
        font=font_stats,
    )

    draw.text(
        (400 + 1 * 6 * (16), 20 + 32 + 16),
        symbol_user,
        (255, 255, 255),
        align="left",
        font=font_symbols_stats,
    )
    draw.text(
        (400 + 1 * 6 * (16) + 32, 20 + 32 + 12),
        numerize.numerize(currency.holders_num),
        (255, 255, 255),
        align="left",
        font=font_stats,
    )

    draw.text(
        (400 + 2 * 6 * (16), 20 + 32 + 16),
        symbol_bolt,
        (255, 255, 255),
        align="left",
        font=font_symbols_stats,
    )
    draw.text(
        (400 + 2 * 6 * (16) + 32, 20 + 32 + 12),
        str(currency.transaction_num),
        (255, 255, 255),
        align="left",
        font=font_stats,
    )

    draw.text(
        (400 + 3 * 6 * (16), 20 + 32 + 16),
        symbol_file_invoice,
        (255, 255, 255),
        align="left",
        font=font_symbols_stats,
    )
    draw.text(
        (400 + 3 * 6 * (16) + 32, 20 + 32 + 12),
        str(currency.orders_num),
        (255, 255, 255),
        align="left",
        font=font_stats,
    )

    desc_wrapped = "\n".join(textwrap.wrap(currency.description, width=1.5 * 400 / 16))

    if currency.is_nft:
        summary_left = f"""
Collection:
{currency.collection.name if currency.collection else "N/A"}

Asset Id:
{currency.asset_id[0:35]}...
    
Description:
{desc_wrapped}
"""
        summary_right = ""

    else:
        if currency.get_lp_listing():
            summary_left = f"""
Current price:
{int(currency.get_lp_listing().get_price_sat())} SAT / {currency.acronym}

Total supply:
{currency.supply} {currency.acronym}

Asset Id:
{currency.asset_id[0:35]}...
    
Description:
{desc_wrapped}
    """
            summary_right = f"""
Market cap:
{int(currency.get_market_cap())} SAT

Liquidity pool:
{numerize.numerize(currency.get_lp_listing().get_lp_btc())} SAT / {numerize.numerize(currency.get_lp_listing().get_lp_curr())} {currency.acronym}
        """
        else:
            summary_left = f"""
Total supply:
{currency.supply} {currency.acronym}

Asset Id:
{currency.asset_id[0:35]}...
    
Description:
{desc_wrapped}
        """
        summary_right = ""

    draw.text(
        (400, 20 + (32 + 2 * 16)),
        summary_left,
        (255, 255, 255),
        align="left",
        font=font_desc,
    )
    draw.text(
        (575, 20 + (32 + 2 * 16)),
        summary_right,
        (255, 255, 255),
        align="left",
        font=font_desc,
    )

    file = io.BytesIO()

    img_currency.save(file, format="PNG")

    return file.getvalue()


def divide_pixels_in_chunks(num_large, num_small):

    chunks = [num_large // num_small] * (num_small)

    num_distribute = num_large % num_small

    for i in range(0, num_distribute):
        chunks[i] = chunks[i] + 1

    return chunks


def collection_card(collection_id, num_side=6):

    im_sz = 800

    col = Collections.objects.get(id=collection_id)

    assets = col.get_assets(max_num=num_side * num_side)

    assets = [asset for asset in assets if asset.picture_small]

    img_collection = Image.new(mode="RGBA", size=(im_sz, im_sz), color=(0, 0, 0))

    num_display_side = min(int(len(assets) ** 0.5), num_side)

    if num_display_side == 0:
        return img_collection

    chunks = divide_pixels_in_chunks(im_sz, num_display_side)
    pos_x = 0
    for ix, chunk_x in enumerate(chunks):

        pos_y = 0
        for iy, chunk_y in enumerate(chunks):

            curr = assets[iy + len(chunks) * ix]

            img_curr_symbol = Image.open(curr.picture_small)

            img_curr_symbol = img_curr_symbol.resize(
                (chunk_x, chunk_y), Image.Resampling.LANCZOS
            )

            img_collection.paste(img_curr_symbol, (pos_x, pos_y))

            pos_y = pos_y + chunk_y

        pos_x = pos_x + chunk_x

    file = io.BytesIO()

    img_collection.save(file, format="PNG")

    return file.getvalue()


def collection_gif(collection_id, max_num=36):

    im_sz = 160

    if Collections.objects.filter(id=collection_id).exists():
        col = Collections.objects.get(id=collection_id)
        assets = col.get_assets(max_num=max_num)
    else:
        assets = []

    assets = [asset for asset in assets if asset.picture_small]

    if len(assets) < 2:
        file = io.BytesIO()
        img_collection = Image.new(mode="RGBA", size=(im_sz, im_sz), color=(0, 0, 0))
        img_collection.save(
            fp=file, format="GIF", append_images=[], save_all=True, duration=333, loop=0
        )
        return file.getvalue()

    img = Image.open(assets[-1].picture_small)

    imgs = []

    for curr in assets[:-1]:

        img_curr_symbol = Image.open(curr.picture_small)

        imgs.append(img_curr_symbol)

    file = io.BytesIO()

    img.save(
        fp=file, format="GIF", append_images=imgs, save_all=True, duration=333, loop=0
    )

    return file.getvalue()
