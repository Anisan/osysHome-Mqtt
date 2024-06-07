
from app.database import Column, Model, SurrogatePK, db

class Topic(SurrogatePK, db.Model):
    __tablename__ = 'mqtt_topics'
    title = Column(db.String(100))
    updated = Column(db.DateTime)
    value = Column(db.Text)
    path = Column(db.String(255))
    path_write = Column(db.String(255))
    linked_object = Column(db.String(255))
    linked_property = Column(db.String(255))
    linked_method = Column(db.String(255))
    qos = Column(db.Integer, default = 0)
    retain = Column(db.Boolean, default = False)
    replace_list = Column(db.String(255))
    readonly = Column(db.Boolean, default = False)
    only_new_value = Column(db.Boolean, default = False)
