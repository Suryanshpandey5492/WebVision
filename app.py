from flask import Flask, render_template, request, jsonify
import asyncio
import time
import logging
from main import WebVision  # Import your WebVision class

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/query', methods=['POST'])
def process_query():
    query = request.form.get('query', '')
    
    if not query.strip():
        return jsonify({'error': 'Please enter a query'})
    
    logger.debug("[MAIN] Starting WebVision execution")
    main_start_time = time.perf_counter()
    
    try:
        # Initialize WebVision with your credentials and callback functions
        web_vision = WebVision("1234", "123", lambda a: a, lambda b: b)
        
        # Run the query
        result = asyncio.run(web_vision.run(query))
        
        # Get response (assuming get_response is part of your module)
        from shared_state import get_response 
        final_response = get_response()
        
        logger.debug(f"[MAIN] Result: {final_response}")
        
        main_end_time = time.perf_counter()
        execution_time = main_end_time - main_start_time
        logger.debug(f"[MAIN] Total execution time: {execution_time:.4f} seconds")
        
        return jsonify({
            'response': final_response,
            'execution_time': f"{execution_time:.2f}"
        })
    
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        return jsonify({'error': f"An error occurred: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)