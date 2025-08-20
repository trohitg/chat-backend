#!/usr/bin/env python3

import os
import sys
import subprocess
import time
import threading
from pathlib import Path
import signal

class ServiceManager:
    def __init__(self):
        self.processes = []
        self.running = True
        
    def start_backend(self):
        """Start the FastAPI backend"""
        print("Starting FastAPI backend...")
        cmd = [
            sys.executable, "-m", "uvicorn", 
            "app.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000",
            "--reload"
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        self.processes.append(("Backend", process))
        
        # Monitor backend output in a thread
        def monitor_backend():
            for line in iter(process.stdout.readline, ''):
                if self.running:
                    print(f"[Backend] {line.rstrip()}")
                else:
                    break
        
        thread = threading.Thread(target=monitor_backend, daemon=True)
        thread.start()
        
        return process
    
    def wait_for_backend(self, timeout=30):
        """Wait for backend to be ready"""
        import httpx
        
        print("Waiting for backend to be ready...")
        
        for i in range(timeout):
            try:
                with httpx.Client(timeout=2.0) as client:
                    response = client.get("http://localhost:8000/api/v1/health")
                    if response.status_code == 200:
                        print("Backend is ready!")
                        return True
            except:
                pass
            
            time.sleep(1)
            if i % 5 == 0:
                print(f"  Still waiting... ({i}/{timeout}s)")
        
        print("Backend failed to start within timeout")
        return False
    
    def stop_all(self):
        """Stop all services"""
        print("\nStopping backend service...")
        self.running = False
        
        for name, process in self.processes:
            try:
                print(f"  Stopping {name}...")
                process.terminate()
                process.wait(timeout=5)
                print(f"  {name} stopped")
            except subprocess.TimeoutExpired:
                print(f"  Force killing {name}...")
                process.kill()
                process.wait()
            except Exception as e:
                print(f"  Error stopping {name}: {e}")
    
    def run(self):
        """Run backend service"""
        try:
            # Start backend
            backend_process = self.start_backend()
            
            # Wait for backend to be ready
            if not self.wait_for_backend():
                return 1
            
            print("\n" + "=" * 60)
            print("Backend service started successfully!")
            print("Backend API: http://localhost:8000")
            print("API Docs: http://localhost:8000/docs")
            print("Health Check: http://localhost:8000/api/v1/health")
            print("=" * 60)
            print("\nPress Ctrl+C to stop the service\n")
            
            # Wait for process
            try:
                while self.running:
                    # Check if process died
                    for name, process in self.processes:
                        if process.poll() is not None:
                            print(f"{name} process died unexpectedly")
                            return 1
                    
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                print("\nReceived interrupt signal")
                
            return 0
            
        except Exception as e:
            print(f"Error running backend service: {e}")
            return 1
        finally:
            self.stop_all()

def main():
    """Main entry point"""
    # Check if we're in the right directory
    if not Path("app").exists():
        print("Please run this script from the chat-backend directory")
        return 1
    
    # Set up signal handlers
    manager = ServiceManager()
    
    def signal_handler(signum, frame):
        manager.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    return manager.run()

if __name__ == "__main__":
    sys.exit(main())