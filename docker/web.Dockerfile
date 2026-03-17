FROM oven/bun:latest AS builder

WORKDIR /app

COPY web/package.json web/bun.lock* ./
RUN bun install --frozen-lockfile

COPY web/ .
RUN bun run build

# Serve the built output with a lightweight static server
FROM oven/bun:latest

WORKDIR /app

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package.json ./

EXPOSE 5173

CMD ["bun", "--hot", "src/index.ts"]
