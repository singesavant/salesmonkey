import datetime
import json
import logging
import requests

LOGGER = logging.getLogger(__name__)


class ERPNextClient:
    def __init__(self, host, username, password):
        self.username = username
        self.host = host
        self.password = password

        self.session = requests.Session()

        self.api_root = "https://{0}/api/".format(self.host)

    def _post(self, path, data={}):
        if data is not {}:
            LOGGER.debug("POST payload: {0}".format(data))
        r = self.session.post("{0}{1}".format(self.api_root,
                                              path),
                              data=data)

        if r.status_code != requests.codes.ok:
            LOGGER.error(r.text)
            r.raise_for_status()

        return r

    def _get(self, path, params={}):
        r = self.session.get("{0}{1}".format(self.api_root,
                                             path),
                             params=params)
        if r.status_code != requests.codes.ok:
            r.raise_for_status()

        return r

    def login(self):
        r = self._post("method/login", data={'usr': self.username,
                                             'pwd': self.password})

        return (r.status_code == requests.codes.ok)

    def get_credentials(self):
        r = self._get("method/frappe.auth.get_logged_user")
        if r.status_code == requests.codes.ok:
            return r.json()
        else:
            return None

    def query(self, aERPResource):
        return aERPResource(self)

    def list_resource(self, resource_type_name, fields=[], filters=[]):
        params = {"fields": json.dumps(fields),
                  "filters": json.dumps(filters)}

        return self._get("resource/{0}".format(resource_type_name), params)

    def get_resource(self, resource_type_name, resource_name, fields=[]):
        params = {"fields": fields}
        return self._get("resource/{0}/{1}".format(resource_type_name,
                                                   resource_name),
                         params=params)

    def create_resource(self, resource_type_name, data):
        encapsulated_data = {'data': json.dumps(data)}
        return self._post("resource/{0}".format(resource_type_name),
                          encapsulated_data)

    def create_sales_order(self, customer, items, title=None, order_type="Sales", naming_series="SO-", date=None):
        if date is None:
            date = "2017-05-10"

        return self.create_resource("Sales Order",
                                    data={'customer': customer,
                                          'title': title,
                                          'naming_series': naming_series,
                                          'order_type': order_type,
                                          'items': items})
