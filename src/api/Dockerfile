FROM python:3.12

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

RUN opentelemetry-bootstrap -a install

COPY ./app /code/app

EXPOSE 80

# Use uvicorn directly to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]