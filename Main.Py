from flask import Flask, render_template, request, flash, Response, session
import os
import io
import base64
import cv2
from random import randint
from PIL import Image
from DBConnection import DBConnection
from ChildIdentification import predict, train

app = Flask(__name__)
app.secret_key = "abc"
camera = cv2.VideoCapture(0)

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/<role>_reg")
def register(role):
    return render_template(f"{role}_reg.html")

@app.route("/<role>_reg2", methods=["POST"])
def register_user(role):
    try:
        data = {key: request.form.get(key) for key in ['name', 'uid', 'pwd', 'email', 'mno']}
        database = DBConnection.getConnection()
        cursor = database.cursor()
        table = "authority" if role == "authority" else "users"
        
        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE uid=%s", (data['uid'],))
        if cursor.fetchone()[0] > 0:
            return render_template(f"{role}_reg.html", messages="User  Id already exists..!")
        
        cursor.execute(f"INSERT INTO {table} VALUES (%s, %s, %s, %s, %s)", tuple(data.values()))
        database.commit()
        return render_template(f"{role}.html", messages="Registered Successfully..! Login Here.")
    except Exception as e:
        print(e)

@app.route("/<role>_login", methods=["POST"])
def login(role):
    uid, pwd = request.form.get("unm"), request.form.get("pwd")
    database = DBConnection.getConnection()
    cursor = database.cursor()
    table = "authority" if role == "authority" else "users"
    
    cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE uid=%s AND pwd=%s", (uid, pwd))
    if cursor.fetchone()[0] > 0:
        session[f"{role}id"] = uid
        return render_template(f"{role}home.html")
    return render_template(f"{role}.html", msg="Invalid Credentials")

@app.route("/upload_photo", methods=["POST"])
def upload_photo():
    try:
        role = "authority" if 'auid' in session else "user"
        uid = session[f"{role}id"]
        data = {key: request.form.get(key) for key in ['cname', 'city', 'lmrks', 'rmrks']}
        image = request.files['file']
        cid = f"{data['cname']}_{randint(1000, 9999)}"
        path = f"../ChildIdentification/dataset/{cid}/"
        os.makedirs(path, exist_ok=True)
        image.save(os.path.join(path, secure_filename(image.filename)))
        
        database = DBConnection.getConnection()
        cursor = database.cursor()
        cursor.execute("INSERT INTO uploadphotos VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                       (data['cname'], data['city'], data['lmrks'], data['rmrks'], image.filename, uid, role.capitalize(), cid, "Pending"))
        database.commit()
        return render_template(f"{role}_upload_photo.html", message="Photo Uploaded Successfully..!")
    except Exception as e:
        print(e)

@app.route("/<role>_search2", methods=["POST"])
def search(role):
    try:
        image = request.files['file']
        imgdata = secure_filename(image.filename)
        image.save(os.path.join("testing", imgdata))
        
        classifier = train("../ChildIdentification/dataset", model_save_path="trained_knn_model.clf", n_neighbors=1)
        namelist = []
        
        for image_file in os.listdir("../ChildIdentification/testing"):
            predictions = predict(os.path.join("../ChildIdentification/testing", image_file), model_path="trained_knn_model.clf")
            namelist.extend([name for name, _ in predictions])
        
        if not namelist or namelist[0] == "unknown":
            return render_template(f"{role}_search.html", message="No Results Found")
        
        database = DBConnection.getConnection()
        cursor = database.cursor()
        cursor.execute("UPDATE uploadphotos SET status='Resolved' WHERE cid=%s", (namelist[0],))
        database.commit()
        
        cursor.execute("SELECT * FROM uploadphotos WHERE cid=%s", (namelist[0],))
        res = cursor.fetchall()
        # Process results and render template...
        
    except Exception as e:
        print(e)

@app.route('/webcam')
def webcam():
    return render_template('camera.html')

def gen_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(debug=True)
