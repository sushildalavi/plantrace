FROM debian:bookworm-slim AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake pkg-config protobuf-compiler libprotobuf-dev \
    libpqxx-dev librdkafka-dev libssl-dev ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN cmake -S . -B build && cmake --build build -j

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpqxx-6.4 libprotobuf32 librdkafka1 librdkafka++1 libssl3 ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=build /app/build/plantrace-collector /usr/local/bin/plantrace-collector
ENTRYPOINT ["plantrace-collector"]
