# python3.x-alpine misses apt which is essential to install gcc in order to use one of the dependencies, so do not use it!
FROM python:3.13-slim-bookworm 

# Set working directory
WORKDIR /piantagione

# Copy files
COPY controller.py requirements.txt config.json ./

# Install build dependencies
RUN apt update && apt install -y libpq-dev gcc python3-dev &&  rm -rf /var/lib/apt/lists/*
RUN pip install "psycopg[binary]"
RUN pip install "psycopg[c]"
RUN pip install --no-cache-dir -r requirements.txt
RUN chmod +x ./entrypoint.sh


# Set environment variable for security and abstraction
ENV BOT_TOKEN = "REDACTED"
ENV I2C_EXPANDER = "REDACTED"
ENV DB_USERNAME "REDACTED"
ENV DB_PASSWORD "REDACTED"
ENV DB_PORT "REDACTED"
ENV DB_CONTAINER_NAME "REDACTED"
ENV DB_NAME "REDACTED"
ENV TIMEZONE "REDACTED"
# These values are for strawberries, but modify according to the type of plant you are cultivating
ENV TEMPERATURE_THRESHOLD "20.00"
ENV MOISTURE_THRESHOLD "75.00"
# Run controller
CMD ["chmod +x ", "entrypoint.sh"]
ENTRYPOINT ["./entrypoint.sh"]
