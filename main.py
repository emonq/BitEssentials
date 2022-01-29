import datetime
import json
import logging
import pickle
import re
import traceback

import pytz
import uuid

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
        msg += f"\n<b>{info['name']} - {info['id']}</b>\n学期：{info['term']}\n成绩：{info['score']}\n平均分：{info['average']}\n最高分：{info['max']}\n班级排名：{int(info['class_rank'] * 100)}%（第{round(info['class_rank'] * info['class_total'])}/{info['class_total']}位）\n专业排名：{int(info['majority_rank'] * 100)}%（第{round(info['majority_rank'] * info['majority_total'])}/{info['majority_total']}位）\n"
    return msg


def get_score_update_of_user(tgid, refresh_all=False):
    obj = db.get_obj(tgid)
    if obj is None:
        return "你还没有绑定学号，使用 /link 绑定后才能使用本功能"
    bit = pickle.loads(obj)
    updates = bit.get_scores_update(refresh_all)
    logging.info(f"开始为{bit.username}更新成绩")
    if len(updates) == 0:
        return "没有新的成绩更新"
    else:
        db.save_obj(bit.username, bit.serialize(), tgid)
        msg = "天啊天啊有新的成绩！！！\n"
        msg += get_scores_message(updates)
        return msg


def refresh_scores(context: CallbackContext):
    logging.info("开始更新所有用户成绩")
    ids = db.get_all_users()
    for ID in ids:
        msg = get_score_update_of_user(ID)
        if msg.startswith("天啊天啊有新的成绩！！！"):
            context.bot.send_message(chat_id=ID, text=msg)


def start_handler(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="这是你的BIT小秘书，我可以帮你查成绩，使用 /tos 查看我们的使用条款，继续使用视为你已经同意条款")


def tos_handler(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text=TOS)


def refresh_handler(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    try:
        refresh_all = False
        if len(context.args) > 0:
            refresh_all = True
        msg = get_score_update_of_user(chat_id, refresh_all)
        for x in range(0, len(msg), 4096):
            context.bot.send_message(chat_id=chat_id, text=msg[x:x + 4096])
    except BitInfoError as e:
        context.bot.send_message(chat_id=chat_id, text=str(e))
        logging.error(f"from {chat_id}:{e}")
    except Exception as e:
        errid = uuid.uuid1()
        logging.error(f"{errid}:{repr(e)}")
        logging.error(traceback.format_exc())
        context.bot.send_message(chat_id=chat_id, text=f"出现了未知错误，错误id {errid}")


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
    try:
        bit = Bit(username, password)
        bit.login()
        db.save_obj(username, bit.serialize(), chat_id)
        context.bot.send_message(chat_id=chat_id, text=f"成功绑定学号{username}")
    except BitInfoError as e:
        context.bot.send_message(chat_id=chat_id, text=str(e))
        logging.error(f"from {chat_id}:{e}")
    except Exception as e:
        errid = uuid.uuid1()
        logging.error(f"{errid}:{repr(e)}")
        logging.error(traceback.format_exc())
        context.bot.send_message(chat_id=chat_id, text=f"绑定失败，出现了未知错误，错误id {errid}")


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
        context.bot.send_message(chat_id=chat_id, text="请稍候，正在为你查询……")
        try:
            bit = pickle.loads(obj)
            if len(context.args) == 0:
                scores = bit.scores
            else:
                if len(context.args) > 1 or context.args[0] == 'help':
                    context.bot.send_message(chat_id=chat_id, text="使用格式 /getscores [学期，如 2019-2020-1] 默认查询所有成绩")
                    return
                else:
                    term = context.args[0]
                    years = re.findall(r'\d\d\d\d', term)
                    if int(years[1]) - int(years[0]) != 1:
                        context.bot.send_message(chat_id=chat_id, text="学期格式有误")
                        return
                    scores = {i: bit.scores[i] for i in bit.scores if bit.scores[i]['term'] == term}
            msg = f"为你查询到{len(scores)}条结果：\n"
            msg += get_scores_message(scores)
            for x in range(0, len(msg), 4096):
                context.bot.send_message(chat_id=chat_id, text=msg[x:x + 4096])
        except BitInfoError as e:
            context.bot.send_message(chat_id=chat_id, text=str(e))
            logging.error(f"from {chat_id}:{e}")
        except Exception as e:
            errid = uuid.uuid1()
            logging.error(f"{errid}:{repr(e)}")
            logging.error(f"from {chat_id}: {update.message}")
            logging.error(traceback.format_exc())
            context.bot.send_message(chat_id=chat_id, text=f"出现了未知错误，错误id {errid}")


def getclasses_handler(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    obj = db.get_obj(chat_id)
    if obj is None:
        context.bot.send_message(chat_id=chat_id, text="你还没有绑定学号，使用 /link 绑定后才能使用本功能")
        return
    else:
        try:
            bit = pickle.loads(obj)
            if len(context.args) == 0:
                term = bit.get_current_term()
            else:
                if len(context.args) > 1 or context.args[0] == 'help' or not re.match(r'\d\d\d\d-\d\d\d\d-\d',
                                                                                      context.args[0]):
                    context.bot.send_message(chat_id=chat_id, text="使用方法：/getclasses [ 学期，如 2019-2020-1 ] 默认查询当前学期")
                    return
                term = context.args[0]
                years = re.findall(r'\d\d\d\d', term)
                if int(years[1]) - int(years[0]) != 1:
                    context.bot.send_message(chat_id=chat_id, text="学期格式有误")
                    return
            context.bot.send_message(chat_id=chat_id, text="请稍候，正在为你查询……")
            res = bit.get_term_classes_ics(term)
            db.save_obj(bit.username, bit.serialize(), chat_id)
            context.bot.send_message(chat_id=chat_id, text=f"这是为你查询到的学期 {term} 课表")
            context.bot.send_document(chat_id=chat_id, document=str(res).encode('UTF-8'),
                                      filename=f"{bit.username}-{term}.ics")
        except BitInfoError as e:
            context.bot.send_message(chat_id=chat_id, text=str(e))
            logging.error(f"from {chat_id}:{e}")
        except Exception as e:
            errid = uuid.uuid1()
            logging.error(f"{errid}:{repr(e)}")
            logging.error(f"from {chat_id}: {update.message}")
            logging.error(traceback.format_exc())
            context.bot.send_message(chat_id=chat_id, text=f"出现了未知错误，错误id {errid}")


def getexams_handler(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    obj = db.get_obj(chat_id)
    if obj is None:
        context.bot.send_message(chat_id=chat_id, text="你还没有绑定学号，使用 /link 绑定后才能使用本功能")
        return
    else:
        try:
            bit = pickle.loads(obj)
            if len(context.args) == 0:
                term = bit.get_current_term()
            else:
                if len(context.args) > 1 or context.args[0] == 'help' or not re.match(r'\d\d\d\d-\d\d\d\d-\d',
                                                                                      context.args[0]):
                    context.bot.send_message(chat_id=chat_id, text="使用方法：/getexams [ 学期，如 2019-2020-1 ] 默认查询当前学期")
                    return
                term = context.args[0]
                years = re.findall(r'\d\d\d\d', term)
                if int(years[1]) - int(years[0]) != 1:
                    context.bot.send_message(chat_id=chat_id, text="学期格式有误")
                    return
            context.bot.send_message(chat_id=chat_id, text="请稍候，正在为你查询……")
            res = bit.get_exams(term)
            if len(res) == 0:
                context.bot.send_message(chat_id=chat_id, text=f"你在学期 {term} 暂无考试安排")
                return
            msg = f"这是为你查询到的学期 {term} 考试安排，共 {len(res)} 项\n"
            for i in res:
                msg += f"\n<b>{i['name']}</b>\n地点：{i['location']}\n时间：{i['begin'].strftime('%Y-%m-%d %H:%M')} - {i['end'].strftime('%Y-%m-%d %H:%M')}\n备注：{i['description'] if 'description' in i.keys() else '无'}\n"
            res_ics = bit.get_exams_ics(term)
            db.save_obj(bit.username, bit.serialize(), chat_id)
            context.bot.send_message(chat_id=chat_id, text=msg)
            context.bot.send_document(chat_id=chat_id, document=str(res_ics).encode('UTF-8'),
                                      filename=f"{bit.username}-{term}-exams.ics")
        except BitInfoError as e:
            context.bot.send_message(chat_id=chat_id, text=str(e))
            logging.error(f"from {chat_id}:{e}")
        except Exception as e:
            errid = uuid.uuid1()
            logging.error(f"{errid}:{repr(e)}")
            logging.error(f"from {chat_id}: {update.message}")
            logging.error(traceback.format_exc())
            context.bot.send_message(chat_id=chat_id, text=f"出现了未知错误，错误id {errid}")


def getaverage_handler(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    obj = db.get_obj(chat_id)
    if obj is None:
        context.bot.send_message(chat_id=chat_id, text="你还没有绑定学号，使用 /link 绑定后才能使用本功能")
        return
    else:
        context.bot.send_message(chat_id=chat_id, text="请稍候，正在为你查询……")
        try:
            if len(context.args) > 1 or (
                    len(context.args) == 1 and (context.args[0] == 'help' or not re.match(r'\d\d\d\d-\d\d\d\d-\d',
                                                                                          context.args[0]))):
                context.bot.send_message(chat_id=chat_id, text="使用格式 /getaverage [学期，如 2019-2020-1] 默认查询所有成绩的加权均分")
                return
            bit = pickle.loads(obj)
            msg = get_score_update_of_user(chat_id)
            if msg.startswith("天啊天啊有新的成绩！！！"):
                context.bot.send_message(chat_id=chat_id, text=msg)
            if len(context.args) == 0:
                term = bit.get_current_term()
            else:
                term = context.args[0]
                years = re.findall(r'\d\d\d\d', term)
                if int(years[1]) - int(years[0]) != 1:
                    context.bot.send_message(chat_id=chat_id, text="学期格式有误")
                    return
            scores = {i: bit.scores[i] for i in bit.scores if
                      bit.scores[i]['term'] == term and bit.scores[i]['type'] != '校公选课'}
            total = 0
            total_credit = 0
            for i in scores:
                total += scores[i]['score'] * scores[i]['credit']
                total_credit += scores[i]['credit']
            if len(scores) == 0:
                msg = f"你在学期 {term} 还没有考试成绩"
            else:
                msg = f"你在学期 {term} 共有 {len(scores)} 项考试成绩，均分为 {round(total / total_credit, 3)} 分"
            context.bot.send_message(chat_id=chat_id, text=msg)
        except BitInfoError as e:
            context.bot.send_message(chat_id=chat_id, text=str(e))
            logging.error(f"from {chat_id}:{e}")
        except Exception as e:
            errid = uuid.uuid1()
            logging.error(f"{errid}:{repr(e)}")
            logging.error(f"from {chat_id}: {update.message}")
            logging.error(traceback.format_exc())
            context.bot.send_message(chat_id=chat_id, text=f"出现了未知错误，错误id {errid}")


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
    dispatcher.add_handler(CommandHandler('getclasses', getclasses_handler))
    dispatcher.add_handler(CommandHandler('getexams', getexams_handler))
    dispatcher.add_handler(CommandHandler('getaverage', getaverage_handler))
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    run()
