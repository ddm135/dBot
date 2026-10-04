"""The database schema, as an ordered list of migrations.

Never edit a migration that has shipped; append a new one instead.
"""

MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        CREATE TABLE word_pings (
            guild_id bigint NOT NULL,
            user_id  bigint NOT NULL,
            word     text   NOT NULL,
            count    integer NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id, word)
        );

        CREATE TABLE word_ping_ignores (
            guild_id  bigint NOT NULL,
            user_id   bigint NOT NULL,
            word      text   NOT NULL,
            kind      text   NOT NULL CHECK (kind IN ('user', 'channel')),
            target_id bigint NOT NULL,
            PRIMARY KEY (guild_id, user_id, word, kind, target_id),
            FOREIGN KEY (guild_id, user_id, word)
                REFERENCES word_pings (guild_id, user_id, word) ON DELETE CASCADE
        );

        CREATE TABLE stored_roles (
            user_id bigint NOT NULL,
            role_id bigint NOT NULL,
            PRIMARY KEY (user_id, role_id)
        );

        CREATE TABLE ssl_history (
            game      text    NOT NULL,
            day       date    NOT NULL,
            song_code integer NOT NULL,
            deck_code integer NOT NULL,
            PRIMARY KEY (game, day)
        );
        CREATE INDEX ssl_history_song_idx ON ssl_history (game, song_code, day DESC);
        CREATE INDEX ssl_history_deck_idx ON ssl_history (game, deck_code, day DESC);

        CREATE TABLE bonus_subscriptions (
            user_id   bigint  NOT NULL,
            game      text    NOT NULL,
            deck_code integer NOT NULL,
            PRIMARY KEY (user_id, game, deck_code)
        );
        CREATE INDEX bonus_subscriptions_deck_idx
            ON bonus_subscriptions (game, deck_code);

        CREATE TABLE bonus_preferences (
            user_id     bigint PRIMARY KEY,
            start_hours smallint NOT NULL DEFAULT 1 CHECK (start_hours BETWEEN 0 AND 23),
            end_hours   smallint NOT NULL DEFAULT 1 CHECK (end_hours BETWEEN 0 AND 23)
        );

        CREATE TABLE bonus_ping_log (
            user_id bigint NOT NULL,
            game    text   NOT NULL,
            day     date   NOT NULL,
            kind    text   NOT NULL CHECK (kind IN ('start', 'end')),
            sent_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, game, day, kind)
        );

        CREATE TABLE live_themes (
            user_id bigint  NOT NULL,
            game    text    NOT NULL,
            amount  integer NOT NULL CHECK (amount >= 0),
            PRIMARY KEY (user_id, game)
        );

        CREATE TABLE game_credentials (
            game   text  PRIMARY KEY,
            fields jsonb NOT NULL
        );

        CREATE TABLE search_aliases (
            game  text    NOT NULL,
            kind  text    NOT NULL CHECK (kind IN ('song', 'deck')),
            code  integer NOT NULL,
            alias text    NOT NULL,
            PRIMARY KEY (game, kind, code, alias)
        );
        """,
    ),
    (
        2,
        """
        CREATE TABLE display_names (
            game text    NOT NULL,
            kind text    NOT NULL CHECK (kind IN ('song', 'deck')),
            code integer NOT NULL,
            name text    NOT NULL,
            PRIMARY KEY (game, kind, code)
        );
        """,
    ),
    (
        3,
        """
        CREATE TABLE song_stats (
            game text    NOT NULL,
            song integer NOT NULL,
            data jsonb   NOT NULL,
            PRIMARY KEY (game, song)
        );
        CREATE TABLE song_stats_versions (
            game    text   PRIMARY KEY,
            version bigint NOT NULL
        );
        """,
    ),
    (
        4,
        """
        ALTER TABLE bonus_preferences
            DROP CONSTRAINT bonus_preferences_start_hours_check,
            DROP CONSTRAINT bonus_preferences_end_hours_check,
            ADD CHECK (start_hours BETWEEN 0 AND 47),
            ADD CHECK (end_hours BETWEEN 0 AND 47);
        """,
    ),
)
