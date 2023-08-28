import logging
import os
import time

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
    """Функция check_tokens() проверяет доступность переменных окружения, которые необходимы для работы программы."""

    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True
    else:
        logging.critical('Отсутствуют переменные окружения')
        raise EnvironmentError('Отсутствуют переменные окружения')


def send_message(bot, message):
    """Функция send_message() отправляет сообщение в Telegram чат, определяемый переменной окружения TELEGRAM_CHAT_ID."""

    if TELEGRAM_CHAT_ID:
        try:
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            logging.debug('Сообщение успешно отправлено')
        except telegram.TelegramError as error:
            logging.error(f'Произошла ошибка при отправке сообщения: {error}')
    else:
        logging.critical(f'Отсутствуеют переменная {TELEGRAM_CHAT_ID}')
        raise EnvironmentError(f'Отсутствуеют переменная {TELEGRAM_CHAT_ID}')


def get_api_answer(timestamp):
    """Функция get_api_answer() делает запрос к единственному эндпоинту API-сервиса."""

    params = {'from_date': timestamp}

    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
        response.raise_for_status()
    except requests.exceptions.RequestException as error:
        logging.error(f'При запросе к API произошла ошибка: {error}')

    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f'Произошла ошибка при запросе к API. Статус страницы: {response.status_code}')
        raise ConnectionError(f'Статус страницы: {response.status_code}')


def check_response(response):
    """Функция check_response() проверяет ответ API на соответствие документации."""

    if type(response) != dict:
        logging.error("Ответ API не соответствует документации - 'TypeError'.")
        raise TypeError('Тип данных в ответе API не соответствует ожидаемому.')

    expected_keys = ['homeworks', 'current_date']

    if all(key in response for key in expected_keys):
        if isinstance(response['homeworks'], list):
            logging.debug('Ответ API соответствует документации')
        else:
            logging.error("Ответ API не соответствует документации - 'TypeError'.")
            raise TypeError('Тип данных в ответе API не соответствует ожидаемому.')
    else:
        logging.error(f'Ответ API не соответствует документации')
        raise KeyError('Отсутствуют ключи Домашки')


def parse_status(homework):
    """Функция parse_status() извлекает из информации о конкретной домашней работе статус этой работы."""

    if 'homework_name' not in homework:
        logging.error("В ответе API нет ключа 'homework_name'.")
        raise KeyError("KeyError('homework_name')")

    try:
        homework_name = homework.get('homework_name')
        status = homework.get('status')
    except Exception as error:
        logging.error(f'{error} - не удалось извлесь информацию о домашке.')

    if status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[status]
    else:
        logging.error('Получен недокументированный статус домашки')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(message)s',
    )
    logging.debug('Бот запущен')

    check_tokens()

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
    main()
