from datetime import date, datetime, timedelta
import logging

import geocoder

from werkzeug.exceptions import NotFound

from flask_apispec import marshal_with, MethodResource, use_kwargs

from erpnext_client.documents import (
    ERPContact,
    ERPAddress,
    ERPCustomer,
    ERPDeliveryNote,
)

from erpnext_client.schemas import (
    Schema,
    fields,
    ERPCustomerSchema,
    ERPContactSchema,
    ERPAddressSchema,
    ERPDeliveryNoteSchema,
)

from salesmonkey import cache
from salesmonkey import app

from ..rest import api_v1
from ..erpnext import erp_client

LOGGER = logging.getLogger(__name__)


class DealerReferenceSchema(Schema):
    name = fields.Str()
    kind = fields.Str()


class DealerSchema(Schema):
    name = fields.Str()
    address = fields.Str()
    spot_type = fields.Str()
    position_lat = fields.Float()
    position_lng = fields.Float()
    references = fields.Nested(DealerReferenceSchema)


@marshal_with(DealerSchema(many=True))
class DealerList(MethodResource):
    """
    List dealers
    """

    @cache.memoize(timeout=30)
    def _get_customer(self, name):
        return erp_client.query(ERPCustomer).get(name=name)

    @cache.memoize(timeout=60 * 60 * 12)
    def get(self):
        three_months_ago = date.today() - timedelta(days=90)
        dealer_list = {}
        try:
            delivery_list = erp_client.query(ERPDeliveryNote).list(
                erp_fields=[
                    "customer_name",
                    "customer",
                    "customer_group",
                    "shipping_address",
                ],
                filters=[
                    [
                        "Delivery Note",
                        "customer_group",
                        "in",
                        "Bar, Cave et Épicerie, Restaurant",
                    ],
                    [
                        "Delivery Note",
                        "posting_date",
                        ">=",
                        three_months_ago.strftime("%Y-%m-%d"),
                    ],
                    ["Delivery Note", "status", "!=", "Cancelled"],
                ],
                page_length=100,
            )
        except ERPDeliveryNote.DoesNotExist:
            raise NotFound

        for delivery in delivery_list:
            if delivery["customer_name"] not in dealer_list:
                customer = self._get_customer(name=delivery["customer"])
                dealer = DealerSchema()
                dealer.name = customer["name"]
                dealer.spot_type = delivery["customer_group"]

                if "shipping_address" in delivery:
                    txt_address = (
                        delivery["shipping_address"]
                        .replace("<br>", ", ")
                        .replace("\n", "")
                        .rstrip(", ")
                    )

                    # Forward geocode address
                    try:
                        geocoding = geocoder.google(
                            txt_address, key=app.config["GOOGLE_API_MAPS_KEY"]
                        )
                        if geocoding.ok:
                            dealer.position_lat = geocoding.lat
                            dealer.position_lng = geocoding.lng
                    except Exception:
                        pass

                    dealer.address = txt_address

                dealer_list[dealer.name] = dealer

        return [d for d in dealer_list.values()]


api_v1.register("/dealers/", DealerList)
