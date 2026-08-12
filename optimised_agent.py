# Integrated strategy:
#   CROPS + LAND + FARM HANDS + ANIMALS + FEED WHEAT + FERTILIZER + MARKET
#
# Main principles:
#   * Never wait for a whole field or batch.
#   * Harvested plots are replanted independently.
#   * Existing land is used before expansion, but land is bought while
#     current crops/animals continue producing when capacity becomes the
#     bottleneck.
#   * Hire enough hands to keep high-value work moving in parallel.
#   * Prefer animals when their capital/feeding economics are attractive.
#   * Maintain a wheat feed reserve for animals; BUY_PRODUCT WHEAT can
#     bridge feed shortages.
#   * Collect animal fertilizer and use/sell it rather than ignoring it.
#   * Sell harvested products regularly so the bank balance, not inventory,
#     remains the final objective.
#   * Use current market prices and town demand as economic signals.


CROP = {
    "WHEAT":      {"seed": 10,  "base": 25,  "first": 2,  "max_age": 4,  "one_time": True},
    "CARROT":     {"seed": 20,  "base": 35,  "first": 2,  "max_age": 3,  "one_time": True},
    "TOMATO":     {"seed": 50,  "base": 60,  "first": 8,  "max_age": 16, "one_time": False},
    "STRAWBERRY": {"seed": 100, "base": 120,"first": 10, "max_age": 20, "one_time": False},
    "MELON":      {"seed": 80,  "base": 250,"first": 10, "max_age": 12, "one_time": True},
}

ANIMAL = {
    "GOOSE": {"buy": 300, "product": "EGG",  "product_price": 50,  "interval": 1, "building": "COOP"},
    "COW":   {"buy": 400, "product": "MILK", "product_price": 160, "interval": 2, "building": "PASTURE"},
    "SHEEP": {"buy": 500, "product": "WOOL", "product_price": 200, "interval": 3, "building": "PASTURE"},
}

CROP_ORDER = ["MELON", "STRAWBERRY", "TOMATO", "CARROT", "WHEAT"]
ANIMAL_ORDER = ["COW", "SHEEP", "GOOSE"]

def safe_int(x, default=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        return default

def dist(a, b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

def shed_spots(board_size):
    h = board_size // 2
    return [[h-1,h-1], [h,h-1], [h-1,h], [h,h]]

def adjacent_to_shed(pos, board_size):
    return any(dist(pos, s) == 1 for s in shed_spots(board_size))

def nearest_shed_spot(pos, board_size):
    spots = shed_spots(board_size)
    return min(spots, key=lambda s: dist(pos, s))

def move(pos, target):
    tx, ty = target
    x, y = pos
    if x < tx: return ["EAST"]
    if x > tx: return ["WEST"]
    if y < ty: return ["SOUTH"]
    if y > ty: return ["NORTH"]
    return ["PASS"]

def tile_scan(tiles):
    empty, weeds, plants, animals = [], [], [], []
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, t in enumerate(row):
            p = [x,y]
            if t is None:
                empty.append(p)
            elif isinstance(t, dict):
                kind = t.get("kind")
                if kind == "WEED":
                    weeds.append(p)
                elif kind == "PLANT":
                    plants.append((p,t))
                elif kind in ("COOP","PASTURE"):
                    animals.append((p,t))
    return empty, weeds, plants, animals

def market_prices(obs):
    m = obs.get("market", {})
    if isinstance(m, dict) and isinstance(m.get("prices"), dict):
        return m["prices"]
    return {}

def price(obs, product):
    v = market_prices(obs).get(product, 0)
    if isinstance(v, dict):
        v = v.get("price", v.get("sell", 0))
    return safe_int(v, 0)

def crop_score(obs, crop, day, money, animal_feed_need=0):
    c = CROP[crop]
    p = price(obs, crop)
    if p <= 0:
        p = c["base"]
    seed_ratio = p / max(1, c["seed"])
    left_days = max(0, 30-day)
    if left_days * 24 < c["first"] * 24:
        return -1
    # Premium price is useful, but do not overreact to one noisy price.
    score = seed_ratio
    if crop == "WHEAT" and animal_feed_need > 0:
        score *= 1.35
    if crop == "MELON":
        score *= 1.10
    if crop == "TOMATO":
        score *= 1.05
    # Late season: prefer quick crops unless premium price is exceptional.
    if day >= 24 and crop in ("STRAWBERRY","MELON"):
        score *= 0.65
    if day >= 27 and crop in ("TOMATO","STRAWBERRY","MELON"):
        score *= 0.35
    return score

def choose_crop(obs, day, money, feed_need):
    vals = [(crop_score(obs,c,day,money,feed_need), c) for c in CROP_ORDER]
    vals = [v for v in vals if v[0] >= 0]
    return max(vals)[1] if vals else "WHEAT"

def animal_structures(animals):
    out = []
    for pos,t in animals:
        a = t.get("animal")
        if a in ANIMAL:
            out.append((pos,t))
    return out

def animal_counts(animals):
    counts = {a:0 for a in ANIMAL}
    for _,t in animals:
        a=t.get("animal")
        if a in counts:
            counts[a]+=1
    return counts

def desired_animal_mix(day, money, feed_capacity, prices):
    # Capital-aware steady-state preference.
    # Cows have strong revenue density, sheep are next, geese are cheap.
    # Keep goose as a fallback when capital is too low.
    if day < 4:
        return {"COW":0,"SHEEP":0,"GOOSE":0}
    milk = safe_int(prices.get("MILK",160),160)
    wool = safe_int(prices.get("WOOL",200),200)
    egg = safe_int(prices.get("EGG",50),50)
    scores = {
        "COW": milk/400.0/2.0,
        "SHEEP": wool/500.0/3.0,
        "GOOSE": egg/300.0,
    }
    # Feed is one wheat/day per animal. Limit animal count to avoid
    # turning the farm into a wheat-feeding charity.
    if feed_capacity <= 0:
        return {"COW":0,"SHEEP":0,"GOOSE":0}
    best = max(scores, key=scores.get)
    if best == "COW":
        return {"COW": min(4, feed_capacity), "SHEEP":1 if feed_capacity>=5 else 0, "GOOSE":1 if feed_capacity>=6 else 0}
    if best == "SHEEP":
        return {"COW":1 if feed_capacity>=2 else 0, "SHEEP":min(4,feed_capacity//1), "GOOSE":1 if feed_capacity>=5 else 0}
    return {"COW":1 if feed_capacity>=3 else 0, "SHEEP":1 if feed_capacity>=4 else 0, "GOOSE":min(5,feed_capacity)}

def hire_cost(n):
    a,b=1,1
    for _ in range(max(0,n)):
        a,b=b,a+b
    return a

def choose_target(pos, targets, used):
    best=None
    key=None
    for t in targets:
        p=tuple(t["pos"])
        if p in used:
            continue
        k=(t["priority"], dist(pos,t["pos"]))
        if key is None or k<key:
            key=k
            best=t
    return best

def action_to_target(pos,target):
    if target is None:
        return ["PASS"]
    if pos == target["pos"]:
        return target["action"]
    return move(pos,target["pos"])

def inventory_count(inv, item):
    if not isinstance(inv, dict):
        return 0
    return safe_int(inv.get(item,0),0)

def agent(obs):
    player=obs.get("player")
    farms=obs.get("farms",[])
    day=safe_int(obs.get("day",0),0)
    hour=safe_int(obs.get("hour",0),0)
    if not isinstance(player,int) or player<0 or player>=len(farms):
        return {"farmer":["PASS"],"hands":[],"market":[]}

    me=farms[player] or {}
    private=obs.get("private",{}) or {}
    money=safe_int(me.get("money",0),0)
    tiles=me.get("tiles",[]) or []
    board_size=len(tiles) if tiles else 10
    farmer_pos=me.get("farmer",[0,0])
    hand_pos=me.get("hands",[]) or []
    inventories=private.get("inventories",[]) or []
    shed=private.get("shed",{}) or {}
    seeds=private.get("seeds",{}) or {}

    empty,weeds,plants,animals=tile_scan(tiles)
    ac=animal_counts(animals)
    real_animals=animal_structures(animals)
    total_animals=sum(ac.values())

   
    # MARKET: SELL FIRST
   
    market=[]
    for product in ("EGG","MILK","WOOL","MELON","STRAWBERRY","TOMATO","CARROT","WHEAT","FERTILIZER"):
        n=safe_int(shed.get(product,0),0)
        if n>0 and len(market)<10:
            market.append(["SELL",product,n])

   
    # ANIMAL ECONOMICS + FEED RESERVE
   
    wheat_shed=safe_int(shed.get("WHEAT",0),0)
    wheat_seed=safe_int(seeds.get("WHEAT",0),0)
    # Wheat available now plus a conservative feed reserve.
    feed_reserve=max(2,total_animals*2)
    wheat_gap=max(0,feed_reserve-(wheat_shed+wheat_seed))

    # If animals need feed, buy wheat product before buying another animal.
    # This is much cheaper than letting an animal escape.
    if total_animals>0 and wheat_gap>0 and len(market)<10:
        wp=price(obs,"WHEAT")
        # Only buy market wheat when it is reasonably priced. If the market
        # is temporarily expensive, grow wheat instead.
        if wp<=30:
            market.append(["BUY_PRODUCT","WHEAT",wheat_gap])
            money-=wp*wheat_gap

   
    # BUY ANIMALS + BUILDINGS
   
    # Build first, then buy. The animal is picked up from the shed and
    # placed on the structure on a later turn.
    reserve=max(150, int(money*0.08))
    prices={k:price(obs,k) for k in ("EGG","MILK","WOOL")}
    feed_capacity=max(0,(wheat_shed+wheat_seed+wheat_gap)//2)

    targets_mix=desired_animal_mix(day,money,feed_capacity,prices)
    if day>=25:
        targets_mix={a:0 for a in targets_mix}

    empty_coops=[p for p,t in animals if t.get("kind")=="COOP" and t.get("animal") is None]
    empty_pastures=[p for p,t in animals if t.get("kind")=="PASTURE" and t.get("animal") is None]
    planned_builds=[]

    for a in ANIMAL_ORDER:
        need=max(0,targets_mix.get(a,0)-ac.get(a,0))
        if need<=0:
            continue

        building=ANIMAL[a]["building"]
        existing=empty_coops if building=="COOP" else empty_pastures

        if not existing and empty:
            p=empty.pop(0)
            existing.append(p)
            planned_builds.append((p,building))

        if existing and len(market)<10:
            cost=ANIMAL[a]["buy"]
            if money-cost-reserve>=0:
                market.append(["BUY_ANIMAL",a,1])
                money-=cost

   
    # LAND EXPANSION
   
    #
    # Use existing land continuously. Buy the next quadrant when the
    # current unlocked area is essentially occupied by useful assets or
    # when there is insufficient empty land for the next production wave.
    #
    unlocked=me.get("unlocked_quadrants",["NW"])
    land_count=len(unlocked) if isinstance(unlocked,list) else 1
    land_costs=[1000,2000,4000]
    next_land=land_costs[land_count-1] if 0<=land_count-1<3 else None

    useful=len(plants)+len(real_animals)
    empty_count=len(empty)
    # Target a compact but continuous utilization threshold.
    land_pressure=(empty_count<=max(2, int(25*0.12)))
    if land_count==1 and useful>=18:
        land_pressure=True
    elif land_count==2 and useful>=40:
        land_pressure=True
    elif land_count==3 and useful>=65:
        land_pressure=True

    if next_land is not None and land_pressure and day<28 and len(market)<10:
        if money-next_land-reserve>=0:
            market.append(["BUY_LAND"])
            money-=next_land

   
    # HIRE HANDS
   
    # Workload = plants needing water/harvest + animals needing feed/care
    # + planting/building jobs. More work -> more hands.
    urgent=0
    for _,t in plants:
        if not t.get("watered_today",False):
            urgent+=1
        if safe_int(t.get("yield_units",0),0)>0:
            urgent+=1
    for _,t in real_animals:
        if t.get("animal") and not t.get("fed_today",False):
            urgent+=2

    # Farmer plus hands. We do not hire the expensive tail unless the
    # workload justifies it.
    desired_hands=min(7,max(0,(urgent+2)//4))
    current_hands=len(hand_pos)
    hires_today=safe_int(me.get("hires_today",0),0)

    while current_hands<desired_hands and len(market)<10:
        c=hire_cost(hires_today)
        if money-c-reserve<0:
            break
        market.append(["HIRE"])
        money-=c
        current_hands+=1
        hires_today+=1

   
    # FARM TARGETS
   
    targets=[]

    # Priority 0: harvest ready crops and animal products.
    for p,t in plants:
        if safe_int(t.get("yield_units",0),0)>0:
            targets.append({"priority":0,"pos":p,"action":["HARVEST"]})

    for p,t in real_animals:
        if t.get("animal") and safe_int(t.get("yield_units",0),0)>0:
            targets.append({"priority":0,"pos":p,"action":["HARVEST"]})

    # Priority 1: keep plants alive and maximize yield.
    for p,t in plants:
        if not t.get("watered_today",False):
            targets.append({"priority":1,"pos":p,"action":["WATER"]})

    # Priority 1: feed and care animals.
    # A unit carrying wheat can go directly to an unfed animal.
    for p,t in real_animals:
        if not t.get("animal"):
            continue
        if not t.get("fed_today",False):
            targets.append({"priority":1,"pos":p,"action":["FEED"]})
        elif not t.get("cared_today",False):
            targets.append({"priority":2,"pos":p,"action":["CARE"]})
        if t.get("fertilizer_available",False):
            targets.append({"priority":3,"pos":p,"action":["COLLECT_FERTILIZER"]})

    # Priority 2: weeds.
    for p in weeds:
        targets.append({"priority":2,"pos":p,"action":["DIG"]})

   
    # ANIMAL PLACEMENT / BUILDING JOBS
   
    for p,building in planned_builds:
        targets.append({
            "priority":2,
            "pos":p,
            "action":["BUILD_"+building],
        })

    for i,inv in enumerate(inventories):
        if not isinstance(inv,dict):
            continue
        for animal_name in ANIMAL_ORDER:
            if inventory_count(inv,animal_name)>0:
                building=ANIMAL[animal_name]["building"]
                for p,t in animals:
                    if t.get("kind")==building and t.get("animal") is None:
                        targets.append({
                            "priority":1,
                            "pos":p,
                            "action":["PLACE",animal_name],
                        })
                        break

    for animal_name in ANIMAL_ORDER:
        if safe_int(shed.get(animal_name,0),0)>0:
            targets.append({
                "priority":1,
                "pos":nearest_shed_spot(farmer_pos,board_size),
                "action":["PICKUP",animal_name,1],
            })

   
    # FERTILIZER USE
   
    # Prefer fertilizer on high-value one-time crops during their bonus
    # window. Otherwise it is sold from the shed.
    fertilizer_available=safe_int(shed.get("FERTILIZER",0),0)
    if fertilizer_available>0:
        best=None
        best_score=-1
        for p,t in plants:
            crop=t.get("crop")
            if crop not in ("MELON","WHEAT","CARROT"):
                continue
            age=day-safe_int(t.get("planted_day",day),day)
            if crop=="MELON":
                good=6<=age<=8
            elif crop=="WHEAT":
                good=2<=age<=3
            else:
                good=2<=age<=2
            if good:
                score={"MELON":5,"WHEAT":2,"CARROT":2}[crop]
                if score>best_score:
                    best_score=score
                    best=p
        if best is not None:
            targets.append({"priority":2,"pos":best,"action":["FERTILIZE"]})

   
    # Optional fertilizer purchase when a premium crop is in its
    # high-value bonus window and fertilizer is still reasonably priced.
    fert_price=price(obs,"FERTILIZER")
    if fert_price>0 and fert_price<=90 and len(market)<10:
        premium_window=False
        for _,t in plants:
            crop=t.get("crop")
            age=day-safe_int(t.get("planted_day",day),day)
            if crop=="MELON" and 6<=age<=8:
                premium_window=True
            elif crop=="WHEAT" and 2<=age<=3:
                premium_window=True
        if premium_window and money-fert_price-reserve>=0:
            market.append(["BUY_PRODUCT","FERTILIZER",1])
            money-=fert_price

    # FERTILIZER PICKUP PIPELINE
   
    # Pick fertilizer from the shed before attempting to fertilize a plant.
    for i,inv in enumerate(inventories):
        if not isinstance(inv,dict):
            inv={}
        if inventory_count(inv,"FERTILIZER")<=0 and safe_int(shed.get("FERTILIZER",0),0)>0:
            targets.append({
                "priority":2,
                "pos":nearest_shed_spot(farmer_pos,board_size),
                "action":["PICKUP","FERTILIZER",1],
            })

    # CONTINUOUS REPLANTING
   
    # Every empty unlocked plot is immediately considered for production.
    # We choose crop independently using the current market, not a batch.
    feed_need=total_animals
    chosen=choose_crop(obs,day,money,feed_need)

    # Only plant if enough time remains for a meaningful first yield.
    if empty:
        for p in empty:
            seed_have=safe_int(seeds.get(chosen,0),0)
            if seed_have>0:
                targets.append({"priority":4,"pos":p,"action":["PLANT",chosen]})
            else:
                # Seed purchase is queued only for actual empty plots.
                cost=CROP[chosen]["seed"]
                if money-cost-reserve>=0 and len(market)<10:
                    market.append(["BUY_SEED",chosen,1])
                    money-=cost
                    targets.append({"priority":4,"pos":p,"action":["PLANT",chosen]})

    # Wheat seed/feed backup: if animals exist and wheat seed inventory is
    # low, buy one wheat seed for future feed production.
    if total_animals>0 and safe_int(seeds.get("WHEAT",0),0)<2 and len(market)<10:
        if money-10-reserve>=0:
            market.append(["BUY_SEED","WHEAT",1])
            money-=10

   
    # ASSIGN ACTIONS
   
    units=[farmer_pos]+list(hand_pos)
    used=set()
    actions=[]

    for i,pos in enumerate(units):
        inv=inventories[i] if i<len(inventories) and isinstance(inventories[i],dict) else {}
        carrying_wheat=inventory_count(inv,"WHEAT")
        carrying_fert=inventory_count(inv,"FERTILIZER")

        feed_targets=[
            t for t in targets
            if t["action"]==["FEED"] and tuple(t["pos"]) not in used
        ]

        if carrying_wheat>0 and feed_targets:
            target=min(feed_targets,key=lambda t:dist(pos,t["pos"]))
        else:
            unfed=sum(
                1 for _,t in real_animals
                if t.get("animal") and not t.get("fed_today",False)
            )

            if carrying_wheat<=0 and unfed>0 and safe_int(shed.get("WHEAT",0),0)>0:
                s=nearest_shed_spot(pos,board_size)
                if adjacent_to_shed(pos,board_size):
                    target={
                        "priority":0,
                        "pos":pos,
                        "action":["PICKUP","WHEAT",max(1,min(unfed,5))],
                    }
                else:
                    target={"priority":0,"pos":s,"action":["PASS"]}
            else:
                fert_targets=[
                    t for t in targets
                    if t["action"]==["FERTILIZE"] and tuple(t["pos"]) not in used
                ]

                if carrying_fert>0 and fert_targets:
                    target=min(fert_targets,key=lambda t:dist(pos,t["pos"]))
                elif carrying_fert<=0 and safe_int(shed.get("FERTILIZER",0),0)>0:
                    s=nearest_shed_spot(pos,board_size)
                    if adjacent_to_shed(pos,board_size):
                        target={
                            "priority":2,
                            "pos":pos,
                            "action":["PICKUP","FERTILIZER",1],
                        }
                    else:
                        target={"priority":2,"pos":s,"action":["PASS"]}
                else:
                    target=choose_target(pos,targets,used)

        if target is None:
            target={"priority":99,"pos":pos,"action":["PASS"]}

        if target["action"]!=["PASS"]:
            used.add(tuple(target["pos"]))

        actions.append(action_to_target(pos,target))

    # DEFENSIVE VALIDATION
  
    # Do not issue duplicate PLANT orders for more seeds than available.
    seed_left={c:safe_int(seeds.get(c,0),0) for c in CROP}
    for a in market:
        if len(a)>=3 and a[0]=="BUY_SEED" and a[1] in seed_left:
            seed_left[a[1]]+=safe_int(a[2],0)

    for i,a in enumerate(actions):
        if len(a)>=2 and a[0]=="PLANT":
            c=a[1]
            if c not in seed_left or seed_left[c]<=0:
                actions[i]=["PASS"]
            else:
                seed_left[c]-=1

    # Never exceed the environment's default market order limit.
    return {
        "farmer":actions[0],
        "hands":actions[1:],
        "market":market[:10],
    }