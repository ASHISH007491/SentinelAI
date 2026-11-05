"""Sample vulnerable code for the SentinelAI Code Review workflow (synthetic)."""
import hashlib
import os
import pickle
import sqlite3

from flask import Flask, request

app = Flask(__name__)
db = sqlite3.connect("app.db", check_same_thread=False)


@app.route("/user")
def get_user():
    # CWE-89: SQL injection via string concatenation
    uid = request.args["id"]
    return db.execute("SELECT * FROM users WHERE id = " + uid).fetchall()


@app.route("/ping")
def ping():
    # CWE-78: OS command injection
    host = request.args["host"]
    return os.popen("ping -c1 " + host).read()


@app.route("/load", methods=["POST"])
def load():
    # CWE-502: deserialisation of untrusted data
    return str(pickle.loads(request.data))


def store_password(pw: str) -> str:
    # CWE-327: weak hashing algorithm
    return hashlib.md5(pw.encode()).hexdigest()


@app.route("/file")
def read_file():
    # CWE-22: path traversal
    name = request.args["f"]
    return open(os.path.join("/data", name)).read()
