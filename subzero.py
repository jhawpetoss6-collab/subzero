#!/usr/bin/env python3
"""
SubZero - Lightweight AI Agent
Uses Ollama locally with a simple skill system
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

class SubZero:
    def __init__(self):
        self.model = "qwen2.5:3b"
        self.memory_file = Path.home() / ".subzero" / "memory_cli.json"
        self.skills_dir = Path.home() / ".subzero" / "skills"
        self.conversation = []
        self._init_dirs()
        self._load_memory()
    
    def _init_dirs(self):
        """Initialize SubZero directories"""
        self.memory_file.parent.mkdir(exist_ok=True)
        self.skills_dir.mkdir(exist_ok=True)
    
    def _load_memory(self):
        """Load conversation memory"""
        if self.memory_file.exists():
            with open(self.memory_file, 'r') as f:
                self.conversation = json.load(f)
    
    def _save_memory(self):
        """Save conversation memory"""
        with open(self.memory_file, 'w') as f:
            json.dump(self.conversation[-50:], f, indent=2)  # Keep last 50 messages
    
    def run_ollama(self, prompt):
        """Send prompt to Ollama"""
        try:
            # Build conversation context
            context = "\n".join([
                f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                for msg in self.conversation[-10:]  # Last 10 messages for context
            ])
            
            full_prompt = f"{context}\nUser: {prompt}\nAssistant:"
            
            result = subprocess.run(
                ['ollama', 'run', self.model, full_prompt],
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return f"Error: {result.stderr}"
        except Exception as e:
            return f"Error calling Ollama: {e}"
    
    def execute_command(self, command):
        """Execute system command (skill)"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return result.stdout if result.returncode == 0 else result.stderr
        except Exception as e:
            return f"Error: {e}"
    
    def chat(self, user_input):
        """Main chat interface"""
        # Add user message to conversation
        self.conversation.append({
            'role': 'user',
            'content': user_input,
            'timestamp': datetime.now().isoformat()
        })
        
        # Get AI response
        response = self.run_ollama(user_input)
        
        # Add AI response to conversation
        self.conversation.append({
            'role': 'assistant',
            'content': response,
            'timestamp': datetime.now().isoformat()
        })
        
        # Save memory
        self._save_memory()
        
        return response
    
    def interactive(self):
        """Start interactive chat"""
        print("╔════════════════════════════════════╗")
        print("║         SubZero Agent v1.0         ║")
        print("║    Lightweight • Local • Free      ║")
        print("╚════════════════════════════════════╝")
        print(f"\nUsing model: {self.model}")
        print("Type 'exit' to quit, 'clear' to clear memory\n")
        
        while True:
            try:
                user_input = input("\n🧊 You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == 'exit':
                    print("\n❄️  SubZero shutting down...")
                    break
                
                if user_input.lower() == 'clear':
                    self.conversation = []
                    self._save_memory()
                    print("💭 Memory cleared!")
                    continue
                
                print("\n🤖 SubZero: ", end='', flush=True)
                response = self.chat(user_input)
                print(response)
                
            except KeyboardInterrupt:
                print("\n\n❄️  SubZero interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")

def main():
    agent = SubZero()
    
    if len(sys.argv) > 1:
        # Single message mode
        message = ' '.join(sys.argv[1:])
        response = agent.chat(message)
        print(response)
    else:
        # Interactive mode
        agent.interactive()

if __name__ == "__main__":
    main()
