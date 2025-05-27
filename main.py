import telebot
import time
import random
import string
import os
import threading

from dotenv import load_dotenv
from functools import wraps

from businesses import BUSINESS_TYPES
from db_work import *

load_dotenv()

TOKEN = os.getenv('TOKEN')
bot = telebot.TeleBot(TOKEN)

active_games = {}

def check_level(user_id):
    user = get_user(user_id)
    required_exp = user['level'] * 1000
    if user['exp'] >= required_exp:
        update_user(user_id, {
            'level': user['level'] + 1,
            'exp': user['exp'] - required_exp
        })
        return True
    return False

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = """
Команды:
/work - Мини-игра для заработка
/crime - Рискованное преступление
/rob @ник - Ограбление игрока
/profile - Ваша статистика
/upgrade [сила/ловкость] - Улучшение характеристик
/top - Топ игроков
/business - Управление бизнесом
/buy_business - Покупка бизнеса
/sell_business - Продать бизнес (70% стоимости)
/buy_resources [кол-во] - Купить сырьё
/casino [сумма] - Игра в казино
    """
    get_user(message.from_user.id)
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['work'])
def start_work_game(message):
    if message.chat.type != "private":
        bot.reply_to(message, "Эта команда доступна только в личном чате!")
        return

    user_id = message.from_user.id
    user = get_user(user_id)
    
    if (remaining := 60 - (time.time() - user['last_work'])) > 0:
        bot.send_message(message.chat.id, f"Работать можно через {int(remaining//60)} мин {int(remaining%60)} сек")
        return
    
    sequence = ''.join(random.choices(string.ascii_uppercase, k=4))
    answer = ''.join(random.sample(sequence, 2))
    
    active_games[user_id] = {
        'start_time': time.time(),
        'sequence': sequence,
        'answer': answer,
        'attempts': 3
    }
    
    bot.send_message(message.chat.id, 
        f"Наберите буквы: {answer}\n"
        "У вас 10 секунд и 3 попытки!"
    )

@bot.message_handler(commands=['crime'])
def crime(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if (remaining := 90 - (time.time() - user['last_crime'])) > 0:
        bot.send_message(message.chat.id, f"Преступление доступно через {int(remaining//60)} мин {int(remaining%60)} сек")
        return
    
    if random.random() < 0.7:
        earned = random.randint(500, 1000)
        update_data = {
            'money': user['money'] + earned  + 25*get_user(user['user_id'])['level'],
            'exp': user['exp'] + earned // 10,
            'last_crime': time.time()
        }
        response = f"Преступление удалось! +{earned} руб"
    else:
        lost = random.randint(200, 500)
        update_data = {
            'money': max(0, user['money'] - lost),
            'last_crime': time.time()
        }
        response = f"Провал! Потеряно: {lost} руб"
    
    update_user(user_id, update_data)
    if check_level(user_id):
        response += f"\nНовый уровень: {get_user(user_id)['level']}"
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['rob'])
def rob(message):
    if message.chat.type != "private":
        bot.reply_to(message, "Эта команда доступна только в личном чате!")
        return
    attacker_id = message.chat.id
    attacker = get_user(attacker_id)
    
    if (remaining := 1200 - (time.time() - attacker['last_rob'])) > 0:
        bot.send_message(message.chat.id, f"Ограбление доступно через {int(remaining//60)} мин {int(remaining%60)} сек")
        return
    
    try: target_username = message.text.split()[1].lstrip('@')
    except:
        bot.send_message(message.chat.id, "Используйте: /rob @username")
        return
    
    target = execute_query(
        "SELECT * FROM users WHERE username = ?",
        (target_username,),
        fetchone=True
    )
    
    if not target or target['user_id'] == attacker_id:
        bot.send_message(message.chat.id, "Недопустимая цель")
        return
    try:
        success_chance = attacker['strength'] / (target['agility'] + attacker['strength'])
    except ZeroDivisionError:
        success_chance = 1
    if random.random() < success_chance:
        stolen = min(target['money'], random.randint(100, 1000))
        execute_query("UPDATE users SET money = ? WHERE user_id = ?", 
                     (target['money'] - stolen, target['user_id']))
        update_user(attacker_id, {'money': attacker['money'] + stolen})
        bot.send_message(message.chat.id, f"Успешное ограбление @{target_username}! +{stolen} руб")
        try:
            bot.send_message(target['user_id'], 
                f"Вас ограбили! Грабитель: {attacker['username']}\n"
                f"Потеряно: {stolen} руб\nСила: {attacker['strength']}")
        except: pass
    else:
        lost = random.randint(200, 500)
        update_user(attacker_id, {'money': max(0, attacker['money'] - lost)})
        bot.send_message(message.chat.id, f"Отпор! Потери: {lost} руб")
    
    update_user(attacker_id, {'last_rob': time.time()})

@bot.message_handler(commands=['profile'])
def profile(message):
    if message.chat.type != "private":
        bot.reply_to(message, "Эта команда доступна только в личном чате!")
        return
    user = get_user(message.chat.id)
    business = get_business(user['user_id'])
    
    profile_text = (
        f"Профиль: @{user['username']}\n"
        f"Уровень: {user['level']}\nДеньги: {user['money']} руб\n"
        f"Опыт: {user['exp']}/{user['level']*1000}\n"
        f"Сила: {user['strength']}\nЛовкость: {user['agility']}"
    )
    
    if business:
        profile_text += f"\nБизнес: {BUSINESS_TYPES[str(business['business_type'])]['name']}"
    
    bot.send_message(message.chat.id, profile_text)

@bot.message_handler(commands=['business'])
def business_info(message):
    user_id = message.from_user.id
    business = get_business(user_id)
    
    if not business:
        return bot.reply_to(message, "У вас нет бизнеса!")
    
    bt = BUSINESS_TYPES[str(business['business_type'])]
    next_collect = business['last_collected'] + 900
    time_left = next_collect - int(time.time())
    
    info_text = (
        f"{bt['name']}\n"
        f"Сырьё: {business['resources']}\n"
        f"Следующее списание через: {max(0, (time_left//60)-15)} мин\n"
        f"Доход за цикл: {business['resources']*bt['income']} руб"
    )
    
    bot.send_message(message.chat.id, info_text)

@bot.message_handler(commands=['buy_resources'])
def buy_resources(message):
    try:
        quantity = int(message.text.split()[1])
        user_id = message.from_user.id
        business = get_business(user_id)
        
        if not business:
            return bot.reply_to(message, "Сначала купите бизнес!")
            
        bt = BUSINESS_TYPES[str(business['business_type'])]
        total_price = quantity * bt['resource_price']
        user = get_user(user_id)
        
        if user['money'] < total_price:
            return bot.reply_to(message, f"Недостаточно денег! Нужно: {total_price} руб")
            
        update_user(user_id, {'money': user['money'] - total_price})
        update_business(user_id, {'resources': business['resources'] + quantity})
        
        bot.send_message(message.chat.id, 
            f"Куплено {quantity} ед. сырья\n"
            f"Потрачено: {total_price} руб\n"
            f"Теперь сырья: {business['resources'] + quantity}"
        )
        
    except Exception as e:
        bot.reply_to(message, "Используйте: /buy_resources [количество]")

@bot.message_handler(commands=['buy_business'])
def buy_business(message):
    user_id = message.from_user.id
    if get_business(user_id):
        bot.send_message(message.chat.id, "У вас уже есть бизнес!")
        return
    
    business_list = "\n".join([f"{k}. {v['name']} - {v['price']} руб" for k,v in BUSINESS_TYPES.items()])
    bot.send_message(message.chat.id, f"Доступные бизнесы:\n{business_list}\nИспользуйте /purchase [номер]")

@bot.message_handler(commands=['purchase'])
def purchase_business(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    try:
        bt = BUSINESS_TYPES[message.text.split()[1]]
    except:
        bot.send_message(message.chat.id, "Ошибка выбора бизнеса")
        return
    
    if user['money'] < bt['price']:
        bot.send_message(message.chat.id, "Недостаточно денег!")
        return
    
    update_user(user_id, {'money': user['money'] - bt['price']})
    create_business(user_id, message.text.split()[1])
    bot.send_message(message.chat.id, f"Приобретен бизнес: {bt['name']}!")

@bot.message_handler(commands=['sell_business'])
def sell_business(message):
    try:
        user_id = message.from_user.id
        business = get_business(user_id)
        
        if not business:
            raise ValueError("Бизнес не найден")
            
        bt = BUSINESS_TYPES[str(business['business_type'])]
        sell_price = bt['price']
        
        with closing(sqlite3.connect(DATABASE_NAME)) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM businesses WHERE user_id = ?", (user_id,))
            c.execute("UPDATE users SET money = money + ? WHERE user_id = ?", 
                     (sell_price, user_id))
            conn.commit()
            
        bot.send_message(message.chat.id, 
            (f"Продажа бизнеса {bt['name']} завершена!\n"
            f"На счет зачислено: {sell_price} ₽\n"
            f"Итоговый баланс: {get_user(user_id)['money']} ₽")
        )
        
    except Exception as e:
        bot.reply_to(message, f"Ошибка продажи: {str(e)}")

@bot.message_handler(commands=['casino'])
def casino(message):
    user = get_user(message.from_user.id)
    
    try:
        bet = int(message.text.split()[1])
    except:
        bot.send_message(message.chat.id, "Используйте: /casino [сумма]")
        return
    
    if bet > user['money']:
        bot.send_message(message.chat.id, "Недостаточно средств")
        return
    
    if random.random() < 0.01:
        win = bet * 30
        update_user(user['user_id'], {'money': user['money'] + win + 25*get_user(user['user_id'])['level']})
        response = f"ДЖЕКПОТ! Выигрыш: {win} руб!"
    else:
        update_user(user['user_id'], {'money': user['money'] - bet})
        response = f"Проигрыш! Потеряно: {bet} руб"
    
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['top'])
def top(message):
    top_list = ["Топ игроков:"]
    for i, user in enumerate(get_top_users(10), 1):
        top_list.append(f"{i}. {user['username']} - {user['money']} руб")
    bot.send_message(message.chat.id, "\n".join(top_list))

@bot.message_handler(commands=['upgrade'])
def upgrade(message):
    if message.chat.type != "private":
        bot.reply_to(message, "Эта команда доступна только в личном чате!")
        return
    user = get_user(message.from_user.id)
    
    try: stat = message.text.split()[1].lower()
    except:
        bot.send_message(message.chat.id, "Используйте: /upgrade [сила/ловкость]")
        return
    
    if stat not in ['сила', 'ловкость']:
        bot.send_message(message.chat.id, "Некорректный параметр")
        return
    
    field = 'strength' if stat == 'сила' else 'agility'
    cost = user[field] * 1000
    
    if user['money'] < cost:
        bot.send_message(message.chat.id, f"Нужно {cost} руб")
        return
    
    update_data = {
        'money': user['money'] - cost,
        field: user[field] + 1
    }
    update_user(user['user_id'], update_data)
    bot.send_message(message.chat.id, f"{stat.capitalize()} улучшена до уровня {user[field]+1}!")

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    if user_id not in active_games:
        return
    
    game = active_games[user_id]
    
    if time.time() - game['start_time'] > 10:
        del active_games[user_id]
        bot.send_message(message.chat.id, "Время вышло!")
        return
    
    user_answer = message.text.upper().replace(' ', '')
    if user_answer == game['answer']:
        earned = random.randint(300, 700)
        update_user(user_id, {
            'money': get_user(user_id)['money'] + earned + 25*get_user(user_id)['level'],
            'last_work': time.time()
        })
        del active_games[user_id]
        bot.send_message(message.chat.id, f"Успех! Заработано: {earned} руб")
    else:
        game['attempts'] -= 1
        if game['attempts'] > 0:
            bot.send_message(message.chat.id, 
                f"Ошибка! Попыток осталось: {game['attempts']}\n"
                f"Повторите: {game['answer']}\nИз: {', '.join(game['sequence'])}"
            )
        else:
            del active_games[user_id]
            bot.send_message(message.chat.id, "Все попытки исчерпаны!")

def business_worker():
    while True:
        try:
            current_time = int(time.time())
            for business in get_all_businesses():
                user_id = business['user_id']
                bt = BUSINESS_TYPES[str(business['business_type'])]
                if current_time >= business['last_collected']:
                    resources_to_use = min(5, business['resources'])
                    if resources_to_use > 0:
                        update_business(user_id, {
                            'resources': business['resources'] - resources_to_use,
                            'last_collected': current_time + 900
                        })
                        income = resources_to_use * bt['income']
                        user = get_user(user_id)
                        update_user(user_id, {'money': user['money'] + income})
                    else:
                        update_business(user_id, {
                            'last_collected': current_time + 900
                        })
        except Exception as e:
            print(f"Business error: {str(e)}")
        time.sleep(60)

threading.Thread(target=business_worker, daemon=True).start()
bot.polling()