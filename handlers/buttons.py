import telebot

def setup_buttons(bot):
    @bot.callback_query_handler(func=lambda call: True)
    def callback(call):
        if call.data == 'test':
            bot.answer_callback_query(call.id, "Нажато!")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Зачем ты нажал?",
                reply_markup=None
            )
    


    return bot