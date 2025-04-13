import json
import requests
import logging
import time
import schedule
import random
from fake_useragent import UserAgent

# 配置日志
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 初始化 User-Agent
ua = UserAgent()

# 加载配置文件
def load_config():
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
        logging.info("成功加载 config.json")
        return config
    except Exception as e:
        logging.error(f"读取 config.json 出错: {e}")
        print(f"读取 config.json 出错: {e}")
        return None

# 使用 2Captcha 解决 Turnstile 验证码
def solve_turnstile_2captcha(api_key, site_key, page_url, proxy, wallet_address, max_retries=3):
    retry_count = 0
    proxy_errors = ["ERROR_PROXY_TOO_SLOW", "ERROR_PROXY_CONNECTION_FAILED", "ERROR_PROXY_TIMEOUT"]

    while retry_count < max_retries:
        try:
            url = 'http://2captcha.com/in.php'
            data = {
                'key': api_key,
                'method': 'turnstile',
                'sitekey': site_key,
                'pageurl': page_url,
                'json': 1
            }
            
            if proxy:
                proxy_str = f"{proxy['login']}:{proxy['password']}@{proxy['address']}:{proxy['port']}"
                data['proxy'] = proxy_str
                data['proxytype'] = 'HTTP'

            # 提交验证码任务
            response = requests.post(url, data=data)
            result = response.json()
            
            if result['status'] != 1:
                logging.error(f"提交验证码失败: {result}")
                print(f"提交验证码失败: {result}")
                return None

            request_id = result['request']
            logging.info(f"验证码任务提交成功，ID: {request_id}")
            print(f"验证码任务提交成功，ID: {request_id}")

            # 查询验证码结果
            for i in range(max_retries):
                time.sleep(5)
                res = requests.get('http://2captcha.com/res.php', params={
                    'key': api_key,
                    'action': 'get',
                    'id': request_id,
                    'json': 1
                })
                res_json = res.json()
                if res_json['status'] == 1:
                    logging.info(f"验证码解决成功: {res_json['request']}")
                    print(f"验证码解决成功: {res_json['request']}")
                    return res_json['request']
                elif res_json['request'] == 'CAPCHA_NOT_READY':
                    logging.info(f"验证码仍在处理中... 尝试 {i+1}/{max_retries}")
                    print(f"验证码仍在处理中... 尝试 {i+1}/{max_retries}")
                    continue
                else:
                    logging.error(f"验证码处理失败: {res_json}")
                    print(f"验证码处理失败: {res_json}")
                    break
        except Exception as e:
            logging.error(f"验证码处理出错: {e}")
            print(f"验证码处理出错: {e}")
            retry_count += 1
            logging.warning(f"验证码处理失败，重试 {retry_count}/{max_retries}")
            print(f"验证码处理失败，重试 {retry_count}/{max_retries}")
            time.sleep(5)

    logging.error(f"尝试 {max_retries} 次后验证码处理失败")
    print(f"尝试 {max_retries} 次后验证码处理失败")
    return None

# 发送请求到 faucet
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
        "user-agent": ua.random
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
        logging.info(f"状态码：{response.status_code}")
        logging.info(f"响应：{response.text}")
        print(f"状态码：{response.status_code}")
        print(f"响应：{response.text}")
        return response.json()
    except Exception as e:
        logging.error(f"请求失败：{e}")
        print(f"请求失败：{e}")
        return None

# 处理所有钱包
def process_wallets():
    print("开始处理 Irys faucet...")
    logging.info("开始处理 Irys faucet...")
    config = load_config()
    if not config:
        logging.error("无法加载配置，Bot 停止。")
        print("无法加载配置，Bot 停止。")
        return

    api_key = config.get("2captcha_api_key")
    website_url = config.get("website_url")
    site_key = config.get("site_key")
    wallets = config.get("wallets", [])

    if not wallets:
        logging.error("config.json 中没有钱包。")
        print("config.json 中没有钱包。")
        return

    for wallet in wallets:
        wallet_address = wallet.get("wallet_address")
        proxy = wallet.get("proxy")

        if not wallet_address or not proxy:
            logging.error(f"钱包配置不完整: {wallet_address}")
            print(f"钱包配置不完整: {wallet_address}")
            continue

        logging.info(f"处理钱包: {wallet_address}，代理: {proxy['address']}")
        print(f"处理钱包: {wallet_address}，代理: {proxy['address']}")
        captcha_token = solve_turnstile_2captcha(api_key, site_key, website_url, proxy, wallet_address)
        if captcha_token:
            logging.info(f"请求 faucet: {wallet_address}...")
            print(f"请求 faucet: {wallet_address}...")
            result = request_faucet(captcha_token, wallet_address, proxy)
            if result:
                logging.info(f"请求成功: {wallet_address}，结果: {result}")
                print(f"请求成功: {wallet_address}，结果: {result}")
            else:
                logging.error(f"请求失败: {wallet_address}")
                print(f"请求失败: {wallet_address}")
        else:
            logging.error(f"验证码失败: {wallet_address}，继续下一个钱包。")
            print(f"验证码失败: {wallet_address}，继续下一个钱包。")
        time.sleep(5)

# 主函数
def main():
    schedule.every(24).hours.do(process_wallets)
    process_wallets()

    print("调度程序启动，等待下次任务（每24小时）...")
    logging.info("调度程序启动。")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
