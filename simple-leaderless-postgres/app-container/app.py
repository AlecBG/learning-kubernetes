from collections import Counter
import json
import logging
import os
from typing import Any, Dict, Optional, Sequence, Tuple

import flask
from psycopg2.pool import ThreadedConnectionPool

app = flask.Flask(__name__)

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

WRITE_FRACTION_QUORUM = 0.51
READ_FRACTION_QUORUM = 0.51
assert WRITE_FRACTION_QUORUM + READ_FRACTION_QUORUM > 1

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)

logging.info(f"RDS_PORT: {RDS_PORT}\nRDS_USER: {RDS_USER}\nRDS_PASSWORD: {RDS_PASSWORD}\nRDS_DB: {RDS_DB}")
CONNECTION_POOLS = [
        ThreadedConnectionPool(1, 10,
                               host=domain_name,
                               database=RDS_DB,
                               user=RDS_USER,
                               password=RDS_PASSWORD,
                               port=RDS_PORT)
        for domain_name in DB_DOMAIN_NAMES
    ]


@app.route('/health/check', methods=['GET'])
def health_check():
    return {'Feeling healthy': True}, 200


@app.route('/readiness/check', methods=['GET'])
def readiness_check():
    command = "SELECT 1"
    was_successful_write = execute_write_command(command)
    _, was_successful_read = execute_read_command(command)
    if was_successful_write and was_successful_read:
        return {'ready': True}, 200
    return {'ready': False}, 400


@app.route('/api', methods=['GET', 'PUT'])
def interact():
    create_table_successful = create_table()
    if not create_table_successful:
        return flask.jsonify({'create-table': 'FAILED'}), 500
    if flask.request.method == 'PUT':
        data = json.loads(flask.request.data)
        try:
            name = get_and_verify_name(data)
            age = get_and_verify_age(data)
        except ValueError as e:
            return flask.jsonify({'error': str(e)}), 400
        was_successful = write_to_table(name, age)
        if was_successful:
            return flask.jsonify({'write': 'successful'}),200
        else:
            return flask.jsonify({'error': 'Write failed', 'name': name, 'age': age}), 500

    elif flask.request.method == 'GET':
        data = json.loads(flask.request.data)
        try:
            name = get_and_verify_name(data)
        except ValueError as e:
            return flask.jsonify({'error': str(e)}), 400

        age = read_age(name)
        if age:
            return flask.jsonify({'name': name, 'age': age}), 200
        else:
            return flask.jsonify({'error': 'Read failed', 'name': name}), 500


def get_and_verify_age(data: Dict) -> int:
    age = data.get('age')
    if age is None:
        raise ValueError('age not present, age must be a non-null integer')
    try:
        age = int(age)
    except:
        raise ValueError('age is not an integer, age must be an integer')
    return age


def get_and_verify_name(data: Dict) -> str:
    name = data.get('name')
    if name is None:
        raise ValueError('name not present, name must be a non-null string')
    return name


def execute_write_command(command: str, variables: Optional[Sequence[Any]] = None) -> bool:
    logger.info(f'execute_write_command\ncommand: {command}\nvariables: {variables}')
    connections = [pool.getconn() for pool in CONNECTION_POOLS]
    try:
        cursors = [c.cursor() for c in connections]
        n_successful_attempts = 0
        was_successful = False
        for cursor in cursors:
            try:
                cursor.execute(command, variables)
            except:
                pass
            else:  # If successful
                n_successful_attempts += 1
        n_quorum = int(len(connections) * WRITE_FRACTION_QUORUM) + 1
        logger.info(f'{n_successful_attempts} write attempts. Quorum size: {n_quorum}')

        if n_successful_attempts >= n_quorum:
            for connection in connections:
                connection.commit()
            was_successful = True

        for cursor in cursors:
            cursor.close()
    finally:
        for pool, connection in zip(CONNECTION_POOLS, connections):
            pool.putconn(connection)
    return was_successful


def execute_read_command(command: str, variables: Optional[Sequence[Any]] = None) -> Tuple[Tuple[Any, ...], bool]:
    logger.info(f'execute_read_command\ncommand: {command}\nvariables: {variables}')
    connections = [pool.getconn() for pool in CONNECTION_POOLS]
    try:
        cursors = [c.cursor() for c in connections]
        values = []
        was_successful = False
        read_value = None
        for cursor in cursors:
            cursor.execute(command, variables)
            values.append(cursor.fetchone())
        counter = Counter(values)
        n_quorum = int(len(CONNECTION_POOLS) * READ_FRACTION_QUORUM) + 1
        logger.info(f'counter of read values: {counter}. Quorum size {n_quorum}')
        for value in values:
            if counter[value] >= n_quorum + 1:
                was_successful = True
                read_value = value
        for cursor in cursors:
            cursor.close()
    finally:
        for pool, connection in zip(CONNECTION_POOLS, connections):
            pool.putconn(connection)
    logger.info(f'read_value: {read_value}    was_successful: {was_successful}')
    return read_value, was_successful


def create_table() -> bool:
    command = f"""
    CREATE TABLE IF NOT EXISTS {RDS_TABLE_NAME} (
        name TEXT PRIMARY KEY NOT NULL,
        age integer NOT NULL
    );
    """
    return execute_write_command(command)


def write_to_table(name: str, age: int) -> bool:
    command = f"INSERT INTO {RDS_TABLE_NAME} (name, age) VALUES (%s, %s)"
    return execute_write_command(command, (name, age))


def read_age(name: str) -> int:
    command = f'SELECT age FROM {RDS_TABLE_NAME} WHERE name = %s'
    value, was_successful = execute_read_command(command, (name,))
    age = None
    if was_successful:
        if value:
            age = value[0]
    return age


if __name__ == '__main__':
    app.run(host='0.0.0.0', port='80')
