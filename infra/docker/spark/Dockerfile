# Kafka 커넥터를 이미지에 구워 넣는다.
# --packages 로 실행 시점에 받으면 오프라인에서 기동이 실패하고,
# 실행마다 해석 시간이 붙는다. 운영에서는 의존성을 이미지에 고정한다.
ARG SPARK_VERSION
FROM apache/spark:${SPARK_VERSION}

ARG SPARK_VERSION
USER root

# 전이 의존성(kafka-clients, commons-pool2, token-provider)의 버전을
# 직접 적지 않고 Ivy 에게 해석시킨다. 버전을 손으로 박으면 Spark 업그레이드 때 깨진다.
RUN echo ':quit' | /opt/spark/bin/spark-shell \
        --packages org.apache.spark:spark-sql-kafka-0-10_2.13:${SPARK_VERSION} \
        --conf spark.jars.ivy=/tmp/ivy \
        --conf spark.ui.enabled=false \
    && cp /tmp/ivy/jars/*.jar /opt/spark/jars/ \
    && rm -rf /tmp/ivy /root/.ivy2 /root/.m2

USER spark