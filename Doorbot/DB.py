import psycopg2
import re
import sqlite3

CONN = None

INSERT_MEMBER = '''
    INSERT INTO members
        (full_name, rfid, phone, email, entry_type)
    VALUES
        (%s, %s, '', '', '')
'''
FETCH_MEMBER_BY_NAME = '''
    SELECT full_name, rfid, active
    FROM members
    WHERE full_name LIKE %s
'''
FETCH_MEMBER_BY_RFID = '''
    SELECT full_name, rfid, active
    FROM members
    WHERE rfid = %s
'''

LOG_ENTRY = '''
    INSERT INTO entry_log (
        rfid
        ,location
        ,is_active_tag
        ,is_found_tag
    ) VALUES (
        %s
        ,(SELECT id FROM locations WHERE name = %s LIMIT 1)
        ,%s
        ,%s
    )
'''
FETCH_ENTRIES_START = '''
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
'''
FETCH_ENTRIES_WHERE_CLAUSE = '''
    WHERE entry_log.rfid = %s
'''
FETCH_ENTRIES_END = '''
    ORDER BY entry_log.entry_time DESC
    LIMIT %s
    OFFSET %s
'''

SET_MEMBER_ACTIVE_STATUS = '''
    UPDATE members
    SET active = %s
    WHERE rfid = %s
'''

DUMP_ACTIVE_MEMBERS = '''
    SELECT rfid FROM members WHERE active = True
'''
SQLITE_DUMP_ACTIVE_MEMBERS = '''
    SELECT rfid FROM members WHERE active = 1
'''

LOWER_NAME_SEARCH = '''
    lower(full_name) LIKE %s
'''
LIMIT = '''
    LIMIT %s
'''
OFFSET = '''
    OFFSET %s
'''

DT_CONVERT_FUNC = None



def _pg_datetime_convert( dt ):
    return dt.isoformat()

def _sqlite_datetime_convert( dt ):
    return dt

def set_db( conn ):
    global CONN
    CONN = conn

def conn():
    return CONN

def close():
    CONN.close()

def set_sqlite():
    placeholder_change = re.compile( '%s' )

    # No, python does not have sensible variable scoping rules, why do you ask?
    global INSERT_MEMBER
    global FETCH_MEMBER_BY_NAME
    global FETCH_MEMBER_BY_RFID
    global LOG_ENTRY
    global FETCH_ENTRIES_START
    global FETCH_ENTRIES_WHERE_CLAUSE
    global FETCH_ENTRIES_END
    global SET_MEMBER_ACTIVE_STATUS
    global DUMP_ACTIVE_MEMBERS
    global LOWER_NAME_SEARCH
    global LIMIT
    global OFFSET
    global DT_CONVERT_FUNC

    INSERT_MEMBER = re.sub( placeholder_change, '?', INSERT_MEMBER )
    FETCH_MEMBER_BY_NAME = re.sub( placeholder_change, '?',
        FETCH_MEMBER_BY_NAME )
    FETCH_MEMBER_BY_RFID = re.sub( placeholder_change, '?',
        FETCH_MEMBER_BY_RFID )
    LOG_ENTRY = re.sub( placeholder_change, '?', LOG_ENTRY )
    FETCH_ENTRIES_START = re.sub( placeholder_change, '?', FETCH_ENTRIES_START )
    FETCH_ENTRIES_WHERE_CLAUSE = re.sub( placeholder_change, '?',
        FETCH_ENTRIES_WHERE_CLAUSE )
    FETCH_ENTRIES_END = re.sub( placeholder_change, '?', FETCH_ENTRIES_END )
    SET_MEMBER_ACTIVE_STATUS = re.sub( placeholder_change, '?',
        SET_MEMBER_ACTIVE_STATUS )
    LOWER_NAME_SEARCH = re.sub( placeholder_change, '?', LOWER_NAME_SEARCH )
    LIMIT = re.sub( placeholder_change, '?', LIMIT )
    OFFSET = re.sub( placeholder_change, '?', OFFSET )


    DUMP_ACTIVE_MEMBERS = SQLITE_DUMP_ACTIVE_MEMBERS

    DT_CONVERT_FUNC = _sqlite_datetime_convert


def add_member(
    name: str,
    rfid: str,
):
    sql = conn()
    cur = sql.cursor()
    cur.execute( INSERT_MEMBER, ( name, rfid ) )
    cur.close()
    return

def fetch_member_by_name(
    name: str,
):
    name = name + '%'

    sql = conn()
    cur = sql.cursor()
    cur.execute( FETCH_MEMBER_BY_NAME, [ name ] )
    row = cur.fetchone()
    cur.close()

    if None == row:
        return None
    else:
        member = {
            'full_name': row[0],
            'rfid': row[1],
            'is_active': True if row[2] else False,
        }
        return member

def fetch_member_by_rfid(
    rfid: str,
):
    sql = conn()
    cur = sql.cursor()
    cur.execute( FETCH_MEMBER_BY_RFID, [ rfid ] )
    row = cur.fetchone()
    cur.close()

    if None == row:
        return None
    else:
        member = {
            'full_name': row[0],
            'rfid': row[1],
            'is_active': True if row[2] else False,
        }
        return member

def log_entry(
    rfid: str,
    location: str,
    is_active_tag: bool,
    is_found_tag: bool,
):
    sql = conn()
    cur = sql.cursor()
    cur.execute( LOG_ENTRY, [ rfid, location, is_active_tag, is_found_tag ] )
    cur.close()
    return

def _map_entry( entry ):
    result = {
        'full_name': entry[0],
        'rfid': entry[1],
        'location': entry[2],
        'entry_time': DT_CONVERT_FUNC( entry[3] ),
        'is_active_tag': True if entry[4] else False,
        'is_found_tag': True if entry[5] else False,
    }
    return result

def fetch_entries(
    limit: int = 100,
    offset: int = 0,
    tag: str = "",
):
    statement = FETCH_ENTRIES_START
    params = []
    if tag:
        statement += FETCH_ENTRIES_WHERE_CLAUSE
        params.append( tag )
    statement += FETCH_ENTRIES_END
    params.append( limit )
    params.append( offset )

    sql = conn()
    cur = sql.cursor()
    cur.execute( statement, params )
    rows = cur.fetchall()
    cur.close()

    results = map(
        _map_entry,
        rows,
    )
    return list( results )

def deactivate_member(
    rfid: str
):
    sql = conn()
    cur = sql.cursor()
    cur.execute( SET_MEMBER_ACTIVE_STATUS, ( False, rfid ) )
    cur.close()
    return

def activate_member(
    rfid: str
):
    sql = conn()
    cur = sql.cursor()
    cur.execute( SET_MEMBER_ACTIVE_STATUS, ( True, rfid ) )
    cur.close()
    return

def _map_search_members( entry ):
    result = {
        'rfid': entry[0],
        'full_name': entry[1],
        'active': True if entry[2] else False,
    }
    return result

def search_members(
    full_name: str,
    rfid: str,
    offset: int,
    limit: int,
):
    where = []
    end = []
    params = []

    if full_name:
        where.append( LOWER_NAME_SEARCH )
        params.append( full_name + '%' )

    if rfid:
        where.append( 'rfid = ?' )
        params.append( rfid )

    if limit or offset:
        end.append( 'ORDER BY join_date' )

    if limit:
        end.append( LIMIT )
        params.append( limit )

    if offset:
        end.append( OFFSET )
        params.append( offset )



    statements = [
        'SELECT rfid, full_name, active FROM members'
    ]
    if where:
        statements.append( 'WHERE' )
        statements.append( ' AND '.join( where ) )
    statements.append( ' '.join( end ) )
    statement = ' '.join( statements )

    sql = conn()
    cur = sql.cursor()
    cur.execute( statement, params )
    rows = cur.fetchall()
    cur.close()

    results = map(
        _map_search_members,
        rows,
    )
    return list( results )

def dump_active_members():
    sql = conn()
    cur = sql.cursor()
    cur.execute( DUMP_ACTIVE_MEMBERS )

    results = {}
    for row in cur.fetchall():
        rfid = row[0]
        results[ rfid ] = True
    cur.close()

    return results



DT_CONVERT_FUNC = _pg_datetime_convert
