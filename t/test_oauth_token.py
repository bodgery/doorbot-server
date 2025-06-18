import unittest
import flask_unittest
import psycopg2
import os
import re
import sqlite3
import Doorbot.API
import Doorbot.Config
import Doorbot.SQLAlchemy
from datetime import timedelta, datetime
from sqlalchemy import select
from sqlalchemy.orm import Session


RFID_FOO = "1234"
TOKEN_GOOD = "0123456789abcdef"
TOKEN_WRONG = "fedcba9876543210"


def add_bearer_token( token_str, member, session ):
    now = datetime.now()
    week_delta = timedelta( weeks = 1 )
    week_later = now + week_delta

    token = Doorbot.SQLAlchemy.OauthToken(
        name = "foo_oauth",
        token = token_str,
        expiration_date = week_later,
        member = member
    )

    session.add( token )

def bearer_header( token, headers = {} ):
    headers[ 'Authorization' ] = "Bearer " + token
    return headers


class TestOauthToken( flask_unittest.ClientTestCase ):
    app = Doorbot.API.app
    app.config[ 'is_testing' ] = True
    engine = None

    @classmethod
    def setUpClass( cls ):
        if 'PG' != os.environ.get( 'DB' ):
            Doorbot.SQLAlchemy.set_engine_sqlite()

        global engine
        engine = Doorbot.SQLAlchemy.get_engine()
        session = Session( engine )

        member = Doorbot.SQLAlchemy.Member(
            full_name = "foo",
            rfid = RFID_FOO,
        )
        add_bearer_token( TOKEN_GOOD, member, session )

        session.add( member )
        session.commit()
        session.close()

    def test_oauth_good( self, client ):
        rv = client.post( '/v1/deactivate_tag/' + RFID_FOO,
            headers = bearer_header( TOKEN_GOOD ),
        )
        self.assertStatus( rv, 200 )

    def test_oauth_bad( self, client ):
        rv = client.post( '/v1/deactivate_tag/' + RFID_FOO,
            headers = bearer_header( TOKEN_WRONG ),
        )
        self.assertStatus( rv, 401 )
