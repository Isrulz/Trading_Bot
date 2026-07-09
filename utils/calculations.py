def get_point_size(symbol: str) -> float:
    """
    Returns the point size based on the symbol name:
    - 0.001 if JPY is in symbol
    - 0.01 if XAU is in symbol
    - 0.00001 otherwise
    """
    if not symbol:
        return 0.00001
    symbol_upper = symbol.upper()
    if 'JPY' in symbol_upper:
        return 0.001
    elif 'XAU' in symbol_upper:
        return 0.01
    else:
        return 0.00001
