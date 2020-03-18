from flask_login import UserMixin
from .manager import login_manager

class User(UserMixin):
    def __init__(self, username, email, first_name, last_name):
        self.email = email
        self.username = username
        self.first_name = first_name
        self.last_name = last_name

        super().__init__()

    def get_id(self):
        return self.email

from erpnext_client.schemas import (
    ERPUserSchema
)

from erpnext_client.documents import (
    ERPUser
)

from ..erpnext import erp_client

import logging

LOGGER = logging.getLogger(__name__)

@login_manager.user_loader
def load_user(user_id):
    try:
        erp_user = erp_client.query(ERPUser).get(user_id,
                                                 fields=['email', 'first_name', 'last_name'])
    except ERPUser.DoesNotExist:
        return None

    return User(username=user_id,
                email=erp_user['email'],
                first_name=erp_user['first_name'],
                last_name=erp_user['last_name'])
