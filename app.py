from flask import Flask, jsonify, request
import requests
from bs4 import BeautifulSoup
import threading
import time
import re

app = Flask(__name__)

# List of URLs to scrape
websites = [
    "https://empireminecraft.com/forums/empire-new..",
    "https://www.planetminecraft.com/forums/",
    "https://forums.minecraftforge.net/forum/64-mi..",
    "https://forums.lokamc.com/",
    "https://hypixel.net/forums/official-hypixel-m..",
    "https://havoc.games/forums/",
    "https://minecraft.fandom.com/wiki/Minecraft_Forum",
    "https://www.reddit.com/r/Minecraft/",
    "https://www.reddit.com/r/MinecraftServer/",
    "https://www.eneba.com/",
    "https://www.g2a.com/",
    "https://lolz.live/",  # lolz.live
    "https://hellofhackers.com/threads/50-cracking-tools-all-the-tools-you-need-to-crack.8/",  # HellOfHackers
    "https://2b2t.miraheze.org/wiki/Cheat_Clients",  # 2b2t Wiki
    "https://www.reddit.com/r/MinecraftLeaks/",  # r/MinecraftLeaks
    "https://www.reddit.com/r/MinecraftSpeedrun/",  # r/MinecraftSpeedrun
    "https://www.reddit.com/r/minecraftclients/",  # r/minecraftclients
    "https://www.reddit.com/r/PiratedGames/",  # r/PiratedGames
    "https://www.reddit.com/r/Piracy/",  # r/Piracy
    "https://cs.rin.ru/",  # cs.rin.ru
    "https://www.nulled.to/",  # Nulled.to
    "https://pirates-forum.org/",  # SuprBay
    "https://www.mpgh.net/",  # MPGH.net
    "https://www.nullforums.net/",  # NullForums.net
    "https://forum.mydigitallife.info/",  # My Digital Life Forums
    "https://serials.ws/",  # serials.ws
    "https://cracked.to/",  # Cracked.to
    "https://forum.mobilism.org/"  # Mobilism Forum
]

def is_minecraft_key(text):
    # Define a regular expression pattern for Minecraft keys
    key_pattern = re.compile(r'[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}')  # Adjust the pattern as needed
    return bool(key_pattern.match(text))

def scrape_reddit(subreddit, num_pages=5):
    keys = []
    for page in range(1, num_pages + 1):
        url = f"https://www.reddit.com/r/{subreddit}/?count={page*25}&after=t3_{page*25}"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all post links on the page
        for link in soup.find_all('a', class_='_eYtD2XCVieq6emjKBH3m'):
            post_url = 'https://www.reddit.com' + link['href']
            post_response = requests.get(post_url)
            post_soup = BeautifulSoup(post_response.content, 'html.parser')

            # Extract text from the post
            post_text = post_soup.find('div', class_='_eYtD2XCVieq6emjKBH3m').get_text(strip=True)
            if post_text and is_minecraft_key(post_text):
                keys.append(post_text)
    return keys

def scrape_forum(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    keys = []

    # Example: Scraping keys from a specific HTML structure
    for element in soup.find_all('div', class_='key-container'):
        key = element.get_text(strip=True)
        if key and is_minecraft_key(key):
            keys.append(key)

    return keys

def scrape_keys(url):
    if 'reddit.com' in url:
        subreddit = url.split('/r/')[1].split('/')[0]
        return scrape_reddit(subreddit)
    else:
        return scrape_forum(url)

@app.route('/scrape', methods=['GET'])
def scrape():
    all_keys = []
    for website in websites:
        keys = scrape_keys(website)
        all_keys.extend(keys)
    return jsonify(keys=all_keys)

def keep_alive():
    while True:
        try:
            requests.get('https://mcscraper.onrender.com/scrape')
        except requests.exceptions.RequestException as e:
            print(f"Keep-alive request failed: {e}")
        time.sleep(60 * 15)  # Keep alive every 15 minutes

if __name__ == '__main__':
    # Start the keep-alive thread
    keep_alive_thread = threading.Thread(target=keep_alive)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()

    app.run(host='0.0.0.0', port=10000)
