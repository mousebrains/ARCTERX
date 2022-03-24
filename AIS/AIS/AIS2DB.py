#
# Save decoded AIS messages into a database
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

class AIS2DB(Thread):
    def __init__(self, args:ArgumentParser) -> None:
        Thread.__init__(self, "AIS2DB", args)
        self.__queue = queue.Queue()

    @staticmethod
    def addArgs(parser:ArgumentParser) -> None:
        grp = parser.add_argument_group(description="AIS2DB related options")
        grp.add_argument("--ais2dbFields", type=str, default="aisFields",
                help="AIS field table name")
        grp.add_argument("--ais2dbTable", type=str, default="ais", help="AIS table name")
        gg = grp.add_mutually_exclusive_group()
        gg.add_argument("--ais2dbSQLite3", type=str, help="SQLite3 database to write to")
        if qPSQL:
            gg.add_argument("--ais2dbPostgreSQL", type=str, help="PostgreSQL database to write to")

    @staticmethod
    def qUse(args:ArgumentParser) -> bool:
        if args.ais2dbSQLite3: return True
        return qPSQL and args.ais2dbPostgreSQL

    def put(self, payload:dict) -> None:
        self.__queue.put(payload)

    def runIt(self): # Called on thread start
        args = self.args
        qSQLite3 = args.ais2dbSQLite3
        dbname = args.ais2dbSQLite3 if qSQLite3 else args.ais2dbPostgreSQL
        logging.info("Starting %s %s", dbname, args.ais2dbTable)
        with sqlite3.connect(dbname) \
                if qSQLite3 else \
                psycopg3.connect(dbname) \
                as db:
                    self.__mkTable(db)
                    self.__process(db)

    def __mkTable(self, db) -> None:
        tbl = self.args.ais2dbTable
        fld = self.args.ais2dbFields

        sql0 = f"CREATE TABLE IF NOT EXISTS {tbl} (\n"
        sql0+=  "  mmsi TEXT, -- AIS unique identifier\n"
        sql0+=  "  key TEXT, -- Field name\n"
        sql0+=  "  t DOUBLE PRECISION, -- UTC seconds\n"
        sql0+=  "  value TEXT, -- field value\n"
        sql0+=  "  PRIMARY KEY(mmsi, key, t)\n"
        sql0+= f"); -- {tbl}"

        # This should not be needed due to the primary key is this index
        # sql1 = f"CREATE INDEX IF NOT EXISTS {tbl}_index ON {tbl} (mmsi,key,t);"

        # logging.debug("Creating table:\n%s\n%s", sql0, sql1)
        logging.debug("Creating table:\n%s\n%s", sql0)
        db.cursor().execute("BEGIN;")
        db.cursor().execute(sql0)
        # db.cursor().execute(sql1)
        db.cursor().execute("COMMIT;")

    def __process(self, db) -> None:
        tbl = self.args.ais2dbTable
        q = self.__queue
        sql = f"INSERT INTO {tbl} VALUES(?,?,?,?) ON CONFLICT DO NOTHING;"
        logging.debug("%s", sql)
        cur = db.cursor()
        while True:
            info = q.get() # Get the decrypted AIS message as a dictionary
            q.task_done()
            requiredKeys = ["mmsi", "t"]
            qGood = True
            for key in requiredKeys:
                if key not in info:
                    logging.warning("No %s field found in %s", key, info)
                    qGood = False
            if not qGood: continue
            mmsi = info["mmsi"]
            t = info["t"]
            cur.execute("BEGIN;")
            for key in info:
                if key not in requiredKeys: # Key to save
                    cur.execute(sql, (mmsi, key, t, info[key]))
            cur.execute("COMMIT;")
