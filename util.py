#!/usr/bin/env python

"""Utility methods"""

__email__ = "nicolas.maire@unibas.ch"
__status__ = "Alpha"

import uuid


def query_db_all(db_cursor, query):
    db_cursor.execute(query)
    return db_cursor.fetchall()


def query_db_one(db_cursor, query):
    db_cursor.execute(query)
    return db_cursor.fetchone()


def create_uuid():
    return str(uuid.uuid1()).replace('-', '')
