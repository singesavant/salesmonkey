import math
import requests
from salesmonkey import app
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
    ERPBin,
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
        # FIXME OrderNumberGenerator not used?
        num_gen = OrderNumberGenerator()

        # Delete previous shopping cart if prevent
        try:
            current_sales_order = erp_client.query(ERPSalesOrder).first(erp_fields=["name"],
                                                                        filters=[
                                                                            ["Sales Order", "order_type", "=", "Shopping Cart"],
                                                                            ["Sales Order", "docstatus", "=", "0"],
                                                                            ["Sales Order", "customer", "=", session['customer']['name']]
                                                                        ])

            response = erp_client.query(ERPSalesOrder).update(name=current_sales_order['name'], data={'items': items})

        except ERPSalesOrder.DoesNotExist:
            # No previous SO, create a new one

            response = erp_client.create_resource("Sales Order",
                                                  data={'customer': session['customer']['name'],
                                                        'title': "Commande Web {0} {1}".format(current_user.first_name,
                                                                                               current_user.last_name),
                                                        'shipping_rule': app.config['ERPNEXT_SHIPPING_RULE'],
                                                        'naming_series': "SO-WEB-.YY.MM.DD.-.###",
                                                        'order_type': "Shopping Cart",
                                                        'items': items,
                                                        'taxes': []})


        if response.ok:
            # Empty Cart once SO has been placed
            # XXX cart.clear()
            sales_order, errors = ERPSalesOrderSchema(strict=True).load(data=response.json()['data'])

            LOGGER.debug(sales_order)
            # FIXME HARDCODED!
            shipping_cost = 0
            if int(sales_order['amount_total']) < 58:
                shipping_cost = 5


            response = erp_client.update_resource("Sales Order",
                                                  resource_name=sales_order['name'],
                                                  data={'taxes': [{
                                                      "charge_type": "On Net Total",
		                                              "account_head": "4457 - TVA collectée - LSS",
		                                              "description": "TVA 20%",
                                                      "included_in_print_rate": "1",
                                                      "rate": "20"
	                                              },{
                                                      "charge_type": "Actual",
                                                      "account_head": "Frais de Transport - LSS",
                                                      "description": "Livraison",
                                                      "rate": "0",
                                                      "tax_amount": shipping_cost
                                                  }]})

            sales_order, errors = ERPSalesOrderSchema(strict=True).load(data=response.json()['data'])

            return sales_order
        else:
            response.raise_for_error()


api_v1.register('/shop/cart/', CartDetail)


@marshal_with(ERPItemSchema(many=True))
class ItemList(MethodResource):
    @use_kwargs({'item_group': fields.Str()})
    def get(self, **kwargs):
        item_group = kwargs.get('item_group', None)
        print("coinnnn")

        # Items
        items = erp_client.query(ERPItem).list(erp_fields=["name", "description", "has_variants", "item_code", "web_long_description", "standard_rate", "thumbnail"],
                                               filters=[["Item", "show_in_website", "=", "1"],
                                                        ["Item", "is_sales_item", "=", True],
                                                        ["Item", "disabled", "=", False],
                                                        ["Item", "item_group", "=", item_group]])

        return items

api_v1.register('/shop/items/', ItemList)

class ShopItemSchema(ERPItemSchema):
    """
    Item Schema extended with a few calculations
    """
    orderable_qty = fields.String(load_from='orderable_qty')
    variants = fields.Nested("ShopItemSchema", many=True)


class ItemDetail(MethodResource):
    @marshal_with(ShopItemSchema)
    def get(self, name):
        try:
            item = erp_client.query(ERPItem).get(name)

            # Fetch the variants
            if item['has_variants'] is True:
                LOGGER.debug("Fetching variants for {0}".format(item['code']))
                item_variants = erp_client.query(ERPItem).list(erp_fields=["item_code", "name", "standard_rate", "website_image", "website_warehouse"],
                                                               filters=[
                                                                   ["Item", "variant_of", "=", item['code']],
                                                                   ["Item", "is_sales_item", "=", True],
                                                                   ["Item", "show_variant_in_website", "=", True]
                                                               ])
                LOGGER.debug(item_variants)
                item['variants'] = item_variants

                # Fetch variant quantity
                for item_variant in item_variants:
                    bin = erp_client.query(ERPBin).first(erp_fields=["projected_qty"],
                                                         filters=[
                                                             ["Bin", "item_code", "=", item_variant['code']],
                                                             ["Bin", "warehouse", "=", item['website_warehouse']]
                                                         ])
                    item_variant['orderable_qty'] = max(bin['projected_qty'], 0)
                    del item_variant['website_warehouse']

            else:
                # Fetch item qtty
                pass

        except ERPItem.DoesNotExist:
            raise NotFound

        return item


    @login_required
    @use_kwargs({'quantity': fields.Int(missing=1)})
    @marshal_with(None, code=201)
    def post(self, name, **kwargs):
        """
        Add/update a quantity of this item to the Cart
        """
        try:
            item = erp_client.query(ERPItem).get(name)
        except ERPItem.DoesNotExist:
            raise NotFound

        # FIXME: Make sure it has "website" flag

        # Add to cart or update quantity
        cart = Cart.from_session()

        quantity = max(0, int(kwargs['quantity']))

        # FIXME Make sure we don't go over orderable_qty

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
                                                      erp_fields=['name', 'link_name', 'parent', 'parenttype'],
                                                      parent="Contact")


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
                                                      erp_fields=['name', 'link_name', 'parent', 'parenttype'],
                                                      parent="Contact")


        customer = erp_client.query(ERPCustomer).first(filters=[['Customer', 'name', '=', link['link_name']]])


        try:
            sales_order = erp_client.query(ERPSalesOrder).get(name,
                                                              fields='["name", "title", "grand_total", "customer", "items", "transaction_date"]',
                                                              filters=[["Sales Order", "Customer", "=", customer['name']],
                                                                       ["Sales Order", "status", "!=", "Cancelled"]])
        except ERPSalesOrder.DoesNotExist:
            raise NotFound

        return sales_order

api_v1.register('/shop/orders/<name>', UserSalesOrderDetail)

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
                                                      erp_fields=['name', 'link_name', 'parent', 'parenttype'],
                                                      parent="Contact")


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


