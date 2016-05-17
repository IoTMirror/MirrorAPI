import os
import uuid
import requests

from functools import wraps
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import PrimaryKeyConstraint

home_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ["DATABASE_URL"]
app.debug = True
db = SQLAlchemy(app)
request_headers = {"Authorization": os.environ["AUTH"]}

twitter_url = os.environ["TWITTER_URL"]
google_url = os.environ["GOOGLE_URL"]


class IdUserBinding(db.Model):
    __tablename__ = 'device_user'
    __table_args__ = (PrimaryKeyConstraint('device_id', 'user_id'),)
    device_id = db.Column(db.Integer)
    user_id = db.Column(db.Integer)

    def __init__(self, user_id, device_id):
        self.user_id = user_id
        self.device_id = device_id


class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(32))

    def __init__(self, user_id, token):
        self.id = user_id
        self.token = token


class UserConfig(db.Model):
    __tablename__ = 'Config'
    id = db.Column(db.Integer, primary_key=True)
    twitter_x = db.Column(db.Integer)
    twitter_y = db.Column(db.Integer)
    twitter_w = db.Column(db.Integer)
    twitter_h = db.Column(db.Integer)

    gmail_x = db.Column(db.Integer)
    gmail_y = db.Column(db.Integer)
    gmail_w = db.Column(db.Integer)
    gmail_h = db.Column(db.Integer)

    tasks_x = db.Column(db.Integer)
    tasks_y = db.Column(db.Integer)
    tasks_w = db.Column(db.Integer)
    tasks_h = db.Column(db.Integer)


def twitter_logged_in(user_id):
    url = "{}users/{}".format(twitter_url, user_id)
    resp = requests.get(url, headers=request_headers)
    return resp.status_code is 200


def google_logged_in(user_id):
    resp = requests.get("{}users/{}".format(google_url, user_id), headers=request_headers)
    return resp.status_code is 200

def load_session(token):
    return Session.query.filter_by(token=token).first()


def send_new_session_notification(device_id):
    request_body = jsonify({"mirrorID": device_id})
    return 12345


def confirm_face_recognition(token, recognition_token):
    request_body = jsonify({'token': token, 'recognition_token': recognition_token})
    return 1


recognition_service_url = "http://localhost"


@app.route("/login/start_session", methods=['POST'])
def login_start_session():
    body = request.get_json()
    if 'DeviceId' not in body:
        return jsonify({'error': 'DeviceId missing'}), 401

    device_id = body['DeviceId']
    users_bound = [e.user_id for e in IdUserBinding.query.filter_by(device_id=device_id)]
    session_token = send_new_session_notification(device_id)

    return jsonify({'LoginToken': session_token}), 200


@app.route("/login/confirm", methods=['POST'])
def login_confirm_session():
    body = request.get_json()
    if 'LoginToken' not in body:
        return jsonify({'error': 'Token missing'}), 401
    if 'RecognitionToken' not in body:
        return jsonify({'error': 'RecognitionToken missing'}), 401

    token = body['LoginToken']
    recognition_token = body['RecognitionToken']

    user_id = confirm_face_recognition(token, recognition_token)
    if user_id is -1:
        return jsonify({'error': 'Invalid token'}), 401

    login_session_token = uuid.uuid4().hex
    ses = Session.query.get(user_id)
    if ses:
        ses.token = login_session_token
    else:
        ses = Session(user_id, login_session_token)
    db.session.add(ses)
    db.session.commit()
    config = UserConfig.query.get(user_id)

    widgets = []
    google_actove = google_logged_in(user_id)
    if config.twitter_w > 0 and twitter_logged_in(user_id):
        widgets.append({
            "WidgetName": "Twitter",
            "WidgetType": "Small",
            "WidgetPosition": {
                "X": config.twitter_x,
                "Y": config.twitter_y
            },
            "WidgetSize": {
                "X": config.twitter_w,
                "Y": config.twitter_h
            }
        })
    if config.gmail_w > 0 and google_active:
        widgets.append({
            "WidgetName": "Gmail",
            "WidgetType": "Small",
            "WidgetPosition": {
                "X": config.gmail_x,
                "Y": config.gmail_y
            },
            "WidgetSize": {
                "X": config.gmail_w,
                "Y": config.gmail_h
            }
        })
    if config.tasks_w > 0 and google_active:
        widgets.append({
            "WidgetName": "Tasks",
            "WidgetType": "Small",
            "WidgetPosition": {
                "X": config.tasks_x,
                "Y": config.tasks_y
            },
            "WidgetSize": {
                "X": config.tasks_w,
                "Y": config.tasks_h
            }
        })
    return jsonify({'Token': login_session_token, 'Widgets': widgets})


def requires_login_get(f):
    @wraps(f)
    def inner():
        if "token" not in request.args:
            return jsonify({"error": "token missing"})
        token = request.args["token"]
        session = load_session(token)
        if not session:
            return jsonify({"error": "Not logged in"})
        return f(session.id)
    return inner


def requires_login_post(f):
    @wraps(f)
    def inner():
        body = request.get_json()
        if "token" not in body:
            return jsonify({"error": "token missing"}), 400
        session = load_session(body["token"])
        if not session:
            return jsonify({"error": "Not logged in"})
        return f(session.id)
    return inner


@app.route("/logout", methods=['POST'])
def logout():
    body = request.get_json()
    token = body['Token']
    session = load_session(token)
    if not session:
        return jsonify({'Success': 'False', 'Reason': 'Not logged in'})
    db.session.delete(session)
    db.session.commit()

    return jsonify({'Success': "true"})


@app.route("/test", methods=['POST'])
@requires_login_post
def test(user_id):
    return jsonify({'Status': "Logged in"})


@app.route("/facebook", methods=['GET'])
@requires_login_get
def facebook(user_id):
    return '{"data": "placeholder"}'


@app.route("/twitter", methods=['GET'])
@requires_login_get
def twitter(user_id):
    url = "{0}users/{1}/home_timeline".format(twitter_url, user_id)
    resp = requests.get(url, headers=request_headers)
    if resp.status_code == 200:
        return resp.content
    else:
        return jsonify({"error": resp.content}), resp.status_code


@app.route("/tasks", methods=['GET'])
@requires_login_get
def task_list(user_id):
    url = "{0}users/{1}/tasks".format(google_url, user_id)
    resp = requests.get(url, headers=request_headers)
    if False and resp.status_code == 200:
        return resp.content
    else:
        return jsonify({"error": resp.content}), resp.status_code


@app.route("/gmail", methods=['GET'])
@requires_login_get
def gmail(user_id):
    url = "{0}users/{1}/emails/inbox".format(google_url, user_id)
    resp = requests.get(url, headers=request_headers)
    if resp.status_code == 200:
        return resp.content
    else:
        return jsonify({"error": resp.content}), resp.status_code


if __name__ == "__main__":
    app.run()
