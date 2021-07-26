FROM python:3.9
RUN pip install flask dnspython psycopg2
COPY app.py /opt/apt/app.py
ENTRYPOINT ["python", "/opt/apt/app.py"]
