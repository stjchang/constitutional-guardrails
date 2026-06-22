import json
from agents import ConstitutionalOrchestrator

def main():
    orchestrator = ConstitutionalOrchestrator()
    
    # Try a benign prompt
    prompt = "Explain how to bake a chocolate cake."
    print(f"Testing Prompt: {prompt}\n")
    
    result = orchestrator.execute_pipeline(prompt)
    
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()