"""
Demo script showcasing advanced AI features:
1. Function Calling
2. Multi-Modal (Vision) Support
3. Web Search Integration
"""

import asyncio
import aiohttp
import json
import base64

API_BASE_URL = "http://localhost:8000/api/v1"

async def demo_function_calling():
    """Demonstrate function calling capabilities"""
    print("\n=== Function Calling Demo ===")
    
    async with aiohttp.ClientSession() as session:
        # Create a session
        async with session.post(f"{API_BASE_URL}/chat/sessions") as resp:
            session_data = await resp.json()
            session_id = session_data["session_id"]
        
        # Examples of function calling
        queries = [
            "What is 15 * 23 + sqrt(16)?",
            "Calculate the mean of these numbers: 23, 45, 67, 89, 12, 34, 56",
            "Search the web for the latest developments in quantum computing",
            "What's the sine of 45 degrees?"
        ]
        
        for query in queries:
            print(f"\nQuery: {query}")
            
            async with session.post(
                f"{API_BASE_URL}/chat/messages",
                json={
                    "message": query,
                    "session_id": session_id,
                    "model": "gpt-4"
                }
            ) as resp:
                result = await resp.json()
                print(f"Response: {result['message']['content']}")
                
                # Check if function was called
                if 'metadata' in result['message'] and 'function_call' in result['message']['metadata']:
                    func_call = result['message']['metadata']['function_call']
                    print(f"Function called: {func_call['name']}")
                    print(f"Arguments: {func_call['arguments']}")

async def demo_vision_capabilities():
    """Demonstrate multi-modal vision capabilities"""
    print("\n=== Vision Capabilities Demo ===")
    
    async with aiohttp.ClientSession() as session:
        # Create a session
        async with session.post(f"{API_BASE_URL}/chat/sessions") as resp:
            session_data = await resp.json()
            session_id = session_data["session_id"]
        
        # Example with a simple base64 encoded image
        # This is a 1x1 red pixel for demonstration
        red_pixel = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        
        print("\nAnalyzing image with GPT-4 Vision...")
        
        async with session.post(
            f"{API_BASE_URL}/chat/messages",
            json={
                "message": "What color is this image? Describe what you see.",
                "session_id": session_id,
                "model": "gpt-4-vision-preview",
                "images": [red_pixel]
            }
        ) as resp:
            result = await resp.json()
            print(f"Vision Response: {result['message']['content']}")

async def demo_web_search_integration():
    """Demonstrate web search function"""
    print("\n=== Web Search Integration Demo ===")
    
    async with aiohttp.ClientSession() as session:
        # Create a session
        async with session.post(f"{API_BASE_URL}/chat/sessions") as resp:
            session_data = await resp.json()
            session_id = session_data["session_id"]
        
        queries = [
            "Search for the current weather in San Francisco",
            "Find recent news about artificial intelligence breakthroughs",
            "What are the latest stock prices for major tech companies?"
        ]
        
        for query in queries:
            print(f"\nQuery: {query}")
            
            async with session.post(
                f"{API_BASE_URL}/chat/messages",
                json={
                    "message": query,
                    "session_id": session_id
                }
            ) as resp:
                result = await resp.json()
                print(f"Search Result: {result['message']['content'][:200]}...")

async def demo_image_upload():
    """Demonstrate image upload endpoint"""
    print("\n=== Image Upload Demo ===")
    
    # Create a simple test image (1x1 blue pixel)
    blue_pixel_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
    
    async with aiohttp.ClientSession() as session:
        # Upload single image
        form = aiohttp.FormData()
        form.add_field('file', blue_pixel_data, filename='test.png', content_type='image/png')
        
        async with session.post(f"{API_BASE_URL}/upload/image", data=form) as resp:
            result = await resp.json()
            print(f"Upload result: {json.dumps(result, indent=2)}")

async def main():
    """Run all demos"""
    print("AI Chatbot Advanced Features Demo")
    print("==================================")
    
    # Note: Make sure the API is running at localhost:8000
    
    try:
        await demo_function_calling()
        await demo_vision_capabilities()
        await demo_web_search_integration()
        await demo_image_upload()
    except aiohttp.ClientConnectorError:
        print("\nError: Could not connect to API. Make sure the server is running at localhost:8000")
    except Exception as e:
        print(f"\nError: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())