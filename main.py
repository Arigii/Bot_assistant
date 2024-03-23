import telebot
import logging
from telebot import types
from gpt import GPT
from config import TOKEN, ERROR_LOG_FILE
from db_create import *

# Создание экземпляра бота
bot = telebot.TeleBot(TOKEN)

# Создание экземпляра класса GPT для взаимодействия с API GPT
gpt_model = GPT()

# Настройка логгера
logging.basicConfig(filename=ERROR_LOG_FILE, level=logging.DEBUG)


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
    chat_id = message.chat.id

    # Запоминание пользователя и применение пустого assistant в словарь нейросети
    con = connect('db.db')
    cur = con.cursor()
    user_history = cur.execute(f'select ai_history from users where chat_id  = {chat_id}').fetchone()
    if user_history is None:
        user_history = " "
    user_history = user_history[0]
    gpt_model.response_id(message.chat.id, user_history)

    if command == 'start':
        user_name = message.from_user.first_name
        bot.send_message(message.chat.id,
                         f"Привет, {user_name}! Я бот-помощник описанию музыки. "
                         "Напиши мне жанр, группу или трек, который тебе нравится, и я дам тебе рекомендацию.",
                         reply_markup=create_keyboard(["/do", '/help', '/settings']))
    elif command == 'help':
        bot.send_message(message.from_user.id,
                         text="Привет! Я виртуальный помощник для описания той или иной музыки. Команды /do для "
                              "начала запроса, /exit для очищения истории, /settings для изменения конфигурации бота"
                              "(выбор жанра и уровня ответа)\n"
                              "Вот моя ссылка в телеграм для сообщения ошибок - https://t.me/Remminders \n"
                              "Вот репозиторий этого бота https://github.com/Arigii/Bot_assistant.git \n"
                              "Создан с помощью инструментария LM Studio",
                         reply_markup=create_keyboard(["/do", '/exit', '/settings']))
    elif command == 'exit':
        chat_id = message.chat.id
        bot.send_message(chat_id, "Вы действительно хотите очистить всю историю? (Да/Нет)",
                         reply_markup=create_keyboard(["Да", "Нет"]))
        bot.register_next_step_handler(message, process_exit)


def process_exit(message):
    chat_id = message.chat.id
    try:
        if message.text == "Да":
            # Очистка к базе и удаление целого поля, связанного с пользователем
            con = connect('db.db')
            cur = con.cursor()
            cur.execute(f"delete from users where chat_id = {chat_id}")
            cur.close()
            gpt_model.clear_history(chat_id)
            logging.debug(f"Очистка памяти у пользователя: {chat_id}")
            bot.send_message(chat_id, "Хорошо! Ваша история посещения очищена.",
                             reply_markup=types.ReplyKeyboardRemove())
        elif message.text == "Нет":
            bot.send_message(chat_id, "Хорошо! Для того, чтобы отправить запрос, напиши команду /do",
                             reply_markup=create_keyboard(["/do"]))
        else:
            bot.send_message(chat_id, "Воспользуйтесь, пожалуйста, кнопками")
    except ValueError as e:
        bot.reply_to(message, "Произошла ошибка очищения памяти. Попробуйте позже или напишите создателю.")
        logging.error(f"Ошибка удаления памяти у пользователя: {chat_id}. Ошибка: {e}")


@bot.message_handler(commands=['settings'])
def items_change(message):
    chat_id = message.chat.id

    # Запоминание пользователя и применение пустого assistant в словарь нейросети,
    # если пользователь не использовал /start
    con = connect('db.db')
    cur = con.cursor()
    user_history = cur.execute(f'select ai_history from users where chat_id  = {chat_id}').fetchone()
    user_history = user_history[0]
    if user_history is None:
        user_history = " "
    gpt_model.response_id(message.chat.id, user_history)

    # Выводим список жанров из базы данных
    genres = [" "]
    try:
        con = connect('db.db')
        cur = con.cursor()
        genres = list(map(lambda x: x[0], cur.execute("select name from genres").fetchall()))
        cur.close()
        # Запрашиваем у пользователя выбор жанра
        bot.send_message(chat_id, "Выберите из списка жанров:\n" + "\n".join(genres),
                         reply_markup=create_keyboard(genres))
    except ValueError as e:
        bot.reply_to(message, "Произошла выдачи списка жанра. Попробуйте позже")
        logging.error(f"Невозможно считать жанры из таблицы. Ошибка: {e}")

    bot.register_next_step_handler(message, catching_an_genres, genres)


def catching_an_genres(message, genres):
    chat_id = message.chat.id
    # Проверяем правильность выбора и присваиваем выбранный жанр, делаем проверку на наличие пользователя
    try:
        try:
            if message.text not in genres:
                bot.reply_to(message, "Воспользуйтесь кнопочками")
                bot.register_next_step_handler(message, catching_an_genres, genres)
            con = connect('db.db')
            cur = con.cursor()
            genre_id = cur.execute(f"select id from genres where name = '{message.text}'").fetchone()[0]
            user = cur.execute(f"select * from users where chat_id = {chat_id}").fetchone()
            if user is not None:
                cur.execute(f"update users set genre_id = {str(genre_id)} where chat_id = {chat_id}")
                logging.debug(f"Обновление жанра у пользователя: {chat_id}")
            else:
                con.execute(f"insert into users (chat_id, genre_id) values ({chat_id}, {str(genre_id)})")
                logging.debug(f"Добавление пользователя: {chat_id} и присвоение жанра ему")
            con.commit()
            cur.close()
            bot.reply_to(message, "Успешно присвоен жанр")
        except ValueError as ex:
            bot.reply_to(message, "Произошла ошибка выбора жанра. Попробуйте позже")
            logging.error(f"Ошибка при присвоения жанра: {ex}")
        # Выводим список уровней
        con = connect('db.db')
        cur = con.cursor()
        levels = list(map(lambda x: x[0], cur.execute("select name from levels").fetchall()))
        cur.close()
        bot.send_message(chat_id, "Выберите из списка уровней:\n" + "\n".join(levels),
                         reply_markup=create_keyboard(levels))
        bot.register_next_step_handler(message, catching_an_levels, levels)
    except ValueError as e:
        bot.reply_to(message, "Произошла ошибка выбора уровня. Попробуйте позже")
        logging.error(f"Ошибка при присвоения уровня: {e}")


def catching_an_levels(message, levels):
    chat_id = message.chat.id
    # Проверяем правильность выбора и присваиваем выбранный уровень, делаем проверку на наличие пользователя
    try:
        if message.text not in levels:
            bot.reply_to(message, "Воспользуйтесь кнопочками")
            bot.register_next_step_handler(message, catching_an_levels, levels)
        con = connect('db.db')
        cur = con.cursor()
        level_id = cur.execute(f"select id from levels where name = '{message.text}'").fetchone()[0]
        user = cur.execute(f"select * from users where chat_id = {chat_id}").fetchone()
        if user is not None:
            cur.execute(f"update users set level_id = {str(level_id)} where chat_id = {chat_id}")
            logging.debug(f"Обновление уровня у пользователя: {chat_id}")
        else:
            con.execute(f"insert into users (chat_id, level_id) values ({chat_id}, {str(level_id)})")
            logging.debug(f"Добавление пользователя: {chat_id} и присвоение уровня ему")
        con.commit()
        cur.close()
        bot.send_message(chat_id, "Успешно присвоен уровень. Теперь можете воспользоваться командой"
                                  " /do", reply_markup=types.ReplyKeyboardRemove())
    except ValueError as e:
        bot.reply_to(message, "Произошла ошибка выбора уровня. Попробуйте позже")
        logging.error(f"Ошибка при присвоения уровня: {e}")


# Обработчик нажатия кнопки "Продолжить решение"
def handle_continue_solution(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Придётся еще немного подождать ;)")
    # Формирование промта для продолжения ответа на основе предыдущего ответа
    prompt = gpt_model.make_promt(chat_id)
    try:
        response = gpt_model.send_request(prompt)
        success, assistant_response = gpt_model.process_resp(response, chat_id)
        if success:
            bot.send_message(chat_id, assistant_response)
            logging.debug("Успешная генерация продолжение. Возвращения пользователя в interceptor")
            bot.register_next_step_handler(message, interceptor)
        else:
            bot.send_message(chat_id, "Произошла ошибка. Пожалуйста, попробуйте написать запрос заново.")
            logging.error("Ошибка продолжения ответа. Возвращение в исходное состояние")
            bot.register_next_step_handler(message, handle_user_input)
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка. Попробуйте в следующий раз.")
        logging.error(f"Ошибка при продолжении текста: {e}")


# Обработчик нажатия кнопки "Завершить решение"
def handle_end_solution(message):
    chat_id = message.chat.id
    try:
        bot.send_message(chat_id, "Хорошо, если у тебя возникнут еще вопросы по музыке, обращайся!",
                         reply_markup=types.ReplyKeyboardRemove())
        # Очистка истории ответов бота
        gpt_model.clear_history(chat_id)
        con = connect("db.db")
        cur = con.cursor()
        cur.execute(f"update users set status = 'answer_question' where chat_id = {chat_id}")
        con.commit()
        cur.close()
        logging.debug(f"Очистка пользователя {chat_id} успешна")
    except ValueError as e:
        bot.reply_to(message, "Произошла ошибка завершения. Попробуйте написать новый запрос.")
        logging.error(f"Очистка пользователя {chat_id} безуспешна. Переход в изначальное состояние. Ошибка: {e}")
        bot.register_next_step_handler(message, handle_user_input)


# Перехват пользователя по состоянию
def interceptor(message):
    chat_id = message.chat.id
    try:
        con = connect("db.db")
        cur = con.cursor()
        users_status = cur.execute(f"select status from users where chat_id = {chat_id}").fetchone()[0]
        cur.close()
        if users_status == "continue_solution":
            if message.text == "Продолжить решение":
                logging.debug(f"Переход пользователя {chat_id} в состояние продолжения ответа")
                handle_continue_solution(message)
            elif message.text == "Завершить решение":
                logging.debug(f"Переход пользователя {chat_id} в состояние окончания ответа")
                handle_end_solution(message)
            else:
                # Режим продолжения объяснения
                bot.send_message(chat_id,
                                 "Чтобы продолжить решение, нажмите кнопку 'Продолжить решение' "
                                 "или 'Завершить решение'.")
                bot.register_next_step_handler(message, interceptor)
        else:
            # Неопознанный режим, возвращаем пользователя к начальному состоянию
            bot.send_message(chat_id, "Произошла ошибка, попробуйте еще раз написать задачу")
            cur = con.cursor()
            cur.execute(f"update users set status = answer_question where chat_id = {chat_id}")
            con.commit()
            cur.close()
            logging.debug(f"Переход пользователя {chat_id} в исходное состояние из-за неизвестного статуса")
            bot.register_next_step_handler(message, handle_user_input)
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")
        logging.error(f"Ошибка при перенаправлении пользователя: {e}")


# Обработчик команды /do
@bot.message_handler(commands=['do'])
def handle_do_command(message):
    user_name = message.from_user.first_name
    chat_id = message.chat.id
    # Присвоение статуса пользователю и переход в обработку запроса
    con = connect('db.db')
    cur = con.cursor()
    user_status = cur.execute(
        f"select 1 from users where status = 'answer_question' and chat_id = {chat_id}").fetchone()
    user = cur.execute(f"select * from users where chat_id = {chat_id}").fetchone()

    # Проверка на наличие выбранных настроек у пользователя
    if user_status is not None:
        bot.send_message(chat_id,
                         f"Здравствуй снова, {user_name}. Введи, пожалуйста, свой вопрос или что бы ты хотел узнать."
                         f" Введи команду /settings, чтобы ты смог написать вопрос боту.",
                         reply_markup=create_keyboard(["/settings"]))
    else:
        bot.send_message(chat_id,
                         f"Первое знакомство, {user_name}! Введи, пожалуйста, свой вопрос или что бы ты хотел узнать."
                         f" Введи команду /settings, чтобы ты смог написать вопрос боту",
                         reply_markup=create_keyboard(["/settings"]))
        # Инициализация состояния пользователя
        if user is None:
            cur.execute(f"insert into users (chat_id, status) values ({chat_id},'answer_question')")
        else:
            cur.execute(f"update users set status = 'answer_question' where chat_id = {chat_id}")
            logging.error("Неизвестное состояние пользователя. Присвоение статуса активного")
    con.commit()
    cur.close()

    # Переключаем состояние пользователя на ожидание ввода текста
    bot.register_next_step_handler(message, handle_user_input)


# Хэндлер для незнакомого пользователя
@bot.message_handler()
def catch_unknown(message):
    chat_id = message.chat.id
    # Поимка знакомого или незнакомого пользователя вне хэндлеров
    try:
        con = connect('db.db')
        cur = con.cursor()
        user = cur.execute(f"select * from users where chat_id = {chat_id}").fetchone()
        user_status = cur.execute(
            f"select 1 from users where status = 'answer_question' and chat_id = {chat_id}").fetchone()
        if user is None:
            bot.send_message(chat_id, "Ошибка! Вы не начинали решение задачи. Начните с команды /do",
                             reply_markup=create_keyboard(["/do"]))
            cur.execute(f"insert into users (chat_id) values ({chat_id})")
            user_history = " "
            gpt_model.response_id(message.chat.id, user_history)
            con.commit()
            cur.close()
        elif user_status is None:
            bot.send_message(chat_id, "Ошибка! Попробуйте написать задачу (просто запрос в чат)")
            cur.close()
            user_history = " "
            gpt_model.response_id(message.chat.id, user_history)
            bot.register_next_step_handler(message, handle_user_input)
        else:
            cur.close()
            bot.send_message(chat_id, "Воспользуйтесь командой /do или /help",
                             reply_markup=create_keyboard(["/do", "/settings"]))
    except Exception as e:
        bot.send_message(chat_id, "Ошибка! свяжусь с создателем, а пока отправьте новый запрос >:^",
                         reply_markup=types.ReplyKeyboardRemove())
        logging.error(f"Ошибка поимки неизвестного пользователя: {e}. Присвоение статуса активного")


# Обработчик ввода текста после команды /do
def handle_user_input(message):
    chat_id = message.chat.id
    # Проверка на команды хэндлеров
    if message.text == "/start" or message.text == "/help" or message.text == "/exit":
        handle_commands(message)
        return
    elif message.text == "/do":
        handle_do_command(message)
        return
    elif message.text == "/settings":
        items_change(message)
        return
    try:
        con = connect('db.db')
        cur = con.cursor()
        setting = cur.execute(f"select l.name, g.name from levels l join users u on u.level_id = l.id "
                              f"join genres g on g.id = u.genre_id"
                              f" where u.chat_id = {chat_id}").fetchone()
        cur.close()

        # Проверка параметров бота у пользователя и перенаправление на функцию по их инициализации
        if setting is None:
            bot.reply_to(message, "У вас не выбраны настройки для бота. Вывожу список жанров и уровень ответа (●'◡'●)")
            logging.debug(f"Переход на settings, ибо у пользователя {chat_id} они не выбраны")
            items_change(message)
            return
    except ValueError as a:
        logging.error(f"Ошибка просмотра уровня и жанра из таблицы пользователя {chat_id}. Ошибка: {a}")
        bot.reply_to(message, "Произошла ошибка генерации запроса, попробуйте позже")
        return

    # Генерация системного контента, исходя из параметров пользователя для нейросети
    gpt_model.system_content[chat_id] = (f"Ты — дружелюбный помощник для описания музыкальных групп и музыки в целом. "
                                         f"Дай подробный ответ с решением на русском языке по жанру: "
                                         f"{setting[1].lower()}. "
                                         f"Уровень сложности должен быть: {setting[0].lower()}")
    logging.debug(f"Передача системного контента у пользователя: {chat_id}")

    # Проверка токенов не работает с моей моделью
    """count = gpt_model.count_tokens(message)
    if count < gpt_model.MAX_TOKENS:
        bot.reply_to(message, "Запрос превышает кол-во допустимых символов. Напишите его заново",
                     reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, handle_user_input)
        return"""

    # Проверка предыдущих ответов у нейросети
    user_request = message.text
    cur = con.cursor()
    cur.execute(f"update users set request = '{user_request}' where chat_id = {chat_id}")
    logging.debug(f"Обновление промта от пользователя {chat_id}")
    user_history = cur.execute(f'select ai_history from users where chat_id  = {chat_id}').fetchone()
    con.commit()
    cur.close()
    user_history = user_history[0]
    if user_history is None:
        user_history = " "
    gpt_model.response_id(message.chat.id, user_history)

    # Формирование промта для GPT
    prompt = gpt_model.make_promt(chat_id)
    bot.send_message(chat_id, "Подождите, пока сформируется запрос. Это не займет много времени.",
                     reply_markup=types.ReplyKeyboardRemove())
    try:
        # Отправка запроса на API GPT
        response = gpt_model.send_request(prompt)

        # Проверка ответа на ошибки
        success, assistant_response = gpt_model.process_resp(response, chat_id)

        if success:
            # Отправка ответа пользователю
            bot.send_message(chat_id, assistant_response)
            logging.debug("Успешная отправка ответа от нейросети")
            # Переключение состояния пользователя
            con = connect("db.db")
            cur = con.cursor()
            cur.execute(
                f"update users set status = 'continue_solution' where chat_id = {chat_id}")
            logging.debug("Запоминание ответа от нейросети")
            con.commit()
            cur.close()
            # Отправка кнопок для продолжения или завершения решения
            bot.send_message(chat_id, "Выберите действие:",
                             reply_markup=create_keyboard(["Продолжить решение", "Завершить решение"]))
            bot.register_next_step_handler(message, interceptor)
        else:
            bot.send_message(chat_id, "Произошла ошибка формирования запроса. Пожалуйста, попробуйте позже.")
            logging.error(f"Ошибка при обработке и отправке нейросети")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")
        logging.error(f"Ошибка при обработке текста: {e}")


if __name__ == "__main__":
    # Создание и импортирование бд
    create_database()
    insert_levels(LEVELS)
    insert_genres(GENRES)
    # Запуск бота
    bot.polling(none_stop=True)
