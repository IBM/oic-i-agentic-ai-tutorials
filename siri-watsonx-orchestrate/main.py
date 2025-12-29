import os
import json
import logging
from typing import Optional
from contextlib import asynccontextmanager

import redis
import requests
from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
class Config:
    IBM_APIKEY: str = os.getenv("IBM_APIKEY")
    ORCHESTRATE_URL: str = os.getenv("ORCHESTRATE_URL")
    MODEL: str = os.getenv("MODEL")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_USERNAME: Optional[str] = os.getenv("REDIS_USERNAME")
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    
    def validate(self):
        """Validate required environment variables"""
        missing = []
        if not self.IBM_APIKEY:
            missing.append("IBM_APIKEY")
        if not self.ORCHESTRATE_URL:
            missing.append("ORCHESTRATE_URL")
        if not self.MODEL:
            missing.append("MODEL")
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

config = Config()

# Global variables for connection management
redis_client: Optional[redis.Redis] = None
cached_token: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global redis_client
    
    # Startup
    logger.info("Starting up application...")
    config.validate()
    
    # Initialize Redis connection
    try:
        redis_client = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            decode_responses=True,
            username=config.REDIS_USERNAME,
            password=config.REDIS_PASSWORD,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise
    
    yield
    
    logger.info("Shutting down application...")
    if redis_client:
        redis_client.close()

app = FastAPI(
    title="AI Chat API",
    description="FastAPI application for AI chat with conversation history",
    version="1.0.0",
    lifespan=lifespan
)

# Pydantic models
class Prompt(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="User query")

class ChatResponse(BaseModel):
    Watson_X_Agent_Replied: str
    # status: str = "success"

class ErrorResponse(BaseModel):
    detail: str
    status: str = "error"

# Dependency injection
def get_redis_client() -> redis.Redis:
    """Get Redis client dependency"""
    if redis_client is None:
        raise HTTPException(status_code=500, detail="Redis connection not available")
    return redis_client

# Utility functions
def get_iam_token() -> str:
    """Get IBM IAM token with caching and error handling"""
    global cached_token
    
    # Simple token caching (in production, implement proper token refresh)
    if cached_token:
        return cached_token
    
    token_url = "https://iam.cloud.ibm.com/identity/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        "apikey": config.IBM_APIKEY,
    }
    
    try:
        response = requests.post(
            token_url, 
            headers=headers, 
            data=data, 
            timeout=10
        )
        response.raise_for_status()
        
        token_data = response.json()
        cached_token = token_data["access_token"]
        logger.info("Successfully obtained IAM token")
        return cached_token
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get IAM token: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to authenticate with IBM Cloud"
        )
    except KeyError:
        logger.error("Invalid token response format")
        raise HTTPException(
            status_code=500, 
            detail="Invalid authentication response"
        )

def get_conversation_history(redis_client: redis.Redis, limit: int = 5) -> str:
    """Get conversation history from Redis"""
    try:
        messages = redis_client.lrange("messages", 0, limit - 1)
        if not messages:
            return "No previous conversation history."
        
        history = "\n".join([
            f"{idx}. {msg}" 
            for idx, msg in enumerate(messages, start=1) # type: ignore
        ])
        return history
        
    except redis.RedisError as e:
        logger.error(f"Redis error getting history: {e}")
        return "Unable to retrieve conversation history."

def call_orchestrate(token: str, query: str, redis_client: redis.Redis) -> str:
    """Call the orchestrate API with improved error handling"""
    
    # Get conversation history
    history = get_conversation_history(redis_client)
    enhanced_query = f"QUERY: {query}\n\nConversation history (last 5 messages):\n{history}"
    # print("Enhanced Query:",enhanced_query)
    
    logger.info(f"Processing query with history context")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "model": config.MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful AI assistant. Provide complete, accurate responses "
                    "based on the conversation history and current query. "
                    "Be concise but thorough. Do not ask follow-up questions unless "
                    "absolutely necessary for clarification."
                ),
            },
            {"role": "user", "content": enhanced_query},
        ],
        "stream": False,
    }

    try:
        response = requests.post(
            config.ORCHESTRATE_URL, 
            headers=headers, 
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        # print(data)

        ai_response = data["choices"][0]["message"]["content"]
        
        # Store response in Redis with error handling
        try:
            redis_client.lpush("messages", ai_response)
            # Keep only last 10 messages to prevent unbounded growth
            redis_client.ltrim("messages", 0, 9)
        except redis.RedisError as e:
            logger.error(f"Failed to store message in Redis: {e}")
            # Continue anyway - don't fail the request
        
        return ai_response
        
    except requests.exceptions.Timeout:
        logger.error("Request to orchestrate API timed out")
        raise HTTPException(
            status_code=504, 
            detail="Request timed out. Please try again."
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        raise HTTPException(
            status_code=502, 
            detail="Failed to communicate with AI service"
        )
    except (KeyError, json.JSONDecodeError) as e:
        logger.error(f"Invalid API response format: {e}")
        raise HTTPException(
            status_code=502, 
            detail="Invalid response from AI service"
        )

# API Routes
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test Redis connection
        redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

@app.post("/ask", response_model=ChatResponse)
async def ask(
    prompt: Prompt, 
    redis_client: redis.Redis = Depends(get_redis_client)#):
) -> ChatResponse:
    """
    Process a user query and return AI response with conversation history context
    """
    try:
        logger.info(f"Processing query: {prompt.query[:50]}...")
        
        # Get authentication token
        token = get_iam_token()
        
        # Call orchestrate API
        answer = call_orchestrate(token, prompt.query, redis_client)
        
        logger.info("Successfully processed query")
        # print(answer)
        print(ChatResponse(Watson_X_Agent_Replied=answer))
        return ChatResponse(Watson_X_Agent_Replied=answer)
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing query: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while processing your request"
        )

@app.get("/history")
async def get_history(
    limit: int = Query(default=5, ge=1, le=20, description="Number of messages to retrieve"),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """Get conversation history"""
    try:
        messages = redis_client.lrange("messages", 0, limit - 1)
        return {
            "messages": messages,
            "count": len(messages),
            "status": "success"
        }
    except redis.RedisError as e:
        logger.error(f"Failed to get history: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve conversation history"
        )
    


@app.delete("/history")
async def clear_history(
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """Clear conversation history"""
    try:
        redis_client.delete("messages")
        logger.info("Conversation history cleared")
        return {"message": "Conversation history cleared", "status": "success"}
    except redis.RedisError as e:
        logger.error(f"Failed to clear history: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to clear conversation history"
        )

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return ErrorResponse(detail=exc.detail)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)