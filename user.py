from google.appengine.ext import ndb

class User(ndb.Model):
    mail = ndb.StringProperty(indexed=True)
    username = ndb.StringProperty(indexed=True)