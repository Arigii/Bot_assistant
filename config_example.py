GPT_LOCAL_URL = 'http://localhost:1234/v1/chat/completions'

HEADERS = {"Content-Type": "application/json"}

TOKEN = "some token"

MAX_TOKENS = 1

# Путь к файлу с состояниями пользователей
USERS_STATE_FILE = 'users_state.json'

# Путь к файлу с логами ошибок
ERROR_LOG_FILE = 'error.log'

# Путь к файлу с историей ответов
HISTORY_FILE = 'history.json'

system_content = "Ты — дружелюбный помощник для описания музыкальных и музыки в целом. Давай подробный ответ с решением на русском языке"