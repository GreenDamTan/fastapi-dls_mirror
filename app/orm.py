import datetime

from sqlalchemy import Column, VARCHAR, CHAR, ForeignKey, DATETIME, UniqueConstraint, update, and_, delete, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import Engine
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class Origin(Base):
    __tablename__ = "origin"

    origin_ref = Column(CHAR(length=36), primary_key=True, unique=True, index=True)  # uuid4

    hostname = Column(VARCHAR(length=256), nullable=True)
    guest_driver_version = Column(VARCHAR(length=10), nullable=True)
    os_platform = Column(VARCHAR(length=256), nullable=True)
    os_version = Column(VARCHAR(length=256), nullable=True)

    def __repr__(self):
        return f'Origin(origin_ref={self.origin_ref}, hostname={self.hostname})'

    @staticmethod
    def create_statement(engine: Engine):
        from sqlalchemy.schema import CreateTable
        return CreateTable(Origin.__table__).compile(engine)

    @staticmethod
    def create_or_update(engine: Engine, origin: "Origin"):
        session = sessionmaker(autocommit=True, autoflush=True, bind=engine)()
        entity = session.query(Origin).filter(Origin.origin_ref == origin.origin_ref).first()
        print(entity)
        if entity is None:
            session.add(origin)
        else:
            values = dict(
                hostname=origin.hostname,
                guest_driver_version=origin.guest_driver_version,
                os_platform=origin.os_platform,
                os_version=origin.os_version,
            )
            session.execute(update(Origin).where(Origin.origin_ref == origin.origin_ref).values(**values))
        session.flush()
        session.close()


class Lease(Base):
    __tablename__ = "lease"

    origin_ref = Column(CHAR(length=36), ForeignKey(Origin.origin_ref), primary_key=True, nullable=False, index=True)  # uuid4
    lease_ref = Column(CHAR(length=36), primary_key=True, nullable=False, index=True)  # uuid4

    lease_created = Column(DATETIME(), nullable=False)
    lease_expires = Column(DATETIME(), nullable=False)
    lease_updated = Column(DATETIME(), nullable=False)

    def __repr__(self):
        return f'Lease(origin_ref={self.origin_ref}, lease_ref={self.lease_ref}, expires={self.lease_expires})'

    @staticmethod
    def create_statement(engine: Engine):
        from sqlalchemy.schema import CreateTable
        return CreateTable(Lease.__table__).compile(engine)

    @staticmethod
    def create_or_update(engine: Engine, lease: "Lease"):
        session = sessionmaker(autocommit=True, autoflush=True, bind=engine)()
        entity = session.query(Lease).filter(and_(Lease.origin_ref == lease.origin_ref, Lease.lease_ref == lease.lease_ref)).first()
        if entity is None:
            if lease.lease_updated is None:
                lease.lease_updated = lease.lease_created
            session.add(lease)
        else:
            values = dict(lease_expires=lease.lease_expires, lease_updated=lease.lease_updated)
            session.execute(update(Lease).where(and_(Lease.origin_ref == lease.origin_ref, Lease.lease_ref == lease.lease_ref)).values(**values))
        session.flush()
        session.close()

    @staticmethod
    def find_by_origin_ref(engine: Engine, origin_ref: str) -> ["Lease"]:
        session = sessionmaker(autocommit=True, autoflush=True, bind=engine)()
        entities = session.query(Lease).filter(Lease.origin_ref == origin_ref).all()
        session.close()
        return entities

    @staticmethod
    def find_by_origin_ref_and_lease_ref(engine: Engine, origin_ref: str, lease_ref: str) -> "Lease":
        session = sessionmaker(autocommit=True, autoflush=True, bind=engine)()
        entity = session.query(Lease).filter(and_(Lease.origin_ref == origin_ref, Lease.lease_ref == lease_ref)).first()
        session.close()
        return entity

    @staticmethod
    def renew(engine: Engine, lease: "Lease", lease_expires: datetime.datetime, lease_updated: datetime.datetime):
        session = sessionmaker(autocommit=True, autoflush=True, bind=engine)()
        values = dict(lease_expires=lease.lease_expires, lease_updated=lease.lease_updated)
        session.execute(update(Lease).where(and_(Lease.origin_ref == lease.origin_ref, Lease.lease_ref == lease.lease_ref)).values(**values))
        session.close()

    @staticmethod
    def cleanup(engine: Engine, origin_ref: str) -> int:
        session = sessionmaker(autocommit=True, autoflush=True, bind=engine)()
        deletions = session.query(Lease).filter(Lease.origin_ref == origin_ref).delete()
        session.close()
        return deletions


def init(engine: Engine):
    tables = [Origin, Lease]
    db = inspect(engine)
    session = sessionmaker(bind=engine)()
    for table in tables:
        if not db.dialect.has_table(engine.connect(), table.__tablename__):
            session.execute(str(table.create_statement(engine)))
    session.close()
