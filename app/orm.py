import logging
from datetime import datetime, timedelta, timezone, UTC
from os import getenv as env
from os.path import join, dirname, isfile

from dateutil.relativedelta import relativedelta
from jose import jwk
from jose.constants import ALGORITHMS
from sqlalchemy import Column, VARCHAR, CHAR, ForeignKey, DATETIME, update, and_, inspect, text, BLOB, INT, FLOAT
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session, relationship
from sqlalchemy.schema import CreateTable

from util import NV, PrivateKey, PublicKey

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

Base = declarative_base()


class Site(Base):
    __tablename__ = "site"

    INITIAL_SITE_KEY_XID = '10000000-0000-0000-0000-000000000000'
    INITIAL_SITE_NAME = 'default-site'

    site_key = Column(CHAR(length=36), primary_key=True, unique=True, index=True)  # uuid4, SITE_KEY_XID
    name = Column(VARCHAR(length=256), nullable=False)

    def __str__(self):
        return f'SITE_KEY_XID: {self.site_key}'

    @staticmethod
    def create_statement(engine: Engine):
        return CreateTable(Site.__table__).compile(engine)

    @staticmethod
    def get_default_site(engine: Engine) -> "Site":
        session = sessionmaker(bind=engine)()
        entity = session.query(Site).filter(Site.site_key == Site.INITIAL_SITE_KEY_XID).first()
        session.close()
        return entity


class Instance(Base):
    __tablename__ = "instance"

    DEFAULT_INSTANCE_REF = '10000000-0000-0000-0000-000000000001'
    DEFAULT_TOKEN_EXPIRE_DELTA = 86_400  # 1 day
    DEFAULT_LEASE_EXPIRE_DELTA = 7_776_000  # 90 days
    DEFAULT_LEASE_RENEWAL_PERIOD = 0.15
    DEFAULT_CLIENT_TOKEN_EXPIRE_DELTA = 378_432_000  # 12 years
    # 1 day = 86400 (min. in production setup, max 90 days), 1 hour = 3600

    instance_ref = Column(CHAR(length=36), primary_key=True, unique=True, index=True)  # uuid4, INSTANCE_REF
    site_key = Column(CHAR(length=36), ForeignKey(Site.site_key, ondelete='CASCADE'), nullable=False, index=True)  # uuid4
    private_key = Column(BLOB(length=2048), nullable=False)
    public_key = Column(BLOB(length=512), nullable=False)
    token_expire_delta = Column(INT(), nullable=False, default=DEFAULT_TOKEN_EXPIRE_DELTA, comment='in seconds')
    lease_expire_delta = Column(INT(), nullable=False, default=DEFAULT_LEASE_EXPIRE_DELTA, comment='in seconds')
    lease_renewal_period = Column(FLOAT(precision=2), nullable=False, default=DEFAULT_LEASE_RENEWAL_PERIOD)
    client_token_expire_delta = Column(INT(), nullable=False, default=DEFAULT_CLIENT_TOKEN_EXPIRE_DELTA, comment='in seconds')

    __origin = relationship(Site, foreign_keys=[site_key])

    def __str__(self):
        return f'INSTANCE_REF: {self.instance_ref} (SITE_KEY_XID: {self.site_key})'

    @staticmethod
    def create_statement(engine: Engine):
        return CreateTable(Instance.__table__).compile(engine)

    @staticmethod
    def create_or_update(engine: Engine, instance: "Instance"):
        session = sessionmaker(bind=engine)()
        entity = session.query(Instance).filter(Instance.instance_ref == instance.instance_ref).first()
        if entity is None:
            session.add(instance)
        else:
            x = dict(
                site_key=instance.site_key,
                private_key=instance.private_key,
                public_key=instance.public_key,
                token_expire_delta=instance.token_expire_delta,
                lease_expire_delta=instance.lease_expire_delta,
                lease_renewal_period=instance.lease_renewal_period,
                client_token_expire_delta=instance.client_token_expire_delta,
            )
            session.execute(update(Instance).where(Instance.instance_ref == instance.instance_ref).values(**x))
        session.commit()
        session.flush()
        session.close()

    # todo: validate on startup that "lease_expire_delta" is between 1 day and 90 days

    @staticmethod
    def get_default_instance(engine: Engine) -> "Instance":
        session = sessionmaker(bind=engine)()
        site = Site.get_default_site(engine)
        entity = session.query(Instance).filter(Instance.site_key == site.site_key).first()
        session.close()
        return entity

    def get_token_expire_delta(self) -> "dateutil.relativedelta.relativedelta":
        return relativedelta(seconds=self.token_expire_delta)

    def get_lease_expire_delta(self) -> "dateutil.relativedelta.relativedelta":
        return relativedelta(seconds=self.lease_expire_delta)

    def get_lease_renewal_delta(self) -> "datetime.timedelta":
        return timedelta(seconds=self.lease_expire_delta)

    def get_client_token_expire_delta(self) -> "dateutil.relativedelta.relativedelta":
        return relativedelta(seconds=self.client_token_expire_delta)

    def __get_private_key(self) -> "PrivateKey":
        return PrivateKey(self.private_key)

    def get_public_key(self) -> "PublicKey":
        return PublicKey(self.public_key)

    def get_jwt_encode_key(self) -> "jose.jkw":
        return jwk.construct(self.__get_private_key().pem().decode('utf-8'), algorithm=ALGORITHMS.RS256)

    def get_jwt_decode_key(self) -> "jose.jwt":
        return jwk.construct(self.get_public_key().pem().decode('utf-8'), algorithm=ALGORITHMS.RS256)

    def get_private_key_str(self, encoding: str = 'utf-8') -> str:
        return self.private_key.decode(encoding)

    def get_public_key_str(self, encoding: str = 'utf-8') -> str:
        return self.private_key.decode(encoding)


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
        _ = NV().find(self.guest_driver_version)

        return {
            'origin_ref': self.origin_ref,
            # 'service_instance_xid': self.service_instance_xid,
            'hostname': self.hostname,
            'guest_driver_version': self.guest_driver_version,
            'os_platform': self.os_platform,
            'os_version': self.os_version,
            '$driver': _ if _ is not None else None,
        }

    @staticmethod
    def create_statement(engine: Engine):
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
            deletions = session.query(Origin).filter(Origin.origin_ref.in_(origin_refs)).delete()
        session.commit()
        session.close()
        return deletions

    @staticmethod
    def delete_expired(engine: Engine) -> int:
        session = sessionmaker(bind=engine)()
        origins = session.query(Origin).join(Lease, Origin.origin_ref == Lease.origin_ref, isouter=True).filter(Lease.lease_ref.is_(None)).all()
        origin_refs = [origin.origin_ref for origin in origins]
        deletions = session.query(Origin).filter(Origin.origin_ref.in_(origin_refs)).delete()
        session.commit()
        session.close()
        return deletions


class Lease(Base):
    __tablename__ = "lease"

    instance_ref = Column(CHAR(length=36), ForeignKey(Instance.instance_ref, ondelete='CASCADE'), nullable=False, index=True)  # uuid4
    lease_ref = Column(CHAR(length=36), primary_key=True, nullable=False, index=True)  # uuid4
    origin_ref = Column(CHAR(length=36), ForeignKey(Origin.origin_ref, ondelete='CASCADE'), nullable=False, index=True)  # uuid4
    # scope_ref = Column(CHAR(length=36), nullable=False, index=True)  # uuid4 # not necessary, we only support one scope_ref ('ALLOTMENT_REF')
    lease_created = Column(DATETIME(), nullable=False)
    lease_expires = Column(DATETIME(), nullable=False)
    lease_updated = Column(DATETIME(), nullable=False)

    __instance = relationship(Instance, foreign_keys=[instance_ref])
    __origin = relationship(Origin, foreign_keys=[origin_ref])

    def __repr__(self):
        return f'Lease(origin_ref={self.origin_ref}, lease_ref={self.lease_ref}, expires={self.lease_expires})'

    def serialize(self) -> dict:
        renewal_period = self.__instance.lease_renewal_period
        renewal_delta = self.__instance.get_lease_renewal_delta

        lease_renewal = int(Lease.calculate_renewal(renewal_period, renewal_delta).total_seconds())
        lease_renewal = self.lease_updated + relativedelta(seconds=lease_renewal)

        return {
            'lease_ref': self.lease_ref,
            'origin_ref': self.origin_ref,
            # 'scope_ref': self.scope_ref,
            'lease_created': self.lease_created.replace(tzinfo=timezone.utc).isoformat(),
            'lease_expires': self.lease_expires.replace(tzinfo=timezone.utc).isoformat(),
            'lease_updated': self.lease_updated.replace(tzinfo=timezone.utc).isoformat(),
            'lease_renewal': lease_renewal.replace(tzinfo=timezone.utc).isoformat(),
        }

    @staticmethod
    def create_statement(engine: Engine):
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
        deletions = session.query(Lease).filter(Lease.lease_expires <= datetime.now(UTC)).delete()
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


def init_default_site(session: Session):
    private_key = PrivateKey.generate()
    public_key = private_key.public_key()

    site = Site(
        site_key=Site.INITIAL_SITE_KEY_XID,
        name=Site.INITIAL_SITE_NAME
    )
    session.add(site)
    session.commit()

    instance = Instance(
        instance_ref=Instance.DEFAULT_INSTANCE_REF,
        site_key=site.site_key,
        private_key=private_key.pem(),
        public_key=public_key.pem(),
    )
    session.add(instance)
    session.commit()


def init(engine: Engine):
    tables = [Site, Instance, Origin, Lease]
    db = inspect(engine)
    session = sessionmaker(bind=engine)()
    for table in tables:
        exists = db.dialect.has_table(engine.connect(), table.__tablename__)
        logger.info(f'> Table "{table.__tablename__:<16}" exists: {exists}')
        if not exists:
            session.execute(text(str(table.create_statement(engine))))
            session.commit()

    # create default site
    cnt = session.query(Site).count()
    if cnt == 0:
        init_default_site(session)

    session.flush()
    session.close()


def migrate(engine: Engine):
    db = inspect(engine)

    # todo: add update guide to use 1.LATEST to 2.0
    def upgrade_1_x_to_2_0():
        site = Site.get_default_site(engine)
        logger.info(site)
        instance = Instance.get_default_instance(engine)
        logger.info(instance)

        # SITE_KEY_XID
        if site_key := env('SITE_KEY_XID', None) is not None:
            site.site_key = str(site_key)

        # INSTANCE_REF
        if instance_ref := env('INSTANCE_REF', None) is not None:
            instance.instance_ref = str(instance_ref)

        # ALLOTMENT_REF
        if allotment_ref := env('ALLOTMENT_REF', None) is not None:
            pass  # todo

        # INSTANCE_KEY_RSA, INSTANCE_KEY_PUB
        default_instance_private_key_path = str(join(dirname(__file__), 'cert/instance.private.pem'))
        instance_private_key = env('INSTANCE_KEY_RSA', None)
        if instance_private_key is not None:
            instance.private_key = PrivateKey(instance_private_key.encode('utf-8'))
        elif isfile(default_instance_private_key_path):
            instance.private_key = PrivateKey.from_file(default_instance_private_key_path)
        default_instance_public_key_path = str(join(dirname(__file__), 'cert/instance.public.pem'))
        instance_public_key = env('INSTANCE_KEY_PUB', None)
        if instance_public_key is not None:
            instance.public_key = PublicKey(instance_public_key.encode('utf-8'))
        elif isfile(default_instance_public_key_path):
            instance.public_key = PublicKey.from_file(default_instance_public_key_path)

        # TOKEN_EXPIRE_DELTA
        token_expire_delta = env('TOKEN_EXPIRE_DAYS', None)
        if token_expire_delta not in (None, 0):
            instance.token_expire_delta = token_expire_delta * 86_400
        token_expire_delta = env('TOKEN_EXPIRE_HOURS', None)
        if token_expire_delta not in (None, 0):
            instance.token_expire_delta = token_expire_delta * 3_600

        # LEASE_EXPIRE_DELTA, LEASE_RENEWAL_DELTA
        lease_expire_delta = env('LEASE_EXPIRE_DAYS', None)
        if lease_expire_delta not in (None, 0):
            instance.lease_expire_delta = lease_expire_delta * 86_400
        lease_expire_delta = env('LEASE_EXPIRE_HOURS', None)
        if lease_expire_delta not in (None, 0):
            instance.lease_expire_delta = lease_expire_delta * 3_600

        # LEASE_RENEWAL_PERIOD
        lease_renewal_period = env('LEASE_RENEWAL_PERIOD', None)
        if lease_renewal_period is not None:
            instance.lease_renewal_period = lease_renewal_period

        # todo: update site, instance

    upgrade_1_x_to_2_0()
