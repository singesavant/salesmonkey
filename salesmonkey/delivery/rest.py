import logging

from werkzeug.exceptions import (
    NotFound
)

from flask_apispec import (
    marshal_with,
    MethodResource,
    use_kwargs
)

from erpnext_client.documents import (
    ERPDeliveryTrip,
    ERPContact,
    ERPAddress
)

from erpnext_client.schemas import (
    ERPDeliveryTripSchema,
    ERPDeliveryStopSchema,
    ERPContactSchema,
    ERPAddressSchema
)

from webargs import fields

from salesmonkey import cache

from ..rest import api_v1
from ..erpnext import erp_client

LOGGER = logging.getLogger(__name__)

class DeliveryStopWithContactSchema(ERPDeliveryStopSchema):
    contact = fields.Nested("ERPContactSchema")
    address = fields.Nested("ERPAddressSchema")

class DeliveryTripWithContactSchema(ERPDeliveryTripSchema):
    stops = fields.Nested("DeliveryStopWithContactSchema", load_from="delivery_stops", many=True)

class DeliveryTrip(MethodResource):
    """
    Help Delivery by giving customer infos and gmap trip
    """

    @cache.memoize(timeout=3600)
    def _get_contact_info(self, contact_name):
        return erp_client.query(ERPContact).get(contact_name)

    @cache.memoize(timeout=3600)
    def _get_address_info(self, address_name):
        return erp_client.query(ERPAddress).get(address_name)


    @marshal_with(DeliveryTripWithContactSchema)
    @cache.memoize(timeout=1)
    def get(self, name):
        try:
            trip = erp_client.query(ERPDeliveryTrip).get(name)
        except ERPDeliveryTrip.DoesNotExist:
            raise NotFound

        for stop in trip['stops']:
            full_contact = self._get_contact_info(stop['contact'])
            stop['address'] = self._get_address_info(stop['address'])
            stop['contact'] = full_contact

        return trip


api_v1.register('/delivery/trip/<name>', DeliveryTrip)
