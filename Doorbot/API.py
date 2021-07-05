import flask
import os
import re
import Doorbot.DB as DB

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


app = flask.Flask( __name__,
    static_url_path = '',
    static_folder = '../static',
)


@app.route( "/" )
@app.route( "/index.html" )
def redirect_home():
    return flask.redirect( '/secure/index.html', code = 301 )

@app.route( "/check_tag/<tag>",  methods = [ "GET" ] )
def check_tag( tag ):
    response = flask.make_response()
    if not MATCH_INT.match( tag ):
        response.status = 400
        return response

    member = DB.fetch_member_by_rfid( tag )
    if None == member:
        response.status = 404
    elif member[ 'is_active' ]:
        response.status = 200
    else:
        response.status = 403

    return response

@app.route( "/entry/<tag>/<location>", methods = [ "GET" ] )
def log_entry( tag, location ):
    response = flask.make_response()
    if (not MATCH_INT.match( tag )) or (not MATCH_NAME.match( location )):
        response.status = 400
        return response

    member = DB.fetch_member_by_rfid( tag )
    if None == member:
        DB.log_entry( tag, location, False, False )
        response.status = 404
    elif member[ 'is_active' ]:
        DB.log_entry( tag, location, True, True )
        response.status = 200
    else:
        DB.log_entry( tag, location, False, True )
        response.status = 403

    return response

@app.route( "/secure/new_tag/<tag>/<full_name>", methods = [ "PUT" ] )
def new_tag( tag, full_name ):
    response = flask.make_response()
    if (not MATCH_INT.match( tag )) or (not MATCH_NAME.match( full_name )):
        response.status = 400
        return response

    DB.add_member( full_name, tag )
    response.status = 201
    return response

@app.route( "/secure/deactivate_tag/<tag>", methods = [ "POST" ] )
def deactivate_tag( tag ):
    response = flask.make_response()
    if not MATCH_INT.match( tag ):
        response.status = 400
        return response

    DB.deactivate_member( tag )
    response.status = 200
    return response

@app.route( "/secure/reactivate_tag/<tag>", methods = [ "POST" ] )
def reactivate_tag( tag ):
    response = flask.make_response()
    if not MATCH_INT.match( tag ):
        response.status = 400
        return response

    DB.activate_member( tag )
    response.status = 200
    return response

@app.route( "/secure/search_tags", methods = [ "GET" ] )
def search_tags():
    args = flask.request.args
    response = flask.make_response()

    name = args.get( 'name' )
    tag = args.get( 'tag' )
    offset = args.get( 'offset' )
    limit = args.get( 'limit' )

    members = DB.search_members( name, tag, offset, limit )

    out = ''
    for member in members:
        out += ','.join([
            member[ 'rfid' ],
            member[ 'full_name' ],
            "1" if member[ 'active' ] else "0",
        ]) + "\n"

    response.status = 200
    response.content_type = 'text/plain'
    response.set_data( out )
    return response

@app.route( "/secure/dump_active_tags", methods = [ "GET" ] )
def dump_tags():
    out = DB.dump_active_members()
    return out

#@app.route('/', defaults={'path': ''})
#@app.route( "/<path:path>" )
#def catch_all_secure( path ):
#    print( f'Hit catch all with {path}' )
#    return flask.send_from_directory( 'static', path )
