"""Sample SAFE code for the Code Review workflow (should produce no findings)."""
import sqlite3

import bcrypt
from flask import Flask, jsonify, request

app = Flask(__name__)
db = sqlite3.connect("app.db", check_same_thread=False)


@app.route("/user")
def get_user():
    uid = request.args["id"]
    rows = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchall()  # parameterised
    return jsonify(rows)


def store_password(pw: str) -> bytes:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt())  # strong hashing
