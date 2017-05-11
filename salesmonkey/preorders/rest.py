import requests
from werkzeug.exceptions import NotFound, BadRequest

from flask_apispec import (
    FlaskApiSpec,
    marshal_with,
    MethodResource
)

from ..schemas import (
    ERPItemSchema, ERPSalesOrderSchema,
    ERPSalesOrderItemSchema,
    CartSchema,
    CartLineSchema
)

from ..erpnext import erp_client
from ..erpnext import (
    ERPItem,
    ERPSalesOrder
)

from ..schemas import Cart, Item
from ..rest import api_v1
from ..utils import OrderNumberGenerator


@marshal_with(CartSchema)
class PreorderCartDetail(MethodResource):
    def get(self, **kwargs):
        return Cart.from_session()

    def post(self):
        cart = Cart.from_session()
        if cart.count() <= 0:
            raise BadRequest("Empty cart")

        items = [{'item_code': line.product.code, 'qty': line.quantity} for line in cart]

        # Place SO
        num_gen = OrderNumberGenerator()
        so = erp_client.create_sales_order(customer="Guillaume Libersat",
                                           order_type="Shopping Cart",
                                           title="Préco {0}".format(num_gen.generate(cart)),
                                           items=items)

        # Empty Cart once SO has been placed
        cart.clear()

api_v1.register('/preorders/cart/', PreorderCartDetail)


@marshal_with(ERPItemSchema(many=True))
class ItemList(MethodResource):
    def get(self, **kwargs):
        items = erp_client.query(ERPItem).list(fields=["name", "description", "item_code", "web_long_description", "standard_rate", "thumbnail"],
                                               filters=[["Item", "show_variant_in_website", "=", "1"]])

        return items.json()['data']

api_v1.register('/preorders/items/', ItemList)


@marshal_with(ERPItemSchema)
class ItemDetail(MethodResource):
    def get(self, name):
        item = erp_client.query(ERPItem).get(name)

        return item.json()['data']

    def post(self, name):
        try:
            item = erp_client.query(ERPItem).get(name)
        except requests.exceptions.HTTPError:
            raise NotFound

        # FIXME: Make sure it has "website" flag

        # Add to cart or update quantity
        cart = Cart.from_session()

        data = item.json()['data']

        cart.add(Item(data['item_code'], data['item_name']))

        return data


api_v1.register('/preorders/items/<name>', ItemDetail)



@marshal_with(ERPSalesOrderSchema(many=True))
class UserSalesOrderList(MethodResource):
    def get(self):
        so = erp_client.query(ERPSalesOrder).list(fields=["name", "grand_total", "title", "customer"],
                                                  filters=[
                                                      ["Sales Order", "Customer", "=", "Guillaume Libersat"],
                                                      ["Sales Order", "status", "!=", "Cancelled"]])

        return so.json()['data']

api_v1.register('/preorders/my/', UserSalesOrderList)


@marshal_with(ERPSalesOrderSchema)
class UserSalesOrderDetail(MethodResource):
    def get(self, name):
        so = erp_client.get_sales_order(name, fields='["name", "title", "customer", "items", "transaction_date"]')

        return so.json()['data']

api_v1.register('/preorders/my/<name>/', UserSalesOrderDetail)
