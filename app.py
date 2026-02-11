from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import calendar
import os

app = Flask(__name__)

# 1) SECRET_KEY：給 session/登入用（從環境變數拿）
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")

# 2) DATABASE_URL：Render 會提供（從環境變數拿）
db_url = os.environ.get("DATABASE_URL")

# Render 的 DATABASE_URL 有時會是 postgres:// 開頭，SQLAlchemy 要 postgresql://
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# 如果沒有 DATABASE_URL（例如你本機跑），就先用 SQLite
app.config["SQLALCHEMY_DATABASE_URI"] = db_url or "sqlite:///local.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# 原本你寫的 "/" 會跟後面的 index() 重複，所以我改成 /health（保留功能）
@app.route("/health")
def home():
    return "OK - site is running"

#SECRET_KEY 改成環境變數
import os
app.secret_key = os.environ.get("SECRET_KEY", "dev")
#管理者帳密改成環境變數
ADMIN_ACCOUNT = os.environ.get("ADMIN_ACCOUNT", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1234")

db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# 這裡你原本直接 app.config["SQLALCHEMY_DATABASE_URI"] = db_url
# 如果 db_url 沒有值會變 None 然後爆掉，所以改成「沒值就沿用原本設定」
app.config["SQLALCHEMY_DATABASE_URI"] = db_url or app.config.get("SQLALCHEMY_DATABASE_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# 你原本這裡會再次建立 SQLAlchemy(app)（會導致 model/db 綁不同物件）
# 我保留這行的位置，但讓它不重新建立（等同「沿用前面那個 db」）
db = db

# --------------------------------------
# 資料表：課程 Course
# --------------------------------------
class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # 日期：YYYY-MM-DD
    course_date = db.Column(db.String(10), nullable=False)

    # 時間區間：開始 / 結束（HH:MM）
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)

    # 課程名稱
    course_name = db.Column(db.String(50), nullable=False)

    # 名額與剩餘名額
    capacity = db.Column(db.Integer, nullable=False)
    remaining = db.Column(db.Integer, nullable=False)

# --------------------------------------
# 資料表：報名 Registration
# --------------------------------------
class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # 對應的課程 id
    course_id = db.Column(db.Integer, nullable=False)

    # 報名資料
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), nullable=False)

# ✅ 你要的「自動建表」就加在這裡：兩個 Model 定義完之後
with app.app_context():
    db.create_all()

# --------------------------------------
# 首頁（月曆 + 月份切換 + 上午/下午顏色 + 同日排序）
# --------------------------------------
@app.route("/")
def index():
    # 取得網址列 month 參數，例如 ?month=2026-01
    month_str = request.args.get("month")

    # 若未指定月份，使用今天年月
    if month_str:
        year, month = map(int, month_str.split("-"))
    else:
        today = datetime.today()
        year, month = today.year, today.month
        month_str = f"{year}-{month:02d}"

    # 產生月曆格子（二維陣列：一週一列）
    cal = calendar.monthcalendar(year, month)

    # 撈出該月份所有課程（以 YYYY-MM 開頭）
    start = f"{year}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    end = f"{year}-{month:02d}-{last_day}"

    courses = Course.query.filter(
        Course.course_date >= start,
        Course.course_date <= end
    ).all()

    # course_dict：key=日(1~31), value=該天課程清單
    course_dict = {}

    for c in courses:
        day = int(c.course_date.split("-")[2])

        # 上午 / 下午判斷（用開始時間的小時）
        hour = int(c.start_time.split(":")[0])
        c.session_type = "morning" if hour < 12 else "afternoon"

        course_dict.setdefault(day, []).append(c)

    # 同一天依開始時間排序（字串 HH:MM 直接排序即可）
    for d in course_dict:
        course_dict[d].sort(key=lambda x: x.start_time)

    return render_template(
        "calendar.html",
        cal=cal,
        year=year,
        month=month,
        courses=course_dict,
        month_str=month_str
    )

#首頁查詢課程
# 你原本這段寫在函式外面，year/month 不存在會直接噴錯
# 我「保留原本內容」但用 if False 包起來避免啟動就執行
if False:
    start = f"{year}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    end = f"{year}-{month:02d}-{last_day}"

    courses = Course.query.filter(
        Course.course_date >= start,
        Course.course_date <= end
    ).all()

# --------------------------------------
# 報名頁：GET 顯示表單 / POST 送出報名
# --------------------------------------
@app.route("/register/<int:course_id>", methods=["GET", "POST"])
def register(course_id):
    course = Course.query.get(course_id)

    # 課程不存在或已額滿
    if not course or course.remaining <= 0:
        return "課程不存在或已額滿"

    if request.method == "POST":
        # 再檢查一次避免多人同時送出
        course = Course.query.get(course_id)
        if course.remaining <= 0:
            return "此課程已額滿"

        # 建立報名資料
        reg = Registration(
            course_id=course.id,
            name=request.form["name"],
            email=request.form["email"],
            phone=request.form["phone"]
        )

        # 名額扣 1
        course.remaining -= 1

        db.session.add(reg)
        db.session.commit()

        return redirect("/")

    return render_template("register.html", course=course)

# --------------------------------------
# 管理者登入 / 登出
# --------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        acc = request.form["account"]
        pwd = request.form["password"]

        if acc == ADMIN_ACCOUNT and pwd == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin")
        return "帳號或密碼錯誤"

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")

# --------------------------------------
# 管理後台：查看所有課程 + 報名名單
# --------------------------------------
@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect("/login")

    courses = Course.query.order_by(Course.course_date, Course.start_time).all()
    return render_template("admin.html", courses=courses, Registration=Registration)

# --------------------------------------
# 新增課程（支援：單日 / 每週重複）
# --------------------------------------
@app.route("/admin/add", methods=["GET", "POST"])
def add_course():
    if not session.get("admin"):
        return redirect("/login")

    if request.method == "POST":
        name = request.form["name"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]
        capacity = int(request.form["capacity"])

        # 簡單檢查：開始時間必須小於結束時間
        if start_time >= end_time:
            return "開始時間必須早於結束時間"

        mode = request.form["mode"]  # single / weekly

        if mode == "single":
            # 單日新增
            date = request.form["date"]
            db.session.add(Course(
                course_date=date,
                start_time=start_time,
                end_time=end_time,
                course_name=name,
                capacity=capacity,
                remaining=capacity
            ))

        else:
            # 每週重複新增
            # start_date：從哪一天開始找第一個指定星期
            start_date = datetime.strptime(request.form["start_date"], "%Y-%m-%d")
            weeks = int(request.form["weeks"])       # 重複幾週
            weekday = int(request.form["weekday"])   # 0=Mon ... 6=Sun

            # 先把 current 移動到「下一個符合 weekday 的日期」
            current = start_date
            while current.weekday() != weekday:
                current += timedelta(days=1)

            # 連續新增 N 週
            for _ in range(weeks):
                db.session.add(Course(
                    course_date=current.strftime("%Y-%m-%d"),
                    start_time=start_time,
                    end_time=end_time,
                    course_name=name,
                    capacity=capacity,
                    remaining=capacity
                ))
                current += timedelta(weeks=1)

        db.session.commit()
        return redirect("/admin")

    return render_template("add_course.html")

# --------------------------------------
# 修改課程（已建立的課程可編輯）
# --------------------------------------
@app.route("/admin/edit/<int:course_id>", methods=["GET", "POST"])
def edit_course(course_id):
    if not session.get("admin"):
        return redirect("/login")

    course = Course.query.get(course_id)
    if not course:
        return "課程不存在"

    if request.method == "POST":
        # 更新課程內容
        course.course_date = request.form["date"]
        course.start_time = request.form["start_time"]
        course.end_time = request.form["end_time"]
        course.course_name = request.form["name"]
        course.capacity = int(request.form["capacity"])

        if course.start_time >= course.end_time:
            return "開始時間必須早於結束時間"

        # 如果把 capacity 調小，remaining 不應大於 capacity
        if course.remaining > course.capacity:
            course.remaining = course.capacity

        db.session.commit()
        return redirect("/admin")

    return render_template("edit_course.html", course=course)

# --------------------------------------
# 刪除課程（連同報名一起刪除）
# --------------------------------------
@app.route("/admin/delete/<int:course_id>", methods=["POST"])
def delete_course(course_id):
    if not session.get("admin"):
        return redirect("/login")

    # 先刪該課程所有報名
    Registration.query.filter_by(course_id=course_id).delete()

    # 再刪課程
    Course.query.filter_by(id=course_id).delete()

    db.session.commit()
    return redirect("/admin")

# --------------------------------------
# 程式入口：建立資料表並啟動
# --------------------------------------
if __name__ == "__main__":
    app.run()
# deploy test