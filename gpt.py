from sqlite3 import connect
import requests
import logging
from transformers import AutoTokenizer
from config import MAX_TOKENS, ERROR_LOG_FILE, HEADERS, GPT_LOCAL_URL

# Настройка логгера
logging.basicConfig(filename=ERROR_LOG_FILE, level=logging.ERROR)


class GPT:
    def __init__(self):
        self.system_content = {}
        self.URL = GPT_LOCAL_URL
        self.HEADERS = HEADERS
        self.MAX_TOKENS = MAX_TOKENS
        self.assistant_content = {}

    # Подсчитываем количество токенов в промте
    @staticmethod
    def count_tokens(prompt):
        tokenizer = AutoTokenizer.from_pretrained("TheBloke/Mistral-7B-Instruct-v0.1-GGUF")  # название модели
        return len(tokenizer.encode(prompt))

    # Проверка ответа на возможные ошибки и его обработка
    def process_resp(self, response, chat_id) -> [bool, str]:
        # Проверка статус кода
        if response.status_code < 200 or response.status_code >= 300:
            logging.error(f"Ошибка: {response.status_code}")
            self.clear_history(chat_id)
            return False, f"Ошибка: {response.status_code}"

        # Проверка json
        try:
            full_response = response.json()
        except:
            logging.error("Ошибка получения JSON")
            self.clear_history(chat_id)
            return False, "Ошибка получения JSON"

        # Проверка сообщения об ошибке
        if "error" in full_response or 'choices' not in full_response:
            logging.error(f"Ошибка: {full_response}")
            self.clear_history(chat_id)
            return False, f"Ошибка: {full_response}"

        # Результат
        result = full_response['choices'][0]['message']['content']

        # Сохраняем сообщение в историю
        self.save_history(result, chat_id)
        return True, self.assistant_content[chat_id]

    # Формирование промта
    def make_promt(self, chat_id):
        try:
            con = connect("db.db")
            cur = con.cursor()
            user_request = cur.execute(f"select request from users where chat_id = {str(chat_id)}").fetchone()
            cur.close()
            if user_request is None:
                user_request = " "
            json = {
                "messages": [
                    {"role": "system", "content": self.system_content[chat_id]},
                    {"role": "user", "content": user_request[0]},
                    {"role": "assistant", "content": self.assistant_content[chat_id]},
                ],
                "temperature": 0.9,
                "max_tokens": self.MAX_TOKENS,
            }
            return json
        except ValueError as e:
            logging.error(f"Ошибка: {e}. Невозможно сгенерировать промт для нейросети")

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
                logging.debug("Обновление и сохранение оветов нейросети впервые")
            else:
                ai_history += self.assistant_content[chat_id]
                cur.execute(
                    f"update users set ai_history = '{self.assistant_content[chat_id]}' where chat_id = {str(chat_id)}")
                logging.debug("Обновление и сохранение оветов нейросети")
            con.commit()
            cur.close()
        except KeyError:
            logging.error(f"Ошибка: {KeyError}. Невозможно запомнить ответ от нейросети")
            self.assistant_content[chat_id] = content_response

    # Очистка истории общения
    def clear_history(self, chat_id):
        del self.assistant_content[chat_id]
        con = connect("db.db")
        cur = con.cursor()
        cur.execute(f"update users set ai_history = ' ' where chat_id = {str(chat_id)}")
        logging.debug("Инициализация пустого assistant_content для нового пользователя")
        con.commit()
        cur.close()

    def response_id(self, chat_id, user_history):
        self.assistant_content[chat_id] = user_history
