import requests
from werkzeug.exceptions import NotFound, BadRequest

from flask_apispec import (
    FlaskApiSpec,
    marshal_with,
    MethodResource
)

from ..erpnext_client.schemas import (
    ERPItemSchema,
    ERPSalesOrderSchema,
    ERPSalesOrderItemSchema
)
from ..erpnext_client.documents import (
    ERPItem,
    ERPSalesOrder
)

from ..schemas import (
    CartSchema,
    CartLineSchema,
    Cart, Item
)

from ..erpnext import erp_client
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
                                           naming_series="SO-WEB-.YY.MM.DD.-.###",
                                           title="Préco Web Guillaume Libersat",
                                           items=items)

        # Empty Cart once SO has been placed
        cart.clear()

api_v1.register('/preorders/cart/', PreorderCartDetail)


@marshal_with(ERPItemSchema(many=True))
class ItemList(MethodResource):
    def get(self, **kwargs):
        items = erp_client.query(ERPItem).list(fields=["name", "description", "item_code", "web_long_description", "standard_rate", "thumbnail"],
                                               filters=[["Item", "show_variant_in_website", "=", "1"]])

        return items

api_v1.register('/preorders/items/', ItemList)



class ItemDetail(MethodResource):
    @marshal_with(ERPItemSchema)
    def get(self, name):
        try:
            item = erp_client.query(ERPItem).get(name)
        except ERPItem.DoesNotExist:
            raise NotFound

        return item

    @marshal_with(CartSchema)
    def post(self, name):
        try:
            item = erp_client.query(ERPItem).get(name)
        except ERPItem.DoesNotExist:
            raise NotFound

        # FIXME: Make sure it has "website" flag

        # Add to cart or update quantity
        cart = Cart.from_session()

        cart.add(Item(item.code, item.name))

        return cart


api_v1.register('/preorders/items/<name>', ItemDetail)



@marshal_with(ERPSalesOrderSchema(many=True))
class UserSalesOrderList(MethodResource):
    def get(self):
        sales_orders = erp_client.query(ERPSalesOrder).list(fields=["name", "grand_total", "title", "customer"],
                                                            filters=[
                                                                ["Sales Order", "Customer", "=", "Guillaume Libersat"],
                                                                ["Sales Order", "status", "!=", "Cancelled"]])

        return sales_orders

api_v1.register('/preorders/my/', UserSalesOrderList)


@marshal_with(ERPSalesOrderSchema)
class UserSalesOrderDetail(MethodResource):
    def get(self, name):
        try:
            sales_order = erp_client.query(ERPSalesOrder).get(name,
                                                              fields='["name", "title", "customer", "items", "transaction_date"]')
        except ERPSalesOrder.DoesNotExist:
            raise NotFound

        return sales_order

api_v1.register('/preorders/my/<name>/', UserSalesOrderDetail)
