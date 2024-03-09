import requests
import logging
from transformers import AutoTokenizer
from config import MAX_TOKENS, ERROR_LOG_FILE, HEADERS, GPT_LOCAL_URL

# Настройка логгера
logging.basicConfig(filename=ERROR_LOG_FILE, level=logging.ERROR)


class GPT:
    def __init__(self, system_content):
        self.system_content = system_content
        self.URL = GPT_LOCAL_URL
        self.HEADERS = HEADERS
        self.MAX_TOKENS = MAX_TOKENS
        self.chat_id = None
        self.assistant_content = {}

    # Подсчитываем количество токенов в промте
    @staticmethod
    def count_tokens(prompt):
        tokenizer = AutoTokenizer.from_pretrained("TheBloke/Mistral-7B-Instruct-v0.1-GGUF")  # название модели
        return len(tokenizer.encode(prompt))

    # Проверка ответа на возможные ошибки и его обработка
    def process_resp(self, response) -> [bool, str]:
        # Проверка статус кода
        if response.status_code < 200 or response.status_code >= 300:
            logging.error(f"Ошибка: {response.status_code}")
            self.clear_history()
            return False, f"Ошибка: {response.status_code}"

        # Проверка json
        try:
            full_response = response.json()
        except:
            logging.error("Ошибка получения JSON")
            self.clear_history()
            return False, "Ошибка получения JSON"

        # Проверка сообщения об ошибке
        if "error" in full_response or 'choices' not in full_response:
            logging.error(f"Ошибка: {full_response}")
            self.clear_history()
            return False, f"Ошибка: {full_response}"

        # Результат
        result = full_response['choices'][0]['message']['content']

        # Сохраняем сообщение в историю
        self.save_history(result)
        return True, self.assistant_content[self.chat_id]

    # Формирование промта
    def make_promt(self, user_request):
        json = {
            "messages": [
                {"role": "system", "content": self.system_content},
                {"role": "user", "content": user_request},
                {"role": "assistant", "content": self.assistant_content[self.chat_id]},
            ],
            "temperature": 0.9,
            "max_tokens": self.MAX_TOKENS,
        }
        return json

    # Отправка запроса
    def send_request(self, json):
        resp = requests.post(url=self.URL, headers=self.HEADERS, json=json)
        return resp

    # Сохраняем историю общения
    def save_history(self, content_response):
        try:
            self.assistant_content[self.chat_id] += content_response
        except KeyError:
            logging.error(f"Ошибка: {KeyError}. Невозможно запомнить ответ от нейросети")
            self.assistant_content[self.chat_id] = content_response

    # Очистка истории общения
    def clear_history(self):
        self.assistant_content = {}

    def response_id(self, chat_id):
        if chat_id not in self.assistant_content:
            self.assistant_content[chat_id] = " "
        self.chat_id = chat_id