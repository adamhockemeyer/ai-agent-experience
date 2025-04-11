FROM python:3.12

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

RUN opentelemetry-bootstrap -a install

COPY ./app /code/app

EXPOSE 80

#CMD [ "opentelemetry-instrument", "python", "-m", "uvicorn", "app.main:app", "--loop", "asyncio", "--host", "0.0.0.0", "--port", "8000"]

CMD [ "fastapi", "run", "app.main.py", "--port", "80"]