import json
import time

from flask import Flask, make_response, render_template, request, redirect, url_for
from flask_restful import Resource, Api
from pymongo import MongoClient
from datetime import date
import random

server = Flask(__name__)
api = Api(server)
mongoClient = MongoClient('localhost', 27017)
db = mongoClient.csr
user_collection = db.users
data_collection = db.data
topics = []
available_session_ids = []
sessions = {}
topics = []
quiz_sessions = {}

def create_user(username, password):
    user_collection.insert_one({
        "username": username,
        "password": password,
        "questions": 0,
        "correct_questions": 0,
        "questions_Cyber Security": 0,
        "correct_questions_Cyber Security": 0
    })

class Session:
    def __init__(self, account, ping_time, expire_time, auth_key):
        self.account = account
        self.ping_time = ping_time
        self.expire_time = expire_time
        self.auth_key = auth_key


class Quiz:
    def __init__(self, questions, topic_name):
        self.questions = questions
        self.topic_name = topic_name
        self.question = 0
        self.correct = 0

def update_topics():
    topics.clear()
    for x in data_collection.find():
        if (x["Type"] == "Topic" and x["Enabled"] == "True"):
            topics.append(x["Name"])

def get_questions(topic_id):
    questions = []
    topic_questions = []
    for x in data_collection.find():
        if (x["Type"] == "Question" and x["Topic"] == topic_id):
            topic_questions.append(x)
    for x in range(5):
        random_question = topic_questions[random.randint(0, len(topic_questions) - 1)]
        questions.append(random_question)
        topic_questions.remove(random_question)
    return questions


def update_profile(profile):
    for x in user_collection.find():
        if x["username"] == profile["username"]:
            user_collection.delete_one(x)
    user_collection.insert_one(profile)

def delete_profile(profile):
    for x in user_collection.find():
        if x["username"] == profile["username"]:
            user_collection.delete_one(x)


def free_sessions():
    for key in list(sessions):
        value = sessions[key]
        if (round(time.time()) - value.ping_time >= value.expire_time):
            available_session_ids.append(key)
            del sessions[key]


def get_session(sessionID, auth_key):
    for key in sessions:
        value = sessions[key]
        if (key == sessionID and float(auth_key) == float(value.auth_key)):
            return value
    return None


def try_login(username, password):
    for x in user_collection.find():
        if str(x["username"]).lower() == str(username).lower():
            if str(x["password"]) == str(password):
                return x
    return None


def question_answer(topic, account):
    account["questions"] = int(account["questions"]) + 1
    account["questions_" + topic] = int(account["questions_" + topic]) + 1
    today = date.today().strftime("%b-%d-%Y")
    if (today in account.keys()):
        account[today] = account[today] + 1
        return
    account[today] = 1


def question_answer_correct(topic, account):
    account["correct_questions"] = int(account["correct_questions"]) + 1
    account["correct_questions_" + topic] = int(account["correct_questions_" + topic]) + 1

@server.route('/api/v1/', methods=['POST'])
def handle_api_request():
    free_sessions()
    client_sessionID = request.cookies.get('sessionID')
    auth_key = request.cookies.get('key')
    if (client_sessionID is None or auth_key is None):
        return {"Status": "fail"}
    session = get_session(float(client_sessionID), float(auth_key))
    if (session is None):
        return {"Status": "fail"}
    d = json.loads(request.data)
    if (d["action"] == "sign_out"):
        del sessions[float(client_sessionID)]
        return {"Status": "success"}
    if (d["action"] == "change_password"):
        if (d["old_password"] != session.account["password"]):
            return {
                "Status": "fail",
                "fail_reason": "old_password"
            }
        if (len(d["new_password"]) < 6):
            return {
                "Status": "fail",
                "fail_reason": "password_laws"
            }
        session.account["password"] = d["new_password"]
        update_profile(session.account)
        del sessions[float(client_sessionID)]
        return {
            "Status": "success",
            "fail_reason": "none"
        }
    if (d["action"] == "create_user"):
        if (session.account["username"] != "William"):
            return {
                "Status": "fail",
                "fail_reason": "permission"
            }
        for x in user_collection.find():
            if (x["username"].lower() == d["username"].lower()):
                return {
                    "Status": "fail",
                    "fail_reason": "exists"
                }
        create_user(d["username"], d["username"])
        return {
            "Status": "success",
            "fail_reason": "none"
        }
    if (d["action"] == "other_change_password"):
        if (session.account["username"] != "William"):
            return {
                "Status": "fail",
                "fail_reason": "permission"
            }
        for x in user_collection.find():
            if (x["username"].lower() == d["username"].lower()):
                user_profile = x
                user_profile["password"] = d["new_password"]
                update_profile(user_profile)
                return {
                    "Status": "success",
                    "fail_reason": "none"
                }
        return {
            "Status": "fail",
            "fail_reason": "user_not_found"
        }
    if (d["action"] == "delete_user"):
        if (session.account["username"] != "William"):
            return {
                "Status": "fail",
                "fail_reason": "permission"
            }
        for x in user_collection.find():
            if (x["username"].lower() == d["username"].lower()):
                delete_profile(x)
                return {
                    "Status": "success",
                    "fail_reason": "none"
                }
        return {
            "Status": "fail",
            "fail_reason": "user_not_found"
        }
    if (d["action"] == "get_users"):
        if (session.account["username"] != "William"):
            return {
                "Status": "fail",
                "fail_reason": "permission"
            }
        users = []
        for x in user_collection.find():
            if x["questions"] == 0:
                users.append({
                    "username": x["username"],
                    "questions": x["questions"],
                    "correct_questions": x["correct_questions"],
                    "accuracy": "100%"
                })
            else:
                users.append({
                    "username": x["username"],
                    "questions": x["questions"],
                    "correct_questions": x["correct_questions"],
                    "accuracy": round((x["correct_questions"] / x["questions"]) * 100) + "%"
                })
        return {
            "Status": "success",
            "fail_reason": "none",
            "result": users
        }
    if (d["action"] == "quiz_answer"):
        quiz_session = quiz_sessions[client_sessionID]
        if (quiz_session is None):
            return {
                "Status": "fail",
                "fail_reason": "no_quiz_session"
            }
        question = quiz_session.questions[quiz_session.question]
        correct_answer_index = question["Answer"]
        correct_answer = question[correct_answer_index]
        client_answer = d["Answer"]
        question_answer(quiz_session.topic_name, session.account)
        quiz_session.question = quiz_session.question + 1
        if (client_answer != correct_answer):
            update_profile(session.account)
            return {
                "Status": "success",
                "fail_reason": "none",
                "question_result": "incorrect",
                "correct_answer": correct_answer
            }
        question_answer_correct(quiz_session.topic_name, session.account)
        update_profile(session.account)
        quiz_session.correct = quiz_session.correct + 1
        return {
            "Status": "success",
            "fail_reason": "none",
            "question_result": "correct"
        }
    if (d["action"] == "quiz_question"):
        quiz_session = quiz_sessions[client_sessionID]
        if (quiz_session is None):
            return {
                "Status": "fail",
                "fail_reason": "no_quiz_session"
            }
        if quiz_session.question > 4:
            return {
                "Status": "fail",
                "fail_reason": "quiz_session_expired"
            }
        q = quiz_sessions[client_sessionID]
        options = ["1", "2", "3", "4"]
        a = options.pop(random.randint(0, len(options) - 1))
        b = options.pop(random.randint(0, len(options) - 1))
        c = options.pop(random.randint(0, len(options) - 1))
        d = options.pop(random.randint(0, len(options) - 1))
        current_question = q.questions[q.question]
        return {
            "Status": "success",
            "question": current_question["Question"] + " (" + str(q.question + 1) + "/5)",
            "A": current_question[a],
            "B": current_question[b],
            "C": current_question[c],
            "D": current_question[d]
        }


@server.route('/api/login/', methods=['POST'])
def handle_auth():
    d = json.loads(request.data)
    username = d["username"]
    password = d["password"]
    if not username is None and not password is None:
        result = try_login(username, password);
        if result is not None:
            listIndex = random.randint(0, len(available_session_ids))
            sessionId = available_session_ids[listIndex]
            key = random.randint(0, 9e+50)
            available_session_ids.pop(listIndex)
            now = round(time.time())
            expire = 900
            sessions[sessionId] = Session(result, now, expire, key)
            return {"login": "ok", "sessionID": str(sessionId), "key": key}
        else:
            return {"login": "fail"}
    else:
        return ("bad_info")

@server.route('/quiz/finish/')
def quiz_finish():
    free_sessions()
    client_sessionID = request.cookies.get('sessionID')
    auth_key = request.cookies.get('key')
    if (client_sessionID is None or auth_key is None):
        return redirect(url_for('login'))
    session = get_session(float(client_sessionID), float(auth_key))
    if (session is None):
        return redirect(url_for('login'))
    if client_sessionID not in quiz_sessions.keys():
        return redirect(url_for("dashboard"))
    q = quiz_sessions[client_sessionID]
    if (q.question < 5):
        return redirect(url_for("dashboard"))
    return make_response(
        render_template('quiz_finish.html', topic=q.topic_name, correct=(str(q.correct) + "/" + str(q.question)), accuracy=(str(q.correct / q.question * 100)) + "%"))

@server.route('/admin/')
def admin_panel():
    free_sessions()
    client_sessionID = request.cookies.get('sessionID')
    auth_key = request.cookies.get('key')
    if (client_sessionID is None or auth_key is None):
        return redirect(url_for('login'))
    session = get_session(float(client_sessionID), float(auth_key))
    if (session is None):
        return redirect(url_for('login'))
    if (session.account["username"] != "William"):
        return redirect(url_for('dashboard'))
    return make_response(
        render_template('admin.html'))

@server.route('/admin/users/')
def admin_users():
    free_sessions()
    client_sessionID = request.cookies.get('sessionID')
    auth_key = request.cookies.get('key')
    if (client_sessionID is None or auth_key is None):
        return redirect(url_for('login'))
    session = get_session(float(client_sessionID), float(auth_key))
    if (session is None):
        return redirect(url_for('login'))
    if (session.account["username"] != "William"):
        return redirect(url_for('dashboard'))
    return make_response(
        render_template('users.html'))


@server.route('/dashboard/')
def dashboard():
    free_sessions()
    client_sessionID = request.cookies.get('sessionID')
    auth_key = request.cookies.get('key')
    if (client_sessionID is None or auth_key is None):
        return redirect(url_for('login'))
    session = get_session(float(client_sessionID), float(auth_key))
    if (session is None):
        return redirect(url_for('login'))
    today = date.today().strftime("%b-%d-%Y")
    if not today in session.account.keys():
        session.account[today] = 0
    return make_response(
        render_template('dashboard.html', username=session.account["username"], questions=str(session.account[today])))


@server.route('/quiz/')
def quiz():
    free_sessions()
    client_sessionID = request.cookies.get('sessionID')
    auth_key = request.cookies.get('key')
    if (client_sessionID is None or auth_key is None):
        return redirect(url_for('login'))
    session = get_session(float(client_sessionID), float(auth_key))
    if (session is None):
        return redirect(url_for('login'))
    if client_sessionID in quiz_sessions.keys() and quiz_sessions[client_sessionID].question < 5:
        q = quiz_sessions[client_sessionID]
        options = ["1", "2", "3", "4"]
        a = options.pop(random.randint(0, len(options) - 1))
        b = options.pop(random.randint(0, len(options) - 1))
        c = options.pop(random.randint(0, len(options) - 1))
        d = options.pop(random.randint(0, len(options) - 1))
        current_question = q.questions[q.question]
        return make_response(
            render_template('quiz.html', Question=(current_question["Question"] + " (" + str(q.question + 1) + "/5)"),
                            A=current_question[a],
                            B=current_question[b],
                            C=current_question[c],
                            D=current_question[d],
                            Topic=q.topic_name))
    update_topics()
    random_topic = topics[random.randint(0, len(topics) - 1)]
    quiz_sessions[client_sessionID] = Quiz(get_questions(random_topic), random_topic)
    q = quiz_sessions[client_sessionID]
    options = ["1", "2", "3", "4"]
    a = options.pop(random.randint(0, len(options) - 1))
    b = options.pop(random.randint(0, len(options) - 1))
    c = options.pop(random.randint(0, len(options) - 1))
    d = options.pop(random.randint(0, len(options) - 1))
    first_question = q.questions[q.question]
    return make_response(
        render_template('quiz.html', Question=(first_question["Question"] + " (" + str(q.question + 1) + "/5)"),
                        A=first_question[a],
                        B=first_question[b],
                        C=first_question[c],
                        D=first_question[d],
                        Topic=q.topic_name))


@server.route('/options/password/')
def change_password():
    free_sessions()
    client_sessionID = request.cookies.get('sessionID')
    auth_key = request.cookies.get('key')
    if (client_sessionID is None or auth_key is None):
        return redirect(url_for('login'))
    session = get_session(float(client_sessionID), float(auth_key))
    if (session is None):
        return redirect(url_for('login'))
    return make_response(render_template('changepassword.html'))


@server.route('/options/')
def options():
    free_sessions()
    client_sessionID = request.cookies.get('sessionID')
    auth_key = request.cookies.get('key')
    if (client_sessionID is None or auth_key is None):
        return redirect(url_for('login'))
    session = get_session(float(client_sessionID), float(auth_key))
    if (session is None):
        return redirect(url_for('login'))
    return make_response(render_template('options.html', username=session.account["username"]))


@server.route('/')
def load_site():
    return redirect(url_for('login'))


@server.route('/login/')
def login():
    free_sessions()
    client_sessionID = request.cookies.get("sessionID")
    key = request.cookies.get("key")
    if (client_sessionID is not None and key is not None):
        session = get_session(float(client_sessionID), float(key))
        if (session is not None):
            return redirect(url_for('dashboard'))
    if request.args.get("failed", "false") == "true":
        return make_response(render_template('login_incorrect.html'))
    return make_response(render_template('login.html'))


@server.route('/mobile/login/')
def mobile_login():
    return make_response(render_template('mobile/login.html'))


@server.route('/loginwrong')
def wrong():
    return make_response(render_template('login_incorrect.html'))

class user:
    def __init__(self, username, password):
        user.username = username
        user.password = password


if __name__ == '__main__':
    for x in range(9999999):
        available_session_ids.append(x)
    update_topics()
    server.run()
