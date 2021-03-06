FROM python:3.8.3-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY clean_registry.py .

CMD [ "/app/clean_registry.py" ]