# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the container at /usr/src/app
COPY requirements.txt ./

# Install system dependencies including cron
RUN apt-get update && apt-get install -y cron

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY . .

# Set execute permissions for the shell scripts
RUN chmod +x /usr/src/app/entrypoint.sh /usr/src/app/loop-runner.sh

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable
ENV NAME World

# Run entrypoint.sh when the container launches
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
