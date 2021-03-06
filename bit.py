import random
import base64
import time
import json
import pickle
import os
import cgi
import re

import ics
import requests
import datetime
import logging
import pytz
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from bs4 import BeautifulSoup

TZ = pytz.timezone("Asia/Shanghai")


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


def get_datetime(date: datetime.datetime, time: datetime.datetime):
    return (date + datetime.timedelta(hours=time.hour, minutes=time.minute)).replace(
        tzinfo=TZ)


def build_ics_event(name, location, begin_t: datetime.datetime, end_t: datetime.datetime, description=None):
    return ics.Event(name=name, location=location, begin=begin_t, end=end_t, description=description)


def build_ics(data: list):
    cal = ics.Calendar()
    for i in data:
        cal.events.add(build_ics_event(i['name'], i['location'], i['begin'], i['end'],
                                       i['description'] if 'description' in i.keys() else None))
    return cal


class BitInfoError(Exception):
    def __init__(self, value):
        self.value = value


class Bit:
    
    def __init__(self, username=None, password=None):
        self.department = ''
        self.name = ''
        self.__session = requests.session()
        self.username = username
        self.__password = password
        self.scores = {}
        self.currentTerm = ''
        self.classTime = {}
    
    def set_info(self, username, password):
        """
        指定学号和密码
        :param str username: 学号
        :param str password: 密码
        :return: 无
        """
        self.username = username
        self.__password = password
    
    def check_account_status(self):
        """
        检查账号状态，返回False说明账号异常
        :return: 账号是否正常
        """
        result = self.__session.get('https://login.bit.edu.cn/authserver/checkNeedCaptcha.htl',
                                    params={'username': self.username})
        return not json.loads(result.text)['isNeed']
    
    def check_login_status(self):
        """
        检查统一身份认证登录状态，未登录返回False
        :return: 是否已经登录
        """
        result = self.__session.post('http://jxzxehallapp.bit.edu.cn/jwapp/sys/wdkbby/modules/xskcb/cxxsjbxx.do',
                                     allow_redirects=False)
        if result.status_code != 200:
            logging.info(f"{self.username} 的统一身份认证登录失效")
            return False
        return True
    
    def check_webvpn_login(self):
        """
        检查webvpn登录状态，未登录返回False
        :return: 是否已经登录
        """
        result = self.__session.get(
            'https://webvpn.bit.edu.cn/http/77726476706e69737468656265737421fae04c8f69326144300d8db9d6562d/jsxsd/framework/main.jsp',
            allow_redirects=False)
        if result.status_code != 200:
            logging.info(f"{self.username} 的webvpn登录失效")
            return False
        return True
    
    def login_to_url(self, login_url):
        """
        登录到url，为统一身份认证和webvpn提供登录
        :param login_url: 登录url
        :return: 无
        """
        if not self.check_account_status():
            raise BitInfoError("账号异常")
        result = self.__session.get(login_url)
        login_url = result.url
        page = BeautifulSoup(result.text, "html.parser")
        if page.find(id="execution") is None:
            return
        param_execution = page.find(id="execution")['value']
        password_salt = page.find(id="pwdEncryptSalt")['value']
        param_password = encrypt_password(self.__password, password_salt)
        data = {
            'username': self.username,
            'password': param_password,
            'captcha': '',
            'rememberMe': 'true',
            '_eventId': 'submit',
            'cllt': 'userNameLogin',
            'dllt': 'generalLogin',
            'lt': '',
            'execution': param_execution
        }
        result = self.__session.post(login_url, data)
        if result.status_code == 401:
            raise BitInfoError("密码错误")
    
    def login(self):
        """
        执行登录操作
        :return: 无
        :rtype: None
        """
        if self.username is None or self.__password is None:
            raise BitInfoError("账号或密码不能为空")
        if self.check_login_status():
            return
        self.login_to_url('https://login.bit.edu.cn/authserver/login')
        self.__session.get('http://jxzxehall.bit.edu.cn/login?service=http://jxzxehall.bit.edu.cn/new/index.html')
        self.__session.get('http://jxzxehall.bit.edu.cn/appShow?appId=5959167891382285')
        self.webvpn_login()
    
    def webvpn_login(self):
        """
        登录webvpn
        :return: 无
        :rtype: None
        """
        self.__session.cookies.set('show_vpn', '0', path='webvpn.bit.edu.cn')
        self.__session.cookies.set('refresh', '1', path='webvpn.bit.edu.cn')
        self.login_to_url('https://webvpn.bit.edu.cn/login?cas_login=true')
        self.__session.get(
            'https://webvpn.bit.edu.cn/http/77726476706e69737468656265737421fae04c8f69326144300d8db9d6562d/jsxsd/kscj/cjcx_list')
    
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
    
    def get_scores_update(self, refresh_all=False):
        """
        从webvpn爬取新成绩，返回更新的成绩项
        字典项定义：
        课程号 - 学期: {
            'id': 课程号,
            'term': 学期，如'2019-2020-1',
            'type': 课程性质
            'name': 课程名,
            'credit': 学分,
            'score': 分数,
            'average': 平均分,
            'max': 最高分,
            'class_rank': 班级排名,
            'class_total': 班级总人数,
            'majority_rank': 专业排名,
            'majority_total': 专业总人数,
            'all_rank': 所有学生排名
            }
        :param refresh_all: 是否刷新全部，默认为否
        :return: 包含成绩相关信息的字典
        :rtype: dict
        """
        if not self.check_webvpn_login():
            self.webvpn_login()
        url = "https://webvpn.bit.edu.cn/http/77726476706e69737468656265737421fae04c8f69326144300d8db9d6562d/jsxsd/kscj/cjcx_list"
        response = self.__session.get(url)
        page = BeautifulSoup(response.text, 'html.parser')
        scores = page.find_all('tr')[2:]
        updates = {}
        for i in scores:
            columns = i.find_all('td')
            key = f"{columns[2].text} - {columns[1].text}"
            if not refresh_all and key in self.scores:  # 如果scores中已经存在该项目则跳过
                logging.debug(f"{columns[3].text} 成绩已存在")
                continue
            data = {
                'id': columns[2].text,
                'term': columns[1].text,
                'name': columns[3].text,
                'type': columns[11].text,
                'credit': float(columns[6].text),
                'score': int(re.search(r'zcj=(\d+)', columns[-1].a['onclick']).group(1))}
            response = self.__session.get(
                'https://webvpn.bit.edu.cn/http/77726476706e69737468656265737421fae04c8f69326144300d8db9d6562d/jsxsd/kscj/cjfx',
                params={'xs0101id': self.username,
                        'xnxq01id': columns[1].text,
                        'kch': columns[2].text
                        })
            bs = BeautifulSoup(response.text, 'html.parser')
            analyse = bs.find_all('td')
            data['class_total'] = int(re.search(r'\d+', analyse[1].text)[0])
            data['majority_total'] = int(re.search(r'\d+', analyse[2].text)[0])
            data['average'] = analyse[4].text.split('：')[1]
            data['max'] = int(analyse[5].text.split('：')[1])
            data['class_rank'] = int(analyse[8].text.split('：')[1].strip('%')) / 100
            data['majority_rank'] = int(analyse[9].text.split('：')[1].strip('%')) / 100
            data['all_rank'] = int(analyse[10].text.split('：')[1].strip('%')) / 100
            self.scores[key] = data
            updates[key] = data
        logging.debug(self.scores)
        return updates
    
    def get_current_term(self):
        """
        获取当前学期并保存
        :return: 当前学期，如2019-2020-1
        """
        if not self.check_login_status():
            self.login()
        response = self.__session.post('http://jxzxehallapp.bit.edu.cn/jwapp/sys/wdkbby/modules/jshkcb/dqxnxq.do')
        self.currentTerm = json.loads(response.text)['datas']['dqxnxq']['rows'][0]['DM']
        return self.currentTerm
    
    def __get_class_time(self):
        """
        获取上课时间并保存，格式{ '第i节': {'begin': datetime,'end': datetime} }
        :return: 上课时间表
        """
        self.classTime = {}
        response = self.__session.post('http://jxzxehallapp.bit.edu.cn/jwapp/sys/wdkbby/modules/jshkcb/jc.do')
        res = response.json()['datas']['jc']['rows']
        for i in res:
            self.classTime[i['MC']] = {'begin': datetime.datetime.strptime(i['KSSJ'], '%H:%M'),
                                       'end': datetime.datetime.strptime(i['JSSJ'], '%H:%M')}
        return self.classTime
    
    def __get_week_classes(self, term, week):
        """
        获取指定学期指定周的课程信息
        :param term: 学期，如2019-2020-1
        :param week: 星期
        :return: 课程信息list，格式为[{ 'name': 课程名, 'location': 上课地点, 'begin': 开始时间, 'end': 结束时间 }]
        """
        # 获取星期中对应日期
        response = self.__session.post('http://jxzxehallapp.bit.edu.cn/jwapp/sys/wdkbby/wdkbByController/cxzkbrq.do',
                                       data={'requestParamStr': f'{{"XNXQDM": "{term}", "ZC": "{week}"}}'})
        res = response.json()['data']
        date = {}
        for i in res:
            date[i['XQ']] = datetime.datetime.strptime(i['RQ'], '%Y-%m-%d')
        response = self.__session.post('http://jxzxehallapp.bit.edu.cn/jwapp/sys/wdkbby/modules/xskcb/cxxszhxqkb.do',
                                       {'XNXQDM': term, 'SKZC': str(week)})
        res = response.json()['datas']['cxxszhxqkb']['rows']
        classes = []
        for i in res:
            classes.append({'name': f"{i['KCM']}-{i['SKJS']}",
                            'location': f"{i['XXXQMC']}{i['JASMC']}",
                            'begin': get_datetime(date[i['SKXQ']], self.classTime[i['KSJC_DISPLAY']]['begin']),
                            'end': get_datetime(date[i['SKXQ']], self.classTime[i['JSJC_DISPLAY']]['end'])
                            })
        return classes
    
    def get_term_classes(self, term=None):
        """
        获取指定学期课程信息
        :param term: 学期，如2019-2020-1
        :return: 课程信息list，格式为[{ 'name': 课程名, 'location': 上课地点, 'begin': 开始时间, 'end': 结束时间 }]
        """
        if not self.check_login_status():
            self.login()
        self.get_current_term()
        self.__get_class_time()
        if term is None:
            term = self.currentTerm
        classes = []
        for i in range(1, 100):
            week_classes = self.__get_week_classes(term, i)
            classes += week_classes
            if len(week_classes) == 0:
                logging.debug(f"学期 {term} 课表共 {i} 周")
                break
        return classes
    
    def get_term_classes_ics(self, term=None):
        """
        获取指定学期课程ics格式日程表
        :param term: 学期，如2019-2020-1
        :return: 课程信息ics
        """
        classes = self.get_term_classes(term)
        res = build_ics(classes)
        return res
    
    def get_exams(self, term=None):
        """
        获取指定学期考试安排信息
        :param term: 学期，如2019-2020-1
        :return: 考试安排list，格式[{ 'name': 课程名, 'location': 考试地点, 'begin': 开始时间, 'end': 结束时间, 'description': 备注信息 }]
        """
        if term is None:
            term = self.currentTerm
        response = self.__session.post(
            "http://jxzxehallapp.bit.edu.cn/jwapp/sys/studentWdksapApp/WdksapController/cxxsksap.do",
            {'requestParamStr': f'{{"XNXQDM":"{term}","*order":"-KSRQ,-KSSJMS"}}'})
        res = response.json()['datas']['cxxsksap']['rows']
        exams = []
        for i in res:
            date = re.findall(r"\d+-\d+-\d+", i['KSSJMS'])[0]
            exams.append({'name': "%s-%s-%s" % (i['KCM'], i['ZJJSXM'], i['KCH']),
                          'location': i['JASMC'],
                          'begin': datetime.datetime.strptime(
                              date + ' ' + re.findall(r"\d+-\d+-\d+ (\d+:\d+)", i['KSSJMS'])[0],
                              "%Y-%m-%d %H:%M").replace(tzinfo=TZ),
                          'end': datetime.datetime.strptime(
                              date + ' ' + re.findall(r"\d+-\d+-\d+ \d+:\d+-(\d+:\d+)", i['KSSJMS'])[0],
                              "%Y-%m-%d %H:%M").replace(tzinfo=TZ), 'description': f"座位号：{i['ZWH']}"
                          })
        return exams
    
    def get_exams_ics(self, term=None):
        """
        获取指定学期考试安排ics
        :param term: 学期，如2019-2020-1
        :return: 考试安排ics
        """
        exams = self.get_exams(term)
        res = build_ics(exams)
        return res
