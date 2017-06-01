import math
import requests
from werkzeug.exceptions import NotFound, BadRequest

from flask_apispec import (
    FlaskApiSpec,
    marshal_with,
    MethodResource,
    use_kwargs
)

from flask_login import login_required

from webargs import fields
from webargs.flaskparser import use_args

from ..erpnext_client.schemas import (
    ERPItemSchema,
    ERPSalesOrderSchema,
    ERPSalesOrderItemSchema
)
from ..erpnext_client.documents import (
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

from ..erpnext import erp_client

from ..rest import api_v1
from ..utils import OrderNumberGenerator

import logging

LOGGER = logging.getLogger(__name__)

class PreorderCartDetail(MethodResource):
    """
    User Cart
    """
    @login_required
    @marshal_with(CartSchema)
    def get(self, **kwargs):
        return Cart.from_session()

    @login_required
    @use_kwargs({'item_code': fields.Str()})
    @marshal_with(None, code=204)
    def delete(self, **kwargs):
        cart = Cart.from_session()

        item_code = kwargs.get('item_code', None)
        if item_code is None:
            raise BadRequest("Missing item")

        cart.add(Item(item_code, item_code, 0.0),
                 quantity=0, replace=True)

    def _prepare_erp_data_for_user(self, aUser):
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
                # Customer
                try:
                    customer = erp_client.query(ERPCustomer).first(filters=[['Customer', 'name', '=', link['link_name']]])
                    LOGGER.debug("Found Customer <{0}> on ERP".format(customer['name']))
                except ERPCustomer.DoesNotExist:
                    raise Unauthorized


        return contact, customer


    @login_required
    @marshal_with(CartSchema)
    def post(self):
        cart = Cart.from_session()
        if cart.count() <= 0:
            raise BadRequest("Empty cart")

        items = [{'item_code': line.product.code, 'qty': line.quantity} for line in cart]

        contact, customer = self._prepare_erp_data_for_user(current_user)

        # Place SO
        num_gen = OrderNumberGenerator()
        so = erp_client.create_sales_order(customer=customer['name'],
                                           order_type="Shopping Cart",
                                           naming_series="SO-WEB-.YY.MM.DD.-.###",
                                           title="Préco Web {0} {1}".format(current_user.first_name,
                                                                            current_user.last_name),
                                           items=items)

        # Empty Cart once SO has been placed
        cart.clear()

        return cart

api_v1.register('/preorders/cart/', PreorderCartDetail)


@marshal_with(ERPItemSchema(many=True))
class ItemList(MethodResource):
    @login_required
    def get(self, **kwargs):
        # Items without variants
        items_no_variant = erp_client.query(ERPItem).list(erp_fields=["name", "description", "item_code", "web_long_description", "standard_rate", "thumbnail"],
                                                          filters=[["Item", "show_in_website", "=", "1"],
                                                                   ["Item", "has_variants", "=", "0"]])

        # Items with variants
        items_variants = erp_client.query(ERPItem).list(erp_fields=["name", "description", "item_code", "web_long_description", "standard_rate", "thumbnail"],
                                               filters=[["Item", "show_variant_in_website", "=", "1"]])

        return items_no_variant + items_variants

api_v1.register('/preorders/items/', ItemList)


class ItemDetail(MethodResource):
    @login_required
    @marshal_with(ERPItemSchema)
    def get(self, name):
        try:
            item = erp_client.query(ERPItem).get(name)
        except ERPItem.DoesNotExist:
            raise NotFound

        return item


    @login_required
    @use_kwargs({'quantity': fields.Int(missing=1)})
    @marshal_with(None, code=201)
    def post(self, name, **kwargs):
        try:
            item = erp_client.query(ERPItem).get(name)
        except ERPItem.DoesNotExist:
            raise NotFound

        # FIXME: Make sure it has "website" flag

        # Add to cart or update quantity
        cart = Cart.from_session()

        quantity = max(0, int(kwargs['quantity']))

        cart.add(Item(item['code'], item['name'], item['price']),
                 quantity=quantity, replace=False)



api_v1.register('/preorders/items/<name>', ItemDetail)


@marshal_with(ERPSalesOrderSchema(many=True))
class UserSalesOrderList(MethodResource):
    @login_required
    def get(self):
        sales_orders = erp_client.query(ERPSalesOrder).list(erp_fields=["name", "grand_total", "title", "customer", "transaction_date"],
                                                            filters=[
                                                                ["Sales Order", "Customer", "=", "Guillaume Libersat"],
                                                                ["Sales Order", "status", "!=", "Cancelled"]],
                                                            schema_fields=['name', 'amount_total', 'title', 'customer', 'transaction_date'])

        return sales_orders

api_v1.register('/preorders/my/', UserSalesOrderList)


@marshal_with(ERPSalesOrderSchema)
class UserSalesOrderDetail(MethodResource):
    @login_required
    def get(self, name):
        try:
            sales_order = erp_client.query(ERPSalesOrder).get(name,
                                                              fields='["name", "title", "grand_total", "customer", "items", "transaction_date"]')
        except ERPSalesOrder.DoesNotExist:
            raise NotFound

        return sales_order

api_v1.register('/preorders/my/<name>/', UserSalesOrderDetail)
