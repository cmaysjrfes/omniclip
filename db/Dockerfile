FROM node:22-alpine
WORKDIR /db
COPY package.json ./
RUN npm install
COPY prisma ./prisma
