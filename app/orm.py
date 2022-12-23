import datetime

from sqlalchemy import Column, VARCHAR, CHAR, ForeignKey, DATETIME, UniqueConstraint, update, and_, delete
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import Engine
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class Origin(Base):
    __tablename__ = "origin"

    """
    CREATE TABLE origin (
        id INTEGER NOT NULL, 
        origin_ref TEXT, 
        hostname TEXT, 
        guest_driver_version TEXT, 
        os_platform TEXT, 
        os_version TEXT, 
        PRIMARY KEY (id)
    );
    CREATE INDEX ix_origin_0548dd22f20de1bb ON origin (origin_ref);
    """

    """
    1|B210CF72-FEC7-4440-9499-1156D1ACD13A|ubuntu-grid-server|525.60.13|Ubuntu 20.04|20.04.5 LTS (Focal Fossa)
    2|230b0000-a356-4000-8a2b-0000564c0000|PC-WORKSTATION|527.41|Windows 10 Pro|10.0.19045
    3|908B202D-CC43-420F-A2EF-FC092AAE8D38|docker-cuda-1|525.60.13|Debian GNU/Linux 10 (buster) 10|10 (buster)
    4|41720000-FA43-4000-9472-0000E8660000|PC-Windows|527.41|Windows 10 Pro|10.0.19045
    5|723EA079-7B0C-4E25-A8D4-DD3E89F9D177|docker-cuda-2|525.60.13|Debian GNU/Linux 10 (buster) 10|10 (buster)
    """

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
            session.execute(update(Origin).where(Origin.origin_ref == origin.origin_ref).values(values))
        session.flush()
        session.close()


class Lease(Base):
    __tablename__ = "lease"

    """
    CREATE TABLE lease (
        id INTEGER NOT NULL, 
        origin_ref TEXT, 
        lease_ref TEXT, 
        lease_created DATETIME, 
        lease_expires DATETIME, lease_last_update DATETIME, 
        PRIMARY KEY (id)
    );
    CREATE INDEX ix_lease_11c7d13bfb17f70d ON lease (origin_ref, lease_ref);
    """

    """
    1|B210CF72-FEC7-4440-9499-1156D1ACD13A|9c4536f9-a216-44c7-a1d3-388a15ee80be|2022-12-20 17:29:07.906668|2022-12-22 04:45:58.138211|2022-12-21 04:45:58.138211
    2|230b0000-a356-4000-8a2b-0000564c0000|1d95e160-058d-4052-b49f-b85306b4c345|2022-12-20 17:30:25.388389|2022-12-23 06:07:29.913027|2022-12-22 06:07:29.913027
    3|908B202D-CC43-420F-A2EF-FC092AAE8D38|9e1bca05-e247-4847-9de6-8b9a210b353e|2022-12-20 17:31:40.158003|2022-12-23 09:28:57.379008|2022-12-22 09:28:57.379008
    4|41720000-FA43-4000-9472-0000E8660000|f2ece7fa-d0c6-4af4-901c-6d3b2c3ecf88|2022-12-20 21:03:33.403711|2022-12-23 08:44:39.998754|2022-12-22 08:44:39.998754
    5|723EA079-7B0C-4E25-A8D4-DD3E89F9D177|5455f59b-dd70-45c1-82fa-3fd5fae6c037|2022-12-21 06:05:35.085572|2022-12-23 04:53:41.385178|2022-12-22 04:53:41.385178
    """

    origin_ref = Column(CHAR(length=36), ForeignKey(Origin.origin_ref), primary_key=True, nullable=False, index=True)
    lease_ref = Column(CHAR(length=36), primary_key=True, nullable=False, index=True)
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
            session.add(lease)
        else:
            values = dict(lease_expires=lease.lease_expires, lease_updated=lease.lease_updated)
            session.execute(update(Lease).where(and_(Lease.origin_ref == lease.origin_ref, Lease.lease_ref == lease.lease_ref)).values(values))
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
        session.execute(update(Lease).where(and_(Lease.origin_ref == lease.origin_ref, Lease.lease_ref == lease.lease_ref)).values(values))
        session.close()

    @staticmethod
    def cleanup(engine: Engine, origin_ref: str) -> int:
        session = sessionmaker(autocommit=True, autoflush=True, bind=engine)()
        deletions = session.query(Lease).delete(Lease.origin_ref == origin_ref)
        session.close()
        return deletions
