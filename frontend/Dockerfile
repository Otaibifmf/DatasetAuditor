FROM node:20-alpine AS build

WORKDIR /app

# Copy manifests first so the dependency layer caches independently of source
# changes. `npm ci` installs exactly what package-lock.json pins, so an image
# built today and one built next month get the same dependency tree.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
