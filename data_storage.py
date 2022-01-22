import sqlite3


class SqliteStorage:
    
    def __init__(self, filename):
        self.__conn = sqlite3.connect(filename, check_same_thread=False)
        self.__cursor = self.__conn.cursor()
        self.__cursor.execute("CREATE TABLE IF NOT EXISTS BIT\n"
                              "        (ID TEXT,\n"
                              "        Obj TEXT,\n"
                              "        TGID TEXT PRIMARY KEY\n"
                              "        )\n")
    
    def save_obj(self, username, obj, tgid):
        """
        存储序列化对象到数据库中
        :param tgid: Telegram ChatID
        :param username: 用户名
        :param obj: 用户名对应的会话对象
        :return: 无
        """
        self.__cursor.execute("REPLACE INTO BIT(ID,Obj,TGID) VALUES (?,?,?)", (username, obj, tgid))
        self.__conn.commit()
    
    def get_obj(self, tgid):
        """
        获取Telegram ChatID对应的会话对象
        :param tgid: Telegram ChatID
        :return: 对应的会话对象字节流
        """
        self.__cursor.execute("SELECT Obj FROM BIT WHERE TGID='%s'" % tgid)
        res = self.__cursor.fetchone()
        if res is not None:
            return res[0]
        return None
    
    def delete_user(self, tgid):
        """
        删除Telegram ChatID对应的用户
        :param tgid:
        :return:
        """
        self.__cursor.execute("DELETE FROM BIT WHERE TGID='%s'" % tgid)
        self.__conn.commit()
    
    def get_all_users(self):
        """
        获取所有用户的Telegram ChatID
        :return: 所有用户的Telegram ChatID列表
        """
        self.__cursor.execute("SELECT TGID FROM BIT")
        res = self.__cursor.fetchone()
        if res is not None:
            return res
        return None
    
    def __del__(self):
        self.__conn.commit()
        self.__conn.close()
