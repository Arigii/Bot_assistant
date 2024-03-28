from sqlite3 import connect
import requests
import logging
from config import MAX_TOKENS, ERROR_LOG_FILE, HEADERS, GPT_LOCAL_URL, FOLDER_ID, GPT_MODEL, TOKENIZER_URL

# Настройка логгера
logging.basicConfig(filename=ERROR_LOG_FILE, level=logging.DEBUG)


class GPT:
    def __init__(self):
        self.system_content = {}
        self.URL = GPT_LOCAL_URL
        self.HEADERS = HEADERS
        self.MAX_TOKENS = MAX_TOKENS
        self.assistant_content = {}
        self.count_token_user = {}

    # Проверка ответа на возможные ошибки и его обработка
    def process_resp(self, response, chat_id) -> [bool, str]:
        # Проверка json
        try:
            full_response = response.json()
        except:
            logging.error("Ошибка получения JSON")
            self.clear_history(chat_id)
            return False, "Ошибка получения JSON"

        try:
            if response.status_code != 200:
                result = f"Status code {response.status_code}"
                logging.debug(f"Неуспешная генерация ответа: {result}")
                return
            result = full_response['result']['alternatives'][0]['message']['text'] + " "
            self.save_history(result, chat_id)
            return True, self.assistant_content[chat_id]
        except Exception as e:
            result = f"Произошла непредвиденная ошибка: {e}"
        return result

    # Формирование промта
    def make_promt(self, chat_id):
        try:
            con = connect("db.db")
            cur = con.cursor()
            user_request = cur.execute(f"select request from users where chat_id = '{chat_id}'").fetchone()[0]
            cur.close()
            if user_request is None:
                return "Не найдет запрос. Повторите позже"
            json = {
                "modelUri": f"gpt://{FOLDER_ID}/{GPT_MODEL}/latest",
                "completionOptions": {
                    "stream": False,
                    "temperature": 0.6,
                    "maxTokens": MAX_TOKENS
                },
                "messages": [
                    {"role": "system", "text": self.system_content[chat_id]},
                    {"role": "user", "text": user_request},
                    {"role": "assistant", "text": " "},
                ]
            }

            # Подсчитываем количество токенов в промте
            self.count_token_user[chat_id] = len(
                requests.post(url=TOKENIZER_URL, json=json, headers=HEADERS).json()['tokens'])

            return json
        except ValueError as e:
            logging.error(f"Ошибка: {e}. Невозможно сгенерировать промпт для нейросети")

    # Отправка запроса
    def send_request(self, json):
        resp = requests.post(url=self.URL, headers=self.HEADERS, json=json)
        return resp

    # Сохраняем историю общения
    def save_history(self, content_response, chat_id):
        try:
            self.assistant_content[chat_id] += content_response
            con = connect('db.db')
            cur = con.cursor()
            ai_history = cur.execute(f"select ai_history from users where chat_id = {str(chat_id)}").fetchone()[0]
            if ai_history is None:
                cur.execute(
                    f"update users set ai_history = '{self.assistant_content[chat_id]}' where chat_id = {str(chat_id)}")
                logging.debug("Обновление и сохранение ответов нейросети впервые")
            else:
                ai_history += self.assistant_content[chat_id]
                cur.execute(
                    f"update users set ai_history = '{self.assistant_content[chat_id]}' where chat_id = {str(chat_id)}")
                logging.debug("Обновление и сохранение ответов нейросети")
            con.commit()
            cur.close()
        except KeyError:
            logging.error(f"Ошибка: {KeyError}. Невозможно запомнить ответ от нейросети")
            self.assistant_content[chat_id] = content_response

    # Очистка истории общения
    def clear_history(self, chat_id):
        try:
            del self.assistant_content[chat_id]
            con = connect("db.db")
            cur = con.cursor()
            cur.execute(f"update users set status = 'answer_question', request = '', ai_history = ' ' "
                        f"where chat_id = {chat_id}")
            logging.debug(f"Инициализация пустого assistant_content пользователя {chat_id}")
            con.commit()
            cur.close()
        except ValueError as e:
            logging.error(f"Ошибка удаления базы данных")

    def response_id(self, chat_id, user_history):
        self.assistant_content[chat_id] = user_history
