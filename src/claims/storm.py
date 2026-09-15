"""Storm-specific claims category logic."""

import pandas as pd


def assign_primary_loss_category(df):
    """Add primary_loss_category for storm claims."""
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

    df_claims["primary_loss_category"] = "Other / unclear"
    assigned = pd.Series(False, index=df_claims.index)

    def assign_category(category, mask):
        nonlocal assigned
        m = mask & ~assigned
        df_claims.loc[m, "primary_loss_category"] = category
        assigned.loc[m] = True

    hail = has(r"\b(?:hail|hailstorm)\b")

    snow = has(
        r"\b(?:snow|snowstorm|ice|freeze|freezing|frozen|froze|frost|ice dam|icicle|sleet)\b"
    )

    surface_water = has(
        r"\b(?:flood|flooded|flooding|surface water|ground water|groundwater|mudslide|mud slide|mudflow|mud flow|mud overflow|landslide|landside|earth movement|ground shift|ground shifting|sink hole|sinkhole|subsidence|settlement|retaining|foundation crack|foundation cracked|foundation wall|through foundation|basement|run off|runoff|washed away|saturation of soil|soil|driveway.*sink|sinking|hill.*slipped|water and dirt)\b"
    )

    plumbing = has(
        r"\b(?:plumbing|pipe burst|burst pipe|water pipe|pipe under slab|drain pipe|sewer backup|sewer line|toilet|sink|shower|bathtub|bath tub|water heater|dishwasher|washing machine|washer supply|supply line|appliance)\b"
    )

    electrical = has(
        r"\b(?:lightning|lightening|lighting strike|power surge|surge|power outage|power out|power loss|electrical|electric|transformer|breaker|circuit|pg\s*(?:and|&)\s*e|pge|edison|power line|power lines|powerline|power pole|wires?|utility pole|food spoil|spoiled food)\b"
    )

    tree = has(
        r"\b(?:tree|trees|branch|branches|limb|limbs|redwood|oak|pine|eucalyptus|treebrances)\b"
    )

    fence = (
        has(r"\b(?:fence|fences|fencing|fenceing|fnce|fnece|gate|gates)\b")
        | has(r"\b(?:wood fnce|wooden fence|sections? completely down|sections? leaning)\b")
    )

    roof_no_water = (
        has(r"\b(?:building/roof damage,? no interior water damage|no interior water damage|no interior damage|no water damage)\b")
        & has(r"\b(?:roof|building|shingle|shingles)\b")
    )

    rainwater = has(
        r"\b(?:roof leak|roof leaking|leak in roof|leaking roof|leakg|leak|leaks|leaked|leaking|rain|rains|rainstorm|rainstorms|rainwater|rain water|water intrusion|water entered|water entering|water came|water coming|water running|water seeped|water seeping|water leakage|water in|water is coming|coming in(?:to)? the house|water found|water damage|water dmg|wtr damage|wtr dmg|water damaged|ceiling|ceilings|cieling|drywall|sheetrock|interior water|interior damage|inside|attic|moisture|mold|wet|soaked|dripping|wallpaper damp)\b"
    ) & ~roof_no_water

    roof = has(
        r"\b(?:roof|roofs|rf|shingle|shingles|shgles|gutter|gutters|flashing|fascia|soffit|skylight|tile roof|composition roof|roofing)\b"
    )

    other_exterior = has(
        r"\b(?:siding|stucco|window|windows|windw|garage door|garage|shed|deck|decking|patio|patios|awning|awnings|carport|pool|hot tub|outbuilding|outbldg|detached|chimney|screen|screens|door|doors|exterior|extior|building|dwelling|premises|structure|structures|wall|walls|porch|barn|metal shelter|sun room|satellite|sattelite)\b"
    )

    general_storm = has(
        r"\b(?:wind|winds|windstorm|storm|storms|stormy|debris|tarp|tarps|weather|blown|blew)\b"
    )

    assign_category("Hail damage", hail)
    assign_category("Snow / ice / freeze", snow)
    assign_category("Surface water / flood / earth movement", surface_water)
    assign_category("Plumbing / drain / appliance", plumbing)
    assign_category("Electrical / power / lightning", electrical)
    assign_category("Tree / branch impact", tree)
    assign_category("Fence / gate wind damage", fence)
    assign_category("Roof / shingle exterior damage", roof_no_water)
    assign_category("Rainwater / roof leak / interior water", rainwater)
    assign_category("Roof / shingle exterior damage", roof)
    assign_category("Other exterior structures", other_exterior)
    assign_category("General storm / wind damage", general_storm)

    return df_claims
