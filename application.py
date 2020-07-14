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

# Test Razor Pay Credential
# RAZORPAY_KEY = 'rzp_test_2QHPO79ACxzRQl'
# RAZORPAY_SECRET = 'f9zvGhJn1MNBT070EUIh9e5o'

# Live  Razor Pay Credential
RAZORPAY_KEY = 'rzp_live_DjZ6EChEMzly9v'
RAZORPAY_SECRET = 'CfgHyNIXwyyDF1KL9KbrnSW4'


# Database Credential Development
MYSQL_HOST = 'database-pdhantu.cqa6f6gkxqbj.us-east-2.rds.amazonaws.com'
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'root_123'
# MYSQL_DB = 'pdhantu-dev'
MYSQL_DB = 'pdhantu-prod'
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
    h = hmac.new(RAZORPAY_SECRET.encode("ASCII"), val.encode(
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
            print(user_data)
            encoded_jwt = jwt.encode({"user_id": user_data["id"], "firstname": user_data["firstname"],"lastname":user_data["lastname"],"mobile":user_data["mobile"],
                                      "email": user_data["email"], "role": user_data["role"]}, 'secretkey', algorithm='HS256').decode("utf-8")
            response = app.response_class(response=json.dumps(
                {"message": "Login Success", "isValid": True, "token": encoded_jwt, "image_url": user_data["image_url"]}), status=200, mimetype='application/json')
            return response
        else:
            response = app.response_class(response=json.dumps(
                {"message": "Wrong Credential", "isValid": False}), status=200, mimetype='application/json')
            return response
    else:
        response =app.response_class(response=json.dumps({"message":"User do not exists, Please sign up"}),status= 200, mimetype='application/json')
        return response

# User Forget Password
@app.route('/forgetPassword', methods=["POST"])
def forgetPassword():
    email = request.json["email"]
    mobile = request.json["mobile"]
    isUserExist = False
    cursor = mysql.connection.cursor()
    cursor.execute(
        """SELECT * FROM users where email=(%s) AND mobile=(%s)""", [email, mobile])
    user_data = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    print(user_data)
    if user_data:
        isUserExist = True
    if isUserExist:
        response = app.response_class(response=json.dumps({"message": "Please Enter New Password", "isValid": True, "user_id": user_data["id"]}), status=200, mimetype='application/json')
        return response
    else:
        response = app.response_class(response=json.dumps({"message": "Please Enter Valid Details", "isValid": False}), status=200, mimetype='application/json')
        return response

# User Change Password
@app.route('/changePassword', methods=["PUT"])
def changePassword():
    user_id = request.json["user_id"]
    password = request.json["password"]
    password_salt = generate_salt()
    password_hash = md5_hash(password + password_salt)
    cursor = mysql.connection.cursor()
    cursor.execute("""UPDATE users SET password_hash = (%s), password_salt = (%s) where id = (%s)""", [password_hash,password_salt,user_id])
    mysql.connection.commit()
    cursor.close()
    response = app.response_class(response=json.dumps({"message": "Password Change Successfully", "isValid": True}), status=200, mimetype='application/json')
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
    order_amount = 240 * 100
    order_currency = 'INR'
    order_receipt = 'order_'+paye_id
    razorId = razorpay_client.order.create(
        amount=order_amount, currency=order_currency, receipt=order_receipt, payment_capture='1')
    return json.dumps(razorId["id"])


@app.route('/verifyRazorpaySucces', methods=['POST'])
def verify_payment():
    user_id = request.json["user_id"]
    test_name=request.json["test_name"]
    request_order_id = request.json["order_id"]
    request_payment_id = request.json["payment_id"]
    request_signature = request.json["signature"]
    is_success = False
    order_at = datetime.fromtimestamp(calendar.timegm(time.gmtime()))
    generated_signature = hmac_sha256(request_order_id+ "|" + request_payment_id)
    status='failure'
    if(generated_signature == request_signature):
        is_success=True
        status='success'
    cursor = mysql.connection.cursor()
    cursor.execute("""INSERT into order_history(payment_id,order_id,user_id,price,order_at,status,test_name) values(%s,%s,%s,%s,%s,%s,%s)""", [request_payment_id,request_order_id,user_id ,'240',order_at,status,test_name])
    mysql.connection.commit()
    cursor.close()
    return json.dumps({"isSuccess": is_success})

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
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT id,firstname,lastname,email,mobile,image_url,role, whatsapp,graduation_year,preparing_for  FROM users where id=(%s)""", [user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"User details exist","user_data":result}),status= 200, mimetype='application/json')
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

@app.route('/orderDetails/<int:user_id>', methods=["GET"])
def getOrderDetails(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT * FROM order_history where user_id =(%s) AND status ="success" """, [user_id])
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Order Details are","order_data":result}),status= 200, mimetype='application/json')
    return response

@app.route('/isPackageBuy/<int:user_id>',methods=["GET"])
def checkOrderDetails(user_id):
    isValid = False
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT id FROM order_history where user_id =(%s) AND status ="success" limit 1""", [user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    if result:
        isValid = True
    response =app.response_class(response=json.dumps({"isValid":isValid}),status= 200, mimetype='application/json')
    return response

@app.route('/myTestSeries/<int:user_id>',methods=["GET"])
def myTestSeries(user_id):
    isValid = False
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT id FROM order_history where user_id =(%s) AND status ="success" limit 1""", [user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    if result:
        isValid = True
    response =app.response_class(response=json.dumps({"isValid":isValid}),status= 200, mimetype='application/json')
    return response

@app.route('/query',methods=["POST"])
def submitQuery():
    name=request.json["name"]
    message = request.json["message"]
    email = request.json["email"]
    created_at = datetime.fromtimestamp(calendar.timegm(time.gmtime()))
    cursor = mysql.connection.cursor()
    cursor.execute("""insert into user_queries(name,email,message,created_at) values(%s,%s,%s,%s)""",[name,email,message,created_at])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Response Added Successfully"}),status= 200, mimetype='application/json')
    return response









##### Admin End #####

# Admin Login
@app.route('/adminLogin', methods=["POST"])
def adminLogin():
    username = request.json["username"]
    password = request.json["password"]
    isAdminExist = False
    cursor = mysql.connection.cursor()
    cursor.execute(
        """SELECT * FROM admin_table where username=(%s) AND password=(%s)""", [username, password])
    admin_data = cursor.fetchone()
    if admin_data:
        isAdminExist = True
    if isAdminExist:
        response = app.response_class(response=json.dumps({"message": "Login Success", "isValid": True, "admin": admin_data}), status=200, mimetype='application/json')
        return response
    else:
        response = app.response_class(response=json.dumps({"message": "Wrong Credential", "isValid": False}), status=200, mimetype='application/json')
        return response

#Admin Dashboard
@app.route('/adminDashboard',methods=["GET"])
def adminDashboard():
    cursor = mysql.connection.cursor()
    cursor.execute(""" select count(*) as total from users""")
    total = cursor.fetchone()
    cursor.execute(""" select count(*) as total from users u join order_history o on u.id = o.user_id""")
    paid = cursor.fetchone()
    cursor.execute(""" select count(*) as total from users left outer join order_history on users.id = order_history.user_id where order_history.user_id is null""")
    unpaid = cursor.fetchone()
    cursor.execute(""" select count(*) as total from users where preparing_for = 'CGACF'""")
    cgacf = cursor.fetchone()
    cursor.execute(""" select count(*) as total from users where preparing_for = 'CGPSC'""")
    cgpsc = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are:", "total_user":total["total"], "paid_user": paid['total'], "unpaid_user": unpaid["total"], "CGACF":cgacf["total"], "CGPSC":cgpsc["total"] }),status= 200, mimetype='application/json')
    return response

#All Users
@app.route('/allUsers',methods=["GET"])
def getAllUsers():
    page = request.headers.get("page")
    offset = 12*(int(page)-1)
    cursor = mysql.connection.cursor()
    cursor.execute(""" select id, firstname, lastname, email, mobile, image_url, created_at, whatsapp, graduation_year, preparing_for from users order by id desc limit 12 offset %s """,[offset])
    result = cursor.fetchall()
    cursor.execute(""" select count(*) as total from users""")
    total = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are", "user_data":result, "total": total['total']}),status= 200, mimetype='application/json')
    return response


#Paid Users
@app.route('/paidUsers',methods=["GET"])
def getPaidUsers():
    page = request.headers.get("page")
    offset = 12*(int(page)-1)
    cursor = mysql.connection.cursor()
    cursor.execute(""" select u.id, u.firstname, u.lastname, u.email, u.mobile, u.image_url, u.created_at, u.whatsapp, u.graduation_year, u.preparing_for, o.order_id, o.order_at, o.status from users u join order_history o on u.id = o.user_id order by u.id desc limit 12 offset %s""", [offset])
    result = cursor.fetchall()
    cursor.execute(""" select count(*) as total from users u join order_history o on u.id = o.user_id""")
    total = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are", "user_data":result, "total": total['total']}),status= 200, mimetype='application/json')
    return response

#Unpaid Users
@app.route('/unpaidUsers',methods=["GET"])
def getUnpaidUsers():
    page = request.headers.get("page")
    offset = 12*(int(page)-1)
    cursor = mysql.connection.cursor()
    cursor.execute(""" select users.id, firstname, lastname, email, mobile, image_url, created_at, whatsapp, graduation_year, preparing_for from users left outer join order_history on users.id = order_history.user_id where order_history.user_id is null order by users.id desc limit 12 offset %s""", [offset])
    result = cursor.fetchall()
    cursor.execute(""" select count(*) as total from users left outer join order_history on users.id = order_history.user_id where order_history.user_id is null""")
    total = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are", "user_data":result, "total": total['total']}),status= 200, mimetype='application/json')
    return response

#Unpaid Users
@app.route('/getAllMockAdmin',methods=["GET"])
def getAllMockAdmin():
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from mock_paper limit 18 """)
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Mock Papers are", "mock_paper":result}),status= 200, mimetype='application/json')
    return response
#Mock Go Live

@app.route('/goMockLive',methods=["POST"])
def goMockLive():
    mock_paper_id = request.json["mock_paper_id"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" UPDATE mock_paper SET is_active = 1 where id=(%s)""",[mock_paper_id])
    mysql.connection.commit()
    response =app.response_class(response=json.dumps({"message":"Paper Live Successfully"}),status= 200, mimetype='application/json')
    cursor.close()
    return response

@app.route('/finishPaper',methods=["POST"])
def finishPaper():
    mock_paper_id = request.json["mock_paper_id"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" UPDATE mock_paper SET is_active = 0 , is_finished = 1 where id=(%s)""",[mock_paper_id])
    mysql.connection.commit()
    response =app.response_class(response=json.dumps({"message":"Paper Finished Successfully"}),status= 200, mimetype='application/json')
    cursor.close()
    return response

@app.route('/releaseResult',methods=["POST"])
def releaseResult():
    mock_paper_id = request.json["mock_paper_id"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" UPDATE mock_paper SET is_result_released = 1 where id=(%s)""",[mock_paper_id])
    mysql.connection.commit()
    response =app.response_class(response=json.dumps({"message":"Result Released Successfully"}),status= 200, mimetype='application/json')
    cursor.close()
    return response



## Test Series End ##

# Get All Test Mock Paper with Status

@app.route('/getAllMockPaper',methods=["GET"])
def getAllMockPaper():
    user_id = request.headers.get("user_id")
    mock_paper_data = []
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from mock_paper limit 18""")
    mock_papers = cursor.fetchall()
    cursor.execute(""" select * from mock_submissions where user_id = (%s)""",[user_id])
    user_submissions = cursor.fetchall()
    for mock_p in mock_papers:
        temp_dict = {}
        is_attepmted = 0
        for user_s in user_submissions:
            if user_s["mock_paper_id"] == mock_p["id"]:
                is_attepmted = 1
                break
        temp_dict["id"] = mock_p["id"]
        temp_dict["mock_paper_name"] = mock_p["mock_paper_name"]
        temp_dict["mock_description"] = mock_p["mock_description"]
        temp_dict["paper_date"] = mock_p["paper_date"]
        temp_dict["is_active"] = mock_p["is_active"]
        temp_dict["is_finished"] = mock_p["is_finished"]
        temp_dict["is_result_released"] = mock_p["is_result_released"]
        temp_dict["is_attempted"] = is_attepmted
        mock_paper_data.append(temp_dict)
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Mock Papers are", "mock_paper":mock_paper_data}),status= 200, mimetype='application/json')
    return response


# Get All Test Mock Paper with Status

@app.route('/getMockPaperDetails',methods=["GET"])
def getMockPaperDetails():
    mock_paper_id = request.headers.get("mock_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from mock_paper where id =(%s)""",[mock_paper_id])
    mock_paper = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Mock Paper Details", "mock_paper":mock_paper}),status= 200, mimetype='application/json')
    return response


# Get Only Live For Home

@app.route('/getOnlyLiveTest',methods=["GET"])
def getOnlyLiveTest():
    user_id = request.headers.get("user_id")
    is_attempted = 0
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from mock_paper where is_active = 0 and is_finished = 0""")
    mock_paper = cursor.fetchone()
    cursor.execute(""" select * from mock_submissions where user_id = (%s) and mock_paper_id = (%s)""",[user_id,mock_paper["id"]])
    user_submissions = cursor.fetchone()
    if user_submissions:
        is_attempted = 1
    mock_paper["is_attempted"] =is_attempted
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Live Paper Details", "live_mock_paper":mock_paper}),status= 200, mimetype='application/json')
    return response



# Get Questions 
@app.route('/getQuestions/<int:id>',methods=["GET"])
def getMockQuestion(id):
    questions_data = []
    cursor = mysql.connection.cursor()
    cursor.execute(""" select total_questions from mock_paper where id = (%s) """,[id])
    questions = cursor.fetchone()
    cursor.execute(""" select id, question_english, question_hindi, options_english, options_hindi from mock_questions where paper_id = (%s) order by id asc limit %s """,[id,questions["total_questions"]])
    results = cursor.fetchall()
    for result in results:
        temp_data = {}
        temp_data["id"] = result["id"]

        if result["question_english"]:
            temp_data["question_english"] = result["question_english"]
        else:
            temp_data["question_english"] = ""

        if result["options_english"]:
            temp_data["options_english"] = result["options_english"].split(',')
        else:
            temp_data["options_english"] = ["","","","",""]

        if result["question_hindi"]:
            temp_data["question_hindi"] = result["question_hindi"]
        else:
            temp_data["question_hindi"] = ""

        if result["options_hindi"]:
            temp_data["options_hindi"] = result["options_hindi"].split(',')
        else:
            temp_data["options_hindi"] = ["","","","",""]

        questions_data.append(temp_data)
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Questions data are", "questions":questions_data}),status= 200, mimetype='application/json')
    return response

# Post Response 
@app.route('/postResponse',methods=["POST"])
def postMockResponse():
    i = 0
    test_response = request.json["responses"]
    responses = test_response.split(',')
    mock_paper_id = request.json["mock_paper_id"]
    user_id = request.json["user_id"]
    paper_time_taken = request.json["paper_time_taken"]
    submission_at = datetime.fromtimestamp(calendar.timegm(time.gmtime()))
    correct = 0
    incorrect = 0
    total_marks = 0
    accuracy = 0
    attempted = 0
    not_attempted = 0
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from mock_paper where id = (%s) """,[mock_paper_id])
    questions = cursor.fetchone()

    total_questions = questions["total_questions"]

    cursor.execute(""" select answer from mock_questions where paper_id = (%s) order by id asc limit %s """,[mock_paper_id,total_questions])
    answers = cursor.fetchall()

    for answer in answers:
        if responses[i] != "":
            if answer["answer"] == responses[i]:
                correct += 1
            else:
                incorrect += 1
        i += 1
    total_marks = round(correct*2 - incorrect*(2/3), 2)
    if (correct+incorrect) == 0:
        accuracy = 0
    else:
        accuracy = int(round(correct/(correct+incorrect), 2)*100)
    attempted = correct + incorrect
    not_attempted = total_questions - attempted

    print(total_marks, accuracy, attempted, not_attempted, total_questions, correct, incorrect, paper_time_taken, user_id, mock_paper_id, test_response,submission_at)
    cursor.execute("""insert into mock_submissions (user_id, mock_paper_id, responses, total_questions, correct, incorrect, attempted, not_attempted, total_marks, accuracy, paper_time_taken, submission_at) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",[user_id,mock_paper_id,test_response,total_questions,correct,incorrect,attempted,not_attempted,total_marks,accuracy,paper_time_taken,submission_at])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Response Submitted"}),status= 200, mimetype='application/json')
    return response



# Get Response 
@app.route('/getResponses',methods=["GET"])
def getMockResponse():
    mock_paper_id = request.headers.get("mock_paper_id")
    user_id = request.headers.get("user_id")
    questions_data = []
    print(mock_paper_id,user_id)
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from mock_paper where id = (%s) """,[mock_paper_id])
    questions = cursor.fetchone()
    total_questions = questions["total_questions"]

    cursor.execute(""" select * from mock_questions where paper_id = (%s) order by id asc limit %s """,[mock_paper_id,total_questions])
    questions = cursor.fetchall()
    for result in questions:
        temp_data = {}
        temp_data["id"] = result["id"]

        if result["question_english"]:
            temp_data["question_english"] = result["question_english"]
        else:
            temp_data["question_english"] = ""

        if result["options_english"]:
            temp_data["options_english"] = result["options_english"].split(',')
        else:
            temp_data["options_english"] = ["","","","",""]

        if result["question_hindi"]:
            temp_data["question_hindi"] = result["question_hindi"]
        else:
            temp_data["question_hindi"] = ""

        if result["options_hindi"]:
            temp_data["options_hindi"] = result["options_hindi"].split(',')
        else:
            temp_data["options_hindi"] = ["","","","",""]

        temp_data["answer"] = result["answer"]
        questions_data.append(temp_data)

    cursor.execute(""" select * from mock_submissions s join mock_paper p on s.mock_paper_id = p.id where s.mock_paper_id = (%s) and s.user_id =(%s) """,[mock_paper_id,user_id])
    responses = cursor.fetchone()

    temp_response = {}
    if responses:
        temp_response["id"] = responses["id"]
        temp_response["user_id"] = responses["user_id"]
        temp_response["mock_paper_id"] = responses["mock_paper_id"]
        temp_response["responses"] = responses["responses"].split(',')
        temp_response["total_questions"] = responses["total_questions"]
        temp_response["correct"] = responses["correct"]
        temp_response["incorrect"] = responses["incorrect"]
        temp_response["attempted"] = responses["attempted"]
        temp_response["not_attempted"] = responses["not_attempted"]
        temp_response["total_marks"] = responses["total_marks"]
        temp_response["accuracy"] = responses["accuracy"]
        temp_response["paper_time_taken"] = responses["paper_time_taken"]
        temp_response["paper_id"] = responses["p.id"]
        temp_response["mock_paper_name"] = responses["mock_paper_name"]
        temp_response["mock_description"] = responses["mock_description"]

    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Responses Available", "questions":questions_data,"user_response":temp_response,"isValid":True}),status= 200, mimetype='application/json')
    return response

@app.route('/getRankMockPaper',methods=["GET"])
def getRankMockPaper():
    mock_paper_id = request.headers.get("mock_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select us.id as user_id, us.firstname user_firstname, us.lastname as user_lastname,us.email as user_email, ms.total_marks as marks, ms.accuracy as accuracy, ms.paper_time_taken as paper_time from mock_submissions ms join users us on ms.user_id = us.id where ms.mock_paper_id = (%s) order by ms.total_marks desc, ms.accuracy desc, ms.paper_time_taken asc""",[mock_paper_id])
    ranks = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Responses Available", "questions":ranks, "isValid":True}),status= 200, mimetype='application/json')
    return response

    
@app.route('/getMockPaperTime',methods=["GET"])
def getMockPaperTime():
    mock_paper_id = request.headers.get("mock_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select paper_time from mock_paper where id = (%s) """,[mock_paper_id])
    paper_time = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Time Available", "paper_time":paper_time["paper_time"], "isValid":True}),status= 200, mimetype='application/json')
    return response

@app.route('/checkTestAttempted',methods=["GET"])
def checkTestAttempted():
    user_id = request.headers.get("user_id")
    mock_paper_id = request.headers.get("mock_paper_id")
    print(user_id,mock_paper_id)
    isValid = True
    cursor = mysql.connection.cursor()
    cursor.execute(""" select id from mock_submissions where mock_paper_id = (%s) and user_id = (%s)""", [mock_paper_id,user_id])
    is_submission = cursor.fetchone()
    print(is_submission)
    if is_submission:
        isValid = False
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Check Mock Submitted", "isValid":isValid}),status= 200, mimetype='application/json')
    return response   

@app.route('/checkValidUser',methods=["GET"])
def checkPaidUser():
    user_id = request.headers.get("user_id")
    isValid = False
    cursor = mysql.connection.cursor()
    cursor.execute(""" select id from order_history where user_id = (%s)""", [user_id])
    check = cursor.fetchone()
    if check:
        isValid = True
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Check Paid User", "isValid":isValid}),status= 200, mimetype='application/json')
    return response   


@app.route('/demoTest',methods=["GET"])
def demoTest():
    user_id = request.headers.get("user_id")
    isValid = False
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from mock_submissions where user_id = (%s) and mock_paper_id = 19""", [user_id])
    demoData = cursor.fetchone()
    if demoData:
        isValid = True
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Demo data are", "isValid":isValid}),status= 200, mimetype='application/json')
    return response   



if __name__ == "__main__":
    app.run(debug="True", host="0.0.0.0", port=5000)
    # app.run(debug = "True")
