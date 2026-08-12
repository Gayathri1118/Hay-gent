import kaggle_environments
from optimised_agent import agent as opt_agent

env = kaggle_environments.make("kaggriculture", configuration={"seed": 42})
state = env.reset()

obs0 = state[0]["observation"]
print("Initial money:", obs0["farms"][0]["money"])

# Track step by step
actions_history = []
for step in range(720):
    player_obs = state[0]["observation"]
    p0_farm = player_obs["farms"][0]
    
    # Run agent
    action = opt_agent(player_obs)
    
    # Print telemetry every 24 steps (1 day) or when key events happen
    if step % 24 == 0 or step in [1, 2, 5, 10, 23, 719]:
        day = player_obs.get("day", 0)
        hour = player_obs.get("hour", 0)
        money = p0_farm.get("money", 0)
        hands = len(p0_farm.get("hands", []))
        shed = player_obs.get("private", {}).get("shed", {})
        seeds = player_obs.get("private", {}).get("seeds", {})
        print(f"Step {step:3d} (Day {day:2d}, Hr {hour:2d}): Money=${int(money):5d} | Hands={hands} | Shed={shed} | Seeds={seeds}")
        print(f"   Farmer Action: {action.get('farmer')} | Market: {action.get('market')}")
        if action.get('hands'):
            print(f"   Hands Actions: {action.get('hands')[:3]}")

    state = env.step([action, {"farmer": ["PASS"], "hands": [], "market": []}])

print("Final Money:", state[-1][0]["observation"]["farms"][0]["money"])
