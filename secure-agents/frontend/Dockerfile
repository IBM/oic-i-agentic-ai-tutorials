# Stage 0, "build-stage", based on Node.js, to build and compile the frontend
FROM --platform=$BUILDPLATFORM registry.access.redhat.com/ubi8/nodejs-20 AS base

WORKDIR /app

USER root

COPY package*.json /app/

RUN npm install

COPY ./ /app/


FROM base AS build-stage

ARG VITE_API_URL=${VITE_API_URL}

RUN npm run build


# Stage 1, based on Nginx, to have only the compiled app, ready for production with Nginx
# FROM nginx:1
FROM ghcr.io/nginxinc/nginx-unprivileged:stable-alpine

EXPOSE 8080
COPY --from=build-stage /app/dist/ /usr/share/nginx/html

COPY ./nginx.conf /etc/nginx/conf.d/default.conf
COPY ./nginx-backend-not-found.conf /etc/nginx/extra-conf.d/backend-not-found.conf
