import time
import re
import json
import pandas as pd


from selenium import webdriver
from selenium.common import NoSuchElementException, StaleElementReferenceException, TimeoutException, \
    ElementClickInterceptedException
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from typing import TypeVar, Callable, Any

from abc import ABC, abstractmethod


count_of_units = 1000

# Установите: pip install webdriver-manager

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import platform


def setup_driver_automatically():
    os_name = platform.system().lower()

    browsers = {}
    if os_name == 'windows':
        # browsers = get_installed_browsers_windows()
        pass
    elif os_name == 'darwin':
        # browsers = get_installed_browsers_mac()
        pass
    elif os_name == 'linux':
        # browsers = get_installed_browsers_linux()
        pass

    if not browsers:
        raise Exception("Браузеры не найдены!")

    # Выбираем браузер по приоритету
    preferred_order = ['chrome', 'firefox', 'edge', 'opera', 'safari']

    for browser in preferred_order:
        if browser in browsers:
            return setup_specific_driver(browser)

    # Если ничего не нашли, пробуем первый доступный
    first_browser = list(browsers.keys())[0]
    return setup_specific_driver(first_browser)


def setup_specific_driver(browser_name):
    if browser_name == 'chrome':
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service)

    elif browser_name == 'firefox':
        service = FirefoxService(GeckoDriverManager().install())
        return webdriver.Firefox(service=service)

    elif browser_name == 'edge':
        from selenium.webdriver.edge.service import Service as EdgeService
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        service = EdgeService(EdgeChromiumDriverManager().install())
        return webdriver.Edge(service=service)

    else:
        raise Exception(f"Браузер {browser_name} не поддерживается")


def setup_stealth_driver():
    chrome_options = Options()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    #chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument("--disable-images")
    chrome_options.add_argument("--disable-javascript")
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_settings.popups": 0,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "dom.webdriver.enabled": False
    }
    chrome_options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(options=chrome_options)


F = TypeVar('F', bound=Callable[..., Any])


def parse_if_enabled(field: str) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        def wrapper(self, *args, **kwargs):
            if not getattr(self, "check_data", {}).get(field, False):
                return None
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


class BaseParser(ABC):
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(self.driver, 20)

    @abstractmethod
    def _parse_data(self):
        pass

    @classmethod
    def _safe_find_text(cls, by, selector, driver):
        try:
            return driver.find_element(by, selector).text.strip()
        except NoSuchElementException:
            return "Не найдено"

    @classmethod
    def _safe_find_attribute(cls, by, selector, attr, driver):
        try:
            return driver.find_element(by, selector).get_attribute(attr)
        except NoSuchElementException:
            return "Не найдено"

    @classmethod
    def _find_phones(cls, driver, platform):
        if platform == '2ИГС':
            elem = driver.find_element(By.CLASS_NAME, "_b0ke8")
            a = elem.find_element(By.CLASS_NAME, '_2lcm958')
            text = a.get_attribute('href')
            phone = re.sub(r"[^\d+]", "", text)

            if not phone.startswith("+") and phone.startswith("8"):
                phone = "+7" + phone[1:]
            elif not phone.startswith("+") and phone.startswith("7"):
                phone = "+" + phone
            return phone[0] if phone else "Не найдено"

        if platform == 'Яндекс':
            phones = []
            try:
                for e in driver.find_elements(By.CLASS_NAME, 'card-phones-view__phone-number'):
                    text = e.text.strip()
                    text = text.replace('Показать телефон', '')
                    if any(c.isdigit() for c in text) and len(text) > 5:
                        phones.append(text)
            except:
                pass
            if isinstance(phones, list):
                return phones[0] if phones else "Не найдено"

        if platform == 'Google':
            try:
                phones = []
                phone_buttons = driver.find_elements(By.CSS_SELECTOR, 'button[aria-label^="Телефон:"]')

                for btn in phone_buttons:
                    label = btn.get_attribute("aria-label")
                    match = re.search(r'\+?\d[\d\s()-]{8,}\d', label)
                    if match:
                        phones.append(match.group(0).strip())

                return phones

            except Exception as e:
                print(f"⚠️ Ошибка внутри _find_phones: {e}")
                return []

    @classmethod
    def _find_email(cls, driver, platform):
        if platform == 'Яндекс':
            try:
                text = driver.page_source
                emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
                emails = [e for e in emails if 'yandex' not in e and 'maps' not in e]
                return emails[0] if emails else "Не найдено"
            except:
                return "Не найдено"
        if platform == '2ГИС':
            try:
                mail = ''
                elements = driver.find_elements(By.CLASS_NAME, '_49kxlr')
                for element in elements:
                    mail = element.find_element(By.CLASS_NAME, '_1rehek')
                return mail.text
            except Exception as e:
                return 'Не найдено'


class YandexParser(BaseParser):
    def __init__(self, driver, platform, check_data):
        super().__init__(driver)
        self.platform = platform
        self.check_data: dict[str, bool] = check_data

    def scroll(self, elements):
        n = 0
        while len(elements) < count_of_units:
            elements1 = len(elements)
            elements = self.driver.find_elements(By.CLASS_NAME, "search-business-snippet-view__content")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", elements[-1])
            time.sleep(0.5)
            elements = self.driver.find_elements(By.CLASS_NAME, "search-business-snippet-view__content")
            elements2 = len(elements)
            if elements1 == elements2:
                n += 1
                if n >= 10:
                    break
            else:
                n = 0

    def parse_element(self) -> list[dict]:
        business_elements = self.driver.find_elements(By.CLASS_NAME, 'search-business-snippet-view__title')
        total = len(business_elements)
        results = []

        for i in range(total):
            success = False
            for attempt in range(3):  # Более понятное имя переменной
                try:
                    # Обновляем элементы перед каждой попыткой
                    current_elements = self.driver.find_elements(By.CLASS_NAME, 'search-business-snippet-view__title')

                    if i >= len(current_elements):
                        break

                    business = current_elements[i]
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", business)
                    time.sleep(0.5)
                    self.wait.until(
                        EC.presence_of_element_located((By.CLASS_NAME, 'search-business-snippet-view__title'))
                    )

                    business.click()

                    data = self._parse_data()

                    if data:
                        results.append(data)
                        success = True
                        break  # Успешно обработали - выходим из цикла попыток

                except StaleElementReferenceException:
                    time.sleep(0.5)  # Добавляем задержку перед повторной попыткой
                    continue
                except Exception as e:
                    time.sleep(0.5)
                    continue

            if not success:
                pass

        return results

    def parse_businesses(self, query):
        result = []
        try:
            self.driver.get("https://yandex.ru/maps/")
            search_box = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "input__control")))
            search_box.clear()
            search_box.send_keys(f"{query}")
            search_box.submit()
            elements = self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'search-snippet-view')))
            self.scroll(elements)
            result = self.parse_element()
        except Exception as e:
            import traceback
            traceback.print_exc()

        return result

    @parse_if_enabled('name')
    def _parse_name(self):
        self.wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, 'card-title-view__title-link'))
        )
        try:
            name = self._safe_find_text(By.CLASS_NAME, 'card-title-view__title-link', self.driver)
        except Exception as e:
            name = None
        return name

    @parse_if_enabled('address')
    def _parse_address(self):
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, 'business-contacts-view__address-link'))
            )
            address = self._safe_find_text(By.CLASS_NAME, 'business-contacts-view__address-link', self.driver)
        except Exception as e:
            address = None
        return address

    @parse_if_enabled('number')
    def _parse_phone(self):
        try:
            phones = self._find_phones(self.driver, self.platform)
        except Exception as e:
            phones = []
        return phones

    @parse_if_enabled('website')
    def _parse_websites(self):
        try:
            website = self._safe_find_attribute(By.CLASS_NAME, 'business-urls-view__link', 'href', self.driver)
        except Exception as e:
            website = None
        return website

    @parse_if_enabled('mail')
    def _parse_email(self):
        try:
            email = self._find_email(self.driver, self.platform)
        except Exception as e:
            email = None

        return email

    def _parse_data(self) -> dict | None:
        try:
            card = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[class*="card"]')))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
        except Exception:
            return None

        result_dict = {
            "name": self._parse_name(), #type: ignore
            "address": self._parse_address(), #type: ignore
            "numbers": self._parse_phone(), #type: ignore
            "websites": self._parse_websites(), #type: ignore
            "email": self._parse_email(), #type: ignore
        }

        return {k: v for k, v in result_dict.items() if v}


class TwoGisParser(BaseParser):
    def __init__(self, driver, platform, check_data):
        super().__init__(driver)
        self.platform = platform
        self.check_data = check_data
        self.force = [[], 0]

    @parse_if_enabled('name')
    def _parse_name(self):
        time.sleep(0.3)
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, '_1x89xo5'))
            )
            name = self._safe_find_text(By.CLASS_NAME, '_1x89xo5', self.driver)
        except:
            print('Имя не найдено')
        return name if name else ''

    @parse_if_enabled('address')
    def _parse_address(self) -> list:
        time.sleep(0.2)
        result = ''
        try:
            for _ in range(3):
                try:
                    self.wait.until(
                        EC.presence_of_element_located((By.CLASS_NAME, '_13eh3hvq'))
                    )
                    address_texts = self.driver.find_elements(By.CLASS_NAME, '_13eh3hvq')
                    address_web = address_texts[0]
                    address_text = address_web.find_element(By.CLASS_NAME, '_2lcm958')
                    result = address_text.text
                    break
                except StaleElementReferenceException:
                    time.sleep(0.3)
            else:
                print("⚠️ Не удалось найти адрес после нескольких попыток")
        except Exception as e:
            print(f"Ошибка адреса: {e}")
        return result

    @parse_if_enabled('number')
    def _parse_phone(self):
        result_phone = []
        time.sleep(0.3)
        try:
            card = self.driver.find_elements(By.CLASS_NAME, '_b0ke8')
            for number_card in card:
                phone_el = number_card.find_element(By.CSS_SELECTOR, 'a[href^="tel:"]')
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", phone_el)
                phone = phone_el.get_attribute('href').replace('tel:', '')

                if phone:
                    result_phone.append(f"{phone} ")
        except NoSuchElementException:
            result_phone = []
        return ' '.join(result_phone)

    @parse_if_enabled('website')
    def _parse_website(self):
        url_pattern = r'^(https?:\/\/|www\.|[A-Za-z0-9-]+\.[A-Za-z]{2,})'
        result_website = []
        time.sleep(0.3)
        try:
            cards_link = self.driver.find_elements(By.CLASS_NAME, '_49kxlr')
            for card in cards_link:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                card = card.text.strip()
                if re.match(url_pattern, card):
                    result_website.append(f"{card} ")
        except NoSuchElementException:
            result_website = []
        return ' '.join(result_website)

    @parse_if_enabled('mail')
    def _parse_email(self):
        result_email = []
        time.sleep(0.3)
        try:
            # Поиск по mailto ссылкам
            mail_elements = self.driver.find_elements(By.CSS_SELECTOR, 'a[href^="mailto:"]')
            for element in mail_elements:
                href = element.get_attribute('href')
                email = href.replace('mailto:', '').strip()
                if self._is_valid_email(email) and email not in result_email:
                    result_email.append(email)

            # Поиск в тексте
            text_elements = self.driver.find_elements(By.CSS_SELECTOR,
                                                      '[class*="email"], [class*="mail"]')
            for element in text_elements:
                text = element.text.strip()
                if self._is_valid_email(text) and text not in result_email:
                    result_email.append(text)

        except Exception as e:
            print(f"Ошибка при парсинге почты: {e}")
        return ' '.join(result_email)

    def _is_valid_email(self, text):
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, text) is not None

    def _extract_clean_url(self, text, href):
        """Очищает URL от лишних символов"""
        # Предпочитаем href если он есть и валидный
        if href and 'http' in href and 'mailto:' not in href:
            return href
        elif text and ('http' in text or 'www.' in text):
            return text
        return None

    def _parse_data(self):
        result = {}
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, '_599hh'))
            )

            result = {
                "name": self._parse_name(),  # type: ignore
                "address": self._parse_address(),  # type: ignore
                "numbers": self._parse_phone(),  # type: ignore
                "websites": self._parse_website(),  # type: ignore
                "email": self._parse_email(),  # type: ignore
            }
            time.sleep(0.2)

        except TimeoutException:
            print("⚠️ Не удалось дождаться карточки компании.")
        except StaleElementReferenceException:
            print("⚠️ DOM обновился — повторяю попытку _parse_data()")
            time.sleep(0.5)
            return self._parse_data()
        except Exception as e:
            print(f"❌ Общая ошибка в _parse_data: {type(e).__name__}: {e}")

        return {k: v for k, v in result.items() if v}

    def parse_element(self):
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, '_awwm2v')))
        parent = self.driver.find_elements(By.CLASS_NAME, "_awwm2v")
        parent = parent[-1]
        total = int(self.driver.find_element(By.CLASS_NAME, '_1xhlznaa').text)

        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, '_1kf6gff')))
        time.sleep(0.5)
        children = parent.find_elements(By.CLASS_NAME, "_1kf6gff")

        for i, child in enumerate(children, 1):
            try:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", child)
                child.click()

                old_url = self.driver.current_url
                for _ in range(10):
                    new_url = self.driver.current_url
                    if new_url != old_url:
                        break
                    time.sleep(0.2)

                current_url = self.driver.current_url

                if "/branches/" in current_url:
                    self.driver.back()
                    for _ in range(10):
                        if "/branches/" not in self.driver.current_url:
                            break
                        time.sleep(0.1)
                    continue

                card = self._parse_data()

                processed_count = self.force[-1] + 1
                self.force[-1] = processed_count
                if card:
                    self.force[0].append(card)
            except StaleElementReferenceException:
                pass

        return self.force[0]

    def parse_businesses(self, query):
        all_results = []  # Все результаты
        try:
            self.driver.get("https://2gis.ru/")
            time.sleep(1)
            search_box = self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "_cu5ae4"))
            )
            search_box.clear()
            search_box.send_keys(f"{query}")
            search_box.submit()

            page_num = 1

            while True:
                print(f"\n📄 Парсим страницу {page_num}")
                page_results = self.parse_element()
                print(f"✅ Страница {page_num}: найдено {len(page_results)} элементов")

                # Поиск стрелки "вперед"
                next_arrow = None
                try:
                    arrows = self.driver.find_elements(By.CLASS_NAME, '_n5hmn94')
                    for arrow in arrows:
                        try:
                            svg = arrow.find_element(By.TAG_NAME, "svg")
                            transform = svg.get_attribute("style") or ""

                            # Более надежная проверка стрелки "вперед"
                            if "rotate(-90deg)" in transform or "rotate(270deg)" in transform:
                                classes = arrow.get_attribute('class')
                                if 'disabled' not in classes and 'hidden' not in classes:
                                    next_arrow = arrow
                                    break
                        except StaleElementReferenceException:
                            continue
                except Exception as arrow_error:
                    print(f"⚠️ Ошибка при поиске стрелки: {arrow_error}")

                if not next_arrow:
                    break

                try:
                    old_first_card = self.driver.find_element(By.CLASS_NAME, '_1kf6gff')
                    next_arrow.click()

                    # Ждем обновления контента
                    self.wait.until(EC.staleness_of(old_first_card))
                    self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "_awwm2v")))

                    page_num += 1
                    time.sleep(1)

                except Exception as e:
                    print(f"⚠️ Ошибка при переходе на страницу {page_num + 1}: {e}")
                    break
            all_results.extend(page_results)
        except Exception as e:
            print(f"❌ Критическая ошибка в parse_businesses: {e}")
            import traceback
            traceback.print_exc()

        print(f"🎉 Парсинг завершен! Всего собрано {len(all_results)} записей")

        return all_results


class GoogleParser(BaseParser):
    def __init__(self, driver, platform, check_data):
        super().__init__(driver)
        self.platform = platform
        self.check_data = check_data

    def scroll(self, max_stuck=10, timeout=120):

        start_time = time.time()
        n = 0

        while True:
            # Проверка таймаута
            if time.time() - start_time > timeout:
                print("⏰ Вышел таймаут ожидания, останавливаю скролл")
                break

            elements = self.driver.find_elements(By.CLASS_NAME, "hfpxzc")
            count = len(elements)

            # если достигли нужного количества — выходим
            if count_of_units and count >= count_of_units:
                print(f"✅ Достигнуто {count} элементов, останавливаю скролл")
                break

            if not elements:
                print("⚠️ Элементы ещё не найдены, жду...")
                time.sleep(1)
                continue

            last_element = elements[-1]

            # плавная прокрутка к последнему элементу
            self.driver.execute_script(
                'arguments[0].scrollIntoView({block: "center", behavior: "smooth"});', last_element
            )
            time.sleep(1.2)  # подождать, пока контент догрузится

            new_count = len(self.driver.find_elements(By.CLASS_NAME, "hfpxzc"))

            if new_count == count:
                n += 1
                if n >= max_stuck:
                    print("⚠️ Новых элементов нет, останавливаю скролл")
                    break
            else:
                n = 0

    def parse_element(self):
        results = []
        total = len(self.driver.find_elements(By.CLASS_NAME, "hfpxzc"))
        unique_el = None

        # Просто выводим в консоль
        print(f"📊 Найдено {total} элементов")
        business_elements = self.driver.find_elements(By.CLASS_NAME, "hfpxzc")
        for i in range(total):
            if i >= total:
                break

            business = business_elements[i]
            for attempt in range(3):
                if business != unique_el:
                    unique_el = business
                else:
                    continue

            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", business)
            time.sleep(0.3)

            try:
                business.click()
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.bJzME.Hu9e2e.tTVLSc')))
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.DUwDvf.lfPIob')))
                data = self._parse_data()

                if data:
                    results.append(data)
                    print(f"✓ Собраны данные: {data['name'][:30]}...")
            except Exception as e:
                print(f"⚠️ Ошибка при обработке {i}-го элемента: {e}")
                import traceback
                print("⚠️ Произошла ошибка:", type(e).__name__)
                print(traceback.format_exc())

        return results

    @parse_if_enabled('name')
    def _parse_name(self) -> str:
        try:
            self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.DUwDvf.lfPIob')))
            name = self._safe_find_text(By.CSS_SELECTOR, '.DUwDvf.lfPIob', self.driver)
        except TimeoutException:
            print("⚠️ Карточка не загрузилась вовремя")
            name = None
        except Exception as e:
            print('Имя карточки не найден или другая беда')
            name = None
        return name

    @parse_if_enabled('address')
    def _parse_address(self) -> list:
        try:
            address = self._safe_find_text(By.CSS_SELECTOR, '.Io6YTe.fontBodyMedium.kR99db.fdkmkc', self.driver)
        except NoSuchElementException as e:
            print('Элемента с адресом не существует')
            address = None
        time.sleep(1)
        return address

    @parse_if_enabled('number')
    def _parse_number(self) -> list:
        try:
            phones = self._find_phones(self.driver, self.platform)
        except Exception as e:
            print(f"⚠️ Ошибка внутри _find_phones: {e}")
            phones = None

        return phones

    @parse_if_enabled('website')
    def _parse_website(self) -> str:
        websites: list = []
        try:
            data_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[aria-label*="Перейти на сайт"]')

            for el in data_links:
                text = el.get_attribute('href')
                if not text:
                    continue
                url_pattern = r'^(https?:\/\/|www\.|[A-Za-z0-9-]+\.[A-Za-z]{2,})'
                if re.match(url_pattern, text):
                    websites.append(text)

        except NoSuchElementException:
            print('нету ссылки, а тебя в Сибирь')
        except Exception as e:
            print('Я нинаю', e)

        return ' '.join(websites) if websites else ''

    def _parse_data(self):
        try:
            # ждем появления карточки
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.bJzME.Hu9e2e.tTVLSc')))
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.DUwDvf.lfPIob')))
        except Exception as e:
            print(f"Ошибка парсинга карточки: {e}")
            return None
        return {'name': self._parse_name(),
                'address': self._parse_address(),
                'phone': ' '.join(self._parse_number()),
                'websites': self._parse_website(),
                }

    def parse_businesses(self, query):
        result = {}
        try:
            self.driver.get('https://www.google.com/maps')
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, 'NhWQq'))
            )
            search_box = self.driver.find_element(By.CSS_SELECTOR, '.fontBodyMedium.searchboxinput.xiQnY')
            search_box.clear()
            search_box.send_keys(f"{query}")
            search_box.send_keys(Keys.ENTER)

            self.scroll()
            result = self.parse_element()
        except Exception as e:
            print(e)
        return result


class YandexService(BaseParser):
    def __init__(self, driver, platform, check_data):
        super().__init__(driver)
        self.platform = platform
        self.check_data = check_data

    def _parse_data(self):
        pass

    def parse_element(self):
        result = []
        time.sleep(1)
        self.wait.until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, 'WorkerCard-MainRight'))
        )
        elements = self.driver.find_elements(By.CLASS_NAME, 'WorkerCard-MainRight')
        if not elements:
            print("⚠️ Нет карточек работников на странице.")
            return []
        for i in elements:
            number = ''
            social_net = []
            name = i.find_element(By.CSS_SELECTOR, ".Link.WorkerCard-Title")
            link = i.find_element(By.CSS_SELECTOR, ".Link.WorkerCard-Title").get_attribute("href")
            link = link.split('?', 1)[0]
            try:
                phone_container = i.find_element(By.CSS_SELECTOR, "button[class='Button2 Button2_width_max Button2_size"
                                                                  "_md Button2_theme_normal Button2_pin_circle PhoneLoa"
                                                                  "der-Button']")
                phone_container.click()
                time.sleep(1)
                div_number = self.wait.until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, ".Text.Text_fontSize_xxl.Text_lineHeight_xxl.Text_weig"
                                                                 "ht_bold.TextBlock.PhoneLoader-Phone"))
                )
                number = div_number.text
                # До сюда - правильно
                name.send_keys(Keys.ESCAPE)
            except Exception as e:
                print("Номер не найден")
                print(e)
            try:
                soc_net = i.find_element(By.CSS_SELECTOR, 'a[class="Link WorkerControls-Control WorkerControls-Control_chat"]')
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", soc_net)

                time.sleep(0.2)  # дать странице доотрисоваться

                soc_net.click()

                time.sleep(0.2)

                div_soc_net = self.driver.find_element(By.CLASS_NAME, "SocialLinkList")
                hrefs = div_soc_net.find_elements(By.CSS_SELECTOR, "a[target='_blank']")
                for k in hrefs:
                    sn = k.get_attribute('href')
                    sn = sn.split('?', 1)[0]
                    social_net.append(sn)
            except TimeoutException:
                print("⏱ Не дождался окна с соцсетями.")
            except ElementClickInterceptedException:
                print("⚠️ Элемент не кликается — возможно, мешает окно поиска.")
            except NoSuchElementException:
                pass
            except Exception as e:
                print('Соц. сети не найдены')
                import traceback
                print("⚠️ Произошла ошибка:", type(e).__name__)
                print(traceback.format_exc())
            result.append({
                "name": name.text,
                "link": link,
                "phone": number,
                "social_networks": social_net
            })
        return result

    def parse_businesses(self, query):
        result = []
        try:
            self.driver.get("https://uslugi.yandex.ru/")
            search_box = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "Textinput-Control")))
            search_box.click()
            search_box.send_keys(f"{query}")
            search_box.send_keys(Keys.ENTER)
            time.sleep(1)

            while True:
                try:
                    self.driver.execute_script("""
                        document.querySelectorAll('.ym-hide-content.desktop')
                            .forEach(e => e.remove());
                    """)
                    next = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "a[class='Link Link_theme_greyDark Pager-Ite"
                                                                     "m Pager-Item_text']"))
                    )
                    result.extend(self.parse_element())
                    next.click()
                    time.sleep(0.1)
                except TimeoutException:
                    print("Следующая страница не найдена — конец списка.")
                    break
        except:
            pass
        finally:
            print('rofls')

        return result


def main(query: str, platform: str, check_data: dict):
    driver = setup_stealth_driver()
    parser = ''
    if platform == 'Яндекс':
        parser = YandexParser(driver, platform, check_data)
    if platform == '2ГИС':
        parser = TwoGisParser(driver, platform, check_data)
    if platform == 'Google':
        parser = GoogleParser(driver, platform, check_data)
    if platform == "Яндекс Услуги":
        parser = YandexService(driver, platform, check_data)

    results = parser.parse_businesses(query)
    driver.quit()

    json_path = f'parsed_{platform}_{query}.json'
    excel_path = f'parsed_{platform}_{query}.xlsx'

    # Сохраняем JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Сохраняем Excel
    try:
        df = pd.DataFrame(results)
        df.to_excel(excel_path, index=False)

    except Exception as e:
        print("⚠️ Ошибка при сохранении Excel:", e)

    return excel_path