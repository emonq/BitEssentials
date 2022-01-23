import datetime
import json
import logging
import pickle
import pytz

from telegram import ParseMode
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import Defaults
from telegram.ext import Updater

from bit import Bit, BitInfoError
from data_storage import SqliteStorage

configs = json.load(open("config.json", 'r'))
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=configs['logging_level'])
db = SqliteStorage(configs['Sqlite_filename'])
with open("TOS.txt", 'r', encoding='UTF-8') as f:
    TOS = f.read()


def get_scores_message(scores):
    msg = ""
    for i in scores:
        info = scores[i]
        msg += f"\n<b>{info['name']} - {info['id']}</b>\n学期：{info['term']}\n成绩：{info['score']}\n平均分：{info['average']}\n最高分：{info['max']}\n班级排名：{int(info['class_rank'] * 100)}%（第{round(info['class_rank'] * info['class_total'])}位）\n专业排名：{int(info['majority_rank'] * 100)}%（第{round(info['majority_rank'] * info['majority_total'])}位）\n"
    return msg


def get_score_update_of_user(TGID):
    obj = db.get_obj(TGID)
    if obj is None:
        return "你还没有绑定学号，使用 /link 绑定后才能使用本功能"
    bit = pickle.loads(obj)
    updates = bit.get_scores_update()
    logging.info(f"开始为{bit.username}更新成绩")
    if len(updates) == 0:
        return "没有新的成绩更新"
    else:
        db.save_obj(bit.username, bit.serialize(), TGID)
        msg = "天啊天啊有新的成绩！！！\n"
        msg += get_scores_message(updates)
        return msg


def refresh_scores(context: CallbackContext):
    logging.info("开始更新所有用户成绩")
    ids = db.get_all_users()
    for ID in ids:
        context.bot.send_message(chat_id=ID, text=get_score_update_of_user(ID))


def start_handler(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="这是你的BIT小秘书，我可以帮你查成绩，使用 /tos 查看我们的使用条款，继续使用视为你已经同意条款")


def tos_handler(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text=TOS)


def refresh_handler(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    msg = get_score_update_of_user(chat_id)
    for x in range(0, len(msg), 4096):
        context.bot.send_message(chat_id=chat_id, text=msg[x:x + 4096])


def link_handler(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    obj = db.get_obj(chat_id)
    if obj is not None:
        context.bot.send_message(chat_id=chat_id, text="你已经绑定成功，如需重新绑定请 /unlink 解绑之后重新绑定")
        return
    if len(context.args) != 2:
        context.bot.send_message(chat_id=chat_id, text="使用格式：/link 学号 密码")
        return
    username = context.args[0]
    password = context.args[1]
    bit = Bit(username, password)
    try:
        bit.login()
        db.save_obj(username, bit.serialize(), chat_id)
        context.bot.send_message(chat_id=chat_id, text=f"成功绑定学号{username}")
    except BitInfoError as e:
        context.bot.send_message(chat_id=chat_id, text=str(e))
        logging.error(f"from {chat_id}:{e}")
    except Exception as e:
        logging.error(repr(e))
        context.bot.send_message(chat_id=chat_id, text="绑定失败，出现了未知错误")


def unlink_handler(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    obj = db.get_obj(chat_id)
    if obj is None:
        context.bot.send_message(chat_id=chat_id, text="你还没有绑定学号，使用 /link 绑定后才能使用本功能")
        return
    else:
        db.delete_user(chat_id)
        context.bot.send_message(chat_id=chat_id, text="解绑成功")


def info_handler(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    msg = f"你的chat id是：{chat_id}\n当前绑定状态："
    obj = db.get_obj(chat_id)
    if obj is None:
        msg += "未绑定"
    else:
        bit = pickle.loads(obj)
        msg += f"已绑定 {bit.username}"
    context.bot.send_message(chat_id=chat_id, text=msg)


def getscores_handler(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    obj = db.get_obj(chat_id)
    if obj is None:
        context.bot.send_message(chat_id=chat_id, text="你还没有绑定学号，使用 /link 绑定后才能使用本功能")
        return
    else:
        bit = pickle.loads(obj)
        msg = "这是你的查询结果：\n"
        if len(context.args) == 0:
            msg += get_scores_message(bit.scores)
        else:
            if len(context.args) > 1:
                msg = "使用格式 /getscores [学期，如 2019-2020-1]"
            else:
                scores = {i: bit.scores[i] for i in bit.scores if bit.scores[i]['term'] == context.args[0]}
                msg += get_scores_message(scores)
        for x in range(0, len(msg), 4096):
            context.bot.send_message(chat_id=chat_id, text=msg[x:x + 4096])


def run():
    defaults = Defaults(parse_mode=ParseMode.HTML, tzinfo=pytz.timezone('Asia/Shanghai'))
    updater = Updater(token=configs['bot_token'], use_context=True, defaults=defaults)
    job_queue = updater.job_queue
    job_queue.run_daily(refresh_scores, datetime.time(0, 10, 0, 0))
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler('start', start_handler))
    dispatcher.add_handler(CommandHandler('tos', tos_handler))
    dispatcher.add_handler(CommandHandler('link', link_handler))
    dispatcher.add_handler(CommandHandler('refresh', refresh_handler))
    dispatcher.add_handler(CommandHandler('unlink', unlink_handler))
    dispatcher.add_handler(CommandHandler('info', info_handler))
    dispatcher.add_handler(CommandHandler('getscores', getscores_handler))
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    run()
