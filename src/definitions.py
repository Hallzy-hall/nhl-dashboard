even_strength_definitions = {
    "Line 1": ["LW1", "C1", "RW1"],
    "Line 2": ["LW2", "C2", "RW2"],
    "Line 3": ["LW3", "C3", "RW3"],
    "Line 4": ["LW4", "C4", "RW4"],
    "Pair 1": ["LD1", "RD1"],
    "Pair 2": ["LD2", "RD2"],
    "Pair 3": ["LD3", "RD3"]
}

pp_definitions = {
    # The keys are for display, the values are for database lookup
    "PP Unit 1": ["LWPP1", "CPP1", "RWPP1", "LDPP1", "RDPP1"],
    "PP Unit 2": ["LWPP2", "CPP2", "RWPP2", "LDPP2", "RDPP2"]
}

pk_definitions = {
    # The keys are for display, the values are for database lookup
    "PK Unit 1": ["CPK1", "WPK1", "LDPK1", "RDPK1"],
    "PK Unit 2": ["CPK2", "WPK2", "LDPK2", "RDPK2"]
}

# Combine all definitions into one dictionary for easier iteration
all_definitions = {**even_strength_definitions, **pp_definitions, **pk_definitions}

