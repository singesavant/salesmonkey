import math
import random
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
    CartLineSchema,
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
                                     client_secret=self.client_secret,
                                     auth={})

        self.token = response.get('access_token', None)

    def create_checkout(self, amount, reference, description, currency='EUR'):
        if not self.token:
            self._make_token()

        r = requests.post("{0}/checkouts".format(self.API_BASE_URL),
                          headers={'Authorization': 'Bearer {0}'.format(self.token)},
                          json={'amount': amount,
                                'currency': currency,
                                'pay_to_email': self.merchant_email,
                                'checkout_reference': reference,
                                'description': description})

        if not r.ok:
            r.raise_for_status()

        current_checkout = r.json()

        return current_checkout

    def get_checkout(self, checkout_id):
        r = requests.get("{0}/checkouts/{1}".format(self.API_BASE_URL, current_checkout['id']),
                          headers={'Authorization': 'Bearer {0}'.format(self.token)})
        if r.ok:
            return r.json()
        else:
            r.raise_for_status()


class SalesOrderSumUpPayment(Step):
    def __init__(self, sales_order):
        self.sales_order = sales_order
        self.client = SumUpClient(app.config["SUMUP_CLIENT_ID"],
                                  app.config["SUMUP_CLIENT_SECRET"],
                                  app.config["SUMUP_MERCHANT_ID"])

    def create_sumup_checkout(self):
        return self.client.create_checkout(self.sales_order['amount_total'],
                                           "{0}-{1}".format(self.sales_order['name'], str(random.randint(0, 1000))),
                                           "Website - {0}".format(self.sales_order['title']))

    def validate(self):
        # checkout = self.client.get_checkout("CHECKOUT ID") # FIMXE
        # if checkout['status'] == 'PAID':
        #     return True
        # else:
        raise InvalidData('Payment not accepted')


class SalesOrderCheckoutManager(ProcessManager):
    def __init__(self, sales_order):
        self.sales_order = sales_order

    def __iter__(self):
        yield SalesOrderSumUpPayment(self.sales_order)


class SalesOrderCheckout(MethodResource):
    @login_required
    def get(self, name):
        customer = session.get('customer', None)
        if not customer:
            raise NotFound

        try:
            sales_order = erp_client.query(ERPSalesOrder).get(name,
                                                              fields='["name", "title", "grand_total", "customer", "items", "transaction_date"]',
                                                              filters=[["Sales Order", "Customer", "=", customer['name']],
                                                                       ["Sales Order", "status", "!=", "Cancelled"]])
        except ERPSalesOrder.DoesNotExist:
            raise NotFound

        manager = SalesOrderCheckoutManager(sales_order)
        next_step = manager.get_next_step()
        sumup_info = next_step.create_sumup_checkout()

        if sumup_info == None:
            raise BadRequest

        return sumup_info

    @login_required
    def post(self, name):
        customer = session.get('customer', None)
        if not customer:
            raise NotFound

        try:
            sales_order = erp_client.query(ERPSalesOrder).get(name,
                                                              fields='["name", "title", "grand_total", "customer", "items", "transaction_date"]',
                                                              filters=[["Sales Order", "Customer", "=", customer['name']],
                                                                       ["Sales Order", "status", "!=", "Cancelled"]])
        except ERPSalesOrder.DoesNotExist:
            raise NotFound



api_v1.register('/shop/orders/<name>/checkout', SalesOrderCheckout)

