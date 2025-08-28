#!/bin/bash

# Load Testing Script for AI Chatbot System
# Provides different testing scenarios and configurations

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
HOST=${HOST:-"http://localhost:8000"}
OUTPUT_DIR=${OUTPUT_DIR:-"./reports"}
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo -e "${GREEN}🚀 AI Chatbot Load Testing Suite${NC}"
echo "Target Host: $HOST"
echo "Reports Directory: $OUTPUT_DIR"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Function to run load test
run_load_test() {
    local test_name=$1
    local users=$2
    local spawn_rate=$3
    local run_time=$4
    local description=$5
    
    echo -e "${YELLOW}Running $test_name...${NC}"
    echo "Description: $description"
    echo "Users: $users, Spawn Rate: $spawn_rate, Duration: $run_time"
    echo ""
    
    local report_file="$OUTPUT_DIR/${test_name}_${TIMESTAMP}"
    
    # Run locust with specified parameters
    locust -f locustfile.py \
        --host="$HOST" \
        --users="$users" \
        --spawn-rate="$spawn_rate" \
        --run-time="$run_time" \
        --html="${report_file}.html" \
        --csv="${report_file}" \
        --headless \
        --print-stats \
        --only-summary
    
    echo -e "${GREEN}✅ $test_name completed${NC}"
    echo "Report: ${report_file}.html"
    echo ""
}

# Function to run WebSocket-specific tests
run_websocket_test() {
    local test_name=$1
    local users=$2
    local duration=$3
    
    echo -e "${YELLOW}Running $test_name...${NC}"
    echo "WebSocket-focused test with $users concurrent connections for $duration"
    echo ""
    
    # Use WebSocket-heavy user class
    locust -f locustfile.py \
        --host="$HOST" \
        --users="$users" \
        --spawn-rate=10 \
        --run-time="$duration" \
        --html="$OUTPUT_DIR/${test_name}_${TIMESTAMP}.html" \
        --csv="$OUTPUT_DIR/${test_name}_${TIMESTAMP}" \
        --user-classes="WebSocketTaskSet" \
        --headless \
        --print-stats
    
    echo -e "${GREEN}✅ $test_name completed${NC}"
    echo ""
}

# Function to run stress test
run_stress_test() {
    echo -e "${YELLOW}Running Stress Test...${NC}"
    echo "This test will push the system to its limits"
    echo ""
    
    locust -f locustfile.py \
        --host="$HOST" \
        --users=2000 \
        --spawn-rate=100 \
        --run-time="10m" \
        --html="$OUTPUT_DIR/stress_test_${TIMESTAMP}.html" \
        --csv="$OUTPUT_DIR/stress_test_${TIMESTAMP}" \
        --user-classes="StressTestUser" \
        --headless \
        --print-stats
    
    echo -e "${GREEN}✅ Stress test completed${NC}"
    echo ""
}

# Function to run capacity test
run_capacity_test() {
    echo -e "${YELLOW}Running Capacity Test...${NC}"
    echo "Gradually increasing load to find system limits"
    echo ""
    
    # Step-wise load increase
    for users in 50 100 200 500 1000; do
        echo "Testing with $users users..."
        
        locust -f locustfile.py \
            --host="$HOST" \
            --users="$users" \
            --spawn-rate=20 \
            --run-time="5m" \
            --html="$OUTPUT_DIR/capacity_${users}users_${TIMESTAMP}.html" \
            --csv="$OUTPUT_DIR/capacity_${users}users_${TIMESTAMP}" \
            --headless \
            --only-summary
        
        echo "Waiting 30 seconds before next test..."
        sleep 30
    done
    
    echo -e "${GREEN}✅ Capacity test completed${NC}"
    echo ""
}

# Function to run endurance test
run_endurance_test() {
    echo -e "${YELLOW}Running Endurance Test...${NC}"
    echo "Long-running test to check for memory leaks and stability"
    echo ""
    
    locust -f locustfile.py \
        --host="$HOST" \
        --users=100 \
        --spawn-rate=10 \
        --run-time="2h" \
        --html="$OUTPUT_DIR/endurance_test_${TIMESTAMP}.html" \
        --csv="$OUTPUT_DIR/endurance_test_${TIMESTAMP}" \
        --headless \
        --print-stats
    
    echo -e "${GREEN}✅ Endurance test completed${NC}"
    echo ""
}

# Function to run API-specific tests
run_api_tests() {
    echo -e "${YELLOW}Running API-Specific Tests...${NC}"
    echo ""
    
    # Test different endpoints with focused load
    endpoints=("auth" "chat" "upload" "analytics")
    
    for endpoint in "${endpoints[@]}"; do
        echo "Testing $endpoint endpoint..."
        
        # Create focused test for each endpoint
        locust -f locustfile.py \
            --host="$HOST" \
            --users=50 \
            --spawn-rate=10 \
            --run-time="3m" \
            --html="$OUTPUT_DIR/api_${endpoint}_${TIMESTAMP}.html" \
            --csv="$OUTPUT_DIR/api_${endpoint}_${TIMESTAMP}" \
            --headless \
            --only-summary
        
        sleep 10
    done
    
    echo -e "${GREEN}✅ API tests completed${NC}"
    echo ""
}

# Function to generate comparison report
generate_comparison_report() {
    echo -e "${YELLOW}Generating Comparison Report...${NC}"
    
    cat > "$OUTPUT_DIR/test_summary_${TIMESTAMP}.md" << EOF
# Load Test Summary Report

Generated: $(date)
Target Host: $HOST

## Test Results

$(ls -la $OUTPUT_DIR/*.html | grep $TIMESTAMP)

## Performance Thresholds

- ✅ Response Time P95 < 2000ms
- ✅ Success Rate > 99%
- ✅ Requests/sec > 100 RPS
- ✅ Error Rate < 1%

## Recommendations

Based on the test results:

1. **Scaling**: Monitor CPU and memory usage during peak load
2. **Caching**: Ensure cache hit rates above 30%
3. **Database**: Monitor connection pool utilization
4. **WebSocket**: Check connection stability under load
5. **Rate Limiting**: Verify rate limits are working correctly

## Next Steps

1. Review detailed HTML reports for each test
2. Analyze CSV data for trends
3. Set up monitoring alerts based on thresholds
4. Schedule regular performance testing

EOF
    
    echo -e "${GREEN}✅ Comparison report generated${NC}"
    echo "Report: $OUTPUT_DIR/test_summary_${TIMESTAMP}.md"
    echo ""
}

# Main menu
show_menu() {
    echo "Select test type:"
    echo "1) Light Load Test (10 users, 5 min)"
    echo "2) Medium Load Test (100 users, 15 min)"
    echo "3) Heavy Load Test (500 users, 30 min)"
    echo "4) WebSocket Test (50 concurrent connections)"
    echo "5) Stress Test (2000 users, 10 min)"
    echo "6) Capacity Test (step-wise load increase)"
    echo "7) Endurance Test (2 hours)"
    echo "8) API-Specific Tests"
    echo "9) Full Test Suite (all tests)"
    echo "10) Custom Test"
    echo "0) Exit"
}

# Custom test function
run_custom_test() {
    echo "Enter custom test parameters:"
    read -p "Number of users: " users
    read -p "Spawn rate: " spawn_rate
    read -p "Duration (e.g., 10m, 1h): " duration
    read -p "Test name: " test_name
    
    run_load_test "$test_name" "$users" "$spawn_rate" "$duration" "Custom test configuration"
}

# Main execution
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    echo "Usage: $0 [test_number]"
    echo ""
    show_menu
    exit 0
fi

# Check if locust is installed
if ! command -v locust &> /dev/null; then
    echo -e "${RED}❌ Locust is not installed${NC}"
    echo "Please install requirements: pip install -r config/requirements/base.txt"
    exit 1
fi

# Check if target host is accessible
if ! curl -f -s "$HOST/health" > /dev/null; then
    echo -e "${RED}❌ Target host $HOST is not accessible${NC}"
    echo "Please ensure the server is running"
    exit 1
fi

# If test number provided as argument
if [ $# -eq 1 ]; then
    choice=$1
else
    # Interactive mode
    show_menu
    read -p "Enter choice [1-10]: " choice
fi

case $choice in
    1)
        run_load_test "light_load" 10 2 "5m" "Light load test for basic functionality"
        ;;
    2)
        run_load_test "medium_load" 100 10 "15m" "Medium load test for typical usage"
        ;;
    3)
        run_load_test "heavy_load" 500 25 "30m" "Heavy load test for peak usage"
        ;;
    4)
        run_websocket_test "websocket_test" 50 "10m"
        ;;
    5)
        run_stress_test
        ;;
    6)
        run_capacity_test
        ;;
    7)
        run_endurance_test
        ;;
    8)
        run_api_tests
        ;;
    9)
        echo -e "${YELLOW}Running Full Test Suite...${NC}"
        run_load_test "light_load" 10 2 "5m" "Light load test"
        run_load_test "medium_load" 100 10 "15m" "Medium load test"
        run_websocket_test "websocket_test" 50 "10m"
        run_api_tests
        generate_comparison_report
        ;;
    10)
        run_custom_test
        ;;
    0)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

generate_comparison_report

echo -e "${GREEN}🎉 Load testing completed!${NC}"
echo "Check the reports in: $OUTPUT_DIR"
echo ""
echo "To view HTML reports:"
echo "  open $OUTPUT_DIR/*.html"
echo ""
echo "To analyze CSV data:"
echo "  python analyze_results.py $OUTPUT_DIR"