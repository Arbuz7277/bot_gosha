# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Arbuz.
# handlers/id.py

"""
Возващает айди пользователя по ответу или его самого.
"""

from utils import log_handler, add_chat, load_users

def setup(bot):
    @bot.message_handler(commands=['id'])
    def cmd_id(msg):
        user_id = msg.from_user.id
        add_chat(msg.chat.id)
        users = load_users()

        try:
            recipient = msg.reply_to_message.from_user.id
            gid = users[str(recipient)].get('gid')

            bot.reply_to(msg, f"Telegram ID: `{recipient}`\nGosha ID: `{gid}`", parse_mode='markdown')
        except:
            gid = users[str(user_id)].get('gid')
            bot.reply_to(msg, f"Telegram ID: `{user_id}`\nGosha ID: `{gid}`", parse_mode='markdown')

    return bot
