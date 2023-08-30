import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from telegram.ext import Updater

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRAC_TOKEN')
TELEGRAM_TOKEN = os.getenv('TEL_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TEL_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Функция check_tokens проверяет доступность переменных окружения."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    token = all(token for token in tokens)

    return token


def send_message(bot, message):
    """Функция send_message отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение успешно отправлено')
    except telegram.TelegramError as error:
        logging.error(f'Произошла ошибка при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Функция get_api_answer делает запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}

    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
        response.raise_for_status()
    except requests.exceptions.RequestException as error:
        logging.error(f'При запросе к API произошла ошибка: {error}')

    if response.status_code == HTTPStatus.OK:
        try:
            return response.json()
        except ValueError as error:
            logging.error(f'При преобразовании возникла ошибка: {error}.')
    else:
        logging.error(
            f'Произошла ошибка при запросе к API. '
            f'Статус страницы: {response.status_code}'
        )
        raise ConnectionError(f'Статус страницы: {response.status_code}')


def check_response(response):
    """Функция check_response проверяет ответ на соответствие документации."""
    if not isinstance(response, dict):
        logging.error("Ответ API не соответствует документации - 'TypeError'.")
        raise TypeError('Тип данных в ответе API не соответствует ожидаемому.')

    expected_keys = ['homeworks', 'current_date']

    if all(key in response for key in expected_keys):
        if isinstance(response['homeworks'], list):
            logging.debug('Ответ API соответствует документации')
        else:
            logging.error(
                "Ответ API не соответствует документации - 'TypeError'."
            )
            raise TypeError(
                'Тип данных в ответе API не соответствует ожидаемому.'
            )
    else:
        logging.error('Ответ API не соответствует документации')
        raise KeyError('Отсутствуют ключи Домашки')


def parse_status(homework):
    """Функция parse_status извлекает статус домашней работы."""
    if 'homework_name' not in homework:
        logging.error("В ответе API нет ключа 'homework_name'.")
        raise KeyError("KeyError('homework_name')")

    homework_name = homework.get('homework_name')
    if not homework_name:
        logging.error('Не удалось извлесь информацию о домашке.')

    status = homework.get('status')

    if status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[status]
    else:
        logging.error('Получен недокументированный статус домашки')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logging.debug('Бот запущен')

    if not check_tokens():
        logging.critical('Отсутствуют переменные окружения')
        raise EnvironmentError('Отсутствуют переменные окружения')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    updater = Updater(token=TELEGRAM_TOKEN)

    while True:
        logging.debug('Начался цикл')
        try:
            api_response = get_api_answer(timestamp)
            check_response(api_response)
            homeworks = api_response.get('homeworks')
            if homeworks:
                for homework in homeworks:
                    status_message = parse_status(homework)
                    send_message(bot, status_message)
            else:
                empry_status_message = 'Список домашних работ пуст'
                send_message(bot, empry_status_message)
            current_date = api_response.get('current_date')
            timestamp = current_date if current_date else timestamp
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)

        time.sleep(RETRY_PERIOD)
        updater.start_polling()
        updater.idle()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(message)s',
    )
    main()
