"""
Spine Rip Bot Diagnostics
==========================
Tests LLM connection, input/output, errors, and timeouts
"""

import json
import urllib.request
import urllib.error
import time
from pathlib import Path

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_section(title):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title:^60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_success(msg):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")

def print_error(msg):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")

# Test 1: Check Ollama Connection
def test_ollama_connection():
    print_section("TEST 1: OLLAMA CONNECTION")
    
    ollama_url = "http://localhost:11434"
    
    # Test 1.1: Ping Ollama API
    print_info("Testing Ollama API endpoint...")
    try:
        req = urllib.request.Request(f"{ollama_url}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print_success(f"Ollama is running (HTTP {resp.status})")
            
            # List available models
            models = data.get('models', [])
            if models:
                print_success(f"Found {len(models)} model(s):")
                for model in models:
                    name = model.get('name', 'unknown')
                    size = model.get('size', 0) / (1024**3)  # Convert to GB
                    print(f"  • {name} ({size:.2f} GB)")
            else:
                print_warning("No models installed. Run: ollama pull qwen2.5:1.5b")
            return True
    except urllib.error.URLError as e:
        print_error(f"Cannot connect to Ollama: {e.reason}")
        print_info("Start Ollama with: ollama serve")
        return False
    except Exception as e:
        print_error(f"Ollama connection error: {e}")
        return False

# Test 2: Test LLM Response
def test_llm_response():
    print_section("TEST 2: LLM RESPONSE")
    
    ollama_url = "http://localhost:11434"
    model = "qwen2.5:1.5b"
    
    print_info(f"Testing model: {model}")
    print_info("Sending test prompt: 'What is 2+2?'")
    
    try:
        start_time = time.time()
        
        payload = json.dumps({
            "model": model,
            "prompt": "What is 2+2? Answer with just the number.",
            "stream": False,
        }).encode('utf-8')
        
        req = urllib.request.Request(
            f"{ollama_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        elapsed = time.time() - start_time
        response = data.get('response', '').strip()
        
        if response:
            print_success(f"Received response in {elapsed:.2f}s")
            print(f"  Response: {response[:100]}")
            
            # Check response metrics
            if 'total_duration' in data:
                total_ms = data['total_duration'] / 1_000_000
                print_info(f"Total duration: {total_ms:.0f}ms")
            if 'load_duration' in data:
                load_ms = data['load_duration'] / 1_000_000
                print_info(f"Load duration: {load_ms:.0f}ms")
            if 'prompt_eval_count' in data:
                print_info(f"Prompt tokens: {data['prompt_eval_count']}")
            if 'eval_count' in data:
                print_info(f"Response tokens: {data['eval_count']}")
                
            return True
        else:
            print_error("Empty response from AI")
            return False
            
    except urllib.error.URLError as e:
        print_error(f"Connection failed: {e.reason}")
        return False
    except TimeoutError:
        print_error("Request timed out after 180 seconds")
        print_warning("The model might be too large or your system is slow")
        return False
    except Exception as e:
        print_error(f"LLM test failed: {e}")
        return False

# Test 3: Test Bot Dependencies
def test_bot_dependencies():
    print_section("TEST 3: BOT DEPENDENCIES")
    
    # Check python-telegram-bot
    print_info("Checking python-telegram-bot...")
    try:
        import telegram
        print_success(f"python-telegram-bot installed (v{telegram.__version__})")
    except ImportError:
        print_error("python-telegram-bot not installed")
        print_info("Install with: pip install python-telegram-bot")
        return False
    
    # Check sz_runtime
    print_info("Checking sz_runtime...")
    try:
        from sz_runtime import ToolRuntime
        rt = ToolRuntime()
        tools = rt.list_tools()
        print_success(f"ToolRuntime loaded ({len(tools)} tools available)")
    except ImportError:
        print_error("sz_runtime.py not found")
        return False
    except Exception as e:
        print_error(f"ToolRuntime error: {e}")
        return False
    
    return True

# Test 4: Test Bot Configuration
def test_bot_config():
    print_section("TEST 4: BOT CONFIGURATION")
    
    config_path = Path.home() / ".subzero" / "telegram.json"
    
    print_info(f"Checking config: {config_path}")
    
    if config_path.exists():
        print_success("Config file exists")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            
            if cfg.get('bot_token'):
                token_preview = cfg['bot_token'][:10] + "..." + cfg['bot_token'][-10:]
                print_success(f"Bot token configured: {token_preview}")
            else:
                print_warning("Bot token is empty")
                print_info("Set token in Spine Rip GUI or run: python sz_telegram.py")
            
            model = cfg.get('model', 'qwen2.5:1.5b')
            print_info(f"Configured model: {model}")
            
            return True
        except Exception as e:
            print_error(f"Cannot read config: {e}")
            return False
    else:
        print_warning("Config file not found")
        print_info("Run the bot once to create it: python sz_telegram.py")
        return False

# Test 5: Test Input/Output Processing
def test_input_output():
    print_section("TEST 5: INPUT/OUTPUT PROCESSING")
    
    print_info("Testing message processing pipeline...")
    
    # Simulate a user message
    test_msg = "Hello, what is Python?"
    print_info(f"Test input: '{test_msg}'")
    
    try:
        from sz_telegram import _build_prompt, ollama_generate
        
        # Build prompt
        print_info("Building prompt...")
        prompt = _build_prompt(user_id=12345, user_msg=test_msg, model="qwen2.5:1.5b")
        print_success(f"Prompt built ({len(prompt)} chars)")
        
        # Test AI response
        print_info("Sending to Ollama...")
        start_time = time.time()
        response = ollama_generate(test_msg, "qwen2.5:1.5b")
        elapsed = time.time() - start_time
        
        if response and not response.startswith("⚠️"):
            print_success(f"Response received in {elapsed:.2f}s")
            print(f"  Output: {response[:100]}...")
            return True
        else:
            print_error(f"Invalid response: {response}")
            return False
            
    except Exception as e:
        print_error(f"Input/output test failed: {e}")
        return False

# Test 6: Test Tool Execution
def test_tool_execution():
    print_section("TEST 6: TOOL EXECUTION")
    
    print_info("Testing tool runtime...")
    
    try:
        from sz_runtime import ToolRuntime
        
        rt = ToolRuntime()
        
        # Test parsing tool calls
        test_response = "@tool run_command cmd=\"echo Hello from diagnostics\""
        print_info(f"Test tool call: {test_response}")
        
        tool_calls = rt.parse(test_response)
        if tool_calls:
            print_success(f"Parsed {len(tool_calls)} tool call(s)")
            for tc in tool_calls:
                print(f"  • Tool: {tc.name}")
                print(f"    Params: {tc.params}")
            
            # Execute
            print_info("Executing tool call...")
            results = rt.execute_all(tool_calls)
            for r in results:
                if r.success:
                    print_success(f"Tool '{r.tool_name}' executed successfully")
                    print(f"  Output: {r.output[:100]}")
                else:
                    print_error(f"Tool '{r.tool_name}' failed: {r.output}")
            return True
        else:
            print_warning("No tool calls parsed")
            return True
            
    except Exception as e:
        print_error(f"Tool execution test failed: {e}")
        return False

# Test 7: Test Timeout Scenarios
def test_timeouts():
    print_section("TEST 7: TIMEOUT TESTING")
    
    print_info("Testing timeout scenarios...")
    
    # Test with a very long prompt (might timeout)
    long_prompt = "Explain quantum computing in extreme detail. " * 100
    
    print_info(f"Testing with {len(long_prompt)} char prompt...")
    
    try:
        from sz_telegram import ollama_generate
        
        start_time = time.time()
        response = ollama_generate(long_prompt[:2000], "qwen2.5:1.5b")  # Limit to 2000 chars
        elapsed = time.time() - start_time
        
        if elapsed > 60:
            print_warning(f"Response took {elapsed:.1f}s (slow)")
        else:
            print_success(f"Response in {elapsed:.1f}s (acceptable)")
        
        if response and not response.startswith("⚠️"):
            print_success("No timeout occurred")
            return True
        else:
            print_error(f"Timeout or error: {response}")
            return False
            
    except Exception as e:
        print_error(f"Timeout test failed: {e}")
        return False

# Main Diagnostic Runner
def run_diagnostics():
    print(f"\n{Colors.BOLD}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
    print(f"{Colors.BOLD}║     SPINE RIP BOT DIAGNOSTICS - COMPREHENSIVE TEST       ║{Colors.RESET}")
    print(f"{Colors.BOLD}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
    
    results = {}
    
    # Run all tests
    results['ollama_connection'] = test_ollama_connection()
    results['llm_response'] = test_llm_response()
    results['bot_dependencies'] = test_bot_dependencies()
    results['bot_config'] = test_bot_config()
    results['input_output'] = test_input_output()
    results['tool_execution'] = test_tool_execution()
    results['timeouts'] = test_timeouts()
    
    # Summary
    print_section("DIAGNOSTIC SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if result else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"  {test_name.replace('_', ' ').title():.<40} {status}")
    
    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.RESET}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ ALL TESTS PASSED! Your bot is ready to use.{Colors.RESET}")
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠ Some tests failed. Check the errors above.{Colors.RESET}")
        
        # Provide recommendations
        print(f"\n{Colors.BOLD}Recommendations:{Colors.RESET}")
        if not results['ollama_connection']:
            print("  • Start Ollama: ollama serve")
            print("  • Pull model: ollama pull qwen2.5:1.5b")
        if not results['bot_dependencies']:
            print("  • Install dependencies: pip install -r requirements.txt")
        if not results['bot_config']:
            print("  • Configure bot: python sz_telegram.py")

if __name__ == "__main__":
    run_diagnostics()
