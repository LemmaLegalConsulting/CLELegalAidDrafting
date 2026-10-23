FROM node:26.12.1-alpine

# eMudhra certificate incident: refresh each stage's system trust store.
RUN apk add --no-cache --upgrade ca-certificates

WORKDIR /app

COPY frontend/package*.json ./
RUN npm install

COPY frontend /app

