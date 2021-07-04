import psycopg2
import sqlite3

CONN = None

INSERT_MEMBER = '''
    INSERT INTO members
        (full_name, rfid, phone, email)
    VALUES
        (?, ?, '', '')
'''
FETCH_MEMBER_BY_NAME = '''
    SELECT full_name, rfid
    FROM members
    WHERE full_name = ?
'''
FETCH_MEMBER_BY_RFID = '''
    SELECT full_name, rfid
    FROM members
    WHERE rfid = ?
'''

LOG_ENTRY = '''
    INSERT INTO entry_log (
        rfid
        ,location_id
        ,is_active_tag
        ,is_found_tag
    ) VALUES (
        ?
        ,(SELECT id FROM locations WHERE name = ? LIMIT 1)
        ,?
        ,?
    )
'''
FETCH_ENTRIES = '''
    SELECT
        entry_log.rfid
        ,locations.name
        ,entry_log.is_active_tag
        ,entry_log.is_found_tag
    FROM entry_log
    JOIN locations ON entry_log.location_id = locations.id
    ORDER BY entry_time DESC
    LIMIT ?
    OFFSET ?
'''



def set_db( conn ):
    global CONN
    CONN = conn

def conn():
    return CONN

def close():
    CONN.close()


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
        'rfid': entry[0],
        'name': entry[1],
        'is_active_tag': True if entry[2] else False,
        'is_found_tag': True if entry[3] else False,
    }
    return result

def fetch_entries(
    limit: int = 100,
    offset: int = 0,
):
    sql = conn()
    cur = sql.cursor()
    cur.execute( FETCH_ENTRIES, [ limit, offset ] )
    rows = cur.fetchall()
    cur.close()

    results = map(
        _map_entry,
        rows,
    )
    return list( results )
