import Doorbot.Config
import flask
from Doorbot.API import app
from Doorbot.SQLAlchemy import Location
from Doorbot.SQLAlchemy import EntryLog
from Doorbot.SQLAlchemy import Member
from Doorbot.SQLAlchemy import Permission
from Doorbot.SQLAlchemy import Role
from Doorbot.SQLAlchemy import get_engine
from Doorbot.SQLAlchemy import get_session
from datetime import datetime, timedelta, timezone
from flask_stache import render_template
from sqlalchemy import select
from sqlalchemy.sql import text
from urllib.parse import urlparse
import pathlib
import secrets


def error_page(
    response,
    tmpl,
    msgs = [],
    status = 500,
    page_name = "",
    username = None,
):
    output = render_template(
        tmpl,
        page_name = page_name,
        username = username,
        has_errors = True,
        errors = msgs,
    )

    response.status = status
    response.set_data( output )
    return response

def require_logged_in( func ):
    def check():
        if flask.session.get( 'username' ) is None:
            return login_form([ "You must be logged in to access this page" ])
        else:
            return func()

    # Avoid error of "View function mapping is overwriting an existing endpoint 
    # function"
    check.__name__ = func.__name__

    return check

def get_env():
    request = flask.request
    host_url = urlparse( request.base_url )
    hostname = host_url.hostname

    env = "personal"
    if "rfid-dev" in hostname:
        env = "dev"
    elif "rfid-stage" in hostname:
        env = "stage"
    elif "rfid-prod" in hostname:
        env = "prod"

    return env


def render_tmpl( name, **context ):
    context[ 'env' ] = env = get_env()
    context[ 'is_lower_env' ] = True if env != "prod" else False

    print( f'Env: {context["env"]}' )
    print( f'Is lower: {context["is_lower_env"]}' )

    return render_template(
        name,
        **context,
    )

@app.route( "/home", methods = [ "GET" ] )
@require_logged_in
def home_page():
    username = flask.session.get( 'username' )

    return render_tmpl(
        'home',
        page_name = "Home",
        username = username,
    )

@app.route( "/login", methods = [ "GET" ] )
def login_form( errors = [] ):
    has_error = True if errors else False

    return render_tmpl(
        'login',
        page_name = "Login",
        has_errors = has_error,
        errors = errors,
    )

@app.route( "/login", methods = [ "POST" ] )
def login():
    request = flask.request
    username = request.form[ 'username' ]
    password = request.form[ 'password' ]

    session = get_session()
    member = Member.get_by_username( username, session )

    response = flask.make_response()
    if not member:
        session.close()
        return error_page(
            response,
            msgs = [ "Incorrect Login" ],
            tmpl = "login",
            page_name = "Login",
            status = 404,
        )
    elif not member.check_password( password, session ):
        session.close()
        return error_page(
            response,
            msgs = [ "Incorrect Login" ],
            tmpl = "login",
            page_name = "Login",
            status = 404,
        )
    else:
        session.close()
        flask.session[ 'username' ] = username
        return home_page()

@app.route( "/logout" )
def logout():
    flask.session[ 'username' ] = None
    return login_form([ "You have been logged out" ])

@app.route( "/add-tag", methods = [ "GET" ] )
@require_logged_in
def add_tag_form():
    username = flask.session.get( 'username' )

    return render_tmpl(
        'add_tag',
        page_name = "Add RFID Tag",
        username = username,
    )

@app.route( "/add-tag", methods = [ "POST" ] )
@require_logged_in
def add_tag():
    username = flask.session.get( 'username' )

    request = flask.request
    rfid = request.form[ 'rfid' ]
    name = request.form[ 'name' ]

    session = get_session()

    errors = []
    if not Doorbot.API.MATCH_INT.match( rfid ):
        errors.append( "RFID should be a series of digits" )
    if not Doorbot.API.MATCH_NAME.match( name ):
        errors.append( "Member Name should be a string" )

    if not errors:
        member = Member.get_by_tag( rfid, session )
        if not member is None:
            errors.append( "Member with RFID tag " + rfid + " already exists" )

    response = flask.make_response()
    if errors:
        session.close()
        return error_page(
            response,
            msgs = errors,
            tmpl = "add_tag",
            page_name = "Add RFID Tag",
            status = 400,
            username = username,
        )
    else:
        member = Member(
            full_name = name,
            rfid = rfid,
        )
        session.add( member )
        session.commit()
        session.close()

        return render_tmpl(
            'add_tag',
            page_name = "Add RFID Tag",
            username = username,
            msg = "Added tag",
        )

def controller_list_main(**args): # List of Controller Groups and Controllers
    session = get_session()
    groups = session.query(Role)
    formatted_groups = list(map(lambda z: {
        "controller_group": z.name,
        "controllers": ', '.join(list(map(lambda x: x.name, z.permissions))),
        "user_count": len(z.members) if len(z.members) != 0 else None,
    }, groups ))
    session.close()

    username = flask.session.get( 'username' )
    return render_tmpl(
        'view_controllers',
        page_name = "Controller List",
        username = username,
        controller_groups = formatted_groups,
        **args
    )

@app.route( "/controller-list", methods = [ "GET" ] )
@require_logged_in
def controller_list():
    return controller_list_main()


@app.route( "/controller-group-add", methods = [ "POST" ] ) # Add a controller group
@require_logged_in
def controller_group_add():
    add_controller_group = flask.request.form[ 'add_controller_group' ]

    session = get_session()

    errors = []
    if not Doorbot.API.MATCH_NAME.match( add_controller_group ):
        errors.append( "New Controller Group must be a string" )
    if len(add_controller_group) < 4:
        errors.append( "New Controller Group name is too short" )
    if not errors:
        z = session.query(Role).filter_by(name=add_controller_group).one_or_none()
        if z is not None:
            errors.append(
                'New Controller Group "' + add_controller_group + '" already exists')

    if errors:
        session.close()
        return controller_list_main(
            has_errors = True,
            errors = errors,
            status = 400,
        )
    else:
        session.add( Role(name = add_controller_group) )
        session.commit()
        session.close()
        return controller_list_main(
            has_errors = True,
            errors = [ 'New Controller Group "' + add_controller_group + '" added' ],
            status = 201,
        )

@app.route( "/controller-group-delete", methods = [ "POST" ] )
@require_logged_in
def controller_group_delete():
    del_controller_group = flask.request.form[ 'del_controller_group' ]

    session = get_session()

    ddg = session.query(Role).filter_by(name=del_controller_group).one_or_none()
    if ddg is None:
        session.close()
        return controller_list_main(
            has_errors = True,
            errors = [ 'Cannot delete "' + del_controller_group + '", not found' ],
            status = 400,
        )
    else:
        session.delete(ddg)
        session.commit()
        session.close()
        return controller_list_main(
            has_errors = True,
            errors = [ 'Controller Group "' + del_controller_group + '" deleted' ],
            status = 200,
        )

def edit_controllers_main(**args): # List of Controllers with add & delete actions
    username = flask.session.get( 'username' )

    if 'controller_group' in args:
        controller_group = args[ 'controller_group' ]
        del(args[ 'controller_group' ])
    else:
        controller_group = flask.request.args.get( 'controller_group' )

    session = get_session()
    controllers = session.query(Permission).join(
        Role, Permission.roles).where((Role.name==controller_group))
    formatted_controllers = list(map(lambda z: {
        "controller_name": z.name
    }, controllers ))
    session.close()

    return render_tmpl(
        'edit_controllers',
        page_name = '' + controller_group + ' controllers',
        username = username,
        controllers = formatted_controllers,
        controller_group = controller_group,
        **args
    )

@app.route( "/edit-controllers", methods = [ "GET" ] )
@require_logged_in
def edit_controllers():
    return edit_controllers_main()


@app.route( "/controller-add", methods = [ "POST" ] ) # Add a controller
@require_logged_in
def controller_add():
    request = flask.request
    add_controller = request.form[ 'add_controller' ]
    controller_group = request.form[ 'controller_group' ]

    session = get_session()
    controller_group_obj = session.query(Role).filter_by(name=controller_group).one_or_none()

    errors = []
    if controller_group_obj is None:
        errors.append('Controller Group "' + controller_group + '" must first exist')
    if not Doorbot.API.MATCH_NAME.match( add_controller ):
        errors.append( "New Controller must be a string" )
    if len(add_controller) < 4:
        errors.append( "New Controller name is too short" )
    if not errors:
        controller_obj = session.query(Permission).filter_by(name=add_controller).one_or_none()
        if controller_obj is not None:
            errors.append('New Controller "' + add_controller + '" already exists')

    if errors:
        session.close()
        return edit_controllers_main(
            has_errors = True,
            errors = errors,
            controller_group = controller_group,
            status = 400,
        )
    else:
        controller_obj = Permission(name=add_controller)
        controller_group_obj.permissions.append( controller_obj )
        session.add_all([ controller_group_obj, controller_obj ])
        session.commit()
        session.close()
        return edit_controllers_main(
            has_errors = True,
            errors = [ 'New Controller "' + add_controller + '" added' ],
            controller_group = controller_group,
            status = 201,
        )

@app.route( "/controller-delete", methods = [ "POST" ] ) # Delete a controller
@require_logged_in
def controller_delete():
    request = flask.request
    del_controller = request.form[ 'del_controller' ]
    controller_group = request.form[ 'controller_group' ]

    session = get_session()
    controller_group_obj = session.query(Role).filter_by(name=controller_group).one_or_none()

    errors = []
    if controller_group_obj is None:
        errors.append('Controller Group "' + controller_group + '" must first exist')
    dev = session.query(Permission).filter_by(name=del_controller).one_or_none()
    if dev is None:
        errors.append('Cannot delete "' + del_controller + '", not found')
    if errors:
        session.close()
        return edit_controllers_main(
            has_errors = True,
            errors = errors,
            controller_group = controller_group,
            status = 400,
        )
    else:
        session.delete(dev)
        session.commit()
        session.close()
        return edit_controllers_main(
            has_errors = True,
            errors = [ 'Controller "' + del_controller + '" deleted' ],
            controller_group = controller_group,
            status = 200,
        )

def edit_group_users_main(**args): # List of Controller Group Users with add & delete actions
    username = flask.session.get( 'username' )

    if 'controller_group' in args:
        controller_group = args[ 'controller_group' ]
        del(args[ 'controller_group' ])
    else:
        controller_group = flask.request.args.get( 'controller_group' )

    session = get_session()
    users = session.query(Role).filter_by(name=controller_group).one_or_none().members
    formatted_users = list(map(lambda z: {
        "group_user_name": z.full_name
    }, users ))

    return render_tmpl(
        'edit_group_users',
        page_name = '' + controller_group + ' users',
        username = username,
        users = formatted_users,
        controller_group = controller_group,
        **args
    )

@app.route( "/edit-group-users", methods = [ "GET" ] )
@require_logged_in
def edit_group_users():
    return edit_group_users_main()


@app.route( "/group-user-add", methods = [ "POST" ] ) # Add a user to a controller group
@require_logged_in
def group_users_add():
    request = flask.request
    add_group_user = request.form[ 'add_group_user' ]
    controller_group = request.form[ 'controller_group' ]

    session = get_session()
    controller_group_obj = session.query(Role).filter_by(name=controller_group).one_or_none()

    errors = []
    if controller_group_obj is None:
        errors.append('Controller Group "' + controller_group + '" must first exist')
    if not Doorbot.API.MATCH_NAME.match( add_group_user ):
        errors.append( "New user name must be a string" )
    if len(add_group_user) < 4:
        errors.append( "New user name is too short" )
    if not errors:
        group_users_obj = session.query(Member).filter_by(full_name=add_group_user).first()
        if group_users_obj is None:
            errors.append('New user name "' + add_group_user + '" not found in database')
    if not errors and controller_group_obj in group_users_obj.roles:
        errors.append('New user name "' + add_group_user +
            '" already exists in "' + controller_group + ' "')

    if errors:
        session.close()
        return edit_group_users_main(
            has_errors = True,
            errors = errors,
            controller_group = controller_group,
            status = 400,
        )
    else:
        group_users_obj.roles.append( controller_group_obj )
        session.add_all([ controller_group_obj, group_users_obj ])
        session.commit()
        session.close()
        return edit_group_users_main(
            has_errors = True,
            errors = [ 'New User "' + add_group_user + '" added' ],
            controller_group = controller_group,
            status = 200,
        )

@app.route( "/group-user-delete", methods = [ "POST" ] ) # Delete a user from a controller group
@require_logged_in
def group_users_delete():
    request = flask.request
    del_group_user = request.form[ 'del_group_user' ]
    controller_group = request.form[ 'controller_group' ]

    session = get_session()
    controller_group_obj = session.query(Role).filter_by(name=controller_group).one_or_none()

    errors = []
    if controller_group_obj is None:
        errors.append('Controller Group "' + controller_group + '" must first exist')
    usr = session.query(Member).filter_by(full_name=del_group_user).one_or_none()
    if usr is None:
        errors.append('Cannot delete "' + del_group_user + '", not found')
    if errors:
        session.close()
        return edit_group_users_main(
            has_errors = True,
            errors = errors,
            controller_group = controller_group,
            status = 400,
        )
    else:
        usr.roles.remove( controller_group_obj )
        session.add_all([ usr, controller_group_obj ])
        session.commit()
        session.close()
        return edit_group_users_main(
            has_errors = True,
            errors = [ 'User "' + del_group_user + '" deleted' ],
            controller_group = controller_group,
            status = 200,
        )

@app.route( "/search-scan-logs", methods = [ "GET" ] )
@require_logged_in
def search_scan_logs():
    args = flask.request.args
    rfid = args.get( 'search_rfid' )
    offset = args.get( 'offset' )
    limit = args.get( 'limit' )

    # Normalize the data
    rfid = "" if rfid is None else rfid
    rfid = rfid.strip()

    offset = int( offset ) if offset else 0
    limit = int( limit ) if limit else 0

    # Clamp offset/limit
    if offset < 0:
        offset = 0
    if limit <= 0:
        limit = 50
    elif limit > 100:
        limit = 100

    logs = Doorbot.API.search_scan_logs( rfid, offset, limit )

    next_offset = offset + limit

    username = flask.session.get( 'username' )
    return render_tmpl(
        'search_scan_logs',
        page_name = "Search Scan Logs",
        tags = logs,
        username = username,
        search_rfid = rfid,
        next_offset = next_offset,
        limit = limit,
    )

@app.route( "/view-tag-list", methods = [ "GET" ] )
@require_logged_in
def view_tag_list():
    args = flask.request.args
    name = args.get( 'search_name' )
    rfid = args.get( 'search_rfid' )
    offset = args.get( 'offset' )
    limit = args.get( 'limit' )

    # Normalize the data
    name = "" if name is None else name
    rfid = "" if rfid is None else rfid

    offset = int( offset ) if offset else 0
    limit = int( limit ) if limit else 0

    # Clamp offset/limit
    if offset < 0:
        offset = 0
    if limit < 0:
        limit = 50
    elif limit < 1:
        limit = 100
    elif limit > 100:
        limit = 100

    next_offset = offset + limit

    members = Doorbot.API.search_tag_list( name, rfid, offset, limit )
    formatted_members = list( map(
        lambda member: {
            "full_name": member.full_name,
            "tag": member.rfid,
            "is_active": member.active,
            "mms_id": member.mms_id if member.mms_id else "",
        },
        members,
    ))

    username = flask.session.get( 'username' )
    return render_tmpl(
        'view_tag_list',
        page_name = "Search Tag List",
        tags = formatted_members,
        username = username,
        next_offset = next_offset,
        limit = limit,
        search_name = name,
        search_rfid = rfid,
    )

@app.route( "/edit-tag", methods = [ "GET" ] )
@require_logged_in
def edit_tag_form():
    username = flask.session.get( 'username' )

    current_tag = flask.request.args.get( 'current_tag' )
    current_tag = current_tag if current_tag else ''

    return render_tmpl(
        'edit_tag',
        page_name = "Edit Tag",
        username = username,
        current_tag = current_tag,
    )

@app.route( "/edit-tag", methods = [ "POST" ] )
@require_logged_in
def edit_tag_submit():
    username = flask.session.get( 'username' )

    current_tag = flask.request.form[ 'current_tag' ]
    new_tag = flask.request.form[ 'new_tag' ]

    errors = []
    if not Doorbot.API.MATCH_INT.match( current_tag ):
        errors.append( "Current tag should be a series of digits" )
    if not Doorbot.API.MATCH_INT.match( new_tag ):
        errors.append( "New tag should be a series of digits" )

    response = flask.make_response()
    if errors:
        return error_page(
            response,
            tmpl = 'edit_tag',
            msgs = errors,
            status = 400,
            page_name = "Edit Tag",
            username = username,
        )

    session = get_session()
    member = Member.get_by_tag( current_tag, session )

    if not member:
        session.close()
        return error_page(
            response,
            tmpl = 'edit_tag',
            msgs = [ "Cannot find member for RFID " + current_tag ],
            status = 400,
            page_name = "Edit Tag",
            username = username,
        )

    member.rfid = new_tag
    session.add( member )
    session.commit()
    session.close()

    return render_tmpl(
        'edit_tag',
        page_name = "Edit Tag",
        username = username,
        current_tag = new_tag,
        msg = "Changed RFID tag",
    )

@app.route( "/edit-name", methods = [ "GET" ] )
@require_logged_in
def edit_name_form():
    username = flask.session.get( 'username' )

    current_tag = flask.request.args.get( 'current_tag' )
    current_name = flask.request.args.get( 'current_name' )

    return render_tmpl(
        'edit_name',
        page_name = "Edit Name",
        username = username,
        current_tag = current_tag,
        full_name = current_name
    )

@app.route( "/edit-name", methods = [ "POST" ] )
@require_logged_in
def edit_name_submit():
    username = flask.session.get( 'username' )

    current_tag = flask.request.form[ 'current_tag' ]
    new_name = flask.request.form[ 'new_name' ]

    errors = []
    if not Doorbot.API.MATCH_INT.match( current_tag ):
        errors.append( "Current tag should be a series of digits" )
    if not Doorbot.API.MATCH_NAME.match( new_name ):
        errors.append( "New name should be a string" )

    response = flask.make_response()
    if errors:
        return error_page(
            response,
            tmpl = 'edit_name',
            msgs = errors,
            status = 400,
            page_name = "Edit Name",
            username = username,
        )

    session = get_session()
    member = Member.get_by_tag( current_tag, session )

    if not member:
        session.close()
        return error_page(
            response,
            tmpl = 'edit_name',
            msgs = [ "Cannot find member for RFID " + current_tag ],
            status = 400,
            page_name = "Edit Name",
            username = username,
        )

    member.full_name = new_name
    session.add( member )
    session.commit()
    session.close()

    return render_tmpl(
        'edit_name',
        page_name = "Edit Name",
        username = username,
        current_tag = current_tag,
        full_name = new_name,
        msg = "Changed member name",
    )

@app.route( "/activate-tag", methods = [ "POST" ] )
@require_logged_in
def activate_tag_submit():
    username = flask.session.get( 'username' )

    tag = flask.request.form[ 'tag' ]
    activate = int( flask.request.form[ 'activate' ] )

    page_name = "Activate Tag" if activate else "Deactivate Tag"

    errors = []
    if not Doorbot.API.MATCH_INT.match( tag ):
        errors.append( "Tag should be a series of digits" )

    response = flask.make_response()
    if errors:
        return error_page(
            response,
            tmpl = 'activate_tag',
            msgs = errors,
            status = 400,
            page_name = page_name,
            username = username,
        )

    session = get_session()
    member = Member.get_by_tag( tag, session )

    if not member:
        session.close()
        return error_page(
            response,
            tmpl = 'activate_tag',
            msgs = [ "Cannot find member for RFID " + current_tag ],
            status = 400,
            page_name = page_name,
            username = username,
        )

    member.active = True if activate else False
    session.add( member )
    session.commit()

    action = "Activated tag" if activate else "Deactivated tag"
    action = action + " " + tag + " for " + member.full_name

    session.close()
    return render_tmpl(
        'activate_tag',
        page_name = page_name,
        username = username,
        msg = action,
    )

@app.route( "/mp-rfid-report", methods = [ "GET" ] )
@require_logged_in
def mp_rfid_report():
    username = flask.session.get( 'username' )

    cur_dir = pathlib \
        .Path( __file__ ) \
        .parent \
        .resolve()
    full_pathname = pathlib \
        .PurePath( cur_dir, '../cache_files/mp_rfid_report.txt')
    f = open(full_pathname, 'r')
    mp_rfid_rpt = f.read()

    return render_tmpl(
        'mp_rfid',
        page_name = "MemberPress vs. RFID Report",
        username = username,
        page_text = mp_rfid_rpt
    )

@app.route( "/create-oauth", methods = [ "GET" ] )
@require_logged_in
def create_oauth_form():
    username = flask.session.get( 'username' )

    return render_tmpl(
        'create_oauth',
        page_name = "Create OAuth2 Token"
    )

@app.route( "/create-oauth", methods = [ "POST" ] )
@require_logged_in
def create_oauth():
    username = flask.session.get( 'username' )

    request = flask.request
    name = request.form[ 'name' ]

    session = get_session()

    errors = []
    if not Doorbot.API.MATCH_NAME.match( name ):
        errors.append( "Token Name should be a string" )

    response = flask.make_response()
    if errors:
        session.close()
        return error_page(
            response,
            msgs = errors,
            tmpl = "create_oauth",
            page_name = "Create OAuth Token",
            status = 400,
        )
    else:
        token_config = Doorbot.Config.get( 'oauth' )

        token_str = secrets.token_hex( token_config[ 'token_hex_length' ] )
        now = datetime.now( timezone.utc )
        expires_delta = timedelta( days = token_config[ 'expires_days' ] )
        expires = now + expires_delta
        member = Member.get_by_username( username, session )

        token = Doorbot.SQLAlchemy.OauthToken(
            name = name,
            token = token_str,
            expiration_date = expires,
            member = member
        )

        session.add( token )
        session.commit()
        session.close()

        return render_tmpl(
            'create_oauth_submit',
            page_name = "Create OAuth Token",
            msg = "Added token",
            token = token_str,
            token_name = name,
            token_expires = expires.isoformat(),
        )

