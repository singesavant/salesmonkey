import logging

from salesmonkey import app

from erpnext_client.query import ERPNextClient

LOGGER = logging.getLogger(__name__)


erp_client = ERPNextClient(
    app.config["ERPNEXT_API_HOST"],
    app.config["ERPNEXT_API_KEY"],
    app.config["ERPNEXT_API_SECRET"],
)
if not erp_client.login():
    LOGGER.error(
        "Login failed on ERP at {0} using API KEY {1}".format(
            erp_client.host, erp_client.api_key
        )
    )
else:
    LOGGER.info(
        "Login OK on ERP at {0} using API KEY {1}".format(
            erp_client.host, erp_client.api_key
        )
    )
