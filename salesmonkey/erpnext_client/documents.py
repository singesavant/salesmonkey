import requests

from .schemas import (
    ERPItemSchema,
    ERPItemGroupSchema,
    ERPSalesOrderSchema,
    ERPCustomerSchema,
    ERPUserSchema,
    ERPContactSchema,
    ERPDynamicLinkSchema,
    ERPBinSchema,
    ERPWebsiteSlideshow,
    ERPWebsiteSlideshowItem
)


class ERPResource:
    class DoesNotExist(Exception):
        """
        When an object isn't found on the server
        """
        pass

    def __init__(self, aERPNextClient):
        self.client = aERPNextClient

    def get(self, name, fields=[], filters=[]):
        try:
            response = self.client.get_resource(self.doctype, name, fields, filters)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise self.DoesNotExist()
            else:
                e.response.raise_for_status()

        instance, errors = self.schema(strict=True).load(data=response.json()['data'])

        return instance

    def list(self, erp_fields=[], filters=[], schema_fields=None):
        """
        Return a list of documents matching the given criterias
        """
        try:
            response = self.client.list_resource(self.doctype,
                                                 fields=erp_fields,
                                                 filters=filters)
        except requests.exceptions.HTTPError as e:
            print(e.response.text)
            e.response.raise_for_status()


        instances, errors = self.schema(partial=schema_fields,
                                        many=True).load(data=response.json()['data'])

        return instances

    def first(self, erp_fields=[], filters=[], schema_fields=None):
        """
        Return first document matching criteras
        """
        documents = self.list(erp_fields, filters, schema_fields)
        if len(documents) == 0:
            raise self.DoesNotExist

        return documents[0]

    def create(self, data):
        """
        Create a document of the current type with given data
        """
        try:
            response = self.client.create_resource(self.doctype, data)
        except requests.exceptions.HTTPError as e:
            e.response.raise_for_status()

        instance, errors = self.schema(strict=True).load(data=response.json()['data'])

        return instance


class ERPDynamicLink(ERPResource):
    doctype = "Dynamic Link"
    schema = ERPDynamicLinkSchema


class ERPItem(ERPResource):
    doctype = "Item"
    schema = ERPItemSchema


class ERPBin(ERPResource):
    doctype = "Bin"
    schema = ERPBinSchema


class ERPItemGroup(ERPResource):
    doctype = "Item Group"
    schema = ERPItemGroupSchema


class ERPCustomer(ERPResource):
    doctype = "Customer"
    schema = ERPCustomerSchema


class ERPContact(ERPResource):
    doctype = "Contact"
    schema = ERPContactSchema


class ERPSalesOrder(ERPResource):
    doctype = "Sales Order"
    schema = ERPSalesOrderSchema


class ERPUser(ERPResource):
    doctype = "User"
    schema = ERPUserSchema

class ERPWebsiteSlideshow(ERPResource):
    doctype = "Website Slideshow"
    schema = ERPWebsiteSlideshow


class ERPWebsiteSlideshowItem(ERPResource):
    doctype = "Website Slideshow Item"
    schema = ERPWebsiteSlideshowItem


