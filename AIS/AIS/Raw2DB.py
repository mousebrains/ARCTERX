#
# Save datagrams into a database
#
# June-2021, Pat Welch, pat@mousebrains.com

from argparse import ArgumentParser
from TPWUtils.Thread import Thread
import logging
import queue
import sqlite3
try:
    import psycopg3
    qPSQL = True
except:
    qPSQL = False

class Raw2DB(Thread):
    def __init__(self, args:ArgumentParser) -> None:
        Thread.__init__(self, "R2DB", args)
        self.__queue = queue.Queue()

    @staticmethod
    def addArgs(parser:ArgumentParser) -> None:
        grp = parser.add_argument_group(description="Raw2DB related options")
        grp.add_argument("--r2dbTable", type=str, default="raw", help="Database table name")
        gg = grp.add_mutually_exclusive_group()
        gg.add_argument("--r2dbSQLite3", type=str, help="SQLite3 database to write to")
        if qPSQL:
            gg.add_argument("--r2dbPostgreSQL", type=str, help="PostgreSQL database to write to")

    @staticmethod
    def qUse(args:ArgumentParser) -> bool:
        if args.r2dbSQLite3: return True
        return qPSQL and self.args.r2dbPostgreSQL

    def put(self, payload:tuple[float, str, int, bytes]) -> None:
        self.__queue.put(payload)

    def runIt(self): # Called on thread start
        args = self.args
        qSQLite3 = args.r2dbSQLite3
        dbname = args.r2dbSQLite3 if qSQLite3 else args.r2dbPostgreSQL
        logging.info("Starting %s %s", dbname, args.r2dbTable)
        with sqlite3.connect(dbname) \
                if qSQLite3 else \
                psycopg3.connect(dbname) \
                as db:
                    self.__mkTable(db)
                    self.__process(db)

    def __mkTable(self, db) -> None:
        tbl = self.args.r2dbTable
        sql = f"CREATE TABLE IF NOT EXISTS {tbl} (\n"
        sql+=  "  t DOUBLE PRECISION, -- UTC seconds\n"
        sql+=  "  ipAddr TEXT,\n"
        sql+=  "  port INTEGER,\n"
        sql+=  "  msg TEXT, -- Datagram\n"
        sql+=  "  PRIMARY KEY(t, msg)\n"
        sql+= f"); -- {tbl}"
        logging.debug("Creating table:\n%s", sql)
        db.cursor().execute("BEGIN;")
        db.cursor().execute(sql)
        db.cursor().execute("COMMIT;")

    def __process(self, db) -> None:
        tbl = self.args.r2dbTable
        q = self.__queue
        sql = f"INSERT INTO {tbl} VALUES(?,?,?,?) ON CONFLICT DO NOTHING;"
        logging.debug("%s", sql)
        cur = db.cursor()
        while True:
            payload = q.get()
            logging.debug("Received %s", payload)
            cur.execute("BEGIN;")
            cur.execute(sql, payload)
            cur.execute("COMMIT;")
            q.task_done()
