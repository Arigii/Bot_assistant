import telebot
import json
import logging
from gpt import GPT
from config import TOKEN, system_content

# Путь к файлу с состояниями пользователей
USERS_STATE_FILE = 'users_state.json'

# Путь к файлу с логами ошибок
ERROR_LOG_FILE = 'error.log'

# Создание экземпляра бота
bot = telebot.TeleBot(TOKEN)

# Создание экземпляра класса GPT для взаимодействия с API GPT
gpt_model = GPT(system_content)

# Настройка логгера
logging.basicConfig(filename=ERROR_LOG_FILE, level=logging.ERROR)


# Функция для загрузки состояний пользователей из файла JSON
def load_users_state():
    try:
        with open(USERS_STATE_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


# Функция для сохранения состояний пользователей в файл JSON
def save_users_state(state_users):
    print(state_users)
    # Сохраняем обновленные состояния в файл
    with open(USERS_STATE_FILE, 'w') as file:
        file.write(json.dumps(state_users))


# Функция для создания клавиатуры
def create_keyboard(buttons_list):
    keyboard = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(*buttons_list)
    return keyboard


# Обработчик команды /debug
@bot.message_handler(commands=['debug'])
def handle_debug(message):
    # Отправляем файл с логами ошибок
    with open(ERROR_LOG_FILE, 'rb') as file:
        bot.send_document(message.chat.id, file)


# Обработчик для команд /start, /help, /exit
@bot.message_handler(commands=['start', 'help', 'exit'])
def handle_commands(message):
    command = message.text[1:]  # Удаление символа "/"
    # Запоминание ответа пользователя в словарь нейросети
    gpt_model.response_id(message.chat.id)
    if command == 'start':
        user_name = message.from_user.first_name
        bot.send_message(message.chat.id,
                         f"Привет, {user_name}! Я бот-помощник описанию музыки. "
                         "Напиши мне жанр, группу или трек, который тебе нравится, и я дам тебе рекомендацию.",
                         reply_markup=create_keyboard(["/do", '/help']))
    elif command == 'help':
        bot.send_message(message.from_user.id,
                         text="Привет! Я виртуальный помощник для описания той или иной музыки. Команды /do для "
                              "начала запроса, /exit для очищения истории\n"
                              "Вот моя ссылка в телеграм для сообщения ошибок - https://t.me/Remminders \n"
                              "Вот репозиторий этого бота https://github.com/Arigii/Bot_assistant.git \n"
                              "Создан с помощью инструментария LM Studio",
                         reply_markup=create_keyboard(["/do", '/exit']))
    elif command == 'exit':
        chat_id = message.chat.id
        keyboard = create_keyboard(["Да", "Нет"])
        bot.send_message(str(chat_id), "Вы действительно хотите очистить всю историю? (Да/Нет)",
                         reply_markup=keyboard)
        bot.register_next_step_handler(message, process_exit)


def process_exit(message):
    chat_id = message.chat.id
    if message.text == "Да":
        bot.send_message(str(chat_id), "Хорошо! Ваша история посещения очищена.")
        users_state[str(chat_id)] = " "
        save_users_state(users_state)
        gpt_model.clear_history()
    elif message.text == "Нет":
        bot.send_message(str(chat_id), "Хорошо! Для того, чтобы отправить запрос, напиши команду /do")
    else:
        bot.send_message(str(chat_id), "Воспользуйтесь, пожалуйста, кнопками")


# Функция для смены состояния
def status_update(message):
    chat_id = message.chat.id
    users_state[str(chat_id)] = "answer_question"
    save_users_state(users_state)
    bot.register_next_step_handler(message, handle_user_input)


# Обработчик нажатия кнопки "Продолжить решение"
def handle_continue_solution(message):
    chat_id = message.chat.id
    bot.send_message(str(chat_id), "Придётся еще немного подождать ;)")
    # Формирование промта для продолжения ответа на основе предыдущего ответа
    prompt = gpt_model.make_promt("Продолжи ответ")
    try:
        response = gpt_model.send_request(prompt)
        success, assistant_response = gpt_model.process_resp(response)
        if success:
            bot.send_message(str(chat_id), assistant_response)
            bot.register_next_step_handler(message, interceptor)
        else:
            bot.send_message(str(chat_id), "Произошла ошибка. Пожалуйста, попробуйте еще раз.")
            logging.error("Ошибка при обработке текста: Ошибка продолжения ответа")
            bot.register_next_step_handler(message, handle_continue_solution)

    except Exception as e:
        bot.send_message(str(chat_id), f"Произошла ошибка: {e}")
        logging.error(f"Ошибка при обработке текста: {e}")


# Обработчик нажатия кнопки "Завершить решение"
def handle_end_solution(message):
    chat_id = message.chat.id
    bot.send_message(str(chat_id), "Хорошо, если у тебя возникнут еще вопросы по музыке, обращайся!")
    # Очистка истории ответов бота
    gpt_model.clear_history()
    users_state[str(chat_id)] = "answer_question"
    save_users_state(users_state)


# Перехват пользователя по состоянию
def interceptor(message):
    chat_id = message.chat.id
    try:
        if users_state[str(chat_id)] == "continue_solution":
            if message.text == "Продолжить решение":
                handle_continue_solution(message)
            elif message.text == "Завершить решение":
                handle_end_solution(message)
            else:
                # Режим продолжения объяснения
                bot.send_message(str(chat_id),
                                 "Чтобы продолжить решение, нажмите кнопку 'Продолжить решение' или 'Завершить решение'.")
                bot.register_next_step_handler(message, interceptor)
        else:
            # Неопознанный режим, возвращаем пользователя к начальному состоянию
            bot.send_message(str(chat_id), "Произошла ошибка, попробуйте еще раз написать задачу")
            users_state[str(chat_id)] = "answer_question"
            save_users_state(users_state)
            bot.register_next_step_handler(message, handle_do_command)
    except Exception as e:
        bot.send_message(str(chat_id), f"Произошла ошибка: {e}")
        logging.error(f"Ошибка при перенаправлении пользователя: {e}")


# Обработчик команды /do
@bot.message_handler(commands=['do'])
def handle_do_command(message):
    user_name = message.from_user.first_name
    chat_id = message.chat.id
    # Запоминание ответа пользователя в словарь нейросети
    gpt_model.response_id(str(chat_id))

    if str(message.chat.id) not in users_state:
        bot.send_message(str(chat_id),
                         f"Первое знакомство, {user_name}! Введи, пожалуйста, свой вопрос или что бы ты хотел узнать.")
        # Инициализация состояния пользователя
        users_state[str(chat_id)] = "answer_question"
        save_users_state(users_state)
    elif users_state[str(chat_id)] == "answer_question":
        bot.send_message(str(chat_id),
                         f"Здравствуй снова, {user_name}. Введи, пожалуйста, свой вопрос или что бы ты хотел узнать.")
    else:
        bot.send_message(str(chat_id),
                         f"Первое знакомство, {user_name}! Введи, пожалуйста, свой вопрос или что бы ты хотел узнать.")
        # Инициализация состояния пользователя
        users_state[str(chat_id)] = "answer_question"
        save_users_state(users_state)

    # Переключаем состояние пользователя на ожидание ввода текста
    bot.register_next_step_handler(message, handle_user_input)


# Хэндлер для незнакомого пользователя
@bot.message_handler()
def catch_unknown(message):
    chat_id = message.chat.id
    # Запоминание ответа пользователя в словарь нейросети
    gpt_model.response_id(str(chat_id))
    try:
        if str(message.chat.id) not in users_state:
            bot.send_message(str(chat_id), "Ошибка! Вы не начинали решение задачи. Начните с команды /do")
        else:
            if users_state[str(chat_id)] == "answer_question":
                bot.send_message(str(chat_id), "Ошибка! Попробуйте написать задачу (просто запрос в чат)")
            else:
                bot.send_message(str(chat_id), "Воспользуйтесь командой /do или /help")
    except Exception as e:
        bot.send_message(str(chat_id), "Ошибка! свяжусь с создателем, а пока отправьте новый запрос >:^")
        logging.error(f"Ошибка поимки неизвестного пользователя: {e}. Присвоение статуса активного")
        status_update(message)


# Обработчик ввода текста после команды /do
def handle_user_input(message):

    if message.text == "/start" or message.text == "/help" or message.text == "/exit":
        handle_commands(message)
        return
    elif message.text == "/do":
        handle_do_command(message)
        return
    # Проверка токенов не работает с моей моделью
    """count = gpt_model.count_tokens(message)
    if count < gpt_model.MAX_TOKENS:
        bot.reply_to(message,"Запрос превышает кол-во допустимых символов. Напишите его заново")
        bot.register_next_step_handler(message, handle_user_input)"""
    chat_id = message.chat.id
    # Режим ответа на вопрос пользователя
    user_request = message.text
    # Формирование промта для GPT
    prompt = gpt_model.make_promt(user_request)
    bot.send_message(str(chat_id), "Подождите, пока сформируется запрос. Это не займет много времени.")

    try:
        # Отправка запроса на API GPT
        response = gpt_model.send_request(prompt)

        # Проверка ответа на ошибки
        success, assistant_response = gpt_model.process_resp(response)

        if success:
            # Отправка ответа пользователю
            bot.send_message(str(chat_id), assistant_response)
            # Переключение состояния пользователя
            users_state[str(chat_id)] = "continue_solution"
            save_users_state(users_state)
            # Отправка кнопок для продолжения или завершения решения
            keyboard = create_keyboard(["Продолжить решение", "Завершить решение"])
            bot.send_message(str(chat_id), "Выберите действие:", reply_markup=keyboard)
            bot.register_next_step_handler(message, interceptor)
        else:
            bot.send_message(str(chat_id), "Произошла ошибка. Пожалуйста, попробуйте еще раз.")
            logging.error(f"Ошибка при обработке текста")
    except Exception as e:
        bot.send_message(str(chat_id), f"Произошла ошибка: {e}")
        logging.error(f"Ошибка при обработке текста: {e}")


if __name__ == "__main__":
    # Загрузка состояний пользователей
    users_state = load_users_state()
    # Запуск бота
    bot.polling(none_stop=True)
