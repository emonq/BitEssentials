import sqlite3


class SqliteStorage:
    
    def __init__(self, filename):
        self.__conn = sqlite3.connect(filename)
        self.__cursor = self.__conn.cursor()
        self.__cursor.execute("CREATE TABLE IF NOT EXISTS BIT\n"
                              "        (ID TEXT PRIMARY KEY,\n"
                              "        Obj TEXT\n"
                              "        )\n"
                              "        ")
    
    def save(self, username, obj):
        """
        存储序列化对象到数据库中
        :param username: 用户名
        :param obj: 用户名对应的会话对象
        :return: 无
        """
        self.__cursor.execute("REPLACE INTO BIT(ID,Obj) VALUES (?,?)", (username, obj))
    
    def get_obj(self, username):
        """
        获取用户名对应的会话对象
        :param username: 用户名
        :return: 对应的会话对象字节流
        """
        self.__cursor.execute("SELECT Obj FROM BIT WHERE ID='%s'" % username)
        res = self.__cursor.fetchone()
        if res is not None:
            return res[0]
        return None
    
    def __del__(self):
        self.__conn.commit()
        self.__conn.close()
