#!/usr/bin/env bash
# 토픽을 선언적으로 생성한다. 여러 번 실행해도 결과는 같다.
# auto.create.topics.enable=false 이므로 이 스크립트가 유일한 생성 경로다.
set -euo pipefail

TOPIC=gharchive.events.raw
BOOTSTRAP=kafka:9092

/opt/kafka/bin/kafka-topics.sh --bootstrap-server "$BOOTSTRAP" \
    --create --if-not-exists \
    --topic "$TOPIC" \
    --partitions "$TOPIC_PARTITIONS" \
    --replication-factor 1 \
    --config "max.message.bytes=$MAX_MESSAGE_BYTES" \
    --config "retention.bytes=$RETENTION_BYTES_PER_PARTITION" \
    --config "retention.ms=$RETENTION_MS" \
    --config compression.type=zstd

# 이미 존재하던 토픽은 --create 로 설정이 바뀌지 않으므로 따로 맞춰준다.
/opt/kafka/bin/kafka-configs.sh --bootstrap-server "$BOOTSTRAP" \
    --entity-type topics --entity-name "$TOPIC" --alter \
    --add-config "max.message.bytes=$MAX_MESSAGE_BYTES,retention.bytes=$RETENTION_BYTES_PER_PARTITION,retention.ms=$RETENTION_MS,compression.type=zstd"

/opt/kafka/bin/kafka-topics.sh --bootstrap-server "$BOOTSTRAP" --describe --topic "$TOPIC"