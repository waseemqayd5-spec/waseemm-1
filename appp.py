#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نظام إدارة عدن المتكامل - النسخة القوية الكاملة
=================================================
الميزات:
- محفظة رقمية إلكترونية
- نظام شكاوى متكامل
- تقييم رضا المواطنين
- نظام تراخيص الأعمال
- إشعارات فورية WebSocket
- رسوم بيانية متقدمة
- تصدير تقارير PDF/Excel/CSV
- كشف احتيال بالذكاء الاصطناعي
- نظام جرد المخزون
=================================================
"""

import os
import sys
import threading
import time
import uuid
import random
import json
import io
import base64
from datetime import datetime, date, timedelta
from functools import wraps
from io import BytesIO

# حذف قاعدة البيانات التالفة إذا وجدت
db_path = 'aden_powerful_system.db'
if os.path.exists(db_path):
    try:
        os.remove(db_path)
        print("🗑️ تم حذف قاعدة البيانات القديمة")
    except:
        pass

from flask import Flask, request, jsonify, send_file, render_template_string, Response
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, decode_token
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
from geopy.distance import geodesic
import numpy as np
import pandas as pd

# محاولة استيراد reportlab مع معالجة الخطأ
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️ reportlab غير مثبت - سيتم تعطيل تصدير PDF")

# محاولة استيراد matplotlib
try:
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.rcParams['font.family'] = 'DejaVu Sans'
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️ matplotlib غير مثبت - سيتم تعطيل الرسوم البيانية")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'aden-powerful-secret-key-2026'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
app.secret_key = 'aden-powerful-session-key'
app.config['SECRET_KEY'] = 'aden-socket-secret'

db = SQLAlchemy(app)
jwt = JWTManager(app)
bcrypt = Bcrypt(app)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")


def gen_uuid():
    return str(uuid.uuid4())


# ==================== نماذج قاعدة البيانات الكاملة ====================

class Governorate(db.Model):
    __tablename__ = 'governorates'
    code = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_english = db.Column(db.String(100))
    capital_city = db.Column(db.String(100))
    population = db.Column(db.Integer, default=0)
    area_km2 = db.Column(db.Float, default=0)
    logo_url = db.Column(db.String(500))
    website = db.Column(db.String(200))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class District(db.Model):
    __tablename__ = 'districts'
    code = db.Column(db.String(20), primary_key=True)
    governorate_code = db.Column(db.String(20), db.ForeignKey('governorates.code'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    name_english = db.Column(db.String(100))
    district_type = db.Column(db.String(50), default='district')
    population = db.Column(db.Integer, default=0)
    center_lat = db.Column(db.Float)
    center_lng = db.Column(db.Float)
    mayor_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    budget = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    performance_score = db.Column(db.Float, default=0)


class Subdistrict(db.Model):
    __tablename__ = 'subdistricts'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    district_code = db.Column(db.String(20), db.ForeignKey('districts.code'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    name_english = db.Column(db.String(100))
    subdistrict_type = db.Column(db.String(50), default='neighborhood')
    population = db.Column(db.Integer, default=0)
    center_lat = db.Column(db.Float)
    center_lng = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    role = db.Column(db.String(50), nullable=False)
    governorate_code = db.Column(db.String(20), db.ForeignKey('governorates.code'))
    district_code = db.Column(db.String(20), db.ForeignKey('districts.code'))
    subdistrict_id = db.Column(db.Integer, db.ForeignKey('subdistricts.id'))
    profile_picture = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Shop(db.Model):
    __tablename__ = 'shops'
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    owner_name = db.Column(db.String(100))
    owner_phone = db.Column(db.String(20))
    owner_email = db.Column(db.String(100))
    governorate_code = db.Column(db.String(20), db.ForeignKey('governorates.code'), nullable=False)
    district_code = db.Column(db.String(20), db.ForeignKey('districts.code'), nullable=False)
    subdistrict_id = db.Column(db.Integer, db.ForeignKey('subdistricts.id'))
    category = db.Column(db.String(50))
    sub_category = db.Column(db.String(50))
    monthly_fee = db.Column(db.Float, default=0)
    annual_fee = db.Column(db.Float, default=0)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    address = db.Column(db.String(300))
    qr_code = db.Column(db.String(100), unique=True)
    ussd_code = db.Column(db.String(20), unique=True)
    commercial_register = db.Column(db.String(50))
    tax_number = db.Column(db.String(50))
    license_expiry = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    rating = db.Column(db.Float, default=0)
    rating_count = db.Column(db.Integer, default=0)
    last_collection_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(36), db.ForeignKey('users.id'))


class BusinessLicense(db.Model):
    __tablename__ = 'business_licenses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    license_number = db.Column(db.String(50), unique=True, nullable=False)
    shop_id = db.Column(db.String(50), db.ForeignKey('shops.id'), nullable=False)
    license_type = db.Column(db.String(50))
    issue_date = db.Column(db.Date, nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    is_renewed = db.Column(db.Boolean, default=False)
    last_renewal_date = db.Column(db.Date)
    fee_paid = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), default='active')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Inventory(db.Model):
    __tablename__ = 'inventories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    shop_id = db.Column(db.String(50), db.ForeignKey('shops.id'), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    product_code = db.Column(db.String(50))
    category = db.Column(db.String(50))
    quantity = db.Column(db.Integer, default=0)
    unit_price = db.Column(db.Float, default=0)
    total_value = db.Column(db.Float, default=0)
    reorder_level = db.Column(db.Integer, default=0)
    expiry_date = db.Column(db.Date)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)


class Collection(db.Model):
    __tablename__ = 'collections'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    shop_id = db.Column(db.String(50), db.ForeignKey('shops.id'))
    collector_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))
    payment_reference = db.Column(db.String(100))
    transaction_id = db.Column(db.String(100), unique=True)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    is_suspicious = db.Column(db.Boolean, default=False)
    suspicious_reason = db.Column(db.String(200))
    receipt_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DigitalWallet(db.Model):
    __tablename__ = 'digital_wallets'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    wallet_number = db.Column(db.String(50), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0)
    currency = db.Column(db.String(3), default='YER')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WalletTransaction(db.Model):
    __tablename__ = 'wallet_transactions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('digital_wallets.id'))
    transaction_type = db.Column(db.String(50))
    amount = db.Column(db.Float, nullable=False)
    reference = db.Column(db.String(100))
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Complaint(db.Model):
    __tablename__ = 'complaints'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    complainant_name = db.Column(db.String(100))
    complainant_phone = db.Column(db.String(20))
    complaint_type = db.Column(db.String(50))
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    attachment_url = db.Column(db.String(500))
    district_code = db.Column(db.String(20), db.ForeignKey('districts.code'))
    status = db.Column(db.String(50), default='pending')
    assigned_to = db.Column(db.String(36), db.ForeignKey('users.id'))
    resolution_notes = db.Column(db.Text)
    satisfaction_rating = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)


class CitizenRating(db.Model):
    __tablename__ = 'citizen_ratings'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    citizen_name = db.Column(db.String(100))
    citizen_phone = db.Column(db.String(20))
    service_type = db.Column(db.String(50))
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    district_code = db.Column(db.String(20), db.ForeignKey('districts.code'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50))
    is_read = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RevenueDaily(db.Model):
    __tablename__ = 'revenue_daily'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    governorate_code = db.Column(db.String(20), db.ForeignKey('governorates.code'))
    district_code = db.Column(db.String(20), db.ForeignKey('districts.code'))
    date = db.Column(db.Date, nullable=False)
    total_amount = db.Column(db.Float, default=0)
    collection_count = db.Column(db.Integer, default=0)
    expected_amount = db.Column(db.Float, default=0)


class Campaign(db.Model):
    __tablename__ = 'campaigns'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    name = db.Column(db.String(200), nullable=False)
    district_code = db.Column(db.String(20), db.ForeignKey('districts.code'))
    status = db.Column(db.String(50), default='active')
    target_amount = db.Column(db.Float, default=0)
    collected_amount = db.Column(db.Float, default=0)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Alert(db.Model):
    __tablename__ = 'alerts'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    district_code = db.Column(db.String(20), db.ForeignKey('districts.code'))
    alert_type = db.Column(db.String(20))
    severity = db.Column(db.Integer)
    message = db.Column(db.Text)
    is_resolved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DevelopmentProject(db.Model):
    __tablename__ = 'development_projects'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    district_code = db.Column(db.String(20), db.ForeignKey('districts.code'))
    project_name = db.Column(db.String(200))
    project_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    budget = db.Column(db.Float, default=0)
    spent_amount = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), default='planned')
    completion_percentage = db.Column(db.Float, default=0)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    contractor = db.Column(db.String(200))
    image_urls = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CitizenReport(db.Model):
    __tablename__ = 'citizen_reports'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reporter_name = db.Column(db.String(100))
    reporter_phone = db.Column(db.String(20))
    shop_name = db.Column(db.String(200))
    district_code = db.Column(db.String(20), db.ForeignKey('districts.code'))
    violation_type = db.Column(db.String(50))
    location = db.Column(db.String(300))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    photo_url = db.Column(db.String(500))
    description = db.Column(db.Text)
    reward_points = db.Column(db.Integer, default=0)
    is_processed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FraudDetection(db.Model):
    __tablename__ = 'fraud_detections'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    shop_id = db.Column(db.String(50), db.ForeignKey('shops.id'))
    detection_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    confidence_score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==================== دوال مساعدة ====================

def role_required(allowed_roles):
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            if not user or user.role not in allowed_roles:
                return jsonify({"error": "غير مصرح لك بهذه العملية"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def send_notification(user_id, title, message, notification_type="general", priority=1):
    """إرسال إشعار فوري"""
    try:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority
        )
        db.session.add(notification)
        db.session.commit()

        socketio.emit('new_notification', {
            'id': notification.id,
            'title': title,
            'message': message,
            'type': notification_type,
            'priority': priority,
            'created_at': notification.created_at.isoformat()
        }, room=f'user_{user_id}')
    except:
        pass
    return None


def generate_shop_id(district_code):
    existing = Shop.query.filter(Shop.id.like(f"{district_code}-%")).count()
    return f"{district_code}-{existing + 1:04d}"


def generate_qr_string(shop_id):
    return f"ADEN-QR-{shop_id}-{uuid.uuid4().hex[:8].upper()}"


def generate_ussd_string(shop_number):
    return f"*159*{shop_number:04d}#"


def generate_license_number():
    year = datetime.now().year
    random_part = random.randint(10000, 99999)
    return f"LIC-{year}-{random_part}"


def generate_wallet_number():
    return f"WLT-{uuid.uuid4().hex[:12].upper()}"


def check_red_alert(district_code):
    """فحص الإنذار الأحمر"""
    today = date.today()
    revenues = []
    for i in range(1, 4):
        d = today - timedelta(days=i)
        rev = RevenueDaily.query.filter_by(district_code=district_code, date=d).first()
        revenues.append(rev.total_amount if rev else 0)

    if len(revenues) == 3 and revenues[0] > 0 and sum(revenues[1:]) > 0:
        avg_prev = np.mean(revenues[1:])
        decline = (1 - revenues[0] / avg_prev) * 100
        if decline >= 15:
            existing = Alert.query.filter_by(district_code=district_code, alert_type="RED", is_resolved=False).first()
            if not existing:
                alert = Alert(district_code=district_code, alert_type="RED", severity=5,
                              message=f"🔴 إنذار أحمر: انخفاض الإيرادات {decline:.1f}%")
                db.session.add(alert)
                db.session.commit()

                governor = User.query.filter_by(role='governor').first()
                if governor:
                    send_notification(governor.id, "🚨 إنذار أحمر",
                                      f"إنذار أحمر في مديرية {district_code}", "alert", 3)


def calculate_district_score(district_code):
    """حساب درجة أداء المديرية"""
    district = District.query.get(district_code)
    if not district:
        return 0

    today = date.today()
    month_rev = RevenueDaily.query.filter_by(district_code=district_code).filter(
        db.extract('month', RevenueDaily.date) == today.month,
        db.extract('year', RevenueDaily.date) == today.year
    ).all()
    total_month = sum(r.total_amount for r in month_rev)

    ratings = CitizenRating.query.filter_by(district_code=district_code).all()
    avg_rating = np.mean([r.rating for r in ratings]) if ratings else 3

    target = max(district.population * 100, 1)
    revenue_score = (total_month / target * 50) if target > 0 else 25
    rating_score = (avg_rating / 5 * 50)

    district.performance_score = min(revenue_score + rating_score, 100)
    db.session.commit()
    return district.performance_score


def detect_fraud(collection_id):
    """كشف الاحتيال بالذكاء الاصطناعي"""
    collection = Collection.query.get(collection_id)
    if not collection:
        return

    shop = Shop.query.get(collection.shop_id)
    if not shop:
        return

    if collection.latitude and shop.latitude:
        try:
            distance = geodesic((shop.latitude, shop.longitude),
                                (collection.latitude, collection.longitude)).meters
            if distance > 200:
                fraud = FraudDetection(
                    shop_id=shop.id,
                    detection_type="geo_fence",
                    description=f"تحصيل من بعد {distance:.0f} متر",
                    confidence_score=0.85
                )
                db.session.add(fraud)
                collection.is_suspicious = True
                collection.suspicious_reason = f"بعيد {distance:.0f} متر"
                db.session.commit()
        except:
            pass


# ==================== API ====================

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data.get('username'), is_active=True).first()

    if user and bcrypt.check_password_hash(user.password_hash, data.get('password')):
        token = create_access_token(identity=user.id)
        user.last_login = datetime.utcnow()
        db.session.commit()

        return jsonify({
            "success": True,
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "email": user.email,
                "phone": user.phone,
                "role": user.role,
                "district_code": user.district_code
            }
        })

    return jsonify({"error": "بيانات الدخول غير صحيحة"}), 401


@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    return jsonify({
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "district_code": user.district_code
    })


@app.route('/api/governorate', methods=['GET'])
def get_governorate():
    gov = Governorate.query.first()
    if not gov:
        return jsonify({"error": "المحافظة غير موجودة"}), 404

    districts = District.query.filter_by(governorate_code=gov.code, is_active=True).all()

    return jsonify({
        "code": gov.code,
        "name": gov.name,
        "name_english": gov.name_english,
        "capital_city": gov.capital_city,
        "population": gov.population,
        "area_km2": gov.area_km2,
        "website": gov.website,
        "email": gov.email,
        "phone": gov.phone,
        "districts_count": len(districts),
        "districts": [{"code": d.code, "name": d.name, "performance_score": d.performance_score} for d in districts]
    })


@app.route('/api/districts', methods=['GET'])
@jwt_required()
def get_districts():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user.role == 'governor':
        districts = District.query.filter_by(is_active=True).all()
    elif user.role == 'mayor':
        districts = District.query.filter_by(code=user.district_code, is_active=True).all()
    else:
        districts = District.query.filter_by(is_active=True).all()

    result = []
    for d in districts:
        subdistricts = Subdistrict.query.filter_by(district_code=d.code, is_active=True).all()
        shops_count = Shop.query.filter_by(district_code=d.code, is_active=True).count()
        result.append({
            "code": d.code,
            "name": d.name,
            "name_english": d.name_english,
            "district_type": d.district_type,
            "population": d.population,
            "budget": d.budget,
            "performance_score": d.performance_score,
            "shops_count": shops_count,
            "subdistricts_count": len(subdistricts),
            "subdistricts": [{"id": s.id, "name": s.name, "type": s.subdistrict_type} for s in subdistricts]
        })

    return jsonify({"districts": result})


@app.route('/api/districts', methods=['POST'])
@jwt_required()
@role_required(['governor'])
def add_district():
    """إضافة مديرية جديدة"""
    data = request.json

    district_code = data.get('code').upper()
    if District.query.get(district_code):
        return jsonify({"error": "المديرية موجودة مسبقاً"}), 400

    district = District(
        code=district_code,
        governorate_code="ADN",
        name=data['name'],
        name_english=data.get('name_english'),
        district_type=data.get('district_type', 'district'),
        population=data.get('population', 0),
        budget=data.get('budget', 0),
        center_lat=data.get('center_lat'),
        center_lng=data.get('center_lng'),
        is_active=True
    )
    db.session.add(district)
    db.session.commit()

    # إضافة الأحياء/المدن التابعة
    subdistricts = data.get('subdistricts', [])
    for sub in subdistricts:
        subdistrict = Subdistrict(
            district_code=district_code,
            name=sub['name'],
            name_english=sub.get('name_english'),
            subdistrict_type=sub.get('type', 'neighborhood'),
            population=sub.get('population', 0),
            center_lat=sub.get('center_lat'),
            center_lng=sub.get('center_lng')
        )
        db.session.add(subdistrict)

    db.session.commit()

    # إشعار للمحافظ
    governor = User.query.filter_by(role='governor').first()
    if governor:
        send_notification(governor.id, "🏙️ إضافة مديرية جديدة",
                          f"تم إضافة {district.name} كنظام جديد", "district", 2)

    return jsonify({
        "message": f"✅ تم إضافة {district.name} بنجاح",
        "district_code": district_code,
        "subdistricts_added": len(subdistricts)
    })


@app.route('/api/districts/<district_code>/subdistricts', methods=['GET'])
def get_subdistricts(district_code):
    subdistricts = Subdistrict.query.filter_by(district_code=district_code, is_active=True).all()

    return jsonify({
        "district_code": district_code,
        "subdistricts": [{
            "id": s.id,
            "name": s.name,
            "name_english": s.name_english,
            "type": s.subdistrict_type,
            "population": s.population,
            "center_lat": s.center_lat,
            "center_lng": s.center_lng
        } for s in subdistricts]
    })


@app.route('/api/districts/<district_code>/subdistricts', methods=['POST'])
@jwt_required()
@role_required(['governor', 'mayor'])
def add_subdistrict(district_code):
    """إضافة مدينة/حي جديد"""
    data = request.json

    district = District.query.get(district_code)
    if not district:
        return jsonify({"error": "المديرية غير موجودة"}), 404

    subdistrict = Subdistrict(
        district_code=district_code,
        name=data['name'],
        name_english=data.get('name_english'),
        subdistrict_type=data.get('type', 'neighborhood'),
        population=data.get('population', 0),
        center_lat=data.get('center_lat'),
        center_lng=data.get('center_lng')
    )
    db.session.add(subdistrict)
    db.session.commit()

    return jsonify({
        "message": f"✅ تم إضافة {subdistrict.name} إلى {district.name}",
        "subdistrict_id": subdistrict.id
    })


@app.route('/api/shops', methods=['GET'])
@jwt_required()
def get_shops():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user.role == 'governor':
        shops = Shop.query.filter_by(is_active=True).all()
    elif user.role == 'mayor':
        shops = Shop.query.filter_by(district_code=user.district_code, is_active=True).all()
    else:
        shops = Shop.query.filter_by(is_active=True).limit(100).all()

    result = []
    for shop in shops:
        district = District.query.get(shop.district_code)
        subdistrict = Subdistrict.query.get(shop.subdistrict_id) if shop.subdistrict_id else None
        result.append({
            "id": shop.id,
            "name": shop.name,
            "owner_name": shop.owner_name,
            "owner_phone": shop.owner_phone,
            "owner_email": shop.owner_email,
            "district": district.name if district else shop.district_code,
            "district_code": shop.district_code,
            "subdistrict": subdistrict.name if subdistrict else None,
            "category": shop.category,
            "monthly_fee": shop.monthly_fee,
            "annual_fee": shop.annual_fee,
            "qr_code": shop.qr_code,
            "ussd_code": shop.ussd_code,
            "address": shop.address,
            "is_active": shop.is_active,
            "rating": shop.rating,
            "license_expiry": shop.license_expiry.isoformat() if shop.license_expiry else None
        })

    return jsonify({"shops": result, "total": len(result)})


@app.route('/api/shops', methods=['POST'])
@jwt_required()
@role_required(['governor', 'mayor'])
def add_shop():
    """إضافة محل تجاري جديد - آلية كاملة"""
    data = request.json
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    district_code = data.get('district_code') or user.district_code

    district = District.query.get(district_code)
    if not district:
        return jsonify({"error": "المديرية غير موجودة"}), 404

    # توليد معرف فريد
    shop_id = generate_shop_id(district_code)
    qr_code = generate_qr_string(shop_id)
    shop_number = int(shop_id.split('-')[-1])
    ussd_code = generate_ussd_string(shop_number)

    shop = Shop(
        id=shop_id,
        name=data['name'],
        owner_name=data.get('owner_name'),
        owner_phone=data.get('owner_phone'),
        owner_email=data.get('owner_email'),
        governorate_code="ADN",
        district_code=district_code,
        subdistrict_id=data.get('subdistrict_id'),
        category=data.get('category', 'ب'),
        sub_category=data.get('sub_category'),
        monthly_fee=data.get('monthly_fee', 0),
        annual_fee=data.get('annual_fee', 0),
        latitude=data.get('latitude'),
        longitude=data.get('longitude'),
        address=data.get('address'),
        qr_code=qr_code,
        ussd_code=ussd_code,
        commercial_register=data.get('commercial_register'),
        tax_number=data.get('tax_number'),
        created_by=user_id
    )
    db.session.add(shop)
    db.session.commit()

    # إشعار للمأمور
    mayor = User.query.filter_by(district_code=district_code, role='mayor').first()
    if mayor:
        send_notification(mayor.id, "🛍️ محل جديد",
                          f"تم إضافة محل جديد: {shop.name}", "shop", 1)

    return jsonify({
        "message": f"✅ تم إضافة المحل '{shop.name}' بنجاح",
        "shop_id": shop_id,
        "qr_code": qr_code,
        "ussd_code": ussd_code,
        "district": district.name
    })


@app.route('/api/collection/collect', methods=['POST'])
@jwt_required()
@role_required(['collector'])
def collect_payment():
    """تسجيل عملية تحصيل مع كشف احتيال"""
    data = request.json
    shop_id = data.get('shop_id')
    amount = data.get('amount')
    payment_method = data.get('method', 'qr')
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    shop = Shop.query.get(shop_id)
    if not shop:
        return jsonify({"error": "المحل غير موجود"}), 404

    collector_id = get_jwt_identity()

    # كشف الاحتيال الجغرافي
    suspicious = False
    suspicious_reason = ""

    if shop.latitude and latitude:
        try:
            distance = geodesic((shop.latitude, shop.longitude), (latitude, longitude)).meters
            if distance > 200:
                suspicious = True
                suspicious_reason = f"التحصيل من بعد {distance:.0f} متر"
        except:
            pass

    # تسجيل التحصيل
    collection = Collection(
        shop_id=shop_id,
        collector_id=collector_id,
        amount=amount,
        payment_method=payment_method,
        transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
        latitude=latitude,
        longitude=longitude,
        is_suspicious=suspicious,
        suspicious_reason=suspicious_reason
    )
    db.session.add(collection)

    # تحديث الإيرادات اليومية
    today = date.today()
    revenue = RevenueDaily.query.filter_by(district_code=shop.district_code, date=today).first()
    if revenue:
        revenue.total_amount += amount
        revenue.collection_count += 1
    else:
        revenue = RevenueDaily(
            governorate_code="ADN",
            district_code=shop.district_code,
            date=today,
            total_amount=amount,
            collection_count=1
        )
        db.session.add(revenue)

    shop.last_collection_date = datetime.utcnow()
    db.session.commit()

    # كشف الاحتيال المتقدم
    detect_fraud(collection.id)

    # فحص الإنذار الأحمر
    check_red_alert(shop.district_code)

    # إشعار لصاحب المحل (محاكاة)
    from_user = User.query.get(collector_id)
    if from_user:
        send_notification(collector_id, "💰 عملية تحصيل",
                          f"تم تحصيل {amount:,.0f} ريال من {shop.name}", "collection", 1)

    return jsonify({
        "message": "✅ تم التحصيل بنجاح",
        "collection_id": collection.id,
        "shop_name": shop.name,
        "amount": amount,
        "transaction_id": collection.transaction_id,
        "suspicious": suspicious,
        "suspicious_reason": suspicious_reason if suspicious else None
    })


@app.route('/api/collection/ussd/<ussd_code>/<amount>', methods=['GET'])
def ussd_collection(ussd_code, amount):
    """USSD للتحصيل عند انقطاع الإنترنت"""
    shop = Shop.query.filter_by(ussd_code=f"*159*{ussd_code}#").first()
    if not shop:
        return "❌ رمز المحل غير صحيح", 404

    collection = Collection(
        shop_id=shop.id,
        amount=float(amount),
        payment_method="ussd",
        transaction_id=f"USSD-{uuid.uuid4().hex[:8].upper()}"
    )
    db.session.add(collection)

    today = date.today()
    revenue = RevenueDaily.query.filter_by(district_code=shop.district_code, date=today).first()
    if revenue:
        revenue.total_amount += float(amount)
        revenue.collection_count += 1
    else:
        revenue = RevenueDaily(
            governorate_code="ADN",
            district_code=shop.district_code,
            date=today,
            total_amount=float(amount),
            collection_count=1
        )
        db.session.add(revenue)

    db.session.commit()

    return f"""
    <html dir="rtl">
    <head><meta charset="UTF-8"><title>تأكيد تحصيل USSD</title></head>
    <body style="background:#000; color:#d4af37; text-align:center; padding:50px; font-family:Arial;">
        <h1>✅ تم التحصيل بنجاح</h1>
        <p>المحل: {shop.name}</p>
        <p>المبلغ: {amount} ريال</p>
        <p>رقم العملية: {collection.transaction_id}</p>
        <p style="margin-top:30px;">شكراً لاستخدامكم نظام USSD</p>
    </body>
    </html>
    """


@app.route('/api/wallet/create', methods=['POST'])
@jwt_required()
def create_wallet():
    user_id = get_jwt_identity()

    existing = DigitalWallet.query.filter_by(user_id=user_id).first()
    if existing:
        return jsonify({"error": "المحفظة موجودة مسبقاً", "wallet_number": existing.wallet_number})

    wallet = DigitalWallet(
        user_id=user_id,
        wallet_number=generate_wallet_number(),
        balance=0,
        is_active=True
    )
    db.session.add(wallet)
    db.session.commit()

    send_notification(user_id, "💰 محفظة رقمية جديدة",
                      f"تم إنشاء محفظتك الرقمية برقم {wallet.wallet_number}", "wallet", 1)

    return jsonify({
        "message": "تم إنشاء المحفظة الرقمية بنجاح",
        "wallet_number": wallet.wallet_number,
        "balance": wallet.balance
    })


@app.route('/api/wallet/balance', methods=['GET'])
@jwt_required()
def get_wallet_balance():
    user_id = get_jwt_identity()
    wallet = DigitalWallet.query.filter_by(user_id=user_id).first()

    if not wallet:
        return jsonify({"error": "لا توجد محفظة رقمية"}), 404

    return jsonify({
        "wallet_number": wallet.wallet_number,
        "balance": wallet.balance,
        "currency": wallet.currency
    })


@app.route('/api/wallet/deposit', methods=['POST'])
@jwt_required()
def deposit_to_wallet():
    user_id = get_jwt_identity()
    data = request.json
    amount = data.get('amount', 0)

    if amount <= 0:
        return jsonify({"error": "المبلغ غير صحيح"}), 400

    wallet = DigitalWallet.query.filter_by(user_id=user_id).first()
    if not wallet:
        return jsonify({"error": "لا توجد محفظة رقمية"}), 404

    transaction = WalletTransaction(
        wallet_id=wallet.id,
        transaction_type='deposit',
        amount=amount,
        reference=f"DEP-{uuid.uuid4().hex[:8].upper()}",
        status='completed'
    )
    db.session.add(transaction)

    wallet.balance += amount
    db.session.commit()

    send_notification(user_id, "💰 إيداع", f"تم إيداع {amount:,.0f} ريال", "wallet", 1)

    return jsonify({
        "message": "تم الإيداع بنجاح",
        "new_balance": wallet.balance,
        "transaction_id": transaction.id
    })


@app.route('/api/wallet/pay', methods=['POST'])
@jwt_required()
def pay_from_wallet():
    user_id = get_jwt_identity()
    data = request.json
    amount = data.get('amount', 0)
    shop_id = data.get('shop_id')

    if amount <= 0:
        return jsonify({"error": "المبلغ غير صحيح"}), 400

    wallet = DigitalWallet.query.filter_by(user_id=user_id).first()
    if not wallet or wallet.balance < amount:
        return jsonify({"error": "رصيد غير كافٍ"}), 400

    transaction = WalletTransaction(
        wallet_id=wallet.id,
        transaction_type='payment',
        amount=amount,
        reference=f"PAY-{uuid.uuid4().hex[:8].upper()}",
        status='completed'
    )
    db.session.add(transaction)

    wallet.balance -= amount

    if shop_id:
        collection = Collection(
            shop_id=shop_id,
            amount=amount,
            payment_method="digital_wallet",
            transaction_id=transaction.reference
        )
        db.session.add(collection)

    db.session.commit()

    send_notification(user_id, "💳 دفع", f"تم دفع {amount:,.0f} ريال", "wallet", 1)

    return jsonify({
        "message": "تم الدفع بنجاح",
        "new_balance": wallet.balance,
        "transaction_id": transaction.id
    })


@app.route('/api/complaints', methods=['POST'])
def submit_complaint():
    data = request.json

    complaint = Complaint(
        complainant_name=data.get('name', 'مواطن'),
        complainant_phone=data.get('phone'),
        complaint_type=data.get('type', 'other'),
        subject=data['subject'],
        description=data['description'],
        district_code=data.get('district_code'),
        status='pending'
    )
    db.session.add(complaint)
    db.session.commit()

    governor = User.query.filter_by(role='governor').first()
    if governor:
        send_notification(governor.id, "📋 شكوى جديدة",
                          f"شكوى جديدة: {complaint.subject}", "complaint", 2)

    return jsonify({
        "message": "تم استلام شكواك، سيتم معالجتها قريباً",
        "complaint_id": complaint.id,
        "tracking_number": f"CM-{complaint.id:06d}"
    })


@app.route('/api/complaints', methods=['GET'])
@jwt_required()
@role_required(['governor', 'mayor'])
def get_complaints():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user.role == 'governor':
        complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    else:
        complaints = Complaint.query.filter_by(district_code=user.district_code).order_by(
            Complaint.created_at.desc()).all()

    result = []
    for c in complaints:
        result.append({
            "id": c.id,
            "subject": c.subject,
            "description": c.description[:100],
            "type": c.complaint_type,
            "status": c.status,
            "name": c.complainant_name,
            "phone": c.complainant_phone,
            "created_at": c.created_at.isoformat()
        })

    return jsonify({"complaints": result, "total": len(result)})


@app.route('/api/complaints/<int:complaint_id>/resolve', methods=['PUT'])
@jwt_required()
@role_required(['governor', 'mayor'])
def resolve_complaint(complaint_id):
    data = request.json
    complaint = Complaint.query.get(complaint_id)

    if not complaint:
        return jsonify({"error": "الشكوى غير موجودة"}), 404

    complaint.status = data.get('status', 'resolved')
    complaint.resolution_notes = data.get('notes')
    complaint.resolved_at = datetime.utcnow()

    if data.get('status') == 'resolved' and data.get('rating'):
        rating = CitizenRating(
            citizen_name=complaint.complainant_name,
            citizen_phone=complaint.complainant_phone,
            service_type='complaint',
            rating=data.get('rating', 5),
            comment=data.get('rating_comment')
        )
        db.session.add(rating)

    db.session.commit()

    return jsonify({"message": "تم تحديث حالة الشكوى"})


@app.route('/api/ratings/submit', methods=['POST'])
def submit_rating():
    data = request.json

    rating = CitizenRating(
        citizen_name=data.get('name', 'مواطن'),
        citizen_phone=data.get('phone'),
        service_type=data['service_type'],
        rating=data['rating'],
        comment=data.get('comment'),
        district_code=data.get('district_code')
    )
    db.session.add(rating)
    db.session.commit()

    if data.get('district_code'):
        calculate_district_score(data['district_code'])

    return jsonify({"message": "شكراً لتقييمك", "rating_id": rating.id})


@app.route('/api/ratings/stats', methods=['GET'])
def get_rating_stats():
    ratings = CitizenRating.query.all()

    if not ratings:
        return jsonify({"average_rating": 0, "total_ratings": 0})

    avg_rating = np.mean([r.rating for r in ratings])

    stats = {
        "average_rating": round(avg_rating, 2),
        "total_ratings": len(ratings),
        "distribution": {
            "5_stars": len([r for r in ratings if r.rating == 5]),
            "4_stars": len([r for r in ratings if r.rating == 4]),
            "3_stars": len([r for r in ratings if r.rating == 3]),
            "2_stars": len([r for r in ratings if r.rating == 2]),
            "1_stars": len([r for r in ratings if r.rating == 1])
        }
    }

    return jsonify(stats)


@app.route('/api/licenses/issue', methods=['POST'])
@jwt_required()
@role_required(['governor', 'mayor'])
def issue_license():
    """إصدار ترخيص جديد"""
    data = request.json
    shop_id = data.get('shop_id')

    shop = Shop.query.get(shop_id)
    if not shop:
        return jsonify({"error": "المحل غير موجود"}), 404

    existing = BusinessLicense.query.filter_by(shop_id=shop_id, status='active').first()
    if existing:
        return jsonify({"error": "يوجد ترخيص ساري", "license_number": existing.license_number})

    license_number = generate_license_number()
    issue_date = date.today()
    expiry_date = issue_date + timedelta(days=365)

    license = BusinessLicense(
        license_number=license_number,
        shop_id=shop_id,
        license_type=data.get('license_type', 'commercial'),
        issue_date=issue_date,
        expiry_date=expiry_date,
        fee_paid=data.get('fee', 0),
        status='active'
    )
    db.session.add(license)

    shop.license_expiry = expiry_date
    db.session.commit()

    if shop.created_by:
        send_notification(shop.created_by, "📜 ترخيص جديد",
                          f"تم إصدار ترخيص لمحلك {shop.name}", "license", 2)

    return jsonify({
        "message": "تم إصدار الترخيص بنجاح",
        "license_number": license_number,
        "issue_date": issue_date.isoformat(),
        "expiry_date": expiry_date.isoformat()
    })


@app.route('/api/licenses/<shop_id>', methods=['GET'])
def get_license(shop_id):
    license = BusinessLicense.query.filter_by(shop_id=shop_id, status='active').first()

    if not license:
        return jsonify({"error": "لا يوجد ترخيص ساري", "shop_id": shop_id})

    days_until_expiry = (license.expiry_date - date.today()).days

    return jsonify({
        "license_number": license.license_number,
        "shop_id": license.shop_id,
        "issue_date": license.issue_date.isoformat(),
        "expiry_date": license.expiry_date.isoformat(),
        "days_until_expiry": days_until_expiry,
        "status": license.status,
        "is_valid": days_until_expiry > 0
    })


@app.route('/api/inventory/add', methods=['POST'])
@jwt_required()
def add_inventory_item():
    data = request.json
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user.role not in ['governor', 'mayor', 'collector']:
        return jsonify({"error": "غير مصرح"}), 403

    item = Inventory(
        shop_id=data['shop_id'],
        product_name=data['product_name'],
        product_code=data.get('product_code'),
        category=data.get('category'),
        quantity=data['quantity'],
        unit_price=data.get('unit_price', 0),
        total_value=data['quantity'] * data.get('unit_price', 0),
        reorder_level=data.get('reorder_level', 0)
    )
    db.session.add(item)
    db.session.commit()

    return jsonify({"message": "تم إضافة الصنف", "item_id": item.id})


@app.route('/api/inventory/<shop_id>', methods=['GET'])
@jwt_required()
def get_inventory(shop_id):
    items = Inventory.query.filter_by(shop_id=shop_id).all()

    result = []
    total_value = 0
    low_stock_items = []

    for item in items:
        total_value += item.total_value
        if item.quantity <= item.reorder_level:
            low_stock_items.append(item.product_name)

        result.append({
            "product_name": item.product_name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "total_value": item.total_value,
            "reorder_level": item.reorder_level
        })

    return jsonify({
        "shop_id": shop_id,
        "items": result,
        "total_inventory_value": total_value,
        "items_count": len(result),
        "low_stock_alerts": low_stock_items
    })


@app.route('/api/campaigns', methods=['GET'])
@jwt_required()
def get_campaigns():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user.role == 'governor':
        campaigns = Campaign.query.all()
    elif user.role == 'mayor':
        campaigns = Campaign.query.filter_by(district_code=user.district_code).all()
    else:
        campaigns = Campaign.query.filter_by(status='active').all()

    result = []
    for c in campaigns:
        district = District.query.get(c.district_code)
        progress = (c.collected_amount / c.target_amount * 100) if c.target_amount > 0 else 0
        result.append({
            "id": c.id,
            "name": c.name,
            "district": district.name if district else c.district_code,
            "status": c.status,
            "target_amount": c.target_amount,
            "collected_amount": c.collected_amount,
            "progress": round(progress, 1),
            "start_date": c.start_date.isoformat() if c.start_date else None,
            "end_date": c.end_date.isoformat() if c.end_date else None
        })

    return jsonify({"campaigns": result})


@app.route('/api/campaigns', methods=['POST'])
@jwt_required()
@role_required(['governor', 'mayor'])
def create_campaign():
    data = request.json
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    district_code = data.get('district_code') or user.district_code

    campaign = Campaign(
        name=data['name'],
        district_code=district_code,
        target_amount=data.get('target_amount', 0),
        start_date=datetime.fromisoformat(data['start_date']) if data.get('start_date') else datetime.utcnow(),
        end_date=datetime.fromisoformat(data['end_date']) if data.get('end_date') else None,
        status='active'
    )
    db.session.add(campaign)
    db.session.commit()

    # إشعار
    governor = User.query.filter_by(role='governor').first()
    if governor:
        send_notification(governor.id, "🚩 حملة جديدة",
                          f"تم إطلاق حملة {campaign.name}", "campaign", 2)

    return jsonify({"message": "تم إنشاء الحملة", "campaign_id": campaign.id})


@app.route('/api/governor/dashboard', methods=['GET'])
@jwt_required()
@role_required(['governor'])
def governor_dashboard():
    """لوحة تحكم المحافظ المتقدمة"""
    today = date.today()
    districts = District.query.filter_by(is_active=True).all()

    total_revenue_today = 0
    district_performance = []

    for dist in districts:
        rev = RevenueDaily.query.filter_by(district_code=dist.code, date=today).first()
        amount = rev.total_amount if rev else 0
        total_revenue_today += amount

        shops_count = Shop.query.filter_by(district_code=dist.code, is_active=True).count()
        complaints_count = Complaint.query.filter_by(district_code=dist.code, status='pending').count()
        campaigns_count = Campaign.query.filter_by(district_code=dist.code, status='active').count()

        district_performance.append({
            "code": dist.code,
            "name": dist.name,
            "revenue": amount,
            "shops": shops_count,
            "campaigns": campaigns_count,
            "complaints": complaints_count,
            "performance": dist.performance_score,
            "population": dist.population
        })

    district_performance.sort(key=lambda x: x['revenue'], reverse=True)

    # إحصائيات عامة
    total_shops = Shop.query.filter_by(is_active=True).count()
    total_complaints = Complaint.query.filter_by(status='pending').count()
    active_campaigns = Campaign.query.filter_by(status='active').count()
    active_alerts = Alert.query.filter_by(is_resolved=False).count()

    # تقييمات
    ratings = CitizenRating.query.all()
    avg_rating = np.mean([r.rating for r in ratings]) if ratings else 0

    # إجمالي الإيرادات الشهرية
    month_start = date(today.year, today.month, 1)
    month_revenues = RevenueDaily.query.filter(RevenueDaily.date >= month_start).all()
    total_month_revenue = sum(r.total_amount for r in month_revenues)

    return jsonify({
        "live_stats": {
            "total_revenue_today": total_revenue_today,
            "total_month_revenue": total_month_revenue,
            "total_shops": total_shops,
            "active_campaigns": active_campaigns,
            "pending_complaints": total_complaints,
            "active_alerts": active_alerts,
            "citizen_satisfaction": round(avg_rating, 1),
            "districts_count": len(districts)
        },
        "district_ranking": district_performance,
        "last_update": datetime.now().isoformat()
    })


@app.route('/api/analytics/fraud', methods=['GET'])
@jwt_required()
@role_required(['governor'])
def fraud_analytics():
    """كشف الاحتيال"""
    frauds = FraudDetection.query.order_by(FraudDetection.created_at.desc()).limit(50).all()

    result = []
    for f in frauds:
        shop = Shop.query.get(f.shop_id)
        result.append({
            "id": f.id,
            "shop_name": shop.name if shop else "غير معروف",
            "detection_type": f.detection_type,
            "description": f.description,
            "confidence_score": f.confidence_score,
            "created_at": f.created_at.isoformat()
        })

    stats = {
        "total_suspicious": len(frauds),
        "geo_fence_violations": FraudDetection.query.filter_by(detection_type="geo_fence").count(),
        "high_confidence": FraudDetection.query.filter(FraudDetection.confidence_score > 0.8).count()
    }

    return jsonify({"fraud_cases": result, "statistics": stats})


@app.route('/api/analytics/predict', methods=['GET'])
@jwt_required()
def predict_revenue():
    """التنبؤ بالإيرادات باستخدام الذكاء الاصطناعي"""
    today = date.today()
    revenues = []
    for i in range(30, 0, -1):
        d = today - timedelta(days=i)
        rev = RevenueDaily.query.filter_by(date=d).all()
        total = sum(r.total_amount for r in rev)
        revenues.append(total)

    if len(revenues) >= 7:
        # المتوسط المتحرك المرجح
        weights = np.exp(np.linspace(-1, 0, 7))
        weights = weights / weights.sum()
        next_week = np.sum(np.array(revenues[-7:]) * weights) * 7
        next_month = next_week * 4
        next_year = next_month * 12
    else:
        next_month = 0
        next_year = 0

    return jsonify({
        "predicted_next_month": round(next_month, 2),
        "predicted_next_year": round(next_year, 2),
        "based_on": "تحليل الذكاء الاصطناعي - المتوسط المتحرك المرجح",
        "confidence": "high" if len(revenues) >= 60 else "medium"
    })


@app.route('/api/development/projects', methods=['GET'])
@jwt_required()
def get_projects():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user.role == 'governor':
        projects = DevelopmentProject.query.all()
    elif user.role == 'mayor':
        projects = DevelopmentProject.query.filter_by(district_code=user.district_code).all()
    else:
        projects = DevelopmentProject.query.filter_by(status='completed').limit(20).all()

    result = []
    for p in projects:
        district = District.query.get(p.district_code)
        result.append({
            "id": p.id,
            "project_name": p.project_name,
            "district": district.name if district else p.district_code,
            "project_type": p.project_type,
            "description": p.description,
            "budget": p.budget,
            "spent_amount": p.spent_amount,
            "status": p.status,
            "completion_percentage": p.completion_percentage
        })

    stats = {
        "total_projects": len(result),
        "completed_projects": len([p for p in result if p['status'] == 'completed']),
        "total_budget": sum(p['budget'] for p in result),
        "roads_projects": len([p for p in result if p['project_type'] == 'roads']),
        "sanitation_projects": len([p for p in result if p['project_type'] == 'sanitation']),
        "lighting_projects": len([p for p in result if p['project_type'] == 'lighting'])
    }

    return jsonify({"projects": result, "stats": stats})


@app.route('/api/development/projects', methods=['POST'])
@jwt_required()
@role_required(['governor'])
def add_project():
    data = request.json

    project = DevelopmentProject(
        district_code=data['district_code'],
        project_name=data['project_name'],
        project_type=data['project_type'],
        description=data.get('description'),
        budget=data.get('budget', 0),
        status=data.get('status', 'planned'),
        completion_percentage=data.get('completion_percentage', 0)
    )
    db.session.add(project)
    db.session.commit()

    return jsonify({"message": "تم إضافة المشروع", "project_id": project.id})


@app.route('/api/reports/export', methods=['GET'])
@jwt_required()
@role_required(['governor'])
def export_report():
    report_type = request.args.get('type', 'collections')
    format_type = request.args.get('format', 'json')

    if report_type == 'collections':
        data = Collection.query.all()
        export_data = [{
            "المحل": Shop.query.get(c.shop_id).name if c.shop_id else "",
            "المبلغ": c.amount,
            "طريقة الدفع": c.payment_method,
            "التاريخ": c.created_at.strftime("%Y-%m-%d %H:%M")
        } for c in data]
    elif report_type == 'shops':
        data = Shop.query.all()
        export_data = [{
            "اسم المحل": s.name,
            "المالك": s.owner_name,
            "المديرية": District.query.get(s.district_code).name if s.district_code else "",
            "الفئة": s.category,
            "الرسم الشهري": s.monthly_fee,
            "التقييم": s.rating
        } for s in data]
    elif report_type == 'revenue':
        data = RevenueDaily.query.all()
        export_data = [{
            "المديرية": District.query.get(r.district_code).name if r.district_code else "",
            "التاريخ": r.date.isoformat(),
            "المبلغ": r.total_amount,
            "عدد العمليات": r.collection_count
        } for r in data]
    else:
        return jsonify({"error": "نوع التقرير غير معروف"}), 400

    if format_type == 'csv':
        df = pd.DataFrame(export_data)
        output = io.StringIO()
        df.to_csv(output, index=False, encoding='utf-8-sig')
        return Response(output.getvalue(), mimetype='text/csv',
                        headers={"Content-Disposition": f"attachment;filename={report_type}_report.csv"})

    elif format_type == 'json':
        return jsonify({"data": export_data, "count": len(export_data), "exported_at": datetime.now().isoformat()})

    else:
        return jsonify({"data": export_data, "count": len(export_data)})


@app.route('/api/public/transparency', methods=['GET'])
def public_transparency():
    """لوحة الشفافية العامة"""
    today = date.today()
    districts = District.query.filter_by(is_active=True).all()

    total_today = 0
    districts_data = []

    for dist in districts:
        rev = RevenueDaily.query.filter_by(district_code=dist.code, date=today).first()
        amount = rev.total_amount if rev else 0
        total_today += amount
        districts_data.append({
            "name": dist.name,
            "revenue": amount,
            "performance": dist.performance_score,
            "population": dist.population
        })

    # مشاريع التنمية
    projects = DevelopmentProject.query.filter_by(status='completed').limit(5).all()
    ongoing_projects = DevelopmentProject.query.filter_by(status='ongoing').limit(5).all()

    # إحصائيات سريعة
    total_shops = Shop.query.filter_by(is_active=True).count()
    total_collections = Collection.query.count()

    return jsonify({
        "governorate": "محافظة عدن",
        "date": today.isoformat(),
        "total_revenue_today": total_today,
        "total_shops": total_shops,
        "total_collections": total_collections,
        "districts": districts_data,
        "completed_projects": [{
            "name": p.project_name,
            "type": p.project_type,
            "completion": p.completion_percentage
        } for p in projects],
        "ongoing_projects": [{
            "name": p.project_name,
            "type": p.project_type,
            "completion": p.completion_percentage
        } for p in ongoing_projects],
        "message": "📢 ديوان محافظة عدن - الشفافية العامة مكفولة"
    })


@app.route('/api/citizen/report', methods=['POST'])
def citizen_report():
    """إبلاغ المواطن"""
    data = request.json

    report = CitizenReport(
        reporter_name=data.get('name', 'مواطن'),
        reporter_phone=data.get('phone'),
        shop_name=data['shop_name'],
        district_code=data.get('district_code'),
        violation_type=data.get('violation_type', 'no_qr'),
        location=data.get('location'),
        latitude=data.get('latitude'),
        longitude=data.get('longitude'),
        description=data.get('description'),
        reward_points=10
    )
    db.session.add(report)

    # إنشاء إنذار
    alert = Alert(
        district_code=data.get('district_code'),
        alert_type="ORANGE",
        severity=2,
        message=f"بلاغ مواطن: {data['shop_name']} - {data.get('violation_type')}"
    )
    db.session.add(alert)
    db.session.commit()

    # إشعار للمأمور
    if data.get('district_code'):
        mayor = User.query.filter_by(district_code=data['district_code'], role='mayor').first()
        if mayor:
            send_notification(mayor.id, "📱 بلاغ جديد",
                              f"بلاغ عن محل {data['shop_name']}", "report", 2)

    return jsonify({
        "message": "✅ تم استلام البلاغ، شكراً لك",
        "reward_points": 10,
        "report_id": report.id
    })


@app.route('/api/live-revenue', methods=['GET'])
def get_live_revenue():
    today = date.today()
    revenues = RevenueDaily.query.filter_by(date=today).all()
    total = sum(r.total_amount for r in revenues)

    # آخر 5 تحصيلات
    last_collections = Collection.query.order_by(Collection.created_at.desc()).limit(5).all()
    recent = []
    for c in last_collections:
        shop = Shop.query.get(c.shop_id)
        recent.append({
            "shop_name": shop.name if shop else "",
            "amount": c.amount,
            "time": c.created_at.strftime("%H:%M:%S")
        })

    return jsonify({
        "total_revenue": total,
        "recent_collections": recent,
        "last_update": datetime.now().isoformat()
    })


# ==================== WebSocket ====================

@socketio.on('connect')
def handle_connect():
    print(f'✅ Client connected: {request.sid}')


@socketio.on('authenticate')
def handle_auth(data):
    token = data.get('token')
    try:
        decoded = decode_token(token)
        user_id = decoded['sub']
        join_room(f'user_{user_id}')
        emit('connected', {'message': 'Connected to notification system', 'user_id': user_id})
        print(f'✅ User {user_id} authenticated')
    except Exception as e:
        emit('error', {'message': 'Authentication failed'})


@socketio.on('disconnect')
def handle_disconnect():
    print(f'❌ Client disconnected: {request.sid}')


# ==================== واجهة المستخدم الكاملة ====================

HTML_TEMPLATE_FULL = '''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ديوان محافظة عدن - النظام المتكامل القوي</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Cairo', 'Tahoma', sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
            color: #fff;
            min-height: 100vh;
        }
        .gold-bar { background: linear-gradient(90deg, #d4af37 0%, #f9e07f 50%, #d4af37 100%); height: 5px; }
        .header {
            background: #000;
            padding: 20px 40px;
            border-bottom: 1px solid rgba(212, 175, 55, 0.3);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .header-content { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; }
        .logo h1 { color: #d4af37; font-size: 28px; }
        .logo p { color: #888; font-size: 12px; }
        .logo span { color: #d4af37; }
        .user-info { background: rgba(212, 175, 55, 0.1); padding: 10px 20px; border-radius: 10px; display: flex; align-items: center; gap: 15px; }
        .user-info span { color: #d4af37; font-weight: bold; }
        .notification-bell { position: relative; cursor: pointer; font-size: 20px; }
        .notification-bell .badge {
            position: absolute;
            top: -8px;
            right: -8px;
            background: #ff0000;
            color: #fff;
            border-radius: 50%;
            padding: 2px 6px;
            font-size: 10px;
        }
        .tabs {
            display: flex;
            gap: 5px;
            padding: 0 40px;
            background: #0d0d0d;
            flex-wrap: wrap;
            overflow-x: auto;
        }
        .tab-btn {
            background: transparent;
            border: none;
            padding: 15px 25px;
            color: #aaa;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            transition: all 0.3s;
            white-space: nowrap;
        }
        .tab-btn:hover, .tab-btn.active { color: #d4af37; border-bottom-color: #d4af37; background: rgba(212, 175, 55, 0.1); }
        .content { padding: 30px 40px; }
        .tab-pane { display: none; animation: fadeIn 0.5s; }
        .tab-pane.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card {
            background: linear-gradient(135deg, #111 0%, #1a1a1a 100%);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid #222;
            transition: all 0.3s;
            cursor: pointer;
        }
        .card:hover { border-color: #d4af37; transform: translateY(-5px); box-shadow: 0 10px 30px rgba(212, 175, 55, 0.1); }
        .card-value { font-size: 32px; font-weight: bold; color: #d4af37; }
        .card-title { color: #888; font-size: 14px; margin-top: 10px; }
        .card-icon { font-size: 40px; margin-bottom: 10px; }
        .table-container { background: #111; border-radius: 15px; overflow-x: auto; border: 1px solid #222; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; }
        th { background: #1a1a1a; color: #d4af37; padding: 15px; text-align: center; }
        td { padding: 12px 15px; text-align: center; border-bottom: 1px solid #222; color: #ccc; }
        tr:hover { background: rgba(212, 175, 55, 0.05); }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; color: #d4af37; font-weight: bold; }
        input, select, textarea {
            width: 100%;
            padding: 12px;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            color: #fff;
            font-size: 14px;
        }
        input:focus, select:focus, textarea:focus { outline: none; border-color: #d4af37; }
        button {
            background: linear-gradient(135deg, #d4af37 0%, #b8960c 100%);
            color: #000;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s;
        }
        button:hover { transform: scale(1.02); box-shadow: 0 5px 20px rgba(212, 175, 55, 0.3); }
        button.secondary { background: #222; color: #d4af37; border: 1px solid #d4af37; }
        button.secondary:hover { background: #d4af37; color: #000; }
        .alert-red { background: rgba(255,0,0,0.2); border-right: 4px solid #ff0000; padding: 12px; margin: 10px 0; border-radius: 8px; }
        .alert-orange { background: rgba(255,165,0,0.2); border-right: 4px solid #ffa500; padding: 12px; margin: 10px 0; border-radius: 8px; }
        .alert-green { background: rgba(0,255,0,0.1); border-right: 4px solid #00ff00; padding: 12px; margin: 10px 0; border-radius: 8px; }
        .login-screen {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: #000;
            z-index: 1000;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-box {
            background: #111;
            padding: 40px;
            border-radius: 20px;
            border: 1px solid #d4af37;
            width: 90%;
            max-width: 400px;
        }
        .login-box h2 { color: #d4af37; text-align: center; margin-bottom: 30px; }
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #111;
            border-right: 4px solid #d4af37;
            padding: 12px 20px;
            border-radius: 8px;
            z-index: 1100;
            display: none;
        }
        .notification-dropdown {
            position: absolute;
            top: 70px;
            right: 20px;
            width: 350px;
            background: #111;
            border: 1px solid #d4af37;
            border-radius: 10px;
            z-index: 200;
            display: none;
            max-height: 400px;
            overflow-y: auto;
        }
        .notification-item {
            padding: 12px;
            border-bottom: 1px solid #222;
            cursor: pointer;
        }
        .notification-item:hover { background: rgba(212, 175, 55, 0.1); }
        .notification-item.unread { background: rgba(212, 175, 55, 0.05); border-right: 3px solid #d4af37; }
        .notification-title { font-weight: bold; color: #d4af37; }
        .notification-message { font-size: 12px; color: #aaa; margin-top: 5px; }
        .notification-time { font-size: 10px; color: #555; margin-top: 5px; }
        .rating-stars { color: #d4af37; font-size: 30px; cursor: pointer; text-align: center; margin: 15px 0; }
        .rating-stars .star { transition: all 0.2s; cursor: pointer; }
        .rating-stars .star:hover, .rating-stars .star.active { color: #ffd700; text-shadow: 0 0 5px #d4af37; }
        canvas { max-height: 300px; background: #111; border-radius: 10px; padding: 10px; }
        .badge { display: inline-block; padding: 3px 8px; border-radius: 5px; font-size: 11px; font-weight: bold; }
        .badge-success { background: #00ff00; color: #000; }
        .badge-warning { background: #ffa500; color: #000; }
        .badge-danger { background: #ff0000; color: #fff; }
        @media (max-width: 768px) { .content { padding: 20px; } .tabs { padding: 0 20px; } .tab-btn { padding: 10px 15px; font-size: 12px; } }
    </style>
</head>
<body>
    <div class="gold-bar"></div>

    <div id="loginScreen" class="login-screen">
        <div class="login-box">
            <h2>🏛️ ديوان محافظة عدن</h2>
            <h3 style="text-align:center; color:#888; margin-bottom:20px;">النظام المتكامل القوي</h3>
            <form onsubmit="event.preventDefault(); login();">
                <input type="text" id="loginUsername" placeholder="اسم المستخدم" value="governor">
                <input type="password" id="loginPassword" placeholder="كلمة المرور" value="admin123">
                <button type="submit" style="width:100%;">تسجيل الدخول</button>
            </form>
            <p style="text-align:center; margin-top:20px; color:#555; font-size:12px;">
                🔐 حسابات تجريبية:<br>
                👑 محافظ: governor / admin123<br>
                🏙️ مأمور المنصورة: mayor_mansoura / mayor123<br>
                👮 محصل: collector1 / collector123
            </p>
        </div>
    </div>

    <div id="mainApp" style="display:none;">
        <div class="header">
            <div class="header-content">
                <div class="logo">
                    <h1>🏛️ ديوان محافظة <span>عدن</span></h1>
                    <p>النظام المتكامل - إدارة الإيرادات والتنمية</p>
                </div>
                <div class="user-info">
                    <div class="notification-bell" onclick="toggleNotifications()">
                        🔔 <span id="notificationBadge" class="badge" style="display:none; background:#ff0000;">0</span>
                    </div>
                    <span id="userName">المستخدم</span> | <span id="userRole">الدور</span>
                    <button onclick="logout()" class="secondary" style="padding:5px 15px;">تسجيل خروج</button>
                </div>
            </div>
            <div id="notificationDropdown" class="notification-dropdown">
                <div style="padding:10px; border-bottom:1px solid #d4af37; font-weight:bold;">📬 الإشعارات</div>
                <div id="notificationsList" style="max-height:350px; overflow-y:auto;"></div>
            </div>
        </div>

        <div class="tabs">
            <button class="tab-btn active" onclick="showTab('dashboard')">📊 لوحة التحكم</button>
            <button class="tab-btn" onclick="showTab('districts')">🏙️ المديريات</button>
            <button class="tab-btn" onclick="showTab('shops')">🛍️ المحلات</button>
            <button class="tab-btn" onclick="showTab('collections')">💰 التحصيل</button>
            <button class="tab-btn" onclick="showTab('wallet')">💳 المحفظة</button>
            <button class="tab-btn" onclick="showTab('complaints')">📋 الشكاوى</button>
            <button class="tab-btn" onclick="showTab('ratings')">⭐ التقييمات</button>
            <button class="tab-btn" onclick="showTab('licenses')">📜 التراخيص</button>
            <button class="tab-btn" onclick="showTab('campaigns')">🚩 الحملات</button>
            <button class="tab-btn" onclick="showTab('projects')">🏗️ المشاريع</button>
            <button class="tab-btn" onclick="showTab('reports')">📊 التقارير</button>
            <button class="tab-btn" onclick="showTab('transparency')">📢 الشفافية</button>
        </div>

        <div class="content">
            <!-- لوحة التحكم -->
            <div id="dashboardTab" class="tab-pane active">
                <div class="cards" id="dashboardCards"></div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:20px;">
                    <div class="card"><canvas id="revenueChart"></canvas></div>
                    <div class="card"><canvas id="performanceChart"></canvas></div>
                </div>
                <h3 style="color:#d4af37;">🏆 ترتيب المديريات</h3>
                <div class="table-container" id="rankingTable"></div>
                <div id="liveRevenue" style="text-align:center; margin-top:20px; padding:15px; background:#111; border-radius:10px;"></div>
            </div>

            <!-- المديريات -->
            <div id="districtsTab" class="tab-pane">
                <button onclick="loadDistricts()" class="secondary">🔄 تحديث</button>
                <div class="table-container" id="districtsTable"></div>
                <div class="card" style="margin-top:20px;">
                    <h3 style="color:#d4af37;">➕ إضافة مديرية جديدة</h3>
                    <form onsubmit="event.preventDefault(); addDistrict();">
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px;">
                            <div class="form-group"><label>الرمز (مثال: ADN-NEW)</label><input type="text" id="newDistrictCode" placeholder="ADN-XXX" required></div>
                            <div class="form-group"><label>اسم المديرية</label><input type="text" id="newDistrictName" required></div>
                            <div class="form-group"><label>الاسم بالإنجليزية</label><input type="text" id="newDistrictNameEn"></div>
                            <div class="form-group"><label>عدد السكان</label><input type="number" id="newDistrictPopulation"></div>
                            <div class="form-group"><label>الميزانية</label><input type="number" id="newDistrictBudget"></div>
                        </div>
                        <button type="submit">إضافة المديرية</button>
                    </form>
                </div>
            </div>

            <!-- المحلات -->
            <div id="shopsTab" class="tab-pane">
                <div style="display:grid; grid-template-columns:1fr 2fr; gap:20px;">
                    <div class="card">
                        <h3 style="color:#d4af37;">➕ إضافة محل جديد</h3>
                        <form onsubmit="event.preventDefault(); addShop();">
                            <div class="form-group"><label>اسم المحل</label><input type="text" id="shopName" required></div>
                            <div class="form-group"><label>اسم المالك</label><input type="text" id="ownerName"></div>
                            <div class="form-group"><label>رقم المالك</label><input type="text" id="ownerPhone"></div>
                            <div class="form-group"><label>المديرية</label><select id="shopDistrict"></select></div>
                            <div class="form-group"><label>الحي/المدينة</label><select id="shopSubdistrict"></select></div>
                            <div class="form-group"><label>الفئة</label><select id="shopCategory"><option>أ</option><option>ب</option><option>ج</option></select></div>
                            <div class="form-group"><label>الرسم الشهري</label><input type="number" id="monthlyFee"></div>
                            <div class="form-group"><label>العنوان</label><input type="text" id="shopAddress"></div>
                            <button type="submit">إضافة المحل</button>
                        </form>
                    </div>
                    <div><button onclick="loadShops()" class="secondary">🔄 تحديث المحلات</button><div class="table-container" id="shopsTable"></div></div>
                </div>
            </div>

            <!-- التحصيل -->
            <div id="collectionsTab" class="tab-pane">
                <div style="display:grid; grid-template-columns:1fr 2fr; gap:20px;">
                    <div class="card">
                        <h3 style="color:#d4af37;">💳 تحصيل جديد</h3>
                        <form onsubmit="event.preventDefault(); collectPayment();">
                            <div class="form-group"><label>رمز المحل</label><input type="text" id="collectShopId" placeholder="ADN-MN-0001" required></div>
                            <div class="form-group"><label>المبلغ</label><input type="number" id="collectAmount" required></div>
                            <div class="form-group"><label>طريقة الدفع</label><select id="paymentMethod"><option>qr</option><option>cash</option><option>digital_wallet</option></select></div>
                            <button type="submit">تسجيل التحصيل</button>
                        </form>
                        <p style="margin-top:15px; font-size:12px; color:#888;">📱 خاصية USSD: *159*رمز_المحل# (بدون إنترنت)</p>
                    </div>
                    <div><button onclick="loadCollections()" class="secondary">🔄 تحديث التحصيلات</button><div class="table-container" id="collectionsTable"></div></div>
                </div>
            </div>

            <!-- المحفظة الرقمية -->
            <div id="walletTab" class="tab-pane">
                <div class="cards" id="walletCards"></div>
                <div class="card" style="max-width:400px; margin:0 auto;">
                    <h3 style="color:#d4af37;">💰 محفظتي الرقمية</h3>
                    <form onsubmit="event.preventDefault(); depositToWallet();">
                        <div class="form-group"><label>المبلغ للإيداع</label><input type="number" id="depositAmount" placeholder="المبلغ"></div>
                        <button type="submit">إيداع</button>
                    </form>
                    <form onsubmit="event.preventDefault(); payFromWallet();" style="margin-top:15px;">
                        <div class="form-group"><label>رمز المحل للدفع</label><input type="text" id="payShopId" placeholder="ADN-MN-0001"></div>
                        <div class="form-group"><label>المبلغ للدفع</label><input type="number" id="payAmount" placeholder="المبلغ"></div>
                        <button type="submit">دفع</button>
                    </form>
                </div>
            </div>

            <!-- الشكاوى -->
            <div id="complaintsTab" class="tab-pane">
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">
                    <div class="card">
                        <h3 style="color:#d4af37;">📝 تقديم شكوى</h3>
                        <form onsubmit="event.preventDefault(); submitComplaint();">
                            <div class="form-group"><label>الموضوع</label><input type="text" id="complaintSubject" required></div>
                            <div class="form-group"><label>نوع الشكوى</label><select id="complaintType"><option>service</option><option>employee</option><option>shop</option><option>other</option></select></div>
                            <div class="form-group"><label>الوصف</label><textarea id="complaintDesc" rows="3" required></textarea></div>
                            <div class="form-group"><label>المديرية</label><select id="complaintDistrict"></select></div>
                            <div class="form-group"><label>رقم هاتفك</label><input type="text" id="complaintPhone"></div>
                            <button type="submit">إرسال الشكوى</button>
                        </form>
                    </div>
                    <div><button onclick="loadComplaints()" class="secondary">🔄 تحديث الشكاوى</button><div class="table-container" id="complaintsTable"></div></div>
                </div>
            </div>

            <!-- التقييمات -->
            <div id="ratingsTab" class="tab-pane">
                <div class="card" style="max-width:500px; margin:0 auto; text-align:center;">
                    <h3 style="color:#d4af37;">⭐ تقييم رضا المواطنين</h3>
                    <div class="rating-stars" id="ratingStars">
                        <span class="star" data-value="1">☆</span>
                        <span class="star" data-value="2">☆</span>
                        <span class="star" data-value="3">☆</span>
                        <span class="star" data-value="4">☆</span>
                        <span class="star" data-value="5">☆</span>
                    </div>
                    <div class="form-group"><label>نوع الخدمة</label><select id="serviceType"><option>collection</option><option>license</option><option>cleanliness</option><option>project</option></select></div>
                    <div class="form-group"><label>تعليقك</label><textarea id="ratingComment" rows="2"></textarea></div>
                    <div class="form-group"><label>المديرية</label><select id="ratingDistrict"></select></div>
                    <button onclick="submitRating()">إرسال التقييم</button>
                </div>
                <div class="cards" id="ratingStats" style="margin-top:20px;"></div>
            </div>

            <!-- التراخيص -->
            <div id="licensesTab" class="tab-pane">
                <div class="card" style="max-width:400px; margin:0 auto;">
                    <h3 style="color:#d4af37;">📜 الاستعلام عن ترخيص</h3>
                    <div class="form-group"><label>رمز المحل</label><input type="text" id="licenseShopId" placeholder="ADN-MN-0001"></div>
                    <button onclick="checkLicense()">استعلام</button>
                    <div id="licenseResult" style="margin-top:20px;"></div>
                </div>
                <div class="card" style="margin-top:20px;">
                    <h3 style="color:#d4af37;">📜 إصدار ترخيص جديد</h3>
                    <form onsubmit="event.preventDefault(); issueLicense();">
                        <div class="form-group"><label>رمز المحل</label><input type="text" id="issueShopId" required></div>
                        <div class="form-group"><label>نوع الترخيص</label><select id="licenseType"><option>commercial</option><option>industrial</option><option>service</option></select></div>
                        <div class="form-group"><label>الرسوم المدفوعة</label><input type="number" id="licenseFee"></div>
                        <button type="submit">إصدار الترخيص</button>
                    </form>
                </div>
            </div>

            <!-- الحملات -->
            <div id="campaignsTab" class="tab-pane">
                <button onclick="loadCampaigns()" class="secondary">🔄 تحديث الحملات</button>
                <div class="table-container" id="campaignsTable"></div>
                <div class="card" style="margin-top:20px;">
                    <h3 style="color:#d4af37;">🚩 إطلاق حملة جديدة</h3>
                    <form onsubmit="event.preventDefault(); createCampaign();">
                        <div class="form-group"><label>اسم الحملة</label><input type="text" id="campaignName" required></div>
                        <div class="form-group"><label>المديرية</label><select id="campaignDistrict"></select></div>
                        <div class="form-group"><label>المبلغ المستهدف</label><input type="number" id="campaignTarget"></div>
                        <div class="form-group"><label>تاريخ الانتهاء</label><input type="date" id="campaignEndDate"></div>
                        <button type="submit">إطلاق الحملة</button>
                    </form>
                </div>
            </div>

            <!-- المشاريع -->
            <div id="projectsTab" class="tab-pane">
                <div class="cards" id="projectsStatsCards"></div>
                <div class="table-container" id="projectsTable"></div>
            </div>

            <!-- التقارير -->
            <div id="reportsTab" class="tab-pane">
                <div class="cards">
                    <div class="card" onclick="exportReport('collections','csv')">📊 تصدير تقرير التحصيلات CSV</div>
                    <div class="card" onclick="exportReport('shops','csv')">🛍️ تصدير تقرير المحلات CSV</div>
                    <div class="card" onclick="exportReport('revenue','csv')">💰 تصدير تقرير الإيرادات CSV</div>
                    <div class="card" onclick="window.open('/api/public/transparency', '_blank')">📢 لوحة الشفافية العامة</div>
                </div>
                <div class="card">
                    <h3 style="color:#d4af37;">📈 توقع الإيرادات (الذكاء الاصطناعي)</h3>
                    <button onclick="loadPredictions()" class="secondary">توقع الإيرادات</button>
                    <div id="predictionsResult" style="margin-top:15px;"></div>
                </div>
                <div class="card">
                    <h3 style="color:#d4af37;">🔍 كشف الاحتيال</h3>
                    <button onclick="loadFraudCases()" class="secondary">عرض حالات الاحتيال</button>
                    <div id="fraudResult" style="margin-top:15px;"></div>
                </div>
            </div>

            <!-- الشفافية -->
            <div id="transparencyTab" class="tab-pane">
                <div class="cards" id="transparencyCards"></div>
                <div class="table-container" id="transparencyTable"></div>
            </div>
        </div>
    </div>

    <div id="toast" class="toast"></div>

    <script>
        let token = null;
        let userRole = null;
        let socket = null;
        let revenueChart = null;
        let performanceChart = null;
        let selectedRating = 0;

        // تهيئة WebSocket
        function initSocket() {
            socket = io();
            socket.on('connect', function() {
                socket.emit('authenticate', { token: token });
            });
            socket.on('new_notification', function(data) {
                showToast(data.title + ': ' + data.message, 'info');
                loadNotifications();
            });
            socket.on('connected', function(data) {
                console.log('Connected:', data);
            });
        }

        // تسجيل الدخول
        async function login() {
            const username = document.getElementById('loginUsername').value;
            const password = document.getElementById('loginPassword').value;
            try {
                const res = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                const data = await res.json();
                if (data.token) {
                    token = data.token;
                    userRole = data.user.role;
                    document.getElementById('userName').innerText = data.user.full_name;
                    document.getElementById('userRole').innerText = data.user.role === 'governor' ? 'محافظ عدن' : (data.user.role === 'mayor' ? 'مأمور' : 'محصل');
                    document.getElementById('loginScreen').style.display = 'none';
                    document.getElementById('mainApp').style.display = 'block';
                    initSocket();
                    loadDashboard();
                    loadDistricts();
                    loadShops();
                    loadComplaints();
                    loadWallet();
                    loadCampaigns();
                    loadProjectsStats();
                    loadDistrictSelects();
                    loadTransparency();
                    startLiveRevenue();
                    loadNotifications();
                    showToast('تم تسجيل الدخول بنجاح', 'success');
                } else { showToast('خطأ في الدخول', 'error'); }
            } catch(e) { showToast('خطأ في الاتصال', 'error'); }
        }

        function logout() { token = null; if(socket) socket.disconnect(); document.getElementById('loginScreen').style.display = 'flex'; document.getElementById('mainApp').style.display = 'none'; }

        function showToast(msg, type) {
            const toast = document.getElementById('toast');
            toast.innerText = msg;
            toast.style.display = 'block';
            toast.style.background = type === 'error' ? '#330000' : '#003300';
            setTimeout(() => toast.style.display = 'none', 3000);
        }

        function showTab(tabName) {
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(tabName + 'Tab').classList.add('active');
            if(event.target) event.target.classList.add('active');
            if(tabName === 'dashboard') loadDashboard();
        }

        // لوحة التحكم
        async function loadDashboard() {
            if(!token) return;
            try {
                const res = await fetch('/api/governor/dashboard', { headers: { 'Authorization': `Bearer ${token}` } });
                const data = await res.json();
                document.getElementById('dashboardCards').innerHTML = `
                    <div class="card"><div class="card-value">${(data.live_stats.total_revenue_today || 0).toLocaleString()}</div><div class="card-title">إيرادات اليوم</div><div class="card-icon">💰</div></div>
                    <div class="card"><div class="card-value">${(data.live_stats.total_month_revenue || 0).toLocaleString()}</div><div class="card-title">إيرادات الشهر</div><div class="card-icon">📊</div></div>
                    <div class="card"><div class="card-value">${data.live_stats.total_shops || 0}</div><div class="card-title">المحلات النشطة</div><div class="card-icon">🛍️</div></div>
                    <div class="card"><div class="card-value">${data.live_stats.active_campaigns || 0}</div><div class="card-title">الحملات النشطة</div><div class="card-icon">🚩</div></div>
                    <div class="card"><div class="card-value">${data.live_stats.pending_complaints || 0}</div><div class="card-title">الشكاوى المعلقة</div><div class="card-icon">📋</div></div>
                    <div class="card"><div class="card-value">${data.live_stats.citizen_satisfaction || 0}/5</div><div class="card-title">رضا المواطنين</div><div class="card-icon">⭐</div></div>
                `;

                let rankingHtml = '<table><th>#</th><th>المديرية</th><th>الإيرادات</th><th>المحلات</th><th>الحملات</th><th>الشكاوى</th><th>درجة الأداء</th></tr>';
                if(data.district_ranking) {
                    data.district_ranking.forEach((d,i) => { rankingHtml += `<tr><td class="${i===0?'rank-1':''}">${i+1}</td><td>${d.name}</td><td>${d.revenue.toLocaleString()}</td><td>${d.shops}</td><td>${d.campaigns}</td><td>${d.complaints}</td><td><span class="badge ${d.performance>80?'badge-success':(d.performance>60?'badge-warning':'badge-danger')}">${d.performance.toFixed(0)}%</span></td></tr>`; });
                }
                document.getElementById('rankingTable').innerHTML = rankingHtml;

                // رسوم بيانية
                const districtNames = data.district_ranking.map(d => d.name);
                const revenues = data.district_ranking.map(d => d.revenue);
                const performances = data.district_ranking.map(d => d.performance);

                if(revenueChart) revenueChart.destroy();
                const revenueCtx = document.getElementById('revenueChart').getContext('2d');
                revenueChart = new Chart(revenueCtx, {
                    type: 'bar',
                    data: { labels: districtNames, datasets: [{ label: 'الإيرادات (ريال)', data: revenues, backgroundColor: '#d4af37' }] },
                    options: { responsive: true, maintainAspectRatio: true }
                });

                if(performanceChart) performanceChart.destroy();
                const perfCtx = document.getElementById('performanceChart').getContext('2d');
                performanceChart = new Chart(perfCtx, {
                    type: 'line',
                    data: { labels: districtNames, datasets: [{ label: 'درجة الأداء (%)', data: performances, borderColor: '#d4af37', fill: false }] },
                    options: { responsive: true, maintainAspectRatio: true }
                });
            } catch(e) { console.error(e); }
        }

        async function loadDistricts() {
            if(!token) return;
            try {
                const res = await fetch('/api/districts', { headers: { 'Authorization': `Bearer ${token}` } });
                const data = await res.json();
                let html = '<table><th>الرمز</th><th>الاسم</th><th>السكان</th><th>الميزانية</th><th>المحلات</th><th>درجة الأداء</th></tr>';
                if(data.districts) {
                    data.districts.forEach(d => { html += `<tr><td>${d.code}</td><td>${d.name}</td><td>${d.population.toLocaleString()}</td><td>${(d.budget || 0).toLocaleString()}</td><td>${d.shops_count}</td><td>${d.performance_score.toFixed(0)}%</td></tr>`; });
                }
                document.getElementById('districtsTable').innerHTML = html;
            } catch(e) {}
        }

        async function loadShops() {
            if(!token) return;
            try {
                const res = await fetch('/api/shops', { headers: { 'Authorization': `Bearer ${token}` } });
                const data = await res.json();
                let html = '<table><th>الرمز</th><th>الاسم</th><th>المالك</th><th>المديرية</th><th>الفئة</th><th>الرسم</th><th>التقييم</th></tr>';
                if(data.shops) {
                    data.shops.forEach(s => { html += `<tr>}<td>${s.id}</td><td>${s.name}</td><td>${s.owner_name || '-'}</td><td>${s.district}</td><td>${s.category}</td><td>${s.monthly_fee.toLocaleString()}</td><td>${s.rating || '-'}</td></tr>`; });
                }
                document.getElementById('shopsTable').innerHTML = html;
            } catch(e) {}
        }

        async function addShop() {
            const name = document.getElementById('shopName').value;
            const owner_name = document.getElementById('ownerName').value;
            const owner_phone = document.getElementById('ownerPhone').value;
            const district_code = document.getElementById('shopDistrict').value;
            const subdistrict_id = document.getElementById('shopSubdistrict').value;
            const category = document.getElementById('shopCategory').value;
            const monthly_fee = document.getElementById('monthlyFee').value;
            const address = document.getElementById('shopAddress').value;
            if(!name) { showToast('يرجى إدخال اسم المحل', 'error'); return; }
            try {
                const res = await fetch('/api/shops', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, owner_name, owner_phone, district_code, subdistrict_id: subdistrict_id ? parseInt(subdistrict_id) : null, category, monthly_fee: parseFloat(monthly_fee) || 0, address })
                });
                const data = await res.json();
                if(res.ok) { showToast(data.message, 'success'); document.getElementById('shopName').value = ''; loadShops(); }
                else { showToast(data.error, 'error'); }
            } catch(e) { showToast('خطأ', 'error'); }
        }

        async function addDistrict() {
            const code = document.getElementById('newDistrictCode').value;
            const name = document.getElementById('newDistrictName').value;
            const name_english = document.getElementById('newDistrictNameEn').value;
            const population = document.getElementById('newDistrictPopulation').value;
            const budget = document.getElementById('newDistrictBudget').value;
            if(!code || !name) { showToast('يرجى إدخال الرمز والاسم', 'error'); return; }
            try {
                const res = await fetch('/api/districts', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code, name, name_english, population: parseInt(population) || 0, budget: parseFloat(budget) || 0 })
                });
                const data = await res.json();
                if(res.ok) { showToast(data.message, 'success'); loadDistricts(); loadDistrictSelects(); }
                else { showToast(data.error, 'error'); }
            } catch(e) { showToast('خطأ', 'error'); }
        }

        async function collectPayment() {
            const shop_id = document.getElementById('collectShopId').value;
            const amount = document.getElementById('collectAmount').value;
            const method = document.getElementById('paymentMethod').value;
            if(!shop_id || !amount) { showToast('يرجى إدخال رمز المحل والمبلغ', 'error'); return; }
            try {
                const res = await fetch('/api/collection/collect', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ shop_id, amount: parseFloat(amount), method })
                });
                const data = await res.json();
                if(res.ok) { showToast(data.message, 'success'); document.getElementById('collectShopId').value = ''; document.getElementById('collectAmount').value = ''; loadDashboard(); }
                else { showToast(data.error, 'error'); }
            } catch(e) { showToast('خطأ', 'error'); }
        }

        async function loadCollections() {
            if(!token) return;
            try {
                const res = await fetch('/api/collections?limit=20', { headers: { 'Authorization': `Bearer ${token}` } });
                if(res.ok) {
                    const data = await res.json();
                    let html = '<table><th>المحل</th><th>المبلغ</th><th>طريقة الدفع</th><th>التاريخ</th></tr>';
                    if(data.collections) {
                        data.collections.forEach(c => { html += `<tr><td>${c.shop_name}</td><td>${c.amount.toLocaleString()}</td><td>${c.method}</td><td>${new Date(c.created_at).toLocaleString()}</td></tr>`; });
                    }
                    document.getElementById('collectionsTable').innerHTML = html;
                }
            } catch(e) {}
        }

        async function loadWallet() {
            if(!token) return;
            try {
                const res = await fetch('/api/wallet/balance', { headers: { 'Authorization': `Bearer ${token}` } });
                const data = await res.json();
                if(data.wallet_number) {
                    document.getElementById('walletCards').innerHTML = `
                        <div class="card"><div class="card-value">${data.wallet_number}</div><div class="card-title">رقم المحفظة</div></div>
                        <div class="card"><div class="card-value">${data.balance.toLocaleString()}</div><div class="card-title">الرصيد الحالي (ريال)</div></div>
                    `;
                } else {
                    document.getElementById('walletCards').innerHTML = `<div class="card"><button onclick="createWallet()" class="secondary">إنشاء محفظة رقمية</button></div>`;
                }
            } catch(e) {}
        }

        async function createWallet() {
            try {
                const res = await fetch('/api/wallet/create', { method: 'POST', headers: { 'Authorization': `Bearer ${token}` } });
                const data = await res.json();
                showToast(data.message, 'success');
                loadWallet();
            } catch(e) {}
        }

        async function depositToWallet() {
            const amount = document.getElementById('depositAmount').value;
            if(!amount || amount <= 0) { showToast('المبلغ غير صحيح', 'error'); return; }
            try {
                const res = await fetch('/api/wallet/deposit', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ amount: parseFloat(amount) })
                });
                const data = await res.json();
                if(res.ok) { showToast(data.message, 'success'); loadWallet(); }
                else { showToast(data.error, 'error'); }
            } catch(e) { showToast('خطأ', 'error'); }
        }

        async function payFromWallet() {
            const shop_id = document.getElementById('payShopId').value;
            const amount = document.getElementById('payAmount').value;
            if(!shop_id || !amount) { showToast('يرجى إدخال رمز المحل والمبلغ', 'error'); return; }
            try {
                const res = await fetch('/api/wallet/pay', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ amount: parseFloat(amount), shop_id })
                });
                const data = await res.json();
                if(res.ok) { showToast(data.message, 'success'); loadWallet(); loadDashboard(); }
                else { showToast(data.error, 'error'); }
            } catch(e) { showToast('خطأ', 'error'); }
        }

        async function submitComplaint() {
            const subject = document.getElementById('complaintSubject').value;
            const description = document.getElementById('complaintDesc').value;
            const type = document.getElementById('complaintType').value;
            const district_code = document.getElementById('complaintDistrict').value;
            const phone = document.getElementById('complaintPhone').value;
            if(!subject || !description) { showToast('يرجى إدخال موضوع ووصف الشكوى', 'error'); return; }
            try {
                const res = await fetch('/api/complaints', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ subject, description, type, district_code, phone })
                });
                const data = await res.json();
                if(res.ok) { showToast(data.message, 'success'); document.getElementById('complaintSubject').value = ''; document.getElementById('complaintDesc').value = ''; }
                else { showToast('حدث خطأ', 'error'); }
            } catch(e) { showToast('خطأ', 'error'); }
        }

        async function loadComplaints() {
            if(!token) return;
            try {
                const res = await fetch('/api/complaints', { headers: { 'Authorization': `Bearer ${token}` } });
                const data = await res.json();
                let html = '<table><th>الموضوع</th><th>النوع</th><th>الحالة</th><th>التاريخ</th></tr>';
                if(data.complaints) {
                    data.complaints.forEach(c => { html += `<tr><td>${c.subject}</td><td>${c.type}</td><td><span class="badge ${c.status==='pending'?'badge-warning':'badge-success'}">${c.status==='pending'?'قيد المعالجة':'تم الحل'}</span></td><td>${new Date(c.created_at).toLocaleDateString()}</td></tr>`; });
                }
                document.getElementById('complaintsTable').innerHTML = html;
            } catch(e) {}
        }

        async function checkLicense() {
            const shop_id = document.getElementById('licenseShopId').value;
            if(!shop_id) { showToast('يرجى إدخال رمز المحل', 'error'); return; }
            try {
                const res = await fetch(`/api/licenses/${shop_id}`);
                const data = await res.json();
                if(res.ok) {
                    document.getElementById('licenseResult').innerHTML = `<div class="alert-green">
                        ✅ الترخيص ساري<br>
                        الرقم: ${data.license_number}<br>
                        ينتهي في: ${new Date(data.expiry_date).toLocaleDateString()}<br>
                        الأيام المتبقية: ${data.days_until_expiry}
                    </div>`;
                } else {
                    document.getElementById('licenseResult').innerHTML = `<div class="alert-orange">❌ ${data.error}</div>`;
                }
            } catch(e) {}
        }

        async function issueLicense() {
            const shop_id = document.getElementById('issueShopId').value;
            const license_type = document.getElementById('licenseType').value;
            const fee = document.getElementById('licenseFee').value;
            if(!shop_id) { showToast('يرجى إدخال رمز المحل', 'error'); return; }
            try {
                const res = await fetch('/api/licenses/issue', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ shop_id, license_type, fee: parseFloat(fee) || 0 })
                });
                const data = await res.json();
                if(res.ok) { showToast(data.message, 'success'); document.getElementById('issueShopId').value = ''; }
                else { showToast(data.error, 'error'); }
            } catch(e) { showToast('خطأ', 'error'); }
        }

        async function loadCampaigns() {
            if(!token) return;
            try {
                const res = await fetch('/api/campaigns', { headers: { 'Authorization': `Bearer ${token}` } });
                const data = await res.json();
                let html = '<table><th>اسم الحملة</th><th>المديرية</th><th>المستهدف</th><th>المحصل</th><th>التقدم</th><th>الحالة</th></tr>';
                if(data.campaigns) {
                    data.campaigns.forEach(c => { html += `<tr>}<td>${c.name}</td>}<td>${c.district}</td>}<td>${c.target_amount.toLocaleString()}</td>}<td>${c.collected_amount.toLocaleString()}</td>}<td><div style="background:#333; border-radius:10px;"><div style="background:#d4af37; width:${c.progress}%; border-radius:10px; padding:2px; text-align:center;">${c.progress}%</div></div></td>}<td><span class="badge ${c.status==='active'?'badge-success':'badge-warning'}">${c.status==='active'?'نشطة':'متعثرة'}</span></td></tr>`; });
                }
                document.getElementById('campaignsTable').innerHTML = html;
            } catch(e) {}
        }

        async function createCampaign() {
            const name = document.getElementById('campaignName').value;
            const district_code = document.getElementById('campaignDistrict').value;
            const target_amount = document.getElementById('campaignTarget').value;
            const end_date = document.getElementById('campaignEndDate').value;
            if(!name) { showToast('يرجى إدخال اسم الحملة', 'error'); return; }
            try {
                const res = await fetch('/api/campaigns', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, district_code, target_amount: parseFloat(target_amount) || 0, end_date })
                });
                const data = await res.json();
                if(res.ok) { showToast(data.message, 'success'); document.getElementById('campaignName').value = ''; loadCampaigns(); }
                else { showToast(data.error, 'error'); }
            } catch(e) { showToast('خطأ', 'error'); }
        }

        async function loadProjectsStats() {
            if(!token) return;
            try {
                const res = await fetch('/api/development/projects', { headers: { 'Authorization': `Bearer ${token}` } });
                const data = await res.json();
                if(data.stats) {
                    document.getElementById('projectsStatsCards').innerHTML = `
                        <div class="card"><div class="card-value">${data.stats.total_projects}</div><div class="card-title">إجمالي المشاريع</div></div>
                        <div class="card"><div class="card-value">${data.stats.completed_projects}</div><div class="card-title">المشاريع المنجزة</div></div>
                        <div class="card"><div class="card-value">${(data.stats.total_budget || 0).toLocaleString()}</div><div class="card-title">الميزانية الإجمالية</div></div>
                        <div class="card"><div class="card-value">${data.stats.roads_projects || 0}</div><div class="card-title">مشاريع الطرق</div></div>
                    `;
                }
                let html = '</table><th>المشروع</th><th>المديرية</th><th>النوع</th><th>الميزانية</th><th>الحالة</th><th>الإنجاز</th></tr>';
                if(data.projects) {
                    data.projects.forEach(p => { html += `<tr><td>${p.project_name}</td><td>${p.district}</td><td>${p.project_type}</td><td>${(p.budget || 0).toLocaleString()}</td>}<td><span class="badge ${p.status==='completed'?'badge-success':'badge-warning'}">${p.status==='completed'?'منجز':'جاري'}</span></td>}<td>${p.completion_percentage || 0}%</td></tr>`; });
                }
                document.getElementById('projectsTable').innerHTML = html;
            } catch(e) {}
        }

        async function loadTransparency() {
            try {
                const res = await fetch('/api/public/transparency');
                const data = await res.json();
                document.getElementById('transparencyCards').innerHTML = `
                    <div class="card"><div class="card-value">${(data.total_revenue_today || 0).toLocaleString()}</div><div class="card-title">إيرادات اليوم</div></div>
                    <div class="card"><div class="card-value">${data.total_shops || 0}</div><div class="card-title">المحلات المسجلة</div></div>
                    <div class="card"><div class="card-value">${data.districts?.length || 0}</div><div class="card-title">المديريات</div></div>
                `;
                let html = '<table><th>المديرية</th><th>الإيرادات</th><th>درجة الأداء</th><th>عدد السكان</th></tr>';
                if(data.districts) {
                    data.districts.forEach(d => { html += `<tr><td>${d.name}</td><td>${d.revenue.toLocaleString()}</td><td>${d.performance.toFixed(0)}%</td><td>${d.population.toLocaleString()}</td></tr>`; });
                }
                document.getElementById('transparencyTable').innerHTML = html;
            } catch(e) {}
        }

        async function loadPredictions() {
            try {
                const res = await fetch('/api/analytics/predict', { headers: { 'Authorization': `Bearer ${token}` } });
                const data = await res.json();
                document.getElementById('predictionsResult').innerHTML = `
                    <div class="alert-green">
                        🤖 توقع الإيرادات الشهر القادم: ${data.predicted_next_month.toLocaleString()} ريال<br>
                        📈 توقع الإيرادات السنة القادمة: ${data.predicted_next_year.toLocaleString()} ريال<br>
                        📊 بناءً على: ${data.based_on}<br>
                        🎯 مستوى الثقة: ${data.confidence === 'high' ? 'مرتفع' : 'متوسط'}
                    </div>
                `;
            } catch(e) {}
        }

        async function loadFraudCases() {
            try {
                const res = await fetch('/api/analytics/fraud', { headers: { 'Authorization': `Bearer ${token}` } });
                const data = await res.json();
                if(data.fraud_cases && data.fraud_cases.length > 0) {
                    let html = '<div class="alert-orange">⚠️ حالات الاحتيال المكتشفة:</div><ul style="margin-top:10px;">';
                    data.fraud_cases.forEach(f => { html += `<li>${f.shop_name}: ${f.description} (ثقة: ${(f.confidence_score*100).toFixed(0)}%)</li>`; });
                    html += '</ul>';
                    document.getElementById('fraudResult').innerHTML = html;
                } else {
                    document.getElementById('fraudResult').innerHTML = '<div class="alert-green">✅ لا توجد حالات احتيال مكتشفة</div>';
                }
            } catch(e) {}
        }

        async function loadDistrictSelects() {
            try {
                const res = await fetch('/api/districts', { headers: { 'Authorization': `Bearer ${token}` } });
                const data = await res.json();
                let options = '<option value="">اختر المديرية</option>';
                let complaintOptions = '<option value="">اختر المديرية</option>';
                let ratingOptions = '<option value="">اختر المديرية</option>';
                let campaignOptions = '<option value="">اختر المديرية</option>';
                if(data.districts) {
                    data.districts.forEach(d => {
                        options += `<option value="${d.code}">${d.name}</option>`;
                        complaintOptions += `<option value="${d.code}">${d.name}</option>`;
                        ratingOptions += `<option value="${d.code}">${d.name}</option>`;
                        campaignOptions += `<option value="${d.code}">${d.name}</option>`;
                    });
                }
                document.getElementById('shopDistrict').innerHTML = options;
                document.getElementById('complaintDistrict').innerHTML = complaintOptions;
                document.getElementById('ratingDistrict').innerHTML = ratingOptions;
                document.getElementById('campaignDistrict').innerHTML = campaignOptions;

                document.getElementById('shopDistrict').onchange = async function() {
                    const distCode = this.value;
                    if(distCode) {
                        const subRes = await fetch(`/api/districts/${distCode}/subdistricts`);
                        const subData = await subRes.json();
                        let subOptions = '<option value="">اختر الحي/المدينة</option>';
                        if(subData.subdistricts) {
                            subData.subdistricts.forEach(s => { subOptions += `<option value="${s.id}">${s.name}</option>`; });
                        }
                        document.getElementById('shopSubdistrict').innerHTML = subOptions;
                    }
                };
            } catch(e) {}
        }

        async function exportReport(type, format) {
            window.open(`/api/reports/export?type=${type}&format=${format}`, '_blank');
        }

        async function startLiveRevenue() {
            const update = async () => {
                try {
                    const res = await fetch('/api/live-revenue');
                    const data = await res.json();
                    document.getElementById('liveRevenue').innerHTML = `💰 الإيرادات اللحظية: ${(data.total_revenue || 0).toLocaleString()} ريال | آخر تحديث: ${new Date(data.last_update).toLocaleTimeString()}`;
                } catch(e) {}
            };
            update();
            setInterval(update, 30000);
        }

        async function loadNotifications() {
            // يمكن إضافة API للإشعارات لاحقاً
        }

        function toggleNotifications() {
            const dropdown = document.getElementById('notificationDropdown');
            dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
        }

        function initRatingStars() {
            const stars = document.querySelectorAll('#ratingStars .star');
            stars.forEach(star => {
                star.onclick = function() {
                    selectedRating = parseInt(this.dataset.value);
                    stars.forEach(s => { s.innerHTML = '☆'; s.classList.remove('active'); });
                    for(let i=0; i<selectedRating; i++) { stars[i].innerHTML = '★'; stars[i].classList.add('active'); }
                };
            });
        }

        async function submitRating() {
            if(selectedRating === 0) { showToast('يرجى اختيار التقييم', 'error'); return; }
            const service_type = document.getElementById('serviceType').value;
            const comment = document.getElementById('ratingComment').value;
            const district_code = document.getElementById('ratingDistrict').value;
            try {
                const res = await fetch('/api/ratings/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ rating: selectedRating, service_type, comment, district_code })
                });
                const data = await res.json();
                if(res.ok) { showToast(data.message, 'success'); selectedRating = 0; document.getElementById('ratingComment').value = ''; }
            } catch(e) {}
        }

        // تهيئة نجوم التقييم
        initRatingStars();
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE_FULL)


# ==================== تحديث الإيرادات اللحظي ====================

live_revenue_cache = {"total": 0, "last_update": None}


def update_live_revenue():
    while True:
        time.sleep(30)
        with app.app_context():
            try:
                today = date.today()
                revenues = RevenueDaily.query.filter_by(date=today).all()
                total = sum(r.total_amount for r in revenues)
                live_revenue_cache["total"] = total
                live_revenue_cache["last_update"] = datetime.now().isoformat()
            except:
                pass


threading.Thread(target=update_live_revenue, daemon=True).start()


# ==================== إنشاء قاعدة البيانات ====================

def init_database():
    # إنشاء الجداول
    db.create_all()

    # التحقق من وجود بيانات
    if User.query.count() > 0:
        print("✅ قاعدة البيانات موجودة مسبقاً")
        return

    print("📦 جاري تهيئة قاعدة البيانات القوية...")

    # إنشاء محافظة عدن
    governorate = Governorate(
        code="ADN",
        name="عدن",
        name_english="Aden",
        capital_city="كريتر",
        population=1000000,
        area_km2=760,
        website="aden.gov.ye",
        email="info@aden.gov.ye",
        phone="967770295876",
        is_active=True
    )
    db.session.add(governorate)
    db.session.commit()

    # إنشاء المستخدمين
    users_data = [
        {"username": "governor", "password": "admin123", "full_name": "محافظ عدن", "email": "governor@aden.gov.ye",
         "phone": "967770295876", "role": "governor", "governorate_code": "ADN"},
        {"username": "mayor_mansoura", "password": "mayor123", "full_name": "أحمد محمد",
         "email": "mayor@mansoura.aden.gov.ye", "phone": "967771234567", "role": "mayor", "district_code": "ADN-MN"},
        {"username": "collector1", "password": "collector123", "full_name": "وسيم الحميدي",
         "email": "collector@aden.gov.ye", "phone": "967773456789", "role": "collector", "district_code": "ADN-MN"},
    ]

    for u in users_data:
        user = User(
            username=u["username"],
            password_hash=bcrypt.generate_password_hash(u["password"]).decode('utf-8'),
            full_name=u["full_name"],
            email=u.get("email"),
            phone=u.get("phone"),
            role=u["role"],
            governorate_code=u.get("governorate_code"),
            district_code=u.get("district_code")
        )
        db.session.add(user)

    db.session.commit()

    # إنشاء المديريات
    districts_data = [
        {"code": "ADN-MN", "name": "مديرية المنصورة", "name_english": "Al-Mansoura", "population": 300000,
         "budget": 50000000},
        {"code": "ADN-KM", "name": "مديرية خور مكسر", "name_english": "Khormaksar", "population": 250000,
         "budget": 40000000},
        {"code": "ADN-SH", "name": "مديرية صيرة", "name_english": "Sira", "population": 80000, "budget": 15000000},
        {"code": "ADN-ML", "name": "مديرية المعلا", "name_english": "Al-Mualla", "population": 50000,
         "budget": 10000000},
        {"code": "ADN-TW", "name": "مديرية التواهي", "name_english": "Tawahi", "population": 45000, "budget": 12000000},
    ]

    for d in districts_data:
        district = District(
            code=d["code"],
            governorate_code="ADN",
            name=d["name"],
            name_english=d["name_english"],
            district_type="district",
            population=d["population"],
            budget=d["budget"],
            performance_score=70,
            is_active=True
        )
        db.session.add(district)

    db.session.commit()

    # أحياء المنصورة
    subdistricts_data = [
        {"district_code": "ADN-MN", "name": "حي الوحدة", "type": "neighborhood", "population": 50000},
        {"district_code": "ADN-MN", "name": "مدينة الشعب", "type": "city", "population": 80000},
        {"district_code": "ADN-MN", "name": "حي 22 مايو", "type": "neighborhood", "population": 40000},
        {"district_code": "ADN-MN", "name": "منطقة البساتين", "type": "neighborhood", "population": 30000},
        {"district_code": "ADN-MN", "name": "منطقة السعادة", "type": "neighborhood", "population": 25000},
        {"district_code": "ADN-MN", "name": "منطقة الروضة", "type": "neighborhood", "population": 35000},
        {"district_code": "ADN-KM", "name": "حي الخساف", "type": "neighborhood", "population": 35000},
        {"district_code": "ADN-KM", "name": "منطقة البريق", "type": "neighborhood", "population": 40000},
        {"district_code": "ADN-KM", "name": "حي الرحاب", "type": "neighborhood", "population": 30000},
        {"district_code": "ADN-SH", "name": "حي صيرة القديمة", "type": "neighborhood", "population": 25000},
    ]

    for sub in subdistricts_data:
        subdistrict = Subdistrict(
            district_code=sub["district_code"],
            name=sub["name"],
            subdistrict_type=sub["type"],
            population=sub["population"]
        )
        db.session.add(subdistrict)

    # ربط المأمور
    mayor = User.query.filter_by(username="mayor_mansoura").first()
    if mayor:
        District.query.filter_by(code="ADN-MN").update({"mayor_id": mayor.id})

    db.session.commit()

    # إنشاء محلات تجارية
    shops_data = [
        {"name": "سوق المنصورة المركزي", "district": "ADN-MN", "category": "أ", "monthly_fee": 50000,
         "owner": "علي أحمد", "phone": "967701234567", "address": "شارع التسعين"},
        {"name": "مجمع عدن مول", "district": "ADN-MN", "category": "أ", "monthly_fee": 100000, "owner": "محمد عبدالله",
         "phone": "967702345678", "address": "جولة كالتكس"},
        {"name": "سوق الخضار المركزي", "district": "ADN-MN", "category": "ب", "monthly_fee": 30000, "owner": "خالد علي",
         "phone": "967703456789", "address": "حي الوحدة"},
        {"name": "مركز البشائر التجاري", "district": "ADN-MN", "category": "ب", "monthly_fee": 40000,
         "owner": "نبيل صالح", "phone": "967704567890", "address": "مدينة الشعب"},
        {"name": "مطعم البحر الأحمر", "district": "ADN-MN", "category": "ج", "monthly_fee": 15000, "owner": "فهد ناصر",
         "phone": "967705678901", "address": "شارع جمال عبدالناصر"},
        {"name": "مطار عدن الدولي", "district": "ADN-KM", "category": "أ", "monthly_fee": 150000,
         "owner": "هيئة الطيران", "phone": "967706789012", "address": "شارع المطار"},
        {"name": "فندق ميركيور", "district": "ADN-KM", "category": "أ", "monthly_fee": 120000, "owner": "مجموعة فنادق",
         "phone": "967707890123", "address": "كورنيش خور مكسر"},
        {"name": "سوق البز", "district": "ADN-KM", "category": "ب", "monthly_fee": 25000, "owner": "عبدالرحمن",
         "phone": "967708901234", "address": "حي الخساف"},
        {"name": "مستوصف الصفا", "district": "ADN-SH", "category": "ب", "monthly_fee": 35000, "owner": "د. أحمد",
         "phone": "967709012345", "address": "شارع صيرة"},
    ]

    for i, s in enumerate(shops_data):
        shop_id = f"{s['district']}-{i + 1:04d}"
        shop = Shop(
            id=shop_id,
            name=s["name"],
            owner_name=s.get("owner"),
            owner_phone=s.get("phone"),
            governorate_code="ADN",
            district_code=s["district"],
            category=s["category"],
            monthly_fee=s["monthly_fee"],
            address=s.get("address"),
            qr_code=generate_qr_string(shop_id),
            ussd_code=generate_ussd_string(i + 1),
            is_active=True,
            rating=4.5,
            rating_count=10
        )
        db.session.add(shop)

    # إنشاء إيرادات تجريبية
    today = date.today()
    collector = User.query.filter_by(username="collector1").first()

    for shop in Shop.query.all():
        amount = random.uniform(10000, 80000)
        collection = Collection(
            shop_id=shop.id,
            collector_id=collector.id if collector else None,
            amount=amount,
            payment_method="qr",
            transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}"
        )
        db.session.add(collection)

        revenue = RevenueDaily(
            governorate_code="ADN",
            district_code=shop.district_code,
            date=today,
            total_amount=amount,
            collection_count=1
        )
        db.session.add(revenue)

    # إنشاء مشاريع تنموية
    projects_data = [
        {"district_code": "ADN-MN", "project_name": "تطوير طريق التسعين", "type": "roads", "budget": 50000000,
         "status": "ongoing", "completion": 60, "description": "توسعة وتأهيل طريق التسعين الرئيسي"},
        {"district_code": "ADN-MN", "project_name": "إنارة شوارع المنصورة", "type": "lighting", "budget": 15000000,
         "status": "completed", "completion": 100, "description": "تركيب أعمدة إنارة LED"},
        {"district_code": "ADN-MN", "project_name": "مشروع الصرف الصحي", "type": "sanitation", "budget": 20000000,
         "status": "ongoing", "completion": 40, "description": "شبكة صرف صحي متكاملة"},
        {"district_code": "ADN-KM", "project_name": "نظافة خور مكسر", "type": "sanitation", "budget": 8000000,
         "status": "ongoing", "completion": 75, "description": "تحسين النظافة العامة"},
        {"district_code": "ADN-KM", "project_name": "تطوير كورنيش خور مكسر", "type": "roads", "budget": 25000000,
         "status": "planned", "completion": 0, "description": "تطوير الواجهة البحرية"},
        {"district_code": "ADN-SH", "project_name": "مستشفى صيرة", "type": "health", "budget": 30000000,
         "status": "ongoing", "completion": 30, "description": "بناء مستشفى جديد"},
        {"district_code": "ADN-ML", "project_name": "سوق مركزي", "type": "market", "budget": 12000000,
         "status": "planned", "completion": 0, "description": "سوق تجاري متكامل"},
    ]

    for p in projects_data:
        project = DevelopmentProject(
            district_code=p["district_code"],
            project_name=p["project_name"],
            project_type=p["type"],
            description=p.get("description"),
            budget=p["budget"],
            status=p["status"],
            completion_percentage=p["completion"]
        )
        db.session.add(project)

    # إنشاء حملة تجريبية
    campaign = Campaign(
        name="حملة تحصيل رسوم المحلات",
        district_code="ADN-MN",
        target_amount=500000,
        collected_amount=125000,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        status='active'
    )
    db.session.add(campaign)

    # تقييمات تجريبية
    ratings_data = [
        {"service_type": "collection", "rating": 5, "district_code": "ADN-MN", "citizen_name": "مواطن 1"},
        {"service_type": "license", "rating": 4, "district_code": "ADN-MN", "citizen_name": "مواطن 2"},
        {"service_type": "cleanliness", "rating": 3, "district_code": "ADN-KM", "citizen_name": "مواطن 3"},
        {"service_type": "collection", "rating": 4, "district_code": "ADN-MN", "citizen_name": "مواطن 4"},
        {"service_type": "project", "rating": 5, "district_code": "ADN-MN", "citizen_name": "مواطن 5"},
    ]

    for r in ratings_data:
        rating = CitizenRating(
            citizen_name=r["citizen_name"],
            service_type=r["service_type"],
            rating=r["rating"],
            district_code=r["district_code"]
        )
        db.session.add(rating)

    # حساب درجات الأداء للمديريات
    for dist in District.query.all():
        calculate_district_score(dist.code)

    db.session.commit()

    print("=" * 60)
    print("✅ تم تهيئة قاعدة البيانات القوية بنجاح!")
    print("=" * 60)
    print("📊 إحصائيات النظام:")
    print(f"   🏛️ محافظة عدن (العاصمة)")
    print(f"   🏙️ {District.query.count()} مديرية")
    print(f"   🏘️ {Subdistrict.query.count()} مدينة/حي")
    print(f"   🛍️ {Shop.query.count()} محل تجاري")
    print(f"   🏗️ {DevelopmentProject.query.count()} مشروع تنموي")
    print(f"   👥 {User.query.count()} مستخدم")
    print("=" * 60)


# ==================== تشغيل التطبيق ====================

if __name__ == '__main__':
    with app.app_context():
        init_database()

    print("=" * 70)
    print("🏛️ نظام إدارة العاصمة عدن - النسخة القوية الكاملة")
    print("=" * 70)
    print("📌 التشغيل على: http://localhost:5000")
    print("=" * 70)
    print("🔐 حسابات تجريبية:")
    print("   👑 محافظ عدن: governor / admin123")
    print("   🏙️ مأمور المنصورة: mayor_mansoura / mayor123")
    print("   👮 محصل: collector1 / collector123")
    print("=" * 70)
    print("✨ الميزات المتاحة:")
    print("   ✅ محفظة رقمية إلكترونية")
    print("   ✅ نظام شكاوى متكامل مع تتبع")
    print("   ✅ تقييم رضا المواطنين")
    print("   ✅ نظام تراخيص الأعمال")
    print("   ✅ إشعارات فورية WebSocket")
    print("   ✅ رسوم بيانية متقدمة")
    print("   ✅ تصدير تقارير CSV")
    print("   ✅ كشف احتيال بالذكاء الاصطناعي")
    print("   ✅ نظام جرد المخزون")
    print("   ✅ إدارة الحملات الميدانية")
    print("   ✅ مشاريع التنمية")
    print("   ✅ 5 مديريات متكاملة")
    print("   ✅ 10 أحياء ومدن تابعة")
    print("   ✅ 9 محلات تجارية")
    print("=" * 70)

    socketio.run(app, debug=True, host='0.0.0.0', port=5000)