import os
import time
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
import concurrent.futures
import random
from webdriver_manager.chrome import ChromeDriverManager

class TokenCrawler:
    def __init__(self, headless=True):
        self.options = Options()
        if headless:
            self.options.add_argument("--headless")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--no-sandbox")
        self.driver1 = None
        self.driver2 = None
        self.driver3 = None
    
    def setup_driver(self):
        # Additional options can be added here
        print("SETTING UP DRIVER")
        return webdriver.Chrome(options=self.options)
    
    def create_embed_file(self, address):
        directory = "embeds"
        if not os.path.exists(directory):
            os.makedirs(directory)
        filename = os.path.join(directory, f"embed_{address}.html")
        embed_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Embed Test for {address}</title>
  <style>
    html, body {{
      height: 100%;
      margin: 0;
    }}
    #dexscreener-embed {{
      position: relative;
      width: 100%;
      height: 450px;
    }}
    @media (max-width: 1400px) {{
      #dexscreener-embed {{
          height: 500px;
      }}
    }}
    #dexscreener-embed iframe {{
      position: absolute;
      width: 100%;
      height: 100%;
      top: 0;
      left: 0;
      border: 0;
    }}
  </style>
</head>
<body>
  <div id="dexscreener-embed">
    <iframe src="https://dexscreener.com/solana/{address}?embed=1&loadChartSettings=1&trades=1&chartLeftToolbar=0&chartTheme=dark&theme=dark&chartStyle=1&chartType=usd&interval=15"></iframe>
  </div>
</body>
</html>
"""
        with open(filename, "w", encoding="utf-8") as f:
            f.write(embed_html)
        return filename
    
    def get_pane_data(self, address):
            # bundle_percentage = future_bundle.result()
        rug_dict = self.get_rugchecker_info(address)
        # volume_dict = self.get_volume(address, timeframes=["5M", "1H"])
        # volume_5m = volume_dict["5M"]
        # volume_1h = volume_dict["1H"]
        rug_score = rug_dict['safety_value']
        alerts = rug_dict['alerts']
        # Determine color for 5-minute volume
        # Using thresholds: <10k = red, 10k-49,999 = yellow, 50k+ = green.
        # if volume_5m['float'] < 10:
        #     vol5_color = "red"
        # elif volume_5m['float'] < 50:
        #     vol5_color = "yellow"
        # else:
        #     vol5_color = "green"

        # # For 1-hour volume, extrapolate thresholds by multiplying by 12.
        # # Thresholds become: <120k = red, 120k-599,999 = yellow, 600k+ = green.
        # if volume_1h['float'] < 120:
        #     vol1h_color = "red"
        # elif volume_1h['float'] < 600:
        #     vol1h_color = "yellow"
        # else:
        #     vol1h_color = "green"

        # Determine color for rug safety score.
        # We use an approximate split: 0-33 (red), 34-66 (orange), 67-100 (green)
        if rug_score <= 33:
            if len(alerts) > 0:
                safety_color = "red"
            else:
                safety_color = "green"
        elif rug_score <= 75:
            safety_color = "orange"
        else:
            safety_color = "green"

        # Format alerts as list items
        alerts_html = "".join(f"<li style='margin: 5px 0;'>{alert}</li>" for alert in alerts)

        # Construct the HTML string for the pane
        html = f"""
        <div style="font-family: Arial, sans-serif; padding: 10px; max-width: 400px; overflow: hidden;">
        <h2 style="text-align:center; margin-bottom: 10px; font-size: 1.5em;">Token Data</h2>
        <p style="margin: 5px 0;">
            <strong>Rug Safety Score:</strong>
            <span style="color: {safety_color}; font-weight: bold;">{rug_score}</span>
        <p style="margin: 5px 0;"><strong>Alerts:</strong></p>
        <ul style="padding-left: 20px; margin-top: 0; list-style-type: disc;">
            {alerts_html}
        </ul>
        </div>
        """
        return html

    def get_bundle_data(self, address):
        url = f"https://trench.bot/bundles/{address}"
        if self.driver1 is None:
            self.driver1 = self.setup_driver()
        driver = self.driver1
        driver.get(url)
        wait = WebDriverWait(driver, 2)
        try:
            trench_element = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.overall-info-overlay.normal-view"))
            )
            held_percentage_element = trench_element.find_element(
                By.XPATH, ".//span[contains(text(),'Held Percentage')]/following-sibling::span"
            )
            held_percentage = held_percentage_element.text.strip()
        except Exception as e:
            print("Error in get_bundle_data:", e)
            return "N/A"
        return held_percentage
    
    def get_rugchecker_info(self, address):
        print(f"Getting rugchecker info for {address}")
        url = f"https://rugchecker.com/tokens/{address}"
        if self.driver1 is None:
            self.driver1 = self.setup_driver()
        driver = self.driver1
        driver.get(url)
        wait = WebDriverWait(driver, 2)
        time.sleep(2)
        try:
            safety_element = wait.until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Safety Score:')]"))
            )
            safety_score = safety_element.text
        except Exception as e:
            print("Error in get_rugchecker_info:", e)
            return {"safety score": "N/A", "alerts": [], "safety_value": 0}
        try:
            safety_score_value = float(safety_score.split(":")[1].split("/")[0].strip())
        except Exception as e:
            print("Error parsing safety score:", e)
            safety_score_value = 0
        alert_elements = driver.find_elements(By.XPATH, "//div[@role='alert']")
        alerts = [elem.text for elem in alert_elements]
        return {"safety score": safety_score, "alerts": alerts, "safety_value": safety_score_value}
    
    def get_volume_text(self, driver, xpath):
        try:
            elem = driver.find_element(By.XPATH, xpath)
            return elem.text.strip()
        except StaleElementReferenceException:
            return None
        except Exception as e:
            print("Exception in get_volume_text:", e)
            return None

    def wait_for_volume_change(self, driver, xpath, old_value):
        try:
            new_value = self.get_volume_text(driver, xpath)
            print("Polling volume:", new_value, " (old value:", old_value, ")")
            if new_value and new_value != old_value:
                return new_value
        except Exception as e:
            print("Exception in wait_for_volume_change:", e)
            return False
        return False

    def get_volume(self, address, timeframes):
        file_path = self.create_embed_file(address)
        file_url = "file://" + os.path.abspath(file_path)
        if self.driver1 is None:
            self.driver1 = self.setup_driver()
        driver = self.driver1
        driver.get(file_url)
        wait = WebDriverWait(driver, 2)
        iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#dexscreener-embed iframe")))
        driver.switch_to.frame(iframe)
        volume_xpath = "//span[normalize-space()='Volume']/following-sibling::span"
        default_volume = self.get_volume_text(driver, volume_xpath)
        print("Default (24h) Volume:", default_volume)
        volume_mapping = {}
        for timeframe in timeframes:
            button_xpath = f"//button[.//span[contains(text(),'{timeframe}')]]"
            button = wait.until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
            print(f"Found {timeframe} button.")
            button.click()
            try:
                new_volume = wait.until(lambda d: self.wait_for_volume_change(d, volume_xpath, default_volume))
            except Exception as e:
                new_volume = default_volume
            try:
                vol_float = float(new_volume[1:-1])
            except Exception:
                vol_float = 0.0
            volume_mapping[timeframe] = {"string": new_volume, "float": vol_float}
            
        return volume_mapping
    
    def cleanup(self):
        if self.driver1 is not None:
            self.driver1.quit()
        if self.driver2 is not None:
            self.driver2.quit()
        if self.driver3 is not None:
            self.driver3.quit()
# Example usage:
if __name__ == "__main__":
    crawler = TokenCrawler(headless=True)
    print("created token crawler.")
    address = "2VKBwYWzUbCUt8whqe3iA8TafXrMeE9MaLHcXqSrpump"
    pane_data = crawler.get_pane_data(address)
    # bundle = crawler.get_bundle_data(address)
    # rug_info = crawler.get_rugchecker_info(address)
    # volume_5m = crawler.get_volume(address, timeframe="5M")
    # volume_1h = crawler.get_volume(address, timeframe="1H")
    
    print("Pane Data HTML:")
    print(pane_data)
    # print("\nHeld Percentage:", bundle)
    # print("\nRugchecker Info:", rug_info)
    # print("\n5M Volume:", volume_5m)
    # print("\n1H Volume:", volume_1h)