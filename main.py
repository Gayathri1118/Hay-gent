# ============================================================
# KAGGRICULTURE - GLOBAL PROFIT SCHEDULER
# ============================================================
#
# Strategy:
#   1. Evaluate the whole farm every turn.
#   2. Build a global list of jobs.
#   3. Score jobs by urgency + economic value + distance.
#   4. Assign different workers to different jobs.
#   5. Keep the farm continuously productive.
#   6. Adapt crop choice to live market prices.
#   7. Exploit fertilizer on high-value one-time crops.
#   8. Run animals only when their economics justify them.
#   9. Hire hands aggressively while cheap.
#  10. Preserve cash for productive investments.
#
# Final required function:
#     agent(obs)
#
# Standard library only.
# ============================================================


CROPS = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
)

# Official documented economics.
SEED_COST = {
    "WHEAT": 10,
    "CARROT": 20,
    "TOMATO": 50,
    "STRAWBERRY": 100,
    "MELON": 80,
}

BASE_PRICE = {
    "WHEAT": 25,
    "CARROT": 35,
    "TOMATO": 60,
    "STRAWBERRY": 120,
    "MELON": 250,
}

FIRST_YIELD_DAY = {
    "WHEAT": 2,
    "CARROT": 2,
    "TOMATO": 8,
    "STRAWBERRY": 10,
    "MELON": 10,
}

MAX_YIELD_DAY = {
    "WHEAT": 4,
    "CARROT": 3,
    "MELON": 12,
}

ANIMALS = {
    "GOOSE": {
        "cost": 300,
        "product": "EGG",
        "price": 50,
        "interval": 1,
        "structure": "COOP",
    },
    "COW": {
        "cost": 400,
        "product": "MILK",
        "price": 160,
        "interval": 2,
        "structure": "PASTURE",
    },
    "SHEEP": {
        "cost": 500,
        "product": "WOOL",
        "price": 200,
        "interval": 3,
        "structure": "PASTURE",
    },
}

ANIMAL_ORDER = ("GOOSE", "COW", "SHEEP")


# ============================================================
# SAFE HELPERS
# ============================================================

def number(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def integer(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def position(unit):
    try:
        return int(unit[0]), int(unit[1])
    except Exception:
        return 0, 0


def distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def tile_at(farm, p):
    x, y = p
    tiles = farm.get("tiles", [])

    if y < 0 or y >= len(tiles):
        return None

    if x < 0 or x >= len(tiles[y]):
        return None

    return tiles[y][x]


def tile_kind(tile):
    if isinstance(tile, dict):
        return tile.get("kind")
    return None


def is_plant(tile):
    return tile_kind(tile) == "PLANT"


def is_weed(tile):
    return tile_kind(tile) == "WEED"


def is_structure(tile):
    return tile_kind(tile) in ("COOP", "PASTURE")


def is_animal_structure(tile):
    return (
        is_structure(tile)
        and tile.get("animal") is not None
    )


def is_empty(tile):
    return tile is None


def direction_to(src, dst):
    sx, sy = src
    dx, dy = dst

    if sx == dx and sy == dy:
        return ["PASS"]

    # Prefer the axis with the larger distance.
    if abs(dx - sx) >= abs(dy - sy):
        if dx > sx:
            return ["EAST"]
        return ["WEST"]

    if dy > sy:
        return ["SOUTH"]

    return ["NORTH"]


# ============================================================
# FARM SCANNER
# ============================================================

def scan_farm(farm):
    plants = []
    harvestable = []
    needs_water = []
    weeds = []
    empty = []
    structures = []
    animals = []

    for y, row in enumerate(farm.get("tiles", [])):
        for x, tile in enumerate(row):

            p = (x, y)

            if tile == "LOCKED":
                continue

            if tile is None:
                empty.append(p)
                continue

            if is_weed(tile):
                weeds.append(p)
                continue

            if is_plant(tile):

                plants.append(p)

                if not tile.get("watered_today", False):
                    needs_water.append(p)

                if integer(tile.get("yield_units", 0)) > 0:
                    harvestable.append(p)

                continue

            if is_structure(tile):

                structures.append(p)

                if tile.get("animal") is not None:
                    animals.append(p)

    return {
        "plants": plants,
        "harvestable": harvestable,
        "water": needs_water,
        "weeds": weeds,
        "empty": empty,
        "structures": structures,
        "animals": animals,
    }


# ============================================================
# MARKET ECONOMICS
# ============================================================

def live_price(obs, item):
    prices = obs.get("market", {}).get("prices", {})
    return number(
        prices.get(
            item,
            BASE_PRICE.get(item, 1),
        ),
        1,
    )


def price_ratio(obs, crop):
    price = live_price(obs, crop)
    cost = SEED_COST.get(crop, 1)

    return price / max(cost, 1)


def crop_profit_score(obs, crop):
    """
    Estimate profit density rather than simply choosing
    the highest sale price.
    """

    day = integer(obs.get("day", 0))
    remaining = 30 - day

    price = live_price(obs, crop)
    cost = SEED_COST.get(crop, 1)
    first = FIRST_YIELD_DAY.get(crop, 10)

    roi = price / max(cost, 1)

    # Long crops become dangerous late in the season.
    if first > remaining:
        return -1000000.0

    # Production efficiency.
    roi *= 1.0 / max(first, 1) * 10.0

    # Premium crops are attractive only while their price
    # has not collapsed.
    if crop in ("STRAWBERRY", "MELON"):
        if price <= BASE_PRICE[crop] * 0.45:
            roi *= 0.25

    # Fast crops become increasingly attractive near the end.
    if remaining <= 6:
        if first <= 2:
            roi *= 4.0
        else:
            roi *= 0.10

    elif remaining <= 10:
        if first <= 3:
            roi *= 2.0
        elif first >= 8:
            roi *= 0.35

    # Ongoing crops become more attractive when enough season remains.
    if crop == "TOMATO" and remaining >= 14:
        roi *= 1.35

    if crop == "STRAWBERRY" and remaining >= 16:
        roi *= 1.20

    return roi


def best_crop(obs):
    best = "WHEAT"
    best_score = -10**30

    for crop in CROPS:

        score = crop_profit_score(
            obs,
            crop,
        )

        if score > best_score:
            best_score = score
            best = crop

    return best


def ranked_crops(obs):
    return sorted(
        CROPS,
        key=lambda c: crop_profit_score(obs, c),
        reverse=True,
    )


# ============================================================
# WORKER JOB MODEL
# ============================================================

def add_job(jobs, job_type, target, score, crop=None):
    jobs.append({
        "type": job_type,
        "target": target,
        "score": float(score),
        "crop": crop,
    })


def plant_jobs(obs, farm, info, jobs):
    seeds = obs.get("private", {}).get("seeds", {})

    ranked = ranked_crops(obs)

    best = ranked[0]

    if integer(seeds.get(best, 0)) <= 0:

        best = None

        for crop in ranked:
            if integer(seeds.get(crop, 0)) > 0:
                best = crop
                break

    if best is None:
        return

    crop_score = crop_profit_score(
        obs,
        best,
    )

    day = integer(obs.get("day", 0))

    for p in info["empty"]:

        # Avoid planting enormous fields late in the season.
        if day >= 28:
            break

        score = (
            35.0
            + crop_score * 10.0
        )

        add_job(
            jobs,
            "PLANT",
            p,
            score,
            best,
        )


def harvest_jobs(obs, farm, info, jobs):

    day = integer(obs.get("day", 0))

    for p in info["harvestable"]:

        tile = tile_at(farm, p)

        if not is_plant(tile):
            continue

        crop = tile.get("crop", "WHEAT")

        units = integer(
            tile.get("yield_units", 1)
        )

        price = live_price(
            obs,
            crop,
        )

        # Harvest value.
        value = units * price

        # Very high priority because harvest unlocks the tile.
        score = (
            1000.0
            + value * 5.0
        )

        # Endgame liquidation.
        if day >= 27:
            score += 1000.0

        add_job(
            jobs,
            "HARVEST",
            p,
            score,
            crop,
        )


def water_jobs(obs, farm, info, jobs):

    day = integer(obs.get("day", 0))

    for p in info["water"]:

        tile = tile_at(farm, p)

        if not is_plant(tile):
            continue

        crop = tile.get("crop", "WHEAT")

        consecutive = integer(
            tile.get(
                "consecutive_unwatered",
                0,
            )
        )

        # Watering is mandatory, but watering during the
        # bonus window has additional economic value.
        score = 700.0

        if consecutive >= 1:
            score += 700.0

        if crop in MAX_YIELD_DAY:

            planted = integer(
                tile.get("planted_day", day)
            )

            age = max(
                0,
                day - planted,
            )

            bonus_start = (
                MAX_YIELD_DAY[crop] + 1
            ) // 2

            if age >= bonus_start:
                score += 600.0

        # Fertilized plants are particularly valuable to water.
        fertilized_until = integer(
            tile.get(
                "fertilized_until_day",
                -1,
            ),
            -1,
        )

        if fertilized_until >= day:
            score += 500.0

        add_job(
            jobs,
            "WATER",
            p,
            score,
            crop,
        )


def fertilizer_jobs(obs, farm, info, jobs):

    shed = obs.get(
        "private",
        {},
    ).get(
        "shed",
        {},
    )

    fertilizer = integer(
        shed.get("FERTILIZER", 0)
    )

    if fertilizer <= 0:
        return

    day = integer(
        obs.get("day", 0)
    )

    for p in info["plants"]:

        tile = tile_at(
            farm,
            p,
        )

        if not is_plant(tile):
            continue

        crop = tile.get(
            "crop",
            "WHEAT",
        )

        # Fertilizer is most valuable on one-time crops
        # while they are inside the yield-building window.
        if crop not in MAX_YIELD_DAY:
            continue

        planted = integer(
            tile.get(
                "planted_day",
                day,
            )
        )

        age = max(
            0,
            day - planted,
        )

        bonus_start = (
            MAX_YIELD_DAY[crop] + 1
        ) // 2

        if age > MAX_YIELD_DAY[crop]:
            continue

        if age < bonus_start:
            continue

        current_until = integer(
            tile.get(
                "fertilized_until_day",
                -1,
            ),
            -1,
        )

        if current_until >= day:
            continue

        value = (
            crop_profit_score(
                obs,
                crop,
            )
            * 100
        )

        add_job(
            jobs,
            "FERTILIZE",
            p,
            500.0 + value,
            crop,
        )


def weed_jobs(obs, farm, info, jobs):

    for p in info["weeds"]:

        add_job(
            jobs,
            "DIG",
            p,
            250.0,
        )


# ============================================================
# ANIMAL JOBS
# ============================================================

def animal_jobs(obs, farm, info, jobs):

    for p in info["animals"]:

        tile = tile_at(
            farm,
            p,
        )

        if not is_animal_structure(tile):
            continue

        # Survival first.
        if not tile.get(
            "fed_today",
            False,
        ):
            add_job(
                jobs,
                "FEED",
                p,
                1500.0,
            )
            continue

        # Care creates a future production bonus.
        if not tile.get(
            "cared_today",
            False,
        ):
            add_job(
                jobs,
                "CARE",
                p,
                900.0,
            )

        # Fertilizer is free recurring income.
        if tile.get(
            "fertilizer_available",
            False,
        ):
            add_job(
                jobs,
                "COLLECT_FERTILIZER",
                p,
                850.0,
            )

        # Harvest accumulated animal output.
        if integer(
            tile.get(
                "yield_units",
                0,
            )
        ) > 0:
            animal = tile.get(
                "animal"
            )

            data = ANIMALS.get(
                animal,
                {},
            )

            product = data.get(
                "product"
            )

            price = live_price(
                obs,
                product,
            )

            units = integer(
                tile.get(
                    "yield_units",
                    1,
                )
            )

            add_job(
                jobs,
                "HARVEST_ANIMAL",
                p,
                850.0 + units * price * 4,
            )


# ============================================================
# GLOBAL JOB BUILDER
# ============================================================

def build_jobs(obs, farm):

    info = scan_farm(
        farm
    )

    jobs = []

    harvest_jobs(
        obs,
        farm,
        info,
        jobs,
    )

    animal_jobs(
        obs,
        farm,
        info,
        jobs,
    )

    water_jobs(
        obs,
        farm,
        info,
        jobs,
    )

    fertilizer_jobs(
        obs,
        farm,
        info,
        jobs,
    )

    weed_jobs(
        obs,
        farm,
        info,
        jobs,
    )

    plant_jobs(
        obs,
        farm,
        info,
        jobs,
    )

    # Highest-value jobs first.
    jobs.sort(
        key=lambda j: j["score"],
        reverse=True,
    )

    return jobs


# ============================================================
# GLOBAL WORKER ASSIGNMENT
# ============================================================

def assign_jobs(obs, farm, jobs):

    workers = [
        farm.get(
            "farmer",
            [0, 0],
        )
    ]

    workers.extend(
        farm.get(
            "hands",
            [],
        )
    )

    assignments = [
        None
        for _ in workers
    ]

    used_targets = set()

    # Assign the most valuable job to the worker
    # for whom it has the best utility.
    for worker_index, worker_pos in enumerate(workers):

        best_job = None
        best_utility = -10**30

        for job in jobs:

            target = job["target"]

            if target in used_targets:
                continue

            d = distance(
                position(worker_pos),
                target,
            )

            # Movement is expensive because every movement
            # consumes a whole turn.
            utility = (
                job["score"]
                - d * 45.0
            )

            # Small role preference.
            if worker_index == 0:
                # Farmer is best used for urgent jobs.
                if job["type"] in (
                    "HARVEST",
                    "FEED",
                    "HARVEST_ANIMAL",
                ):
                    utility += 120.0

            if utility > best_utility:

                best_utility = utility
                best_job = job

        if best_job is not None:

            assignments[
                worker_index
            ] = best_job

            used_targets.add(
                best_job["target"]
            )

    return assignments


# ============================================================
# JOB EXECUTION
# ============================================================

def execute_job(
    worker_pos,
    job,
    farm,
    obs,
):

    if job is None:
        return ["PASS"]

    target = job["target"]

    current = position(
        worker_pos
    )

    if current != target:
        return direction_to(
            current,
            target,
        )

    job_type = job["type"]

    if job_type == "HARVEST":
        return ["HARVEST"]

    if job_type == "WATER":
        return ["WATER"]

    if job_type == "FERTILIZE":
        return ["FERTILIZE"]

    if job_type == "DIG":
        return ["DIG"]

    if job_type == "PLANT":

        crop = job.get(
            "crop"
        )

        seeds = obs.get(
            "private",
            {},
        ).get(
            "seeds",
            {},
        )

        if (
            crop
            and integer(
                seeds.get(
                    crop,
                    0,
                )
            ) > 0
        ):
            return [
                "PLANT",
                crop,
            ]

        return ["PASS"]

    if job_type == "FEED":
        return ["FEED"]

    if job_type == "CARE":
        return ["CARE"]

    if job_type == "COLLECT_FERTILIZER":
        return [
            "COLLECT_FERTILIZER"
        ]

    if job_type == "HARVEST_ANIMAL":
        return ["HARVEST"]

    return ["PASS"]


# ============================================================
# ANIMAL PURCHASE / PLACEMENT
# ============================================================

def animal_strategy(obs, farm, info):

    day = integer(
        obs.get("day", 0)
    )

    money = number(
        farm.get(
            "money",
            0,
        )
    )

    # Animals need enough season remaining to amortize setup.
    if day < 4 or day > 22:
        return []

    structures = info["structures"]
    animals = info["animals"]

    orders = []

    # One goose is the safest first animal.
    # Cheap setup and daily production.
    if len(animals) == 0:

        if money >= 900:

            # Only buy if there is a structure already
            # or we can build one.
            if len(structures) > 0:

                orders.append(
                    [
                        "BUY_ANIMAL",
                        "GOOSE",
                        1,
                    ]
                )

    # Don't flood the farm with animals.
    if len(animals) >= 2:
        return orders

    return orders


# ============================================================
# MARKET MANAGER
# ============================================================

def market_actions(obs, farm, info):

    private = obs.get(
        "private",
        {},
    )

    shed = private.get(
        "shed",
        {},
    )

    seeds = private.get(
        "seeds",
        {},
    )

    money = number(
        farm.get(
            "money",
            0,
        )
    )

    day = integer(
        obs.get(
            "day",
            0,
        )
    )

    orders = []

    # --------------------------------------------------------
    # SELL HARVESTED GOODS
    # --------------------------------------------------------

    sellable = (
        "WHEAT",
        "CARROT",
        "TOMATO",
        "STRAWBERRY",
        "MELON",
        "EGG",
        "MILK",
        "WOOL",
    )

    for item in sellable:

        amount = integer(
            shed.get(
                item,
                0,
            )
        )

        if amount <= 0:
            continue

        price = live_price(
            obs,
            item,
        )

        # Premium goods are sold only when they are not being
        # destroyed by a market glut.
        if item in (
            "STRAWBERRY",
            "MELON",
            "MILK",
            "WOOL",
        ):
            base = BASE_PRICE.get(
                item,
                price,
            )

            if price < base * 0.35 and day < 27:
                # Keep a small reserve, but don't hoard forever.
                sell_amount = max(
                    0,
                    amount - 2,
                )
            else:
                sell_amount = amount

        else:
            sell_amount = amount

        if sell_amount > 0:
            orders.append(
                [
                    "SELL",
                    item,
                    sell_amount,
                ]
            )

    # --------------------------------------------------------
    # SEED PURCHASE
    # --------------------------------------------------------

    ranked = ranked_crops(
        obs
    )

    # Keep multiple seeds rather than betting the whole farm
    # on one market quote.
    for crop in ranked[:2]:

        have = integer(
            seeds.get(
                crop,
                0,
            )
        )

        target = 5

        if day >= 24:
            target = 2

        needed = max(
            0,
            target - have,
        )

        if needed <= 0:
            continue

        cost = SEED_COST.get(
            crop,
            20,
        )

        # Keep enough cash for operations.
        reserve = (
            1000
            if day < 15
            else 500
        )

        affordable = int(
            max(
                0,
                money - reserve,
            )
            // cost
        )

        buy = min(
            needed,
            affordable,
        )

        if buy > 0:

            orders.append(
                [
                    "BUY_SEED",
                    crop,
                    buy,
                ]
            )

    # --------------------------------------------------------
    # WHEAT BUFFER
    # --------------------------------------------------------

    wheat = integer(
        seeds.get(
            "WHEAT",
            0,
        )
    )

    # Animals consume wheat.
    animal_count = len(
        info["animals"]
    )

    desired_wheat = (
        5
        + animal_count * 2
    )

    if wheat < desired_wheat:

        amount = desired_wheat - wheat

        affordable = int(
            max(
                0,
                money - 300,
            )
            // SEED_COST["WHEAT"]
        )

        amount = min(
            amount,
            affordable,
        )

        if amount > 0:

            orders.append(
                [
                    "BUY_SEED",
                    "WHEAT",
                    amount,
                ]
            )

    # --------------------------------------------------------
    # FERTILIZER PURCHASE
    # --------------------------------------------------------

    fertilizer = integer(
        shed.get(
            "FERTILIZER",
            0,
        )
    )

    high_value_plants = 0

    for p in info["plants"]:

        tile = tile_at(
            farm,
            p,
        )

        if not is_plant(tile):
            continue

        crop = tile.get(
            "crop",
        )

        if crop in (
            "TOMATO",
            "STRAWBERRY",
            "MELON",
        ):
            high_value_plants += 1

    # Buy a small fertilizer buffer when useful.
    if (
        high_value_plants >= 2
        and fertilizer < 2
        and money >= 1000
    ):

        orders.append(
            [
                "BUY_PRODUCT",
                "FERTILIZER",
                1,
            ]
        )

    # --------------------------------------------------------
    # HIRE HANDS
    # --------------------------------------------------------

    hands = farm.get(
        "hands",
        [],
    )

    hires_today = integer(
        farm.get(
            "hires_today",
            0,
        )
    )

    fib = [1, 1]

    while len(fib) <= hires_today:
        fib.append(
            fib[-1]
            + fib[-2]
        )

    hire_cost = fib[
        min(
            hires_today,
            len(fib) - 1,
        )
    ]

    # Early/mid game: maximize action count.
    desired_hands = 6

    if day >= 24:
        desired_hands = 4

    if len(hands) < desired_hands:

        if money >= hire_cost + 500:

            orders.append(
                ["HIRE"]
            )

    # --------------------------------------------------------
    # LAND
    # --------------------------------------------------------

    quadrants = farm.get(
        "unlocked_quadrants",
        [],
    )

    occupied = (
        len(info["plants"])
        + len(info["structures"])
    )

    empty = len(
        info["empty"]
    )

    # Land is only useful when the current area is genuinely busy.
    if (
        day >= 7
        and day <= 22
        and len(quadrants) < 4
        and money >= 2500
        and occupied >= 18
        and empty <= 7
    ):

        orders.append(
            ["BUY_LAND"]
        )

    # --------------------------------------------------------
    # ANIMALS
    # --------------------------------------------------------

    orders.extend(
        animal_strategy(
            obs,
            farm,
            info,
        )
    )

    return orders[:10]


# ============================================================
# BUILD ANIMAL STRUCTURE
# ============================================================

def structure_action(
    obs,
    farm,
    info,
):

    day = integer(
        obs.get(
            "day",
            0,
        )
    )

    if day < 3 or day > 22:
        return None

    # Build a coop if we have none.
    coop_exists = False
    pasture_exists = False

    for p in info["structures"]:

        tile = tile_at(
            farm,
            p,
        )

        if not isinstance(
            tile,
            dict,
        ):
            continue

        if tile.get(
            "kind"
        ) == "COOP":
            coop_exists = True

        if tile.get(
            "kind"
        ) == "PASTURE":
            pasture_exists = True

    empty = info["empty"]

    if not empty:
        return None

    farmer = position(
        farm.get(
            "farmer",
            [0, 0],
        )
    )

    target = min(
        empty,
        key=lambda p: distance(
            farmer,
            p,
        )
    )

    if target != farmer:
        return direction_to(
            farmer,
            target,
        )

    if not coop_exists:
        return [
            "BUILD_COOP"
        ]

    # Pasture is only needed for future cows/sheep.
    if (
        day <= 15
        and not pasture_exists
        and len(info["animals"]) >= 1
    ):
        return [
            "BUILD_PASTURE"
        ]

    return None


# ============================================================
# ANIMAL PLACEMENT
# ============================================================

def placement_action(
    obs,
    farm,
    worker_index,
    worker_pos,
):

    shed = obs.get(
        "private",
        {},
    ).get(
        "shed",
        {},
    )

    current = position(
        worker_pos,
    )

    tile = tile_at(
        farm,
        current,
    )

    # Only place an animal when standing on its matching structure.
    if not is_structure(tile):
        return None

    structure = tile.get(
        "kind"
    )

    if tile.get(
        "animal"
    ) is not None:
        return None

    desired = None

    if structure == "COOP":
        desired = "GOOSE"

    elif structure == "PASTURE":

        if integer(
            shed.get(
                "SHEEP",
                0,
            )
        ) > 0:
            desired = "SHEEP"

        elif integer(
            shed.get(
                "COW",
                0,
            )
        ) > 0:
            desired = "COW"

    if desired is None:
        return None

    if integer(
        shed.get(
            desired,
            0,
        )
    ) <= 0:
        return None

    return [
        "PLACE",
        desired,
        1,
    ]


# ============================================================
# SHED MANAGEMENT
# ============================================================

def inventory_total(inv):
    total = 0

    if not isinstance(
        inv,
        dict,
    ):
        return 0

    for value in inv.values():
        total += integer(
            value,
            0,
        )

    return total


def shed_management(
    obs,
    farm,
    actions,
):

    private = obs.get(
        "private",
        {},
    )

    inventories = private.get(
        "inventories",
        [],
    )

    if not inventories:
        return actions

    positions = [
        farm.get(
            "farmer",
            [0, 0],
        )
    ]

    positions.extend(
        farm.get(
            "hands",
            [],
        )
    )

    # Starting shed is around the central area of the
    # initially unlocked quadrant. Use several adjacent cells.
    shed_points = (
        (2, 2),
        (1, 2),
        (2, 1),
        (3, 2),
        (2, 3),
    )

    for i, inv in enumerate(
        inventories
    ):

        if i >= len(
            positions
        ):
            break

        if i >= len(
            actions
        ):
            break

        if inventory_total(
            inv
        ) <= 0:
            continue

        if actions[i][0] != "PASS":
            continue

        pos = position(
            positions[i]
        )

        near = min(
            shed_points,
            key=lambda p: distance(
                pos,
                p,
            )
        )

        if distance(
            pos,
            near,
        ) <= 1:

            actions[i] = [
                "DROP"
            ]

    return actions


# ============================================================
# MAIN AGENT
# ============================================================

def agent(obs):

    try:

        player = integer(
            obs.get(
                "player",
                0,
            )
        )

        farms = obs.get(
            "farms",
            [],
        )

        if (
            not farms
            or player < 0
            or player >= len(farms)
        ):

            return {
                "farmer": ["PASS"],
                "hands": [],
                "market": [],
            }

        farm = farms[player]

        info = scan_farm(
            farm
        )

        # ----------------------------------------------------
        # MARKET
        # ----------------------------------------------------

        market = market_actions(
            obs,
            farm,
            info,
        )

        # ----------------------------------------------------
        # GLOBAL JOB SCHEDULER
        # ----------------------------------------------------

        jobs = build_jobs(
            obs,
            farm,
        )

        assignments = assign_jobs(
            obs,
            farm,
            jobs,
        )

        # ----------------------------------------------------
        # WORKER ACTIONS
        # ----------------------------------------------------

        workers = [
            farm.get(
                "farmer",
                [0, 0],
            )
        ]

        workers.extend(
            farm.get(
                "hands",
                [],
            )
        )

        actions = []

        for i, worker in enumerate(
            workers
        ):

            # Animal placement can override an idle worker.
            placement = placement_action(
                obs,
                farm,
                i,
                worker,
            )

            if placement is not None:
                actions.append(
                    placement
                )
                continue

            job = (
                assignments[i]
                if i < len(assignments)
                else None
            )

            action = execute_job(
                worker,
                job,
                farm,
                obs,
            )

            actions.append(
                action
            )

        # ----------------------------------------------------
        # STRUCTURE BUILDING
        # ----------------------------------------------------

        if actions:

            if actions[0][0] == "PASS":

                build = structure_action(
                    obs,
                    farm,
                    info,
                )

                if build is not None:
                    actions[0] = build

        # ----------------------------------------------------
        # INVENTORY DROP
        # ----------------------------------------------------

        actions = shed_management(
            obs,
            farm,
            actions,
        )

        # ----------------------------------------------------
        # SAFE OUTPUT
        # ----------------------------------------------------

        farmer_action = actions[0]

        hands_actions = []

        for action in actions[1:]:

            if (
                isinstance(
                    action,
                    list,
                )
                and action
            ):
                hands_actions.append(
                    action
                )
            else:
                hands_actions.append(
                    ["PASS"]
                )

        if not isinstance(
            farmer_action,
            list,
        ):
            farmer_action = [
                "PASS"
            ]

        return {
            "farmer": farmer_action,
            "hands": hands_actions,
            "market": market[:10],
        }

    except Exception:

        # The competition should never receive a traceback.
        # Return valid no-op actions instead.
        try:
            farm = obs.get(
                "farms",
                [],
            )[obs.get(
                "player",
                0,
            )]

            n = len(
                farm.get(
                    "hands",
                    [],
                )
            )

        except Exception:
            n = 0

        return {
            "farmer": ["PASS"],
            "hands": [
                ["PASS"]
                for _ in range(n)
            ],
            "market": [],
        }