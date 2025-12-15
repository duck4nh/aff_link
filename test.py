# Cleaned & streamlined version of login_shopee_affiliate_cookie_json.py
# Purpose: keep cookie load + core pipeline (go to offer, search, filter commission, select all pages 1-5,
# click "Lấy link hàng loạt" -> click "Lấy link"), but remove non-essential code and shorten wait times.
# USAGE: python login_shopee_affiliate_cookie_json.cleaned.py "từ khóa tìm kiếm"

import json
import time
import os
import argparse
from urllib.parse import urlparse

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# ---------------- CONFIG ----------------
COOKIE_JSON_FILE = "cookie.json"
TARGET_URL = "https://affiliate.shopee.vn"
HEADLESS = False
KEEP_BROWSER_OPEN = False
OFFER_PATH = "/offer/product_offer"
ALTERNATE_PATHS = [
    "/offer/custom_link",
    "/campaign/campaign_list",
    "/creative/product_feed",
]
MAX_OFFER_ATTEMPTS = 6
DEFAULT_WAIT = 6  # base explicit wait (seconds) - short for speed
DOWNLOAD_DIR = os.path.abspath("downloads")
# -----------------------------------------

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def load_cookies_from_json(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}. Export cookie bằng Cookie Editor trước.")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cookies, local_storage = [], []
    if isinstance(data, dict):
        if 'cookies' in data and isinstance(data['cookies'], list):
            cookies = data['cookies']
        elif 'cookie' in data and isinstance(data['cookie'], list):
            cookies = data['cookie']
        else:
            if 'name' in data and 'value' in data:
                cookies = [data]
            else:
                for v in data.values():
                    if isinstance(v, list) and v and isinstance(v[0], dict) and 'name' in v[0]:
                        cookies = v
                        break
        if 'localStorage' in data and isinstance(data['localStorage'], list):
            local_storage = data['localStorage']
    elif isinstance(data, list):
        cookies = data
    else:
        raise ValueError('Không hiểu format cookie.json')

    print(f"Loaded {len(cookies)} cookies")
    return cookies, local_storage


def normalize_domain_for_selenium(domain, default_host):
    return (domain or default_host).lstrip('.')


def try_set_cookie_via_cdp(driver, cookie):
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        payload = {
            'name': cookie['name'],
            'value': cookie['value'],
            'domain': cookie.get('domain'),
            'path': cookie.get('path', '/'),
            'secure': bool(cookie.get('secure', False)),
            'httpOnly': bool(cookie.get('httpOnly', False)),
        }
        if cookie.get('expiry') is not None:
            try:
                payload['expires'] = float(cookie.get('expiry'))
            except:
                pass
        driver.execute_cdp_cmd("Network.setCookie", payload)
        return True
    except Exception:
        return False


def add_cookies_to_driver(driver, cookies, target_url):
    parsed = urlparse(target_url)
    host = parsed.hostname or 'shopee.vn'
    root = f"{parsed.scheme or 'https'}://{host}"
    driver.get(root)
    time.sleep(0.5)
    try:
        driver.delete_all_cookies()
    except:
        pass

    added = 0
    for c in cookies:
        try:
            name = c.get('name') or c.get('Name') or c.get('key')
            value = c.get('value') or c.get('Value') or c.get('val') or c.get('cookie')
            if not name or value is None:
                continue
            domain_raw = c.get('domain', '') or host
            domain = normalize_domain_for_selenium(domain_raw, host)
            sc = {'name': name, 'value': value, 'domain': domain, 'path': c.get('path', '/') or '/'}
            exp = c.get('expirationDate') or c.get('expires') or c.get('expiry')
            if exp:
                try:
                    sc['expiry'] = int(float(exp))
                except:
                    pass
            try:
                driver.add_cookie(sc)
                added += 1
            except Exception:
                cdp_payload = sc.copy(); cdp_payload['domain'] = domain_raw or host
                if try_set_cookie_via_cdp(driver, cdp_payload):
                    added += 1
        except Exception:
            continue

    print(f"Added ~{added}/{len(cookies)} cookies")
    driver.get(target_url)
    time.sleep(1)
    try:
        driver.refresh()
        time.sleep(0.5)
    except:
        pass


def import_local_storage(driver, items, target_origin):
    if not items:
        return
    parsed = urlparse(target_origin)
    origin = f"{parsed.scheme}://{parsed.hostname}"
    try:
        driver.get(origin)
        time.sleep(0.3)
    except:
        pass
    for it in items:
        try:
            if isinstance(it, dict) and 'key' in it and 'value' in it:
                k, v = it['key'], it['value']
            elif isinstance(it, (list, tuple)) and len(it) >= 2:
                k, v = it[0], it[1]
            elif isinstance(it, dict) and len(it) == 1:
                k = list(it.keys())[0]; v = it[k]
            else:
                continue
            driver.execute_script(f"window.localStorage.setItem({json.dumps(k)}, {json.dumps(v)});")
        except Exception:
            continue
    time.sleep(0.2)


def is_captcha_page(driver):
    try:
        url = (driver.current_url or '').lower()
        src = (driver.page_source or '').lower()
        for k in ['captcha', 'checkcaptcha', 'challenge', 'verify', 'hcaptcha', 'recaptcha']:
            if k in url or k in src:
                return True
        return False
    except:
        return False


def try_navigate_offer_with_retries(driver, target_origin, offer_path, alternate_paths, max_attempts=3):
    parsed = urlparse(target_origin)
    root = f"{parsed.scheme}://{parsed.hostname}"
    offer_url = root.rstrip('/') + offer_path
    alt_urls = [root.rstrip('/') + p for p in alternate_paths]

    for attempt in range(1, max_attempts + 1):
        try:
            driver.get(offer_url)
            WebDriverWait(driver, DEFAULT_WAIT).until(lambda d: d.current_url is not None)
            time.sleep(0.6)
        except Exception:
            time.sleep(0.5)
        if not is_captcha_page(driver):
            print('Reached offer page')
            return True
        try:
            driver.get(alt_urls[attempt % len(alt_urls)])
            time.sleep(0.6)
            driver.get(offer_url)
            time.sleep(0.6)
        except Exception:
            pass
    print('Cannot reach offer without captcha')
    return False


def perform_search(driver, query):
    if not query:
        return False
    selectors = [
        'input[placeholder="Tìm kiếm tất cả sản phẩm Shopee"]',
        'input.ant-input.ant-input-lg[placeholder*="Tìm kiếm"]',
        'input[type="search"]',
        'input[role="searchbox"]'
    ]
    input_el = None
    for sel in selectors:
        try:
            input_el = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
            break
        except Exception:
            continue
    if not input_el:
        for el in driver.find_elements(By.TAG_NAME, 'input'):
            try:
                ph = (el.get_attribute('placeholder') or '').lower()
                if 'tìm kiếm' in ph:
                    input_el = el
                    break
            except:
                continue
    if not input_el:
        return False

    try:
        input_el.click()
        input_el.clear()
    except Exception:
        pass
    input_el.send_keys(query)
    input_el.send_keys(Keys.ENTER)

    try:
        WebDriverWait(driver, DEFAULT_WAIT).until(lambda d: d.current_url and ('search' in d.current_url or 'offer' in d.current_url))
    except Exception:
        time.sleep(0.8)
    time.sleep(0.6)
    return True


def click_commission_and_select_all(driver):
    try:
        try:
            radio = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'input.ant-radio-button-input[value="5"]')))
            driver.execute_script('arguments[0].click();', radio)
        except Exception:
            labels = driver.find_elements(By.CSS_SELECTOR, 'label.ant-radio-button-wrapper')
            for lbl in labels:
                if 'hoa hồng' in (lbl.text or '').lower():
                    driver.execute_script('arguments[0].click();', lbl)
                    break
        time.sleep(0.6)
    except Exception:
        return False

    try:
        WebDriverWait(driver, 4).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.batch-bar-wrapper, .search-list, .shopee-search-item-result')))
    except Exception:
        time.sleep(0.6)

    try:
        checkbox = None
        try:
            checkbox = driver.find_element(By.CSS_SELECTOR, '.batch-bar-wrapper #batch-bar .ant-checkbox-input')
        except Exception:
            try:
                checkbox = driver.find_element(By.CSS_SELECTOR, '.batch-bar-wrapper .ant-checkbox-input')
            except Exception:
                checkbox = None
        if checkbox:
            driver.execute_script('arguments[0].click();', checkbox)
            time.sleep(0.5)
            return True
        return False
    except Exception:
        return False


def select_all_on_multiple_pages(driver, start_page=2, end_page=5):
    for page in range(start_page, end_page + 1):
        try:
            btn = WebDriverWait(driver, 4).until(
                EC.element_to_be_clickable((By.XPATH, f"//span[contains(@class,'page-item') and normalize-space()='{page}']"))
            )
            driver.execute_script('arguments[0].click();', btn)
            time.sleep(0.8)
        except Exception:
            continue

        try:
            WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.search-list, .shopee-search-item-result')))
        except Exception:
            time.sleep(0.5)
        try:
            cb = None
            try:
                cb = driver.find_element(By.CSS_SELECTOR, '.batch-bar-wrapper #batch-bar .ant-checkbox-input')
            except Exception:
                try:
                    cb = driver.find_element(By.CSS_SELECTOR, '.batch-bar-wrapper .ant-checkbox-input')
                except Exception:
                    cb = None
            if cb:
                driver.execute_script('arguments[0].click();', cb)
                time.sleep(0.4)
        except Exception:
            continue


# --- robust click helper used by batch link flow ---
def robust_click(driver, el, timeout=1.0):
    """Try multiple ways to click an element reliably."""
    from selenium.webdriver.common.keys import Keys
    try:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except:
            pass
        time.sleep(0.05)
        try:
            driver.execute_script('arguments[0].click();', el)
            return True
        except:
            pass
        try:
            script = (
                "var el = arguments[0];"
                "function fire(type){var e=new MouseEvent(type,{view:window,bubbles:true,cancelable:true,button:0});el.dispatchEvent(e);}"
                "fire('mousedown');fire('mouseup');fire('click');"
            )
            driver.execute_script(script, el)
            time.sleep(0.05)
            return True
        except:
            pass
        try:
            script = (
                "var el = arguments[0];"
                "try{el.removeAttribute('disabled');}catch(e){}"
                "try{el.classList.remove('ant-btn-disabled');}catch(e){}"
                "el.style.pointerEvents='auto';el.style.opacity='1';"
            )
            driver.execute_script(script, el)
            time.sleep(0.03)
            try:
                driver.execute_script('arguments[0].click();', el)
                return True
            except:
                pass
        except:
            pass
        try:
            el.click()
            return True
        except:
            pass
        try:
            el.send_keys(Keys.ENTER)
            return True
        except:
            pass
        start = time.time()
        while time.time() - start < timeout:
            try:
                driver.execute_script('arguments[0].click();', el)
                return True
            except:
                time.sleep(0.05)
        return False
    except Exception:
        return False


def click_get_batch_links(driver):
    """
    Click "Lấy link hàng loạt", wait for modal, click inner "Lấy link" and fallback-download CSV if popup blocked.
    """
    # inject override to capture window.open calls (fallback to download via requests when popup blocked)
    try:
        driver.execute_script("""
            window._last_opened_url = null;
            if(!window._originalWindowOpen) {
                window._originalWindowOpen = window.open;
                window.open = function(url, name, specs) {
                    try { window._last_opened_url = url; } catch(e){}
                    return window._originalWindowOpen.apply(window, arguments);
                }
            } else {
                window._last_opened_url = null;
            }
        """)
    except Exception:
        pass

    # try to find and click main trigger
    def try_click_candidate(elem):
        try:
            driver.execute_script('arguments[0].scrollIntoView({block:"center"});', elem)
            time.sleep(0.12)
            return robust_click(driver, elem, timeout=1.0)
        except Exception:
            try:
                elem.click()
                return True
            except:
                return False

    candidates = []
    try:
        candidates = driver.find_elements(By.XPATH, "//button[.//span[normalize-space()='Lấy link hàng loạt']]")
    except Exception:
        candidates = []

    if not candidates:
        try:
            all_primary = driver.find_elements(By.CSS_SELECTOR, 'button.ant-btn.ant-btn-primary')
            for b in all_primary:
                try:
                    if 'lấy link hàng loạt' in (b.text or '').strip().lower():
                        candidates.append(b)
                except:
                    continue
        except Exception:
            pass

    if not candidates:
        try:
            batch = driver.find_element(By.CSS_SELECTOR, '.batch-bar-wrapper')
            for b in batch.find_elements(By.TAG_NAME, 'button'):
                try:
                    if 'lấy link' in (b.text or '').strip().lower():
                        candidates.append(b)
                except:
                    continue
        except Exception:
            pass

    clicked_main = False
    for cand in candidates:
        if try_click_candidate(cand):
            clicked_main = True
            time.sleep(0.25)
            break

    if not clicked_main:
        print('Không tìm/không click được nút Lấy link hàng loạt')
        return False

    # wait for modal
    try:
        WebDriverWait(driver, 8).until(
            EC.visibility_of_element_located((By.XPATH, "//div[contains(@class,'ant-modal-body')]//h4[normalize-space()='Link Hoa hồng Sản phẩm']"))
        )
        time.sleep(0.2)
    except Exception:
        try:
            WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.ant-modal-body')))
            time.sleep(0.2)
        except Exception:
            print('Modal không hiển thị sau khi click Lấy link hàng loạt')
            return False

    try:
        modal = driver.find_element(By.CSS_SELECTOR, '.ant-modal-body')
    except Exception:
        print('Không tìm thấy modal sau khi mở.')
        return False

    inner_selectors = [
        "//div[contains(@class,'ant-modal-body')]//button[.//span[normalize-space()='Lấy link']]",
        ".//button[contains(@class,'mkt-btn') and contains(normalize-space(string(.)), 'Lấy link')]",
        ".//button[contains(normalize-space(string(.)), 'Lấy link') or contains(normalize-space(string(.)), 'lấy link')]",
    ]

    clicked_inner = False
    for sel in inner_selectors:
        try:
            elems = []
            if sel.startswith('.//'):
                elems = modal.find_elements(By.XPATH, sel)
            else:
                elems = driver.find_elements(By.XPATH, sel)
            for e in elems:
                if try_click_candidate(e):
                    clicked_inner = True
                    time.sleep(0.2)
                    break
            if clicked_inner:
                break
        except Exception:
            continue

    if not clicked_inner:
        try:
            for b in modal.find_elements(By.TAG_NAME, 'button'):
                try:
                    txt = (b.text or '').strip().lower()
                    if 'lấy link' in txt:
                        if robust_click(driver, b, timeout=1.0):
                            clicked_inner = True
                            break
                except Exception:
                    continue
        except Exception:
            pass

    if not clicked_inner:
        print('Không thể click nút Lấy link trong modal')
        return False

    # after clicking inner button: try to detect window.open URL and download if popup blocked
    try:
        import requests, pathlib
        csv_url = None
        for _ in range(18):
            try:
                url = driver.execute_script("return window._last_opened_url || null;")
                if url:
                    csv_url = url
                    break
            except Exception:
                pass
            time.sleep(0.2)

        if csv_url:
            print("Detected download URL:", csv_url)
            cookie_jar = {}
            try:
                for c in driver.get_cookies():
                    cookie_jar[c['name']] = c['value']
            except Exception:
                pass
            headers = {
                "User-Agent": driver.execute_script("return navigator.userAgent") or "Mozilla/5.0",
                "Referer": TARGET_URL
            }
            if csv_url.startswith("//"):
                csv_url = "https:" + csv_url
            elif csv_url.startswith("/"):
                parsed = urlparse(driver.current_url)
                csv_url = f"{parsed.scheme}://{parsed.hostname}{csv_url}"
            # --- clean old CSV files before saving new one ---
            for f in os.listdir(DOWNLOAD_DIR):
                if f.lower().endswith(".csv"):
                    try:
                        os.remove(os.path.join(DOWNLOAD_DIR, f))
                    except Exception:
                        pass
            r = requests.get(csv_url, cookies=cookie_jar, headers=headers, stream=True, timeout=20)
            r.raise_for_status()
            fixed_filename = "shopee_affiliate_links.csv"
            target_path = os.path.join(DOWNLOAD_DIR, fixed_filename)
            with open(target_path, "wb") as fh:
                for chunk in r.iter_content(8192):
                    if chunk:
                        fh.write(chunk)
            print("Saved CSV to:", target_path)
        else:
            print("No window.open URL detected; maybe modal returned links inside DOM or popup allowed handled the download.")
    except Exception as e:
        print("Fallback download error:", e)

    try:
        WebDriverWait(driver, 6).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, '.ant-modal-body')))
        time.sleep(0.2)
    except Exception:
        time.sleep(0.5)

    print('Đã click Lấy link hàng loạt -> Lấy link')
    return True


def login_with_cookie_json(search_query=None):
    cookies, local_items = load_cookies_from_json(COOKIE_JSON_FILE)

    options = uc.ChromeOptions()
    if HEADLESS:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--start-maximized')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-popup-blocking')

    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_setting_values.popups": 1,
    }
    options.add_experimental_option("prefs", prefs)

    driver = uc.Chrome(options=options)

    try:
        add_cookies_to_driver(driver, cookies, TARGET_URL)
        if local_items:
            import_local_storage(driver, local_items, TARGET_URL)

        time.sleep(0.8)
        cur = driver.current_url.lower()
        if 'login' in cur or 'sign' in cur:
            print('Cookie không hợp lệ/đã hết hạn - vui lòng export lại cookie mới')
            if not KEEP_BROWSER_OPEN:
                driver.quit(); return
        else:
            print('Cookie applied - tiếp tục')

        ok = try_navigate_offer_with_retries(driver, TARGET_URL, OFFER_PATH, ALTERNATE_PATHS, MAX_OFFER_ATTEMPTS)
        if not ok:
            print('Không vào được offer, dừng')
            if not KEEP_BROWSER_OPEN:
                driver.quit(); return

        if search_query:
            if not perform_search(driver, search_query):
                print('Không tìm thấy input search')
            else:
                if click_commission_and_select_all(driver):
                    select_all_on_multiple_pages(driver, 2, 5)
                    if click_get_batch_links(driver):
                        print('Lấy link hàng loạt: đã click Lấy link')
                    else:
                        print('Không thể click Lấy link hàng loạt / Lấy link')
                else:
                    print('Không thể chọn bộ lọc hoa hồng / tick tất cả')

        print('Xong. Giữ trình duyệt mở để kiểm tra.' if KEEP_BROWSER_OPEN else 'Xong. Đóng trình duyệt.')
        if KEEP_BROWSER_OPEN:
            input('Nhấn Enter để đóng...')
    finally:
        if not KEEP_BROWSER_OPEN:
            try:
                driver.quit()
            except:
                pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('query', nargs='*')
    args = parser.parse_args()
    search_query = ' '.join(args.query).strip() if args.query else ''
    login_with_cookie_json(search_query=search_query)
