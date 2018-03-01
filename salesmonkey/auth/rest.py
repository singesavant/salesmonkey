from werkzeug.exceptions import Unauthorized, NotImplemented
import requests

from flask import session

from salesmonkey.rest import api_v1

from webargs import fields

from flask_apispec import (
    FlaskApiSpec,
    marshal_with,
    MethodResource,
    use_kwargs
)

from .schemas import UserSchema

from .models import User
from flask_login import login_user

from ..erpnext import erp_client
from ..erpnext_client.documents import (
    ERPUser,
    ERPCustomer,
    ERPContact,
    ERPDynamicLink
)


import logging

LOGGER = logging.getLogger(__name__)

@marshal_with(UserSchema)
class AuthWith(MethodResource):
    """
    Auth using a third-party provider
    """
    def _get_or_create_erp_user_from_google(self, token):
        res = requests.get("https://www.googleapis.com/oauth2/v3/tokeninfo", {'access_token': token})

        if res.status_code != requests.codes.ok:
            raise Unauthorized

        json = res.json()
        if not ('sub' in json and 'email' in json):
            raise Unauthorized

        erp_user = None
        try:
            erp_user = erp_client.query(ERPUser).get(json['email'], fields='["first_name", "last_name"]')
            LOGGER.debug("Found User <{0}> on ERP".format(erp_user['name']))
        except ERPUser.DoesNotExist:
            res = requests.get("https://www.googleapis.com/oauth2/v3/userinfo", {'access_token': token})

            if res.status_code != requests.codes.ok:
                raise Unauthorized

            user_info_json = res.json()

            if user_info_json['email_verified'] is False:
                raise Unhautorized

            # Compute gender
            try:
                gender = {'male': 'Male',
                          'female': 'Female'}[user_info_json['gender']]
            except KeyError:
                gender = 'Other'

            erp_user = erp_client.query(ERPUser).create(data={'email': user_info_json['email'],
                                                              'google_userid': json['sub'],
                                                              'username': user_info_json['email'],
                                                              'language': user_info_json['locale'],
                                                              'gender': gender,
                                                              'image_field': user_info_json['picture'], # XXX Should be Attach
                                                              'first_name': user_info_json['given_name'],
                                                              'last_name': user_info_json['family_name'],
                                                              'send_welcome_email': False})
            LOGGER.debug("Created User <{0}> on ERP".format(erp_user['name']))

        return erp_user

    def _get_or_create_contact_and_customer_for_user(self, aUser):
        """
        Get or create Customer and Contact objects for the given user on the ERP
        """
        # Contact Creation
        try:
            contact = erp_client.query(ERPContact).first(filters=[['Contact', 'user', '=', aUser.username]],
                                                         erp_fields=['name', 'first_name', 'last_name'])
            LOGGER.debug("Found Contact <{0}> on ERP".format(contact['name']))
        except ERPContact.DoesNotExist:
            contact = erp_client.query(ERPContact).create(data={'email_id': aUser.email,
                                                                'email': aUser.email,
                                                                'first_name': aUser.first_name,
                                                                'last_name': aUser.last_name})

            LOGGER.debug("Created Contact <{0}> on ERP".format(contact['name']))

        # Contact -> Customer Link
        customer = None
        try:
            link = erp_client.query(ERPDynamicLink).first(filters=[['Dynamic Link', 'parenttype', '=', 'Contact'],
                                                                   ['Dynamic Link', 'parent', '=', contact['name']],
                                                                   ['Dynamic Link', 'parentfield', '=', 'links']],
                                                          erp_fields=['name', 'link_name', 'parent', 'parenttype'])

            customer = erp_client.query(ERPCustomer).first(filters=[['Customer', 'name', '=', link['link_name']]])
            LOGGER.debug("Found Customer <{0}> on ERP".format(customer['name']))

        except ERPDynamicLink.DoesNotExist:
            customer = erp_client.query(ERPCustomer).create(data={'customer_name': "{0} {1}".format(contact['first_name'],
                                                                                                    contact['last_name']),
                                                                  'customer_type': 'Individual',
                                                                  'language': 'fr',
                                                                  'customer_group': 'Individual',
                                                                  'territory': 'France'})

            # Create link between Contact and Customer
            link = erp_client.query(ERPDynamicLink).create(data={'parent': contact['name'],
                                                                 'parenttype': 'Contact',
                                                                 'parentfield': 'links',
                                                                 'link_doctype': 'Customer',
                                                                 'link_name': customer['name']})

            LOGGER.debug("Created Customer <{0}> on ERP".format(customer['name']))

        if customer is None:
            raise Unauthorized

        return contact, customer



    @use_kwargs({'provider': fields.Str(required=True)})
    @use_kwargs({'token': fields.Str(required=True)})
    def get(self, provider, token, **kwargs):
        if provider == "google":
            erp_user = self._get_or_create_erp_user_from_google(token)
        else:
            raise NotImplemented

        user = User(username=erp_user['email'],
                    email=erp_user['email'],
                    first_name=erp_user['first_name'],
                    last_name=erp_user['last_name'])

        if login_user(user):
            # Create ERP Contact and Customer
            contact, customer = self._get_or_create_contact_and_customer_for_user(user)
            session['contact'] = contact
            session['customer'] = customer

            return user

        raise NotAuthorized

api_v1.register('/auth/with', AuthWith)
