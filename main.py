# Kaggriculture competitive agent
# Single-file submission: main.py
#
# Strategy:
#   - Hire cheap farm hands early.
#   - Keep every worker productive.
#   - Harvest immediately when profitable.
#   - Water all crops before they can miss a day.
#   - Plant continuously.
#   - Use dynamic market prices.
#   - Sell shed inventory frequently.
#   - Avoid expensive land until existing land is saturated.
#   - Use fertilizer selectively.
#
# The final function is: agent(obs) -> action

CROPS = [
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
]

# Conservative estimated economics.
# These are used only for choosing priorities. Actual prices
# always come from the observation.
CROP_SCORE = {
    "WHEAT": 1.00,
    "CARROT": 1.05,
    "TOMATO": 1.20,
    "STRAWBERRY": 1.35,
    "MELON": 1.45,
}

# Growth estimates used only as a fallback.
GROWTH = {
    "WHEAT": 2,
    "CARROT": 3,
    "TOMATO": 4,
    "STRAWBERRY": 5,
    "MELON": 6,
}

# Approximate seed costs.
SEED_COST = {
    "WHEAT": 10,
    "CARROT": 15,
    "TOMATO": 20,
    "STRAWBERRY": 30,
    "MELON": 80,
}

# Crop preference changes as the season progresses.
# Fast crops become more attractive near the end.
def crop_value(crop, price, day):
    base = CROP_SCORE.get(crop, 1.0)

    # Current market price matters more than our static estimate.
    p = float(price or 1)

    # Approximate value per seed.
    cost = SEED_COST.get(crop, 20)

    # Higher price and lower cost -> better score.
    value = base * (p / max(cost, 1))

    # End-season adjustment.
    remaining = max(0, 30 - day)

    growth = GROWTH.get(crop, 4)

    if growth > remaining:
        value *= 0.08
    elif growth + 1 > remaining:
        value *= 0.30
    elif growth <= 2:
        value *= 1.15

    return value


def tile_kind(tile):
    if tile is None:
        return None
    if tile == "LOCKED":
        return "LOCKED"
    if isinstance(tile, dict):
        return tile.get("kind")
    return None


def is_plant(tile):
    return isinstance(tile, dict) and tile.get("kind") == "PLANT"


def is_animal(tile):
    return (
        isinstance(tile, dict)
        and tile.get("kind") in ("COOP", "PASTURE")
        and tile.get("animal") is not None
    )


def is_structure(tile):
    return (
        isinstance(tile, dict)
        and tile.get("kind") in ("COOP", "PASTURE")
    )


def is_weed(tile):
    return isinstance(tile, dict) and tile.get("kind") == "WEED"


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def nearest_target(pos, targets):
    if not targets:
        return None

    best = None
    best_d = 10**9

    for target in targets:
        d = manhattan(pos, target)
        if d < best_d:
            best_d = d
            best = target

    return best


def direction_toward(pos, target):
    x, y = pos
    tx, ty = target

    dx = tx - x
    dy = ty - y

    # Prefer the larger distance first to reduce zig-zagging.
    if abs(dx) >= abs(dy):
        if dx > 0:
            return ["EAST"]
        if dx < 0:
            return ["WEST"]

    if dy > 0:
        return ["SOUTH"]
    if dy < 0:
        return ["NORTH"]

    return ["PASS"]


def unlocked_empty_tiles(farm):
    result = []

    tiles = farm.get("tiles", [])

    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if tile is None:
                result.append((x, y))

    return result


def scan_farm(farm):
    plants = []
    watered_needed = []
    harvestable = []
    weeds = []
    animals = []
    empty = []

    tiles = farm.get("tiles", [])

    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            p = (x, y)

            if tile is None:
                empty.append(p)

            elif is_weed(tile):
                weeds.append(p)

            elif is_plant(tile):
                plants.append(p)

                if not tile.get("watered_today", False):
                    watered_needed.append(p)

                crop = tile.get("crop")
                planted_day = tile.get("planted_day", 0)
                age = max(0, farm.get("_current_day", 0) - planted_day)

                # The environment exposes yield_units. If positive,
                # harvesting is usually preferable to waiting.
                if tile.get("yield_units", 0) > 0:
                    harvestable.append(p)

                # Fallback for crops whose yield is not yet represented.
                if crop in GROWTH and age >= GROWTH[crop]:
                    if p not in harvestable:
                        harvestable.append(p)

            elif is_animal(tile):
                animals.append(p)

    return {
        "plants": plants,
        "water": watered_needed,
        "harvest": harvestable,
        "weeds": weeds,
        "animals": animals,
        "empty": empty,
    }


def shed_total(shed):
    total = 0
    for v in shed.values():
        try:
            total += int(v)
        except Exception:
            pass
    return total


def market_sell_orders(obs):
    """
    Sell harvested resources sitting in the shed.

    We don't blindly sell fertilizer or seeds.
    Fertilizer is a strategic input.
    """
    private = obs.get("private", {})
    shed = private.get("shed", {})
    market = obs.get("market", {})
    prices = market.get("prices", {})

    orders = []

    # Products that can safely be liquidated.
    products = [
        "WHEAT",
        "CARROT",
        "TOMATO",
        "STRAWBERRY",
        "MELON",
        "EGG",
        "MILK",
        "WOOL",
    ]

    # During the final days, liquidate aggressively.
    day = obs.get("day", 0)
    final_phase = day >= 27

    for item in products:
        amount = int(shed.get(item, 0) or 0)

        if amount <= 0:
            continue

        price = int(prices.get(item, 1) or 1)

        # Don't hoard harvested produce.
        # End game values banked money, not inventory.
        if final_phase:
            sell_n = amount
        else:
            sell_n = amount

        if sell_n > 0:
            orders.append(["SELL", item, sell_n])

    return orders


def choose_seed_orders(obs):
    """
    Buy seeds dynamically.

    We maintain a small rolling buffer instead of buying
    huge quantities. This prevents cash from becoming trapped
    in seeds and allows adaptation to market conditions.
    """
    private = obs.get("private", {})
    seeds = private.get("seeds", {})

    farm = obs["farms"][obs["player"]]
    money = float(farm.get("money", 0))

    day = int(obs.get("day", 0))

    prices = obs.get("market", {}).get("prices", {})

    remaining = max(0, 30 - day)

    # End game: don't buy seeds that cannot reasonably pay back.
    if remaining <= 2:
        return []

    candidates = []

    for crop in CROPS:
        seed_count = int(seeds.get(crop, 0) or 0)

        # Keep a rolling buffer.
        target = 2

        if crop == "WHEAT":
            target = 4

        # Near endgame use smaller inventory.
        if remaining <= 5:
            target = 1

        if seed_count >= target:
            continue

        cost = SEED_COST.get(crop, 20)

        if money < cost:
            continue

        score = crop_value(
            crop,
            prices.get(crop, 1),
            day,
        )

        candidates.append((score, crop, target - seed_count))

    candidates.sort(reverse=True)

    orders = []

    # Buy only the best few crops.
    for _, crop, amount in candidates[:2]:
        if amount > 0:
            orders.append(["BUY_SEED", crop, amount])

    return orders


def hire_orders(obs):
    """
    Farm hands are extremely valuable because they create
    parallel actions every turn.

    The hire cost is Fibonacci-like and resets each day.
    We therefore hire aggressively while the farm has
    enough cash, but avoid draining the bank.
    """
    farm = obs["farms"][obs["player"]]
    money = float(farm.get("money", 0))

    hires_today = int(farm.get("hires_today", 0) or 0)

    # Fibonacci-like cost sequence:
    # 1, 1, 2, 3, 5, 8, ...
    fib = [1, 1]

    while len(fib) <= hires_today + 2:
        fib.append(fib[-1] + fib[-2])

    next_cost = fib[min(hires_today, len(fib) - 1)]

    hands = len(farm.get("hands", []))

    # Don't explode hiring after the farm is already sufficiently parallel.
    #
    # Early game:
    #   1-3 hands
    #
    # Mid game:
    #   3-5 hands
    #
    # Late game:
    #   use cheap hands when possible, but don't burn capital.
    if obs.get("day", 0) < 8:
        desired = 4
    elif obs.get("day", 0) < 18:
        desired = 5
    else:
        desired = 3

    if hands >= desired:
        return []

    # Preserve a cash reserve.
    if money < next_cost + 150:
        return []

    return [["HIRE"]]


def land_orders(obs):
    """
    Land expansion is useful only after the currently unlocked
    area is being exploited.

    Buy one new quadrant when:
      - cash is healthy
      - unlocked area is substantially occupied
      - enough season remains
    """
    farm = obs["farms"][obs["player"]]
    money = float(farm.get("money", 0))
    day = int(obs.get("day", 0))

    unlocked = set(farm.get("unlocked_quadrants", []))

    if day < 5:
        return []

    # Only expand if we have enough cash left to operate.
    if money < 2200:
        return []

    if len(unlocked) >= 4:
        return []

    info = scan_farm(farm)

    empty = len(info["empty"])
    plants = len(info["plants"])

    # Current 5x5 area is still spacious.
    if empty > 10 and plants < 12:
        return []

    # Expansion costs 1000, 2000, 4000.
    # Only buy first/second expansion with a healthy reserve.
    if len(unlocked) == 1 and money >= 2500:
        return [["BUY_LAND"]]

    if len(unlocked) == 2 and money >= 4000:
        return [["BUY_LAND"]]

    return []


def animal_market_orders(obs):
    """
    Animal strategy is deliberately conservative.

    Animals can generate recurring production and fertilizer,
    but they require daily feeding/care and structures.
    We avoid buying them before the crop operation is stable.
    """
    day = int(obs.get("day", 0))
    if day < 7 or day > 25:
        return []

    farm = obs["farms"][obs["player"]]
    money = float(farm.get("money", 0))

    if money < 700:
        return []

    # Count current animals.
    animal_count = 0
    structures = 0

    for row in farm.get("tiles", []):
        for tile in row:
            if is_structure(tile):
                structures += 1
                if tile.get("animal") is not None:
                    animal_count += 1

    # Start with a single animal.
    if animal_count >= 2:
        return []

    # Buy one goose as the cheapest/safer animal choice.
    if structures >= 1:
        return [["BUY_ANIMAL", "GOOSE", 1]]

    return []


def market_actions(obs):
    """
    Market is free from movement, so use it every turn.

    Maximum is 10 orders per turn.
    """
    orders = []

    # Sell first. Banked cash is what ultimately matters.
    orders.extend(market_sell_orders(obs))

    # Buy seeds.
    orders.extend(choose_seed_orders(obs))

    # Hire.
    orders.extend(hire_orders(obs))

    # Occasional animal investment.
    orders.extend(animal_market_orders(obs))

    # Land expansion should be rare and late in the order list.
    orders.extend(land_orders(obs))

    # Never exceed the environment's market order cap.
    return orders[:10]


def best_crop(obs):
    """
    Choose the crop with the best current price/economics.
    """
    prices = obs.get("market", {}).get("prices", {})
    day = int(obs.get("day", 0))

    best = "WHEAT"
    best_score = -1

    for crop in CROPS:
        score = crop_value(
            crop,
            prices.get(crop, 1),
            day,
        )

        if score > best_score:
            best_score = score
            best = crop

    return best


def nearest_action(pos, farm, obs, occupied_targets=None):
    """
    Decide what a worker should do.

    Priority:
      1. harvest
      2. water
      3. animal maintenance
      4. weed clearing
      5. plant
      6. fertilizer
      7. return to useful region
    """
    if occupied_targets is None:
        occupied_targets = set()

    info = scan_farm(farm)

    # Remove targets already assigned to another worker.
    def free_targets(items):
        return [
            p for p in items
            if p not in occupied_targets
        ]

    # 1. Harvest.
    targets = free_targets(info["harvest"])

    target = nearest_target(pos, targets)

    if target is not None:
        if tuple(pos) == tuple(target):
            return ["HARVEST"], target

        return direction_toward(pos, target), target

    # 2. Water.
    targets = free_targets(info["water"])

    target = nearest_target(pos, targets)

    if target is not None:
        if tuple(pos) == tuple(target):
            return ["WATER"], target

        return direction_toward(pos, target), target

    # 3. Animals.
    animal_targets = []

    for y, row in enumerate(farm.get("tiles", [])):
        for x, tile in enumerate(row):
            if is_animal(tile):
                animal_targets.append((x, y))

    target = nearest_target(pos, free_targets(animal_targets))

    if target is not None:
        tile = farm["tiles"][target[1]][target[0]]

        if tuple(pos) == tuple(target):

            # Feed first.
            if not tile.get("fed_today", False):
                return ["FEED"], target

            # Care after feeding.
            if not tile.get("cared_today", False):
                return ["CARE"], target

            # Collect fertilizer if available.
            if tile.get("fertilizer_available", False):
                return ["COLLECT_FERTILIZER"], target

            # Harvest animal output.
            if tile.get("yield_units", 0) > 0:
                return ["HARVEST"], target

            return ["PASS"], target

        return direction_toward(pos, target), target

    # 4. Clear weeds.
    targets = free_targets(info["weeds"])

    target = nearest_target(pos, targets)

    if target is not None:
        if tuple(pos) == tuple(target):
            return ["DIG"], target

        return direction_toward(pos, target), target

    # 5. Plant.
    empty = free_targets(info["empty"])

    target = nearest_target(pos, empty)

    if target is not None:
        if tuple(pos) == tuple(target):
            crop = best_crop(obs)

            seeds = obs.get("private", {}).get("seeds", {})

            if seeds.get(crop, 0) > 0:
                return ["PLANT", crop], target

            # Find any available seed.
            for c in sorted(
                CROPS,
                key=lambda c: crop_value(
                    c,
                    obs.get("market", {}).get("prices", {}).get(c, 1),
                    obs.get("day", 0),
                ),
                reverse=True,
            ):
                if seeds.get(c, 0) > 0:
                    return ["PLANT", c], target

            return ["PASS"], target

        return direction_toward(pos, target), target

    return ["PASS"], None


def fallback_action(pos, farm):
    """
    If there is nothing urgent, stay near the central farm area.

    This prevents workers from wandering aimlessly across
    locked quadrants.
    """
    center = (4, 4)

    if tuple(pos) == center:
        return ["PASS"]

    return direction_toward(pos, center)


def worker_action(index, obs, farm, occupied):
    """
    Compute one action for farmer or farm hand.
    """
    positions = [farm.get("farmer", [0, 0])]
    positions.extend(farm.get("hands", []))

    if index >= len(positions):
        return ["PASS"]

    pos = positions[index]

    action, target = nearest_action(
        pos,
        farm,
        obs,
        occupied,
    )

    if target is not None:
        occupied.add(tuple(target))

    return action


def shed_management(obs):
    """
    If a worker is standing beside the shed and carrying inventory,
    DROP it.

    We only use this as a secondary action when there is no urgent
    field work for that worker.
    """
    private = obs.get("private", {})
    inventories = private.get("inventories", [])

    farm = obs["farms"][obs["player"]]

    shed_positions = {
        (4, 4),
        (5, 4),
        (4, 5),
        (5, 5),
    }

    actions = []

    positions = [farm.get("farmer", [])]
    positions.extend(farm.get("hands", []))

    for i, pos in enumerate(positions):
        if i >= len(inventories):
            continue

        if tuple(pos) not in shed_positions:
            continue

        inv = inventories[i] or {}

        carrying = False

        for v in inv.values():
            try:
                if int(v) > 0:
                    carrying = True
                    break
            except Exception:
                pass

        if carrying:
            actions.append((i, ["DROP"]))

    return actions


def build_structure_action(obs, farm):
    """
    Build one animal structure if we have enough money and
    an empty tile. This is intentionally slow and conservative.
    """
    day = int(obs.get("day", 0))

    if day < 8 or day > 24:
        return None

    money = float(farm.get("money", 0))

    if money < 500:
        return None

    # Only build if we don't already have structures.
    structures = 0

    for row in farm.get("tiles", []):
        for tile in row:
            if is_structure(tile):
                structures += 1

    if structures >= 1:
        return None

    empty = unlocked_empty_tiles(farm)

    if not empty:
        return None

    # Build near center to reduce future movement.
    center = (4, 4)
    target = nearest_target(center, empty)

    if target is None:
        return None

    pos = tuple(farm.get("farmer", [0, 0]))

    if pos == target:
        return ["BUILD_COOP"]

    return direction_toward(pos, target)


def agent(obs):
    """
    Main Kaggriculture agent.

    Must return:
        {
            "farmer": [...],
            "hands": [[...], ...],
            "market": [[...], ...]
        }
    """
    try:
        player = int(obs.get("player", 0))

        farms = obs.get("farms", [])
        if not farms or player >= len(farms):
            return {
                "farmer": ["PASS"],
                "hands": [],
                "market": [],
            }

        farm = farms[player]

        # Keep current day available to scan_farm.
        # We do not mutate the real observation in a meaningful way,
        # only attach a harmless local field to this dictionary.
        farm["_current_day"] = int(obs.get("day", 0))

        # Market work is independent of movement.
        market = market_actions(obs)

        # Determine number of workers.
        hands_positions = farm.get("hands", [])
        worker_count = 1 + len(hands_positions)

        actions = []

        occupied = set()

        for i in range(worker_count):
            action = worker_action(
                i,
                obs,
                farm,
                occupied,
            )

            actions.append(action)

        farmer_action = actions[0]
        hand_actions = actions[1:]

        # Shed drops are only used if the worker isn't currently
        # doing something more important.
        drops = shed_management(obs)

        for index, drop_action in drops:
            if index < len(actions):
                # Drop only when worker has no urgent action.
                if actions[index][0] == "PASS":
                    actions[index] = drop_action

        # Structure construction is lower priority than crop work.
        # Only invoke if farmer would otherwise be idle.
        if farmer_action[0] == "PASS":
            structure_action = build_structure_action(
                obs,
                farm,
            )

            if structure_action is not None:
                farmer_action = structure_action

        return {
            "farmer": farmer_action,
            "hands": hand_actions,
            "market": market[:10],
        }

    except Exception:
        # Never crash the Kaggle environment.
        # A PASS is vastly better than a traceback.
        hands = []

        try:
            hands = [
                ["PASS"]
                for _ in obs.get("farms", [])[obs.get("player", 0)].get(
                    "hands", []
                )
            ]
        except Exception:
            hands = []

        return {
            "farmer": ["PASS"],
            "hands": hands,
            "market": [],
        }