
from asyncio.log import logger
from pickle import bytes_types
from typing import Optional
from PySide6 import QtCore
import logging
import os
import time
from PIL import Image
from pytesseract import pytesseract
from telethon import TelegramClient, events
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import chromedriver_autoinstaller
import re

logger = logging.getLogger(__name__)

class AmazonGiftPlugin(QtCore.QObject):
    api_id = 17489921
    api_hash = '9a398324222e145ac488afbd54a71cd1'
    client = TelegramClient('anon', api_id, api_hash)
    teserract_path = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        self.pattern = re.compile(r'^[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+$', re.MULTILINE)
        logger.info("Installing driver")
        chromedriver_autoinstaller.install()

        logger.info("Starting client telegram")
        self.client.start()
        self.client.run_until_disconnected()

    @client.on(events.NewMessage(chats='bilbiamtengarsada'))
    async def my_event_handler(self, event):
        logger.info(event)
        if hasattr(event, 'message') and hasattr(event.message.media, 'photo') and hasattr(event.message.media.photo, 'file_reference'):
            path = await self.client.download_media(event.message)

            img = Image.open(path)
            pytesseract.tesseract_cmd = self.teserract_path

            text = pytesseract.image_to_string(img).replace(" ", "")

            coupons = self.pattern.findall(text)
            for coupon in coupons:
                if len(coupon.upper().replace("-", "")) != 14:
                    continue

                logger.info("%s %s" % (event.message.date, coupon))
                                    
                options = webdriver.ChromeOptions()
                options.add_argument('user-data-dir=C:\\Users\\dbtds\\Desktop\\ChromeSelenium')
                options.add_argument('profile-directory=Profile 1')
                browser = webdriver.Chrome(options=options)
                browser.get("https://www.amazon.es/-/pt/gc/redeem")

                # Check if it is login or code page
                try:
                    WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "gc-redemption-input")))
                except TimeoutError:
                    WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "signInSubmit")))
                    browser.find_element(By.ID, "ap_email").send_keys("dbtdsilva@gmail.com")
                    browser.find_element(By.ID, "ap_password").send_keys("6t3TcxstFhATP0hI0OOh")
                    browser.find_element(By.ID, "signInSubmit").click()
                    
                WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "gc-redemption-input")))
                # Wait for captcha to be filled
                if browser.find_element(By.ID, "gc-captcha-code-input"):
                    while browser.find_element(By.ID, "gc-captcha-code-input").get_attribute('value').strip() == "":
                        time.sleep(1)
                    print("Captcha filled")
                browser.find_element(By.ID, "gc-redemption-input").send_keys(coupon)
                browser.find_element(By.ID, "gc-redemption-apply-button").click()
                time.sleep(5)
                if 'result' in browser.current_url:
                    logger.info("Code registered")
                    browser.save_screenshot("%s_%s.png" % (coupon, event.message.date))
                    browser.close()
                else:
                    pass
            os.remove(path)
