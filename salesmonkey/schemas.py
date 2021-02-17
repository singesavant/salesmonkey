from flask import session

import satchless.item
import satchless.cart

from erpnext_client.documents import ERPItem, ERPBin

from salesmonkey import ma

from .erpnext import erp_client

import logging

LOGGER = logging.getLogger(__name__)


class Item(satchless.item.StockedItem):
    def __init__(self, code, name, warehouse, price=0):
        self.code = code
        self.name = name
        self.warehouse = warehouse
        self.price = float(price)

    def __eq__(self, otherItem):
        return self.code == otherItem.code

    def get_price(self):
        return self.price

    def get_stock(self):
        item = erp_client.query(ERPItem).get(self.code)

        try:
            bin = erp_client.query(ERPBin).first(
                erp_fields=["projected_qty"],
                filters=[
                    ["Bin", "item_code", "=", self.code],
                    ["Bin", "warehouse", "=", self.warehouse],
                ],
            )
        except ERPBin.DoesNotExist:
            # No warehouse entry equals ZERO stock
            return 0

        return max(bin["projected_qty"], 0)


class ItemSchema(ma.Schema):
    code = ma.String()
    name = ma.String()
    warehouse = ma.String()
    price = ma.Float()


class CartLineSchema(ma.Schema):
    product = ma.Nested(ItemSchema)
    quantity = ma.Integer()
    warehouse = ma.String()
    line_price = ma.Method("get_line_price", deserialize="load_line_price")

    def get_line_price(self, obj):
        return obj.get_total()

    def load_line_price(self, value):
        return float(value)


class Cart(satchless.cart.Cart):
    @staticmethod
    def from_session():
        cart = session.get("cart", None)
        if cart is None:
            session["cart"] = Cart()

        return session.get("cart")

    @property
    def items(self):
        return list(self)


class CartSchema(ma.Schema):
    items = ma.Nested(CartLineSchema, many=True)
    grand_total = ma.Method("get_grand_total", deserialize="load_grand_total")

    def get_grand_total(self, obj):
        return obj.get_total()

    def load_grand_total(self, value):
        return float(value)
