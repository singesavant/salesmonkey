from flask_apispec import (
    FlaskApiSpec,
    marshal_with,
    MethodResource
)

from ..schemas import (
    ERPItemSchema, ERPSalesOrderSchema,
    ERPSalesOrderItemSchema,
    CartSchema,
    CartItemSchema
)

from ..erpnext import erp_client
from ..erpnext import (
    ERPItem,
    ERPSalesOrder
)

from ..schemas import Cart
from ..rest import api_v1

@marshal_with(CartSchema)
class PreorderCart(MethodResource):
    def get(self, **kwargs):
        return Cart.from_session()

api_v1.register('/preorders/cart/', PreorderCart)


@marshal_with(ERPItemSchema(many=True))
class ItemList(MethodResource):
    def get(self, **kwargs):
        items = erp_client.query(ERPItem).list(fields=["name", "description", "item_code", "web_long_description", "standard_rate", "thumbnail"],
                                               filters=[["Item", "show_variant_in_website", "=", "1"]])

        return items.json()['data']

api_v1.register('/preorders/items/', ItemList)

@marshal_with(ERPItemSchema)
class Item(MethodResource):
    def get(self, name):
        item = erp_client.query(ERPItem).get(name)

        return item.json()['data']

api_v1.register('/preorders/items/<name>', Item)



@marshal_with(ERPSalesOrderSchema(many=True))
class UserSalesOrderList(MethodResource):
    def get(self):
        so = erp_client.query(ERPSalesOrder).list(fields=["name", "title", "customer"],
                                                  filters=[
                                                      ["Sales Order", "Customer", "=", "Guillaume Libersat"],
                                                      ["Sales Order", "status", "!=", "Cancelled"]])

        return so.json()['data']

    def post(self):
        x = erp_client.create_sales_order(customer="Guillaume Libersat",
                                          order_type="Shopping Cart",
                                          items=[{"item_code": "Hop Shot-75CL",
                                                  "qty": 0}])

api_v1.register('/preorders/my/', UserSalesOrderList)

@marshal_with(ERPSalesOrderSchema)
class UserSalesOrder(MethodResource):
    def get(self, name):
        x = erp_client.get_sales_order(name, fields='["name", "title", "customer", "items", "transaction_date"]')

        return x.json()['data']

api_v1.register('/preorders/my/<name>/', UserSalesOrder)

