import json
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    encoding="utf-8",
    level=logging.WARNING,
    filename="homework.log",
    format="%(asctime)s, %(levelname)s, %(message)s",
)

logger = logging.getLogger()
streamHandler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

PRACTICUM_TOKEN = os.getenv("TOKEN_PRACTICUM")
TELEGRAM_TOKEN = os.getenv("TOKEN_TELEGRAM")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}

HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}


def check_tokens():
    """Проверка обяязательных переменных."""
    error_tokens = []
    PARAMETRS_DICT = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    for name, parametrs in PARAMETRS_DICT.items():
        if parametrs is None:
            error_tokens.append(name)
    if error_tokens:
        error_message = "Проверьте переменные окружения."
        logger.critical(error_message)
        raise ValueError(error_message)


def send_message(bot, message):
    """Отправка сообщения в телеграм чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
    except telegram.error.TelegramError as error:
        logger.error(f"Бот не отправил сообщение: {error}")
    logger.debug(f"Бот отправил сообщение: {message}.")


def get_api_answer(timestamp):
    """Выполняем запрос API."""
    payload = {"from_date": timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException as error:
        raise ConnectionError(
            f"Ошибка при подключении к основному API: {error}"
        )
    if response.status_code != HTTPStatus.OK.value:
        error_message = "Ошибочный код в ответе API."
        logger.error(error_message)
        raise requests.exceptions.HTTPError(error_message)
    if not isinstance(response.json(), dict):
        error_message = "Ошибка типа данных ответа на запрос."
        logger.error(error_message)
        raise TypeError(error_message)
    try:
        response_json = response.json()
    except json.JSONDecodeError as error:
        error_message = f"Не удалось расшифровать ответ JSON: {error}."
        logger.error(error_message)
        raise ValueError(error_message)

    return response_json


def check_response(response):
    """Проверка корректности полученных от API данных."""
    if not isinstance(response, dict):
        error_message = "Ответ API имеет ошибочный тип данных."
        logger.error(error_message)
        raise TypeError(error_message)
    if "homeworks" not in response:
        error_message = "В ответе API отсутствует параметр 'homeworks'."
        logger.error(error_message)
        raise ValueError(error_message)
    if "current_date" not in response:
        error_message = "В ответе API отсутствует параметр 'curren_date'."
        logger.error(error_message)
        raise ValueError(error_message)
    if not isinstance(response["homeworks"], list):
        error_message = "Ответ API имеет ошибочный тип данных."
        logger.error(error_message)
        raise TypeError(error_message)
    if not response["current_date"]:
        error_message = (
            "В ответе API параметр 'current_date' имеет ошибочное значение."
        )
        logger.exception(error_message)
    if not response["homeworks"]:
        error_message = "Статус работ не изменился."
        raise Exception(error_message)
    else:
        return response["homeworks"][0]


def parse_status(homework):
    """Проверка статуса домашней работы."""
    if "homework_name" not in homework:
        error_message = "API домашки нет ключа: 'homework_name'"
        logger.error(error_message)
        raise KeyError(error_message)
    if "status" not in homework:
        error_message = "API домашки нет ключа: 'status'"
        logger.error(error_message)
        raise KeyError(error_message)
    homework_name = homework["homework_name"]
    status = homework["status"]
    if status not in HOMEWORK_VERDICTS:
        error_message = (
            f"Некорректное значения состояния проверки работы: {status}"
        )
        logger.error(error_message)
        raise ValueError(error_message)
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    timestamp = int(time.time())
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    old_message = ""
    while True:
        try:
            response_json = get_api_answer(timestamp)
            homework = check_response(response_json)
            timestamp = response_json["current_date"]
            message = parse_status(homework)
            if old_message != message:
                send_message(bot, message)
                old_message = message
        except Exception as error:
            error_message = f"Работа программы: {error}"
            logger.exception(error_message)
            if old_message != error_message:
                old_message = error_message
                send_message(bot, error_message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
