from datetime import datetime
from config import *
import time
import os
import json

class Users:
    def __init__(self, name):
        if not os.path.exists(name):
            with open(name, 'w') as f:
                f.write('{}')

        self.path = name

    def get_user(self, uid):
        uid = str(uid)
        with open(self.path, 'r') as f:
            data = json.load(f)
            user = data[uid]
            return user

    def add_money(self, uid, money):
        uid = str(uid)
        if not isinstance(money, (int, float)):
            raise TypeError(f'Expected int or float, got {type(money).__name__}')

        user = get_user(uid)



class Bank:
    def __init__(self, name):
        if not os.path.exists(name):
            with open(name, 'w') as f:
                f.write('{"money": 0}')

        self.path = name

    def _get_data(self):
        with open(self.path, 'r') as f:
            return json.load(f)

    def _save_data(self, data):
        with open(self.path, 'w') as f:
            json.dump(data, f)


bank = Bank(BANK)
