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
import xlrd


# S3 buket Credential
ACCESS_KEY_ID = 'AKIAIVI7KFEM5MDNWJAQ'
ACCESS_SECRET_KEY = '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'
BUCKET_NAME = 'pdhantu-classes'

# Test Razor Pay Credential
# RAZORPAY_KEY = 'rzp_test_x8I5D7s72Z0kOk'
# RAZORPAY_SECRET = 'IsPwjbGZx9vojbrA95vVoXzd'

# Live  Razor Pay Credential
RAZORPAY_KEY = 'rzp_live_dG54e74x2QdKcw'
RAZORPAY_SECRET = 'YqklWxoyHIc1s9boGOL94Z4B'


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

# Generate MD5 hashing
def md5_hash(string):
    hash = hashlib.md5()
    hash.update(string.encode('utf-8'))
    return hash.hexdigest()

# Generate Salt
def generate_salt():
    salt = os.urandom(16)
    return salt.hex()

# Generate Random String
def randomString(stringLength=8):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))


# Test
@app.route('/', methods=["GET"])
def hello():
    return "Hello World"

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
                                      "email": user_data["email"], "role": user_data["role"],"module": user_data["module"]}, 'secretkey', algorithm='HS256').decode("utf-8")
            response = app.response_class(response=json.dumps({"message": "Login Success", "isValid": True, "token": encoded_jwt, "image_url": user_data["image_url"]}), status=200, mimetype='application/json')
            return response
        else:
            response = app.response_class(response=json.dumps({"message": "Wrong Credential", "isValid": False}), status=200, mimetype='application/json')
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

# Social Login
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


# Razorpay Create Order
@app.route('/createOrder', methods=['POST'])
def create_app():
    paye_id = randomString(10)
    order_amount = 240 * 100
    order_currency = 'INR'
    order_receipt = 'order_'+paye_id
    razorId = razorpay_client.order.create(
        amount=order_amount, currency=order_currency, receipt=order_receipt, payment_capture='1')
    return json.dumps(razorId["id"])

# Razorpay Verify Signature
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

# Upload Profile Image
@app.route('/upload-image', methods=["POST"])
def uploadImage():
    isUpload = False
    response = {}
    user_id = request.headers.get("user_id")
    file = request.files["file"]
    seconds = str(time.time()).replace(".","")
    newFile = "user-images/"+seconds + "-" + file.filename
    uploadFileToS3(newFile, file)
    image_url = 'https://pdhantu-classes.s3.us-east-2.amazonaws.com/'+newFile
    cursor = mysql.connection.cursor()
    cursor.execute("""UPDATE users SET image_url =(%s) where id=(%s)""", [image_url,user_id])
    mysql.connection.commit()
    cursor.close()
    isUpload = True
    response["isUpload"] = isUpload
    response["imageUrl"] = image_url
    return json.dumps(response)

# Get Mock Paper PDF Images(Question Paper)
@app.route('/getMockPaperPdfImages', methods=["GET"])
def getMockPaperPdfImages():
    mock_paper_id = request.headers.get("mock_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute("""select * from  questions_paper_pdf where mock_paper_id = (%s)""",[mock_paper_id])
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    data_arr = []
    temp_dict = {}
    for data in result:
        temp1 =  data["question_image_url"].split('.')
        temp2 = int(temp1[-2][-2:])
        print(temp2)
        temp_dict[temp2] = data["question_image_url"]

    for i in sorted (temp_dict.keys()):
        result_dict = {}
        result_dict["question_image_url"] = temp_dict[i]
        data_arr.append(result_dict)
    return json.dumps(data_arr)


# Get Mock Paper PDF Images(Answer Key)
@app.route('/getMockAnswerKeyImages', methods=["GET"])
def getMockAnswerKeyImages():
    mock_paper_id = request.headers.get("mock_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute("""select * from  answer_key_pdf where mock_paper_id = (%s)""",[mock_paper_id])
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    return json.dumps(result)


# Check User Registered
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


# Get Profile Details
@app.route('/userDetails/<int:user_id>', methods=["GET"])
def getUserDetails(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT id,firstname,lastname,email,mobile,image_url,role, whatsapp,graduation_year,preparing_for  FROM users where id=(%s)""", [user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"User details exist","user_data":result}),status= 200, mimetype='application/json')
    return response


# Change Profile Details 
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


# User Order Details
@app.route('/orderDetails/<int:user_id>', methods=["GET"])
def getOrderDetails(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT * FROM order_history where user_id =(%s) AND status ="success" """, [user_id])
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Order Details are","order_data":result}),status= 200, mimetype='application/json')
    return response


# Check Package Buy or NOT
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


# Get All Test Series bought by User
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

# User Query
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
    offset = 20*(int(page)-1)
    cursor = mysql.connection.cursor()
    cursor.execute(""" select id, firstname, lastname, email, mobile, image_url, created_at, whatsapp, graduation_year, preparing_for from users order by id desc limit 20 offset %s """,[offset])
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
    offset = 20*(int(page)-1)
    cursor = mysql.connection.cursor()
    cursor.execute(""" select u.id, u.firstname, u.lastname, u.email, u.mobile, u.image_url, u.created_at, u.whatsapp, u.graduation_year, u.preparing_for, o.order_id, o.order_at, o.status from users u join order_history o on u.id = o.user_id order by u.id desc limit 20 offset %s""", [offset])
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
    offset = 20*(int(page)-1)
    cursor = mysql.connection.cursor()
    cursor.execute(""" select users.id, firstname, lastname, email, mobile, image_url, created_at, whatsapp, graduation_year, preparing_for from users left outer join order_history on users.id = order_history.user_id where order_history.user_id is null order by users.id desc limit 20 offset %s""", [offset])
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

#Mock Stop 
@app.route('/finishPaper',methods=["POST"])
def finishPaper():
    mock_paper_id = request.json["mock_paper_id"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" UPDATE mock_paper SET is_active = 0 , is_finished = 1 where id=(%s)""",[mock_paper_id])
    mysql.connection.commit()
    response =app.response_class(response=json.dumps({"message":"Paper Finished Successfully"}),status= 200, mimetype='application/json')
    cursor.close()
    return response


#Mock Rank Released and PDF
@app.route('/releaseResult',methods=["POST"])
def releaseResult():
    mock_paper_id = request.json["mock_paper_id"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" UPDATE mock_paper SET is_result_released = 1 where id=(%s)""",[mock_paper_id])
    mysql.connection.commit()
    response =app.response_class(response=json.dumps({"message":"Result Released Successfully"}),status= 200, mimetype='application/json')
    cursor.close()
    return response

# Check User Payment by Email
@app.route('/checkPayment',methods=["GET"])
def checkPayment():
    email = request.headers.get("email")
    user_exist = False
    is_exist = False
    payment_exist = []
    cursor = mysql.connection.cursor()
    cursor.execute("""select id from users where email=(%s)""",[email])
    user_id = cursor.fetchone()
    if user_id:
        user_exist = True
    if user_exist:
        cursor.execute("""select oh.*, u.firstname,u.lastname,u.email from users u join order_history oh on u.id=oh.user_id where user_id=(%s)""",[user_id["id"]])
        temp = cursor.fetchone()
        mysql.connection.commit()
        cursor.close()
        if temp:
            response =app.response_class(response=json.dumps({"message":"User Payment Details", "isExist":True, "payment_data":temp}),status= 200, mimetype='application/json')
        else :
             response =app.response_class(response=json.dumps({"message":"User Payment Details", "isExist":False}),status= 200, mimetype='application/json')
    else:
         response =app.response_class(response=json.dumps({"message":"User Not Exist", "isExist":False}),status= 200, mimetype='application/json')    
   
    return response

# Settle User Payment
@app.route('/addUserToPaymentList',methods=["POST"])
def addUserToPaymentList():
    email = request.json["email"]
    order_id = request.json["order_id"]
    payment_id = request.json["payment_id"]
    order_at = request.json["payment_date"]
    cursor = mysql.connection.cursor()
    cursor.execute("""select id from users where email=(%s)""",[email])
    user_id = cursor.fetchone()
    if user_id:
        cursor.execute("""insert into order_history(payment_id, order_id, user_id, price, order_at, status, test_name) values(%s,%s,%s,%s,%s,%s,%s)""",[payment_id,order_id,user_id["id"],240,order_at,"success","Pdhantu Test Series"])
        response =app.response_class(response=json.dumps({"message":"Payment Details Updated Successfully"}),status= 200, mimetype='application/json')
    else:
        response =app.response_class(response=json.dumps({"message":"User not exist"}),status= 200, mimetype='application/json')
    mysql.connection.commit()
    cursor.close()
    return response


# Get Mock Status 
@app.route('/getLiveMockStatus',methods=["GET"])
def getLiveMockStatus():
    cursor = mysql.connection.cursor()
    cursor.execute("""select id,mock_paper_name,is_active from mock_paper where is_active = 1 or is_finished = 1""")
    mock_paper_details = cursor.fetchall()
    for mock in mock_paper_details:
        cursor.execute("""select count(*) as user_count from mock_submissions where mock_paper_id = (%s)""",[mock["id"]])
        user_details = cursor.fetchone()
        mock["user_count"] = user_details["user_count"]
    response =app.response_class(response=json.dumps({"message":"All Mock Status", "mock_data":mock_paper_details}),status= 200, mimetype='application/json')
    mysql.connection.commit()
    cursor.close()
    return response

# Upload Question Images
@app.route('/upload-question-image', methods=["POST"])
def uploadQuestionImage():
    isUpload = False
    response = {}
    file = request.files["file"]
    seconds = str(time.time()).replace(".","")
    newFile = "question-images/"+seconds + "-" + file.filename
    uploadFileToS3(newFile, file)
    image_url = 'https://pdhantu-classes.s3.us-east-2.amazonaws.com/'+newFile
    isUpload = True
    response["isUpload"] = isUpload
    response["imageUrl"] = image_url
    return json.dumps(response)

# Upload Bulk Question Paper PDF Images in S3
@app.route('/upload-image-bulk-question', methods=["POST"])
def uploadImageBulk():
    isUpload = False
    imageUrl = []
    response = {}
    for file in request.files.getlist('file'):
        seconds = str(time.time()).replace(".","")
        newFile = "question_paper_pdf/"+seconds + "-" + file.filename
        image_url = 'https://pdhantu-classes.s3.us-east-2.amazonaws.com/'+newFile
        uploadFileToS3(newFile,file)
        imageUrl.append(image_url)
        isUpload = True
    response["isUpload"] = isUpload
    response["imageUrl"] = imageUrl
    return json.dumps(response)

# Dump Bulk Question Paper PDF Images Urls to DB
@app.route('/dump-question-images', methods=["POST"])
def dumpImages():
    response = {}
    images = request.json["images"]
    mock_paper_id = request.json["mock_paper_id"]
    for image in images:
        cursor = mysql.connection.cursor()
        cursor.execute("""INSERT into questions_paper_pdf(mock_paper_id, question_image_url) values(%s,%s)""", [mock_paper_id,image])
        mysql.connection.commit()
        cursor.close()
    response["isUpload"] = True
    return json.dumps(response)

# Upload Answer Key PDF Images in S3
@app.route('/upload-image-answer', methods=["POST"])
def uploadImageAnswerKey():
    isUpload = False
    file = request.files["file"]
    response = {}
    seconds = str(time.time()).replace(".","")
    newFile = "answer_key_pdf/"+seconds + "-" + file.filename
    image_url = 'https://pdhantu-classes.s3.us-east-2.amazonaws.com/'+newFile
    uploadFileToS3(newFile,file)
    isUpload = True
    response["isUpload"] = isUpload
    response["imageUrl"] = image_url
    return json.dumps(response)

# Dump Answer PDF Images Urls to DB
@app.route('/dump-images-answer', methods=["POST"])
def dumpImagesAnswerKey():
    response = {}
    images = request.json["images"]
    mock_paper_id = request.json["mock_paper_id"]
    cursor = mysql.connection.cursor()
    cursor.execute("""INSERT into answer_key_pdf(mock_paper_id, answer_image_url) values(%s,%s)""", [mock_paper_id,images])
    mysql.connection.commit()
    cursor.close()
    response["isUpload"] = True
    return json.dumps(response)

# Get Mock Paper List for Non Exist PDF for Question Paper
@app.route('/getMockPaperForQuestion', methods=["GET"])
def getMockPaperQuestion():
    cursor = mysql.connection.cursor()
    cursor.execute("""select id, mock_paper_name from mock_paper where id not in(select distinct(mock_paper_id) from questions_paper_pdf )""")
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    return json.dumps({"result":result})

# Get Mock Paper List for Non Exist PDF for Answer Key
@app.route('/getMockPaperForAnswer', methods=["GET"])
def getMockPaperAnswer():
    cursor = mysql.connection.cursor()
    cursor.execute("""select id, mock_paper_name from mock_paper where id not in(select distinct(mock_paper_id) from answer_key_pdf )""")
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    return json.dumps({"result":result})

# Get User List wrt Mock Paper
@app.route('/getUserListMock',methods=["GET"])
def getUserListMock():
    mock_paper_id = request.headers.get("mock_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select us.id as user_id, us.firstname user_firstname, us.lastname as user_lastname,us.email as user_email, ms.total_marks as marks, ms.accuracy as accuracy, ms.paper_time_taken as paper_time from mock_submissions ms join users us on ms.user_id = us.id where ms.mock_paper_id = (%s) order by ms.total_marks desc, ms.accuracy desc, ms.paper_time_taken asc""",[mock_paper_id])
    user_list = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"User List are", "user_list":user_list}),status= 200, mimetype='application/json')
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
        is_attempted = 0
        is_live_attempted = 0
        for user_s in user_submissions:
            if user_s["mock_paper_id"] == mock_p["id"]:
                is_attempted = user_s["is_attempted"]
                is_live_attempted = user_s["is_live_attempted"]
                break
        temp_dict["id"] = mock_p["id"]
        temp_dict["mock_paper_name"] = mock_p["mock_paper_name"]
        temp_dict["mock_description"] = mock_p["mock_description"]
        temp_dict["paper_date"] = mock_p["paper_date"]
        temp_dict["is_active"] = mock_p["is_active"]
        temp_dict["is_finished"] = mock_p["is_finished"]
        temp_dict["is_result_released"] = mock_p["is_result_released"]
        temp_dict["paper_pdf"] = mock_p["paper_pdf"]
        temp_dict["is_attempted"] = is_attempted
        temp_dict["is_live_attempted"] = is_live_attempted
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
    cursor.execute(""" select * from mock_questions where paper_id = (%s) order by id asc limit %s """,[id,questions["total_questions"]])
    results = cursor.fetchall()
    for result in results:
        temp_data = {}
        temp_data["id"] = result["id"]

        if result["question_english"]:
            temp_data["question_english"] = result["question_english"].split('$')
        else:
            temp_data["question_english"] = ""

        if result["options_english"]:
            temp_data["options_english"] = result["options_english"].split('$')
        else:
            temp_data["options_english"] = ["","","","",""]

        if result["question_hindi"]:
            temp_data["question_hindi"] = result["question_hindi"].split('$')
        else:
            temp_data["question_hindi"] = ""

        if result["options_hindi"]:
            temp_data["options_hindi"] = result["options_hindi"].split('$')
        else:
            temp_data["options_hindi"] = ["","","","",""]
        
        if result["extras_question"]:
            temp_data["extras_question"] = result["extras_question"].split('$')
        else:
            temp_data["extras_question"] = []

        if result["extras_option"]:
            temp_data["extras_option"] = result["extras_option"].split('$')
        else:
            temp_data["extras_option"] = []
        temp_data["question_type"] = result["question_type"]
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
    print(mock_paper_id)
    submission_at = datetime.fromtimestamp(calendar.timegm(time.gmtime()))
    correct = 0
    incorrect = 0
    total_marks = 0
    accuracy = 0
    attempted = 0
    not_attempted = 0
    total_questions = 0
    is_live_attempted = 0
    cursor = mysql.connection.cursor()

    cursor.execute(""" select id from mock_submissions where user_id = (%s) and mock_paper_id =(%s) """,[user_id,mock_paper_id])
    is_already_exist = cursor.fetchone()
    
    if is_already_exist:
        response =app.response_class(response=json.dumps({"message":"Response Submitted"}),status= 200, mimetype='application/json')
    else:
        cursor.execute(""" select total_questions,is_active from mock_paper where id = (%s) """,[mock_paper_id])
        questions = cursor.fetchone()
        total_questions = questions["total_questions"]
        is_live_attempted = questions["is_active"]

        cursor.execute(""" select answer from mock_questions where paper_id = (%s) order by id asc limit %s """,[mock_paper_id,total_questions])
        answers = cursor.fetchall()

        for answer in answers:
            if responses[i] != "":
                print(responses[i], answer)
                if answer["answer"].lower() == responses[i]:
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
        cursor.execute("""insert into mock_submissions (user_id, mock_paper_id, responses, total_questions, correct, incorrect, attempted, not_attempted, total_marks, accuracy, paper_time_taken, is_live_attempted, submission_at) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",[user_id,mock_paper_id,test_response,total_questions,correct,incorrect,attempted,not_attempted,total_marks,accuracy,paper_time_taken, is_live_attempted, submission_at])
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
            temp_data["options_english"] = result["options_english"].split('$')
        else:
            temp_data["options_english"] = ["","","",""]

        if result["question_hindi"]:
            temp_data["question_hindi"] = result["question_hindi"]
        else:
            temp_data["question_hindi"] = ""

        if result["options_hindi"]:
            temp_data["options_hindi"] = result["options_hindi"].split('$')
        else:
            temp_data["options_hindi"] = ["","","",""]

        if result["extras_question"]:
            temp_data["extras_question"] = result["extras_question"].split('$')
        else:
            temp_data["extras_question"] = []

        if result["extras_option"]:
            temp_data["extras_option"] = result["extras_option"].split('$')
        else:
            temp_data["extras_option"] = []
        temp_data["question_type"] = result["question_type"]
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

# Get Rank List 
@app.route('/getRankMockPaper',methods=["GET"])
def getRankMockPaper():
    mock_paper_id = request.headers.get("mock_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select us.id as user_id, us.firstname user_firstname, us.lastname as user_lastname,us.email as user_email, ms.total_marks as marks, ms.accuracy as accuracy, ms.paper_time_taken as paper_time from mock_submissions ms join users us on ms.user_id = us.id where ms.mock_paper_id = (%s) and ms.is_live_attempted = 1 order by ms.total_marks desc, ms.accuracy desc, ms.paper_time_taken asc""",[mock_paper_id])
    ranks = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Responses Available", "questions":ranks, "isValid":True}),status= 200, mimetype='application/json')
    return response

# Get Mock Time
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

# Check Test Attempted
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

# Check Paid User or Not
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


# For Demo Test
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



@app.route('/dumpQuestionsExcelfile', methods=["POST"])
def dumpQuestions():
    excel_file = request.files['excel_file']
    prefix_file = str(time.time()).replace(".","")[:11]
    new_name_file = prefix_file + "-" + excel_file.filename
    excel_file.save(new_name_file)
    book = xlrd.open_workbook(new_name_file)
    sheet = book.sheet_by_index(0)
    cursor = mysql.connection.cursor()
    query = """INSERT INTO mock_questions(paper_id, question_english, options_english, question_hindi, options_hindi, answer, extras_question, extras_option, question_type) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
    for r in range(1, sheet.nrows):
        paper_id = sheet.cell(r,0).value
        question_english = sheet.cell(r,1).value
        options_english = sheet.cell(r,2).value
        answer =  sheet.cell(r,3).value
        question_hindi = sheet.cell(r,4).value
        options_hindi = sheet.cell(r,5).value
        extras_question = sheet.cell(r,6).value
        extras_option = sheet.cell(r,7).value
        question_type = sheet.cell(r,8).value

        values = (paper_id, question_english, options_english, question_hindi, options_hindi, answer, extras_question, extras_option, question_type)     
        print(values)
        cursor.execute(query, values)

    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Sucessfully Uploaded"}),status= 200, mimetype='application/json')
    return response


# Get Mock Questions
@app.route('/getQuestionsByPaperId',methods=["GET"])
def getMockQuestionsByPaperId():
    questions_data = []
    mock_paper_id = request.headers.get("mock_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from mock_questions where paper_id = (%s) order by id asc""",[mock_paper_id])
    results = cursor.fetchall()
    for result in results:
        temp_data = {}
        temp_data["id"] = result["id"]

        if result["question_english"]:
            temp_data["question_english"] = result["question_english"].split('$')
        else:
            temp_data["question_english"] = ""

        if result["options_english"]:
            temp_data["options_english"] = result["options_english"].split('$')
        else:
            temp_data["options_english"] = ["","","",""]

        if result["question_hindi"]:
            temp_data["question_hindi"] = result["question_hindi"].split('$')
        else:
            temp_data["question_hindi"] = ""

        if result["options_hindi"]:
            temp_data["options_hindi"] = result["options_hindi"].split('$')
        else:
            temp_data["options_hindi"] = ["","","",""]
        
        if result["extras_question"]:
            temp_data["extras_question"] = result["extras_question"].split('$')
        else:
            temp_data["extras_question"] = []

        if result["extras_option"]:
            temp_data["extras_option"] = result["extras_option"].split('$')
        else:
            temp_data["extras_option"] = []
        temp_data["question_type"] = result["question_type"]
        temp_data["answer"] = result["answer"]
        questions_data.append(temp_data)
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Questions data are", "questions":questions_data}),status= 200, mimetype='application/json')
    return response

# Get Mock Questions
@app.route('/getQuestionsById', methods=["GET"])
def getMockQuestionsById():
    questions_id = request.headers.get("questions_id")
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT * from mock_questions where id = (%s)""", [questions_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Mock Questions details","question_list":result}),status= 200, mimetype='application/json')
    return response

# Add Mock Question
@app.route('/addQuestionToPaper', methods=["POST"])
def addQuestionToPaper():
    mock_paper_id = request.json["mock_paper_id"]
    question_english = request.json["question_english"]
    options_english = request.json["options_english"]
    question_hindi = request.json["question_hindi"]
    options_hindi = request.json["options_hindi"]
    answer =  request.json["answer"]
    extras_question = request.json["extras_question"]
    extras_option = request.json["extras_option"]
    question_type = request.json["question_type"]

    cursor = mysql.connection.cursor()
    cursor.execute("""INSERT INTO mock_questions(paper_id, question_english, options_english, question_hindi, options_hindi, answer, extras_question, extras_option, question_type) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""", [mock_paper_id,question_english, options_english, question_hindi, options_hindi, answer, extras_question, extras_option, question_type])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Successfully Added"}),status= 200, mimetype='application/json')
    return response

# Edit Mock Questions
@app.route('/editQuestionsById', methods=["PUT"])
def editQuestionsById():
    questions_id = request.json["questions_id"]
    question_english = request.json["question_english"]
    options_english = request.json["options_english"]
    question_hindi = request.json["question_hindi"]
    options_hindi = request.json["options_hindi"]
    answer =  request.json["answer"]
    extras_question = request.json["extras_question"]
    extras_option = request.json["extras_option"]
    question_type = request.json["question_type"]

    cursor = mysql.connection.cursor()
    cursor.execute(""" update mock_questions set question_english=(%s), options_english=(%s), question_hindi=(%s), options_hindi=(%s),answer=(%s),extras_question=(%s),extras_option=(%s), question_type=(%s) where id=(%s) """, [question_english, options_english, question_hindi, options_hindi, answer, extras_question, extras_option, question_type, questions_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"SuccessfullgetMockQuestionsByIdy Updated"}),status= 200, mimetype='application/json')
    return response

# Delete Question
@app.route('/deleteQuestionById',methods=["DELETE"])
def deleteQuestionById():
    question_id = request.headers.get("question_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" delete from mock_questions where id =(%s)""",[question_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Successfully Deleted", "isValid":True}),status= 200, mimetype='application/json')
    return response



# Delete Question
@app.route('/deleteQuestionsByPaperId',methods=["DELETE"])
def deleteQuestionByPaperId():
    mock_paper_id = request.headers.get("mock_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" delete from mock_questions where paper_id =(%s)""",[mock_paper_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Successfully Deleted", "isValid":True}),status= 200, mimetype='application/json')
    return response

#################################### Course ###########################################

# SignUp
@app.route('/course/signup', methods=['POST'])
def signUpCourse():
    firstname = request.json['firstname']
    lastname = request.json['lastname']
    email = request.json['email']
    password = request.json['password']
    mobile = request.json['mobile']
    #Change Batch Here
    batch = 4
    created_at = datetime.fromtimestamp(calendar.timegm(time.gmtime()))
    flag = False
    password_salt = generate_salt()
    password_hash = md5_hash(password + password_salt)
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT * FROM course_users where email = (%s)""", [email])
    results = cursor.fetchone()
    if results:
        flag = True
        mysql.connection.commit()
        cursor.close()
    if flag == True:
        response = app.response_class(response=json.dumps(
            {"message": "Already Exist", "isValid": False}), status=200, mimetype='application/json')
        return response
    else:
        cursor.execute(
            """INSERT INTO course_users (firstname, lastname, email, mobile, password_hash, password_salt, sign_up_method, is_active, role, created_at, batch) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """, (
                firstname, lastname, email, mobile, password_hash, password_salt, "NORMAL", True, "USER", created_at, batch)
        )
        mysql.connection.commit()
        cursor.close()
        response = app.response_class(response=json.dumps(
            {"message": "Sign Up Successfully", "isValid": True}), status=200, mimetype='application/json')
        return response

# User Login
@app.route('/course/login', methods=["POST"])
def userLoginCourse():
    email = request.json["email"]
    password = request.json["password"]
    isUserExist = False
    cursor = mysql.connection.cursor()
    cursor.execute(
        """SELECT * FROM course_users where email=(%s)""", [email])
    user_data = cursor.fetchone()
    response = {}
    if user_data:
        if str(user_data["password_hash"]) == str(md5_hash(password+user_data["password_salt"])):
            isUserExist = True

        if isUserExist:
            print(user_data)
            encoded_jwt = jwt.encode({"user_id": user_data["id"], "firstname": user_data["firstname"],"lastname":user_data["lastname"],"mobile":user_data["mobile"],
                                      "email": user_data["email"], "role": user_data["role"],"module": user_data["module"]}, 'secretkey', algorithm='HS256').decode("utf-8")
            response = app.response_class(response=json.dumps(
                {"message": "Login Success", "isValid": True, "token": encoded_jwt, "course": user_data["course"], "image_url": user_data["image_url"]}), status=200, mimetype='application/json')
            return response
        else:
            response = app.response_class(response=json.dumps(
                {"message": "Wrong Credential", "isValid": False}), status=200, mimetype='application/json')
            return response
    else:
        response =app.response_class(response=json.dumps({"message":"User do not exists, Please sign up"}),status= 200, mimetype='application/json')
        return response


# User Forget Password
@app.route('/course/forgetPassword', methods=["POST"])
def forgetPasswordCourse():
    email = request.json["email"]
    mobile = request.json["mobile"]
    isUserExist = False
    cursor = mysql.connection.cursor()
    cursor.execute(
        """SELECT * FROM course_users where email=(%s) AND mobile=(%s)""", [email, mobile])
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
@app.route('/course/changePassword', methods=["PUT"])
def changePasswordCourse():
    user_id = request.json["user_id"]
    password = request.json["password"]
    password_salt = generate_salt()
    password_hash = md5_hash(password + password_salt)
    cursor = mysql.connection.cursor()
    cursor.execute("""UPDATE course_users SET password_hash = (%s), password_salt = (%s) where id = (%s)""", [password_hash,password_salt,user_id])
    mysql.connection.commit()
    cursor.close()
    response = app.response_class(response=json.dumps({"message": "Password Change Successfully", "isValid": True}), status=200, mimetype='application/json')
    return response


# Razorpay Create Order
@app.route('/course/createOrder', methods=['POST'])
def createOrderCourse():
    package_id = request.json["package_id"]
    user_id = request.json["user_id"]
    initiate_at = datetime.fromtimestamp(calendar.timegm(time.gmtime()))
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT package_price FROM course_package where id=(%s)""", [package_id])
    result = cursor.fetchone()
    paye_id = randomString(10)
    order_amount = int(result["package_price"]) * 100
    order_currency = 'INR'
    order_receipt = 'order_'+paye_id
    cursor.execute("""INSERT into course_order_initiates(order_id, user_id, package_id, price, initiate_at) values(%s,%s,%s,%s,%s)""", [order_receipt, user_id ,package_id, order_amount/100, initiate_at])
    razorId = razorpay_client.order.create(
        amount=order_amount, currency=order_currency, receipt=order_receipt, payment_capture='1')
    mysql.connection.commit()
    cursor.close()
    return json.dumps(razorId["id"])


# Razorpay Verify Signature
@app.route('/course/verifyRazorpaySucces', methods=['POST'])
def verifyPaymentCourse():
    user_id = request.json["user_id"]
    package_id=request.json["package_id"]
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
    cursor.execute("""SELECT package_price FROM course_package where id=(%s)""", [package_id])
    result = cursor.fetchone()
    cursor.execute("""UPDATE course_order_initiates SET status = (%s) where user_id =(%s) and package_id=(%s)""",[status,user_id,package_id])
    cursor.execute("""INSERT into course_order_history(payment_id,order_id,user_id,price,order_at,status,package_id) values(%s,%s,%s,%s,%s,%s,%s)""", [request_payment_id,request_order_id,user_id,result["package_price"],order_at,status,package_id])
    mysql.connection.commit()
    cursor.close()
    return json.dumps({"isSuccess": is_success})


# Check User Registered
@app.route('/course/isUserRegister/<int:user_id>', methods=["GET"])
def isUserRegisterCourse(user_id):
    cursor = mysql.connection.cursor()
    isValid = False
    cursor.execute("""SELECT course FROM course_users where id=(%s)""", [user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    if result["course"]:
        isValid = True
    response =app.response_class(response=json.dumps({"message":"User details exist", "isValid":isValid, "package_id":result["course"]}),status= 200, mimetype='application/json')
    return response

# Get Profile Details
@app.route('/course/userDetails/<int:user_id>', methods=["GET"])
def getUserDetailsCourse(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT cu.*, cp.package_name as courses  FROM course_users cu left join course_package cp on cu.course = cp.id where cu.id=(%s)""", [user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"User details exist","user_data":result}),status= 200, mimetype='application/json')
    return response


# Upload Profile Image
@app.route('/course/upload-image', methods=["POST"])
def uploadImageCourse():
    isUpload = False
    response = {}
    file = request.files["file"]
    seconds = str(time.time()).replace(".","")
    newFile = "user-images/"+seconds + "-" + file.filename
    uploadFileToS3(newFile, file)
    image_url = 'https://pdhantu-classes.s3.us-east-2.amazonaws.com/'+newFile
    isUpload = True
    response["isUpload"] = isUpload
    response["imageUrl"] = image_url
    return json.dumps(response)

# Change Profile Details 
@app.route('/course/userDetails/<int:user_id>', methods=["PUT"])
def postUserDetailsCourse(user_id):
    whatsapp = request.json["whatsapp"]
    graduation_year = request.json["graduation_year"]
    course = request.json["course"]
    gender = request.json["gender"]
    dob = request.json["dob"]
    address = request.json["address"]
    pincode = request.json["pincode"]
    qualification = request.json["qualification"]
    occupation = request.json["occupation"]
    fathers_name = request.json["fathers_name"]
    medium = request.json["medium"]
    imageUrl = request.json["imageUrl"]
    cursor = mysql.connection.cursor()
    cursor.execute("""UPDATE course_users SET whatsapp =(%s), graduation_year=(%s), course=(%s), gender=(%s), dob=(%s), address=(%s), pincode=(%s), qualification=(%s), occupation=(%s), fathers_name=(%s), medium=(%s), image_url =(%s)  where id=(%s)""", [whatsapp, graduation_year, course, gender, dob, address, pincode, qualification, occupation, fathers_name, medium,imageUrl, user_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"User Data Added Successfully"}),status= 200, mimetype='application/json')
    return response


# Get All Test Series bought by User
@app.route('/course/myOrders/<int:user_id>',methods=["GET"])
def myOrdersCourse(user_id):
    isValid = False
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT coh.*, cp.package_name FROM course_order_history coh left join course_package cp on coh.package_id= cp.id where coh.user_id =(%s) AND coh.status ="success" limit 1""", [user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    if result:
        isValid = True
    response =app.response_class(response=json.dumps({"isValid":isValid,"orders":result}),status= 200, mimetype='application/json')
    return response

# Check Package Buy or NOT
@app.route('/course/isPackageBuy/<int:user_id>',methods=["GET"])
def checkOrderDetailsCourse(user_id):
    isValid = False
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT id FROM course_order_history where user_id =(%s) AND status ="success" limit 1""", [user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    if result:
        isValid = True
    response =app.response_class(response=json.dumps({"isValid":isValid}),status= 200, mimetype='application/json')
    return response

##### Admin End #####

# Admin Login
@app.route('/course/adminLogin', methods=["POST"])
def adminLoginCourse():
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
@app.route('/course/adminDashboard',methods=["GET"])
def adminDashboardCourse():
    cursor = mysql.connection.cursor()
    cursor.execute(""" select count(*) as total from course_users""")
    total = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users u join course_order_history o on u.id = o.user_id where u.batch = 1""")
    paid_batch1 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 1 and batch = 1""")
    prelims_batch1 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 2 and batch = 1""")
    mains_batch1 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 3 and batch = 1""")
    mains_hindi_batch1 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 4 and batch = 1""")
    mains_english_batch1 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users u join course_order_history o on u.id = o.user_id where u.batch = 2""")
    paid_batch2 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 1 and batch = 2""")
    prelims_batch2 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 2 and batch = 2""")
    mains_batch2 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 3 and batch = 2""")
    mains_hindi_batch2 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 4 and batch = 2""")
    mains_english_batch2 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users u join course_order_history o on u.id = o.user_id where u.batch = 3""")
    paid_batch3 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 1 and batch = 3""")
    prelims_batch3 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 2 and batch = 3""")
    mains_batch3 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 3 and batch = 3""")
    mains_hindi_batch3 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 4 and batch = 3""")
    mains_english_batch3 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users u join course_order_history o on u.id = o.user_id where u.batch = 4""")
    paid_batch4 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 1 and batch = 4""")
    prelims_batch4 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 2 and batch = 4""")
    mains_batch4 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 3 and batch = 4""")
    mains_hindi_batch4 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where course = 4 and batch = 4""")
    mains_english_batch4 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where batch = 1""")
    batch_1 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where batch = 2""")
    batch_2 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where batch = 3""")
    batch_3 = cursor.fetchone()
    cursor.execute(""" select count(*) as total from course_users where batch = 4""")
    batch_4 = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are:", 
        "total_user":total["total"], 
        "paid_user_batch1": paid_batch1['total'], 
        "prelims_batch1":prelims_batch1["total"], 
        "mains_batch1":mains_batch1["total"], 
        "mains_hindi_batch1":mains_hindi_batch1["total"], 
        "mains_english_batch1":mains_english_batch1["total"],
        "paid_user_batch2": paid_batch2['total'], 
        "prelims_batch2":prelims_batch2["total"], 
        "mains_batch2":mains_batch2["total"], 
        "mains_hindi_batch2":mains_hindi_batch2["total"], 
        "mains_english_batch2":mains_english_batch2["total"], 
        "paid_user_batch3": paid_batch3['total'], 
        "prelims_batch3":prelims_batch3["total"], 
        "mains_batch3":mains_batch3["total"], 
        "mains_hindi_batch3":mains_hindi_batch3["total"], 
        "mains_english_batch3":mains_english_batch3["total"],
        "paid_user_batch4": paid_batch4['total'], 
        "prelims_batch4":prelims_batch4["total"], 
        "mains_batch4":mains_batch4["total"], 
        "mains_hindi_batch4":mains_hindi_batch4["total"],
        "mains_english_batch4":mains_english_batch4["total"], 
        "batch_1": batch_1["total"], 
        "batch_2": batch_2["total"],
        "batch_3": batch_3["total"],
        "batch_4": batch_4["total"]
        }),status= 200, mimetype='application/json')
    return response

#All Users
@app.route('/course/allUsers',methods=["GET"])
def getAllUsersCourse():
    page = request.headers.get("page")
    offset = 20*(int(page)-1)
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from course_users order by id desc limit 20 offset %s """,[offset])
    result = cursor.fetchall()
    cursor.execute(""" select count(*) as total from course_users""")
    total = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are", "user_data":result, "total": total['total']}),status= 200, mimetype='application/json')
    return response


#Paid Users
@app.route('/course/paidUsers',methods=["GET"])
def getPaidUsersCourse():
    page = request.headers.get("page")
    offset = 20*(int(page)-1)
    cursor = mysql.connection.cursor()
    cursor.execute(""" select u.*, o.* from course_users u join course_order_history o on u.id = o.user_id order by u.id desc limit 20 offset %s""", [offset])
    result = cursor.fetchall()
    cursor.execute(""" select count(*) as total from course_users u join course_order_history o on u.id = o.user_id""")
    total = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are", "user_data":result, "total": total['total']}),status= 200, mimetype='application/json')
    return response

#Unpaid Users
@app.route('/course/unpaidUsers',methods=["GET"])
def getUnpaidUsersCourse():
    page = request.headers.get("page")
    offset = 20*(int(page)-1)
    cursor = mysql.connection.cursor()
    cursor.execute(""" select course_users.* from course_users left outer join course_order_history on course_users.id = course_order_history.user_id where course_order_history.user_id is null order by course_users.id desc limit 20 offset %s""", [offset])
    result = cursor.fetchall()
    cursor.execute(""" select count(*) as total from course_users left outer join course_order_history on course_users.id = course_order_history.user_id where course_order_history.user_id is null""")
    total = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are", "user_data":result, "total": total['total']}),status= 200, mimetype='application/json')
    return response

#Disputed Users
@app.route('/course/disputeOrders',methods=["GET"])
def disputeOrdersCourse():
    cursor = mysql.connection.cursor()
    cursor.execute(""" select cu.firstname, cu.lastname, cu.email, coi.user_id, coi.id, coi.order_id, coi.package_id, coi.price, coi.initiate_at from course_order_initiates coi left join course_users cu on coi.user_id = cu.id where status is null order by coi.id desc""")
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are", "order_data":result}),status= 200, mimetype='application/json')
    return response

#Disputed Users
@app.route('/course/disputeOrdersById',methods=["GET"])
def disputeOrderByIdCourse():
    initiate_id = request.headers.get("initiate_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select cu.firstname, cu.lastname, cu.email, coi.user_id, coi.id, coi.order_id, coi.package_id, coi.price, coi.initiate_at from course_order_initiates coi left join course_users cu on coi.user_id = cu.id where coi.id =(%s)""",[initiate_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are", "order_data":result}),status= 200, mimetype='application/json')
    return response

# Resolve Orders
@app.route('/course/resolveOrder',methods=["POST"])
def resolveOrderCourse():
    payment_id = request.json["payment_id"]
    initiate_id = request.json["initiate_id"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from course_order_initiates where id =(%s)""",[initiate_id])
    result = cursor.fetchone()
    cursor.execute(""" update course_order_initiates set status='success' where id =(%s)""",[initiate_id])
    cursor.execute(""" insert into course_order_history(payment_id, order_id, user_id, price, order_at, package_id, status) values(%s,%s,%s,%s,%s,%s,%s)""",[payment_id,result["order_id"],result["user_id"],result["price"],result["initiate_at"],result["package_id"],"success"])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Successfully Resolved", "isValid":True}),status= 200, mimetype='application/json')
    return response

# Delete Orders
@app.route('/course/deleteDisputeOrder',methods=["DELETE"])
def deleteDisputeOrderCourse():
    initiate_id = request.headers.get("initiate_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" delete from course_order_initiates where id =(%s)""",[initiate_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Successfully Deleted", "isValid":True}),status= 200, mimetype='application/json')
    return response

# Get Profile Details
@app.route('/course/userDetails', methods=["GET"])
def getUserDetailsCourseByAdmin():
    user_id = request.headers.get("user_id")
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT cu.*, cp.package_name as course_name,coh.*  FROM course_users cu left join course_package cp on cu.course = cp.id left join course_order_history coh on coh.user_id = cu.id where cu.id=(%s)""", [user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"User details exist","user_data":result}),status= 200, mimetype='application/json')
    return response


# Upload Question Images
@app.route('/upload-pdf', methods=["POST"])
def uploadQuestionPdf():
    isUpload = False
    response = {}
    file = request.files["study_pdf"]
    seconds = str(time.time()).replace(".","")
    newFile = "material_pdf/"+seconds + "-" + file.filename
    uploadFileToS3(newFile, file)
    image_url = 'https://pdhantu-classes.s3.us-east-2.amazonaws.com/'+newFile
    isUpload = True
    response["isUpload"] = isUpload
    response["imageUrl"] = image_url
    return json.dumps(response)

# Get Subjects 
@app.route('/course/getSubjects', methods=["GET"])
def getSubjectsCourse():
    paper_id = request.headers.get("paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from course_subjects where paper_id =(%s)""",[paper_id])
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Records Available", "subjects":result}),status= 200, mimetype='application/json')
    return response


# Get Video & Pdf 
@app.route('/course/getTopics', methods=["GET"])
def getTopicsCourse():
    course_id = request.headers.get("course_id")
    subject_id = request.headers.get("subject_id")
    batch = request.headers.get("batch")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from course_video_lacture where course_id =(%s) and subject_id = (%s) and batch_id=(%s) order by id desc""",[course_id, subject_id, batch])
    result = cursor.fetchall()
    cursor.execute(""" select * from course_subjects where id = (%s)""",[subject_id])
    subject = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Records Available", "topics":result, "subjectDetails":subject}),status= 200, mimetype='application/json')
    return response


# Get Video & Pdf 
@app.route('/course/getTopicsUsers', methods=["GET"])
def getTopicsCourseUsers():
    course_id = request.headers.get("course_id")
    subject_id = request.headers.get("subject_id")
    user_id = request.headers.get("user_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select batch from course_users where id = (%s)""",[user_id])
    result = cursor.fetchone()
    cursor.execute(""" select * from course_video_lacture where course_id =(%s) and subject_id = (%s) and batch_id=(%s) order by id desc""",[course_id, subject_id,result["batch"]])
    result = cursor.fetchall()
    cursor.execute(""" select * from course_subjects where id = (%s)""",[subject_id])
    subject = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Records Available", "topics":result, "subjectDetails":subject}),status= 200, mimetype='application/json')
    return response

# Add Videos 
@app.route('/course/addTopicVideos', methods=["POST"])
def addTopicVideos():
    course_id = request.json["course_id"]
    subject_id = request.json["subject_id"]
    video_url_link = request.json["video_url_link"]
    topics = request.json["topics"]
    batch =  request.json["batch"]
    created_at = datetime.fromtimestamp(calendar.timegm(time.gmtime()))
    cursor = mysql.connection.cursor()
    # print(course_id,subject_id,topics,video_url_link,created_at)
    if int(course_id) == 1 or int(course_id) == 3:
        cursor.execute(""" insert into course_video_lacture(course_id,subject_id,topics,video_url_link,upload_date,batch_id) values(%s,%s,%s,%s,%s,%s)""",[course_id,subject_id,topics,video_url_link,created_at,batch])
        cursor.execute(""" insert into course_video_lacture(course_id,subject_id,topics,video_url_link,upload_date,batch_id) values(%s,%s,%s,%s,%s,%s)""",[2,subject_id,topics,video_url_link,created_at,batch])
    else:
        cursor.execute(""" insert into course_video_lacture(course_id,subject_id,topics,video_url_link,upload_date,batch_id) values(%s,%s,%s,%s,%s,%s)""",[course_id,subject_id,topics,video_url_link,created_at,batch])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Added Successfully"}),status= 200, mimetype='application/json')
    return response

# Upload Topic Pdf
@app.route('/course/uploadTopicPdf', methods=["POST"])
def uploadTopicPdf():
    topic_id = request.headers.get("topic_id")
    course_id = request.headers.get("course_id")
    file = request.files["study_pdf"]
    seconds = str(time.time()).replace(".","")
    newFile = "material_pdf/"+seconds + "-" + file.filename
    uploadFileToS3(newFile, file)
    pdf_file = 'https://pdhantu-classes.s3.us-east-2.amazonaws.com/'+newFile
    cursor = mysql.connection.cursor()
    cursor.execute("""select * from course_video_lacture where id=(%s)""",[topic_id])
    result = cursor.fetchone()
    if int(course_id) == 1 or int(course_id) == 3:
        cursor.execute("""UPDATE course_video_lacture SET pdf_url_link =(%s) where subject_id=(%s) and topics=(%s) and upload_date=(%s)""", [pdf_file,result["subject_id"],result["topics"], result["upload_date"]])
    else:
        cursor.execute("""UPDATE course_video_lacture SET pdf_url_link =(%s) where id=(%s) """,[pdf_file,topic_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Uploaded Successfully"}),status= 200, mimetype='application/json')
    return response

# Delete Topic
@app.route('/course/deleteVideoLacture', methods=["POST"])
def deleteVideoLacture():
    topic_id = request.json["topic_id"]
    course_id = request.json["course_id"]
    cursor = mysql.connection.cursor()
    cursor.execute("""select * from course_video_lacture where id=(%s)""",[topic_id])
    result = cursor.fetchone()
    if int(course_id) == 1 or int(course_id) == 3:
        cursor.execute("""DELETE from course_video_lacture where subject_id=(%s) and upload_date=(%s)""", [result["subject_id"], result["upload_date"]])
    else:
        cursor.execute("""DELETE from course_video_lacture where id=(%s) """,[topic_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Deleted Successfully"}),status= 200, mimetype='application/json')
    return response

# Get User by Email
@app.route('/course/getUserbyEmail', methods=["GET"])
def getUserbyEmail():
    email = request.headers.get("email")
    cursor = mysql.connection.cursor()
    cursor.execute("""select * from course_users where email=(%s)""",[email])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    if result:
        response =app.response_class(response=json.dumps({"message":"Users exist", "isValid": True, "usersDetails": result }),status= 200, mimetype='application/json')
    else:
        response =app.response_class(response=json.dumps({"message":"Users doesnot exist", "isValid": False }),status= 200, mimetype='application/json')
    return response

# Get User by Email
@app.route('/course/editUserDetails', methods=["PUT"])
def editUserDetails():
    user_id = request.json["user_id"]
    email = request.json["email"]
    batch = request.json["batch"]
    course = request.json["course"]
    price = 0
    if(int(course) == 1):
        price = 2940
    elif(int(course) == 2):
        price = 6940
    elif(int(course) == 3):
        price = 4940
    elif(int(course) == 4):
        price = 4940
    cursor = mysql.connection.cursor()
    cursor.execute("""UPDATE course_users SET email=(%s), course=(%s), batch=(%s) where id =(%s)""",[email,course,batch,user_id])
    cursor.execute("""UPDATE course_order_history SET price=(%s) where user_id =(%s)""",[price,user_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Updated Successfully" }),status= 200, mimetype='application/json')
    return response


@app.route('/course/uploadClassSchedule', methods=["POST"])
def uploadClassSchedule():
    file = request.files["class_schedule"]
    seconds = str(time.time()).replace(".","")
    newFile = "miscellaneous/"+seconds + "-" + file.filename
    uploadFileToS3(newFile, file)
    pdf_file = 'https://pdhantu-classes.s3.us-east-2.amazonaws.com/'+newFile
    cursor = mysql.connection.cursor()
    cursor.execute(""" INSERT INTO course_class_schedule(pdf_link) VALUES(%s)""",[pdf_file])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Uploaded Successfully"}),status= 200, mimetype='application/json')
    return response

@app.route('/course/getClassSchedule', methods=["GET"])
def getClassSchedule():
    cursor = mysql.connection.cursor()
    cursor.execute(""" select id,pdf_link from course_class_schedule order by id desc limit 1 """)
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Pdf Available", "pdf_link":result["pdf_link"]}),status= 200, mimetype='application/json')
    return response

#Paid Users
@app.route('/course/paidUserLists',methods=["GET"])
def getPaidUsersLists():
    batch = request.headers.get("batch")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select u.*, o.* from course_users u inner join course_order_history o on u.id = o.user_id where u.batch = (%s) order by o.id asc""", [batch])
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are", "user_data":result }),status= 200, mimetype='application/json')
    return response

# Check Medium
@app.route('/course/checkMedium',methods=["GET"])
def checkMedium():
    user_id = request.headers.get("user_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select medium from course_users where id=(%s)""",[user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are", "medium":result["medium"] }),status= 200, mimetype='application/json')
    return response

# Add Class Test Prelims
@app.route('/course/addClassTestPrelims',methods=["POST"])
def addClassTestPrelims():
    batch_id = 1
    subject_name = request.json["subject_name"]
    topic_name = request.json["topic_name"]
    no_of_questions = request.json["no_of_questions"]
    paper_time = request.json["paper_time"]
    paper_date = request.json["paper_date"]
    batch = request.json["batch"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" insert into course_test_paper_prelims(batch_id, subject_name, topic_name, no_of_questions, paper_time, paper_date, batch) values(%s,%s,%s,%s,%s,%s,%s)""",[batch_id, subject_name, topic_name, no_of_questions, paper_time, paper_date, batch])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Uploaded Successfully"}),status= 200, mimetype='application/json')
    return response

# Get All Class Test Prelims Admin
@app.route('/course/getClassTestPrelimsAdmin',methods=["GET"])
def getClassTestPrelimsAdmin():
    batch = request.headers.get("batch")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from course_test_paper_prelims where batch = (%s) """,[batch])
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Records Available", "testData": result}),status= 200, mimetype='application/json')
    return response

#Go Live Test Prelims Admin
@app.route('/course/goLiveClassTestPrelims',methods=["PUT"])
def goLiveClassTestPrelims():
    class_test_id = request.json["class_test_id"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" update course_test_paper_prelims set is_active = 1 where id =(%s)""",[class_test_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Updated Successfully"}),status= 200, mimetype='application/json')
    return response

#STOP and Release Rank Test Prelims Admin
@app.route('/course/stopClassTestPrelims',methods=["PUT"])
def stopClassTestPrelims():
    class_test_id = request.json["class_test_id"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" update course_test_paper_prelims set is_active = 0, is_rank_released = 1 where id =(%s)""",[class_test_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Updated Successfully"}),status= 200, mimetype='application/json')
    return response

# Dump Questions of Class Test Prelims
@app.route('/course/dumpQuestionClassTestPrelims', methods=["POST"])
def dumpQuestionClassTestPrelims():
    excel_file = request.files['excel_file']
    prefix_file = str(time.time()).replace(".","")[:11]
    new_name_file = prefix_file + "-" + excel_file.filename
    excel_file.save(new_name_file)
    book = xlrd.open_workbook(new_name_file)
    sheet = book.sheet_by_index(0)
    cursor = mysql.connection.cursor()
    query = """INSERT INTO course_test_paper_questions_prelims(paper_id, question_english, options_english, question_hindi, options_hindi, answer, extras_question, extras_option, question_type) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
    for r in range(1, sheet.nrows):
        paper_id = sheet.cell(r,0).value
        question_english = sheet.cell(r,1).value
        options_english = sheet.cell(r,2).value
        answer =  sheet.cell(r,3).value
        question_hindi = sheet.cell(r,4).value
        options_hindi = sheet.cell(r,5).value
        extras_question = sheet.cell(r,6).value
        extras_option = sheet.cell(r,7).value
        question_type = sheet.cell(r,8).value

        values = (paper_id, question_english, options_english, question_hindi, options_hindi, answer, extras_question, extras_option, question_type)     
        print(values)
        cursor.execute(query, values)

    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Sucessfully Uploaded"}),status= 200, mimetype='application/json')
    return response

# Get Class Test Questions Prelims Admin
@app.route('/course/getQuestionsByTestIdPrelims',methods=["GET"])
def getQuestionsByTestIdPrelims():
    questions_data = []
    test_paper_id = request.headers.get("test_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from course_test_paper_questions_prelims where paper_id = (%s) order by id asc""",[test_paper_id])
    results = cursor.fetchall()
    for result in results:
        temp_data = {}
        temp_data["id"] = result["id"]

        if result["question_english"]:
            temp_data["question_english"] = result["question_english"].split('$')
        else:
            temp_data["question_english"] = ""

        if result["options_english"]:
            temp_data["options_english"] = result["options_english"].split('$')
        else:
            temp_data["options_english"] = ["","","",""]

        if result["question_hindi"]:
            temp_data["question_hindi"] = result["question_hindi"].split('$')
        else:
            temp_data["question_hindi"] = ""

        if result["options_hindi"]:
            temp_data["options_hindi"] = result["options_hindi"].split('$')
        else:
            temp_data["options_hindi"] = ["","","",""]
        
        if result["extras_question"]:
            temp_data["extras_question"] = result["extras_question"].split('$')
        else:
            temp_data["extras_question"] = []

        if result["extras_option"]:
            temp_data["extras_option"] = result["extras_option"].split('$')
        else:
            temp_data["extras_option"] = []
        temp_data["question_type"] = result["question_type"]
        temp_data["answer"] = result["answer"]
        questions_data.append(temp_data)
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Questions data are", "questions":questions_data}),status= 200, mimetype='application/json')
    return response

# Get Class Test Question Prelims Admin
@app.route('/course/getQuestionsByIdPrelims', methods=["GET"])
def getQuestionsByIdPrelims():
    questions_id = request.headers.get("questions_id")
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT * from course_test_paper_questions_prelims where id = (%s)""", [questions_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Test Questions details","question_list":result}),status= 200, mimetype='application/json')
    return response

# Edit Class Test Questions Admin
@app.route('/course/editQuestionsByIdPrelims', methods=["PUT"])
def editQuestionsByIdPrelims():
    questions_id = request.json["questions_id"]
    question_english = request.json["question_english"]
    options_english = request.json["options_english"]
    question_hindi = request.json["question_hindi"]
    options_hindi = request.json["options_hindi"]
    answer =  request.json["answer"]
    extras_question = request.json["extras_question"]
    extras_option = request.json["extras_option"]
    question_type = request.json["question_type"]

    cursor = mysql.connection.cursor()
    cursor.execute(""" update course_test_paper_questions_prelims set question_english=(%s), options_english=(%s), question_hindi=(%s), options_hindi=(%s),answer=(%s),extras_question=(%s),extras_option=(%s), question_type=(%s) where id=(%s) """, [question_english, options_english, question_hindi, options_hindi, answer, extras_question, extras_option, question_type, questions_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"SuccessfullgetMockQuestionsByIdy Updated"}),status= 200, mimetype='application/json')
    return response

# Get All Test Tesr Paper with Status Prelims User
@app.route('/course/getAllClassTestPrelims',methods=["GET"])
def getAllClassTestPrelims():
    user_id = request.headers.get("user_id")
    test_paper_data = []
    cursor = mysql.connection.cursor()
    cursor.execute(""" select batch from course_users where id=(%s)""",[user_id])
    result = cursor.fetchone()
    cursor.execute(""" select * from course_test_paper_prelims where batch =(%s)""",[result["batch"]])
    test_papers = cursor.fetchall()
    cursor.execute(""" select * from course_test_paper_submissions_prelims where user_id = (%s)""",[user_id])
    user_submissions = cursor.fetchall()
    for test_p in test_papers:
        temp_dict = {}
        is_attempted = 0
        for user_s in user_submissions:
            if user_s["test_paper_id"] == test_p["id"]:
                is_attempted = user_s["is_attempted"]
                break
        temp_dict["id"] = test_p["id"]
        temp_dict["subject_name"] = test_p["subject_name"]
        temp_dict["topic_name"] = test_p["topic_name"]
        temp_dict["no_of_questions"] = test_p["no_of_questions"]
        temp_dict["paper_date"] = test_p["paper_date"]
        temp_dict["paper_time"] = test_p["paper_time"]
        temp_dict["is_active"] = test_p["is_active"]
        temp_dict["is_rank_released"] = test_p["is_rank_released"]
        temp_dict["is_attempted"] = is_attempted
        test_paper_data.append(temp_dict)
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Test Papers are", "test_paper":test_paper_data}),status= 200, mimetype='application/json')
    return response

# Check Test Attempted
@app.route('/course/checkClassTestAttempted',methods=["GET"])
def checkClassTestAttempted():
    user_id = request.headers.get("user_id")
    test_paper_id = request.headers.get("test_paper_id")
    isValid = True
    cursor = mysql.connection.cursor()
    cursor.execute(""" select id from course_test_paper_submissions_prelims where test_paper_id = (%s) and user_id = (%s)""", [test_paper_id,user_id])
    is_submission = cursor.fetchone()
    if is_submission:
        isValid = False
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Check Class Test Submitted", "isValid":isValid}),status= 200, mimetype='application/json')
    return response   


# Get Class Test Questions Prelims
@app.route('/course/getQuestionsClassTest/<int:id>',methods=["GET"])
def getQuestionsClassTest(id):
    questions_data = []
    cursor = mysql.connection.cursor()
    cursor.execute(""" select no_of_questions from course_test_paper_prelims where id = (%s) """,[id])
    questions = cursor.fetchone()
    cursor.execute(""" select * from course_test_paper_questions_prelims where paper_id = (%s) order by id asc limit %s """,[id,questions["no_of_questions"]])
    results = cursor.fetchall()
    for result in results:
        temp_data = {}
        temp_data["id"] = result["id"]

        if result["question_english"]:
            temp_data["question_english"] = result["question_english"].split('$')
        else:
            temp_data["question_english"] = ""

        if result["options_english"]:
            temp_data["options_english"] = result["options_english"].split('$')
        else:
            temp_data["options_english"] = ["","","","",""]

        if result["question_hindi"]:
            temp_data["question_hindi"] = result["question_hindi"].split('$')
        else:
            temp_data["question_hindi"] = ""

        if result["options_hindi"]:
            temp_data["options_hindi"] = result["options_hindi"].split('$')
        else:
            temp_data["options_hindi"] = ["","","","",""]
        
        if result["extras_question"]:
            temp_data["extras_question"] = result["extras_question"].split('$')
        else:
            temp_data["extras_question"] = []

        if result["extras_option"]:
            temp_data["extras_option"] = result["extras_option"].split('$')
        else:
            temp_data["extras_option"] = []
        temp_data["question_type"] = result["question_type"]
        questions_data.append(temp_data)
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Questions data are", "questions":questions_data}),status= 200, mimetype='application/json')
    return response


# Post Response 
@app.route('/course/postResponseClassTestPrelims',methods=["POST"])
def postResponseClassTestPrelims():
    i = 0
    test_response = request.json["responses"]
    responses = test_response.split(',')
    test_paper_id = request.json["test_paper_id"]
    user_id = request.json["user_id"]
    paper_time_taken = request.json["paper_time_taken"]
    print(test_paper_id)
    submission_at = datetime.fromtimestamp(calendar.timegm(time.gmtime()))
    correct = 0
    incorrect = 0
    total_marks = 0
    accuracy = 0
    attempted = 0
    not_attempted = 0
    total_questions = 0
    percentage = 0
    cursor = mysql.connection.cursor()

    cursor.execute(""" select id from course_test_paper_submissions_prelims where user_id = (%s) and test_paper_id =(%s) """,[user_id, test_paper_id])
    is_already_exist = cursor.fetchone()
    
    if is_already_exist:
        response =app.response_class(response=json.dumps({"message":"Response Submitted"}),status= 200, mimetype='application/json')
    else:
        cursor.execute(""" select no_of_questions from course_test_paper_prelims where id = (%s) """,[test_paper_id])
        questions = cursor.fetchone()
        total_questions = questions["no_of_questions"]

        cursor.execute(""" select answer from course_test_paper_questions_prelims where paper_id = (%s) order by id asc limit %s """,[test_paper_id,total_questions])
        answers = cursor.fetchall()

        for answer in answers:
            if responses[i] != "":
                if answer["answer"].lower() == responses[i]:
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
        percentage = int(round((correct / int(total_questions)), 2)*100)

        # print(total_marks, accuracy, attempted, not_attempted, total_questions, correct, incorrect, paper_time_taken, user_id,percentage, test_paper_id, test_response, submission_at)
        cursor.execute("""insert into course_test_paper_submissions_prelims (user_id, test_paper_id, responses, total_questions, correct, incorrect, attempted, not_attempted, total_marks, accuracy, paper_time_taken, percentage, submission_at) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",[user_id,test_paper_id,test_response,total_questions,correct,incorrect,attempted,not_attempted,total_marks,accuracy,paper_time_taken, percentage, submission_at])
        mysql.connection.commit()
        cursor.close()
        response =app.response_class(response=json.dumps({"message":"Response Submitted"}),status= 200, mimetype='application/json')
    return response


# Get Response 
@app.route('/course/getResponsesClassTestPrelims',methods=["GET"])
def getResponsesClassTestPrelims():
    test_paper_id = request.headers.get("test_paper_id")
    user_id = request.headers.get("user_id")
    questions_data = []
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from course_test_paper_prelims where id = (%s) """,[test_paper_id])
    questions = cursor.fetchone()
    total_questions = questions["no_of_questions"]

    cursor.execute(""" select * from course_test_paper_questions_prelims where paper_id = (%s) order by id asc limit %s """,[test_paper_id,total_questions])
    questions = cursor.fetchall()
    for result in questions:
        temp_data = {}
        temp_data["id"] = result["id"]

        if result["question_english"]:
            temp_data["question_english"] = result["question_english"]
        else:
            temp_data["question_english"] = ""

        if result["options_english"]:
            temp_data["options_english"] = result["options_english"].split('$')
        else:
            temp_data["options_english"] = ["","","",""]

        if result["question_hindi"]:
            temp_data["question_hindi"] = result["question_hindi"]
        else:
            temp_data["question_hindi"] = ""

        if result["options_hindi"]:
            temp_data["options_hindi"] = result["options_hindi"].split('$')
        else:
            temp_data["options_hindi"] = ["","","",""]

        if result["extras_question"]:
            temp_data["extras_question"] = result["extras_question"].split('$')
        else:
            temp_data["extras_question"] = []

        if result["extras_option"]:
            temp_data["extras_option"] = result["extras_option"].split('$')
        else:
            temp_data["extras_option"] = []
        temp_data["question_type"] = result["question_type"]
        temp_data["answer"] = result["answer"]
        questions_data.append(temp_data)

    cursor.execute(""" select * from course_test_paper_submissions_prelims s join course_test_paper_prelims p on s.test_paper_id = p.id where s.test_paper_id = (%s) and s.user_id =(%s) """,[test_paper_id,user_id])
    responses = cursor.fetchone()

    temp_response = {}
    if responses:
        temp_response["id"] = responses["id"]
        temp_response["user_id"] = responses["user_id"]
        temp_response["test_paper_id"] = responses["test_paper_id"]
        temp_response["responses"] = responses["responses"].split(',')
        temp_response["total_questions"] = responses["total_questions"]
        temp_response["correct"] = responses["correct"]
        temp_response["incorrect"] = responses["incorrect"]
        temp_response["attempted"] = responses["attempted"]
        temp_response["not_attempted"] = responses["not_attempted"]
        temp_response["total_marks"] = responses["total_marks"]
        temp_response["accuracy"] = responses["accuracy"]
        temp_response["percentage"] = responses["percentage"]
        temp_response["paper_time_taken"] = responses["paper_time_taken"]
        temp_response["paper_id"] = responses["p.id"]
        temp_response["subject_name"] = responses["subject_name"]
        temp_response["topic_name"] = responses["topic_name"]

    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Responses Available", "questions":questions_data,"user_response":temp_response,"isValid":True}),status= 200, mimetype='application/json')
    return response


# Get Rank List 
@app.route('/course/getRankMockPaper',methods=["GET"])
def getRankClassTestPaper():
    test_paper_id = request.headers.get("test_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select us.id as user_id, us.firstname as user_firstname, us.lastname as user_lastname,us.email as user_email, ms.total_marks as marks, ms.accuracy as accuracy, ms.paper_time_taken as paper_time from course_test_paper_submissions_prelims ms join course_users us on ms.user_id = us.id where ms.test_paper_id = (%s) order by ms.total_marks desc, ms.accuracy desc, ms.paper_time_taken asc""",[test_paper_id])
    ranks = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Responses Available", "ranks":ranks, "isValid":True}),status= 200, mimetype='application/json')
    return response

# Get Users List 
@app.route('/course/allUsersList',methods=["GET"])
def allUsersListCourse():
    batch = request.headers.get("batch")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select id, firstname, lastname, email, mobile from course_users where batch = (%s)""", [batch])
    allUsers = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Responses Available", "allUsers":allUsers, "isValid":True}),status= 200, mimetype='application/json')
    return response

@app.route('/course/getStudentBatch',methods=["GET"])
def getStudentBatch():
    user_id = request.headers.get("user_id")
    print(user_id)
    cursor = mysql.connection.cursor()
    cursor.execute(""" select batch from course_users where id = (%s)""",[user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Batch Available","batch": result["batch"]}),status= 200, mimetype='application/json')
    return response

@app.route('/course/getCurrentAffairs',methods=["GET"])
def getCurrentAffairsCourse():
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from course_current_affairs order by id desc""")
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Records Available","currentAffairs": result}),status= 200, mimetype='application/json')
    return response

@app.route('/course/addCurrentAffairs',methods=["POST"])
def addCurrentAffairsCourse():
    topics = request.json["topics"]
    video_url_link = request.json["video_url_link"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" insert into course_current_affairs(topics,video_url_link) values(%s,%s)""",[topics,video_url_link])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Uploaded Successfully"}),status= 200, mimetype='application/json')
    return response

# Get Users List 
@app.route('/allUsersList',methods=["GET"])
def allUsersList():
    cursor = mysql.connection.cursor()
    cursor.execute(""" select id, firstname, lastname, email, mobile from users """)
    allUsers = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Responses Available", "allUsers":allUsers, "isValid":True}),status= 200, mimetype='application/json')
    return response

############################## Website Service #################################

@app.route('/postNotice',methods=["POST"])
def postNotice():
    notice = request.json["notice"]
    link = request.json["link"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" insert into notice(notice, link) values(%s,%s)""",[notice, link])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Uploaded Successfully"}),status= 200, mimetype='application/json')
    return response

@app.route('/postCurrentAffairs',methods=["POST"])
def postCurrentAffairs():
    current_affairs = request.json["current_affairs"]
    link = request.json["link"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" insert into current_affairs(current_affairs, link) values(%s,%s)""",[current_affairs, link])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Uploaded Successfully"}),status= 200, mimetype='application/json')
    return response

@app.route('/inactiveNotice',methods=["PUT"])
def inactiveNotice():
    notice_id = request.json["notice_id"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" update notice set is_active = 0 where id =(%s)""",[notice_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Updated Successfully"}),status= 200, mimetype='application/json')
    return response

@app.route('/inactiveCurrentAffairs',methods=["PUT"])
def inactiveCurrentAffairs():
    current_affairs_id = request.json["current_affairs_id"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" update current_affairs set is_active = 0  where id =(%s)""",[current_affairs_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Updated Successfully"}),status= 200, mimetype='application/json')
    return response

@app.route('/getNoticeAll',methods=["GET"])
def getNotice():
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from notice order by id desc""")
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Records Available", "noticeData": result}),status= 200, mimetype='application/json')
    return response

@app.route('/getNoticeActivate',methods=["GET"])
def getNoticeActivate():
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from notice where is_active = 1""")
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Records Available","noticeData": result}),status= 200, mimetype='application/json')
    return response

@app.route('/getCurrentAffairsAll',methods=["GET"])
def getCurrentAffairsAll():
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from current_affairs order by id desc""")
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Updated Successfully","currentAffairsData": result}),status= 200, mimetype='application/json')
    return response

@app.route('/getCurrentAffairsActive',methods=["GET"])
def getCurrentAffairsActive():
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from current_affairs where is_active = 1""")
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Updated Successfully","currentAffairsData": result}),status= 200, mimetype='application/json')
    return response



#                                              CGPSC Test Series


# SignUp
@app.route('/testseries/signup', methods=['POST'])
def signUpTestSeries():
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
    cursor.execute("""SELECT * FROM testseries_users""")
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
            """INSERT INTO testseries_users (firstname, lastname, email, mobile, password_hash, password_salt, sign_up_method, is_active, role, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """, (
                firstname, lastname, email, mobile, password_hash, password_salt, "NORMAL", True, "USER", created_at)
        )
        mysql.connection.commit()
        cursor.close()
        response = app.response_class(response=json.dumps(
            {"message": "Sign Up Successfully", "isValid": True}), status=200, mimetype='application/json')
        return response


# User Login
@app.route('/testseries/login', methods=["POST"])
def userLoginTestSeries():
    email = request.json["email"]
    password = request.json["password"]
    isUserExist = False
    cursor = mysql.connection.cursor()
    cursor.execute(
        """SELECT * FROM testseries_users where email=(%s)""", [email])
    user_data = cursor.fetchone()
    response = {}
    if user_data:
        if str(user_data["password_hash"]) == str(md5_hash(password+user_data["password_salt"])):
            isUserExist = True

        if isUserExist:
            print(user_data)
            encoded_jwt = jwt.encode({"user_id": user_data["id"], "firstname": user_data["firstname"],"lastname":user_data["lastname"],"mobile":user_data["mobile"],
                                      "email": user_data["email"], "role": user_data["role"],"module": user_data["module"]}, 'secretkey', algorithm='HS256').decode("utf-8")
            response = app.response_class(response=json.dumps({"message": "Login Success", "isValid": True, "token": encoded_jwt, "image_url": user_data["image_url"]}), status=200, mimetype='application/json')
            return response
        else:
            response = app.response_class(response=json.dumps({"message": "Wrong Credential", "isValid": False}), status=200, mimetype='application/json')
            return response
    else:
        response =app.response_class(response=json.dumps({"message":"User do not exists, Please sign up"}),status= 200, mimetype='application/json')
        return response

# User Forget Password
@app.route('/testseries/forgetPassword', methods=["POST"])
def forgetPasswordTestSeries():
    email = request.json["email"]
    mobile = request.json["mobile"]
    isUserExist = False
    cursor = mysql.connection.cursor()
    cursor.execute(
        """SELECT * FROM testseries_users where email=(%s) AND mobile=(%s)""", [email, mobile])
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
@app.route('/testseries/changePassword', methods=["PUT"])
def changePasswordTestSeries():
    user_id = request.json["user_id"]
    password = request.json["password"]
    password_salt = generate_salt()
    password_hash = md5_hash(password + password_salt)
    cursor = mysql.connection.cursor()
    cursor.execute("""UPDATE testseries_users SET password_hash = (%s), password_salt = (%s) where id = (%s)""", [password_hash,password_salt,user_id])
    mysql.connection.commit()
    cursor.close()
    response = app.response_class(response=json.dumps({"message": "Password Change Successfully", "isValid": True}), status=200, mimetype='application/json')
    return response


# Razorpay Create Order
@app.route('/testseries/createOrder', methods=['POST'])
def createOrderTestSeries():
    package_id = request.json["package_id"]
    user_id = request.json["user_id"]
    initiate_at = datetime.fromtimestamp(calendar.timegm(time.gmtime()))
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT package_price FROM testseries_mock_package where id=(%s)""", [package_id])
    result = cursor.fetchone()
    paye_id = randomString(10)
    order_amount = int(result["package_price"]) * 100
    order_currency = 'INR'
    order_receipt = 'order_'+paye_id
    cursor.execute("""INSERT into testseries_order_initiates(order_id, user_id, package_id, price, initiate_at) values(%s,%s,%s,%s,%s)""", [order_receipt, user_id ,package_id, order_amount/100, initiate_at])
    razorId = razorpay_client.order.create(
        amount=order_amount, currency=order_currency, receipt=order_receipt, payment_capture='1')
    mysql.connection.commit()
    cursor.close()
    return json.dumps(razorId["id"])


# Razorpay Verify Signature
@app.route('/testseries/verifyRazorpaySucces', methods=['POST'])
def verifyPaymentTestSeries():
    user_id = request.json["user_id"]
    package_id=request.json["package_id"]
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
    cursor.execute("""SELECT package_price FROM testseries_mock_package where id=(%s)""", [package_id])
    result = cursor.fetchone()
    cursor.execute("""UPDATE testseries_order_initiates SET status = (%s) where user_id =(%s) and package_id=(%s)""",[status,user_id,package_id])
    cursor.execute("""INSERT into testseries_order_history(payment_id,order_id,user_id,price,order_at,status,package_id) values(%s,%s,%s,%s,%s,%s,%s)""", [request_payment_id,request_order_id,user_id,result["package_price"],order_at,status,package_id])
    mysql.connection.commit()
    cursor.close()
    return json.dumps({"isSuccess": is_success})


# Upload Profile Image
@app.route('/testseries/upload-image', methods=["POST"])
def uploadImageTestSeries():
    isUpload = False
    response = {}
    user_id = request.headers.get("user_id")
    file = request.files["file"]
    seconds = str(time.time()).replace(".","")
    newFile = "user-images/"+seconds + "-" + file.filename
    uploadFileToS3(newFile, file)
    image_url = 'https://pdhantu-classes.s3.us-east-2.amazonaws.com/'+newFile
    cursor = mysql.connection.cursor()
    cursor.execute("""UPDATE testseries_users SET image_url =(%s) where id=(%s)""", [image_url,user_id])
    mysql.connection.commit()
    cursor.close()
    isUpload = True
    response["isUpload"] = isUpload
    response["imageUrl"] = image_url
    return json.dumps(response)


# Check User Registered
@app.route('/testseries/isUserRegister/<int:user_id>', methods=["GET"])
def isUserRegisterTestSeries(user_id):
    cursor = mysql.connection.cursor()
    isValid = False
    cursor.execute("""SELECT * FROM testseries_users where id=(%s)""", [user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    if result["whatsapp"] and result["graduation_year"] and result["preparing_for"]:
        isValid = True
    response =app.response_class(response=json.dumps({"message":"User details exist","isValid":isValid, "package_id":result["preparing_for"]}),status= 200, mimetype='application/json')
    return response


# Get Profile Details
@app.route('/testseries/userDetails/<int:user_id>', methods=["GET"])
def getUserDetailsTestSeries(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT id,firstname,lastname,email,mobile,image_url,role, whatsapp,graduation_year,preparing_for  FROM testseries_users where id=(%s)""", [user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"User details exist","user_data":result}),status= 200, mimetype='application/json')
    return response


# Change Profile Details 
@app.route('/testseries/userDetails/<int:user_id>', methods=["PUT"])
def pstUserDetailsTestSeries(user_id):
    whatsapp = request.json["whatsapp"]
    graduation_year = request.json["graduation_year"]
    course = request.json["course"]
    cursor = mysql.connection.cursor()
    cursor.execute("""UPDATE testseries_users SET whatsapp =(%s), graduation_year=(%s), preparing_for=(%s) where id=(%s)""", [whatsapp,graduation_year,course,user_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"User Data Added Successfully"}),status= 200, mimetype='application/json')
    return response


# User Order Details
@app.route('/testseries/orderDetails/<int:user_id>', methods=["GET"])
def getOrderDetailsTestSeries(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT * FROM testseries_order_history where user_id =(%s) AND status ="success" """, [user_id])
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Order Details are","order_data":result}),status= 200, mimetype='application/json')
    return response


# Check Package Buy or NOT
@app.route('/testseries/isPackageBuy/<int:user_id>',methods=["GET"])
def checkOrderDetailsTestSeries(user_id):
    isValid = False
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT id FROM testseries_order_history where user_id =(%s) AND status ="success" limit 1""", [user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    if result:
        isValid = True
    response =app.response_class(response=json.dumps({"isValid":isValid}),status= 200, mimetype='application/json')
    return response


# Get All Test Series bought by User
@app.route('/testseries/myTestSeries/<int:user_id>',methods=["GET"])
def myTestSeriesTestSeries(user_id):
    isValid = False
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT id FROM testseries_order_history where user_id =(%s) AND status ="success" limit 1""", [user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    if result:
        isValid = True
    response =app.response_class(response=json.dumps({"isValid":isValid}),status= 200, mimetype='application/json')
    return response

# Get User Test Series bought by User
@app.route('/testseries/myTestSeriesPackage',methods=["GET"])
def myTestSeriesPackageTestSeries():
    user_id = request.headers.get("user_id")
    isValid = False
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT preparing_for FROM testseries_users where id =(%s) """, [user_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    if result:
        isValid = True
    response =app.response_class(response=json.dumps({"package_id":result["preparing_for"]}),status= 200, mimetype='application/json')
    return response


@app.route('/testseries/getAllMockPaper',methods=["GET"])
def getAllMockPaperTestSeries():
    package_id = request.headers.get("package_id")
    user_id = request.headers.get("user_id")
    mock_paper_data = []
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from testseries_mock_paper where package_id=(%s)""", [package_id])
    mock_papers = cursor.fetchall()
    cursor.execute(""" select * from testseries_mock_submissions where user_id = (%s)""",[user_id])
    user_submissions = cursor.fetchall()
    for mock_p in mock_papers:
        temp_dict = {}
        is_attempted = 0
        is_live_attempted = 0
        for user_s in user_submissions:
            if user_s["mock_paper_id"] == mock_p["id"]:
                is_attempted = user_s["is_attempted"]
                is_live_attempted = user_s["is_live_attempted"]
                break
        temp_dict["id"] = mock_p["id"]
        temp_dict["mock_paper_name"] = mock_p["mock_paper_name"]
        temp_dict["mock_description"] = mock_p["mock_description"]
        temp_dict["paper_date"] = mock_p["paper_date"]
        temp_dict["is_active"] = mock_p["is_active"]
        temp_dict["is_finished"] = mock_p["is_finished"]
        temp_dict["is_result_released"] = mock_p["is_result_released"]
        temp_dict["paper_pdf"] = mock_p["paper_pdf"]
        temp_dict["paper_time"] = mock_p["paper_time"]
        temp_dict["total_questions"] = mock_p["total_questions"]
        temp_dict["is_attempted"] = is_attempted
        temp_dict["is_live_attempted"] = is_live_attempted
        mock_paper_data.append(temp_dict)
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Mock Papers are", "mock_paper":mock_paper_data}),status= 200, mimetype='application/json')
    return response


# Get All Test Mock Paper with Status

@app.route('/testseries/getMockPaperDetails',methods=["GET"])
def getMockPaperDetailsTestSeries():
    mock_paper_id = request.headers.get("mock_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from testseries_mock_paper where id =(%s)""",[mock_paper_id])
    mock_paper = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Mock Paper Details", "mock_paper":mock_paper}),status= 200, mimetype='application/json')
    return response


# Get Only Live For Home

@app.route('/testseries/getOnlyLiveTest',methods=["GET"])
def getOnlyLiveTestTestSeries():
    user_id = request.headers.get("user_id")
    is_attempted = 0
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from testseries_mock_paper where is_active = 0 and is_finished = 0""")
    mock_paper = cursor.fetchone()
    cursor.execute(""" select * from testseries_mock_submissions where user_id = (%s) and mock_paper_id = (%s)""",[user_id,mock_paper["id"]])
    user_submissions = cursor.fetchone()
    if user_submissions:
        is_attempted = 1
    mock_paper["is_attempted"] =is_attempted
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Live Paper Details", "live_mock_paper":mock_paper}),status= 200, mimetype='application/json')
    return response

# Get Questions 
@app.route('/testseries/getQuestions/<int:id>',methods=["GET"])
def getMockQuestionTestSeries(id):
    questions_data = []
    cursor = mysql.connection.cursor()
    cursor.execute(""" select total_questions from testseries_mock_paper where id = (%s) """,[id])
    questions = cursor.fetchone()
    cursor.execute(""" select * from testseries_mock_questions where paper_id = (%s) order by id asc limit %s """,[id,questions["total_questions"]])
    results = cursor.fetchall()
    for result in results:
        temp_data = {}
        temp_data["id"] = result["id"]

        if result["question_english"]:
            temp_data["question_english"] = result["question_english"].split('$')
        else:
            temp_data["question_english"] = ""

        if result["options_english"]:
            temp_data["options_english"] = result["options_english"].split('$')
        else:
            temp_data["options_english"] = ["","","",""]

        if result["question_hindi"]:
            temp_data["question_hindi"] = result["question_hindi"].split('$')
        else:
            temp_data["question_hindi"] = ""

        if result["options_hindi"]:
            temp_data["options_hindi"] = result["options_hindi"].split('$')
        else:
            temp_data["options_hindi"] = ["","","",""]
        
        if result["extras_question"]:
            temp_data["extras_question"] = result["extras_question"].split('$')
        else:
            temp_data["extras_question"] = []

        if result["extras_option"]:
            temp_data["extras_option"] = result["extras_option"].split('$')
        else:
            temp_data["extras_option"] = []
        temp_data["question_type"] = result["question_type"]
        questions_data.append(temp_data)
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Questions data are", "questions":questions_data}),status= 200, mimetype='application/json')
    return response

# Post Response 
@app.route('/testseries/postResponse',methods=["POST"])
def postMockResponseTestSeries():
    i = 0
    test_response = request.json["responses"]
    responses = test_response.split(',')
    mock_paper_id = request.json["mock_paper_id"]
    user_id = request.json["user_id"]
    paper_time_taken = request.json["paper_time_taken"]
    print(mock_paper_id)
    submission_at = datetime.fromtimestamp(calendar.timegm(time.gmtime()))
    correct = 0
    incorrect = 0
    total_marks = 0
    accuracy = 0
    attempted = 0
    not_attempted = 0
    total_questions = 0
    is_live_attempted = 0
    cursor = mysql.connection.cursor()

    cursor.execute(""" select id from testseries_mock_submissions where user_id = (%s) and mock_paper_id =(%s) """,[user_id,mock_paper_id])
    is_already_exist = cursor.fetchone()
    
    if is_already_exist:
        response =app.response_class(response=json.dumps({"message":"Response Submitted"}),status= 200, mimetype='application/json')
    else:
        cursor.execute(""" select total_questions,is_active from testseries_mock_paper where id = (%s) """,[mock_paper_id])
        questions = cursor.fetchone()
        total_questions = questions["total_questions"]
        is_live_attempted = questions["is_active"]

        cursor.execute(""" select answer from testseries_mock_questions where paper_id = (%s) order by id asc limit %s """,[mock_paper_id,total_questions])
        answers = cursor.fetchall()

        for answer in answers:
            if responses[i] != "":
                print(responses[i], answer)
                if answer["answer"].lower() == responses[i]:
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
        cursor.execute("""insert into testseries_mock_submissions (user_id, mock_paper_id, responses, total_questions, correct, incorrect, attempted, not_attempted, total_marks, accuracy, paper_time_taken, is_live_attempted, submission_at) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",[user_id,mock_paper_id,test_response,total_questions,correct,incorrect,attempted,not_attempted,total_marks,accuracy,paper_time_taken, is_live_attempted, submission_at])
        mysql.connection.commit()
        cursor.close()
        response =app.response_class(response=json.dumps({"message":"Response Submitted"}),status= 200, mimetype='application/json')
    return response



# Get Response 
@app.route('/testseries/getResponses',methods=["GET"])
def getMockResponseTestSeries():
    mock_paper_id = request.headers.get("mock_paper_id")
    user_id = request.headers.get("user_id")
    questions_data = []
    print(mock_paper_id,user_id)
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from testseries_mock_paper where id = (%s) """,[mock_paper_id])
    questions = cursor.fetchone()
    total_questions = questions["total_questions"]

    cursor.execute(""" select * from testseries_mock_questions where paper_id = (%s) order by id asc limit %s """,[mock_paper_id,total_questions])
    questions = cursor.fetchall()
    for result in questions:
        temp_data = {}
        temp_data["id"] = result["id"]

        if result["question_english"]:
            temp_data["question_english"] = result["question_english"]
        else:
            temp_data["question_english"] = ""

        if result["options_english"]:
            temp_data["options_english"] = result["options_english"].split('$')
        else:
            temp_data["options_english"] = ["","","",""]

        if result["question_hindi"]:
            temp_data["question_hindi"] = result["question_hindi"]
        else:
            temp_data["question_hindi"] = ""

        if result["options_hindi"]:
            temp_data["options_hindi"] = result["options_hindi"].split('$')
        else:
            temp_data["options_hindi"] = ["","","",""]

        if result["extras_question"]:
            temp_data["extras_question"] = result["extras_question"].split('$')
        else:
            temp_data["extras_question"] = []

        if result["extras_option"]:
            temp_data["extras_option"] = result["extras_option"].split('$')
        else:
            temp_data["extras_option"] = []
        temp_data["question_type"] = result["question_type"]
        temp_data["answer"] = result["answer"]
        questions_data.append(temp_data)

    cursor.execute(""" select * from testseries_mock_submissions s join testseries_mock_paper p on s.mock_paper_id = p.id where s.mock_paper_id = (%s) and s.user_id =(%s) """,[mock_paper_id,user_id])
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

# Get Rank List 
@app.route('/testseries/getRankMockPaper',methods=["GET"])
def getRankMockPaperTestSeries():
    mock_paper_id = request.headers.get("mock_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select us.id as user_id, us.firstname user_firstname, us.lastname as user_lastname,us.email as user_email, ms.total_marks as marks, ms.accuracy as accuracy, ms.paper_time_taken as paper_time from testseries_mock_submissions ms join testseries_users us on ms.user_id = us.id where ms.mock_paper_id = (%s) and ms.is_live_attempted = 1 order by ms.total_marks desc, ms.accuracy desc, ms.paper_time_taken asc""",[mock_paper_id])
    ranks = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Responses Available", "questions":ranks, "isValid":True}),status= 200, mimetype='application/json')
    return response

# Get Mock Time
@app.route('/testseries/getMockPaperTime',methods=["GET"])
def getMockPaperTimeTestSeries():
    mock_paper_id = request.headers.get("mock_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select paper_time from testseries_mock_paper where id = (%s) """,[mock_paper_id])
    paper_time = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Time Available", "paper_time":paper_time["paper_time"], "isValid":True}),status= 200, mimetype='application/json')
    return response

# Check Test Attempted
@app.route('/testseries/checkTestAttempted',methods=["GET"])
def checkTestAttemptedTestSeries():
    user_id = request.headers.get("user_id")
    mock_paper_id = request.headers.get("mock_paper_id")
    print(user_id,mock_paper_id)
    isValid = True
    cursor = mysql.connection.cursor()
    cursor.execute(""" select id from testseries_mock_submissions where mock_paper_id = (%s) and user_id = (%s)""", [mock_paper_id,user_id])
    is_submission = cursor.fetchone()
    print(is_submission)
    if is_submission:
        isValid = False
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Check Mock Submitted", "isValid":isValid}),status= 200, mimetype='application/json')
    return response   

# Check Paid User or Not
@app.route('/testseries/checkValidUser',methods=["GET"])
def checkPaidUserTestSeries():
    user_id = request.headers.get("user_id")
    isValid = False
    cursor = mysql.connection.cursor()
    cursor.execute(""" select id from testseries_order_history where user_id = (%s)""", [user_id])
    check = cursor.fetchone()
    if check:
        isValid = True
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Check Paid User", "isValid":isValid}),status= 200, mimetype='application/json')
    return response


# ---------------------------------------------Admin End----------------------------------------



# Admin Login
@app.route('/testseries/adminLogin', methods=["POST"])
def adminLoginTestSeries():
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
@app.route('/testseries/adminDashboard',methods=["GET"])
def adminDashboardTestSeries():
    cursor = mysql.connection.cursor()
    cursor.execute(""" select count(*) as total from testseries_users""")
    total = cursor.fetchone()
    cursor.execute(""" select count(*) as total from testseries_users u join testseries_order_history o on u.id = o.user_id""")
    paid = cursor.fetchone()
    cursor.execute(""" select count(*) as total from testseries_users left outer join testseries_order_history on testseries_users.id = testseries_order_history.user_id where testseries_order_history.user_id is null""")
    unpaid = cursor.fetchone()
    cursor.execute(""" select count(*) as total from testseries_users where preparing_for = 1 """)
    cgacf = cursor.fetchone()
    cursor.execute(""" select count(*) as total from testseries_users where preparing_for = 2 """)
    cgpsc = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are:", "total_user":total["total"], "paid_user": paid['total'], "unpaid_user": unpaid["total"], "CGACF":cgacf["total"], "CGPSC":cgpsc["total"] }),status= 200, mimetype='application/json')
    return response

#All Users
@app.route('/testseries/allUsers',methods=["GET"])
def getAllUsersTestSeries():
    page = request.headers.get("page")
    offset = 20*(int(page)-1)
    cursor = mysql.connection.cursor()
    cursor.execute(""" select id, firstname, lastname, email, mobile, image_url, created_at, whatsapp, graduation_year, preparing_for from testseries_users order by id desc limit 20 offset %s """,[offset])
    result = cursor.fetchall()
    cursor.execute(""" select count(*) as total from testseries_users""")
    total = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are", "user_data":result, "total": total['total']}),status= 200, mimetype='application/json')
    return response


#Paid Users
@app.route('/testseries/paidUsers',methods=["GET"])
def getPaidUsersTestSeries():
    page = request.headers.get("page")
    offset = 20*(int(page)-1)
    cursor = mysql.connection.cursor()
    cursor.execute(""" select u.id, u.firstname, u.lastname, u.email, u.mobile, u.image_url, u.created_at, u.whatsapp, u.graduation_year, u.preparing_for, o.order_id, o.order_at, o.status from testseries_users u join testseries_order_history o on u.id = o.user_id order by u.id desc limit 20 offset %s""", [offset])
    result = cursor.fetchall()
    cursor.execute(""" select count(*) as total from testseries_users u join testseries_order_history o on u.id = o.user_id""")
    total = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are", "user_data":result, "total": total['total']}),status= 200, mimetype='application/json')
    return response

#Unpaid Users
@app.route('/testseries/unpaidUsers',methods=["GET"])
def getUnpaidUsersTestSeries():
    page = request.headers.get("page")
    offset = 20*(int(page)-1)
    cursor = mysql.connection.cursor()
    cursor.execute(""" select testseries_users.id, firstname, lastname, email, mobile, image_url, created_at, whatsapp, graduation_year, preparing_for from testseries_users left outer join testseries_order_history on testseries_users.id = testseries_order_history.user_id where testseries_order_history.user_id is null order by testseries_users.id desc limit 20 offset %s""", [offset])
    result = cursor.fetchall()
    cursor.execute(""" select count(*) as total from testseries_users left outer join testseries_order_history on testseries_users.id = testseries_order_history.user_id where testseries_order_history.user_id is null""")
    total = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Users data are", "user_data":result, "total": total['total']}),status= 200, mimetype='application/json')
    return response

#Unpaid Users
@app.route('/testseries/getAllMockAdmin',methods=["GET"])
def getAllMockAdminTestSeries():
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from testseries_mock_paper""")
    result = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Mock Papers are", "mock_paper":result}),status= 200, mimetype='application/json')
    return response


#Mock Go Live
@app.route('/testseries/goMockLive',methods=["POST"])
def goMockLiveTestSeries():
    mock_paper_id = request.json["mock_paper_id"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" UPDATE testseries_mock_paper SET is_active = 1 where id=(%s)""",[mock_paper_id])
    mysql.connection.commit()
    response =app.response_class(response=json.dumps({"message":"Paper Live Successfully"}),status= 200, mimetype='application/json')
    cursor.close()
    return response

#Mock Stop 
@app.route('/testseries/finishPaper',methods=["POST"])
def finishPaperTestSeries():
    mock_paper_id = request.json["mock_paper_id"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" UPDATE testseries_mock_paper SET is_active = 0 , is_finished = 1 where id=(%s)""",[mock_paper_id])
    mysql.connection.commit()
    response =app.response_class(response=json.dumps({"message":"Paper Finished Successfully"}),status= 200, mimetype='application/json')
    cursor.close()
    return response


#Mock Rank Released and PDF
@app.route('/testseries/releaseResult',methods=["POST"])
def releaseResultTestSeries():
    mock_paper_id = request.json["mock_paper_id"]
    cursor = mysql.connection.cursor()
    cursor.execute(""" UPDATE testseries_mock_paper SET is_result_released = 1 where id=(%s)""",[mock_paper_id])
    mysql.connection.commit()
    response =app.response_class(response=json.dumps({"message":"Result Released Successfully"}),status= 200, mimetype='application/json')
    cursor.close()
    return response

# Check User Payment by Email
@app.route('/testseries/checkPayment',methods=["GET"])
def checkPaymentTestSeries():
    email = request.headers.get("email")
    user_exist = False
    is_exist = False
    payment_exist = []
    cursor = mysql.connection.cursor()
    cursor.execute("""select id from testseries_users where email=(%s)""",[email])
    user_id = cursor.fetchone()
    if user_id:
        user_exist = True
    if user_exist:
        cursor.execute("""select oh.*, u.firstname,u.lastname,u.email from testseries_users u join testseries_order_history oh on u.id=oh.user_id where user_id=(%s)""",[user_id["id"]])
        temp = cursor.fetchone()
        mysql.connection.commit()
        cursor.close()
        if temp:
            response =app.response_class(response=json.dumps({"message":"User Payment Details", "isExist":True, "payment_data":temp}),status= 200, mimetype='application/json')
        else :
             response =app.response_class(response=json.dumps({"message":"User Payment Details", "isExist":False}),status= 200, mimetype='application/json')
    else:
         response =app.response_class(response=json.dumps({"message":"User Not Exist", "isExist":False}),status= 200, mimetype='application/json')    
   
    return response

# Settle User Payment
@app.route('/testseries/addUserToPaymentList',methods=["POST"])
def addUserToPaymentListTestSeries():
    email = request.json["email"]
    order_id = request.json["order_id"]
    payment_id = request.json["payment_id"]
    order_at = request.json["payment_date"]
    cursor = mysql.connection.cursor()
    cursor.execute("""select * from testseries_users where email=(%s)""",[email])
    result = cursor.fetchone()
    cursor.execute("""select * from testseries_mock_package where id=(%s)""",[result["preparing_for"]])
    result2 = cursor.fetchone()
    if result:
        cursor.execute("""insert into testseries_order_history(payment_id, order_id, user_id, price, order_at, status, package_id) values(%s,%s,%s,%s,%s,%s,%s)""",[payment_id,order_id,result["id"],result2["package_price"],order_at,"success",result["preparing_for"]])
        response =app.response_class(response=json.dumps({"message":"Payment Details Updated Successfully"}),status= 200, mimetype='application/json')
    else:
        response =app.response_class(response=json.dumps({"message":"User not exist"}),status= 200, mimetype='application/json')
    mysql.connection.commit()
    cursor.close()
    return response


# Get Mock Status 
@app.route('/testseries/getLiveMockStatus',methods=["GET"])
def getLiveMockStatusTestSeries():
    cursor = mysql.connection.cursor()
    cursor.execute("""select id,mock_paper_name,is_active from testseries_mock_paper where is_active = 1 or is_finished = 1""")
    mock_paper_details = cursor.fetchall()
    for mock in mock_paper_details:
        cursor.execute("""select count(*) as user_count from testseries_mock_submissions where mock_paper_id = (%s)""",[mock["id"]])
        user_details = cursor.fetchone()
        mock["user_count"] = user_details["user_count"]
    response =app.response_class(response=json.dumps({"message":"All Mock Status", "mock_data":mock_paper_details}),status= 200, mimetype='application/json')
    mysql.connection.commit()
    cursor.close()
    return response


# Get User List wrt Mock Paper
@app.route('/testseries/getUserListMock',methods=["GET"])
def getUserListMockTestSeries():
    mock_paper_id = request.headers.get("mock_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select us.id as user_id, us.firstname user_firstname, us.lastname as user_lastname,us.email as user_email, ms.total_marks as marks, ms.accuracy as accuracy, ms.paper_time_taken as paper_time from testseries_mock_submissions ms join testseries_users us on ms.user_id = us.id where ms.mock_paper_id = (%s) order by ms.total_marks desc, ms.accuracy desc, ms.paper_time_taken asc""",[mock_paper_id])
    user_list = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"User List are", "user_list":user_list}),status= 200, mimetype='application/json')
    return response   


@app.route('/testseries/dumpQuestionsExcelfile', methods=["POST"])
def dumpQuestionsTestSeries():
    excel_file = request.files['excel_file']
    prefix_file = str(time.time()).replace(".","")[:11]
    new_name_file = prefix_file + "-" + excel_file.filename
    excel_file.save(new_name_file)
    book = xlrd.open_workbook(new_name_file)
    sheet = book.sheet_by_index(0)
    cursor = mysql.connection.cursor()
    query = """INSERT INTO testseries_mock_questions(paper_id, question_english, options_english, question_hindi, options_hindi, answer, extras_question, extras_option, question_type) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
    for r in range(1, sheet.nrows):
        paper_id = sheet.cell(r,0).value
        question_english = sheet.cell(r,1).value
        options_english = sheet.cell(r,2).value
        answer =  sheet.cell(r,3).value
        question_hindi = sheet.cell(r,4).value
        options_hindi = sheet.cell(r,5).value
        extras_question = sheet.cell(r,6).value
        extras_option = sheet.cell(r,7).value
        question_type = sheet.cell(r,8).value

        values = (paper_id, question_english, options_english, question_hindi, options_hindi, answer, extras_question, extras_option, question_type)     
        print(values)
        cursor.execute(query, values)

    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Sucessfully Uploaded"}),status= 200, mimetype='application/json')
    return response


# Get Mock Questions
@app.route('/testseries/getQuestionsByPaperId',methods=["GET"])
def getMockQuestionsByPaperIdTestSeries():
    questions_data = []
    mock_paper_id = request.headers.get("mock_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" select * from testseries_mock_questions where paper_id = (%s) order by id asc""",[mock_paper_id])
    results = cursor.fetchall()
    for result in results:
        temp_data = {}
        temp_data["id"] = result["id"]

        if result["question_english"]:
            temp_data["question_english"] = result["question_english"].split('$')
        else:
            temp_data["question_english"] = ""

        if result["options_english"]:
            temp_data["options_english"] = result["options_english"].split('$')
        else:
            temp_data["options_english"] = ["","","",""]

        if result["question_hindi"]:
            temp_data["question_hindi"] = result["question_hindi"].split('$')
        else:
            temp_data["question_hindi"] = ""

        if result["options_hindi"]:
            temp_data["options_hindi"] = result["options_hindi"].split('$')
        else:
            temp_data["options_hindi"] = ["","","",""]
        
        if result["extras_question"]:
            temp_data["extras_question"] = result["extras_question"].split('$')
        else:
            temp_data["extras_question"] = []

        if result["extras_option"]:
            temp_data["extras_option"] = result["extras_option"].split('$')
        else:
            temp_data["extras_option"] = []
        temp_data["question_type"] = result["question_type"]
        temp_data["answer"] = result["answer"]
        questions_data.append(temp_data)
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Questions data are", "questions":questions_data}),status= 200, mimetype='application/json')
    return response

# Get Mock Questions
@app.route('/testseries/getQuestionsById', methods=["GET"])
def getMockQuestionsByIdTestSeries():
    questions_id = request.headers.get("questions_id")
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT * from testseries_mock_questions where id = (%s)""", [questions_id])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Mock Questions details","question_list":result}),status= 200, mimetype='application/json')
    return response

# Get Mock Questions
@app.route('/testseries/getDemoTestStatus', methods=["GET"])
def getDemoTestStatus():
    user_id = request.headers.get("user_id")
    cursor = mysql.connection.cursor()
    cursor.execute("""SELECT * from testseries_mock_submissions where user_id = (%s) and mock_paper_id = (%s)""", [user_id, 49])
    result = cursor.fetchone()
    mysql.connection.commit()
    cursor.close()
    if result:
        response =app.response_class(response=json.dumps({"message":"Demo Test Details","isValid": False}),status= 200, mimetype='application/json')
    else:
        response =app.response_class(response=json.dumps({"message":"Demo Test Details","isValid": True}),status= 200, mimetype='application/json')        
    return response

# Add Mock Question
@app.route('/testseries/addQuestionToPaper', methods=["POST"])
def addQuestionToPaperTestSeries():
    mock_paper_id = request.json["mock_paper_id"]
    question_english = request.json["question_english"]
    options_english = request.json["options_english"]
    question_hindi = request.json["question_hindi"]
    options_hindi = request.json["options_hindi"]
    answer =  request.json["answer"]
    extras_question = request.json["extras_question"]
    extras_option = request.json["extras_option"]
    question_type = request.json["question_type"]

    cursor = mysql.connection.cursor()
    cursor.execute("""INSERT INTO testseries_mock_questions(paper_id, question_english, options_english, question_hindi, options_hindi, answer, extras_question, extras_option, question_type) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""", [mock_paper_id,question_english, options_english, question_hindi, options_hindi, answer, extras_question, extras_option, question_type])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Successfully Added"}),status= 200, mimetype='application/json')
    return response

# Edit Mock Questions
@app.route('/testseries/editQuestionsById', methods=["PUT"])
def editQuestionsByIdTestSeries():
    questions_id = request.json["questions_id"]
    question_english = request.json["question_english"]
    options_english = request.json["options_english"]
    question_hindi = request.json["question_hindi"]
    options_hindi = request.json["options_hindi"]
    answer =  request.json["answer"]
    extras_question = request.json["extras_question"]
    extras_option = request.json["extras_option"]
    question_type = request.json["question_type"]

    cursor = mysql.connection.cursor()
    cursor.execute(""" update testseries_mock_questions set question_english=(%s), options_english=(%s), question_hindi=(%s), options_hindi=(%s),answer=(%s),extras_question=(%s),extras_option=(%s), question_type=(%s) where id=(%s) """, [question_english, options_english, question_hindi, options_hindi, answer, extras_question, extras_option, question_type, questions_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"SuccessfullgetMockQuestionsByIdy Updated"}),status= 200, mimetype='application/json')
    return response

# Delete Question
@app.route('/testseries/deleteQuestionById',methods=["DELETE"])
def deleteQuestionByIdTestSeries():
    question_id = request.headers.get("question_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" delete from testseries_mock_questions where id =(%s)""",[question_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Successfully Deleted", "isValid":True}),status= 200, mimetype='application/json')
    return response

# Delete Question
@app.route('/testseries/deleteQuestionsByPaperId',methods=["DELETE"])
def deleteQuestionByPaperIdTestSeries():
    mock_paper_id = request.headers.get("mock_paper_id")
    cursor = mysql.connection.cursor()
    cursor.execute(""" delete from testseries_mock_questions where paper_id =(%s)""",[mock_paper_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Successfully Deleted", "isValid":True}),status= 200, mimetype='application/json')
    return response

# Get Users List 
@app.route('/testseries/allUsersList',methods=["GET"])
def allUsersListTestSeries():
    cursor = mysql.connection.cursor()
    cursor.execute(""" select id, firstname, lastname, email, mobile from testseries_users""")
    allUsers = cursor.fetchall()
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Responses Available", "allUsers":allUsers, "isValid":True}),status= 200, mimetype='application/json')
    return response

# Upload Question Paper Pdf
@app.route('/testseries/uploadPaperPdf', methods=["POST"])
def uploadQuestionPaperPdf():
    mock_paper_id = request.headers.get("mock_paper_id")
    file = request.files["question_paper_pdf"]
    seconds = str(time.time()).replace(".","")
    newFile = "material_pdf/"+seconds + "-" + file.filename
    uploadFileToS3(newFile, file)
    pdf_file = 'https://pdhantu-classes.s3.us-east-2.amazonaws.com/'+newFile
    cursor = mysql.connection.cursor()
    cursor.execute("""UPDATE testseries_mock_paper SET paper_pdf =(%s) where id=(%s) """,[pdf_file,mock_paper_id])
    mysql.connection.commit()
    cursor.close()
    response =app.response_class(response=json.dumps({"message":"Uploaded Successfully"}),status= 200, mimetype='application/json')
    return response


if __name__ == "__main__":
    app.run(debug="True", host="0.0.0.0", port=5000)
    # app.run(debug = "True")
