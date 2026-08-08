import sys

def manhattan(p1, p2):
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

def agent(obs):
    # Safe state loading
    player = obs.get("player")
    day = obs.get("day", 0)
    
    farms = obs.get("farms", [])
    if not farms or player is None or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}
        
    farm = farms[player]
    farmer_pos = farm.get("farmer", [0, 0])
    money = farm.get("money", 0)
    
    private = obs.get("private", {})
    seeds = private.get("seeds", {})
    shed = private.get("shed", {})
    
    # 1. Market Actions
    market_actions = []
    
    wheat_in_shed = shed.get("WHEAT", 0)
    if wheat_in_shed > 0:
        market_actions.append(["SELL", "WHEAT", wheat_in_shed])
        
    if seeds.get("WHEAT", 0) == 0 and money >= 10:
        market_actions.append(["BUY_SEED", "WHEAT", 1])
        
    # 2. Find Farmer Targets
    targets = []
    tiles = farm.get("tiles", [])
    
    # First pass: count active wheat plants to avoid overexpansion
    active_wheat = 0
    for y in range(len(tiles)):
        if not isinstance(tiles[y], list): continue
        for x in range(len(tiles[y])):
            tile = tiles[y][x]
            if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == "WHEAT":
                active_wheat += 1

    MAX_WHEAT = 3

    for y in range(len(tiles)):
        if not isinstance(tiles[y], list): continue
        for x in range(len(tiles[y])):
            tile = tiles[y][x]
            
            if tile == "LOCKED":
                continue
                
            if tile is None:
                # Empty, unlocked tile
                if seeds.get("WHEAT", 0) > 0 and active_wheat < MAX_WHEAT:
                    targets.append({"priority": 3, "pos": [x, y], "action": ["PLANT", "WHEAT"]})
            elif isinstance(tile, dict):
                # Plant or weed or animal structure
                if tile.get("kind") == "PLANT" and tile.get("crop") == "WHEAT":
                    planted_day = tile.get("planted_day", day)
                    crop_age = day - planted_day
                    
                    if crop_age >= 2:
                        targets.append({"priority": 1, "pos": [x, y], "action": ["HARVEST"]})
                    elif not tile.get("watered_today", False):
                        targets.append({"priority": 2, "pos": [x, y], "action": ["WATER"]})

    farmer_action = ["PASS"]
    
    if targets:
        # Sort targets by priority (1 is highest), then by distance to farmer
        targets.sort(key=lambda t: (t["priority"], manhattan(farmer_pos, t["pos"])))
        best_target = targets[0]
        
        tx, ty = best_target["pos"]
        cx, cy = farmer_pos
        
        if cx == tx and cy == ty:
            farmer_action = best_target["action"]
        else:
            # Move towards the target
            if cx < tx:
                farmer_action = ["EAST"]
            elif cx > tx:
                farmer_action = ["WEST"]
            elif cy < ty:
                farmer_action = ["SOUTH"]
            elif cy > ty:
                farmer_action = ["NORTH"]
                
    return {
        "farmer": farmer_action,
        "hands": [],
        "market": market_actions[:10]
    }
