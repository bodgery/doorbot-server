-- For searching text fields with a good index
CREATE EXTENSION pg_trgm;

CREATE TABLE members (
    id SERIAL PRIMARY KEY NOT NULL,
    rfid TEXT UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    mms_id TEXT UNIQUE,
    full_name TEXT NOT NULL,
    join_date DATE NOT NULL DEFAULT NOW(),
    end_date DATE,
    phone TEXT NOT NULL,
    email TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    notes TEXT,
    password_type TEXT,
    encoded_password TEXT,
    username TEXT UNIQUE
);
CREATE INDEX members_full_name_trgm_idx ON members
    USING gist (full_name gist_trgm_ops);

CREATE TABLE locations (
    id SERIAL PRIMARY KEY NOT NULL,
    name TEXT NOT NULL UNIQUE,
    hostname TEXT
);
INSERT INTO locations (name) VALUES
    ( 'cleanroom.door' )
    ,( 'garage.door' )
    ,( 'woodshop.door' )
    ,( 'dummy' );

CREATE TABLE entry_log (
    id              SERIAL PRIMARY KEY NOT NULL,
    -- This could be some random RFID tag, which we may not have in our 
    -- database.  So don't reference tags in bodgery_rfid directly.
    rfid            TEXT NOT NULL,
    entry_time      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_active_tag   BOOLEAN NOT NULL,
    is_found_tag    BOOLEAN NOT NULL,
    location        INT REFERENCES locations (id)
);
CREATE INDEX ON entry_log (entry_time DESC);

CREATE TABLE roles (
    id SERIAL PRIMARY KEY NOT NULL,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE role_members (
    id SERIAL PRIMARY KEY NOT NULL,
    member_id INT REFERENCES members (id),
    role_id INT REFERENCES roles (id)
);
CREATE INDEX ON role_members (member_id);
CREATE INDEX ON role_members (role_id);

CREATE TABLE permissions (
    id SERIAL PRIMARY KEY NOT NULL,
    name TEXT NOT NULL UNIQUE,
    role_id INT REFERENCES roles (id)
);

CREATE TABLE role_permissions (
    id SERIAL PRIMARY KEY NOT NULL,
    role_id INT REFERENCES roles (id),
    permission_id INT REFERENCES permissions(id)
);
CREATE INDEX ON role_permissions (role_id);
CREATE INDEX ON role_permissions (permission_id);

CREATE TABLE oauth_tokens (
    id SERIAL PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    expiration_date TIMESTAMP WITH TIME ZONE NOT NULL,
    member_id INT NOT NULL REFERENCES members (id)
);
CREATE INDEX ON oauth_tokens (member_id);
