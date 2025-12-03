import json
import logging
import time
from abc import ABC
import timeit

import threading

from bs4 import BeautifulSoup

from functools import wraps

from pprint import pprint

from selenium import webdriver
from selenium.common import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


def handle_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception('Ошибка подключения драйвера:', e)
            raise ConnectionError
    return wrapper


def setup_stealth_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    # chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    # chrome_options.add_argument("--disable-images")
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


class BaseParser(ABC):
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(self.driver, 20)

    def _connect_driver(self):
        pass

    def _send_query(self):
        pass

    def _scroll(self):
        pass

    def _get_data(self):
        pass

    def _processing_data(self):
        pass

    def __execute(self):
        pass


class YandexParser(BaseParser):
    def __init__(self, driver, query: str):
        self.url = 'https://yandex.ru/maps/'
        self.query = query
        super().__init__(driver)

    @handle_errors
    def _connect_driver(self):
        self.driver.get(self.url)

    def send_query(self):
        old_url = self.driver.current_url
        for attempt in range(1, 6):
            try:
                search_box = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "input__control")))

                if search_box:
                    search_box.clear()
                    search_box.send_keys(self.query)
                    search_box.submit()
                    self.wait.until(
                        lambda d: d.current_url != old_url
                    )
                    break

            except StaleElementReferenceException as e:
                logger.exception('Не найден поле ввода', e)
                continue

    def _scroll(self):
        last_count = 0
        new_contains = []
        containers = []

        for attempt in range(1, 6):
            containers = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".scroll__container"))
            )
            if len(containers) == len(new_contains):
                continue
            break

        container = containers[-1]
        stable_rounds = 0
        while True:
            try:
                ul = self.wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'search-list-view__list'))
                )

            except TimeoutException as e:
                logger.exception('Время запроса истекло', e)
                break

            items = ul.find_elements(By.TAG_NAME, 'li')
            current_count = len(items)

            if current_count > last_count:
                last_count = current_count
                stable_rounds = 0
            else:
                stable_rounds += 1

            if stable_rounds >= 3:
                break

            self.driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollTop + arguments[0].clientHeight * 0.8;",
                container
            )
            time.sleep(0.5)

    def _get_data(self):
        all_work_time: list = []
        ul = None
        try:
            ul = self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, 'search-list-view__list'))
            )

        except TimeoutException as e:
            logger.exception('Время запроса истекло', e)

        if ul is not None:
            self.wait.until(
                EC.element_to_be_clickable((By.CLASS_NAME, 'search-business-snippet-view__title'))
            )
            data = ul.find_elements(By.CLASS_NAME, 'search-business-snippet-view__title')
            logger.info(f'Найдено элементов {len(data)}')
            print(f'Найдено элементов {len(data)}')
        else:
            raise TypeError

        with open('elements.json', 'w', encoding='utf-8') as f:
            for i, element in enumerate(data):
                start_time = timeit.default_timer()
                element.click()
                self.wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'card-title-view__title-link'))
                )
                time.sleep(0.5)
                aside_bar = self.driver.find_element(By.CLASS_NAME, 'business-card-view__main-wrapper')

                html_content = aside_bar.get_attribute("outerHTML")
                item_dict = {"html": html_content}
                f.write(json.dumps(item_dict, ensure_ascii=False) + "\n")
                time_work = timeit.default_timer() - start_time
                all_work_time.append(time_work)
                logger.info(f'Обработан элемент {i}, Время работы {time_work:.3f}')
                print(f'Обработан элемент {i}, Время работы {time_work:.3f}')
        logger.info(f'Среднее время выполнения {sum(all_work_time) / len(all_work_time):.2f}')
        print(f'Среднее время выполнения {sum(all_work_time) / len(all_work_time):.3f}')

    def _processing_data(self):
        import json

        with open('elements.json', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()  # убираем лишние пробелы/переносы
                if not line:  # пропускаем пустые строки
                    continue
                item = json.loads(line)  # превращаем строку в словарь
                print(item.get('html'))  # доступ к полю 'html'

    def _processing_by_soup(self, element):
        soup = BeautifulSoup(element, 'xlml')

        soup.find()

    def __execute(self):
        self._connect_driver()
        self.send_query()
        self._scroll()
        self._get_data()
        self._processing_data()

    def execute(self):
        self.__execute()

# Название - card-title-view__title-link
# Адрес - business-contacts-view__address-link
# Список номеров - card-dropdown-view
# Список вебсайтов - business-urls-view__url
# Список соц-сетей

def main(query: str):
    logging.basicConfig(filename='parser.log', level=logging.INFO)
    driver = setup_stealth_driver()

    parser = YandexParser(driver, query)
    parser.execute()


# main('Омск, гипермаркет')


with open('check.html', 'r', encoding='utf-8') as f:
    res = f.read()

soup = BeautifulSoup(res, 'lxml')

name = soup.find('a', attrs={'class': 'card-title-view__title-link'})
print(name.text)
address = soup.find('div', attrs={'class': 'business-contacts-view__address-link'})
print(address.text)
number_list = soup.find('div', attrs={'class': 'card-phones-view'})
numbers = number_list.find('div', attrs={'class': 'card-phones-view__phone-number'})
print(numbers.text)