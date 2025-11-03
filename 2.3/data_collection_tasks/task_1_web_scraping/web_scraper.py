import requests
from bs4 import BeautifulSoup
import csv

URL = "https://news.ycombinator.com/"  # приклад сайту
response = requests.get(URL)
soup = BeautifulSoup(response.text, 'html.parser')

titles = [tag.text for tag in soup.select('.titleline a')]

with open("news_titles.csv", "w", newline='', encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["Title"])
    for title in titles:
        writer.writerow([title])

print("✅ Збережено новини у 'news_titles.csv'")
