
import base64
import configparser
import datetime
import getpass
import time
from collections import namedtuple
import lxml.etree
import logging
import os
import requests
import rsa
from tenacity import retry, stop_after_attempt, wait_fixed
import urllib.parse

import smtplib

# 创建 SMTP 对象
smtp = smtplib.SMTP()
# 连接（connect）指定服务器
smtp.connect("smtp.163.com", port=25)
# 登录，需要：登录邮箱和授权码
#todo:替换邮箱用户名和授权码
smtp.login(user="", password="")
from email.mime.text import MIMEText
from email.header import Header


def connectsmtp():
    global smtp
    smtp = smtplib.SMTP()
    #todo:可能要改，根据不同的邮箱更改为不同的服务器
    smtp.connect("smtp.163.com", port=25)
    #todo:替换邮箱用户名和授权码
    smtp.login(user="", password="")


def printf(mess, end="\n"):
    print(mess, end)
    send(mess)


def send(messagetext):
    print(messagetext)
    message = MIMEText(messagetext, 'plain', 'utf-8')
    message['Subject'] = Header(messagetext, 'utf-8')  # 定义主题内容
    c = 1
    while c == 1:
        try:
            #todo:替换发件人和收件人
            smtp.sendmail(from_addr="", to_addrs="", msg=message.as_string())
            c = 2
        except:
            print("发送失败")
            reconnect()
            connectsmtp()


def reconnect():
    #todo:因为本人是在ubuntu的环境下使用，因此网络重新连接部分不能被使用到windows或者mac下可能需要进行适配并对这个功能进行开关调整
    print("重新连接中")
    import subprocess
    # scan_result = subprocess.run(['nmcli', 'con', 'show'], capture_output=True, text=True)
    while 1:
        print("尝试重新连接中中中\n",flush=True)
        try:
            yn = False
            #todo: 更改为一个不是校园网的wifi,在''中填入
            scan_result = subprocess.run(['nmcli', 'device', 'wifi', 'connect', ''], timeout=5,
                                         capture_output=True, text=True)
            print(scan_result.stdout, flush=True)
            if "成功" not in scan_result.stdout:
                print("第一个烂了", flush=True)
                yn = True
            #todo:使用的是(https://github.com/SHUzhekiNg/SHU-VPNconfig-for-Ubuntu)   (@Licheng Zheng)提供的ubuntu下openvpn的使用方式
            scan_result = subprocess.run(['nmcli', 'con', 'up', 'id', 'SHU-VPN-Ubuntu'], timeout=5, capture_output=True,
                                         text=True)
            print(scan_result.stdout, flush=True)
            if "成功" not in scan_result.stdout:
                print("第2个烂了", flush=True)
                yn = True
            if yn == True:
                #todo:使用的是SHuWlan-1X，可以通过下一行注释掉的指令在ubuntu下获取所有wifi的名称，记得需要print(scan_result.stdout),使用其中的ssid替换最后一个单引号即可
                # scan_result =subprocess.run(['nmcli','device','wifi','list'],capture_output=True,text=True)
                scan_result = subprocess.run(['nmcli', 'device', 'wifi', 'connect', 'ShuWlan-1X'], timeout=5,
                                             capture_output=True, text=True)
                print(scan_result.stdout, flush=True)
                yn = False
                if "成功" not in scan_result.stdout:
                    print("第3个烂了", flush=True)
                    yn = True
            if yn == False:
                break
        except:
            pass
    printf("连接成功了")


# Settings
VER = "1.3.3"
query_delay = 1.5
chk_select_time_delay = 5
auto_cls = True
warn_diff_campus = True
CONFIGPATH = "courses.txt"
keep_logs = True
logging_level = 20
LOGPATH = "selection.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Variables
Termlist = []
Courselist = []
inputlist = []
username = ""
password = ""
encryptedpassword = ""
sterm = 0

# Declaration
Termitem = namedtuple("Term", ["termid", "name"])
Courseinfo = namedtuple("CourseInfo",
                        ["courseid", "coursename", "teacherid", "teachername", "capacity", "number", "restriction"])
Courseitem = namedtuple("CourseItem", ["courseid", "teacherid", "replacecid", "replacetid"])
Selectionresult = namedtuple("SelectionResult",
                             ["courseid", "coursename", "teacherid", "teachername", "msg", "isSuccess"])

# Base Urls
_baseurl = "http://xk.autoisp.shu.edu.cn/"
_termindex = "Home/TermIndex"
_termselect = "Home/TermSelect"
_fastinput = "CourseSelectionStudent/FastInput"
_querycourse = "StudentQuery/QueryCourseList"
_selectcourse = "CourseSelectionStudent/CourseSelectionSave"
_diffcampus = "CourseSelectionStudent/VerifyDiffCampus"
_selectedcourse = "CourseSelectionStudent/QueryCourseTable"
_dropcourse = "CourseReturnStudent/CourseReturnSave"
_baseerror = "Base/Error"

_stop_condition = ["课时冲突", "已选同组课程", "已选过且成绩合格"]
_stop_condition2 = ["已选此课程", "课时冲突", "已选同组课程", "已选过且成绩合格"]

# SSO Pubkey
_keystr = '''-----BEGIN PUBLIC KEY-----
    MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDl/aCgRl9f/4ON9MewoVnV58OLOU2ALBi2FKc5yIsfSpivKxe7A6FitJjHva3WpM7gvVOinMehp6if2UNIkbaN+plWf5IwqEVxsNZpeixc4GsbY9dXEk3WtRjwGSyDLySzEESH/kpJVoxO7ijRYqU+2oSRwTBNePOk1H+LRQokgQIDAQAB
    -----END PUBLIC KEY-----'''

def str_courseinfo(course:Courseinfo):
    return "%s(%s) by %s(%s) : %d/%d %s" % (
        course.coursename, course.courseid, course.teachername, course.teacherid, course.number, course.capacity, course.restriction)

def str_selectionresult(selection:Selectionresult):
    return "%s(%s) by %s(%s) : %s" % (
        selection.coursename, selection.courseid, selection.teachername, selection.teacherid, selection.msg)

def str_coursebaseinfo(info):
    return "%s(%s) by %s(%s)" % (info.coursename, info.courseid, info.teachername, info.teacherid)

def printnwarn(msg):
    printf(msg)
    logging.warning(msg)

def initconfig():  # write a default config
    config = configparser.ConfigParser(allow_no_value=True)
    config["Userinfo"] = {}
    config["Userinfo"]["user"] = ""
    config["Userinfo"]["password"] = ""
    config["Userinfo"]["encryptpassword"] = ""
    config["Settings"] = {}
    config["Settings"]["term"] = ""
    config["Settings"]["querydelay"] = "1.5"
    config["Settings"]["checkselectdelay"] = "5"
    config["Settings"]["warndiffcampus"] = "1"
    config["Settings"]["autoclearscreen"] = "1"
    config["Settings"]["keeplogs"] = "1"
    config["Settings"]["loglevel"] = "2"
    config["Courses"] = {}
    for i in range(1, 10):
        config["Courses"]["course%d" % i] = ""

    try:
        with open(CONFIGPATH, 'w', encoding="utf-8") as configfile:
            config.write(configfile, space_around_delimiters=False)
        print("Default config file is saved")
    except:
        print("Unable to initialize config")


def readconfig():  # read config from file
    config = configparser.ConfigParser(allow_no_value=True)
    try:
        config.read(CONFIGPATH, encoding="utf-8")
        userinfo = config["Userinfo"]
        settings = config["Settings"]
    except KeyError:
        print("Warning: Config is corrupted")
        initconfig()
        return
    courses = config["Courses"]
    global username, password, encryptedpassword, sterm
    global query_delay, chk_select_time_delay, warn_diff_campus, auto_cls, inputlist, keep_logs, logging_level
    # use global in order to modify global values
    username = userinfo.get("user", "")
    password = userinfo.get("password", "")
    encryptedpassword = userinfo.get("encryptpassword", "")
    sterm = settings.get("term", "")
    try:
        query_delay = settings.getfloat("querydelay", "1.5")
    except ValueError:
        print("Warning: config of querydelay is invalid, set to default..")
        query_delay = 1.5
    try:
        chk_select_time_delay = settings.getfloat("checkselectdelay", "5")
    except ValueError:
        print("Warning: config of checkselectdelay is invalid, set to default..")
        chk_select_time_delay = 5
    try:
        warn_diff_campus = bool(settings.getint("warndiffcampus", "1"))
    except ValueError:
        print("Warning: config of warndiffcampus is invalid, set to default..")
        warn_diff_campus = True
    try:
        auto_cls = bool(settings.getint("autoclearscreen", "1"))
    except ValueError:
        print("Warning: config of autoclearscreen is invalid, set to default..")
        auto_cls = True
    try:
        keep_logs = bool(settings.getint("keeplogs", "1"))
    except ValueError:
        print("Warning: config of keeplogs is invalid, set to default..")
        keep_logs = True
    try:
        logging_level = 10 * settings.getint("loglevel", "2")
        if not (10 <= logging_level <= 50):
            raise ValueError
    except ValueError:
        print("Warning: config of loglevel is invalid, set to default..")
        logging_level = 20
    i = 0
    while True:
        i += 1
        s = courses.get("course%d" % i, "")
        if s != "":
            a = s.split(",")
            if len(a) != 2 or len(a[0]) != 8 or len(a[1]) != 4:
                if len(a) != 4 or len(a[2]) != 8 or len(a[3]) != 4:
                    print(s + " is not a valid course format")
                    continue
            if len(a) == 2:
                s = s + ",null,null"
            inputlist.append(Courseitem._make(s.split(",")))
        else:
            break
    print("OK")


def writeepwd():  # write encrypted password to config
    config = configparser.ConfigParser(allow_no_value=True,comment_prefixes=(';'))
    config.read(CONFIGPATH,encoding="utf-8")
    config["Userinfo"]["user"] = username
    config["Userinfo"]["encryptpassword"] = encryptedpassword
    config["Userinfo"]["password"] = ""
    try:
        with open(CONFIGPATH, 'w', encoding="utf-8") as configfile:
            config.write(configfile, space_around_delimiters=False)
    except:
        print("Error: Unable to write config")


def writeterm():  # write current termid to config
    config = configparser.ConfigParser(allow_no_value=True,comment_prefixes=(';'))
    config.read(CONFIGPATH, encoding="utf-8")
    config["Settings"]["term"] = str(sterm)
    try:
        with open(CONFIGPATH, 'w', encoding="utf-8") as configfile:
            config.write(configfile, space_around_delimiters=False)
    except:
        print("Error: Unable to write config")


def clear():  # cross-platform clear screen function
    # for windows
    if os.name == 'nt':
        _ = os.system('cls')
    # for mac and linux
    else:
        _ = os.system('clear')


def encryptPass(passwd):
    pubkey = rsa.PublicKey.load_pkcs1_openssl_pem(_keystr.encode('utf-8'))
    encryptpwd = base64.b64encode(rsa.encrypt(passwd.encode('utf-8'), pubkey)).decode()
    return encryptpwd


def getTerms(text):  # analyze terms from text
    html = lxml.etree.HTML(text)
    termslist = html.xpath("//table/tr[@name='rowterm']")
    terms = []
    for term in termslist:
        termid = term.attrib["value"]
        name = term.xpath("./td/text()")[0].strip()
        terms.append(Termitem(termid, name))
    return terms


def deletecoursefromlist(cid, tid):  # delete an item from list
    global inputlist
    index = findcourseinlist(cid, tid, inputlist)
    if index != -1:
        del inputlist[index]
        logging.info("Delete course %s,%s from list" % (cid, tid))
    else:
        logging.critical("Unable to find course to delete")
        raise ValueError("Unexpected Result")


def findcourseinlist(cid, tid, listitem):  # find the item in a list given cid and tid
    for index, item in enumerate(listitem):
        if (item.courseid == cid) and (item.teacherid == tid):
            return index
    return -1


def findreplaceinlist(cid, tid):  # find the item in the inputlist given replacecid and replacetid
    for index, item in enumerate(inputlist):
        if (item.replacecid == cid) and (item.replacetid == tid):
            return index
    return -1


@retry(stop=stop_after_attempt(10), wait=wait_fixed(0.25))
def getCourseInfo(cid, tid, sess: requests.session):  # query course info by cid and tid
    params = {
        "PageIndex": 1,
        "PageSize": 1,
        "FunctionString": "Query",
        "CID": cid,
        "CourseName": "",
        "IsNotFull": "False",
        "CourseType": "B",
        "TeachNo": tid,
        "TeachName": "",
        "Enrolls": "",
        "Capacity1": "",
        "Capacity2": "",
        "CampusId": "",
        "CollegeId": "",
        "Credit": "",
        "TimeText": ""
    }
    count = 0
    while count < 5:
        try:
            r = sess.post(_baseurl + _querycourse, params, timeout=5)
            break
        except requests.exceptions.Timeout:
            reconnect()
            if count == 4:
                printf("网络重新连接失败了")
        count += 1

    if "未查询到符合条件的数据！" in r.text:
        raise RuntimeError(3, f"Course Not Exist")
    html = lxml.etree.HTML(r.text)
    a = 1
    starttime = time.time()
    while a == 1:
        print("尝试获取网页")
        try:
            td = html.xpath("//table[@class='tbllist']/tr/td")
            a = 2
        except:
            endtime = time.time()
            print(endtime - starttime)
            if (endtime - starttime >= 30):
                printf("网络炸了")
                time.sleep(20)
            html = lxml.etree.HTML(r.text)
    try:
        return Courseinfo(courseid=td[0].text.strip(),
                          coursename=td[1].text.strip(),
                          teacherid=td[3].text.strip(),
                          teachername=td[4].xpath("./span/text()")[0],
                          capacity=int(td[8].text.strip()),
                          number=int(td[9].text.strip()),
                          restriction=td[11].text.strip() if td[11].text else "")
    except:
        emsg = r.status_code
        if r.url.startswith(_baseurl+_baseerror):
            emsg = urllib.parse.unquote(r.url.replace(_baseurl+_baseerror+"?msg=",""))
        logging.warning('Error Occurred: %s' % emsg)
        logging.debug(r.text)
        time.sleep(0.5)
        return Courseinfo(courseid=cid,
                          coursename="XXX",
                          teacherid=tid,
                          teachername="XXX",
                          capacity=0,
                          number=0,
                          restriction="Error Occurred: %s Retry..." % emsg)


def canSelect(cinfo):  # judge whether a course can be selected
    if cinfo.restriction:
        return False
    # if cinfo.capacity==0:return False
    # if cinfo.capacity == cinfo.number:
    #    return False
    # if cinfo.capacity < cinfo.number:
    #    return False  # First round selection
    return True


@retry(stop=stop_after_attempt(10), wait=wait_fixed(0.25))
def checkDiffCampus(param, sess):
    r = sess.post(_baseurl + _diffcampus, param)
    if any(x in r.text for x in ["点击选择选课学期","未将对象引用设置到对象的实例"]):
        printf("Error: Did not select term!")
        logging.warning("System error when checkDiffCampus. Logged in elsewhere?")
        return
    else:
        if "ERROR" in r.text:
            printf("Something wrong. Please check your network")
            logging.warning("System error when checkDiffCampus. Network failure?")
    if "没有非本校区课程" not in r.text:
        printf("Warning: The location of some courses are in another campus")
        printf("Course Selection will proceed anyway")
        logging.warning("checkDiffCampus: The location of some courses are in another campus")
    return


@retry(stop=stop_after_attempt(10), wait=wait_fixed(0.25))
def returnCourse(courses, sess):  # return a list of courses
    datastr = ""
    for course in courses:
        datastr += ("&cids=" + course.replacecid)
    for course in courses:
        datastr += ("&tnos=" + course.replacetid)
    headers = {'Content-type': 'application/x-www-form-urlencoded; charset=UTF-8'}
    r = sess.post(_baseurl + _dropcourse, data=datastr[1:], headers=headers)
    while _termindex in r.url:
        printf("\nYou have logged in elsewhere:(  Need to select term first...")
        logging.warning("Return Course Failed. Retry selecting term")
        sess = selectTerm(sterm, sess, False)
        r = sess.post(_baseurl + _dropcourse, data=datastr[1:], headers=headers)
    return ("退课成功" in r.text) and ("无此教学班数据" not in r.text) and ("未选此教学班" not in r.text)
    # TODO: verify the result of each course


@retry(stop=stop_after_attempt(10), wait=wait_fixed(0.25))
def selectCourse(courses, sess):  # select a list of courses
    params = {}
    i = 0
    for course in courses:
        # if not canSelect(course):
        #    continue
        params["cids[%d]" % i] = course.courseid
        params["tnos[%d]" % i] = course.teacherid
        i += 1
    for j in range(i, 9):
        params["cids[%d]" % j] = ""
        params["tnos[%d]" % j] = ""
    if warn_diff_campus:
        checkDiffCampus(params, sess)
    r = sess.post(_baseurl + _selectcourse, params)
    while "未指定当前选课学期！" in r.text:
        printf("You have logged in elsewhere:(  Need to select term first...")
        logging.warning("Select Course Failed. Retry selecting term")
        sess = selectTerm(sterm, sess, False)
        r = sess.post(_baseurl + _selectcourse, params)
    html = lxml.etree.HTML(r.text)
    table_rows = html.xpath("//table/tr/td/..")
    if len(table_rows) <= 1:
        # Something wrong, select term first
        sess = selectTerm(sterm, sess, False)
        if not isSelectTime(sess):
            printf("Selection Time has ended:(\n\nQuitting...")
            logging.critical("Selection period appears to be ended")
            raise RuntimeError("Selection period appears to be ended")
        r = sess.post(_baseurl + _selectcourse, params)
        html = lxml.etree.HTML(r.text)
        table_rows = html.xpath("//table/tr/td/..")
        if len(table_rows) <= 1:  # retry one time
            printf("Something Wrong :(")
            logging.critical("Cannot analyze return results")
            logging.debug("EXTRA INFO: r.url = " + r.url)
            logging.debug("EXTRA INFO: r.text = " + r.text)
            raise RuntimeError("Cannot analyze return results")

    del table_rows[-1]  # Close Button
    result = []
    for tb_item in table_rows:
        tb_datas = tb_item.xpath("td/text()")
        tb_datas = [x.strip() for x in tb_datas]
        if len(tb_datas) == 6:
            item_result = Selectionresult(courseid=tb_datas[1],
                                          coursename=tb_datas[2],
                                          teacherid=tb_datas[3],
                                          teachername=tb_datas[4],
                                          msg=tb_datas[5],
                                          isSuccess="成功" in tb_datas[5])
            result.append(item_result)
        else:
            logging.critical("Cannot analyze return results")
            logging.debug("EXTRA INFO: r.url = " + r.url)
            logging.debug("EXTRA INFO: r.text = " + r.text)
            raise RuntimeError("Cannot analyze return results")

    return result


@retry(stop=stop_after_attempt(10), wait=wait_fixed(0.25))
def isSelectTime(sess):  # judge whether it is selection time
    r = sess.get(_baseurl + _fastinput)
    if "非本校区提示" in r.text:
        logging.info("Course selection has begun")
        return True
    else:
        return False


@retry(stop=stop_after_attempt(10), wait=wait_fixed(0.25))
def selectTerm(term, sess, dtips=True):  # select the term
    global sterm
    sterm = term
    r = sess.post(_baseurl + _termselect, {"termId": term})
    if "学生信息" in r.text and "未选择" not in r.text:
        print("-------------------------")
    else:
        if "切换选课学期" not in r.text:
            printf("Login Failed?")
            logging.critical("Select Term Failed: Login Failed?")
            raise RuntimeError(3, f"Select Term Failed")
        else:
            if "未选择" not in r.text:
                printf("Unexpected Error Occured. Are you Student?")
                logging.critical("Select Term Failed: User role is student?")
                raise RuntimeError(9, f"User seems not a student")
            else:
                printf("Unknown Error Occured. TermId invalid?")
                logging.critical("Select Term Failed: Invalid TermID?")
                raise RuntimeError(8, f"Select Term Failed")
    logging.info("Selected Term: %s" % term)
    if dtips:
        writeterm()
        print("Term info has been saved, to change it or select again, please delete the value in config file",
              end="\n\n")
    return sess


def login(username, encryptpwd):
    global sterm
    print("Logging in...")
    session = requests.Session()
    try:
        r = session.get(_baseurl)
    except Exception as emsg:
        printf(str(emsg))
        printf("\nUnable to connect:(\nPlease use VPN or check network settings")
        logging.error("ERROR in logging in: %s" % emsg)
        exit(1)
    if not r.url.startswith(
            ("https://oauth.shu.edu.cn/", "https://newsso.shu.edu.cn/")):
        logging.critical("Unexpected Result in redirected url: " + r.url)
        raise RuntimeError(1, f"Unexpected Result")
    request_data = {"username": username, "password": encryptpwd}
    r = session.post(r.url, request_data)
    if not r.url.endswith(_termindex):
        if "too many requests" in r.text:
            logging.critical("ERROR in logging in: Too may Requests")
            raise RuntimeError(2, f"Too many Requests, try again later")
        logging.error("Failed to login.")
        raise RuntimeError(2, f"Login Failed")
    else:
        print("Login Successful:" + username)
        logging.info("Login Sucessful")
        global encryptedpassword
        if encryptedpassword == "":
            tmp = input("Do you want to save encrypted credentials in config?[Y/N]:")
            while True:
                if tmp == "Y" or tmp == "y":
                    encryptedpassword = encryptPass(password)
                    writeepwd()
                    break
                else:
                    if tmp == "N" or tmp == "n":
                        break
                    else:
                        tmp = input("Please enter ""Y"" or ""N"" :")
        print("-------------------------")
        Termlist = getTerms(r.text)
        if len(Termlist) > 1:  # User Selection if exists multiple terms
            print("Available Terms:")
            i = 1
            for tmp in Termlist:
                print(str(i) + ': ' + tmp.name)
                if tmp.termid == sterm:
                    print("Selected Term: " + tmp.name)
                    return selectTerm(sterm, session)
                i += 1
            s = 0

            while not (1 <= s <= i - 1):
                s = int(input("Select Term[1-" + str(i - 1) + "]:"))
            print("Selected Term: " + Termlist[s - 1].name)
            return selectTerm(Termlist[s - 1].termid, session)
        else:  # Automatically Select the only term
            print("Selected Term: " + Termlist[0].name)
            return selectTerm(Termlist[0].termid, session)


count = 0
while count < 6:

    try:
        print("SCourseHelper V" + VER)
        print()
        print("FREE, Open Source on https://github.com/hidacow/SHU-CourseHelper")
        print()
        print()
        print("Reading Config...", end="")
        readconfig()
        print()
        if keep_logs == True:
            logging.basicConfig(filename=LOGPATH, format=LOG_FORMAT, datefmt=DATE_FORMAT, level=logging_level)
            print("Logging is ENABLED. Program logs can be found at %s\n" % LOGPATH)
        else:
            logging.disable(100)

        logging.info("SCourseHelper V%s started." % VER)
        if username == "":
            username = input("User:")
        else:
            print("User:%s" % username)
        if password == "" and encryptedpassword == "":
            password = getpass.getpass("Password:")

        if encryptedpassword != "":
            s = login(username, encryptedpassword)
        else:
            s = login(username, encryptPass(password))

        if not isSelectTime(s):
            i = 0
            print("Not Selection Time...Wait %.2f sec..." % chk_select_time_delay)
            logging.warning("Not Selection Time")
            while True:
                print("Retry Times: " + str(i))
                time.sleep(chk_select_time_delay)
                i += 1
                if isSelectTime(s):
                    break

        print("Selection Time OK", end="\n\n")
        if len(inputlist) == 0:
            i = 1
            print("Enter the courses in the config is recommended. See README for more info\n")

            print("Please enter the info of courses, enter nothing to finish")
            while True:
                a = input("Enter the course  id of course %d :" % i)
                if a == "":
                    if i > 1:
                        break
                    else:
                        print("You must enter at least 1 course")
                        continue
                if len(a) != 8:
                    print("Invalid input, please enter again")
                    continue
                b = input("Enter the teacher id of course %d :" % i)

                if b == "":
                    if i > 1:
                        break
                    else:
                        print("Incomplete information, please enter again")
                        continue
                if len(b) != 4:
                    print("Invalid input, please enter again")
                    continue
                c = input("Do you want to replace a course you have selected with this one?\n[Y/N(default)]:")
                while True:
                    if c == "Y" or c == "y":
                        d = input("Enter the course  id of the course to replace :")
                        if d == "":
                            print("Abort")
                            c = "n"
                            continue
                        if len(d) != 8:
                            print("Invalid input, please enter again")
                            continue
                        e = input("Enter the teacher id of the course to replace :")
                        if e == "":
                            print("Incomplete information, please enter again")
                            continue
                        if len(e) != 4:
                            print("Invalid input, please enter again")
                            continue
                        inputlist.append(Courseitem(a, b, d, e))
                        break
                    else:
                        if c == "N" or c == "n" or c == "":
                            inputlist.append(Courseitem(a, b, "null", "null"))
                            break
                        else:
                            c = input("Please enter ""Y"" or ""N"" :")
                i += 1

        SubmitList = []
        DropList = []
        i = 0
        send("开始了")
        while True:
            if i > 0:
                if auto_cls:
                    clear()
                print()
                print('#' * 50)
                print()
                print("Retry:%d" % i)
                SubmitList.clear()
                DropList.clear()

            print("Checking %d course(s)" % len(inputlist), end="\n\n")
            print("-------------------------")
            for item in inputlist:
                course = getCourseInfo(item.courseid, item.teacherid, s)
                print(str_courseinfo(course), end="")
                if canSelect(course):
                    print("... can be selected!!")
                    SubmitList.append(item)
                    if item.replacecid != "null":
                        DropList.append(item)
                        SubmitList.append(Courseitem(item.replacecid, item.replacetid, "backup",
                                                     "backup"))  # select it back in case of failure
                else:
                    print("")
            print("-------------------------", end="\n\n")

            if len(SubmitList) > 0:
                printf("Trying to select %d course(s)..." % (len(SubmitList) - len(DropList)), end="\n\n")
                logging.info("%d course(s) can be selected" % (len(SubmitList) - len(DropList)))
                dropsuccess = 0
                if len(DropList) > 0:  # Drop the replace courses first
                    printf("Need to drop %d course(s)..." % len(DropList), end="")
                    logging.info("%d course(s) need to be dropped first" % len(DropList))
                    if returnCourse(DropList, s):
                        printf("Success")
                        dropsuccess = 1
                    else:
                        printf("Failed, continue anyway")
                        logging.warning("Cannot to return some courses")
                        dropsuccess = -1

            print()
            result = selectCourse(SubmitList, s)
            for item in SubmitList:
                rid = findcourseinlist(item.courseid, item.teacherid, result)  # find in result
                selection = result[rid]
                if item.replacecid != "null" and item.replacecid != "backup":  # Has backup
                    rid2 = findcourseinlist(item.replacecid, item.replacetid, result)  # Find the result of backup selection
                    # if selection is success and backupselection is not success: replacement successful, delete from task
                    # if selection failed but backup selection is success: replacement not successful, continue loop
                    # if selection and backup both failed: continue loop
                    printf(str_selectionresult(selection))
                    logging.info("Target  Course %s" % str_selectionresult(selection))
                    if selection.isSuccess:
                        if not result[rid2].isSuccess:  # Best situation
                            printf("Previously selected course %s had been automatically returned" % str_coursebaseinfo(result[rid2]))
                            logging.info("Previously selected course %s had been automatically returned" % str_coursebaseinfo(result[rid2]))
                        else:  # Exceptional situation: User entered two courses that are not conflicting, TODO(maybe):return the unwanted course
                            printf(str_selectionresult(result[rid2]))
                            printf(
                                "The two courses are not conflicting, both are selected, you might want to manually return one of them")
                            logging.info("Backup Course %s" % str_selectionresult(result[rid2]))
                        deletecoursefromlist(selection.courseid, selection.teacherid)  # remove from task due to success
                    else:  # not selection.isSuccess
                        printf(str_selectionresult(result[rid2]))
                        logging.info("Backup Course %s" % str_selectionresult(result[rid2]))
                        if result[rid2].isSuccess:
                            printf("Course replacement failed, the course you previously selected had been selected back")
                            # if target course selection failed with certain reason, discontinue
                            if selection.isSuccess or any(x in selection.msg for x in _stop_condition2):
                                deletecoursefromlist(selection.courseid, selection.teacherid)
                                if "已选此课程" in selection.msg:
                                    printnwarn("Please return the course %s manually, and add it again" % selection.coursename)
                                if any(x in selection.msg for x in _stop_condition):
                                    printnwarn(
                                        "Please change courses conflicting with %s manually, and add it again" % selection.coursename)
                                printnwarn(
                                    "Due to unresolved conflicts in selecting the target course, the program will stop selecting this course")
                            else:
                                printf("The program will continue trying to replace the course")
                        else:  # Exceptional or Unfortunate situation: Both courses are dropped
                            if "无此教学班数据" in result[rid2].msg:
                                printnwarn("Invalid Return Course Data")
                                deletecoursefromlist(selection.courseid, selection.teacherid)
                                # remove original item first
                                inputlist.append(Courseitem(item.courseid, item.teacherid, "null", "null"))
                                logging.info("Add %s,%s to list" % (item.courseid, item.teacherid))
                                # add an item without replacement
                            else:
                                if any(x in selection.msg for x in _stop_condition2):
                                    if dropsuccess == 1:  # drop success
                                        printnwarn(
                                            "Seems impossible to replace course, please check selection strategy and retry")
                                        deletecoursefromlist(selection.courseid, selection.teacherid)  # discontinue
                                    if dropsuccess == -1 and ("已选此课程" in result[rid2].msg) or any(x in result[rid2].msg for x in _stop_condition):
                                        printnwarn("Seems unable to select the original course back, did you select it?")
                                        deletecoursefromlist(selection.courseid, selection.teacherid)  # discontinue
                                    else:
                                        if dropsuccess == -1:
                                            printf(
                                                "It seems that the error relates to failure in returning courses, the program will retry")
                                else:
                                    printf(
                                        "Unfortunately, failed to select both courses, trying to select either of the courses")
                                    deletecoursefromlist(selection.courseid, selection.teacherid)
                                    logging.warning("Cannot Select both course. Add %s,%s ; %s,%s to list" % (
                                        item.courseid, item.teacherid, item.replacecid, item.replacetid))
                                    # remove original item first
                                    inputlist.append(Courseitem(item.courseid, item.teacherid, "null", "null"))
                                    # add an item without replacement
                                    inputlist.append(Courseitem(item.replacecid, item.replacetid, "null", "null"))
                                    # add the original course to tasks
                else:
                    if item.replacecid != "backup":
                        printf(str_selectionresult(selection))
                        logging.info("Target  Course %s" % str_selectionresult(selection))
                        if selection.isSuccess or any(x in selection.msg for x in _stop_condition2):
                            deletecoursefromlist(selection.courseid, selection.teacherid)
                            # success or need user actions, discontinue
                            if "已选此课程" in selection.msg:
                                printnwarn("Please return the course %s manually, and add it again" % selection.coursename)
                            if any(x in selection.msg for x in _stop_condition):
                                printnwarn(
                                    "Please change courses conflicting with %s manually, and add it again" % selection.coursename)
                            printf(
                                "You may also edit the config to let the program automatically return conflicting courses")
                    # else is backup, ok to skip
                del result[rid]  # We don't need this result item anymore
                print()

                # Judge task progress
                if len(inputlist) == 0:
                    printf("Task done!")
                    logging.info("All Task Done!")
                    break
            else:
                print("No course can be selected...")

            print("%d course(s) remaining...Wait %.2f sec..." % (len(inputlist), query_delay))
            logging.debug("%d course(s) remaining" % len(inputlist))
            i += 1
            time.sleep(query_delay)
        logging.info("Program terminated normally.")
    except Exception as e:
        ans = ""
        for each in e.args:
            if type(each) is str:
                ans += each + '\n'
        printf("报错了，但仍然在继续运行:" + ans)
        time.sleep(60)
        count += 1
        if (count > 5):
            printf("报错五次了，不运行了")
            e = 2
