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
RFID1 = "1234"
RFID2 = "2345"
RFID3 = "3456"
TOKEN = "0123456789abcdef"

class TestDumpTagsByLocationAPI( flask_unittest.ClientTestCase ):
    app = Doorbot.API.app
    app.config[ 'is_testing' ] = True
    engine = None

    @classmethod
    def setUpClass( cls ):
        if 'PG' != os.environ.get( 'DB' ):
            Doorbot.SQLAlchemy.set_engine_sqlite()

        global engine
        engine = Doorbot.SQLAlchemy.get_engine()

        permission_back_door = Doorbot.SQLAlchemy.Permission(
            name = "back.door",
        )
        permission_front_door = Doorbot.SQLAlchemy.Permission(
            name = "front.door",
        )

        permission_wood_tablesaw = Doorbot.SQLAlchemy.Permission(
            name = "woodshop.tablesaw",
        )

        role_doors = Doorbot.SQLAlchemy.Role(
            name = "doors",
        )
        role_wood = Doorbot.SQLAlchemy.Role(
            name = "woodshop",
        )

        role_doors.permissions.append( permission_back_door )
        role_doors.permissions.append( permission_front_door )
        role_wood.permissions.append( permission_wood_tablesaw )

        members = [
            Doorbot.SQLAlchemy.Member(
                full_name = "Foo Foo",
                rfid = RFID1,
            ),
            Doorbot.SQLAlchemy.Member(
                full_name = "Bar Baz",
                rfid = RFID2,
            ),
            Doorbot.SQLAlchemy.Member(
                full_name = "Bar Qux",
                rfid = RFID3,
                active = False,
            ),
            Doorbot.SQLAlchemy.Member(
                full_name = "Auth Member",
                rfid = USER_PASS[0],
            ),
        ]
        members[0].roles.append( role_doors )
        members[0].roles.append( role_wood )
        members[1].roles.append( role_doors )
        members[2].roles.append( role_doors )
        members[2].roles.append( role_wood )

        members[3].set_password( USER_PASS[1], {
            "type": "plaintext",
        })

        session = Session( engine )
        add_bearer_token( TOKEN, members[0], session )
        session.add_all( members )
        session.add_all([
            permission_back_door,
            permission_front_door,
            permission_wood_tablesaw,
            role_doors,
            role_wood,
        ])
        session.commit()

    def test_dump_active_tags_for_doors( self, client ):
        rv = client.get( '/v1/dump_active_tags/back.door',
            headers = bearer_header( TOKEN )
        )
        self.assertStatus( rv, 200 )

        data = rv.data.decode( "UTF-8" )
        data = json.loads( data )
        assert RFID1 in data, "First user can open doors"
        assert RFID2 in data, "Second user can open doors"
        assert not RFID3 in data, "Third user inactive, can't open doors"

    def test_dump_active_tags_for_wood( self, client ):
        rv = client.get( '/v1/dump_active_tags/woodshop.tablesaw',
            headers = bearer_header( TOKEN )
        )
        self.assertStatus( rv, 200 )

        data = rv.data.decode( "UTF-8" )
        data = json.loads( data )
        assert RFID1 in data, "First user use woodshop"
        assert not RFID2 in data, "Second user lacks permission for woodshop"
        assert not RFID3 in data, "Third user has permission, but inactive, can't use woodshop"

    def test_dump_active_tags_not_found( self, client ):
        rv = client.get( '/v1/dump_active_tags/no_such.permission',
            headers = bearer_header( TOKEN )
        )
        self.assertStatus( rv, 404 )
