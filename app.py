from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import requests
import telebot
from datetime import datetime
from threading import Thread

app = Flask(__name__)
app.config['SECRET_KEY'] = 'zukasmtavaripaneli'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'delivery.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


TELEGRAM_TOKEN = "8722774055:AAGrs56BqrvegJx8BD3Pxy64DtPUkJ12owA"
TELEGRAM_CHAT_ID = "6510438875" 
bot = telebot.TeleBot(TELEGRAM_TOKEN)



def send_telegram_notification(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Telegram error: {e}")


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(20), default='user')
    applications = db.relationship('Application', backref='applicant', lazy=True)
    assigned_orders = db.relationship('Order', backref='courier', lazy=True)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    pid = db.Column(db.String(11))
    phone = db.Column(db.String(20))
    location = db.Column(db.String(100))
    status = db.Column(db.String(20), default='განხილვაშია')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100))
    customer_name = db.Column(db.String(100))
    customer_phone = db.Column(db.String(20))
    city = db.Column(db.String(50))      
    address = db.Column(db.String(200))
    weight = db.Column(db.String(20))
    price = db.Column(db.Float)          
    status = db.Column(db.String(20), default='მზად არის')
    courier_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(id): 
    return db.session.get(User, int(id))


@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/about')
def about(): 
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        

        msg = (f"📩 <b>ახალი შეტყობინება კონტაქტიდან!</b>\n\n"
               f"👤 სახელი: {name}\n"
               f"📧 Email: {email}\n"
               f"📝 მესიჯი: {message}")
        
        send_telegram_notification(msg)
        flash('შეტყობინება წარმატებით გაიგზავნა!', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/track', methods=['GET', 'POST'])
def track_order():
    order_data = None
    if request.method == 'POST':
        order_id = request.form.get('order_id')
        if order_id and order_id.isdigit():
            order_data = db.session.get(Order, int(order_id))
            if not order_data:
                flash('შეკვეთა ამ ID-ით ვერ მოიძებნა!', 'danger')
        else:
            flash('გთხოვთ შეიყვანოთ ვალიდური ID!', 'warning')
    return render_template('track.html', order=order_data)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').lower().strip()
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('სახელი დაკავებულია!', 'danger')
            return redirect(url_for('register'))
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        role = 'admin' if username == 'zuka abashidze' else 'user'
        new_user = User(username=username, password=hashed_pw, role=role)
        db.session.add(new_user)
        db.session.commit()
        send_telegram_notification(f"🆕 <b>ახალი წევრი!</b>\n👤 იუზერი: {username}\n🎭 როლი: {role}")
        flash('რეგისტრაცია წარმატებულია!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username').lower().strip()).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('არასწორი მონაცემები!', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin' or current_user.username == 'zuka abashidze':
        return redirect(url_for('admin'))
    if current_user.role == 'courier':
        orders = Order.query.filter_by(courier_id=current_user.id).all()
        return render_template('courier_dashboard.html', orders=orders)
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin' and current_user.username != 'zuka abashidze': 
        return redirect(url_for('dashboard'))
    apps = Application.query.all()
    couriers = User.query.filter_by(role='courier').all()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin.html', apps=apps, couriers=couriers, orders=orders, total_orders=len(orders))

@app.route('/create_order', methods=['POST'])
@login_required
def create_order():
    if current_user.role != 'admin' and current_user.username != 'zuka abashidze': 
        return redirect(url_for('dashboard'))
    
    item = request.form.get('item_name')
    c_name = request.form.get('customer_name')
    c_phone = request.form.get('customer_phone')
    city = request.form.get('city')
    addr = request.form.get('address')
    weight = request.form.get('weight')
    price = request.form.get('price')
    cour_id = request.form.get('courier_id')
    
    new_order = Order(
        item_name=item, customer_name=c_name, customer_phone=c_phone,
        city=city, address=addr, weight=weight, price=price, courier_id=cour_id
    )
    db.session.add(new_order)
    db.session.commit()
    
    courier = db.session.get(User, cour_id)

    msg = (f"🔔 <b>ახალი შეკვეთა!</b>\n\n"
           f"🆔 Tracking ID: {new_order.id}\n"
           f"📦 ნივთი: {item}\n"
           f"👤 შემკვეთი: {c_name}\n"
           f"📞 ნომერი: {c_phone}\n"
           f"📍 ქალაქი: {city}\n"
           f"🏠 მისამართი: {addr}\n"
           f"💰 ფასი: {price} ₾\n"
           f"🚴 კურიერი: {courier.username if courier else 'უცნობი'}")
    
    send_telegram_notification(msg)
    flash(f'შეკვეთა დაემატა! ID: {new_order.id}', 'success')
    return redirect(url_for('admin'))

@app.route('/apply', methods=['GET', 'POST'])
@login_required
def apply():
    if request.method == 'POST':
        name = request.form.get('name')
        pid = request.form.get('pid')
        phone = request.form.get('phone')
        location = request.form.get('location')
        
        if not pid.isdigit() or len(pid) != 11:
            flash('პირადი ნომერი უნდა შედგებოდეს 11 ციფრისგან!', 'danger')
            return redirect(url_for('apply'))


        if not phone.startswith('+995') or len(phone) != 13:
            flash('ტელეფონის ნომერი უნდა იწყებოდეს +995-ით და მოჰყვებოდეს 9 ციფრი!', 'danger')
            return redirect(url_for('apply'))

        new_app = Application(
            name=name, pid=pid,
            phone=phone, location=location,
            user_id=current_user.id
        )
        db.session.add(new_app)
        db.session.commit()
        
        msg = (f"🚀 <b>ახალი CV მოვიდა!</b>\n\n"
               f"👤 სახელი: {name}\n"
               f"🆔 პირადი: {pid}\n"
               f"📞 ტელეფონი: {phone}\n"
               f"📍 ლოკაცია: {location}")
        
        send_telegram_notification(msg)
        flash('განაცხადი მიღებულია!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('apply.html')
@app.route('/approve_courier/<int:id>')
@login_required
def approve_courier(id):
    if current_user.role != 'admin' and current_user.username != 'zuka abashidze': return redirect(url_for('dashboard'))
    app_obj = db.session.get(Application, id)
    if app_obj:
        user = db.session.get(User, app_obj.user_id)
        app_obj.status = 'დადასტურებულია'
        user.role = 'courier'
        db.session.commit()
        send_telegram_notification(f"✅ <b>კურიერი დადასტურდა!</b>\n👤 {user.username}")
        flash('კურიერი წარმატებით დადასტურდა!', 'success')
    return redirect(url_for('admin'))

@app.route('/delete_application/<int:id>')
@login_required
def delete_application(id):
    if current_user.role != 'admin' and current_user.username != 'zuka abashidze': 
        return redirect(url_for('dashboard'))
    app_obj = db.session.get(Application, id)
    if app_obj:
        db.session.delete(app_obj)
        db.session.commit()
        flash('განაცხადი წაიშალა!', 'info')
    return redirect(url_for('admin'))

@app.route('/delete_order/<int:id>')
@login_required
def delete_order(id):
    if current_user.role != 'admin' and current_user.username != 'zuka abashidze': 
        return redirect(url_for('dashboard'))
    order_obj = db.session.get(Order, id)
    if order_obj:
        db.session.delete(order_obj)
        db.session.commit()
        flash('შეკვეთა წარმატებით წაიშალა!', 'warning')
    return redirect(url_for('admin'))

@app.route('/update_order_status/<int:id>/<string:status>')
@login_required
def update_order_status(id, status):
    if current_user.role not in ['admin', 'courier'] and current_user.username != 'zuka abashidze':
        return redirect(url_for('dashboard'))
    order_obj = db.session.get(Order, id)
    if order_obj:
        order_obj.status = status
        db.session.commit()
        send_telegram_notification(f"🔄 <b>სტატუსის ცვლილება!</b>\n📦 ID: {id}\n📍 ახალი სტატუსი: {status}")
        flash(f'სტატუსი განახლდა: {status}', 'success')
    return redirect(url_for('dashboard') if current_user.role == 'courier' else url_for('admin'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    if not os.path.exists('instance'): os.makedirs('instance')
    with app.app_context(): db.create_all()
    
    bot_thread = Thread(target=lambda: bot.polling(none_stop=True))
    bot_thread.daemon = True
    bot_thread.start()
    
    app.run(debug=True, use_reloader=False)