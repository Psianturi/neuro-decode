FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

# Download VGG16 notop weights at build time so vision observer is active.
# Source: official Keras/TF release (stable GCS URL).
# MD5: 6d6bbae143d832006294945121d1f1fc
RUN wget -q -O /app/app/models/vgg16_weights_tf_dim_ordering_tf_kernels_notop.h5 \
    "https://storage.googleapis.com/tensorflow/keras-applications/vgg16/vgg16_weights_tf_dim_ordering_tf_kernels_notop.h5" \
    && echo "6d6bbae143d832006294945121d1f1fc  /app/app/models/vgg16_weights_tf_dim_ordering_tf_kernels_notop.h5" \
       | md5sum -c - \
    && echo "VGG16 weights verified OK"

EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
