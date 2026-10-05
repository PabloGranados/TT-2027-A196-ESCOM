FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --include=optional
COPY . .
CMD ["npm", "run", "dev", "--", "--host"]