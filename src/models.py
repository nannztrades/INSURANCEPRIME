# src/models.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Numeric, Boolean, Date, DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Upload(Base):
    __tablename__ = 'uploads'
    UploadID = Column(Integer, primary_key=True, autoincrement=True)
    agent_code = Column(String(50))
    AgentName = Column(String(255))
    doc_type = Column(String(20))  # STATEMENT, SCHEDULE, TERMINATED
    FileName = Column(String(500))
    UploadTimestamp = Column(DateTime, default=datetime.now)
    month_year = Column(String(20))
    is_active = Column(Boolean, default=True)

class Statement(Base):
    __tablename__ = 'statement'
    statement_id = Column(Integer, primary_key=True, autoincrement=True)
    upload_id = Column(Integer)
    agent_code = Column(String(50))
    policy_no = Column(String(100))
    holder = Column(String(255))
    policy_type = Column(String(100))
    pay_date = Column(Date)
    receipt_no = Column(String(100))
    premium = Column(DECIMAL(15, 2))
    com_rate = Column(DECIMAL(5, 2))
    com_amt = Column(DECIMAL(15, 2))
    inception = Column(Date)
    MONTH_YEAR = Column(String(20))
    AGENT_LICENSE_NUMBER = Column(String(100))

class Schedule(Base):
    __tablename__ = 'schedule'
    schedule_id = Column(Integer, primary_key=True, autoincrement=True)
    upload_id = Column(Integer)
    agent_code = Column(String(50))
    agent_name = Column(String(255))
    commission_batch_code = Column(String(100))
    total_premiums = Column(DECIMAL(15, 2))
    income = Column(DECIMAL(15, 2))
    total_deductions = Column(DECIMAL(15, 2))
    net_commission = Column(DECIMAL(15, 2))
    month_year = Column(String(20))

class Terminated(Base):
    __tablename__ = 'terminated'
    terminated_id = Column(Integer, primary_key=True, autoincrement=True)
    upload_id = Column(Integer)
    agent_code = Column(String(50))
    policy_no = Column(String(100))
    holder = Column(String(255))
    surname = Column(String(255))
    other_name = Column(String(255))
    receipt_no = Column(String(100))
    paydate = Column(Date)
    premium = Column(DECIMAL(15, 2))
    com_rate = Column(DECIMAL(5, 2))
    com_amt = Column(DECIMAL(15, 2))
    policy_type = Column(String(100))
    inception = Column(Date)
    status = Column(String(50))
    agent_name = Column(String(255))
    reason = Column(Text)
    month_year = Column(String(20))
    AGENT_LICENSE_NUMBER = Column(String(100))
    termination_date = Column(Date)

class Agent(Base):
    __tablename__ = 'agents'
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_code = Column(String(50), unique=True, nullable=False)
    agent_name = Column(String(255))
    license_number = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    agent_code = Column(String(50))
    role = Column(String(20), default='agent')  # agent, admin, superuser
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)