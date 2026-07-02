"""
Database layer — PostgreSQL via Docker container (ainoc-db).
Stores alerts, settings, and ping history persistently.

Connection: postgres:password@localhost:5432/ainoc
Container:  docker start ainoc-db
"""

import json
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, String, Float, Boolean,
    Integer, DateTime, Text
)
from sqlalchemy.orm import declarative_base, sessionmaker

# Your Docker container credentials
DATABASE_URL = "postgresql+psycopg2://postgres:password@localhost:5432/ainoc"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

 
# ----------------------------- Table Models ----------------------
class AlertRecord(Base):
    """Persistent alert history — survives server restarts."""
    __tablename__ = "alerts"

    id           = Column(String(8),   primary_key=True)
    device_id    = Column(String(64),  nullable=False)
    device_name  = Column(String(128), nullable=False)
    severity     = Column(String(16),  nullable=False)
    message      = Column(Text,        nullable=False)
    created_at   = Column(DateTime,    default=lambda: datetime.now(timezone.utc))
    acknowledged = Column(Boolean,     default=False)


class SettingsRecord(Base):
    """Key-value settings — persists across restarts."""
    __tablename__ = "settings"

    key   = Column(String(64), primary_key=True)
    value = Column(Text,       nullable=False)


class PingRecord(Base):
    """Ping history — used for uptime percentage calculation."""
    __tablename__ = "ping_history"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    ip          = Column(String(64),  nullable=False, index=True)
    device_name = Column(String(128), default="")
    alive       = Column(Boolean,     nullable=False)
    avg_rtt     = Column(Float,       nullable=True)
    packet_loss = Column(Float,       nullable=True)
    checked_at  = Column(DateTime,    default=lambda: datetime.now(timezone.utc))


# ----------------------------- Init ------------------------------
def init_db() -> None:
    """Create all tables if they don't exist. Safe to call multiple times."""
    try:
        Base.metadata.create_all(bind=engine)
        print("[db] PostgreSQL tables ready (ainoc-db container).")
    except Exception as e:
        print(f"[db] WARNING: Could not connect to PostgreSQL: {e}")
        print("[db] Run: docker start ainoc-db")


# ----------------------------- Alert helpers ---------------------
def save_alert(alert_data: dict) -> None:
    db = SessionLocal()
    try:
        record = AlertRecord(
            id=alert_data["id"],
            device_id=alert_data["device_id"],
            device_name=alert_data["device_name"],
            severity=alert_data["severity"],
            message=alert_data["message"],
            acknowledged=alert_data.get("acknowledged", False),
        )
        db.merge(record)
        db.commit()
    except Exception as e:
        print(f"[db] save_alert error: {e}")
        db.rollback()
    finally:
        db.close()


def get_alerts(limit: int = 100) -> list:
    db = SessionLocal()
    try:
        records = (
            db.query(AlertRecord)
            .order_by(AlertRecord.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "device_id": r.device_id,
                "device_name": r.device_name,
                "severity": r.severity,
                "message": r.message,
                "created_at": r.created_at.isoformat(),
                "acknowledged": r.acknowledged,
            }
            for r in records
        ]
    except Exception as e:
        print(f"[db] get_alerts error: {e}")
        return []
    finally:
        db.close()


# ----------------------------- Settings helpers ------------------
def save_setting(key: str, value: str) -> None:
    db = SessionLocal()
    try:
        record = SettingsRecord(key=key, value=value)
        db.merge(record)
        db.commit()
    except Exception as e:
        print(f"[db] save_setting error: {e}")
        db.rollback()
    finally:
        db.close()


def get_all_settings() -> dict:
    db = SessionLocal()
    try:
        records = db.query(SettingsRecord).all()
        return {r.key: r.value for r in records}
    except Exception as e:
        print(f"[db] get_all_settings error: {e}")
        return {}
    finally:
        db.close()


# ----------------------------- Ping helpers ----------------------
def save_ping(ip: str, device_name: str, alive: bool,
              avg_rtt: float = None, packet_loss: float = None) -> None:
    db = SessionLocal()
    try:
        record = PingRecord(
            ip=ip, device_name=device_name,
            alive=alive, avg_rtt=avg_rtt, packet_loss=packet_loss,
        )
        db.add(record)
        db.commit()
    except Exception as e:
        print(f"[db] save_ping error: {e}")
        db.rollback()
    finally:
        db.close()


def get_ping_history(ip: str, limit: int = 50) -> list:
    db = SessionLocal()
    try:
        records = (
            db.query(PingRecord)
            .filter(PingRecord.ip == ip)
            .order_by(PingRecord.checked_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "ip": r.ip,
                "device_name": r.device_name,
                "alive": r.alive,
                "avg_rtt": r.avg_rtt,
                "packet_loss": r.packet_loss,
                "checked_at": r.checked_at.isoformat(),
            }
            for r in records
        ]
    except Exception as e:
        print(f"[db] get_ping_history error: {e}")
        return []
    finally:
        db.close()


def get_uptime_percentage(ip: str, last_n: int = 100) -> float:
    """Calculate uptime % from the last N ping checks."""
    db = SessionLocal()
    try:
        records = (
            db.query(PingRecord)
            .filter(PingRecord.ip == ip)
            .order_by(PingRecord.checked_at.desc())
            .limit(last_n)
            .all()
        )
        if not records:
            return 100.0
        alive_count = sum(1 for r in records if r.alive)
        return round((alive_count / len(records)) * 100, 1)
    except Exception as e:
        print(f"[db] get_uptime error: {e}")
        return 100.0
    finally:
        db.close()