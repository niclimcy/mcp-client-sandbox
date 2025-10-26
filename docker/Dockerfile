FROM python:3.14-alpine
WORKDIR /app
RUN apk add nodejs npm
RUN pip install uv
RUN apk add --no-cache docker-cli bash curl

COPY . . 

CMD ["tail", "-f", "/dev/null"]