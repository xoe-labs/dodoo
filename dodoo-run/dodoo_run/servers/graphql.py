# =============================================================================
# Created By : David Arnold
# Part of    : xoe-labs/dodoo
# =============================================================================
"""This module implements the dodoo suck-less graphql server"""

import importlib
import logging

from dodoo_run.middleware.odoo import (
    OdooBasicAuthBackendAsync,
    OdooEnvironmentMiddlewareAsync,
)
from starlette.applications import Starlette
from starlette.authentication import requires
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import Route, WebSocketRoute
from starlette.types import ASGIApp
from starlette_prometheus import PrometheusMiddleware, metrics
from strawberry.asgi import GraphQL

from ._common import SessionMiddlewareArgs

try:
    import graphene
except ImportError:  # pragma: nocover
    graphene = None  # type: ignore


_log = logging.getLogger(__name__)


def middleware(prod):
    return [
        Middleware(HTTPSRedirectMiddleware),
        Middleware(SessionMiddleware, **SessionMiddlewareArgs),
        Middleware(AuthenticationMiddleware, backend=OdooBasicAuthBackendAsync()),
        Middleware(OdooEnvironmentMiddlewareAsync),
    ] + ([Middleware(PrometheusMiddleware)] if prod else [])


def routes(graphql_app, prod):
    return [
        Route("/graphql", endpoint=graphql_app),
        WebSocketRoute("/graphql", endpoint=graphql_app),
    ] + ([Route("/metrics", endpoint=metrics)] if prod else [])


def app(schema: "graphene.Schema", prod: bool) -> ASGIApp:
    s = importlib.import_module(schema)
    g = requires("authenticated")(GraphQL(s.schema, debug=not prod))
    app = Starlette(middleware=middleware(prod), routes=routes(g, prod), debug=not prod)
    return app
