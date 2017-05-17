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
            response = self.client.get_resource(self.doctype, name, fields=[])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise self.DoesNotExist()
            else:
                reponse.raise_for_status()

        return self.schema().load(data=response.json()['data'])

    def list(self, fields=[], filters=[]):
        try:
            response = self.client.list_resource(self.doctype,
                                                 fields=fields,
                                                 filters=filters)
        except requests.exceptions.HTTPError as e:
            reponse.raise_for_status()

        return self.schema().load(data=response.json()['data'], many=True)


class ERPItem(ERPResource):
    doctype = "Item"
    schema = ERPItemSchema


class ERPCustomer(ERPResource):
    doctype = "Customer"
    schema = ERPCustomerSchema


class ERPSalesOrder(ERPResource):
    doctype = "Sales Order"
    schema = ERPSalesOrderSchema
