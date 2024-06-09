from io import BytesIO
import os

import requests
from PIL import Image


OPEN_API_KEY = os.getenv("OPEN_API_KEY")
def get_description(text_in):
    res = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPEN_API_KEY}"},
        json={
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"Describe a {text_in} in one sentence."},
            ],
            "max_tokens": 1000,
        },
    )

    print(res.json())

    text = (res.json())["choices"][0]["message"]["content"].replace("\n", "")

    return text


def get_image(text_in):
    res = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": "dall-e-3",
            "prompt": f"{text_in}, anime style",
            "n": 1,
            "size": "1024x1024",
        },
    )

    print(res.json())

    image_url = res.json()["data"][0]["url"]

    file = BytesIO()

    response = requests.get(image_url, stream=True)

    if not response.ok:
        print(response)

    for block in response.iter_content(1024):
        if not block:
            break

        file.write(block)

    img = Image.open(BytesIO(file.getvalue()))

    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format="JPEG", quality=90, optimize=True)

    print(f"Generated image of size {len(img_byte_arr.getvalue())}")

    return BytesIO(img_byte_arr.getvalue())


# nft_name_list = [
#     "Wonder Woman",
#     "She-Ra",
#     "Supergirl",
#     "Catwoman",
#     "Storm",
#     "Emma Frost",
#     "Rogue",
#     "Jean Grey",
#     "Harley Quinn",
#     "Poison Ivy",
#     "Betsy Braddock",
#     "Talia al Ghul",
#     "Zatanna",
#     "Black Canary",
# ]

# i = 0

# for nft_name in nft_name_list:
#     try:
#         desc = get_description(
#             f"The superhero {nft_name} in the world of cryptocurrency."
#         )
#         data = get_image(f"Attractive superhero {nft_name} eating a carrot.")

#         with open(
#             f"/Users/adamivansky/Pictures/CryptoSuperheros/{i+1-1}.png", "wb"
#         ) as f:
#             f.write(data.getvalue())

#         with open(
#             f"/Users/adamivansky/Pictures/CryptoSuperheros/{i+1-1}.json", "w"
#         ) as f:
#             f.write(
#                 json.dumps(
#                     {
#                         "name": nft_name.replace(" ", "") + "CryptoSuperhero",
#                         "description": f"{nft_name}. " + desc,
#                     }
#                 )
#             )
#         i = i + 1
#     except Exception as e:
#         print(e)


get_image(
    "Coin representing a nice girl Brittany who looks like Britney Spears and likes"
    " makeup"
)
