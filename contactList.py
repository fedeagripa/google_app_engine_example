from google.appengine.ext import ndb
from user import User

class ContactList(ndb.Model):
    list = ndb.StructuredProperty(User, repeated=True)
    owner = ndb.StringProperty(indexed=True)