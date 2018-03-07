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

from flask import session

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

class CartDetail(MethodResource):
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



    @login_required
    @marshal_with(ERPSalesOrderSchema)
    def post(self):
        cart = Cart.from_session()
        if cart.count() <= 0:
            raise BadRequest("Empty cart")

        items = [{'item_code': line.product.code, 'qty': line.quantity} for line in cart]

        # FIXME We should check the quantities!

        # Place SO
        num_gen = OrderNumberGenerator()
        response = erp_client.create_sales_order(customer=session['customer']['name'],
                                                 order_type="Shopping Cart",
                                                 naming_series="SO-WEB-.YY.MM.DD.-.###",
                                                 title="Commande Web {0} {1}".format(current_user.first_name,
                                                                                     current_user.last_name),
                                                 items=items)

        if response.ok:
            # Empty Cart once SO has been placed
            cart.clear()
            sales_order = response.json()['data']
            return sales_order
        else:
            response.raise_for_error()


api_v1.register('/shop/cart/', CartDetail)


@marshal_with(ERPItemSchema(many=True))
class ItemList(MethodResource):
    @use_kwargs({'item_group': fields.Str()})
    def get(self, **kwargs):
        item_group = kwargs.get('item_group', None)

        # Items without variants
        items = erp_client.query(ERPItem).list(erp_fields=["name", "description", "has_variants", "item_code", "web_long_description", "standard_rate", "thumbnail"],
                                               filters=[["Item", "show_in_website", "=", "1"],
                                                        ["Item", "is_sales_item", "=", True],
                                                        ["Item", "disabled", "=", False],
                                                        ["Item", "item_group", "=", item_group]])

        # Items with variants
        # items_variants = erp_client.query(ERPItem).list(erp_fields=["name", "description", "item_code", "web_long_description", "standard_rate", "thumbnail"],
        #                                                filters=[["Item", "show_variant_in_website", "=", "1"],
        #                                                         ["Item", "item_group", "=", item_group]])

        return items

api_v1.register('/shop/items/', ItemList)


class ItemDetail(MethodResource):
    @marshal_with(ERPItemSchema)
    def get(self, name):
        try:
            item = erp_client.query(ERPItem).get(name)
            # Fetch the variants
            if item['has_variants'] is True:
                item_variants = erp_client.query(ERPItem).list(erp_fields=["name", "standard_rate", "total_projected_qty", "website_image"],
                                                               filters=[
                                                                   ["Item", "variant_of", "=", item['name']],
                                                                   ["Item", "is_sales_item", "=", True],
                                                                   ["Item", "show_variant_in_website", "=", True]
                                                               ])
                item['variants'] = item_variants

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



api_v1.register('/shop/items/<name>', ItemDetail)


@marshal_with(ERPSalesOrderSchema(many=True))
class UserSalesOrderList(MethodResource):
    @login_required
    def get(self):
        # FIXME duplicate code
        contact = erp_client.query(ERPContact).first(filters=[['Contact', 'user', '=', current_user.username]],
                                                     erp_fields=['name', 'first_name', 'last_name'])

        link = erp_client.query(ERPDynamicLink).first(filters=[['Dynamic Link', 'parenttype', '=', 'Contact'],
                                                               ['Dynamic Link', 'parent', '=', contact['name']],
                                                               ['Dynamic Link', 'parentfield', '=', 'links']],
                                                      erp_fields=['name', 'link_name', 'parent', 'parenttype'])


        customer = erp_client.query(ERPCustomer).first(filters=[['Customer', 'name', '=', link['link_name']]])

        sales_orders = erp_client.query(ERPSalesOrder).list(erp_fields=["name", "grand_total", "title", "customer", "transaction_date"],
                                                            filters=[
                                                                ["Sales Order", "Customer", "=", customer['name']],
                                                                ["Sales Order", "status", "!=", "Cancelled"]],
                                                            schema_fields=['name', 'amount_total', 'title', 'customer', 'transaction_date'])

        return sales_orders

api_v1.register('/shop/orders/', UserSalesOrderList)


@marshal_with(ERPSalesOrderSchema)
class UserSalesOrderDetail(MethodResource):
    @login_required
    def get(self, name):
        # FIXME duplicate code
        contact = erp_client.query(ERPContact).first(filters=[['Contact', 'user', '=', current_user.username]],
                                                     erp_fields=['name', 'first_name', 'last_name'])

        link = erp_client.query(ERPDynamicLink).first(filters=[['Dynamic Link', 'parenttype', '=', 'Contact'],
                                                               ['Dynamic Link', 'parent', '=', contact['name']],
                                                               ['Dynamic Link', 'parentfield', '=', 'links']],
                                                      erp_fields=['name', 'link_name', 'parent', 'parenttype'])


        customer = erp_client.query(ERPCustomer).first(filters=[['Customer', 'name', '=', link['link_name']]])


        try:
            sales_order = erp_client.query(ERPSalesOrder).get(name,
                                                              fields='["name", "title", "grand_total", "customer", "items", "transaction_date"]',
                                                              filters=[["Sales Order", "Customer", "=", customer['name']],
                                                                       ["Sales Order", "status", "!=", "Cancelled"]])
        except ERPSalesOrder.DoesNotExist:
            raise NotFound

        return sales_order

api_v1.register('/shop/orders/<name>/', UserSalesOrderDetail)

#-- Shipping Method
class UserSalesOrderShippingMethod(MethodResource):
    @login_required
    def get(self, name):
        """
        Retrieve the shipping method
        """
        # FIXME duplicate code
        contact = erp_client.query(ERPContact).first(filters=[['Contact', 'user', '=', current_user.username]],
                                                     erp_fields=['name', 'first_name', 'last_name'])

        link = erp_client.query(ERPDynamicLink).first(filters=[['Dynamic Link', 'parenttype', '=', 'Contact'],
                                                               ['Dynamic Link', 'parent', '=', contact['name']],
                                                               ['Dynamic Link', 'parentfield', '=', 'links']],
                                                      erp_fields=['name', 'link_name', 'parent', 'parenttype'])


        customer = erp_client.query(ERPCustomer).first(filters=[['Customer', 'name', '=', link['link_name']]])


        try:
            sales_order = erp_client.query(ERPSalesOrder).get(name,
                                                              fields='["name", "title", "grand_total", "customer", "items", "transaction_date"]',
                                                              filters=[["Sales Order", "Customer", "=", customer['name']],
                                                                       ["Sales Order", "status", "!=", "Cancelled"]])
        except ERPSalesOrder.DoesNotExist:
            raise NotFound

        return sales_order

    @login_required
    def post(self, name):
        """
        Set the shipping method
        """
        pass

api_v1.register('/shop/orders/<name>/shipping', UserSalesOrderShippingMethod)


