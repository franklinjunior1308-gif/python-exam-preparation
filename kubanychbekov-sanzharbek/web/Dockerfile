FROM oven/bun:1 AS build
WORKDIR /app
COPY package.json bun.lock ./
# retry: a dropped connection while downloading packages must not break `make up`
RUN for attempt in 1 2 3; do bun install --frozen-lockfile && exit 0; echo "bun install failed (attempt $attempt), retrying"; sleep 5; done; exit 1
COPY . .
RUN bun run build

FROM oven/bun:1 AS run
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["bun", "server.js"]
