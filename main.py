import json
import requests
import logging
import time
import schedule
import random
from anticaptchaofficial.turnstileproxyon import *
from fake_useragent import UserAgent

# Konfigurasi logging
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Inisialisasi User-Agent acak
ua = UserAgent()

# Fungsi untuk memuat konfigurasi dari config.json
def load_config():
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
        logging.info("Berhasil memuat config.json")
        return config
    except Exception as e:
        logging.error(f"Error membaca config.json: {e}")
        print(f"Error membaca config.json: {e}")
        return None

# Fungsi untuk menyelesaikan Turnstile CAPTCHA dengan retry
def solve_turnstile_captcha(api_key, website_url, site_key, proxy, wallet_address, max_retries=3):
    retry_count = 0
    proxy_errors = ["ERROR_PROXY_TOO_SLOW", "ERROR_PROXY_CONNECTION_FAILED", "ERROR_PROXY_TIMEOUT"]

    while retry_count < max_retries:
        try:
            solver = turnstileProxyon()
            solver.set_verbose(1)
            solver.set_key(api_key)
            solver.set_website_url(website_url)
            solver.set_website_key(site_key)
            solver.set_proxy_address(proxy["address"])
            solver.set_proxy_port(proxy["port"])
            solver.set_proxy_login(proxy["login"])
            solver.set_proxy_password(proxy["password"])
            solver.set_action("faucet")
            solver.set_soft_id(0)

            token = solver.solve_and_return_solution()
            if token:
                logging.info(f"CAPTCHA Token untuk {wallet_address} (proxy: {proxy['address']}): {token}")
                print(f"CAPTCHA Token untuk {wallet_address}: {token}")
                return token
            else:
                error_code = solver.error_code
                logging.error(f"Gagal menyelesaikan CAPTCHA untuk {wallet_address}: {error_code}")
                print(f"Gagal menyelesaikan CAPTCHA untuk {wallet_address}: {error_code}")
                if error_code in proxy_errors:
                    retry_count += 1
                    logging.warning(f"Proxy error ({error_code}) untuk {wallet_address}. Retry {retry_count}/{max_retries}...")
                    print(f"Proxy error ({error_code}). Retry {retry_count}/{max_retries}...")
                    time.sleep(5)
                    continue
                return None
        except Exception as e:
            logging.error(f"Error saat menyelesaikan CAPTCHA untuk {wallet_address}: {e}")
            print(f"Error saat menyelesaikan CAPTCHA untuk {wallet_address}: {e}")
            retry_count += 1
            logging.warning(f"Exception selama CAPTCHA untuk {wallet_address}. Retry {retry_count}/{max_retries}...")
            print(f"Exception selama CAPTCHA. Retry {retry_count}/{max_retries}...")
            time.sleep(5)
    logging.error(f"Gagal menyelesaikan CAPTCHA untuk {wallet_address} setelah {max_retries} percobaan.")
    print(f"Gagal menyelesaikan CAPTCHA untuk {wallet_address} setelah {max_retries} percobaan.")
    return None

# Fungsi untuk mengirim permintaan ke faucet
def request_faucet(captcha_token, wallet_address, proxy):
    url = "https://irys.xyz/api/faucet"
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "origin": "https://irys.xyz",
        "priority": "u=1, i",
        "referer": "https://irys.xyz/faucet",
        "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": ua.random  # User-Agent acak
    }
    payload = {
        "captchaToken": captcha_token,
        "walletAddress": wallet_address
    }
    proxies = {
        "http": f"http://{proxy['login']}:{proxy['password']}@{proxy['address']}:{proxy['port']}",
        "https": f"http://{proxy['login']}:{proxy['password']}@{proxy['address']}:{proxy['port']}"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, proxies=proxies)
        logging.info(f"Status Code untuk {wallet_address}: {response.status_code}")
        logging.info(f"Response untuk {wallet_address}: {response.text}")
        print(f"Status Code untuk {wallet_address}: {response.status_code}")
        print(f"Response: {response.text}")
        return response.json()
    except Exception as e:
        logging.error(f"Error saat mengirim permintaan untuk {wallet_address}: {e}")
        print(f"Error saat mengirim permintaan untuk {wallet_address}: {e}")
        return None

# Fungsi utama untuk memproses semua wallet
def process_wallets():
    print("Memulai proses faucet Irys...")
    logging.info("Memulai proses faucet Irys...")
    config = load_config()
    if not config:
        logging.error("Gagal memuat konfigurasi. Bot dihentikan.")
        print("Bot dihentikan karena gagal memuat konfigurasi.")
        return

    api_key = config.get("anti_captcha_api_key")
    website_url = config.get("website_url")
    site_key = config.get("site_key")
    wallets = config.get("wallets", [])

    if not wallets:
        logging.error("Tidak ada wallet ditemukan di config.json.")
        print("Tidak ada wallet ditemukan di config.json.")
        return

    for wallet in wallets:
        wallet_address = wallet.get("wallet_address")
        proxy = wallet.get("proxy")

        if not wallet_address or not proxy:
            logging.error(f"Konfigurasi tidak lengkap untuk wallet: {wallet_address}")
            print(f"Konfigurasi tidak lengkap untuk wallet: {wallet_address}")
            continue

        logging.info(f"Memproses wallet: {wallet_address} dengan proxy: {proxy['address']}")
        print(f"Memproses wallet: {wallet_address} dengan proxy: {proxy['address']}")
        captcha_token = solve_turnstile_captcha(api_key, website_url, site_key, proxy, wallet_address)
        if captcha_token:
            logging.info(f"Mengirim permintaan faucet untuk {wallet_address}...")
            print(f"Mengirim permintaan faucet untuk {wallet_address}...")
            result = request_faucet(captcha_token, wallet_address, proxy)
            if result:
                logging.info(f"Permintaan berhasil untuk {wallet_address}: {result}")
                print(f"Permintaan berhasil untuk {wallet_address}: {result}")
            else:
                logging.error(f"Permintaan gagal untuk {wallet_address}.")
                print(f"Permintaan gagal untuk {wallet_address}.")
        else:
            logging.error(f"CAPTCHA gagal untuk {wallet_address}. Melanjutkan ke wallet berikutnya.")
            print(f"CAPTCHA gagal untuk {wallet_address}. Melanjutkan ke wallet berikutnya.")
        time.sleep(5)

# Fungsi utama
def main():
    schedule.every(24).hours.do(process_wallets)
    process_wallets()

    print("Scheduler berjalan. Menunggu jadwal berikutnya (setiap 24 jam)...")
    logging.info("Scheduler dimulai.")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()