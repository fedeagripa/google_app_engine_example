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
from google.appengine.api import mail
from google.appengine.api import search
from google.appengine.api import channel
from google.appengine.api import images

from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext import vendor

#Modelos
from user import User
from contactList import ContactList
from blob import UserFile


from googleapiclient import discovery
from googleapiclient.http import MediaIoBaseUpload
from oauth2client.client import GoogleCredentials

vendor.add('libs')
import dicttoxml

# Defino el entorno de Jinja2
JINJA_ENVIRONMENT = jinja2.Environment(
    loader = jinja2.FileSystemLoader('views'),
    extensions = ['jinja2.ext.autoescape'],
    autoescape = True)

USERS_INDEX_NAME = 'users'
MESSAGES_INDEX_NAME = 'messages'

# [START handlers]

########################################################################################################################
#                                       HANDLERS
########################################################################################################################

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

                search.Index(name=USERS_INDEX_NAME).put(CreateUserDocument(newUser.username,newUser.mail))

                registeredUser = newUser
                registeredUserContacts = newUserContacts

                SendWelcomeEmail(loggedUser.email())

            token = channel.create_channel(loggedUser.nickname())

            template  = JINJA_ENVIRONMENT.get_template('index.html')

            template_values = {
                'nickname' : loggedUser.nickname(),
                'contactList' : registeredUserContacts.list,
                'token': token,
                'logouturl' : users.create_logout_url(self.request.uri)
            }

            self.response.write(template.render(template_values))

        else:
            self.redirect(users.create_login_url(self.request.uri))




class UserSearchHandler(webapp2.RequestHandler):

    def post(self):
        query = self.request.get('search-text')

        loggedUser = users.get_current_user()

        if loggedUser != query :

            results = GetUsers(query)

            contactlist = ContactList()
            contactlist = contactlist.query(ContactList.owner == loggedUser.nickname()).get()

            results_json = []

            for match in results:

                val = {'nickname' : match.field('nickname').value,
                       'mail' : match.field('email').value}

                results_json.append(val)

            # xml = dicttoxml.dicttoxml(results_json)
            values = {
                'results' : results_json
              #  'results' : xml
            }

            self.response.write(json.dumps(values, self.response.out))

#Agrega un usuario
class AddUserHandler(webapp2.RequestHandler):
    def post(self):

        inviter = users.get_current_user().nickname()
        invited = self.request.get('nickname')

        AddContact(inviter,invited)
        AddContact(invited,inviter)

        invitedUser = User()
        invitedUser = invitedUser.query(User.username == invited).get()

        self.response.write(invitedUser.mail)

#Obtiene url para subir blob y lo envia a la vista
class FileUploadFormHandler(webapp2.RequestHandler):

    def get(self):
        upload_url = blobstore.create_upload_url('/upload_file')

        self.response.write(upload_url)

#Recibe el blob, lo guarda y responde okay
class FileUploadHandler(blobstore_handlers.BlobstoreUploadHandler):

    def post(self):

        upload = self.get_uploads()[0]
        receiver = self.request.get('receiver')

        user_photo = UserFile(
            owner=users.get_current_user().nickname(),
            blob_key=upload.key())

        user_photo.put()

        message = 'te he enviado una imagen, mirala '

        imageUrl = images.get_serving_url(upload.key(), None, False, None, None, None)

        sender = users.get_current_user().nickname()

        SendMessage(sender, receiver, message, 2, imageUrl)

        self.response.write('okay')

#Manda mensaje de chat
class SendMessageHandler(webapp2.RequestHandler):

    def post(self):

        sender = users.get_current_user().nickname()
        receiver = self.request.get('receiver')
        message = self.request.get('message')

        SendMessage(sender, receiver, message, 1, None)

        self.response.write('okay')



#Obtiene los mensajes intercambiados entre dos usuarios
class GetMessagesHandler(webapp2.RequestHandler):
    def post(self):

        userOne = self.request.get('nickname')
        userTwo = users.get_current_user().nickname()

        messages = GetMessages(userOne,userTwo)

        messages_json = []

        for match in messages:

            type = match.field('type').value

            val = None

            if type == 1:

                val = { 'type': type,
                    'sender' : match.field('sender').value,
                   'receiver' : match.field('receiver').value,
                   'message' : match.field('message').value }

            else:
                val = { 'type': type,
                    'sender' : match.field('sender').value,
                   'receiver' : match.field('receiver').value,
                   'message' : match.field('message').value,
                        'url': match.field('url').value }

            messages_json.append(val)

        values = {
            'messages' : messages_json
        }

        self.response.write(json.dumps(messages_json, self.response.out))




class CronJobHandler(webapp2.RequestHandler):
    def get(self):
        blob = blobstore.get('vtgizu6aBLyqXTP_FRzstQ==')

        credentials = GoogleCredentials.get_application_default()

        service = discovery.build('storage', 'v1', credentials=credentials)

        media = MediaIoBaseUpload(
            blob,
            mimetype=blob.content_type
        )

        req = service.objects().insert(bucket='adroit-crow-130918.appspot.com', name= blob.filename, media_body=media)

        resp = req.execute()

        print resp['name']


class BroadcastHandler(webapp2.RequestHandler):

    def post(self):

        message = self.request.get('message')
        receivers = json.loads(self.request.get('receivers'))
        sender = users.get_current_user().nickname()

        for receiver in receivers:

            SendMessage(sender, receiver, message, 1, None)

        self.response.write('okay')

# [END handlers]

# [START funcaux]
########################################################################################################################
#                                       FUNCIONES AUXILIARES
########################################################################################################################

# Agrega al usuario 1 a la lista de contactos del usuario 2
def AddContact(user1, user2):

    userOne = User()
    userOne= userOne.query(User.username == user1).get()

    userTwoContactList = ContactList()
    userTwoContactList = userTwoContactList.query(ContactList.owner == user2).get()

    userTwoContactList.list.append(userOne)

    userTwoContactList.put()


def SendMessage(sender, receiver, message, type, url):

    try:

        if type == 1:

            messageTypeOne = { 'type' : 1,
                'sender' : sender,
                'message' : message
            }

            channel.send_message(receiver, json.dumps(messageTypeOne))

        else:

            messageTypeTwo = { 'type' : 2,
                'sender' : sender,
                'message' : message,
                'url' : url
            }

            channel.send_message(receiver, json.dumps(messageTypeTwo))


        search.Index(name=MESSAGES_INDEX_NAME).put(CreateMessageDocument(sender,receiver,message,str(type),url))

    except:
        pass


def SendWelcomeEmail(address):

    mail.send_mail('aplicacionesescalables@gmail.com',address,'Bienvenido','Ha sido registrado en la aplicacion de chat con exito, bienvenido!')

#Crea documento para guardar usuarios
def CreateUserDocument(nickname, email):

    return search.Document(
        fields=[search.TextField(name='nickname', value=nickname),
                search.TextField(name='email', value=email)])

#Crea documento para guardar usuarios
def CreateMessageDocument(sender, receiver, message, type, url):

    return search.Document(
        fields=[search.TextField(name='sender', value=sender),
                search.TextField(name='receiver', value=receiver),
                search.TextField(name='message', value=message),
                search.DateField(name='timestamp', value=datetime.now()),
                search.TextField(name='type', value= type),
                search.TextField(name='url', value= url)])


def GetMessages(sender, receiver):

    expr_list = [
        search.SortExpression(
            expression='timestamp', default_value=datetime.min,
            direction=search.SortExpression.DESCENDING),
        search.SortExpression(
                    expression='sender', default_value='',
                    direction=search.SortExpression.ASCENDING),
        search.SortExpression(
                    expression='receiver', default_value='',
                    direction=search.SortExpression.ASCENDING)

                    ]

    sort_opts = search.SortOptions(expressions=expr_list)

    query_options = search.QueryOptions(limit= 10,sort_options=sort_opts)

    query_obj = search.Query(query_string=sender + ' ' +receiver, options=query_options)

    results = search.Index(name=MESSAGES_INDEX_NAME).search(query=query_obj)

    return results

#Devuelve usuarios que coincidan con la busqueda
def GetUsers(query):

    expr_list = [search.SortExpression(
                    expression='nickname', default_value='',
                    direction=search.SortExpression.DESCENDING)]

    sort_opts = search.SortOptions(expressions=expr_list)

    query_options = search.QueryOptions(limit= 50,sort_options=sort_opts)

    query_obj = search.Query(query_string=query, options=query_options)

    results = search.Index(name=USERS_INDEX_NAME).search(query=query_obj)

    return results

# [END funcaux]


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/search', UserSearchHandler),
    ('/upload_file', FileUploadHandler),
    ('/upload_file_form', FileUploadFormHandler),
    ('/add_contact', AddUserHandler),
    ('/send_message', SendMessageHandler),
    ('/get_messages', GetMessagesHandler),
    ('/tasks',CronJobHandler),
    ('/send_broadcast', BroadcastHandler)
], debug=True)
