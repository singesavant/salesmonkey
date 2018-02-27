import logging

from salesmonkey import app

from .erpnext_client.query import ERPNextClient

LOGGER = logging.getLogger(__name__)


erp_client = ERPNextClient(app.config["ERPNEXT_API_HOST"],
                           app.config["ERPNEXT_API_USERNAME"],
                           app.config["ERPNEXT_API_PASSWORD"])
if not erp_client.login():
    LOGGER.error("Login failed on ERP at {0} using username {1}".format(erp_client.host,
                                                                        erp_client.username))
else:
    LOGGER.info("Login OK on ERP at {0} using username {1}".format(erp_client.host,
                                                                   erp_client.username))
    LOGGER.debug(erp_client.get_credentials())

