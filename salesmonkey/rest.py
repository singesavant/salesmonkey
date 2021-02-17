import functools

import marshmallow

from flask_apispec import FlaskApiSpec, marshal_with, MethodResource


class Api:
    """
    Holds a version of the API with documentation and allows routes to
    register.
    """

    def __init__(self, prefix=""):
        self.prefix = prefix
        self._deferred_routes = []

    def register(self, path, aMethodResource):
        self._deferred_routes.append(
            (
                "/{0}/{1}".format(self.prefix, path.lstrip("/")),
                aMethodResource.as_view(
                    name=aMethodResource.__module__
                    + "_"
                    + aMethodResource.__name__.lower()
                ),
            )
        )

    def init_app(self, app):
        for deferred in self._deferred_routes:
            app.add_url_rule(deferred[0], view_func=deferred[1])
            specs.register(deferred[1])


specs = FlaskApiSpec()
api_v1 = Api(prefix="v0.1")
