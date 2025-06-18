import unittest
import flask_unittest
import flask.globals
from flask import json
import os
import psycopg2
import re
import sqlite3
import Doorbot.Config
import Doorbot.API
import Doorbot.SQLAlchemy
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_oauth_token import add_bearer_token, bearer_header


USER1 = "1234"
TOKEN = "0123456789abcdef"

class TestAPIManagePermissions( flask_unittest.ClientTestCase ):
    app = Doorbot.API.app
    app.config[ 'is_testing' ] = True
    engine = None

    @classmethod
    def setUpClass( cls ):
        if 'PG' != os.environ.get( 'DB' ):
            Doorbot.SQLAlchemy.set_engine_sqlite()

        global engine
        engine = Doorbot.SQLAlchemy.get_engine()

        member = Doorbot.SQLAlchemy.Member(
            full_name = "_tester",
            rfid = USER1,
        )

        session = Session( engine )
        add_bearer_token( TOKEN, member, session )
        session.add( member )
        session.commit()

    def test_manage_permission( self, client ):
        # User starts with no permission
        rv = client.get( '/v1/check_tag/' + USER1 + '/foo.permission',
            headers = bearer_header( TOKEN )
        )
        self.assertStatus( rv, 403 )

        # Creates the role and the permission at once
        rv = client.put( '/v1/permission/foo.permission/foo_role',
            headers = bearer_header( TOKEN )
        )
        self.assertStatus( rv, 201 )

        # User still has no permission
        rv = client.get( '/v1/check_tag/' + USER1 + '/foo.permission',
            headers = bearer_header( TOKEN )
        )
        self.assertStatus( rv, 403 )

        # Add role to user
        rv = client.put( '/v1/role/foo_role/' + USER1,
            headers = bearer_header( TOKEN )
        )
        self.assertStatus( rv, 201 )

        # User has permission
        rv = client.get( '/v1/check_tag/' + USER1 + '/foo.permission',
            headers = bearer_header( TOKEN )
        )
        self.assertStatus( rv, 200 )
        data = rv.data.decode( "UTF-8" )
        self.assertRegex( data, r'"full_name":\s*"_tester"' )


        # Remove permission from role
        rv = client.delete( '/v1/permission/foo.permission/foo_role',
            headers = bearer_header( TOKEN )
        )
        self.assertStatus( rv, 200 )

        # User has no permission
        rv = client.get( '/v1/check_tag/' + USER1 + '/foo.permission',
            headers = bearer_header( TOKEN )
        )
        self.assertStatus( rv, 403 )

        # Set permission again on role
        rv = client.put( '/v1/permission/foo.permission/foo_role',
            headers = bearer_header( TOKEN )
        )
        self.assertStatus( rv, 201 )

        # User has permission again
        rv = client.get( '/v1/check_tag/' + USER1 + '/foo.permission',
            headers = bearer_header( TOKEN )
        )
        self.assertStatus( rv, 200 )

        # Remove role from user
        rv = client.delete( '/v1/role/foo_role/' + USER1,
            headers = bearer_header( TOKEN )
        )
        self.assertStatus( rv, 200 )

        # User no longer has permission
        rv = client.get( '/v1/check_tag/' + USER1 + '/foo.permission',
             headers = bearer_header( TOKEN )
        )
        self.assertStatus( rv, 403 )
