import argparse
import requests
import re
from lxml import html
from datetime import date
import logging
import time
import os

MONTHS = [
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]

LOGGER = logging.getLogger(__name__)
CAUSES = list(range(1,9))
RE_NOT_FREE = re.compile(r"^Keine\s+freien\s+Termine\s+am\s+(?P<day>[0-9]+)\s*\.\s*(?P<month>\w+)\s(?P<year>[0-9]+)$")
RE_FREE = re.compile(r"^Termine\s+am\s+(?P<day>[0-9]+)\s*\.\s*(?P<month>\w+)\s(?P<year>[0-9]+)$")
CHAT_ID = os.getenv("CHAT_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")


def parse_date(*, day, month, year):
    return date(day=day, year=year, month=MONTHS.index(month) + 1)


def get_appointments(cause=1, month=None, year=None):
    params = {
        'cur_cause': cause
    }
    if month is not None:
        params[month] = month
    if year is not None:
        params[year] = year
    r = requests.get(
        'https://termine.dresden.de/netappoint/index.php?company=stadtdresden-bb&step=2',
        params=params
    ).text
    doc = html.fromstring(r)
    text = [
        "".join(e.xpath(".//text()")).strip()
        for e in doc.xpath('//td[.//span[contains(text(), "Termine am")]]')
    ]

    out = []
    for t in text:
        match = RE_FREE.match(t)
        if match is not None:
            out.append(parse_date(
                day=int(match.group('day')),
                month=match.group('month'),
                year=int(match.group('year')),
            ))
            continue
        if RE_NOT_FREE.match(t):
            continue

        LOGGER.warning("could not parse %s", t)
    return out


def telegram_bot_sendtext(message, chat_id):
    response = requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage', json={
        'chat_id': chat_id,
        'parse_mode': 'MarkdownV2',
        'text': message,
    })
    return response.json()


def telegram_escape(msg):
    for char in ['_', '-', '.', '=']:
        msg = msg.replace(char, '\\' + char)
    return msg


def get_all_appointments():
    all_dates = [(date, cause) for cause in CAUSES for date in get_appointments(cause)]
    return sorted(all_dates)


def notify(best):
    date, cause = best
    LOGGER.info("new best: %s %d", str(date), cause)
    link = f'https://termine.dresden.de/netappoint/index.php?company=stadtdresden-bb&cur_cause={cause}'
    message = f'new free appointment: {date}, visit [{link}]({link})'
    message = telegram_escape(message)
    r = telegram_bot_sendtext(message, chat_id=CHAT_ID)
    if not r.get('ok'):
        LOGGER.error("error sending tg message: %s", repr(r))

def main():
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    LOGGER.info("starting")

    best_date = min(get_all_appointments())
    notify(best_date)

    while True:
        time.sleep(5 * 60)
        LOGGER.info("start fetching best appointment")
        new_best_date = min(get_all_appointments())
        LOGGER.info("done fetching best appointment")
        if new_best_date[0] < best_date[0]:
            best_date = new_best_date
            notify(best_date)



if __name__ == '__main__':
    main()
