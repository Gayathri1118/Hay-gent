"""
Kaggriculture Competitive Agent - Main Submission File
Advanced Features:
 1. Price Volatility & Supply Glut Detector (20%+ price drop detection & hold)
 2. Targeted Fertilizer Delivery Pipeline (Melon Days 6-8, Wheat/Carrot Day 2)
 3. Predictive Town Demand Pre-Planting (2-day advance planting for shop unlocks)
 4. Early-Morning Burst Farm Hand Hiring (Hour 0-2 Fibonacci optimization)
 5. Dynamic Livestock Diversification (Cows, Sheep, Geese) & Cash Buffer Guard
"""

from collections import deque

# --- GAME CONSTANTS & SPECS ---

CROP_SPECS = {
    "WHEAT":      {"seed": 10,  "base": 25,  "first_day": 2,  "one_time": True,  "max_yield": 4},
    "CARROT":     {"seed": 20,  "base": 35,  "first_day": 2,  "one_time": True,  "max_yield": 3},
    "TOMATO":     {"seed": 50,  "base": 60,  "first_day": 8,  "one_time": False, "max_yield": 4},
    "STRAWBERRY": {"seed": 100, "base": 120, "first_day": 10, "one_time": False, "max_yield": 4},
    "MELON":      {"seed": 80,  "base": 250, "first_day": 10, "one_time": True,  "max_yield": 6},
}

ANIMAL_SPECS = {
    "GOOSE": {"buy": 300, "product": "EGG",  "price": 50,  "interval": 1, "building": "COOP"},
    "COW":   {"buy": 400, "product": "MILK", "price": 160, "interval": 2, "building": "PASTURE"},
    "SHEEP": {"buy": 500, "product": "WOOL", "price": 200, "interval": 3, "building": "PASTURE"},
}

TOWN_DEMAND_MAP = {
    "Bakery": ["EGG", "WHEAT"],
    "Pizza Shop": ["MILK", "TOMATO", "WHEAT"],
    "Brunch Spot": ["EGG", "WHEAT", "STRAWBERRY"],
    "Yarn Store": ["WOOL"],
    "Ice Cream Shop": ["STRAWBERRY", "MILK", "WHEAT"],
    "Pet Cafe": ["CARROT"],
    "Smoothie Shop": ["STRAWBERRY", "MILK"],
    "Farmers Market": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"]
}

SHED_TILES = {(4, 4), (5, 4), (4, 5), (5, 5)}

# --- EPISODE STATE TRACKING (RESET ON STEP 0) ---
_PRICE_HISTORY = {}  # crop -> deque of (step, price)

def reset_state_if_needed(step_num):
    if step_num == 0:
        _PRICE_HISTORY.clear()

def get_shed_adjacent_tiles(board_size=10):
    adj = set()
    for sx, sy in SHED_TILES:
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            nx, ny = sx + dx, sy + dy
            if 0 <= nx < board_size and 0 <= ny < board_size and (nx, ny) not in SHED_TILES:
                adj.add((nx, ny))
    return list(adj)

def is_adjacent_to_shed(pos):
    x, y = pos
    if (x, y) in SHED_TILES:
        return True
    for sx, sy in SHED_TILES:
        if abs(x - sx) + abs(y - sy) <= 1:
            return True
    return False

def manhattan(p1, p2):
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

# --- PATHFINDING & MOVEMENT ---

def bfs_next_step(start_pos, target_pos, tiles, board_size=10):
    if start_pos == target_pos:
        return ["PASS"]
    
    start = tuple(start_pos)
    target = tuple(target_pos)
    
    queue = deque([[start]])
    visited = {start}
    
    blocked = set()
    for y in range(len(tiles)):
        if not isinstance(tiles[y], list): continue
        for x in range(len(tiles[y])):
            if tiles[y][x] == "LOCKED":
                blocked.add((x, y))
    
    while queue:
        path = queue.popleft()
        curr = path[-1]
        
        if curr == target:
            first = path[1]
            cx, cy = start
            nx, ny = first
            if nx > cx: return ["EAST"]
            if nx < cx: return ["WEST"]
            if ny > cy: return ["SOUTH"]
            if ny < cy: return ["NORTH"]
            return ["PASS"]
            
        for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
            nx, ny = curr[0] + dx, curr[1] + dy
            nxt = (nx, ny)
            if 0 <= nx < board_size and 0 <= ny < board_size:
                if nxt not in visited and nxt not in blocked:
                    visited.add(nxt)
                    queue.append(path + [nxt])
                    
    cx, cy = start_pos
    tx, ty = target_pos
    if cx < tx: return ["EAST"]
    if cx > tx: return ["WEST"]
    if cy < ty: return ["SOUTH"]
    if cy > ty: return ["NORTH"]
    return ["PASS"]

def move_towards(pos, target, tiles, board_size=10):
    if pos == target:
        return ["PASS"]
    return bfs_next_step(pos, target, tiles, board_size)

# --- ECONOMIC & VOLATILITY ENGINE ---

def safe_int(x, default=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        return default

def get_town_demands(obs):
    town = obs.get("town", {})
    shops = town.get("unlocked_shops", []) if isinstance(town, dict) else []
    demands = set()
    for shop in shops:
        if shop in TOWN_DEMAND_MAP:
            demands.update(TOWN_DEMAND_MAP[shop])
    return demands

def get_market_price(obs, item, base_price=0):
    m = obs.get("market", {})
    if isinstance(m, dict) and isinstance(m.get("prices"), dict):
        p = m["prices"].get(item, base_price)
        if isinstance(p, dict):
            return safe_int(p.get("price", p.get("sell", base_price)), base_price)
        return safe_int(p, base_price)
    return base_price

def update_and_check_volatility(obs, step_num):
    """
    Feature 1: Track price history & detect supply gluts (20%+ drop over 2 days / 48 steps).
    Returns dict of {crop: is_glut_boolean}.
    """
    gluts = {}
    for crop, spec in CROP_SPECS.items():
        curr_p = get_market_price(obs, crop, spec["base"])
        if crop not in _PRICE_HISTORY:
            _PRICE_HISTORY[crop] = deque(maxlen=48)
        _PRICE_HISTORY[crop].append((step_num, curr_p))
        
        # Check price drop over available history
        if len(_PRICE_HISTORY[crop]) >= 12:
            oldest_p = _PRICE_HISTORY[crop][0][1]
            if oldest_p > 0 and (curr_p / oldest_p) <= 0.80:
                gluts[crop] = True
            else:
                gluts[crop] = False
        else:
            gluts[crop] = False
            
    return gluts

def evaluate_crop_roi(crop, obs, day, money, town_demands, gluts):
    spec = CROP_SPECS[crop]
    days_left = max(0, 30 - day)
    
    if days_left < spec["first_day"]:
        return -100.0
        
    base_p = spec["base"]
    mkt_p = get_market_price(obs, crop, base_p)
    actual_p = max(1, mkt_p)
    
    # Base ROI per tile per day
    net_profit = (actual_p * spec["max_yield"]) - spec["seed"]
    daily_roi = net_profit / spec["first_day"]
    
    # Feature 1: Price Glut Penalty
    if gluts.get(crop, False):
        daily_roi *= 0.50
        
    # Town demand multiplier
    if crop in town_demands:
        daily_roi *= 1.35
        
    # Feature 3: Town Demand Predictive Pre-Planting
    # Shops unlock every 3 days (Day 3, 6, 9, 12, 15, 18, 21, 24, 27)
    days_to_next_shop = 3 - (day % 3)
    if days_to_next_shop == 2 and spec["first_day"] == 2:
        # 2-day crop planted today matures EXACTLY on the upcoming shop unlock!
        daily_roi *= 1.35
        
    # Strategic crop weighting
    if crop == "WHEAT":
        daily_roi *= 1.25
    elif crop == "CARROT":
        daily_roi *= 1.15
    elif crop == "MELON":
        daily_roi *= 1.15 if days_left >= 12 else 0.3
    elif crop == "STRAWBERRY":
        daily_roi *= 1.10 if days_left >= 14 else 0.2
    elif crop == "TOMATO":
        daily_roi *= 1.05 if days_left >= 10 else 0.2

    # End-game filter (Day 22+)
    if day >= 22 and spec["first_day"] > 2:
        return -100.0
        
    return daily_roi

def select_best_crop(obs, day, money, town_demands, gluts):
    candidates = []
    for crop in CROP_SPECS:
        roi = evaluate_crop_roi(crop, obs, day, money, town_demands, gluts)
        if roi > -50:
            candidates.append((roi, crop))
            
    if not candidates:
        return "WHEAT"
        
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]

def calculate_hire_cost(n):
    a, b = 1, 1
    for _ in range(max(0, n)):
        a, b = b, a + b
    return a

# --- MAIN AGENT FUNCTION ---

def agent(obs):
    player = obs.get("player")
    farms = obs.get("farms", [])
    day = safe_int(obs.get("day", 0), 0)
    hour = safe_int(obs.get("hour", 0), 0)
    step_num = day * 24 + hour
    
    reset_state_if_needed(step_num)
    
    if not isinstance(player, int) or player < 0 or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}
        
    me = farms[player] or {}
    private = obs.get("private", {}) or {}
    
    money = safe_int(me.get("money", 0), 0)
    tiles = me.get("tiles", []) or []
    board_size = len(tiles) if tiles else 10
    
    farmer_pos = me.get("farmer", [0, 0])
    hand_positions = me.get("hands", []) or []
    inventories = private.get("inventories", []) or []
    shed = private.get("shed", {}) or {}
    seeds = private.get("seeds", {}) or {}
    
    town_demands = get_town_demands(obs)
    gluts = update_and_check_volatility(obs, step_num)
    
    # 1. SCAN BOARD TILES
    empty_tiles = []
    weed_tiles = []
    plant_tiles = []  # (pos, dict)
    animal_tiles = [] # (pos, dict)
    
    for y in range(len(tiles)):
        row = tiles[y]
        if not isinstance(row, list): continue
        for x in range(len(row)):
            t = row[x]
            pos = [x, y]
            if t is None:
                empty_tiles.append(pos)
            elif isinstance(t, dict):
                kind = t.get("kind")
                if kind == "WEED":
                    weed_tiles.append(pos)
                elif kind == "PLANT":
                    plant_tiles.append((pos, t))
                elif kind in ("COOP", "PASTURE"):
                    animal_tiles.append((pos, t))
                    
    active_animals = [t for _, t in animal_tiles if t.get("animal") in ANIMAL_SPECS]
    num_animals = len(active_animals)
    
    wheat_in_shed = safe_int(shed.get("WHEAT", 0), 0)
    wheat_seeds = safe_int(seeds.get("WHEAT", 0), 0)
    active_wheat_plants = sum(1 for _, t in plant_tiles if t.get("crop") == "WHEAT")
    fertilizer_in_shed = safe_int(shed.get("FERTILIZER", 0), 0)
    
    # 2. MARKET ACTIONS ENGINE (MAX 10 ORDERS)
    market_orders = []
    CASH_RESERVE = 350
    
    # Strategic Selling with Glut Hold
    products_to_sell = ["EGG", "MILK", "WOOL", "FERTILIZER"]
    
    for crop in ["MELON", "STRAWBERRY", "TOMATO", "CARROT"]:
        qty = safe_int(shed.get(crop, 0), 0)
        if qty > 0:
            # If crop is in severe glut and day < 28, hold inventory for price recovery
            if gluts.get(crop, False) and day < 28:
                continue
            products_to_sell.append(crop)
            
    if day >= 28:
        products_to_sell.extend(["WHEAT", "MELON", "STRAWBERRY", "TOMATO", "CARROT"])
        
    for prod in set(products_to_sell):
        qty = safe_int(shed.get(prod, 0), 0)
        if qty > 0 and len(market_orders) < 10:
            market_orders.append(["SELL", prod, qty])
            
    # Wheat Selling / Reserve
    if day < 28:
        needed_feed = num_animals * 3
        sellable_wheat = max(0, wheat_in_shed - needed_feed)
        if sellable_wheat > 0 and len(market_orders) < 10:
            market_orders.append(["SELL", "WHEAT", sellable_wheat])
            
    # Emergency Wheat Feed Purchase
    if num_animals > 0 and (wheat_in_shed + wheat_seeds) < num_animals and day < 28:
        gap = max(1, num_animals * 2 - (wheat_in_shed + wheat_seeds))
        wp = get_market_price(obs, "WHEAT", 25)
        if wp <= 35 and money >= wp * gap + CASH_RESERVE and len(market_orders) < 10:
            market_orders.append(["BUY_PRODUCT", "WHEAT", gap])
            money -= wp * gap
            wheat_in_shed += gap

    # Diversified Livestock Engine (COW, SHEEP, GOOSE mix)
    if day < 22 and money >= 750 and (wheat_in_shed + wheat_seeds + active_wheat_plants) >= (num_animals + 1) * 3 + 2:
        empty_coops = [p for p, t in animal_tiles if t.get("kind") == "COOP" and t.get("animal") is None]
        empty_pastures = [p for p, t in animal_tiles if t.get("kind") == "PASTURE" and t.get("animal") is None]
        
        # Priority order for animal mix diversity
        animal_mix_priority = ["COW", "SHEEP", "COW", "GOOSE"]
        for anim in animal_mix_priority:
            spec = ANIMAL_SPECS[anim]
            building = spec["building"]
            cost = spec["buy"]
            avail_structs = empty_coops if building == "COOP" else empty_pastures
            
            if avail_structs and money - cost - CASH_RESERVE >= 0 and len(market_orders) < 10:
                market_orders.append(["BUY_ANIMAL", anim, 1])
                money -= cost
                break

    # Land Expansion
    unlocked_quadrants = me.get("unlocked_quadrants", ["NW"])
    land_count = len(unlocked_quadrants) if isinstance(unlocked_quadrants, list) else 1
    land_costs = [1000, 2000, 4000]
    next_land_cost = land_costs[land_count - 1] if 0 <= land_count - 1 < 3 else None
    
    if next_land_cost is not None and len(empty_tiles) <= 2 and money - next_land_cost >= CASH_RESERVE:
        if (land_count == 1 and day <= 18) or (land_count == 2 and day <= 14):
            if len(market_orders) < 10:
                market_orders.append(["BUY_LAND"])
                money -= next_land_cost

    # 3. FEATURE 4: BURST FARM HAND HIRING ENGINE (HOUR 0-2 FIBONACCI OPTIMIZATION)
    urgent_water = sum(1 for _, t in plant_tiles if not t.get("watered_today", False))
    urgent_harvest = sum(1 for _, t in plant_tiles if safe_int(t.get("yield_units", 0), 0) > 0)
    urgent_feed = sum(1 for _, t in animal_tiles if t.get("animal") and not t.get("fed_today", False))
    
    total_workload = urgent_water + urgent_harvest + (urgent_feed * 2) + len(empty_tiles)
    
    # Early morning burst hiring: hire up to 4 hands at Hour 0-2 if workload is high
    if hour <= 2 and total_workload >= 5:
        target_hands = min(5, max(2, total_workload // 2))
    elif hour <= 18:
        target_hands = min(4, max(0, total_workload // 3))
    else:
        target_hands = 0  # No late night hiring
        
    if day >= 28:
        target_hands = min(3, max(0, urgent_harvest // 2))
        
    current_hands = len(hand_positions)
    hires_today = safe_int(me.get("hires_today", 0), 0)
    
    while current_hands < target_hands and len(market_orders) < 10:
        hcost = calculate_hire_cost(hires_today)
        if money - hcost - CASH_RESERVE < 0:
            break
        market_orders.append(["HIRE"])
        money -= hcost
        current_hands += 1
        hires_today += 1

    # 4. TASK QUEUE & FEATURE 2: FERTILIZER MAXIMIZATION PIPELINE
    task_queue = []
    
    # Priority 0: Emergency Animal Feed
    for p, t in animal_tiles:
        if t.get("animal") and not t.get("fed_today", False):
            task_queue.append({"priority": 0, "pos": p, "action": ["FEED"], "type": "FEED"})

    # Priority 1: Water Crops
    if day < 28:
        for p, t in plant_tiles:
            if not t.get("watered_today", False):
                task_queue.append({"priority": 1, "pos": p, "action": ["WATER"], "type": "WATER"})

    # Priority 2: FEATURE 2 - Target Fertilizer Window Delivery
    # Melon bonus window: Days 6-8 | Wheat/Carrot: Day 2
    if day < 28:
        for p, t in plant_tiles:
            crop = t.get("crop")
            planted_d = safe_int(t.get("planted_day", day), day)
            crop_age = day - planted_d
            
            in_bonus_window = False
            if crop == "MELON" and 6 <= crop_age <= 8:
                in_bonus_window = True
            elif crop in ("WHEAT", "CARROT") and crop_age == 2:
                in_bonus_window = True
                
            if in_bonus_window:
                task_queue.append({"priority": 2, "pos": p, "action": ["FERTILIZE"], "type": "FERTILIZE"})

    # Priority 2: Harvest Ready Crops & Animals
    for p, t in plant_tiles:
        if safe_int(t.get("yield_units", 0), 0) > 0:
            task_queue.append({"priority": 2, "pos": p, "action": ["HARVEST"], "type": "HARVEST"})
        elif t.get("crop") in CROP_SPECS:
            spec = CROP_SPECS[t["crop"]]
            planted_d = safe_int(t.get("planted_day", day), day)
            if spec["one_time"] and (day - planted_d) >= spec["first_day"]:
                task_queue.append({"priority": 2, "pos": p, "action": ["HARVEST"], "type": "HARVEST"})
                
    for p, t in animal_tiles:
        if t.get("animal") and safe_int(t.get("yield_units", 0), 0) > 0:
            task_queue.append({"priority": 2, "pos": p, "action": ["HARVEST"], "type": "HARVEST"})

    # Priority 3: Clear Weeds
    for p in weed_tiles:
        task_queue.append({"priority": 3, "pos": p, "action": ["DIG"], "type": "DIG"})

    # Priority 4: Animal Care & Fertilizer Collection
    for p, t in animal_tiles:
        if t.get("animal"):
            if not t.get("cared_today", False):
                task_queue.append({"priority": 4, "pos": p, "action": ["CARE"], "type": "CARE"})
            if t.get("fertilizer_available", False):
                task_queue.append({"priority": 4, "pos": p, "action": ["COLLECT_FERTILIZER"], "type": "COLLECT"})

    # Priority 5: Animal Structures & Placement
    for anim in ANIMAL_SPECS:
        building = ANIMAL_SPECS[anim]["building"]
        in_shed = safe_int(shed.get(anim, 0), 0)
        
        for i, inv in enumerate(inventories):
            if isinstance(inv, dict) and safe_int(inv.get(anim, 0), 0) > 0:
                for p, t in animal_tiles:
                    if t.get("kind") == building and t.get("animal") is None:
                        task_queue.append({"priority": 1, "pos": p, "action": ["PLACE", anim], "type": "PLACE"})
                        break
                        
        if in_shed > 0:
            shed_adj = get_shed_adjacent_tiles(board_size)
            if shed_adj:
                task_queue.append({"priority": 2, "pos": shed_adj[0], "action": ["PICKUP", anim, 1], "type": "PICKUP"})

    # Priority 6: Plant High-ROI Crops on Empty Tiles
    if day < 28 and empty_tiles:
        best_crop = select_best_crop(obs, day, money, town_demands, gluts)
        for p in empty_tiles:
            seed_cnt = safe_int(seeds.get(best_crop, 0), 0)
            if seed_cnt > 0:
                task_queue.append({"priority": 6, "pos": p, "action": ["PLANT", best_crop], "type": "PLANT"})
            else:
                c_cost = CROP_SPECS[best_crop]["seed"]
                if money - c_cost - CASH_RESERVE >= 0 and len(market_orders) < 10:
                    market_orders.append(["BUY_SEED", best_crop, 1])
                    money -= c_cost
                    seeds[best_crop] = seeds.get(best_crop, 0) + 1
                    task_queue.append({"priority": 6, "pos": p, "action": ["PLANT", best_crop], "type": "PLANT"})

    # 5. MULTI-WORKER TASK ALLOCATION & FERTILIZER PIPELINE
    workers = [farmer_pos] + list(hand_positions)
    assigned_targets = set()
    worker_actions = []
    shed_adj_spots = get_shed_adjacent_tiles(board_size)
    
    for i, wpos in enumerate(workers):
        w_inv = inventories[i] if i < len(inventories) and isinstance(inventories[i], dict) else {}
        carrying_wheat = safe_int(w_inv.get("WHEAT", 0), 0)
        carrying_fert = safe_int(w_inv.get("FERTILIZER", 0), 0)
        
        chosen_action = ["PASS"]
        matched_target = None
        
        # Carrying wheat -> Feed unfed animal
        if carrying_wheat > 0:
            feed_tasks = [t for t in task_queue if t["type"] == "FEED" and tuple(t["pos"]) not in assigned_targets]
            if feed_tasks:
                best_t = min(feed_tasks, key=lambda t: manhattan(wpos, t["pos"]))
                matched_target = best_t
                if wpos == best_t["pos"]:
                    chosen_action = ["FEED"]
                else:
                    chosen_action = move_towards(wpos, best_t["pos"], tiles, board_size)
                    
        # Carrying fertilizer -> Fertilize bonus window crop
        if matched_target is None and carrying_fert > 0:
            fert_tasks = [t for t in task_queue if t["type"] == "FERTILIZE" and tuple(t["pos"]) not in assigned_targets]
            if fert_tasks:
                best_t = min(fert_tasks, key=lambda t: manhattan(wpos, t["pos"]))
                matched_target = best_t
                if wpos == best_t["pos"]:
                    chosen_action = ["FERTILIZE"]
                else:
                    chosen_action = move_towards(wpos, best_t["pos"], tiles, board_size)

        # Unfed animal, worker has no wheat, shed HAS wheat -> Pickup Wheat
        if matched_target is None and carrying_wheat <= 0 and wheat_in_shed > 0:
            unfed_tasks = [t for t in task_queue if t["type"] == "FEED" and tuple(t["pos"]) not in assigned_targets]
            if unfed_tasks:
                if is_adjacent_to_shed(wpos):
                    chosen_action = ["PICKUP", "WHEAT", min(5, len(unfed_tasks))]
                    matched_target = {"pos": wpos}
                else:
                    s_target = min(shed_adj_spots, key=lambda s: manhattan(wpos, s))
                    chosen_action = move_towards(wpos, s_target, tiles, board_size)
                    matched_target = {"pos": s_target}

        # Fertilizer task exists, worker has no fert, shed HAS fert -> Pickup Fertilizer
        if matched_target is None and carrying_fert <= 0 and fertilizer_in_shed > 0:
            fert_tasks = [t for t in task_queue if t["type"] == "FERTILIZE" and tuple(t["pos"]) not in assigned_targets]
            if fert_tasks:
                if is_adjacent_to_shed(wpos):
                    chosen_action = ["PICKUP", "FERTILIZER", 1]
                    matched_target = {"pos": wpos}
                else:
                    s_target = min(shed_adj_spots, key=lambda s: manhattan(wpos, s))
                    chosen_action = move_towards(wpos, s_target, tiles, board_size)
                    matched_target = {"pos": s_target}

        # Match general priority tasks
        if matched_target is None:
            best_t = None
            best_key = None
            
            for t in task_queue:
                tpos = tuple(t["pos"])
                if tpos in assigned_targets:
                    continue
                k = (t["priority"], manhattan(wpos, t["pos"]))
                if best_key is None or k < best_key:
                    best_key = k
                    best_t = t
                    
            if best_t is not None:
                matched_target = best_t
                tpos = best_t["pos"]
                
                if best_t["type"] == "PICKUP":
                    if is_adjacent_to_shed(wpos):
                        chosen_action = best_t["action"]
                    else:
                        s_target = min(shed_adj_spots, key=lambda s: manhattan(wpos, s))
                        chosen_action = move_towards(wpos, s_target, tiles, board_size)
                elif wpos == tpos:
                    chosen_action = best_t["action"]
                else:
                    chosen_action = move_towards(wpos, tpos, tiles, board_size)

        if matched_target and "pos" in matched_target:
            assigned_targets.add(tuple(matched_target["pos"]))
            
        worker_actions.append(chosen_action)

    # 6. DEFENSIVE VALIDATION
    available_seeds = {c: safe_int(seeds.get(c, 0), 0) for c in CROP_SPECS}
    for m in market_orders:
        if len(m) >= 3 and m[0] == "BUY_SEED" and m[1] in available_seeds:
            available_seeds[m[1]] += safe_int(m[2], 0)
            
    for idx, act in enumerate(worker_actions):
        if len(act) >= 2 and act[0] == "PLANT":
            crop_name = act[1]
            if crop_name not in available_seeds or available_seeds[crop_name] <= 0:
                worker_actions[idx] = ["PASS"]
            else:
                available_seeds[crop_name] -= 1

    valid_market = market_orders[:10]
    
    return {
        "farmer": worker_actions[0] if worker_actions else ["PASS"],
        "hands": worker_actions[1:],
        "market": valid_market
    }
