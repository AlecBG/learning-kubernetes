import logging
import os

import psycopg2

NAMESPACE = os.environ.get('NAMESPACE')
RDS_NAME = os.environ.get('RDS_NAME')
N_REPLICAS_STATEFUL_SET = int(os.environ.get('N_REPLICAS_STATEFUL_SET'))
RDS_SERVER = os.environ.get('RDS_SERVER')

DB_DOMAIN_NAMES = [f"{RDS_NAME}-{i}.{RDS_SERVER}.{NAMESPACE}.svc.cluster.local"
                   for i in range(N_REPLICAS_STATEFUL_SET)]

RDS_PORT = os.environ.get('RDS_PORT')
RDS_USER = os.environ.get('RDS_USER')
RDS_PASSWORD = os.environ.get('RDS_PASSWORD')

RDS_DB = os.environ.get('RDS_DB')

RDS_TABLE_NAME = 'mytable'

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)

CONNECTIONS = [
    psycopg2.connect(host=domain_name,
                     database=RDS_DB,
                     user=RDS_USER,
                     password=RDS_PASSWORD,
                     port=RDS_PORT)
    for domain_name in DB_DOMAIN_NAMES
]


def drop_tables() -> None:
    command = f"DROP TABLE IF EXISTS {RDS_TABLE_NAME}"
    cursors = [c.cursor() for c in CONNECTIONS]
    for cursor in cursors:
        try:
            cursor.execute(command)
        except:
            pass

    for connection in CONNECTIONS:
        connection.commit()

    for cursor in cursors:
        cursor.close()
    logger.info("Have dropped all tables.")
    return


def count_tables() -> None:
    command = f"SELECT COUNT(*) FROM {RDS_TABLE_NAME}"
    cursors = [c.cursor() for c in CONNECTIONS]
    counts = []
    for cursor in cursors:
        cursor.execute(command)
        counts.append(cursor.fetchone()[0])
    for cursor in cursors:
        cursor.close()
    logger.info(f'counts: {counts}')


if __name__ == '__main__':
    count_tables()
    drop_tables()
