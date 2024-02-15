from requests import get
import time
import html

api_id = 'x4PxPrCv2ckJbiBH0QfjG'
bible_id = 3699

headers = {
    "Referer": "https://bible.com/",
    "Origin": "https://bible.com",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
}

next = "GEN.1"

while next is not None:
    res = get(f"https://www.bible.com/_next/data/{api_id}/en/bible/{bible_id}/{next}.json", headers=headers)
    data = res.json()
    filename = data["pageProps"]["params"]["usfm"]
    contents = data["pageProps"]["chapterInfo"]["content"]

    with open(filename, "w", encoding='utf-8') as file:
        file.writelines(html.unescape(contents))

    nextObj = data["pageProps"]["chapterInfo"]["next"]
    next = nextObj["usfm"][0] if nextObj is not None else None
    print(next)

    time.sleep(.5)