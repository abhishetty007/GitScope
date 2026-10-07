FROM node:22-bookworm-slim AS dependencies
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-bookworm-slim AS builder
WORKDIR /app

ENV NODE_ENV=production
ARG GITSCOPE_SITE_URL=http://localhost:3000
ENV GITSCOPE_SITE_URL=${GITSCOPE_SITE_URL}

COPY --from=dependencies /app/node_modules ./node_modules
COPY . .

# Prisma 7 reads datasource configuration from prisma7.config.ts. Generation
# uses its build-time fallback URL and does not connect to a database.
RUN npm run db:generate
RUN npm run build

FROM node:22-bookworm-slim AS runner
WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN groupadd --system --gid 1001 nextjs \
    && useradd --system --uid 1001 --gid nextjs nextjs

COPY --from=builder --chown=nextjs:nextjs /app/public ./public
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]

# One-off release target: includes Prisma CLI/config/migrations but is not used
# by the web service. Database credentials are supplied only when it runs.
FROM dependencies AS migrator
WORKDIR /app
COPY prisma ./prisma
COPY prisma7.config.ts ./prisma7.config.ts
COPY src/lib/migration-database-url.js ./src/lib/migration-database-url.js
CMD ["npm", "run", "db:migrate:deploy"]
