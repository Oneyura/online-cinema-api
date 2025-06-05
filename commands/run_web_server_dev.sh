#!/bin/bash

# Start the FastAPI development server with hot reload
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /usr/src/app
