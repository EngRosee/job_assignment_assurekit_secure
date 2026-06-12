import os
import sys
import time
import datetime

from flask import Flask, Response
from flask import send_from_directory
from flask_cors import CORS, cross_origin
from flask_jwt_extended import JWTManager

import psycopg2
from psycopg2 import pool

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY', os.urandom(32))

CORS(app, resources={r"/api/*": {"origins": ["https://your-trusted-domain.com"]}})
DB_NAME = os.environ.get('POSTGRES_DB') or os.environ.get('POSTGRES_USER')
DB_HOST = os.environ.get('POSTGRES_HOST')
DB_USER = os.environ.get('POSTGRES_USER')
DB_PASS = os.environ.get('POSTGRES_PASSWORD')
DB_PORT = os.environ.get('POSTGRES_PORT', '5432')

if not all([DB_HOST, DB_USER, DB_PASS, DB_NAME]):
    print("ERROR: Missing required database environment variables.")
    print("Required: POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB or POSTGRES_USER as dbname.")
    sys.exit(1)

conn_pool = None

def init_pool():
    global conn_pool
    if conn_pool:
        try:
            conn_pool.closeall()
        except Exception:
            pass
    conn_pool = psycopg2.pool.ThreadedConnectionPool(
        1,
        2,
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        dbname=DB_NAME,
        port=DB_PORT
    )
    print("Database connection pool established")

init_pool()

class DB():
    def _getConnection(self):
        global conn_pool
        while True:
            if not conn_pool:
                time.sleep(1)
                init_pool()
                continue
            try:
                conn = conn_pool.getconn()
                if conn:
                    return conn
            except psycopg2.pool.PoolError:
                time.sleep(0.5)
                continue
            except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
                print(f"Connection pool error: {e}, recreating...")
                init_pool()
                time.sleep(1)
                continue
            except Exception as e:
                print(f"Unexpected error getting connection: {e}")
                time.sleep(1)
                continue

    def _releaseConnection(self, conn):
        global conn_pool
        if conn and conn_pool:
            try:
                conn_pool.putconn(conn)
            except Exception as e:
                print(f"Error releasing connection: {e}")

    def run(self, query, args=()):
        conn = None
        try:
            conn = self._getConnection()
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(query, args)
            cur.close()
            return True
        except Exception as e:
            print(f"Error in run: {e}")
            raise
        finally:
            if conn:
                self._releaseConnection(conn)

    def execute(self, query, args=()):
        conn = None
        try:
            conn = self._getConnection()
            cur = conn.cursor()
            cur.execute(query, args)
            result = cur.fetchone()
            cur.close()
            return result
        except Exception as e:
            print(f"Error in execute: {e}")
            raise
        finally:
            if conn:
                self._releaseConnection(conn)

    def query_db(self, query, args=(), one=False):
        conn = None
        try:
            conn = self._getConnection()
            cur = conn.cursor()
            cur.execute(query, args)
            if cur.description is None:
                cur.close()
                return [] if not one else None
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            result_list = [dict(zip(columns, row)) for row in rows]
            if one:
                return result_list[0] if result_list else None
            return result_list
        except Exception as e:
            print(f"Error in query_db: {e}")
            raise
        finally:
            if conn:
                self._releaseConnection(conn)

db = DB()

from autho_blueprint import autho
app.register_blueprint(autho, url_prefix="/")

from data_blueprint import data
app.register_blueprint(data, url_prefix="/")

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    if os.environ.get("ENV") == "production":
        debug_mode = False
    port = int(os.environ.get("PORT", 8888))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
    #Fix Bugs By Rose
