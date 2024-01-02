import flask
import os
import re
import Doorbot.Config
from Doorbot.SQLAlchemy import Location
from Doorbot.SQLAlchemy import EntryLog
from Doorbot.SQLAlchemy import Member
from Doorbot.SQLAlchemy import Permission
from Doorbot.SQLAlchemy import Role
from Doorbot.SQLAlchemy import get_engine
from Doorbot.SQLAlchemy import get_session
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.sql import text

MATCH_INT = re.compile( ''.join([
    '^',
    '\\d+',
    '$',
]) )
MATCH_NAME = re.compile( ''.join([
    '^',
    '[',
        '\\w',
        '\\s',
        '\\-',
        '\\.',
    ']+',
    '$',
]) )


app = flask.Flask( "rfid_app",
    static_url_path = '',
    static_folder = 'rfid_app/static/',
)

def set_error(
    response,
    msg,
    status = 500,
):
    error_data = {
        "msg": msg,
        "datetime": datetime.now().isoformat(),
    }
    json_data = flask.json.dumps( error_data )

    response.status = status
    response.content_type = 'application/json'
    response.set_data( json_data )
    return response

# From https://stackoverflow.com/questions/2546207/does-sqlalchemy-have-an-equivalent-of-djangos-get-or-create
def get_or_create(
    session,
    model,
    **kwargs,
):
    instance = session.query( model ).filter_by( **kwargs ).first()
    if instance:
        return instance
    else:
        instance = model( **kwargs )
        session.add( instance )
        session.commit()
        return instance

def get(
    session,
    model,
    **kwargs,
):
    instance = session.query( model ).filter_by( **kwargs ).first()
    return instance

def search_scan_logs( tag, offset, limit):
    # People could scan an RFID that isn't in the system. We still want to 
    # log that, but it means we can't explicitly link the member and entry_log 
    # tables. This is a problem for SQLAlchemy, so don't bother, and use raw 
    # SQL.
    sql_params = {
        "offset": offset,
        "limit": limit,
    }
    where_clause = ""
    if tag:
        where_clause = "WHERE entry_log.rfid = :rfid"
        sql_params[ 'rfid' ] = tag

    conn = get_engine().connect()
    stmt = text( """
        SELECT
            members.full_name AS full_name
            ,entry_log.rfid AS rfid
            ,locations.name AS location
            ,entry_log.entry_time AS entry_time
            ,entry_log.is_active_tag AS is_active_tag
            ,entry_log.is_found_tag AS is_found_tag
        FROM entry_log
        LEFT OUTER JOIN members ON entry_log.rfid = members.rfid
        LEFT OUTER JOIN locations ON entry_log.location = locations.id
    """ + where_clause +
    """
        ORDER BY entry_log.entry_time DESC
        LIMIT :limit
        OFFSET :offset
    """ )

    logs = conn.execute( stmt, sql_params )
    return logs

def search_tag_list(
    name = None,
    tag = None,
    offset = 0,
    limit = 100,
):
    stmt = select( Member )
    if name:
        stmt = stmt.where(
            Member.full_name.ilike( '%' + name + '%' )
        )
    if tag:
        stmt = stmt.where(
            Member.rfid == tag,
        )

    stmt = stmt.order_by(
        'join_date'
    ).limit(
        limit
    ).offset(
        offset
    )

    session = get_session()
    members = session.scalars( stmt ).all()

    return members

def auth_required( func ):
    def check( *args, **kwargs ):
        # For now, we only allow these endpoints for testing
        if 'is_testing' in app.config and app.config[ 'is_testing' ]:
            return func( *args, **kwargs )
        else:
            return redirect_home()

    # Avoid error of "View function mapping is overwriting an existing endpoint 
    # function"
    check.__name__ = func.__name__

    return check


@app.route( "/" )
def redirect_home():
    if flask.session.get( 'username' ) is None:
        return flask.redirect( '/login', code = 302 )
    else:
        return flask.redirect( '/home', code = 302 )

@app.route( "/check_tag/<tag>",  methods = [ "GET" ] )
def check_tag( tag ):
    response = flask.make_response()
    if not MATCH_INT.match( tag ):
        response.status = 400
        return response

    session = get_session()
    member = Member.get_by_tag( tag, session )

    if None == member:
        response.status = 404
    elif member.active:
        response.status = 200
    else:
        response.status = 403

    return response

@app.route( "/v1/check_tag/<tag>/<permission>",  methods = [ "GET" ] )
@auth_required
def check_tag_by_permission( tag, permission ):
    response = flask.make_response()
    if not MATCH_INT.match( tag ):
        response.status = 400
        return response

    session = get_session()
    member = Member.get_by_tag( tag, session )

    if None == member:
        response.status = 404
    elif member.active:
        if member.has_permission( permission ):
            response.status = 200
        else:
            response.status = 403
    else:
        response.status = 403

    return response

# TODO change this to /v1/entry/<tag>/<location>
@app.route( "/secure/entry/<tag>/<location>", methods = [ "GET" ] )
def log_entry( tag, location ):
    response = flask.make_response()
    if (not MATCH_INT.match( tag )) or (not MATCH_NAME.match( location )):
        response.status = 400
        return response

    session = get_session()
    member = Member.get_by_tag( tag, session )

    stmt = select( Location ).where(
        Location.name == location
    )
    location_db = session.scalars( stmt ).one()

    entry = EntryLog(
        rfid = tag,
        mapped_location = location_db,
    )

    if None == member:
        entry.is_active_tag = False
        entry.is_found_tag = False
        response.status = 404
    elif member.active:
        entry.is_active_tag = True
        entry.is_found_tag = True
        response.status = 200
    else:
        entry.is_active_tag = False
        entry.is_found_tag = True
        response.status = 403

    session.add( entry )
    session.add( location_db )
    session.commit()

    return response

@app.route( "/v1/new_tag/<tag>/<full_name>", methods = [ "PUT" ] )
@auth_required
def new_tag( tag, full_name ):
    response = flask.make_response()
    if (not MATCH_INT.match( tag )) or (not MATCH_NAME.match( full_name )):
        response.status = 400
        return response

    session = get_session()
    member = Doorbot.SQLAlchemy.Member(
        full_name = full_name,
        rfid = tag,
    )
    session.add( member )
    session.commit()

    response.status = 201
    return response

@app.route( "/v1/deactivate_tag/<tag>", methods = [ "POST" ] )
@auth_required
def deactivate_tag( tag ):
    response = flask.make_response()
    if not MATCH_INT.match( tag ):
        response.status = 400
        return response

    session = get_session()
    member = Member.get_by_tag( tag, session )

    member.active = False
    session.add( member )
    session.commit()

    response.status = 200
    return response

@app.route( "/v1/reactivate_tag/<tag>", methods = [ "POST" ] )
@auth_required
def reactivate_tag( tag ):
    response = flask.make_response()
    if not MATCH_INT.match( tag ):
        response.status = 400
        return response

    session = get_session()
    member = Member.get_by_tag( tag, session )

    member.active = True
    session.add( member )
    session.commit()

    response.status = 200
    return response

@app.route( "/v1/edit_tag/<current_tag>/<new_tag>", methods = [ "POST" ] )
@auth_required
def edit_tag( current_tag, new_tag ):
    response = flask.make_response()
    if not MATCH_INT.match( current_tag ):
        response.status = 400
        return response
    if not MATCH_INT.match( new_tag ):
        response.status = 400
        return response

    session = get_session()
    member = Member.get_by_tag( current_tag, session )

    member.rfid = new_tag
    session.add( member )
    session.commit()

    response.status = 201
    return response

@app.route( "/v1/edit_name/<tag>/<new_name>", methods = [ "POST" ] )
@auth_required
def edit_name( tag, new_name ):
    response = flask.make_response()
    if not MATCH_INT.match( tag ):
        response.status = 400
        return response

    session = get_session()
    member = Member.get_by_tag( tag, session )

    member.full_name = new_name
    session.add( member )
    session.commit()

    response.status = 201
    return response

@app.route( "/v1/search_tags", methods = [ "GET" ] )
@auth_required
def search_tags():
    args = flask.request.args
    response = flask.make_response()

    name = args.get( 'name' )
    tag = args.get( 'tag' )
    offset = args.get( 'offset' )
    limit = args.get( 'limit' )

    offset = int( offset ) if offset else 0
    limit = int( limit ) if limit else 0

    # Clamp offset/limit
    if offset < 0:
        offset = 0
    if limit < 0:
        limit = 50
    elif limit > 100:
        limit = 100

    members = Doorbot.API.search_tag_list( name, tag, offset, limit )

    out = ''
    for member in members:
        out += ','.join([
            member.rfid,
            member.full_name,
            "1" if member.active else "0",
            member.mms_id if member.mms_id else "",
        ]) + "\n"

    response.status = 200
    response.content_type = 'text/plain'
    response.set_data( out )
    return response

@app.route( "/v1/search_entry_log", methods = [ "GET" ] )
@auth_required
def search_entry_log():
    args = flask.request.args
    response = flask.make_response()

    tag = args.get( 'tag' )
    offset = args.get( 'offset' )
    limit = args.get( 'limit' )

    offset = int( offset ) if offset else 0
    limit = int( limit ) if limit else 0

    # Clamp offset/limit
    if offset < 0:
        offset = 0
    if limit <= 0:
        limit = 50
    elif limit > 100:
        limit = 100

    logs = search_scan_logs( tag, offset, limit )

    out = ''
    for entry in logs:
        out += ','.join([
            entry[ 0 ] if entry[ 0 ] else "",
            entry[ 1 ],
            entry[ 3 ],
            "1" if entry[ 4 ] else "0",
            "1" if entry[ 5 ] else "0",
            entry[ 2 ] if entry[ 2 ] else "",
        ]) + "\n"

    response.status = 200
    response.content_type = 'text/plain'
    response.set_data( out )
    return response

@app.route( "/v1/dump_active_tags/<permission>", methods = [ "GET" ] )
@auth_required
def dump_tags_for_permission( permission ):
    session = get_session()
    stmt = select( Doorbot.SQLAlchemy.Permission ).where(
        Doorbot.SQLAlchemy.Permission.name == permission
    )
    found_permission = session.scalars( stmt ).one_or_none()

    response = flask.make_response()
    if found_permission is None:
        set_error(
            response = response,
            msg = "Permission " + permission + " was not found",
            status = 404,
        )
    else:
        members = {}
        for member in found_permission.all_members_with_permission():
            rfid = member.rfid
            members[ rfid ] = True

        json_data = flask.json.dumps( members )
        response.content_type = 'application/json'
        response.set_data( json_data )

    return response

@app.route( "/secure/dump_active_tags", methods = [ "GET" ] )
def dump_tags():
    session = get_session()
    stmt = select( Member ).where(
        Member.active == True
    )
    members = session.scalars( stmt ).all()

    out = {}
    for member in members:
        rfid = member.rfid
        out[ rfid ] = True

    return out


@app.route( "/v1/change_passwd/<tag>", methods = [ "PUT" ] )
@auth_required
def change_password( tag ):
    session = get_session()
    member = Member.get_by_tag( tag, session )

    response = flask.make_response()

    if member is None:
        set_error(
            response = response,
            msg = "Member with RFID " + rfid + " was not found",
            status = 404,
        )
    else:
        pass1 = flask.request.form[ 'new_pass' ]
        pass2 = flask.request.form[ 'new_pass2' ]

        if pass1 != pass2:
            set_error(
                response = response,
                msg = "Passwords do not match",
                status = 400,
            )
        else:
            password_config = Doorbot.Config.get( 'password_storage' )
            member.set_password( pass1, password_config )
            session.add( member )
            session.commit()

            response.status = 200

    return response

@app.route( "/v1/permission/<permission>/<role>", methods = [ "PUT" ] )
@auth_required
def add_permission( permission, role ):
    session = get_session()
    role_obj = get_or_create( session, Role, name = role )
    permission_obj = get_or_create( session, Permission, name = permission )

    role_obj.permissions.append( permission_obj )
    session.add_all([ role_obj, permission_obj ])
    session.commit()

    response = flask.make_response()
    response.status = 201
    return response

@app.route( "/v1/permission/<permission>/<role>", methods = [ "DELETE" ] )
@auth_required
def delete_permission( permission, role ):
    session = get_session()
    role_obj = get( session, Role, name = role )
    permission_obj = get( session, Permission, name = permission )

    response = flask.make_response()
    if not role_obj:
        set_error(
            response = response,
            msg = "Role " + role + " was not found",
            status = 404,
        )
    elif not permission_obj:
        set_error(
            response = response,
            msg = "Permission " + permission + " was not found",
            status = 404,
        )
    else:
        response.status = 200

        role_obj.permissions.remove( permission_obj )
        session.add_all([ role_obj, permission_obj ])
        session.commit()

    return response

@app.route( "/v1/role/<role>/<tag>", methods = [ "PUT" ] )
@auth_required
def add_role_to_member( role, tag ):
    session = get_session()
    member = Member.get_by_tag( tag, session )

    response = flask.make_response()
    if None == member:
        response.status = 404
    else:
        role_obj = get_or_create( session, Role, name = role )
        member.roles.append( role_obj )
        session.add_all([ role_obj, member ])
        session.commit()

        response.status = 201

    return response

@app.route( "/v1/role/<role>/<tag>", methods = [ "DELETE" ] )
@auth_required
def delete_role_from_member( role, tag ):
    session = get_session()
    role_obj = get( session, Role, name = role )
    member_obj = get( session, Member, rfid = tag )

    response = flask.make_response()
    if not member_obj:
        set_error(
            response = response,
            msg = "Member for RFID " + tag + " was not found",
            status = 404,
        )
    elif not role_obj:
        set_error(
            response = response,
            msg = "Role " + role + " was not found",
            status = 404,
        )
    else:
        response.status = 200

        member_obj.roles.remove( role_obj )
        session.add_all([ member_obj, role_obj ])
        session.commit()

    return response


# TODO /secure/change_passwd

#@app.route('/', defaults={'path': ''})
#@app.route( "/<path:path>" )
#def catch_all_secure( path ):
#    print( f'Hit catch all with {path}' )
#    return flask.send_from_directory( 'static', path )
