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

from google.appengine.api import users
from google.appengine.api import app_identity
from google.appengine.api import mail
from user import User
from contactList import ContactList

# Defino el entorno de Jinja2
JINJA_ENVIRONMENT = jinja2.Environment(
    loader = jinja2.FileSystemLoader('views'),
    extensions = ['jinja2.ext.autoescape'],
    autoescape = True)

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

                user1 = User()
                user1.username = "pepito"
                user1.mail = "asd@gmail.com"

                newUserContacts = ContactList()
                newUserContacts.contactUserList = [user1]
                newUserContacts.owner = newUser.username

                newUser.put()
                newUserContacts.put()
                registeredUserContacts = newUserContacts


            template  = JINJA_ENVIRONMENT.get_template('index.html')

            if not registeredUserContacts:
                template_values = {
                    'nickname': loggedUser.nickname(),
                    'contactList': []
                }
            else:
                template_values = {
                    'nickname': loggedUser.nickname(),
                    'contactList': registeredUserContacts.contactUserList
                }

            self.response.write(template.render(template_values))

        else:
            self.redirect(users.create_login_url(self.request.uri))


app = webapp2.WSGIApplication([
    ('/', MainHandler)
], debug=True)
