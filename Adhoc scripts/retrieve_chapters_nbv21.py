from requests import get
import json
import time

headers = {
    "x-api-key": "896f6f87-fc95-4605-b782-804b99b83800",
    "x-brand": "NBG",
    "Authorization": "Bearer anonymous",
    "Referer": "https://www.debijbel.nl/",
    "Origin": "https://www.debijbel.nl",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
}

next = "GEN.1"

while next is not None:
    res = get(f"https://api.ibep-prod.com/bibles/01b58d476a09e6a6-01/chapters/{next}/with-study-content", headers=headers)
    data = res.json()
    filename = data["data"]["chapter"]["id"]

    with open(filename, "w") as file:
        file.writelines(json.dumps(data, indent=3))

    next = data["data"]["chapter"]["next"]["id"] if "next" in data["data"]["chapter"] else None
    print(next)

    time.sleep(.5)