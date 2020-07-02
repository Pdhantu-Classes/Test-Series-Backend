import json
import os
from datetime import datetime
import time
import calendar
import hashlib
from flask import request
from flask import Flask
import math
import jwt
import boto3
from botocore.client import Config
from flask_cors import CORS
from flask_mysqldb import MySQL
import razorpay
import string
import random
import hmac
import hashlib


# S3 buket Credential
ACCESS_KEY_ID = 'AKIAI6NB5RRTIW3YYDDQ'
ACCESS_SECRET_KEY = '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'
BUCKET_NAME = 'quizzes-for-kid'

# Razor Pay Credential
RAZORPAY_KEY = 'rzp_test_2QHPO79ACxzRQl'
RAZORPAY_SECRET = 'f9zvGhJn1MNBT070EUIh9e5o'


# Database Credential Development
MYSQL_HOST = 'database-flask.c8ez6rfgj511.us-east-2.rds.amazonaws.com'
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'root_123'
MYSQL_DB = 'padhantu-classes'
MYSQL_CURSORCLASS = 'DictCursor'


app = Flask(__name__)
CORS(app)

# Database Connection
app.config['MYSQL_HOST'] = MYSQL_HOST
app.config['MYSQL_USER'] = MYSQL_USER
app.config['MYSQL_PASSWORD'] = MYSQL_PASSWORD
app.config['MYSQL_DB'] = MYSQL_DB
app.config['MYSQL_CURSORCLASS'] = MYSQL_CURSORCLASS
mysql = MySQL(app)


razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY, RAZORPAY_SECRET))


def hmac_sha256(val):
    h = hmac.new(razorpay_client.encode("ASCII"), val.encode(
        "ASCII"), digestmod=hashlib.sha256).hexdigest()
    print(h)
    return h
# Upload Photo to S3 bucket


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

def randomString(stringLength=8):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))


# SignUp
@app.route('/signup', methods=['POST'])
def signUp():
    firstname = request.json['firstname']
    lastname = request.json['lastname']
    email = request.json['email']
    password = request.json['password']
    mobile = request.json['mobile']
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
        response = app.response_class(response=json.dumps(
            {"message": "Already Exist", "isValid": False}), status=200, mimetype='application/json')
        return response
    else:
        cursor.execute(
            """INSERT INTO users (firstname, lastname, email, mobile, password_hash, password_salt, sign_up_method, is_active, role, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """, (
                firstname, lastname, email, mobile, password_hash, password_salt, "NORMAL", True, "USER", created_at)
        )
        mysql.connection.commit()
        cursor.close()
        response = app.response_class(response=json.dumps(
            {"message": "Sign Up Successfully", "isValid": True}), status=200, mimetype='application/json')
        return response

# User Login
@app.route('/login', methods=["POST"])
def userLogin():
    login_value = request.json["login_value"]
    password = request.json["password"]
    isUserExist = False
    cursor = mysql.connection.cursor()
    cursor.execute(
        """SELECT * FROM users where email=(%s) OR mobile=(%s)""", [login_value, login_value])
    user_data = cursor.fetchone()
    response = {}
    if user_data:
        if str(user_data["password_hash"]) == str(md5_hash(password+user_data["password_salt"])):
            isUserExist = True

        if isUserExist:
            encoded_jwt = jwt.encode({"user_id": user_data["id"], "firstname": user_data["firstname"],"lastname":user_data["lastname"],"mobile":user_data["mobile"],
                                      "email": user_data["email"], "role": user_data["role"]}, 'secretkey', algorithm='HS256').decode("utf-8")
            response = app.response_class(response=json.dumps(
                {"message": "Login Success", "isValid": True, "token": encoded_jwt}), status=200, mimetype='application/json')
            return response
        else:
            response = app.response_class(response=json.dumps(
                {"message": "Wrong Credential", "isValid": False}), status=403, mimetype='application/json')
            return response
    else:
        response =app.response_class(response=json.dumps({"message":"User do not exists, Please sign up"}),status= 404, mimetype='application/json')
        return response


# Facebook Login
@app.route('/socialLogin', methods=["POST"])
def facebookLogin():
    uuid = request.json["uuid"]
    username = request.json["username"]
    userImgUrl = request.json["userImgUrl"]
    signInMethod = "social"
    print(uuid, username, userImgUrl)
    isUserExist = False
    cursor = mysql.connection.cursor()
    if len(uuid) > 0:
        cursor.execute("""SELECT * FROM users where uuid=(%s)""", [uuid])
        exist_user_data = cursor.fetchone()
        if exist_user_data:
            isUserExist = True

        if isUserExist:
            return json.dumps({"isUserExist": isUserExist, "UserData": exist_user_data})
        else:
            cursor.execute("""INSERT INTO users(uuid,username,user_image_url,sign_in_method) VALUES(%s,%s,%s,%s)""", [
                           uuid, username, userImgUrl, signInMethod])
            cursor.execute("""SELECT * FROM users where uuid=(%s)""", [uuid])
            user_data = cursor.fetchone()
            mysql.connection.commit()
            cursor.close()
            return json.dumps({"isUserExist": isUserExist, "UserData": user_data, "isValid": True, "message": "Login/Signup Successful"})
    else:
        return json.dumps("Something went wrong, Try Again")



@app.route('/createOrder', methods=['POST'])
def create_app():
    paye_id = randomString(10)
    order_amount = 500 * 100
    order_currency = 'INR'
    order_receipt = 'order_'+paye_id
    razorId = razorpay_client.order.create(
        amount=order_amount, currency=order_currency, receipt=order_receipt, payment_capture='0')
    return json.dumps(razorId["id"])


@app.route('/verifyRazorpaySucces', methods=['POST'])
def verify_payment():
    request_order_id = request.json["order_id"]
    request_payment_id = request.json["payment_id"]
    request_signature = request.json["singnature"]

    generated_signature = hmac_sha256(request_order_id+ "|" + request_payment_id)

    if(generated_signature == request_signature):
        return json.dumps({"isSuccess": True})
    else:
        return json.dumps({"isSuccess": False})



@app.route('/upload-image', methods=["POST"])
def uploadImage():
    isUpload = False
    response = {}
    user_id = request.headers.get("user_id")
    file = request.files["file"]
    seconds = str(time.time()).replace(".","")
    newFile = "images/"+seconds + "-" + file.filename
    uploadFileToS3(newFile, file)
    image_url = 'https://quizzes-for-kid.s3.us-east-2.amazonaws.com/'+newFile
    cursor = mysql.connection.cursor()
    cursor.execute("""UPDATE users SET image_url =(%s) where id=(%s)""", [image_url,user_id])
    mysql.connection.commit()
    cursor.close()
    isUpload = True
    response["isUpload"] = isUpload
    response["imageUrl"] = image_url
    return json.dumps(response)



@app.route('/isUserRegister/<int:user_id>', methods=["GET"])
def isUserRegister(user_id):
    cursor = mysql.connection.cursor()
    isValid = False
    cursor.execute("""SELECT * FROM users where id=(%s)""", [user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    if result["whatsapp"] and result["graduation_year"] and result["preparing_for"]:
        isValid = True
    response =app.response_class(response=json.dumps({"message":"User details exist","isValid":isValid}),status= 200, mimetype='application/json')
    return response



@app.route('/userDetails/<int:user_id>', methods=["GET"])
def getUserDetails(user_id):
    response_data = {}
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT * FROM users where id=(%s)""", [user_id])
    result = cursor.fetchone()
    if result:
        response_data["user_id"] = result["id"]
        response_data["firstname"] = result["firstname"]
        response_data["lastname"] = result["lastname"]
        response_data["email"] = result["email"]
        response_data["mobile"] = result["mobile"]        
        response_data["image_url"] = result["image_url"]
        response_data["role"] = result["role"]
        response_data["whatsapp"] = result["whatsapp"]
        response_data["graduation_year"] = result["graduation_year"]
        response_data["preparing_for"] = result["preparing_for"]
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"User details exist","user_data":response_data}),status= 200, mimetype='application/json')
    return response

@app.route('/userDetails/<int:user_id>', methods=["PUT"])
def pstUserDetails(user_id):
    whatsapp = request.json["whatsapp"]
    graduation_year = request.json["graduation_year"]
    course = request.json["course"]
    cursor = mysql.connection.cursor()
    cursor.execute("""UPDATE users SET whatsapp =(%s), graduation_year=(%s), preparing_for=(%s) where id=(%s)""", [whatsapp,graduation_year,course,user_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"User Data Added Successfully"}),status= 200, mimetype='application/json')
    return response

if __name__ == "__main__":
    app.run(debug="True", host="0.0.0.0", port=5000)
    # app.run(debug = "True")
