import kaggle_environments
import time
from main import agent as main_agent
from optimised_agent import agent as old_agent

def run_match(agent1, agent2, seed=42):
    env = kaggle_environments.make("kaggriculture", configuration={"seed": seed})
    start = time.time()
    state = env.run([agent1, agent2])
    elapsed = time.time() - start
    
    final_step = state[-1]
    p0_reward = final_step[0].get("reward", 0)
    p1_reward = final_step[1].get("reward", 0)
    
    status0 = final_step[0].get("status", "DONE")
    status1 = final_step[1].get("status", "DONE")
    
    result = "WIN" if p0_reward > p1_reward else ("LOSS" if p0_reward < p1_reward else "TIE")
    
    return {
        "p0_reward": p0_reward,
        "p1_reward": p1_reward,
        "result": result,
        "status0": status0,
        "status1": status1,
        "elapsed": elapsed
    }

if __name__ == "__main__":
    seeds = [42, 100, 2026, 999]
    
    print("=" * 60)
    print("COMPETITIVE KAGGRICULTURE AGENT BENCHMARK EVALUATION")
    print("=" * 60)
    
    print("\n[TEST 1] Optimized main.py vs random:")
    for s in seeds:
        res = run_match(main_agent, "random", seed=s)
        print(f"Seed {s:4d} | My Money: ${res['p0_reward']:7.1f} | Opp Money: ${res['p1_reward']:7.1f} | Result: {res['result']} ({res['elapsed']:.2f}s)")
        
    print("\n[TEST 2] Optimized main.py vs starter:")
    for s in seeds:
        res = run_match(main_agent, "starter", seed=s)
        print(f"Seed {s:4d} | My Money: ${res['p0_reward']:7.1f} | Opp Money: ${res['p1_reward']:7.1f} | Result: {res['result']} ({res['elapsed']:.2f}s)")

    print("\n[TEST 3] Optimized main.py vs Old Experimental (optimised_agent.py):")
    for s in seeds:
        res = run_match(main_agent, old_agent, seed=s)
        print(f"Seed {s:4d} | My Money: ${res['p0_reward']:7.1f} | Opp Money: ${res['p1_reward']:7.1f} | Result: {res['result']} ({res['elapsed']:.2f}s)")

    print("\n[TEST 4] Optimized main.py Self-Match (Self-vs-Self):")
    for s in seeds:
        res = run_match(main_agent, main_agent, seed=s)
        print(f"Seed {s:4d} | P0 Money: ${res['p0_reward']:7.1f} | P1 Money: ${res['p1_reward']:7.1f} | Result: {res['result']} ({res['elapsed']:.2f}s)")
