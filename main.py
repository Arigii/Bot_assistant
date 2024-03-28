import telebot
import logging
from telebot import types
from gpt import GPT
from config import TOKEN, ERROR_LOG_FILE, MAX_USERS, MAX_SESSION, MAX_TOKEN_USERS
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
                         f"Привет, {user_name}! Я бот-сценарист, связанный с музыкой. "
                         "Выбери жанр произведения, персонажа и сеттинг, который тебе нравится, "
                         "и я сделаю бесподобную историю!",
                         reply_markup=create_keyboard(["/do", '/help', '/settings', '/configuration']))
    elif command == 'help':
        bot.send_message(message.from_user.id,
                         text="Привет! Я виртуальный сценарист для генерации текста. Команды /do для "
                              "начала запроса, /exit для очищения истории, /settings для изменения конфигурации бота, "
                              "/configuration для просмотра оставшихся сессий и токенов\n"
                              "Вот моя ссылка в телеграм для сообщения ошибок - https://t.me/Remminders \n"
                              "Вот репозиторий этого бота https://github.com/Arigii/Bot_assistant.git \n"
                              "Создан с помощью инструментария GPTYandex",
                         reply_markup=create_keyboard(["/do", '/exit', '/settings', '/configuration']))
    elif command == 'exit':
        chat_id = message.chat.id
        bot.send_message(chat_id, "Вы действительно хотите очистить всю историю? (Да/Нет)",
                         reply_markup=create_keyboard(["Да", "Нет"]))
        bot.register_next_step_handler(message, process_exit)
        return


@bot.message_handler(commands=['configuration'])
def configuration(message):
    chat_id = message.chat.id
    try:
        con = connect('db.db')
        cur = con.cursor()
        user_existence = cur.execute(f"select 1 from users where chat_id = {chat_id}").fetchone()
        if user_existence is not None:
            user_con = cur.execute(f"select tokens_left, sessions_left from users where chat_id = {chat_id}").fetchone()
            if user_con[0] is not None:
                if user_con[1] <= 0:
                    bot.reply_to(message, f"У вас закончились сессии")
                    cur.close()
                    return [False]
                bot.reply_to(message, f"У вас осталось {str(user_con[0])} токенов и {str(user_con[1])} сессий")
                return [True, user_con[0], user_con[1]]
            cur.execute(f"update users set tokens_left = '{MAX_TOKEN_USERS}', "
                        f"sessions_left = '{MAX_SESSION}' where chat_id = {chat_id}")
            con.commit()
            cur.close()
            bot.reply_to(message, f"У вас осталось {MAX_TOKEN_USERS} токенов и {MAX_SESSION} сессий")
            return [True, MAX_TOKEN_USERS]
        cur.execute(f"insert into users (chat_id, tokens_left, sessions_left) "
                    f"values ({chat_id}, {MAX_TOKEN_USERS}, {MAX_SESSION})")
        con.commit()
        cur.close()
        bot.reply_to(message, "У вас осталось 400 токенов и 3 сессий")
    except ValueError as e:
        bot.send_message(chat_id, "Произошла ошибка подсчета сессий и токенов")
        logging.error(f"Ошибка {e} у пользователя {chat_id}")


def process_exit(message):
    chat_id = message.chat.id
    try:
        if message.text == "Да":
            # Очистка к базе и удаление целого поля, связанного с пользователем
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
    if user_history is None:
        user_history = " "
    user_history = user_history[0]
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
    return


def catching_an_genres(message, genres):
    chat_id = message.chat.id
    # Проверяем правильность выбора и присваиваем выбранный жанр, делаем проверку на наличие пользователя
    try:
        try:
            if message.text not in genres:
                bot.reply_to(message, "Воспользуйтесь кнопочками")
                bot.register_next_step_handler(message, catching_an_genres, genres)
                return
            con = connect('db.db')
            cur = con.cursor()
            genre_id = cur.execute(f"select id from genres where name = '{message.text}'").fetchone()[0]
            user = cur.execute(f"select 1 from users where chat_id = {chat_id}").fetchone()
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
        characters = list(map(lambda x: x[0], cur.execute("select name from characters").fetchall()))
        cur.close()
        bot.send_message(chat_id, "Выберите из списка персонажей:\n" + "\n".join(characters),
                         reply_markup=create_keyboard(characters))
        bot.register_next_step_handler(message, catching_an_levels, characters)
        return
    except ValueError as e:
        bot.reply_to(message, "Произошла ошибка вывода персонажа. Попробуйте позже")
        logging.error(f"Ошибка вывода персонажей: {e}")


def catching_an_levels(message, characters):
    chat_id = message.chat.id
    # Проверяем правильность выбора и присваиваем выбранный уровень, делаем проверку на наличие пользователя
    try:
        try:
            if message.text not in characters:
                bot.reply_to(message, "Воспользуйтесь кнопочками")
                bot.register_next_step_handler(message, catching_an_levels, characters)
                return
            con = connect('db.db')
            cur = con.cursor()
            character_id = cur.execute(f"select id from characters where name = '{message.text}'").fetchone()[0]
            user = cur.execute(f"select 1 from users where chat_id = {chat_id}").fetchone()
            if user is not None:
                cur.execute(f"update users set character_id = {str(character_id)} where chat_id = {chat_id}")
                logging.debug(f"Обновление персонажа у пользователя: {chat_id}")
            else:
                con.execute(f"insert into users (chat_id, character_id) values ({chat_id}, {str(character_id)})")
                logging.debug(f"Добавление пользователя: {chat_id} и присвоение персонажа ему")
            con.commit()
            cur.close()
            bot.send_message(chat_id, "Успешно присвоен персонаж.")
        except ValueError as a:
            bot.reply_to(message, "Произошла ошибка выбора персонажа. Попробуйте позже")
            logging.error(f"Ошибка при присвоения персонажа: {a}")
        con = connect('db.db')
        cur = con.cursor()
        settings = list(map(lambda x: x[0], cur.execute("select name from settings").fetchall()))
        cur.close()
        bot.send_message(chat_id, "Выберите из списка сеттингов:\n" + "\n".join(settings),
                         reply_markup=create_keyboard(settings))
        bot.register_next_step_handler(message, catching_an_setting, settings)
        return
    except ValueError as e:
        bot.reply_to(message, "Произошла ошибка вывода сеттинга. Попробуйте позже")
        logging.error(f"Ошибка вывода сеттингов: {e}")


def catching_an_setting(message, settings):
    chat_id = message.chat.id
    # Проверяем правильность выбора и присваиваем выбранный уровень, делаем проверку на наличие пользователя
    try:
        if message.text not in settings:
            bot.reply_to(message, "Воспользуйтесь кнопочками")
            bot.register_next_step_handler(message, catching_an_setting, settings)
            return
        con = connect('db.db')
        cur = con.cursor()
        setting_id = cur.execute(f"select id from settings where name = '{message.text}'").fetchone()[0]
        user = cur.execute(f"select 1 from users where chat_id = {chat_id}").fetchone()
        if user is not None:
            cur.execute(f"update users set setting_id = {str(setting_id)} where chat_id = {chat_id}")
            logging.debug(f"Обновление сеттинга у пользователя: {chat_id}")
        else:
            con.execute(f"insert into users (chat_id, character_id) values ({chat_id}, {str(setting_id)})")
            logging.debug(f"Добавление пользователя: {chat_id} и присвоение персонажа ему")
        con.commit()
        cur.close()
        bot.send_message(chat_id, "Успешно присвоен сеттинг. Теперь можете воспользоваться командой"
                                  " /do", reply_markup=types.ReplyKeyboardRemove())
    except ValueError as e:
        bot.reply_to(message, "Произошла ошибка выбора сеттинга. Попробуйте позже")
        logging.error(f"Ошибка при присвоения сеттинга: {e}")


def is_limit_users():
    try:
        con = connect('db.db')
        cur = con.cursor()
        count = cur.execute("SELECT count(status) FROM users where status = 'continue_solution'").fetchone()[0]
        return count >= MAX_USERS
    except ValueError as e:
        logging.error(f"Невозможно прочитать базу данных для подсчета кол-ва пользователей. Ошибка: {e}")


# Обработчик нажатия кнопки "Продолжить решение"
def handle_continue_solution(message):
    chat_id = message.chat.id
    user_request = message.text

    try:
        # Проверка и вывод токенов и сессий у пользователя
        user_con = configuration(message)
        if not user_con[0]:
            logging.debug(f"Вывод токенов и сессий у пользователя {chat_id}")
            return

        # Генерация системного контента, исходя из параметров пользователя для нейросети
        gpt_model.system_content[
            chat_id] = "Продолжай сюжет по 1-3 предложения, держи интригу. Не давай пояснительных сообщений"
        logging.debug(f"Передача системного контента у пользователя: {chat_id} для продолжения")

        # Проверка предыдущих ответов у нейросети
        con = connect("db.db")
        cur = con.cursor()
        cur.execute(f"update users set request = '{user_request}' where chat_id = {chat_id}")
        logging.debug(f"Обновление промта от пользователя {chat_id}")

        # Формирование промта для GPT
        prompt = gpt_model.make_promt(chat_id)
        is_big_prompt = gpt_model.count_token_user[chat_id] - MAX_TOKEN_USERS
        if is_big_prompt > 0:
            bot.reply_to(message, f"Превышен лимит токенов. Напиши начало поменьше на {is_big_prompt}")
            bot.register_next_step_handler(message, handle_user_input)
            return
        new_tokens = user_con[1] - gpt_model.count_token_user[chat_id]
        if new_tokens < -40:
            new_tokens = MAX_TOKEN_USERS
            new_sessions = user_con[2] - 1
            cur.execute(f"update users set status = 'answer_question', request = '', ai_history = ' ', "
                        f"tokens_left = '{new_tokens}', sessions_left = '{new_sessions}' where chat_id = {chat_id}")
            bot.send_message(chat_id, "Сессия завершена, токены кончились")
            con.commit()
            cur.close()
            del gpt_model.assistant_content[chat_id]
            return
        cur.execute(f"update users set tokens_left = '{new_tokens}' where chat_id = {chat_id}")
        con.commit()
        cur.close()

        # Отправка запроса на API GPT
        response = gpt_model.send_request(prompt)

        # Проверка ответа на ошибки
        success, assistant_response = gpt_model.process_resp(response, chat_id)
        print(3)

        if success:
            # Отправка ответа пользователю
            bot.send_message(chat_id, assistant_response)
            logging.debug("Успешная отправка продолжения от нейросети. Запоминание ответа от нейросети")
            # Отправка кнопок для продолжения или завершения решения
            bot.send_message(chat_id, "Выберите действие:",
                             reply_markup=create_keyboard(["Завершить решение"]))
            bot.register_next_step_handler(message, interceptor)
            return
        else:
            bot.send_message(chat_id, "Произошла ошибка формирования запроса. Пожалуйста, попробуйте позже.")
            logging.error(f"Ошибка при обработке и отправке нейросети")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")
        logging.error(f"Ошибка при обработке текста: {e}")


# Обработчик нажатия кнопки "Завершить решение"
def handle_end_solution(message):
    chat_id = message.chat.id
    try:
        bot.send_message(chat_id, "Хорошо, если у тебя возникнут еще вопросы по музыке, обращайся! Сессия завершена",
                         reply_markup=types.ReplyKeyboardRemove())
        # Очистка истории ответов бота
        gpt_model.clear_history(chat_id)
        con = connect("db.db")
        cur = con.cursor()
        user_con = cur.execute(f"select tokens_left, sessions_left from users where chat_id = {chat_id}").fetchone()
        new_tokens = MAX_TOKEN_USERS
        new_sessions = user_con[1] - 1
        cur.execute(f"update users set status = 'answer_question', request = '', ai_history = ' ', "
                    f"tokens_left = '{new_tokens}', sessions_left = '{new_sessions}' where chat_id = {chat_id}")
        con.commit()
        cur.close()
        logging.debug(f"Очистка пользователя {chat_id} успешна")
    except ValueError as e:
        bot.reply_to(message, "Произошла ошибка завершения. Попробуйте написать новый запрос.")
        logging.error(f"Очистка пользователя {chat_id} безуспешна. Переход в изначальное состояние. Ошибка: {e}")
        bot.register_next_step_handler(message, handle_user_input)
        return


# Перехват пользователя по состоянию
def interceptor(message):
    chat_id = message.chat.id
    try:
        con = connect("db.db")
        cur = con.cursor()
        users_status = cur.execute(f"select status from users where chat_id = {chat_id}").fetchone()[0]
        if users_status == "continue_solution":
            if message.text == "Завершить решение":
                logging.debug(f"Переход пользователя {chat_id} в состояние окончания ответа")
                cur.close()
                handle_end_solution(message)
                return
            else:
                # Режим продолжения объяснения
                logging.debug(f"Переход пользователя {chat_id} в состояние продолжения ответа")
                bot.send_message(chat_id, "Продолжение генерации...")
                cur.close()
                handle_continue_solution(message)
                return
        else:
            # Неопознанный режим, возвращаем пользователя к начальному состоянию
            logging.debug(f"Переход пользователя {chat_id} в исходное состояние из-за неизвестного статуса")
            bot.send_message(chat_id, "Произошла ошибка, попробуйте еще раз написать задачу")
            cur.execute(f"update users set status = answer_question where chat_id = {chat_id}")
            con.commit()
            cur.close()
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
                         f"Здравствуй снова, {user_name}. Введи, пожалуйста, начало истории."
                         f" Если хочешь изменить настройки, введи команду /settings, "
                         f"чтобы ты смог написать вопрос боту.",
                         reply_markup=create_keyboard(["/settings"]))
    else:
        bot.send_message(chat_id,
                         f"Первое знакомство, {user_name}! Введи, пожалуйста, начало истории."
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
    return


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
            bot.send_message(chat_id, "Ошибка! Вы не начинали историю. Начните с команды /do",
                             reply_markup=create_keyboard(["/do"]))
            cur.execute(f"insert into users (chat_id) values ({chat_id})")
            user_history = " "
            gpt_model.response_id(message.chat.id, user_history)
            con.commit()
            cur.close()
        elif user_status is None:
            bot.send_message(chat_id, "Ошибка! Попробуйте написать начало истории (просто запрос в чат)")
            cur.close()
            user_history = " "
            gpt_model.response_id(message.chat.id, user_history)
            bot.register_next_step_handler(message, handle_user_input)
            return
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
    elif message.text == "/configuration":
        configuration(message)
        return
    try:
        con = connect('db.db')
        cur = con.cursor()
        setting = cur.execute(
            f"select c.name, g.name, s.name from characters c join users u on u.character_id = c.id "
            f"join genres g on g.id = u.genre_id "
            f"join settings s on s.id = u.setting_id"
            f" where u.chat_id = {chat_id}").fetchone()
        cur.close()

        # Проверка параметров бота у пользователя и перенаправление на функцию по их инициализации
        if setting is None:
            bot.reply_to(message, "У вас не выбраны настройки для бота. Вывожу списки настроек (●'◡'●)")
            logging.debug(f"Переход на settings, ибо у пользователя {chat_id} они не выбраны")
            items_change(message)
            return
    except ValueError as a:
        logging.error(f"Ошибка просмотра настроек из таблицы пользователя {chat_id}. Ошибка: {a}")
        bot.reply_to(message, "Произошла ошибка генерации запроса, попробуйте позже")
        return

    # Подсчет пользователей, которые сейчас работают с нейросетью
    user_count = is_limit_users()
    if user_count:
        logging.debug("Заняты все доступные пользователи")
        bot.reply_to(message, "Бот сейчас недоступен, ибо много пользователей. Попробуйте чуть позже.")
        return

    # Проверка и вывод токенов и сессий у пользователя
    user_con = configuration(message)
    if not user_con[0]:
        return

    # Генерация системного контента, исходя из параметров пользователя для нейросети
    gpt_model.system_content[chat_id] = (f"\nНапиши начало истории в стиле {setting[1].lower()} "
                                         f"c главным героем {setting[0].lower()}. "
                                         f"Начальный сеттинг: \n{setting[2].lower()}. \n"
                                         "Начало должно быть коротким, 1-3 предложения. "
                                         "Не пиши никакие подсказки или пояснительные части")

    logging.debug(f"Передача системного контента у пользователя: {chat_id}")

    # Проверка предыдущих ответов у нейросети
    user_request = message.text
    cur = con.cursor()
    cur.execute(f"update users set request = '{user_request}' where chat_id = {chat_id}")
    logging.debug(f"Обновление промта от пользователя {chat_id}")
    user_history = cur.execute(f'select ai_history from users where chat_id  = {chat_id}').fetchone()
    con.commit()
    user_history = user_history[0]
    if user_history is None:
        user_history = " "
    gpt_model.response_id(message.chat.id, user_history)

    # Формирование промта для GPT
    prompt = gpt_model.make_promt(chat_id)
    is_big_prompt = gpt_model.count_token_user[chat_id] - MAX_TOKEN_USERS
    if is_big_prompt > 0:
        bot.reply_to(message, f"Превышен лимит токенов. Напиши начало поменьше на {is_big_prompt}")
        bot.register_next_step_handler(message, handle_user_input)
        return
    new_tokens = user_con[1] - gpt_model.count_token_user[chat_id]
    if new_tokens < 0:
        new_tokens = MAX_TOKEN_USERS
        new_sessions = user_con[2] - 1
        cur.execute(f"update users set status = 'answer_question', request = '', ai_history = ' ', "
                    f"tokens_left = '{new_tokens}', sessions_left = '{new_sessions}' where chat_id = {chat_id}")
        bot.send_message(chat_id, "Сессия завершена, токены кончились")
        con.commit()
        cur.close()
        del gpt_model.assistant_content[chat_id]
        return
    cur.execute(f"update users set tokens_left = '{new_tokens}' where chat_id = {chat_id}")
    con.commit()
    cur.close()

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
                             reply_markup=create_keyboard(["Завершить решение"]))
            bot.register_next_step_handler(message, interceptor)
            return
        else:
            bot.send_message(chat_id, "Произошла ошибка формирования запроса. Пожалуйста, попробуйте позже.")
            logging.error(f"Ошибка при обработке и отправке нейросети")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")
        logging.error(f"Ошибка при обработке текста: {e}")


if __name__ == "__main__":
    # Создание и импортирование бд
    create_database()
    insert_characters(CHARACTERS)
    insert_genres(GENRES)
    insert_settings(SETTINGS)
    # Запуск бота
    bot.polling(none_stop=True)
