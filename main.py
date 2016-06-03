#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import cgi
import os
import webapp2
import jinja2
import json

from datetime import datetime
from google.appengine.api import users
from google.appengine.api import search
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import app_identity
from google.appengine.api import mail
from user import User
from contactList import ContactList
from blob import UserFile

# Defino el entorno de Jinja2
JINJA_ENVIRONMENT = jinja2.Environment(
    loader = jinja2.FileSystemLoader('views'),
    extensions = ['jinja2.ext.autoescape'],
    autoescape = True)

_INDEX_NAME = 'users'

class MainHandler(webapp2.RequestHandler):
    def get(self):

        loggedUser = users.get_current_user()

        if loggedUser:

            registeredUser = User()
            registeredUser = registeredUser.query(User.username == loggedUser.nickname()).get()

            registeredUserContacts = ContactList()
            registeredUserContacts = registeredUserContacts.query(ContactList.owner == loggedUser.nickname()).get()

            if not registeredUser:

                newUser = User()
                newUser.username = loggedUser.nickname()
                newUser.mail = loggedUser.email()

                newUserContacts = ContactList()
                newUserContacts.list = []
                newUserContacts.owner = newUser.username

                newUser.put()
                newUserContacts.put()

                search.Index(name=_INDEX_NAME).put(CreateDocument(newUser.username,newUser.mail))

                registeredUser = newUser
                registeredUserContacts = newUserContacts


            template  = JINJA_ENVIRONMENT.get_template('index.html')

            template_values = {
                'nickname' : loggedUser.nickname(),
                'contactList' : registeredUserContacts.list
            }

            self.response.write(template.render(template_values))

        else:
            self.redirect(users.create_login_url(self.request.uri))


#Crea documento para guardar usuarios
def CreateDocument(nickname, email):

    return search.Document(
        fields=[search.TextField(name='nickname', value=nickname),
                search.TextField(name='email', value=email)])


#Devuelve usuarios que coincidan con la busqueda
def GetUsers(query):

    expr_list = [search.SortExpression(
                    expression='nickname', default_value='',
                    direction=search.SortExpression.DESCENDING)]

    sort_opts = search.SortOptions(expressions=expr_list)

    query_options = search.QueryOptions(limit= 50,sort_options=sort_opts)

    query_obj = search.Query(query_string=query, options=query_options)

    results = search.Index(name=_INDEX_NAME).search(query=query_obj)

    return results


class UserSearchHandler(webapp2.RequestHandler):

    def post(self):
        query = self.request.get('search-text')

        results = GetUsers(query)

        loggedUser = users.get_current_user()

        contactlist = ContactList()
        contactlist = contactlist.query(ContactList.owner == loggedUser.nickname()).get()


        results_json = []

        for match in results:

            val = {'nickname' : match.field('nickname').value,
                   'mail' : match.field('email').value}

            results_json.append(val)

        values = {
            'results' : results_json
        }

        self.response.write(json.dumps(results_json, self.response.out))

#Agrega un usuario
class AddUserHandler(webapp2.RequestHandler):
    def post(self):

        nickname = self.request.get('nickname')

        newcontact = User()
        newcontact = newcontact.query(User.username == nickname).get()

        loggedUser = users.get_current_user()

        contactlist = ContactList()
        contactlist = contactlist.query(ContactList.owner == loggedUser.nickname()).get()

        contactlist.list.append(newcontact)

        contactlist.put()

        self.response.write(newcontact.mail)


#Obtiene url para subir blob y lo envia a la vista
class FileUploadFormHandler(webapp2.RequestHandler):

    def get(self):
        upload_url = blobstore.create_upload_url('/upload_file')

        self.response.write(upload_url)

#Recibe el blob, lo guarda y responde okay
class FileUploadHandler(blobstore_handlers.BlobstoreUploadHandler):

    def post(self):
            form = cgi.FieldStorage()
            upload = form.getvalue('image')
            user_photo = UserFile(
                owner=users.get_current_user().nickname(),
                blob_key=form.getvalue('blobkey'))
            user_photo.put()

            self.response.write('okay')


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/search', UserSearchHandler),
    ('/upload_file', FileUploadHandler),
    ('/upload_file_form', FileUploadFormHandler),
    ('/add_contact', AddUserHandler)
], debug=True)
