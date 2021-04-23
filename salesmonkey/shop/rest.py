import logging
import math
from datetime import date
from random import randint

import requests
import satchless
from erpnext_client.documents import (ERPBin, ERPContact, ERPCustomer,
                                      ERPDynamicLink, ERPItem, ERPItemPrice,
                                      ERPJournalEntry, ERPSalesOrder, ERPUser)
from erpnext_client.schemas import (ERPCustomerSchema, ERPItemSchema,
                                    ERPSalesOrderItemSchema,
                                    ERPSalesOrderSchema)
from flask import session
from flask_apispec import (FlaskApiSpec, MethodResource, marshal_with,
                           use_kwargs)
from flask_login import current_user, login_required
from salesmonkey import app, cache
from webargs import fields
from webargs.flaskparser import use_args
from werkzeug.exceptions import BadRequest, Conflict, Gone, NotFound

from ..erpnext import erp_client
from ..rest import api_v1
from ..schemas import Cart, CartLineSchema, CartSchema, Item
from ..utils import OrderNumberGenerator

LOGGER = logging.getLogger(__name__)


def calculate_shipping_cost(sales_order):
    shipping_cost = 0
    if sales_order["shipping_rule"] == "Emport Brasserie":
        return 0

    if int(sales_order["amount_total"]) < 50:
        shipping_cost = 5

    return shipping_cost


class GiveAway(MethodResource):
    """
    Offer 5% to partner
    """

    @login_required
    @marshal_with(ERPCustomerSchema(many=True))
    @cache.memoize(timeout=10)
    def get(self, name):
        pro_customers = erp_client.query(ERPCustomer).list(
            erp_fields=["*"],
            filters=[
                ["Customer", "customer_group", "in", "Restaurant, Bar"],
            ],
            page_length=1000,
        )

        return pro_customers

    @login_required
    @use_kwargs({"partner_name": fields.Str(required=True)})
    @marshal_with(None, code=204)
    def post(self, name, partner_name):
        sales_order = None

        try:
            sales_order = erp_client.query(ERPSalesOrder).get(name)
        except ERPSalesOrder.DoesNotExist:
            raise NotFound

        # First, check if we don't already have a giveaway for this transaction
        try:
            jv = erp_client.query(ERPJournalEntry).first(
                filters=[
                    ["Journal Entry", "voucher_type", "=", "Credit Note"],
                    ["Journal Entry", "cheque_no", "=", sales_order["name"]],
                ]
            )

            raise BadRequest("Giveaway already made, cheater!")
        except ERPJournalEntry.DoesNotExist:
            pass

        five_pc = float(sales_order["total"]) * 5 / 100.0

        response = erp_client.create_resource(
            "Journal Entry",
            data={
                "docstatus": 1,
                "voucher_type": "Credit Note",
                "title": "CORONA {0} to {1}".format(sales_order["name"], partner_name),
                "posting_date": "{0}".format(date.today()),
                "company": "Le Singe Savant",
                "cheque_no": sales_order["name"],
                "cheque_date": "{0}".format(sales_order["date"]),
                "user_remark": sales_order["customer"],
                "accounts": [
                    {
                        "account": "709700 - Rabais remises et ristournes sur ventes de marchandises - LSS",
                        "debit_in_account_currency": five_pc,
                    },
                    {
                        "account": "411 - Clients - LSS",
                        "party_type": "Customer",
                        "party": partner_name,
                        "credit_in_account_currency": five_pc,
                    },
                ],
            },
        )


api_v1.register("/shop/orders/<name>/giveaway", GiveAway)


class CartDetail(MethodResource):
    """
    User Cart
    """

    @marshal_with(CartSchema)
    def get(self, **kwargs):
        return Cart.from_session()

    @login_required
    @use_kwargs({"item_code": fields.Str()})
    @marshal_with(None, code=204)
    def delete(self, item_code):
        cart = Cart.from_session()

        for idx, cart_line in enumerate(cart):
            if cart_line.product.code == item_code:
                cart.add(
                    cart_line.product, quantity=0, replace=True, check_quantity=False
                )

                return

    @login_required
    @marshal_with(ERPSalesOrderSchema)
    def post(self):
        cart = Cart.from_session()
        if cart.count() <= 0:
            raise BadRequest("Empty cart")

        items = [
            {
                "item_code": line.product.code,
                "qty": line.quantity,
                "warehouse": line.product.warehouse,
            }
            for line in cart
        ]

        # FIXME We should check the quantities!

        # Place SO
        # FIXME OrderNumberGenerator not used?
        num_gen = OrderNumberGenerator()

        # Delete previous shopping cart if prevent
        try:
            current_sales_order = erp_client.query(ERPSalesOrder).first(
                erp_fields=["name"],
                filters=[
                    ["Sales Order", "order_type", "=", "Shopping Cart"],
                    ["Sales Order", "status", "=", "Draft"],
                    ["Sales Order", "customer", "=", session["customer"]["name"]],
                ],
            )

            response = erp_client.query(ERPSalesOrder).update(
                name=current_sales_order["name"], data={"items": items}
            )

        except ERPSalesOrder.DoesNotExist:
            # No previous SO, create a new one

            response = erp_client.create_resource(
                "Sales Order",
                data={
                    "customer": session["customer"]["name"],
                    "title": "Commande Web {0} {1}".format(
                        current_user.first_name, current_user.last_name
                    ),
                    "shipping_rule": app.config["ERPNEXT_SHIPPING_RULE"],
                    "naming_series": "SO-WEB-.YY.MM.DD.-.###",
                    "set_warehouse": "Vente en Ligne - LSS",
                    "order_type": "Shopping Cart",
                    "items": items,
                    "taxes": [],
                },
            )

        if response.ok:
            # Empty Cart once SO has been placed
            # XXX cart.clear()
            sales_order, errors = ERPSalesOrderSchema(strict=True).load(
                data=response.json()["data"]
            )

            shipping_cost = calculate_shipping_cost(sales_order)

            response = erp_client.update_resource(
                "Sales Order",
                resource_name=sales_order["name"],
                data={
                    "taxes": [
                        {
                            "charge_type": "On Net Total",
                            "account_head": "445710 - TVA collectée - LSS",
                            "description": "TVA 20%",
                            "included_in_print_rate": "1",
                            "rate": "20",
                        },
                        {
                            "charge_type": "Actual",
                            "account_head": "7085 - Ports et frais accessoires facturés - LSS",
                            "description": "Livraison",
                            "rate": "0",
                            "tax_amount": shipping_cost,
                        },
                    ]
                },
            )

            sales_order, errors = ERPSalesOrderSchema(strict=True).load(
                data=response.json()["data"]
            )

            return sales_order
        else:
            response.raise_for_error()


api_v1.register("/shop/cart/", CartDetail)


@marshal_with(ERPItemSchema(many=True))
class ItemList(MethodResource):
    @use_kwargs({"item_group": fields.Str()})
    @cache.memoize(timeout=5)
    def get(self, **kwargs):
        item_group = kwargs.get("item_group", None)

        # Items
        items = erp_client.query(ERPItem).list(
            erp_fields=[
                "name",
                "description",
                "has_variants",
                "item_code",
                "web_long_description",
                "standard_rate",
                "thumbnail",
            ],
            filters=[
                ["Item", "show_in_website", "=", "1"],
                ["Item", "is_sales_item", "=", True],
                ["Item", "disabled", "=", False],
                ["Item", "item_group", "=", item_group],
            ],
        )

        return items


api_v1.register("/shop/items/", ItemList)


class ShopItemSchema(ERPItemSchema):
    """
    Item Schema extended with a few calculations
    """

    orderable_qty = fields.String(load_from="orderable_qty")
    variants = fields.Nested("ShopItemSchema", many=True)


class ItemDetail(MethodResource):
    @marshal_with(ShopItemSchema)
    @cache.memoize(timeout=10)
    def get(self, name):
        try:
            item = erp_client.query(ERPItem).get(name)

            # Fetch the variants
            if item["has_variants"] is True:
                LOGGER.debug("Fetching variants for {0}".format(item["code"]))
                item_variants = erp_client.query(ERPItem).list(
                    erp_fields=[
                        "item_code",
                        "name",
                        "standard_rate",
                        "website_image",
                        "website_warehouse",
                    ],
                    filters=[
                        ["Item", "variant_of", "=", item["code"]],
                        ["Item", "is_sales_item", "=", True],
                        ["Item", "show_variant_in_website", "=", True],
                    ],
                )
                LOGGER.debug(item_variants)
                item["variants"] = item_variants

                # Fetch variant quantity
                for item_variant in item_variants:
                    try:
                        bin = erp_client.query(ERPBin).first(
                            erp_fields=["name", "projected_qty"],
                            filters=[
                                ["Bin", "item_code", "=", item_variant["code"]],
                                [
                                    "Bin",
                                    "warehouse",
                                    "=",
                                    item_variant["website_warehouse"],
                                ],
                            ],
                        )

                        item_variant["orderable_qty"] = max(bin["projected_qty"], 0)
                    except ERPBin.DoesNotExist:
                        # If we have no Bin, it means, there was no stock movement there so it equals to zero stock
                        item_variant["orderable_qty"] = 0

                    # Get price for current customer
                    # FIXME: Should lookup current user price group
                    try:
                        variant_price = erp_client.query(ERPItemPrice).first(
                            erp_fields=["price_list_rate"],
                            filters=[
                                ["Item Price", "item_code", "=", item_variant["code"]],
                                ["Item Price", "selling", "=", "1"],
                                [
                                    "Item Price",
                                    "price_list",
                                    "=",
                                    "Tarifs standards TTC",
                                ],
                            ],
                        )

                        item_variant["price"] = variant_price["price_list_rate"]
                    except ERPItemPrice.DoesNotExist:
                        LOGGER.debug(
                            "No price list for Item <{0}>".format(item_variant["code"])
                        )
                        raise BadRequest
            else:
                # Fetch item qtty
                try:
                    bin = erp_client.query(ERPBin).first(
                        erp_fields=["name", "projected_qty"],
                        filters=[
                            ["Bin", "item_code", "=", item["code"]],
                            ["Bin", "warehouse", "=", item["website_warehouse"]],
                        ],
                    )

                    item["orderable_qty"] = max(bin["projected_qty"], 0)
                except ERPBin.DoesNotExist:
                    # If we have no Bin, it means, there was no stock movement there so it equals to zero stock
                    item["orderable_qty"] = 0

        except ERPItem.DoesNotExist:
            raise NotFound

        return item

    @login_required
    @use_kwargs({"quantity": fields.Int(missing=1)})
    @marshal_with(None, code=201)
    def post(self, name, **kwargs):
        """
        Add/update a quantity of this item to the Cart
        """
        try:
            item = erp_client.query(ERPItem).get(name)

            # Get price for current customer
            # FIXME: Should lookup current user price group
            try:
                variant_price = erp_client.query(ERPItemPrice).first(
                    erp_fields=["price_list_rate"],
                    filters=[
                        ["Item Price", "item_code", "=", item["code"]],
                        ["Item Price", "selling", "=", "1"],
                        ["Item Price", "price_list", "=", "Tarifs standards TTC"],
                    ],
                )
                item["price"] = variant_price["price_list_rate"]
            except ERPItemPrice.DoesNotExist:
                LOGGER.debug(
                    "No price list for Item <{0}>".format(item_variant["code"])
                )
                raise NotFound

        except ERPItem.DoesNotExist:
            raise NotFound

        # FIXME: Make sure it has "website" flag

        # Add to cart or update quantity
        cart = Cart.from_session()

        quantity = max(0, int(kwargs["quantity"]))

        LOGGER.debug(item)

        product = Item(
            code=item["code"],
            name=item["name"],
            warehouse=item["website_warehouse"],
            price=item["price"],
        )

        try:
            product.check_quantity(quantity)
            cart.add(product, quantity=quantity, replace=False)
        except satchless.item.InsufficientStock as e:
            quantity = e.item.get_stock()
            cart.add(product, quantity=quantity, replace=True)


api_v1.register("/shop/items/<name>", ItemDetail)


@marshal_with(ERPSalesOrderSchema(many=True))
class UserSalesOrderList(MethodResource):
    @login_required
    def get(self):
        # FIXME duplicate code
        contact = erp_client.query(ERPContact).first(
            filters=[["Contact", "user", "=", current_user.username]],
            erp_fields=["name", "first_name", "last_name"],
        )

        link = erp_client.query(ERPDynamicLink).first(
            filters=[
                ["Dynamic Link", "parenttype", "=", "Contact"],
                ["Dynamic Link", "parent", "=", contact["name"]],
                ["Dynamic Link", "parentfield", "=", "links"],
            ],
            erp_fields=["name", "link_name", "parent", "parenttype"],
            parent="Contact",
        )

        customer = erp_client.query(ERPCustomer).first(
            filters=[["Customer", "name", "=", link["link_name"]]]
        )

        sales_orders = erp_client.query(ERPSalesOrder).list(
            erp_fields=["name", "grand_total", "title", "customer", "transaction_date"],
            filters=[
                ["Sales Order", "Customer", "=", customer["name"]],
                ["Sales Order", "status", "!=", "Cancelled"],
            ],
            schema_fields=[
                "name",
                "amount_total",
                "title",
                "customer",
                "transaction_date",
            ],
        )

        return sales_orders


api_v1.register("/shop/orders/", UserSalesOrderList)


@marshal_with(ERPSalesOrderSchema)
class UserSalesOrderDetail(MethodResource):
    @login_required
    @use_kwargs({"update_qttys": fields.Boolean(missing=False)})
    def get(self, name, update_qttys):
        # FIXME duplicate code
        contact = erp_client.query(ERPContact).first(
            filters=[["Contact", "user", "=", current_user.username]],
            erp_fields=["name", "first_name", "last_name"],
        )

        link = erp_client.query(ERPDynamicLink).first(
            filters=[
                ["Dynamic Link", "parenttype", "=", "Contact"],
                ["Dynamic Link", "parent", "=", contact["name"]],
                ["Dynamic Link", "parentfield", "=", "links"],
            ],
            erp_fields=["name", "link_name", "parent", "parenttype"],
            parent="Contact",
        )

        customer = erp_client.query(ERPCustomer).first(
            filters=[["Customer", "name", "=", link["link_name"]]]
        )

        try:
            sales_order = erp_client.query(ERPSalesOrder).get(
                name,
                fields='["name", "title", "grand_total", "customer", "items", "transaction_date"]',
                filters=[
                    ["Sales Order", "Customer", "=", customer["name"]],
                    ["Sales Order", "status", "!=", "Cancelled"],
                ],
            )

            if update_qttys:
                LOGGER.debug("Checking stocks !")

                need_updating = False

                updated_items = []

                for item in sales_order["items"]:
                    # XXX Hardcoded cateogry group!
                    if (item["item_group"] != "BrewLab") and (
                        item["projected_qty"] < item["quantity"]
                    ):
                        new_qtty = max(0, item["projected_qty"])
                        need_updating = True
                    else:
                        new_qtty = item["quantity"]

                    if new_qtty > 0:
                        updated_items.append(
                            {"item_code": item["item_code"], "qty": new_qtty}
                        )

                if need_updating == True:
                    # We delete our SO since nothing is available anymore
                    if len(updated_items) == 0:
                        erp_client.query(ERPSalesOrder).delete(name)
                        # Empty Cart
                        cart = Cart.from_session()
                        cart.clear()
                        raise Gone

                    LOGGER.debug(
                        "Updating SO <{0}> since we are out of stock on some items".format(
                            name
                        )
                    )

                    # Update SO
                    response = erp_client.query(ERPSalesOrder).update(
                        name, data={"items": updated_items}
                    )

                    sales_order, errors = ERPSalesOrderSchema(strict=True).load(
                        data=response.json()["data"]
                    )
                    LOGGER.debug(sales_order)

                    # FIXME HARDCODED!
                    shipping_cost = calculate_shipping_cost(sales_order)

                    response = erp_client.update_resource(
                        "Sales Order",
                        resource_name=sales_order["name"],
                        data={
                            "taxes": [
                                {
                                    "charge_type": "On Net Total",
                                    "account_head": "445710 - TVA collectée - LSS",
                                    "description": "TVA 20%",
                                    "included_in_print_rate": "1",
                                    "rate": "20",
                                },
                                {
                                    "charge_type": "Actual",
                                    "account_head": "7085 - Ports et frais accessoires facturés - LSS",
                                    "description": "Livraison",
                                    "rate": "0",
                                    "tax_amount": shipping_cost,
                                },
                            ]
                        },
                    )

                    sales_order, errors = ERPSalesOrderSchema(strict=True).load(
                        data=response.json()["data"]
                    )

                    # Update Cart based on new SO
                    cart = Cart.from_session()
                    cart.clear()

                    for item in sales_order["items"]:
                        cart.add(
                            Item(
                                code=item["item_code"],
                                name=item["item_name"],
                                warehouse=item["warehouse"],
                                price=item["rate"],
                            ),
                            quantity=item["quantity"],
                            check_quantity=False,
                        )

                    raise Conflict

        except ERPSalesOrder.DoesNotExist:
            raise NotFound

        return sales_order


api_v1.register("/shop/orders/<name>", UserSalesOrderDetail)

# -- Shipping Method
class UserSalesOrderShippingMethod(MethodResource):
    @login_required
    def get(self, name):
        """
        Retrieve the shipping method
        """
        # FIXME duplicate code
        contact = erp_client.query(ERPContact).first(
            filters=[["Contact", "user", "=", current_user.username]],
            erp_fields=["name", "first_name", "last_name"],
        )

        link = erp_client.query(ERPDynamicLink).first(
            filters=[
                ["Dynamic Link", "parenttype", "=", "Contact"],
                ["Dynamic Link", "parent", "=", contact["name"]],
                ["Dynamic Link", "parentfield", "=", "links"],
            ],
            erp_fields=["name", "link_name", "parent", "parenttype"],
            parent="Contact",
        )

        customer = erp_client.query(ERPCustomer).first(
            filters=[["Customer", "name", "=", link["link_name"]]]
        )

        try:
            sales_order = erp_client.query(ERPSalesOrder).get(
                name,
                fields='["name", "title", "grand_total", "customer", "items", "transaction_date"]',
                filters=[
                    ["Sales Order", "Customer", "=", customer["name"]],
                    ["Sales Order", "status", "!=", "Cancelled"],
                ],
            )
        except ERPSalesOrder.DoesNotExist:
            raise NotFound

        if sales_order["customer"] != customer["name"]:
            raise NotFound

        return sales_order

    @login_required
    @use_kwargs({"shipping_method": fields.String(required=True)})
    def post(self, name, shipping_method):
        """
        Set the shipping method
        """
        customer = session.get("customer", None)
        if not customer:
            raise NotFound

        if shipping_method not in ("drive", "shipping"):
            raise NotAllowed

        try:
            sales_order = erp_client.query(ERPSalesOrder).get(name)
        except ERPSalesOrder.DoesNotExist:
            raise NotFound

        if sales_order["status"] != "Draft":
            raise NotAllowed

        try:
            erp_shipping_rule = {
                "drive": "Emport Brasserie",
                "shipping": "Livraison Centre Lille",
            }[shipping_method]
        except KeyError:
            raise NotAllowed

        sales_order["shipping_rule"] = erp_shipping_rule
        shipping_cost = calculate_shipping_cost(sales_order)

        taxes = [
            {
                "charge_type": "On Net Total",
                "account_head": "445710 - TVA collectée - LSS",
                "description": "TVA 20%",
                "included_in_print_rate": "1",
                "rate": "20",
            },
            {
                "charge_type": "Actual",
                "account_head": "7085 - Ports et frais accessoires facturés - LSS",
                "description": "Livraison",
                "rate": "0",
                "tax_amount": shipping_cost,
            },
        ]

        erp_client.query(ERPSalesOrder).update(
            name, {"shipping_rule": erp_shipping_rule, "taxes": taxes}
        )

        return erp_client.query(ERPSalesOrder).get(name)


api_v1.register("/shop/orders/<name>/shipping", UserSalesOrderShippingMethod)
