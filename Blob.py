from google.appengine.ext import ndb

class UserFile(ndb.Model):
    owner = ndb.StringProperty()
    blob_key = ndb.BlobKeyProperty()