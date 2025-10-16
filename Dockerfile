FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better cache utilization
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose health port (optional)
EXPOSE 8080

# Run the bot
CMD ["python", "main.py"] 