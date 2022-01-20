import requests
import random
import base64
import time
import json
import pickle
import os
import cgi
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from bs4 import BeautifulSoup


def get_random_string(length):
    return ''.join(random.choices("ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678", k=length))


def encrypt_password(password, key):
    password = password.strip()
    aes = AES.new(bytes(key, encoding='utf-8'), mode=AES.MODE_CBC,
                  iv=bytes(get_random_string(16), encoding='utf-8'))
    pad_pkcs7 = pad(bytes(get_random_string(64) + password,
                          encoding='utf-8'), AES.block_size, style='pkcs7')
    return base64.b64encode(aes.encrypt(pad_pkcs7)).decode('utf-8')


def timestamp():
    return round(time.time() * 1000)


class BitInfoError(Exception):
    def __init__(self, value):
        self.value = value


class Bit:
    """
    北理工统一身份认证
    """
    
    def __init__(self, username=None, password=None):
        self.department = ''
        self.name = ''
        self.__session = requests.session()
        self.__username = username
        self.__password = password
    
    def set_info(self, username, password):
        """
        指定学号和密码
        :param str username: 学号
        :param str password: 密码
        :return: 无
        """
        self.__username = username
        self.__password = password
    
    def check_account_status(self):
        """
        检查账号状态，返回False说明账号异常
        :return: 账号是否正常
        """
        result = self.__session.get('https://login.bit.edu.cn/authserver/checkNeedCaptcha.htl',
                                    params={'username': self.__username})
        return not json.loads(result.text)['isNeed']
    
    def check_login_status(self):
        """
        检查登录状态，未登录返回False
        :return: 是否已经登录
        """
        result = self.__session.post('http://jxzxehallapp.bit.edu.cn/jwapp/sys/wdkbby/modules/xskcb/cxxsjbxx.do',
                                     allow_redirects=False)
        return result.status_code == 200
    
    def login(self):
        """
        执行登录操作
        :return: 无
        :rtype: None
        """
        if self.__username is None or self.__password is None:
            raise BitInfoError("账号或密码不能为空")
        if self.check_login_status():
            return
        if self.check_account_status():
            result = self.__session.get('https://login.bit.edu.cn/authserver/login')
            page = BeautifulSoup(result.text, "html.parser")
            param_execution = page.find(id="execution")['value']
            password_salt = page.find(id="pwdEncryptSalt")['value']
            param_password = encrypt_password(self.__password, password_salt)
            data = {
                'username': self.__username,
                'password': param_password,
                'captcha': '',
                'rememberMe': 'true',
                '_eventId': 'submit',
                'cllt': 'userNameLogin',
                'dllt': 'generalLogin',
                'lt': '',
                'execution': param_execution
            }
            result = self.__session.post('https://login.bit.edu.cn/authserver/login', data)
            if result.status_code == 401:
                raise BitInfoError("密码错误")
            self.__session.get('http://jxzxehall.bit.edu.cn/login?service=http://jxzxehall.bit.edu.cn/new/index.html')
            self.__session.get('http://jxzxehall.bit.edu.cn/appShow?appId=5959167891382285')
        else:
            raise BitInfoError("账号异常")
    
    def serialize(self):
        """
        序列化为字节流
        :return: 字节流
        """
        return pickle.dumps(self)
    
    def get_info(self):
        """
        获取用户姓名和学院
        :return: {'name': 姓名, 'department': 学院}
        """
        if not self.check_login_status():
            raise BitInfoError("未登录")
        result = self.__session.post('http://jxzxehallapp.bit.edu.cn/jwapp/sys/wdkbby/modules/xskcb/cxxsjbxx.do')
        result = json.loads(result.text)['datas']['cxxsjbxx']['rows'][0]
        self.name = result['XM']
        self.department = result['YXMC']
        return {'name': self.name, 'department': self.department}
    
    def download_file(self, url, path='', override=False):
        """
        从指定url下载单个文件并保存到指定路径
        :param url: 文件url
        :param path: 保存路径，默认为运行路径
        :param override: 是否覆盖已存在的文件，默认为否
        :return: 无
        """
        file = self.__session.get(url)
        filename = cgi.parse_header(file.headers['Content-Disposition'])[1]['filename'].encode(
            'ISO-8859-1').decode('utf8')
        filepath = os.path.join(path, filename)
        if not os.path.exists(filepath) or override:
            with open(filepath, 'wb') as f:
                f.write(file.content)
            print(f"已下载：{filepath}")
        else:
            print(f"跳过已存在：{filepath}")
    
    def download_lexue_course_files(self, courseid, path='', override=False):
        """
        根据课程号下载乐学课程文件并保存到指定路径
        :param courseid: 课程号
        :param path: 保存路径，默认为运行路径
        :param override: 是否覆盖已存在的文件，默认为否
        :return: 无
        """
        courseurl = 'https://lexue.bit.edu.cn/course/view.php?id=' + courseid
        page = self.__session.get(courseurl).text
        bs = BeautifulSoup(page, 'html.parser')
        course_title = bs.find('h1').text
        self.download_lexue_page_files(courseurl, os.path.join(path, course_title), override)
    
    def download_lexue_page_files(self, url, path='', override=False):
        """
        递归下载乐学指定url页面上的文件
        :param url: 页面url
        :param path: 保存路径，默认为运行路径
        :param override: 是否覆盖已存在的文件，默认为否
        :return: 无
        """
        if not os.path.exists(path):
            os.makedirs(path)
        result = self.__session.get(url)
        bs = BeautifulSoup(result.text, 'html.parser')
        print(f"正在下载页面 {bs.title.text} 中的内容")
        for i in bs.find_all(class_='fp-filename'):
            if i.parent.has_attr('href'):
                self.download_file(i.parent['href'], path, override)
        if bs.find(class_='single-section'):
            targets = bs.find(class_='single-section').findAll(class_='instancename')
        elif bs.find(class_='topics'):
            targets = bs.find(class_='topics').findAll(class_='instancename')
        else:
            targets = bs.findAll(class_='instancename')
        for i in targets:
            type_tag = i.find(class_='accesshide')
            if type_tag:
                obj_type = type_tag.text.strip()
                type_tag.decompose()
                filepath = os.path.join(path, i.text)
                if obj_type == '文件夹':
                    if not os.path.exists(filepath):
                        os.makedirs(filepath)
                    self.download_lexue_page_files(i.parent['href'], filepath)
                elif obj_type == '文件':
                    self.download_file(i.parent['href'], path, override)
        for i in bs.findAll(class_='section-title'):
            self.download_lexue_page_files(i.a['href'], os.path.join(path, i.a.text))
