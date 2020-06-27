import json
import os
from datetime import datetime
import time
import calendar;
import hashlib
from flask import request
from flask import Flask
import math
import jwt
import boto3
from botocore.client import Config
from flask_cors import CORS
from flask_mysqldb import MySQL

# S3 buket Credentials

ACCESS_KEY_ID = 'AKIAI6NB5RRTIW3YYDDQ'
ACCESS_SECRET_KEY = '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'
BUCKET_NAME = 'quizzes-for-kid'


app = Flask(__name__)
CORS(app)

## Database Connection
app.config['MYSQL_HOST'] = 'database-flask.c8ez6rfgj511.us-east-2.rds.amazonaws.com'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root_123'
app.config['MYSQL_DB'] = 'padhantu-classes'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
mysql = MySQL(app)

## Upload Photo to S3 bucket
def uploadFileToS3(fileName, file):
    s3 = boto3.resource(
    's3',
    aws_access_key_id=ACCESS_KEY_ID,
    aws_secret_access_key=ACCESS_SECRET_KEY,
    config=Config(signature_version='s3v4')
    )
    s3.Bucket(BUCKET_NAME).put_object(Key=fileName, Body=file)


@app.route('/', methods=["GET"])
def hello():
    return "Hello World"

def md5_hash(string):
    hash = hashlib.md5()
    hash.update(string.encode('utf-8'))
    return hash.hexdigest()


def generate_salt():
    salt = os.urandom(16)
    return salt.hex()


# SignUp
@app.route('/signup',methods=['POST'])  
def signUp():
    name = request.headers.get('name')
    email = request.headers.get('email')
    password = request.headers.get('password')
    mobile = request.headers.get('mobile')
    created_at = datetime.fromtimestamp(calendar.timegm(time.gmtime()))
    flag = False
    password_salt = generate_salt()
    password_hash = md5_hash(password + password_salt)
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT * FROM users""")
    results = cursor.fetchall()
    for item in results:
        if str(email) == str(item["email"]):
            flag = True
            mysql.connection.commit()
            cursor.close()
    if flag == True:
        response = app.response_class(response=json.dumps({"message":"Already Exist","isValid":False}),status=422,mimetype='application/json')
        return response
    else:
        cursor.execute(
            """INSERT INTO users (username, email, mobile, password_hash, password_salt, sign_up_method, is_active, role, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """, (name, email,mobile,password_hash, password_salt,"NORMAL",True,"USER",created_at)
        )
        mysql.connection.commit()
        cursor.close()
        response = app.response_class(response=json.dumps({"message":"Sign Up Successfully","isValid":True}),status=200,mimetype='application/json')
        return response

# User Login
@app.route('/login', methods=["POST"])
def userLogin():
    email = request.headers.get("email")
    password = request.headers.get("password")
    isUserExist = False
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT * FROM users where email=(%s)""", [email])
    user_data = cursor.fetchone()
    if user_data:
        if str(user_data["password_hash"]) == str(md5_hash(password+user_data["password_salt"])):
            isUserExist = True

        if isUserExist:
            encoded_jwt = jwt.encode({"user_id":user_data["id"],"name":user_data["username"],"email":user_data["email"],"role":user_data["role"]}, 'secretkey', algorithm='HS256').decode("utf-8")
            response = app.response_class(response=json.dumps({"message":"Login Success","isValid":True,"token":encoded_jwt}),status=200,mimetype='application/json')
            return response
        else:
            response = app.response_class(response=json.dumps({"message":"Wrong Credential","isValid":False}),status=403,mimetype='application/json')
            return response


# Facebook Login
@app.route('/socialLogin', methods=["POST"])
def facebookLogin():
    uuid = request.json["uuid"]
    username = request.json["username"]
    userImgUrl = request.json["userImgUrl"]
    signInMethod = "social"
    print(uuid,username,userImgUrl)
    isUserExist = False
    cursor = mysql.connection.cursor()      
    if len(uuid) > 0:
        cursor.execute("""SELECT * FROM users where uuid=(%s)""", [uuid])
        exist_user_data = cursor.fetchone()
        if exist_user_data:
            isUserExist = True

        if isUserExist:
            return json.dumps({"isUserExist":isUserExist,"UserData":exist_user_data})
        else:
            cursor.execute("""INSERT INTO users(uuid,username,user_image_url,sign_in_method) VALUES(%s,%s,%s,%s)""", [uuid,username,userImgUrl,signInMethod])
            cursor.execute("""SELECT * FROM users where uuid=(%s)""", [uuid])
            user_data = cursor.fetchone()
            mysql.connection.commit()
            cursor.close()
            return json.dumps({"isUserExist":isUserExist,"UserData":user_data,"isValid": True,"message":"Login/Signup Successful"})
    else:
        return json.dumps("Something went wrong, Try Again")

    

if __name__ == "__main__":
    app.run(debug = "True",host="0.0.0.0",port=5000)
    # app.run(debug = "True")