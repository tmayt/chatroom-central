FROM node:18-alpine as build
WORKDIR /app
# copy package.json only (package-lock.json may be absent in scaffold)
COPY frontend/package.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
