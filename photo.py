from google.appengine.ext import ndb

class Photo(ndb.Model):
    title = ndb.StringProperty()
    full_size_image = ndb.BlobProperty()