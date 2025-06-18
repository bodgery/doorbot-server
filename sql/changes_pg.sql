CREATE TABLE oauth_tokens (
    id SERIAL PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    expiration_date TIMESTAMP WITH TIME ZONE NOT NULL,
    member_id INT NOT NULL REFERENCES members (id)
);
CREATE INDEX ON oauth_tokens (member_id);
