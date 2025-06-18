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


USER_PASS = ( "user", "pass" )
TOKEN = "0123456789abcdef"

class TestAPIChangePassword( flask_unittest.ClientTestCase ):
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
            rfid = USER_PASS[0],
        )
        member.set_password( USER_PASS[1], {
            "type": "plaintext",
        })

        session = Session( engine )
        add_bearer_token( TOKEN, member, session )
        session.add( member )
        session.commit()

    def test_change_password( self, client ):
        session = Session( engine )
        member = Doorbot.SQLAlchemy.Member.get_by_tag( USER_PASS[0], session )

        assert member.check_password( USER_PASS[1], session ), "Old password works"

        rv = client.put( '/v1/change_passwd/' + USER_PASS[0], data = {
            "new_pass": USER_PASS[1] + "foo",
            "new_pass2": USER_PASS[1] + "foo",
        }, headers = bearer_header( TOKEN ) )
        self.assertStatus( rv, 200 )

        # Fetch fresh user
        session = Session( engine )
        member = Doorbot.SQLAlchemy.Member.get_by_tag( USER_PASS[0], session )
        assert not member.check_password( USER_PASS[1], session ), "Old password no longer works"
        assert member.check_password( USER_PASS[1] + "foo", session ), "New password works"
