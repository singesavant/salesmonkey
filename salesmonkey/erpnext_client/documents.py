import requests

from .schemas import (
    ERPItemSchema,
    ERPSalesOrderSchema,
    ERPCustomerSchema
)


class ERPResource:
    class DoesNotExist(Exception):
        """
        When an object isn't found on the server
        """
        pass

    def __init__(self, aERPNextClient):
        self.client = aERPNextClient

    def get(self, name, fields=[]):
        try:
            response = self.client.get_resource(self.doctype, name, fields)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise self.DoesNotExist()
            else:
                response.raise_for_status()

        instance, errors = self.schema(strict=True).load(data=response.json()['data'])

        return instance

    def list(self, erp_fields=[], filters=[], schema_fields=None):
        try:
            response = self.client.list_resource(self.doctype,
                                                 fields=erp_fields,
                                                 filters=filters)
        except requests.exceptions.HTTPError as e:
            e.response.raise_for_status()

        instances, errors = self.schema(partial=schema_fields,
                                        many=True).load(data=response.json()['data'])

        return instances


class ERPItem(ERPResource):
    doctype = "Item"
    schema = ERPItemSchema


class ERPCustomer(ERPResource):
    doctype = "Customer"
    schema = ERPCustomerSchema


class ERPSalesOrder(ERPResource):
    doctype = "Sales Order"
    schema = ERPSalesOrderSchema
