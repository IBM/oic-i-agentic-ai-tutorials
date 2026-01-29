# ---- Build Stage ----
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install && npm install node-rsa

# Copy all source code
COPY . .

# Build the Next.js app (with turbopack)
RUN npm run build

# ---- Production Stage ----
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

# Copy only required files
COPY --from=builder /app/package*.json ./
RUN npm install --omit=dev --ignore-scripts --prefer-offline && npm install node-rsa

# Copy build output
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

# Expose port
EXPOSE 8080

# Run the app
CMD ["npm", "start"]
