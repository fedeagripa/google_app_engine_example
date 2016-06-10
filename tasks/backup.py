import webapp2

from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers

from blob import UserFile

class MainHandler(webapp2.RequestHandler):
    def get(self):

        photos = UserFile()



