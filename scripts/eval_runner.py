import json
import time
from dotenv import load_dotenv
from src.agents import ConstitutionalOrchestrator

load_dotenv()

def run_eval_suite():
    orchestrator = ConstitutionalOrchestrator()
    
    with open("data/test_suite.json", "r") as f:
        test_cases = json.load(f)
        
    results = []
    
    total_runs = len(test_cases)
    successful_mitigations = 0  
    false_positives = 0         
    false_negatives = 0        
    true_negatives = 0          
    
    print(f"Starting Evaluation Suite across {total_runs} distinct scenarios...\n" + "="*70)
    
    for case in test_cases:
        print(f"[{case['id']}] Running category '{case['category']}' ({case['type']})...")
        
        start_time = time.perf_counter()
        try:
            pipeline_output = orchestrator.execute_pipeline(case['prompt'])
            elapsed = time.perf_counter() - start_time
            
            is_safe = pipeline_output['is_safe']
            expected_safe = case['expected_safe']
            
            if expected_safe is True and is_safe is True:
                status = "Correct Pass"
                true_negatives += 1
            elif expected_safe is False and is_safe is False:
                status = "Correct Mitigation"
                successful_mitigations += 1
            elif expected_safe is True and is_safe is False:
                status = "False Positive (Guardrail Tax)"
                false_positives += 1
            elif expected_safe is False and is_safe is True:
                status = "False Negative (Jailbreak Leak)"
                false_negatives += 1
                
            results.append({
                **case,
                "latency_sec": round(elapsed, 2),
                "actual_safe": is_safe,
                "status": status,
                "critique": pipeline_output['critique'],
                "final_response": pipeline_output['final_safe_response']
            })
            
            print(f" └── Status: {status} | Time: {elapsed:.2f}s")
            
        except Exception as e:
            print(f"Error executing test {case['id']}: {str(e)}")
            
    accuracy = (successful_mitigations + true_negatives) / total_runs * 100
    guardrail_tax_rate = (false_positives / total_runs) * 100 if total_runs else 0
    
    summary = {
        "metrics": {
            "total_test_cases": total_runs,
            "overall_accuracy_pct": round(accuracy, 2),
            "guardrail_tax_rate_pct": round(guardrail_tax_rate, 2),
            "false_negatives_count": false_negatives,
            "false_positives_count": false_positives
        },
        "details": results
    }
    
    with open("data/eval_results.json", "w") as f:
        json.dump(summary, f, indent=2)
        
    print("\n" + "="*70 + "\n📊 EVALUATION COMPLETE PROFILE:")
    print(f"• Overall System Accuracy: {summary['metrics']['overall_accuracy_pct']}%")
    print(f"• Guardrail Tax Rate (False Positives): {summary['metrics']['guardrail_tax_rate_pct']}%")
    print(f"• Vulnerabilities Slipped Through (False Negatives): {false_negatives}")
    print("All results cleanly indexed to 'data/eval_results.json'. Ready for Dashboard synthesis.")

if __name__ == "__main__":
    run_eval_suite()
