import math
import random
from datetime import date
import requests
from werkzeug.exceptions import NotFound, BadRequest

from flask_apispec import (
    FlaskApiSpec,
    marshal_with,
    MethodResource,
    use_kwargs
)

from flask_login import login_required
from flask import session

from webargs import fields
from webargs.flaskparser import use_args

from erpnext_client.schemas import (
    ERPItemSchema,
    ERPSalesOrderSchema,
    ERPSalesOrderItemSchema
)
from erpnext_client.documents import (
    ERPItem,
    ERPSalesOrder,
    ERPUser,
    ERPCustomer,
    ERPContact,
    ERPDynamicLink
)

from ..schemas import (
    CartSchema,
    Cart, Item
)

from flask_login import current_user

from salesmonkey import app

from ..erpnext import erp_client

from ..rest import api_v1
from ..utils import OrderNumberGenerator

import logging

LOGGER = logging.getLogger(__name__)

from satchless.process import InvalidData, Step, ProcessManager

from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session


class SumUpClient:
    """
    Simple SumUp Client
    """
    API_BASE_URL = 'https://api.sumup.com/v0.1'

    def __init__(self, client_id, client_secret, merchant_email):

        self.client_id = client_id
        self.client_secret = client_secret

        self.merchant_email = merchant_email

        self.token = None # FIXME Need refresh
        self.current_checkout = None

    def _make_token(self):
        client = BackendApplicationClient(client_id=self.client_id)

        oauth = OAuth2Session(client=client)

        response = oauth.fetch_token(token_url='https://api.sumup.com/token',
                                     client_id=self.client_id,
                                     client_secret=self.client_secret)

        self.token = response.get('access_token', None)

    def get_checkout_by_reference(self, reference):
        if not self.token:
            self._make_token()


        r = requests.get("{0}/checkouts".format(self.API_BASE_URL),
                          headers={'Authorization': 'Bearer {0}'.format(self.token)},
                          params={'checkout_reference': reference})
        if not r.ok:
            r.raise_for_status()

        checkouts = r.json()

        LOGGER.debug(checkouts)

        if len(checkouts):
            return checkouts[0]
        else:
            raise NotFound


    def create_checkout(self, amount, reference, description, currency='EUR'):
        if not self.token:
            self._make_token()

        json_payload = {'amount': amount,
                        'currency': currency,
                        'pay_to_email': self.merchant_email,
                        'checkout_reference': "{0}".format(reference),
                        # 'return_url': 'http://singe-savant.com/return',
                        'description': description}

        r = requests.post("{0}/checkouts".format(self.API_BASE_URL),
                          headers={'Authorization': 'Bearer {0}'.format(self.token)},
                          json=json_payload)

        # If we already have a checkout with this checkout reference
        if r.status_code == requests.codes.conflict:
            LOGGER.debug("A checkout already exist for: {0}".format(reference))
            try:
                existing_checkout = self.get_checkout_by_reference(reference=reference)
                if existing_checkout['status'] == 'PENDING':
                    if existing_checkout['amount'] != amount:
                        # Old Checkout, delete it and recreate !
                        r = requests.delete("{0}/checkouts/{1}".format(self.API_BASE_URL, existing_checkout['id']),
                                            headers={'Authorization': 'Bearer {0}'.format(self.token)})

                        # and make a new one
                        r = requests.post("{0}/checkouts".format(self.API_BASE_URL),
                                          headers={'Authorization': 'Bearer {0}'.format(self.token)},
                                          json=json_payload)

            except NotFound:
                # Already paid ?
                return {"status": "ALREADY_PAID"}
            return existing_checkout
        elif not r.ok:
            r.raise_for_status()

        LOGGER.debug("Created new checkout!")

        current_checkout = r.json()

        return current_checkout


    def get_checkout(self, checkout_id):
        if not self.token:
            self._make_token()

        r = requests.get("{0}/checkouts/{1}".format(self.API_BASE_URL, checkout_id),
                          headers={'Authorization': 'Bearer {0}'.format(self.token)})
        if r.ok:
            return r.json()
        else:
            r.raise_for_status()


class SalesOrderSumUpPayment(Step):
    def __str__(self): return 'payment'

    def __init__(self, sales_order):
        self.sales_order = sales_order
        self.client = SumUpClient(app.config["SUMUP_CLIENT_ID"],
                                  app.config["SUMUP_CLIENT_SECRET"],
                                  app.config["SUMUP_MERCHANT_ID"])

    def create_sumup_checkout(self):
        return self.client.create_checkout(amount=self.sales_order['amount_total'],
                                           reference="{0}".format(self.sales_order['name']),
                                           description="Website - {0} - {1}".format(self.sales_order['title'],
                                                                                    self.sales_order['name']))

    def validate(self, checkout_id):
        checkout = self.client.get_checkout(checkout_id)
        customer = session.get('customer', None)
        if customer is None:
            raise InvalidData('Session Error')

        if checkout['status'] == 'PAID':
            erp_client.query(ERPSalesOrder).update(name=self.sales_order['name'], data={'docstatus': 1})

            payment_entry  = erp_client.create_resource("Payment Entry",
                                                        data={'docstatus': 1,
                                                              'title': "Paiement Web {0} {1}".format(current_user.first_name,
                                                                                                     current_user.last_name),
                                                              'company': 'Le Singe Savant',
                                                              'party_type': "Customer",
                                                              'party': customer['name'],
                                                              'payment_type': "Receive",
                                                              'mode_of_payment': "Credit Card",
                                                              'naming_series': "PE-WEB-.YY.MM.DD.-.###",

                                                              'paid_amount': checkout['amount'],

                                                              'paid_to': '517 - SumUp - LSS',
                                                              'received_amount': checkout['amount'],

                                                              'reference_no': "SUMUP/{0}".format(checkout['transaction_code']),
                                                              'reference_date': "{0}".format(date.today()),
                                                              'references': [{
                                                                  'reference_doctype': 'Sales Order',
                                                                  'reference_name': self.sales_order['name'],
                                                                  'allocated_amount': checkout['amount']
                                                              }]
                                                        })

            cart = Cart.from_session()
            cart.clear()
        else:
            raise InvalidData('Payment not accepted')


class SalesOrderAddress(Step):
    def __init__(self, sales_order):
        self.sales_order = sales_order

    def validate(self):
        return True


class SalesOrderCheckoutManager(ProcessManager):
    def __init__(self, sales_order):
        self.sales_order = sales_order

    def __iter__(self):
        yield SalesOrderSumUpPayment(self.sales_order)


class SalesOrderPayment(MethodResource):
    def _get_shopping_cart_so_from_erp(self, so_name, customer_name):
            return erp_client.query(ERPSalesOrder).get(so_name,
                                                       fields='["name", "title", "grand_total", "customer", "items", "transaction_date"]',
                                                       filters=[["Sales Order", "docstatus", "=", "0"],
                                                                ["Sales Order", "Customer", "=", customer_name],
                                                                ["Sales Order", "Order Type", "=", "Shopping Cart"],
                                                                ["Sales Order", "status", "=", "Draft"]])
    @login_required
    def get(self, name):
        customer = session.get('customer', None)

        if not customer:
            raise NotFound

        try:
            sales_order = self._get_shopping_cart_so_from_erp(name, customer['name'])
        except ERPSalesOrder.DoesNotExist:
            raise NotFound

        manager = SalesOrderCheckoutManager(sales_order)

        payment_step = manager['payment']

        sumup_info = payment_step.create_sumup_checkout()

        if sumup_info == None:
            raise BadRequest

        return sumup_info

    @login_required
    @use_kwargs({'checkout_id': fields.String(required=True)})
    def post(self, name, **kwargs):
        customer = session.get('customer', None)
        if not customer:
            raise NotFound

        try:
            sales_order = self._get_shopping_cart_so_from_erp(name, customer['name'])
        except ERPSalesOrder.DoesNotExist:
            raise NotFound


        manager = SalesOrderCheckoutManager(sales_order)

        payment_step = manager['payment']

        payment_step.validate(kwargs['checkout_id'])



api_v1.register('/shop/orders/<name>/payment', SalesOrderPayment)

