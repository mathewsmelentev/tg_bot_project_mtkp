import sqlite3
import time
from contextlib import closing

DATABASE_NAME = 'db.db'

def init_db():
    with closing(sqlite3.connect(DATABASE_NAME)) as conn:
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (user_id INTEGER PRIMARY KEY,
                     username TEXT,
                     money INTEGER DEFAULT 0,
                     exp INTEGER DEFAULT 0,
                     level INTEGER DEFAULT 1,
                     strength INTEGER DEFAULT 1,
                     agility INTEGER DEFAULT 1,
                     last_work INTEGER DEFAULT 0,
                     last_crime INTEGER DEFAULT 0,
                     last_rob INTEGER DEFAULT 0
                     )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS businesses
                    (user_id INTEGER PRIMARY KEY,
                     business_type INTEGER,
                     resources INTEGER DEFAULT 0,
                     last_collected INTEGER DEFAULT 0)''')
        conn.commit()

def execute_query(query, params=(), fetchone=False):
    with closing(sqlite3.connect(DATABASE_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(query, params)
        result = c.fetchone() if fetchone else c.fetchall()
        conn.commit()
        return result

def get_user(user_id):
    user = execute_query(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,),
        fetchone=True
    )
    if not user:
        execute_query("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        return {
            'user_id': user_id,
            'username': str(user_id),
            'money': 0,
            'exp': 0,
            'level': 1,
            'strength': 1,
            'agility': 1,
            'last_work': 0,
            'last_crime': 0,
            'last_rob': 0
        }
    return dict(user)

def update_user(user_id, updates):
    if not updates: return
    set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [user_id]
    execute_query(
        f"UPDATE users SET {set_clause} WHERE user_id = ?",
        values
    )

def get_business(user_id):
    business = execute_query(
        "SELECT * FROM businesses WHERE user_id = ?",
        (user_id,),
        fetchone=True
    )
    return dict(business) if business else None

def create_business(user_id, business_type):
    execute_query(
        "INSERT INTO businesses (user_id, business_type) VALUES (?, ?)",
        (user_id, business_type)
    )

def update_business(user_id, updates):
    if not updates: return
    set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [user_id]
    execute_query(
        f"UPDATE businesses SET {set_clause} WHERE user_id = ?",
        values
    )

def get_all_businesses():
    return execute_query("SELECT * FROM businesses", fetchone=False)

def get_top_users(limit=10):
    return execute_query(
        "SELECT username, money FROM users ORDER BY money DESC LIMIT ?",
        (limit,)
    )

init_db()