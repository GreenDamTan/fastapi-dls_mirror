from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from sqlalchemy import Column, VARCHAR, CHAR, ForeignKey, DATETIME, update, and_, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()


class Origin(Base):
    __tablename__ = "origin"

    origin_ref = Column(CHAR(length=36), primary_key=True, unique=True, index=True)  # uuid4

    # service_instance_xid = Column(CHAR(length=36), nullable=False, index=True)  # uuid4 # not necessary, we only support one service_instance_xid ('INSTANCE_REF')
    hostname = Column(VARCHAR(length=256), nullable=True)
    guest_driver_version = Column(VARCHAR(length=10), nullable=True)
    os_platform = Column(VARCHAR(length=256), nullable=True)
    os_version = Column(VARCHAR(length=256), nullable=True)

    def __repr__(self):
        return f'Origin(origin_ref={self.origin_ref}, hostname={self.hostname})'

    def serialize(self) -> dict:
        return {
            'origin_ref': self.origin_ref,
            # 'service_instance_xid': self.service_instance_xid,
            'hostname': self.hostname,
            'guest_driver_version': self.guest_driver_version,
            'os_platform': self.os_platform,
            'os_version': self.os_version,
        }

    @staticmethod
    def create_statement(engine: Engine):
        from sqlalchemy.schema import CreateTable
        return CreateTable(Origin.__table__).compile(engine)

    @staticmethod
    def create_or_update(engine: Engine, origin: "Origin"):
        session = sessionmaker(bind=engine)()
        entity = session.query(Origin).filter(Origin.origin_ref == origin.origin_ref).first()
        if entity is None:
            session.add(origin)
        else:
            x = dict(
                hostname=origin.hostname,
                guest_driver_version=origin.guest_driver_version,
                os_platform=origin.os_platform,
                os_version=origin.os_version
            )
            session.execute(update(Origin).where(Origin.origin_ref == origin.origin_ref).values(**x))
        session.commit()
        session.flush()
        session.close()

    @staticmethod
    def delete(engine: Engine, origin_refs: [str] = None) -> int:
        session = sessionmaker(bind=engine)()
        if origin_refs is None:
            deletions = session.query(Origin).delete()
        else:
            deletions = session.query(Origin).filter(Origin.origin_ref in origin_refs).delete()
        session.commit()
        session.close()
        return deletions


class Lease(Base):
    __tablename__ = "lease"

    lease_ref = Column(CHAR(length=36), primary_key=True, nullable=False, index=True)  # uuid4

    origin_ref = Column(CHAR(length=36), ForeignKey(Origin.origin_ref, ondelete='CASCADE'), nullable=False, index=True)  # uuid4
    # scope_ref = Column(CHAR(length=36), nullable=False, index=True)  # uuid4 # not necessary, we only support one scope_ref ('ALLOTMENT_REF')
    lease_created = Column(DATETIME(), nullable=False)
    lease_expires = Column(DATETIME(), nullable=False)
    lease_updated = Column(DATETIME(), nullable=False)

    def __repr__(self):
        return f'Lease(origin_ref={self.origin_ref}, lease_ref={self.lease_ref}, expires={self.lease_expires})'

    def serialize(self, renewal_period: float, renewal_delta: timedelta) -> dict:
        lease_renewal = int(Lease.calculate_renewal(renewal_period, renewal_delta).total_seconds())
        lease_renewal = self.lease_updated + relativedelta(seconds=lease_renewal)

        return {
            'lease_ref': self.lease_ref,
            'origin_ref': self.origin_ref,
            # 'scope_ref': self.scope_ref,
            'lease_created': self.lease_created.isoformat(),
            'lease_expires': self.lease_expires.isoformat(),
            'lease_updated': self.lease_updated.isoformat(),
            'lease_renewal': lease_renewal.isoformat(),
        }

    @staticmethod
    def create_statement(engine: Engine):
        from sqlalchemy.schema import CreateTable
        return CreateTable(Lease.__table__).compile(engine)

    @staticmethod
    def create_or_update(engine: Engine, lease: "Lease"):
        session = sessionmaker(bind=engine)()
        entity = session.query(Lease).filter(Lease.lease_ref == lease.lease_ref).first()
        if entity is None:
            if lease.lease_updated is None:
                lease.lease_updated = lease.lease_created
            session.add(lease)
        else:
            x = dict(origin_ref=lease.origin_ref, lease_expires=lease.lease_expires, lease_updated=lease.lease_updated)
            session.execute(update(Lease).where(Lease.lease_ref == lease.lease_ref).values(**x))
        session.commit()
        session.flush()
        session.close()

    @staticmethod
    def find_by_origin_ref(engine: Engine, origin_ref: str) -> ["Lease"]:
        session = sessionmaker(bind=engine)()
        entities = session.query(Lease).filter(Lease.origin_ref == origin_ref).all()
        session.close()
        return entities

    @staticmethod
    def find_by_lease_ref(engine: Engine, lease_ref: str) -> "Lease":
        session = sessionmaker(bind=engine)()
        entity = session.query(Lease).filter(Lease.lease_ref == lease_ref).first()
        session.close()
        return entity

    @staticmethod
    def find_by_origin_ref_and_lease_ref(engine: Engine, origin_ref: str, lease_ref: str) -> "Lease":
        session = sessionmaker(bind=engine)()
        entity = session.query(Lease).filter(and_(Lease.origin_ref == origin_ref, Lease.lease_ref == lease_ref)).first()
        session.close()
        return entity

    @staticmethod
    def renew(engine: Engine, lease: "Lease", lease_expires: datetime, lease_updated: datetime):
        session = sessionmaker(bind=engine)()
        x = dict(lease_expires=lease_expires, lease_updated=lease_updated)
        session.execute(update(Lease).where(and_(Lease.origin_ref == lease.origin_ref, Lease.lease_ref == lease.lease_ref)).values(**x))
        session.commit()
        session.close()

    @staticmethod
    def cleanup(engine: Engine, origin_ref: str) -> int:
        session = sessionmaker(bind=engine)()
        deletions = session.query(Lease).filter(Lease.origin_ref == origin_ref).delete()
        session.commit()
        session.close()
        return deletions

    @staticmethod
    def delete(engine: Engine, lease_ref: str) -> int:
        session = sessionmaker(bind=engine)()
        deletions = session.query(Lease).filter(Lease.lease_ref == lease_ref).delete()
        session.commit()
        session.close()
        return deletions

    @staticmethod
    def delete_expired(engine: Engine) -> int:
        session = sessionmaker(bind=engine)()
        deletions = session.query(Lease).filter(Lease.lease_expires <= datetime.utcnow()).delete()
        session.commit()
        session.close()
        return deletions

    @staticmethod
    def calculate_renewal(renewal_period: float, delta: timedelta) -> timedelta:
        """
        import datetime
        LEASE_RENEWAL_PERIOD=0.2  # 20%
        delta = datetime.timedelta(days=1)
        renew = delta.total_seconds() * LEASE_RENEWAL_PERIOD
        renew = datetime.timedelta(seconds=renew)
        expires = delta - renew  # 19.2

        import datetime
        LEASE_RENEWAL_PERIOD=0.15  # 15%
        delta = datetime.timedelta(days=90)
        renew = delta.total_seconds() * LEASE_RENEWAL_PERIOD
        renew = datetime.timedelta(seconds=renew)
        expires = delta - renew  # 76 days, 12:00:00 hours

        """
        renew = delta.total_seconds() * renewal_period
        renew = timedelta(seconds=renew)
        return renew


def init(engine: Engine):
    tables = [Origin, Lease]
    db = inspect(engine)
    session = sessionmaker(bind=engine)()
    for table in tables:
        if not db.dialect.has_table(engine.connect(), table.__tablename__):
            session.execute(text(str(table.create_statement(engine))))
            session.commit()
    session.close()


def migrate(engine: Engine):
    db = inspect(engine)

    def upgrade_1_0_to_1_1():
        x = db.dialect.get_columns(engine.connect(), Lease.__tablename__)
        x = next(_ for _ in x if _['name'] == 'origin_ref')
        if x['primary_key'] > 0:
            print('Found old database schema with "origin_ref" as primary-key in "lease" table. Dropping table!')
            print('  Your leases are recreated on next renewal!')
            print('  If an error message appears on the client, you can ignore it.')
            Lease.__table__.drop(bind=engine)
            init(engine)

    # def upgrade_1_2_to_1_3():
    #    x = db.dialect.get_columns(engine.connect(), Lease.__tablename__)
    #    x = next((_ for _ in x if _['name'] == 'scope_ref'), None)
    #    if x is None:
    #        Lease.scope_ref.compile()
    #        column_name = Lease.scope_ref.name
    #        column_type = Lease.scope_ref.type.compile(engine.dialect)
    #        engine.execute(f'ALTER TABLE "{Lease.__tablename__}" ADD COLUMN "{column_name}" {column_type}')

    upgrade_1_0_to_1_1()
    # upgrade_1_2_to_1_3()
