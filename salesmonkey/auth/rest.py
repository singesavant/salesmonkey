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
from flask_login import login_user, logout_user
from flask_login import login_required

from ..erpnext import erp_client
from erpnext_client.documents import (
    ERPUser,
    ERPCustomer,
    ERPContact,
    ERPContactPhone,
    ERPContactEmail,
    ERPAddress,
    ERPDynamicLink
)

from erpnext_client.schemas import (
    ERPAddressSchema,
    ERPContactSchema
)

import logging

LOGGER = logging.getLogger(__name__)

@marshal_with(ERPAddressSchema)
class CustomerPostalAddress(MethodResource):
    """
    Customer Address management
    """

    def _get_customer_postal_address(self, customer_name):
        link = erp_client.query(ERPDynamicLink).first(filters=[['Dynamic Link', 'parenttype', '=', 'Address'],
                                                               ['Dynamic Link', 'link_name', '=', customer_name],
                                                               ['Dynamic Link', 'parentfield', '=', 'links']],
                                                      erp_fields=['parent'],
                                                      parent="Address")
        address = erp_client.query(ERPAddress).get(name=link['parent'])

        return address


    @login_required
    def get(self, **kwargs):
        address = {}

        customer = session.get('customer')

        try:
            address = self._get_customer_postal_address(customer['name'])
        except ERPAddress.DoesNotExist:
            pass

        return address

    @login_required
    @marshal_with(None, code=201)
    @use_kwargs(ERPAddressSchema)
    def post(self, **kwargs):
        customer = session.get('customer')
        contact = session.get('contact')

        LOGGER.debug(customer)

        data = {
            'address_type': 'Shipping',
            'address_title': '{0}'.format(contact['name'])
        }


        kwargs.update(data)

        # Try to fetch existing Address
        try:
            existing_address = self._get_customer_postal_address(customer['name'])
            LOGGER.debug("we already have an address")

            existing_address.update(kwargs)

            LOGGER.debug(existing_address)
            erp_client.query(ERPAddress).update(name=existing_address['name'], data=existing_address)

        except ERPAddress.DoesNotExist:
            # Create a new address object and link it
            if 'address_line2' in kwargs:
                data['address_line2'] = ''

            address = erp_client.query(ERPAddress).create(data=kwargs)

            LOGGER.debug("Address <{0}> created.".format(address['name']))

            link = erp_client.query(ERPDynamicLink).create(data={'parent': address['name'],
                                                                 'parenttype': 'Address',
                                                                 'parentfield': 'links',
                                                                 'link_doctype': 'Customer',
                                                                 'link_name': customer['name']})

            LOGGER.debug("Address successfully linked to Customer <{0}>.".format(link['name']))

        return True


api_v1.register('/customer/address', CustomerPostalAddress)

@marshal_with(ERPContactSchema)
class CustomerContact(MethodResource):
    """
    Handle User Address management
    """
    def _get_customer_contact(self, customer_name):
        link = erp_client.query(ERPDynamicLink).first(filters=[['Dynamic Link', 'parenttype', '=', 'Contact'],
                                                               ['Dynamic Link', 'link_name', '=', customer_name],
                                                               ['Dynamic Link', 'parentfield', '=', 'links']],
                                                      erp_fields=['parent'],
                                                      parent="Contact")

        contact = erp_client.query(ERPContact).get(name=link['parent'])

        return contact


    @login_required
    def get(self, **kwargs):
        contact = {}

        customer = session.get('customer')

        try:
            contact = self._get_customer_contact(customer['name'])
        except ERPAddress.DoesNotExist:
            pass

        return contact

    @login_required
    @marshal_with(None, code=201)
    @use_kwargs(ERPContactSchema)
    def post(self, **kwargs):
        customer = session.get('customer')

        # Try to fetch existing Contact
        try:
            existing_contact = self._get_customer_contact(customer['name'])
            LOGGER.debug("we already have a contact")

            existing_contact['first_name'] = kwargs['first_name']
            existing_contact['last_name'] = kwargs['last_name']

            # We don't want to update email fields
            del existing_contact['email_ids']
            del existing_contact['email']

            contact_phone = {
                'phone': kwargs['mobile_no'],
                'is_primary_mobile_no': 1
            }

            if len(existing_contact['phone_nos']) > 0:
                for phone_no in existing_contact['phone_nos']:
                    if phone_no['is_primary_mobile_no'] is True:
                        LOGGER.debug("We have a phone!")
                        phone_no.update(contact_phone)

            else:
                LOGGER.debug("NEW PHONE")
                contact_phone_data = {'docstatus': 0,
                                      'parent': existing_contact['name'],
                                      'parenttype': 'Contact',
                                      'phone': kwargs['mobile_no'],
                                      'is_primary_mobile_no': True,
                                      'parentfield': 'phone_nos',
                                      'doctype': 'Contact Phone'}

                contact_phone = erp_client.query(ERPContactPhone).create(data=contact_phone_data)
                existing_contact['phone_nos'].append(contact_phone)

            # Trigger update !
            erp_client.query(ERPContact).update(name=existing_contact['name'], data=existing_contact)

        except ERPContact.DoesNotExist:
            # Create a new contact object and link it
            contact = erp_client.query(ERPContact).create(data=kwargs)

            LOGGER.debug("Contact <{0}> created.".format(contact['name']))

            link = erp_client.query(ERPDynamicLink).create(data={'parent': contact['name'],
                                                                 'parenttype': 'Contact',
                                                                 'parentfield': 'links',
                                                                 'link_doctype': 'Customer',
                                                                 'link_name': customer['name']})

            LOGGER.debug("Contact successfully linked to Customer <{0}>.".format(link['name']))

        return True



api_v1.register('/customer/contact', CustomerContact)

class LogoutManager(MethodResource):
    @login_required
    def get(self):
        logout_user()

        return True

api_v1.register('/auth/logout', LogoutManager)

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
            LOGGER.debug("Creating New contact for <{0}>".format(aUser.username))

            contact = erp_client.query(ERPContact).create(data={'first_name': aUser.first_name,
                                                                'user': aUser.username,
                                                                'email_id': aUser.email,
                                                                'last_name': aUser.last_name})

            contact_email_data = {'docstatus': 0,
                                  'parent': contact['name'],
                                  'parenttype': 'Contact',
                                  'email_id': aUser.email,
                                  'is_primary': True,
                                  'parentfield': 'email_ids',
                                  'doctype': 'Contact Email'}

            contact_email = erp_client.query(ERPContactEmail).create(data=contact_email_data)

            contact['email'] = contact_email['email']

            LOGGER.debug("Created Contact <{0}> on ERP".format(contact['name']))

        # Contact -> Customer Link
        customer = None
        try:
            link = erp_client.query(ERPDynamicLink).first(filters=[['Dynamic Link', 'parenttype', '=', 'Contact'],
                                                                   ['Dynamic Link', 'parent', '=', contact['name']],
                                                                   ['Dynamic Link', 'parentfield', '=', 'links']],
                                                          erp_fields=['name', 'link_name', 'parent', 'parenttype'],
                                                          parent="Contact")

            customer = erp_client.query(ERPCustomer).first(filters=[['Customer', 'name', '=', link['link_name']]])
            LOGGER.debug("Found Customer <{0}> on ERP".format(customer['name']))

        except ERPDynamicLink.DoesNotExist:
            customer = erp_client.query(ERPCustomer).create(data={'customer_name': "{0} {1}".format(contact['first_name'],
                                                                                                    contact['last_name']),
                                                                  'customer_type': 'Individual',
                                                                  'primary_address': "",
                                                                  'language': 'fr',
                                                                  'customer_group': 'Particulier',
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
