"""Fire-specific claims category logic."""

import pandas as pd


def assign_primary_loss_category(df):
    """Add primary_loss_category for fire claims."""
    df_claims = df.copy()

    desc = (
        df_claims["claim_desc"]
        .fillna("")
        .astype(str)
        .str.lower()
        .str.replace(r"[\r\n]+", " ", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    def has(pattern):
        return desc.str.contains(pattern, regex=True, na=False)

    df_claims["primary_loss_category"] = "Other / unusual or unclear description"
    assigned = pd.Series(False, index=df_claims.index)

    def assign_category(category, mask):
        nonlocal assigned
        m = mask & ~assigned
        df_claims.loc[m, "primary_loss_category"] = category
        assigned.loc[m] = True

    wildfire = has(
        r"\b(?:wild\s*fire|wildfire|wildland|brush fire|grass fire|forest fire|vegetation fire|"
        r"cal\s*fire|camp fire|bobcat fire|kincade fire|glass fire|dixie fire|czu|lightning complex|"
        r"holy fire|evacuat\w*|smoke and ash|ash(?:es)? damage|ash/soot|soot/ash)\b"
    )

    kitchen = has(
        r"\b(?:kitchen|stove|oven|range|cook(?:ing)?|grease|frying|pan|pot|microwave|"
        r"toaster|air fryer|dishwasher|hot butter)\b"
    )

    garage_vehicle_outbuilding = has(
        r"\b(?:garage|vehicle|car|truck|auto|automobile|rv|motorhome|trailer|shed|barn|"
        r"detached|outbuilding|out bldg|outbldg|accessory structure|boat|motorcycle|tractor)\b"
    )

    heating = has(
        r"\b(?:chimney|fireplace|fire place|wood stove|woodstove|pellet stove|stove pipe|flue|"
        r"heater|heaters|furnace|space heater|wall heater|baseboard heater|water heater|boiler|"
        r"heat lamp|electric blanket|bb heater|fp|fire log|burning log|log rolled|log roll)\b"
    )

    electrical = has(
        r"\b(?:electric|electrical|wiring|wire|outlet|breaker|panel|short(?:ed)?|short circuit|"
        r"arcing|arc|power surge|transformer|utility|power line|powerline|power pole|"
        r"extension cord|junction box|j-box|lightning|halogen light|lamp)\b"
    )

    appliance_equipment = has(
        r"\b(?:dryer|dry caught|washer|washing machine|refrigerator|refrigator|fridge|freezer|"
        r"appliance|hvac|a/c|ac unit|air condition|generator|motor|equipment|vacuum|"
        r"swamp cooler|pump)\b"
    )

    external_exposure = has(
        r"\b(?:neighbor|neighbors|neighbour|next door|adjacent|unit below|unit above|nearby|near by|"
        r"spread from|jumped over|jumped and caught|started in another|from another|adjoining|"
        r"exposure fire)\b"
    )

    open_flame = has(
        r"\b(?:candle|candles|smoking|smoker|cigarette|cigar|lighter|match|open flame|"
        r"fireworks?|barbecue|bbq|grill|fire pit|firepit|magnifying glass)\b"
    )

    gas_explosion = has(
        r"\b(?:gas|propane|explosion|explode|exploded|natural gas|bbq tank|gas leak)\b"
    )

    arson = has(
        r"\b(?:arson|set fire|intentionally|suspicious|incendiary|vandal(?:ism)?)\b"
    )

    work_activity = has(
        r"\b(?:contractor|construction|worker|roofing|welding|welder|torch|solder|soldering|"
        r"plumber|pipe repair|repairman|repair man|maintenance|work being performed)\b"
    )

    outdoor_yard = has(
        r"\b(?:trash|garbage|dumpster|yard|fence|deck|decking|patio|bush|shrub|mulch|tree|"
        r"landscap|outside fire|exterior fire|plants)\b"
    )

    severe_total = has(
        r"\b(?:total burn|total loss|totally burned|completely burned|destroyed|burned down|"
        r"burnt down|home burned|house burned|home burnt|house burnt|house total(?:ed|led)|"
        r"totalled|burnted down|gutted|severely burned|severe fire|major fire|major damage|"
        r"whole home|entire dwelling|not habitable|uninhabitable|red tagged|need(?:s)? to be rebuilt|"
        r"will need to be rebuilt|rebuild)\b"
    )

    unknown_cause = has(
        r"\b(?:unknown cause|cause unknown|cause.*unknown|unknown source|extent unknown|unknown details|"
        r"unknown how|no other information|no other info|unsure what happened|cause.*undetermined|"
        r"undetermined cause|unknown at this time|unknown how it started)\b"
    )

    attic_roof_exterior = has(
        r"\b(?:attic|roof|rafter|eave|soffit|fascia|siding|exterior wall|outside wall|porch|"
        r"crawlspace|crawl space|north side|side of.*home|root cellar)\b"
    )

    interior_room = has(
        r"\b(?:bedroom|bedrm|bathroom|living room|family room|dining room|laundry room|closet|"
        r"hallway|basement|upstairs|downstairs|room|floor|ceiling|wall|walls|interior|"
        r"carpet|rug|two levels|both levels|center of the home|contents|personal items)\b"
    )

    smoke_soot_water = has(
        r"\b(?:smoke|smk|soot|water damage|fire and water|smoke damage|soot damage|walls black)\b"
    )

    generic_dwelling = (
        has(
            r"\b(?:house fire|home fire|fire at home|fire to home|fire in home|fire damage to home|"
            r"fire damage to dwelling|dwelling fire|structure fire|residence fire|residential fire|"
            r"fire loss|fire damage|fire at residence|fire to residence|fire at the residence|"
            r"fire at insured(?:`|'|’)?s? (?:home|house|residence)|"
            r"fire to insured(?:`|'|’)?s? (?:home|house|residence)|"
            r"insured(?:`|'|’)?s? (?:home|house|residence).*fire|"
            r"(?:home|house|residence|dwelling|property|premises|building) caught (?:on )?fire|"
            r"fire @ insured dwelling|fire to house|fire in residence|fire to dwelling|"
            r"fire causing damage to dwelling|premises caught on fire|property was caught in fire|"
            r"house is on fire|home.*due to fire|fire at cottage|fire to the insured home|"
            r"damage to home.*fire|damages to home.*fire|fire damaged home|fire damaged.*home|"
            r"due to fire.*damage.*home|fire.*see notes|no addl info)\b"
        )
        | desc.eq("fire")
    )

    assign_category("Wildfire / vegetation / smoke-ash exposure", wildfire)
    assign_category("Kitchen / cooking", kitchen)
    assign_category("Garage / outbuilding / vehicle fire", garage_vehicle_outbuilding)
    assign_category("Heating / chimney / fireplace", heating)
    assign_category("Electrical / power", electrical)
    assign_category("Appliance / equipment", appliance_equipment)
    assign_category("External exposure / neighboring fire", external_exposure)
    assign_category("Open flame / smoking / BBQ / fireworks", open_flame)
    assign_category("Gas / propane / explosion", gas_explosion)
    assign_category("Arson / suspicious", arson)
    assign_category("Work activity / contractor", work_activity)
    assign_category("Outdoor / yard / trash fire", outdoor_yard)
    assign_category("Severe / total dwelling fire, source not stated", severe_total)
    assign_category("Unknown cause stated / limited details", unknown_cause)
    assign_category("Attic / roof / exterior fire, source not stated", attic_roof_exterior)
    assign_category("Interior room fire, source not stated", interior_room)
    assign_category("Smoke / soot / water damage, source not stated", smoke_soot_water)
    assign_category("Generic dwelling fire, no details", generic_dwelling)

    return df_claims
